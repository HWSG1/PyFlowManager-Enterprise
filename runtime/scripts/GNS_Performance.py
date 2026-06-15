# =========================================================
# GNS PERFORMANCE - Genesys Cloud -> SAP HANA
# PyFlow Manager
# =========================================================
#
# Objetivo:
# - Consultar métricas de performance de agentes por usuario/cola desde Genesys.
# - Cruzar con catálogos de usuarios y colas desde SAP HANA ESPEJO.
# - Cargar resultado en SAP HANA PRINCIPAL.
#
# Servidores HANA:
# - HPR_HOST: servidor principal para escritura (DELETE / INSERT / MERGE)
# - HPR_HOST_ESPEJO: servidor espejo para lectura (SELECT)
#
# =========================================================

import os
import sys
import time
import math
import argparse
import logging
import traceback
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Tuple, Optional

import requests

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False

try:
    from hdbcli import dbapi
except Exception:
    dbapi = None


PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Genesys Region / Domain", "required": True},

    "HPR_HOST": {"type": "global", "global_key": "HPR_HOST", "label": "SAP HANA Host Escritura", "required": True},
    "HPR_HOST_ESPEJO": {"type": "global", "global_key": "HPR_HOST_ESPEJO", "label": "SAP HANA Host Espejo Lectura", "required": True},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "SAP HANA Port", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "SAP HANA User", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "SAP HANA Password", "required": True, "secret": True},

    "HANA_SCHEMA": {"type": "text", "label": "Esquema HANA", "required": True, "default": "BI_SS"},
    "HANA_USERS_TABLE": {"type": "text", "label": "Tabla usuarios Genesys", "required": True, "default": "GNS_API_USUARIOS"},
    "HANA_QUEUES_TABLE": {"type": "text", "label": "Tabla colas Genesys", "required": True, "default": "GNS_API_COLAS"},
    "HANA_PERFORMANCE_TABLE": {"type": "text", "label": "Tabla destino performance", "required": True, "default": "GNS_API_PERFORMANCE"},

    "DATE": {"type": "date", "label": "Fecha específica local", "required": False},
    "START_DATE": {"type": "date", "label": "Fecha inicial local", "required": False},
    "END_DATE": {"type": "date", "label": "Fecha final local", "required": False},
    "DAYS_BACK": {"type": "number", "label": "Días hacia atrás si no se indican fechas", "required": False, "default": "5"},

    "GENESYS_TIMEZONE": {"type": "text", "label": "Zona horaria Genesys", "required": True, "default": "America/Tegucigalpa"},
    "GRANULARITY": {"type": "select", "label": "Granularidad", "required": True, "options": ["PT30M", "PT15M", "PT1H"], "default": "PT30M"},

    "BATCH_SIZE_USERS": {"type": "number", "label": "Usuarios por consulta Genesys", "required": False, "default": "50"},
    "MAX_USERS": {"type": "number", "label": "Máximo usuarios para prueba; vacío = todos", "required": False},
    "EXCLUDE_DIVISIONS": {"type": "text", "label": "Divisiones excluidas separadas por coma", "required": False, "default": "TeleventasMP"},

    "HANA_BATCH_SIZE": {"type": "number", "label": "Filas por lote HANA", "required": False, "default": "1000"},
    "REQUEST_TIMEOUT": {"type": "number", "label": "Timeout HTTP segundos", "required": False, "default": "120"},
    "API_SLEEP_SECONDS": {"type": "number", "label": "Pausa entre requests", "required": False, "default": "1"},
    "MAX_RETRIES": {"type": "number", "label": "Reintentos HTTP", "required": False, "default": "5"},

    "DELETE_RANGE_BEFORE_LOAD": {"type": "select", "label": "Borrar rango antes de cargar", "required": True, "options": ["true", "false"], "default": "true"},
    "DRY_RUN": {"type": "select", "label": "Modo prueba sin insertar", "required": True, "options": ["true", "false"], "default": "false"},
    "OUTPUT_CSV": {"type": "text", "label": "Ruta CSV opcional", "required": False}
}


