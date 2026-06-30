#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GNS_Trunk_Divisiones_JOB.py
Reporte de volumen de llamadas por División de Genesys Cloud usando Analytics Details Jobs, con filtro opcional por troncal.

Uso principal:
- Ejecutar desde PyFlow Manager.
- Si no se colocan fechas, consulta desde 2026-01-01 hasta hoy.
- Genera un Excel con resumen general, resumen mensual por División y, opcionalmente, detalle de conversaciones.

IMPORTANTE:
Genesys Cloud Analytics no siempre expone el nombre de la troncal directamente en conversation details.
Por eso este script usa una estrategia flexible:
1) Intenta identificar la troncal por coincidencias de texto dentro del detalle de la conversación.
2) Si no encuentra coincidencias por TRUNK_NAME, puede filtrar por números definidos en TRUNK_NUMBERS.
3) Agrupa por División usando la División de la cola, usuario, flujo o campaña encontrada en la conversación.

Requiere:
pip install requests pandas openpyxl
"""

# =============================================================================
# PYFLOW_PARAMS
# =============================================================================
# IMPORTANTE:
# PyFlow Manager detecta este bloque para crear los parámetros y mapear
# automáticamente las Variables Globales. Debe ser un DICCIONARIO, no una lista.

PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Genesys Region / Domain", "required": True},
    "TRUNK_NAME": {"type": "text", "label": "Nombre de troncal (opcional)", "required": False, "default": "Trunk_SBC_200.3.194.151_Tigo_2", "description": "Si se deja vacío y tampoco se colocan DNIS/ANI, el reporte traerá todas las llamadas."},
    "START_DATE": {"type": "date", "label": "Fecha inicial local", "required": False, "default": "2026-01-01"},
    "END_DATE": {"type": "date", "label": "Fecha final local", "required": False},
    "TRUNK_NUMBERS": {"type": "text", "label": "DNIS/ANI asociados a la troncal (opcional)", "required": False, "default": "", "description": "Números separados por coma. Si se deja vacío, se usará modo aproximado por Edge cuando exista TRUNK_NAME; si TRUNK_NAME también está vacío, trae todo."},
    "OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida del Excel", "required": False, "default": "exports"},
    "EXPORT_DETAIL": {"type": "select", "label": "Exportar detalle", "required": True, "options": ["NO", "SI"], "default": "NO"},
    "FILTER_MODE": {"type": "select", "label": "Modo de filtro", "required": True, "options": ["AUTO", "DNIS", "EDGE", "TODO"], "default": "AUTO", "description": "AUTO usa DNIS/ANI si se configuran. Si no hay DNIS/ANI, trae llamadas de voz para evitar reportes vacios; EDGE queda disponible solo si se selecciona manualmente."},
    "CHUNK_DAYS": {"type": "number", "label": "Días por bloque para crear Jobs", "required": False, "default": "30"},
    "PAGE_SIZE": {"type": "number", "label": "Tamaño de página resultados Job", "required": False, "default": "1000"},
    "JOB_WAIT_SECONDS": {"type": "number", "label": "Segundos entre validaciones del Job", "required": False, "default": "10"},
    "MAX_WAIT_MINUTES": {"type": "number", "label": "Tiempo máximo de espera por Job", "required": False, "default": "60"},
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
from collections import defaultdict
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


# =============================================================================
# Utilidades de parámetros
# =============================================================================

def clean_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    if value.lower() in {"none", "null", "<vacío>", "vacio"}:
        return ""
    return value


def env_or_default(name: str, default: str = "") -> str:
    return clean_value(os.getenv(name, default))


def pyflow_progress(value: int) -> None:
    value = max(0, min(100, int(value)))
    print(f"PYFLOW_PROGRESS={value}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reporte de llamadas por División para troncal Genesys Cloud.")
    parser.add_argument("--GENESYS_CLIENT_ID", default=env_or_default("GENESYS_CLIENT_ID"))
    parser.add_argument("--GENESYS_CLIENT_SECRET", default=env_or_default("GENESYS_CLIENT_SECRET"))
    parser.add_argument("--GENESYS_REGION", default=env_or_default("GENESYS_REGION", env_or_default("GENESYS_CLOUD_REGION", "mypurecloud.com")))
    parser.add_argument("--TRUNK_NAME", default=env_or_default("TRUNK_NAME", "Trunk_SBC_200.3.194.151_Tigo_2"))
    parser.add_argument("--START_DATE", default=env_or_default("START_DATE", "2026-01-01"))
    parser.add_argument("--END_DATE", default=env_or_default("END_DATE", ""))
    parser.add_argument("--TRUNK_NUMBERS", default=env_or_default("TRUNK_NUMBERS", ""))
    parser.add_argument("--OUTPUT_DIR", default=env_or_default("OUTPUT_DIR", "exports"))
    parser.add_argument("--EXPORT_DETAIL", default=env_or_default("EXPORT_DETAIL", "NO"))
    parser.add_argument("--FILTER_MODE", default=env_or_default("FILTER_MODE", "AUTO"))
    parser.add_argument("--CHUNK_DAYS", default=env_or_default("CHUNK_DAYS", "30"))
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
            raise ValueError("Fecha vacía sin fallback")
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
            out.add(normalize_phone(p))
    return out


def normalize_phone(value: Any) -> str:
    text = str(value or "")
    digits = re.sub(r"\D+", "", text)
    return digits


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
        log.info("Autenticación exitosa.")

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
                    "API %s %s falló por conexión/timeout. Reintento %s/%s en %ss. Detalle: %s",
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
                log.warning("API %s %s devolvió %s. Reintento %s/%s en %ss.",
                            method, path, resp.status_code, attempt, self.max_retries, sleep_s)
                time.sleep(sleep_s)
                continue

            if resp.status_code == 401 and attempt == 1:
                log.warning("Token expirado/no válido. Reautenticando.")
                self.authenticate()
                continue

            if resp.status_code >= 400:
                raise RuntimeError(f"Error API {method} {path} {resp.status_code}: {resp.text[:1200]}")

            if not resp.text:
                return None
            return resp.json()

        raise RuntimeError(f"No fue posible completar API {method} {path} después de {self.max_retries} reintentos. Último error: {last_error}")

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
# Telefonía / Trunks
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

# =============================================================================
# Caches de administración Genesys
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
            name = d.get("name") or did or "Sin División"
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
        return "Sin División"

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
            result = {"id": queue_id, "name": queue_id, "division": "Sin División"}
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
            result = {"id": user_id, "name": user_id, "division": "Sin División"}
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
            result = {"id": flow_id, "name": flow_id, "division": "Sin División"}
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
            result = {"id": campaign_id, "name": campaign_id, "division": "Sin División"}
        self.campaigns_by_id[campaign_id] = result
        return result


# =============================================================================
# Extracción y análisis de conversaciones
# =============================================================================

def conversation_contains_trunk(
    conversation: Dict[str, Any],
    trunk_name: str,
    trunk_numbers: Set[str],
    trunk_edge_ids: Set[str],
    filter_mode: str = "AUTO"
) -> Tuple[bool, str]:
    """
    Filtro flexible:
    - TODO: no filtra; trae todas las llamadas de voz.
    - DNIS: filtra por TRUNK_NUMBERS.
    - EDGE: filtra por edgeId relacionado al TRUNK_NAME.
    - AUTO:
        1) Si hay TRUNK_NUMBERS, usa DNIS/ANI exacto.
        2) Si hay TRUNK_NAME y se encontraron edgeIds, usa EDGE aproximado.
        3) Si no hay TRUNK_NAME ni TRUNK_NUMBERS, trae TODO.
    """
    mode = clean_value(filter_mode).upper() or "AUTO"
    trunk_name_clean = clean_value(trunk_name).lower()

    if mode == "TODO" or (mode == "AUTO" and not trunk_name_clean and not trunk_numbers):
        return True, "TODO_SIN_FILTRO"

    session_vals = collect_session_values(conversation)

    def match_numbers() -> bool:
        if not trunk_numbers:
            return False
        numbers_found: Set[str] = set()
        for raw in list(session_vals.get("anis", set())) + list(session_vals.get("dniss", set())):
            n = normalize_phone(raw)
            if n:
                numbers_found.add(n)
        for configured in trunk_numbers:
            for found in numbers_found:
                if configured and (configured == found or found.endswith(configured) or configured.endswith(found)):
                    return True
        return False

    def match_edge() -> bool:
        if not trunk_edge_ids:
            return False
        return bool(session_vals.get("edge_ids", set()) & trunk_edge_ids)

    if mode == "DNIS":
        return (True, "DNIS_ANI_EXACTO") if match_numbers() else (False, "")

    if mode == "EDGE":
        return (True, "EDGE_APROXIMADO") if match_edge() else (False, "")

    # AUTO
    if match_numbers():
        return True, "DNIS_ANI_EXACTO"
    if trunk_name_clean and match_edge():
        return True, "EDGE_APROXIMADO"

    # Último recurso: buscar el texto del trunk en el JSON, por si Genesys lo expone en otra org.
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

        # A veces están a nivel participante
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
    """
    Prioridad:
    1. Cola: normalmente representa mejor la operación/división.
    2. Campaña.
    3. Flow.
    4. Usuario/agente.
    """
    # Si Analytics ya trae divisionIds, usarlo primero como fuente directa.
    div_ids = conversation.get("divisionIds") or []
    if isinstance(div_ids, list) and div_ids:
        names = [lookup.divisions_by_id.get(str(d), str(d)) for d in div_ids if d]
        if names:
            return "; ".join(sorted(set(names))), "conversation.divisionIds", "; ".join([str(d) for d in div_ids])

    objs = extract_conversation_objects(conversation)

    queue_names: List[str] = []
    for qid in sorted(objs["queue_ids"]):
        q = lookup.get_queue(qid)
        queue_names.append(q.get("name", qid))
        div = q.get("division")
        if div and div != "Sin División":
            return div, "queue", "; ".join(queue_names)

    campaign_names: List[str] = []
    for cid in sorted(objs["campaign_ids"]):
        c = lookup.get_campaign(cid)
        campaign_names.append(c.get("name", cid))
        div = c.get("division")
        if div and div != "Sin División":
            return div, "campaign", "; ".join(campaign_names)

    flow_names: List[str] = []
    for fid in sorted(objs["flow_ids"]):
        f = lookup.get_flow(fid)
        flow_names.append(f.get("name", fid))
        div = f.get("division")
        if div and div != "Sin División":
            return div, "flow", "; ".join(flow_names)

    user_names: List[str] = []
    for uid in sorted(objs["user_ids"]):
        u = lookup.get_user(uid)
        user_names.append(u.get("name", uid))
        div = u.get("division")
        if div and div != "Sin División":
            return div, "user", "; ".join(user_names)

    # Si no pudo resolver por API, intentar detectar division literal en JSON.
    # Esto ayuda cuando conversation details ya trae objetos division.
    conv_text = conversation
    return "Sin División", "not_found", ""


def create_conversations_job(
    gc: GenesysClient,
    interval: str,
    trunk_numbers: Optional[Set[str]] = None,
    filter_mode: str = "AUTO"
) -> str:
    """Crea un Analytics Conversation Details Job para un intervalo."""
    segment_filters: List[Dict[str, Any]] = [
        {
            "type": "and",
            "predicates": [
                {"dimension": "mediaType", "value": "voice"}
            ]
        }
    ]

    # Si el usuario configura DNIS/ANI, se filtra desde Genesys antes de descargar.
    # Esto evita traer todo el universo de llamadas para luego descartarlo localmente.
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
                "Job Analytics usará prefiltro DNIS/ANI con %s número(s). Esto reduce la descarga.",
                len(trunk_numbers)
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
        raise RuntimeError(f"No se recibió jobId al crear el job. Respuesta: {str(data)[:800]}")
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
            raise RuntimeError(f"Job {job_id} finalizó con estado {status}: {json.dumps(last_status, ensure_ascii=False)[:1200]}")
        time.sleep(max(3, wait_seconds))
    raise RuntimeError(f"Job {job_id} no finalizó en {max_wait_minutes} minutos. Último estado: {json.dumps(last_status, ensure_ascii=False)[:1200]}")


def iter_job_result_pages(gc: GenesysClient, job_id: str, page_size: int) -> Iterable[Tuple[int, List[Dict[str, Any]], Dict[str, Any]]]:
    """Descarga resultados del Job por páginas. Soporta cursor y pageNumber por compatibilidad."""
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
                "Job %s | descarga finalizada | página %s sin registros | acumulado descargado: %s",
                job_id,
                page_number,
                total_downloaded
            )
            break

        total_downloaded += len(conversations)
        page_count = data.get("pageCount") or 0
        next_cursor = clean_value(data.get("cursor") or data.get("nextCursor") or data.get("nextPage") or data.get("after"))
        log.info(
            "Job %s | página %s%s descargada en %.1fs | registros página: %s | acumulado: %s | cursor: %s",
            job_id,
            page_number,
            f"/{page_count}" if page_count else "",
            time.time() - started_at,
            len(conversations),
            total_downloaded,
            "sí" if next_cursor else "no"
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
    trunk_numbers: Set[str],
    trunk_edge_ids: Set[str],
    filter_mode: str,
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
    job_id = create_conversations_job(gc, interval, trunk_numbers=trunk_numbers, filter_mode=filter_mode)
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

            matched, match_method = conversation_contains_trunk(conv, trunk_name, trunk_numbers, trunk_edge_ids, filter_mode)
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
            duration_seconds = conversation_duration_seconds(conv.get("conversationStart"), conv.get("conversationEnd"))

            rows.append({
                "conversationId": conv_id,
                "conversationStart": conv.get("conversationStart"),
                "conversationEnd": conv.get("conversationEnd"),
                "tiempo_real_segundos": duration_seconds,
                "tiempo_real_minutos": round(duration_seconds / 60, 4),
                "tiempo_real_hhmmss": seconds_to_hhmmss(duration_seconds),
                "division": division,
                "division_source": division_source,
                "source_name": source_name,
                "direction": direction,
                "ani": ani,
                "dnis": dnis,
                "trunk_name": trunk_name,
                "match_method": match_method,
                "edge_ids": edge_ids,
                "peer_ids": peer_ids,
                "providers": providers,
                "job_id": job_id,
                "interval": interval
            })
            page_matched += 1

        elapsed = time.time() - page_started_at
        rate = len(conversations) / elapsed if elapsed > 0 else 0
        log.info(
            "Job %s | página %s procesada | revisadas página: %s | asociadas página: %s | revisadas total: %s | asociadas total: %s | %.0f conv/s",
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
# Exportación Excel
# =============================================================================

def autosize_excel(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df.columns, 1):
        max_len = max([len(str(col))] + [len(str(x)) for x in df[col].head(500).fillna("").tolist()])
        worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = min(max_len + 2, 60)


def add_excel_table(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame, table_name: str) -> None:
    """Agrega formato de tabla con filtros. No falla si la hoja está vacía."""
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


def enrich_month_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega anio, mes_num, mes y periodo usando conversationStart."""
    if df.empty:
        return df
    out = df.copy()
    dt = pd.to_datetime(out.get("conversationStart"), errors="coerce", utc=True).dt.tz_convert(LOCAL_TIMEZONE)
    out["anio"] = dt.dt.year.fillna(0).astype(int)
    out["mes_num"] = dt.dt.month.fillna(0).astype(int)
    out["mes"] = out["mes_num"].map(MONTHS_ES).fillna("Sin fecha")
    out["periodo"] = dt.dt.strftime("%Y-%m").fillna("Sin fecha")
    return out


