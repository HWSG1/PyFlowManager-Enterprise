#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GNS_Trunk_Divisiones_Final.py
Reporte de volumen de llamadas por División de Genesys Cloud, con filtro opcional por troncal.

Uso principal:
- Ejecutar desde PyFlow Manager.
- Si no se colocan fechas, consulta desde 2026-01-01 hasta hoy.
- Genera un Excel con resumen por División y, opcionalmente, detalle de conversaciones.

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
    "FILTER_MODE": {"type": "select", "label": "Modo de filtro", "required": True, "options": ["AUTO", "DNIS", "EDGE", "TODO"], "default": "AUTO"},
    "CHUNK_DAYS": {"type": "number", "label": "Días por bloque", "required": False, "default": "7"}
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
    parser.add_argument("--CHUNK_DAYS", default=env_or_default("CHUNK_DAYS", "7"))
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
    start_dt = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_day_exclusive, datetime.min.time(), tzinfo=timezone.utc)
    return f"{start_dt.isoformat().replace('+00:00', 'Z')}/{end_dt.isoformat().replace('+00:00', 'Z')}"


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
    def __init__(self, client_id: str, client_secret: str, region: str, max_retries: int = 6):
        self.client_id = clean_value(client_id)
        self.client_secret = clean_value(client_secret)
        self.login_base, self.api_base = normalize_region(region)
        self.max_retries = max_retries
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
        for attempt in range(1, self.max_retries + 1):
            resp = self.session.request(method, url, timeout=120, **kwargs)

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

        raise RuntimeError(f"No fue posible completar API {method} {path} después de {self.max_retries} reintentos.")

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


def query_conversations_page(gc: GenesysClient, interval: str, page_number: int, page_size: int = 100) -> Dict[str, Any]:
    body = {
        "interval": interval,
        "order": "asc",
        "orderBy": "conversationStart",
        "paging": {
            "pageSize": page_size,
            "pageNumber": page_number
        },
        "segmentFilters": [
            {
                "type": "and",
                "predicates": [
                    {
                        "dimension": "mediaType",
                        "value": "voice"
                    }
                ]
            }
        ]
    }
    return gc.request("POST", "/api/v2/analytics/conversations/details/query", json=body)


def extract_conversations_for_range(
    gc: GenesysClient,
    lookup: GenesysLookup,
    start_day: date,
    end_day_exclusive: date,
    trunk_name: str,
    trunk_numbers: Set[str],
    trunk_edge_ids: Set[str],
    filter_mode: str,
) -> List[Dict[str, Any]]:
    interval = iso_interval(start_day, end_day_exclusive)
    page = 1
    rows: List[Dict[str, Any]] = []
    total_checked = 0

    while True:
        data = query_conversations_page(gc, interval, page, page_size=100)
        conversations = data.get("conversations", []) or []
        if not conversations:
            break

        for conv in conversations:
            total_checked += 1
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

            rows.append({
                "conversationId": conv_id,
                "conversationStart": conv.get("conversationStart"),
                "conversationEnd": conv.get("conversationEnd"),
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
                "providers": providers
            })

        page_count = data.get("pageCount") or 0
        if page_count and page >= page_count:
            break
        # Si no viene pageCount, detener si vienen menos de 100
        if not page_count and len(conversations) < 100:
            break

        page += 1

    log.info("Bloque %s | revisadas: %s | asociadas a troncal: %s", interval, total_checked, len(rows))
    return rows


# =============================================================================
# Exportación Excel
# =============================================================================

