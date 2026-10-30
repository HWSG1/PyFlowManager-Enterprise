# -*- coding: utf-8 -*-
"""PyFlow Manager | Encuestas Qualtrics para llamadas de Belice.

Dependencias: pip install hdbcli requests python-dotenv
Opcional: pip install openpyxl (este programa exporta CSV sin dependencias extra)

PREVISUALIZAR_PRUEBA es el modo por defecto y NO invoca Qualtrics.
PRUEBA_REAL envia solo la muestra aprobada; ENVIAR_TODOS requiere
BZ_CONFIRMAR_ENVIO=True y bitacora persistente en HANA.
PyFlow expone 10 variables GLOBAL y tres controles opcionales: RUN_MODE,
WRAP_UP_MODE, CORREOS_PRUEBA. Todas las opciones restantes y el endpoint
(incluyendo urlTokenId) se editan en CONFIGURACION_INTERNA. Restringir acceso al .py por contener urlTokenId.
"""
import argparse
import csv
import hashlib
import json
import logging
import random
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import requests
except ImportError:
    requests = None
try:
    from hdbcli import dbapi
except ImportError:
    dbapi = None
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# 1. VARIABLES GLOBALES EXCLUSIVAS DE PYFLOW MANAGER (10)
# ============================================================
# Mantener SOLO 10 variables de tipo global.
# Se agregan UNICAMENTE los controles explicitamente requeridos para
# operar una prueba: RUN_MODE, WRAP_UP_MODE y CORREOS_PRUEBA.
# El resto se configura solo dentro del script.
PYFLOW_PARAMS = {
    "HPR_HOST_ESPEJO": {"type": "global", "global_key": "HPR_HOST_ESPEJO", "label": "HANA Genesys: host lectura", "required": True},
    "HPR_HOST": {"type": "global", "global_key": "HPR_HOST", "label": "HANA Genesys: host escritura bitacora", "required": True},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "HANA Genesys: puerto", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "HANA Genesys: usuario", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "HANA Genesys: contrasena", "required": True, "secret": True},
    "TOKEN_QUALTRICTS": {"type": "global", "global_key": "TOKEN_QUALTRICTS", "label": "Token API Qualtrics", "required": True, "secret": True},
    "BZ_HANA_HOST": {"type": "global", "global_key": "BZ_HANA_HOST", "label": "HANA BW Belice: host", "required": True},
    "BZ_HANA_PORT": {"type": "global", "global_key": "BZ_HANA_PORT", "label": "HANA BW Belice: puerto", "required": True},
    "BZ_HANA_USER": {"type": "global", "global_key": "BZ_HANA_USER", "label": "HANA BW Belice: usuario", "required": True},
    "BZ_HANA_PASSWORD": {"type": "global", "global_key": "BZ_HANA_PASSWORD", "label": "HANA BW Belice: contrasena", "required": True, "secret": True},
    "RUN_MODE": {
        "type": "select", "label": "Modo de ejecucion Qualtrics", "required": True,
        "options": ["PREVISUALIZAR", "PREVISUALIZAR_PRUEBA", "PRUEBA_REAL", "ENVIAR_TODOS"],
        "default": "PREVISUALIZAR_PRUEBA"
    },
    "WRAP_UP_MODE": {
        "type": "select", "label": "Filtro de WRAP_UP_CODE_NAME", "required": True,
        "options": ["TODOS", "SOLO_CON_WRAP_UP", "SOLO_SIN_WRAP_UP", "FILTRAR_LISTA"],
        "default": "SOLO_CON_WRAP_UP"
    },
    "CORREOS_PRUEBA": {
        "type": "tags", "label": "Correos a probar (opcional; vacio = muestra aleatoria)",
        "required": False
    },
}

# ============================================================
# 2. CONFIGURACION INTERNA (EDITAR DIRECTAMENTE EN ESTE SCRIPT)
# ============================================================
# Para produccion: RUN_MODE=ENVIAR_TODOS y BZ_CONFIRMAR_ENVIO=True
# SOLAMENTE despues de validar el archivo de vista previa.
# El urlTokenId forma parte del endpoint de activacion de Qualtrics:
# proteger el archivo .py y no publicar esta URL en logs.
CONFIGURACION_INTERNA = {
    "QUALTRICS_BZ_ENDPOINT": "https://yul1.qualtrics.com/inbound-event/v1/events/json/triggers?urlTokenId=b576369d-de39-4eda-b9ce-2ff57a5a02b3",
    "BZ_RUN_MODE": "PREVISUALIZAR_PRUEBA", # respaldo si PyFlow no envia RUN_MODE
    "WRAP_UP_MODE": "SOLO_CON_WRAP_UP",  # respaldo si PyFlow no envia WRAP_UP_MODE
    "WRAP_UP_LISTA_PERMITIDA": [],      # para FILTRAR_LISTA: textos exactos de WRAP_UP_CODE_NAME
    "BZ_CONFIRMAR_ENVIO": False,        # habilitar SOLO para ENVIAR_TODOS
    "CANTIDAD_MUESTRA_PRUEBA": 3,        # correos distintos al azar; maximo 10
    "SEMILLA_MUESTRA_PRUEBA": "BELICE_QUALTRICS_V1", # fija resultados al repetir fecha
    "PERMITIR_PRUEBA_REAL": True,       # limita SOLO PRUEBA_REAL a muestra <= 10
    "PROCESS_DATE": "",                # YYYY-MM-DD; vacio = ayer en Belice
    "HANA_INTERACTION_TIMEZONE": "America/Belize",  # Cambiar a UTC si SAP almacena UTC
    "OUTPUT_DIR": "",                  # Vacio = ./reportes_belice_qualtrics
    "HANA_AUDIT_SCHEMA": "BI_SS",
    "HANA_AUDIT_TABLE": "GNS_QUALTRICS_BZ_ENVIOS",
    "QUALTRICS_DELAY_SECONDS": 1.0,
}

