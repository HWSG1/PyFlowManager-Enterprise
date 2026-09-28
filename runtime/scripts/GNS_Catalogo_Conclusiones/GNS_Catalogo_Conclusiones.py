"""Carga el catálogo Genesys en BI_SS.GNS_API_CAT_CONCLUSIONES.

Dependencias: requests, hdbcli; python-dotenv opcional.
Ejecutar desde PyFlow o con Python; --dry-run consulta Genesys sin conectar a HANA.
La tabla debe existir con CONCLUSION_ID y CONCLUSION de tipo VARCHAR/NVARCHAR.
No crea tablas ni elimina conclusiones históricas. Conviene una clave única en
CONCLUSION_ID y programar una sola ejecución a la vez.
Solo carga los códigos visibles para el cliente OAuth; no inventa códigos
eliminados o de sistema que no estén presentes en el catálogo de Genesys.
Referencia API: https://developer.genesys.cloud/devapps/api-explorer
GET /api/v2/routing/wrapupcodes (pageSize, pageNumber).
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Dominio Genesys", "required": True},
    "HPR_HOST": {"type": "global", "global_key": "HPR_HOST", "label": "Servidor HANA", "required": True},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "Puerto HANA", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "Usuario HANA", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "Contraseña HANA", "required": True, "secret": True},
    "HANA_SCHEMA": {"type": "text", "label": "Esquema destino", "default": "BI_SS", "required": True},
    "HANA_TABLE": {"type": "text", "label": "Tabla catálogo de conclusiones", "default": "GNS_API_CAT_CONCLUSIONES", "required": True},
    "HANA_BATCH_SIZE": {"type": "number", "label": "Filas por lote", "default": "500", "required": False},
    "DRY_RUN": {"type": "boolean", "label": "Simular sin conectar a HANA", "default": "false", "required": False},
}

LOG = logging.getLogger("gns_catalogo_conclusiones")


def env(name, default=""):
    value = os.getenv(name, "").strip()
    return default if value.lower() in ("", "none", "null", "undefined") else value


def required(name):
    value = env(name)
    if not value:
        raise ValueError(f"Falta configurar {name}.")
    return value


def identifier(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("El esquema y la tabla deben ser identificadores SQL simples.")
    return '"' + value + '"'


def progress(value):
    print(f"PYFLOW_PROGRESS={value}", flush=True)


def retry_delay(response, attempt):
    value = response.headers.get("Retry-After", "") if response is not None else ""
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return min(60, 2 ** attempt)


class Genesys:
    def __init__(self):
        import requests
        self.requests = requests
        self.client_id = required("GENESYS_CLIENT_ID")
        self.secret = required("GENESYS_CLIENT_SECRET")
        domain = re.sub(r"^https?://", "", required("GENESYS_REGION").lower()).rstrip("/")
        self.domain = re.sub(r"^(api|login|apps)\.", "", domain)
        if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", self.domain):
            raise ValueError("GENESYS_REGION debe contener un dominio, por ejemplo mypurecloud.com.")
        self.http = requests.Session()
        self.token = ""
        self.expires = 0

    def request(self, method, url, **kwargs):
        for attempt in range(6):
            response = None
            try:
                response = self.http.request(method, url, timeout=90, **kwargs)
            except (self.requests.Timeout, self.requests.ConnectionError):
                pass
            if response is not None:
                if response.status_code < 400:
                    return response
                if response.status_code != 429 and response.status_code < 500:
                    return response
            if attempt == 5:
                raise RuntimeError("Genesys agotó los reintentos por conexión, HTTP 429 o error del servidor.")
            delay = retry_delay(response, attempt)
            LOG.warning("Reintento Genesys %s/5; espera %.1f segundos", attempt + 1, delay)
            time.sleep(delay)

    def authenticate(self):
        response = self.request("POST", f"https://login.{self.domain}/oauth/token",
                                auth=(self.client_id, self.secret), data={"grant_type": "client_credentials"})
        if response.status_code != 200:
            raise RuntimeError(f"OAuth rechazado: HTTP {response.status_code}.")
        data = response.json()
        self.token = data.get("access_token")
        if not self.token:
            raise RuntimeError("OAuth no devolvió access_token.")
        self.expires = time.monotonic() + max(1, float(data.get("expires_in", 3600)) - 60)

    def page(self, number):
        for refresh in range(2):
            if not self.token or time.monotonic() >= self.expires:
                self.authenticate()
            response = self.request("GET", f"https://api.{self.domain}/api/v2/routing/wrapupcodes",
                                    headers={"Authorization": f"Bearer {self.token}"},
                                    params={"pageSize": 100, "pageNumber": number})
            if response.status_code == 401 and refresh == 0:
                self.token = ""
                continue
            if response.status_code != 200:
                raise RuntimeError(f"Consulta de conclusiones rechazada: HTTP {response.status_code}. Revise permisos OAuth y divisiones.")
            return response.json()


def download(api):
    rows = {}
    for number in range(1, 10001):
        data = api.page(number)
        items = data.get("entities")
        if not isinstance(items, list):
            raise ValueError("Respuesta de catálogo inválida: falta entities.")
        previous = len(rows)
        for item in items:
            code, name = item.get("id"), item.get("name")
            if not isinstance(code, str) or not code.strip() or not isinstance(name, str) or not name.strip():
                raise ValueError("Genesys devolvió una conclusión sin ID o nombre válido; carga cancelada.")
            rows[code] = name
        LOG.info("Página %s: %s conclusiones únicas acumuladas", number, len(rows))
        count = data.get("pageCount")
        complete = (count is not None and number >= int(count)) or (
            count is None and not data.get("nextUri") and len(items) < 100)
        if complete:
            if data.get("total") is not None and len(rows) != int(data["total"]):
                raise RuntimeError("El total del catálogo cambió o la descarga está incompleta. Reintente la carga.")
            return sorted(rows.items())
        if not items or len(rows) == previous:
            raise RuntimeError("La paginación no avanza; carga cancelada para evitar datos incompletos.")
    raise RuntimeError("Se excedió el límite de páginas; carga cancelada.")


def save(connection, rows, schema, table, batch_size):
    target = f"{identifier(schema)}.{identifier(table)}"
    if batch_size < 1:
        raise ValueError("HANA_BATCH_SIZE debe ser mayor que cero.")
    cursor = connection.cursor()
    try:
        connection.setautocommit(False)
        cursor.execute('SELECT COLUMN_NAME, DATA_TYPE_NAME, LENGTH FROM SYS.TABLE_COLUMNS '
                       'WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?', (schema, table))
        columns = {name: (kind, size) for name, kind, size in cursor.fetchall()}
        for index, column in enumerate(("CONCLUSION_ID", "CONCLUSION")):
            if column not in columns or columns[column][0] not in ("VARCHAR", "NVARCHAR"):
                raise ValueError(f"{target} debe existir y contener {column} VARCHAR/NVARCHAR.")
            if any(len(row[index]) > int(columns[column][1]) for row in rows):
                raise ValueError(f"Un valor supera la longitud de {column}; no se truncarán datos.")
        cursor.execute(f'SELECT "CONCLUSION_ID" FROM {target} GROUP BY "CONCLUSION_ID" HAVING COUNT(*) > 1')
        if cursor.fetchone() is not None:
            raise ValueError("El catálogo destino contiene IDs duplicados; corrija los duplicados antes de cargar.")
        id_length = int(columns["CONCLUSION_ID"][1])
        name_length = int(columns["CONCLUSION"][1])
        sql = f'''MERGE INTO {target} AS T
USING (SELECT CAST(? AS NVARCHAR({id_length})) AS "CONCLUSION_ID",
              CAST(? AS NVARCHAR({name_length})) AS "CONCLUSION" FROM DUMMY) AS S
ON T."CONCLUSION_ID" = S."CONCLUSION_ID"
WHEN MATCHED THEN UPDATE SET T."CONCLUSION" = S."CONCLUSION"
WHEN NOT MATCHED THEN INSERT ("CONCLUSION_ID", "CONCLUSION")
VALUES (S."CONCLUSION_ID", S."CONCLUSION")'''
        for start in range(0, len(rows), batch_size):
            cursor.executemany(sql, rows[start:start + batch_size])
            done = min(start + batch_size, len(rows))
            LOG.info("Preparadas %s/%s filas (pendientes de confirmación)", done, len(rows))
            progress(50 + int(45 * done / len(rows)))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Consulta Genesys sin conectar a HANA")
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    dry_value = env("DRY_RUN", "false").lower()
    if dry_value not in ("true", "false", "1", "0", "yes", "no", "si", "sí"):
        raise ValueError("DRY_RUN debe ser true o false.")
    dry = args.dry_run or dry_value in ("true", "1", "yes", "si", "sí")
    schema, table = env("HANA_SCHEMA", "BI_SS"), env("HANA_TABLE", "GNS_API_CAT_CONCLUSIONES")
    identifier(schema)
    identifier(table)
    batch_size = int(env("HANA_BATCH_SIZE", "500"))
    if batch_size < 1:
        raise ValueError("HANA_BATCH_SIZE debe ser mayor que cero.")
    progress(0)
    api = Genesys()
    try:
        rows = download(api)
    finally:
        api.http.close()
    progress(50)
    if not rows:
        LOG.warning("Genesys devolvió cero conclusiones. Revise permisos y divisiones del cliente OAuth. HANA no se modificó.")
    elif dry:
        LOG.info("Simulación: %s conclusiones disponibles para %s.%s. Sin conexión HANA.", len(rows), schema, table)
    else:
        from hdbcli import dbapi
        connection = dbapi.connect(address=required("HPR_HOST"), port=int(env("HPR_PORT", "30015")),
                                   user=required("HPR_USER"), password=required("HPR_PASSWORD"), connectTimeout=15000)
        try:
            save(connection, rows, schema, table, batch_size)
        finally:
            connection.close()
        LOG.info("Carga confirmada: %s conclusiones insertadas o actualizadas en %s.%s.", len(rows), schema, table)
    progress(100)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        message = str(error)
        for key in ("GENESYS_CLIENT_SECRET", "HPR_PASSWORD"):
            if os.getenv(key):
                message = message.replace(os.environ[key], "***")
        logging.getLogger("gns_catalogo_conclusiones").error("Carga cancelada: %s", message)
        sys.exit(1)
