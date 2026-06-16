# =========================================================
# FORMAS DE EJECUCIÓN
# =========================================================
#
# 1. EJECUCIÓN AUTOMÁTICA
#    Si no colocás fechas, calcula automáticamente desde
#    el mismo día del mes anterior hasta hoy a las 00:00.
#
#    py .\GNS_Adherencia.py 
#
# 2. EJECUTAR UNA FECHA ESPECÍFICA
#
#    py .\GNS_Adherencia.py --date 2026-05-27
#
# 3. EJECUTAR UN RANGO LOCAL
#
#    py .\GNS_Adherencia.py --start-date 2026-05-01 --end-date 2026-05-27
#
# 4. EJECUTAR UTC EXACTO COMO KNIME
#
#    py .\GNS_Adherencia.py --start-utc 2026-05-01T06:00:00.000Z --end-utc 2026-05-28T06:00:00.000Z
#
# 5. PROBAR SIN CARGAR A HANA
#
#    py .\GNS_Adherencia.py --dry-run
#
# =========================================================

import os
import sys
import time
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
    "HPR_HOST_ESPEJO": {"type": "global", "global_key": "HPR_HOST_ESPEJO", "label": "SAP HANA Host Espejo Lectura", "required": False},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "SAP HANA Port", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "SAP HANA User", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "SAP HANA Password", "required": True, "secret": True},
    "HANA_SCHEMA": {"type": "text", "label": "Esquema HANA", "required": True, "default": "BI_SS"},
    "HANA_ADHERENCIA_TABLE": {"type": "text", "label": "Tabla destino adherencia", "required": True, "default": "GNS_API_ADHERENCIA"},
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
    "ADHERENCIA_REPORT_EMAIL_TO": {"type": "tags", "label": "Destinatarios reporte adherencia", "required": False},
    "ADHERENCIA_REPORT_EMAIL_CC": {"type": "tags", "label": "Copias reporte adherencia", "required": False},
    "ADHERENCIA_REPORT_SUBJECT": {"type": "text", "label": "Asunto reporte adherencia", "required": False, "default": "Reporte de Adherencia Genesys"}
}

LOGGER_NAME = "gns_adherencia_pyflow"

ADHERENCIA_COLUMNS = [
    "startDate",
    "userId",
    "id_unidad",
    "impact",
    "userAdherencePercentage",
    "userConformancePercentage",
    "dayStartOffsetSeconds",
    "adherenceScheduleSeconds",
    "conformanceScheduleSeconds",
    "conformanceActualSeconds",
    "exceptionCount",
    "exceptionDurationSeconds",
    "impactSeconds",
    "scheduleLengthSeconds",
    "actualLengthSeconds",
    "adherencePercentage",
    "conformancePercentage",
]


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



@dataclass
class Config:
    """Configuración normalizada para PyFlow Manager.

    Nota: en PyFlow las variables globales reales de SAP HANA son HPR_*,
    pero internamente mantenemos nombres hana_* para no tocar toda la lógica
    original del script.
    """

    genesys_client_id: str
    genesys_client_secret: str
    genesys_region_base_url: str
    genesys_login_url: str
    hana_host: str
    hana_read_host: str
    hana_port: int
    hana_user: str
    hana_password: str
    hana_schema: str
    hana_table: str
    timezone_name: str
    batch_size: int
    request_timeout: int
    poll_seconds: int
    max_poll_attempts: int
    max_api_retries: int
    report_output_format: str
    attach_report_file: bool
    report_output_dir: str
    graph_tenant_id: str
    graph_client_id: str
    graph_client_secret: str
    graph_sender_email: str
    adherencia_report_email_to: List[str]
    adherencia_report_email_cc: List[str]
    adherencia_report_subject: str


def setup_logger() -> logging.Logger:
    """Logger compatible con PyFlow: todo sale por stdout en tiempo real."""
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
    console.flush = sys.stdout.flush
    logger.addHandler(console)

    return logger


def mask_secret(value: str) -> str:
    if not value:
        return ""
    return "********"


def log_params(logger: logging.Logger, names: List[str]) -> None:
    """Imprime parámetros usados, ocultando secretos."""
    secret_names = {"SECRET", "PASSWORD", "TOKEN", "CLIENT_SECRET"}
    logger.info("Parámetros recibidos:")
    for name in names:
        value = env_str(name, "")
        if any(part in name.upper() for part in secret_names):
            value = mask_secret(value)
        logger.info("- %s: %s", name, value)


