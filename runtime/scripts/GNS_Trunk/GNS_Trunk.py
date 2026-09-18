#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GNS_Trunk_Divisiones_JOB.py
Reporte de volumen de llamadas por DivisiÃ³n de Genesys Cloud usando Analytics Details Jobs, con filtro opcional por troncal.

Uso principal:
- Ejecutar desde PyFlow Manager.
- Si no se colocan fechas, consulta desde 2026-01-01 hasta hoy.
- Genera un Excel con resumen general, resumen mensual por DivisiÃ³n y, opcionalmente, detalle de conversaciones.

IMPORTANTE:
Genesys Cloud Analytics no siempre expone el nombre/id de la troncal directamente en conversation details.
Para esta troncal especÃ­fica se usa la regla operativa mÃ¡s confiable:
- Trunk_SBC_200.3.194.151_Tigo_2 / Trunk ID 7b99de49-f612-48ab-9c0c-6d8e25aa52ff
- DNIS o Session DNIS inicia con 2275.

Estrategia:
1) Consulta conversaciones de voz con Analytics Details Jobs.
2) Prefiltra por direcciÃ³n inbound cuando aplica.
3) Filtra localmente por prefijo DNIS/Session DNIS 2275 para evitar falsos positivos del modo EDGE.
4) Agrupa por DivisiÃ³n usando la DivisiÃ³n de la cola, usuario, flujo o campaÃ±a encontrada en la conversaciÃ³n.

