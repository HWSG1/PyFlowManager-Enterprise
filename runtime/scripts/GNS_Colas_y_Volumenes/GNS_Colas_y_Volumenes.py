# =========================================================
# GNS_COLAS_Y_VOLUMENES.py
# =========================================================
#
# Automatiza dos flujos KNIME en un solo proceso:
#
# 1) GNS Colas
#    - Consulta /api/v2/routing/queues
#    - Carga tabla BI_SS.GNS_API_COLAS
#
# 2) GNS Volúmenes de Colas
#    - Usa las colas cargadas/consultadas previamente
#    - Consulta /api/v2/analytics/conversations/aggregates/query
#    - Carga tabla BI_SS.GNS_API_VOLUMEN
#
# IMPORTANTE:
# - Primero se ejecuta COLAS.
# - Luego se ejecuta VOLUMENES.
# - Esto reemplaza la dependencia que tenías en KNIME.
#
# =========================================================
# FORMAS DE EJECUCIÓN
# =========================================================
#
# Ejecutar automático último mes cerrado:
#
#   py .\GNS_Colas_y_Volumenes.py
#
# Ejecutar solo colas:
#
#   py .\GNS_Colas_y_Volumenes.py --solo-colas
#
# Ejecutar solo volúmenes usando colas desde HANA:
#
#   py .\GNS_Colas_y_Volumenes.py --solo-volumenes
#
# Ejecutar una fecha específica:
#
#   py .\GNS_Colas_y_Volumenes.py --date 2026-05-27
#
# Ejecutar un rango local:
#
#   py .\GNS_Colas_y_Volumenes.py --start-date 2026-05-01 --end-date 2026-05-27
#
# Ejecutar rango UTC/local exacto para Genesys:
#
#   py .\GNS_Colas_y_Volumenes.py --start-local 2026-05-01T00:00:00 --end-local 2026-05-28T00:00:00
#
# Probar sin cargar a HANA:
#
#   py .\GNS_Colas_y_Volumenes.py --dry-run
#
# =========================================================

import os
import sys
import time
import argparse
import logging
import traceback
import csv
import json
import base64
import mimetypes
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from html import escape
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Tuple, Optional

import requests
from dotenv import load_dotenv
from hdbcli import dbapi

try:
    import pandas as pd
except Exception:
    pd = None


# =========================================================
# PYFLOW MANAGER PARAMS
# =========================================================
# PyFlow detecta este bloque para solicitar parámetros y mapear variables globales.
# Las llaves del diccionario son los nombres que el script leerá desde variables
# de entorno durante la ejecución.

PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Genesys Region / Domain", "required": True},
    "HPR_HOST": {"type": "global", "global_key": "HPR_HOST", "label": "SAP HANA Host", "required": True},
    "HPR_HOST_ESPEJO": {"type": "global", "global_key": "HPR_HOST_ESPEJO", "label": "SAP HANA Host Espejo Lectura", "required": True},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "SAP HANA Port", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "SAP HANA Service User", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "SAP HANA Service Password", "required": True, "secret": True},
    "HANA_SCHEMA": {"type": "text", "label": "Esquema HANA", "required": True, "default": "BI_SS"},
    "HANA_COLAS_TABLE": {"type": "text", "label": "Tabla catálogo colas", "required": True, "default": "GNS_API_COLAS"},
    "HANA_VOLUMEN_TABLE": {"type": "text", "label": "Tabla volumen colas", "required": True, "default": "GNS_API_VOLUMEN"},
    "RUN_MODE": {"type": "select", "label": "Modo ejecución", "required": True, "options": ["colas_y_volumenes", "solo_colas", "solo_volumenes"], "default": "colas_y_volumenes"},
    "START_DATE": {"type": "date", "label": "Fecha inicial local", "required": False},
    "END_DATE": {"type": "date", "label": "Fecha final local", "required": False},
    "DAYS_BACK": {"type": "number", "label": "Días hacia atrás si no se indican fechas", "required": False, "default": "5"},
    "GENESYS_TIMEZONE": {"type": "text", "label": "Zona horaria Genesys", "required": True, "default": "America/Tegucigalpa"},
    "REPORT_OUTPUT_FORMAT": {"type": "select", "label": "Generar archivo de reporte", "required": False, "options": ["csv", "xlsx"]},
    "ATTACH_REPORT_FILE": {"type": "select", "label": "Adjuntar archivo al correo", "required": False, "options": ["false", "true"], "default": "false"},
    "REPORT_OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida del reporte", "required": False},
    "GRAPH_TENANT_ID": {"type": "global", "global_key": "GRAPH_TENANT_ID", "label": "Microsoft Graph Tenant ID", "required": False},
    "GRAPH_CLIENT_ID": {"type": "global", "global_key": "GRAPH_CLIENT_ID", "label": "Microsoft Graph Client ID", "required": False},
    "GRAPH_CLIENT_SECRET": {"type": "global", "global_key": "GRAPH_CLIENT_SECRET", "label": "Microsoft Graph Client Secret", "required": False, "secret": True},
    "GRAPH_SENDER_EMAIL": {"type": "global", "global_key": "GRAPH_SENDER_EMAIL", "label": "Correo remitente Graph", "required": False},
    "QUEUE_VOLUME_REPORT_EMAIL_TO": {"type": "tags", "label": "Destinatarios reporte colas/volúmenes", "required": False},
    "QUEUE_VOLUME_REPORT_EMAIL_CC": {"type": "tags", "label": "Copias reporte colas/volúmenes", "required": False},
    "QUEUE_VOLUME_REPORT_SUBJECT": {"type": "text", "label": "Asunto reporte colas/volúmenes", "required": False, "default": "Reporte de Colas y Volúmenes"}
}

LOGGER_NAME = "gns_colas_volumenes_pyflow"


def _clean_env_value(value: Any, default: Optional[str] = None) -> Optional[str]:
    """Normaliza valores recibidos desde PyFlow, CLI o .env."""
    if value is None:
        return default
    text = str(value).strip()
    if text == "" or text.lower() in ("null", "none", "undefined"):
        return default
    return text


