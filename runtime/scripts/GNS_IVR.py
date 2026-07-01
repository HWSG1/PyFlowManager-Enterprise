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
import calendar
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from html import escape
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
            "Cargar a SAP HANA",
            "Análisis Autoservicio",
            "Enviar de Encuestas Autoservicio",
            "Análisis Abandono",
            "HANA + Análisis Autoservicio",
            "HANA + Envío de encuestas"
        ],
        "default": "Cargar a SAP HANA"
    },
    "START_DATE": {"type": "date", "label": "Fecha inicio", "required": False},
    "END_DATE": {"type": "date", "label": "Fecha fin", "required": False},
    "DAYS_BACK": {"type": "number", "label": "Dias hacia atras si no se indican fechas", "required": False, "default": "1"},
    "PROCESS_BY_DAY": {"type": "select", "label": "Procesar dia por dia", "required": True, "options": ["true", "false"], "default": "true"},
    "DELETE_RANGE_BEFORE_LOAD": {"type": "select", "label": "Borrar rango antes de cargar IVR", "required": True, "options": ["true", "false"], "default": "true"},
    "OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida para Excel/CSV", "required": False},
    "OUTPUT_FORMAT": {"type": "select", "label": "Formato salida", "required": True, "options": ["xlsx", "csv"], "default": "xlsx"},
    "TOKEN_QUALTRICTS": {"type": "global", "global_key": "TOKEN_QUALTRICTS", "label": "Token Qualtrics", "required": True, "secret": True},
    "POST_AUTOSERVICIO_QUALTRICTS_IVR": {"type": "global", "global_key": "POST_AUTOSERVICIO_QUALTRICTS_IVR", "label": "Endpoint Qualtrics", "required": True},
    "GRAPH_TENANT_ID": {"type": "global", "global_key": "GRAPH_TENANT_ID", "label": "Microsoft Graph Tenant ID", "required": False},
    "GRAPH_CLIENT_ID": {"type": "global", "global_key": "GRAPH_CLIENT_ID", "label": "Microsoft Graph Client ID", "required": False},
    "GRAPH_CLIENT_SECRET": {"type": "global", "global_key": "GRAPH_CLIENT_SECRET", "label": "Microsoft Graph Client Secret", "required": False, "secret": True},
    "GRAPH_SENDER_EMAIL": {"type": "global", "global_key": "GRAPH_SENDER_EMAIL", "label": "Correo remitente Graph", "required": False},
    "SURVEY_REPORT_EMAIL_TO": {"type": "tags", "label": "Destinatarios reporte encuestas", "required": False},
    "SURVEY_REPORT_EMAIL_CC": {"type": "tags", "label": "Copias reporte encuestas", "required": False},
    "SURVEY_REPORT_SUBJECT": {"type": "text", "label": "Asunto reporte encuestas", "required": False, "default": "Reporte de Encuesta de Satisfacción - Autoservicio"}
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


def local_day_start(d: date, tz: ZoneInfo) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=tz)


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


def split_list_value(value: Any) -> List[str]:
    text = "" if value is None else str(value)
    text = text.replace("\r", "\n").replace(",", ";").replace("\n", ";")
    result: List[str] = []
    for item in text.split(";"):
        cleaned = item.strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


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
    qualtrics_delay_seconds: int
    graph_tenant_id: str
    graph_client_id: str
    graph_client_secret: str
    graph_sender_email: str
    survey_report_email_to: List[str]
    survey_report_email_cc: List[str]
    survey_report_subject: str


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
        qualtrics_token=env_str("TOKEN_QUALTRICTS", ""),
        qualtrics_endpoint=env_str("POST_AUTOSERVICIO_QUALTRICTS_IVR", ""),
        qualtrics_delay_seconds=env_int("QUALTRICS_DELAY_SECONDS", 5),
        graph_tenant_id=env_str("GRAPH_TENANT_ID", ""),
        graph_client_id=env_str("GRAPH_CLIENT_ID", ""),
        graph_client_secret=env_str("GRAPH_CLIENT_SECRET", ""),
        graph_sender_email=env_str("GRAPH_SENDER_EMAIL", ""),
        survey_report_email_to=split_list_value(env_str("SURVEY_REPORT_EMAIL_TO", "")),
        survey_report_email_cc=split_list_value(env_str("SURVEY_REPORT_EMAIL_CC", "")),
        survey_report_subject=env_str("SURVEY_REPORT_SUBJECT", "Reporte de Encuesta de Satisfacción - Autoservicio"),
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
        raise ValueError("Para enviar encuestas debes configurar TOKEN_QUALTRICTS y POST_AUTOSERVICIO_QUALTRICTS_IVR.")

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