def require_env_any(names: List[str], label: str) -> str:
    """Lee la primera variable disponible para soportar nombres nuevos y legados."""
    for name in names:
        value = env_str(name, "")
        if value:
            return value
    raise ValueError(f"Falta configurar variable/parámetro requerido: {label} ({', '.join(names)})")


def load_config() -> Config:
    """Carga configuración desde variables inyectadas por PyFlow.

    También soporta nombres legados HANA_* por compatibilidad, pero el estándar
    correcto del proyecto es HPR_HOST, HPR_PORT, HPR_USER y HPR_PASSWORD.
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
        hana_host=require_env_any(["HPR_HOST", "HANA_HOST"], "HPR_HOST"),
        hana_read_host=env_str("HPR_HOST_ESPEJO", env_str("HANA_HOST_ESPEJO", ""), required=False),
        hana_port=int(require_env_any(["HPR_PORT", "HANA_PORT"], "HPR_PORT")),
        hana_user=require_env_any(["HPR_USER", "HANA_USER"], "HPR_USER"),
        hana_password=require_env_any(["HPR_PASSWORD", "HANA_PASSWORD"], "HPR_PASSWORD"),
        hana_schema=env_str("HANA_SCHEMA", "BI_SS"),
        hana_table=env_str("HANA_ADHERENCIA_TABLE", "GNS_API_ADHERENCIA"),
        timezone_name=env_str("GENESYS_TIMEZONE", "America/Tegucigalpa"),
        batch_size=env_int("HANA_BATCH_SIZE", 1000),
        request_timeout=env_int("REQUEST_TIMEOUT", 120),
        poll_seconds=env_int("POLL_SECONDS", 30),
        max_poll_attempts=env_int("MAX_POLL_ATTEMPTS", 120),
        max_api_retries=env_int("MAX_API_RETRIES", 5),
        report_output_format=env_str("REPORT_OUTPUT_FORMAT", "").lower(),
        attach_report_file=env_bool("ATTACH_REPORT_FILE", False),
        report_output_dir=env_str("REPORT_OUTPUT_DIR", ""),
        graph_tenant_id=env_str("GRAPH_TENANT_ID", ""),
        graph_client_id=env_str("GRAPH_CLIENT_ID", ""),
        graph_client_secret=env_str("GRAPH_CLIENT_SECRET", ""),
        graph_sender_email=env_str("GRAPH_SENDER_EMAIL", ""),
        adherencia_report_email_to=split_list_value(env_str("ADHERENCIA_REPORT_EMAIL_TO", "")),
        adherencia_report_email_cc=split_list_value(env_str("ADHERENCIA_REPORT_EMAIL_CC", "")),
        adherencia_report_subject=env_str("ADHERENCIA_REPORT_SUBJECT", "Reporte de Adherencia Genesys"),
    )


def parse_local_date(value: str) -> date:
    """Acepta YYYY-MM-DD y DD/MM/YYYY para facilitar uso desde la pantalla."""
    value = env_str("_INTERNAL_DATE_VALUE", value)
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Fecha inválida: {value!r}. Use YYYY-MM-DD o DD/MM/YYYY.")



def to_utc_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def parse_dates(args: argparse.Namespace, tz_name: str) -> Tuple[str, str, str]:
    tz = ZoneInfo(tz_name)

    if args.start_utc and args.end_utc:
        return args.start_utc, args.end_utc, "UTC manual"

    if args.date:
        d = parse_local_date(args.date)

        start_local = datetime(
            d.year,
            d.month,
            d.day,
            0,
            0,
            0,
            tzinfo=tz
        )

        end_local = start_local + timedelta(days=1)

        return (
            to_utc_z(start_local),
            to_utc_z(end_local),
            f"Día local {args.date}"
        )

    if args.start_date and args.end_date:
        d1 = parse_local_date(args.start_date)
        d2 = parse_local_date(args.end_date)

        if d2 < d1:
            raise ValueError("La fecha final no puede ser menor que la fecha inicial.")

        start_local = datetime(
            d1.year,
            d1.month,
            d1.day,
            0,
            0,
            0,
            tzinfo=tz
        )

        end_local = datetime(
            d2.year,
            d2.month,
            d2.day,
            0,
            0,
            0,
            tzinfo=tz
        ) + timedelta(days=1)

        return (
            to_utc_z(start_local),
            to_utc_z(end_local),
            f"Rango local {args.start_date} al {args.end_date}"
        )

    # Automático PyFlow: últimos N días cerrados.
    # Ejemplo con DAYS_BACK=5 y hoy 2026-05-31:
    # trae desde 2026-05-26 00:00 hasta 2026-05-31 00:00.
    days_back = env_int("DAYS_BACK", 5)
    if days_back <= 0:
        raise ValueError("DAYS_BACK debe ser mayor que cero.")

    today = datetime.now(tz)
    end_dt = today.replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = end_dt - timedelta(days=days_back)

    return (
        to_utc_z(start_dt),
        to_utc_z(end_dt),
        f"Automático últimos {days_back} días cerrados"
    )



def request_with_retry(
    method: str,
    url: str,
    config: Config,
    logger: logging.Logger,
    **kwargs
) -> requests.Response:
    """Request HTTP con reintentos para errores temporales de red/API.

    Esto evita que un ConnectionResetError o un 429/5xx haga fallar de inmediato
    una Management Unit completa.
    """
    last_error = None
    for attempt in range(1, config.max_api_retries + 1):
        try:
            response = requests.request(method, url, timeout=config.request_timeout, **kwargs)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * attempt)
                logger.warning(
                    "HTTP 429 Too Many Requests | intento %s/%s | esperando %s segundos...",
                    attempt,
                    config.max_api_retries,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 500:
                wait_seconds = min(60, 5 * attempt)
                logger.warning(
                    "HTTP %s en Genesys | intento %s/%s | esperando %s segundos...",
                    response.status_code,
                    attempt,
                    config.max_api_retries,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 400:
                logger.error("Error HTTP %s | Respuesta: %s", response.status_code, response.text[:1000])

            response.raise_for_status()
            return response

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            last_error = exc
            wait_seconds = min(60, 5 * attempt)
            logger.warning(
                "Error temporal de conexión | intento %s/%s | %s | esperando %s segundos...",
                attempt,
                config.max_api_retries,
                exc,
                wait_seconds,
            )
            time.sleep(wait_seconds)
        except Exception as exc:
            last_error = exc
            wait_seconds = min(60, 5 * attempt)
            logger.warning(
                "Error en request | intento %s/%s | %s | esperando %s segundos...",
                attempt,
                config.max_api_retries,
                exc,
                wait_seconds,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"No se pudo completar request después de {config.max_api_retries} intentos: {last_error}")


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


def get_business_units(
    config: Config,
    token: str,
    logger: logging.Logger
) -> List[Dict[str, Any]]:

    logger.info("Consultando Business Units de WFM...")

    url = f"{config.genesys_region_base_url}/api/v2/workforcemanagement/businessunits"

    response = request_with_retry(
        "GET",
        url,
        config,
        logger,
        headers=genesys_headers(token)
    )

    response.raise_for_status()

    entities = response.json().get("entities", [])

    logger.info("Business Units obtenidas: %s", len(entities))

    return [
        {
            "id": x.get("id"),
            "name": x.get("name")
        }
        for x in entities
        if x.get("id")
    ]


def get_management_units(
    config: Config,
    token: str,
    business_units: List[Dict[str, Any]],
    logger: logging.Logger
) -> List[Dict[str, Any]]:

    all_units: List[Dict[str, Any]] = []

    logger.info("Consultando Management Units por Business Unit...")

    for i, bu in enumerate(business_units, start=1):

        url = (
            f"{config.genesys_region_base_url}"
            f"/api/v2/workforcemanagement/businessunits/{bu['id']}/managementunits"
        )

        response = requests.get(
            url,
            headers=genesys_headers(token),
            timeout=config.request_timeout
        )

        response.raise_for_status()

        entities = response.json().get("entities", [])

        logger.info(
            "Business Unit %s/%s | %s | Management Units: %s",
            i,
            len(business_units),
            bu.get("name"),
            len(entities)
        )

        for mu in entities:
            if mu.get("id"):
                all_units.append({
                    "businessUnitId": bu["id"],
                    "businessUnitName": bu.get("name"),
                    "managementUnitId": mu.get("id"),
                    "managementUnitName": mu.get("name"),
                })

    logger.info("Total Management Units obtenidas: %s", len(all_units))

    return all_units


def create_adherence_job(
    config: Config,
    token: str,
    management_unit_id: str,
    start_date: str,
    end_date: str,
    logger: logging.Logger
) -> str:

    url = (
        f"{config.genesys_region_base_url}"
        "/api/v2/workforcemanagement/adherence/historical/bulk"
    )

    body = {
        "items": [
            {
                "managementUnitId": management_unit_id,
                "startDate": start_date,
                "endDate": end_date
            }
        ],
        "timeZone": config.timezone_name
    }

    response = request_with_retry(
        "POST",
        url,
        config,
        logger,
        headers=genesys_headers(token),
        json=body
    )

    response.raise_for_status()

    data = response.json()

    job_id = data.get("job", {}).get("id")

    if not job_id:
        raise RuntimeError(
            f"No se recibió job.id para managementUnitId={management_unit_id}. "
            f"Respuesta: {data}"
        )

    return job_id


def wait_for_job(
    config: Config,
    token: str,
    job_id: str,
    logger: logging.Logger
) -> Dict[str, Any]:

    url = (
        f"{config.genesys_region_base_url}"
        f"/api/v2/workforcemanagement/adherence/historical/bulk/jobs/{job_id}"
    )

    success_statuses = {
        "Succeeded",
        "Completed",
        "Complete",
        "SUCCESS",
        "COMPLETED",
        "COMPLETE"
    }
    fail_statuses = {
        "Failed",
        "Canceled",
        "Cancelled",
        "FAILED",
        "CANCELED",
        "CANCELLED"
    }

    for attempt in range(1, config.max_poll_attempts + 1):

        response = requests.get(
            url,
            headers=genesys_headers(token),
            timeout=config.request_timeout
        )

        response.raise_for_status()

        data = response.json()

        status = data.get("job", {}).get("status")

        if status in success_statuses:
            return data

        if status in fail_statuses:
            raise RuntimeError(
                f"Job {job_id} terminó con estado {status}. Respuesta: {data}"
            )

        logger.info(
            "Job %s en estado %s | intento %s/%s | esperando %s segundos...",
            job_id,
            status,
            attempt,
            config.max_poll_attempts,
            config.poll_seconds
        )

        time.sleep(config.poll_seconds)

    raise TimeoutError(
        f"Job {job_id} no finalizó después de {config.max_poll_attempts} intentos."
    )


def download_job_data(
    config: Config,
    token: str,
    job_result: Dict[str, Any],
    logger: logging.Logger
) -> Dict[str, Any]:

    download_urls = job_result.get("downloadUrls") or []

    if not download_urls:
        raise RuntimeError(
            f"El job no devolvió downloadUrls. Respuesta: {job_result}"
        )

    response = request_with_retry(
        "GET",
        download_urls[0],
        config,
        logger,
        headers=genesys_headers(token)
    )

    response.raise_for_status()

    return response.json()


def safe_num(value: Any) -> Any:
    return None if value in (None, "") else value


def parse_genesys_datetime(value: str) -> datetime:
    """Convierte fecha ISO de Genesys a datetime con zona horaria UTC."""
    if not value:
        raise ValueError("No se recibió startDate en la respuesta de Genesys.")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def transform_adherence_data(
    data: Dict[str, Any],
    management_unit_id: str
) -> List[Dict[str, Any]]:

    rows: List[Dict[str, Any]] = []

    # Genesys devuelve un startDate general para todo el rango
    # y cada métrica diaria trae dayStartOffsetSeconds.
    # Por eso la fecha real de cada fila se calcula así:
    # fecha_fila = startDate + dayStartOffsetSeconds
    base_start_date = data.get("startDate")
    base_start_dt = parse_genesys_datetime(base_start_date)

    user_results = data.get("userResults") or []

    for user in user_results:

        user_id = user.get("userId")
        user_impact = user.get("impact")
        user_adherence_percentage = user.get("adherencePercentage")
        user_conformance_percentage = user.get("conformancePercentage")

        for metric in user.get("dayMetrics") or []:

            offset_seconds = metric.get("dayStartOffsetSeconds") or 0
            metric_start_dt = base_start_dt + timedelta(seconds=offset_seconds)
            start_date = metric_start_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            rows.append({
                "startDate": start_date,
                "userId": user_id,
                "id_unidad": management_unit_id,
                "impact": safe_num(user_impact),
                "userAdherencePercentage": safe_num(user_adherence_percentage),
                "userConformancePercentage": safe_num(user_conformance_percentage),
                "dayStartOffsetSeconds": safe_num(metric.get("dayStartOffsetSeconds")),
                "adherenceScheduleSeconds": safe_num(metric.get("adherenceScheduleSeconds")),
                "conformanceScheduleSeconds": safe_num(metric.get("conformanceScheduleSeconds")),
                "conformanceActualSeconds": safe_num(metric.get("conformanceActualSeconds")),
                "exceptionCount": safe_num(metric.get("exceptionCount")),
                "exceptionDurationSeconds": safe_num(metric.get("exceptionDurationSeconds")),
                "impactSeconds": safe_num(metric.get("impactSeconds")),
                "scheduleLengthSeconds": safe_num(metric.get("scheduleLengthSeconds")),
                "actualLengthSeconds": safe_num(metric.get("actualLengthSeconds")),
                "adherencePercentage": safe_num(metric.get("adherencePercentage")),
                "conformancePercentage": safe_num(metric.get("conformancePercentage")),
            })

    return rows


def hana_connect_write(config: Config):
    """
    Conexión HANA para escritura: DELETE / INSERT / UPDATE / MERGE.

    Debe apuntar al servidor principal productivo:
    HPR_HOST = 150.150.70.124
    """
    return dbapi.connect(
        address=config.hana_host,
        port=config.hana_port,
        user=config.hana_user,
        password=config.hana_password
    )


def hana_connect_read(config: Config):
    """
    Conexión HANA para lectura: SELECT / validaciones / catálogos.

    Debe apuntar al servidor espejo:
    HPR_HOST_ESPEJO = 150.150.70.167

    Nota:
    Este script de adherencia actualmente no realiza SELECT contra HANA.
    Se deja la función definida para mantener el estándar de PyFlow.
    """
    read_host = config.hana_read_host or config.hana_host
    return dbapi.connect(
        address=read_host,
        port=config.hana_port,
        user=config.hana_user,
        password=config.hana_password
    )


# Alias de compatibilidad:
# En este script todas las operaciones HANA actuales son de escritura.
def hana_connect(config: Config):
    return hana_connect_write(config)


def delete_existing_range(
    config: Config,
    start_date: str,
    end_date: str,
    logger: logging.Logger
) -> int:
    """
    Borra en HANA el mismo rango que se va a cargar.
    Esto evita duplicados cuando el proceso se ejecuta diariamente
    trayendo los últimos 30/31 días.
    """

    logger.info(
        'Eliminando registros existentes en "%s"."%s" para el rango %s -> %s...',
        config.hana_schema,
        config.hana_table,
        start_date,
        end_date
    )

    conn = hana_connect(config)
    cursor = conn.cursor()

    try:
        sql = (
            f'DELETE FROM "{config.hana_schema}"."{config.hana_table}" '
            f'WHERE "startDate" >= ? AND "startDate" < ?'
        )

        cursor.execute(sql, (start_date, end_date))
        deleted = cursor.rowcount
        conn.commit()

        logger.info("Registros eliminados previamente: %s", deleted)

        return deleted

    finally:
        try:
            cursor.close()
        finally:
            conn.close()


def insert_rows_to_hana(
    config: Config,
    rows: List[Dict[str, Any]],
    logger: logging.Logger
) -> Tuple[int, int]:

    if not rows:
        logger.warning("No hay filas para cargar en HANA.")
        return 0, 0

    columns = ADHERENCIA_COLUMNS

    quoted_cols = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["?"] * len(columns))

    sql = (
        f'INSERT INTO "{config.hana_schema}"."{config.hana_table}" '
        f'({quoted_cols}) VALUES ({placeholders})'
    )

    loaded = 0
    failed = 0

    logger.info("Conectando a SAP HANA para carga...")

    conn = hana_connect(config)
    cursor = conn.cursor()

    try:
        logger.info(
            'Iniciando carga INSERT en "%s"."%s"...',
            config.hana_schema,
            config.hana_table
        )

        for start in range(0, len(rows), config.batch_size):

            batch = rows[start:start + config.batch_size]

            values = [
                tuple(row.get(c) for c in columns)
                for row in batch
            ]

            try:
                cursor.executemany(sql, values)
                conn.commit()
                loaded += len(batch)

                logger.info(
                    "Carga parcial confirmada | lote: %s | cargados acumulados: %s/%s",
                    len(batch),
                    loaded,
                    len(rows)
                )

            except Exception as exc:
                conn.rollback()
                failed += len(batch)

                logger.exception(
                    "Error cargando lote desde fila %s: %s",
                    start + 1,
                    exc
                )

    finally:
        try:
            cursor.close()
        finally:
            conn.close()

    return loaded, failed


def output_directory(config: Config) -> str:
    path = config.report_output_dir or os.getcwd()
    os.makedirs(path, exist_ok=True)
    return path


def write_report_file(config: Config, rows: List[Dict[str, Any]], logger: logging.Logger) -> Optional[str]:
    report_format = (config.report_output_format or "").strip().lower()
    if not report_format and config.attach_report_file:
        report_format = "xlsx"
    if not report_format:
        return None

    if report_format not in ("csv", "xlsx"):
        logger.warning("REPORT_OUTPUT_FORMAT invÃ¡lido: %s. No se generarÃ¡ archivo.", report_format)
        return None

    if not rows:
        logger.warning("No hay filas para generar reporte de adherencia.")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_directory(config), f"GNS_Adherencia_{timestamp}.{report_format}")

    if report_format == "csv":
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=ADHERENCIA_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    else:
        if pd is None:
            raise RuntimeError("Para generar Excel instala pandas y openpyxl: pip install pandas openpyxl")
        pd.DataFrame(rows, columns=ADHERENCIA_COLUMNS).to_excel(path, index=False)

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


def build_adherencia_report_html(
    total_business_units: int,
    total_management_units: int,
    total_jobs_ok: int,
    total_jobs_error: int,
    total_rows: int,
    loaded: int,
    failed: int,
    date_mode: str,
    duration_seconds: float
) -> str:
    now = datetime.now(ZoneInfo("America/Tegucigalpa"))
    coverage = (loaded / total_rows * 100) if total_rows else 0
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
              <h1 style="margin:8px 0 0;font-size:24px;line-height:1.2;">Reporte de Adherencia Genesys</h1>
              <p style="margin:8px 0 0;font-size:13px;color:#fecaca;">Reporte automático generado por PyFlow Manager</p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px;">
              <p style="margin:0 0 24px;font-size:14px;line-height:1.6;">Se ha completado la ejecución del proceso de adherencia. A continuación se presenta el resumen de Jobs WFM y carga a HANA.</p>
              <table width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Management Units</div>
                    <div style="font-size:26px;font-weight:700;color:#1e293b;margin-top:8px;">{total_management_units:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Business Units: {total_business_units:,}</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#DA282D;text-transform:uppercase;">Filas transformadas</div>
                    <div style="font-size:26px;font-weight:700;color:#DA282D;margin-top:8px;">{total_rows:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Registros obtenidos</div>
                  </td>
                </tr>
                <tr><td colspan="3" height="16"></td></tr>
                <tr>
                  <td width="48%" style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Jobs WFM</div>
                    <div style="font-size:22px;font-weight:700;color:#1e293b;margin-top:8px;">OK {total_jobs_ok:,} / Error {total_jobs_error:,}</div>
                    <div style="font-size:11px;color:#94a3b8;">Resultado por Management Unit</div>
                  </td>
                  <td width="4%">&nbsp;</td>
                  <td width="48%" style="background:#fdf2f2;border:1px solid #fee2e2;border-radius:6px;padding:20px;">
                    <div style="font-size:11px;font-weight:700;color:#b91c1c;text-transform:uppercase;">Errores HANA</div>
                    <div style="font-size:22px;font-weight:700;color:#b91c1c;margin-top:8px;">{failed:,}</div>
                    <div style="font-size:11px;color:#f87171;">Filas fallidas</div>
                  </td>
                </tr>
              </table>
              <div style="margin-top:24px;background:#fafafa;border:1px solid #f1f5f9;border-radius:6px;padding:22px;">
                <table width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td style="font-size:12px;font-weight:700;color:#475569;text-transform:uppercase;">Indicador de carga</td>
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
            <td align="center" style="background:#f1f5f9;padding:20px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;">Este es un correo automático generado por PyFlow Manager.</td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def enviar_reporte_adherencia(
    config: Config,
    total_business_units: int,
    total_management_units: int,
    total_jobs_ok: int,
    total_jobs_error: int,
    total_rows: int,
    loaded: int,
    failed: int,
    date_mode: str,
    duration_seconds: float,
    report_file: Optional[str],
    logger: logging.Logger
) -> bool:
    recipients = config.adherencia_report_email_to
    cc = config.adherencia_report_email_cc

    if not recipients:
        logger.info("Reporte por correo no enviado: no hay destinatarios en ADHERENCIA_REPORT_EMAIL_TO.")
        return False
    if not config.graph_sender_email:
        logger.warning("Reporte por correo no enviado: configura GRAPH_SENDER_EMAIL.")
        return False

    html = build_adherencia_report_html(
        total_business_units,
        total_management_units,
        total_jobs_ok,
        total_jobs_error,
        total_rows,
        loaded,
        failed,
        date_mode,
        duration_seconds
    )

    payload = {
        "message": {
            "subject": config.adherencia_report_subject,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": email}} for email in recipients],
            "ccRecipients": [{"emailAddress": {"address": email}} for email in cc],
        },
        "saveToSentItems": "true",
    }

    if config.attach_report_file and report_file:
        payload["message"]["attachments"] = [build_file_attachment(report_file)]
    elif config.attach_report_file and not report_file:
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
        logger.info("Reporte adherencia enviado a: %s", ", ".join(recipients + cc))
        return True
    except Exception as exc:
        logger.error("No se pudo enviar reporte adherencia: %s", exc)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Carga de adherencia Genesys Cloud WFM a SAP HANA"
    )

    parser.add_argument("--date", default=env_str("DATE", ""), help="Fecha local específica. Ejemplo: 2026-05-27")

    parser.add_argument("--start-date", default=env_str("START_DATE", ""), help="Fecha local inicial inclusiva. Ejemplo: 2026-05-01")

    parser.add_argument("--end-date", default=env_str("END_DATE", ""), help="Fecha local final inclusiva. Ejemplo: 2026-05-27")

    parser.add_argument("--start-utc", default=env_str("START_UTC", ""), help="Fecha UTC exacta como KNIME. Ejemplo: 2026-05-01T06:00:00.000Z")

    parser.add_argument("--end-utc", default=env_str("END_UTC", ""), help="Fecha UTC exacta como KNIME. Ejemplo: 2026-05-28T06:00:00.000Z")

    parser.add_argument("--days-back", default=env_str("DAYS_BACK", "5"), help="Días hacia atrás si no se indican fechas. Default: 5")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Ejecuta API y transformación, pero no carga a HANA."
    )

    args = parser.parse_args()
    if env_str("DAYS_BACK", "") == "" and getattr(args, "days_back", ""):
        os.environ["DAYS_BACK"] = str(args.days_back)
    if env_bool("DRY_RUN", False):
        args.dry_run = True

    logger = setup_logger()

    total_business_units = 0
    total_management_units = 0
    total_jobs_ok = 0
    total_jobs_error = 0
    total_rows = 0
    loaded = 0
    failed = 0
    config: Optional[Config] = None
    date_mode = ""
    report_file: Optional[str] = None
    all_rows: List[Dict[str, Any]] = []
    general_errors: List[str] = []
    management_unit_errors: List[str] = []

    start_time = time.time()
    pyflow_progress(2)

    try:
        config = load_config()
        pyflow_progress(5)

        start_date, end_date, date_mode = parse_dates(
            args,
            config.timezone_name
        )

        logger.info("=" * 70)
        logger.info("INICIO PROCESO GNS ADHERENCIA")
        log_params(logger, ["GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION", "HPR_HOST", "HPR_HOST_ESPEJO", "HPR_PORT", "HPR_USER", "HPR_PASSWORD", "HANA_SCHEMA", "HANA_ADHERENCIA_TABLE", "DATE", "START_DATE", "END_DATE", "START_UTC", "END_UTC", "DAYS_BACK", "MAX_API_RETRIES", "FAIL_ON_MU_ERROR", "DRY_RUN"])
        logger.info("Modo fecha: %s", date_mode)
        logger.info("startDate API: %s", start_date)
        logger.info("endDate API: %s", end_date)
        logger.info("Zona horaria Genesys: %s", config.timezone_name)
        logger.info("Tabla destino: %s.%s", config.hana_schema, config.hana_table)
        logger.info("HANA escritura: %s:%s", config.hana_host, config.hana_port)
        logger.info("HANA lectura/espejo: %s:%s", config.hana_read_host or "(no aplica en este script)", config.hana_port)
        logger.info("=" * 70)

        token = get_access_token(config, logger)
        pyflow_progress(10)

        business_units = get_business_units(config, token, logger)
        total_business_units = len(business_units)
        pyflow_progress(15)

        management_units = get_management_units(
            config,
            token,
            business_units,
            logger
        )

        total_management_units = len(management_units)
        pyflow_progress(20)

        all_rows = []

        for idx, mu in enumerate(management_units, start=1):

            mu_id = mu["managementUnitId"]
            mu_name = mu.get("managementUnitName")

            try:
                logger.info("-" * 70)
                logger.info(
                    "Procesando Management Unit %s/%s | %s | %s",
                    idx,
                    total_management_units,
                    mu_name,
                    mu_id
                )

                job_id = create_adherence_job(
                    config,
                    token,
                    mu_id,
                    start_date,
                    end_date,
                    logger
                )

                logger.info("Job creado correctamente: %s", job_id)

                job_result = wait_for_job(
                    config,
                    token,
                    job_id,
                    logger
                )

                data = download_job_data(
                    config,
                    token,
                    job_result,
                    logger
                )

                rows = transform_adherence_data(
                    data,
                    mu_id
                )

                all_rows.extend(rows)
                total_jobs_ok += 1

                logger.info(
                    "Management Unit procesada OK | filas obtenidas: %s | acumulado filas: %s",
                    len(rows),
                    len(all_rows)
                )

                time.sleep(10)

            except Exception as exc:
                total_jobs_error += 1

                msg = (
                    f"Error en Management Unit {mu_name} "
                    f"({mu_id}): {exc}"
                )

                management_unit_errors.append(msg)
                logger.exception(msg)

            progress = 20 + int((idx / max(total_management_units, 1)) * 50)
            pyflow_progress(progress)

        total_rows = len(all_rows)
        pyflow_progress(72)

        logger.info("=" * 70)
        logger.info(
            "Extracción finalizada. Filas transformadas válidas: %s",
            total_rows
        )

        if args.dry_run:
            logger.warning("DRY RUN activo. No se cargará información a HANA.")
        else:
            delete_existing_range(
                config,
                start_date,
                end_date,
                logger
            )
            pyflow_progress(82)

            loaded, failed = insert_rows_to_hana(
                config,
                all_rows,
                logger
            )
            pyflow_progress(92)

        if config.report_output_format or config.attach_report_file:
            report_file = write_report_file(config, all_rows, logger)
        pyflow_progress(95)

    except Exception as exc:
        general_errors.append(str(exc))
        logger.exception(
            "El proceso terminó con error general: %s",
            exc
        )
        logger.error(traceback.format_exc())

    duration = time.time() - start_time

    logger.info("=" * 70)
    logger.info("RESUMEN FINAL")
    logger.info("Business Units obtenidas: %s", total_business_units)
    logger.info("Management Units obtenidas: %s", total_management_units)
    logger.info("Jobs OK: %s", total_jobs_ok)
    logger.info("Jobs con error: %s", total_jobs_error)
    logger.info("Filas transformadas: %s", total_rows)
    logger.info("Filas cargadas/actualizadas en HANA: %s", loaded)
    logger.info("Filas fallidas en carga: %s", failed)
    if report_file:
        logger.info("Archivo generado: %s", report_file)
    logger.info("Errores generales: %s", len(general_errors))
    logger.info("Errores de Management Unit: %s", len(management_unit_errors))

    for err in general_errors[:20]:
        logger.error("Detalle error general: %s", err)

    for err in management_unit_errors[:20]:
        logger.error("Detalle error Management Unit: %s", err)

    logger.info("Duración total: %.2f segundos", duration)
    logger.info("=" * 70)

    if config is not None:
        enviar_reporte_adherencia(
            config,
            total_business_units,
            total_management_units,
            total_jobs_ok,
            total_jobs_error,
            total_rows,
            loaded,
            failed,
            date_mode,
            duration,
            report_file,
            logger
        )

    pyflow_progress(100)

    fail_on_mu_error = env_bool("FAIL_ON_MU_ERROR", True)
    has_mu_error = bool(management_unit_errors)

    if general_errors or failed > 0:
        return 1

    if has_mu_error and fail_on_mu_error:
        return 1

    if has_mu_error and not fail_on_mu_error:
        logger.warning("La ejecución finaliza OK porque FAIL_ON_MU_ERROR=false, aunque hubo Management Units con error temporal.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