GENESYS_QUEUE_ID = "8ab6c76b-2e37-40aa-aaf0-0e50ed1cd41c"
LOG = logging.getLogger("GNS_Encuestas_Qualtrics_Belice")

INTERACTION_COLUMNS = ["ANIO", "MES", "DIA", "CONVERSATION_ID", "EXTERNAL_TAG", "ANI", "SECUENCIA", "FECHA", "HORA", "COLA", "AGENTE_ID", "AGENTE", "CONTAR_INTERACCION", "CC_SERVICE_DESCRIPTION", "STARTING_LANGUAGE", "IDIOMA", "CONVERSATION_START"]
CLIENT_COLUMNS = ["FIRSTNAME", "LASTNAME", "EXTERNALREFERENCE", "EMAIL", "PHONE", "BP_ID", "DATE_OF_BIRTH", "GENDER", "BP_TYPE"]

# Usa SELECT con parametros de fecha para permitir procesar ayer o reprocesar un dia de prueba.
# El filtro de fechas se adapta a la zona horaria interna de HANA (por defecto Belice).
INTERACTIONS_SQL = """
WITH CAT_COLAS AS (
    SELECT ID, MAX(QUEUE_NAME) AS QUEUE_NAME
    FROM BI_SS.GNS_API_COLAS GROUP BY ID
), CAT_USUARIOS AS (
    SELECT ID, MAX(NAME) AS NAME
    FROM BI_SS.GNS_API_USUARIOS GROUP BY ID
)
SELECT
    YEAR(A.CONVERSATION_START) AS ANIO,
    MONTH(A.CONVERSATION_START) AS MES,
    DAYOFMONTH(A.CONVERSATION_START) AS DIA,
    A.CONVERSATION_ID,
    A.EXTERNAL_TAG,
    V.ANI,
    A.SECUENCIA,
    TO_DATE(A.CONVERSATION_START) AS FECHA,
    HOUR(A.CONVERSATION_START) AS HORA,
    COALESCE(A.QUEUE_NAME, Q.QUEUE_NAME) AS COLA,
    A.USER_ID AS AGENTE_ID,
    COALESCE(A.USER_NAME, U.NAME) AS AGENTE,
    ROW_NUMBER() OVER (
        PARTITION BY A.CONVERSATION_ID, A.QUEUE_ID, A.MEDIA_TYPE
        ORDER BY A.SECUENCIA
    ) AS CONTAR_INTERACCION,
    A.WRAP_UP_CODE_NAME AS CC_SERVICE_DESCRIPTION,
    A.STARTING_LANGUAGE,
    CASE
        WHEN A.STARTING_LANGUAGE IS NULL
             OR LOWER(A.STARTING_LANGUAGE) = 'es-us'
        THEN 'ESPAÑOL'
        ELSE 'INGLES'
    END AS IDIOMA,
    A.CONVERSATION_START
FROM BI_SS.GNS_API_INTERACCIONES A
LEFT JOIN BI_SS.GNS_API_INTERACCIONES_VOICE V
    ON A.CONVERSATION_ID = V.CONVERSATION_ID AND A.SECUENCIA = V.SECUENCIA
LEFT JOIN CAT_COLAS Q ON A.QUEUE_ID = Q.ID
LEFT JOIN CAT_USUARIOS U ON A.USER_ID = U.ID
WHERE A.CONVERSATION_START >= TO_TIMESTAMP(?, 'YYYY-MM-DD HH24:MI:SS')
  AND A.CONVERSATION_START < TO_TIMESTAMP(?, 'YYYY-MM-DD HH24:MI:SS')
  AND A.ORIGINATING_DIRECTION = 'inbound'
  AND A.SECUENCIA IN (0, 1)
  AND A.QUEUE_ID = ?
ORDER BY A.CONVERSATION_ID, A.SECUENCIA
"""
# No se filtra por correo: tambien debemos detectar numeros compartidos con
# clientes que no tienen email o tienen N/A.
CLIENTS_SQL = """
SELECT FIRSTNAME, LASTNAME, EXTERNALREFERENCE, LOWER(EMAIL) AS EMAIL,
       PHONE, BP_ID, DATE_OF_BIRTH, GENDER, BP_TYPE
FROM BZ_CC.BZ_CRM_CLIENTS
"""


def global_env(name, required=True):
    """Lee exclusivamente las diez variables globales declaradas a PyFlow."""
    if name not in PYFLOW_PARAMS:
        raise ValueError("La opcion no esta definida como variable global PyFlow: " + name)
    val = str(os.getenv(name, "") or "").strip()
    if required and not val:
        raise ValueError("Falta configurar variable global PyFlow: " + name)
    return val


