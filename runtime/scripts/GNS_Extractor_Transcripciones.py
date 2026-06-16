# =========================================================
# GNS EXTRACTOR DE TRANSCRIPCIONES - Genesys Cloud -> CSV
# =========================================================
#
# Objetivo:
#   Extraer transcripciones de llamadas de Genesys Cloud en texto plano.
#
# Modos:
#   1) solo_transcript:
#      Extrae conversación, comunicación y texto transcrito.
#
#   2) transcript_campania:
#      Además de la transcripción, intenta enriquecer con datos de campaña
#      usando ContactId y ContactListId del participante Dialer.
#
# Ejemplos:
#   py .\GNS_Extractor_Transcripciones_PyFlow.py --start-date 2026-06-01 --end-date 2026-06-03
#   py .\GNS_Extractor_Transcripciones_PyFlow.py --date 2026-06-01
##
# Notas:
#   - No escribe en SAP HANA.
#   - No hace SELECT a HANA.
#   - El enriquecimiento de campaña se hace contra Genesys Outbound Contact Lists.
#   - Requiere fechas obligatorias: DATE o START_DATE/END_DATE.
#   - No limita el rango máximo; usar filtros para controlar volumen.
#   - Permite filtros por campaña, lista de contacto, conversationId, usuario y cola.
#   - Requiere que Speech and Text Analytics tenga transcripción disponible.
# =========================================================

import os
import sys
import csv
import json
import time
import math
import argparse
import logging
import traceback
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False


PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Genesys Region / Domain", "required": True},

    "START_DATE": {"type": "date", "label": "Fecha inicial local", "required": False},
    "END_DATE": {"type": "date", "label": "Fecha final local", "required": False},
    "GENESYS_TIMEZONE": {"type": "text", "label": "Zona horaria Genesys", "required": True, "default": "America/Tegucigalpa"},

    "OUTPUT_MODE": {
        "type": "select",
        "label": "Salida requerida",
        "required": True,
        "options": ["solo_transcript", "transcript_campania"],
        "default": "solo_transcript"
    },
    "CONVERSATION_ID": {"type": "tags", "label": "Conversation ID específico", "required": False},
    "USER_ID": {"type": "tags", "label": "User ID del agente", "required": False},
    "USER_NAME": {"type": "tags", "label": "Nombre/correo del agente", "required": False},
    "QUEUE_ID": {"type": "tags", "label": "Queue ID", "required": False},
    "QUEUE_NAME": {"type": "tags", "label": "Nombre de cola", "required": False},
    "CAMPAIGN_ID": {"type": "tags", "label": "Campaign ID", "required": False},
    "CAMPAIGN_NAME": {"type": "tags", "label": "Nombre de campaña", "required": False},
    "CONTACT_LIST_ID": {"type": "tags", "label": "Contact List ID", "required": False},
    "CONTACT_LIST_NAME": {"type": "tags", "label": "Nombre lista de contacto", "required": False},
    "WRAPUP_CODE_ID": {"type": "tags", "label": "WrapUpCode ID opcional", "required": False},
    "MAX_CONVERSATIONS": {"type": "number", "label": "Máximo conversaciones; vacío = todas", "required": False},
    "OUTPUT_CSV": {"type": "text", "label": "Ruta CSV de salida", "required": False},
    "JSON_OUTPUT_DIR": {"type": "text", "label": "Carpeta JSON opcional", "required": False}
}

LOGGER_NAME = "gns_extractor_transcripciones_pyflow"


class TranscriptNotFound(Exception):
    """La comunicación no tiene transcripción disponible en Genesys."""
    pass


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


def split_filter_values(value: Any) -> List[str]:
    """Acepta valores separados por ;, coma o salto de linea y elimina duplicados."""
    if value is None:
        return []

    raw = str(value).replace("\r", "\n").replace(",", ";").replace("\n", ";")
    result: List[str] = []

    for item in raw.split(";"):
        text = item.strip()
        if text and text not in result:
            result.append(text)

    return result


def join_filter_values(values: List[str]) -> str:
    return ";".join([str(value).strip() for value in values if str(value).strip()])


def filter_contains(value: str, allowed_values: str) -> bool:
    items = split_filter_values(allowed_values)
    if not items:
        return True
    return str(value or "") in items


