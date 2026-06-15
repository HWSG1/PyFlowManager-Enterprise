#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyFlow Manager - Conteo de Listas Outbound Genesys

Objetivo
--------
1. Obtener las listas de contactos outbound desde Genesys Cloud.
2. Consultar la cantidad de contactos por lista.
3. Generar un Excel con dos hojas:
   - Base: detalle por lista.
   - Resumen: resumen por división/año y límites de referencia.

Notas PyFlow
------------
- No contiene credenciales quemadas.
- Usa variables globales GENESYS_CLIENT_ID, GENESYS_CLIENT_SECRET y GENESYS_REGION.
- Imprime logs con flush=True para consola en tiempo real.
- Soporta valores vacíos, "null" y "undefined" sin romper.
- El Excel se guarda en OUTPUT_DIR.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import pandas as pd


PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Genesys Region / Domain", "required": True},
    "OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida del Excel", "required": False, "default": "runtime/exports"},
    "PAGE_SIZE": {"type": "number", "label": "Tamaño página listas", "required": False, "default": "100"},
    "REQUEST_TIMEOUT": {"type": "number", "label": "Timeout HTTP segundos", "required": False, "default": "120"},
    "API_SLEEP_SECONDS": {"type": "number", "label": "Pausa entre requests", "required": False, "default": "0.2"},
    "MAX_RETRIES": {"type": "number", "label": "Reintentos HTTP", "required": False, "default": "5"},
    "MAX_LISTS": {"type": "number", "label": "Máximo listas para prueba; 0 = todas", "required": False, "default": "0"},
    "INCLUDE_CONTACT_COUNTS": {"type": "select", "label": "Consultar cantidad de contactos por lista", "required": True, "options": ["true", "false"], "default": "true"},
    "INCLUDE_ATTEMPT_COUNTS": {"type": "select", "label": "Consultar intentos históricos por lista", "required": True, "options": ["true", "false"], "default": "true"},
    "CONTACTS_PAGE_SIZE": {"type": "number", "label": "Tamaño página contactos para intentos (máximo permitido Genesys: 100)", "required": False, "default": "100"}
}

def log(message: str) -> None:
    print(message, flush=True)


def clean_env_value(value: Any, default: Optional[str] = None) -> Optional[str]:
    if value is None:
        return default
    text = str(value).strip()
    if text == "" or text.lower() in ("null", "none", "undefined"):
        return default
    return text


def env_str(name: str, default: str = "", required: bool = False) -> str:
    value = clean_env_value(os.getenv(name), default)
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


def env_int_clamped(name: str, default: int, minimum: int, maximum: int) -> int:
    """
    Lee un entero desde variables/parámetros y lo limita a un rango permitido.
    Esto evita errores 400 cuando Genesys exige pageSize entre 1 y 100.
    """
    value = env_int(name, default)
    if value < minimum:
        log(f"[WARN] {name}={value} es menor al mínimo {minimum}. Se usará {minimum}.")
        return minimum
    if value > maximum:
        log(f"[WARN] {name}={value} supera el máximo permitido {maximum}. Se usará {maximum}.")
        return maximum
    return value


def normalize_genesys_domain(region: str) -> str:
    region = str(region or "mypurecloud.com").strip()
    region = region.replace("https://", "").replace("http://", "").strip("/")
    if region.startswith("api."):
        region = region[4:]
    if region.startswith("login."):
        region = region[6:]
    return region


def build_urls() -> tuple[str, str]:
    domain = normalize_genesys_domain(env_str("GENESYS_REGION", "mypurecloud.com", required=True))
    return f"https://login.{domain}/oauth/token", f"https://api.{domain}"


def masked(value: str) -> str:
    return "********" if value else "<vacío>"