def internal_setting(name):
    """Opciones editadas solamente dentro del .py; no consulta el entorno."""
    return CONFIGURACION_INTERNA[name]


def pyflow_control(name, fallback=""):
    """Lee SOLO controles operativos declarados en PYFLOW_PARAMS.

    No son variables globales del gestor de secretos. Si el proceso no
    recibe controles de PyFlow (por ejemplo al ejecutarse por CLI), usa
    la configuracion interna como respaldo.
    """
    if name not in ("RUN_MODE", "WRAP_UP_MODE", "CORREOS_PRUEBA"):
        raise ValueError("Control operativo no permitido: " + name)
    raw = os.getenv(name, "")
    return str(raw).strip() if raw else str(fallback)


def parse_test_emails(raw):
    """Admite tags separados por coma, punto y coma o formato JSON lista."""
    if isinstance(raw, (list, tuple)):
        entries = raw
    else:
        raw = text_value(raw)
        if not raw:
            return []
        if raw.startswith("["):
            try:
                entries = json.loads(raw)
                if not isinstance(entries, list):
                    raise ValueError("CORREOS_PRUEBA debe ser una lista de emails")
            except json.JSONDecodeError as exc:
                raise ValueError("CORREOS_PRUEBA tiene JSON invalido") from exc
        else:
            entries = re.split(r"[,;\n]+", raw)
    result = []
    for email in entries:
        clean = valid_email(email)
        if not clean:
            raise ValueError("CORREOS_PRUEBA contiene una direccion invalida")
        if clean not in result:
            result.append(clean)
    if len(result) > 10:
        raise ValueError("Como maximo se pueden seleccionar 10 correos de prueba")
    return result


def match_wrap_up(name, mode, allowed_names):
    mode = text_value(mode).upper()
    value = text_value(name)
    if mode == "TODOS":
        return True
    if mode == "SOLO_CON_WRAP_UP":
        return bool(value)
    if mode == "SOLO_SIN_WRAP_UP":
        return not bool(value)
    if mode == "FILTRAR_LISTA":
        if not allowed_names:
            raise ValueError("Configura WRAP_UP_LISTA_PERMITIDA dentro del script")
        return value.strip().casefold() in {text_value(x).casefold() for x in allowed_names}
    raise ValueError("WRAP_UP_MODE no valido: " + mode)


def choose_test_sample(eligible, process_day, count, seed, email_allowlist=None):
    """Muestra determinista, sin reemplazo, con emails unicos.

    Si se especifican correos, SOLO se usan destinatarios elegibles que
    ya existen en el CRM: nunca se reemplaza Email de un cliente por otro.
    """
    count = int(count)
    if not 1 <= count <= 10:
        raise ValueError("CANTIDAD_MUESTRA_PRUEBA debe estar entre 1 y 10")
    unique = {x["__PAYLOAD"]["Email"].lower(): x for x in eligible}
    if email_allowlist:
        missing = sorted(set(email_allowlist) - set(unique))
        if missing:
            raise ValueError("Los correos de prueba deben existir entre los elegibles del dia. "
                             "No coinciden: " + ", ".join(missing))
        return [unique[email] for email in email_allowlist]
    ordered = sorted(unique.values(), key=lambda x: (x["__PAYLOAD"]["Email"], x["CONVERSATION_ID"]))
    rng = random.Random(f"{process_day.isoformat()}|{seed}")
    return rng.sample(ordered, min(count, len(ordered)))


def require_identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("Nombre invalido de esquema/tabla")
    return '"' + value.upper() + '"'


def text_value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def numeric_identifier(value):
    """Normaliza ID numerico sin perder seguridad (no concatena digitos de decimales)."""
    raw = text_value(value)
    if re.fullmatch(r"\d+\.0+", raw):
        raw = raw.split(".")[0]
    raw = re.sub(r"[\s\-]", "", raw)
    if not raw or not raw.isascii() or not raw.isdigit():
        return ""
    return raw.lstrip("0")  # 0/000... son marcadores vacios, no un ID real


def normalize_belize_phone(value):
    """Solo admite numero nacional BZ de 7 digitos, con o sin 501/+501/00501."""
    raw = text_value(value).lower().removeprefix("tel:").strip()
    if not raw or re.search(r"[^0-9\s+().-]", raw):
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 12 and digits.startswith("00501"):
        digits = digits[5:]
    elif len(digits) == 10 and digits.startswith("501"):
        digits = digits[3:]
    if len(digits) != 7 or digits[0] not in "2345678":
        return ""
    return digits


def valid_email(value):
    val = text_value(value).lower()
    if val in ("", "n/a", "na", "null", "none"):
        return ""
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", val) or len(val) > 320:
        return ""
    return val


def client_identity(row):
    return numeric_identifier(row.get("BP_ID")) or numeric_identifier(row.get("EXTERNALREFERENCE"))


def parse_date_formatted(value, fmt):
    if isinstance(value, (date, datetime)):
        return value.strftime(fmt)
    raw = text_value(value)
    if not raw:
        return ""
    for item in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw[:19], item).strftime(fmt)
        except ValueError:
            pass
    # No adivinar fechas ambiguas; mantener el valor CRM original.
    return raw