def env_str(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = _clean_env_value(os.getenv(name), default)
    if required and not value:
        raise ValueError(f"Falta configurar variable/parámetro requerido: {name}")
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


def normalize_genesys_domain(value: str) -> str:
    """Acepta mypurecloud.com, api.mypurecloud.com o URL completa."""
    value = env_str("GENESYS_REGION", value, required=False)
    value = str(value or "mypurecloud.com").strip()
    value = value.replace("https://", "").replace("http://", "").strip("/")
    if value.startswith("api."):
        value = value[4:]
    if value.startswith("login."):
        value = value[6:]
    return value


def genesys_api_url_from_region(default_region: str = "mypurecloud.com") -> str:
    domain = normalize_genesys_domain(default_region)
    return f"https://api.{domain}"


def genesys_login_url_from_region(default_region: str = "mypurecloud.com") -> str:
    domain = normalize_genesys_domain(default_region)
    return f"https://login.{domain}/oauth/token"



# =========================================================
# CONFIGURACIÓN / LOGGING
# =========================================================

@dataclass
class Config:
    genesys_client_id: str
    genesys_client_secret: str
    genesys_region_base_url: str
    genesys_login_url: str

    HPR_HOST: str
    HPR_HOST_ESPEJO: str
    HPR_PORT: int
    HPR_USER: str
    HPR_PASSWORD: str

    hana_schema: str
    hana_colas_table: str
    hana_volumen_table: str

    timezone_name: str
    queue_page_size: int
    batch_size: int
    request_timeout: int
    api_sleep_seconds: float
    max_retries: int
    report_output_format: str
    attach_report_file: bool
    report_output_dir: str
    graph_tenant_id: str
    graph_client_id: str
    graph_client_secret: str
    graph_sender_email: str
    queue_volume_report_email_to: List[str]
    queue_volume_report_email_cc: List[str]
    queue_volume_report_subject: str


def setup_logger() -> logging.Logger:
    """
    Logger compatible con PyFlow Manager.

    Importante:
    - StreamHandler hacia stdout para que PyFlow vea los logs en tiempo real.
    - No usa archivos locales para evitar problemas de permisos/rutas.
    """
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


def log_params(logger: logging.Logger, names: List[str]) -> None:
    """Muestra parámetros usados ocultando secretos."""
    secret_tokens = ("SECRET", "PASSWORD", "TOKEN", "KEY")
    logger.info("Parámetros recibidos:")

    for name in names:
        value = env_str(name, "", required=False)
        if name in ("GENESYS_CLIENT_SECRET", "HPR_PASSWORD") or any(token in name.upper() for token in secret_tokens):
            shown = "********" if value else "(vacío)"
        else:
            shown = value if value else "(vacío)"
        logger.info("  - %s: %s", name, shown)


def load_config() -> Config:
    """
    Lee configuración desde variables de entorno inyectadas por PyFlow.

    Nota:
    Se mantiene load_dotenv() solo como apoyo para pruebas locales.
    En PyFlow Manager los valores deben venir de PYFLOW_PARAMS.
    """
    try:
        load_dotenv()
    except Exception:
        pass

    region = env_str("GENESYS_REGION", "mypurecloud.com", required=True)

    return Config(
        genesys_client_id=env_str("GENESYS_CLIENT_ID", required=True),
        genesys_client_secret=env_str("GENESYS_CLIENT_SECRET", required=True),
        genesys_region_base_url=genesys_api_url_from_region(region),
        genesys_login_url=genesys_login_url_from_region(region),

        HPR_HOST=env_str("HPR_HOST", required=True),
        HPR_HOST_ESPEJO=env_str("HPR_HOST_ESPEJO", required=True),
        HPR_PORT=env_int("HPR_PORT", 30015, required=True),
        HPR_USER=env_str("HPR_USER", required=True),
        HPR_PASSWORD=env_str("HPR_PASSWORD", required=True),

        hana_schema=env_str("HANA_SCHEMA", "BI_SS"),
        hana_colas_table=env_str("HANA_COLAS_TABLE", "GNS_API_COLAS"),
        hana_volumen_table=env_str("HANA_VOLUMEN_TABLE", "GNS_API_VOLUMEN"),

        timezone_name=env_str("GENESYS_TIMEZONE", "America/Tegucigalpa"),
        queue_page_size=env_int("QUEUE_PAGE_SIZE", 100),
        batch_size=env_int("HANA_BATCH_SIZE", 1000),
        request_timeout=env_int("REQUEST_TIMEOUT", 120),
        api_sleep_seconds=env_float("API_SLEEP_SECONDS", 2.0),
        max_retries=env_int("MAX_RETRIES", 5),
        report_output_format=env_str("REPORT_OUTPUT_FORMAT", "").lower(),
        attach_report_file=env_bool("ATTACH_REPORT_FILE", False),
        report_output_dir=env_str("REPORT_OUTPUT_DIR", ""),
        graph_tenant_id=env_str("GRAPH_TENANT_ID", ""),
        graph_client_id=env_str("GRAPH_CLIENT_ID", ""),
        graph_client_secret=env_str("GRAPH_CLIENT_SECRET", ""),
        graph_sender_email=env_str("GRAPH_SENDER_EMAIL", ""),
        queue_volume_report_email_to=split_list_value(env_str("QUEUE_VOLUME_REPORT_EMAIL_TO", "")),
        queue_volume_report_email_cc=split_list_value(env_str("QUEUE_VOLUME_REPORT_EMAIL_CC", "")),
        queue_volume_report_subject=env_str("QUEUE_VOLUME_REPORT_SUBJECT", "Reporte de Colas y Volúmenes"),
    )


def parse_local_date(value: str) -> date:
    """
    Acepta fechas desde PyFlow en formatos comunes:
    - yyyy-mm-dd
    - dd/mm/yyyy
    """
    value = env_str("_DATE_PARSE_TMP", value, required=False)
    if not value:
        raise ValueError("Fecha vacía.")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    raise ValueError(f"Formato de fecha no válido: {value!r}. Use yyyy-mm-dd o dd/mm/yyyy.")


def parse_local_datetime(value: str, tz: ZoneInfo) -> datetime:
    """
    Acepta fecha/hora exacta:
    - yyyy-mm-ddTHH:MM:SS
    - yyyy-mm-dd HH:MM:SS
    - dd/mm/yyyy HH:MM:SS
    """
    value = _clean_env_value(value, "")
    if not value:
        raise ValueError("Fecha/hora vacía.")

    candidates = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]

    for fmt in candidates:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=tz)
        except ValueError:
            pass

    # Último intento: fromisoformat
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=tz)
    except ValueError:
        raise ValueError(
            f"Formato de fecha/hora no válido: {value!r}. "
            "Use yyyy-mm-ddTHH:MM:SS."
        )



# =========================================================
# FECHAS
# =========================================================