def build_survey_report_html(total_autoservicio: int, enviadas: int, sin_correo: int, date_mode: str) -> str:
    porcentaje_envio = (enviadas / total_autoservicio * 100) if total_autoservicio else 0
    porcentaje_cobertura = max(0, min(100, porcentaje_envio))
    now = datetime.now(ZoneInfo("America/Tegucigalpa"))

    template = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="es">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Resumen de Encuestas Enviadas</title>
</head>
<body style="margin: 0; padding: 0; width: 100% !important; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; background-color: #f8fafc; font-family: 'NeoSans STD', 'Segoe UI', Arial, sans-serif;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; padding: 40px 10px;">
    <tr>
      <td align="center" valign="top">
        <table width="100%" max-width="650" border="0" cellspacing="0" cellpadding="0" style="max-width: 650px; width: 100%; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #e2e8f0;">
          <tr>
            <td align="left" valign="top" style="background-color: #DA282D; padding: 40px 40px 35px 40px;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td valign="middle">
                    <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #fecaca; display: block; margin-bottom: 6px;">SISTEMA DE MONITOREO DE PROCESOS</span>
                    <h1 style="margin: 0; font-size: 24px; font-weight: 700; line-height: 1.2; color: #ffffff; letter-spacing: -0.5px;">Resumen de Encuestas Enviadas</h1>
                    <p style="margin: 8px 0 0 0; font-size: 13px; color: #fecaca; opacity: 0.95;">Reporte automático generado por PyFlow Manager</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 40px;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="font-size: 14px; line-height: 1.6; color: #334155; padding-bottom: 30px;">
                    <p style="margin: 0 0 10px 0;">Estimado equipo de operaciones,</p>
                    <p style="margin: 0;">Se ha completado con éxito la ejecución programada para el envío de encuestas de satisfacción. A continuación, se presenta el consolidado de las estadísticas de cobertura obtenidas en este ciclo:</p>
                  </td>
                </tr>
                <tr>
                  <td style="padding-bottom: 30px;">
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td width="48%" valign="top" style="background-color: #f1f5f9; border-radius: 6px; padding: 20px; border: 1px solid #e2e8f0; text-align: left;">
                          <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 8px;">Clientes Identificados</span>
                          <span style="font-size: 26px; font-weight: 700; color: #1e293b; display: block;">{{TOTAL_CLIENTES}}</span>
                          <span style="font-size: 11px; color: #94a3b8; display: block; margin-top: 4px;">Población objetivo</span>
                        </td>
                        <td width="4%">&nbsp;</td>
                        <td width="48%" valign="top" style="background-color: #f1f5f9; border-radius: 6px; padding: 20px; border: 1px solid #e2e8f0; text-align: left;">
                          <span style="font-size: 11px; font-weight: 700; color: #DA282D; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 8px;">Encuestas Enviadas</span>
                          <span style="font-size: 26px; font-weight: 700; color: #DA282D; display: block;">{{ENCUESTAS_ENVIADAS}}</span>
                          <span style="font-size: 11px; color: #94a3b8; display: block; margin-top: 4px;">Envíos efectivos</span>
                        </td>
                      </tr>
                      <tr><td colspan="3" height="16"></td></tr>
                      <tr>
                        <td width="48%" valign="top" style="background-color: #f1f5f9; border-radius: 6px; padding: 20px; border: 1px solid #e2e8f0; text-align: left;">
                          <span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 8px;">Sin Correo Válido</span>
                          <span style="font-size: 26px; font-weight: 700; color: #475569; display: block;">{{SIN_CORREO}}</span>
                          <span style="font-size: 11px; color: #94a3b8; display: block; margin-top: 4px;">Registros no procesados</span>
                        </td>
                        <td width="4%">&nbsp;</td>
                        <td width="48%" valign="top" style="background-color: #fdf2f2; border-radius: 6px; padding: 20px; border: 1px solid #fee2e2; text-align: left;">
                          <span style="font-size: 11px; font-weight: 700; color: #b91c1c; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 8px;">Tasa de Cobertura</span>
                          <span style="font-size: 26px; font-weight: 700; color: #b91c1c; display: block;">{{PORCENTAJE_COBERTURA}}%</span>
                          <span style="font-size: 11px; color: #f87171; display: block; margin-top: 4px;">Porcentaje del total</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="background-color: #fafafa; border-radius: 6px; padding: 24px; border: 1px solid #f1f5f9; padding-bottom: 24px; margin-bottom: 30px;">
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td style="font-size: 12px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; padding-bottom: 8px;">Indicador Visual de Cobertura</td>
                        <td align="right" style="font-size: 13px; font-weight: 700; color: #1e293b; padding-bottom: 8px;">{{PORCENTAJE_COBERTURA}}% Completado</td>
                      </tr>
                      <tr>
                        <td colspan="2" style="padding-top: 4px;">
                          <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #e2e8f0; border-radius: 4px; overflow: hidden; height: 8px;">
                            <tr>
                              <td width="{{PORCENTAJE_COBERTURA}}%" style="background-color: #DA282D; height: 8px; border-radius: 4px 0 0 4px;"></td>
                              <td style="background-color: #e2e8f0; height: 8px;"></td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr><td height="25"></td></tr>
                <tr>
                  <td>
                    <table width="100%" border="0" cellspacing="0" cellpadding="0" style="border-left: 3px solid #DA282D; padding-left: 16px;">
                      <tr>
                        <td style="font-size: 13px; line-height: 1.5; color: #64748b; font-style: italic;">
                          <strong>Nota de exclusión técnica:</strong> Los registros identificados sin una cuenta de correo electrónico válida asociada han sido automáticamente excluidos del envío a través de este canal para salvaguardar la reputación del dominio emisor y evitar rebotes innecesarios.
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr><td height="35"></td></tr>
                <tr>
                  <td style="border-top: 1px solid #f1f5f9; padding-top: 25px; font-size: 12px; color: #64748b; line-height: 1.6;">
                    <table width="100%" border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td valign="top" style="color: #64748b;">
                          Fecha de ejecución: <strong>{{FECHA_EJECUCION}}</strong><br />
                          Hora de ejecución: <strong>{{HORA_EJECUCION}}</strong>
                        </td>
                        <td align="right" valign="top" style="color: #475569;">
                          Generado por:<br />
                          <strong style="color: #1e293b;">PyFlow Manager</strong><br />
                          <span style="font-size: 11px; color: #94a3b8;">Automatización de Reportes y Procesos</span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td align="center" style="background-color: #f1f5f9; padding: 20px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; line-height: 1.4;">
              Este es un correo automático generado por el módulo de reportería integrado en PyFlow Manager.<br />
              Por favor, no respondas a este mensaje de manera directa.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return (
        template
        .replace("{{TOTAL_CLIENTES}}", escape(f"{total_autoservicio:,}"))
        .replace("{{ENCUESTAS_ENVIADAS}}", escape(f"{enviadas:,}"))
        .replace("{{SIN_CORREO}}", escape(f"{sin_correo:,}"))
        .replace("{{PORCENTAJE_COBERTURA}}", escape(f"{porcentaje_cobertura:.1f}"))
        .replace("{{FECHA_EJECUCION}}", escape(now.strftime("%d/%m/%Y")))
        .replace("{{HORA_EJECUCION}}", escape(now.strftime("%I:%M %p")))
    )


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