def trunk_metadata_summary(trunk_rows: List[Dict[str, Any]], trunk_name: str) -> Dict[str, str]:
    """Resume información relevante de la troncal para agregarla al reporte."""
    if not trunk_rows:
        return {
            "trunk_name": trunk_name if clean_value(trunk_name) else "TODAS",
            "trunk_estado": "N/A",
            "trunk_enabled": "N/A",
            "trunk_in_service": "N/A",
            "proxy": "",
            "edges": "",
            "trunks_detectados": "0",
        }
    df = pd.DataFrame(trunk_rows)
    def unique_join(col: str, limit: int = 20) -> str:
        if col not in df.columns:
            return ""
        vals = [str(x) for x in df[col].dropna().astype(str).unique().tolist() if str(x).strip()]
        vals = sorted(vals)
        return "; ".join(vals[:limit]) + ("; ..." if len(vals) > limit else "")
    return {
        "trunk_name": trunk_name if clean_value(trunk_name) else "TODAS",
        "trunk_estado": unique_join("state") or "N/A",
        "trunk_enabled": unique_join("enabled") or "N/A",
        "trunk_in_service": unique_join("inService") or "N/A",
        "proxy": unique_join("proxyAddressList") or unique_join("proxy"),
        "edges": unique_join("edge_name") or unique_join("edge"),
        "trunks_detectados": str(len(df)),
    }


