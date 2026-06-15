# =========================================================
# GNS IVR - Genesys Cloud -> SAP HANA / Excel / CSV
# =========================================================
#
# Objetivo:
# - Extraer conversaciones IVR por periodos controlados.
# - Cargar la base IVR a SAP HANA.
# - Generar bases de clientes con Full Autoservicio y/o Abandono Real.
#
# Reglas principales:
# - Si no se ingresan fechas, procesa automáticamente el día anterior.
# - Si se ingresan fechas, el rango no puede superar MAX_RANGE_DAYS.
# - Las lecturas SELECT a HANA usan HPR_HOST_ESPEJO.
# - Las escrituras MERGE/INSERT/DELETE a HANA usan HPR_HOST.
#
# Dependencias:
#   pip install requests hdbcli pandas openpyxl python-dotenv
#
# =========================================================

import os
import sys
import time
import json
import argparse
import logging
import traceback
import re
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Tuple, Optional, Iterable

import requests

try:
    import pandas as pd
except Exception:
    pd = None

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

    "HPR_HOST": {"type": "global", "global_key": "HPR_HOST", "label": "SAP HANA Host escritura", "required": True},
    "HPR_HOST_ESPEJO": {"type": "global", "global_key": "HPR_HOST_ESPEJO", "label": "SAP HANA Host espejo lectura", "required": True},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "SAP HANA Port", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "SAP HANA User", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "SAP HANA Password", "required": True, "secret": True},

    "HANA_SCHEMA": {"type": "text", "label": "Esquema HANA destino", "required": True, "default": "BI_SS"},
    "HANA_IVR_TABLE": {"type": "text", "label": "Tabla destino IVR", "required": True, "default": "GNS_IVR"},

    "RUN_MODE": {
        "type": "select",
        "label": "Modo de ejecucion",
        "required": True,
        "options": [
            "cargar_hana",
            "cargar_y_autoservicio",
            "cargar_y_abandono",
            "solo_autoservicio",
            "solo_abandono",
            "cargar_y_ambos",
            "enviar_encuesta",
            "cargar_hana_y_enviar_encuesta",
            "todo"
        ],
        "default": "cargar_hana"
    },
    "DAYS_BACK": {"type": "number", "label": "Dias hacia atras si no se indican fechas", "required": False, "default": "1"},
    "PROCESS_BY_DAY": {"type": "select", "label": "Procesar dia por dia", "required": True, "options": ["true", "false"], "default": "true"},

    "DELETE_RANGE_BEFORE_LOAD": {"type": "select", "label": "Borrar rango antes de cargar IVR", "required": True, "options": ["true", "false"], "default": "true"},
    "DRY_RUN": {"type": "select", "label": "Modo prueba sin escribir HANA", "required": True, "options": ["true", "false"], "default": "false"},

    "OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida para Excel/CSV", "required": False},
    "OUTPUT_FORMAT": {"type": "select", "label": "Formato salida", "required": True, "options": ["xlsx", "csv"], "default": "xlsx"},

    "ONLY_WITH_IVR": {"type": "select", "label": "Conservar solo conversaciones con IVR", "required": True, "options": ["true", "false"], "default": "true"},
    "ENRICH_CLIENTS_FROM_HANA": {"type": "select", "label": "Enriquecer salidas con datos cliente desde HANA espejo", "required": True, "options": ["true", "false"], "default": "true"},
    
    "TOKEN_QUALTRICTS": {
    "type": "global",
    "global_key": "TOKEN_QUALTRICTS",
    "label": "Token Qualtrics",
    "required": True,
    "secret": True}
}

LOGGER_NAME = "gns_ivr_pyflow"


def _clean(value: Any, default: Optional[str] = None) -> Optional[str]:
    if value is None:
        return default
    text = str(value).strip()
    if text == "" or text.lower() in ("null", "none", "undefined"):
        return default
    return text


def env_str(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = _clean(os.getenv(name), default)
    if required and not value:
        raise ValueError(f"Falta configurar variable/parámetro requerido: {name}")
    return "" if value is None else str(value)


def env_int(name: str, default: int, required: bool = False) -> int:
    raw = env_str(name, str(default), required=required)
    try:
        return int(raw)
    except Exception:
        raise ValueError(f"El parámetro {name} debe ser numérico. Valor recibido: {raw!r}")


def env_float(name: str, default: float, required: bool = False) -> float:
    raw = env_str(name, str(default), required=required)
    try:
        return float(raw)
    except Exception:
        raise ValueError(f"El parámetro {name} debe ser numérico. Valor recibido: {raw!r}")


def env_bool(name: str, default: bool = False) -> bool:
    raw = env_str(name, "", required=False).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "si", "sí")


def setup_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger


def log_params(logger: logging.Logger, names: List[str]) -> None:
    logger.info("Parámetros recibidos / aplicados:")
    secret_words = ("SECRET", "PASSWORD", "TOKEN", "KEY")
    for name in names:
        value = env_str(name, "")
        if any(w in name.upper() for w in secret_words) and value:
            value = "********"
        logger.info("  - %s: %s", name, value if value else "<vacío>")


def normalize_genesys_domain(value: str) -> str:
    value = str(value or "mypurecloud.com").strip()
    value = value.replace("https://", "").replace("http://", "").strip("/")
    if value.startswith("api."):
        value = value[4:]
    if value.startswith("login."):
        value = value[6:]
    return value


def genesys_api_url(region: str) -> str:
    return f"https://api.{normalize_genesys_domain(region)}"


def genesys_login_url(region: str) -> str:
    return f"https://login.{normalize_genesys_domain(region)}/oauth/token"


def validate_identifier(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""):
        raise ValueError(f"Identificador SQL inválido: {value!r}")


def parse_local_date(value: str) -> date:
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Fecha inválida: {value!r}. Use YYYY-MM-DD o DD/MM/YYYY.")


def to_utc_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def parse_utc_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def utc_to_local_str(value: str, tz_name: str) -> str:
    if not value:
        return ""
    try:
        dt = parse_utc_z(value)
        return dt.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def compact_phone(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"[^0-9]", "", text)


def remove_hn_prefix(value: Any) -> str:
    text = compact_phone(value)
    if len(text) == 11 and text.startswith("504"):
        return text[3:]
    return text


def join_unique(values: Iterable[Any], sep: str = "|") -> str:
    seen = []
    for value in values:
        text = _clean(value, "")
        if text and text not in seen:
            seen.append(text)
    return sep.join(seen)