LOGGER_NAME = "gns_performance_pyflow"


def _clean_env_value(value: Any, default: Optional[str] = None) -> Optional[str]:
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


def normalize_genesys_domain(value: str) -> str:
    value = str(value or "mypurecloud.com").strip()
    value = value.replace("https://", "").replace("http://", "").strip("/")
    if value.startswith("api."):
        value = value[4:]
    if value.startswith("login."):
        value = value[6:]
    return value


def genesys_api_url_from_region(region: str) -> str:
    return f"https://api.{normalize_genesys_domain(region)}"


def genesys_login_url_from_region(region: str) -> str:
    return f"https://login.{normalize_genesys_domain(region)}/oauth/token"


@dataclass
class Config:
    genesys_client_id: str
    genesys_client_secret: str
    genesys_api_url: str
    genesys_login_url: str

    hana_host_write: str
    hana_host_read: str
    hana_port: int
    hana_user: str
    hana_password: str

    hana_schema: str
    users_table: str
    queues_table: str
    performance_table: str

    timezone_name: str
    granularity: str
    batch_size_users: int
    hana_batch_size: int
    request_timeout: int
    api_sleep_seconds: float
    max_retries: int


def load_config() -> Config:
    try:
        load_dotenv()
    except Exception:
        pass

    region = env_str("GENESYS_REGION", "mypurecloud.com", required=True)

    return Config(
        genesys_client_id=env_str("GENESYS_CLIENT_ID", required=True),
        genesys_client_secret=env_str("GENESYS_CLIENT_SECRET", required=True),
        genesys_api_url=genesys_api_url_from_region(region),
        genesys_login_url=genesys_login_url_from_region(region),

        hana_host_write=env_str("HPR_HOST", required=True),
        hana_host_read=env_str("HPR_HOST_ESPEJO", env_str("HPR_HOST", ""), required=True),
        hana_port=env_int("HPR_PORT", 30015, required=True),
        hana_user=env_str("HPR_USER", required=True),
        hana_password=env_str("HPR_PASSWORD", required=True),

        hana_schema=env_str("HANA_SCHEMA", "BI_SS"),
        users_table=env_str("HANA_USERS_TABLE", "GNS_API_USUARIOS"),
        queues_table=env_str("HANA_QUEUES_TABLE", "GNS_API_COLAS"),
        performance_table=env_str("HANA_PERFORMANCE_TABLE", "GNS_API_PERFORMANCE"),

        timezone_name=env_str("GENESYS_TIMEZONE", "America/Tegucigalpa"),
        granularity=env_str("GRANULARITY", "PT30M"),
        batch_size_users=env_int("BATCH_SIZE_USERS", 50),
        hana_batch_size=env_int("HANA_BATCH_SIZE", 1000),
        request_timeout=env_int("REQUEST_TIMEOUT", 120),
        api_sleep_seconds=env_float("API_SLEEP_SECONDS", 1.0),
        max_retries=env_int("MAX_RETRIES", 5),
    )


def setup_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


def log_params(logger: logging.Logger) -> None:
    secret_words = ("SECRET", "PASSWORD", "TOKEN", "KEY")
    names = [
        "GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION",
        "HPR_HOST", "HPR_HOST_ESPEJO", "HPR_PORT", "HPR_USER", "HPR_PASSWORD",
        "HANA_SCHEMA", "HANA_USERS_TABLE", "HANA_QUEUES_TABLE", "HANA_PERFORMANCE_TABLE",
        "DATE", "START_DATE", "END_DATE", "DAYS_BACK", "GRANULARITY",
        "DELETE_RANGE_BEFORE_LOAD", "DRY_RUN"
    ]
    logger.info("Parámetros recibidos:")
    for name in names:
        value = env_str(name, "")
        shown = "********" if value and any(w in name.upper() for w in secret_words) else (value or "<vacío>")
        logger.info("- %s: %s", name, shown)