def connect_hana(host, port, user, password):
    if dbapi is None:
        raise RuntimeError("Falta hdbcli: pip install hdbcli")
    return dbapi.connect(address=host, port=int(port), user=user, password=password)


def genesys_connection(write=False):
    host = global_env("HPR_HOST") if write else global_env("HPR_HOST_ESPEJO")
    return connect_hana(host, global_env("HPR_PORT"), global_env("HPR_USER"), global_env("HPR_PASSWORD"))


def belize_connection():
    return connect_hana(global_env("BZ_HANA_HOST"), global_env("BZ_HANA_PORT"), global_env("BZ_HANA_USER"), global_env("BZ_HANA_PASSWORD"))


def fetch_dict_rows(cur, size=5000):
    columns = [str(x[0]).upper() for x in cur.description]
    while True:
        block = cur.fetchmany(size)
        if not block:
            return
        for rec in block:
            yield dict(zip(columns, rec))


def get_source_timezone():
    return ZoneInfo(internal_setting("HANA_INTERACTION_TIMEZONE"))


def idioma_de_inicio(starting_language):
    """Misma regla del query: NULL/es-us = ESPAÑOL; otros = INGLES."""
    return "ESPAÑOL" if starting_language is None or text_value(starting_language).lower() == "es-us" else "INGLES"


def get_interactions(day):
    # Interpretar "ayer" como dia calendario de Belice y convertir los limites
    # a la zona en la que se almacenan los timestamps de SAP HANA.
    bz = ZoneInfo("America/Belize")
    source_tz = get_source_timezone()
    start_bz = datetime(day.year, day.month, day.day, tzinfo=bz)
    end_bz = datetime((day + timedelta(days=1)).year, (day + timedelta(days=1)).month,
                      (day + timedelta(days=1)).day, tzinfo=bz)
    start = start_bz.astimezone(source_tz).strftime("%Y-%m-%d %H:%M:%S")
    end = end_bz.astimezone(source_tz).strftime("%Y-%m-%d %H:%M:%S")
    conn = genesys_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(INTERACTIONS_SQL, (start, end, GENESYS_QUEUE_ID))
            rows = list(fetch_dict_rows(cur))
        finally:
            cur.close()
    finally:
        conn.close()
    # El join con VOICE puede multiplicar filas; consolidar por conversationId.
    grouped = defaultdict(list)
    for row in rows:
        key = text_value(row.get("CONVERSATION_ID"))
        if key:
            grouped[key].append(row)
    consolidated = []
    for group in grouped.values():
        def priority(r):
            return (bool(numeric_identifier(r.get("EXTERNAL_TAG"))),
                    bool(text_value(r.get("CC_SERVICE_DESCRIPTION"))),
                    bool(text_value(r.get("AGENTE"))),
                    bool(normalize_belize_phone(r.get("ANI"))),
                    int(r.get("SECUENCIA") or 0))
        primary = dict(max(group, key=priority))
        for field in ("EXTERNAL_TAG", "ANI", "AGENTE", "AGENTE_ID", "CC_SERVICE_DESCRIPTION", "COLA"):
            if not text_value(primary.get(field)):
                for item in sorted(group, key=priority, reverse=True):
                    if text_value(item.get(field)):
                        primary[field] = item[field]
                        break
        # STARTING_LANGUAGE corresponde al idioma de entrada de la llamada.
        # Preferimos secuencia 0 si tiene valor y, si no, secuencia 1.
        # Se conserva aunque el agente y el cierre vengan de otra secuencia.
        ordered_by_sequence = sorted(group, key=lambda item: int(item.get("SECUENCIA") or 0))
        fallback = next((r.get("STARTING_LANGUAGE") for r in ordered_by_sequence
                         if r.get("STARTING_LANGUAGE") is not None), None)
        starting = next((r.get("STARTING_LANGUAGE") for r in ordered_by_sequence
                         if text_value(r.get("STARTING_LANGUAGE"))), fallback)
        primary["STARTING_LANGUAGE"] = starting
        primary["IDIOMA"] = idioma_de_inicio(starting)
        primary["CONTAR_INTERACCION"] = 1
        consolidated.append(primary)
    LOG.info("Interacciones: %s filas originales; %s conversaciones unicas", len(rows), len(consolidated))
    return consolidated


def get_relevant_clients(interactions):
    wanted_ids = {numeric_identifier(x.get("EXTERNAL_TAG")) for x in interactions if numeric_identifier(x.get("EXTERNAL_TAG"))}
    wanted_phones = {normalize_belize_phone(x.get("ANI")) for x in interactions if not numeric_identifier(x.get("EXTERNAL_TAG")) and normalize_belize_phone(x.get("ANI"))}
    by_id, by_phone = defaultdict(list), defaultdict(list)
    nread, nrelevant = 0, 0
    conn = belize_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(CLIENTS_SQL)
            for row in fetch_dict_rows(cur, 5000):
                nread += 1
                ref = numeric_identifier(row.get("EXTERNALREFERENCE"))
                phone = normalize_belize_phone(row.get("PHONE"))
                interested = False
                if ref and ref in wanted_ids:
                    by_id[ref].append(row)
                    interested = True
                if phone and phone in wanted_phones:
                    by_phone[phone].append(row)
                    interested = True
                if interested:
                    nrelevant += 1
        finally:
            cur.close()
    finally:
        conn.close()
    LOG.info("CRM Belice: %d registros leidos, %d relevantes; %d identificaciones y %d telefonos candidatos",
             nread, nrelevant, len(by_id), len(by_phone))
    return by_id, by_phone


