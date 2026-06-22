# =========================================================
# GNS FORMULARIOS Y EVALUACIONES - Genesys Cloud -> SAP HANA
# =========================================================
#
# FORMAS DE EJECUCIÓN
# ---------------------------------------------------------
# 1. EJECUCIÓN AUTOMÁTICA
#    Calcula automáticamente desde el mismo día del mes anterior
#    hasta hoy 00:00, en zona horaria America/Tegucigalpa.
#
#    py .\GNS_Form_Evaluaciones.py
#
# 2. EJECUTAR UNA FECHA ESPECÍFICA
#
#    py .\GNS_Form_Evaluaciones.py --date 2026-05-27
#
# 3. EJECUTAR UN RANGO LOCAL
#
#    py .\GNS_Form_Evaluaciones.py --start-date 2026-05-01 --end-date 2026-05-27
#
# 4. EJECUTAR UTC EXACTO COMO KNIME
#
#    py .\GNS_Form_Evaluaciones.py --start-utc 2026-05-01T06:00:00.000Z --end-utc 2026-05-28T06:00:00.000Z
#
# 5. SOLO FORMULARIOS
#
#    py .\GNS_Form_Evaluaciones.py --solo-formularios
#
# 6. SOLO EVALUACIONES
#
#    py .\GNS_Form_Evaluaciones.py --solo-evaluaciones
#
# 7. PROBAR SIN CARGAR A HANA
#
#    py .\GNS_Form_Evaluaciones.py --dry-run
#
# VARIABLES OPCIONALES EN .env
# ---------------------------------------------------------
# HPR_HOST_ESPEJO=150.150.70.167  # Host réplica para SELECT
# HANA_FORM_EVALUACIONES_TABLE=GNS_API_FORM_EVALUACIONES
# HANA_EVALUACIONES_TABLE=GNS_API_EVALUACIONES
# API_SLEEP_SECONDS=1
# API_MAX_RETRIES=5
# HANA_BATCH_SIZE=1000
# GENESYS_TIMEZONE=America/Tegucigalpa
#
# DEPENDENCIA
# ---------------------------------------------------------
# Para evaluaciones, este script lee usuarios desde:
# BI_SS.GNS_API_USUARIOS
#
# Por eso conviene ejecutar antes:
# py ".\GNS Usuarios.py"
# =========================================================

import os
import sys
import time
import math
import argparse
import logging
import traceback
import csv
import base64
import mimetypes
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from html import escape
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
except ImportError:
    dbapi = None

try:
    import pandas as pd
except Exception:
    pd = None

# =========================================================
# PYFLOW MANAGER PARAMS
# =========================================================
# PyFlow detecta este bloque para solicitar parámetros y mapear variables globales.
# Si no se ingresan fechas, el script carga los últimos DAYS_BACK días cerrados.

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
    "HANA_FORM_EVALUACIONES_TABLE": {"type": "text", "label": "Tabla formularios/preguntas", "required": True, "default": "GNS_API_FORM_EVALUACIONES"},
    "HANA_EVALUACIONES_TABLE": {"type": "text", "label": "Tabla evaluaciones", "required": True, "default": "GNS_API_EVALUACIONES"},
    "RUN_MODE": {"type": "select", "label": "Modo ejecución", "required": True, "options": ["formularios_y_evaluaciones", "solo_formularios", "solo_evaluaciones"], "default": "formularios_y_evaluaciones"},
    "START_DATE": {"type": "date", "label": "Fecha inicial local", "required": False},
    "END_DATE": {"type": "date", "label": "Fecha final local", "required": False},
    "DAYS_BACK": {"type": "number", "label": "Días hacia atrás si no se indican fechas", "required": False, "default": "5"},
    "REPORT_OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida del reporte (opcional)", "required": False},
    "REPORT_OUTPUT_FORMAT": {"type": "select", "label": "Formato del reporte", "required": False, "options": ["xlsx", "csv"], "default": "xlsx"},
    "ATTACH_REPORT_FILE": {"type": "select", "label": "Adjuntar archivo al correo", "required": False, "options": ["false", "true"], "default": "false"},
    "GRAPH_TENANT_ID": {"type": "global", "global_key": "GRAPH_TENANT_ID", "label": "Microsoft Graph Tenant ID", "required": False},
    "GRAPH_CLIENT_ID": {"type": "global", "global_key": "GRAPH_CLIENT_ID", "label": "Microsoft Graph Client ID", "required": False},
    "GRAPH_CLIENT_SECRET": {"type": "global", "global_key": "GRAPH_CLIENT_SECRET", "label": "Microsoft Graph Client Secret", "required": False, "secret": True},
    "GRAPH_SENDER_EMAIL": {"type": "global", "global_key": "GRAPH_SENDER_EMAIL", "label": "Correo remitente Graph", "required": False},
    "FORM_EVALUACIONES_REPORT_EMAIL_TO": {"type": "tags", "label": "Destinatarios reporte formularios/evaluaciones", "required": False},
    "FORM_EVALUACIONES_REPORT_EMAIL_CC": {"type": "tags", "label": "Copias reporte formularios/evaluaciones", "required": False},
    "FORM_EVALUACIONES_REPORT_SUBJECT": {"type": "text", "label": "Asunto reporte formularios/evaluaciones", "required": False, "default": "Reporte de Formularios y Evaluaciones Genesys"}
}

LOGGER_NAME = "gns_form_evaluaciones_pyflow"


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
    value = env_str("GENESYS_REGION", value, required=False)
    value = str(value or "mypurecloud.com").strip()
    value = value.replace("https://", "").replace("http://", "").strip("/")
    if value.startswith("api."):
        value = value[4:]
    if value.startswith("login."):
        value = value[6:]
    return value


def genesys_api_url_from_region(default_region: str = "mypurecloud.com") -> str:
    return f"https://api.{normalize_genesys_domain(default_region)}"


def genesys_login_url_from_region(default_region: str = "mypurecloud.com") -> str:
    return f"https://login.{normalize_genesys_domain(default_region)}/oauth/token"


def log_params(logger: logging.Logger, names: List[str]) -> None:
    logger.info("Parámetros recibidos / aplicados:")
    secret_words = ("SECRET", "PASSWORD", "TOKEN", "KEY")
    for name in names:
        value = env_str(name, "")
        if any(w in name.upper() for w in secret_words) and value:
            value = "********"
        logger.info("- %s: %s", name, value if value != "" else "<vacío>")