Requiere:
pip install requests pandas openpyxl
"""

# =============================================================================
# PYFLOW_PARAMS
# =============================================================================
# IMPORTANTE:
# PyFlow Manager detecta este bloque para crear los parÃ¡metros y mapear
# automÃ¡ticamente las Variables Globales. Debe ser un DICCIONARIO, no una lista.

PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Genesys Region / Domain", "required": True},
    "TRUNK_NAME": {"type": "text", "label": "Nombre de troncal", "required": False, "default": "Trunk_SBC_200.3.194.151_Tigo_2", "description": "Nombre/base de la troncal para documentar el reporte."},
    "TRUNK_ID": {"type": "text", "label": "Trunk ID", "required": False, "default": "7b99de49-f612-48ab-9c0c-6d8e25aa52ff", "description": "ID de la troncal encontrada en /api/v2/telephony/providers/edges/trunks."},
    "TRUNK_BASE_ID": {"type": "text", "label": "Trunk Base ID", "required": False, "default": "5df5c1fe-86d6-4119-b08a-ef4eceb16eb0"},
    "START_DATE": {"type": "date", "label": "Fecha inicial local", "required": False, "default": "2026-01-01"},
    "END_DATE": {"type": "date", "label": "Fecha final local", "required": False},
    "TRUNK_DNIS_PREFIXES": {"type": "text", "label": "Prefijos ANI/DNIS de la troncal", "required": False, "default": "2275", "description": "Prefijos separados por coma. Se comparan contra ANI, DNIS y Session DNIS para soportar outbound con otra mascara."},
    "TRUNK_NUMBERS": {"type": "text", "label": "ANI/DNIS exactos opcionales", "required": False, "default": "", "description": "Numeros exactos separados por coma. Use este campo para mascaras especificas que no compartan el prefijo 2275."},
    "TRUNK_EDGE_IDS": {"type": "text", "label": "Edge IDs troncal opcionales", "required": False, "default": "", "description": "Edge IDs historicos separados por coma si la API de trunks actual no coincide con el periodo."},
    "CALL_DIRECTION": {"type": "select", "label": "Direccion de llamada", "required": True, "options": ["OUTBOUND", "INBOUND", "TODAS"], "default": "OUTBOUND", "description": "Permite filtrar llamadas salientes, entrantes o todas desde el front."},
    "OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida del Excel", "required": False, "default": "exports"},
    "EXPORT_DETAIL": {"type": "select", "label": "Exportar detalle", "required": True, "options": ["NO", "SI"], "default": "NO"},
    "FILTER_MODE": {"type": "select", "label": "Modo de filtro", "required": True, "options": ["EDGE", "AUTO", "DNIS_PREFIX", "DNIS", "TODO"], "default": "EDGE", "description": "EDGE filtra por los Edge IDs asociados al nombre de troncal. AUTO usa Edge primero y 2275 solo como respaldo. TODO trae todas las llamadas de voz segun direccion y periodo."},
    "CHUNK_DAYS": {"type": "number", "label": "DÃ­as por bloque para crear Jobs", "required": False, "default": "7"},
    "PAGE_SIZE": {"type": "number", "label": "TamaÃ±o de pÃ¡gina resultados Job", "required": False, "default": "1000"},
    "JOB_WAIT_SECONDS": {"type": "number", "label": "Segundos entre validaciones del Job", "required": False, "default": "10"},
    "MAX_WAIT_MINUTES": {"type": "number", "label": "Tiempo mÃ¡ximo de espera por Job", "required": False, "default": "60"},
    "REQUEST_TIMEOUT_SECONDS": {"type": "number", "label": "Timeout HTTP segundos", "required": False, "default": "240"}
}
import argparse
import base64
import json
import logging
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    import requests
except ImportError as exc:
    raise SystemExit("Falta instalar requests. Ejecuta: pip install requests") from exc

try:
    import pandas as pd
except ImportError as exc:
    raise SystemExit("Falta instalar pandas/openpyxl. Ejecuta: pip install pandas openpyxl") from exc


# =============================================================================
# Logging
# =============================================================================

def setup_logging() -> logging.Logger:
    logger = logging.getLogger("GNS_Trunk_Divisiones")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


log = setup_logging()

EXCEL_MAX_ROWS = 1_048_576
EXCEL_MAX_DATA_ROWS = EXCEL_MAX_ROWS - 1
LOCAL_TIMEZONE = timezone(timedelta(hours=-6), "America/Tegucigalpa")

DEFAULT_TRUNK_NAME = "Trunk_SBC_200.3.194.151_Tigo_2"
DEFAULT_TRUNK_ID = "7b99de49-f612-48ab-9c0c-6d8e25aa52ff"
DEFAULT_TRUNK_BASE_ID = "5df5c1fe-86d6-4119-b08a-ef4eceb16eb0"
DEFAULT_TRUNK_DNIS_PREFIXES = "2275"
DEFAULT_TRUNK_PROXY = "200.3.194.151:5060"

DIAGNOSTIC_SAMPLE_LIMIT = 100
DIAGNOSTIC_COUNTER_LIMIT = 300
DIAGNOSTIC_UNMATCHED_SAMPLES: List[Dict[str, Any]] = []
DIAGNOSTIC_COUNTERS: Dict[str, Counter] = defaultdict(Counter)
DIAGNOSTIC_SECONDS: Dict[str, Counter] = defaultdict(Counter)


# =============================================================================
# Utilidades de parÃ¡metros
# =============================================================================

def clean_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    if value.lower() in {"none", "null", "<vacÃ­o>", "vacio"}:
        return ""
    return value


def only_digits(value: Any) -> str:
    return re.sub(r"\D+", "", clean_value(value))


def env_or_default(name: str, default: str = "") -> str:
    return clean_value(os.getenv(name, default))


def pyflow_progress(value: int) -> None:
    value = max(0, min(100, int(value)))
    print(f"PYFLOW_PROGRESS={value}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reporte de llamadas por DivisiÃ³n para troncal Genesys Cloud.")
    parser.add_argument("--GENESYS_CLIENT_ID", default=env_or_default("GENESYS_CLIENT_ID"))
    parser.add_argument("--GENESYS_CLIENT_SECRET", default=env_or_default("GENESYS_CLIENT_SECRET"))
    parser.add_argument("--GENESYS_REGION", default=env_or_default("GENESYS_REGION", env_or_default("GENESYS_CLOUD_REGION", "mypurecloud.com")))
    parser.add_argument("--TRUNK_NAME", default=env_or_default("TRUNK_NAME", DEFAULT_TRUNK_NAME))
    parser.add_argument("--TRUNK_ID", default=env_or_default("TRUNK_ID", DEFAULT_TRUNK_ID))
    parser.add_argument("--TRUNK_BASE_ID", default=env_or_default("TRUNK_BASE_ID", DEFAULT_TRUNK_BASE_ID))
    parser.add_argument("--START_DATE", default=env_or_default("START_DATE", "2026-01-01"))
    parser.add_argument("--END_DATE", default=env_or_default("END_DATE", ""))
    parser.add_argument("--TRUNK_DNIS_PREFIXES", default=env_or_default("TRUNK_DNIS_PREFIXES", DEFAULT_TRUNK_DNIS_PREFIXES))
    parser.add_argument("--TRUNK_NUMBERS", default=env_or_default("TRUNK_NUMBERS", ""))
    parser.add_argument("--TRUNK_EDGE_IDS", default=env_or_default("TRUNK_EDGE_IDS", ""))
    parser.add_argument("--CALL_DIRECTION", default=env_or_default("CALL_DIRECTION", "OUTBOUND"))
    parser.add_argument("--OUTPUT_DIR", default=env_or_default("OUTPUT_DIR", "exports"))
    parser.add_argument("--EXPORT_DETAIL", default=env_or_default("EXPORT_DETAIL", "NO"))
    parser.add_argument("--FILTER_MODE", default=env_or_default("FILTER_MODE", "EDGE"))
    parser.add_argument("--CHUNK_DAYS", default=env_or_default("CHUNK_DAYS", "7"))
    parser.add_argument("--PAGE_SIZE", default=env_or_default("PAGE_SIZE", "1000"))
    parser.add_argument("--JOB_WAIT_SECONDS", default=env_or_default("JOB_WAIT_SECONDS", "10"))
    parser.add_argument("--MAX_WAIT_MINUTES", default=env_or_default("MAX_WAIT_MINUTES", "60"))
    parser.add_argument("--REQUEST_TIMEOUT_SECONDS", default=env_or_default("REQUEST_TIMEOUT_SECONDS", "240"))
    return parser.parse_args()


def normalize_region(region: str) -> Tuple[str, str]:
    """
    Acepta mypurecloud.com, usw2.pure.cloud, https://api.mypurecloud.com, etc.
    Devuelve (login_base, api_base).
    """
    region = clean_value(region)
    if not region:
        region = "mypurecloud.com"

    region = region.replace("https://", "").replace("http://", "").strip("/")
    if region.startswith("api."):
        domain = region[4:]
    elif region.startswith("login."):
        domain = region[6:]
    else:
        domain = region

    login_base = f"https://login.{domain}"
    api_base = f"https://api.{domain}"
    return login_base, api_base


def parse_date_yyyy_mm_dd(value: str, fallback: Optional[date] = None) -> date:
    value = clean_value(value)
    if not value:
        if fallback is None:
            raise ValueError("Fecha vacÃ­a sin fallback")
        return fallback
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def daterange_chunks(start: date, end_exclusive: date, chunk_days: int) -> Iterable[Tuple[date, date]]:
    current = start
    while current < end_exclusive:
        nxt = min(current + timedelta(days=chunk_days), end_exclusive)
        yield current, nxt
        current = nxt


def iso_interval(start_day: date, end_day_exclusive: date) -> str:
    start_dt = datetime.combine(start_day, datetime.min.time(), tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)
    end_dt = datetime.combine(end_day_exclusive, datetime.min.time(), tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)
    return f"{start_dt.isoformat().replace('+00:00', 'Z')}/{end_dt.isoformat().replace('+00:00', 'Z')}"


def interval_bounds_utc(start_day: date, end_day_exclusive: date) -> Tuple[datetime, datetime]:
    start_dt = datetime.combine(start_day, datetime.min.time(), tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)
    end_dt = datetime.combine(end_day_exclusive, datetime.min.time(), tzinfo=LOCAL_TIMEZONE).astimezone(timezone.utc)
    return start_dt, end_dt


def parse_genesys_datetime(value: Any) -> Optional[datetime]:
    text = clean_value(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def conversation_duration_seconds(start_value: Any, end_value: Any) -> int:
    start_dt = parse_genesys_datetime(start_value)
    end_dt = parse_genesys_datetime(end_value)
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0
    return int((end_dt - start_dt).total_seconds())

def segment_duration_seconds(segment: Dict[str, Any]) -> int:
    """Devuelve la duraciÃ³n de un segmento Genesys en segundos.

    Usa segmentStart/segmentEnd cuando estÃ¡n disponibles. Si faltan o son invÃ¡lidos,
    devuelve 0 para evitar inflar mÃ©tricas.
    """
    start_dt = parse_genesys_datetime(segment.get("segmentStart"))
    end_dt = parse_genesys_datetime(segment.get("segmentEnd"))
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0
    return int((end_dt - start_dt).total_seconds())


def merge_interval_seconds(intervals: List[Tuple[datetime, datetime]]) -> int:
    """Suma intervalos reales sin duplicar traslapes ni huecos entre segmentos."""
    valid = sorted((start, end) for start, end in intervals if start and end and end > start)
    if not valid:
        return 0

    merged: List[Tuple[datetime, datetime]] = []
    cur_start, cur_end = valid[0]
    for start, end in valid[1:]:
        if start <= cur_end:
            if end > cur_end:
                cur_end = end
        else:
            merged.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))

    return int(sum((end - start).total_seconds() for start, end in merged))


def extract_time_metrics(conversation: Dict[str, Any]) -> Dict[str, int]:
    """Calcula tiempos sin inflar por segmentos simultaneos o rangos con huecos.

    Para comparar contra factura de troncal se usa tiempo_cliente_linea_segundos como base:
    suma la union de los segmentos del participante customer. Esto evita el error comun de
    tomar primer segmento customer hasta ultimo segmento customer, que puede incluir esperas,
    transferencias, callbacks o huecos largos dentro de una misma conversacion.
    """
    metrics = {
        "tiempo_conversacion_segundos": conversation_duration_seconds(
            conversation.get("conversationStart"), conversation.get("conversationEnd")
        ),
        "tiempo_cliente_linea_segundos": 0,
        "tiempo_facturable_segundos": 0,
        "tiempo_agente_interact_segundos": 0,
        "tiempo_cola_segundos": 0,
        "tiempo_ivr_flujo_segundos": 0,
        "tiempo_hold_segundos": 0,
        "tiempo_acw_segundos": 0,
        "tiempo_alerta_agente_segundos": 0,
    }

    customer_intervals: List[Tuple[datetime, datetime]] = []

    for participant in conversation.get("participants", []) or []:
        purpose = clean_value(participant.get("purpose")).lower()
        for session in participant.get("sessions", []) or []:
            has_flow = bool(session.get("flowId"))
            for segment in session.get("segments", []) or []:
                seg_type = clean_value(segment.get("segmentType")).lower()
                start_dt = parse_genesys_datetime(segment.get("segmentStart"))
                end_dt = parse_genesys_datetime(segment.get("segmentEnd"))
                if not start_dt or not end_dt or end_dt <= start_dt:
                    continue

                dur = int((end_dt - start_dt).total_seconds())

                if purpose == "customer":
                    customer_intervals.append((start_dt, end_dt))

                if purpose == "agent" and seg_type == "interact":
                    metrics["tiempo_agente_interact_segundos"] += dur
                elif purpose == "agent" and seg_type == "alert":
                    metrics["tiempo_alerta_agente_segundos"] += dur
                elif purpose == "agent" and seg_type == "wrapup":
                    metrics["tiempo_acw_segundos"] += dur

                if seg_type == "hold":
                    metrics["tiempo_hold_segundos"] += dur

                if seg_type == "delay" and (purpose == "acd" or segment.get("queueId") or session.get("queueId")):
                    metrics["tiempo_cola_segundos"] += dur

                if purpose in {"ivr", "flow", "bot"} or has_flow:
                    if purpose != "agent":
                        metrics["tiempo_ivr_flujo_segundos"] += dur

    customer_seconds = merge_interval_seconds(customer_intervals)
    metrics["tiempo_cliente_linea_segundos"] = customer_seconds
    metrics["tiempo_facturable_segundos"] = customer_seconds or metrics["tiempo_conversacion_segundos"]

    return metrics

def add_time_formats(row: Dict[str, Any], base_name: str, seconds_value: Any) -> None:
    """Agrega columnas segundos/minutos/hhmmss para una mÃ©trica base."""
    try:
        seconds_int = int(float(seconds_value or 0))
    except Exception:
        seconds_int = 0
    row[f"{base_name}_segundos"] = seconds_int
    row[f"{base_name}_minutos"] = round(seconds_int / 60, 4)
    row[f"{base_name}_hhmmss"] = seconds_to_hhmmss(seconds_int)



def seconds_to_hhmmss(seconds: Any) -> str:
    try:
        total = int(float(seconds or 0))
    except Exception:
        total = 0
    hours, rem = divmod(max(total, 0), 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def split_numbers(value: str) -> Set[str]:
    out: Set[str] = set()
    for part in clean_value(value).split(","):
        p = part.strip()
        if p:
            normalized = normalize_phone(p)
            if normalized:
                out.add(normalized)
    return out


def split_prefixes(value: str) -> Set[str]:
    """Normaliza prefijos separados por coma. Ej.: '2275,5042275'."""
    return split_numbers(value)


def split_text_set(value: str) -> Set[str]:
    out: Set[str] = set()
    for part in clean_value(value).split(","):
        text = clean_value(part)
        if text:
            out.add(text)
    return out


def normalize_phone(value: Any) -> str:
    text = str(value or "")
    digits = re.sub(r"\D+", "", text)
    return digits


def phone_candidates(value: Any) -> Set[str]:
    """
    Devuelve variantes Ãºtiles para comparar DNIS/ANI.
    Ej.: +50422751234 -> {'50422751234', '22751234'}
    """
    digits = normalize_phone(value)
    candidates = {digits} if digits else set()
    if digits.startswith("504") and len(digits) > 8:
        candidates.add(digits[3:])
    return {c for c in candidates if c}


def phone_matches_exact_or_suffix(found_value: Any, configured_numbers: Set[str]) -> bool:
    if not configured_numbers:
        return False
    found_candidates = phone_candidates(found_value)
    configured_candidates: Set[str] = set()
    for configured in configured_numbers:
        configured_candidates.update(phone_candidates(configured))
    for found in found_candidates:
        for configured in configured_candidates:
            if configured and (found == configured or found.endswith(configured) or configured.endswith(found)):
                return True
    return False


def phone_matches_prefix(found_value: Any, prefixes: Set[str]) -> bool:
    if not prefixes:
        return False
    found_candidates = phone_candidates(found_value)
    prefix_candidates: Set[str] = set()
    for prefix in prefixes:
        prefix_candidates.update(phone_candidates(prefix))
    for found in found_candidates:
        for prefix in prefix_candidates:
            if prefix and found.startswith(prefix):
                return True
    return False


# =============================================================================
# Cliente Genesys Cloud
# =============================================================================

class GenesysClient:
    def __init__(self, client_id: str, client_secret: str, region: str, max_retries: int = 6, request_timeout: int = 240):
        self.client_id = clean_value(client_id)
        self.client_secret = clean_value(client_secret)
        self.login_base, self.api_base = normalize_region(region)
        self.max_retries = max_retries
        self.request_timeout = max(60, int(request_timeout or 240))
        self.token = ""
        self.session = requests.Session()

    def authenticate(self) -> None:
        if not self.client_id or not self.client_secret:
            raise RuntimeError("GENESYS_CLIENT_ID y GENESYS_CLIENT_SECRET son requeridos.")

        url = f"{self.login_base}/oauth/token"
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        auth = base64.b64encode(raw).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {"grant_type": "client_credentials"}

        log.info("Autenticando contra Genesys Cloud: %s", self.login_base)
        resp = requests.post(url, headers=headers, data=data, timeout=60)
        if resp.status_code >= 400:
            raise RuntimeError(f"Error autenticando Genesys Cloud {resp.status_code}: {resp.text[:800]}")

        payload = resp.json()
        self.token = payload["access_token"]
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        })
        log.info("AutenticaciÃ³n exitosa.")

    def request(self, method: str, path: str, **kwargs) -> Any:
        url = path if path.startswith("http") else f"{self.api_base}{path}"
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=self.request_timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                sleep_s = min(90, 5 * attempt)
                log.warning(
                    "API %s %s fallÃ³ por conexiÃ³n/timeout. Reintento %s/%s en %ss. Detalle: %s",
                    method,
                    path,
                    attempt,
                    self.max_retries,
                    sleep_s,
                    exc
                )
                time.sleep(sleep_s)
                continue

            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_s = int(retry_after)
                else:
                    sleep_s = min(60, 2 ** attempt)
                log.warning("API %s %s devolviÃ³ %s. Reintento %s/%s en %ss.",
                            method, path, resp.status_code, attempt, self.max_retries, sleep_s)
                time.sleep(sleep_s)
                continue

            if resp.status_code == 401 and attempt == 1:
                log.warning("Token expirado/no vÃ¡lido. Reautenticando.")
                self.authenticate()
                continue

            if resp.status_code >= 400:
                raise RuntimeError(f"Error API {method} {path} {resp.status_code}: {resp.text[:1200]}")

            if not resp.text:
                return None
            return resp.json()

        raise RuntimeError(f"No fue posible completar API {method} {path} despuÃ©s de {self.max_retries} reintentos. Ãšltimo error: {last_error}")

    def get_all_pages(self, path: str, key: str = "entities", page_size: int = 100) -> List[Dict[str, Any]]:
        page_number = 1
        items: List[Dict[str, Any]] = []
        while True:
            sep = "&" if "?" in path else "?"
            p = f"{path}{sep}pageSize={page_size}&pageNumber={page_number}"
            data = self.request("GET", p)
            entities = data.get(key, []) if isinstance(data, dict) else []
            items.extend(entities)
            page_count = data.get("pageCount") or 0
            if not entities or (page_count and page_number >= page_count):
                break
            page_number += 1
        return items



# =============================================================================
# TelefonÃ­a / Trunks
# =============================================================================

def get_nested(obj: Dict[str, Any], path: str, default: str = "") -> Any:
    cur: Any = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return default
    return cur if cur is not None else default


def list_trunks(gc: GenesysClient, trunk_name: str = "") -> Tuple[List[Dict[str, Any]], Set[str], str]:
    """Devuelve inventario de trunks y edgeIds relacionados al nombre de troncal."""
    rows: List[Dict[str, Any]] = []
    edge_ids: Set[str] = set()
    target = clean_value(trunk_name).lower()
    try:
        trunks = gc.get_all_pages("/api/v2/telephony/providers/edges/trunks", page_size=100)
    except Exception as exc:
        log.warning("No se pudo consultar inventario de trunks: %s", exc)
        return rows, edge_ids, "No se pudo consultar inventario de trunks"

    for t in trunks:
        name = clean_value(t.get("name"))
        trunk_base_name = clean_value(get_nested(t, "trunkBase.name"))
        blob = json.dumps(t, ensure_ascii=False).lower()
        matched = bool(target and (target in name.lower() or target in trunk_base_name.lower() or target in blob))
        edge_id = clean_value(get_nested(t, "edge.id"))
        if matched and edge_id:
            edge_ids.add(edge_id)
        rows.append({
            "coincide_trunk_name": "SI" if matched else "NO",
            "trunk_id": clean_value(t.get("id")),
            "trunk_name": name,
            "state": clean_value(t.get("state")),
            "trunk_type": clean_value(t.get("trunkType")),
            "trunk_base_id": clean_value(get_nested(t, "trunkBase.id")),
            "trunk_base_name": trunk_base_name,
            "edge_id": edge_id,
            "edge_name": clean_value(get_nested(t, "edge.name")),
            "edge_group": clean_value(get_nested(t, "edgeGroup.name")),
            "enabled": t.get("enabled"),
            "in_service": t.get("inService"),
            "connected": get_nested(t, "connectedStatus.connected", ""),
            "connected_state_time": clean_value(get_nested(t, "connectedStatus.connectedStateTime")),
            "ip_status_address": clean_value(get_nested(t, "ipStatus.address")),
            "proxy_address_list": ", ".join(t.get("proxyAddressList") or []),
            "self_uri": clean_value(t.get("selfUri")),
        })
    note = f"Trunks encontrados: {len(rows)}. Edges asociados al TRUNK_NAME: {len(edge_ids)}"
    return rows, edge_ids, note


def collect_session_values(conversation: Dict[str, Any]) -> Dict[str, Set[str]]:
    values = {"edge_ids": set(), "anis": set(), "dniss": set(), "directions": set(), "peer_ids": set(), "providers": set()}
    for participant in conversation.get("participants", []) or []:
        for session in participant.get("sessions", []) or []:
            for k in ("edgeId", "edgeId".lower()):
                v = session.get(k)
                if v:
                    values["edge_ids"].add(str(v))
            for k in ("ani",):
                v = session.get(k)
                if v:
                    values["anis"].add(str(v))
            for k in ("dnis", "sessionDnis"):
                v = session.get(k)
                if v:
                    values["dniss"].add(str(v))
            for k in ("direction",):
                v = session.get(k)
                if v:
                    values["directions"].add(str(v))
            for k in ("peerId",):
                v = session.get(k)
                if v:
                    values["peer_ids"].add(str(v))
            for k in ("provider",):
                v = session.get(k)
                if v:
                    values["providers"].add(str(v))
    return values


def add_diagnostic_counter(name: str, values: Iterable[Any], seconds_value: int = 0) -> None:
    counter = DIAGNOSTIC_COUNTERS[name]
    seconds_counter = DIAGNOSTIC_SECONDS[name]
    for value in values:
        text = clean_value(value)
        if not text:
            continue
        if text in counter or len(counter) < DIAGNOSTIC_COUNTER_LIMIT:
            counter[text] += 1
            seconds_counter[text] += int(seconds_value or 0)
        else:
            counter["__otros__"] += 1
            seconds_counter["__otros__"] += int(seconds_value or 0)


def register_conversation_diagnostics(conversation: Dict[str, Any], matched: bool, match_method: str = "") -> None:
    vals = collect_session_values(conversation)
    seconds_value = conversation_duration_seconds(conversation.get("conversationStart"), conversation.get("conversationEnd"))
    add_diagnostic_counter("edge_ids", vals.get("edge_ids", set()), seconds_value)
    add_diagnostic_counter("providers", vals.get("providers", set()), seconds_value)
    add_diagnostic_counter("directions", vals.get("directions", set()), seconds_value)
    add_diagnostic_counter("peer_ids", vals.get("peer_ids", set()), seconds_value)
    add_diagnostic_counter("ani", vals.get("anis", set()), seconds_value)
    add_diagnostic_counter("dnis", vals.get("dniss", set()), seconds_value)
    add_diagnostic_counter("ani_prefijo_4", [only_digits(v)[:4] for v in vals.get("anis", set())], seconds_value)
    add_diagnostic_counter("dnis_prefijo_4", [only_digits(v)[:4] for v in vals.get("dniss", set())], seconds_value)
    add_diagnostic_counter("match_method", [match_method or ("MATCH" if matched else "NO_MATCH")], seconds_value)

    if matched or len(DIAGNOSTIC_UNMATCHED_SAMPLES) >= DIAGNOSTIC_SAMPLE_LIMIT:
        return

    participant_purposes: Set[str] = set()
    session_keys: Set[str] = set()
    segment_keys: Set[str] = set()
    protocol_call_ids: Set[str] = set()
    destination_addresses: Set[str] = set()
    for participant in conversation.get("participants", []) or []:
        purpose = clean_value(participant.get("purpose"))
        if purpose:
            participant_purposes.add(purpose)
        for session in participant.get("sessions", []) or []:
            session_keys.update(str(k) for k in session.keys())
            if session.get("protocolCallId"):
                protocol_call_ids.add(clean_value(session.get("protocolCallId")))
            for destination in session.get("destinationAddresses", []) or []:
                destination_addresses.add(clean_value(destination))
            for segment in session.get("segments", []) or []:
                segment_keys.update(str(k) for k in segment.keys())

    blob = json.dumps(conversation, ensure_ascii=False).lower()
    DIAGNOSTIC_UNMATCHED_SAMPLES.append({
        "conversationId": conversation.get("conversationId") or conversation.get("id"),
        "conversationStart": conversation.get("conversationStart"),
        "conversationEnd": conversation.get("conversationEnd"),
        "directions": "; ".join(sorted(vals.get("directions", set()))),
        "ani": "; ".join(sorted(vals.get("anis", set()))),
        "dnis": "; ".join(sorted(vals.get("dniss", set()))),
        "edge_ids": "; ".join(sorted(vals.get("edge_ids", set()))),
        "providers": "; ".join(sorted(vals.get("providers", set()))),
        "peer_ids": "; ".join(sorted(vals.get("peer_ids", set()))),
        "protocol_call_ids": "; ".join(sorted(protocol_call_ids)),
        "destination_addresses": "; ".join(sorted(destination_addresses)),
        "participant_purposes": "; ".join(sorted(participant_purposes)),
        "session_keys": "; ".join(sorted(session_keys)),
        "segment_keys": "; ".join(sorted(segment_keys)),
        "contiene_nombre_trunk": "SI" if DEFAULT_TRUNK_NAME.lower() in blob else "NO",
        "contiene_proxy_tigo": "SI" if "200.3.194.151" in blob else "NO",
        "contiene_tigo": "SI" if "tigo" in blob else "NO",
    })

# =============================================================================
# Caches de administraciÃ³n Genesys
# =============================================================================

class GenesysLookup:
    def __init__(self, gc: GenesysClient):
        self.gc = gc
        self.divisions_by_id: Dict[str, str] = {}
        self.queues_by_id: Dict[str, Dict[str, str]] = {}
        self.users_by_id: Dict[str, Dict[str, str]] = {}
        self.flows_by_id: Dict[str, Dict[str, str]] = {}
        self.campaigns_by_id: Dict[str, Dict[str, str]] = {}

    def load_divisions(self) -> None:
        log.info("Cargando divisiones...")
        try:
            divisions = self.gc.get_all_pages("/api/v2/authorization/divisions", page_size=100)
        except Exception as exc:
            log.warning("No se pudieron cargar divisiones: %s", exc)
            divisions = []

        for d in divisions:
            did = d.get("id")
            name = d.get("name") or did or "Sin DivisiÃ³n"
            if did:
                self.divisions_by_id[did] = name

        log.info("Divisiones cargadas: %s", len(self.divisions_by_id))

    def division_name(self, division_obj: Any) -> str:
        if isinstance(division_obj, dict):
            did = division_obj.get("id")
            name = division_obj.get("name")
            if name:
                return name
            if did:
                return self.divisions_by_id.get(did, did)
        return "Sin DivisiÃ³n"

    def get_queue(self, queue_id: str) -> Dict[str, str]:
        if not queue_id:
            return {}
        if queue_id in self.queues_by_id:
            return self.queues_by_id[queue_id]
        try:
            q = self.gc.request("GET", f"/api/v2/routing/queues/{queue_id}")
            result = {
                "id": queue_id,
                "name": q.get("name", queue_id),
                "division": self.division_name(q.get("division"))
            }
        except Exception as exc:
            log.warning("No se pudo consultar queue %s: %s", queue_id, exc)
            result = {"id": queue_id, "name": queue_id, "division": "Sin DivisiÃ³n"}
        self.queues_by_id[queue_id] = result
        return result

    def get_user(self, user_id: str) -> Dict[str, str]:
        if not user_id:
            return {}
        if user_id in self.users_by_id:
            return self.users_by_id[user_id]
        try:
            u = self.gc.request("GET", f"/api/v2/users/{user_id}")
            result = {
                "id": user_id,
                "name": u.get("name", user_id),
                "division": self.division_name(u.get("division"))
            }
        except Exception as exc:
            log.warning("No se pudo consultar user %s: %s", user_id, exc)
            result = {"id": user_id, "name": user_id, "division": "Sin DivisiÃ³n"}
        self.users_by_id[user_id] = result
        return result

    def get_flow(self, flow_id: str) -> Dict[str, str]:
        if not flow_id:
            return {}
        if flow_id in self.flows_by_id:
            return self.flows_by_id[flow_id]
        try:
            f = self.gc.request("GET", f"/api/v2/flows/{flow_id}")
            result = {
                "id": flow_id,
                "name": f.get("name", flow_id),
                "division": self.division_name(f.get("division"))
            }
        except Exception as exc:
            log.warning("No se pudo consultar flow %s: %s", flow_id, exc)
            result = {"id": flow_id, "name": flow_id, "division": "Sin DivisiÃ³n"}
        self.flows_by_id[flow_id] = result
        return result

    def get_campaign(self, campaign_id: str) -> Dict[str, str]:
        if not campaign_id:
            return {}
        if campaign_id in self.campaigns_by_id:
            return self.campaigns_by_id[campaign_id]
        # Outbound campaigns viven bajo /api/v2/outbound/campaigns/{id}
        try:
            c = self.gc.request("GET", f"/api/v2/outbound/campaigns/{campaign_id}")
            result = {
                "id": campaign_id,
                "name": c.get("name", campaign_id),
                "division": self.division_name(c.get("division"))
            }
        except Exception as exc:
            log.warning("No se pudo consultar campaign %s: %s", campaign_id, exc)
            result = {"id": campaign_id, "name": campaign_id, "division": "Sin DivisiÃ³n"}
        self.campaigns_by_id[campaign_id] = result
        return result


# =============================================================================
# ExtracciÃ³n y anÃ¡lisis de conversaciones
# =============================================================================

def conversation_contains_trunk(
    conversation: Dict[str, Any],
    trunk_name: str,
    trunk_numbers: Set[str],
    trunk_dnis_prefixes: Set[str],
    trunk_edge_ids: Set[str],
    filter_mode: str = "TODO"
) -> Tuple[bool, str]:
    """
    Filtro flexible:
    - TODO: no filtra; trae todas las llamadas de voz.
    - DNIS_PREFIX: filtra por prefijo en ANI, DNIS o Session DNIS. Para esta troncal: 2275.
    - DNIS: filtra por nÃºmeros exactos en TRUNK_NUMBERS, comparando ANI y DNIS.
    - EDGE: filtra por edgeId relacionado al TRUNK_NAME. Puede ser aproximado.
    - AUTO:
        1) Si /telephony/providers/edges/trunks devuelve edgeIds para el nombre/base de troncal, filtra por edgeId.
        2) Si hay TRUNK_NUMBERS, usa DNIS/ANI exacto.
        3) Si hay TRUNK_DNIS_PREFIXES, usa prefijo como respaldo.
        4) Si no hay datos de troncal, trae TODO.
    """
    mode = clean_value(filter_mode).upper() or "TODO"
    trunk_name_clean = clean_value(trunk_name).lower()

    if mode == "TODO" or (mode == "AUTO" and not trunk_name_clean and not trunk_numbers and not trunk_dnis_prefixes):
        return True, "TODO_SIN_FILTRO"

    session_vals = collect_session_values(conversation)

    def match_dnis_prefix() -> Tuple[bool, str]:
        if not trunk_dnis_prefixes:
            return False, ""
        prefix_fields = [
            ("ANI", session_vals.get("anis", set())),
            ("DNIS", session_vals.get("dniss", set())),
        ]
        for field_name, values in prefix_fields:
            for raw in values:
                if phone_matches_prefix(raw, trunk_dnis_prefixes):
                    return True, f"{field_name}_PREFIX_{raw}"
        return False, ""

    def match_numbers() -> Tuple[bool, str]:
        if not trunk_numbers:
            return False, ""
        for raw in list(session_vals.get("anis", set())) + list(session_vals.get("dniss", set())):
            if phone_matches_exact_or_suffix(raw, trunk_numbers):
                return True, f"DNIS_ANI_EXACTO_{raw}"
        return False, ""

    def match_edge() -> bool:
        if not trunk_edge_ids:
            return False
        return bool(session_vals.get("edge_ids", set()) & trunk_edge_ids)

    if mode == "DNIS_PREFIX":
        ok, reason = match_dnis_prefix()
        return (True, reason) if ok else (False, "")

    if mode == "DNIS":
        ok, reason = match_numbers()
        return (True, reason) if ok else (False, "")

    if mode == "EDGE":
        return (True, "EDGE_TRUNK") if match_edge() else (False, "")

    # AUTO: para Tigo con mascaras, priorizar el Edge asociado a la troncal.
    if trunk_name_clean and match_edge():
        return True, "EDGE_TRUNK"

    ok, reason = match_numbers()
    if ok:
        return True, reason

    ok, reason = match_dnis_prefix()
    if ok:
        return True, reason

    # Ãšltimo recurso: buscar el texto del trunk en el JSON, por si Genesys lo expone en otra org.
    if trunk_name_clean and trunk_name_clean in json.dumps(conversation, ensure_ascii=False).lower():
        return True, "TRUNK_NAME_JSON"

    return False, ""


def extract_conversation_objects(conversation: Dict[str, Any]) -> Dict[str, Set[str]]:
    queue_ids: Set[str] = set()
    user_ids: Set[str] = set()
    flow_ids: Set[str] = set()
    campaign_ids: Set[str] = set()

    for participant in conversation.get("participants", []) or []:
        purpose = participant.get("purpose")
        pid = participant.get("userId") or participant.get("id")
        if purpose == "agent" and participant.get("userId"):
            user_ids.add(participant["userId"])

        for session in participant.get("sessions", []) or []:
            for segment in session.get("segments", []) or []:
                qid = segment.get("queueId")
                if qid:
                    queue_ids.add(qid)

            # Campos comunes
            for key in ("queueId",):
                if session.get(key):
                    queue_ids.add(session[key])
            for key in ("flowId",):
                if session.get(key):
                    flow_ids.add(session[key])
            for key in ("outboundCampaignId", "campaignId"):
                if session.get(key):
                    campaign_ids.add(session[key])

        # A veces estÃ¡n a nivel participante
        if participant.get("queueId"):
            queue_ids.add(participant["queueId"])
        if participant.get("flowId"):
            flow_ids.add(participant["flowId"])
        if participant.get("outboundCampaignId"):
            campaign_ids.add(participant["outboundCampaignId"])
        if participant.get("campaignId"):
            campaign_ids.add(participant["campaignId"])

    return {
        "queue_ids": queue_ids,
        "user_ids": user_ids,
        "flow_ids": flow_ids,
        "campaign_ids": campaign_ids
    }


def resolve_division_for_conversation(conversation: Dict[str, Any], lookup: GenesysLookup) -> Tuple[str, str, str]:
    """Devuelve una sola division: la ultima division operativa detectada en la conversacion."""
    candidates: List[Tuple[datetime, str, str]] = []

    def add_candidate(when_value: Any, obj_type: str, obj_id: Any) -> None:
        obj_id_clean = clean_value(obj_id)
        if not obj_id_clean:
            return
        when = parse_genesys_datetime(when_value) or parse_genesys_datetime(conversation.get("conversationEnd")) or parse_genesys_datetime(conversation.get("conversationStart"))
        if when:
            candidates.append((when, obj_type, obj_id_clean))

    for participant in conversation.get("participants", []) or []:
        latest_participant_time: Optional[datetime] = None
        if participant.get("userId") and participant.get("purpose") == "agent":
            latest_participant_time = parse_genesys_datetime(conversation.get("conversationEnd"))

        for session in participant.get("sessions", []) or []:
            session_times: List[datetime] = []
            for segment in session.get("segments", []) or []:
                seg_time = parse_genesys_datetime(segment.get("segmentEnd")) or parse_genesys_datetime(segment.get("segmentStart"))
                if seg_time:
                    session_times.append(seg_time)
                    if latest_participant_time is None or seg_time > latest_participant_time:
                        latest_participant_time = seg_time
                add_candidate(seg_time, "queue", segment.get("queueId"))

            session_time = max(session_times) if session_times else conversation.get("conversationEnd")
            add_candidate(session_time, "queue", session.get("queueId"))
            add_candidate(session_time, "campaign", session.get("outboundCampaignId") or session.get("campaignId"))
            add_candidate(session_time, "flow", session.get("flowId"))

        add_candidate(latest_participant_time, "user", participant.get("userId") if participant.get("purpose") == "agent" else "")
        add_candidate(latest_participant_time, "queue", participant.get("queueId"))
        add_candidate(latest_participant_time, "campaign", participant.get("outboundCampaignId") or participant.get("campaignId"))
        add_candidate(latest_participant_time, "flow", participant.get("flowId"))

    seen: Set[Tuple[str, str]] = set()
    for _, obj_type, obj_id in sorted(candidates, key=lambda item: item[0], reverse=True):
        key = (obj_type, obj_id)
        if key in seen:
            continue
        seen.add(key)

        if obj_type == "queue":
            obj = lookup.get_queue(obj_id)
        elif obj_type == "campaign":
            obj = lookup.get_campaign(obj_id)
        elif obj_type == "flow":
            obj = lookup.get_flow(obj_id)
        elif obj_type == "user":
            obj = lookup.get_user(obj_id)
        else:
            continue

        div = obj.get("division")
        if div and div != "Sin DivisiÃ³n":
            return div, f"ultima_{obj_type}", obj.get("name", obj_id)

    div_ids = conversation.get("divisionIds") or []
    if isinstance(div_ids, list) and len(div_ids) == 1:
        div_id = str(div_ids[0])
        return lookup.divisions_by_id.get(div_id, div_id), "conversation.divisionIds", div_id

    return "Sin Division", "not_found", ""

def create_conversations_job(
    gc: GenesysClient,
    interval: str,
    trunk_numbers: Optional[Set[str]] = None,
    trunk_dnis_prefixes: Optional[Set[str]] = None,
    filter_mode: str = "TODO",
    call_direction: str = "OUTBOUND"
) -> str:
    """Crea un Analytics Conversation Details Job para un intervalo."""
    predicates: List[Dict[str, Any]] = [
        {"dimension": "mediaType", "value": "voice"}
    ]

    direction = clean_value(call_direction).upper() or "OUTBOUND"
    if direction in {"INBOUND", "OUTBOUND"}:
        predicates.append({"dimension": "direction", "value": direction.lower()})

    segment_filters: List[Dict[str, Any]] = [
        {"type": "and", "predicates": predicates}
    ]

    # Si se configuran nÃºmeros exactos, se prefiltran desde Genesys.
    # Para prefijos como 2275 NO se aplica prefiltro API porque en varias orgs
    # el operador matches se comporta como coincidencia exacta; se filtra localmente
    # sobre dnis/sessionDnis para no perder llamadas.
    mode = clean_value(filter_mode).upper()
    if trunk_numbers and mode in {"AUTO", "DNIS"}:
        number_predicates = [
            {"dimension": dimension, "value": number, "operator": "matches"}
            for number in sorted(trunk_numbers)
            for dimension in ("dnis", "ani")
            if clean_value(number)
        ]
        if number_predicates:
            segment_filters.append({
                "type": "or",
                "predicates": number_predicates
            })
            log.info(
                "Job Analytics usarÃ¡ prefiltro DNIS/ANI exacto con %s nÃºmero(s).",
                len(trunk_numbers)
            )

    if trunk_dnis_prefixes and mode in {"AUTO", "DNIS_PREFIX"}:
        log.info(
            "Filtro principal local por prefijo ANI/DNIS/Session DNIS: %s. El Job descargarÃ¡ voz%s y filtrarÃ¡ localmente.",
            ", ".join(sorted(trunk_dnis_prefixes)),
            f" {direction.lower()}" if direction in {"INBOUND", "OUTBOUND"} else ""
        )

    body = {
        "interval": interval,
        "order": "asc",
        "orderBy": "conversationStart",
        "segmentFilters": segment_filters
    }
    data = gc.request("POST", "/api/v2/analytics/conversations/details/jobs", json=body)
    job_id = clean_value((data or {}).get("jobId") or (data or {}).get("id"))
    if not job_id:
        raise RuntimeError(f"No se recibiÃ³ jobId al crear el job. Respuesta: {str(data)[:800]}")
    return job_id


def get_job_status(gc: GenesysClient, job_id: str) -> Dict[str, Any]:
    return gc.request("GET", f"/api/v2/analytics/conversations/details/jobs/{job_id}") or {}


def wait_for_job(gc: GenesysClient, job_id: str, wait_seconds: int, max_wait_minutes: int) -> Dict[str, Any]:
    """Espera hasta que el Job termine. Acepta varios nombres de estados usados por Genesys."""
    terminal_ok = {"FULFILLED", "COMPLETED", "COMPLETE", "DONE", "SUCCESS", "SUCCEEDED"}
    terminal_bad = {"FAILED", "CANCELLED", "CANCELED", "EXPIRED", "ERROR"}
    deadline = time.time() + max(1, max_wait_minutes) * 60
    last_status: Dict[str, Any] = {}
    while time.time() < deadline:
        last_status = get_job_status(gc, job_id)
        status = clean_value(
            last_status.get("state") or last_status.get("status") or last_status.get("jobStatus")
        ).upper()
        percent = last_status.get("percentComplete") or last_status.get("completionPercentage") or ""
        log.info("Job %s | estado: %s%s", job_id, status or "<sin estado>", f" | avance: {percent}" if percent != "" else "")
        if status in terminal_ok:
            return last_status
        if status in terminal_bad:
            raise RuntimeError(f"Job {job_id} finalizÃ³ con estado {status}: {json.dumps(last_status, ensure_ascii=False)[:1200]}")
        time.sleep(max(3, wait_seconds))
    raise RuntimeError(f"Job {job_id} no finalizÃ³ en {max_wait_minutes} minutos. Ãšltimo estado: {json.dumps(last_status, ensure_ascii=False)[:1200]}")


def iter_job_result_pages(gc: GenesysClient, job_id: str, page_size: int) -> Iterable[Tuple[int, List[Dict[str, Any]], Dict[str, Any]]]:
    """Descarga resultados del Job por pÃ¡ginas. Soporta cursor y pageNumber por compatibilidad."""
    cursor = ""
    page_number = 1
    seen_cursors: Set[str] = set()
    total_downloaded = 0
    while True:
        if cursor:
            path = f"/api/v2/analytics/conversations/details/jobs/{job_id}/results?pageSize={page_size}&cursor={cursor}"
        else:
            path = f"/api/v2/analytics/conversations/details/jobs/{job_id}/results?pageSize={page_size}&pageNumber={page_number}"
        started_at = time.time()
        data = gc.request("GET", path) or {}
        conversations = data.get("conversations") or data.get("entities") or data.get("results") or []
        if not conversations:
            log.info(
                "Job %s | descarga finalizada | pÃ¡gina %s sin registros | acumulado descargado: %s",
                job_id,
                page_number,
                total_downloaded
            )
            break

        total_downloaded += len(conversations)
        page_count = data.get("pageCount") or 0
        next_cursor = clean_value(data.get("cursor") or data.get("nextCursor") or data.get("nextPage") or data.get("after"))
        log.info(
            "Job %s | pÃ¡gina %s%s descargada en %.1fs | registros pÃ¡gina: %s | acumulado: %s | cursor: %s",
            job_id,
            page_number,
            f"/{page_count}" if page_count else "",
            time.time() - started_at,
            len(conversations),
            total_downloaded,
            "sÃ­" if next_cursor else "no"
        )
        yield page_number, conversations, data

        # Evitar loops si la API devuelve el mismo cursor.
        if next_cursor and next_cursor not in seen_cursors:
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            page_number += 1
            continue

        if page_count and page_number >= int(page_count):
            break
        if not page_count and len(conversations) < page_size:
            break
        page_number += 1


def iter_job_results(gc: GenesysClient, job_id: str, page_size: int) -> Iterable[Dict[str, Any]]:
    for _, conversations, _ in iter_job_result_pages(gc, job_id, page_size):
        for conv in conversations:
            yield conv


def extract_conversations_for_range_job(
    gc: GenesysClient,
    lookup: GenesysLookup,
    start_day: date,
    end_day_exclusive: date,
    trunk_name: str,
    trunk_id: str,
    trunk_base_id: str,
    trunk_numbers: Set[str],
    trunk_dnis_prefixes: Set[str],
    trunk_edge_ids: Set[str],
    filter_mode: str,
    call_direction: str,
    page_size: int,
    job_wait_seconds: int,
    max_wait_minutes: int,
    progress_start: int = 10,
    progress_end: int = 85,
) -> List[Dict[str, Any]]:
    interval = iso_interval(start_day, end_day_exclusive)
    interval_start_utc, interval_end_utc = interval_bounds_utc(start_day, end_day_exclusive)
    rows: List[Dict[str, Any]] = []
    total_checked = 0
    skipped_no_date = 0
    skipped_out_of_range = 0
    started_at = time.time()

    log.info("Creando Job Analytics para intervalo: %s", interval)
    job_id = create_conversations_job(
        gc,
        interval,
        trunk_numbers=trunk_numbers,
        trunk_dnis_prefixes=trunk_dnis_prefixes,
        filter_mode=filter_mode,
        call_direction=call_direction
    )
    log.info("Job creado: %s", job_id)
    pyflow_progress(progress_start)
    wait_for_job(gc, job_id, job_wait_seconds, max_wait_minutes)

    log.info("Descargando resultados del Job: %s", job_id)
    for page_number, conversations, data in iter_job_result_pages(gc, job_id, page_size):
        page_started_at = time.time()
        page_matched = 0
        page_count = int(data.get("pageCount") or 0)

        if page_count:
            page_progress = progress_start + int(((page_number / max(page_count, 1)) * (progress_end - progress_start)))
            pyflow_progress(page_progress)

        for conv in conversations:
            total_checked += 1
            conv_start = parse_genesys_datetime(conv.get("conversationStart"))
            if conv_start is None:
                skipped_no_date += 1
                continue
            if conv_start < interval_start_utc or conv_start >= interval_end_utc:
                skipped_out_of_range += 1
                continue

            matched, match_method = conversation_contains_trunk(
                conv,
                trunk_name,
                trunk_numbers,
                trunk_dnis_prefixes,
                trunk_edge_ids,
                filter_mode
            )
            register_conversation_diagnostics(conv, matched, match_method)
            if not matched:
                continue

            division, division_source, source_name = resolve_division_for_conversation(conv, lookup)
            conv_id = conv.get("conversationId") or conv.get("id")
            vals = collect_session_values(conv)
            direction = "; ".join(sorted(vals.get("directions", set())))
            ani = "; ".join(sorted(vals.get("anis", set())))
            dnis = "; ".join(sorted(vals.get("dniss", set())))
            edge_ids = "; ".join(sorted(vals.get("edge_ids", set())))
            peer_ids = "; ".join(sorted(vals.get("peer_ids", set())))
            providers = "; ".join(sorted(vals.get("providers", set())))
            time_metrics = extract_time_metrics(conv)
            duration_seconds = time_metrics.get("tiempo_conversacion_segundos", 0)

            row = {
                "conversationId": conv_id,
                "conversationStart": conv.get("conversationStart"),
                "conversationEnd": conv.get("conversationEnd"),
                # Compatibilidad con versiones anteriores: tiempo_real = duraciÃ³n total de conversaciÃ³n.
                "tiempo_real_segundos": duration_seconds,
                "tiempo_real_minutos": round(duration_seconds / 60, 4),
                "tiempo_real_hhmmss": seconds_to_hhmmss(duration_seconds),
                "division": division,
                "division_source": division_source,
                "source_name": source_name,
                "direction": direction,
                "ani": ani,
                "dnis": dnis,
                "trunk_id": trunk_id,
                "trunk_base_id": trunk_base_id,
                "trunk_name": trunk_name,
                "trunk_dnis_prefixes": ", ".join(sorted(trunk_dnis_prefixes)),
                "match_method": match_method,
                "edge_ids": edge_ids,
                "peer_ids": peer_ids,
                "providers": providers,
                "job_id": job_id,
                "interval": interval
            }
            # MÃ©tricas adicionales de tiempo. Esto ayuda a separar duraciÃ³n completa vs tiempo atendido.
            for metric_name, metric_seconds in time_metrics.items():
                base = metric_name[:-9] if metric_name.endswith("_segundos") else metric_name
                add_time_formats(row, base, metric_seconds)
            rows.append(row)
            page_matched += 1

        elapsed = time.time() - page_started_at
        rate = len(conversations) / elapsed if elapsed > 0 else 0
        log.info(
            "Job %s | pÃ¡gina %s procesada | revisadas pÃ¡gina: %s | asociadas pÃ¡gina: %s | revisadas total: %s | asociadas total: %s | %.0f conv/s",
            job_id,
            page_number,
            len(conversations),
            page_matched,
            total_checked,
            len(rows),
            rate
        )

    log.info(
        "Job %s | intervalo %s | revisadas: %s | asociadas: %s | sin fecha: %s | fuera de rango: %s | duracion bloque: %.1f minutos",
        job_id,
        interval,
        total_checked,
        len(rows),
        skipped_no_date,
        skipped_out_of_range,
        (time.time() - started_at) / 60
    )
    pyflow_progress(progress_end)
    return rows


# =============================================================================
# ExportaciÃ³n Excel
# =============================================================================

def autosize_excel(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df.columns, 1):
        max_len = max([len(str(col))] + [len(str(x)) for x in df[col].head(500).fillna("").tolist()])
        worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = min(max_len + 2, 60)


def add_excel_table(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame, table_name: str) -> None:
    """Agrega formato de tabla con filtros. No falla si la hoja estÃ¡ vacÃ­a."""
    if df is None or df.empty:
        return
    try:
        from openpyxl.worksheet.table import Table, TableStyleInfo
        ws = writer.sheets[sheet_name]
        last_row = len(df) + 1
        last_col = len(df.columns)
        ref = f"A1:{ws.cell(row=last_row, column=last_col).coordinate}"
        tab = Table(displayName=table_name, ref=ref)
        style = TableStyleInfo(name="TableStyleMedium9", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        tab.tableStyleInfo = style
        ws.add_table(tab)
        ws.freeze_panes = "A2"
    except Exception as exc:
        log.warning("No se pudo aplicar formato de tabla en %s: %s", sheet_name, exc)


MONTHS_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}


def add_months(year: int, month: int, months: int) -> Tuple[int, int]:
    month_index = (year * 12 + (month - 1)) + months
    return month_index // 12, (month_index % 12) + 1


def billing_period_from_local_date(value: Any) -> Dict[str, str]:
    if pd.isna(value):
        return {
            "periodo_facturado": "Sin fecha",
            "mes_facturado": "Sin fecha",
            "rango_facturado": "Sin fecha",
        }

    bill_year = int(value.year)
    bill_month = int(value.month)
    if int(value.day) >= 26:
        bill_year, bill_month = add_months(bill_year, bill_month, 1)

    start_year, start_month = add_months(bill_year, bill_month, -1)
    start_date = date(start_year, start_month, 26)
    end_date = date(bill_year, bill_month, 25)
    return {
        "periodo_facturado": f"{bill_year:04d}-{bill_month:02d}",
        "mes_facturado": MONTHS_ES.get(bill_month, "Sin fecha"),
        "rango_facturado": f"{start_date:%Y-%m-%d} al {end_date:%Y-%m-%d}",
    }


def enrich_month_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega periodo calendario y periodo facturado Tigo usando conversationStart."""
    if df.empty:
        return df
    out = df.copy()
    dt = pd.to_datetime(out.get("conversationStart"), errors="coerce", utc=True).dt.tz_convert(LOCAL_TIMEZONE)
    out["fecha_local"] = dt.dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
    out["anio"] = dt.dt.year.fillna(0).astype(int)
    out["mes_num"] = dt.dt.month.fillna(0).astype(int)
    out["mes_calendario"] = out["mes_num"].map(MONTHS_ES).fillna("Sin fecha")
    out["periodo_calendario"] = dt.dt.strftime("%Y-%m").fillna("Sin fecha")

    billing_info = dt.map(billing_period_from_local_date)
    billing_df = pd.DataFrame(billing_info.tolist(), index=out.index)
    out = pd.concat([out, billing_df], axis=1)
    out["periodo"] = out["periodo_facturado"]
    out["mes"] = out["mes_facturado"]
    return out