def resolve_customer(rows):
    if not rows:
        return None, "SIN_MATCH_CRM"
    ids = {client_identity(row) for row in rows}
    if "" in ids or len(ids) != 1:
        return None, "CLIENTES_AMBIGUOS_EN_CRM"
    emails = {valid_email(row.get("EMAIL")) for row in rows if valid_email(row.get("EMAIL"))}
    if len(emails) > 1:
        return None, "MULTIPLES_CORREOS_MISMO_CLIENTE"
    if not emails:
        return None, "SIN_CORREO_VALIDO"
    email = next(iter(emails))
    # Un mismo cliente repetido con igual identidad/correo no es telefono compartido.
    chosen = next(row for row in rows if valid_email(row.get("EMAIL")) == email)
    return chosen, ""


def get_call_date_belize(interaction):
    raw = interaction.get("CONVERSATION_START")
    if isinstance(raw, datetime):
        moment = raw
    else:
        try:
            moment = datetime.fromisoformat(text_value(raw).replace(" ", "T"))
        except ValueError:
            # Solo para casos sin timestamp completo: usa fecha de la consulta.
            return parse_date_formatted(interaction.get("FECHA"), "%m/%d/%y")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=get_source_timezone())
    return moment.astimezone(ZoneInfo("America/Belize")).strftime("%m/%d/%y")


def build_payload(client, interaction):
    """Payload original + STARTING_LANGUAGE sin modificar los campos previos."""
    return {
        "FirstName": text_value(client.get("FIRSTNAME")),
        "LastName": text_value(client.get("LASTNAME")),
        "ExternalReference": text_value(client.get("EXTERNALREFERENCE")),
        "Email": valid_email(client.get("EMAIL")),
        "Phone": normalize_belize_phone(client.get("PHONE")) or text_value(client.get("PHONE")),
        "Phone_2": normalize_belize_phone(interaction.get("ANI")),
        "BP_ID": text_value(client.get("BP_ID")),
        "Date_Of_Birth": parse_date_formatted(client.get("DATE_OF_BIRTH"), "%m/%d/%Y"),
        "CC_Date": get_call_date_belize(interaction),
        "Gender": text_value(client.get("GENDER")),
        "INTERACTION_ID": text_value(interaction.get("CONVERSATION_ID")),
        "Agent": text_value(interaction.get("AGENTE")),
        "BP_Type": text_value(client.get("BP_TYPE")),
        "CC_Service_Description": text_value(interaction.get("CC_SERVICE_DESCRIPTION")),
        "STARTING_LANGUAGE": text_value(interaction.get("STARTING_LANGUAGE")),
    }


def merged_report_record(inter, client=None, method="", reason=""):
    rec = {name: text_value(inter.get(name)) for name in INTERACTION_COLUMNS}
    rec.update({name: text_value((client or {}).get(name)) for name in CLIENT_COLUMNS})
    rec["METODO_CRUCE"] = method
    rec["ESTADO_VALIDACION"] = reason or "ELEGIBLE"
    return rec


def evaluate(interactions, id_map, phone_map):
    candidates, excluded = [], []
    for inter in interactions:
        external_tag = numeric_identifier(inter.get("EXTERNAL_TAG"))
        if external_tag:
            method, clients = "EXTERNAL_TAG", id_map.get(external_tag, [])
        else:
            method = "ANI_PHONE"
            phone = normalize_belize_phone(inter.get("ANI"))
            if not phone:
                excluded.append(merged_report_record(inter, method=method, reason="SIN_IDENTIFICADOR_NI_ANI_BZ_VALIDO"))
                continue
            clients = phone_map.get(phone, [])
        client, error = resolve_customer(clients)
        if error:
            excluded.append(merged_report_record(inter, method=method, reason=error))
            continue
        candidate = merged_report_record(inter, client=client, method=method)
        candidate["__CLIENT_KEY"] = client_identity(client)
        candidate["__PAYLOAD"] = build_payload(client, inter)
        candidates.append(candidate)

    # Distintos clientes usando el mismo email -> excluir a todos, no seleccionar uno arbitrariamente.
    email_clients = defaultdict(set)
    for item in candidates:
        email_clients[item["__PAYLOAD"]["Email"]].add(item["__CLIENT_KEY"])
    nonshared = []
    for item in candidates:
        if len(email_clients[item["__PAYLOAD"]["Email"]]) > 1:
            item["ESTADO_VALIDACION"] = "CORREO_COMPARTIDO_ENTRE_CLIENTES"
            excluded.append(item)
        else:
            nonshared.append(item)

    # Prioridad: EXTERNAL_TAG > ANI; dentro del mismo metodo, llamada mas reciente.
    def priority(item):
        return (1 if item["METODO_CRUCE"] == "EXTERNAL_TAG" else 0,
                item.get("CONVERSATION_START", ""), item.get("CONVERSATION_ID", ""))
    ordered = sorted(nonshared, key=priority, reverse=True)
    selected, seen_clients, seen_emails = [], set(), set()
    for item in ordered:
        client_key = item["__CLIENT_KEY"]
        email = item["__PAYLOAD"]["Email"]
        if client_key in seen_clients or email in seen_emails:
            item["ESTADO_VALIDACION"] = "INTERACCION_DUPLICADA_CLIENTE_O_CORREO"
            excluded.append(item)
            continue
        seen_clients.add(client_key)
        seen_emails.add(email)
        selected.append(item)
    return selected, excluded