def enviar_reporte_encuestas(config: Config, total_autoservicio: int, enviadas: int, sin_correo: int, date_mode: str, logger: logging.Logger) -> bool:
    recipients = config.survey_report_email_to
    cc = config.survey_report_email_cc

    if not recipients:
        logger.info("Reporte de encuestas no enviado: no hay destinatarios configurados en SURVEY_REPORT_EMAIL_TO.")
        return False
    if not config.graph_sender_email:
        logger.warning("Reporte de encuestas no enviado: configura GRAPH_SENDER_EMAIL.")
        return False

    html = build_survey_report_html(total_autoservicio, enviadas, sin_correo, date_mode)
    payload = {
        "message": {
            "subject": config.survey_report_subject,
            "body": {
                "contentType": "HTML",
                "content": html,
            },
            "toRecipients": [
                {"emailAddress": {"address": email}}
                for email in recipients
            ],
            "ccRecipients": [
                {"emailAddress": {"address": email}}
                for email in cc
            ],
        },
        "saveToSentItems": "true",
    }

    try:
        token = get_graph_access_token(config, logger)
        url = f"https://graph.microsoft.com/v1.0/users/{config.graph_sender_email}/sendMail"
        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        if response.status_code >= 400:
            logger.error("Error enviando reporte Graph %s | %s", response.status_code, response.text[:1000])
        response.raise_for_status()

        logger.info("Reporte de encuestas enviado a: %s", ", ".join(recipients + cc))
        return True
    except Exception as exc:
        logger.error("No se pudo enviar reporte de encuestas: %s", exc)
        return False