@dataclass
class Config:
    genesys_client_id: str
    genesys_client_secret: str
    genesys_api_base: str
    genesys_login_url: str
    hana_write_host: str
    hana_read_host: str
    hana_port: int
    hana_user: str
    hana_password: str
    hana_schema: str
    hana_ivr_table: str
    timezone_name: str
    days_back: int
    max_range_days: int
    process_by_day: bool
    delete_range_before_load: bool
    dry_run: bool
    output_dir: str
    output_format: str
    job_page_size: int
    request_timeout: int
    max_api_retries: int
    poll_seconds: int
    max_poll_attempts: int
    api_sleep_seconds: float
    batch_size: int
    max_conversations: int
    only_with_ivr: bool
    enrich_clients_from_hana: bool
    qualtrics_token: str
    qualtrics_endpoint: str
    qualtrics_token: str
    qualtrics_endpoint: str
    qualtrics_delay_seconds: int


def load_config() -> Config:
    try:
        load_dotenv()
    except Exception:
        pass

    region = env_str("GENESYS_REGION", "mypurecloud.com", required=True)

    return Config(
        genesys_client_id=env_str("GENESYS_CLIENT_ID", required=True),
        genesys_client_secret=env_str("GENESYS_CLIENT_SECRET", required=True),
        genesys_api_base=genesys_api_url(region),
        genesys_login_url=genesys_login_url(region),
        hana_write_host=env_str("HPR_HOST", required=True),
        hana_read_host=env_str("HPR_HOST_ESPEJO", required=True),
        hana_port=env_int("HPR_PORT", 30015, required=True),
        hana_user=env_str("HPR_USER", required=True),
        hana_password=env_str("HPR_PASSWORD", required=True),
        hana_schema=env_str("HANA_SCHEMA", "BI_SS"),
        hana_ivr_table=env_str("HANA_IVR_TABLE", "GNS_IVR"),
        timezone_name=env_str("GENESYS_TIMEZONE", "America/Tegucigalpa"),
        days_back=env_int("DAYS_BACK", 1),
        max_range_days=env_int("MAX_RANGE_DAYS", 30),
        process_by_day=env_bool("PROCESS_BY_DAY", True),
        delete_range_before_load=env_bool("DELETE_RANGE_BEFORE_LOAD", True),
        dry_run=env_bool("DRY_RUN", False),
        output_dir=env_str("OUTPUT_DIR", ""),
        output_format=env_str("OUTPUT_FORMAT", "xlsx").lower(),
        job_page_size=env_int("JOB_PAGE_SIZE", 100),
        request_timeout=env_int("REQUEST_TIMEOUT", 120),
        max_api_retries=env_int("MAX_API_RETRIES", 5),
        poll_seconds=env_int("POLL_SECONDS", 10),
        max_poll_attempts=env_int("MAX_POLL_ATTEMPTS", 120),
        api_sleep_seconds=env_float("API_SLEEP_SECONDS", 1.0),
        batch_size=env_int("HANA_BATCH_SIZE", 1000),
        max_conversations=env_int("MAX_CONVERSATIONS", 0),
        only_with_ivr=env_bool("ONLY_WITH_IVR", True),
        enrich_clients_from_hana=env_bool("ENRICH_CLIENTS_FROM_HANA", True),
        qualtrics_token=env_str("TOKEN_QUALTRICTS", required=True),
        qualtrics_endpoint=env_str("POST_AUTOSERVICIO_QUALTRICTS_QA", required=True),
    )

#Funcion para enviar encuesta
def enviar_encuesta_qualtrics(config: Config,
                              cliente: Dict[str, Any],
                              logger: logging.Logger) -> bool:

    correo = str(
        cliente.get("CLIENTE_E_MAIL")
        or cliente.get("E_MAIL")
        or ""
    ).strip()

    if not correo:
        logger.warning(
            "Cliente sin correo. No se envía encuesta. DNI: %s",
            cliente.get("ETIQUETA_EXTERNA")
        )
        return False

    event_data = {}

    for key, value in cliente.items():

        if value is None:
            event_data[key] = ""

        elif isinstance(value, datetime):
            event_data[key] = value.strftime("%Y-%m-%d %H:%M:%S")

        elif isinstance(value, date):
            event_data[key] = value.strftime("%Y-%m-%d")

        else:
            texto = str(value).strip()

            if re.match(r"^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}:\d{3}$", texto):
                texto = texto[:-4]

            elif re.match(r"^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3,6}$", texto):
                texto = texto.split(".")[0]

            event_data[key] = texto

    # Asegura campos importantes como en KNIME
    event_data["E_MAIL"] = correo

    payload = event_data

    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": config.qualtrics_token
    }

    try:
        logger.info(
            "Payload Qualtrics enviado: %s",
            json.dumps(payload, ensure_ascii=False)[:3000]
        )

        response = requests.post(
            config.qualtrics_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )

        logger.info(
            "Respuesta Qualtrics | Status=%s | Body=%s",
            response.status_code,
            response.text[:1000]
        )

        if response.status_code in (200, 201, 202):
            logger.info(
                "Encuesta enviada | Correo=%s | DNI=%s",
                correo,
                cliente.get("ETIQUETA_EXTERNA")
            )
            return True

        logger.error(
            "Error Qualtrics %s | %s",
            response.status_code,
            response.text
        )
        return False

    except Exception as exc:
        logger.error(
            "Error enviando encuesta: %s",
            str(exc)
        )
        return False
    
        qualtrics_token=env_str("TOKEN_QUALTRICTS", ""),
        qualtrics_endpoint=env_str("POST_AUTOSERVICIO_QUALTRICTS_QA", ""),
        qualtrics_delay_seconds=env_int("QUALTRICS_DELAY_SECONDS", 5),
    )


def pyflow_progress(value: int) -> None:
    value = max(0, min(100, int(value)))
    print(f"PYFLOW_PROGRESS={value}", flush=True)


def limpiar_valor_qualtrics(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    texto = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}:\d{3}$", texto):
        return texto[:-4]
    if re.match(r"^\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\.\d{3,6}$", texto):
        return texto.split(".")[0]
    return texto