def get_ledger_name():
    return require_identifier(internal_setting("HANA_AUDIT_SCHEMA")) + "." + require_identifier(internal_setting("HANA_AUDIT_TABLE"))


def ledger_init(conn):
    qualified = get_ledger_name()
    schema, table = [name.replace('"', '') for name in qualified.split(".")]
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM SYS.TABLES WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?", (schema, table))
        exists = int(cur.fetchone()[0]) > 0
        if not exists:
            LOG.info("Bitacora no encontrada; intentando crearla en SAP HANA")
            cur.execute(f"""CREATE COLUMN TABLE {qualified} (
                EVENT_KEY NVARCHAR(64) NOT NULL PRIMARY KEY,
                FECHA_LLAMADA DATE,
                CLIENT_KEY NVARCHAR(128),
                EMAIL NVARCHAR(320),
                INTERACTION_ID NVARCHAR(128),
                ESTADO NVARCHAR(24),
                HTTP_STATUS INTEGER,
                DETALLE NVARCHAR(500),
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UPDATED_AT TIMESTAMP
            )""")
            conn.commit()
    finally:
        cur.close()
    return qualified


def ledger_reserve(conn, qualified, event_key, item, process_date):
    """Insercion con PK unica: protege ejecuciones repetidas y concurrentes."""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT ESTADO FROM {qualified} WHERE EVENT_KEY = ?", (event_key,))
        old = cur.fetchone()
        if old:
            return False, text_value(old[0])
        try:
            cur.execute(f"""INSERT INTO {qualified}
                (EVENT_KEY, FECHA_LLAMADA, CLIENT_KEY, EMAIL, INTERACTION_ID, ESTADO, UPDATED_AT)
                VALUES (?, TO_DATE(?, 'YYYY-MM-DD'), ?, ?, ?, 'RESERVADO', CURRENT_TIMESTAMP)""",
                (event_key, process_date.isoformat(), item["__CLIENT_KEY"],
                 item["__PAYLOAD"]["Email"], item["__PAYLOAD"]["INTERACTION_ID"]))
            conn.commit()
            return True, ""
        except Exception:
            conn.rollback()
            # Puede haberlo reservado otro proceso simultaneamente.
            cur.execute(f"SELECT ESTADO FROM {qualified} WHERE EVENT_KEY = ?", (event_key,))
            simultaneous = cur.fetchone()
            if simultaneous:
                return False, text_value(simultaneous[0])
            raise
    finally:
        cur.close()


def ledger_finish(conn, qualified, key, status, code=None, description=""):
    cur = conn.cursor()
    try:
        cur.execute(f"""UPDATE {qualified}
            SET ESTADO = ?, HTTP_STATUS = ?, DETALLE = ?, UPDATED_AT = CURRENT_TIMESTAMP
            WHERE EVENT_KEY = ?""", (status, code, description[:500], key))
        conn.commit()
    finally:
        cur.close()


def post_qualtrics(session, endpoint, token, payload, max_retries=3):
    """Reintenta solo 429 (no aceptado); NO repite timeouts/5xx inciertos."""
    for attempt in range(max_retries):
        try:
            response = session.post(endpoint, json=payload, headers={
                "X-API-TOKEN": token, "Content-Type": "application/json"
            }, timeout=(10, 30), allow_redirects=False)
        except requests.RequestException:
            return "DESCONOCIDO", None, "Error de transporte: resultado incierto; revision manual"
        code = response.status_code
        if code == 429 and attempt < max_retries - 1:
            header = response.headers.get("Retry-After", "")
            wait = int(header) if header.isdigit() else 5 * (attempt + 1)
            time.sleep(min(wait, 60))
            continue
        if 200 <= code < 300:
            return "ACEPTADO", code, "Evento aceptado por Qualtrics; entrega no confirmada"
        if code == 429:
            return "RECHAZADO", code, "Limite de API Qualtrics; revisar para reintentar"
        if code >= 500:
            return "DESCONOCIDO", code, "Error del servidor Qualtrics; posible recepcion; revisar"
        return "RECHAZADO", code, "Rechazo HTTP por Qualtrics; revisar configuracion/campos"
    return "DESCONOCIDO", None, "Sin respuesta conclusiva"


def csv_safe(val):
    """Protege los archivos CSV contra interpretacion de formulas al abrirse en Excel."""
    result = text_value(val)
    if result.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + result
    return result


def write_csv(path, records, columns):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow({column: csv_safe(rec.get(column)) for column in columns})