def normalize_run_mode(value: str) -> str:
    text = (value or "").strip()
    modes = {
        "Cargar a SAP HANA": "cargar_hana",
        "Analisis Autoservicio": "solo_autoservicio",
        "Análisis Autoservicio": "solo_autoservicio",
        "Enviar de Encuestas Autoservicio": "enviar_encuesta",
        "Analisis Abandono": "solo_abandono",
        "Análisis Abandono": "solo_abandono",
        "HANA + Analisis Autoservicio": "cargar_y_autoservicio",
        "HANA + Análisis Autoservicio": "cargar_y_autoservicio",
        "HANA + Envio de encuestas": "cargar_hana_y_enviar_encuesta",
        "HANA + Envío de encuestas": "cargar_hana_y_enviar_encuesta",
    }
    return modes.get(text, text)


def calculate_interval(args: argparse.Namespace, config: Config) -> Tuple[datetime, datetime, str]:
    tz = ZoneInfo(config.timezone_name)

    if args.start_utc and args.end_utc:
        start_dt = parse_utc_z(args.start_utc)
        end_dt = parse_utc_z(args.end_utc)
        mode = "UTC manual"
    elif args.date:
        d = parse_local_date(args.date)
        start_dt = local_day_start(d, tz)
        end_dt = start_dt + timedelta(days=1)
        mode = f"Dia local {d.isoformat()} 00:00 {config.timezone_name} -> {to_utc_z(start_dt)} Genesys"
    elif args.start_date and args.end_date:
        d1 = parse_local_date(args.start_date)
        d2 = parse_local_date(args.end_date)
        if d2 < d1:
            raise ValueError("END_DATE no puede ser menor que START_DATE.")
        start_dt = local_day_start(d1, tz)
        end_dt = local_day_start(d2, tz) + timedelta(days=1)
        mode = (
            f"Rango local {d1.isoformat()} 00:00 al {d2.isoformat()} 23:59:59 "
            f"{config.timezone_name}; Genesys UTC {to_utc_z(start_dt)} -> {to_utc_z(end_dt)}"
        )
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
    allowed_days = config.max_range_days
    if args.start_date and args.end_date:
        allowed_days = calendar.monthrange(start_dt.year, start_dt.month)[1]

    if duration_days > allowed_days:
        raise ValueError(
            f"Rango no permitido: {duration_days:.2f} dias. Maximo permitido para el mes seleccionado: {allowed_days} dias."
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


def request_with_retry(
    method: str,
    url: str,
    config: Config,
    logger: logging.Logger,
    retry_statuses: Optional[Iterable[int]] = None,
    **kwargs
) -> requests.Response:
    """Ejecuta requests con reintentos controlados.

    - Reintenta 429 y errores 5xx.
    - Permite reintentar códigos específicos como 404 cuando Genesys crea el job
      pero todavía no expone /jobs/{id} o /results.
    """
    retry_status_set = {int(x) for x in (retry_statuses or [])}
    last_error = None
    for attempt in range(1, config.max_api_retries + 1):
        try:
            response = requests.request(method, url, timeout=config.request_timeout, **kwargs)
            should_retry = response.status_code == 429 or response.status_code >= 500 or response.status_code in retry_status_set
            if should_retry and attempt < config.max_api_retries:
                retry_after = response.headers.get("Retry-After")
                wait = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * attempt)
                logger.warning(
                    "HTTP %s | intento %s/%s | esperando %ss | %s",
                    response.status_code,
                    attempt,
                    config.max_api_retries,
                    wait,
                    response.text[:500],
                )
                time.sleep(wait)
                continue
            if response.status_code >= 400:
                logger.error("HTTP %s | %s", response.status_code, response.text[:1000])
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt >= config.max_api_retries:
                break
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
            {
                "type": "and",
                "predicates": [
                    {"dimension": "mediaType", "operator": "matches", "value": "voice"},
                    {"dimension": "segmentType", "operator": "matches", "value": "ivr"},
                ],
            }
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