def log_params() -> None:
    log("Parámetros recibidos / aplicados:")
    for name in [
        "GENESYS_CLIENT_ID",
        "GENESYS_CLIENT_SECRET",
        "GENESYS_REGION",
        "OUTPUT_DIR",
        "PAGE_SIZE",
        "REQUEST_TIMEOUT",
        "API_SLEEP_SECONDS",
        "MAX_RETRIES",
        "MAX_LISTS",
        "INCLUDE_CONTACT_COUNTS",
        "INCLUDE_ATTEMPT_COUNTS",
        "CONTACTS_PAGE_SIZE",
    ]:
        value = env_str(name, "")
        if any(word in name.upper() for word in ("SECRET", "PASSWORD", "TOKEN", "KEY")) and value:
            value = masked(value)
        log(f"- {name}: {value if value else '<vacío>'}")


def request_with_retry(method: str, url: str, **kwargs: Any) -> requests.Response:
    max_retries = env_int("MAX_RETRIES", 5)
    timeout = env_int("REQUEST_TIMEOUT", 120)
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(60, attempt * 5)
                log(f"[WARN] Rate limit 429 | intento {attempt}/{max_retries} | esperando {wait_seconds} segundos...")
                time.sleep(wait_seconds)
                continue

            if 500 <= response.status_code <= 599:
                wait_seconds = min(60, attempt * 5)
                log(f"[WARN] Error servidor {response.status_code} | intento {attempt}/{max_retries} | esperando {wait_seconds} segundos...")
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 400:
                log(f"[ERROR] HTTP {response.status_code} | Respuesta: {response.text[:1000]}")

            response.raise_for_status()
            return response

        except Exception as exc:
            last_error = exc
            wait_seconds = min(60, attempt * 5)
            log(f"[WARN] Error request intento {attempt}/{max_retries}: {exc} | esperando {wait_seconds} segundos...")
            time.sleep(wait_seconds)

    raise RuntimeError(f"No se pudo completar request después de {max_retries} intentos: {last_error}")


def get_token() -> str:
    token_url, _ = build_urls()
    client_id = env_str("GENESYS_CLIENT_ID", required=True)
    client_secret = env_str("GENESYS_CLIENT_SECRET", required=True)

    response = request_with_retry(
        "POST",
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Genesys no devolvió access_token.")
    return token


def genesys_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def get_contact_lists(token: str) -> List[Dict[str, Any]]:
    _, base_url = build_urls()
    page_size = env_int_clamped("PAGE_SIZE", 100, 1, 100)
    sleep_seconds = env_float("API_SLEEP_SECONDS", 0.2)
    max_lists = env_int("MAX_LISTS", 0)

    log("Obteniendo cantidad de páginas de listas outbound...")

    first_url = f"{base_url}/api/v2/outbound/contactlists?pageSize={page_size}&pageNumber=1"
    first = request_with_retry("GET", first_url, headers=genesys_headers(token))
    payload = first.json()

    page_count = int(payload.get("pageCount") or 1)
    results: List[Dict[str, Any]] = []

    log(f"Total de páginas detectadas: {page_count}")

    for page in range(1, page_count + 1):
        log(f"Consultando página de listas {page}/{page_count}...")
        url = f"{base_url}/api/v2/outbound/contactlists?pageSize={page_size}&pageNumber={page}"
        response = request_with_retry("GET", url, headers=genesys_headers(token))

        entities = response.json().get("entities") or []
        for item in entities:
            results.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "division": (item.get("division") or {}).get("name"),
                "divisionId": (item.get("division") or {}).get("id"),
                "dateCreated": item.get("dateCreated"),
            })

            if max_lists > 0 and len(results) >= max_lists:
                log(f"MAX_LISTS={max_lists}. Se detiene lectura para prueba.")
                return results

        log(f"Página {page}/{page_count} OK | listas acumuladas: {len(results)}")
        time.sleep(sleep_seconds)

    log(f"Total de listas encontradas: {len(results)}")
    return results


def get_contacts_count(token: str, contact_list_id: str) -> int:
    _, base_url = build_urls()
    url = f"{base_url}/api/v2/outbound/contactlists/{contact_list_id}/contacts/search"
    body = {"pageSize": 1, "pageNumber": 1}

    response = request_with_retry("POST", url, headers=genesys_headers(token), json=body)
    return int(response.json().get("contactsCount") or 0)


