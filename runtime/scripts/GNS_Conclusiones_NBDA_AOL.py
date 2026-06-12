# =========================================================
# GNS Reporte Conclusiones NBDA / AOL
# =========================================================
#
# OBJETIVO
# Extrae desde Genesys Cloud el rendimiento de códigos de conclusión
# que comienzan con:
#   - NBDA_
#   - CONSULTA_AOL_
#   - CONSULTAS_AOL_
#   - GESTIONES_AOL_
#   - NBDA_
#   - SOPORTE_TÉCNICO_AOL_
#   - SOPORTE_AOL_
#
# Genera un Excel con:
#   1. Resumen tipo tabla dinámica
#   2. Conclusiones AOL acumuladas por día/mes
#   3. Conclusiones NBDA acumuladas por día/mes
#
# Opcionalmente envía correo con el Excel adjunto.
#
# =========================================================
# FORMAS DE EJECUCIÓN
# =========================================================
#
# 1. Ejecución automática:
#    Desde el día 5 del mes actual a la fecha/hora actual.
#
#    py .\GNS_Conclusiones_NBDA_AOL.py
#
# 2. Una fecha específica:
#
#    py .\GNS_Conclusiones_NBDA_AOL.py --date 2026-05-27
#
# 3. Rango de fechas local:
#
#    py .\GNS_Conclusiones_NBDA_AOL.py --start-date 2026-05-05 --end-date 2026-05-27
#
# 4. UTC exacto:
#
#    py .\GNS_Conclusiones_NBDA_AOL.py --start-utc 2026-05-05T06:00:00.000Z --end-utc 2026-05-28T06:00:00.000Z
#
# 5. Enviar correo:
#
#    py .\GNS_Conclusiones_NBDA_AOL.py --send-email --to "correo@dominio.com"
#
# 6. Solo generar Excel, sin correo:
#
#    py .\GNS_Conclusiones_NBDA_AOL.py
#
# =========================================================
# VARIABLES .ENV REQUERIDAS
# =========================================================
#
# GENESYS_CLIENT_ID=
# GENESYS_CLIENT_SECRET=
# GENESYS_REGION_URL=https://api.mypurecloud.com
# GENESYS_LOGIN_URL=https://login.mypurecloud.com/oauth/token
# GENESYS_TIMEZONE=America/Tegucigalpa
#
# Opcional para correo por Microsoft Graph API:
#
# GRAPH_TENANT_ID=
# GRAPH_CLIENT_ID=
# GRAPH_CLIENT_SECRET=
# GRAPH_SENDER_EMAIL=correo_remitente@dominio.com
# GRAPH_AUTHORITY_URL=https://login.microsoftonline.com
# GRAPH_SCOPE=https://graph.microsoft.com/.default
# GRAPH_SAVE_TO_SENT_ITEMS=true
#
# Requiere permiso Application: Microsoft Graph / Mail.Send
# con Admin Consent aprobado.
#
# =========================================================

import os
import sys
import time
import argparse
import logging
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path

import base64
import requests
import pandas as pd


# =========================================================
# PYFLOW MANAGER PARAMS
# =========================================================
# IMPORTANTE:
# Mantener este bloque simple y al inicio para que PyFlow lo detecte.

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
    "DATE": {
        "type": "date",
        "label": "Fecha específica local",
        "required": False
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
    "START_UTC": {
        "type": "text",
        "label": "Inicio UTC exacto",
        "required": False
    },
    "END_UTC": {
        "type": "text",
        "label": "Fin UTC exacto",
        "required": False
    },
    "AUTO_START_DAY": {
        "type": "number",
        "label": "Día inicial automático del mes",
        "required": False,
        "default": "5"
    },
    "GENESYS_TIMEZONE": {
        "type": "text",
        "label": "Zona horaria Genesys",
        "required": True,
        "default": "America/Tegucigalpa"
    },
    "OUTPUT_DIR": {
        "type": "text",
        "label": "Carpeta de salida del Excel",
        "required": False,
        "default": "runtime/exports"
    },
    "REPORT_TYPE": {
        "type": "select",
        "label": "Tipo de datos a generar",
        "required": True,
        "options": ["Reporte consolidado", "Data", "Consolidado + Data"],
        "default": "Reporte consolidado"
    },
    "PAGE_SIZE": {
        "type": "number",
        "label": "Tamaño página Genesys",
        "required": False,
        "default": "100"
    },
    "REQUEST_TIMEOUT": {
        "type": "number",
        "label": "Timeout HTTP segundos",
        "required": False,
        "default": "120"
    },
    "API_SLEEP_SECONDS": {
        "type": "number",
        "label": "Pausa entre requests",
        "required": False,
        "default": "1"
    },
    "MAX_RETRIES": {
        "type": "number",
        "label": "Reintentos HTTP",
        "required": False,
        "default": "5"
    },
    "WRAPUP_FILTER_CHUNK_SIZE": {
        "type": "number",
        "label": "Cantidad de wrapups por bloque",
        "required": False,
        "default": "20"
    },
    "SEND_EMAIL": {
        "type": "select",
        "label": "Enviar correo",
        "required": True,
        "options": ["true", "false"],
        "default": "false"
    },
    "EMAIL_TO": {
        "type": "text",
        "label": "Destinatarios Para separados por coma",
        "required": False
    },
    "EMAIL_CC": {
        "type": "text",
        "label": "Destinatarios CC separados por coma",
        "required": False
    },
    "EMAIL_SUBJECT": {
        "type": "text",
        "label": "Asunto del correo",
        "required": False,
        "default": "Reporte de Conclusiones NBDA y AOL"
    },
    "EMAIL_BODY_HTML": {
        "type": "text",
        "label": "Body HTML del correo",
        "required": False,
        "default": ""
    },
    "INCLUDE_SUMMARY_TABLE_IN_EMAIL": {
        "type": "select",
        "label": "Incluir tabla resumen en correo",
        "required": True,
        "options": ["true", "false"],
        "default": "true"
    },
    "GRAPH_TENANT_ID": {
        "type": "global",
        "global_key": "GRAPH_TENANT_ID",
        "label": "Microsoft Graph Tenant ID",
        "required": False
    },
    "GRAPH_CLIENT_ID": {
        "type": "global",
        "global_key": "GRAPH_CLIENT_ID",
        "label": "Microsoft Graph Client ID",
        "required": False
    },
    "GRAPH_CLIENT_SECRET": {
        "type": "global",
        "global_key": "GRAPH_CLIENT_SECRET",
        "label": "Microsoft Graph Client Secret",
        "required": False,
        "secret": True
    },
    "GRAPH_SENDER_EMAIL": {
        "type": "global",
        "global_key": "GRAPH_SENDER_EMAIL",
        "label": "Correo remitente Graph",
        "required": False
    },
    "GRAPH_AUTHORITY_URL": {
        "type": "text",
        "label": "Microsoft Authority URL",
        "required": False,
        "default": "https://login.microsoftonline.com"
    },
    "GRAPH_SCOPE": {
        "type": "text",
        "label": "Microsoft Graph Scope",
        "required": False,
        "default": "https://graph.microsoft.com/.default"
    },
    "GRAPH_SAVE_TO_SENT_ITEMS": {
        "type": "select",
        "label": "Guardar en enviados",
        "required": False,
        "options": ["true", "false"],
        "default": "true"
    },
    "DRY_RUN": {
        "type": "select",
        "label": "Modo prueba, genera Excel pero no envía correo",
        "required": True,
        "options": ["true", "false"],
        "default": "false"
    }
}