def fmt_local(dt: datetime) -> str:
    # Genesys acepta intervalos locales cuando se envía timeZone.
    # Ejemplo: 2026-05-21T18:00:00
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_dates(args: argparse.Namespace, tz_name: str) -> Tuple[datetime, datetime, str]:
    """
    Prioridad de fechas:
    1. START_LOCAL + END_LOCAL
    2. DATE
    3. START_DATE + END_DATE
    4. DAYS_BACK, por defecto 5 días hacia atrás

    Si no se llenan fechas en PyFlow, cargará desde hoy 00:00 menos DAYS_BACK
    hasta hoy 00:00 en la zona horaria configurada.
    """
    tz = ZoneInfo(tz_name)

    if args.start_local and args.end_local:
        start_dt = parse_local_datetime(args.start_local, tz)
        end_dt = parse_local_datetime(args.end_local, tz)

        if end_dt <= start_dt:
            raise ValueError("END_LOCAL debe ser mayor que START_LOCAL.")

        return start_dt, end_dt, "Rango local manual exacto"

    if args.date:
        d = parse_local_date(args.date)
        start_dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
        end_dt = start_dt + timedelta(days=1)
        return start_dt, end_dt, f"Día local {d.isoformat()}"

    if args.start_date and args.end_date:
        d1 = parse_local_date(args.start_date)
        d2 = parse_local_date(args.end_date)

        if d2 < d1:
            raise ValueError("La fecha final no puede ser menor que la fecha inicial.")

        start_dt = datetime(d1.year, d1.month, d1.day, 0, 0, 0, tzinfo=tz)
        # Fecha final inclusiva: 2026-05-30 significa hasta 2026-05-31 00:00
        end_dt = datetime(d2.year, d2.month, d2.day, 0, 0, 0, tzinfo=tz) + timedelta(days=1)

        return start_dt, end_dt, f"Rango local {d1.isoformat()} al {d2.isoformat()}"

    days_back = env_int("DAYS_BACK", 5)
    if days_back <= 0:
        raise ValueError("DAYS_BACK debe ser mayor que cero.")

    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = today - timedelta(days=days_back)
    end_dt = today

    return start_dt, end_dt, f"Automático últimos {days_back} días cerrados"

def build_12h_intervals(start_dt: datetime, end_dt: datetime) -> List[Tuple[datetime, datetime]]:
    """
    Replica la lógica del flujo KNIME de volúmenes:
    procesa intervalos de 12 horas, alineados en bloques:
    00:00 -> 12:00 y 12:00 -> 00:00.
    """
    intervals = []
    current = start_dt

    while current < end_dt:
        nxt = min(current + timedelta(hours=12), end_dt)
        intervals.append((current, nxt))
        current = nxt

    return intervals


# =========================================================
# HTTP / GENESYS
# =========================================================