def autosize_excel(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    worksheet = writer.sheets[sheet_name]
    for idx, col in enumerate(df.columns, 1):
        max_len = max([len(str(col))] + [len(str(x)) for x in df[col].head(500).fillna("").tolist()])
        worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = min(max_len + 2, 60)


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
    filename = f"GNS_Trunk_Divisiones_Final_{start_date.strftime('%Y%m%d')}_{end_date_inclusive.strftime('%Y%m%d')}_{timestamp}.xlsx"
    file_path = output_path / filename

    detail_df = pd.DataFrame(rows)
    if detail_df.empty:
        summary_df = pd.DataFrame(columns=["division", "volumen_llamadas", "trunk_name"])
    else:
        # Contar conversationId únicos por división
        summary_df = (
            detail_df.drop_duplicates(subset=["conversationId"])
            .groupby("division", dropna=False)
            .agg(volumen_llamadas=("conversationId", "nunique"))
            .reset_index()
            .sort_values(["volumen_llamadas", "division"], ascending=[False, True])
        )
        summary_df["trunk_name"] = trunk_name if clean_value(trunk_name) else "TODAS"
        summary_df["modo_filtro"] = filter_mode

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
        {"parametro": "nota", "valor": "DNIS/ANI es exacto. EDGE es aproximado porque un Edge puede tener varias troncales. Si TRUNK_NAME y TRUNK_NUMBERS están vacíos, el reporte trae todas las llamadas."}
    ])

    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Resumen")
        parametros_df.to_excel(writer, index=False, sheet_name="Parametros")
        trunk_df.to_excel(writer, index=False, sheet_name="Trunks")
        dnis_df.to_excel(writer, index=False, sheet_name="Numeros")
        autosize_excel(writer, "Resumen", summary_df)
        autosize_excel(writer, "Parametros", parametros_df)
        autosize_excel(writer, "Trunks", trunk_df)
        autosize_excel(writer, "Numeros", dnis_df)

        if export_detail:
            detail_export = detail_df.copy()
            if detail_export.empty:
                detail_export = pd.DataFrame(columns=[
                    "conversationId", "conversationStart", "conversationEnd", "division",
                    "division_source", "source_name", "direction", "ani", "dnis",
                    "trunk_name", "match_method", "edge_ids", "peer_ids", "providers"
                ])
            detail_export.to_excel(writer, index=False, sheet_name="Detalle")
            autosize_excel(writer, "Detalle", detail_export)

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
        chunk_days = int(clean_value(args.CHUNK_DAYS) or "7")
    except Exception:
        chunk_days = 7
    chunk_days = max(1, min(chunk_days, 31))

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
    log.info("- TRUNK_NUMBERS configurados: %s", len(trunk_numbers))
    log.info("- FILTER_MODE: %s", filter_mode)
    log.info("- EXPORT_DETAIL: %s", "SI" if export_detail else "NO")
    log.info("- OUTPUT_DIR: %s", args.OUTPUT_DIR)

    gc = GenesysClient(
        client_id=args.GENESYS_CLIENT_ID,
        client_secret=args.GENESYS_CLIENT_SECRET,
        region=args.GENESYS_REGION
    )
    gc.authenticate()

    lookup = GenesysLookup(gc)
    lookup.load_divisions()

    trunk_rows, trunk_edge_ids, trunk_note = list_trunks(gc, trunk_name) if trunk_name else ([], set(), "Sin TRUNK_NAME: no se consultó coincidencia específica de trunks; el reporte puede traer todo.")
    log.info("%s", trunk_note)
    if filter_mode == "AUTO":
        if trunk_numbers:
            effective_mode = "DNIS"
        elif trunk_name and trunk_edge_ids:
            effective_mode = "EDGE"
        elif not trunk_name and not trunk_numbers:
            effective_mode = "TODO"
        else:
            effective_mode = "TODO"
            log.warning("No se encontraron edgeIds para la troncal y no hay DNIS/ANI; se traerán todas las llamadas.")
    else:
        effective_mode = filter_mode
    log.info("- MODO EFECTIVO: %s", effective_mode)

    all_rows: List[Dict[str, Any]] = []
    for chunk_start, chunk_end in daterange_chunks(start_day, end_exclusive, chunk_days):
        log.info("Consultando bloque: %s a %s", chunk_start, chunk_end - timedelta(days=1))
        rows = extract_conversations_for_range(
            gc=gc,
            lookup=lookup,
            start_day=chunk_start,
            end_day_exclusive=chunk_end,
            trunk_name=trunk_name,
            trunk_numbers=trunk_numbers,
            trunk_edge_ids=trunk_edge_ids,
            filter_mode=effective_mode
        )
        all_rows.extend(rows)

    # Deduplicación final
    unique = {}
    for row in all_rows:
        cid = row.get("conversationId")
        if cid and cid not in unique:
            unique[cid] = row
    final_rows = list(unique.values())

    log.info("Conversaciones únicas identificadas: %s", len(final_rows))

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
