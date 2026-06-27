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
#   1. Data para análisis
#   2. Resumen tipo tabla dinámica con Conversación media
#   3. Conclusiones AOL acumuladas por día/mes
#   4. Conclusiones NBDA acumuladas por día/mes
#
# Corrección V3:
#   La consulta de Genesys se agrupa solo por wrapUpCode, no por queueId,
#   para evitar duplicar llamadas cuando una conversación pasa por varias colas.
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
import html
import re
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path

import base64
import requests
import pandas as pd

try:
    from hdbcli import dbapi
except Exception:
    dbapi = None


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
    "CUT_OFF_TIME": {
        "type": "select",
        "label": "Hora de corte",
        "required": True,
        "options": ["9:00 a.m.", "12:00 m.", "3:00 p.m.", "6:00 p.m."],
        "default": "9:00 a.m."
    },
    "EMAIL_TO": {
        "type": "tags",
        "label": "Destinatarios del correo",
        "required": False
    },
    "EMAIL_CC": {
        "type": "tags",
        "label": "Copia del correo",
        "required": False
    },
    "EMAIL_SUBJECT": {
        "type": "text",
        "label": "Asunto del correo",
        "required": False,
        "default": "Reporte Acumulado de Conclusiones NBDA y AOL"
    },
    "INCLUDE_SUMMARY_TABLE_IN_EMAIL": {
        "type": "select",
        "label": "Incluir tabla resumen en correo",
        "required": True,
        "options": ["true", "false"],
        "default": "true"
    },
    "INCLUDE_CLIENT_ANALYSIS": {
        "type": "select",
        "label": "Incluir recurrencia, ubicacion y demografia",
        "required": True,
        "options": ["true", "false"],
        "default": "true"
    },
    "HPR_HOST_ESPEJO": {
        "type": "global",
        "global_key": "HPR_HOST_ESPEJO",
        "label": "SAP HANA Host espejo lectura",
        "required": False
    },
    "HPR_PORT": {
        "type": "global",
        "global_key": "HPR_PORT",
        "label": "SAP HANA Port",
        "required": False
    },
    "HPR_USER": {
        "type": "global",
        "global_key": "HPR_USER",
        "label": "SAP HANA User",
        "required": False
    },
    "HPR_PASSWORD": {
        "type": "global",
        "global_key": "HPR_PASSWORD",
        "label": "SAP HANA Password",
        "required": False,
        "secret": True
    },
    "HANA_CLIENT_SCHEMA": {
        "type": "text",
        "label": "Esquema HANA datos cliente",
        "required": False,
        "default": "DS_STG"
    },
    "HANA_CLIENT_TABLE": {
        "type": "text",
        "label": "Tabla HANA datos cliente",
        "required": False,
        "default": "CRM_DIM_CLIENTES"
    },
    "DETAIL_PAGE_SIZE": {
        "type": "number",
        "label": "Tamano pagina detalle Genesys",
        "required": False,
        "default": "100"
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
    }
}

LOGGER_NAME = "gns_conclusiones_nbda_aol_pyflow"

DEFAULT_GRAPH_AUTHORITY_URL = "https://login.microsoftonline.com"
DEFAULT_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
DEFAULT_GRAPH_SAVE_TO_SENT_ITEMS = True
DEFAULT_SEND_EMAIL = True
DEFAULT_DRY_RUN = False

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reporte Acumulado NBDA y AOL</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f5f7; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%;">
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f4f5f7; padding: 20px 0;">
    <tr>
      <td align="center">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 650px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #e5e7eb;">
          <tr>
            <td style="background-color: #DA282D; padding: 35px 40px; text-align: left;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <p style="margin: 0; font-family: 'Neo Sans Std', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 13px; font-weight: bold; color: #ffccd0; text-transform: uppercase; letter-spacing: 2px;">
                      Reporte Acumulado
                    </p>
                    <h1 style="margin: 5px 0 0 0; font-family: 'Neo Sans Std', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; font-size: 26px; font-weight: 800; color: #ffffff; line-height: 1.2;">
                      Conclusiones NBDA y AOL
                    </h1>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 30px 40px 15px 40px;">
              <p style="margin: 0 0 16px 0; font-family: 'Neo Sans Std', 'Segoe UI', Arial, sans-serif; font-size: 15px; line-height: 1.6; color: #374151;">
                Buen dia,
              </p>
              <p style="margin: 0 0 24px 0; font-family: 'Neo Sans Std', 'Segoe UI', Arial, sans-serif; font-size: 15px; line-height: 1.6; color: #4b5563;">
                Comparto el detalle de <strong>Conclusiones NBDA y AOL</strong> correspondiente al periodo del <span style="color: #DA282D; font-weight: bold;">{{FECHA_INICIO}}</span> al <span style="color: #DA282D; font-weight: bold;">{{FECHA_FIN}}</span>, con corte de las {{HORA_CORTE}}.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 20px 40px;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td width="48%" style="background-color: #f9fafb; border-left: 4px solid #DA282D; border-top: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb; border-bottom: 1px solid #e5e7eb; border-radius: 0 6px 6px 0; padding: 16px; text-align: left;">
                    <span style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; text-transform: uppercase; color: #6b7280; font-weight: 600; letter-spacing: 0.5px;">Total Interacciones</span>
                    <div style="font-family: 'Neo Sans Std', 'Segoe UI', Arial, sans-serif; font-size: 28px; font-weight: 800; color: #111827; margin-top: 4px;">{{TOTAL_INTERACCIONES}}</div>
                    <span style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; color: #9ca3af;">Periodo consolidado</span>
                  </td>
                  <td width="4%"></td>
                  <td width="48%" style="background-color: #f9fafb; border-left: 4px solid #374151; border-top: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb; border-bottom: 1px solid #e5e7eb; border-radius: 0 6px 6px 0; padding: 16px; text-align: left;">
                    <span style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; text-transform: uppercase; color: #6b7280; font-weight: 600; letter-spacing: 0.5px;">Cobertura Top 10</span>
                    <div style="font-family: 'Neo Sans Std', 'Segoe UI', Arial, sans-serif; font-size: 28px; font-weight: 800; color: #374151; margin-top: 4px;">{{COBERTURA_PORCENTAJE}}</div>
                    <span style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; color: #9ca3af;">{{COBERTURA_INTERACCIONES}}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 25px 40px;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 18px;">
                <tr>
                  <td colspan="3" style="padding-bottom: 10px;">
                    <span style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; text-transform: uppercase; color: #6b7280; font-weight: 700; letter-spacing: 0.8px;">Distribucion General de Canales</span>
                  </td>
                </tr>
                <tr>
                  <td width="45%" align="left" style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #111827;">
                    <span style="display: inline-block; width: 8px; height: 8px; background-color: #DA282D; border-radius: 50%; margin-right: 6px;"></span>
                    <strong>AOL:</strong> {{TOTAL_AOL}} <span style="color: #6b7280; font-size: 11px;">({{PCT_AOL}})</span>
                  </td>
                  <td width="10%" align="center" style="font-family: 'Neo Sans Std', Arial, sans-serif; font-size: 11px; font-weight: bold; color: #9ca3af;">
                    VS
                  </td>
                  <td width="45%" align="right" style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #111827;">
                    <strong>NBDA:</strong> {{TOTAL_NBDA}} <span style="color: #6b7280; font-size: 11px;">({{PCT_NBDA}})</span>
                    <span style="display: inline-block; width: 8px; height: 8px; background-color: #374151; border-radius: 50%; margin-left: 6px;"></span>
                  </td>
                </tr>
                <tr>
                  <td colspan="3" style="padding-top: 12px;">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="height: 10px; border-radius: 5px; overflow: hidden; background-color: #e5e7eb;">
                      <tr>
                        <td width="{{PCT_AOL}}" style="background-color: #DA282D; height: 10px; border-radius: 5px 0 0 5px;"></td>
                        <td width="{{PCT_NBDA}}" style="background-color: #374151; height: 10px; border-radius: 0 5px 5px 0;"></td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 10px 40px 0 40px;">
{{CLIENT_EXECUTIVE_BLOCK}}
            </td>
          </tr>
          <tr>
            <td style="padding: 10px 40px 0 40px;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td style="border-bottom: 2px solid #DA282D; padding-bottom: 8px;">
                    <h2 style="margin: 0; font-family: 'Neo Sans Std', 'Segoe UI', Arial, sans-serif; font-size: 16px; font-weight: bold; color: #111827; text-transform: uppercase; letter-spacing: 1px;">
                      Top 10 Interacciones Principales
                    </h2>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 15px 40px 30px 40px;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse;">
                <thead>
                  <tr style="background-color: #374151;">
                    <th align="center" width="5%" style="padding: 12px 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase; border-radius: 4px 0 0 0;">#</th>
                    <th align="left" width="35%" style="padding: 12px 10px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase;">Descripcion de la Interaccion</th>
                    <th align="center" width="15%" style="padding: 12px 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase;">AOL</th>
                    <th align="center" width="15%" style="padding: 12px 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase;">NBDA</th>
                    <th align="center" width="16%" style="padding: 12px 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase;">Conversacion Media</th>
                    <th align="center" width="14%" style="padding: 12px 10px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; font-weight: bold; color: #ffffff; text-transform: uppercase; border-radius: 0 4px 0 0;">Total</th>
                  </tr>
                </thead>
                <tbody>
{{TABLE_ROWS}}
                </tbody>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 30px 40px;">
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f3f4f6; border-radius: 6px;">
                <tr>
                  <td style="padding: 15px 20px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; font-weight: bold; color: #374151;">
                    TOTAL GENERAL CANALES (AOL + NBDA)
                  </td>
                  <td align="right" style="padding: 15px 20px; font-family: 'Neo Sans Std', Arial, sans-serif; font-size: 18px; font-weight: 800; color: #DA282D;">
                    {{TOTAL_INTERACCIONES}}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 40px 35px 40px; border-top: 1px solid #f3f4f6;">
              <p style="margin: 25px 0 0 0; font-family: 'Neo Sans Std', 'Segoe UI', Arial, sans-serif; font-size: 14px; color: #4b5563; line-height: 1.5;">
                Saludos cordiales,<br>
                <strong style="color: #111827;">{{FIRMA}}</strong>
              </p>
            </td>
          </tr>
          <tr>
            <td style="background-color: #f9fafb; padding: 20px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
              <p style="margin: 0; font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; color: #9ca3af; line-height: 1.4;">
                Este reporte ha sido generado automaticamente por Estrategia y Gestión Contact Center.<br>
                &copy; 2026.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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