def _count_call_records(call_records: Any) -> int:
    """
    Cuenta intentos históricos desde callRecords del contacto.

    Genesys puede devolver callRecords como lista o como diccionario por columna/teléfono.
    Esta función es defensiva para soportar ambas formas.
    """
    if not call_records:
        return 0

    if isinstance(call_records, list):
        return len(call_records)

    if isinstance(call_records, dict):
        total = 0
        for value in call_records.values():
            if isinstance(value, list):
                total += len(value)
            elif isinstance(value, dict):
                # Algunas respuestas pueden traer un objeto por número.
                # Si contiene lista interna, se suma; si no, cuenta como 1 registro.
                nested_count = 0
                for nested_value in value.values():
                    if isinstance(nested_value, list):
                        nested_count += len(nested_value)
                total += nested_count if nested_count > 0 else 1
            elif value:
                total += 1
        return total

    return 0


def get_contacts_metrics_historico(token: str, contact_list_id: str) -> Dict[str, int]:
    """
    Retorna:
    - contactsCount: total cargado en la lista.
    - attemptsCount: total histórico de intentos identificados en callRecords.

    Nota: el histórico corresponde a los contactos existentes en la lista al momento
    de consultar. Si se han eliminado/purgado contactos, esos intentos ya no podrían
    contarse desde la lista actual.
    """
    _, base_url = build_urls()
    url = f"{base_url}/api/v2/outbound/contactlists/{contact_list_id}/contacts/search"
    page_size = env_int_clamped("CONTACTS_PAGE_SIZE", 100, 1, 100)
    sleep_seconds = env_float("API_SLEEP_SECONDS", 0.2)

    page_number = 1
    contacts_count = 0
    attempts_count = 0

    while True:
        body = {"pageSize": page_size, "pageNumber": page_number}
        response = request_with_retry("POST", url, headers=genesys_headers(token), json=body)
        payload = response.json()

        if page_number == 1:
            contacts_count = int(payload.get("contactsCount") or payload.get("total") or 0)

        entities = payload.get("entities") or []
        for contact in entities:
            attempts_count += _count_call_records(contact.get("callRecords"))

        # Si no hay entities, o ya se leyeron todos los contactos, se termina.
        if not entities:
            break

        if contacts_count > 0 and page_number * page_size >= contacts_count:
            break

        page_number += 1
        time.sleep(sleep_seconds)

    return {"contactsCount": contacts_count, "attemptsCount": attempts_count}


def build_output_file() -> Path:
    output_dir = Path(env_str("OUTPUT_DIR", "runtime/exports"))
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"Detalle_Listas_Genesys_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
    return output_dir / filename


def generar_excel_con_resumen(df: pd.DataFrame, output_file: Path) -> None:
    df = df.copy()
    df["Año"] = df["dateCreated"].astype(str).str[:4]
    df["contactsCount"] = pd.to_numeric(df.get("contactsCount", 0), errors="coerce").fillna(0).astype(int)
    df["attemptsCount"] = pd.to_numeric(df.get("attemptsCount", 0), errors="coerce").fillna(0).astype(int)
    df["vueltasBase"] = pd.to_numeric(df.get("vueltasBase", 0), errors="coerce").fillna(0).round(2)

    resumen = df.pivot_table(
        index="division",
        columns="Año",
        values=["id", "contactsCount", "attemptsCount"],
        aggfunc={"id": "count", "contactsCount": "sum", "attemptsCount": "sum"},
        fill_value=0,
        dropna=False,
    )

    resumen.columns = [
        f"{year} " + ("listas" if metric == "id" else "registros" if metric == "contactsCount" else "intentos")
        for metric, year in resumen.columns
    ]

    resumen = resumen.reset_index().rename(columns={"division": "Listas"})

    total_por_division = df.groupby("division", dropna=False).agg(
        **{
            "Total listas": ("id", "count"),
            "Total registros": ("contactsCount", "sum"),
            "Total intentos": ("attemptsCount", "sum"),
        }
    ).reset_index()
    total_por_division["Vueltas estimadas"] = (
        total_por_division["Total intentos"] / total_por_division["Total registros"].replace(0, pd.NA)
    ).fillna(0).round(2)

    resumen = resumen.merge(total_por_division, left_on="Listas", right_on="division", how="left").drop(columns=["division"])

    total_listas = int(df["id"].count())
    total_registros = int(df["contactsCount"].sum())
    total_intentos = int(df["attemptsCount"].sum())
    vueltas_global = round(total_intentos / total_registros, 2) if total_registros > 0 else 0

    limite_listas = 1000
    limite_registros = 5_000_000

    limites = pd.DataFrame({
        "Indicador": ["Límite", "Utilizado", "% Utilizado", "Intentos históricos", "Vueltas globales"],
        "Listas": [limite_listas, total_listas, f"{(total_listas / limite_listas):.0%}", "", ""],
        "Registros": [limite_registros, total_registros, f"{(total_registros / limite_registros):.0%}", total_intentos, vueltas_global],
    })

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Base", index=False)
        resumen.to_excel(writer, sheet_name="Resumen", index=False, startrow=0)
        limites.to_excel(writer, sheet_name="Resumen", index=False, startrow=len(resumen) + 4)