def request_with_retry(
    method: str,
    url: str,
    logger: logging.Logger,
    max_retries: int,
    timeout: int,
    **kwargs
) -> requests.Response:
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * attempt)

                logger.warning(
                    "Genesys respondió 429 Too Many Requests | intento %s/%s | esperando %s segundos...",
                    attempt,
                    max_retries,
                    wait_seconds
                )

                time.sleep(wait_seconds)
                continue

            if response.status_code >= 500:
                wait_seconds = min(60, 5 * attempt)
                logger.warning(
                    "Genesys respondió %s | intento %s/%s | esperando %s segundos...",
                    response.status_code,
                    attempt,
                    max_retries,
                    wait_seconds
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 400:
                logger.error("Error HTTP %s | Respuesta: %s", response.status_code, response.text[:1000])

            response.raise_for_status()
            return response

        except Exception as exc:
            last_error = exc
            wait_seconds = min(60, 5 * attempt)
            logger.warning(
                "Error de request | intento %s/%s | %s | esperando %s segundos...",
                attempt,
                max_retries,
                exc,
                wait_seconds
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"No se pudo completar request después de {max_retries} intentos: {last_error}")


def get_access_token(config: Config, logger: logging.Logger) -> str:
    logger.info("Solicitando token OAuth en Genesys Cloud...")

    response = request_with_retry(
        "POST",
        config.genesys_login_url,
        logger=logger,
        max_retries=config.max_retries,
        timeout=config.request_timeout,
        data={
            "grant_type": "client_credentials",
            "client_id": config.genesys_client_id,
            "client_secret": config.genesys_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = response.json().get("access_token")

    if not token:
        raise RuntimeError("No se recibió access_token desde Genesys.")

    logger.info("Token obtenido correctamente.")
    return token


def genesys_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


# =========================================================
# HANA
# =========================================================

def hana_connect(config: Config, *, read_only: bool = False):
    """
    Abre conexión a SAP HANA separando lectura y escritura.

    - read_only=False: usa HPR_HOST para cargas, updates y deletes.
    - read_only=True: usa HPR_HOST_ESPEJO para SELECT/consultas.
    """
    host = config.HPR_HOST_ESPEJO if read_only else config.HPR_HOST

    return dbapi.connect(
        address=host,
        port=config.HPR_PORT,
        user=config.HPR_USER,
        password=config.HPR_PASSWORD
    )


def hana_delete_all(config: Config, table: str, logger: logging.Logger) -> int:
    conn = hana_connect(config, read_only=False)
    cursor = conn.cursor()

    try:
        sql = f'DELETE FROM "{config.hana_schema}"."{table}"'
        logger.info('Eliminando registros existentes en "%s"."%s"...', config.hana_schema, table)
        cursor.execute(sql)
        deleted = cursor.rowcount
        conn.commit()
        logger.info("Registros eliminados previamente: %s", deleted)
        return deleted
    finally:
        cursor.close()
        conn.close()


def hana_delete_volume_range(
    config: Config,
    start_date_str: str,
    end_date_str: str,
    logger: logging.Logger
) -> int:
    conn = hana_connect(config, read_only=False)
    cursor = conn.cursor()

    try:
        sql = (
            f'DELETE FROM "{config.hana_schema}"."{config.hana_volumen_table}" '
            f'WHERE "START_DATE" >= ? AND "START_DATE" < ?'
        )

        logger.info(
            'Eliminando volúmenes existentes en "%s"."%s" para rango %s -> %s...',
            config.hana_schema,
            config.hana_volumen_table,
            start_date_str,
            end_date_str
        )

        cursor.execute(sql, (start_date_str, end_date_str))
        deleted = cursor.rowcount
        conn.commit()

        logger.info("Registros de volumen eliminados previamente: %s", deleted)
        return deleted
    finally:
        cursor.close()
        conn.close()


def hana_insert_rows(
    config: Config,
    table: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    logger: logging.Logger
) -> Tuple[int, int]:

    if not rows:
        logger.warning('No hay filas para cargar en "%s"."%s".', config.hana_schema, table)
        return 0, 0

    quoted_cols = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["?"] * len(columns))

    sql = (
        f'INSERT INTO "{config.hana_schema}"."{table}" '
        f'({quoted_cols}) VALUES ({placeholders})'
    )

    loaded = 0
    failed = 0

    conn = hana_connect(config, read_only=False)
    cursor = conn.cursor()

    try:
        logger.info('Iniciando carga INSERT en "%s"."%s"...', config.hana_schema, table)

        for start in range(0, len(rows), config.batch_size):
            batch = rows[start:start + config.batch_size]
            values = [tuple(row.get(c) for c in columns) for row in batch]

            try:
                cursor.executemany(sql, values)
                conn.commit()
                loaded += len(batch)

                logger.info(
                    "Carga parcial confirmada | tabla: %s | lote: %s | cargados acumulados: %s/%s",
                    table,
                    len(batch),
                    loaded,
                    len(rows)
                )

            except Exception as exc:
                conn.rollback()
                failed += len(batch)
                logger.exception("Error cargando lote desde fila %s en tabla %s: %s", start + 1, table, exc)

    finally:
        cursor.close()
        conn.close()

    return loaded, failed


def read_queues_from_hana(config: Config, logger: logging.Logger) -> List[Dict[str, Any]]:
    conn = hana_connect(config, read_only=True)
    cursor = conn.cursor()

    try:
        sql = (
            f'SELECT DISTINCT "ID", "QUEUE_NAME", "DIVISION_ID", "DIVISION_NAME" '
            f'FROM "{config.hana_schema}"."{config.hana_colas_table}"'
        )

        logger.info('Leyendo colas desde servidor espejo %s | tabla "%s"."%s"...', config.HPR_HOST_ESPEJO, config.hana_schema, config.hana_colas_table)

        cursor.execute(sql)

        rows = []
        for r in cursor.fetchall():
            rows.append({
                "ID": r[0],
                "QUEUE_NAME": r[1],
                "DIVISION_ID": r[2],
                "DIVISION_NAME": r[3],
            })

        logger.info("Colas leídas desde HANA: %s", len(rows))
        return rows

    finally:
        cursor.close()
        conn.close()


# =========================================================
# FLUJO 1: COLAS
# =========================================================

def service_level_duration(queue: Dict[str, Any], media: str) -> Optional[int]:
    media_settings = queue.get("mediaSettings") or {}
    settings = media_settings.get(media) or {}
    sl = settings.get("serviceLevel") or {}

    # Genesys puede devolver durationMs o duration dependiendo del objeto.
    value = sl.get("durationMs")
    if value is None:
        value = sl.get("duration")

    return value


def created_by_value(queue: Dict[str, Any]) -> Optional[str]:
    value = queue.get("createdBy")

    if isinstance(value, dict):
        return value.get("id") or value.get("name") or value.get("selfUri")

    return value


def transform_queue(queue: Dict[str, Any]) -> Dict[str, Any]:
    division = queue.get("division") or {}

    return {
        "ID": queue.get("id"),
        "QUEUE_NAME": queue.get("name"),
        "DIVISION_ID": division.get("id"),
        "DIVISION_NAME": division.get("name"),
        "DATECREATED": queue.get("dateCreated"),
        "CREATEDBY": created_by_value(queue),
        "CALL_SERVICELEVEL_DURATION": service_level_duration(queue, "call"),
        "CHAT_SERVICELEVEL_DURATION": service_level_duration(queue, "chat"),
        "EMAIL_SERVICELEVEL_DURATION": service_level_duration(queue, "email"),
        "MESAGGE_SERVICELEVEL_DURATION": service_level_duration(queue, "message"),
        "FECHA_CARGA": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_queues(config: Config, token: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    logger.info("Iniciando lectura paginada de colas Genesys...")

    page_number = 1
    page_count = None
    rows: List[Dict[str, Any]] = []

    while True:
        url = (
            f"{config.genesys_region_base_url}"
            f"/api/v2/routing/queues?pageNumber={page_number}&pageSize={config.queue_page_size}"
        )

        response = request_with_retry(
            "GET",
            url,
            logger=logger,
            max_retries=config.max_retries,
            timeout=config.request_timeout,
            headers=genesys_headers(token)
        )

        data = response.json()

        entities = data.get("entities") or []
        page_count = data.get("pageCount") or page_count or page_number

        for q in entities:
            row = transform_queue(q)
            if row.get("ID"):
                rows.append(row)

        logger.info(
            "Página colas %s/%s procesada | colas en página: %s | acumulado: %s",
            page_number,
            page_count,
            len(entities),
            len(rows)
        )

        if page_number >= int(page_count):
            break

        page_number += 1
        time.sleep(config.api_sleep_seconds)

    logger.info("Lectura de colas finalizada. Total colas: %s", len(rows))
    return rows


QUEUE_COLUMNS = [
    "ID",
    "QUEUE_NAME",
    "DIVISION_ID",
    "DIVISION_NAME",
    "DATECREATED",
    "CREATEDBY",
    "CALL_SERVICELEVEL_DURATION",
    "CHAT_SERVICELEVEL_DURATION",
    "EMAIL_SERVICELEVEL_DURATION",
    "MESAGGE_SERVICELEVEL_DURATION",
    "FECHA_CARGA",
]


def run_colas(
    config: Config,
    token: str,
    logger: logging.Logger,
    dry_run: bool
) -> Tuple[List[Dict[str, Any]], int, int]:

    rows = fetch_queues(config, token, logger)

    loaded = 0
    failed = 0

    if dry_run:
        logger.warning("DRY RUN activo. No se cargará tabla de colas.")
        return rows, loaded, failed

    # Para catálogo de colas conviene recargar completo.
    hana_delete_all(config, config.hana_colas_table, logger)

    loaded, failed = hana_insert_rows(
        config,
        config.hana_colas_table,
        QUEUE_COLUMNS,
        rows,
        logger
    )

    return rows, loaded, failed


# =========================================================
# FLUJO 2: VOLÚMENES
# =========================================================

METRICS = [
    "nBlindTransferred",
    "nBotInteractions",
    "nCobrowseSessions",
    "nConnected",
    "nConsult",
    "nError",
    "nOffered",
    "oServiceLevel",
    "nOutbound",
    "nOutboundAbandoned",
    "nOutboundAttempted",
    "nOutboundConnected",
    "nOverSla",
    "nStateTransitionError",
    "nTransferred",
    "tAbandon",
    "tAcd",
    "tActiveCallback",
    "tAcw",
    "tAgentResponseTime",
    "tAlert",
    "tAnswered",
    "tAverageAgentResponseTime",
    "tAverageCustomerResponseTime",
    "tBarging",
    "tCoaching",
    "tCoachingComplete",
    "tConnected",
    "tContacting",
    "tDialing",
    "tFirstConnect",
    "tFirstDial",
    "tFirstEngagement",
    "tFirstResponse",
    "tFlowOut",
    "tHandle",
    "tHeld",
    "tHeldComplete",
    "tIvr",
    "tMonitoring",
    "tMonitoringComplete",
    "tNotResponding",
    "tPark",
    "tParkComplete",
    "tShortAbandon",
    "tTalk",
    "tTalkComplete",
    "tUserResponseTime",
    "tVoicemail",
    "tWait",
]


METRIC_COLUMN_MAP = {
    ("nOffered", "count"): "OFFERED_NUMBER",
    ("tAnswered", "count"): "ANSWERED_NUMBER",
    ("tAnswered", "sum"): "ANSWERED_TIME",
    ("tHandle", "count"): "HANDLE_NUMBER",
    ("tHandle", "sum"): "HANDLE_TIME",
    ("tAcw", "count"): "ACW_NUMBER",
    ("tAcw", "sum"): "ACW_TIME",
    ("tAlert", "count"): "ALERT_NUMBER",
    ("tAlert", "sum"): "ALERT_TIME",
    ("tAcd", "count"): "TACD_NUMBER",
    ("tAcd", "sum"): "TACD_TIME",
    ("tConnected", "count"): "CONNECTED_NUMBER",
    ("tConnected", "sum"): "CONNECTED_TIME",
    ("tTalkComplete", "count"): "TALK_NUMBER",
    ("tTalkComplete", "sum"): "TALK_TIME",
    ("tWait", "count"): "WAIT_NUMBER",
    ("tWait", "sum"): "WAIT_TIME",
    ("tAbandon", "count"): "ABANDON_NUMBER",
    ("tAbandon", "sum"): "ABANDON_TIME",
    ("tAgentResponseTime", "count"): "AGENT_RESPONSE_NUMBER",
    ("tAgentResponseTime", "sum"): "AGENT_RESPONSE_TIME",
    ("tHeldComplete", "count"): "HOLD_NUMBER",
    ("tHeldComplete", "sum"): "HOLD_TIME",
    ("tAverageAgentResponseTime", "count"): "AVERAGE_AGENT_RESPONSE_NUMBER",
    ("tAverageAgentResponseTime", "sum"): "AVERAGE_AGENT_RESPONSE_TIME",
    ("tAverageCustomerResponseTime", "count"): "AVERAGE_CUSTOMER_RESPONSE_NUMBER",
    ("tAverageCustomerResponseTime", "sum"): "AVERAGE_CUSTOMER_RESPONSE_TIME",
    ("tFirstEngagement", "count"): "FIRST_ENGAGEMENT_NUMBER",
    ("tFirstEngagement", "sum"): "FIRST_ENGAGEMENT_TIME",
    ("tFirstResponse", "count"): "FIRST_RESPONSE_NUMBER",
    ("tFirstResponse", "sum"): "FIRST_RESPONSE_TIME",
    ("nOverSla", "count"): "OVER_SLA_NUMBER",
    ("nError", "count"): "ERROR_NUMBER",
    ("nOutboundConnected", "count"): "OUTBOUND_CONNECTED_NUMBER",
    ("tShortAbandon", "count"): "SHORT_ABANDON_NUMBER",
    ("tShortAbandon", "sum"): "SHORT_ABANDON_TIME",
    ("tNotResponding", "count"): "NOT_RESPONDING_NUMBER",
    ("tNotResponding", "sum"): "NOT_RESPONDING_TIME",
    ("nBlindTransferred", "count"): "BLIND_TRANSFERRED",
    ("nTransferred", "count"): "TRANSFERRED_NUMBER",
    ("nConsult", "count"): "CONSULT_TRANSFERRED_NUMBER",
    ("tIvr", "count"): "IVR_NUMBER",
    ("tIvr", "sum"): "IVR_TIME",
    ("tActiveCallback", "count"): "ACTIVE_CALLBACK_NUMBER",
    ("tActiveCallback", "sum"): "ACTIVE_CALLBACK_TIME",
    ("tFirstDial", "count"): "FIRST_DIAL_NUMBER",
    ("tFirstDial", "sum"): "FIRST_DIAL_TIME",
    ("nOutbound", "count"): "OUTBOUND_NUMBER",
    ("nOutboundAttempted", "count"): "OUTBOUND_ATTEMPTED_NUMBER",
    ("tContacting", "count"): "CONTACTING_NUMBER",
    ("tContacting", "sum"): "CONTACTING_TIME",
    ("tDialing", "count"): "DIALING_NUMBER",
    ("tDialing", "sum"): "DIALING_TIME",
    ("nOutboundAbandoned", "count"): "OUTBOUND_ABANDONED_NUMBER",
    ("nOutboundAbandoned", "sum"): "OUTBOUND_ABANDONED_TIME",
}


VOLUME_COLUMNS = [
    "ID_UNICO",
    "DIRECTION",
    "MEDIATYPE",
    "QUEUE_ID",
    "QUEUE_NAME",
    "DIVISION_ID",
    "DIVISION_NAME",
    "START_DATE",
    "FINISH_DATE",
    "OFFERED_NUMBER",
    "ANSWERED_NUMBER",
    "ANSWERED_TIME",
    "HANDLE_NUMBER",
    "HANDLE_TIME",
    "ACW_NUMBER",
    "ACW_TIME",
    "ALERT_NUMBER",
    "ALERT_TIME",
    "TACD_NUMBER",
    "TACD_TIME",
    "CONNECTED_NUMBER",
    "CONNECTED_TIME",
    "TALK_NUMBER",
    "TALK_TIME",
    "WAIT_NUMBER",
    "WAIT_TIME",
    "ABANDON_NUMBER",
    "ABANDON_TIME",
    "AGENT_RESPONSE_TIME",
    "AGENT_RESPONSE_NUMBER",
    "HOLD_NUMBER",
    "HOLD_TIME",
    "AVERAGE_AGENT_RESPONSE_NUMBER",
    "AVERAGE_AGENT_RESPONSE_TIME",
    "AVERAGE_CUSTOMER_RESPONSE_NUMBER",
    "AVERAGE_CUSTOMER_RESPONSE_TIME",
    "FIRST_ENGAGEMENT_NUMBER",
    "FIRST_ENGAGEMENT_TIME",
    "FIRST_RESPONSE_NUMBER",
    "FIRST_RESPONSE_TIME",
    "OVER_SLA_NUMBER",
    "ERROR_NUMBER",
    "OUTBOUND_CONNECTED_NUMBER",
    "SHORT_ABANDON_NUMBER",
    "SHORT_ABANDON_TIME",
    "NOT_RESPONDING_NUMBER",
    "NOT_RESPONDING_TIME",
    "BLIND_TRANSFERRED",
    "TRANSFERRED_NUMBER",
    "CONSULT_TRANSFERRED_NUMBER",
    "IVR_NUMBER",
    "IVR_TIME",
    "ACTIVE_CALLBACK_NUMBER",
    "ACTIVE_CALLBACK_TIME",
    "FIRST_DIAL_NUMBER",
    "FIRST_DIAL_TIME",
    "OUTBOUND_NUMBER",
    "OUTBOUND_ATTEMPTED_NUMBER",
    "CONTACTING_NUMBER",
    "CONTACTING_TIME",
    "DIALING_NUMBER",
    "DIALING_TIME",
    "OUTBOUND_ABANDONED_NUMBER",
    "OUTBOUND_ABANDONED_TIME",
    "FECHA_CARGA",
]


def empty_volume_row() -> Dict[str, Any]:
    return {col: None for col in VOLUME_COLUMNS}


def make_id_unico(row: Dict[str, Any]) -> str:
    parts = [
        row.get("DIRECTION"),
        row.get("MEDIATYPE"),
        row.get("QUEUE_ID"),
        row.get("QUEUE_NAME"),
        row.get("DIVISION_ID"),
        row.get("DIVISION_NAME"),
        row.get("START_DATE"),
        row.get("FINISH_DATE"),
    ]

    value = "_".join("" if p is None else str(p) for p in parts)

    while "__" in value:
        value = value.replace("__", "_")

    return value.strip("_")


def build_queue_lookup(queues: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    lookup = {}

    for q in queues:
        qid = q.get("ID")
        if qid:
            lookup[qid] = q

    return lookup


def query_queue_volume(
    config: Config,
    token: str,
    start_dt: datetime,
    end_dt: datetime,
    logger: logging.Logger
) -> Dict[str, Any]:

    url = f"{config.genesys_region_base_url}/api/v2/analytics/conversations/aggregates/query"

    body = {
        "interval": f"{fmt_local(start_dt)}/{fmt_local(end_dt)}",
        "timeZone": config.timezone_name,
        "groupBy": [
            "queueId",
            "mediaType",
            "direction",
            "messageType"
        ],
        "filter": {
            "type": "and",
            "clauses": [
                {
                    "type": "or",
                    "predicates": [
                        {
                            "dimension": "queueId",
                            "operator": "EXISTS"
                        }
                    ]
                }
            ]
        },
        "metrics": METRICS,
        "flattenMultivaluedDimensions": True,
        "granularity": "PT30M",
        "alternateTimeDimension": "eventTime"
    }

    response = request_with_retry(
        "POST",
        url,
        logger=logger,
        max_retries=config.max_retries,
        timeout=config.request_timeout,
        headers=genesys_headers(token),
        json=body
    )

    return response.json()


def transform_volume_response(
    data: Dict[str, Any],
    queue_lookup: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:

    rows: List[Dict[str, Any]] = []
    results = data.get("results") or []

    for result in results:
        group = result.get("group") or {}

        queue_id = group.get("queueId")
        queue_info = queue_lookup.get(queue_id, {})

        direction = group.get("direction")
        media_type = group.get("mediaType")

        for item in result.get("data") or []:
            interval = item.get("interval") or ""

            if "/" in interval:
                start_date, finish_date = interval.split("/", 1)
            else:
                start_date, finish_date = None, None

            row = empty_volume_row()

            row["DIRECTION"] = direction
            row["MEDIATYPE"] = media_type
            row["QUEUE_ID"] = queue_id
            row["QUEUE_NAME"] = queue_info.get("QUEUE_NAME")
            row["DIVISION_ID"] = queue_info.get("DIVISION_ID")
            row["DIVISION_NAME"] = queue_info.get("DIVISION_NAME")
            row["START_DATE"] = start_date
            row["FINISH_DATE"] = finish_date
            row["FECHA_CARGA"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for metric in item.get("metrics") or []:
                metric_name = metric.get("metric")
                stats = metric.get("stats") or {}

                for stat_name, stat_value in stats.items():
                    col = METRIC_COLUMN_MAP.get((metric_name, stat_name))
                    if col:
                        row[col] = stat_value

            row["ID_UNICO"] = make_id_unico(row)

            rows.append(row)

    return rows


def run_volumenes(
    config: Config,
    token: str,
    queues: List[Dict[str, Any]],
    start_dt: datetime,
    end_dt: datetime,
    logger: logging.Logger,
    dry_run: bool,
    progress_start: int = 45,
    progress_end: int = 78
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]:

    if not queues:
        logger.warning("No hay colas disponibles para cruzar con volúmenes.")
        return 0, 0, 0, 0, []

    queue_lookup = build_queue_lookup(queues)
    intervals = build_12h_intervals(start_dt, end_dt)

    logger.info("Intervalos de volumen a procesar: %s", len(intervals))

    all_rows: List[Dict[str, Any]] = []
    intervals_ok = 0
    intervals_error = 0

    for idx, (ini, fin) in enumerate(intervals, start=1):
        try:
            logger.info(
                "Consultando volumen %s/%s | %s -> %s",
                idx,
                len(intervals),
                fmt_local(ini),
                fmt_local(fin)
            )

            data = query_queue_volume(config, token, ini, fin, logger)
            rows = transform_volume_response(data, queue_lookup)
            all_rows.extend(rows)
            intervals_ok += 1

            logger.info(
                "Intervalo procesado OK | filas obtenidas: %s | acumulado: %s",
                len(rows),
                len(all_rows)
            )

            time.sleep(config.api_sleep_seconds)

        except Exception as exc:
            intervals_error += 1
            logger.exception("Error procesando intervalo %s -> %s: %s", fmt_local(ini), fmt_local(fin), exc)
            time.sleep(max(config.api_sleep_seconds, 10))

        progress = progress_start + int((idx / max(len(intervals), 1)) * (progress_end - progress_start))
        pyflow_progress(progress)

    if dry_run:
        logger.warning("DRY RUN activo. No se cargará tabla de volúmenes.")
        return len(all_rows), 0, 0, intervals_error, all_rows

    hana_delete_volume_range(
        config,
        fmt_local(start_dt),
        fmt_local(end_dt),
        logger
    )

    loaded, failed = hana_insert_rows(
        config,
        config.hana_volumen_table,
        VOLUME_COLUMNS,
        all_rows,
        logger
    )

    return len(all_rows), loaded, failed, intervals_error, all_rows


def output_directory(config: Config) -> str:
    path = config.report_output_dir or os.getcwd()
    os.makedirs(path, exist_ok=True)
    return path


def write_report_file(
    config: Config,
    rows: List[Dict[str, Any]],
    columns: List[str],
    name: str,
    logger: logging.Logger
) -> Optional[str]:
    report_format = (config.report_output_format or "").strip().lower()
    if not report_format and config.attach_report_file:
        report_format = "xlsx"
    if not report_format:
        return None

    if report_format not in ("csv", "xlsx"):
        logger.warning("REPORT_OUTPUT_FORMAT inválido: %s. No se generará archivo.", report_format)
        return None

    if not rows:
        logger.warning("No hay filas para generar archivo %s.", name)
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_directory(config), f"{name}_{ts}.{report_format}")

    if report_format == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    else:
        if pd is None:
            raise RuntimeError("Para generar Excel instala pandas y openpyxl: pip install pandas openpyxl")
        pd.DataFrame(rows, columns=columns).to_excel(path, index=False)

    logger.info("Archivo de reporte generado: %s | filas: %s", path, len(rows))
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


def get_graph_access_token(config: Config, logger: logging.Logger) -> str:
    if not config.graph_tenant_id or not config.graph_client_id or not config.graph_client_secret:
        raise ValueError("Configura GRAPH_TENANT_ID, GRAPH_CLIENT_ID y GRAPH_CLIENT_SECRET para enviar el reporte por Microsoft Graph.")

    url = f"https://login.microsoftonline.com/{config.graph_tenant_id}/oauth2/v2.0/token"
    response = requests.post(
        url,
        data={
            "client_id": config.graph_client_id,
            "client_secret": config.graph_client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if response.status_code >= 400:
        logger.error("Error obteniendo token Graph %s | %s", response.status_code, response.text[:1000])
    response.raise_for_status()

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Microsoft Graph no devolvió access_token.")
    return token


def build_queue_volume_report_html(
    total_queues: int,
    queues_loaded: int,
    queues_failed: int,
    volume_rows: int,
    volume_loaded: int,
    volume_failed: int,
    volume_interval_errors: int,
    date_mode: str,
    duration_seconds: float
) -> str:
    now = datetime.now(ZoneInfo("America/Tegucigalpa"))
    coverage = (volume_loaded / volume_rows * 100) if volume_rows else 0
    coverage = max(0, min(100, coverage))

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
              <h1 style="margin:8px 0 0;font-size:24px;line-height:1.2;">Reporte de Colas y Volúmenes</h1>
              <p style="margin:8px 0 0;font-size:13px;color:#fecaca;">Reporte automático generado por PyFlow Manager</p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px;">
              <p style="margin:0 0 24px;font-size:14px;line-height:1.6;">
                Se ha completado la ejecución del proceso de colas y volúmenes. A continuación se presenta el resumen de carga para el periodo procesado.
              </p>
              <table width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Colas obtenidas</div>
                    <div style="font-size:26px;font-weight:700;color:#1e293b;margin-top:8px;">{total_queues:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Catálogo consultado</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#DA282D;text-transform:uppercase;">Filas volumen</div>
                    <div style="font-size:26px;font-weight:700;color:#DA282D;margin-top:8px;">{volume_rows:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Registros transformados</div>
                  </td>
                </tr>
                <tr><td colspan="3" height="16"></td></tr>
                <tr>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Cargas HANA</div>
                    <div style="font-size:22px;font-weight:700;color:#1e293b;margin-top:8px;">Colas {queues_loaded:,} / Volumen {volume_loaded:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Registros cargados</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background:#fdf2f2;border:1px solid #fee2e2;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#b91c1c;text-transform:uppercase;">Errores</div>
                    <div style="font-size:22px;font-weight:700;color:#b91c1c;margin-top:8px;">{queues_failed + volume_failed + volume_interval_errors:,}</div>
                    <div style="font-size:11px;color:#f87171;">Filas o intervalos con error</div>
                  </td>
                </tr>
              </table>
              <div style="margin-top:24px;background:#fafafa;border:1px solid #f1f5f9;border-radius:6px;padding:22px;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="font-size:12px;font-weight:700;color:#475569;text-transform:uppercase;">Indicador de carga de volumen</td>
                    <td align="right" style="font-size:13px;font-weight:700;color:#1e293b;">{coverage:.1f}%</td>
                  </tr>
                  <tr>
                    <td colspan="2" style="padding-top:10px;">
                      <table width="100%" cellspacing="0" cellpadding="0" style="background:#e2e8f0;height:8px;border-radius:4px;overflow:hidden;">
                        <tr>
                          <td width="{coverage:.1f}%" style="background:#DA282D;height:8px;"></td>
                          <td style="background:#e2e8f0;height:8px;"></td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </div>
              <div style="margin-top:24px;border-left:3px solid #DA282D;padding-left:16px;font-size:13px;line-height:1.5;color:#64748b;">
                <strong>Periodo:</strong> {escape(date_mode)}<br />
                <strong>Duración:</strong> {duration_seconds:.2f} segundos
              </div>
              <div style="margin-top:28px;border-top:1px solid #f1f5f9;padding-top:22px;font-size:12px;color:#64748b;">
                Fecha de ejecución: <strong>{escape(now.strftime("%d/%m/%Y"))}</strong><br />
                Hora de ejecución: <strong>{escape(now.strftime("%I:%M %p"))}</strong>
              </div>
            </td>
          </tr>
          <tr>
            <td align="center" style="background:#f1f5f9;padding:20px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;">
              Este es un correo automático generado por PyFlow Manager.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def enviar_reporte_colas_volumenes(
    config: Config,
    total_queues: int,
    queues_loaded: int,
    queues_failed: int,
    volume_rows: int,
    volume_loaded: int,
    volume_failed: int,
    volume_interval_errors: int,
    date_mode: str,
    duration_seconds: float,
    report_files: List[str],
    logger: logging.Logger
) -> bool:
    recipients = config.queue_volume_report_email_to
    cc = config.queue_volume_report_email_cc

    if not recipients:
        logger.info("Reporte por correo no enviado: no hay destinatarios en QUEUE_VOLUME_REPORT_EMAIL_TO.")
        return False
    if not config.graph_sender_email:
        logger.warning("Reporte por correo no enviado: configura GRAPH_SENDER_EMAIL.")
        return False

    html = build_queue_volume_report_html(
        total_queues,
        queues_loaded,
        queues_failed,
        volume_rows,
        volume_loaded,
        volume_failed,
        volume_interval_errors,
        date_mode,
        duration_seconds
    )

    payload = {
        "message": {
            "subject": config.queue_volume_report_subject,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": email}} for email in recipients],
            "ccRecipients": [{"emailAddress": {"address": email}} for email in cc],
        },
        "saveToSentItems": "true",
    }

    if config.attach_report_file and report_files:
        payload["message"]["attachments"] = [build_file_attachment(path) for path in report_files]
    elif config.attach_report_file and not report_files:
        logger.warning("Se solicitÃ³ adjuntar archivo, pero no se generÃ³ ningÃºn reporte para adjuntar.")

    try:
        token = get_graph_access_token(config, logger)
        url = f"https://graph.microsoft.com/v1.0/users/{config.graph_sender_email}/sendMail"
        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code >= 400:
            logger.error("Error enviando reporte Graph %s | %s", response.status_code, response.text[:1000])
        response.raise_for_status()
        logger.info("Reporte de colas/volúmenes enviado a: %s", ", ".join(recipients + cc))
        return True
    except Exception as exc:
        logger.error("No se pudo enviar reporte de colas/volúmenes: %s", exc)
        return False


# =========================================================
# MAIN
# =========================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Carga Genesys Cloud: colas y volúmenes de colas a SAP HANA"
    )

    parser.add_argument("--solo-colas", action="store_true", help="Ejecuta solamente carga de colas.")
    parser.add_argument("--solo-volumenes", action="store_true", help="Ejecuta solamente carga de volúmenes usando colas desde HANA.")
    parser.add_argument("--date", default=env_str("DATE", ""), help="Fecha local específica. Ejemplo: 2026-05-27")
    parser.add_argument("--start-date", default=env_str("START_DATE", ""), help="Fecha local inicial inclusiva. Ejemplo: 2026-05-01")
    parser.add_argument("--end-date", default=env_str("END_DATE", ""), help="Fecha local final inclusiva. Ejemplo: 2026-05-27")
    parser.add_argument("--start-local", default=env_str("START_LOCAL", ""), help="Fecha/hora local inicial exacta. Ejemplo: 2026-05-01T00:00:00")
    parser.add_argument("--end-local", default=env_str("END_LOCAL", ""), help="Fecha/hora local final exacta. Ejemplo: 2026-05-28T00:00:00")
    parser.add_argument("--days-back", default=env_str("DAYS_BACK", "5"), help="Días hacia atrás si no se indican fechas. Default: 5")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta API y transformación, pero no carga a HANA.")

    args = parser.parse_args()
    run_mode = env_str("RUN_MODE", "")
    if run_mode == "solo_colas":
        args.solo_colas = True
    elif run_mode == "solo_volumenes":
        args.solo_volumenes = True
    if args.days_back:
        os.environ["DAYS_BACK"] = str(args.days_back)
    if env_bool("DRY_RUN", False):
        args.dry_run = True

    logger = setup_logger()
    start_time = time.time()

    total_errors: List[str] = []
    output_files: List[str] = []
    date_mode = ""
    config: Optional[Config] = None

    total_queues = 0
    queues_loaded = 0
    queues_failed = 0
    queue_rows: List[Dict[str, Any]] = []

    volume_rows = 0
    volume_loaded = 0
    volume_failed = 0
    volume_interval_errors = 0
    volume_report_rows: List[Dict[str, Any]] = []

    try:
        pyflow_progress(2)
        config = load_config()
        start_dt, end_dt, date_mode = parse_dates(args, config.timezone_name)
        pyflow_progress(5)

        logger.info("=" * 80)
        logger.info("INICIO PROCESO GNS COLAS Y VOLUMENES")
        log_params(logger, ["GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION", "HPR_HOST", "HPR_HOST_ESPEJO", "HPR_PORT", "HPR_USER", "HPR_PASSWORD", "HANA_SCHEMA", "HANA_COLAS_TABLE", "HANA_VOLUMEN_TABLE", "RUN_MODE", "DATE", "START_DATE", "END_DATE", "START_LOCAL", "END_LOCAL", "DAYS_BACK", "DRY_RUN"])
        logger.info("Modo fecha: %s", date_mode)
        logger.info("Inicio local API: %s", fmt_local(start_dt))
        logger.info("Fin local API: %s", fmt_local(end_dt))
        logger.info("Zona horaria Genesys: %s", config.timezone_name)
        logger.info("Tabla colas: %s.%s", config.hana_schema, config.hana_colas_table)
        logger.info("Tabla volúmenes: %s.%s", config.hana_schema, config.hana_volumen_table)
        logger.info("HANA escritura/carga: %s", config.HPR_HOST)
        logger.info("HANA lectura/consultas: %s", config.HPR_HOST_ESPEJO)
        logger.info("=" * 80)

        token = get_access_token(config, logger)
        pyflow_progress(10)

        queues: List[Dict[str, Any]] = []

        if not args.solo_volumenes:
            logger.info("=" * 80)
            logger.info("PASO 1/2: CARGA DE COLAS")
            logger.info("=" * 80)

            queues, queues_loaded, queues_failed = run_colas(
                config,
                token,
                logger,
                args.dry_run
            )

            total_queues = len(queues)
            queue_rows = queues
            pyflow_progress(35)

        if args.solo_volumenes:
            queues = read_queues_from_hana(config, logger)
            total_queues = len(queues)
            queue_rows = queues
            pyflow_progress(35)

        if not args.solo_colas:
            logger.info("=" * 80)
            logger.info("PASO 2/2: CARGA DE VOLUMENES DE COLAS")
            logger.info("=" * 80)

            volume_rows, volume_loaded, volume_failed, volume_interval_errors, volume_report_rows = run_volumenes(
                config,
                token,
                queues,
                start_dt,
                end_dt,
                logger,
                args.dry_run,
                45,
                78
            )
        else:
            pyflow_progress(78)

        if config.report_output_format or config.attach_report_file:
            queue_file = write_report_file(config, queue_rows, QUEUE_COLUMNS, "GNS_Colas", logger)
            if queue_file:
                output_files.append(queue_file)

            volume_file = write_report_file(config, volume_report_rows, VOLUME_COLUMNS, "GNS_Volumen_Colas", logger)
            if volume_file:
                output_files.append(volume_file)
        pyflow_progress(90)

    except Exception as exc:
        total_errors.append(str(exc))
        logger.exception("El proceso terminó con error general: %s", exc)
        logger.error(traceback.format_exc())

    duration = time.time() - start_time

    logger.info("=" * 80)
    logger.info("RESUMEN FINAL")
    logger.info("Colas obtenidas: %s", total_queues)
    logger.info("Colas cargadas: %s", queues_loaded)
    logger.info("Colas fallidas: %s", queues_failed)
    logger.info("Filas volumen transformadas: %s", volume_rows)
    logger.info("Filas volumen cargadas: %s", volume_loaded)
    logger.info("Filas volumen fallidas: %s", volume_failed)
    logger.info("Intervalos volumen con error: %s", volume_interval_errors)
    logger.info("Archivos generados: %s", len(output_files))
    for path in output_files:
        logger.info("Archivo: %s", path)
    logger.info("Errores generales: %s", len(total_errors))

    for err in total_errors[:20]:
        logger.error("Detalle error: %s", err)

    logger.info("Duración total: %.2f segundos", duration)
    logger.info("=" * 80)

    if config:
        enviar_reporte_colas_volumenes(
            config,
            total_queues,
            queues_loaded,
            queues_failed,
            volume_rows,
            volume_loaded,
            volume_failed,
            volume_interval_errors,
            date_mode,
            duration,
            output_files,
            logger
        )

    pyflow_progress(100)

    if total_errors or queues_failed or volume_failed or volume_interval_errors:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