def enviar_encuesta_qualtrics(config: Config, cliente: Dict[str, Any], logger: logging.Logger) -> bool:
    correo = limpiar_valor_qualtrics(
        cliente.get("CLIENTE_E_MAIL")
        or cliente.get("E_MAIL")
        or ""
    )

    if not correo:
        logger.warning(
            "Cliente sin correo. No se envia encuesta. DNI: %s",
            cliente.get("ETIQUETA_EXTERNA")
        )
        return False

    payload: Dict[str, str] = {}
    for key, value in cliente.items():
        payload[str(key)] = limpiar_valor_qualtrics(value)
    payload["E_MAIL"] = correo

    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": config.qualtrics_token
    }

    try:
        logger.info(
            "Payload Qualtrics enviado: %s",
            json.dumps(payload, ensure_ascii=False)[:3000]
        )
        response = requests.post(
            config.qualtrics_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )
        logger.info(
            "Respuesta Qualtrics | Status=%s | Body=%s",
            response.status_code,
            response.text[:1000]
        )
        if response.status_code in (200, 201, 202):
            logger.info(
                "Encuesta enviada | Correo=%s | DNI=%s",
                correo,
                cliente.get("ETIQUETA_EXTERNA")
            )
            return True

        logger.error("Error Qualtrics %s | %s", response.status_code, response.text)
        return False
    except Exception as exc:
        logger.error("Error enviando encuesta: %s", str(exc))
        return False


def enviar_encuestas_qualtrics(config: Config, rows: List[Dict[str, Any]], logger: logging.Logger) -> Tuple[int, int]:
    if not config.qualtrics_token or not config.qualtrics_endpoint:
        raise ValueError("Para enviar encuestas debes configurar TOKEN_QUALTRICTS y POST_AUTOSERVICIO_QUALTRICTS_QA.")

    logger.info("Enviando encuestas Qualtrics a clientes Full Autoservicio...")
    enviadas = 0
    sin_correo = 0
    total_clientes = len(rows)

    for index, cliente in enumerate(rows, start=1):
        correo = limpiar_valor_qualtrics(
            cliente.get("CLIENTE_E_MAIL")
            or cliente.get("E_MAIL")
            or ""
        )
        if not correo:
            sin_correo += 1

        if enviar_encuesta_qualtrics(config, cliente, logger):
            enviadas += 1

        if total_clientes:
            pyflow_progress(80 + int((index / total_clientes) * 15))

        if index < total_clientes:
            logger.info(
                "Esperando %s segundos antes del siguiente envio Qualtrics...",
                config.qualtrics_delay_seconds
            )
            time.sleep(config.qualtrics_delay_seconds)

    logger.info(
        "Encuestas Qualtrics enviadas: %s | Sin correo: %s | Total Full Autoservicio: %s",
        enviadas,
        sin_correo,
        total_clientes
    )
    return enviadas, sin_correo


def calculate_interval(args: argparse.Namespace, config: Config) -> Tuple[datetime, datetime, str]:
    tz = ZoneInfo(config.timezone_name)

    if args.start_utc and args.end_utc:
        start_dt = parse_utc_z(args.start_utc)
        end_dt = parse_utc_z(args.end_utc)
        mode = "UTC manual"
    elif args.date:
        d = parse_local_date(args.date)
        start_dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
        end_dt = start_dt + timedelta(days=1)
        mode = f"Día local {d.isoformat()}"
    elif args.start_date and args.end_date:
        d1 = parse_local_date(args.start_date)
        d2 = parse_local_date(args.end_date)
        if d2 < d1:
            raise ValueError("END_DATE no puede ser menor que START_DATE.")
        start_dt = datetime(d1.year, d1.month, d1.day, 0, 0, 0, tzinfo=tz)
        end_dt = datetime(d2.year, d2.month, d2.day, 0, 0, 0, tzinfo=tz) + timedelta(days=1)
        mode = f"Rango local {d1.isoformat()} al {d2.isoformat()} inclusive"
    else:
        if config.days_back <= 0:
            raise ValueError("DAYS_BACK debe ser mayor que cero.")
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = today - timedelta(days=config.days_back)
        end_dt = today
        mode = f"Automático: últimos {config.days_back} días cerrados"

    if end_dt <= start_dt:
        raise ValueError("La fecha final debe ser mayor que la fecha inicial.")

    duration_days = (end_dt - start_dt).total_seconds() / 86400
    if duration_days > config.max_range_days:
        raise ValueError(
            f"Rango no permitido: {duration_days:.2f} días. Máximo permitido: {config.max_range_days} días."
        )

    return start_dt, end_dt, mode


def build_windows(start_dt: datetime, end_dt: datetime, by_day: bool) -> List[Tuple[datetime, datetime]]:
    if not by_day:
        return [(start_dt, end_dt)]
    windows = []
    current = start_dt
    while current < end_dt:
        nxt = min(current + timedelta(days=1), end_dt)
        windows.append((current, nxt))
        current = nxt
    return windows


def request_with_retry(method: str, url: str, config: Config, logger: logging.Logger, **kwargs) -> requests.Response:
    last_error = None
    for attempt in range(1, config.max_api_retries + 1):
        try:
            response = requests.request(method, url, timeout=config.request_timeout, **kwargs)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * attempt)
                logger.warning("HTTP 429 | intento %s/%s | esperando %ss", attempt, config.max_api_retries, wait)
                time.sleep(wait)
                continue
            if response.status_code >= 500:
                wait = min(60, 5 * attempt)
                logger.warning("HTTP %s | intento %s/%s | esperando %ss", response.status_code, attempt, config.max_api_retries, wait)
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                logger.error("HTTP %s | %s", response.status_code, response.text[:1000])
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            wait = min(60, 5 * attempt)
            logger.warning("Error request | intento %s/%s | %s | esperando %ss", attempt, config.max_api_retries, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"No se pudo completar request: {url}. Último error: {last_error}")


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
        raise RuntimeError("Genesys no devolvió access_token.")
    logger.info("Token obtenido correctamente.")
    return token


def genesys_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_details_job(config: Config, token: str, start_dt: datetime, end_dt: datetime, logger: logging.Logger) -> str:
    url = f"{config.genesys_api_base}/api/v2/analytics/conversations/details/jobs"
    body = {
        "interval": f"{to_utc_z(start_dt)}/{to_utc_z(end_dt)}",
        "order": "asc",
        "orderBy": "conversationStart",
        "paging": {"pageSize": config.job_page_size},
        "segmentFilters": [
            {"type": "or", "predicates": [{"dimension": "mediaType", "value": "voice"}]}
        ],
    }
    logger.info("Creando job conversations details | %s", body["interval"])
    response = request_with_retry("POST", url, config, logger, headers=genesys_headers(token), json=body)
    data = response.json()
    job_id = data.get("jobId") or data.get("id") or (data.get("job") or {}).get("id")
    if not job_id:
        raise RuntimeError(f"No se recibió jobId desde Genesys. Respuesta: {data}")
    logger.info("Job creado: %s", job_id)
    return job_id


