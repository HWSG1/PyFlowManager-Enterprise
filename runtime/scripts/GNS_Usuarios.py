"""
MigraciÃ³n de flujo KNIME "GNS Usuarios" a Python.

QuÃ© hace:
1. Obtiene token OAuth Client Credentials de Genesys Cloud.
2. Consulta /api/v2/users de forma paginada.
3. Extrae campos: ID, NAME, DIVISION_ID, EMAIL, USERNAME, STATE, JABBERID, TITLE.
4. Convierte NAME a mayÃºsculas, igual que el nodo String Manipulation de KNIME.
5. Realiza UPSERT/MERGE en SAP HANA sobre BI_SS.GNS_API_USUARIOS.
6. Muestra progreso en consola y resumen final.

Requisitos:
    pip install requests python-dotenv hdbcli

Variables de entorno requeridas:
    GENESYS_CLIENT_ID
    GENESYS_CLIENT_SECRET
    HPR_HOST
    HPR_PORT
    HPR_USER
    HPR_PASSWORD

Variables opcionales:
    GENESYS_REGION_URL=https://api.mypurecloud.com
    GENESYS_LOGIN_URL=https://login.mypurecloud.com/oauth/token
    HANA_SCHEMA=BI_SS
    HANA_TABLE=GNS_API_USUARIOS
    PAGE_SIZE=100
    COMMIT_EVERY=500
"""

from __future__ import annotations

import logging
import os
import traceback
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


# =========================================================
# PYFLOW MANAGER PARAMS
# =========================================================
# PyFlow detecta este bloque para solicitar parÃ¡metros y mapear variables globales.
# Las llaves del diccionario son los nombres que el script leerÃ¡ desde variables
# de entorno durante la ejecuciÃ³n.

PYFLOW_PARAMS = {
    "GENESYS_CLIENT_ID": {"type": "global", "global_key": "GENESYS_CLIENT_ID", "label": "Genesys Client ID", "required": True},
    "GENESYS_CLIENT_SECRET": {"type": "global", "global_key": "GENESYS_CLIENT_SECRET", "label": "Genesys Client Secret", "required": True, "secret": True},
    "GENESYS_REGION": {"type": "global", "global_key": "GENESYS_REGION", "label": "Genesys Region / Domain", "required": True},
    "HPR_HOST": {"type": "global", "global_key": "HPR_HOST", "label": "SAP HANA Host", "required": True},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "SAP HANA Port", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "SAP HANA User", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "SAP HANA Password", "required": True, "secret": True},
    "HANA_SCHEMA": {"type": "text", "label": "Esquema HANA", "required": True, "default": "BI_SS"},
    "HANA_TABLE": {"type": "text", "label": "Tabla destino usuarios", "required": True, "default": "GNS_API_USUARIOS"}
}

LOGGER_NAME = "gns_usuarios_pyflow"


def pyflow_progress(percent: int) -> None:
    percent = max(0, min(100, int(percent)))
    print(f"PYFLOW_PROGRESS={percent}", flush=True)


def _clean_env_value(value: Any, default: Optional[str] = None) -> Optional[str]:
    """Normaliza valores recibidos desde PyFlow, CLI o .env."""
    if value is None:
        return default
    text = str(value).strip()
    if text == "" or text.lower() in ("null", "none", "undefined"):
        return default
    return text


def env_str(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = _clean_env_value(os.getenv(name), default)
    if required and not value:
        raise ValueError(f"Falta configurar variable/parÃ¡metro requerido: {name}")
    return "" if value is None else str(value)


def env_int(name: str, default: int, required: bool = False) -> int:
    value = env_str(name, str(default), required=required)
    try:
        return int(value)
    except Exception:
        raise ValueError(f"El parÃ¡metro {name} debe ser numÃ©rico. Valor recibido: {value!r}")


def env_float(name: str, default: float, required: bool = False) -> float:
    value = env_str(name, str(default), required=required)
    try:
        return float(value)
    except Exception:
        raise ValueError(f"El parÃ¡metro {name} debe ser numÃ©rico. Valor recibido: {value!r}")


def env_bool(name: str, default: bool = False) -> bool:
    value = env_str(name, "", required=False).lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "y", "si", "sÃ­")


def normalize_genesys_domain(value: str) -> str:
    """Acepta mypurecloud.com, api.mypurecloud.com o URL completa."""
    value = env_str("GENESYS_REGION", value, required=False)
    value = str(value or "mypurecloud.com").strip()
    value = value.replace("https://", "").replace("http://", "").strip("/")
    if value.startswith("api."):
        value = value[4:]
    if value.startswith("login."):
        value = value[6:]
    return value


def genesys_api_url_from_region(default_region: str = "mypurecloud.com") -> str:
    domain = normalize_genesys_domain(default_region)
    return f"https://api.{domain}"


def genesys_login_url_from_region(default_region: str = "mypurecloud.com") -> str:
    domain = normalize_genesys_domain(default_region)
    return f"https://login.{domain}/oauth/token"


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