def normalize_genesys_domain(value: str) -> str:
    value = str(value or "mypurecloud.com").strip()
    value = value.replace("https://", "").replace("http://", "").strip("/")
    if value.startswith("api."):
        value = value[4:]
    if value.startswith("login."):
        value = value[6:]
    if value.startswith("apps."):
        value = value[5:]
    return value


def genesys_api_url_from_region(region: str) -> str:
    return f"https://api.{normalize_genesys_domain(region)}"


def genesys_login_url_from_region(region: str) -> str:
    return f"https://login.{normalize_genesys_domain(region)}/oauth/token"


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


@dataclass
class Config:
    genesys_client_id: str
    genesys_client_secret: str
    genesys_api_url: str
    genesys_login_url: str
    timezone_name: str
    output_mode: str
    conversation_id: str
    user_id: str
    user_name: str
    queue_id: str
    queue_name: str
    campaign_id: str
    campaign_name: str
    contact_list_id: str
    contact_list_name: str
    wrapup_code_id: str
    max_conversations: int
    page_size: int
    request_timeout: int
    max_retries: int
    api_sleep_seconds: float
    job_poll_seconds: int
    job_max_polls: int
    output_csv: str
    save_transcript_json: bool
    json_output_dir: str
    dry_run: bool


def load_config() -> Config:
    load_dotenv()
    region = env_str("GENESYS_REGION", "mypurecloud.com", required=True)
    output_mode = env_str("OUTPUT_MODE", "solo_transcript")
    if output_mode not in ("solo_transcript", "transcript_campania"):
        raise ValueError("OUTPUT_MODE debe ser solo_transcript o transcript_campania")
    return Config(
        genesys_client_id=env_str("GENESYS_CLIENT_ID", required=True),
        genesys_client_secret=env_str("GENESYS_CLIENT_SECRET", required=True),
        genesys_api_url=genesys_api_url_from_region(region),
        genesys_login_url=genesys_login_url_from_region(region),
        timezone_name=env_str("GENESYS_TIMEZONE", "America/Tegucigalpa"),
        output_mode=output_mode,
        conversation_id=env_str("CONVERSATION_ID", ""),
        user_id=env_str("USER_ID", ""),
        user_name=env_str("USER_NAME", ""),
        queue_id=env_str("QUEUE_ID", ""),
        queue_name=env_str("QUEUE_NAME", ""),
        campaign_id=env_str("CAMPAIGN_ID", ""),
        campaign_name=env_str("CAMPAIGN_NAME", ""),
        contact_list_id=env_str("CONTACT_LIST_ID", ""),
        contact_list_name=env_str("CONTACT_LIST_NAME", ""),
        wrapup_code_id=env_str("WRAPUP_CODE_ID", ""),
        max_conversations=env_int("MAX_CONVERSATIONS", 0),
        page_size=env_int("PAGE_SIZE", 500),
        request_timeout=env_int("REQUEST_TIMEOUT", 120),
        max_retries=env_int("MAX_RETRIES", 5),
        api_sleep_seconds=env_float("API_SLEEP_SECONDS", 1.0),
        job_poll_seconds=env_int("JOB_POLL_SECONDS", 5),
        job_max_polls=env_int("JOB_MAX_POLLS", 120),
        output_csv=env_str("OUTPUT_CSV", ""),
        save_transcript_json=env_bool("SAVE_TRANSCRIPT_JSON", False),
        json_output_dir=env_str("JSON_OUTPUT_DIR", ""),
        dry_run=env_bool("DRY_RUN", False),
    )


def log_params(logger: logging.Logger, names: List[str]) -> None:
    secret_words = ("SECRET", "PASSWORD", "TOKEN", "KEY")
    logger.info("Parámetros recibidos:")
    for name in names:
        value = env_str(name, "")
        if any(w in name.upper() for w in secret_words) and value:
            value = "********"
        logger.info("- %s: %s", name, value if value else "<vacío>")


def parse_local_date(value: str) -> date:
    value = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Fecha inválida: {value!r}. Use YYYY-MM-DD o DD/MM/YYYY.")


def to_utc_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")