def export_excel(
    rows: List[Dict[str, Any]],
    output_dir: str,
    trunk_name: str,
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
    filename = f"GNS_Trunk_Divisiones_JOB_MENSUAL_{start_date.strftime('%Y%m%d')}_{end_date_inclusive.strftime('%Y%m%d')}_{timestamp}.xlsx"
    file_path = output_path / filename

    detail_df = enrich_month_columns(pd.DataFrame(rows))
    meta = trunk_metadata_summary(trunk_rows, trunk_name)

    base_cols = [
        "trunk_name", "trunk_estado", "trunk_enabled", "trunk_in_service",
        "proxy", "edges", "trunks_detectados", "modo_filtro"
    ]

    if detail_df.empty:
        duration_cols = ["tiempo_real_segundos", "tiempo_real_minutos", "tiempo_real_hhmmss"]
        summary_df = pd.DataFrame(columns=["division", "volumen_llamadas"] + duration_cols + base_cols)
        summary_month_df = pd.DataFrame(columns=["anio", "mes_num", "mes", "periodo", "division", "volumen_llamadas"] + duration_cols + base_cols)
        pivot_df = pd.DataFrame()
    else:
        unique_detail = detail_df.drop_duplicates(subset=["conversationId"]).copy()
        unique_detail["tiempo_real_segundos"] = pd.to_numeric(
            unique_detail.get("tiempo_real_segundos", 0),
            errors="coerce"
        ).fillna(0).astype(int)

        # Resumen general por división
        summary_df = (
            unique_detail
            .groupby("division", dropna=False)
            .agg(
                volumen_llamadas=("conversationId", "nunique"),
                tiempo_real_segundos=("tiempo_real_segundos", "sum")
            )
            .reset_index()
            .sort_values(["volumen_llamadas", "division"], ascending=[False, True])
        )
        summary_df["tiempo_real_minutos"] = (summary_df["tiempo_real_segundos"] / 60).round(4)
        summary_df["tiempo_real_hhmmss"] = summary_df["tiempo_real_segundos"].map(seconds_to_hhmmss)

        # Resumen mensual por división
        summary_month_df = (
            unique_detail
            .groupby(["anio", "mes_num", "mes", "periodo", "division"], dropna=False)
            .agg(
                volumen_llamadas=("conversationId", "nunique"),
                tiempo_real_segundos=("tiempo_real_segundos", "sum")
            )
            .reset_index()
            .sort_values(["anio", "mes_num", "division"], ascending=[True, True, True])
        )
        summary_month_df["tiempo_real_minutos"] = (summary_month_df["tiempo_real_segundos"] / 60).round(4)
        summary_month_df["tiempo_real_hhmmss"] = summary_month_df["tiempo_real_segundos"].map(seconds_to_hhmmss)

        # Matriz tipo tabla dinámica: filas Mes, columnas División
        pivot_df = (
            summary_month_df.pivot_table(
                index=["anio", "mes_num", "mes", "periodo"],
                columns="division",
                values=["volumen_llamadas", "tiempo_real_minutos"],
                aggfunc="sum",
                fill_value=0
            )
            .reset_index()
            .sort_values(["anio", "mes_num"])
        )
        pivot_df.columns = [
            "_".join([str(part) for part in c if str(part)])
            if isinstance(c, tuple)
            else str(c)
            for c in pivot_df.columns
        ]
        if len(pivot_df.columns) > 4:
            volume_cols = [c for c in pivot_df.columns if c.startswith("volumen_llamadas_")]
            minute_cols = [c for c in pivot_df.columns if c.startswith("tiempo_real_minutos_")]
            if volume_cols:
                pivot_df["volumen_llamadas_Total general"] = pivot_df[volume_cols].sum(axis=1)
            if minute_cols:
                pivot_df["tiempo_real_minutos_Total general"] = pivot_df[minute_cols].sum(axis=1).round(4)

        for k, v in meta.items():
            summary_df[k] = v
            summary_month_df[k] = v
        summary_df["modo_filtro"] = filter_mode
        summary_month_df["modo_filtro"] = filter_mode

        summary_df = summary_df[
            ["division", "volumen_llamadas", "tiempo_real_segundos", "tiempo_real_minutos", "tiempo_real_hhmmss"]
            + base_cols
        ]
        summary_month_df = summary_month_df[
            ["anio", "mes_num", "mes", "periodo", "division", "volumen_llamadas", "tiempo_real_segundos", "tiempo_real_minutos", "tiempo_real_hhmmss"]
            + base_cols
        ]

        # Total general como fila final en resumen general
        total_duration = int(unique_detail["tiempo_real_segundos"].sum())
        total_row = {
            "division": "TOTAL GENERAL",
            "volumen_llamadas": int(unique_detail["conversationId"].nunique()),
            "tiempo_real_segundos": total_duration,
            "tiempo_real_minutos": round(total_duration / 60, 4),
            "tiempo_real_hhmmss": seconds_to_hhmmss(total_duration)
        }
        for k, v in meta.items():
            total_row[k] = v
        total_row["modo_filtro"] = filter_mode
        summary_df = pd.concat([summary_df, pd.DataFrame([total_row])], ignore_index=True)

    trunk_df = pd.DataFrame(trunk_rows)
    dnis_df = pd.DataFrame([
        {"tipo": "TRUNK_NUMBER_CONFIGURADO", "valor_normalizado": n} for n in sorted(trunk_numbers)
    ])
    if not detail_df.empty:
        encontrados = []
        for col in ["ani", "dnis"]:
            for raw in detail_df[col].fillna("").astype(str).tolist():
                for part in raw.split(";"):
                    n = normalize_phone(part)
                    if n:
                        encontrados.append({"tipo": col.upper() + "_ENCONTRADO", "valor_normalizado": n, "valor_original": part.strip()})
        if encontrados:
            dnis_df = pd.concat([dnis_df, pd.DataFrame(encontrados).drop_duplicates()], ignore_index=True)

    parametros_df = pd.DataFrame([
        {"parametro": "trunk_name", "valor": trunk_name if clean_value(trunk_name) else "TODAS"},
        {"parametro": "filter_mode", "valor": filter_mode},
        {"parametro": "trunk_numbers_configurados", "valor": len(trunk_numbers)},
        {"parametro": "trunk_edge_ids_detectados", "valor": ", ".join(sorted(trunk_edge_ids))},
        {"parametro": "trunk_note", "valor": trunk_note},
        {"parametro": "start_date", "valor": str(start_date)},
        {"parametro": "end_date", "valor": str(end_date_inclusive)},
        {"parametro": "fecha_generacion", "valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        {"parametro": "total_conversaciones_identificadas", "valor": len(detail_df.drop_duplicates(subset=["conversationId"])) if not detail_df.empty else 0},
        {"parametro": "nota", "valor": "Generado usando Analytics Conversation Details Jobs. DNIS/ANI es el filtro recomendado para troncales. EDGE depende de datos que Genesys no siempre expone en conversation details; por eso AUTO solo usa EDGE si se selecciona manualmente."}
    ])

    diagnostico_rows: List[Dict[str, Any]] = []
    if detail_df.empty:
        diagnostico_rows.extend([
            {
                "tipo": "Sin conversaciones asociadas",
                "detalle": (
                    "El Job de Genesys pudo ejecutarse, pero ninguna conversacion paso el filtro aplicado. "
                    "Si se requiere una troncal exacta, configure TRUNK_NUMBERS con los DNIS/ANI reales. "
                    "Si desea validar volumen general por division, use FILTER_MODE=TODO o AUTO sin TRUNK_NUMBERS."
                )
            },
            {"tipo": "Modo aplicado", "detalle": filter_mode},
            {"tipo": "TRUNK_NAME", "detalle": trunk_name if clean_value(trunk_name) else "TODAS"},
            {"tipo": "TRUNK_NUMBERS configurados", "detalle": len(trunk_numbers)},
            {"tipo": "Edge IDs detectados", "detalle": len(trunk_edge_ids)},
        ])

    detail_exceeds_excel_limit = export_detail and len(detail_df) > EXCEL_MAX_DATA_ROWS
    if detail_exceeds_excel_limit:
        warning_msg = (
            f"El detalle tiene {len(detail_df):,} filas y Excel solo permite "
            f"{EXCEL_MAX_DATA_ROWS:,} filas de datos por hoja. Se omitira la hoja Detalle "
            "y se generaran solo las hojas agrupadas."
        )
        log.warning(warning_msg)
        diagnostico_rows.append({
            "tipo": "Detalle omitido",
            "detalle": warning_msg
        })

    diagnostico_df = pd.DataFrame(diagnostico_rows)

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        # Hoja principal solicitada: detalle por mes y división
        summary_month_df.to_excel(writer, index=False, sheet_name="Resumen_Mensual")
        # Resumen general por división
        summary_df.to_excel(writer, index=False, sheet_name="Resumen_General")
        # Vista tipo tabla dinámica: meses en filas y divisiones en columnas
        pivot_df.to_excel(writer, index=False, sheet_name="Matriz_Mensual")
        parametros_df.to_excel(writer, index=False, sheet_name="Parametros")
        trunk_df.to_excel(writer, index=False, sheet_name="Trunks")
        dnis_df.to_excel(writer, index=False, sheet_name="Numeros")
        if not diagnostico_df.empty:
            diagnostico_df.to_excel(writer, index=False, sheet_name="Diagnostico")

        for sheet, df, table in [
            ("Resumen_Mensual", summary_month_df, "tblResumenMensual"),
            ("Resumen_General", summary_df, "tblResumenGeneral"),
            ("Matriz_Mensual", pivot_df, "tblMatrizMensual"),
            ("Parametros", parametros_df, "tblParametros"),
            ("Trunks", trunk_df, "tblTrunks"),
            ("Numeros", dnis_df, "tblNumeros"),
        ]:
            autosize_excel(writer, sheet, df)
            add_excel_table(writer, sheet, df, table)

        if not diagnostico_df.empty:
            autosize_excel(writer, "Diagnostico", diagnostico_df)
            add_excel_table(writer, "Diagnostico", diagnostico_df, "tblDiagnostico")

        if export_detail and not detail_exceeds_excel_limit:
            detail_export = detail_df.copy()
            if detail_export.empty:
                detail_export = pd.DataFrame(columns=[
                    "conversationId", "conversationStart", "conversationEnd", "anio", "mes_num", "mes", "periodo", "division",
                    "tiempo_real_segundos", "tiempo_real_minutos", "tiempo_real_hhmmss",
                    "division_source", "source_name", "direction", "ani", "dnis",
                    "trunk_name", "match_method", "edge_ids", "peer_ids", "providers", "job_id", "interval"
                ])
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

    today = date.today()
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

    trunk_name = clean_value(args.TRUNK_NAME)
    trunk_numbers = split_numbers(args.TRUNK_NUMBERS)
    export_detail = clean_value(args.EXPORT_DETAIL).upper() in {"SI", "SÍ", "YES", "TRUE", "1"}
    filter_mode = clean_value(args.FILTER_MODE).upper() or "AUTO"
    if filter_mode not in {"AUTO", "DNIS", "EDGE", "TODO"}:
        filter_mode = "AUTO"

    log.info("Parámetros aplicados:")
    log.info("- TRUNK_NAME: %s", trunk_name if trunk_name else "<vacío: traer todo si no hay DNIS/ANI>")
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

    trunk_rows, trunk_edge_ids, trunk_note = list_trunks(gc, trunk_name) if trunk_name else ([], set(), "Sin TRUNK_NAME: no se consultó coincidencia específica de trunks; el reporte puede traer todo.")
    log.info("%s", trunk_note)
    if filter_mode == "AUTO":
        if trunk_numbers:
            effective_mode = "DNIS"
        elif not trunk_name and not trunk_numbers:
            effective_mode = "TODO"
        else:
            effective_mode = "TODO"
            log.warning(
                "AUTO no usara EDGE porque Genesys no siempre expone edgeId en conversation details. "
                "Se traeran llamadas de voz. Para filtrar troncal exacta, configure TRUNK_NUMBERS con DNIS/ANI."
            )
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
            trunk_numbers=trunk_numbers,
            trunk_edge_ids=trunk_edge_ids,
            filter_mode=effective_mode,
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

    # Deduplicación final
    unique = {}
    for row in all_rows:
        cid = row.get("conversationId")
        if cid and cid not in unique:
            unique[cid] = row
    final_rows = list(unique.values())

    log.info("Conversaciones únicas identificadas: %s", len(final_rows))
    pyflow_progress(92)

    report_path = export_excel(
        rows=final_rows,
        output_dir=args.OUTPUT_DIR,
        trunk_name=trunk_name,
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

    # PyFlow suele capturar stdout; dejamos ruta fácil de localizar.
    print(f"OUTPUT_FILE={report_path.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log.exception("Error ejecutando reporte: %s", exc)
        raise SystemExit(1)