def get_details_job_status(config: Config, token: str, job_id: str, logger: logging.Logger) -> Dict[str, Any]:
    """Consulta el estado del job antes de pedir /results.

    En Genesys, si se consulta /results antes de que el job termine, puede devolver
    404 Not Found. Por eso primero esperamos el estado final correcto.
    """
    url = f"{config.genesys_api_base}/api/v2/analytics/conversations/details/jobs/{job_id}"
    response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token), retry_statuses={404})
    return response.json()


def _extract_job_state(data: Dict[str, Any]) -> str:
    state = (
        data.get("state")
        or data.get("status")
        or data.get("jobStatus")
        or data.get("completionStatus")
        or ""
    )
    return str(state or "").strip().upper()


def wait_for_details_job(config: Config, token: str, job_id: str, logger: logging.Logger) -> Dict[str, Any]:
    ready_states = {"FULFILLED", "COMPLETED", "COMPLETE", "SUCCESS", "SUCCEEDED"}
    pending_states = {"QUEUED", "PENDING", "RUNNING", "PROCESSING", "INPROGRESS", "IN_PROGRESS"}
    failed_states = {"FAILED", "FAILURE", "CANCELLED", "CANCELED", "EXPIRED", "TIMEOUT", "TIMED_OUT"}

    last_status: Dict[str, Any] = {}
    for attempt in range(1, config.max_poll_attempts + 1):
        last_status = get_details_job_status(config, token, job_id, logger)
        state = _extract_job_state(last_status)

        # Algunos tenants devuelven percentComplete o completionPercentage. Lo dejamos solo como log.
        percent = last_status.get("percentComplete") or last_status.get("completionPercentage") or last_status.get("percent")
        logger.info(
            "Estado job %s | intento %s/%s | estado=%s%s",
            job_id,
            attempt,
            config.max_poll_attempts,
            state or "<sin estado>",
            f" | avance={percent}" if percent is not None else "",
        )

        if state in ready_states:
            return last_status
        if state in failed_states:
            raise RuntimeError(f"Job Genesys {job_id} finalizó en estado {state}. Detalle: {last_status}")

        # Si Genesys no devuelve estado, esperamos igual en vez de consultar /results de inmediato.
        if state and state not in pending_states:
            logger.warning("Estado de job no reconocido: %s | Respuesta: %s", state, str(last_status)[:1000])

        time.sleep(config.poll_seconds)

    raise RuntimeError(
        f"Job Genesys {job_id} no finalizó después de {config.max_poll_attempts} intentos "
        f"cada {config.poll_seconds}s. Último estado: {last_status}"
    )


def get_job_results_page(config: Config, token: str, job_id: str, cursor: str, logger: logging.Logger) -> Dict[str, Any]:
    url = f"{config.genesys_api_base}/api/v2/analytics/conversations/details/jobs/{job_id}/results?pageSize={config.job_page_size}"
    if cursor:
        url += f"&cursor={cursor}"
    response = request_with_retry("GET", url, config, logger, headers=genesys_headers(token), retry_statuses={404})
    return response.json()