def parse_dates(args: argparse.Namespace, tz_name: str) -> Tuple[str, str, str]:
    """
    Fechas obligatorias para evitar ejecuciones accidentales sin rango.

    Acepta:
    - DATE: extrae un solo día.
    - START_DATE + END_DATE: rango local, END_DATE inclusivo.

    No permite ejecución automática por DAYS_BACK.
    No limita el rango máximo; el control de volumen debe hacerse con filtros
    como lista de contacto, campaña, cola, usuario, wrapup o MAX_CONVERSATIONS.
    """
    tz = ZoneInfo(tz_name)

    if args.date:
        d = parse_local_date(args.date)
        start_local_dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)
        end_local_dt = start_local_dt + timedelta(days=1)
        return to_utc_z(start_local_dt), to_utc_z(end_local_dt), f"Día local {d.isoformat()}"

    if args.start_date or args.end_date:
        if not (args.start_date and args.end_date):
            raise ValueError("Debe informar START_DATE y END_DATE juntos.")
        d1 = parse_local_date(args.start_date)
        d2 = parse_local_date(args.end_date)
        if d2 < d1:
            raise ValueError("La fecha final no puede ser menor que la fecha inicial.")

        # END_DATE es inclusiva en pantalla; para API usamos exclusivo +1 día.
        start_local_dt = datetime(d1.year, d1.month, d1.day, 0, 0, 0, tzinfo=tz)
        end_local_dt = datetime(d2.year, d2.month, d2.day, 0, 0, 0, tzinfo=tz) + timedelta(days=1)
        return to_utc_z(start_local_dt), to_utc_z(end_local_dt), f"Rango local {d1.isoformat()} al {d2.isoformat()}"

    raise ValueError(
        "Fechas obligatorias: indique DATE o START_DATE + END_DATE. "
        "No se permite ejecutar sin rango de fechas para evitar extracciones masivas."
    )

def request_with_retry(method: str, url: str, config: Config, logger: logging.Logger, **kwargs) -> requests.Response:
    """Request HTTP con reintentos.

    Para errores no recuperables, como 404 al pedir un transcript que no existe,
    se puede pasar no_retry_statuses={404} para fallar rápido sin esperar 5 reintentos.
    """
    no_retry_statuses = set(kwargs.pop("no_retry_statuses", set()) or set())
    last_error = None

    for attempt in range(1, config.max_retries + 1):
        try:
            response = requests.request(method, url, timeout=config.request_timeout, **kwargs)

            if response.status_code in no_retry_statuses:
                response.raise_for_status()

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * attempt)
                logger.warning("HTTP 429 | intento %s/%s | esperando %ss", attempt, config.max_retries, wait)
                time.sleep(wait)
                continue

            if response.status_code >= 500:
                wait = min(60, 5 * attempt)
                logger.warning("HTTP %s | intento %s/%s | esperando %ss", response.status_code, attempt, config.max_retries, wait)
                time.sleep(wait)
                continue

            if response.status_code >= 400:
                logger.error("Error HTTP %s | %s", response.status_code, response.text[:1000])

            response.raise_for_status()
            return response

        except Exception as exc:
            last_error = exc
            if attempt >= config.max_retries:
                break
            wait = min(60, 5 * attempt)
            logger.warning("Error request | intento %s/%s | %s | esperando %ss", attempt, config.max_retries, exc, wait)
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



def normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def find_first_by_name(items: List[Dict[str, Any]], wanted: str, name_keys: Tuple[str, ...] = ("name",)) -> Optional[Dict[str, Any]]:
    wanted_n = normalize_text(wanted)
    if not wanted_n:
        return None
    exact = []
    partial = []
    for item in items:
        for key in name_keys:
            name = normalize_text(str(item.get(key) or ""))
            if not name:
                continue
            if name == wanted_n:
                exact.append(item)
            elif wanted_n in name:
                partial.append(item)
    return exact[0] if exact else (partial[0] if partial else None)


def paged_get_entities(config: Config, token: str, logger: logging.Logger, path: str, page_size: int = 100, extra_query: str = "") -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    page = 1
    while True:
        sep = "&" if "?" in path else "?"
        url = f"{config.genesys_api_url}{path}{sep}pageSize={page_size}&pageNumber={page}"
        if extra_query:
            url += "&" + extra_query.lstrip("&")
        response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token))
        data = response.json() if response.text else {}
        entities = data.get("entities") or []
        items.extend(entities)
        page_count = data.get("pageCount") or data.get("page_count") or page
        if not entities or page >= int(page_count):
            break
        page += 1
        time.sleep(config.api_sleep_seconds)
    return items


