#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyFlow Manager - Migración KNIME: GNS Estados de agentes

Objetivo
--------
Migrar el flujo KNIME "GNS Estados de agentes" a Python.

Lógica migrada desde KNIME:
1. Calcular intervalo de fechas.
2. Obtener token OAuth de Genesys Cloud.
3. Consultar usuarios existentes desde SAP HANA:
   SELECT DISTINCT ID AS userId FROM BI_SS.GNS_API_USUARIOS
4. Consultar definiciones de presencia:
   GET /api/v2/presence/definitions
5. Consultar estados de agentes:
   POST /api/v2/analytics/users/aggregates/query
6. Aplanar JSON:
   results[*] -> data[*] -> metrics[*]
7. Enriquecer QUALIFIER con presencia:
   QUALIFIER = presence.id
8. Agregar equivalencia para tAgentRoutingStatus + IDLE:
   ID = d4e7a3c1-b6e8-4f5a-92f9-c1b0f8a7e5d2
   TYPE = System
   LANGUAGELABELS = Inactivo No Responde
   SYSTEMPRESENCE = NotResponding
   DIVISIONID = *
9. Crear columnas:
   CONCAT = USERID-INTERVAL-METRIC-STARTTIME
   FECHA = substring(INTERVAL, 0, 10)
   HORA = substring(INTERVAL, 11, 5)
   FECHA_CARGA = fecha actual local
10. Insertar/actualizar en SAP HANA:
    BI_SS.GNS_API_USER_STATUS
    llave de merge: CONCAT