def fetch_conversation_details(config: Config, token: str, start_dt: datetime, end_dt: datetime, logger: logging.Logger) -> List[Dict[str, Any]]:
    job_id = create_details_job(config, token, start_dt, end_dt, logger)
    wait_for_details_job(config, token, job_id, logger)

    all_conversations: List[Dict[str, Any]] = []
    cursor = ""
    page_number = 0

    while True:
        data = get_job_results_page(config, token, job_id, cursor, logger)
        conversations = data.get("conversations") or []
        next_cursor = str(data.get("cursor") or "").strip()

        page_number += 1
        if conversations:
            all_conversations.extend(conversations)
            logger.info(
                "Página job %s recibida | conversaciones: %s | acumulado: %s | cursor siguiente: %s",
                page_number,
                len(conversations),
                len(all_conversations),
                "sí" if next_cursor else "no",
            )
        else:
            logger.info("Página job %s sin conversaciones | cursor siguiente: %s", page_number, "sí" if next_cursor else "no")

        if config.max_conversations and len(all_conversations) >= config.max_conversations:
            logger.warning("Se alcanzó MAX_CONVERSATIONS=%s. Se corta extracción.", config.max_conversations)
            return all_conversations[:config.max_conversations]

        if not next_cursor:
            logger.info(
                "Lectura de job completada | páginas: %s | conversaciones acumuladas: %s",
                page_number,
                len(all_conversations),
            )
            break

        cursor = next_cursor
        time.sleep(config.api_sleep_seconds)

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

    attrs = collect_attributes(conversation)
    ivr_attr_names = (
        "SPD_IVR_TrazaOpciones",
        "SPD_IVR",
        "IVR",
        "IVR_OPCIONES",
        "OPCIONES_NAVEGACION",
    )
    for key, value in attrs.items():
        key_upper = str(key or "").upper()
        if value and any(name.upper() in key_upper for name in ivr_attr_names):
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