def resolve_queue_id(config: Config, token: str, logger: logging.Logger) -> str:
    if config.queue_id:
        return join_filter_values(split_filter_values(config.queue_id))
    if not config.queue_name:
        return ""

    names = split_filter_values(config.queue_name)
    logger.info("Resolviendo Queue por nombre: %s", ", ".join(names))
    queues = paged_get_entities(config, token, logger, "/api/v2/routing/queues")
    resolved: List[str] = []

    for name in names:
        found = find_first_by_name(queues, name)
        if not found:
            raise ValueError(f"No se encontró cola con nombre: {name}")
        logger.info("Queue resuelta: %s -> %s", found.get("name"), found.get("id"))
        resolved.append(str(found.get("id") or ""))

    return join_filter_values(resolved)


def resolve_user_id(config: Config, token: str, logger: logging.Logger) -> str:
    if config.user_id:
        return join_filter_values(split_filter_values(config.user_id))
    if not config.user_name:
        return ""

    resolved: List[str] = []

    for name in split_filter_values(config.user_name):
        logger.info("Resolviendo usuario por nombre/correo: %s", name)
        # La búsqueda de usuarios soporta q por nombre/correo en Genesys.
        users = paged_get_entities(config, token, logger, "/api/v2/users", extra_query=f"q={requests.utils.quote(name)}")
        found = find_first_by_name(users, name, ("name", "email", "username"))
        if not found and users:
            found = users[0]
        if not found:
            raise ValueError(f"No se encontró usuario con: {name}")
        logger.info("Usuario resuelto: %s -> %s", found.get("name") or found.get("email"), found.get("id"))
        resolved.append(str(found.get("id") or ""))

    return join_filter_values(resolved)


def resolve_campaign_id(config: Config, token: str, logger: logging.Logger) -> str:
    if config.campaign_id:
        return join_filter_values(split_filter_values(config.campaign_id))
    if not config.campaign_name:
        return ""

    names = split_filter_values(config.campaign_name)
    logger.info("Resolviendo campaña por nombre: %s", ", ".join(names))
    campaigns = paged_get_entities(config, token, logger, "/api/v2/outbound/campaigns")
    resolved: List[str] = []

    for name in names:
        found = find_first_by_name(campaigns, name)
        if not found:
            raise ValueError(f"No se encontró campaña con nombre: {name}")
        logger.info("Campaña resuelta: %s -> %s", found.get("name"), found.get("id"))
        resolved.append(str(found.get("id") or ""))

    return join_filter_values(resolved)


def resolve_contact_list_id(config: Config, token: str, logger: logging.Logger) -> str:
    if config.contact_list_id:
        return join_filter_values(split_filter_values(config.contact_list_id))
    if not config.contact_list_name:
        return ""

    names = split_filter_values(config.contact_list_name)
    logger.info("Resolviendo lista de contacto por nombre: %s", ", ".join(names))
    lists = paged_get_entities(config, token, logger, "/api/v2/outbound/contactlists")
    resolved: List[str] = []

    for name in names:
        found = find_first_by_name(lists, name)
        if not found:
            raise ValueError(f"No se encontró lista de contacto con nombre: {name}")
        logger.info("Lista de contacto resuelta: %s -> %s", found.get("name"), found.get("id"))
        resolved.append(str(found.get("id") or ""))

    return join_filter_values(resolved)


def apply_resolved_filters(config: Config, token: str, logger: logging.Logger) -> Config:
    """Resuelve filtros por nombre a sus IDs y los coloca en el mismo config."""
    config.queue_id = resolve_queue_id(config, token, logger)
    config.user_id = resolve_user_id(config, token, logger)
    config.campaign_id = resolve_campaign_id(config, token, logger)
    config.contact_list_id = resolve_contact_list_id(config, token, logger)
    return config