def main() -> int:
    start_time = time.time()
    total_lists = 0
    count_errors = 0
    output_file: Optional[Path] = None

    try:
        log("=" * 80)
        log("INICIO PROCESO DETALLE DE LISTAS GENESYS")
        log_params()
        log("=" * 80)

        log("Obteniendo token Genesys...")
        token = get_token()
        log("Token obtenido correctamente.")

        log("Consultando listas outbound...")
        lists = get_contact_lists(token)
        total_lists = len(lists)

        include_counts = env_bool("INCLUDE_CONTACT_COUNTS", True)
        include_attempts = env_bool("INCLUDE_ATTEMPT_COUNTS", True)
        if include_counts or include_attempts:
            log("Consultando total cargado e intentos históricos por lista...")
            sleep_seconds = env_float("API_SLEEP_SECONDS", 0.2)

            for index, item in enumerate(lists, start=1):
                name = item.get("name") or item.get("id")
                try:
                    log(f"[{index}/{total_lists}] Procesando lista: {name}")

                    if include_attempts:
                        metrics = get_contacts_metrics_historico(token, item["id"])
                        item["contactsCount"] = metrics["contactsCount"] if include_counts else 0
                        item["attemptsCount"] = metrics["attemptsCount"]
                    else:
                        item["contactsCount"] = get_contacts_count(token, item["id"]) if include_counts else 0
                        item["attemptsCount"] = 0

                    total_cargado = int(item.get("contactsCount") or 0)
                    total_intentos = int(item.get("attemptsCount") or 0)
                    item["vueltasBase"] = round(total_intentos / total_cargado, 2) if total_cargado > 0 else 0

                except Exception as exc:
                    count_errors += 1
                    item["contactsCount"] = 0
                    item["attemptsCount"] = 0
                    item["vueltasBase"] = 0
                    item["metricsError"] = str(exc)
                    log(f"[WARN] No se pudo obtener métricas para {name}: {exc}")
                time.sleep(sleep_seconds)
        else:
            log("INCLUDE_CONTACT_COUNTS=false e INCLUDE_ATTEMPT_COUNTS=false. No se consultarán métricas por lista.")
            for item in lists:
                item["contactsCount"] = 0
                item["attemptsCount"] = 0
                item["vueltasBase"] = 0

        df = pd.DataFrame(lists)
        output_file = build_output_file()

        log(f"Generando Excel: {output_file}")
        generar_excel_con_resumen(df, output_file)

        duration = time.time() - start_time
        log("=" * 80)
        log("RESUMEN FINAL")
        log(f"Listas obtenidas: {total_lists}")
        log(f"Errores consultando contactos: {count_errors}")
        log(f"Archivo generado: {output_file}")
        log(f"Duración total: {duration:.2f} segundos")
        log("=" * 80)

        return 0 if count_errors == 0 else 1

    except Exception as exc:
        log("=" * 80)
        log(f"[ERROR] El proceso terminó con error general: {exc}")
        log(traceback.format_exc())
        log("=" * 80)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