def trunk_metadata_summary(trunk_rows: List[Dict[str, Any]], trunk_name: str, trunk_id: str = "", trunk_base_id: str = "") -> Dict[str, str]:
    """Resume informaciÃ³n relevante de la troncal para agregarla al reporte."""
    base = {
        "trunk_id": clean_value(trunk_id) or DEFAULT_TRUNK_ID,
        "trunk_base_id": clean_value(trunk_base_id) or DEFAULT_TRUNK_BASE_ID,
        "trunk_name": trunk_name if clean_value(trunk_name) else DEFAULT_TRUNK_NAME,
        "trunk_estado": "N/A",
        "trunk_enabled": "N/A",
        "trunk_in_service": "N/A",
        "proxy": DEFAULT_TRUNK_PROXY,
        "edges": "",
        "trunks_detectados": "0",
    }
    if not trunk_rows:
        return base
    df = pd.DataFrame(trunk_rows)

    # Priorizar la troncal exacta por TRUNK_ID; si no estÃ¡, usar coincidencias por nombre.
    selected = df.copy()
    if clean_value(trunk_id) and "trunk_id" in selected.columns:
        exact = selected[selected["trunk_id"].astype(str).str.lower() == clean_value(trunk_id).lower()]
        if not exact.empty:
            selected = exact
    elif "coincide_trunk_name" in selected.columns:
        matched = selected[selected["coincide_trunk_name"].astype(str).str.upper() == "SI"]
        if not matched.empty:
            selected = matched

    def unique_join(col: str, limit: int = 20) -> str:
        if col not in selected.columns:
            return ""
        vals = [str(x) for x in selected[col].dropna().astype(str).unique().tolist() if str(x).strip()]
        vals = sorted(vals)
        return "; ".join(vals[:limit]) + ("; ..." if len(vals) > limit else "")

    base.update({
        "trunk_estado": unique_join("state") or "N/A",
        "trunk_enabled": unique_join("enabled") or "N/A",
        "trunk_in_service": unique_join("in_service") or "N/A",
        "proxy": unique_join("proxy_address_list") or DEFAULT_TRUNK_PROXY,
        "edges": unique_join("edge_name"),
        "trunks_detectados": str(len(selected)),
    })
    return base