def transform_conversations(
    conversations: List[Dict[str, Any]],
    config: Config,
    divisions_lookup: Dict[str, str],
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    rows = []
    skipped_no_ivr = 0
    for conv in conversations:
        row = transform_conversation(conv, config, divisions_lookup)
        if row:
            rows.append(row)
        elif config.only_with_ivr:
            skipped_no_ivr += 1

    if logger:
        logger.info(
            "Transformación IVR | conversaciones recibidas: %s | filas generadas: %s | descartadas sin evidencia IVR: %s",
            len(conversations),
            len(rows),
            skipped_no_ivr,
        )
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
    if "FECHA_INGRESO" not in hana_set:
        raise RuntimeError(
            'La tabla destino no tiene la columna obligatoria FECHA_INGRESO. '
            'No se puede borrar/cargar rangos IVR de forma segura.'
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
                logger.exception("Error en MERGE lote desde fila %s: %s. Se intentará fila por fila para rescatar registros válidos.", start + 1, exc)
                for offset, row_value in enumerate(values, start=1):
                    try:
                        cur.execute(sql, row_value)
                        conn.commit()
                        loaded += 1
                    except Exception as row_exc:
                        conn.rollback()
                        failed += 1
                        row_id = batch[offset - 1].get("ID_TRANSACCION") if offset - 1 < len(batch) else "<sin id>"
                        logger.exception(
                            "Fila fallida en MERGE | posición global=%s | ID_TRANSACCION=%s | error=%s",
                            start + offset,
                            row_id,
                            row_exc,
                        )
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
            cdc.FECHA_ULTIMA_ACTUALIZACION,
        
            CASE
                WHEN cdc.FECHA_ULTIMA_ACTUALIZACION IS NULL THEN '0. No actualizado'
                WHEN TO_DATE(cdc.FECHA_ULTIMA_ACTUALIZACION, 'YYYYMMDD') >= ADD_MONTHS(CURRENT_DATE, -6)  THEN '1. 0–6 meses'
                WHEN TO_DATE(cdc.FECHA_ULTIMA_ACTUALIZACION, 'YYYYMMDD') >= ADD_MONTHS(CURRENT_DATE, -12) THEN '2. 6–12 meses'
                WHEN TO_DATE(cdc.FECHA_ULTIMA_ACTUALIZACION, 'YYYYMMDD') >= ADD_MONTHS(CURRENT_DATE, -36) THEN '3. 1–3 años'
                WHEN TO_DATE(cdc.FECHA_ULTIMA_ACTUALIZACION, 'YYYYMMDD') >= ADD_MONTHS(CURRENT_DATE, -60) THEN '4. 3–5 años'
                ELSE '5. >5 años'
            END AS RANGO_FECHA_ACTUALIZACION,
        
            CASE 
                WHEN LEFT(cdc.FECHA_NACIMIENTO, 4) BETWEEN '2013' AND '2025' THEN 'Alpha (2013 - 2025)'
                WHEN LEFT(cdc.FECHA_NACIMIENTO, 4) BETWEEN '1997' AND '2012' THEN 'Z (1997 - 2012)'
                WHEN LEFT(cdc.FECHA_NACIMIENTO, 4) BETWEEN '1981' AND '1996' THEN 'Millennials (1981 - 1996)'
                WHEN LEFT(cdc.FECHA_NACIMIENTO, 4) BETWEEN '1965' AND '1980' THEN 'X (1965 - 1980)'
                WHEN LEFT(cdc.FECHA_NACIMIENTO, 4) BETWEEN '1946' AND '1964' THEN 'Baby Boomers (1946 - 1964)'
                WHEN LEFT(cdc.FECHA_NACIMIENTO, 4) < '1946' THEN 'Silent (<1946)'
                ELSE 'Desconocida'
            END AS GENERACION_CLIENTE
        
        FROM DS_STG.CRM_DIM_CLIENTES cdc
        WHERE (
            TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_1)) IN ({placeholders})
            OR TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_2)) IN ({placeholders})
        )
    '''
    cols = ["ETIQUETA_EXTERNA", "TEL_CELULAR", "TEL_PRINCIPAL", "DEPARTAMENTO", "ESTADO_CIVIL", "PAIS", "NOMBRE_LEGAL", "PRIMER_NOMBRE", "PRIMER_APELLIDO", "E_MAIL", "SEGMENTO_BANCA", "GENERO", "TIPO_SECTOR_ECONOMICO", "NIVEL_EDUCATIVO", "FECHA_ULTIMA_ACTUALIZACION","RANGO_FECHA_ACTUALIZACION","GENERACION_CLIENTE"]
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


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        text = str(value).strip()
        if text == "":
            return default
        return int(float(text))
    except Exception:
        return default


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
        max_auto = max(safe_int(x.get("AUTOSERVICIO")) for x in items)
        max_paso_agente = max(safe_int(x.get("PASO_AGENTE_FLAG")) for x in items)
        max_blacklist = max(safe_int(x.get("BLACKLIST")) for x in items)
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
        run_mode_raw = env_str("RUN_MODE", "Cargar a SAP HANA")
        run_mode = normalize_run_mode(run_mode_raw)
        valid_modes = {
            "cargar_hana",
            "solo_autoservicio",
            "solo_abandono",
            "enviar_encuesta",
            "cargar_y_autoservicio",
            "cargar_hana_y_enviar_encuesta",
        }
        if run_mode not in valid_modes:
            raise ValueError(f"RUN_MODE inválido: {run_mode}. Valores válidos: {sorted(valid_modes)}")
        send_surveys = run_mode in ("enviar_encuesta", "cargar_hana_y_enviar_encuesta")
        write_autoservicio = run_mode in ("solo_autoservicio", "enviar_encuesta", "cargar_y_autoservicio", "cargar_hana_y_enviar_encuesta")
        write_abandono = run_mode == "solo_abandono"
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
            "ONLY_WITH_IVR", "ENRICH_CLIENTS_FROM_HANA", "TOKEN_QUALTRICTS", "POST_AUTOSERVICIO_QUALTRICTS_IVR"
        ])
        logger.info("Modo fecha: %s", date_mode)
        logger.info("Inicio local calculado: %s", start_dt.astimezone(ZoneInfo(config.timezone_name)).strftime("%Y-%m-%d %H:%M:%S %Z"))
        logger.info("Fin local calculado: %s", end_dt.astimezone(ZoneInfo(config.timezone_name)).strftime("%Y-%m-%d %H:%M:%S %Z"))
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
            rows = transform_conversations(conversations, config, divisions_lookup, logger)
            all_rows.extend(rows)
            logger.info("Ventana procesada | conversaciones: %s | filas IVR: %s | acumulado filas IVR: %s", len(conversations), len(rows), len(all_rows))
            pyflow_progress(15 + int((idx / max(len(windows), 1)) * 35))
            time.sleep(config.api_sleep_seconds)
        total_ivr_rows = len(all_rows)
        pyflow_progress(50)
        logger.info("=" * 80)
        logger.info("Extracción finalizada | conversaciones: %s | filas IVR: %s", total_conversations, total_ivr_rows)
        must_load = run_mode in ("cargar_hana", "cargar_y_autoservicio", "cargar_hana_y_enviar_encuesta")
        if must_load:
            if config.dry_run:
                logger.warning("DRY_RUN=true. No se escribirá en SAP HANA.")
            else:
                # Validamos columnas ANTES de borrar para evitar pérdida de datos si la estructura de HANA no coincide.
                load_columns, hana_meta = resolve_load_columns(config, logger)
                pyflow_progress(55)

                # Protección: si Genesys no devolvió filas, no borramos rangos existentes por accidente.
                # Si de verdad necesitas limpiar un rango vacío, configura ALLOW_EMPTY_RANGE_DELETE=true.
                allow_empty_delete = env_bool("ALLOW_EMPTY_RANGE_DELETE", False)
                if config.delete_range_before_load and not all_rows and not allow_empty_delete:
                    raise RuntimeError(
                        "Genesys devolvió 0 filas IVR. Se detiene la carga para evitar borrar el rango en HANA "
                        "sin tener datos nuevos para reemplazarlo. Si deseas permitirlo, usa ALLOW_EMPTY_RANGE_DELETE=true."
                    )

                if config.delete_range_before_load:
                    deleted = delete_ivr_range(config, start_dt, end_dt, logger)
                pyflow_progress(60)
                loaded, failed = merge_ivr_rows(config, all_rows, logger, load_columns, hana_meta)
                pyflow_progress(70)

                if failed > 0 and run_mode == "cargar_hana_y_enviar_encuesta":
                    raise RuntimeError(
                        f"No se enviarán encuestas porque fallaron {failed} filas al cargar HANA. "
                        "Corrige la carga antes de ejecutar el envío."
                    )
        need_auto = run_mode in ("solo_autoservicio", "enviar_encuesta", "cargar_y_autoservicio", "cargar_hana_y_enviar_encuesta")
        need_abandono = run_mode == "solo_abandono"
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

                if need_abandono:
                    abandono_rows = enrich_rows(abandono_rows, client_lookup)
            if need_auto:
                if send_surveys:
                    if config.dry_run:
                        logger.warning("DRY_RUN=true. No se enviarán encuestas Qualtrics ni reporte por correo.")
                    elif run_mode == "cargar_hana_y_enviar_encuesta" and failed > 0:
                        raise RuntimeError(f"No se enviarán encuestas porque existen {failed} filas fallidas en HANA.")
                    else:
                        surveys_sent, surveys_without_email = enviar_encuestas_qualtrics(config, autoservicio_rows, logger)
                        enviar_reporte_encuestas(
                            config,
                            total_autoservicio=len(autoservicio_rows),
                            enviadas=surveys_sent,
                            sin_correo=surveys_without_email,
                            date_mode=date_mode,
                            logger=logger,
                        )
                if write_autoservicio:
                    path = write_output(autoservicio_rows, config.output_dir, "GNS_IVR_Full_Autoservicio", config.output_format, logger)
                    if path:
                        output_files.append(path)
            if need_abandono and write_abandono:
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