def export_reports(output_dir, day, selected, excluded, counts, preview=False,
                   test_sample=None, mode="PREVISUALIZAR"):
    folder = Path(output_dir).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    try:
        folder.chmod(0o700)
    except OSError:
        pass
    timestamp = datetime.now(ZoneInfo("America/Belize")).strftime("%Y%m%d_%H%M%S_%f")
    stem = f"Belice_Qualtrics_{day.isoformat()}_{timestamp}"
    cols = INTERACTION_COLUMNS + CLIENT_COLUMNS + ["METODO_CRUCE", "ESTADO_VALIDACION", "ESTADO_ENVIO"]
    eligible = []
    for item in selected:
        data = dict(item)
        data["ESTADO_ENVIO"] = item.get("__STATUS", "NO_SELECCIONADO_MUESTRA"
                                         if mode in ("PREVISUALIZAR_PRUEBA", "PRUEBA_REAL")
                                         else "NO_ENVIADO_PREVIEW")
        eligible.append(data)
    excluded_clean = []
    for item in excluded:
        data = dict(item)
        data["ESTADO_ENVIO"] = "EXCLUIDO"
        excluded_clean.append(data)
    write_csv(folder / (stem + "_ELEGIBLES.csv"), eligible, cols)
    write_csv(folder / (stem + "_EXCLUIDOS.csv"), excluded_clean, cols)
    write_csv(folder / (stem + "_RESUMEN.csv"),
              [{"METRICA": k, "CANTIDAD": v} for k, v in sorted(counts.items())],
              ["METRICA", "CANTIDAD"])
    if test_sample is not None:
        to_write = []
        for item in test_sample:
            rec = dict(item)
            rec["ESTADO_ENVIO"] = item.get("__STATUS", "MUESTRA_PREVIEW_SIN_ENVIAR")
            to_write.append(rec)
        write_csv(folder / (stem + "_MUESTRA_PRUEBA.csv"), to_write, cols)
    if preview:
        payload_path = folder / (stem + "_PAYLOADS_PREVIEW.jsonl")
        payload_rows = test_sample if test_sample is not None else selected
        with payload_path.open("w", encoding="utf-8") as handle:
            for item in payload_rows:
                handle.write(json.dumps(item["__PAYLOAD"], ensure_ascii=False, default=str) + "\n")
        try:
            payload_path.chmod(0o600)
        except OSError:
            pass
    for file_path in folder.glob(stem + "*.csv"):
        try:
            file_path.chmod(0o600)
        except OSError:
            pass
    LOG.info("Reportes en %s | elegibles, excluidos, resumen%s",
             folder, ", muestra de prueba" if test_sample is not None else "")