def validate_filter_safety(config: Config, logger: logging.Logger) -> None:
    filters = {
        "CONVERSATION_ID": config.conversation_id,
        "USER_ID/USER_NAME": config.user_id or config.user_name,
        "QUEUE_ID/QUEUE_NAME": config.queue_id or config.queue_name,
        "CAMPAIGN_ID/CAMPAIGN_NAME": config.campaign_id or config.campaign_name,
        "CONTACT_LIST_ID/CONTACT_LIST_NAME": config.contact_list_id or config.contact_list_name,
        "WRAPUP_CODE_ID": config.wrapup_code_id,
        "MAX_CONVERSATIONS": str(config.max_conversations) if config.max_conversations else "",
    }
    active = [k for k, v in filters.items() if str(v or "").strip()]
    if active:
        logger.info("Filtros activos: %s", ", ".join(active))
    else:
        logger.warning("No hay filtros adicionales aparte del rango de fechas. Se respetará el rango máximo de un mes.")


def build_predicate(dimension: str, value: str, operator: str = "matches") -> Dict[str, str]:
    pred = {"dimension": dimension, "value": value}
    if operator:
        pred["operator"] = operator
    return pred


def build_dimension_filter(dimension: str, values: str, operator: str = "matches") -> Optional[Dict[str, Any]]:
    items = split_filter_values(values)
    if not items:
        return None

    return {
        "type": "or" if len(items) > 1 else "and",
        "predicates": [build_predicate(dimension, item, operator) for item in items],
    }


def build_details_job_body(start_utc: str, end_utc: str, config: Config) -> Dict[str, Any]:
    """Construye el job de Analytics Details con filtros seguros.

    Nota: algunas dimensiones dependen de cómo Genesys registra los segmentos.
    Además del filtro en el job, se hace una validación posterior por atributos
    para campaña/lista cuando esos datos vienen en participantes Dialer.
    """
    segment_filters: List[Dict[str, Any]] = [
        {
            "type": "and",
            "predicates": [build_predicate("mediaType", "voice", "matches")],
        }
    ]

    for dimension, values in (
        ("wrapUpCode", config.wrapup_code_id),
        ("queueId", config.queue_id),
        ("userId", config.user_id),
        ("outboundCampaignId", config.campaign_id),
        ("outboundContactListId", config.contact_list_id),
    ):
        dimension_filter = build_dimension_filter(dimension, values)
        if dimension_filter:
            segment_filters.append(dimension_filter)

    return {
        "order": "asc",
        "orderBy": "conversationStart",
        "interval": f"{start_utc}/{end_utc}",
        "segmentFilters": segment_filters,
    }


def conversation_matches_post_filters(conversation: Dict[str, Any], config: Config) -> bool:
    """Filtro posterior para datos que pueden venir como atributos Dialer."""
    if config.conversation_id:
        cid = conversation.get("conversationId") or conversation.get("id")
        if not filter_contains(str(cid or ""), config.conversation_id):
            return False

    dialer = extract_dialer_attributes(conversation)
    if config.campaign_id and not filter_contains(dialer.get("CampaignId", ""), config.campaign_id):
        return False
    if config.contact_list_id and not filter_contains(dialer.get("ContactListId", ""), config.contact_list_id):
        return False

    return True


def create_conversation_details_job(config: Config, token: str, start_utc: str, end_utc: str, logger: logging.Logger) -> str:
    url = f"{config.genesys_api_url}/api/v2/analytics/conversations/details/jobs"
    body = build_details_job_body(start_utc, end_utc, config)
    logger.info("Creando job de conversaciones detalle...")
    response = request_with_retry("POST", url, config, logger, headers=genesys_headers(token), json=body)
    data = response.json()
    job_id = data.get("jobId") or data.get("id") or data.get("job", {}).get("id")
    if not job_id:
        raise RuntimeError(f"No se recibió jobId. Respuesta: {data}")
    logger.info("Job conversaciones creado: %s", job_id)
    return job_id


def wait_details_job(config: Config, token: str, job_id: str, logger: logging.Logger) -> None:
    url = f"{config.genesys_api_url}/api/v2/analytics/conversations/details/jobs/{job_id}"
    done_status = {"FULFILLED", "Succeeded", "Complete", "Completed", "SUCCESS", "COMPLETED"}
    fail_status = {"FAILED", "Failed", "Canceled", "Cancelled", "CANCELED", "CANCELLED"}
    for attempt in range(1, config.job_max_polls + 1):
        response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token))
        data = response.json()
        status = data.get("state") or data.get("status") or data.get("job", {}).get("status")
        if status in done_status:
            logger.info("Job conversaciones finalizado: %s", status)
            return
        if status in fail_status:
            raise RuntimeError(f"Job conversaciones terminó con estado {status}. Respuesta: {data}")
        logger.info("Job conversaciones estado %s | intento %s/%s", status, attempt, config.job_max_polls)
        time.sleep(config.job_poll_seconds)
    raise TimeoutError(f"Job conversaciones {job_id} no finalizó.")