def parse_local_date(value: str) -> date:
    value = env_str("_DATE_TMP", value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            pass
    raise ValueError(f"Fecha inválida: {value!r}. Use YYYY-MM-DD o DD/MM/YYYY.")


def parse_dates(args: argparse.Namespace, tz_name: str) -> Tuple[datetime, datetime, str]:
    tz = ZoneInfo(tz_name)

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
        end_dt = datetime(d2.year, d2.month, d2.day, 0, 0, 0, tzinfo=tz) + timedelta(days=1)
        return start_dt, end_dt, f"Rango local {d1.isoformat()} al {d2.isoformat()}"

    days_back = env_int("DAYS_BACK", 5)
    if days_back <= 0:
        raise ValueError("DAYS_BACK debe ser mayor que cero.")

    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = today - timedelta(days=days_back)
    end_dt = today
    return start_dt, end_dt, f"Automático últimos {days_back} días cerrados"


def fmt_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def build_12h_intervals(start_dt: datetime, end_dt: datetime) -> List[Tuple[datetime, datetime]]:
    intervals = []
    current = start_dt
    while current < end_dt:
        nxt = min(current + timedelta(hours=12), end_dt)
        intervals.append((current, nxt))
        current = nxt
    return intervals


def request_with_retry(method: str, url: str, config: Config, logger: logging.Logger, **kwargs) -> requests.Response:
    last_error = None

    for attempt in range(1, config.max_retries + 1):
        try:
            response = requests.request(method, url, timeout=config.request_timeout, **kwargs)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * attempt)
                logger.warning("HTTP 429 | intento %s/%s | esperando %s segundos...", attempt, config.max_retries, wait)
                time.sleep(wait)
                continue

            if response.status_code >= 500:
                wait = min(60, 5 * attempt)
                logger.warning("HTTP %s | intento %s/%s | esperando %s segundos...", response.status_code, attempt, config.max_retries, wait)
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                logger.error("Error HTTP %s | Respuesta: %s", response.status_code, response.text[:1000])

            response.raise_for_status()
            return response

        except Exception as exc:
            last_error = exc
            wait = min(60, 5 * attempt)
            logger.warning("Error request | intento %s/%s | %s | esperando %s segundos...", attempt, config.max_retries, exc, wait)
            time.sleep(wait)

    raise RuntimeError(f"No se pudo completar request después de {config.max_retries} intentos: {last_error}")


def get_access_token(config: Config, logger: logging.Logger) -> str:
    logger.info("Solicitando token OAuth en Genesys Cloud...")
    response = request_with_retry(
        "POST",
        config.genesys_login_url,
        config,
        logger,
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
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def validate_identifier(value: str) -> None:
    import re
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""):
        raise ValueError(f"Identificador SQL inválido: {value}")


def hana_connect_read(config: Config):
    if dbapi is None:
        raise RuntimeError("No está instalado hdbcli. Ejecuta: pip install hdbcli")
    return dbapi.connect(address=config.hana_host_read, port=config.hana_port, user=config.hana_user, password=config.hana_password)


def hana_connect_write(config: Config):
    if dbapi is None:
        raise RuntimeError("No está instalado hdbcli. Ejecuta: pip install hdbcli")
    return dbapi.connect(address=config.hana_host_write, port=config.hana_port, user=config.hana_user, password=config.hana_password)


def fetch_users_from_hana(config: Config, logger: logging.Logger) -> List[Dict[str, Any]]:
    schema = config.hana_schema
    table = config.users_table
    validate_identifier(schema)
    validate_identifier(table)

    sql = f'SELECT ID, UPPER(NAME) AS USER_NAME, UPPER(EMAIL) AS EMAIL FROM "{schema}"."{table}" WHERE ID IS NOT NULL'
    max_users = env_str("MAX_USERS", "")
    if max_users:
        sql += f" LIMIT {int(max_users)}"

    logger.info('Leyendo usuarios desde HANA ESPEJO "%s"."%s"...', schema, table)

    conn = hana_connect_read(config)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        rows = [{"ID": r[0], "USER_NAME": r[1], "EMAIL": r[2]} for r in cur.fetchall() if r and r[0]]
        logger.info("Usuarios leídos: %s", len(rows))
        return rows
    finally:
        cur.close()
        conn.close()