def get_job_results_page(config: Config, token: str, job_id: str, cursor: str, logger: logging.Logger) -> Dict[str, Any]:
    url = f"{config.genesys_api_base}/api/v2/analytics/conversations/details/jobs/{job_id}/results?pageSize={config.job_page_size}"
    if cursor:
        url += f"&cursor={cursor}"
    response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token))
    return response.json()


def fetch_conversation_details(config: Config, token: str, start_dt: datetime, end_dt: datetime, logger: logging.Logger) -> List[Dict[str, Any]]:
    job_id = create_details_job(config, token, start_dt, end_dt, logger)
    all_conversations: List[Dict[str, Any]] = []
    cursor = ""
    for attempt in range(1, config.max_poll_attempts + 1):
        data = get_job_results_page(config, token, job_id, cursor, logger)
        conversations = data.get("conversations") or []
        next_cursor = data.get("cursor") or ""
        if conversations:
            all_conversations.extend(conversations)
            logger.info("Página job recibida | conversaciones: %s | acumulado: %s", len(conversations), len(all_conversations))
        else:
            logger.info("Job sin conversaciones todavía | intento %s/%s", attempt, config.max_poll_attempts)
        if config.max_conversations and len(all_conversations) >= config.max_conversations:
            logger.warning("Se alcanzó MAX_CONVERSATIONS=%s. Se corta extracción.", config.max_conversations)
            return all_conversations[:config.max_conversations]
        if next_cursor:
            cursor = next_cursor
            time.sleep(config.api_sleep_seconds)
            continue
        if conversations or all_conversations:
            break
        time.sleep(config.poll_seconds)
    return all_conversations


def fetch_divisions_lookup(config: Config, token: str, logger: logging.Logger) -> Dict[str, str]:
    url = f"{config.genesys_api_base}/api/v2/authorization/divisions?pageSize=500"
    try:
        response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token))
        entities = response.json().get("entities") or []
        lookup = {e.get("id"): e.get("name") for e in entities if e.get("id")}
        logger.info("Divisiones obtenidas: %s", len(lookup))
        return lookup
    except Exception as exc:
        logger.warning("No se pudo obtener catálogo de divisiones: %s", exc)
        return {}


IVR_COLUMNS = [
    "FECHA_CARGA", "ID_TRANSACCION", "FECHA_INGRESO", "FECHA_FIN", "DIRECCION_ORIGINAL",
    "ANI", "DNIS", "ETIQUETA_EXTERNA", "OPCIONES_NAVEGACION", "PASO_CE",
    *[f"CUSTOM_{i}" for i in range(1, 51)],
    "DIVISION", "DIRECCION", "ID_IVR", "NOMBRE_IVR", "DURACION_IVR_TOTAL",
    "TIPO_DESCONEXION", "AUTOSERVICIO", "INGRESO_DNI", "AUTENTICACION", "TOKEN",
    "OTP", "ORGANIZACION", "BLACKLIST", "PASO_AGENTE_FLAG",
]


def collect_attributes(conversation: Dict[str, Any]) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {}
    for participant in conversation.get("participants") or []:
        p_attrs = participant.get("attributes") or {}
        for k, v in p_attrs.items():
            if k not in attrs or attrs.get(k) in (None, ""):
                attrs[k] = v
    return attrs


def iter_sessions(conversation: Dict[str, Any]):
    for participant in conversation.get("participants") or []:
        purpose = participant.get("purpose")
        for session in participant.get("sessions") or []:
            yield participant, purpose, session


def has_ivr(conversation: Dict[str, Any]) -> bool:
    for _p, purpose, session in iter_sessions(conversation):
        if purpose == "ivr" or session.get("flow"):
            return True
    return False


def get_ivr_info(conversation: Dict[str, Any]) -> Tuple[str, str, Any]:
    flow_ids = []
    flow_names = []
    total_ivr = 0
    for _participant, purpose, session in iter_sessions(conversation):
        flow = session.get("flow") or {}
        if flow.get("flowId"):
            flow_ids.append(flow.get("flowId"))
        if flow.get("flowName"):
            flow_names.append(flow.get("flowName"))
        if purpose == "ivr":
            for metric in session.get("metrics") or []:
                if metric.get("name") == "tIvr":
                    try:
                        total_ivr += int(metric.get("value") or 0)
                    except Exception:
                        pass
    return join_unique(flow_ids), join_unique(flow_names), total_ivr if total_ivr else None


def get_first_customer_session(conversation: Dict[str, Any]) -> Dict[str, Any]:
    for participant, purpose, session in iter_sessions(conversation):
        if purpose == "customer":
            return session
    for participant, purpose, session in iter_sessions(conversation):
        return session
    return {}


def get_disconnect_types(conversation: Dict[str, Any]) -> str:
    values = []
    for _p, _purpose, session in iter_sessions(conversation):
        for segment in session.get("segments") or []:
            if segment.get("disconnectType"):
                values.append(segment.get("disconnectType"))
    return join_unique(values)


def get_queue_ids(conversation: Dict[str, Any]) -> str:
    values = []
    for _p, _purpose, session in iter_sessions(conversation):
        for segment in session.get("segments") or []:
            qid = segment.get("queueId")
            if qid:
                values.append(qid)
    return join_unique(values)


def get_directions(conversation: Dict[str, Any]) -> str:
    values = []
    for _p, _purpose, session in iter_sessions(conversation):
        if session.get("direction"):
            values.append(session.get("direction"))
    return join_unique(values)


def flag_autoservicio(opciones: str) -> int:
    x = (opciones or "").upper()
    patterns = ["TARJETA[OK]", "CONSULTACUENTA[OK]", "CONSULTAPRESTAMOS[OK]", "REMESAS[NOEXISTE]", "REMESAS[OK]", "BLOQUEARTARJETA[OK]"]
    return 1 if any(p in x for p in patterns) else 0