def log_params(logger: logging.Logger, names: List[str]) -> None:
    logger.info("ParÃ¡metros recibidos / aplicados:")
    secret_words = ("SECRET", "PASSWORD", "TOKEN", "KEY")
    for name in names:
        value = env_str(name, "")
        if any(w in name.upper() for w in secret_words) and value:
            value = "********"
        logger.info("- %s: %s", name, value if value != "" else "<vacÃ­o>")

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from hdbcli import dbapi
except ImportError:
    dbapi = None


@dataclass
class Config:
    genesys_client_id: str
    genesys_client_secret: str
    genesys_region_url: str = "https://api.mypurecloud.com"
    genesys_login_url: str = "https://login.mypurecloud.com/oauth/token"
    HPR_HOST: str = ""
    HPR_PORT: int = 30015
    HPR_USER: str = ""
    HPR_PASSWORD: str = ""
    hana_schema: str = "BI_SS"
    hana_table: str = "GNS_API_USUARIOS"
    page_size: int = 100
    commit_every: int = 500

    @staticmethod
    def from_env() -> "Config":
        return Config(
            genesys_client_id=env_str("GENESYS_CLIENT_ID", required=True),
            genesys_client_secret=env_str("GENESYS_CLIENT_SECRET", required=True),
            genesys_region_url=env_str("GENESYS_REGION_URL", genesys_api_url_from_region(), required=False).rstrip("/"),
            genesys_login_url=env_str("GENESYS_LOGIN_URL", genesys_login_url_from_region(), required=False),
            HPR_HOST=env_str("HPR_HOST", required=True),
            HPR_PORT=env_int("HPR_PORT", 30015),
            HPR_USER=env_str("HPR_USER", required=True),
            HPR_PASSWORD=env_str("HPR_PASSWORD", required=True),
            hana_schema=env_str("HANA_SCHEMA", "BI_SS"),
            hana_table=env_str("HANA_TABLE", "GNS_API_USUARIOS"),
            page_size=env_int("PAGE_SIZE", 100),
            commit_every=env_int("COMMIT_EVERY", 500),
        )


def setup_logging() -> logging.Logger:
    return setup_logger()


def get_access_token(config: Config, logger: logging.Logger) -> str:
    logger.info("Solicitando token OAuth en Genesys Cloud...")
    response = requests.post(
        config.genesys_login_url,
        data={
            "grant_type": "client_credentials",
            "client_id": config.genesys_client_id,
            "client_secret": config.genesys_client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=env_int("REQUEST_TIMEOUT_SECONDS", 90),
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Genesys no devolviÃ³ access_token.")
    logger.info("Token obtenido correctamente.")
    pyflow_progress(10)
    return token


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    logger: logging.Logger,
    retries: int = None,
    **kwargs: Any,
) -> requests.Response:
    if retries is None:
        retries = env_int("MAX_RETRIES", 5)
    for attempt in range(1, retries + 1):
        response = session.request(method, url, timeout=env_int("REQUEST_TIMEOUT_SECONDS", 90), **kwargs)
        if response.status_code not in (429, 500, 502, 503, 504):
            response.raise_for_status()
            return response

        wait_seconds = min(30, 2 ** attempt)
        logger.warning(
            "Intento %s/%s fallÃ³ con HTTP %s. Reintentando en %s segundos...",
            attempt,
            retries,
            response.status_code,
            wait_seconds,
        )
        time.sleep(wait_seconds)

    response.raise_for_status()
    return response


def fetch_users(config: Config, token: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})

    users: List[Dict[str, Any]] = []
    page_number = 1
    page_count: Optional[int] = None

    logger.info("Iniciando lectura paginada de usuarios...")

    while page_count is None or page_number <= page_count:
        url = (
            f"{config.genesys_region_url}/api/v2/users"
            f"?pageSize={config.page_size}&pageNumber={page_number}"
        )
        response = request_with_retry(session, "GET", url, logger)
        payload = response.json()

        page_count = int(payload.get("pageCount") or 1)
        entities = payload.get("entities") or []
        users.extend(entities)

        logger.info(
            "PÃ¡gina %s/%s procesada | usuarios en pÃ¡gina: %s | acumulado: %s",
            page_number,
            page_count,
            len(entities),
            len(users),
        )

        pyflow_progress(10 + int((page_number / max(page_count, 1)) * 40))

        if not entities and page_number >= page_count:
            break

        page_number += 1

    logger.info("Lectura finalizada. Total usuarios obtenidos: %s", len(users))
    return users


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None


def transform_user(user: Dict[str, Any]) -> Dict[str, Optional[str]]:
    division = user.get("division") or {}
    chat = user.get("chat") or {}

    name = clean_text(user.get("name"))
    return {
        "ID": clean_text(user.get("id")),
        "NAME": name.upper() if name else None,
        "DIVISION_ID": clean_text(division.get("id")),
        "EMAIL": clean_text(user.get("email")),
        "USERNAME": clean_text(user.get("username")),
        "STATE": clean_text(user.get("state")),
        "JABBERID": clean_text(chat.get("jabberId")),
        "TITLE": clean_text(user.get("title")),
    }