TIME_METRIC_SECONDS = [
    "tiempo_real_segundos",  # duraciÃ³n completa conversationEnd - conversationStart
    "tiempo_cliente_linea_segundos",
    "tiempo_facturable_segundos",
    "tiempo_agente_interact_segundos",
    "tiempo_cola_segundos",
    "tiempo_ivr_flujo_segundos",
    "tiempo_hold_segundos",
    "tiempo_acw_segundos",
    "tiempo_alerta_agente_segundos",
]


def ensure_time_metric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Garantiza columnas de tiempo para detalle y resÃºmenes."""
    out = df.copy()
    for col in TIME_METRIC_SECONDS:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
        base = col[:-9] if col.endswith("_segundos") else col
        out[f"{base}_minutos"] = (out[col] / 60).round(4)
        out[f"{base}_hhmmss"] = out[col].map(seconds_to_hhmmss)
    return out


def summarize_time_metrics(grouped: Any) -> pd.DataFrame:
    """Agrega llamadas y suma las mÃ©tricas de tiempo disponibles."""
    agg_spec = {"volumen_llamadas": ("conversationId", "nunique")}
    for col in TIME_METRIC_SECONDS:
        agg_spec[col] = (col, "sum")
    summary = grouped.agg(**agg_spec).reset_index()
    for col in TIME_METRIC_SECONDS:
        base = col[:-9] if col.endswith("_segundos") else col
        summary[f"{base}_minutos"] = (summary[col] / 60).round(4)
        summary[f"{base}_hhmmss"] = summary[col].map(seconds_to_hhmmss)
    if "tiempo_agente_interact_segundos" in summary.columns:
        summary["tmo_agente_interact_minutos"] = summary.apply(
            lambda r: round((float(r.get("tiempo_agente_interact_segundos") or 0) / 60) / float(r.get("volumen_llamadas") or 1), 4),
            axis=1
        )
    if "tiempo_cliente_linea_segundos" in summary.columns:
        summary["duracion_prom_cliente_linea_minutos"] = summary.apply(
            lambda r: round((float(r.get("tiempo_cliente_linea_segundos") or 0) / 60) / float(r.get("volumen_llamadas") or 1), 4),
            axis=1
        )
    return summary


def export_excel(
    rows: List[Dict[str, Any]],
    output_dir: str,
    trunk_name: str,
    trunk_id: str,
    trunk_base_id: str,
    trunk_dnis_prefixes: Set[str],
    call_direction: str,
    start_date: date,
    end_date_inclusive: date,
    export_detail: bool,
    trunk_rows: List[Dict[str, Any]],
    filter_mode: str,
    trunk_numbers: Set[str],
    trunk_edge_ids: Set[str],
    trunk_note: str
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"GNS_Trunk_Tigo_Tiempos_{start_date.strftime('%Y%m%d')}_{end_date_inclusive.strftime('%Y%m%d')}_{timestamp}.xlsx"
    file_path = output_path / filename

    detail_df = enrich_month_columns(pd.DataFrame(rows))
    if detail_df.empty:
        resumen_rango_df = pd.DataFrame(columns=["rango_filtrado", "volumen_total_llamadas", "tiempo_total_minutos"])
        resumen_periodo_df = pd.DataFrame(columns=["periodo", "mes", "rango_facturado", "volumen_total_llamadas", "tiempo_total_minutos"])
        resumen_division_df = pd.DataFrame(columns=["division", "volumen_total_llamadas", "tiempo_total_minutos", "porcentaje_tiempo_total"])
        resumen_periodo_division_df = pd.DataFrame(columns=["periodo", "mes", "rango_facturado", "division", "volumen_total_llamadas", "tiempo_total_minutos", "porcentaje_tiempo_periodo"])
        resumen_metodo_df = pd.DataFrame(columns=["match_method", "volumen_total_llamadas", "tiempo_total_minutos"])
    else:
        unique_detail = detail_df.drop_duplicates(subset=["conversationId"]).copy()
        unique_detail = ensure_time_metric_columns(unique_detail)
        unique_detail["tiempo_total_minutos"] = (unique_detail["tiempo_facturable_segundos"] / 60).round(4)
        resumen_rango_df = pd.DataFrame([{
            "rango_filtrado": f"{start_date:%Y-%m-%d} al {end_date_inclusive:%Y-%m-%d}",
            "volumen_total_llamadas": int(unique_detail["conversationId"].nunique()),
            "tiempo_total_minutos": round(float(unique_detail["tiempo_total_minutos"].sum() or 0), 4),
        }])

        resumen_periodo_df = (
            unique_detail.groupby("periodo", dropna=False)
            .agg(
                mes=("mes", "first"),
                rango_facturado=("rango_facturado", "first"),
                volumen_total_llamadas=("conversationId", "nunique"),
                tiempo_total_minutos=("tiempo_total_minutos", "sum"),
            )
            .reset_index()
            .sort_values("periodo")
        )
        resumen_periodo_df["tiempo_total_minutos"] = resumen_periodo_df["tiempo_total_minutos"].round(4)

        resumen_division_df = (
            unique_detail.groupby("division", dropna=False)
            .agg(
                volumen_total_llamadas=("conversationId", "nunique"),
                tiempo_total_minutos=("tiempo_total_minutos", "sum"),
            )
            .reset_index()
            .sort_values(["tiempo_total_minutos", "division"], ascending=[False, True])
        )
        total_minutes = float(resumen_division_df["tiempo_total_minutos"].sum() or 0)
        resumen_division_df["tiempo_total_minutos"] = resumen_division_df["tiempo_total_minutos"].round(4)
        resumen_division_df["porcentaje_tiempo_total"] = resumen_division_df["tiempo_total_minutos"].apply(
            lambda value: round((float(value or 0) / total_minutes) * 100, 2) if total_minutes else 0
        )

        resumen_periodo_division_df = (
            unique_detail.groupby(["periodo", "division"], dropna=False)
            .agg(
                mes=("mes", "first"),
                rango_facturado=("rango_facturado", "first"),
                volumen_total_llamadas=("conversationId", "nunique"),
                tiempo_total_minutos=("tiempo_total_minutos", "sum"),
            )
            .reset_index()
            .sort_values(["periodo", "tiempo_total_minutos", "division"], ascending=[True, False, True])
        )
        resumen_periodo_division_df = resumen_periodo_division_df[
            ["periodo", "mes", "rango_facturado", "division", "volumen_total_llamadas", "tiempo_total_minutos"]
        ]
        resumen_periodo_division_df["tiempo_total_minutos"] = resumen_periodo_division_df["tiempo_total_minutos"].round(4)
        periodo_totales = resumen_periodo_df.set_index("periodo")["tiempo_total_minutos"].to_dict()
        resumen_periodo_division_df["porcentaje_tiempo_periodo"] = resumen_periodo_division_df.apply(
            lambda row: round((float(row["tiempo_total_minutos"] or 0) / float(periodo_totales.get(row["periodo"], 0))) * 100, 2)
            if float(periodo_totales.get(row["periodo"], 0) or 0) else 0,
            axis=1,
        )
        resumen_metodo_df = (
            unique_detail.groupby("match_method", dropna=False)
            .agg(
                volumen_total_llamadas=("conversationId", "nunique"),
                tiempo_total_minutos=("tiempo_total_minutos", "sum"),
            )
            .reset_index()
            .sort_values(["tiempo_total_minutos", "match_method"], ascending=[False, True])
        )
        resumen_metodo_df["tiempo_total_minutos"] = resumen_metodo_df["tiempo_total_minutos"].round(4)

    trunks_df = pd.DataFrame(trunk_rows)
    if not trunks_df.empty:
        if "coincide_trunk_name" in trunks_df.columns:
            trunks_df = trunks_df[trunks_df["coincide_trunk_name"].astype(str).str.upper().eq("SI")].copy()
        keep_trunk_cols = [
            "trunk_id", "trunk_name", "trunk_base_id", "trunk_base_name", "edge_id", "edge_name",
            "edge_group", "state", "enabled", "in_service", "connected", "ip_status_address", "proxy_address_list"
        ]
        trunks_df = trunks_df[[c for c in keep_trunk_cols if c in trunks_df.columns]]

    diagnostico_campos_rows: List[Dict[str, Any]] = []
    for campo, counter in sorted(DIAGNOSTIC_COUNTERS.items()):
        for valor, cantidad in counter.most_common(100):
            seconds_value = int(DIAGNOSTIC_SECONDS.get(campo, Counter()).get(valor, 0))
            diagnostico_campos_rows.append({
                "campo": campo,
                "valor": valor,
                "cantidad": cantidad,
                "minutos_aprox_conversacion": round(seconds_value / 60, 4),
            })
    diagnostico_campos_df = pd.DataFrame(diagnostico_campos_rows)
    muestra_no_match_df = pd.DataFrame(DIAGNOSTIC_UNMATCHED_SAMPLES)

    parametros_df = pd.DataFrame([
        {"parametro": "direccion", "valor": call_direction},
        {"parametro": "fecha_inicio", "valor": str(start_date)},
        {"parametro": "fecha_fin", "valor": str(end_date_inclusive)},
        {"parametro": "trunk_name", "valor": trunk_name if clean_value(trunk_name) else DEFAULT_TRUNK_NAME},
        {"parametro": "trunk_id", "valor": trunk_id},
        {"parametro": "trunk_base_id", "valor": trunk_base_id},
        {"parametro": "edge_ids_troncal_detectados", "valor": ", ".join(sorted(trunk_edge_ids))},
        {"parametro": "trunk_dnis_prefixes", "valor": ", ".join(sorted(trunk_dnis_prefixes))},
        {"parametro": "trunk_numbers_configurados", "valor": ", ".join(sorted(trunk_numbers))},
        {"parametro": "modo_filtro", "valor": filter_mode},
        {"parametro": "tiempo_usado", "valor": "tiempo_facturable_minutos = union de segmentos customer; si no existe, conversationEnd - conversationStart"},
        {"parametro": "periodo_usado", "valor": "periodo_facturado_tigo = 26 del mes anterior al 25 del mes facturado"},
        {"parametro": "total_conversaciones", "valor": len(detail_df.drop_duplicates(subset=["conversationId"])) if not detail_df.empty else 0},
        {"parametro": "fecha_generacion", "valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
    ])

    diagnostico_df = pd.DataFrame()
    if detail_df.empty:
        diagnostico_df = pd.DataFrame([{
            "tipo": "Sin conversaciones asociadas",
            "detalle": "No se encontraron llamadas con los filtros seleccionados. Valide direccion, periodo y filtros de troncal."
        }])

    detail_exceeds_excel_limit = export_detail and len(detail_df) > EXCEL_MAX_DATA_ROWS
    if detail_exceeds_excel_limit:
        log.warning("El detalle excede el limite de Excel; se omitira la hoja Detalle.")

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        resumen_rango_df.to_excel(writer, index=False, sheet_name="Resumen_Rango")
        resumen_periodo_df.to_excel(writer, index=False, sheet_name="Resumen_Periodo")
        resumen_division_df.to_excel(writer, index=False, sheet_name="Resumen_Division")
        resumen_periodo_division_df.to_excel(writer, index=False, sheet_name="Periodo_Division")
        resumen_metodo_df.to_excel(writer, index=False, sheet_name="Resumen_Metodo")
        parametros_df.to_excel(writer, index=False, sheet_name="Parametros")
        if not trunks_df.empty:
            trunks_df.to_excel(writer, index=False, sheet_name="Trunks_Detectados")
        if not diagnostico_campos_df.empty:
            diagnostico_campos_df.to_excel(writer, index=False, sheet_name="Diagnostico_Campos")
        if not muestra_no_match_df.empty:
            muestra_no_match_df.to_excel(writer, index=False, sheet_name="Muestra_No_Match")
        if not diagnostico_df.empty:
            diagnostico_df.to_excel(writer, index=False, sheet_name="Diagnostico")

        for sheet, df, table in [
            ("Resumen_Rango", resumen_rango_df, "tblResumenRango"),
            ("Resumen_Periodo", resumen_periodo_df, "tblResumenPeriodo"),
            ("Resumen_Division", resumen_division_df, "tblResumenDivision"),
            ("Periodo_Division", resumen_periodo_division_df, "tblPeriodoDivision"),
            ("Resumen_Metodo", resumen_metodo_df, "tblResumenMetodo"),
            ("Parametros", parametros_df, "tblParametros"),
        ]:
            autosize_excel(writer, sheet, df)
            add_excel_table(writer, sheet, df, table)

        if not trunks_df.empty:
            autosize_excel(writer, "Trunks_Detectados", trunks_df)
            add_excel_table(writer, "Trunks_Detectados", trunks_df, "tblTrunksDetectados")

        if not diagnostico_campos_df.empty:
            autosize_excel(writer, "Diagnostico_Campos", diagnostico_campos_df)
            add_excel_table(writer, "Diagnostico_Campos", diagnostico_campos_df, "tblDiagnosticoCampos")

        if not muestra_no_match_df.empty:
            autosize_excel(writer, "Muestra_No_Match", muestra_no_match_df)
            add_excel_table(writer, "Muestra_No_Match", muestra_no_match_df, "tblMuestraNoMatch")

        if not diagnostico_df.empty:
            autosize_excel(writer, "Diagnostico", diagnostico_df)
            add_excel_table(writer, "Diagnostico", diagnostico_df, "tblDiagnostico")

        if export_detail and not detail_exceeds_excel_limit:
            detail_export = detail_df.copy()
            if not detail_export.empty:
                detail_export = ensure_time_metric_columns(detail_export)
                detail_export["tiempo_total_minutos"] = (detail_export["tiempo_facturable_segundos"] / 60).round(4)
                keep_cols = [
                    "conversationId", "fecha_local", "periodo", "mes", "rango_facturado", "periodo_calendario",
                    "division", "direction", "ani", "dnis",
                    "tiempo_total_minutos", "match_method", "division_source", "source_name"
                ]
                detail_export = detail_export[[c for c in keep_cols if c in detail_export.columns]]
            detail_export.to_excel(writer, index=False, sheet_name="Detalle")
            autosize_excel(writer, "Detalle", detail_export)
            add_excel_table(writer, "Detalle", detail_export, "tblDetalle")

    return file_path


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    args = parse_args()

    log.info("=" * 90)
    log.info("INICIO REPORTE TRUNK / DIVISIONES GENESYS CLOUD")
    log.info("=" * 90)

    today = datetime.now(LOCAL_TIMEZONE).date()
    start_day = parse_date_yyyy_mm_dd(args.START_DATE, date(2026, 1, 1))
    end_day_inclusive = parse_date_yyyy_mm_dd(args.END_DATE, today)

    if end_day_inclusive < start_day:
        raise RuntimeError("END_DATE no puede ser menor que START_DATE.")

    end_exclusive = end_day_inclusive + timedelta(days=1)

    try:
        chunk_days = int(clean_value(args.CHUNK_DAYS) or "30")
    except Exception:
        chunk_days = 7
    chunk_days = max(1, min(chunk_days, 31))

    try:
        page_size = int(clean_value(args.PAGE_SIZE) or "1000")
    except Exception:
        page_size = 1000
    page_size = max(25, min(page_size, 5000))

    try:
        job_wait_seconds = int(clean_value(args.JOB_WAIT_SECONDS) or "10")
    except Exception:
        job_wait_seconds = 10
    job_wait_seconds = max(3, min(job_wait_seconds, 120))

    try:
        max_wait_minutes = int(clean_value(args.MAX_WAIT_MINUTES) or "60")
    except Exception:
        max_wait_minutes = 60
    max_wait_minutes = max(5, min(max_wait_minutes, 240))

    try:
        request_timeout = int(clean_value(args.REQUEST_TIMEOUT_SECONDS) or "240")
    except Exception:
        request_timeout = 240
    request_timeout = max(60, min(request_timeout, 900))

    trunk_name = clean_value(args.TRUNK_NAME) or DEFAULT_TRUNK_NAME
    trunk_id = clean_value(args.TRUNK_ID) or DEFAULT_TRUNK_ID
    trunk_base_id = clean_value(args.TRUNK_BASE_ID) or DEFAULT_TRUNK_BASE_ID
    trunk_numbers = split_numbers(args.TRUNK_NUMBERS)
    trunk_dnis_prefixes = split_prefixes(args.TRUNK_DNIS_PREFIXES)
    manual_trunk_edge_ids = split_text_set(args.TRUNK_EDGE_IDS)
    export_detail = clean_value(args.EXPORT_DETAIL).upper() in {"SI", "SÃ", "YES", "TRUE", "1"}
    call_direction = clean_value(args.CALL_DIRECTION).upper() or "OUTBOUND"
    if call_direction not in {"INBOUND", "OUTBOUND", "TODAS"}:
        call_direction = "OUTBOUND"
    filter_mode = clean_value(args.FILTER_MODE).upper() or "TODO"
    if filter_mode not in {"AUTO", "DNIS_PREFIX", "DNIS", "EDGE", "TODO"}:
        filter_mode = "EDGE"

    log.info("ParÃ¡metros aplicados:")
    log.info("- TRUNK_NAME: %s", trunk_name if trunk_name else "<vacÃ­o>")
    log.info("- TRUNK_ID: %s", trunk_id)
    log.info("- TRUNK_BASE_ID: %s", trunk_base_id)
    log.info("- TRUNK_DNIS_PREFIXES: %s", ", ".join(sorted(trunk_dnis_prefixes)) if trunk_dnis_prefixes else "<vacÃ­o>")
    log.info("- TRUNK_EDGE_IDS manuales: %s", ", ".join(sorted(manual_trunk_edge_ids)) if manual_trunk_edge_ids else "<vacÃ­o>")
    log.info("- CALL_DIRECTION: %s", call_direction)
    log.info("- START_DATE: %s", start_day)
    log.info("- END_DATE: %s", end_day_inclusive)
    log.info("- CHUNK_DAYS: %s", chunk_days)
    log.info("- PAGE_SIZE: %s", page_size)
    log.info("- JOB_WAIT_SECONDS: %s", job_wait_seconds)
    log.info("- MAX_WAIT_MINUTES: %s", max_wait_minutes)
    log.info("- REQUEST_TIMEOUT_SECONDS: %s", request_timeout)
    log.info("- TRUNK_NUMBERS configurados: %s", len(trunk_numbers))
    log.info("- FILTER_MODE: %s", filter_mode)
    log.info("- EXPORT_DETAIL: %s", "SI" if export_detail else "NO")
    log.info("- OUTPUT_DIR: %s", args.OUTPUT_DIR)

    gc = GenesysClient(
        client_id=args.GENESYS_CLIENT_ID,
        client_secret=args.GENESYS_CLIENT_SECRET,
        region=args.GENESYS_REGION,
        request_timeout=request_timeout
    )
    pyflow_progress(2)
    gc.authenticate()

    lookup = GenesysLookup(gc)
    lookup.load_divisions()
    pyflow_progress(5)

    trunk_rows, trunk_edge_ids, trunk_note = list_trunks(gc, trunk_name) if trunk_name else ([], set(), "Sin TRUNK_NAME: no se consultÃ³ coincidencia especÃ­fica de trunks; el reporte puede traer todo.")
    log.info("%s", trunk_note)
    if manual_trunk_edge_ids:
        trunk_edge_ids.update(manual_trunk_edge_ids)
        log.info("Edge IDs manuales agregados al filtro: %s", ", ".join(sorted(manual_trunk_edge_ids)))

    # Asegurar que el inventario tenga la troncal exacta aunque el match por nombre no la encuentre.
    if trunk_rows and trunk_id:
        exact_trunk = [r for r in trunk_rows if clean_value(r.get("trunk_id")).lower() == trunk_id.lower()]
        if exact_trunk:
            edge_id = clean_value(exact_trunk[0].get("edge_id"))
            if edge_id:
                trunk_edge_ids.add(edge_id)
            log.info("Troncal exacta localizada por TRUNK_ID. Edge asociado: %s", edge_id or "<no detectado>")

    if filter_mode == "AUTO":
        if trunk_edge_ids or trunk_numbers or trunk_dnis_prefixes or trunk_name:
            effective_mode = "AUTO"
            log.info(
                "AUTO filtrara localmente en este orden: Edge IDs de la troncal (%s), numeros exactos (%s), prefijos (%s).",
                len(trunk_edge_ids),
                len(trunk_numbers),
                ", ".join(sorted(trunk_dnis_prefixes)) if trunk_dnis_prefixes else "<vacio>",
            )
        else:
            effective_mode = "TODO"
    else:
        effective_mode = filter_mode
    log.info("- MODO EFECTIVO: %s", effective_mode)

    chunks_to_run = list(daterange_chunks(start_day, end_exclusive, chunk_days))
    log.info("Bloques a consultar: %s", len(chunks_to_run))

    all_rows: List[Dict[str, Any]] = []
    for chunk_index, (chunk_start, chunk_end) in enumerate(chunks_to_run, start=1):
        block_progress_start = 5 + int(((chunk_index - 1) / max(len(chunks_to_run), 1)) * 85)
        block_progress_end = 5 + int((chunk_index / max(len(chunks_to_run), 1)) * 85)
        log.info(
            "Consultando bloque %s/%s: %s a %s",
            chunk_index,
            len(chunks_to_run),
            chunk_start,
            chunk_end - timedelta(days=1)
        )
        rows = extract_conversations_for_range_job(
            gc=gc,
            lookup=lookup,
            start_day=chunk_start,
            end_day_exclusive=chunk_end,
            trunk_name=trunk_name,
            trunk_id=trunk_id,
            trunk_base_id=trunk_base_id,
            trunk_numbers=trunk_numbers,
            trunk_dnis_prefixes=trunk_dnis_prefixes,
            trunk_edge_ids=trunk_edge_ids,
            filter_mode=effective_mode,
            call_direction=call_direction,
            page_size=page_size,
            job_wait_seconds=job_wait_seconds,
            max_wait_minutes=max_wait_minutes,
            progress_start=block_progress_start,
            progress_end=block_progress_end
        )
        all_rows.extend(rows)
        log.info(
            "Bloque %s/%s completado | asociadas bloque: %s | acumulado asociadas: %s",
            chunk_index,
            len(chunks_to_run),
            len(rows),
            len(all_rows)
        )

    # DeduplicaciÃ³n final
    unique = {}
    for row in all_rows:
        cid = row.get("conversationId")
        if cid and cid not in unique:
            unique[cid] = row
    final_rows = list(unique.values())

    log.info("Conversaciones Ãºnicas identificadas: %s", len(final_rows))
    pyflow_progress(92)

    report_path = export_excel(
        rows=final_rows,
        output_dir=args.OUTPUT_DIR,
        trunk_name=trunk_name,
        trunk_id=trunk_id,
        trunk_base_id=trunk_base_id,
        trunk_dnis_prefixes=trunk_dnis_prefixes,
        call_direction=call_direction,
        start_date=start_day,
        end_date_inclusive=end_day_inclusive,
        export_detail=export_detail,
        trunk_rows=trunk_rows,
        filter_mode=effective_mode,
        trunk_numbers=trunk_numbers,
        trunk_edge_ids=trunk_edge_ids,
        trunk_note=trunk_note
    )

    log.info("Reporte generado correctamente: %s", report_path.resolve())
    pyflow_progress(100)
    log.info("=" * 90)
    log.info("FIN REPORTE TRUNK / DIVISIONES")
    log.info("=" * 90)

    # PyFlow suele capturar stdout; dejamos ruta fÃ¡cil de localizar.
    print(f"OUTPUT_FILE={report_path.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log.exception("Error ejecutando reporte: %s", exc)
        raise SystemExit(1)