def fetch_details_job_results(config: Config, token: str, job_id: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    conversations: List[Dict[str, Any]] = []
    cursor = ""
    while True:
        url = f"{config.genesys_api_url}/api/v2/analytics/conversations/details/jobs/{job_id}/results?pageSize={config.page_size}"
        if cursor:
            url += f"&cursor={cursor}"
        response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token))
        data = response.json()
        items = data.get("conversations") or data.get("entities") or []
        conversations.extend(items)
        logger.info("Conversaciones recuperadas página: %s | acumulado: %s", len(items), len(conversations))
        if config.max_conversations and len(conversations) >= config.max_conversations:
            return conversations[: config.max_conversations]
        cursor = data.get("cursor") or data.get("nextCursor") or ""
        if not cursor or not items:
            break
        time.sleep(config.api_sleep_seconds)
    return conversations



def fetch_conversation_details_by_id(config: Config, token: str, conversation_id: str, logger: logging.Logger) -> Dict[str, Any]:
    """Obtiene el detalle de una conversación específica."""
    url = f"{config.genesys_api_url}/api/v2/analytics/conversations/{conversation_id}/details"
    logger.info("Consultando conversación específica: %s", conversation_id)
    response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token))
    data = response.json() if response.text else {}
    return data

def extract_dialer_attributes(conversation: Dict[str, Any]) -> Dict[str, str]:
    result = {"ContactId": "", "ContactListId": "", "CampaignId": ""}
    for participant in conversation.get("participants") or []:
        attrs = participant.get("attributes") or {}
        ptype = str(participant.get("participantType") or "")
        if ptype.lower() == "dialer" or attrs.get("dialerContactId") or attrs.get("dialerContactListId"):
            result["ContactId"] = str(attrs.get("dialerContactId") or result["ContactId"] or "")
            result["ContactListId"] = str(attrs.get("dialerContactListId") or result["ContactListId"] or "")
            result["CampaignId"] = str(attrs.get("dialerCampaignId") or result["CampaignId"] or "")
    return result


def extract_communication_ids(conversation: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    for participant in conversation.get("participants") or []:
        for session in participant.get("sessions") or []:
            media_type = str(session.get("mediaType") or "").lower()
            if media_type and media_type != "voice":
                continue
            # En Genesys, el endpoint transcripturl normalmente usa sessionId.
            # Evitamos peerId porque suele generar 404 y retrasa la ejecución.
            value = session.get("sessionId") or session.get("communicationId")
            if value and value not in ids:
                ids.append(str(value))
    return ids


def get_transcript_signed_url(config: Config, token: str, conversation_id: str, communication_id: str, logger: logging.Logger) -> str:
    url = f"{config.genesys_api_url}/api/v2/speechandtextanalytics/conversations/{conversation_id}/communications/{communication_id}/transcripturl"

    try:
        response = request_with_retry(
            "GET",
            url,
            config,
            logger,
            headers=genesys_headers(token),
            no_retry_statuses={404},
        )
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status == 404:
            raise TranscriptNotFound(f"Transcript no disponible para communicationId={communication_id}") from exc
        raise

    data = response.json() if response.text else {}
    signed_url = data.get("url") or data.get("transcriptUrl") or data.get("downloadUrl")
    if not signed_url:
        raise RuntimeError(f"No se recibió URL de transcript. Respuesta: {data}")
    return signed_url


def download_transcript_json(config: Config, signed_url: str, logger: logging.Logger) -> Any:
    # La URL firmada normalmente no requiere Authorization.
    response = request_with_retry("GET", signed_url, config, logger)
    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


def transcript_to_text(transcript_json: Any) -> Tuple[str, int, str, str]:
    segments: List[str] = []
    phrases_count = 0
    first_ts = ""
    last_ts = ""

    def walk(obj: Any):
        nonlocal phrases_count, first_ts, last_ts
        if isinstance(obj, dict):
            text = obj.get("text") or obj.get("transcript") or obj.get("phrase") or obj.get("utterance")
            if text and isinstance(text, str):
                speaker = obj.get("speaker") or obj.get("participantPurpose") or obj.get("channel") or ""
                start = obj.get("startTime") or obj.get("start") or obj.get("startOffsetMs") or obj.get("offset") or ""
                if start and not first_ts:
                    first_ts = str(start)
                if start:
                    last_ts = str(start)
                prefix = f"{speaker}: " if speaker else ""
                segments.append(prefix + " ".join(text.split()))
                phrases_count += 1
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(transcript_json)
    full_text = "\n".join([s for s in segments if s.strip()])
    return full_text, phrases_count, first_ts, last_ts


def fetch_contact_from_genesys(config: Config, token: str, contact_list_id: str, contact_id: str, logger: logging.Logger) -> Dict[str, Any]:
    if not contact_list_id or not contact_id:
        return {}
    url = f"{config.genesys_api_url}/api/v2/outbound/contactlists/{contact_list_id}/contacts/{contact_id}"
    response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token))
    data = response.json() if response.text else {}
    return data