def split_recipients(value: Any) -> List[str]:
    if value is None:
        return []

    text = str(value).strip()
    if not text or text.lower() in ("null", "none", "undefined"):
        return []

    if text.startswith("[") and text.endswith("]"):
        try:
            import json
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass

    normalized = text.replace(";", ",").replace("\n", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


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
    detail_page_size: int
    hana_read_host: str
    hana_port: int
    hana_user: str
    hana_password: str
    hana_client_schema: str
    hana_client_table: str
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
        detail_page_size=env_int("DETAIL_PAGE_SIZE", 100),
        hana_read_host=env_str("HPR_HOST_ESPEJO", ""),
        hana_port=env_int("HPR_PORT", 30015),
        hana_user=env_str("HPR_USER", ""),
        hana_password=env_str("HPR_PASSWORD", ""),
        hana_client_schema=env_str("HANA_CLIENT_SCHEMA", "DS_STG"),
        hana_client_table=env_str("HANA_CLIENT_TABLE", "CRM_DIM_CLIENTES"),
        graph_tenant_id=env_str("GRAPH_TENANT_ID", ""),
        graph_client_id=env_str("GRAPH_CLIENT_ID", ""),
        graph_client_secret=env_str("GRAPH_CLIENT_SECRET", ""),
        graph_sender_email=env_str("GRAPH_SENDER_EMAIL", ""),
        graph_authority_url=DEFAULT_GRAPH_AUTHORITY_URL,
        graph_scope=DEFAULT_GRAPH_SCOPE,
        graph_save_to_sent_items=DEFAULT_GRAPH_SAVE_TO_SENT_ITEMS,
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



# =========================================================
# CONCLUSIONES PARAMETRIZADAS DENTRO DEL SCRIPT
# =========================================================
# Importante:
#   El reporte SOLO consultará las conclusiones incluidas en estas dos listas.
#   Ya no filtra por prefijos amplios como NBDA_, CONSULTA_AOL_, GESTIONES_AOL_, etc.
#   Esto evita traer conclusiones que no corresponden y que inflan el total.

NBDA_WRAPUP_EXACT_NAMES = {
    "NBDA_PAGINA_WEB_NO_FUNCIONA",
    "NBDA_NO_APARECE_RECIBO_PAGO",
    "NBDA_CAMBIO_CORREO_ELECTRÓNICO",
    "NBDA_SOPORTE_USO_PAGINA_WEB",
    "NBDA_AGREGAR_CUENTA_FIRMANTE",
    "NBDA_PAGINA_WEB_APP_NO_FUNCIONA",
    "NBDA_NO_RECIBE_CODIGO_OTP",
    "NBDA_TOKEN_SMART_TOKEN_REMITIDO_A_AGENCIA",
    "NBDA_SOPORTE_USO_BANCA_MOVIL",
    "NBDA_DESBLOQUEO_USUARIO",
    "NBDA_SOPORTE_MIGRACIÓN_ATLANTIDA_HN",
    "NBDA_SOPORTE_APERTURA_CTA_DIGITAL",
    "NBDA_RETIRO_SIN_TD",
    "NBDA_REQUIERE_DESLIGAR_TOKEN_SMART_TOKEN",
    "NBDA_ACTIVACION_DE_USUARIO",
    "NBDA_INSTALACION_APP_MOVIL",
    "NBDA_TRANSFERENCIAS_ACH",
    "NBDA_CABINAS_TELEFONICAS",
    "NBDA_SOPORTE_CREACION_DE_USUARIO",
    "NBDA_CONTRASEÑA_TEMPORAL_VENCIDA",
    "NBDA_CAJA_EMPRESARIAL",
    "NBDA_SOPORTE_TRANSFERENCIA_INTERNACIONAL",
    "NBDA_AGREGAR_PRODUCTOS",
    "NBDA_ACTUALIZACION_DE_DATOS",
    "NBDA_PROBLEMAS_TECNICOS_DEL_CLIENTE",
    "NBDA_REQUISITOS_APERTURA",
    "NBDA_CLIENTE_EN_EXTRANJERO,_NO_RECUERDA_USUAR._EN_EL_EXTRANJE",
    "NBDA_CLIENTE_EN_EXTRANJERO_NO_RECUERDA_USUAR_EN_EL_EXTRANJE",
    "NBDA_BLOQUEO_DE_TOKEN",
    "NBDA_SINCRONIZACION_TOKEN_OFFLINE",
    "NBDA_APLICACIÓN_PAGO_NO_GENERADO",
    "NBDA_REVERSIONES_PAGOS",
    "NBDA_SOPORTE_DE_REMESAS",
    "NBDA_SOPORTE_REMESAS",
    "NBDA_CAMBIO_DE_CONTRASEÑA",
}

AOL_WRAPUP_EXACT_NAMES = {
    "GESTIONES_AOL_ACTIVACION_DE_USUARIO_AOL",
    "CONSULTA_AOL_RESOLUCIÓN_GEST_AOL/SMS/DEB_AUTOMÁTICO",
    "CONSULTAS_RETIRO_SIN_TD_POR_AOL",
    "CONSULTA_AOL_CAJA_EMPRESARIAL",
    "CONSULTA_AOL_REQUISITOS_APERTURA_SMS",
    "SOPORTE_REMESAS_INGRESAR_A_AOL",
    "GESTIONES_AOL_APROBACION_USUARIO_AOL_PROCESO",
    "GESTIONES_AOL_SINCRONIZACION_TOKEN/SMART_TOKEN",
    "CONSULTA_AOL_PAGO_DE_DÉBITO_AUTOMÁTICO",
    "CONSULTA_AOL_TOKEN/SMART_TOKEN/REMITIDO_A_AGENCIA",
    "GESTIONES_AOL_PRIVILEGIOS_CUENTAS_SMS_ATLANTIDA",
    "CONSULTA_AOL_AOL_MOVIL",
    "GESTIONES_AOL_DESBLOQ/SINCRONIZACIÓN_TOKEN/SMART_TOKEN",
    "GESTIONES_AOL_REVERSIONES_PAGOS_POR_AOL",
    "GESTIONES_AOL_CLIENTE_EN_EXTRANJERO,_NO_RECUERDA_USUAR._EN_EL_EXTRANJE",
    "CONSULTA_AOL_COBRO_DEVOLUCION_DE_TOKEN",
    "GESTIONES_AOL_APLICACIÓN_PAGO_NO_GENERADO_AOL",
    "CONSULTA_AOL_TRANSFERENCIAS_ACH",
    "GESTIONES_AOL_CAMBIO_CORREO_ELECTRÓNICO",
    "GESTIONES_AOL_AGREGAR_CUENTAS_SMS_ATLANTIDA",
    "GESTIONES_AOL_NO_APARECE_RECIBO_PAGO_AOL",
    "GESTIONES_AOL_CAMBIO_DE_PIN_A_TOKEN",
    "GESTIONES_AOL_PRIVILEGIOS_CTA_FIRMANTE_AOL",
    "GESTIONES_AOL_REGISTRO_DE_BENEFICIARIO_C__EN_EL_EXTRAN",
    "GESTIONES_AOL_CAMBIO_DE_TOKEN_A_PIN",
    "GESTIONES_AOL_REGISTRO_DE_BENEFICIARIO_C._EN_EL_EXTRAN._EN_EL_EXTRANJERO,_NO_RECUERDA_USUAR._EN_EL_EXTRANJE",
    "CONSULTAS_AOL_REQUISITOS_APERTURA_DEBITOS_AUTOMÁTICOS",
    "SOPORTE_TÉCNICO_AOL_INSTALACION_APP_AOL_MOVIL",
    "GESTIONES_AOL_AGREGAR_PRODUCTOS_A_AOL",
    "CONSULTA_AOL_AOL_LANDING_PAGE",
    "GESTIONES_AOL_CREACION_DE_TOKEN_C._EN_EL_EXTRANJERO,_NO_RECUERDA_USUAR._EN_EL_EXTRANJE",
    "CONSULTA_AOL_COBRO_DE_REPOSICION_DE_TOKEN",
    "CONSULTA_AOL_DESBLOQUEO_USUARIO/CONTRASEÑA_(LANDING)",
    "GESTIONES_AOL_CREACION_DE_USUARIO_EN_ENTRUST",
    "GESTIONES_AOL_DESBLOQUEO_DE_SESIONES_ACTIVAS_AOL",
    "GESTIONES_AOL_CAMBIO_DE_PIN_A_SMART_TOKEN",
    "CONSULTA_AOL_PAGINA_WEB_NO_FUNCIONA",
    "GESTIONES_AOL_CAMBIO_DE_TOKEN_A_SMART_TOKEN",
    "SOPORTE_TÉCNICO_AOL_SOPORTE_USO_AOL",
    "GESTIONES_AOL_CAMBIO_PORTABILIDAD_SMS_ATLANTIDA",
    "GESTIONES_AOL_PRIVILEGIOS_A_PRODUCTOS_AOL",
    "GESTIONES_AOL_BLOQUEO_DE_TOKEN",
    "CONSULTA_AOL_REQUISITOS_APERTURA_AOL",
    "GESTIONES_AOL_CAMBIO_DE_CONTRASEÑA",
    "CONSULTA_AOL_REQUIERE_DESLIGAR_TTOKEN/SMART_TOKEN",
    "SOPORTE_TÉCNICO_AOL_SOPORTE_PARA_MASE",
    "GESTIONES_AOL_AGREGAR_CUENTA_FIRMANTE_AOL",
    "GESTIONES_AOL_CORRECCION_DE_USUARIOS_ENTRUST",
    "CONSULTA_AOL_SOPORTE_DE_REMESAS_AOL",
    "SOPORTE_TÉCNICO_AOL_SOPORTE_DEBITOS_AUTOMATICOS",
    "SOPORTE_TÉCNICO_AOL_INSTALACION_APP_ENTRUST",
    "CONSULTA_AOL_REQUISITOS_APERTURA_DEBITOS_AUTOMATICOS",
    "GESTIONES_AOL_CORRECION_NOMBRE/APELLIDO_MASE",
    "CONSULTA_AOL_ACH_LANDING_PAGE",
    "CONSULTA_AOL_TRANSFERENCIA_DE_LLAMADA",
    "CONSULTA_AOL_CANCELAR_AOL/SMS/DÉBITO_AUTOMÁTICO",
    "GESTIONES_AOL_ACTUALIZACION_DE_DATOS_C._EN_EL_EXTRANJE",
    "SOPORTE_TÉCNICO_AOL_SOPORTE_P/SINCRONIZAR_TOKENS",
    "SOPORTE_TÉCNICO_AOL_SOPORTE_USO_SMS_ATLANTIDA",
}



def _norm_code_name(value: str) -> str:
    """Normaliza nombres de wrapup para comparar sin acentos, NBSP, espacios dobles ni diferencias menores."""
    if not value:
        return ""
    import unicodedata
    text = str(value).replace("\ufeff", "").replace("\xa0", " ").strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = " ".join(text.split())
    return text


NBDA_WRAPUP_EXACT_NAMES_NORM = {_norm_code_name(x) for x in NBDA_WRAPUP_EXACT_NAMES}
AOL_WRAPUP_EXACT_NAMES_NORM = {_norm_code_name(x) for x in AOL_WRAPUP_EXACT_NAMES}
ALL_WRAPUP_EXACT_NAMES_NORM = NBDA_WRAPUP_EXACT_NAMES_NORM | AOL_WRAPUP_EXACT_NAMES_NORM


def seconds_to_mmss(value: Any) -> str:
    """Convierte segundos a formato mm:ss para reportes ejecutivos."""
    try:
        seconds = float(value or 0)
    except Exception:
        seconds = 0
    seconds = int(round(seconds))
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def is_target_wrapup_name(name: str) -> bool:
    """Valida únicamente contra las conclusiones exactas parametrizadas en el script."""
    if not name:
        return False
    return _norm_code_name(name) in ALL_WRAPUP_EXACT_NAMES_NORM

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
        "SOPORTE_REMESAS_",
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

    Corrección importante:
    - Para cuadrar con el total de Genesys en Rendimiento de conclusión,
      el agrupamiento debe ser SOLO por wrapUpCode.
    - No se agrupa por queueId porque una misma conversación puede pasar por
      varias colas/segmentos y al sumar por cola se inflan los totales.
    - Se mantiene granularity P1D para poder generar las pestañas diarias.
    """
    return {
        "interval": f"{start_utc}/{end_utc}",
        "granularity": "P1D",
        "groupBy": [
            "wrapUpCode"
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

    logger.info("Consultando analytics aggregates por wrapUpCode, sin queueId para evitar duplicidad...")

    target_wrapup_ids = [
        wrapup_id
        for wrapup_id, wrapup_name in wrapup_catalog.items()
        if is_target_wrapup_name(wrapup_name)
    ]

    logger.info("Wrapup codes objetivo encontrados: %s", len(target_wrapup_ids))
    logger.info(
        "Conclusiones parametrizadas en script | AOL: %s | NBDA: %s | Total: %s",
        len(AOL_WRAPUP_EXACT_NAMES_NORM),
        len(NBDA_WRAPUP_EXACT_NAMES_NORM),
        len(ALL_WRAPUP_EXACT_NAMES_NORM),
    )

    catalog_norm_names = {_norm_code_name(name) for name in wrapup_catalog.values()}
    missing_from_catalog = sorted(ALL_WRAPUP_EXACT_NAMES_NORM - catalog_norm_names)
    if missing_from_catalog:
        logger.warning("Conclusiones parametrizadas no encontradas en catálogo Genesys: %s", len(missing_from_catalog))
        for missing in missing_from_catalog[:80]:
            logger.warning("No encontrada en Genesys: %s", missing)

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

            wrapup_name = wrapup_catalog.get(wrapup_id, "")

            if not is_target_wrapup_name(wrapup_name):
                continue

            # No se usa queueId en esta consulta.
            # Al agrupar por cola el mismo wrapUpCode puede contarse varias veces
            # si la conversación pasó por más de una cola/segmento.
            queue_id = ""
            queue_name = ""

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


def normalize_dni(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() in ("null", "none", "undefined", "nan"):
        return ""
    return re.sub(r"[\s\-.]+", "", text)


def validate_identifier(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(value or "")):
        raise ValueError(f"Identificador SQL invalido: {value!r}")


def hana_read_connect(config: Config):
    if dbapi is None:
        raise RuntimeError("No esta instalado hdbcli. Instala hdbcli para consultar SAP HANA.")

    missing = [
        name for name, value in {
            "HPR_HOST_ESPEJO": config.hana_read_host,
            "HPR_USER": config.hana_user,
            "HPR_PASSWORD": config.hana_password,
        }.items()
        if not str(value or "").strip()
    ]
    if missing:
        raise ValueError("Faltan variables globales de SAP HANA espejo: " + ", ".join(missing))

    return dbapi.connect(
        address=config.hana_read_host,
        port=config.hana_port,
        user=config.hana_user,
        password=config.hana_password
    )


def extract_external_tag(conversation: Dict[str, Any]) -> str:
    candidates = [conversation.get("externalTag"), conversation.get("externalContactId")]
    for participant in conversation.get("participants") or []:
        attrs = participant.get("attributes") or {}
        for key in (
            "ETIQUETA_EXTERNA", "Etiqueta_Externa", "etiqueta_externa",
            "DNI", "dni", "IDENTIFICACION", "identificacion",
            "documento", "DOCUMENTO", "customerId", "CustomerId"
        ):
            candidates.append(attrs.get(key))

    for candidate in candidates:
        cleaned = normalize_dni(candidate)
        if cleaned:
            return cleaned
    return ""


def get_last_target_wrapup_for_conversation(
    conversation: Dict[str, Any],
    wrapup_catalog: Dict[str, str]
) -> Tuple[str, str, str]:
    found: List[Tuple[str, str, str]] = []
    for participant in conversation.get("participants") or []:
        for session in participant.get("sessions") or []:
            if str(session.get("mediaType") or "").lower() not in ("", "voice"):
                continue
            for segment in session.get("segments") or []:
                wrapup_id = segment.get("wrapUpCode") or ""
                wrapup_name = wrapup_catalog.get(wrapup_id, wrapup_id)
                if wrapup_id and is_target_wrapup_name(wrapup_name):
                    found.append((
                        segment.get("segmentEnd") or segment.get("segmentStart") or "",
                        wrapup_id,
                        wrapup_name
                    ))

    if not found:
        return "", "", ""
    found.sort(key=lambda item: item[0])
    _, wrapup_id, wrapup_name = found[-1]
    return wrapup_id, wrapup_name, clean_conclusion_name(wrapup_name)


def utc_to_local_display(value: Any, tz_name: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


def query_conclusion_call_details(
    config: Config,
    token: str,
    start_utc: str,
    end_utc: str,
    wrapup_catalog: Dict[str, str],
    logger: logging.Logger
) -> pd.DataFrame:
    target_wrapup_ids = [
        wrapup_id
        for wrapup_id, wrapup_name in wrapup_catalog.items()
        if is_target_wrapup_name(wrapup_name)
    ]
    columns = [
        "conversationId", "conversationStart", "conversationEnd", "Fecha",
        "wrapUpCode", "Nombre de conclusion", "conclusion", "Banca",
        "externalTag", "Estado externalTag"
    ]
    if not target_wrapup_ids:
        logger.warning("Detalle clientes omitido: no hay wrapups objetivo.")
        return pd.DataFrame(columns=columns)

    jobs_url = f"{config.genesys_region_base_url}/api/v2/analytics/conversations/details/jobs"
    page_size = max(25, min(int(config.detail_page_size or 100), 500))
    wrapup_chunks = chunks(target_wrapup_ids, env_int("WRAPUP_DETAIL_CHUNK_SIZE", 20))
    poll_seconds = env_int("DETAIL_JOB_POLL_SECONDS", 10)
    max_poll_attempts = env_int("DETAIL_JOB_MAX_POLL_ATTEMPTS", 120)
    rows: List[Dict[str, Any]] = []

    logger.info("Creando Details Job de Genesys para detalle de conversaciones...")
    for chunk_number, wrapup_chunk in enumerate(wrapup_chunks, start=1):
        body = {
            "interval": f"{start_utc}/{end_utc}",
            "order": "asc",
            "orderBy": "conversationStart",
            "segmentFilters": [
                {
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
                                for wrapup_id in wrapup_chunk
                            ]
                        }
                    ]
                }
            ]
        }

        logger.info(
            "Job creado: solicitando bloque %s/%s | wrapups: %s",
            chunk_number,
            len(wrapup_chunks),
            len(wrapup_chunk)
        )
        create_response = request_with_retries(
            "POST",
            jobs_url,
            config,
            logger,
            headers=genesys_headers(token),
            json=body
        )
        job_payload = create_response.json() or {}
        job_id = job_payload.get("jobId") or job_payload.get("id")
        if not job_id:
            raise RuntimeError(f"Genesys no devolvio jobId. Respuesta: {str(job_payload)[:1000]}")

        logger.info("Job creado: %s", job_id)
        status_url = f"{jobs_url}/{job_id}"
        state = ""
        for attempt in range(1, max_poll_attempts + 1):
            logger.info("Esperando resultados del job %s | intento %s/%s", job_id, attempt, max_poll_attempts)
            status_response = request_with_retries(
                "GET",
                status_url,
                config,
                logger,
                headers=genesys_headers(token)
            )
            status_payload = status_response.json() or {}
            state = str(status_payload.get("state") or status_payload.get("status") or "").upper()
            logger.info("Job %s | estado: %s", job_id, state)
            if state in ("FULFILLED", "COMPLETED", "COMPLETE", "FINISHED", "SUCCEEDED"):
                break
            if state in ("FAILED", "ERROR", "CANCELLED", "CANCELED", "EXPIRED"):
                raise RuntimeError(f"Details Job fallo. jobId={job_id} estado={state} respuesta={str(status_payload)[:1200]}")
            time.sleep(poll_seconds)
        else:
            raise TimeoutError(f"Details Job no finalizo. jobId={job_id} ultimo_estado={state}")

        results_url = f"{jobs_url}/{job_id}/results"
        cursor = ""
        page = 1
        while True:
            params: Dict[str, Any] = {"pageSize": page_size}
            if cursor:
                params["cursor"] = cursor

            result_response = request_with_retries(
                "GET",
                results_url,
                config,
                logger,
                headers=genesys_headers(token),
                params=params
            )
            result_payload = result_response.json() or {}
            conversations = result_payload.get("conversations") or result_payload.get("entities") or result_payload.get("results") or []
            if not conversations:
                break

            for conversation in conversations:
                wrapup_id, wrapup_name, conclusion = get_last_target_wrapup_for_conversation(conversation, wrapup_catalog)
                if not wrapup_id:
                    continue
                external_tag = extract_external_tag(conversation)
                rows.append({
                    "conversationId": conversation.get("conversationId") or conversation.get("id") or "",
                    "conversationStart": conversation.get("conversationStart") or "",
                    "conversationEnd": conversation.get("conversationEnd") or "",
                    "Fecha": utc_to_local_display(conversation.get("conversationStart"), config.timezone_name),
                    "wrapUpCode": wrapup_id,
                    "Nombre de conclusion": wrapup_name,
                    "conclusion": conclusion,
                    "Banca": get_banca(wrapup_name),
                    "externalTag": external_tag,
                    "Estado externalTag": "Con DNI" if external_tag else "Sin DNI / externalTag"
                })

            logger.info(
                "Paginas leidas | job %s | pagina %s | conversaciones: %s | acumulado: %s",
                job_id,
                page,
                len(conversations),
                len(rows)
            )
            cursor = result_payload.get("cursor") or result_payload.get("nextCursor") or ""
            if not cursor:
                break
            page += 1
            time.sleep(config.api_sleep_seconds)

    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df = df.drop_duplicates(subset=["conversationId"], keep="last")
    logger.info("Conversaciones obtenidas: %s", len(df))
    logger.info("Registros con externalTag: %s", 0 if df.empty else int(df["externalTag"].astype(str).str.strip().ne("").sum()))
    return df


DEMOGRAPHIC_COLUMNS = [
    "PAIS", "DEPARTAMENTO", "ESTADO_CIVIL", "GENERO", "SEGMENTO_BANCA",
    "TIPO_SECTOR_ECONOMICO", "NIVEL_EDUCATIVO", "NUMERO_DEPENDIENTES",
    "PROFESION", "FECHA_ULTIMA_ACTUALIZACION", "RANGO_FECHA_ACTUALIZACION",
    "GENERACION_CLIENTE"
]


def query_client_demographics(config: Config, external_tags: List[str], logger: logging.Logger) -> pd.DataFrame:
    etiquetas = sorted({normalize_dni(value) for value in external_tags if normalize_dni(value)})
    columns = ["ETIQUETA_EXTERNA"] + DEMOGRAPHIC_COLUMNS
    if not etiquetas:
        logger.warning("HANA no consultado: no hay externalTag para cruzar.")
        return pd.DataFrame(columns=columns)

    validate_identifier(config.hana_client_schema)
    validate_identifier(config.hana_client_table)
    logger.info("Consultando HANA espejo para %s clientes...", len(etiquetas))

    select_cols = """
        cdc.PAIS,
        cdc.DEPARTAMENTO,
        cdc.ESTADO_CIVIL,
        cdc.GENERO,
        CASE
            WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO PERSONAS' THEN 'Personas'
            WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO PYME' THEN 'PYME'
            WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO COMERCIAL' THEN 'Comercial'
            WHEN cdc.SEGMENTO_BANCA = 'SEGMENTO CORPORATIVA' THEN 'Corporativa'
            ELSE COALESCE(cdc.SEGMENTO_BANCA, 'Sin dato')
        END AS SEGMENTO_BANCA,
        cdc.TIPO_SECTOR_ECONOMICO,
        cdc.NIVEL_EDUCATIVO,
        cdc.NUMERO_DEPENDIENTES,
        cdc.PROFESION,
        cdc.FECHA_ULTIMA_ACTUALIZACION,
        CASE
            WHEN cdc.FECHA_ULTIMA_ACTUALIZACION IS NULL THEN '0. No actualizado'
            WHEN cdc.FECHA_ULTIMA_ACTUALIZACION >= ADD_MONTHS(CURRENT_DATE, -6) THEN '1. 0-6 meses'
            WHEN cdc.FECHA_ULTIMA_ACTUALIZACION >= ADD_MONTHS(CURRENT_DATE, -12) THEN '2. 6-12 meses'
            WHEN cdc.FECHA_ULTIMA_ACTUALIZACION >= ADD_MONTHS(CURRENT_DATE, -36) THEN '3. 1-3 anos'
            WHEN cdc.FECHA_ULTIMA_ACTUALIZACION >= ADD_MONTHS(CURRENT_DATE, -60) THEN '4. 3-5 anos'
            ELSE '5. >5 anos'
        END AS RANGO_FECHA_ACTUALIZACION,
        CASE
            WHEN LEFT(TO_NVARCHAR(cdc.FECHA_NACIMIENTO), 4) BETWEEN '2013' AND '2025' THEN 'Alpha (2013 - 2025)'
            WHEN LEFT(TO_NVARCHAR(cdc.FECHA_NACIMIENTO), 4) BETWEEN '1997' AND '2012' THEN 'Z (1997 - 2012)'
            WHEN LEFT(TO_NVARCHAR(cdc.FECHA_NACIMIENTO), 4) BETWEEN '1981' AND '1996' THEN 'Millennials (1981 - 1996)'
            WHEN LEFT(TO_NVARCHAR(cdc.FECHA_NACIMIENTO), 4) BETWEEN '1965' AND '1980' THEN 'X (1965 - 1980)'
            WHEN LEFT(TO_NVARCHAR(cdc.FECHA_NACIMIENTO), 4) BETWEEN '1946' AND '1964' THEN 'Baby Boomers (1946 - 1964)'
            WHEN LEFT(TO_NVARCHAR(cdc.FECHA_NACIMIENTO), 4) < '1946' THEN 'Silent (<1946)'
            ELSE 'Desconocida'
        END AS GENERACION_CLIENTE
    """

    parts = [
        f"""
        SELECT DISTINCT TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_{idx})) AS ETIQUETA_EXTERNA,
               {select_cols}
        FROM {config.hana_client_schema}.{config.hana_client_table} cdc
        WHERE cdc.IDENTIFICACION_{idx} IS NOT NULL
          AND TRIM(TO_NVARCHAR(cdc.IDENTIFICACION_{idx})) IN ({{placeholders}})
        """
        for idx in (1, 2, 3)
    ]
    sql_template = " UNION ALL ".join(parts)

    rows: List[Dict[str, Any]] = []
    conn = hana_read_connect(config)
    cur = conn.cursor()
    try:
        for batch in chunks(etiquetas, 500):
            placeholders = ", ".join(["?"] * len(batch))
            params: List[str] = []
            for _ in range(3):
                params.extend(batch)
            cur.execute(sql_template.format(placeholders=placeholders), params)
            for row in cur.fetchall():
                rows.append(dict(zip(columns, row)))
    finally:
        cur.close()
        conn.close()

    df = pd.DataFrame(rows, columns=columns)
    if not df.empty:
        df["ETIQUETA_EXTERNA"] = df["ETIQUETA_EXTERNA"].map(normalize_dni)
        df = df.drop_duplicates(subset=["ETIQUETA_EXTERNA"], keep="first")
    logger.info("Clientes encontrados en HANA: %s", len(df))
    return df


def _volume_pct_table(df: pd.DataFrame, field: str, label: str) -> pd.DataFrame:
    columns = [label, "Llamadas", "%"]
    if df.empty or field not in df.columns:
        return pd.DataFrame(columns=columns)
    work = df.copy()
    work[field] = work[field].fillna("Sin dato").replace("", "Sin dato")
    total = max(int(work["conversationId"].nunique()), 1)
    out = (
        work.groupby(field, dropna=False)
        .agg(Llamadas=("conversationId", "nunique"))
        .reset_index()
        .rename(columns={field: label})
        .sort_values("Llamadas", ascending=False)
    )
    out["%"] = out["Llamadas"] / total
    return out[columns]


def build_client_analysis(
    df_calls: pd.DataFrame,
    df_demo: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, pd.DataFrame], Dict[str, pd.DataFrame]]:
    detail_columns = [
        "conversationId", "Fecha", "conversationStart", "conversationEnd", "wrapUpCode",
        "Nombre de conclusion", "conclusion", "Banca", "externalTag", "Estado externalTag",
        "Estado HANA"
    ] + DEMOGRAPHIC_COLUMNS

    if df_calls.empty:
        empty_detail = pd.DataFrame(columns=detail_columns)
        return empty_detail, pd.DataFrame(), {}, {}

    detail = df_calls.copy()
    detail["externalTag"] = detail["externalTag"].map(normalize_dni)
    if not df_demo.empty:
        detail = detail.merge(df_demo, left_on="externalTag", right_on="ETIQUETA_EXTERNA", how="left")
    else:
        detail["ETIQUETA_EXTERNA"] = ""

    for col in DEMOGRAPHIC_COLUMNS:
        if col not in detail.columns:
            detail[col] = ""
        detail[col] = detail[col].fillna("No encontrado en HANA").replace("", "No encontrado en HANA")

    detail["Estado HANA"] = detail.apply(
        lambda row: "Sin DNI / externalTag"
        if not normalize_dni(row.get("externalTag"))
        else ("Encontrado en HANA" if normalize_dni(row.get("ETIQUETA_EXTERNA")) else "No encontrado en HANA"),
        axis=1
    )
    for col in detail_columns:
        if col not in detail.columns:
            detail[col] = ""
    detail = detail[detail_columns]

    known = detail[detail["externalTag"].astype(str).str.strip().ne("")].copy()
    recurrence_rows: List[Dict[str, Any]] = []
    if not known.empty:
        per_client = (
            known.groupby(["conclusion", "externalTag"], dropna=False)
            .agg(consultas=("conversationId", "nunique"))
            .reset_index()
        )
        for conclusion, group in per_client.groupby("conclusion", dropna=False):
            calls_total = int(known.loc[known["conclusion"] == conclusion, "conversationId"].nunique())
            unique_clients = int(group["externalTag"].nunique())
            c1 = int((group["consultas"] == 1).sum())
            c2 = int((group["consultas"] == 2).sum())
            c3 = int((group["consultas"] == 3).sum())
            c4 = int((group["consultas"] >= 4).sum())
            recurrent = c2 + c3 + c4
            recurrence_rows.append({
                "Conclusión": conclusion,
                "Clientes únicos": unique_clients,
                "Llamadas totales": calls_total,
                "1 consulta": c1,
                "2 consultas": c2,
                "3 consultas": c3,
                "4+ consultas": c4,
                "% recurrentes": recurrent / unique_clients if unique_clients else 0
            })

    recurrence = pd.DataFrame(recurrence_rows)
    if not recurrence.empty:
        recurrence = recurrence.sort_values(["% recurrentes", "Llamadas totales"], ascending=[False, False])

    location_tables = {
        "Por PAIS": _volume_pct_table(detail, "PAIS", "PAIS"),
        "Por DEPARTAMENTO": _volume_pct_table(detail, "DEPARTAMENTO", "DEPARTAMENTO")
    }
    demographic_tables = {
        field: _volume_pct_table(detail, field, field)
        for field in ["GENERACION_CLIENTE", "GENERO", "RANGO_FECHA_ACTUALIZACION", "SEGMENTO_BANCA", "ESTADO_CIVIL"]
    }
    return detail, recurrence, location_tables, demographic_tables


def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resumen ejecutivo por conclusión:
    - AOL / AOL %
    - NBDA / NBDA %
    - Total
    - Conversación media ponderada por Manejo

    La conversación media se calcula de forma ponderada para no distorsionar
    conclusiones con poco volumen.
    """
    columns = [
        "DESCRIPCIÓN DE LA INTERACCIÓN",
        "AOL",
        "AOL %",
        "NBDA",
        "NBDA %",
        "Total",
        "Conversación media"
    ]

    if df.empty:
        return pd.DataFrame(columns=columns)

    work = df.copy()
    work["Manejo"] = pd.to_numeric(work.get("Manejo", 0), errors="coerce").fillna(0)
    work["Conversación media"] = pd.to_numeric(work.get("Conversación media", 0), errors="coerce").fillna(0)
    work["_talk_weight"] = work["Conversación media"] * work["Manejo"]

    pivot = (
        work.pivot_table(
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

    talk = (
        work.groupby("conclusion", dropna=False)
        .agg(_talk_weight=("_talk_weight", "sum"), _manejo=("Manejo", "sum"))
        .reset_index()
    )
    talk["Conversación media"] = talk.apply(
        lambda r: seconds_to_mmss(r["_talk_weight"] / r["_manejo"]) if r["_manejo"] else "00:00",
        axis=1
    )

    pivot["Total"] = pivot["AOL"] + pivot["NBDA"]
    pivot = pivot[pivot["Total"] > 0].copy()

    pivot["AOL %"] = (pivot["AOL"] / pivot["Total"]).fillna(0)
    pivot["NBDA %"] = (pivot["NBDA"] / pivot["Total"]).fillna(0)

    pivot = pivot.merge(talk[["conclusion", "Conversación media"]], on="conclusion", how="left")
    pivot["Conversación media"] = pivot["Conversación media"].fillna("00:00")

    pivot = pivot.rename(columns={"conclusion": "DESCRIPCIÓN DE LA INTERACCIÓN"})

    pivot = pivot[columns].sort_values("Total", ascending=False)

    total_aol = pivot["AOL"].sum()
    total_nbda = pivot["NBDA"].sum()
    total_general = pivot["Total"].sum()

    total_talk_weight = work["_talk_weight"].sum()
    total_manejo = work["Manejo"].sum()
    total_conversacion_media = seconds_to_mmss(total_talk_weight / total_manejo) if total_manejo else "00:00"

    total_row = pd.DataFrame([{
        "DESCRIPCIÓN DE LA INTERACCIÓN": "Total general",
        "AOL": total_aol,
        "AOL %": total_aol / total_general if total_general else 0,
        "NBDA": total_nbda,
        "NBDA %": total_nbda / total_general if total_general else 0,
        "Total": total_general,
        "Conversación media": total_conversacion_media
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


def _write_sectioned_tables(writer: pd.ExcelWriter, sheet_name: str, tables: Dict[str, pd.DataFrame]) -> None:
    worksheet = writer.book.create_sheet(sheet_name)
    row = 0
    for title, table in tables.items():
        worksheet.cell(row=row + 1, column=1, value=title)
        row += 1
        safe_table = table if table is not None else pd.DataFrame()
        if safe_table.empty:
            safe_table = pd.DataFrame([{"Mensaje": "Sin datos para el periodo"}])
        safe_table.to_excel(writer, sheet_name=sheet_name, startrow=row, index=False)
        row += len(safe_table) + 3


def create_excel(
    df_detail: pd.DataFrame,
    df_summary: pd.DataFrame,
    output_path: Path,
    logger: logging.Logger,
    df_client_detail: Optional[pd.DataFrame] = None,
    df_recurrence: Optional[pd.DataFrame] = None,
    location_tables: Optional[Dict[str, pd.DataFrame]] = None,
    demographic_tables: Optional[Dict[str, pd.DataFrame]] = None
) -> Path:

    logger.info("Generando Excel: %s", output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_aol = build_conclusion_daily_matrix(df_detail, "AOL")
    df_nbda = build_conclusion_daily_matrix(df_detail, "NBDA")

    # Pestaña adicional para análisis: conserva la data transformada desde Genesys.
    df_data = df_detail.copy()
    if not df_data.empty:
        preferred_order = [
            "Inicio del intervalo", "Fin del intervalo", "Fecha conclusión", "Día", "Mes", "Año",
            "Banca", "ID de código de conclusión", "Nombre de código de conclusión", "conclusion",
            "ID de cola", "Nombre de cola", "Manejo", "Manejo medio", "Conversación media",
            "Retención", "Retención media", "ACW medio"
        ]
        existing = [c for c in preferred_order if c in df_data.columns]
        remaining = [c for c in df_data.columns if c not in existing]
        df_data = df_data[existing + remaining]

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Requerimiento actualizado: agregar Data para análisis.
        df_data.to_excel(writer, sheet_name="Data", index=False)
        df_summary.to_excel(writer, sheet_name="Resumen", index=False)
        df_aol.to_excel(writer, sheet_name="Conclusiones AOL", index=False)
        df_nbda.to_excel(writer, sheet_name="Conclusiones NBDA", index=False)
        if df_client_detail is not None:
            df_client_detail.to_excel(writer, sheet_name="Detalle Clientes", index=False)
        if df_recurrence is not None:
            df_recurrence.to_excel(writer, sheet_name="Recurrencia", index=False)
        if location_tables is not None:
            _write_sectioned_tables(writer, "Ubicación", location_tables)
        if demographic_tables is not None:
            _write_sectioned_tables(writer, "Demografía", demographic_tables)

        wb = writer.book

        for sheet_name in list(wb.sheetnames):
            _format_excel_sheet(wb[sheet_name])

        ws = wb["Resumen"]

        # Formato de porcentaje en columnas AOL % y NBDA %.
        headers = {ws.cell(row=1, column=col).value: col for col in range(1, ws.max_column + 1)}
        for row in range(2, ws.max_row + 1):
            for header in ["AOL %", "NBDA %"]:
                col = headers.get(header)
                if col:
                    ws.cell(row=row, column=col).number_format = "0%"

    logger.info("Excel generado correctamente.")
    return output_path

def format_int(value: Any) -> str:
    try:
        return f"{int(float(value)):,}"
    except Exception:
        return "0"


def format_pct(value: Any, decimals: int = 1) -> str:
    try:
        return f"{float(value) * 100:.{decimals}f}%"
    except Exception:
        return f"{0:.{decimals}f}%"


def pct_from_counts(part: float, total: float, decimals: int = 1) -> str:
    if not total:
        return f"{0:.{decimals}f}%"
    return f"{(part / total) * 100:.{decimals}f}%"


def build_top10_table_rows(df_summary: pd.DataFrame, include_table: bool = True) -> str:
    if not include_table:
        return """
                    <tr>
                      <td colspan="6" align="center" style="padding: 22px 12px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #6b7280; background-color: #f9fafb;">
                        Tabla resumen no incluida para esta ejecución.
                      </td>
                    </tr>
"""

    if df_summary.empty:
        return """
                    <tr>
                      <td colspan="6" align="center" style="padding: 22px 12px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #6b7280; background-color: #f9fafb;">
                        No se encontraron registros para el periodo seleccionado.
                      </td>
                    </tr>
"""

    body_rows = (
        df_summary[df_summary["DESCRIPCIÓN DE LA INTERACCIÓN"] != "Total general"]
        .copy()
        .sort_values("Total", ascending=False)
        .head(10)
    )

    if body_rows.empty:
        return """
                    <tr>
                      <td colspan="6" align="center" style="padding: 22px 12px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #6b7280; background-color: #f9fafb;">
                        No se encontraron registros para el periodo seleccionado.
                      </td>
                    </tr>
"""

    rows: List[str] = []
    for pos, (_, row) in enumerate(body_rows.iterrows(), start=1):
        bg_color = "background-color: #fdfdfd;" if pos % 2 == 0 else ""
        num_color = "color: #DA282D;" if pos == 1 else "color: #4b5563;"
        desc = html.escape(str(row.get("DESCRIPCIÓN DE LA INTERACCIÓN", "")))
        aol = int(float(row.get("AOL", 0) or 0))
        nbda = int(float(row.get("NBDA", 0) or 0))
        total = int(float(row.get("Total", 0) or 0))
        aol_pct = format_pct(row.get("AOL %", 0))
        nbda_pct = format_pct(row.get("NBDA %", 0))
        media = html.escape(str(row.get("Conversación media", "00:00") or "00:00"))

        aol_cell = (
            f'<span style="font-weight: bold; color: #111827;">{format_int(aol)}</span><br>'
            f'<span style="font-size: 10px; color: #9ca3af;">({aol_pct})</span>'
            if aol > 0
            else '<span>0</span><br><span style="font-size: 10px; color: #cbd5e1;">(0.0%)</span>'
        )
        nbda_cell = (
            f'<span style="font-weight: bold; color: #111827;">{format_int(nbda)}</span><br>'
            f'<span style="font-size: 10px; color: #9ca3af;">({nbda_pct})</span>'
            if nbda > 0
            else '<span>0</span><br><span style="font-size: 10px; color: #cbd5e1;">(0.0%)</span>'
        )

        rows.append(f"""                    <tr style="border-bottom: 1px solid #e5e7eb; {bg_color}">
                      <td align="center" style="padding: 12px 8px; font-family: 'Neo Sans Std', Arial, sans-serif; font-size: 13px; font-weight: bold; {num_color}">{pos}</td>
                      <td align="left" style="padding: 12px 10px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #111827; font-weight: 500;">{desc}</td>
                      <td align="center" style="padding: 12px 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; color: #4b5563;">{aol_cell}</td>
                      <td align="center" style="padding: 12px 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; color: #4b5563;">{nbda_cell}</td>
                      <td align="center" style="padding: 12px 8px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #4b5563; font-weight: bold;">{media}</td>
                      <td align="center" style="padding: 12px 10px; font-family: 'Neo Sans Std', Arial, sans-serif; font-size: 14px; font-weight: bold; color: #111827; background-color: #f9fafb;">{format_int(total)}</td>
                    </tr>""")

    return "\n".join(rows)


def _mini_metric_rows(df: Optional[pd.DataFrame], label_col: str, value_col: str = "Llamadas", max_rows: int = 5) -> str:
    if df is None or df.empty or label_col not in df.columns:
        return "<tr><td colspan='2' style='padding:6px 0;color:#9ca3af;font-size:12px;'>Sin datos disponibles</td></tr>"
    rows: List[str] = []
    work = df.copy().head(max_rows)
    for _, item in work.iterrows():
        label = html.escape(str(item.get(label_col, "Sin dato") or "Sin dato"))
        value = format_int(item.get(value_col, 0))
        pct = ""
        if "%" in item:
            pct = f" <span style='color:#9ca3af;font-size:11px;'>({format_pct(item.get('%', 0))})</span>"
        rows.append(
            "<tr>"
            f"<td style='padding:5px 0;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#374151;'>{label}</td>"
            f"<td align='right' style='padding:5px 0;font-family:Segoe UI,Arial,sans-serif;font-size:12px;color:#111827;font-weight:bold;'>{value}{pct}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_client_executive_email_block(
    df_client_detail: Optional[pd.DataFrame],
    df_recurrence: Optional[pd.DataFrame],
    location_tables: Optional[Dict[str, pd.DataFrame]],
    demographic_tables: Optional[Dict[str, pd.DataFrame]]
) -> str:
    if df_client_detail is None:
        return ""

    total_calls = int(df_client_detail["conversationId"].nunique()) if not df_client_detail.empty and "conversationId" in df_client_detail.columns else 0
    identified = pd.DataFrame()
    if not df_client_detail.empty and "externalTag" in df_client_detail.columns:
        identified = df_client_detail[df_client_detail["externalTag"].astype(str).str.strip().ne("")]
    unique_clients = int(identified["externalTag"].nunique()) if not identified.empty else 0

    recurrent_clients = 0
    recurrent_pct = 0.0
    if not identified.empty:
        per_client = identified.groupby("externalTag")["conversationId"].nunique()
        recurrent_clients = int((per_client > 1).sum())
        recurrent_pct = recurrent_clients / unique_clients if unique_clients else 0.0

    top_recurrence = pd.DataFrame()
    if df_recurrence is not None and not df_recurrence.empty:
        top_recurrence = df_recurrence.sort_values(["% recurrentes", "Llamadas totales"], ascending=[False, False]).head(5)
        top_recurrence = top_recurrence.rename(columns={"Conclusión": "Conclusion", "Llamadas totales": "Llamadas"})

    dept_table = (location_tables or {}).get("Por DEPARTAMENTO", pd.DataFrame())
    gen_table = (demographic_tables or {}).get("GENERACION_CLIENTE", pd.DataFrame())
    gender_table = (demographic_tables or {}).get("GENERO", pd.DataFrame())

    return f"""
              <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#fff7f7;border:1px solid #fecaca;border-radius:6px;margin-bottom:20px;">
                <tr>
                  <td colspan="3" style="padding:16px 16px 8px 16px;font-family:Segoe UI,Arial,sans-serif;">
                    <strong style="font-size:15px;color:#111827;">Resumen ejecutivo de clientes</strong>
                    <div style="font-size:12px;color:#6b7280;margin-top:3px;">Recurrencia, ubicacion y demografia identificada con externalTag y HANA espejo.</div>
                  </td>
                </tr>
                <tr>
                  <td width="33%" style="padding:12px 16px;font-family:Segoe UI,Arial,sans-serif;border-top:1px solid #fee2e2;">
                    <span style="font-size:11px;color:#6b7280;text-transform:uppercase;">Llamadas analizadas</span><br>
                    <strong style="font-size:22px;color:#111827;">{format_int(total_calls)}</strong>
                  </td>
                  <td width="33%" style="padding:12px 16px;font-family:Segoe UI,Arial,sans-serif;border-top:1px solid #fee2e2;">
                    <span style="font-size:11px;color:#6b7280;text-transform:uppercase;">Clientes unicos</span><br>
                    <strong style="font-size:22px;color:#111827;">{format_int(unique_clients)}</strong>
                  </td>
                  <td width="34%" style="padding:12px 16px;font-family:Segoe UI,Arial,sans-serif;border-top:1px solid #fee2e2;">
                    <span style="font-size:11px;color:#6b7280;text-transform:uppercase;">Clientes recurrentes</span><br>
                    <strong style="font-size:22px;color:#DA282D;">{format_pct(recurrent_pct)}</strong>
                    <span style="font-size:11px;color:#6b7280;">({format_int(recurrent_clients)})</span>
                  </td>
                </tr>
                <tr>
                  <td valign="top" style="padding:10px 16px 16px 16px;font-family:Segoe UI,Arial,sans-serif;">
                    <strong style="font-size:12px;color:#111827;">Top recurrencia</strong>
                    <table width="100%" cellpadding="0" cellspacing="0">{_mini_metric_rows(top_recurrence, "Conclusion", "Llamadas")}</table>
                  </td>
                  <td valign="top" style="padding:10px 16px 16px 16px;font-family:Segoe UI,Arial,sans-serif;">
                    <strong style="font-size:12px;color:#111827;">Top departamentos</strong>
                    <table width="100%" cellpadding="0" cellspacing="0">{_mini_metric_rows(dept_table, "DEPARTAMENTO")}</table>
                  </td>
                  <td valign="top" style="padding:10px 16px 16px 16px;font-family:Segoe UI,Arial,sans-serif;">
                    <strong style="font-size:12px;color:#111827;">Generacion</strong>
                    <table width="100%" cellpadding="0" cellspacing="0">{_mini_metric_rows(gen_table, "GENERACION_CLIENTE")}</table>
                    <div style="height:8px;"></div>
                    <strong style="font-size:12px;color:#111827;">Genero</strong>
                    <table width="100%" cellpadding="0" cellspacing="0">{_mini_metric_rows(gender_table, "GENERO")}</table>
                  </td>
                </tr>
              </table>
"""


def build_email_metrics(
    df_summary: pd.DataFrame,
    include_table: bool,
    df_client_detail: Optional[pd.DataFrame] = None,
    df_recurrence: Optional[pd.DataFrame] = None,
    location_tables: Optional[Dict[str, pd.DataFrame]] = None,
    demographic_tables: Optional[Dict[str, pd.DataFrame]] = None
) -> Dict[str, str]:
    total_row = pd.DataFrame()
    if not df_summary.empty:
        total_row = df_summary[df_summary["DESCRIPCIÓN DE LA INTERACCIÓN"] == "Total general"]

    if not total_row.empty:
        total_aol = float(total_row.iloc[0].get("AOL", 0) or 0)
        total_nbda = float(total_row.iloc[0].get("NBDA", 0) or 0)
        total_general = float(total_row.iloc[0].get("Total", 0) or 0)
    else:
        total_aol = 0.0
        total_nbda = 0.0
        total_general = 0.0

    body_rows = pd.DataFrame()
    if not df_summary.empty:
        body_rows = (
            df_summary[df_summary["DESCRIPCIÓN DE LA INTERACCIÓN"] != "Total general"]
            .copy()
            .sort_values("Total", ascending=False)
            .head(10)
        )

    top10_total = float(pd.to_numeric(body_rows.get("Total", 0), errors="coerce").fillna(0).sum()) if not body_rows.empty else 0.0

    return {
        "TOTAL_INTERACCIONES": format_int(total_general),
        "COBERTURA_PORCENTAJE": pct_from_counts(top10_total, total_general),
        "COBERTURA_INTERACCIONES": f"{format_int(top10_total)} interacciones del Top 10",
        "TOTAL_AOL": format_int(total_aol),
        "PCT_AOL": pct_from_counts(total_aol, total_general),
        "TOTAL_NBDA": format_int(total_nbda),
        "PCT_NBDA": pct_from_counts(total_nbda, total_general),
        "TABLE_ROWS": build_top10_table_rows(df_summary, include_table=include_table),
        "CLIENT_EXECUTIVE_BLOCK": build_client_executive_email_block(
            df_client_detail,
            df_recurrence,
            location_tables,
            demographic_tables
        ),
        "FIRMA": env_str("EMAIL_SIGNATURE", "Odair Umanzor"),
    }


def render_email_html(
    df_summary: pd.DataFrame,
    start_local: datetime,
    end_local: datetime,
    cut_off_time: str,
    include_table: bool,
    df_client_detail: Optional[pd.DataFrame] = None,
    df_recurrence: Optional[pd.DataFrame] = None,
    location_tables: Optional[Dict[str, pd.DataFrame]] = None,
    demographic_tables: Optional[Dict[str, pd.DataFrame]] = None
) -> str:
    values = build_email_metrics(
        df_summary,
        include_table=include_table,
        df_client_detail=df_client_detail,
        df_recurrence=df_recurrence,
        location_tables=location_tables,
        demographic_tables=demographic_tables
    )
    values.update({
        "FECHA_INICIO": start_local.strftime("%d/%m/%Y %H:%M"),
        "FECHA_FIN": end_local.strftime("%d/%m/%Y %H:%M"),
        "HORA_CORTE": cut_off_time,
    })

    rendered = HTML_TEMPLATE
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered


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
    parser.add_argument("--to", default=env_str("EMAIL_TO", ""), help="Destinatarios del correo.")
    parser.add_argument("--cc", default=env_str("EMAIL_CC", ""), help="CC del correo.")
    parser.add_argument("--subject", default=env_str("EMAIL_SUBJECT", ""), help="Asunto del correo.")
    parser.add_argument("--dry-run", action="store_true", help="Genera Excel pero no envía correo.")
    parser.add_argument("--cut-off-time", default=env_str("CUT_OFF_TIME", "9:00 a.m."), help="Hora de corte del reporte.")

    args = parser.parse_args()
    args.send_email = DEFAULT_SEND_EMAIL
    args.dry_run = DEFAULT_DRY_RUN

    logger = setup_logger()
    start_time = time.time()

    errors: List[str] = []
    detail_rows: List[Dict[str, Any]] = []
    output_path: Optional[Path] = None
    df_client_detail: Optional[pd.DataFrame] = None
    df_recurrence: Optional[pd.DataFrame] = None
    location_tables: Optional[Dict[str, pd.DataFrame]] = None
    demographic_tables: Optional[Dict[str, pd.DataFrame]] = None

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
            "GENESYS_TIMEZONE", "OUTPUT_DIR", "CUT_OFF_TIME", "EMAIL_TO", "EMAIL_CC",
            "EMAIL_SUBJECT", "INCLUDE_SUMMARY_TABLE_IN_EMAIL", "GRAPH_TENANT_ID", "GRAPH_CLIENT_ID",
            "GRAPH_CLIENT_SECRET", "GRAPH_SENDER_EMAIL", "INCLUDE_CLIENT_ANALYSIS",
            "HPR_HOST_ESPEJO", "HPR_PORT", "HPR_USER", "HPR_PASSWORD",
            "HANA_CLIENT_SCHEMA", "HANA_CLIENT_TABLE", "DETAIL_PAGE_SIZE"
        ])
        logger.info("Modo fecha: %s", date_mode)
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
            total_manejo_sin_cola = int(pd.to_numeric(df_detail.get("Manejo", 0), errors="coerce").fillna(0).sum())
            logger.info("Total Manejo obtenido sin agrupar por cola: %s", total_manejo_sin_cola)
            df_detail = df_detail.sort_values(
                ["Inicio del intervalo", "Nombre de código de conclusión", "Nombre de cola"],
                ascending=[True, True, True]
            )

        df_summary = build_summary(df_detail)

        if env_bool("INCLUDE_CLIENT_ANALYSIS", True):
            try:
                df_calls = query_conclusion_call_details(
                    config,
                    token,
                    start_utc,
                    end_utc,
                    wrapup_catalog,
                    logger
                )
                external_tags = df_calls.get("externalTag", pd.Series(dtype=str)).dropna().astype(str).tolist() if not df_calls.empty else []
                try:
                    df_demo = query_client_demographics(config, external_tags, logger)
                except Exception as hana_exc:
                    logger.exception(
                        "No se pudo consultar HANA espejo. El reporte continuara sin demografia: %s",
                        hana_exc
                    )
                    df_demo = pd.DataFrame(columns=["ETIQUETA_EXTERNA"] + DEMOGRAPHIC_COLUMNS)

                df_client_detail, df_recurrence, location_tables, demographic_tables = build_client_analysis(df_calls, df_demo)
                logger.info("Detalle Clientes generado: %s filas", 0 if df_client_detail is None else len(df_client_detail))
                logger.info("Recurrencia generada: %s filas", 0 if df_recurrence is None else len(df_recurrence))
            except Exception as detail_exc:
                logger.exception(
                    "No se pudo construir recurrencia/ubicacion/demografia. El reporte base continuara: %s",
                    detail_exc
                )
                df_client_detail = pd.DataFrame()
                df_recurrence = pd.DataFrame()
                location_tables = {}
                demographic_tables = {}
        else:
            logger.info("Analisis de clientes omitido por parametro INCLUDE_CLIENT_ANALYSIS=false.")

        timestamp = datetime.now(ZoneInfo(config.timezone_name)).strftime("%Y%m%d_%H%M%S")
        output_path = Path(config.output_dir) / f"Reporte_Conclusiones_NBDA_AOL_{timestamp}.xlsx"

        create_excel(
            df_detail,
            df_summary,
            output_path,
            logger,
            df_client_detail=df_client_detail,
            df_recurrence=df_recurrence,
            location_tables=location_tables,
            demographic_tables=demographic_tables
        )

        if args.send_email and not args.dry_run:
            to_recipients = split_recipients(args.to)
            cc_recipients = split_recipients(args.cc)

            if not to_recipients:
                logger.warning(
                    "Correo no enviado: no hay destinatarios configurados en EMAIL_TO. "
                    "El Excel fue generado correctamente."
                )
            else:
                include_summary_table = env_bool("INCLUDE_SUMMARY_TABLE_IN_EMAIL", True)
                cut_off_time = env_str("CUT_OFF_TIME", args.cut_off_time or "9:00 a.m.")
                subject_base = args.subject.strip() or "Reporte Acumulado de Conclusiones NBDA y AOL"
                subject = f"{subject_base} - Corte {cut_off_time}"
                body_html = render_email_html(
                    df_summary,
                    start_local,
                    end_local,
                    cut_off_time,
                    include_table=include_summary_table,
                    df_client_detail=df_client_detail,
                    df_recurrence=df_recurrence,
                    location_tables=location_tables,
                    demographic_tables=demographic_tables
                )

                try:
                    send_email_with_attachment(
                        config,
                        to_recipients,
                        cc_recipients,
                        subject,
                        body_html,
                        output_path,
                        logger
                    )
                except Exception as email_exc:
                    logger.exception(
                        "Error enviando correo por Microsoft Graph. "
                        "El Excel ya fue generado y se conserva disponible: %s",
                        email_exc
                    )

        elif args.send_email and args.dry_run:
            logger.warning("DRY RUN interno activo. No se enviará correo.")

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