LOGGER_NAME = "gns_conclusiones_nbda_aol_pyflow"


def _clean_env_value(value: Any, default: Optional[str] = None) -> Optional[str]:
    """Normaliza valores recibidos desde PyFlow: vacío, null, none y undefined."""
    if value is None:
        return default
    text = str(value).strip()
    if text == "" or text.lower() in ("null", "none", "undefined"):
        return default
    return text


def env_str(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = _clean_env_value(os.getenv(name), default)
    if required and not value:
        raise RuntimeError(f"Falta configurar variable/parámetro requerido: {name}")
    return "" if value is None else str(value)


def env_int(name: str, default: int, required: bool = False) -> int:
    value = env_str(name, str(default), required=required)
    try:
        return int(value)
    except Exception:
        raise ValueError(f"El parámetro {name} debe ser numérico. Valor recibido: {value!r}")


def env_float(name: str, default: float, required: bool = False) -> float:
    value = env_str(name, str(default), required=required)
    try:
        return float(value)
    except Exception:
        raise ValueError(f"El parámetro {name} debe ser numérico. Valor recibido: {value!r}")


def env_bool(name: str, default: bool = False) -> bool:
    value = env_str(name, "", required=False).lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "y", "si", "sí")


def normalize_genesys_domain(value: str) -> str:
    """Acepta mypurecloud.com, api.mypurecloud.com, login.mypurecloud.com o URL completa."""
    value = str(value or "mypurecloud.com").strip()
    value = value.replace("https://", "").replace("http://", "").strip("/")
    if value.startswith("api."):
        value = value[4:]
    if value.startswith("login."):
        value = value[6:]
    return value


def genesys_api_url_from_region() -> str:
    domain = normalize_genesys_domain(env_str("GENESYS_REGION", "mypurecloud.com"))
    return f"https://api.{domain}"


def genesys_login_url_from_region() -> str:
    domain = normalize_genesys_domain(env_str("GENESYS_REGION", "mypurecloud.com"))
    return f"https://login.{domain}/oauth/token"


def log_params(logger: logging.Logger, names: List[str]) -> None:
    logger.info("Parámetros recibidos / aplicados:")
    secret_words = ("SECRET", "PASSWORD", "TOKEN", "KEY")
    for name in names:
        value = env_str(name, "")
        if any(w in name.upper() for w in secret_words) and value:
            value = "********"
        logger.info("- %s: %s", name, value if value else "<vacío>")


@dataclass
class Config:
    genesys_client_id: str
    genesys_client_secret: str
    genesys_region_base_url: str
    genesys_login_url: str
    timezone_name: str
    request_timeout: int
    api_sleep_seconds: float
    max_retries: int
    page_size: int
    output_dir: str
    graph_tenant_id: str
    graph_client_id: str
    graph_client_secret: str
    graph_sender_email: str
    graph_authority_url: str
    graph_scope: str
    graph_save_to_sent_items: bool



def load_config() -> Config:
    return Config(
        genesys_client_id=env_str("GENESYS_CLIENT_ID", required=True),
        genesys_client_secret=env_str("GENESYS_CLIENT_SECRET", required=True),
        genesys_region_base_url=genesys_api_url_from_region(),
        genesys_login_url=genesys_login_url_from_region(),
        timezone_name=env_str("GENESYS_TIMEZONE", "America/Tegucigalpa"),
        request_timeout=env_int("REQUEST_TIMEOUT", 120),
        api_sleep_seconds=env_float("API_SLEEP_SECONDS", 1.0),
        max_retries=env_int("MAX_RETRIES", 5),
        page_size=env_int("PAGE_SIZE", 100),
        output_dir=env_str("OUTPUT_DIR", "runtime/exports"),
        graph_tenant_id=env_str("GRAPH_TENANT_ID", ""),
        graph_client_id=env_str("GRAPH_CLIENT_ID", ""),
        graph_client_secret=env_str("GRAPH_CLIENT_SECRET", ""),
        graph_sender_email=env_str("GRAPH_SENDER_EMAIL", ""),
        graph_authority_url=env_str("GRAPH_AUTHORITY_URL", "https://login.microsoftonline.com").rstrip("/"),
        graph_scope=env_str("GRAPH_SCOPE", "https://graph.microsoft.com/.default"),
        graph_save_to_sent_items=env_bool("GRAPH_SAVE_TO_SENT_ITEMS", True),
    )