def flatten_contact_data(contact: Dict[str, Any]) -> Dict[str, Any]:
    if not contact:
        return {}
    out: Dict[str, Any] = {}
    out["contact_callable"] = contact.get("callable")
    out["contact_phone_number_status"] = json.dumps(contact.get("phoneNumberStatus") or {}, ensure_ascii=False)
    data = contact.get("data") or {}
    if isinstance(data, dict):
        for key, value in data.items():
            safe_key = "camp_" + "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(key))[:80]
            out[safe_key] = value
    return out


def default_output_csv() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(os.getcwd(), f"GNS_Transcripciones_{ts}.csv")


def write_csv(rows: List[Dict[str, Any]], output_csv: str, logger: logging.Logger) -> None:
    if not output_csv:
        output_csv = default_output_csv()
    if os.path.isdir(output_csv) or output_csv.endswith("/") or output_csv.endswith("\\"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = os.path.join(output_csv, f"GNS_Transcripciones_{ts}.csv")
    out_dir = os.path.dirname(output_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    all_cols: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in all_cols:
                all_cols.append(key)
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_cols)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("CSV generado: %s", output_csv)


def save_json_if_needed(config: Config, conversation_id: str, communication_id: str, data: Any) -> None:
    if not config.save_transcript_json:
        return
    out_dir = config.json_output_dir or os.path.join(os.getcwd(), "transcripts_json")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{conversation_id}_{communication_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extractor de transcripciones Genesys Cloud")
    parser.add_argument("--date", default=env_str("DATE", ""), help="Fecha local específica. Ejemplo: 2026-06-01")
    parser.add_argument("--start-date", default=env_str("START_DATE", ""), help="Fecha inicial local inclusiva")
    parser.add_argument("--end-date", default=env_str("END_DATE", ""), help="Fecha final local inclusiva")
    parser.add_argument("--dry-run", action="store_true", help="No genera CSV")
    args = parser.parse_args()

    if env_bool("DRY_RUN", False):
        args.dry_run = True

    logger = setup_logger()
    start_time = time.time()
    errors: List[str] = []
    rows: List[Dict[str, Any]] = []
    transcript_not_found_count = 0

    try:
        config = load_config()
        if args.dry_run:
            config.dry_run = True
        start_utc, end_utc, date_mode = parse_dates(args, config.timezone_name)

        logger.info("=" * 80)
        logger.info("INICIO EXTRACTOR DE TRANSCRIPCIONES")
        log_params(logger, [
            "GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION", "START_DATE", "END_DATE",
            "OUTPUT_MODE", "CONVERSATION_ID", "USER_ID", "USER_NAME",
            "QUEUE_ID", "QUEUE_NAME", "CAMPAIGN_ID", "CAMPAIGN_NAME", "CONTACT_LIST_ID", "CONTACT_LIST_NAME",
            "WRAPUP_CODE_ID", "MAX_CONVERSATIONS", "OUTPUT_CSV"
        ])
        logger.info("Modo fecha: %s", date_mode)
        logger.info("Intervalo Genesys: %s/%s", start_utc, end_utc)
        logger.info("Modo salida: %s", config.output_mode)
        logger.info("=" * 80)

        token = get_access_token(config, logger)
        config = apply_resolved_filters(config, token, logger)
        validate_filter_safety(config, logger)

        conversation_ids = split_filter_values(config.conversation_id)
        if conversation_ids:
            conversations = [
                fetch_conversation_details_by_id(config, token, conversation_id, logger)
                for conversation_id in conversation_ids
            ]
        else:
            job_id = create_conversation_details_job(config, token, start_utc, end_utc, logger)
            wait_details_job(config, token, job_id, logger)
            conversations = fetch_details_job_results(config, token, job_id, logger)

        conversations = [c for c in conversations if conversation_matches_post_filters(c, config)]
        logger.info("Total conversaciones para procesar después de filtros: %s", len(conversations))

        for idx, conv in enumerate(conversations, start=1):
            conversation_id = conv.get("conversationId") or conv.get("id")
            if not conversation_id:
                continue
            dialer_attrs = extract_dialer_attributes(conv)
            communication_ids = extract_communication_ids(conv)
            if not communication_ids:
                logger.warning("Conversación sin communication/sessionId de voz: %s", conversation_id)
                continue

            logger.info("Procesando conversación %s/%s | %s | comunicaciones: %s", idx, len(conversations), conversation_id, len(communication_ids))

            contact_flat: Dict[str, Any] = {}
            if config.output_mode == "transcript_campania":
                try:
                    contact_list_for_lookup = dialer_attrs.get("ContactListId", "") or (split_filter_values(config.contact_list_id)[:1] or [""])[0]
                    contact = fetch_contact_from_genesys(config, token, contact_list_for_lookup, dialer_attrs.get("ContactId", ""), logger)
                    contact_flat = flatten_contact_data(contact)
                except Exception as exc:
                    logger.warning("No se pudo enriquecer contacto/campaña para %s: %s", conversation_id, exc)

            for communication_id in communication_ids:
                try:
                    signed_url = get_transcript_signed_url(config, token, conversation_id, communication_id, logger)
                    transcript_json = download_transcript_json(config, signed_url, logger)
                    save_json_if_needed(config, conversation_id, communication_id, transcript_json)
                    text, phrases_count, first_ts, last_ts = transcript_to_text(transcript_json)
                    row = {
                        "conversationId": conversation_id,
                        "communicationId": communication_id,
                        "conversationStart": conv.get("conversationStart", ""),
                        "conversationEnd": conv.get("conversationEnd", ""),
                        "originatingDirection": conv.get("originatingDirection", ""),
                        "ContactId": dialer_attrs.get("ContactId", ""),
                        "ContactListId": dialer_attrs.get("ContactListId", ""),
                        "CampaignId": dialer_attrs.get("CampaignId", ""),
                        "phrases_count": phrases_count,
                        "transcript_first_marker": first_ts,
                        "transcript_last_marker": last_ts,
                        "text": text,
                        "fecha_carga": datetime.now(ZoneInfo(config.timezone_name)).strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    row.update(contact_flat)
                    rows.append(row)
                    logger.info("Transcripción OK | conversación: %s | chars: %s", conversation_id, len(text or ""))
                    time.sleep(config.api_sleep_seconds)
                except TranscriptNotFound as exc:
                    transcript_not_found_count += 1
                    logger.info("Transcript omitido | conversación: %s | communicationId: %s | motivo: %s", conversation_id, communication_id, exc)
                    continue
                except Exception as exc:
                    msg = f"Error transcript conversationId={conversation_id} communicationId={communication_id}: {exc}"
                    errors.append(msg)
                    logger.warning(msg)

        logger.info("Filas finales generadas: %s", len(rows))
        if config.dry_run:
            logger.warning("DRY_RUN=true. No se generará CSV.")
        else:
            write_csv(rows, config.output_csv, logger)

    except Exception as exc:
        errors.append(str(exc))
        logger.exception("El proceso terminó con error general: %s", exc)
        logger.error(traceback.format_exc())

    duration = time.time() - start_time
    logger.info("=" * 80)
    logger.info("RESUMEN FINAL")
    logger.info("Filas transcripción: %s", len(rows))
    logger.info("Transcripts no disponibles omitidos: %s", transcript_not_found_count)
    logger.info("Errores: %s", len(errors))
    for err in errors[:20]:
        logger.error("Detalle error: %s", err)
    logger.info("Duración total: %.2f segundos", duration)
    logger.info("=" * 80)

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