def fetch_queues_from_hana(config: Config, logger: logging.Logger) -> List[Dict[str, Any]]:
    schema = config.hana_schema
    table = config.queues_table
    validate_identifier(schema)
    validate_identifier(table)

    exclude_divisions = [x.strip().upper() for x in env_str("EXCLUDE_DIVISIONS", "TeleventasMP").split(",") if x.strip()]
    sql = f'SELECT DISTINCT ID, QUEUE_NAME, DIVISION_ID, DIVISION_NAME FROM "{schema}"."{table}" WHERE ID IS NOT NULL'

    params = []
    if exclude_divisions:
        placeholders = ", ".join(["?"] * len(exclude_divisions))
        sql += f' AND UPPER(DIVISION_NAME) NOT IN ({placeholders})'
        params = exclude_divisions

    logger.info('Leyendo colas desde HANA ESPEJO "%s"."%s"...', schema, table)

    conn = hana_connect_read(config)
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        rows = [{"ID": r[0], "QUEUE_NAME": r[1], "DIVISION_ID": r[2], "DIVISION_NAME": r[3]} for r in cur.fetchall() if r and r[0]]
        logger.info("Colas leídas: %s", len(rows))
        return rows
    finally:
        cur.close()
        conn.close()


def delete_existing_range(config: Config, start_dt: datetime, end_dt: datetime, logger: logging.Logger) -> int:
    schema = config.hana_schema
    table = config.performance_table
    validate_identifier(schema)
    validate_identifier(table)

    start_str = fmt_local(start_dt)
    end_str = fmt_local(end_dt)

    logger.info('Eliminando rango existente en HANA PRINCIPAL "%s"."%s": %s -> %s...', schema, table, start_str, end_str)

    conn = hana_connect_write(config)
    cur = conn.cursor()
    try:
        sql = f'DELETE FROM "{schema}"."{table}" WHERE "START_DATE" >= ? AND "START_DATE" < ?'
        cur.execute(sql, (start_str, end_str))
        deleted = cur.rowcount
        conn.commit()
        logger.info("Registros eliminados previamente: %s", deleted)
        return deleted
    finally:
        cur.close()
        conn.close()


METRICS = [
    "tAnswered", "tHandle", "tAcw", "tAlert", "tConnected", "tTalkComplete",
    "tAgentResponseTime", "tHeldComplete", "tAverageAgentResponseTime",
    "tFirstEngagement", "tFirstResponse", "nError", "nOutboundConnected",
    "tNotResponding", "nBlindTransferred", "nTransferred", "nConsult",
    "tActiveCallback", "tFirstDial", "nOutbound", "tContacting", "tDialing", "tMonitoring",
]