@dataclass
class Config:
    genesys_client_id: str
    genesys_client_secret: str
    genesys_region_base_url: str
    genesys_login_url: str

    hana_host: str
    hana_host_espejo: str
    hana_port: int
    hana_user: str
    hana_password: str
    hana_schema: str

    users_table: str
    forms_table: str
    evaluations_table: str

    timezone_name: str
    batch_size: int
    request_timeout: int
    api_sleep_seconds: float
    api_max_retries: int
    report_output_dir: str
    report_output_format: str
    attach_report_file: bool
    graph_tenant_id: str
    graph_client_id: str
    graph_client_secret: str
    graph_sender_email: str
    report_email_to: List[str]
    report_email_cc: List[str]
    report_email_subject: str


def get_env(name: str, default: Optional[str] = None, required: bool = True) -> str:
    return env_str(name, default, required=required)


def load_config() -> Config:
    load_dotenv()

    region_base = get_env("GENESYS_REGION_BASE_URL", genesys_api_url_from_region(), required=False).rstrip("/")

    return Config(
        genesys_client_id=get_env("GENESYS_CLIENT_ID"),
        genesys_client_secret=get_env("GENESYS_CLIENT_SECRET"),
        genesys_region_base_url=region_base,
        genesys_login_url=get_env("GENESYS_LOGIN_URL", genesys_login_url_from_region(), required=False),

        hana_host=get_env("HPR_HOST", required=True),
        hana_host_espejo=get_env("HPR_HOST_ESPEJO", required=True),
        hana_port=env_int("HPR_PORT", 30015, required=True),
        hana_user=get_env("HPR_USER", required=True),
        hana_password=get_env("HPR_PASSWORD", required=True),
        hana_schema=get_env("HANA_SCHEMA", "BI_SS", required=False),

        users_table=get_env("HANA_USERS_TABLE", "GNS_API_USUARIOS", required=False),
        forms_table=get_env("HANA_FORM_EVALUACIONES_TABLE", "GNS_API_FORM_EVALUACIONES", required=False),
        evaluations_table=get_env("HANA_EVALUACIONES_TABLE", "GNS_API_EVALUACIONES", required=False),

        timezone_name=get_env("GENESYS_TIMEZONE", "America/Tegucigalpa", required=False),
        batch_size=env_int("HANA_BATCH_SIZE", 1000),
        request_timeout=env_int("REQUEST_TIMEOUT", 120),
        api_sleep_seconds=env_float("API_SLEEP_SECONDS", 1.0),
        api_max_retries=env_int("API_MAX_RETRIES", 5),
        report_output_dir=env_str("REPORT_OUTPUT_DIR", ""),
        report_output_format=env_str("REPORT_OUTPUT_FORMAT", "xlsx").lower(),
        attach_report_file=env_bool("ATTACH_REPORT_FILE", False),
        graph_tenant_id=env_str("GRAPH_TENANT_ID", ""),
        graph_client_id=env_str("GRAPH_CLIENT_ID", ""),
        graph_client_secret=env_str("GRAPH_CLIENT_SECRET", ""),
        graph_sender_email=env_str("GRAPH_SENDER_EMAIL", ""),
        report_email_to=split_list_value(env_str("FORM_EVALUACIONES_REPORT_EMAIL_TO", "")),
        report_email_cc=split_list_value(env_str("FORM_EVALUACIONES_REPORT_EMAIL_CC", "")),
        report_email_subject=env_str("FORM_EVALUACIONES_REPORT_SUBJECT", "Reporte de Formularios y Evaluaciones Genesys"),
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


def hana_connect_write(config: Config):
    """Conexión SAP HANA para escrituras: INSERT, UPDATE, DELETE, MERGE."""
    if dbapi is None:
        raise RuntimeError("No está instalado hdbcli. Ejecuta: pip install hdbcli")
    return dbapi.connect(
        address=config.hana_host,
        port=config.hana_port,
        user=config.hana_user,
        password=config.hana_password
    )


def hana_connect_read(config: Config):
    """Conexión SAP HANA para lecturas: SELECT y catálogos."""
    if dbapi is None:
        raise RuntimeError("No está instalado hdbcli. Ejecuta: pip install hdbcli")
    return dbapi.connect(
        address=config.hana_host_espejo,
        port=config.hana_port,
        user=config.hana_user,
        password=config.hana_password
    )


def to_utc_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def parse_dates(args: argparse.Namespace, tz_name: str) -> Tuple[str, str, str]:
    tz = ZoneInfo(tz_name)

    if args.start_utc and args.end_utc:
        return args.start_utc, args.end_utc, "UTC manual"

    if args.date:
        d = date.fromisoformat(args.date)
        start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        return to_utc_z(start_local), to_utc_z(end_local), f"Día local {args.date}"

    if args.start_date and args.end_date:
        d1 = date.fromisoformat(args.start_date)
        d2 = date.fromisoformat(args.end_date)

        if d2 < d1:
            raise ValueError("La fecha final no puede ser menor que la fecha inicial.")

        start_local = datetime(d1.year, d1.month, d1.day, 0, 0, 0, tzinfo=tz)
        end_local = datetime(d2.year, d2.month, d2.day, 0, 0, 0, tzinfo=tz) + timedelta(days=1)

        return (
            to_utc_z(start_local),
            to_utc_z(end_local),
            f"Rango local {args.start_date} al {args.end_date}"
        )

    # Automático PyFlow: últimos DAYS_BACK días cerrados.
    # Ejemplo con DAYS_BACK=5 y hoy 2026-05-31:
    # 2026-05-26 00:00 -> 2026-05-31 00:00 hora local.
    days_back = env_int("DAYS_BACK", 5)
    if days_back <= 0:
        raise ValueError("DAYS_BACK debe ser mayor a 0.")

    today = datetime.now(tz)
    end_dt = today.replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(days=days_back)

    return to_utc_z(start_dt), to_utc_z(end_dt), f"Automático últimos {days_back} días cerrados"


def get_access_token(config: Config, logger: logging.Logger) -> str:
    logger.info("Solicitando token OAuth en Genesys Cloud...")

    response = requests.post(
        config.genesys_login_url,
        data={
            "grant_type": "client_credentials",
            "client_id": config.genesys_client_id,
            "client_secret": config.genesys_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=config.request_timeout,
    )

    response.raise_for_status()
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


def request_with_retries(
    method: str,
    url: str,
    config: Config,
    logger: logging.Logger,
    token: Optional[str] = None,
    **kwargs
) -> requests.Response:

    headers = kwargs.pop("headers", {})
    if token:
        headers.update(genesys_headers(token))

    last_exc: Optional[Exception] = None

    for attempt in range(1, config.api_max_retries + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                timeout=config.request_timeout,
                **kwargs
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * attempt)
                logger.warning(
                    "Rate limit 429 | intento %s/%s | esperando %s segundos | %s",
                    attempt,
                    config.api_max_retries,
                    wait_seconds,
                    url
                )
                time.sleep(wait_seconds)
                continue

            if 500 <= response.status_code <= 599:
                wait_seconds = min(60, 3 * attempt)
                logger.warning(
                    "Error servidor %s | intento %s/%s | esperando %s segundos | %s",
                    response.status_code,
                    attempt,
                    config.api_max_retries,
                    wait_seconds,
                    url
                )
                time.sleep(wait_seconds)
                continue

            response.raise_for_status()
            return response

        except Exception as exc:
            last_exc = exc
            wait_seconds = min(60, 3 * attempt)
            logger.warning(
                "Error request | intento %s/%s | esperando %s segundos | %s | %s",
                attempt,
                config.api_max_retries,
                wait_seconds,
                url,
                exc
            )
            time.sleep(wait_seconds)

    if last_exc:
        raise last_exc

    raise RuntimeError(f"No se pudo completar request: {url}")


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).replace("\t", "").strip()
    return text if text != "" else None


def bool_to_hana(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in ("true", "1", "yes", "y", "si", "sí"):
        return True
    if str(value).strip().lower() in ("false", "0", "no", "n"):
        return False
    return None


def safe_num(value: Any) -> Any:
    return None if value in (None, "") else value


# =========================================================
# HANA GENERIC HELPERS
# =========================================================

def delete_all_from_table(config: Config, table_name: str, logger: logging.Logger) -> int:
    logger.info('Eliminando registros existentes en "%s"."%s"...', config.hana_schema, table_name)

    conn = hana_connect_write(config)
    cursor = conn.cursor()

    try:
        sql = f'DELETE FROM "{config.hana_schema}"."{table_name}"'
        cursor.execute(sql)
        deleted = cursor.rowcount
        conn.commit()
        logger.info("Registros eliminados previamente: %s", deleted)
        return deleted

    finally:
        cursor.close()
        conn.close()


def insert_rows(
    config: Config,
    table_name: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    logger: logging.Logger
) -> Tuple[int, int]:

    if not rows:
        logger.warning('No hay filas para cargar en "%s"."%s".', config.hana_schema, table_name)
        return 0, 0

    quoted_cols = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["?"] * len(columns))

    sql = (
        f'INSERT INTO "{config.hana_schema}"."{table_name}" '
        f'({quoted_cols}) VALUES ({placeholders})'
    )

    loaded = 0
    failed = 0

    conn = hana_connect_write(config)
    cursor = conn.cursor()

    try:
        logger.info('Iniciando carga INSERT en "%s"."%s"...', config.hana_schema, table_name)

        for start in range(0, len(rows), config.batch_size):
            batch = rows[start:start + config.batch_size]
            values = [tuple(row.get(c) for c in columns) for row in batch]

            try:
                cursor.executemany(sql, values)
                conn.commit()
                loaded += len(batch)

                logger.info(
                    "Carga parcial confirmada | tabla: %s | lote: %s | cargados acumulados: %s/%s",
                    table_name,
                    len(batch),
                    loaded,
                    len(rows)
                )

            except Exception as exc:
                conn.rollback()
                failed += len(batch)
                logger.exception(
                    "Error cargando lote en tabla %s desde fila %s: %s",
                    table_name,
                    start + 1,
                    exc
                )

    finally:
        cursor.close()
        conn.close()

    return loaded, failed


def get_users_from_hana(config: Config, logger: logging.Logger) -> List[str]:
    logger.info('Leyendo usuarios desde "%s"."%s"...', config.hana_schema, config.users_table)

    conn = hana_connect_read(config)
    cursor = conn.cursor()

    try:
        sql = f'SELECT DISTINCT "ID" AS "USERID" FROM "{config.hana_schema}"."{config.users_table}" WHERE "ID" IS NOT NULL'
        cursor.execute(sql)
        users = [row[0] for row in cursor.fetchall() if row and row[0]]
        logger.info("Usuarios obtenidos para consultar evaluaciones: %s", len(users))
        return users

    finally:
        cursor.close()
        conn.close()


def get_question_lookup_from_hana(config: Config, logger: logging.Logger) -> Dict[str, str]:
    logger.info('Leyendo catálogo de preguntas desde "%s"."%s"...', config.hana_schema, config.forms_table)

    conn = hana_connect_read(config)
    cursor = conn.cursor()

    try:
        sql = (
            f'SELECT DISTINCT "ID_PREGUNTA", "PREGUNTA" '
            f'FROM "{config.hana_schema}"."{config.forms_table}" '
            f'WHERE "ID_PREGUNTA" IS NOT NULL'
        )
        cursor.execute(sql)
        lookup = {row[0]: row[1] for row in cursor.fetchall() if row and row[0]}
        logger.info("Preguntas disponibles para cruce: %s", len(lookup))
        return lookup

    finally:
        cursor.close()
        conn.close()


def delete_evaluations_range(
    config: Config,
    start_date: str,
    end_date: str,
    logger: logging.Logger
) -> int:

    logger.info(
        'Eliminando evaluaciones existentes en "%s"."%s" para rango %s -> %s...',
        config.hana_schema,
        config.evaluations_table,
        start_date,
        end_date
    )

    conn = hana_connect_write(config)
    cursor = conn.cursor()

    try:
        # En el flujo KNIME el endpoint filtra por startTime/endTime.
        # Se elimina por CONVERSATIONDATE porque viene del JSON de evaluación.
        sql = (
            f'DELETE FROM "{config.hana_schema}"."{config.evaluations_table}" '
            f'WHERE "CONVERSATIONDATE" >= ? AND "CONVERSATIONDATE" < ?'
        )

        cursor.execute(sql, (start_date, end_date))
        deleted = cursor.rowcount
        conn.commit()

        logger.info("Registros de evaluaciones eliminados previamente: %s", deleted)
        return deleted

    except Exception as exc:
        conn.rollback()
        logger.warning(
            "No se pudo eliminar por CONVERSATIONDATE. Se continuará sin borrar rango. Error: %s",
            exc
        )
        return 0

    finally:
        cursor.close()
        conn.close()


# =========================================================
# FORMULARIOS
# =========================================================

def fetch_published_forms(config: Config, token: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    logger.info("Consultando formularios publicados de evaluación...")

    page_size = 25
    page_number = 1
    forms_basic: List[Dict[str, Any]] = []
    total = None

    while True:
        url = (
            f"{config.genesys_region_base_url}"
            f"/api/v2/quality/publishedforms/evaluations"
            f"?pageSize={page_size}&pageNumber={page_number}&expand=publishHistory"
        )

        response = request_with_retries("GET", url, config, logger, token=token)
        data = response.json()

        entities = data.get("entities") or []
        if total is None:
            total = data.get("total", len(entities))
            total_pages = max(1, math.ceil(total / page_size)) if total else 1
        else:
            total_pages = max(1, math.ceil(total / page_size)) if total else page_number

        forms_basic.extend(entities)

        logger.info(
            "Página formularios %s/%s procesada | formularios en página: %s | acumulado: %s",
            page_number,
            total_pages,
            len(entities),
            len(forms_basic)
        )

        if not entities or page_number >= total_pages:
            break

        page_number += 1
        time.sleep(config.api_sleep_seconds)

    logger.info("Formularios base obtenidos: %s", len(forms_basic))

    detailed_forms: List[Dict[str, Any]] = []

    for idx, item in enumerate(forms_basic, start=1):
        self_uri = item.get("selfUri")
        form_id = item.get("id")

        if self_uri:
            url = self_uri if self_uri.startswith("http") else f"{config.genesys_region_base_url}{self_uri}"
        elif form_id:
            url = f"{config.genesys_region_base_url}/api/v2/quality/publishedforms/evaluations/{form_id}"
        else:
            continue

        logger.info("Consultando detalle formulario %s/%s | %s", idx, len(forms_basic), form_id or url)

        response = request_with_retries("GET", url, config, logger, token=token)
        detailed_forms.append(response.json())
        pyflow_progress(15 + int((idx / max(1, len(forms_basic))) * 15))

        time.sleep(config.api_sleep_seconds)

    logger.info("Detalles de formularios obtenidos: %s", len(detailed_forms))
    return detailed_forms


def transform_forms(forms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    load_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for form in forms:
        form_id = form.get("id")
        form_name = clean_text(form.get("name"))
        published = bool_to_hana(form.get("published"))

        for group in form.get("questionGroups") or []:
            group_id = group.get("id")
            group_name = clean_text(group.get("name"))

            for question in group.get("questions") or []:
                rows.append({
                    "ID_FORMULARIO": form_id,
                    "FORMULARIO": form_name,
                    "PUBLISHED": published,
                    "ID_QUESTION_GROUP": group_id,
                    "CUESTIONARIO": group_name,
                    "ID_PREGUNTA": question.get("id"),
                    "PREGUNTA": clean_text(question.get("text")),
                    "FECHA_CARGA": load_ts,
                })

    return rows


def run_forms(config: Config, token: str, logger: logging.Logger, dry_run: bool) -> Tuple[int, int, Dict[str, str], List[Dict[str, Any]]]:
    forms = fetch_published_forms(config, token, logger)
    rows = transform_forms(forms)

    logger.info("Filas de formulario/preguntas transformadas: %s", len(rows))

    if dry_run:
        logger.warning("DRY RUN activo. No se cargará catálogo de formularios a HANA.")
        lookup = {r["ID_PREGUNTA"]: r["PREGUNTA"] for r in rows if r.get("ID_PREGUNTA")}
        return len(rows), 0, lookup, rows

    delete_all_from_table(config, config.forms_table, logger)

    columns = [
        "ID_FORMULARIO",
        "FORMULARIO",
        "PUBLISHED",
        "ID_QUESTION_GROUP",
        "CUESTIONARIO",
        "ID_PREGUNTA",
        "PREGUNTA",
        "FECHA_CARGA",
    ]

    loaded, failed = insert_rows(config, config.forms_table, columns, rows, logger)

    lookup = {r["ID_PREGUNTA"]: r["PREGUNTA"] for r in rows if r.get("ID_PREGUNTA")}

    return loaded, failed, lookup, rows


# =========================================================
# EVALUACIONES
# =========================================================

def fetch_evaluations_for_user(
    config: Config,
    token: str,
    user_id: str,
    start_date: str,
    end_date: str,
    logger: logging.Logger
) -> List[Dict[str, Any]]:

    url = (
        f"{config.genesys_region_base_url}"
        f"/api/v2/quality/evaluations/query"
        f"?agentUserId={user_id}"
        f"&startTime={start_date}"
        f"&endTime={end_date}"
        f"&expandAnswerTotalScores=true"
        f"&includeDeletedUsers=true"
    )

    response = request_with_retries("GET", url, config, logger, token=token)
    data = response.json()

    return data.get("entities") or []


def first_or_value(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def transform_evaluations(
    evaluations: List[Dict[str, Any]],
    question_lookup: Dict[str, str]
) -> List[Dict[str, Any]]:

    rows: List[Dict[str, Any]] = []

    for ev in evaluations:
        answers = ev.get("answers") or {}
        conversation = ev.get("conversation") or {}
        evaluation_form = ev.get("evaluationForm") or {}
        evaluator = ev.get("evaluator") or {}
        agent = ev.get("agent") or {}
        queue = ev.get("queue") or {}
        agent_team = ev.get("agentTeam") or {}
        evaluation_source = ev.get("evaluationSource") or {}
        ai_scoring = ev.get("aiScoring") or {}

        base = {
            "EVALUATIONID": ev.get("id"),
            "CONVERSATIONID": conversation.get("id"),
            "EVALUATIONFORMID": evaluation_form.get("id"),
            "EVALUATIONFORMNAME": clean_text(evaluation_form.get("name")),
            "EVALUATORID": evaluator.get("id"),
            "AGENTID": agent.get("id"),
            "STATUS": ev.get("status"),
            "AGENTHASREAD": bool_to_hana(ev.get("agentHasRead")),
            "ASSIGNEEAPPLICABLE": bool_to_hana(ev.get("assigneeApplicable")),
            "RELEASEDATE": ev.get("releaseDate"),
            "ASSIGNEDDATE": ev.get("assignedDate"),
            "CREATEDDATE": ev.get("createdDate"),
            "CHANGEDDATE": ev.get("changedDate"),
            "SUBMITTEDDATE": ev.get("submittedDate"),
            "QUEUEID": queue.get("id"),
            "MEDIATYPE": first_or_value(ev.get("mediaType")),
            "CONVERSATIONDATE": ev.get("conversationDate"),
            "CONVERSATIONENDDATE": ev.get("conversationEndDate"),
            "NEVERRELEASE": bool_to_hana(ev.get("neverRelease")),
            "DATEASSIGNEECHANGED": ev.get("dateAssigneeChanged"),
            "AGENTTEAMID": agent_team.get("id"),
            "HASASSISTANCEFAILED": bool_to_hana(ev.get("hasAssistanceFailed")),
            "EVALUATIONSOURCEID": evaluation_source.get("id"),
            "EVALUATIONSOURCETYPE": evaluation_source.get("type"),
            "DISPUTECOUNT": safe_num(ev.get("disputeCount")),
            "VERSION": safe_num(ev.get("version")),
            "DECLINEDREVIEW": bool_to_hana(ev.get("declinedReview")),
            "EVALUATIONCONTEXTID": ev.get("evaluationContextId"),
            "AISCORINGPENDING": bool_to_hana(ai_scoring.get("pending")),
            "SYSTEMSUBMITTED": bool_to_hana(ev.get("systemSubmitted")),
            "MISSINGREQUIREDANSWER": bool_to_hana(ev.get("missingRequiredAnswer")),
            "TOTALSCORE": safe_num(answers.get("totalScore")),
            "TOTALCRITICALSCORE": safe_num(answers.get("totalCriticalScore")),
            "TOTALNONCRITICALSCORE": safe_num(answers.get("totalNonCriticalScore")),
            "ANYFAILEDKILLQUESTIONS": bool_to_hana(answers.get("anyFailedKillQuestions")),
            "COMMENTS": clean_text(answers.get("comments")),
        }

        question_group_scores = answers.get("questionGroupScores") or []

        # Si no hay questionGroupScores, dejamos una fila base sin pregunta.
        if not question_group_scores:
            row = base.copy()
            row.update({
                "QUESTIONGROUPID": None,
                "TOTALSCORE_QG": None,
                "MAXTOTALSCORE": None,
                "MARKEDNA": None,
                "SYSTEMMARKEDNA": None,
                "TOTALCRITICALSCORE_QG": None,
                "MAXTOTALCRITICALSCORE": None,
                "TOTALNONCRITICALSCORE_QG": None,
                "MAXTOTALNONCRITICALSCORE": None,
                "TOTALSCOREUNWEIGHTED": None,
                "MAXTOTALSCOREUNWEIGHTED": None,
                "TOTALCRITICALSCOREUNWEIGHTED": None,
                "MAXTOTALCRITICALSCOREUNWEIGHTED": None,
                "TOTALNONCRITICALSCOREUNWEIGHTED": None,
                "MAXTOTALNONCRITICALSCOREUNWEIGHTED": None,
                "QUESTIONID": None,
                "ANSWERID": None,
                "SCORE": None,
                "MARKEDNA_Q": None,
                "COMMENTS_Q": None,
                "FAILEDKILLQUESTION": None,
                "QUESTION_NAME": None,
            })
            row["MERGE_KEY"] = f'{row.get("EVALUATIONID")}-{row.get("CONVERSATIONID")}-None-None'
            rows.append(row)
            continue

        for qg in question_group_scores:
            qg_base = {
                "QUESTIONGROUPID": qg.get("questionGroupId"),
                "TOTALSCORE_QG": safe_num(qg.get("totalScore")),
                "MAXTOTALSCORE": safe_num(qg.get("maxTotalScore")),
                "MARKEDNA": bool_to_hana(qg.get("markedNA")),
                "SYSTEMMARKEDNA": bool_to_hana(qg.get("systemMarkedNA")),
                "TOTALCRITICALSCORE_QG": safe_num(qg.get("totalCriticalScore")),
                "MAXTOTALCRITICALSCORE": safe_num(qg.get("maxTotalCriticalScore")),
                "TOTALNONCRITICALSCORE_QG": safe_num(qg.get("totalNonCriticalScore")),
                "MAXTOTALNONCRITICALSCORE": safe_num(qg.get("maxTotalNonCriticalScore")),
                "TOTALSCOREUNWEIGHTED": safe_num(qg.get("totalScoreUnweighted")),
                "MAXTOTALSCOREUNWEIGHTED": safe_num(qg.get("maxTotalScoreUnweighted")),
                "TOTALCRITICALSCOREUNWEIGHTED": safe_num(qg.get("totalCriticalScoreUnweighted")),
                "MAXTOTALCRITICALSCOREUNWEIGHTED": safe_num(qg.get("maxTotalCriticalScoreUnweighted")),
                "TOTALNONCRITICALSCOREUNWEIGHTED": safe_num(qg.get("totalNonCriticalScoreUnweighted")),
                "MAXTOTALNONCRITICALSCOREUNWEIGHTED": safe_num(qg.get("maxTotalNonCriticalScoreUnweighted")),
            }

            question_scores = qg.get("questionScores") or []

            if not question_scores:
                row = base.copy()
                row.update(qg_base)
                row.update({
                    "QUESTIONID": None,
                    "ANSWERID": None,
                    "SCORE": None,
                    "MARKEDNA_Q": None,
                    "COMMENTS_Q": None,
                    "FAILEDKILLQUESTION": None,
                    "QUESTION_NAME": None,
                })
                row["MERGE_KEY"] = f'{row.get("EVALUATIONID")}-{row.get("CONVERSATIONID")}-{row.get("QUESTIONGROUPID")}-None'
                rows.append(row)
                continue

            for qs in question_scores:
                question_id = qs.get("questionId")
                row = base.copy()
                row.update(qg_base)
                row.update({
                    "QUESTIONID": question_id,
                    "ANSWERID": qs.get("answerId"),
                    "SCORE": safe_num(qs.get("score")),
                    "MARKEDNA_Q": bool_to_hana(qs.get("markedNA")),
                    "COMMENTS_Q": clean_text(qs.get("comments")),
                    "FAILEDKILLQUESTION": bool_to_hana(qs.get("failedKillQuestion")),
                    "QUESTION_NAME": question_lookup.get(question_id),
                })
                row["MERGE_KEY"] = (
                    f'{row.get("EVALUATIONID")}-'
                    f'{row.get("CONVERSATIONID")}-'
                    f'{row.get("QUESTIONGROUPID")}-'
                    f'{row.get("QUESTIONID")}'
                )
                rows.append(row)

    return rows


def run_evaluations(
    config: Config,
    token: str,
    start_date: str,
    end_date: str,
    question_lookup: Dict[str, str],
    logger: logging.Logger,
    dry_run: bool
) -> Tuple[int, int, int, int, List[Dict[str, Any]]]:

    if not question_lookup:
        question_lookup = get_question_lookup_from_hana(config, logger)

    users = get_users_from_hana(config, logger)

    all_rows: List[Dict[str, Any]] = []
    users_ok = 0
    users_error = 0

    for idx, user_id in enumerate(users, start=1):
        try:
            logger.info("Consultando evaluaciones usuario %s/%s | %s", idx, len(users), user_id)

            evaluations = fetch_evaluations_for_user(
                config,
                token,
                user_id,
                start_date,
                end_date,
                logger
            )

            rows = transform_evaluations(evaluations, question_lookup)
            all_rows.extend(rows)
            users_ok += 1
            pyflow_progress(40 + int((idx / max(1, len(users))) * 40))

            logger.info(
                "Usuario procesado OK | evaluaciones: %s | filas obtenidas: %s | acumulado filas: %s",
                len(evaluations),
                len(rows),
                len(all_rows)
            )

            time.sleep(config.api_sleep_seconds)

        except Exception as exc:
            users_error += 1
            logger.exception("Error consultando usuario %s: %s", user_id, exc)
            pyflow_progress(40 + int((idx / max(1, len(users))) * 40))
            time.sleep(max(config.api_sleep_seconds, 3))

    logger.info("Extracción evaluaciones finalizada. Filas transformadas: %s", len(all_rows))

    if dry_run:
        logger.warning("DRY RUN activo. No se cargarán evaluaciones a HANA.")
        return len(all_rows), 0, users_ok, users_error, all_rows

    delete_evaluations_range(config, start_date, end_date, logger)

    columns = [
        "EVALUATIONID",
        "CONVERSATIONID",
        "EVALUATIONFORMID",
        "EVALUATIONFORMNAME",
        "EVALUATORID",
        "AGENTID",
        "STATUS",
        "AGENTHASREAD",
        "ASSIGNEEAPPLICABLE",
        "RELEASEDATE",
        "ASSIGNEDDATE",
        "CREATEDDATE",
        "CHANGEDDATE",
        "SUBMITTEDDATE",
        "QUEUEID",
        "MEDIATYPE",
        "CONVERSATIONDATE",
        "CONVERSATIONENDDATE",
        "NEVERRELEASE",
        "DATEASSIGNEECHANGED",
        "AGENTTEAMID",
        "HASASSISTANCEFAILED",
        "EVALUATIONSOURCEID",
        "EVALUATIONSOURCETYPE",
        "DISPUTECOUNT",
        "VERSION",
        "DECLINEDREVIEW",
        "EVALUATIONCONTEXTID",
        "AISCORINGPENDING",
        "SYSTEMSUBMITTED",
        "MISSINGREQUIREDANSWER",
        "TOTALSCORE",
        "TOTALCRITICALSCORE",
        "TOTALNONCRITICALSCORE",
        "ANYFAILEDKILLQUESTIONS",
        "COMMENTS",
        "QUESTIONGROUPID",
        "TOTALSCORE_QG",
        "MAXTOTALSCORE",
        "MARKEDNA",
        "SYSTEMMARKEDNA",
        "TOTALCRITICALSCORE_QG",
        "MAXTOTALCRITICALSCORE",
        "TOTALNONCRITICALSCORE_QG",
        "MAXTOTALNONCRITICALSCORE",
        "TOTALSCOREUNWEIGHTED",
        "MAXTOTALSCOREUNWEIGHTED",
        "TOTALCRITICALSCOREUNWEIGHTED",
        "MAXTOTALCRITICALSCOREUNWEIGHTED",
        "TOTALNONCRITICALSCOREUNWEIGHTED",
        "MAXTOTALNONCRITICALSCOREUNWEIGHTED",
        "QUESTIONID",
        "ANSWERID",
        "SCORE",
        "MARKEDNA_Q",
        "COMMENTS_Q",
        "FAILEDKILLQUESTION",
        "QUESTION_NAME",
        "MERGE_KEY",
    ]

    loaded, failed = insert_rows(config, config.evaluations_table, columns, all_rows, logger)

    return loaded, failed, users_ok, users_error, all_rows


def validate_report_directory(config: Config) -> Optional[str]:
    raw_path = (config.report_output_dir or "").strip()
    if not raw_path:
        return None

    path = os.path.abspath(os.path.expandvars(os.path.expanduser(raw_path)))
    if not os.path.isdir(path):
        raise ValueError(f"La carpeta de salida del reporte no existe o no es válida: {path}")
    if not os.access(path, os.W_OK):
        raise ValueError(f"La carpeta de salida del reporte no permite escritura: {path}")
    return path


def write_csv_report(path: str, rows: List[Dict[str, Any]]) -> None:
    columns = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report_files(
    config: Config,
    form_rows: List[Dict[str, Any]],
    evaluation_rows: List[Dict[str, Any]],
    logger: logging.Logger
) -> List[str]:
    output_dir = validate_report_directory(config)
    if not output_dir:
        logger.info("Reporte en archivo no generado: no se indicó carpeta de salida.")
        return []

    report_format = (config.report_output_format or "xlsx").strip().lower()
    if report_format not in ("xlsx", "csv"):
        raise ValueError("REPORT_OUTPUT_FORMAT debe ser xlsx o csv.")
    if not form_rows and not evaluation_rows:
        logger.warning("No hay datos para generar el archivo de reporte.")
        return []

    timestamp = datetime.now(ZoneInfo(config.timezone_name)).strftime("%Y%m%d_%H%M%S")
    generated: List[str] = []

    if report_format == "xlsx":
        if pd is None:
            raise RuntimeError("Para generar Excel instala pandas y openpyxl: pip install pandas openpyxl")
        path = os.path.join(output_dir, f"GNS_Form_Evaluaciones_{timestamp}.xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            if form_rows:
                pd.DataFrame(form_rows).to_excel(writer, sheet_name="Formularios", index=False)
            if evaluation_rows:
                pd.DataFrame(evaluation_rows).to_excel(writer, sheet_name="Evaluaciones", index=False)
        generated.append(path)
    else:
        if form_rows:
            path = os.path.join(output_dir, f"GNS_Formularios_{timestamp}.csv")
            write_csv_report(path, form_rows)
            generated.append(path)
        if evaluation_rows:
            path = os.path.join(output_dir, f"GNS_Evaluaciones_{timestamp}.csv")
            write_csv_report(path, evaluation_rows)
            generated.append(path)

    for path in generated:
        logger.info("Archivo de reporte generado: %s", path)
    return generated


def build_file_attachment(path: str) -> Dict[str, str]:
    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as handle:
        content = base64.b64encode(handle.read()).decode("ascii")
    return {
        "@odata.type": "#microsoft.graph.fileAttachment",
        "name": os.path.basename(path),
        "contentType": content_type,
        "contentBytes": content,
    }


def get_graph_access_token(config: Config, logger: logging.Logger) -> str:
    if not config.graph_tenant_id or not config.graph_client_id or not config.graph_client_secret:
        raise ValueError("Configura GRAPH_TENANT_ID, GRAPH_CLIENT_ID y GRAPH_CLIENT_SECRET para enviar el reporte.")

    response = requests.post(
        f"https://login.microsoftonline.com/{config.graph_tenant_id}/oauth2/v2.0/token",
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


def build_report_html(
    forms_loaded: int,
    forms_failed: int,
    eval_loaded: int,
    eval_failed: int,
    users_ok: int,
    users_error: int,
    date_mode: str,
    duration_seconds: float
) -> str:
    now = datetime.now(ZoneInfo("America/Tegucigalpa"))
    total = forms_loaded + eval_loaded + forms_failed + eval_failed
    loaded = forms_loaded + eval_loaded
    coverage = (loaded / total * 100) if total else 0
    return f"""<!doctype html>
<html lang="es"><body style="margin:0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif;color:#334155;">
<table width="100%" cellspacing="0" cellpadding="0" style="padding:40px 10px;"><tr><td align="center">
<table width="100%" cellspacing="0" cellpadding="0" style="max-width:650px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
<tr><td style="background:#DA282D;padding:34px 40px;color:#fff;"><div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.4px;color:#fecaca;">PyFlow Manager</div><h1 style="margin:8px 0 0;font-size:24px;">Reporte de Formularios y Evaluaciones</h1><p style="margin:8px 0 0;color:#fecaca;font-size:13px;">Genesys Cloud Quality</p></td></tr>
<tr><td style="padding:34px 40px;"><p style="font-size:14px;line-height:1.6;">Se completó el proceso de extracción y carga de formularios y evaluaciones.</p>
<table width="100%" cellspacing="0" cellpadding="0"><tr>
<td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;"><div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Formularios / preguntas</div><div style="font-size:26px;font-weight:700;margin-top:8px;">{forms_loaded:,}</div><div style="font-size:11px;color:#94a3b8;">Fallidos: {forms_failed:,}</div></td><td width="4%">&nbsp;</td>
<td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;"><div style="font-size:11px;font-weight:700;color:#DA282D;text-transform:uppercase;">Filas de evaluaciones</div><div style="font-size:26px;font-weight:700;color:#DA282D;margin-top:8px;">{eval_loaded:,}</div><div style="font-size:11px;color:#94a3b8;">Fallidas: {eval_failed:,}</div></td>
</tr></table>
<div style="margin-top:20px;background:#fafafa;border:1px solid #e2e8f0;border-radius:6px;padding:20px;font-size:13px;line-height:1.7;"><strong>Usuarios procesados:</strong> {users_ok:,}<br><strong>Usuarios con error:</strong> {users_error:,}<br><strong>Resultado de carga:</strong> {coverage:.1f}%<br><strong>Periodo:</strong> {escape(date_mode)}<br><strong>Duración:</strong> {duration_seconds:.2f} segundos</div>
<div style="margin-top:24px;border-top:1px solid #e2e8f0;padding-top:18px;font-size:12px;color:#64748b;">Generado el {escape(now.strftime('%d/%m/%Y'))} a las {escape(now.strftime('%I:%M %p'))}.</div></td></tr>
</table></td></tr></table></body></html>"""


def send_report_email(
    config: Config,
    forms_loaded: int,
    forms_failed: int,
    eval_loaded: int,
    eval_failed: int,
    users_ok: int,
    users_error: int,
    date_mode: str,
    duration_seconds: float,
    report_files: List[str],
    logger: logging.Logger
) -> bool:
    if not config.report_email_to:
        logger.info("Reporte por correo no enviado: no hay destinatarios configurados.")
        return False
    if not config.graph_sender_email:
        logger.warning("Reporte por correo no enviado: configura GRAPH_SENDER_EMAIL.")
        return False

    payload: Dict[str, Any] = {
        "message": {
            "subject": config.report_email_subject,
            "body": {
                "contentType": "HTML",
                "content": build_report_html(forms_loaded, forms_failed, eval_loaded, eval_failed, users_ok, users_error, date_mode, duration_seconds),
            },
            "toRecipients": [{"emailAddress": {"address": email}} for email in config.report_email_to],
            "ccRecipients": [{"emailAddress": {"address": email}} for email in config.report_email_cc],
        },
        "saveToSentItems": "true",
    }

    if config.attach_report_file and report_files:
        payload["message"]["attachments"] = [build_file_attachment(path) for path in report_files]
    elif config.attach_report_file:
        logger.warning("Se solicitó adjuntar el reporte, pero no se generó ningún archivo.")

    try:
        token = get_graph_access_token(config, logger)
        response = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{config.graph_sender_email}/sendMail",
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=30,
        )
        if response.status_code >= 400:
            logger.error("Error enviando reporte Graph %s | %s", response.status_code, response.text[:1000])
        response.raise_for_status()
        logger.info("Reporte enviado a: %s", ", ".join(config.report_email_to + config.report_email_cc))
        return True
    except Exception as exc:
        logger.error("No se pudo enviar el reporte: %s", exc)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Carga formularios y evaluaciones Genesys Cloud Quality a SAP HANA"
    )

    parser.add_argument("--date", default=env_str("DATE", ""), help="Fecha local específica. Ejemplo: 2026-05-27")
    parser.add_argument("--start-date", default=env_str("START_DATE", ""), help="Fecha local inicial inclusiva. Ejemplo: 2026-05-01")
    parser.add_argument("--end-date", default=env_str("END_DATE", ""), help="Fecha local final inclusiva. Ejemplo: 2026-05-27")
    parser.add_argument("--start-utc", default=env_str("START_UTC", ""), help="Fecha UTC exacta. Ejemplo: 2026-05-01T06:00:00.000Z")
    parser.add_argument("--end-utc", default=env_str("END_UTC", ""), help="Fecha UTC exacta. Ejemplo: 2026-05-28T06:00:00.000Z")

    parser.add_argument("--solo-formularios", action="store_true", help="Solo carga catálogo de formularios/preguntas.")
    parser.add_argument("--solo-evaluaciones", action="store_true", help="Solo carga evaluaciones. Usa catálogo existente de preguntas.")
    parser.add_argument("--dry-run", action="store_true", help="Ejecuta API y transformación, pero no carga a HANA.")

    args = parser.parse_args()

    run_mode = env_str("RUN_MODE", "")
    if run_mode == "solo_formularios":
        args.solo_formularios = True
    elif run_mode == "solo_evaluaciones":
        args.solo_evaluaciones = True
    if env_bool("DRY_RUN", False):
        args.dry_run = True

    logger = setup_logger()
    start_time = time.time()

    forms_loaded = 0
    forms_failed = 0
    eval_loaded = 0
    eval_failed = 0
    users_ok = 0
    users_error = 0
    form_rows: List[Dict[str, Any]] = []
    evaluation_rows: List[Dict[str, Any]] = []
    report_files: List[str] = []
    general_errors: List[str] = []

    try:
        pyflow_progress(3)
        config = load_config()
        start_date, end_date, date_mode = parse_dates(args, config.timezone_name)

        logger.info("=" * 80)
        logger.info("INICIO PROCESO GNS FORMULARIOS Y EVALUACIONES")
        log_params(logger, ["GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION", "HPR_HOST", "HPR_HOST_ESPEJO", "HPR_PORT", "HPR_USER", "HPR_PASSWORD", "HANA_SCHEMA", "HANA_USERS_TABLE", "HANA_FORM_EVALUACIONES_TABLE", "HANA_EVALUACIONES_TABLE", "RUN_MODE", "DATE", "START_DATE", "END_DATE", "START_UTC", "END_UTC", "DAYS_BACK", "DRY_RUN"])
        logger.info("Modo fecha: %s", date_mode)
        logger.info("startTime API: %s", start_date)
        logger.info("endTime API: %s", end_date)
        logger.info("Zona horaria: %s", config.timezone_name)
        logger.info("HANA escritura: %s:%s", config.hana_host, config.hana_port)
        logger.info("HANA lectura/espejo: %s:%s", config.hana_host_espejo, config.hana_port)
        logger.info("Tabla usuarios: %s.%s", config.hana_schema, config.users_table)
        logger.info("Tabla formularios: %s.%s", config.hana_schema, config.forms_table)
        logger.info("Tabla evaluaciones: %s.%s", config.hana_schema, config.evaluations_table)
        logger.info("=" * 80)

        token = get_access_token(config, logger)
        pyflow_progress(10)

        question_lookup: Dict[str, str] = {}

        if not args.solo_evaluaciones:
            logger.info("=" * 80)
            logger.info("PASO 1/2: CARGA DE FORMULARIOS/PREGUNTAS")
            logger.info("=" * 80)

            forms_loaded, forms_failed, question_lookup, form_rows = run_forms(
                config,
                token,
                logger,
                args.dry_run
            )
            pyflow_progress(35)

        if not args.solo_formularios:
            logger.info("=" * 80)
            logger.info("PASO 2/2: CARGA DE EVALUACIONES")
            logger.info("=" * 80)

            eval_loaded, eval_failed, users_ok, users_error, evaluation_rows = run_evaluations(
                config,
                token,
                start_date,
                end_date,
                question_lookup,
                logger,
                args.dry_run
            )
            pyflow_progress(85)

        report_files = write_report_files(config, form_rows, evaluation_rows, logger)
        pyflow_progress(93)

        send_report_email(
            config,
            forms_loaded,
            forms_failed,
            eval_loaded,
            eval_failed,
            users_ok,
            users_error,
            date_mode,
            time.time() - start_time,
            report_files,
            logger
        )
        pyflow_progress(98)

    except Exception as exc:
        general_errors.append(str(exc))
        logger.exception("El proceso terminó con error general: %s", exc)
        logger.error(traceback.format_exc())

    duration = time.time() - start_time

    logger.info("=" * 80)
    logger.info("RESUMEN FINAL")
    logger.info("Formularios/preguntas cargados: %s", forms_loaded)
    logger.info("Formularios/preguntas fallidos: %s", forms_failed)
    logger.info("Usuarios evaluaciones OK: %s", users_ok)
    logger.info("Usuarios evaluaciones con error: %s", users_error)
    logger.info("Filas evaluaciones cargadas: %s", eval_loaded)
    logger.info("Filas evaluaciones fallidas: %s", eval_failed)
    logger.info("Errores generales: %s", len(general_errors))

    for err in general_errors[:20]:
        logger.error("Detalle error: %s", err)

    logger.info("Duración total: %.2f segundos", duration)
    logger.info("=" * 80)

    success = not general_errors and forms_failed == 0 and eval_failed == 0 and users_error == 0
    if success:
        pyflow_progress(100)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