def flag_ingreso_dni(opciones: str) -> int:
    return 1 if "SEGMENTO[OK]" in (opciones or "").upper() else 0


def flag_autenticacion(opciones: str) -> int:
    x = (opciones or "").upper()
    return 1 if ("VALIDAROTP[OK]" in x or "VALIDARTOKEN[OK]" in x) else 0


def flag_token(opciones: str) -> int:
    return 1 if "VALIDARTOKEN[OK]" in (opciones or "").upper() else 0


def flag_otp(opciones: str) -> int:
    return 1 if "VALIDAROTP[OK]" in (opciones or "").upper() else 0


def transform_conversation(conversation: Dict[str, Any], config: Config, divisions_lookup: Dict[str, str]) -> Optional[Dict[str, Any]]:
    if config.only_with_ivr and not has_ivr(conversation):
        return None
    attrs = collect_attributes(conversation)
    session0 = get_first_customer_session(conversation)
    ivr_id, ivr_name, ivr_duration = get_ivr_info(conversation)
    opciones = str(attrs.get("SPD_IVR_TrazaOpciones") or "")
    paso_ce = get_queue_ids(conversation)
    division_ids = conversation.get("divisionIds") or []
    division_names = [divisions_lookup.get(did, did) for did in division_ids]
    row = {
        "FECHA_CARGA": datetime.now(ZoneInfo(config.timezone_name)).strftime("%Y-%m-%d %H:%M:%S"),
        "ID_TRANSACCION": conversation.get("conversationId"),
        "FECHA_INGRESO": utc_to_local_str(conversation.get("conversationStart"), config.timezone_name),
        "FECHA_FIN": utc_to_local_str(conversation.get("conversationEnd"), config.timezone_name),
        "DIRECCION_ORIGINAL": conversation.get("originatingDirection"),
        "ANI": remove_hn_prefix(session0.get("ani")),
        "DNIS": remove_hn_prefix(session0.get("dnis")),
        "ETIQUETA_EXTERNA": str(conversation.get("externalTag") or ""),
        "OPCIONES_NAVEGACION": opciones,
        "PASO_CE": "SI" if paso_ce else "NO",
        "DIVISION": join_unique(division_names),
        "DIRECCION": get_directions(conversation),
        "ID_IVR": ivr_id,
        "NOMBRE_IVR": ivr_name,
        "DURACION_IVR_TOTAL": ivr_duration,
        "TIPO_DESCONEXION": get_disconnect_types(conversation),
        "AUTOSERVICIO": flag_autoservicio(opciones),
        "INGRESO_DNI": flag_ingreso_dni(opciones),
        "AUTENTICACION": flag_autenticacion(opciones),
        "TOKEN": flag_token(opciones),
        "OTP": flag_otp(opciones),
        "ORGANIZACION": "",
        "BLACKLIST": 1 if "|BLACKLIST_IVR" in opciones else 0,
        "PASO_AGENTE_FLAG": 1 if paso_ce else 0,
    }
    for i in range(1, 51):
        row[f"CUSTOM_{i}"] = attrs.get(f"SPD_Custom{i}")
    return row


def transform_conversations(conversations: List[Dict[str, Any]], config: Config, divisions_lookup: Dict[str, str]) -> List[Dict[str, Any]]:
    rows = []
    for conv in conversations:
        row = transform_conversation(conv, config, divisions_lookup)
        if row:
            rows.append(row)
    return rows


def hana_connect(config: Config, mode: str):
    if dbapi is None:
        raise RuntimeError("No está instalado hdbcli. Ejecuta: pip install hdbcli")
    host = config.hana_read_host if mode == "read" else config.hana_write_host
    return dbapi.connect(address=host, port=config.hana_port, user=config.hana_user, password=config.hana_password)