def transform_users(users: Iterable[Dict[str, Any]], logger: logging.Logger) -> List[Dict[str, Optional[str]]]:
    rows = [transform_user(user) for user in users]
    rows = [row for row in rows if row.get("ID")]
    logger.info("Usuarios transformados vÃ¡lidos para carga: %s", len(rows))
    pyflow_progress(60)
    return rows


def hana_connect(config: Config):
    if dbapi is None:
        raise RuntimeError(
            "No estÃ¡ instalado hdbcli. Ejecuta: pip install hdbcli"
        )
    return dbapi.connect(
        address=config.HPR_HOST,
        port=config.HPR_PORT,
        user=config.HPR_USER,
        password=config.HPR_PASSWORD,
    )


def upsert_users_to_hana(
    config: Config,
    rows: List[Dict[str, Optional[str]]],
    logger: logging.Logger,
) -> Tuple[int, int]:
    if not rows:
        logger.warning("No hay filas para cargar en HANA.")
        return 0, 0

    full_table = f'"{config.hana_schema}"."{config.hana_table}"'
    columns = ["ID", "NAME", "DIVISION_ID", "EMAIL", "USERNAME", "STATE", "JABBERID", "TITLE"]

    sql = f"""
    UPSERT {full_table}
    ("ID", "NAME", "DIVISION_ID", "EMAIL", "USERNAME", "STATE", "JABBERID", "TITLE")
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    WITH PRIMARY KEY
    """

    logger.info("Conectando a SAP HANA...")
    conn = hana_connect(config)
    cursor = conn.cursor()

    loaded = 0
    failed = 0

    try:
        logger.info("Iniciando carga UPSERT en %s...", full_table)
        batch: List[Tuple[Optional[str], ...]] = []

        for index, row in enumerate(rows, start=1):
            batch.append(tuple(row.get(column) for column in columns))

            if len(batch) >= config.commit_every or index == len(rows):
                try:
                    cursor.executemany(sql, batch)
                    conn.commit()
                    loaded += len(batch)
                    logger.info(
                        "Carga parcial confirmada | lote: %s | cargados acumulados: %s/%s",
                        len(batch),
                        loaded,
                        len(rows),
                    )
                    pyflow_progress(65 + int((loaded / max(len(rows), 1)) * 30))
                except Exception as exc:
                    conn.rollback()
                    failed += len(batch)
                    logger.exception("Error cargando lote de %s filas: %s", len(batch), exc)
                finally:
                    batch.clear()

    finally:
        cursor.close()
        conn.close()

    return loaded, failed


def main() -> int:
    logger = setup_logging()
    start_time = time.time()
    pyflow_progress(1)

    summary = {
        "genesys_obtenidos": 0,
        "transformados": 0,
        "cargados": 0,
        "fallidos": 0,
        "errores": [],
    }

    try:
        config = Config.from_env()
        log_params(logger, ["GENESYS_CLIENT_ID", "GENESYS_CLIENT_SECRET", "GENESYS_REGION", "HPR_HOST", "HPR_PORT", "HPR_USER", "HPR_PASSWORD", "HANA_SCHEMA", "HANA_TABLE"])
        pyflow_progress(5)
        token = get_access_token(config, logger)
        raw_users = fetch_users(config, token, logger)
        summary["genesys_obtenidos"] = len(raw_users)

        rows = transform_users(raw_users, logger)
        summary["transformados"] = len(rows)

        loaded = 0
        failed = 0

        loaded, failed = upsert_users_to_hana(config, rows, logger)

        summary["cargados"] = loaded
        summary["fallidos"] = failed

    except Exception as exc:
        logger.exception("El proceso terminÃ³ con error: %s", exc)
        logger.error(traceback.format_exc())
        summary["errores"].append(str(exc))

    elapsed = round(time.time() - start_time, 2)

    logger.info("=" * 70)
    logger.info("RESUMEN FINAL")
    logger.info("Usuarios obtenidos desde Genesys: %s", summary["genesys_obtenidos"])
    logger.info("Usuarios transformados vÃ¡lidos: %s", summary["transformados"])
    logger.info("Filas cargadas/actualizadas en HANA: %s", summary["cargados"])
    logger.info("Filas fallidas: %s", summary["fallidos"])
    logger.info("Errores generales: %s", len(summary["errores"]))
    if summary["errores"]:
        for err in summary["errores"]:
            logger.error("Detalle error: %s", err)
    logger.info("DuraciÃ³n total: %s segundos", elapsed)
    logger.info("=" * 70)

    pyflow_progress(100)

    return 1 if summary["errores"] or summary["fallidos"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