def run(day, mode, confirm_send, output_dir, delay, wrap_up_mode="SOLO_CON_WRAP_UP",
        test_emails=None):
    LOG.info("Inicio | fecha de llamadas: %s | modo: %s | WRAP_UP: %s",
             day, mode, wrap_up_mode)
    print("PYFLOW_PROGRESS=5", flush=True)
    interactions = get_interactions(day)
    valid_interactions = []
    excluded_by_wrap = []
    permitted_names = internal_setting("WRAP_UP_LISTA_PERMITIDA")
    for interaction in interactions:
        if match_wrap_up(interaction.get("CC_SERVICE_DESCRIPTION"), wrap_up_mode, permitted_names):
            valid_interactions.append(interaction)
        else:
            excluded_by_wrap.append(merged_report_record(interaction, method="NO_EVALUADO",
                                                          reason="EXCLUIDO_FILTRO_WRAP_UP"))
    LOG.info("Filtro WRAP_UP: %s interacciones incluidas; %s excluidas",
             len(valid_interactions), len(excluded_by_wrap))
    print("PYFLOW_PROGRESS=35", flush=True)
    id_map, phone_map = get_relevant_clients(valid_interactions) if valid_interactions else ({}, {})
    print("PYFLOW_PROGRESS=60", flush=True)
    selected, excluded = evaluate(valid_interactions, id_map, phone_map)
    excluded = excluded_by_wrap + excluded
    stats = Counter(x.get("ESTADO_VALIDACION", "") for x in excluded)
    counts = {"interacciones_unicas": len(interactions),
              "interacciones_tras_filtro_wrap_up": len(valid_interactions),
              "elegibles": len(selected), "excluidos": len(excluded),
              **{"exclusion_" + k: v for k, v in stats.items()}}
    LOG.info("Cruce completado | elegibles=%s | excluidos=%s", len(selected), len(excluded))
    for k, v in sorted(stats.items()):
        LOG.info("Exclusion %s: %d", k, v)

    is_test = mode in ("PREVISUALIZAR_PRUEBA", "PRUEBA_REAL")
    test_sample = None
    if is_test:
        test_sample = choose_test_sample(selected, day,
                                         internal_setting("CANTIDAD_MUESTRA_PRUEBA"),
                                         internal_setting("SEMILLA_MUESTRA_PRUEBA"), test_emails)
        counts["correos_elegidos_prueba"] = len(test_sample)
        LOG.info("Muestra %s: elegidos=%s de %s elegibles; maximo permitido=10",
                 mode, len(test_sample), len(selected))
    to_send = test_sample if is_test else selected
    sending = mode in ("PRUEBA_REAL", "ENVIAR_TODOS")
    if sending:
        if mode == "ENVIAR_TODOS" and not confirm_send:
            raise ValueError("ENVIAR_TODOS necesita BZ_CONFIRMAR_ENVIO=True dentro del script")
        if mode == "PRUEBA_REAL" and internal_setting("PERMITIR_PRUEBA_REAL") is not True:
            raise ValueError("La prueba real esta deshabilitada en CONFIGURACION_INTERNA")
        if requests is None:
            raise RuntimeError("Falta requests: pip install requests")
        token = global_env("TOKEN_QUALTRICTS")
        endpoint = internal_setting("QUALTRICS_BZ_ENDPOINT")
        from urllib.parse import urlsplit, parse_qs
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https" or parsed.hostname != "yul1.qualtrics.com" or parsed.path != "/inbound-event/v1/events/json/triggers":
            raise ValueError("Endpoint Qualtrics inesperado: verifica host/ruta segura")
        if not parse_qs(parsed.query).get("urlTokenId"):
            raise ValueError("Falta urlTokenId en endpoint interno")
        if not to_send:
            LOG.info("Sin destinatarios para %s: no se genera ninguna llamada API", mode)
        else:
            conn = genesys_connection(write=True)
            try:
                qualified = ledger_init(conn)
                with requests.Session() as sess:
                    for index, item in enumerate(to_send, start=1):
                        event_key = hashlib.sha256((day.isoformat() + "|" + item["__CLIENT_KEY"]).encode("utf-8")).hexdigest()
                        reserved, prior = ledger_reserve(conn, qualified, event_key, item, day)
                        if not reserved:
                            item["__STATUS"] = "OMITIDO_BITACORA_" + prior
                        else:
                            status, code, detail = post_qualtrics(sess, endpoint, token, item["__PAYLOAD"])
                            item["__STATUS"] = status
                            ledger_finish(conn, qualified, event_key, status, code, detail)
                        LOG.info("Evento %d/%d | estado=%s | metodo=%s", index, len(to_send),
                                 item["__STATUS"], item["METODO_CRUCE"])
                        print(f"PYFLOW_PROGRESS={65 + int(index / len(to_send) * 25)}", flush=True)
                        if index < len(to_send) and delay > 0:
                            time.sleep(delay)
            finally:
                conn.close()
    else:
        LOG.info("%s: no se ejecuta ningun POST a Qualtrics", mode)
    counts.update({"estado_" + k: v for k, v in
                   Counter(i.get("__STATUS", "NO_ENVIADO_PREVIEW") for i in to_send).items()})
    counts["objetivos_envio"] = len(to_send)
    export_reports(output_dir, day, selected, excluded, counts,
                   preview=not sending, test_sample=test_sample, mode=mode)
    print("PYFLOW_PROGRESS=100", flush=True)
    LOG.info("RESUMEN FINAL: %s", json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description="Cruce Genesys + CRM Belice para Qualtrics")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD")
    parser.add_argument("--mode", default=None,
                        choices=["PREVISUALIZAR", "PREVISUALIZAR_PRUEBA", "PRUEBA_REAL", "ENVIAR_TODOS"],
                        help="Anula RUN_MODE de PyFlow")
    parser.add_argument("--wrap-up-mode", default=None,
                        choices=["TODOS", "SOLO_CON_WRAP_UP", "SOLO_SIN_WRAP_UP", "FILTRAR_LISTA"])
    parser.add_argument("--test-emails", default=None, help="Lista de correos separados por comas")
    parser.add_argument("--confirm-send", action="store_true", help="Confirma ENVIAR_TODOS")
    args = parser.parse_args(argv)
    chosen_date = args.date if args.date is not None else str(internal_setting("PROCESS_DATE")).strip()
    day = (date.fromisoformat(chosen_date) if chosen_date
           else datetime.now(ZoneInfo("America/Belize")).date() - timedelta(days=1))
    mode = (args.mode or pyflow_control("RUN_MODE", internal_setting("BZ_RUN_MODE"))).upper().strip()
    if mode not in ("PREVISUALIZAR", "PREVISUALIZAR_PRUEBA", "PRUEBA_REAL", "ENVIAR_TODOS"):
        raise ValueError("RUN_MODE no reconocido")
    wrap_up_mode = (args.wrap_up_mode or pyflow_control("WRAP_UP_MODE", internal_setting("WRAP_UP_MODE"))).upper().strip()
    if wrap_up_mode not in ("TODOS", "SOLO_CON_WRAP_UP", "SOLO_SIN_WRAP_UP", "FILTRAR_LISTA"):
        raise ValueError("WRAP_UP_MODE no reconocido")
    test_emails = parse_test_emails(args.test_emails if args.test_emails is not None
                                   else pyflow_control("CORREOS_PRUEBA", ""))
    if test_emails and mode not in ("PREVISUALIZAR_PRUEBA", "PRUEBA_REAL"):
        raise ValueError("CORREOS_PRUEBA solo se puede usar con modos de prueba")
    confirmed = args.confirm_send or internal_setting("BZ_CONFIRMAR_ENVIO") is True
    configured_dir = str(internal_setting("OUTPUT_DIR")).strip()
    output_dir = configured_dir or str(Path.cwd() / "reportes_belice_qualtrics")
    delay = float(internal_setting("QUALTRICS_DELAY_SECONDS"))
    if delay < 0:
        raise ValueError("QUALTRICS_DELAY_SECONDS interno no puede ser negativo")
    run(day, mode, confirmed, output_dir, delay, wrap_up_mode, test_emails)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", stream=sys.stdout)
    try:
        sys.exit(main())
    except Exception as exc:
        LOG.exception("Proceso interrumpido: %s", exc)
        print("PYFLOW_PROGRESS=0", flush=True)
        sys.exit(1)