METRIC_COLUMN_MAP = {
    ("tAnswered", "count"): "ANSWERED_NUMBER", ("tAnswered", "sum"): "ANSWERED_TIME",
    ("tHandle", "count"): "HANDLE_NUMBER", ("tHandle", "sum"): "HANDLE_TIME",
    ("tAcw", "count"): "ACW_NUMBER", ("tAcw", "sum"): "ACW_TIME",
    ("tAlert", "count"): "ALERT_NUMBER", ("tAlert", "sum"): "ALERT_TIME",
    ("tConnected", "count"): "CONNECTED_NUMBER", ("tConnected", "sum"): "CONNECTED_TIME",
    ("tTalkComplete", "count"): "TALK_NUMBER", ("tTalkComplete", "sum"): "TALK_TIME",
    ("tAgentResponseTime", "count"): "AGENT_RESPONSE_NUMBER", ("tAgentResponseTime", "sum"): "AGENT_RESPONSE_TIME",
    ("tHeldComplete", "count"): "HOLD_NUMBER", ("tHeldComplete", "sum"): "HOLD_TIME",
    ("tAverageAgentResponseTime", "count"): "AVERAGE_AGENT_RESPONSE_NUMBER", ("tAverageAgentResponseTime", "sum"): "AVERAGE_AGENT_RESPONSE_TIME",
    ("tFirstEngagement", "count"): "FIRST_ENGAGEMENT_NUMBER", ("tFirstEngagement", "sum"): "FIRST_ENGAGEMENT_TIME",
    ("tFirstResponse", "count"): "FIRST_RESPONSE_NUMBER", ("tFirstResponse", "sum"): "FIRST_RESPONSE_TIME",
    ("nError", "count"): "ERROR_NUMBER",
    ("nOutboundConnected", "count"): "OUTBOUND_CONNECTED_NUMBER",
    ("tNotResponding", "count"): "NOT_RESPONDING_NUMBER", ("tNotResponding", "sum"): "NOT_RESPONDING_TIME",
    ("nBlindTransferred", "count"): "BLIND_TRANSFERRED",
    ("nTransferred", "count"): "TRANSFERRED_NUMBER",
    ("nConsult", "count"): "CONSULT_TRANSFERRED_NUMBER",
    ("tActiveCallback", "count"): "ACTIVE_CALLBACK_NUMBER", ("tActiveCallback", "sum"): "ACTIVE_CALLBACK_TIME",
    ("tFirstDial", "count"): "FIRST_DIAL_NUMBER", ("tFirstDial", "sum"): "FIRST_DIAL_TIME",
    ("nOutbound", "count"): "OUTBOUND_NUMBER",
    ("tContacting", "count"): "CONTACTING_NUMBER", ("tContacting", "sum"): "CONTACTING_TIME",
    ("tDialing", "count"): "DIALING_NUMBER", ("tDialing", "sum"): "DIALING_TIME",
    ("tMonitoring", "count"): "MONITORING_NUMBER", ("tMonitoring", "sum"): "MONITORING_TIME",
}

PERFORMANCE_COLUMNS = [
    "ID_UNICO", "DIRECTION", "MEDIATYPE", "USER_ID", "USER_NAME", "EMAIL",
    "QUEUE_ID", "QUEUE_NAME", "DIVISION_ID", "DIVISION_NAME", "START_DATE", "FINISH_DATE",
    "ANSWERED_NUMBER", "ANSWERED_TIME", "HANDLE_NUMBER", "HANDLE_TIME", "ACW_NUMBER", "ACW_TIME",
    "ALERT_NUMBER", "ALERT_TIME", "CONNECTED_NUMBER", "CONNECTED_TIME", "TALK_NUMBER", "TALK_TIME",
    "AGENT_RESPONSE_TIME", "AGENT_RESPONSE_NUMBER", "HOLD_NUMBER", "HOLD_TIME",
    "AVERAGE_AGENT_RESPONSE_NUMBER", "AVERAGE_AGENT_RESPONSE_TIME",
    "FIRST_ENGAGEMENT_NUMBER", "FIRST_ENGAGEMENT_TIME", "FIRST_RESPONSE_NUMBER", "FIRST_RESPONSE_TIME",
    "ERROR_NUMBER", "OUTBOUND_CONNECTED_NUMBER", "NOT_RESPONDING_NUMBER", "NOT_RESPONDING_TIME",
    "BLIND_TRANSFERRED", "TRANSFERRED_NUMBER", "CONSULT_TRANSFERRED_NUMBER",
    "ACTIVE_CALLBACK_NUMBER", "ACTIVE_CALLBACK_TIME", "FIRST_DIAL_NUMBER", "FIRST_DIAL_TIME",
    "OUTBOUND_NUMBER", "CONTACTING_NUMBER", "CONTACTING_TIME", "DIALING_NUMBER", "DIALING_TIME",
    "MONITORING_NUMBER", "MONITORING_TIME", "FECHA_CARGA",
]


def empty_performance_row() -> Dict[str, Any]:
    return {c: None for c in PERFORMANCE_COLUMNS}


def build_lookup(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(r.get("ID")): r for r in rows if r.get("ID")}