def get_hana_table_columns(config: Config, logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    """Lee columnas y tipos reales de HANA antes de cargar.

    Esto evita errores por columnas inexistentes y permite convertir valores
    vacíos a NULL cuando la columna es numérica, por ejemplo ETIQUETA_EXTERNA BIGINT.
    """
    validate_identifier(config.hana_schema)
    validate_identifier(config.hana_ivr_table)

    sql = """
        SELECT COLUMN_NAME, DATA_TYPE_NAME, LENGTH, SCALE, IS_NULLABLE
        FROM SYS.TABLE_COLUMNS
        WHERE SCHEMA_NAME = ?
          AND TABLE_NAME = ?
        ORDER BY POSITION
    """

    conn = hana_connect(config, "write")
    cur = conn.cursor()
    try:
        cur.execute(sql, (config.hana_schema.upper(), config.hana_ivr_table.upper()))
        meta = {}
        for r in cur.fetchall():
            col = str(r[0])
            meta[col.upper()] = {
                "column_name": col,
                "data_type": str(r[1] or "").upper(),
                "length": r[2],
                "scale": r[3],
                "is_nullable": str(r[4] or "").upper() == "TRUE",
            }
        if not meta:
            raise RuntimeError(
                f'No se encontraron columnas para "{config.hana_schema}"."{config.hana_ivr_table}". '
                'Valida esquema y nombre de tabla.'
            )
        logger.info('Columnas detectadas en HANA para "%s"."%s": %s', config.hana_schema, config.hana_ivr_table, len(meta))
        return meta
    finally:
        cur.close()
        conn.close()


def resolve_load_columns(config: Config, logger: logging.Logger) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """Devuelve solo columnas compatibles y metadata de HANA."""
    hana_meta = get_hana_table_columns(config, logger)
    hana_set = set(hana_meta.keys())

    if "ID_TRANSACCION" not in hana_set:
        raise RuntimeError(
            'La tabla destino no tiene la columna obligatoria ID_TRANSACCION. '
            'No se puede hacer MERGE de IVR de forma segura.'
        )

    load_columns = [c for c in IVR_COLUMNS if c.upper() in hana_set]
    missing_columns = [c for c in IVR_COLUMNS if c.upper() not in hana_set]

    if missing_columns:
        logger.warning(
            'Columnas del script que NO existen en HANA y serán omitidas: %s',
            ', '.join(missing_columns)
        )

    if not load_columns:
        raise RuntimeError('No hay columnas compatibles entre el script y la tabla HANA.')

    logger.info('Columnas que se cargarán a HANA: %s', len(load_columns))
    return load_columns, hana_meta


def sanitize_hana_value(value: Any, meta: Dict[str, Any]) -> Any:
    """Convierte valores Python al tipo esperado por HANA."""
    dtype = str(meta.get("data_type") or "").upper()

    if value is None:
        return None

    if isinstance(value, str):
        raw = value.strip()
        if raw == "":
            return None
    else:
        raw = value

    numeric_types = {
        "BIGINT", "INTEGER", "INT", "SMALLINT", "TINYINT",
        "DECIMAL", "DEC", "NUMERIC", "DOUBLE", "REAL", "FLOAT"
    }

    if dtype in numeric_types:
        text = str(raw).strip()
        if text == "":
            return None
        # ETIQUETA_EXTERNA y otros identificadores numéricos pueden venir con guiones/espacios.
        cleaned = re.sub(r"[^0-9.-]", "", text)
        if cleaned in ("", "-", ".", "-."):
            return None
        try:
            if dtype in {"BIGINT", "INTEGER", "INT", "SMALLINT", "TINYINT"}:
                return int(float(cleaned))
            return float(cleaned)
        except Exception:
            return None

    if dtype in {"TIMESTAMP", "DATE", "SECONDDATE", "TIME"}:
        text = str(raw).strip()
        return text if text else None

    return raw


def prepare_hana_tuple(row: Dict[str, Any], columns: List[str], hana_meta: Dict[str, Dict[str, Any]]) -> Tuple[Any, ...]:
    values = []
    for col in columns:
        meta = hana_meta.get(col.upper(), {})
        values.append(sanitize_hana_value(row.get(col), meta))
    return tuple(values)


def delete_ivr_range(config: Config, start_dt: datetime, end_dt: datetime, logger: logging.Logger) -> int:
    validate_identifier(config.hana_schema)
    validate_identifier(config.hana_ivr_table)
    start_local = start_dt.astimezone(ZoneInfo(config.timezone_name)).strftime("%Y-%m-%d %H:%M:%S")
    end_local = end_dt.astimezone(ZoneInfo(config.timezone_name)).strftime("%Y-%m-%d %H:%M:%S")
    sql = f'DELETE FROM "{config.hana_schema}"."{config.hana_ivr_table}" WHERE "FECHA_INGRESO" >= ? AND "FECHA_INGRESO" < ?'
    logger.info('Eliminando rango IVR en "%s"."%s": %s -> %s', config.hana_schema, config.hana_ivr_table, start_local, end_local)
    conn = hana_connect(config, "write")
    cur = conn.cursor()
    try:
        cur.execute(sql, (start_local, end_local))
        deleted = cur.rowcount
        conn.commit()
        logger.info("Registros eliminados previamente: %s", deleted)
        return deleted
    finally:
        cur.close()
        conn.close()


def merge_ivr_rows(config: Config, rows: List[Dict[str, Any]], logger: logging.Logger, columns: Optional[List[str]] = None, hana_meta: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[int, int]:
    if not rows:
        logger.warning("No hay filas IVR para cargar.")
        return 0, 0
    validate_identifier(config.hana_schema)
    validate_identifier(config.hana_ivr_table)
    if columns is None or hana_meta is None:
        columns, hana_meta = resolve_load_columns(config, logger)
    select_cols = ", ".join([f'? AS "{c}"' for c in columns])
    update_cols = ", ".join([f'T."{c}" = S."{c}"' for c in columns if c != "ID_TRANSACCION"])
    insert_cols = ", ".join([f'"{c}"' for c in columns])
    insert_values = ", ".join([f'S."{c}"' for c in columns])
    sql = f'''
        MERGE INTO "{config.hana_schema}"."{config.hana_ivr_table}" AS T
        USING (SELECT {select_cols} FROM DUMMY) AS S
        ON T."ID_TRANSACCION" = S."ID_TRANSACCION"
        WHEN MATCHED THEN UPDATE SET {update_cols}
        WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_values})
    '''
    loaded = 0
    failed = 0
    conn = hana_connect(config, "write")
    cur = conn.cursor()
    try:
        logger.info('Cargando IVR por MERGE en "%s"."%s"...', config.hana_schema, config.hana_ivr_table)
        for start in range(0, len(rows), config.batch_size):
            batch = rows[start:start + config.batch_size]
            values = [prepare_hana_tuple(row, columns, hana_meta) for row in batch]
            try:
                cur.executemany(sql, values)
                conn.commit()
                loaded += len(batch)
                logger.info("MERGE parcial OK | lote: %s | acumulado: %s/%s", len(batch), loaded, len(rows))
            except Exception as exc:
                conn.rollback()
                failed += len(batch)
                logger.exception("Error en MERGE lote desde fila %s: %s", start + 1, exc)
    finally:
        cur.close()
        conn.close()
    return loaded, failed


def chunks(items: List[Any], size: int):
    for i in range(0, len(items), size):
        yield items[i:i+size]


def query_client_profiles(config: Config, etiquetas: List[str], logger: logging.Logger) -> Dict[str, Dict[str, Any]]:
    etiquetas = sorted({str(x).strip() for x in etiquetas if str(x or "").strip()})
    if not etiquetas:
        return {}
    logger.info("Consultando datos de cliente en HANA espejo para %s identificaciones...", len(etiquetas))
    sql_tpl = '''
        SELECT DISTINCT
            COALESCE(
                NULLIF(TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_1)), ''),
                NULLIF(TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_2)), '')
            ) AS ETIQUETA_EXTERNA,
            cdc.TEL_CELULAR,
            cdc.TEL_PRINCIPAL,
            cdc.DEPARTAMENTO,
            cdc.ESTADO_CIVIL,
            cdc.PAIS,
            cdc.NOMBRE_LEGAL,
            SUBSTRING_REGEXPR('^[^ ]+' IN TRIM(cdc.NOMBRE_LEGAL)) AS PRIMER_NOMBRE,
            SUBSTRING_REGEXPR('[^ ]+$' IN TRIM(cdc.NOMBRE_LEGAL)) AS PRIMER_APELLIDO,
            cdc.E_MAIL,
            CASE
                WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO PERSONAS' THEN 'Personas'
                WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO PYME' THEN 'PYME'
                WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO COMERCIAL' THEN 'Comercial'
                WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO CORPORATIVA' THEN 'Corporativa'
                ELSE 'Otros'
            END AS SEGMENTO_BANCA,
            cdc.GENERO,
            cdc.TIPO_SECTOR_ECONOMICO,
            cdc.NIVEL_EDUCATIVO,
            cdc.FECHA_ULTIMA_ACTUALIZACION
        FROM DS_STG.CRM_DIM_CLIENTES cdc
        WHERE (TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_1)) IN ({placeholders})
               OR TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_2)) IN ({placeholders}))
    '''
    cols = ["ETIQUETA_EXTERNA", "TEL_CELULAR", "TEL_PRINCIPAL", "DEPARTAMENTO", "ESTADO_CIVIL", "PAIS", "NOMBRE_LEGAL", "PRIMER_NOMBRE", "PRIMER_APELLIDO", "E_MAIL", "SEGMENTO_BANCA", "GENERO", "TIPO_SECTOR_ECONOMICO", "NIVEL_EDUCATIVO", "FECHA_ULTIMA_ACTUALIZACION"]
    lookup: Dict[str, Dict[str, Any]] = {}
    conn = hana_connect(config, "read")
    cur = conn.cursor()
    try:
        for batch in chunks(etiquetas, 500):
            placeholders = ", ".join(["?"] * len(batch))
            sql = sql_tpl.format(placeholders=placeholders)
            params = batch + batch
            cur.execute(sql, params)
            for r in cur.fetchall():
                item = dict(zip(cols, r))
                key = str(item.get("ETIQUETA_EXTERNA") or "").strip()
                if key and key not in lookup:
                    lookup[key] = item
        logger.info("Clientes enriquecidos encontrados: %s", len(lookup))
        return lookup
    finally:
        cur.close()
        conn.close()


def build_segment_bases(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        etiqueta = str(row.get("ETIQUETA_EXTERNA") or "").strip()
        if not etiqueta:
            etiqueta = str(row.get("ANI") or "").strip()
        if not etiqueta:
            continue
        grouped.setdefault(etiqueta, []).append(row)
    autoservicio = []
    abandono = []
    for etiqueta, items in grouped.items():
        max_auto = max(int(x.get("AUTOSERVICIO") or 0) for x in items)
        max_paso_agente = max(int(x.get("PASO_AGENTE_FLAG") or 0) for x in items)
        max_blacklist = max(int(x.get("BLACKLIST") or 0) for x in items)
        base = dict(items[0])
        base["MAX_AUTOSERVICIO"] = max_auto
        base["MAX_PASO_AGENTE_FLAG"] = max_paso_agente
        base["MAX_BLACKLIST"] = max_blacklist
        base["TOTAL_INTERACCIONES_IVR"] = len(items)
        if max_blacklist == 0 and max_auto == 1 and max_paso_agente == 0:
            base["FULL_AUTOSERVICIO"] = 1
            autoservicio.append(base)
        if max_blacklist == 0 and max_auto == 0 and max_paso_agente == 0:
            base["ABANDONO_REAL"] = 1
            abandono.append(base)
    return autoservicio, abandono


def enrich_rows(rows: List[Dict[str, Any]], client_lookup: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        etiqueta = str(row.get("ETIQUETA_EXTERNA") or "").strip()
        client = client_lookup.get(etiqueta, {})
        new = dict(row)
        for k, v in client.items():
            if k not in new:
                new[k] = v
            else:
                new[f"CLIENTE_{k}"] = v
        out.append(new)
    return out


def write_output(rows: List[Dict[str, Any]], output_dir: str, name: str, fmt: str, logger: logging.Logger) -> Optional[str]:
    if not output_dir:
        output_dir = os.getcwd()
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fmt = fmt.lower()
    path = os.path.join(output_dir, f"{name}_{ts}.{fmt}")
    if pd is None:
        raise RuntimeError("Para generar Excel/CSV instala pandas y openpyxl: pip install pandas openpyxl")
    df = pd.DataFrame(rows)
    if fmt == "xlsx":
        df.to_excel(path, index=False)
    elif fmt == "csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        raise ValueError("OUTPUT_FORMAT debe ser xlsx o csv")
    logger.info("Archivo generado: %s | filas: %s", path, len(rows))
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="GNS IVR - Genesys Cloud -> SAP HANA / segmentos")
    parser.add_argument("--date", default=env_str("DATE", ""), help="Fecha local específica YYYY-MM-DD.")
    parser.add_argument("--start-date", default=env_str("START_DATE", ""), help="Fecha local inicial YYYY-MM-DD.")
    parser.add_argument("--end-date", default=env_str("END_DATE", ""), help="Fecha local final YYYY-MM-DD inclusive.")
    parser.add_argument("--start-utc", default=env_str("START_UTC", ""), help="Inicio UTC exacto.")
    parser.add_argument("--end-utc", default=env_str("END_UTC", ""), help="Fin UTC exacto.")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en HANA.")
    args = parser.parse_args()
    logger = setup_logger()
    start_time = time.time()
    total_conversations = 0
    total_ivr_rows = 0
    deleted = 0
    loaded = 0
    failed = 0
    surveys_sent = 0
    surveys_without_email = 0
    output_files: List[str] = []
    errors: List[str] = []
    try:
        pyflow_progress(2)
        config = load_config()
        if args.dry_run:
            config.dry_run = True
        run_mode = env_str("RUN_MODE", "cargar_hana")
        valid_modes = {
            "cargar_hana",
            "cargar_y_autoservicio",
            "cargar_y_abandono",
            "solo_autoservicio",
            "solo_abandono",
            "cargar_y_ambos",
            "enviar_encuesta",
            "cargar_hana_y_enviar_encuesta",
            "todo",
        }
        if run_mode not in valid_modes:
            raise ValueError(f"RUN_MODE inválido: {run_mode}. Valores válidos: {sorted(valid_modes)}")
        send_surveys = run_mode in ("enviar_encuesta", "cargar_hana_y_enviar_encuesta", "todo")
        start_dt, end_dt, date_mode = calculate_interval(args, config)
        windows = build_windows(start_dt, end_dt, config.process_by_day)
        pyflow_progress(5)
        logger.info("=" * 80)
        logger.info("INICIO PROCESO GNS IVR")
        log_params(logger, [
            "GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION",
            "HPR_HOST", "HPR_HOST_ESPEJO", "HPR_PORT", "HPR_USER", "HPR_PASSWORD",
            "HANA_SCHEMA", "HANA_IVR_TABLE", "RUN_MODE", "DATE", "START_DATE", "END_DATE", "START_UTC", "END_UTC",
            "GENESYS_TIMEZONE", "DAYS_BACK", "MAX_RANGE_DAYS", "PROCESS_BY_DAY", "DELETE_RANGE_BEFORE_LOAD", "DRY_RUN", "OUTPUT_DIR", "OUTPUT_FORMAT",
            "ONLY_WITH_IVR", "ENRICH_CLIENTS_FROM_HANA", "TOKEN_QUALTRICTS", "POST_AUTOSERVICIO_QUALTRICTS_QA"
        ])
        logger.info("Modo fecha: %s", date_mode)
        logger.info("Inicio UTC: %s", to_utc_z(start_dt))
        logger.info("Fin UTC: %s", to_utc_z(end_dt))
        logger.info("Ventanas a procesar: %s", len(windows))
        logger.info("=" * 80)
        token = get_access_token(config, logger)
        pyflow_progress(10)
        divisions_lookup = fetch_divisions_lookup(config, token, logger)
        pyflow_progress(15)
        all_rows: List[Dict[str, Any]] = []
        for idx, (w_start, w_end) in enumerate(windows, start=1):
            logger.info("-" * 80)
            logger.info("Procesando ventana %s/%s | %s -> %s", idx, len(windows), to_utc_z(w_start), to_utc_z(w_end))
            conversations = fetch_conversation_details(config, token, w_start, w_end, logger)
            total_conversations += len(conversations)
            rows = transform_conversations(conversations, config, divisions_lookup)
            all_rows.extend(rows)
            logger.info("Ventana procesada | conversaciones: %s | filas IVR: %s | acumulado filas IVR: %s", len(conversations), len(rows), len(all_rows))
            pyflow_progress(15 + int((idx / max(len(windows), 1)) * 35))
            time.sleep(config.api_sleep_seconds)
        total_ivr_rows = len(all_rows)
        pyflow_progress(50)
        logger.info("=" * 80)
        logger.info("Extracción finalizada | conversaciones: %s | filas IVR: %s", total_conversations, total_ivr_rows)
        must_load = run_mode in ("cargar_hana", "cargar_y_autoservicio", "cargar_y_abandono", "cargar_y_ambos", "cargar_hana_y_enviar_encuesta", "todo")
        if must_load:
            if config.dry_run:
                logger.warning("DRY_RUN=true. No se escribirá en SAP HANA.")
            else:
                # Validamos columnas ANTES de borrar para evitar pérdida de datos si la estructura de HANA no coincide.
                load_columns = resolve_load_columns(config, logger)
                pyflow_progress(55)
                if config.delete_range_before_load:
                    deleted = delete_ivr_range(config, start_dt, end_dt, logger)
                pyflow_progress(60)
                loaded, failed = merge_ivr_rows(config, all_rows, logger, load_columns)
                pyflow_progress(70)
        need_auto = run_mode in ("cargar_y_autoservicio", "solo_autoservicio", "cargar_y_ambos", "enviar_encuesta", "cargar_hana_y_enviar_encuesta", "todo")
        need_abandono = run_mode in ("cargar_y_abandono", "solo_abandono", "cargar_y_ambos", "todo")
        if need_auto or need_abandono:
            autoservicio_rows, abandono_rows = build_segment_bases(all_rows)
            pyflow_progress(72)
            if config.enrich_clients_from_hana:
                etiquetas = []
                if need_auto:
                    etiquetas.extend([r.get("ETIQUETA_EXTERNA") for r in autoservicio_rows])
                if need_abandono:
                    etiquetas.extend([r.get("ETIQUETA_EXTERNA") for r in abandono_rows])
                client_lookup = query_client_profiles(config, etiquetas, logger)
                pyflow_progress(78)
                if need_auto:
                    autoservicio_rows = enrich_rows(autoservicio_rows, client_lookup)

                    logger.info(
                        "Enviando encuestas Qualtrics a clientes Full Autoservicio..."
                    )

                    enviadas = 0
                    total_clientes = len(autoservicio_rows)

                    for index, cliente in enumerate(autoservicio_rows, start=1):

                        if enviar_encuesta_qualtrics(
                            config,
                            cliente,
                            logger
                        ):
                            enviadas += 1

                            if index < total_clientes:
                                logger.info(
                                    "Esperando 5 segundos antes del siguiente envío..."
                                )
                                time.sleep(5)

                    logger.info(
                        "Encuestas Qualtrics enviadas: %s",
                        enviadas
                    )  


                if need_abandono:
                    abandono_rows = enrich_rows(abandono_rows, client_lookup)
            if need_auto:
                if send_surveys:
                    surveys_sent, surveys_without_email = enviar_encuestas_qualtrics(config, autoservicio_rows, logger)
                if run_mode in ("cargar_y_autoservicio", "solo_autoservicio", "cargar_y_ambos", "todo"):
                    path = write_output(autoservicio_rows, config.output_dir, "GNS_IVR_Full_Autoservicio", config.output_format, logger)
                    if path:
                        output_files.append(path)
            if need_abandono:
                path = write_output(abandono_rows, config.output_dir, "GNS_IVR_Abandono_Real", config.output_format, logger)
                if path:
                    output_files.append(path)
        if failed > 0:
            logger.error("Proceso finalizó con filas fallidas en HANA: %s", failed)
        else:
            logger.info("Proceso finalizado correctamente.")
        pyflow_progress(100)
    except Exception as exc:
        errors.append(str(exc))
        logger.exception("Error general: %s", exc)
        logger.error(traceback.format_exc())
    duration = time.time() - start_time
    logger.info("=" * 80)
    logger.info("RESUMEN FINAL")
    logger.info("Conversaciones leídas desde Genesys: %s", total_conversations)
    logger.info("Filas IVR transformadas: %s", total_ivr_rows)
    logger.info("Registros eliminados HANA: %s", deleted)
    logger.info("Filas cargadas/actualizadas HANA: %s", loaded)
    logger.info("Filas fallidas HANA: %s", failed)
    logger.info("Encuestas Qualtrics enviadas: %s", surveys_sent)
    logger.info("Encuestas sin correo: %s", surveys_without_email)
    logger.info("Archivos generados: %s", len(output_files))
    for path in output_files:
        logger.info("Archivo: %s", path)
    logger.info("Errores: %s", len(errors))
    for err in errors[:20]:
        logger.error("Detalle error: %s", err)
    logger.info("Duración total: %.2f segundos", duration)
    logger.info("=" * 80)
    return 0 if not errors and failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