def setup_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger

def to_utc_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def parse_interval_start_to_local_date(value: str, tz_name: str) -> Tuple[str, int, int, int]:
    """
    Convierte el Inicio del intervalo de Genesys a fecha local.
    Retorna:
      fecha_dd_mm_yyyy, dia, mes, anio
    """
    if not value:
        return "", 0, 0, 0

    tz = ZoneInfo(tz_name)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(tz)

    return (
        dt.strftime("%d/%m/%Y"),
        dt.day,
        dt.month,
        dt.year
    )


def parse_dates(args: argparse.Namespace, tz_name: str) -> Tuple[str, str, str, datetime, datetime]:
    tz = ZoneInfo(tz_name)

    if args.start_utc and args.end_utc:
        start_dt = datetime.fromisoformat(args.start_utc.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(args.end_utc.replace("Z", "+00:00"))
        return args.start_utc, args.end_utc, "UTC manual", start_dt.astimezone(tz), end_dt.astimezone(tz)

    if args.date:
        d = date.fromisoformat(args.date)
        start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        return to_utc_z(start_local), to_utc_z(end_local), f"Día local {args.date}", start_local, end_local

    if args.start_date:

        d1 = date.fromisoformat(args.start_date)

        start_local = datetime(
            d1.year,
            d1.month,
            d1.day,
            0,
            0,
            0,
            tzinfo=tz
        )

        if not args.end_date:

            end_local = datetime.now(tz)

            return (
                to_utc_z(start_local),
                to_utc_z(end_local),
                f"Desde {args.start_date} hasta fecha/hora actual",
                start_local,
                end_local
            )

        d2 = date.fromisoformat(args.end_date)

        if d2 < d1:
            raise ValueError("La fecha final no puede ser menor que la fecha inicial.")

        today_local = datetime.now(tz).date()

        if d2 == today_local:
            end_local = datetime.now(tz)
        else:
            end_local = datetime(d2.year, d2.month, d2.day, 0, 0, 0, tzinfo=tz) + timedelta(days=1)

        return (
            to_utc_z(start_local),
            to_utc_z(end_local),
            f"Rango local {args.start_date} al {args.end_date}",
            start_local,
            end_local
        )

    # Automático PyFlow: desde el día configurado del mes actual hasta la fecha/hora actual.
    # Por defecto inicia el día 5, igual que la ejecución manual original.
    auto_start_day = env_int("AUTO_START_DAY", 5)
    if auto_start_day < 1 or auto_start_day > 28:
        raise ValueError("AUTO_START_DAY debe estar entre 1 y 28.")

    now_local = datetime.now(tz)
    start_local = datetime(now_local.year, now_local.month, auto_start_day, 0, 0, 0, tzinfo=tz)
    end_local = now_local

    return (
        to_utc_z(start_local),
        to_utc_z(end_local),
        f"Automático desde día {auto_start_day} del mes actual a fecha/hora actual",
        start_local,
        end_local
    )


def genesys_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def request_with_retries(
    method: str,
    url: str,
    config: Config,
    logger: logging.Logger,
    **kwargs
) -> requests.Response:

    last_exc = None

    for attempt in range(1, config.max_retries + 1):
        try:
            response = requests.request(
                method,
                url,
                timeout=config.request_timeout,
                **kwargs
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(60, attempt * 10)

                logger.warning(
                    "Rate limit 429 | intento %s/%s | esperando %s segundos...",
                    attempt,
                    config.max_retries,
                    wait_seconds
                )

                time.sleep(wait_seconds)
                continue

            if 500 <= response.status_code <= 599:
                wait_seconds = min(60, attempt * 10)

                logger.warning(
                    "Error servidor %s | intento %s/%s | esperando %s segundos...",
                    response.status_code,
                    attempt,
                    config.max_retries,
                    wait_seconds
                )

                time.sleep(wait_seconds)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as http_exc:
                last_exc = http_exc

                # En errores 400/401/403 normalmente repetir no corrige el problema.
                # Se registra el detalle que devuelve la API para facilitar diagnóstico en PyFlow.
                logger.error(
                    "Error HTTP %s en %s %s. Respuesta API: %s",
                    response.status_code,
                    method,
                    url,
                    response.text[:2000]
                )

                if response.status_code in (400, 401, 403):
                    raise RuntimeError(
                        f"Request falló con HTTP {response.status_code}: {response.text[:2000]}"
                    ) from http_exc

                raise

            return response

        except Exception as exc:
            last_exc = exc
            wait_seconds = min(60, attempt * 5)

            logger.warning(
                "Error request intento %s/%s: %s | esperando %s segundos...",
                attempt,
                config.max_retries,
                exc,
                wait_seconds
            )

            time.sleep(wait_seconds)

    raise RuntimeError(f"Request falló luego de {config.max_retries} intentos: {last_exc}")


def get_access_token(config: Config, logger: logging.Logger) -> str:
    logger.info("Solicitando token OAuth en Genesys Cloud...")

    response = request_with_retries(
        "POST",
        config.genesys_login_url,
        config,
        logger,
        data={
            "grant_type": "client_credentials",
            "client_id": config.genesys_client_id,
            "client_secret": config.genesys_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    token = response.json().get("access_token")

    if not token:
        raise RuntimeError("No se recibió access_token desde Genesys.")

    logger.info("Token obtenido correctamente.")
    return token


def get_all_wrapup_codes(config: Config, token: str, logger: logging.Logger) -> Dict[str, str]:
    logger.info("Consultando catálogo de códigos de conclusión...")

    results: Dict[str, str] = {}
    page = 1
    page_count = 1

    while page <= page_count:
        url = f"{config.genesys_region_base_url}/api/v2/routing/wrapupcodes?pageSize={config.page_size}&pageNumber={page}"

        response = request_with_retries(
            "GET",
            url,
            config,
            logger,
            headers=genesys_headers(token)
        )

        data = response.json()
        entities = data.get("entities", []) or []
        page_count = int(data.get("pageCount") or 1)

        for item in entities:
            item_id = item.get("id")
            name = item.get("name")
            if item_id:
                results[item_id] = name or ""

        logger.info(
            "Página wrapups %s/%s procesada | registros: %s | acumulado: %s",
            page,
            page_count,
            len(entities),
            len(results)
        )

        page += 1
        time.sleep(config.api_sleep_seconds)

    logger.info("Catálogo wrapups finalizado. Total: %s", len(results))
    return results


def get_all_queues(config: Config, token: str, logger: logging.Logger) -> Dict[str, str]:
    logger.info("Consultando catálogo de colas...")

    results: Dict[str, str] = {}
    page = 1
    page_count = 1

    while page <= page_count:
        url = f"{config.genesys_region_base_url}/api/v2/routing/queues?pageSize={config.page_size}&pageNumber={page}"

        response = request_with_retries(
            "GET",
            url,
            config,
            logger,
            headers=genesys_headers(token)
        )

        data = response.json()
        entities = data.get("entities", []) or []
        page_count = int(data.get("pageCount") or 1)

        for item in entities:
            item_id = item.get("id")
            name = item.get("name")
            if item_id:
                results[item_id] = name or ""

        logger.info(
            "Página colas %s/%s procesada | registros: %s | acumulado: %s",
            page,
            page_count,
            len(entities),
            len(results)
        )

        page += 1
        time.sleep(config.api_sleep_seconds)

    logger.info("Catálogo colas finalizado. Total: %s", len(results))
    return results


def is_target_wrapup_name(name: str) -> bool:
    if not name:
        return False

    upper_name = name.upper()

    return (
        upper_name.startswith("NBDA_")
        or upper_name.startswith("CONSULTA_AOL_")
        or upper_name.startswith("CONSULTAS_AOL_")
        or upper_name.startswith("GESTIONES_AOL_")
        or upper_name.startswith("SOPORTE_AOL_")
        or upper_name.startswith("SOPORTE_TECNICO_AOL_")
        or upper_name.startswith("SOPORTE_TÉCNICO_AOL_")
    )


def clean_conclusion_name(name: str) -> str:
    if not name:
        return ""

    replacements = [
        "NBDA_",
        "CONSULTA_AOL_",
        "CONSULTAS_AOL_",
        "GESTIONES_AOL_",
        "SOPORTE_TÉCNICO_AOL_",
        "SOPORTE_TECNICO_AOL_",
        "SOPORTE_AOL_",
    ]

    result = name

    for prefix in replacements:
        if result.upper().startswith(prefix):
            return result[len(prefix):]

    return result


def get_banca(name: str) -> str:
    if not name:
        return "AOL"

    return "NBDA" if name.upper().startswith("NBDA_") else "AOL"


def metric_stats(metrics: List[Dict[str, Any]], metric_name: str) -> Dict[str, Any]:
    for metric in metrics or []:
        if metric.get("metric") == metric_name:
            stats = metric.get("stats") or {}
            return {
                "count": stats.get("count") or 0,
                "sum": stats.get("sum") or 0,
                "min": stats.get("min"),
                "max": stats.get("max")
            }

    return {"count": 0, "sum": 0, "min": None, "max": None}


def ms_avg_to_seconds(stats: Dict[str, Any]) -> float:
    count = stats.get("count") or 0
    total_sum = stats.get("sum") or 0

    if count == 0:
        return 0.0

    return round((total_sum / count) / 1000, 2)


def chunks(items: List[str], size: int) -> List[List[str]]:
    """Divide listas grandes para evitar rechazos 400 por filtros demasiado extensos."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_analytics_body(start_utc: str, end_utc: str, wrapup_ids_chunk: List[str]) -> Dict[str, Any]:
    """
    Construye el body de /analytics/conversations/aggregates/query.

    Importante:
    - Genesys no permite filtrar por varios valores en un solo predicate.
    - Por eso se usa una cláusula OR con predicates individuales por wrapUpCode.
    - Se consulta por bloques para evitar HTTP 400 por payload/filtro demasiado grande.
    """
    return {
        "interval": f"{start_utc}/{end_utc}",
        "granularity": "P1D",
        "groupBy": [
            "wrapUpCode",
            "queueId"
        ],
        "metrics": [
            "tHandle",
            "tTalkComplete",
            "tHeldComplete",
            "tAcw"
        ],
        "filter": {
            "type": "and",
            "predicates": [
                {
                    "type": "dimension",
                    "dimension": "mediaType",
                    "operator": "matches",
                    "value": "voice"
                }
            ],
            "clauses": [
                {
                    "type": "or",
                    "predicates": [
                        {
                            "type": "dimension",
                            "dimension": "wrapUpCode",
                            "operator": "matches",
                            "value": wrapup_id
                        }
                        for wrapup_id in wrapup_ids_chunk
                    ]
                }
            ]
        }
    }


def query_conclusion_performance(
    config: Config,
    token: str,
    start_utc: str,
    end_utc: str,
    wrapup_catalog: Dict[str, str],
    queue_catalog: Dict[str, str],
    logger: logging.Logger
) -> List[Dict[str, Any]]:

    logger.info("Consultando analytics aggregates por wrapUpCode y queueId...")

    target_wrapup_ids = [
        wrapup_id
        for wrapup_id, wrapup_name in wrapup_catalog.items()
        if is_target_wrapup_name(wrapup_name)
    ]

    logger.info("Wrapup codes objetivo encontrados: %s", len(target_wrapup_ids))

    if not target_wrapup_ids:
        logger.warning("No se encontraron códigos de conclusión objetivo.")
        return []

    url = f"{config.genesys_region_base_url}/api/v2/analytics/conversations/aggregates/query"

    rows: List[Dict[str, Any]] = []
    chunk_size = env_int("WRAPUP_FILTER_CHUNK_SIZE", 20)
    if chunk_size <= 0:
        chunk_size = 20

    wrapup_chunks = chunks(target_wrapup_ids, chunk_size)

    for chunk_number, wrapup_chunk in enumerate(wrapup_chunks, start=1):
        logger.info(
            "Consultando bloque wrapups %s/%s | códigos: %s",
            chunk_number,
            len(wrapup_chunks),
            len(wrapup_chunk)
        )

        body = build_analytics_body(start_utc, end_utc, wrapup_chunk)

        response = request_with_retries(
            "POST",
            url,
            config,
            logger,
            headers=genesys_headers(token),
            json=body
        )

        data = response.json()
        results = data.get("results") or []

        logger.info(
            "Bloque wrapups %s/%s procesado | grupos recibidos: %s",
            chunk_number,
            len(wrapup_chunks),
            len(results)
        )

        for result in results:
            group = result.get("group") or {}
            wrapup_id = group.get("wrapUpCode")
            queue_id = group.get("queueId")

            wrapup_name = wrapup_catalog.get(wrapup_id, "")
            queue_name = queue_catalog.get(queue_id, "")

            if not is_target_wrapup_name(wrapup_name):
                continue

            if not queue_name:
                continue

            for item in result.get("data") or []:
                interval = item.get("interval") or ""
                interval_start = ""
                interval_end = ""

                if "/" in interval:
                    interval_start, interval_end = interval.split("/", 1)

                metrics = item.get("metrics") or []

                t_handle = metric_stats(metrics, "tHandle")
                t_talk = metric_stats(metrics, "tTalkComplete")
                t_held = metric_stats(metrics, "tHeldComplete")
                t_acw = metric_stats(metrics, "tAcw")

                manejo_count = int(t_handle.get("count") or 0)
                retencion_count = int(t_held.get("count") or 0)

                if manejo_count == 0:
                    continue

                fecha_conclusion, dia_conclusion, mes_conclusion, anio_conclusion = parse_interval_start_to_local_date(
                    interval_start,
                    config.timezone_name
                )

                rows.append({
                    "Inicio del intervalo": interval_start,
                    "Fin del intervalo": interval_end,
                    "Fecha conclusión": fecha_conclusion,
                    "Día": dia_conclusion,
                    "Mes": mes_conclusion,
                    "Año": anio_conclusion,
                    "ID de código de conclusión": wrapup_id,
                    "Nombre de código de conclusión": wrapup_name,
                    "ID de cola": queue_id,
                    "Nombre de cola": queue_name,
                    "Manejo medio": ms_avg_to_seconds(t_handle),
                    "Conversación media": ms_avg_to_seconds(t_talk),
                    "Retención media": ms_avg_to_seconds(t_held),
                    "ACW medio": ms_avg_to_seconds(t_acw),
                    "Manejo": manejo_count,
                    "Retención": retencion_count,
                    "conclusion": clean_conclusion_name(wrapup_name),
                    "Banca": get_banca(wrapup_name),
                })

        time.sleep(config.api_sleep_seconds)

    logger.info("Filas analytics transformadas: %s", len(rows))
    return rows

def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mantiene el resumen original del script:
    descripción de conclusión vs AOL / NBDA / porcentajes / total.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "DESCRIPCIÓN DE LA INTERACCIÓN",
                "AOL",
                "AOL %",
                "NBDA",
                "NBDA %",
                "Total"
            ]
        )

    pivot = (
        df.pivot_table(
            index="conclusion",
            columns="Banca",
            values="Manejo",
            aggfunc="sum",
            fill_value=0
        )
        .reset_index()
    )

    if "AOL" not in pivot.columns:
        pivot["AOL"] = 0

    if "NBDA" not in pivot.columns:
        pivot["NBDA"] = 0

    pivot["Total"] = pivot["AOL"] + pivot["NBDA"]
    pivot = pivot[pivot["Total"] > 0].copy()

    pivot["AOL %"] = (pivot["AOL"] / pivot["Total"]).fillna(0)
    pivot["NBDA %"] = (pivot["NBDA"] / pivot["Total"]).fillna(0)

    pivot = pivot.rename(columns={"conclusion": "DESCRIPCIÓN DE LA INTERACCIÓN"})

    pivot = pivot[
        [
            "DESCRIPCIÓN DE LA INTERACCIÓN",
            "AOL",
            "AOL %",
            "NBDA",
            "NBDA %",
            "Total"
        ]
    ].sort_values("Total", ascending=False)

    total_aol = pivot["AOL"].sum()
    total_nbda = pivot["NBDA"].sum()
    total_general = pivot["Total"].sum()

    total_row = pd.DataFrame([{
        "DESCRIPCIÓN DE LA INTERACCIÓN": "Total general",
        "AOL": total_aol,
        "AOL %": total_aol / total_general if total_general else 0,
        "NBDA": total_nbda,
        "NBDA %": total_nbda / total_general if total_general else 0,
        "Total": total_general
    }])

    return pd.concat([pivot, total_row], ignore_index=True)


def build_conclusion_daily_matrix(df: pd.DataFrame, banca: str) -> pd.DataFrame:
    """
    Crea la matriz solicitada para AOL o NBDA:
    - Filas: conclusión.
    - Columnas: mes/día, representado como YYYY-MM-DD para evitar ambigüedad.
    - Última columna: Total general.
    - Última fila: Total general.
    """
    base_columns = ["DESCRIPCIÓN DE LA INTERACCIÓN", "Total general"]

    if df.empty:
        return pd.DataFrame(columns=base_columns)

    required_cols = {"Banca", "conclusion", "Manejo", "Año", "Mes", "Día"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"No se pueden construir las pestañas AOL/NBDA. Faltan columnas: {sorted(missing)}")

    data = df[df["Banca"].astype(str).str.upper() == banca.upper()].copy()

    if data.empty:
        return pd.DataFrame(columns=base_columns)

    data["_fecha"] = pd.to_datetime(
        dict(
            year=data["Año"].astype(int),
            month=data["Mes"].astype(int),
            day=data["Día"].astype(int),
        ),
        errors="coerce"
    )

    data = data[data["_fecha"].notna()].copy()

    if data.empty:
        return pd.DataFrame(columns=base_columns)

    data["MES_DIA"] = data["_fecha"].dt.strftime("%Y-%m-%d")

    pivot = data.pivot_table(
        index="conclusion",
        columns="MES_DIA",
        values="Manejo",
        aggfunc="sum",
        fill_value=0
    )

    ordered_date_columns = sorted(pivot.columns.tolist())
    pivot = pivot[ordered_date_columns]

    pivot["Total general"] = pivot.sum(axis=1)
    pivot = pivot[pivot["Total general"] > 0].sort_values("Total general", ascending=False)

    total_row = pivot.sum(axis=0).to_frame().T
    total_row.index = ["Total general"]

    pivot = pd.concat([pivot, total_row], axis=0)

    # Al concatenar la fila de Total general, pandas puede perder el nombre del índice.
    # Si eso pasa, reset_index() crea una columna llamada "index" y luego el script
    # intenta convertir esa columna de textos (ej. CAMBIO_DE_CONTRASEÑA) a entero.
    # Por eso se fuerza aquí el nombre correcto antes de resetear el índice.
    pivot.index.name = "DESCRIPCIÓN DE LA INTERACCIÓN"
    pivot = pivot.reset_index()

    # Solo convertir a número las columnas de fechas y total.
    numeric_cols = [c for c in pivot.columns if c != "DESCRIPCIÓN DE LA INTERACCIÓN"]
    for col in numeric_cols:
        pivot[col] = pd.to_numeric(pivot[col], errors="coerce").fillna(0).astype(int)

    return pivot


def _format_excel_sheet(ws) -> None:
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for col_cells in ws.columns:
        max_length = 0
        col_letter = col_cells[0].column_letter

        for cell in col_cells:
            value = cell.value
            if value is not None:
                max_length = max(max_length, len(str(value)))

        ws.column_dimensions[col_letter].width = min(max_length + 2, 55)


def normalize_report_type(value: str) -> str:
    """Normaliza el tipo de salida para aceptar valores desde PyFlow o CLI."""
    text = str(value or "Reporte consolidado").strip().lower()
    text = text.replace("_", " ").replace("+", " + ")
    text = " ".join(text.split())

    if text in ("data", "datos", "detalle"):
        return "Data"

    if text in (
        "consolidado + data",
        "reporte consolidado + data",
        "consolidado y data",
        "ambos",
        "todo"
    ):
        return "Consolidado + Data"

    return "Reporte consolidado"


def build_data_for_analysis(df_detail: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara la hoja Data con una estructura más cómoda para análisis.
    Mantiene métricas de volumen y tiempos promedio devueltas por Genesys.
    """
    columns = [
        "Fecha conclusión",
        "Día",
        "Mes",
        "Año",
        "Banca",
        "conclusion",
        "Nombre de código de conclusión",
        "ID de código de conclusión",
        "Nombre de cola",
        "ID de cola",
        "Manejo",
        "Retención",
        "Manejo medio",
        "Conversación media",
        "Retención media",
        "ACW medio",
        "Inicio del intervalo",
        "Fin del intervalo",
    ]

    if df_detail.empty:
        return pd.DataFrame(columns=columns)

    df = df_detail.copy()

    for col in columns:
        if col not in df.columns:
            df[col] = None

    df = df[columns].copy()

    numeric_cols = [
        "Día", "Mes", "Año", "Manejo", "Retención",
        "Manejo medio", "Conversación media", "Retención media", "ACW medio"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.rename(columns={
        "conclusion": "Conclusión limpia",
        "Manejo": "Volumen",
        "Retención": "Cantidad retenciones/hold",
        "Manejo medio": "Tiempo manejo medio (seg)",
        "Conversación media": "Tiempo conversación media (seg)",
        "Retención media": "Tiempo retención media (seg)",
        "ACW medio": "Tiempo ACW medio (seg)",
    })

    return df.sort_values(
        ["Fecha conclusión", "Banca", "Nombre de código de conclusión", "Nombre de cola"],
        ascending=[True, True, True, True]
    )


def create_excel(
    df_detail: pd.DataFrame,
    df_summary: pd.DataFrame,
    output_path: Path,
    logger: logging.Logger,
    report_type: str = "Reporte consolidado"
) -> Path:

    logger.info("Generando Excel: %s", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report_type = normalize_report_type(report_type)
    logger.info("Tipo de archivo solicitado: %s", report_type)

    df_data = build_data_for_analysis(df_detail)
    df_aol = build_conclusion_daily_matrix(df_detail, "AOL")
    df_nbda = build_conclusion_daily_matrix(df_detail, "NBDA")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        sheets_to_format: List[str] = []

        if report_type in ("Reporte consolidado", "Consolidado + Data"):
            df_summary.to_excel(writer, sheet_name="Resumen", index=False)
            df_aol.to_excel(writer, sheet_name="Conclusiones AOL", index=False)
            df_nbda.to_excel(writer, sheet_name="Conclusiones NBDA", index=False)
            sheets_to_format.extend(["Resumen", "Conclusiones AOL", "Conclusiones NBDA"])

        if report_type in ("Data", "Consolidado + Data"):
            df_data.to_excel(writer, sheet_name="Data", index=False)
            sheets_to_format.append("Data")

        wb = writer.book

        for sheet_name in sheets_to_format:
            _format_excel_sheet(wb[sheet_name])

        if "Resumen" in wb.sheetnames:
            ws = wb["Resumen"]

            for row in range(2, ws.max_row + 1):
                ws[f"C{row}"].number_format = "0%"
                ws[f"E{row}"].number_format = "0%"

    logger.info("Excel generado correctamente.")
    return output_path


def summary_to_html(df_summary: pd.DataFrame, max_rows: int = 30) -> str:
    if df_summary.empty:
        return "<p>No se encontraron datos para el período consultado.</p>"

    df = df_summary.copy()

    total_row = df[df["DESCRIPCIÓN DE LA INTERACCIÓN"] == "Total general"]
    body_rows = df[df["DESCRIPCIÓN DE LA INTERACCIÓN"] != "Total general"].head(max_rows)
    df_email = pd.concat([body_rows, total_row], ignore_index=True)

    for col in ["AOL %", "NBDA %"]:
        df_email[col] = df_email[col].apply(lambda x: f"{x:.0%}" if pd.notnull(x) else "0%")

    for col in ["AOL", "NBDA", "Total"]:
        df_email[col] = df_email[col].apply(lambda x: f"{int(x):,}".replace(",", ","))

    return df_email.to_html(index=False, border=0, justify="center")


def get_graph_access_token(config: Config, logger: logging.Logger) -> str:
    """Obtiene token OAuth2 client_credentials para Microsoft Graph."""
    required = {
        "GRAPH_TENANT_ID": config.graph_tenant_id,
        "GRAPH_CLIENT_ID": config.graph_client_id,
        "GRAPH_CLIENT_SECRET": config.graph_client_secret,
        "GRAPH_SENDER_EMAIL": config.graph_sender_email,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(
            "Para enviar correo por Microsoft Graph faltan variables globales: "
            + ", ".join(missing)
        )

    token_url = f"{config.graph_authority_url}/{config.graph_tenant_id}/oauth2/v2.0/token"

    logger.info("Solicitando token Microsoft Graph...")
    response = requests.post(
        token_url,
        data={
            "client_id": config.graph_client_id,
            "client_secret": config.graph_client_secret,
            "scope": config.graph_scope,
            "grant_type": "client_credentials",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=config.request_timeout,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            f"Error obteniendo token Microsoft Graph. HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Microsoft Graph no devolvió access_token.")

    logger.info("Token Microsoft Graph obtenido correctamente.")
    return token


def _graph_recipients(emails: List[str]) -> List[Dict[str, Dict[str, str]]]:
    return [
        {"emailAddress": {"address": email.strip()}}
        for email in emails
        if email and email.strip()
    ]


def send_email_with_attachment(
    config: Config,
    to_recipients: List[str],
    cc_recipients: List[str],
    subject: str,
    body_html: str,
    attachment_path: Path,
    logger: logging.Logger
) -> None:
    """
    Envía correo mediante Microsoft Graph API usando permisos de aplicación.

    Requisitos en Azure/Entra ID:
    - Application permission: Mail.Send
    - Admin consent aprobado
    - El buzón GRAPH_SENDER_EMAIL debe existir y permitir envío por la app.
    """
    if not to_recipients:
        raise ValueError("Debe indicar al menos un destinatario en EMAIL_TO.")

    graph_token = get_graph_access_token(config, logger)

    with open(attachment_path, "rb") as file:
        encoded_attachment = base64.b64encode(file.read()).decode("utf-8")

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_html,
            },
            "toRecipients": _graph_recipients(to_recipients),
            "ccRecipients": _graph_recipients(cc_recipients),
            "attachments": [
                {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": attachment_path.name,
                    "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "contentBytes": encoded_attachment,
                }
            ],
        },
        "saveToSentItems": config.graph_save_to_sent_items,
    }

    url = f"https://graph.microsoft.com/v1.0/users/{config.graph_sender_email}/sendMail"

    logger.info(
        "Enviando correo por Microsoft Graph | remitente: %s | para: %s | cc: %s",
        config.graph_sender_email,
        ", ".join(to_recipients),
        ", ".join(cc_recipients) if cc_recipients else "<sin cc>",
    )

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {graph_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=config.request_timeout,
    )

    if response.status_code not in (202, 200):
        raise RuntimeError(
            f"Error enviando correo por Microsoft Graph. HTTP {response.status_code}: "
            f"{response.text[:1500]}"
        )

    logger.info("Correo enviado correctamente por Microsoft Graph.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reporte Genesys Conclusiones NBDA y AOL"
    )

    parser.add_argument("--date", default=env_str("DATE", ""), help="Fecha local específica. Ejemplo: 2026-05-27")
    parser.add_argument("--start-date", default=env_str("START_DATE", ""), help="Fecha local inicial. Ejemplo: 2026-05-05")
    parser.add_argument("--end-date", default=env_str("END_DATE", ""), help="Fecha local final. Ejemplo: 2026-05-27")
    parser.add_argument("--start-utc", default=env_str("START_UTC", ""), help="Fecha UTC inicial exacta.")
    parser.add_argument("--end-utc", default=env_str("END_UTC", ""), help="Fecha UTC final exacta.")

    parser.add_argument("--send-email", action="store_true", help="Envía correo con Excel adjunto.")
    parser.add_argument("--to", default=env_str("EMAIL_TO", ""), help="Destinatarios separados por coma.")
    parser.add_argument("--cc", default=env_str("EMAIL_CC", ""), help="CC separados por coma.")
    parser.add_argument("--subject", default=env_str("EMAIL_SUBJECT", ""), help="Asunto del correo.")
    parser.add_argument("--dry-run", action="store_true", help="Genera Excel pero no envía correo.")
    parser.add_argument(
        "--report-type",
        default=env_str("REPORT_TYPE", "Reporte consolidado"),
        choices=["Reporte consolidado", "Data", "Consolidado + Data"],
        help="Tipo de Excel a generar."
    )

    args = parser.parse_args()
    if env_bool("SEND_EMAIL", False):
        args.send_email = True
    if env_bool("DRY_RUN", False):
        args.dry_run = True

    logger = setup_logger()
    start_time = time.time()

    errors: List[str] = []
    detail_rows: List[Dict[str, Any]] = []
    output_path: Optional[Path] = None

    try:
        config = load_config()

        start_utc, end_utc, date_mode, start_local, end_local = parse_dates(
            args,
            config.timezone_name
        )

        logger.info("=" * 80)
        logger.info("INICIO REPORTE CONCLUSIONES NBDA / AOL")
        log_params(logger, [
            "GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION",
            "DATE", "START_DATE", "END_DATE", "START_UTC", "END_UTC", "AUTO_START_DAY",
            "GENESYS_TIMEZONE", "OUTPUT_DIR", "REPORT_TYPE", "SEND_EMAIL", "EMAIL_TO", "EMAIL_CC",
            "EMAIL_SUBJECT", "INCLUDE_SUMMARY_TABLE_IN_EMAIL", "WRAPUP_FILTER_CHUNK_SIZE", "GRAPH_TENANT_ID", "GRAPH_CLIENT_ID",
            "GRAPH_CLIENT_SECRET", "GRAPH_SENDER_EMAIL", "GRAPH_AUTHORITY_URL", "GRAPH_SCOPE",
            "GRAPH_SAVE_TO_SENT_ITEMS", "DRY_RUN"
        ])
        args.report_type = normalize_report_type(args.report_type)
        logger.info("Modo fecha: %s", date_mode)
        logger.info("Tipo de reporte: %s", args.report_type)
        logger.info("Inicio UTC: %s", start_utc)
        logger.info("Fin UTC: %s", end_utc)
        logger.info("Inicio local: %s", start_local.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("Fin local: %s", end_local.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("=" * 80)

        token = get_access_token(config, logger)

        wrapup_catalog = get_all_wrapup_codes(config, token, logger)
        queue_catalog = get_all_queues(config, token, logger)

        detail_rows = query_conclusion_performance(
            config,
            token,
            start_utc,
            end_utc,
            wrapup_catalog,
            queue_catalog,
            logger
        )

        df_detail = pd.DataFrame(detail_rows)

        if not df_detail.empty:
            df_detail = df_detail.sort_values(
                ["Inicio del intervalo", "Nombre de código de conclusión", "Nombre de cola"],
                ascending=[True, True, True]
            )

        df_summary = build_summary(df_detail)

        timestamp = datetime.now(ZoneInfo(config.timezone_name)).strftime("%Y%m%d_%H%M%S")
        output_path = Path(config.output_dir) / f"Reporte_Conclusiones_NBDA_AOL_{timestamp}.xlsx"

        create_excel(
            df_detail,
            df_summary,
            output_path,
            logger,
            args.report_type
        )

        if args.send_email and not args.dry_run:
            if not args.to:
                raise ValueError("Para enviar correo debe indicar --to.")

            to_recipients = [x.strip() for x in args.to.split(",") if x.strip()]
            cc_recipients = [x.strip() for x in args.cc.split(",") if x.strip()]

            subject = args.subject.strip() or "Reporte de Conclusiones NBDA y AOL"

            corte = end_local.strftime("%I:%M %p").lower().replace("am", "a.m.").replace("pm", "p.m.")
            periodo = f"{start_local.strftime('%d/%m/%Y %H:%M')} al {end_local.strftime('%d/%m/%Y %H:%M')}"
            tabla_resumen = summary_to_html(df_summary) if env_bool("INCLUDE_SUMMARY_TABLE_IN_EMAIL", True) else ""

            body_template = env_str("EMAIL_BODY_HTML", "")
            if not body_template:
                body_template = """
                <html>
                    <body>
                        <p>Buen día,</p>

                        <p>
                            Comparto el detalle de Conclusiones NBDA y AOL
                            correspondiente al período <b>{periodo}</b>, con corte de las <b>{corte}</b>.
                        </p>

                        {tabla_resumen}

                        <p>Saludos cordiales,</p>
                    </body>
                </html>
                """

            body_html = body_template.format(
                corte=corte,
                periodo=periodo,
                start_date=start_local.strftime("%d/%m/%Y"),
                end_date=end_local.strftime("%d/%m/%Y"),
                archivo=output_path.name if output_path else "",
                filas_detalle=len(detail_rows),
                tabla_resumen=tabla_resumen,
            )

            send_email_with_attachment(
                config,
                to_recipients,
                cc_recipients,
                subject,
                body_html,
                output_path,
                logger
            )

        elif args.send_email and args.dry_run:
            logger.warning("DRY RUN activo. No se enviará correo.")

    except Exception as exc:
        errors.append(str(exc))
        logger.exception("El proceso terminó con error: %s", exc)

    duration = time.time() - start_time

    logger.info("=" * 80)
    logger.info("RESUMEN FINAL")
    logger.info("Filas detalle obtenidas: %s", len(detail_rows))
    logger.info("Archivo generado: %s", output_path if output_path else "No generado")
    logger.info("Errores generales: %s", len(errors))

    for error in errors[:10]:
        logger.error("Detalle error: %s", error)

    logger.info("Duración total: %.2f segundos", duration)
    logger.info("=" * 80)

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