def make_id_unico(row: Dict[str, Any]) -> str:
    parts = [row.get("DIRECTION"), row.get("MEDIATYPE"), row.get("USER_ID"), row.get("QUEUE_ID"), row.get("START_DATE"), row.get("FINISH_DATE")]
    return "_".join("" if p is None else str(p) for p in parts).replace("__", "_").strip("_")


def query_performance(config: Config, token: str, user_ids: List[str], start_dt: datetime, end_dt: datetime, logger: logging.Logger) -> Dict[str, Any]:
    url = f"{config.genesys_api_url}/api/v2/analytics/conversations/aggregates/query"

    body = {
        "interval": f"{fmt_local(start_dt)}/{fmt_local(end_dt)}",
        "timeZone": config.timezone_name,
        "groupBy": ["userId", "queueId", "mediaType", "direction"],
        "filter": {
            "type": "and",
            "clauses": [
                {"type": "or", "predicates": [{"dimension": "userId", "value": uid} for uid in user_ids]},
                {"type": "or", "predicates": [{"dimension": "queueId", "operator": "EXISTS"}]},
            ],
        },
        "metrics": METRICS,
        "flattenMultivaluedDimensions": True,
        "granularity": config.granularity,
        "alternateTimeDimension": "eventTime",
    }

    response = request_with_retry("POST", url, config, logger, headers=genesys_headers(token), json=body)
    return response.json()