Notas importantes
-----------------
- Este script NO guarda secrets en archivos.
- Está preparado para PyFlow Manager usando variables globales y parámetros.
- Si DRY_RUN=true, no escribe en HANA; solo valida flujo y exporta CSV opcional.
- Para conexión SAP HANA requiere instalar: hdbcli
- Para Genesys requiere: requests
"""

import csv
import base64
import mimetypes
import math
import os
import sys
import time
import traceback
import re
from datetime import datetime, date, time as dt_time, timedelta, timezone
from html import escape
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import requests

try:
    import pandas as pd
except Exception:
    pd = None


PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {
        "type": "global",
        "global_key": "GENESYS_CLIENT_ID",
        "label": "Genesys Client ID",
        "required": True
    },
    "GENESYS_CLIENT_SECRET": {
        "type": "global",
        "global_key": "GENESYS_CLIENT_SECRET",
        "label": "Genesys Client Secret",
        "required": True,
        "secret": True
    },
    "GENESYS_REGION": {
        "type": "global",
        "global_key": "GENESYS_REGION",
        "label": "Genesys Region / Domain",
        "required": True
    },
    "HPR_HOST": {
        "type": "global",
        "global_key": "HPR_HOST",
        "label": "SAP HANA Host Escritura",
        "required": True
    },
    "HPR_HOST_ESPEJO": {
        "type": "global",
        "global_key": "HPR_HOST_ESPEJO",
        "label": "SAP HANA Host Espejo Lectura",
        "required": True
    },
    "HPR_PORT": {
        "type": "global",
        "global_key": "HPR_PORT",
        "label": "SAP HANA Port",
        "required": True
    },
    "HPR_USER": {
        "type": "global",
        "global_key": "HPR_USER",
        "label": "SAP HANA Service User",
        "required": True
    },
    "HPR_PASSWORD": {
        "type": "global",
        "global_key": "HPR_PASSWORD",
        "label": "SAP HANA Service Password",
        "required": True,
        "secret": True
    },
    "HANA_SCHEMA": {
        "type": "text",
        "label": "Esquema HANA",
        "required": True,
        "default": "BI_SS"
    },
    "USERS_TABLE": {
        "type": "text",
        "label": "Tabla de usuarios Genesys en HANA",
        "required": True,
        "default": "GNS_API_USUARIOS"
    },
    "TARGET_TABLE": {
        "type": "text",
        "label": "Tabla destino estados de agentes",
        "required": True,
        "default": "GNS_API_USER_STATUS"
    },
    "START_DATE": {
        "type": "date",
        "label": "Fecha inicial local",
        "required": False
    },
    "END_DATE": {
        "type": "date",
        "label": "Fecha final local",
        "required": False
    },
    "DAYS_BACK": {
        "type": "number",
        "label": "Días hacia atrás si no se indican fechas",
        "required": False,
        "default": "30"
    },
    "TIMEZONE": {
        "type": "text",
        "label": "Zona horaria",
        "required": True,
        "default": "America/Tegucigalpa"
    },
    "GRANULARITY": {
        "type": "select",
        "label": "Granularidad Genesys",
        "required": True,
        "options": ["PT30M", "PT15M", "PT1H"],
        "default": "PT30M"
    },
    "MAX_USERS": {
        "type": "number",
        "label": "Máximo usuarios para prueba; vacío = todos",
        "required": False
    },
    "REPORT_OUTPUT_FORMAT": {
        "type": "select",
        "label": "Generar archivo de reporte",
        "required": False,
        "options": ["csv", "xlsx"]
    },
    "ATTACH_REPORT_FILE": {
        "type": "select",
        "label": "Adjuntar archivo al correo",
        "required": False,
        "options": ["false", "true"],
        "default": "false"
    },
    "REPORT_OUTPUT_DIR": {
        "type": "text",
        "label": "Carpeta de salida del reporte",
        "required": False
    },
    "GRAPH_TENANT_ID": {"type": "global", "global_key": "GRAPH_TENANT_ID", "label": "Microsoft Graph Tenant ID", "required": False},
    "GRAPH_CLIENT_ID": {"type": "global", "global_key": "GRAPH_CLIENT_ID", "label": "Microsoft Graph Client ID", "required": False},
    "GRAPH_CLIENT_SECRET": {"type": "global", "global_key": "GRAPH_CLIENT_SECRET", "label": "Microsoft Graph Client Secret", "required": False, "secret": True},
    "GRAPH_SENDER_EMAIL": {"type": "global", "global_key": "GRAPH_SENDER_EMAIL", "label": "Correo remitente Graph", "required": False},
    "AGENT_STATUS_REPORT_EMAIL_TO": {"type": "tags", "label": "Destinatarios reporte estados", "required": False},
    "AGENT_STATUS_REPORT_EMAIL_CC": {"type": "tags", "label": "Copias reporte estados", "required": False},
    "AGENT_STATUS_REPORT_SUBJECT": {"type": "text", "label": "Asunto reporte estados", "required": False, "default": "Reporte de Estados de Agentes Genesys"}
}

STATUS_COLUMNS = ["CONCAT", "USERID", "STARTTIME", "INTERVAL", "METRIC", "QUALIFIER", "SUM", "ID", "TYPE", "LANGUAGELABELS", "SYSTEMPRESENCE", "DIVISIONID", "FECHA", "HORA", "FECHA_CARGA"]


def log(msg: str) -> None:
    print(msg, flush=True)


def env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default

    value = str(value).strip()

    # PyFlow/JSON puede enviar campos opcionales como texto "null" o "undefined".
    # Los tratamos como no informados para usar el default.
    if value == "" or value.lower() in ("null", "none", "undefined"):
        return default

    return value


def env_int(name: str, default: int) -> int:
    value = env_str(name, "")
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Parámetro {name} debe ser numérico. Valor recibido: {value!r}")


def env_bool(name: str, default: bool = False) -> bool:
    value = env_str(name, "")
    if not value:
        return default
    return value.lower() in ("1", "true", "yes", "si", "sí", "y")


def split_list_value(value: Any) -> List[str]:
    text = "" if value is None else str(value)
    text = text.replace("\r", "\n").replace(",", ";").replace("\n", ";")
    result: List[str] = []
    for item in text.split(";"):
        cleaned = item.strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def pyflow_progress(value: int) -> None:
    value = max(0, min(100, int(value)))
    print(f"PYFLOW_PROGRESS={value}", flush=True)


def require_env(name: str) -> str:
    value = env_str(name, "")
    if not value:
        raise RuntimeError(f"Falta variable/parámetro requerido: {name}")
    return value


def normalize_genesys_domain(region: str) -> str:
    region = region.strip()
    region = region.replace("https://", "").replace("http://", "")
    region = region.strip("/")
    if region.startswith("api."):
        region = region[4:]
    if region.startswith("login."):
        region = region[6:]
    return region


def build_genesys_urls(region: str) -> Tuple[str, str]:
    domain = normalize_genesys_domain(region)
    return f"https://login.{domain}", f"https://api.{domain}"


def local_date_to_utc_iso(local_day: date, tz: ZoneInfo) -> str:
    local_dt = datetime.combine(local_day, dt_time.min).replace(tzinfo=tz)
    utc_dt = local_dt.astimezone(timezone.utc)
    return utc_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def calculate_interval() -> Tuple[str, str, str, str]:
    tz_name = env_str("TIMEZONE", "America/Tegucigalpa")
    tz = ZoneInfo(tz_name)
    start_param = env_str("START_DATE", "")
    end_param = env_str("END_DATE", "")
    today_local = datetime.now(tz).date()

    if start_param and end_param:
        start_local = datetime.strptime(start_param, "%Y-%m-%d").date()
        end_local = datetime.strptime(end_param, "%Y-%m-%d").date()
    elif start_param and not end_param:
        start_local = datetime.strptime(start_param, "%Y-%m-%d").date()
        end_local = today_local
    else:
        days_back = env_int("DAYS_BACK", 30)
        end_local = today_local
        start_local = end_local - timedelta(days=days_back)

    if end_local <= start_local:
        raise ValueError("END_DATE debe ser mayor que START_DATE.")

    start_iso = local_date_to_utc_iso(start_local, tz)
    end_iso = local_date_to_utc_iso(end_local, tz)
    return start_iso, end_iso, start_local.isoformat(), end_local.isoformat()


def build_daily_windows(start_local: date, end_local: date, tz: ZoneInfo):
    """
    Genera ventanas diarias independientes para Genesys.

    Motivo:
    -------
    En KNIME el flujo trabajaba ventanas diarias. Al consultar varios días en
    una sola llamada agregada, Genesys puede devolver cortes que luego provocan
    diferencias al validar 24 horas por usuario/día.

    Ejemplo:
        start_local = 2026-05-27
        end_local   = 2026-05-30

    Produce:
        2026-05-27 -> 2026-05-28
        2026-05-28 -> 2026-05-29
        2026-05-29 -> 2026-05-30
    """
    current = start_local

    while current < end_local:
        next_day = current + timedelta(days=1)

        start_iso = local_date_to_utc_iso(current, tz)
        end_iso = local_date_to_utc_iso(next_day, tz)

        yield current.isoformat(), next_day.isoformat(), start_iso, end_iso

        current = next_day


def get_genesys_token(login_base_url: str, client_id: str, client_secret: str, timeout: int) -> str:
    url = f"{login_base_url}/oauth/token"
    response = requests.post(
        url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Error obteniendo token Genesys. HTTP {response.status_code}: {response.text[:500]}")
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Genesys no devolvió access_token.")
    return token


def request_json_with_retries(method: str, url: str, headers: Dict[str, str], timeout: int, max_retries: int = 3, **kwargs: Any) -> Dict[str, Any]:
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
            if response.status_code == 429:
                wait = int(response.headers.get("Retry-After", "5"))
                log(f"[WARN] Rate limit 429. Esperando {wait}s. Intento {attempt}/{max_retries}")
                time.sleep(wait)
                continue
            if response.status_code >= 500:
                wait = min(30, 2 ** attempt)
                log(f"[WARN] Error servidor {response.status_code}. Esperando {wait}s. Intento {attempt}/{max_retries}")
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP {response.status_code}: {response.text[:1000]}")
            return response.json() if response.text else {}
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            wait = min(30, 2 ** attempt)
            log(f"[WARN] Error HTTP: {exc}. Reintentando en {wait}s. Intento {attempt}/{max_retries}")
            time.sleep(wait)
    raise RuntimeError(f"Error consultando {url}: {last_error}")


def get_hana_connection(host_env_name: str, purpose: str):
    """
    Abre conexión SAP HANA según el propósito:
    - Lectura / SELECT: HPR_HOST_ESPEJO
    - Escritura / MERGE / INSERT / UPDATE / DELETE: HPR_HOST
    """
    try:
        from hdbcli import dbapi
    except Exception as exc:
        raise RuntimeError("No se pudo importar hdbcli. Instala el paquete: pip install hdbcli") from exc

    host = require_env(host_env_name)
    port = env_int("HPR_PORT", 30015)
    user = require_env("HPR_USER")
    password = require_env("HPR_PASSWORD")
    log(f"[INFO] Conectando a SAP HANA {host}:{port} con usuario {user} | propósito: {purpose}")
    return dbapi.connect(address=host, port=port, user=user, password=password)


def get_hana_connection_read():
    return get_hana_connection("HPR_HOST_ESPEJO", "LECTURA / SELECT")


def get_hana_connection_write():
    return get_hana_connection("HPR_HOST", "ESCRITURA / MERGE")


def validate_identifier(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""):
        raise ValueError(f"Identificador SQL inválido: {value}")


def fetch_user_ids(conn) -> List[str]:
    schema = env_str("HANA_SCHEMA", "BI_SS")
    users_table = env_str("USERS_TABLE", "GNS_API_USUARIOS")
    validate_identifier(schema)
    validate_identifier(users_table)
    max_users = env_str("MAX_USERS", "")
    sql = f'''
        SELECT DISTINCT ID AS "USERID"
        FROM "{schema}"."{users_table}"
        WHERE ID IS NOT NULL
          AND TRIM(ID) <> ''
    '''
    if max_users:
        sql += f"\nLIMIT {int(max_users)}"
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return [str(r[0]) for r in cur.fetchall()]
    finally:
        cur.close()


def fetch_presence_definitions(api_base_url: str, headers: Dict[str, str], timeout: int) -> Dict[str, Dict[str, str]]:
    url = f"{api_base_url}/api/v2/presence/definitions"
    payload = request_json_with_retries("GET", url, headers=headers, timeout=timeout)
    definitions: Dict[str, Dict[str, str]] = {}
    for entity in payload.get("entities", []) or []:
        presence_id = str(entity.get("id", "") or "")
        if not presence_id:
            continue
        language_labels = entity.get("languageLabels") or {}
        definitions[presence_id] = {
            "ID": presence_id,
            "TYPE": str(entity.get("type", "") or ""),
            "LANGUAGELABELS": str(language_labels.get("es") or language_labels.get("es-es") or language_labels.get("en_US") or language_labels.get("en") or ""),
            "SYSTEMPRESENCE": str(entity.get("systemPresence", "") or ""),
            "DIVISIONID": str(entity.get("divisionId", "") or "")
        }

    definitions["IDLE"] = {
        "ID": "d4e7a3c1-b6e8-4f5a-92f9-c1b0f8a7e5d2",
        "TYPE": "System",
        "LANGUAGELABELS": "Inactivo No Responde",
        "SYSTEMPRESENCE": "NotResponding",
        "DIVISIONID": "*"
    }
    return definitions


def chunks(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def build_analytics_body(user_ids: List[str], start_iso: str, end_iso: str) -> Dict[str, Any]:
    return {
        "interval": f"{start_iso}/{end_iso}",
        "granularity": env_str("GRANULARITY", "PT30M"),
        "timeZone": env_str("TIMEZONE", "America/Tegucigalpa"),
        "groupBy": ["userId"],
        "filter": {
            "type": "or",
            "predicates": [{"dimension": "userId", "value": user_id} for user_id in user_ids]
        },
        "metrics": ["tAgentRoutingStatus", "tOrganizationPresence", "tSystemPresence"],
        "flattenMultivaluedDimensions": True,
        "alternateTimeDimension": "eventTime"
    }


def flatten_analytics_response(payload: Dict[str, Any], presence_map: Dict[str, Dict[str, str]], fecha_carga: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in payload.get("results", []) or []:
        user_id = str(((result.get("group") or {}).get("userId")) or "")
        start_time = str(result.get("startTime") or "")
        for data_item in result.get("data", []) or []:
            interval = str(data_item.get("interval") or "")
            for metric_item in data_item.get("metrics", []) or []:
                metric = str(metric_item.get("metric") or "")
                qualifier = str(metric_item.get("qualifier") or "")
                stats = metric_item.get("stats") or {}
                sum_value = stats.get("sum")
                if sum_value is None:
                    sum_value = 0
                presence_key = "IDLE" if metric == "tAgentRoutingStatus" and qualifier == "IDLE" else qualifier
                presence = presence_map.get(presence_key, {})
                interval_start_utc = interval.split("/")[0] if "/" in interval else interval
                interval_end_utc = interval.split("/")[1] if "/" in interval else ""

                tz = ZoneInfo(env_str("TIMEZONE", "America/Tegucigalpa"))

                def utc_iso_to_local_str(value: str) -> str:
                    if not value:
                        return ""
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")

                start_time = utc_iso_to_local_str(interval_start_utc)
                end_time = utc_iso_to_local_str(interval_end_utc)
                fecha = start_time[0:10] if len(start_time) >= 10 else ""
                hora = start_time[11:16] if len(start_time) >= 16 else ""
                concat = f"{user_id}-{interval}-{metric}-{qualifier}-{start_time}"
                rows.append({
                    "CONCAT": concat,
                    "USERID": user_id,
                    "STARTTIME": start_time,
                    "INTERVAL": interval,
                    "METRIC": metric,
                    "QUALIFIER": qualifier,
                    "SUM": str(sum_value),
                    "ID": presence.get("ID", ""),
                    "TYPE": presence.get("TYPE", ""),
                    "LANGUAGELABELS": presence.get("LANGUAGELABELS", ""),
                    "SYSTEMPRESENCE": presence.get("SYSTEMPRESENCE", ""),
                    "DIVISIONID": presence.get("DIVISIONID", ""),
                    "FECHA": fecha,
                    "HORA": hora,
                    "FECHA_CARGA": fecha_carga
                })
    return rows


def fetch_agent_status_rows(
    api_base_url: str,
    headers: Dict[str, str],
    user_ids: List[str],
    presence_map: Dict[str, Dict[str, str]],
    start_iso: str,
    end_iso: str,
    timeout: int,
    progress_start: int = 25,
    progress_end: int = 75
) -> List[Dict[str, Any]]:
    url = f"{api_base_url}/api/v2/analytics/users/aggregates/query"
    batch_size = env_int("BATCH_SIZE_USERS", 50)
    fecha_carga = datetime.now(ZoneInfo(env_str("TIMEZONE", "America/Tegucigalpa"))).date().isoformat()
    all_rows: List[Dict[str, Any]] = []
    total_batches = math.ceil(len(user_ids) / batch_size) if user_ids else 0
    for idx, batch in enumerate(chunks(user_ids, batch_size), start=1):
        log(f"[INFO] Consultando Genesys batch {idx}/{total_batches}. Usuarios: {len(batch)}")
        body = build_analytics_body(batch, start_iso, end_iso)
        payload = request_json_with_retries("POST", url, headers=headers, timeout=timeout, json=body)
        rows = flatten_analytics_response(payload, presence_map, fecha_carga)
        all_rows.extend(rows)
        log(f"[INFO] Filas obtenidas batch {idx}: {len(rows)}")
        progress = progress_start + int((idx / max(total_batches, 1)) * (progress_end - progress_start))
        pyflow_progress(progress)
    return all_rows


def write_csv(rows: List[Dict[str, Any]], output_csv: str) -> None:
    if not output_csv:
        return

    # Si el usuario ingresa solo una carpeta, generamos un nombre de archivo automáticamente.
    # Ejemplo: C:\\Temp -> C:\\Temp\\GNS_Estados_Agentes_20260530_143000.csv
    if os.path.isdir(output_csv) or output_csv.endswith("\\") or output_csv.endswith("/"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = os.path.join(output_csv, f"GNS_Estados_Agentes_{timestamp}.csv")

    output_dir = os.path.dirname(output_csv)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    columns = STATUS_COLUMNS
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    log(f"[INFO] CSV generado: {output_csv}")


def output_directory() -> str:
    path = env_str("REPORT_OUTPUT_DIR", "") or os.getcwd()
    os.makedirs(path, exist_ok=True)
    return path


def write_report_file(rows: List[Dict[str, Any]]) -> Optional[str]:
    report_format = env_str("REPORT_OUTPUT_FORMAT", "").lower()
    if not report_format and env_bool("ATTACH_REPORT_FILE", False):
        report_format = "xlsx"
    if not report_format:
        return None
    if report_format not in ("csv", "xlsx"):
        log(f"[WARN] REPORT_OUTPUT_FORMAT invÃ¡lido: {report_format}. No se generarÃ¡ archivo.")
        return None
    if not rows:
        log("[WARN] No hay filas para generar reporte de estados de agentes.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_directory(), f"GNS_Estados_Agentes_{timestamp}.{report_format}")

    if report_format == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=STATUS_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    else:
        if pd is None:
            raise RuntimeError("Para generar Excel instala pandas y openpyxl: pip install pandas openpyxl")
        pd.DataFrame(rows, columns=STATUS_COLUMNS).to_excel(path, index=False)

    log(f"[INFO] Archivo de reporte generado: {path} | filas: {len(rows)}")
    return path


def build_file_attachment(path: str) -> Dict[str, str]:
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": os.path.basename(path),
        "contentType": content_type,
        "contentBytes": content,
    }


def merge_rows_hana(conn, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        log("[INFO] No hay filas para insertar/actualizar en HANA.")
        return
    schema = env_str("HANA_SCHEMA", "BI_SS")
    target_table = env_str("TARGET_TABLE", "GNS_API_USER_STATUS")
    validate_identifier(schema)
    validate_identifier(target_table)
    columns = STATUS_COLUMNS
    select_cols = ", ".join([f'? AS "{c}"' for c in columns])
    update_cols = ", ".join([f'T."{c}" = S."{c}"' for c in columns if c != "CONCAT"])
    insert_cols = ", ".join([f'"{c}"' for c in columns])
    insert_values = ", ".join([f'S."{c}"' for c in columns])
    sql = f'''
        MERGE INTO "{schema}"."{target_table}" AS T
        USING (
            SELECT {select_cols}
            FROM DUMMY
        ) AS S
        ON T."CONCAT" = S."CONCAT"
        WHEN MATCHED THEN
            UPDATE SET {update_cols}
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({insert_values})
    '''
    values = [tuple(row.get(col, "") for col in columns) for row in rows]
    cur = conn.cursor()
    try:
        log(f"[INFO] Insertando/actualizando {len(values)} filas en {schema}.{target_table}")
        cur.executemany(sql, values)
        conn.commit()
        log("[INFO] Merge completado correctamente.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


def get_graph_access_token(timeout: int) -> str:
    tenant_id = env_str("GRAPH_TENANT_ID", "")
    client_id = env_str("GRAPH_CLIENT_ID", "")
    client_secret = env_str("GRAPH_CLIENT_SECRET", "")

    if not tenant_id or not client_id or not client_secret:
        raise RuntimeError("Configura GRAPH_TENANT_ID, GRAPH_CLIENT_ID y GRAPH_CLIENT_SECRET para enviar el reporte por Microsoft Graph.")

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    response = requests.post(
        url,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    if response.status_code >= 400:
        log(f"[ERROR] Error obteniendo token Graph {response.status_code} | {response.text[:1000]}")
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Microsoft Graph no devolviÃ³ access_token.")
    return token


def build_agent_status_report_html(total_users: int, total_rows: int, loaded: bool, date_range: str, duration_seconds: float) -> str:
    now = datetime.now(ZoneInfo(env_str("TIMEZONE", "America/Tegucigalpa")))
    return f"""<!doctype html>