def transform_performance_response(data: Dict[str, Any], user_lookup: Dict[str, Dict[str, Any]], queue_lookup: Dict[str, Dict[str, Any]], fecha_carga: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for result in data.get("results") or []:
        group = result.get("group") or {}
        user_id = group.get("userId")
        queue_id = group.get("queueId")
        user_info = user_lookup.get(str(user_id), {})
        queue_info = queue_lookup.get(str(queue_id), {})

        for item in result.get("data") or []:
            interval = item.get("interval") or ""
            if "/" in interval:
                start_date, finish_date = interval.split("/", 1)
            else:
                start_date, finish_date = None, None

            row = empty_performance_row()
            row["DIRECTION"] = group.get("direction")
            row["MEDIATYPE"] = group.get("mediaType")
            row["USER_ID"] = user_id
            row["USER_NAME"] = user_info.get("USER_NAME")
            row["EMAIL"] = user_info.get("EMAIL")
            row["QUEUE_ID"] = queue_id
            row["QUEUE_NAME"] = queue_info.get("QUEUE_NAME")
            row["DIVISION_ID"] = queue_info.get("DIVISION_ID")
            row["DIVISION_NAME"] = queue_info.get("DIVISION_NAME")
            row["START_DATE"] = start_date
            row["FINISH_DATE"] = finish_date
            row["FECHA_CARGA"] = fecha_carga

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


def fetch_performance_rows(config: Config, token: str, users: List[Dict[str, Any]], queues: List[Dict[str, Any]], start_dt: datetime, end_dt: datetime, logger: logging.Logger) -> Tuple[List[Dict[str, Any]], int]:
    user_lookup = build_lookup(users)
    queue_lookup = build_lookup(queues)
    user_ids = list(user_lookup.keys())
    intervals = build_12h_intervals(start_dt, end_dt)
    total_batches = math.ceil(len(user_ids) / config.batch_size_users) if user_ids else 0
    all_rows: List[Dict[str, Any]] = []
    errors = 0
    fecha_carga = datetime.now(ZoneInfo(config.timezone_name)).strftime("%Y-%m-%d %H:%M:%S")

    logger.info("Intervalos a procesar: %s | batches por intervalo: %s", len(intervals), total_batches)

    for i, (ini, fin) in enumerate(intervals, start=1):
        for b, start_idx in enumerate(range(0, len(user_ids), config.batch_size_users), start=1):
            batch_ids = user_ids[start_idx:start_idx + config.batch_size_users]
            try:
                logger.info("Consultando Genesys intervalo %s/%s batch %s/%s | %s -> %s | usuarios: %s", i, len(intervals), b, total_batches, fmt_local(ini), fmt_local(fin), len(batch_ids))
                data = query_performance(config, token, batch_ids, ini, fin, logger)
                rows = transform_performance_response(data, user_lookup, queue_lookup, fecha_carga)
                all_rows.extend(rows)
                logger.info("Filas obtenidas: %s | acumulado: %s", len(rows), len(all_rows))
                time.sleep(config.api_sleep_seconds)
            except Exception as exc:
                errors += 1
                logger.exception("Error consultando intervalo/batch: %s", exc)
                time.sleep(max(config.api_sleep_seconds, 5))

    return all_rows, errors



def get_hana_table_columns(config: Config, logger: logging.Logger) -> List[str]:
    """
    Lee las columnas reales de la tabla destino en SAP HANA.

    Motivo:
    Algunos ambientes tienen tablas históricas con columnas distintas al
    diccionario del script. Para evitar errores como:
      invalid column name: CONNECTED_NUMBER
    el MERGE usará únicamente las columnas que existan en la tabla destino.
    """
    schema = config.hana_schema
    table = config.performance_table
    validate_identifier(schema)
    validate_identifier(table)

    sql = """
        SELECT COLUMN_NAME
        FROM SYS.TABLE_COLUMNS
        WHERE SCHEMA_NAME = ?
          AND TABLE_NAME = ?
        ORDER BY POSITION
    """

    conn = hana_connect_read(config)
    cur = conn.cursor()
    try:
        cur.execute(sql, (schema, table))
        cols = [str(r[0]) for r in cur.fetchall()]
        logger.info('Columnas detectadas en HANA espejo para "%s"."%s": %s', schema, table, len(cols))
        return cols
    finally:
        cur.close()
        conn.close()

def merge_rows_to_hana(config: Config, rows: List[Dict[str, Any]], logger: logging.Logger) -> Tuple[int, int]:
    if not rows:
        logger.warning("No hay filas para cargar en HANA.")
        return 0, 0

    schema = config.hana_schema
    table = config.performance_table
    validate_identifier(schema)
    validate_identifier(table)

    table_columns = get_hana_table_columns(config, logger)
    table_column_set = {c.upper() for c in table_columns}

    # Usar solo columnas que existen físicamente en HANA.
    cols = [c for c in PERFORMANCE_COLUMNS if c.upper() in table_column_set]
    skipped_cols = [c for c in PERFORMANCE_COLUMNS if c.upper() not in table_column_set]

    if skipped_cols:
        logger.warning(
            "Columnas del script que no existen en HANA y serán omitidas: %s",
            ", ".join(skipped_cols)
        )

    if "ID_UNICO" not in cols:
        raise RuntimeError('La tabla destino debe tener la columna llave "ID_UNICO" para ejecutar el MERGE.')

    select_cols = ", ".join([f'? AS "{c}"' for c in cols])
    update_cols = ", ".join([f'T."{c}" = S."{c}"' for c in cols if c != "ID_UNICO"])
    insert_cols = ", ".join([f'"{c}"' for c in cols])
    insert_values = ", ".join([f'S."{c}"' for c in cols])

    sql = f'''
        MERGE INTO "{schema}"."{table}" AS T
        USING (
            SELECT {select_cols}
            FROM DUMMY
        ) AS S
        ON T."ID_UNICO" = S."ID_UNICO"
        WHEN MATCHED THEN
            UPDATE SET {update_cols}
        WHEN NOT MATCHED THEN
            INSERT ({insert_cols})
            VALUES ({insert_values})
    '''

    loaded = 0
    failed = 0
    conn = hana_connect_write(config)
    cur = conn.cursor()

    try:
        logger.info('Iniciando MERGE en HANA PRINCIPAL "%s"."%s"...', schema, table)
        for start in range(0, len(rows), config.hana_batch_size):
            batch = rows[start:start + config.hana_batch_size]
            values = [tuple(row.get(c) for c in cols) for row in batch]
            try:
                cur.executemany(sql, values)
                conn.commit()
                loaded += len(batch)
                logger.info("Merge parcial OK | lote: %s | acumulado: %s/%s", len(batch), loaded, len(rows))
            except Exception as exc:
                conn.rollback()
                failed += len(batch)
                logger.exception("Error en lote HANA desde fila %s: %s", start + 1, exc)
    finally:
        cur.close()
        conn.close()

    return loaded, failed


def write_csv(rows: List[Dict[str, Any]], output_csv: str, logger: logging.Logger) -> None:
    if not output_csv:
        return

    import csv

    if os.path.isdir(output_csv) or output_csv.endswith("\\") or output_csv.endswith("/"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = os.path.join(output_csv, f"GNS_Performance_{timestamp}.csv")

    out_dir = os.path.dirname(output_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PERFORMANCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("CSV generado: %s", output_csv)


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga Genesys Performance a SAP HANA")
    parser.add_argument("--date", default=env_str("DATE", ""), help="Fecha local específica YYYY-MM-DD")
    parser.add_argument("--start-date", default=env_str("START_DATE", ""), help="Fecha inicial local inclusiva YYYY-MM-DD")
    parser.add_argument("--end-date", default=env_str("END_DATE", ""), help="Fecha final local inclusiva YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="No carga a HANA")
    args = parser.parse_args()

    if env_bool("DRY_RUN", False):
        args.dry_run = True

    logger = setup_logger()
    start_time = time.time()
    total_rows = 0
    loaded = 0
    failed = 0
    query_errors = 0
    general_errors: List[str] = []

    try:
        config = load_config()
        start_dt, end_dt, date_mode = parse_dates(args, config.timezone_name)

        logger.info("=" * 80)
        logger.info("INICIO PROCESO GNS PERFORMANCE")
        log_params(logger)
        logger.info("Modo fecha: %s", date_mode)
        logger.info("Inicio local API: %s", fmt_local(start_dt))
        logger.info("Fin local API: %s", fmt_local(end_dt))
        logger.info("HANA lectura espejo: %s", config.hana_host_read)
        logger.info("HANA escritura principal: %s", config.hana_host_write)
        logger.info("Tabla destino: %s.%s", config.hana_schema, config.performance_table)
        logger.info("=" * 80)

        token = get_access_token(config, logger)
        users = fetch_users_from_hana(config, logger)
        queues = fetch_queues_from_hana(config, logger)

        if not users:
            raise RuntimeError("No se encontraron usuarios en HANA para consultar performance.")
        if not queues:
            raise RuntimeError("No se encontraron colas en HANA para cruzar performance.")

        rows, query_errors = fetch_performance_rows(config, token, users, queues, start_dt, end_dt, logger)
        total_rows = len(rows)

        logger.info("Extracción finalizada. Filas transformadas: %s | errores consulta: %s", total_rows, query_errors)

        output_csv = env_str("OUTPUT_CSV", "")
        if output_csv:
            write_csv(rows, output_csv, logger)

        if args.dry_run:
            logger.warning("DRY_RUN=true. No se cargará información a HANA.")
        else:
            if env_bool("DELETE_RANGE_BEFORE_LOAD", True):
                delete_existing_range(config, start_dt, end_dt, logger)
            loaded, failed = merge_rows_to_hana(config, rows, logger)

    except Exception as exc:
        general_errors.append(str(exc))
        logger.exception("Error general: %s", exc)
        logger.error(traceback.format_exc())

    duration = time.time() - start_time
    logger.info("=" * 80)
    logger.info("RESUMEN FINAL")
    logger.info("Filas transformadas: %s", total_rows)
    logger.info("Filas cargadas/actualizadas: %s", loaded)
    logger.info("Filas fallidas: %s", failed)
    logger.info("Errores consulta Genesys: %s", query_errors)
    logger.info("Errores generales: %s", len(general_errors))
    for err in general_errors[:20]:
        logger.error("Detalle error: %s", err)
    logger.info("Duración total: %.2f segundos", duration)
    logger.info("=" * 80)

    return 0 if not general_errors and failed == 0 and query_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