<html lang="es">
<body style="margin:0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif;color:#334155;">
  <table width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;padding:40px 10px;">
    <tr>
      <td align="center">
        <table width="100%" cellspacing="0" cellpadding="0" style="max-width:650px;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
          <tr>
            <td style="background:#DA282D;padding:36px 40px;color:#ffffff;">
              <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:#fecaca;">Sistema de monitoreo de procesos</div>
              <h1 style="margin:8px 0 0;font-size:24px;line-height:1.2;">Reporte de Estados de Agentes</h1>
              <p style="margin:8px 0 0;font-size:13px;color:#fecaca;">Reporte automÃ¡tico generado por PyFlow Manager</p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px;">
              <p style="margin:0 0 24px;font-size:14px;line-height:1.6;">Se ha completado la ejecuciÃ³n del proceso de estados de agentes. A continuaciÃ³n se presenta el resumen del periodo procesado.</p>
              <table width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Usuarios consultados</div>
                    <div style="font-size:26px;font-weight:700;color:#1e293b;margin-top:8px;">{total_users:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Desde HANA espejo</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#DA282D;text-transform:uppercase;">Filas transformadas</div>
                    <div style="font-size:26px;font-weight:700;color:#DA282D;margin-top:8px;">{total_rows:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Registros obtenidos</div>
                  </td>
                </tr>
              </table>
              <div style="margin-top:24px;border-left:3px solid #DA282D;padding-left:16px;font-size:13px;line-height:1.5;color:#64748b;">
                <strong>Periodo:</strong> {escape(date_range)}<br />
                <strong>Carga HANA:</strong> {"Completada" if loaded else "No ejecutada"}<br />
                <strong>DuraciÃ³n:</strong> {duration_seconds:.2f} segundos
              </div>
              <div style="margin-top:28px;border-top:1px solid #f1f5f9;padding-top:22px;font-size:12px;color:#64748b;">
                Fecha de ejecuciÃ³n: <strong>{escape(now.strftime("%d/%m/%Y"))}</strong><br />
                Hora de ejecuciÃ³n: <strong>{escape(now.strftime("%I:%M %p"))}</strong>
              </div>
            </td>
          </tr>
          <tr>
            <td align="center" style="background:#f1f5f9;padding:20px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;">Este es un correo automÃ¡tico generado por PyFlow Manager.</td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def enviar_reporte_estados(total_users: int, total_rows: int, loaded: bool, date_range: str, duration_seconds: float, report_file: Optional[str], timeout: int) -> bool:
    recipients = split_list_value(env_str("AGENT_STATUS_REPORT_EMAIL_TO", ""))
    cc = split_list_value(env_str("AGENT_STATUS_REPORT_EMAIL_CC", ""))
    sender = env_str("GRAPH_SENDER_EMAIL", "")

    if not recipients:
        log("[INFO] Reporte por correo no enviado: no hay destinatarios en AGENT_STATUS_REPORT_EMAIL_TO.")
        return False
    if not sender:
        log("[WARN] Reporte por correo no enviado: configura GRAPH_SENDER_EMAIL.")
        return False

    payload = {
        "message": {
            "subject": env_str("AGENT_STATUS_REPORT_SUBJECT", "Reporte de Estados de Agentes Genesys"),
            "body": {"contentType": "HTML", "content": build_agent_status_report_html(total_users, total_rows, loaded, date_range, duration_seconds)},
            "toRecipients": [{"emailAddress": {"address": email}} for email in recipients],
            "ccRecipients": [{"emailAddress": {"address": email}} for email in cc],
        },
        "saveToSentItems": "true",
    }

    if env_bool("ATTACH_REPORT_FILE", False) and report_file:
        payload["message"]["attachments"] = [build_file_attachment(report_file)]
    elif env_bool("ATTACH_REPORT_FILE", False) and not report_file:
        log("[WARN] Se solicitÃ³ adjuntar archivo, pero no se generÃ³ ningÃºn reporte para adjuntar.")

    try:
        token = get_graph_access_token(timeout)
        url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=timeout,
        )
        if response.status_code >= 400:
            log(f"[ERROR] Error enviando reporte Graph {response.status_code} | {response.text[:1000]}")
        response.raise_for_status()
        log(f"[INFO] Reporte de estados enviado a: {', '.join(recipients + cc)}")
        return True
    except Exception as exc:
        log(f"[ERROR] No se pudo enviar reporte de estados: {exc}")
        return False


def main() -> int:
    start_time = time.time()
    total_users = 0
    total_rows = 0
    hana_loaded = False
    report_file: Optional[str] = None
    date_range = ""

    log("[INFO] Iniciando migracion KNIME -> Python: GNS Estados de agentes")
    pyflow_progress(2)
    client_id = require_env("GENESYS_CLIENT_ID")
    client_secret = require_env("GENESYS_CLIENT_SECRET")
    region = require_env("GENESYS_REGION")
    timeout = env_int("REQUEST_TIMEOUT_SECONDS", 60)
    start_iso, end_iso, start_local, end_local = calculate_interval()
    date_range = f"{start_local} -> {end_local}"
    log(f"[INFO] Intervalo local: {start_local} -> {end_local}")
    log(f"[INFO] Intervalo UTC Genesys: {start_iso}/{end_iso}")
    login_base_url, api_base_url = build_genesys_urls(region)
    dry_run = False
    conn_read = None
    conn_write = None

    try:
        pyflow_progress(5)
        token = get_genesys_token(login_base_url, client_id, client_secret, timeout)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        log("[INFO] Token Genesys obtenido correctamente.")
        pyflow_progress(10)

        conn_read = get_hana_connection_read()
        user_ids = fetch_user_ids(conn_read)
        total_users = len(user_ids)
        log(f"[INFO] Usuarios leidos desde HANA espejo: {len(user_ids)}")
        pyflow_progress(15)
        try:
            conn_read.close()
            conn_read = None
        except Exception:
            pass

        if not user_ids:
            log("[WARN] No se encontraron usuarios en HANA espejo. Finalizando.")
            pyflow_progress(100)
            return 0

        presence_map = fetch_presence_definitions(api_base_url, headers, timeout)
        log(f"[INFO] Definiciones de presencia obtenidas: {len(presence_map)}")
        pyflow_progress(20)

        all_rows: List[Dict[str, Any]] = []
        tz = ZoneInfo(env_str("TIMEZONE", "America/Tegucigalpa"))
        start_date_obj = datetime.strptime(start_local, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_local, "%Y-%m-%d").date()
        windows = list(build_daily_windows(start_date_obj, end_date_obj, tz))

        for day_index, (day_start, day_end, day_start_iso, day_end_iso) in enumerate(windows, start=1):
            log(f"[INFO] Procesando dia local: {day_start} -> {day_end}")
            log(f"[INFO] Intervalo UTC Genesys dia: {day_start_iso}/{day_end_iso}")
            segment_start = 20 + int(((day_index - 1) / max(len(windows), 1)) * 55)
            segment_end = 20 + int((day_index / max(len(windows), 1)) * 55)

            day_rows = fetch_agent_status_rows(
                api_base_url,
                headers,
                user_ids,
                presence_map,
                day_start_iso,
                day_end_iso,
                timeout,
                segment_start,
                segment_end,
            )

            log(f"[INFO] Filas transformadas dia {day_start}: {len(day_rows)}")
            all_rows.extend(day_rows)
            time.sleep(2)

        rows = all_rows
        total_rows = len(rows)
        log(f"[INFO] Total filas transformadas: {len(rows)}")

        report_file = write_report_file(rows)
        pyflow_progress(80)

        if dry_run:
            log("[INFO] DRY_RUN=true. No se insertara informacion en HANA.")
            return 0

        conn_write = get_hana_connection_write()
        merge_rows_hana(conn_write, rows)
        hana_loaded = True
        pyflow_progress(92)

        duration = time.time() - start_time
        enviar_reporte_estados(total_users, total_rows, hana_loaded, date_range, duration, report_file, timeout)
        pyflow_progress(100)
        log("[INFO] Proceso finalizado exitosamente.")
        return 0
    except Exception as exc:
        log(f"[ERROR] {exc}")
        traceback.print_exc()
        return 1
    finally:
        for conn in (conn_read, conn_write):
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

if __name__ == "__main__":
    sys.exit(main())
