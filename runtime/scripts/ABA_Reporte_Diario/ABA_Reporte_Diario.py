# =========================================================
# ABA - Extracción SAP HANA, reporte ejecutivo y envío por Graph
# =========================================================
#
# OBJETIVO
# Consulta directamente SAP HANA, genera un archivo Excel, calcula
# métricas por ORDEN_ID único, crea un correo HTML ejecutivo y lo
# envía mediante Microsoft Graph, sin automatizar Excel ni Outlook.
#
# DESARROLLO / PRUEBAS
# Utiliza HPR_HOST_ESPEJO. Para habilitar producción debe cambiarse
# HANA_ENVIRONMENT a PRODUCCION; nunca se incluyen hosts ni
# credenciales directamente en este código.
#
# DEPENDENCIAS
#   pip install hdbcli pandas openpyxl requests
#
# PYFLOW_PROGRESS
# El script imprime avances con el formato:
#   PYFLOW_PROGRESS:10
#
# =========================================================

import argparse
import base64
import html
import json
import logging
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import quote

import pandas as pd
import requests
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

try:
    from hdbcli import dbapi
except ImportError:
    dbapi = None


# =========================================================
# PYFLOW MANAGER PARAMS
# =========================================================
# Mantener este bloque simple y cerca del inicio para que PyFlow
# Manager detecte los parámetros.

PYFLOW_PARAMS = {
    "HPR_HOST_ESPEJO": {
        "type": "global",
        "global_key": "HPR_HOST_ESPEJO",
        "label": "SAP HANA Host espejo",
        "required": True
    },
    "HPR_PORT": {
        "type": "global",
        "global_key": "HPR_PORT",
        "label": "SAP HANA Port",
        "required": True
    },
    "HPR_USER": {
        "type": "global",
        "global_key": "HPR_USER",
        "label": "SAP HANA User",
        "required": True
    },
    "HPR_PASSWORD": {
        "type": "global",
        "global_key": "HPR_PASSWORD",
        "label": "SAP HANA Password",
        "required": True,
        "secret": True
    },
    "FECHA_INICIO": {
        "type": "date",
        "label": "Fecha inicial",
        "required": True,
        "default": ""
    },
    "FECHA_FIN": {
        "type": "date",
        "label": "Fecha final",
        "required": True,
        "default": ""
    },
    "OUTPUT_FOLDER": {
        "type": "text",
        "label": "Carpeta de salida",
        "required": False,
        "default": "runtime/exports"
    },
    "OUTPUT_FILE": {
        "type": "text",
        "label": "Nombre del archivo Excel",
        "required": False,
        "default": "Data ABA.xlsx"
    },
    "EMAIL_TO": {
        "type": "tags",
        "label": "Destinatarios",
        "required": True
    },
    "EMAIL_CC": {
        "type": "tags",
        "label": "Destinatarios CC",
        "required": False
    },
    "GRAPH_TENANT_ID": {
        "type": "global",
        "global_key": "GRAPH_TENANT_ID",
        "label": "Microsoft Graph Tenant ID",
        "required": True
    },
    "GRAPH_CLIENT_ID": {
        "type": "global",
        "global_key": "GRAPH_CLIENT_ID",
        "label": "Microsoft Graph Client ID",
        "required": True
    },
    "GRAPH_CLIENT_SECRET": {
        "type": "global",
        "global_key": "GRAPH_CLIENT_SECRET",
        "label": "Microsoft Graph Client Secret",
        "required": True,
        "secret": True
    },
    "GRAPH_SENDER_EMAIL": {
        "type": "global",
        "global_key": "GRAPH_SENDER_EMAIL",
        "label": "Correo remitente Graph",
        "required": True
    }
}


LOGGER_NAME = "aba_hana_excel_graph_pyflow"
EXCEL_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
LOGO_CONTENT_ID = "logo-banco-atlantida"
DEFAULT_GRAPH_AUTHORITY_URL = "https://login.microsoftonline.com"
DEFAULT_GRAPH_SCOPE = "https://graph.microsoft.com/.default"
DEFAULT_QUERY_FILE = "ABA_Reclamos_En_Tramite.sql"
DEFAULT_SHEET_NAME = "Data ABA"
DEFAULT_EMAIL_SUBJECT = (
    "[Data ABA] Órdenes de Servicio CRM - {fecha_reporte}"
)
DEFAULT_REPORT_TITLE = "Órdenes de Servicio CRM · ABA"
DEFAULT_REPORT_PROCESS_NAME = "Proceso automático Data ABA"
INPUT_FOLDER_NAME = "input"
TEMPLATE_EXTENSIONS = {".html", ".htm"}
LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _clean_env_value(
    value: Any,
    default: Optional[str] = None
) -> Optional[str]:
    """Normaliza valores recibidos desde variables de entorno o PyFlow."""
    if value is None:
        return default

    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "undefined"}:
        return default

    return text


def env_str(
    name: str,
    default: Optional[str] = None,
    required: bool = False
) -> str:
    """Obtiene una variable de entorno como texto.

    Args:
        name: Nombre de la variable.
        default: Valor predeterminado.
        required: Indica si la variable es obligatoria.

    Returns:
        Valor normalizado.

    Raises:
        RuntimeError: Si la variable es requerida y no tiene valor.
    """
    value = _clean_env_value(os.getenv(name), default)
    if required and not value:
        raise RuntimeError(
            f"Falta configurar variable/parámetro requerido: {name}"
        )
    return "" if value is None else str(value)


def env_int(name: str, default: int, required: bool = False) -> int:
    """Obtiene una variable de entorno como entero."""
    value = env_str(name, str(default), required=required)
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"El parámetro {name} debe ser numérico. "
            f"Valor recibido: {value!r}"
        ) from exc


def env_bool(name: str, default: bool = False) -> bool:
    """Obtiene una variable de entorno como booleano."""
    value = env_str(name, "").lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "y", "si", "sí"}


def env_date(name: str, required: bool = False) -> date:
    """Obtiene una fecha ISO (aaaa-mm-dd) desde PyFlow."""
    value = env_str(name, "", required=required)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"El parámetro {name} debe usar el formato aaaa-mm-dd. "
            f"Valor recibido: {value!r}"
        ) from exc


def split_recipients(value: Any) -> List[str]:
    """Convierte destinatarios de PyFlow o texto separado en una lista."""
    if value is None:
        return []

    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "undefined"}:
        return []

    items: Optional[List[str]] = None
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                items = [
                    str(item).strip()
                    for item in parsed
                    if str(item).strip()
                ]
        except json.JSONDecodeError:
            pass

    if items is None:
        normalized = text.replace(";", ",").replace("\n", ",")
        items = [
            item.strip()
            for item in normalized.split(",")
            if item.strip()
        ]

    recipients: List[str] = []
    seen = set()
    for item in items:
        normalized_item = item.casefold()
        if normalized_item not in seen:
            seen.add(normalized_item)
            recipients.append(item)
    return recipients


def emit_progress(percent: int, message: str = "") -> None:
    """Publica el porcentaje de avance para PyFlow Manager."""
    safe_percent = max(0, min(100, int(percent)))
    print(f"PYFLOW_PROGRESS:{safe_percent}", flush=True)
    if message:
        print(f"PYFLOW_STATUS:{message}", flush=True)


def setup_logger() -> logging.Logger:
    """Configura el logger estándar del proceso."""
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


@dataclass(frozen=True)
class Config:
    """Configuración centralizada del proceso ABA."""

    hana_environment: str
    hana_host: str
    hana_port: int
    hana_user: str
    hana_password: str
    hana_schema: str
    query_sql: str
    query_file: str
    start_date: date
    end_date: date
    output_folder: Path
    output_file: str
    sheet_name: str
    send_email: bool
    email_to: List[str]
    email_cc: List[str]
    email_subject: str
    report_title: str
    report_process_name: str
    graph_tenant_id: str
    graph_client_id: str
    graph_client_secret: str
    graph_sender_email: str
    graph_authority_url: str
    graph_scope: str
    graph_save_to_sent_items: bool
    request_timeout: int
    max_column_width: int
    fetch_size: int

    @classmethod
    def from_env(cls) -> "Config":
        """Construye y valida la configuración desde el entorno."""
        config = cls(
            hana_environment="ESPEJO",
            hana_host=env_str("HPR_HOST_ESPEJO", required=True),
            hana_port=env_int("HPR_PORT", 30015, required=True),
            hana_user=env_str("HPR_USER", required=True),
            hana_password=env_str("HPR_PASSWORD", required=True),
            hana_schema="",
            query_sql="",
            query_file=DEFAULT_QUERY_FILE,
            start_date=env_date("FECHA_INICIO", required=True),
            end_date=env_date("FECHA_FIN", required=True),
            output_folder=Path(
                env_str("OUTPUT_FOLDER", "runtime/exports")
            ),
            output_file=env_str("OUTPUT_FILE", "Data ABA.xlsx"),
            sheet_name=DEFAULT_SHEET_NAME,
            send_email=env_bool("SEND_EMAIL", True),
            email_to=split_recipients(env_str("EMAIL_TO", "")),
            email_cc=split_recipients(env_str("EMAIL_CC", "")),
            email_subject=DEFAULT_EMAIL_SUBJECT,
            report_title=DEFAULT_REPORT_TITLE,
            report_process_name=DEFAULT_REPORT_PROCESS_NAME,
            graph_tenant_id=env_str("GRAPH_TENANT_ID", ""),
            graph_client_id=env_str("GRAPH_CLIENT_ID", ""),
            graph_client_secret=env_str(
                "GRAPH_CLIENT_SECRET",
                ""
            ),
            graph_sender_email=env_str("GRAPH_SENDER_EMAIL", ""),
            graph_authority_url=env_str(
                "GRAPH_AUTHORITY_URL",
                DEFAULT_GRAPH_AUTHORITY_URL
            ).rstrip("/"),
            graph_scope=env_str(
                "GRAPH_SCOPE",
                DEFAULT_GRAPH_SCOPE
            ),
            graph_save_to_sent_items=env_bool(
                "GRAPH_SAVE_TO_SENT_ITEMS",
                True
            ),
            request_timeout=env_int("REQUEST_TIMEOUT", 120),
            max_column_width=env_int("MAX_COLUMN_WIDTH", 60),
            fetch_size=env_int("HANA_FETCH_SIZE", 10000),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Valida reglas funcionales de configuración."""
        if dbapi is None:
            raise RuntimeError(
                "No está instalada la dependencia hdbcli. "
                "Ejecute: pip install hdbcli"
            )

        if not self.output_file.lower().endswith(".xlsx"):
            raise ValueError("OUTPUT_FILE debe finalizar en .xlsx.")

        if len(self.sheet_name) > 31:
            raise ValueError(
                "SHEET_NAME no puede exceder 31 caracteres."
            )

        if not self.query_sql and not self.query_file:
            raise ValueError(
                "Debe configurar QUERY_SQL o QUERY_FILE."
            )

        if self.start_date > self.end_date:
            raise ValueError(
                "FECHA_INICIO no puede ser posterior a FECHA_FIN."
            )

        if self.send_email:
            required_graph = {
                "EMAIL_TO": self.email_to,
                "GRAPH_TENANT_ID": self.graph_tenant_id,
                "GRAPH_CLIENT_ID": self.graph_client_id,
                "GRAPH_CLIENT_SECRET": self.graph_client_secret,
                "GRAPH_SENDER_EMAIL": self.graph_sender_email,
            }
            missing = [
                name
                for name, value in required_graph.items()
                if not value
            ]
            if missing:
                raise ValueError(
                    "Para enviar el correo faltan parámetros: "
                    + ", ".join(missing)
                )

            invalid_recipients = [
                address
                for address in [
                    *self.email_to,
                    *self.email_cc,
                    self.graph_sender_email,
                ]
                if not re.fullmatch(
                    r"[^@\s]+@[^@\s]+\.[^@\s]+",
                    address
                )
            ]
            if invalid_recipients:
                raise ValueError(
                    "Hay destinatarios con formato inválido: "
                    + ", ".join(invalid_recipients)
                )


def log_config(config: Config, logger: logging.Logger) -> None:
    """Registra la configuración aplicada sin exponer secretos."""
    logger.info("Parámetros recibidos / aplicados:")
    logger.info("- HANA_ENVIRONMENT: %s", config.hana_environment)
    logger.info("- HANA_HOST: %s", config.hana_host)
    logger.info("- HPR_PORT: %s", config.hana_port)
    logger.info("- HPR_USER: %s", config.hana_user)
    logger.info("- HPR_PASSWORD: ********")
    logger.info("- FECHA_INICIO: %s", config.start_date.isoformat())
    logger.info("- FECHA_FIN: %s", config.end_date.isoformat())
    logger.info("- QUERY_SOURCE: %s", config.query_file)
    logger.info("- OUTPUT_FOLDER: %s", config.output_folder)
    logger.info("- OUTPUT_FILE: %s", config.output_file)
    logger.info("- SHEET_NAME: %s", config.sheet_name)
    logger.info("- SEND_EMAIL: %s", config.send_email)
    logger.info(
        "- EMAIL_TO: %s",
        ", ".join(config.email_to) or "<vacío>"
    )
    logger.info(
        "- EMAIL_CC: %s",
        ", ".join(config.email_cc) or "<vacío>"
    )
    logger.info(
        "- GRAPH_SENDER_EMAIL: %s",
        config.graph_sender_email or "<vacío>"
    )


def resolve_query_path(query_file: str) -> Path:
    """Resuelve el archivo SQL desde CWD o junto al script."""
    requested = Path(query_file).expanduser()

    candidates = [requested]
    if not requested.is_absolute():
        candidates.append(Path(__file__).resolve().parent / requested)

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    searched = ", ".join(str(item) for item in candidates)
    raise FileNotFoundError(
        f"No se encontró QUERY_FILE. Rutas revisadas: {searched}"
    )


def load_query(config: Config, logger: logging.Logger) -> str:
    """Carga el SQL desde QUERY_SQL o desde QUERY_FILE."""
    if config.query_sql.strip():
        logger.info("Cargando consulta desde QUERY_SQL.")
        sql = config.query_sql.strip()
    else:
        query_path = resolve_query_path(config.query_file)
        logger.info("Cargando consulta desde: %s", query_path)
        sql = query_path.read_text(encoding="utf-8-sig").strip()

    if not sql:
        raise ValueError("La consulta SQL está vacía.")

    normalized = sql.lstrip().upper()
    if not (
        normalized.startswith("SELECT")
        or normalized.startswith("WITH")
        or normalized.startswith("--")
        or normalized.startswith("/*")
    ):
        raise ValueError(
            "La consulta debe ser de lectura y comenzar con SELECT o WITH."
        )

    start_token = "{{FECHA_INICIO}}"
    end_token = "{{FECHA_FIN}}"
    if start_token not in sql or end_token not in sql:
        raise ValueError(
            "La consulta interna debe contener los marcadores "
            "{{FECHA_INICIO}} y {{FECHA_FIN}}."
        )

    sql = sql.replace(start_token, config.start_date.isoformat())
    sql = sql.replace(end_token, config.end_date.isoformat())
    logger.info(
        "Filtro SQL aplicado: %s al %s.",
        config.start_date.isoformat(),
        config.end_date.isoformat()
    )
    return sql.rstrip().rstrip(";")


def get_hana_connection(config: Config, logger: logging.Logger) -> Any:
    """Abre una conexión directa a SAP HANA mediante hdbcli.

    Args:
        config: Configuración del proceso.
        logger: Logger de ejecución.

    Returns:
        Conexión activa de hdbcli.

    Raises:
        RuntimeError: Si no se logra establecer la conexión.
    """
    logger.info(
        "Conectando a SAP HANA %s...",
        config.hana_environment
    )

    try:
        connection = dbapi.connect(
            address=config.hana_host,
            port=config.hana_port,
            user=config.hana_user,
            password=config.hana_password,
        )

        if config.hana_schema:
            cursor = None
            try:
                cursor = connection.cursor()
                safe_schema = config.hana_schema.replace('"', '""')
                cursor.execute(f'SET SCHEMA "{safe_schema}"')
            finally:
                if cursor is not None:
                    cursor.close()

        logger.info("Conexión SAP HANA exitosa.")
        return connection
    except Exception as exc:
        raise RuntimeError(
            "No fue posible conectar con SAP HANA "
            f"{config.hana_environment}: {exc}"
        ) from exc


def execute_query(
    sql: str,
    config: Config,
    logger: logging.Logger
) -> pd.DataFrame:
    """Ejecuta un SELECT y construye un DataFrame.

    Args:
        sql: Consulta SQL a ejecutar.
        config: Configuración de SAP HANA.
        logger: Logger de ejecución.

    Returns:
        DataFrame con las columnas y registros obtenidos.

    Raises:
        RuntimeError: Si la consulta falla.
    """
    connection = None
    cursor = None
    rows: List[Sequence[Any]] = []

    try:
        connection = get_hana_connection(config, logger)
        cursor = connection.cursor()

        logger.info("Ejecutando query SQL...")
        cursor.execute(sql)

        if cursor.description is None:
            raise RuntimeError(
                "La consulta no devolvió un conjunto de resultados."
            )

        columns = [column[0] for column in cursor.description]

        while True:
            batch = cursor.fetchmany(config.fetch_size)
            if not batch:
                break
            rows.extend(batch)
            logger.info(
                "Registros recuperados hasta el momento: %s",
                f"{len(rows):,}"
            )

        dataframe = pd.DataFrame.from_records(
            rows,
            columns=columns
        )
        logger.info("Consulta finalizada.")
        logger.info(
            "Cantidad de registros obtenidos: %s",
            f"{len(dataframe):,}"
        )
        return dataframe

    except Exception as exc:
        raise RuntimeError(
            f"Error ejecutando consulta SAP HANA: {exc}"
        ) from exc
    finally:
        if cursor is not None:
            try:
                cursor.close()
                logger.info("Cursor SAP HANA cerrado.")
            except Exception:
                logger.exception("No fue posible cerrar el cursor HANA.")

        if connection is not None:
            try:
                connection.close()
                logger.info("Conexión SAP HANA cerrada.")
            except Exception:
                logger.exception("No fue posible cerrar la conexión HANA.")


def normalize_output_path(config: Config) -> Path:
    """Construye la ruta final configurable del archivo Excel."""
    config.output_folder.mkdir(parents=True, exist_ok=True)
    return (config.output_folder / config.output_file).resolve()


def _excel_safe_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas incompatibles con Excel/openpyxl."""
    result = dataframe.copy()

    for column in result.columns:
        if pd.api.types.is_datetime64tz_dtype(result[column]):
            result[column] = result[column].dt.tz_localize(None)

    return result


def generate_excel(
    dataframe: pd.DataFrame,
    config: Config,
    logger: logging.Logger
) -> Path:
    """Genera el archivo XLSX con formato profesional.

    Args:
        dataframe: Datos a exportar.
        config: Configuración de salida.
        logger: Logger de ejecución.

    Returns:
        Ruta absoluta del archivo generado.
    """
    output_path = normalize_output_path(config)
    safe_dataframe = _excel_safe_dataframe(dataframe)

    logger.info("Generando archivo Excel: %s", output_path)

    try:
        with pd.ExcelWriter(
            output_path,
            engine="openpyxl",
            datetime_format="dd/mm/yyyy hh:mm:ss",
            date_format="dd/mm/yyyy"
        ) as writer:
            safe_dataframe.to_excel(
                writer,
                sheet_name=config.sheet_name,
                index=False
            )

            worksheet = writer.sheets[config.sheet_name]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            worksheet.sheet_view.showGridLines = False

            header_fill = PatternFill(
                fill_type="solid",
                fgColor="DA282D"
            )
            header_font = Font(
                color="FFFFFF",
                bold=True
            )

            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center"
                )

            worksheet.row_dimensions[1].height = 24

            for index, column_name in enumerate(
                safe_dataframe.columns,
                start=1
            ):
                values = safe_dataframe[column_name].dropna().astype(str)
                sample = values.head(5000)
                max_data_length = (
                    int(sample.str.len().max())
                    if not sample.empty
                    else 0
                )
                width = min(
                    max(
                        len(str(column_name)) + 2,
                        max_data_length + 2,
                        10
                    ),
                    config.max_column_width
                )
                worksheet.column_dimensions[
                    get_column_letter(index)
                ].width = width

            for row in worksheet.iter_rows(
                min_row=2,
                max_row=worksheet.max_row
            ):
                for cell in row:
                    cell.alignment = Alignment(
                        vertical="top",
                        wrap_text=False
                    )

        logger.info("Archivo Excel generado correctamente.")
        return output_path

    except Exception as exc:
        raise RuntimeError(
            f"Error generando archivo Excel {output_path}: {exc}"
        ) from exc


def _normalize_name(value: Any) -> str:
    """Normaliza nombres de columnas y valores para comparaciones."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")


def _find_column(
    dataframe: pd.DataFrame,
    *candidates: str
) -> Optional[str]:
    """Busca una columna tolerando espacios, acentos y mayúsculas."""
    lookup = {
        _normalize_name(column): str(column)
        for column in dataframe.columns
    }
    for candidate in candidates:
        found = lookup.get(_normalize_name(candidate))
        if found:
            return found
    return None


def _display_text(value: Any, fallback: str = "") -> str:
    """Convierte un valor de datos en texto visible y limpio."""
    if value is None or pd.isna(value):
        return fallback
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or fallback


def _percentage(part: int, total: int) -> float:
    """Calcula un porcentaje evitando divisiones entre cero."""
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 2)


def _format_number(value: Any) -> str:
    """Formatea cantidades enteras con separador de miles."""
    return f"{int(value):,}"


def _format_date(value: Any) -> str:
    """Formatea una fecha como dd/mm/aaaa."""
    if value is None or pd.isna(value):
        return "No disponible"
    return pd.Timestamp(value).strftime("%d/%m/%Y")


def _format_time(value: datetime) -> str:
    """Formatea la hora con indicador a. m./p. m."""
    suffix = "a. m." if value.hour < 12 else "p. m."
    hour = value.hour % 12 or 12
    return f"{hour:02d}:{value.minute:02d} {suffix}"


def _variation_text(today: int, previous: int) -> Tuple[Optional[float], str]:
    """Construye una comparación diaria legible."""
    if previous == 0:
        if today == 0:
            return 0.0, "Sin órdenes hoy ni el día anterior"
        return None, "Sin base comparable el día anterior"

    variation = round(((today - previous) / previous) * 100, 2)
    sign = "+" if variation > 0 else ""
    return variation, f"{sign}{variation:.2f}% vs. día anterior"


def calculate_report_metrics(
    dataframe: pd.DataFrame,
    file_path: Path,
    report_datetime: Optional[datetime] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None
) -> Dict[str, Any]:
    """Calcula el resumen del correo usando ORDEN_ID como unidad.

    Las columnas de cliente y SLA son opcionales. Si no existen en el
    resultado SQL, esas métricas no se inventan ni se muestran.
    """
    if dataframe.empty:
        raise ValueError(
            "La consulta no devolvió registros; no se generará un "
            "reporte ejecutivo vacío."
        )

    order_column = _find_column(dataframe, "ORDEN_ID", "ORDENES_ID")
    if not order_column:
        raise ValueError(
            "La consulta debe devolver la columna ORDEN_ID para "
            "calcular métricas sin duplicar órdenes por sus pasos."
        )

    now = report_datetime or datetime.now()
    work = dataframe.copy()
    work["_REPORT_ORDER_ID"] = (
        work[order_column]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    work = work.loc[work["_REPORT_ORDER_ID"].ne("")].copy()
    if work.empty:
        raise ValueError("ORDEN_ID no contiene valores utilizables.")

    creation_column = _find_column(
        work,
        "CREACION_GESTION",
        "FECHA_CREACION",
        "INGRESO_SIST"
    )
    if creation_column:
        work["_REPORT_CREATED_AT"] = pd.to_datetime(
            work[creation_column],
            errors="coerce"
        )
    else:
        work["_REPORT_CREATED_AT"] = pd.NaT

    latest_event_column = _find_column(
        work,
        "ULTIMA_FECHA_PASO",
        "FECHA_CREACION_PASO",
        "FECHA_CAMBIO_ESTADO"
    )
    if latest_event_column:
        work["_REPORT_SORT_AT"] = pd.to_datetime(
            work[latest_event_column],
            errors="coerce"
        )
        work["_REPORT_SORT_AT"] = work["_REPORT_SORT_AT"].fillna(
            work["_REPORT_CREATED_AT"]
        )
    else:
        work["_REPORT_SORT_AT"] = work["_REPORT_CREATED_AT"]

    work = work.sort_values(
        ["_REPORT_ORDER_ID", "_REPORT_SORT_AT"],
        na_position="first",
        kind="stable"
    )

    orders = work.drop_duplicates(
        subset=["_REPORT_ORDER_ID"],
        keep="last"
    ).copy()
    total_orders = int(len(orders))
    total_rows = int(len(dataframe))
    extra_step_rows = max(total_rows - total_orders, 0)

    valid_dates = orders["_REPORT_CREATED_AT"].dropna()
    report_day = period_end or now.date()
    previous_day = report_day - timedelta(days=1)

    if valid_dates.empty:
        orders_today = 0
        orders_previous_day = 0
        data_start = None
        data_end = None
    else:
        order_dates = orders["_REPORT_CREATED_AT"].dt.date
        orders_today = int((order_dates == report_day).sum())
        orders_previous_day = int((order_dates == previous_day).sum())
        data_start = valid_dates.min()
        data_end = valid_dates.max()

    variation_pct, variation_label = _variation_text(
        orders_today,
        orders_previous_day
    )

    state_column = _find_column(
        orders,
        "ESTADO_ACTUAL",
        "ESTADO"
    )
    states: List[Dict[str, Any]] = []
    in_progress = 0
    closed = 0

    if state_column:
        orders["_REPORT_STATE_DISPLAY"] = orders[state_column].map(
            lambda value: _display_text(value, "Sin estado")
        )
        orders["_REPORT_STATE_KEY"] = orders[
            "_REPORT_STATE_DISPLAY"
        ].map(_normalize_name)

        grouped_states = (
            orders.groupby(
                "_REPORT_STATE_KEY",
                dropna=False,
                sort=False
            )["_REPORT_STATE_DISPLAY"]
            .agg(["first", "size"])
            .sort_values("size", ascending=False)
        )
        for _, row in grouped_states.iterrows():
            count = int(row["size"])
            states.append(
                {
                    "estado": str(row["first"]),
                    "cantidad": count,
                    "porcentaje": _percentage(count, total_orders),
                }
            )

        normalized_states = orders["_REPORT_STATE_KEY"]
        in_progress = int(
            normalized_states.str.contains(
                r"TRAMIT|PROCES|PENDIENT",
                regex=True,
                na=False
            ).sum()
        )
        closed = int(
            normalized_states.str.contains(
                r"CERRAD|FINALIZ|CONCLUID",
                regex=True,
                na=False
            ).sum()
        )

    returned_columns = [
        column
        for column in (
            _find_column(work, "DEVUELTO"),
            _find_column(work, "RESOLUCION"),
            _find_column(work, "DESENCADENADOR_REAL"),
        )
        if column
    ]
    returned_orders = 0
    if returned_columns:
        returned_rows = pd.Series(False, index=work.index)
        for column in returned_columns:
            normalized = work[column].map(_normalize_name)
            returned_rows = returned_rows | normalized.str.contains(
                "DEVUELT",
                na=False
            )
        returned_orders = int(
            returned_rows.groupby(work["_REPORT_ORDER_ID"]).any().sum()
        )

    client_column = _find_column(
        orders,
        "CODIGO_CLIENTE_IBS",
        "CODIGO_CLIENTE_CRM",
        "CLIENTE_ID",
        "COD_CLIENTE"
    )
    unique_clients: Optional[int] = None
    if client_column:
        client_values = (
            orders[client_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        unique_clients = int(client_values.loc[client_values.ne("")].nunique())

    sla_column = _find_column(
        orders,
        "TIEMPO_EXCEDIDO_MINUTOS",
        "TIEMPO_EXCEDIDO_HORAS"
    )
    sla_pct: Optional[float] = None
    if sla_column:
        sla_values = pd.to_numeric(
            orders[sla_column],
            errors="coerce"
        ).dropna()
        if not sla_values.empty:
            sla_pct = round(float((sla_values <= 0).mean() * 100), 2)

    responsible_column = _find_column(
        orders,
        "NOMBRE_ENCARGADO_PASO",
        "NOMBRE_OPERADOR",
        "CREADO_POR"
    )
    top_responsibles: List[Dict[str, Any]] = []
    if responsible_column:
        responsibles = orders[responsible_column].map(
            lambda value: _display_text(value, "Sin asignar")
        )
        counts = responsibles.value_counts().head(5)
        top_responsibles = [
            {"nombre": str(name), "cantidad": int(count)}
            for name, count in counts.items()
        ]

    daily_trend: List[Dict[str, Any]] = []
    if not valid_dates.empty:
        order_dates = orders["_REPORT_CREATED_AT"].dt.date
        daily_counts = order_dates.value_counts()
        for offset in range(6, -1, -1):
            current_day = report_day - timedelta(days=offset)
            daily_trend.append(
                {
                    "fecha": current_day.strftime("%d/%m/%Y"),
                    "cantidad": int(daily_counts.get(current_day, 0)),
                }
            )

    observations = (
        "Las métricas se calculan por ORDEN_ID distinto para evitar "
        "duplicar una orden cuando el archivo contiene varios pasos."
    )
    if unique_clients is None:
        observations += (
            " Clientes únicos no se muestra porque la consulta no "
            "incluye un identificador de cliente."
        )
    if sla_pct is None:
        observations += (
            " Cumplimiento SLA no se muestra porque la consulta no "
            "incluye un campo de tiempo excedido."
        )

    return {
        "report_datetime": now,
        "fecha_reporte": now.strftime("%d/%m/%Y"),
        "hora_actualizacion": _format_time(now),
        "fecha_inicio": _format_date(period_start or data_start),
        "fecha_fin": _format_date(period_end or data_end),
        "nombre_archivo": file_path.name,
        "total_registros": total_rows,
        "total_registros_formateado": (
            f"{_format_number(total_rows)} registros"
        ),
        "total_ordenes": total_orders,
        "filas_pasos_adicionales": extra_step_rows,
        "ordenes_dia": orders_today,
        "ordenes_dia_anterior": orders_previous_day,
        "variacion_diaria_pct": variation_pct,
        "variacion_diaria_texto": variation_label,
        "clientes_unicos": unique_clients,
        "ordenes_en_tramite": in_progress,
        "pct_en_tramite": _percentage(in_progress, total_orders),
        "ordenes_cerradas": closed,
        "pct_cerradas": _percentage(closed, total_orders),
        "cumplimiento_sla_pct": sla_pct,
        "ordenes_devueltas": returned_orders,
        "pct_devueltas": _percentage(returned_orders, total_orders),
        "estados": states,
        "top_responsables": top_responsibles,
        "tendencia_diaria": daily_trend,
        "observaciones": observations,
    }


def _escape(value: Any) -> str:
    """Escapa contenido dinámico antes de insertarlo en el HTML."""
    return html.escape(str(value), quote=True)


def _kpi_card(
    label: str,
    value: str,
    caption: str,
    accent: bool = False
) -> str:
    """Genera una tarjeta KPI compatible con clientes de correo."""
    value_color = "#da282d" if accent else "#2f343a"
    return f"""
      <td class="kpi-cell" width="33.33%" valign="top"
          style="padding:0 5px 10px 5px;">
        <table role="presentation" width="100%" cellspacing="0"
               cellpadding="0" border="0"
               style="border:1px solid #dde1e5; border-radius:10px;">
          <tr>
            <td style="padding:15px 14px 14px 14px;">
              <div style="font-size:11px; color:#747b83; font-weight:bold;
                          text-transform:uppercase; letter-spacing:.2px;">
                {_escape(label)}
              </div>
              <div style="font-size:25px; color:{value_color};
                          font-weight:bold; margin-top:5px;">
                {_escape(value)}
              </div>
              <div style="font-size:12px; line-height:17px; color:#7c838b;
                          margin-top:3px;">
                {_escape(caption)}
              </div>
            </td>
          </tr>
        </table>
      </td>"""


def _kpi_rows(cards: Sequence[Tuple[str, str, str, bool]]) -> str:
    """Agrupa tarjetas KPI en filas de tres columnas."""
    rows: List[str] = []
    for start in range(0, len(cards), 3):
        chunk = list(cards[start:start + 3])
        cells = [
            _kpi_card(label, value, caption, accent)
            for label, value, caption, accent in chunk
        ]
        while len(cells) < 3:
            cells.append(
                '<td class="kpi-cell" width="33.33%" '
                'style="padding:0 5px 10px 5px;"></td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(rows)


def build_email_html(
    metrics: Mapping[str, Any],
    config: Config,
    include_logo: bool
) -> str:
    """Crea el cuerpo HTML ejecutivo con estilos inline."""
    cards: List[Tuple[str, str, str, bool]] = [
        (
            "Órdenes únicas",
            _format_number(metrics["total_ordenes"]),
            "Calculadas por ORDEN_ID",
            True,
        ),
        (
            "Órdenes del día",
            _format_number(metrics["ordenes_dia"]),
            str(metrics["variacion_diaria_texto"]),
            True,
        ),
        (
            "Registros exportados",
            _format_number(metrics["total_registros"]),
            "Incluye los pasos asociados",
            True,
        ),
        (
            "En trámite",
            _format_number(metrics["ordenes_en_tramite"]),
            f'{metrics["pct_en_tramite"]:.2f}% del total',
            False,
        ),
        (
            "Cerradas",
            _format_number(metrics["ordenes_cerradas"]),
            f'{metrics["pct_cerradas"]:.2f}% del total',
            False,
        ),
    ]

    if metrics["clientes_unicos"] is not None:
        cards.append(
            (
                "Clientes únicos",
                _format_number(metrics["clientes_unicos"]),
                "Con identificador disponible",
                False,
            )
        )
    elif metrics["cumplimiento_sla_pct"] is not None:
        cards.append(
            (
                "Cumplimiento SLA",
                f'{metrics["cumplimiento_sla_pct"]:.2f}%',
                "Pasos dentro del tiempo",
                False,
            )
        )
    else:
        cards.append(
            (
                "Filas de pasos",
                _format_number(metrics["filas_pasos_adicionales"]),
                "Adicionales a las órdenes únicas",
                False,
            )
        )

    state_rows = "".join(
        (
            "<tr>"
            '<td style="padding:10px 12px; border-top:1px solid #eceef0; '
            'font-size:13px; color:#343a40;">'
            f'{_escape(item["estado"])}</td>'
            '<td align="right" style="padding:10px 12px; '
            'border-top:1px solid #eceef0; font-size:13px; '
            'color:#343a40; font-weight:bold;">'
            f'{_format_number(item["cantidad"])}</td>'
            '<td align="right" style="padding:10px 12px; '
            'border-top:1px solid #eceef0; font-size:13px; '
            'color:#6c7279;">'
            f'{item["porcentaje"]:.2f}%</td>'
            "</tr>"
        )
        for item in metrics["estados"]
    )
    if not state_rows:
        state_rows = (
            '<tr><td colspan="3" style="padding:12px; border-top:1px '
            'solid #eceef0; font-size:13px; color:#6c7279;">'
            "La consulta no incluye una columna de estado.</td></tr>"
        )

    responsible_rows = "".join(
        (
            "<tr>"
            '<td style="padding:9px 11px; border-top:1px solid #eceef0; '
            'font-size:12px; color:#454b51;">'
            f'{_escape(item["nombre"])}</td>'
            '<td align="right" width="50" style="padding:9px 11px; '
            'border-top:1px solid #eceef0; font-size:13px; '
            'color:#da282d; font-weight:bold;">'
            f'{_format_number(item["cantidad"])}</td>'
            "</tr>"
        )
        for item in metrics["top_responsables"]
    )
    if not responsible_rows:
        responsible_rows = (
            '<tr><td style="padding:12px; font-size:12px; color:#6c7279;">'
            "Sin responsable disponible</td></tr>"
        )

    trend_rows = "".join(
        (
            "<tr>"
            '<td style="padding:9px 11px; border-top:1px solid #eceef0; '
            'font-size:12px; color:#454b51;">'
            f'{_escape(item["fecha"])}</td>'
            '<td align="right" width="50" style="padding:9px 11px; '
            'border-top:1px solid #eceef0; font-size:13px; '
            'color:#2f343a; font-weight:bold;">'
            f'{_format_number(item["cantidad"])}</td>'
            "</tr>"
        )
        for item in metrics["tendencia_diaria"]
    )
    if not trend_rows:
        trend_rows = (
            '<tr><td style="padding:12px; font-size:12px; color:#6c7279;">'
            "Sin fecha de creación disponible</td></tr>"
        )

    logo_html = (
        f'<img src="cid:{LOGO_CONTENT_ID}" width="164" '
        'alt="Banco Atlántida" style="display:block; border:0; '
        'width:164px; max-width:164px; height:auto;">'
        if include_logo
        else (
            '<div style="font-size:16px; color:#da282d; '
            'font-weight:bold; padding:11px 16px;">ABA</div>'
        )
    )

    returned_alert = ""
    if int(metrics["ordenes_devueltas"]) > 0:
        returned_alert = f"""
          <tr>
            <td class="mobile-padding" style="padding:2px 32px 20px 32px;">
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0"
                     style="background-color:#fff3f3; border-left:4px solid
                            #da282d; border-radius:7px;">
                <tr>
                  <td style="padding:13px 14px; color:#7b292c;
                             font-size:13px; line-height:19px;">
                    <strong>Atención:</strong> se identificaron
                    {_format_number(metrics["ordenes_devueltas"])} órdenes
                    devueltas ({metrics["pct_devueltas"]:.2f}% del total).
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""

    preheader = (
        "Actualización diaria de órdenes de servicio CRM relacionadas "
        f"con ABA al {metrics['fecha_reporte']}."
    )

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(config.report_title)}</title>
  <style>
    @media only screen and (max-width:700px) {{
      .email-container {{ width:100% !important; }}
      .mobile-padding {{ padding-left:18px !important;
                         padding-right:18px !important; }}
      .mobile-block {{ display:block !important; width:100% !important;
                       box-sizing:border-box !important; }}
      .kpi-cell {{ display:block !important; width:100% !important;
                   padding-left:0 !important; padding-right:0 !important; }}
      .hide-mobile {{ display:none !important; }}
    }}
  </style>
</head>
<body style="margin:0; padding:0; background-color:#f3f4f6;
             font-family:Arial, Helvetica, sans-serif; color:#2f343a;">
  <div style="display:none; max-height:0; overflow:hidden; opacity:0;">
    {_escape(preheader)}
  </div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
         border="0" style="background-color:#f3f4f6;">
    <tr>
      <td align="center" style="padding:20px 10px;">
        <table role="presentation" class="email-container" width="680"
               cellspacing="0" cellpadding="0" border="0"
               style="width:680px; max-width:680px; background:#ffffff;
                      border-radius:14px; overflow:hidden;">
          <tr>
            <td style="background-color:#da282d; padding:26px 32px;">
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0">
                <tr>
                  <td valign="middle">
                    <div style="font-size:12px; line-height:16px;
                                color:#ffffff; font-weight:bold;
                                letter-spacing:1px; text-transform:uppercase;">
                      Reporte diario
                    </div>
                    <div style="font-size:25px; line-height:31px;
                                color:#ffffff; font-weight:bold;
                                margin-top:3px;">
                      {_escape(config.report_title)}
                    </div>
                    <div style="font-size:12px; line-height:18px;
                                color:#ffffff; margin-top:7px;">
                      Corte de información: {_escape(metrics["fecha_reporte"])}
                      · {_escape(metrics["hora_actualizacion"])}
                    </div>
                  </td>
                  <td class="hide-mobile" align="right" valign="middle"
                      width="190">
                    <table role="presentation" cellspacing="0" cellpadding="0"
                           border="0" style="background:#ffffff;
                           border-radius:9px;">
                      <tr><td style="padding:8px 10px;">{logo_html}</td></tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td class="mobile-padding" style="padding:28px 32px 12px 32px;">
              <div style="font-size:15px; line-height:22px; color:#41474e;">
                Buen día, equipo:
              </div>
              <div style="font-size:14px; line-height:22px; color:#555c64;
                          margin-top:11px;">
                Se comparte la actualización diaria de las
                <strong>órdenes de servicio CRM relacionadas con ABA</strong>.
                El archivo adjunto contiene el detalle disponible del
                <strong>{_escape(metrics["fecha_inicio"])}</strong> al
                <strong>{_escape(metrics["fecha_fin"])}</strong>.
              </div>
            </td>
          </tr>
          <tr>
            <td class="mobile-padding" style="padding:12px 32px 20px 32px;">
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0"
                     style="background:#f6f7f8; border:1px solid #dde1e5;
                            border-radius:10px;">
                <tr>
                  <td class="mobile-block" width="50%"
                      style="padding:14px 16px; border-right:1px solid #e3e5e8;">
                    <div style="font-size:10px; color:#7b828a; font-weight:bold;
                                letter-spacing:.7px;">ARCHIVO ADJUNTO</div>
                    <div style="font-size:13px; color:#30363c; font-weight:bold;
                                margin-top:5px;">
                      {_escape(metrics["nombre_archivo"])}
                    </div>
                  </td>
                  <td class="mobile-block" width="50%"
                      style="padding:14px 16px;">
                    <div style="font-size:10px; color:#7b828a; font-weight:bold;
                                letter-spacing:.7px;">REGISTROS INCLUIDOS</div>
                    <div style="font-size:13px; color:#30363c; font-weight:bold;
                                margin-top:5px;">
                      {_escape(metrics["total_registros_formateado"])}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td class="mobile-padding" style="padding:0 27px 10px 27px;">
              <div style="font-size:16px; color:#30363c; font-weight:bold;
                          padding:0 5px 13px 5px;">Resumen ejecutivo</div>
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0">
                {_kpi_rows(cards)}
              </table>
            </td>
          </tr>
          {returned_alert}
          <tr>
            <td class="mobile-padding" style="padding:0 32px 22px 32px;">
              <div style="font-size:16px; color:#30363c; font-weight:bold;
                          margin-bottom:12px;">Distribución por estado</div>
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0"
                     style="border:1px solid #dde1e5; border-radius:10px;
                            border-collapse:separate; overflow:hidden;">
                <tr style="background:#f0f2f4;">
                  <th align="left" style="padding:10px 12px; font-size:11px;
                      color:#59616a;">Estado</th>
                  <th align="right" style="padding:10px 12px; font-size:11px;
                      color:#59616a;">Cantidad</th>
                  <th align="right" style="padding:10px 12px; font-size:11px;
                      color:#59616a;">Participación</th>
                </tr>
                {state_rows}
              </table>
            </td>
          </tr>
          <tr>
            <td class="mobile-padding" style="padding:0 24px 22px 24px;">
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0">
                <tr>
                  <td class="mobile-block" width="50%" valign="top"
                      style="padding:0 8px;">
                    <div style="font-size:15px; color:#30363c; font-weight:bold;
                                margin-bottom:10px;">Top responsables</div>
                    <table role="presentation" width="100%" cellspacing="0"
                           cellpadding="0" border="0"
                           style="border:1px solid #dde1e5;
                                  border-radius:9px;">
                      {responsible_rows}
                    </table>
                  </td>
                  <td class="mobile-block" width="50%" valign="top"
                      style="padding:0 8px;">
                    <div style="font-size:15px; color:#30363c; font-weight:bold;
                                margin-bottom:10px;">Órdenes creadas · 7 días</div>
                    <table role="presentation" width="100%" cellspacing="0"
                           cellpadding="0" border="0"
                           style="border:1px solid #dde1e5;
                                  border-radius:9px;">
                      {trend_rows}
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td class="mobile-padding" style="padding:0 32px 22px 32px;">
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0"
                     style="background:#f7f8f9; border-radius:9px;">
                <tr>
                  <td style="padding:13px 15px; font-size:12px;
                             line-height:18px; color:#656c74;">
                    <strong>Nota metodológica:</strong>
                    {_escape(metrics["observaciones"])}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td class="mobile-padding" style="padding:3px 32px 28px 32px;">
              <div style="font-size:13px; line-height:19px; color:#555c64;">
                Saludos cordiales,<br>
                <strong>Equipo ABA</strong>
              </div>
            </td>
          </tr>
          <tr>
            <td align="center" style="background:#f0f2f4; padding:14px 20px;
                                     font-size:11px; color:#7b828a;">
              {_escape(config.report_process_name)} ·
              {_escape(metrics["fecha_reporte"])}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _select_input_file(
    input_folder: Path,
    extensions: set[str],
    preferred_names: Sequence[str],
    description: str
) -> Path:
    """Selecciona un recurso de input sin pedir rutas al usuario."""
    for name in preferred_names:
        candidate = input_folder / name
        if candidate.is_file():
            return candidate.resolve()

    candidates = sorted(
        path.resolve()
        for path in input_folder.iterdir()
        if path.is_file() and path.suffix.lower() in extensions
    )
    if not candidates:
        allowed = ", ".join(sorted(extensions))
        raise FileNotFoundError(
            f"No se encontró {description} en {input_folder}. "
            f"Extensiones permitidas: {allowed}."
        )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise ValueError(
            f"Hay más de un archivo posible para {description} en "
            f"{input_folder}: {names}. Deje solamente uno."
        )
    return candidates[0]


def resolve_input_assets() -> Tuple[Path, Path]:
    """Obtiene automáticamente plantilla y logo desde la carpeta input."""
    script_folder = Path(
        env_str(
            "PYFLOW_SCRIPT_DIR",
            str(Path(__file__).resolve().parent)
        )
    ).resolve()
    input_folder = script_folder / INPUT_FOLDER_NAME
    if not input_folder.is_dir():
        raise FileNotFoundError(
            f"No existe la carpeta de entrada requerida: {input_folder}"
        )

    template_path = _select_input_file(
        input_folder,
        TEMPLATE_EXTENSIONS,
        (
            "plantilla_correo_ordenes_aba.html",
            "plantilla_correo_aba.html",
        ),
        "la plantilla HTML"
    )
    logo_path = _select_input_file(
        input_folder,
        LOGO_EXTENSIONS,
        (
            "Logo_Banco_Atlantida_Email.png",
            "Logo Banco.png",
        ),
        "el logo"
    )
    return template_path, logo_path


def _image_content_type(path: Path) -> str:
    """Devuelve el MIME de una imagen permitida."""
    if path.suffix.lower() == ".png":
        return "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    raise ValueError(f"Formato de logo no admitido: {path.suffix}")


def _template_cards(
    metrics: Mapping[str, Any]
) -> List[Tuple[str, str, str, bool]]:
    """Construye las seis tarjetas del resumen externo."""
    cards: List[Tuple[str, str, str, bool]] = [
        (
            "Órdenes únicas",
            _format_number(metrics["total_ordenes"]),
            "Calculadas por ORDEN_ID",
            True,
        ),
        (
            "Órdenes del día",
            _format_number(metrics["ordenes_dia"]),
            str(metrics["variacion_diaria_texto"]),
            True,
        ),
        (
            "Registros exportados",
            _format_number(metrics["total_registros"]),
            "Incluye los pasos asociados",
            True,
        ),
        (
            "En trámite",
            _format_number(metrics["ordenes_en_tramite"]),
            f'{metrics["pct_en_tramite"]:.2f}% del total',
            False,
        ),
        (
            "Cerradas",
            _format_number(metrics["ordenes_cerradas"]),
            f'{metrics["pct_cerradas"]:.2f}% del total',
            False,
        ),
    ]
    if metrics["clientes_unicos"] is not None:
        cards.append(
            (
                "Clientes únicos",
                _format_number(metrics["clientes_unicos"]),
                "Con identificador disponible",
                False,
            )
        )
    elif metrics["cumplimiento_sla_pct"] is not None:
        cards.append(
            (
                "Cumplimiento SLA",
                f'{metrics["cumplimiento_sla_pct"]:.2f}%',
                "Pasos dentro del tiempo",
                False,
            )
        )
    else:
        cards.append(
            (
                "Filas de pasos",
                _format_number(metrics["filas_pasos_adicionales"]),
                "Adicionales a las órdenes únicas",
                False,
            )
        )
    return cards


def render_input_template(
    template_path: Path,
    metrics: Mapping[str, Any],
    config: Config
) -> str:
    """Renderiza la plantilla HTML encontrada en input.

    La plantilla usa marcadores simples para no requerir Jinja2 dentro
    del runtime de PyFlow.
    """
    template = template_path.read_text(encoding="utf-8-sig")

    state_rows = "".join(
        (
            "<tr>"
            '<td style="padding:10px 12px; border-top:1px solid #eceef0; '
            'font-size:13px; color:#343a40;">'
            f'{_escape(item["estado"])}</td>'
            '<td align="right" style="padding:10px 12px; '
            'border-top:1px solid #eceef0; font-size:13px; '
            'color:#343a40; font-weight:bold;">'
            f'{_format_number(item["cantidad"])}</td>'
            '<td align="right" style="padding:10px 12px; '
            'border-top:1px solid #eceef0; font-size:13px; '
            'color:#6c7279;">'
            f'{item["porcentaje"]:.2f}%</td>'
            "</tr>"
        )
        for item in metrics["estados"]
    )
    if not state_rows:
        state_rows = (
            '<tr><td colspan="3" style="padding:12px; border-top:1px '
            'solid #eceef0; font-size:13px; color:#6c7279;">'
            "La consulta no incluye una columna de estado.</td></tr>"
        )

    responsible_rows = "".join(
        (
            "<tr>"
            f'<td style="padding:9px 11px; border-top:'
            f'{"0" if index == 0 else "1px solid #eceef0"}; '
            'font-size:12px; line-height:17px; color:#454b51;">'
            f'{_escape(item["nombre"])}</td>'
            f'<td align="right" width="48" style="padding:9px 11px; '
            f'border-top:{"0" if index == 0 else "1px solid #eceef0"}; '
            'font-size:13px; color:#da282d; font-weight:bold;">'
            f'{_format_number(item["cantidad"])}</td>'
            "</tr>"
        )
        for index, item in enumerate(metrics["top_responsables"])
    )
    if not responsible_rows:
        responsible_rows = (
            '<tr><td style="padding:12px; font-size:12px; color:#6c7279;">'
            "Sin responsable disponible</td></tr>"
        )

    trend_rows = "".join(
        (
            "<tr>"
            f'<td style="padding:9px 11px; border-top:'
            f'{"0" if index == 0 else "1px solid #eceef0"}; '
            'font-size:12px; color:#454b51;">'
            f'{_escape(item["fecha"])}</td>'
            f'<td align="right" width="48" style="padding:9px 11px; '
            f'border-top:{"0" if index == 0 else "1px solid #eceef0"}; '
            'font-size:13px; color:#2f343a; font-weight:bold;">'
            f'{_format_number(item["cantidad"])}</td>'
            "</tr>"
        )
        for index, item in enumerate(metrics["tendencia_diaria"])
    )
    if not trend_rows:
        trend_rows = (
            '<tr><td style="padding:12px; font-size:12px; color:#6c7279;">'
            "Sin fecha de creación disponible</td></tr>"
        )

    returned_alert = ""
    if int(metrics["ordenes_devueltas"]) > 0:
        returned_alert = (
            '<tr><td class="mobile-padding" '
            'style="padding:2px 32px 20px 32px;">'
            '<table role="presentation" width="100%" cellspacing="0" '
            'cellpadding="0" border="0" style="background-color:#fff5f5; '
            'border-left:4px solid #da282d; border-radius:7px;"><tr>'
            '<td style="padding:12px 14px; font-size:13px; line-height:20px; '
            'color:#6d3235;"><strong>Atención:</strong> se identificaron '
            f'{_format_number(metrics["ordenes_devueltas"])} órdenes '
            f'devueltas ({metrics["pct_devueltas"]:.2f}% del total).'
            "</td></tr></table></td></tr>"
        )

    observations_block = ""
    if metrics.get("observaciones"):
        observations_block = (
            '<tr><td class="mobile-padding" '
            'style="padding:0 32px 22px 32px;"><table role="presentation" '
            'width="100%" cellspacing="0" cellpadding="0" border="0" '
            'style="background-color:#f7f7f8; border-radius:10px;"><tr>'
            '<td style="padding:14px 16px;"><div style="font-size:12px; '
            'color:#6f757c; text-transform:uppercase; font-weight:bold; '
            'letter-spacing:.5px;">Observaciones</div><div '
            'style="font-size:13px; line-height:20px; color:#4c5258; '
            f'margin-top:5px;">{_escape(metrics["observaciones"])}</div>'
            "</td></tr></table></td></tr>"
        )

    replacements = {
        "REPORT_TITLE": _escape(config.report_title),
        "FECHA_REPORTE": _escape(metrics["fecha_reporte"]),
        "HORA_ACTUALIZACION": _escape(metrics["hora_actualizacion"]),
        "FECHA_INICIO": _escape(metrics["fecha_inicio"]),
        "FECHA_FIN": _escape(metrics["fecha_fin"]),
        "NOMBRE_ARCHIVO": _escape(metrics["nombre_archivo"]),
        "TOTAL_REGISTROS_FORMATEADO": _escape(
            metrics["total_registros_formateado"]
        ),
        "NOMBRE_PROCESO": _escape(config.report_process_name),
        "LOGO_HTML": (
            f'<table role="presentation" cellspacing="0" cellpadding="0" '
            'border="0" style="background:#ffffff; border-radius:9px;">'
            '<tr><td style="padding:8px 10px;">'
            f'<img src="cid:{LOGO_CONTENT_ID}" width="164" '
            'alt="Banco Atlántida" style="display:block; border:0; '
            'width:164px; max-width:164px; height:auto;"></td></tr></table>'
        ),
        "KPI_ROWS": _kpi_rows(_template_cards(metrics)),
        "RETURNED_ALERT": returned_alert,
        "ESTADOS_FILAS": state_rows,
        "RESPONSABLES_FILAS": responsible_rows,
        "TENDENCIA_FILAS": trend_rows,
        "OBSERVACIONES_BLOQUE": observations_block,
    }

    required_markers = {f"{{{{{key}}}}}" for key in replacements}
    missing = sorted(
        marker for marker in required_markers if marker not in template
    )
    if missing:
        raise ValueError(
            "La plantilla de input no contiene estos marcadores "
            f"requeridos: {', '.join(missing)}"
        )

    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))

    unresolved = sorted(set(re.findall(r"\{\{[A-Z][A-Z0-9_]*\}\}", rendered)))
    if unresolved:
        raise ValueError(
            "La plantilla conserva marcadores sin resolver: "
            + ", ".join(unresolved)
        )
    return rendered


def render_subject(
    template: str,
    metrics: Mapping[str, Any]
) -> str:
    """Aplica variables seguras al asunto configurable."""
    values = {
        "fecha_reporte": metrics["fecha_reporte"],
        "total_ordenes": metrics["total_ordenes"],
        "total_registros": metrics["total_registros"],
        "nombre_archivo": metrics["nombre_archivo"],
    }
    try:
        return template.format_map(values)
    except (KeyError, ValueError) as exc:
        raise ValueError(
            "EMAIL_SUBJECT contiene una variable no admitida. "
            "Use: {fecha_reporte}, {total_ordenes}, "
            "{total_registros} o {nombre_archivo}."
        ) from exc


def get_graph_access_token(
    config: Config,
    logger: logging.Logger
) -> str:
    """Obtiene token OAuth2 client_credentials para Microsoft Graph."""
    token_url = (
        f"{config.graph_authority_url}/"
        f"{config.graph_tenant_id}/oauth2/v2.0/token"
    )

    logger.info("Solicitando token Microsoft Graph...")
    response = requests.post(
        token_url,
        data={
            "client_id": config.graph_client_id,
            "client_secret": config.graph_client_secret,
            "scope": config.graph_scope,
            "grant_type": "client_credentials",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        timeout=config.request_timeout,
    )

    if response.status_code >= 400:
        raise RuntimeError(
            "Error obteniendo token Microsoft Graph. "
            f"HTTP {response.status_code}: {response.text[:1000]}"
        )

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError(
            "Microsoft Graph no devolvió access_token."
        )

    logger.info("Token Microsoft Graph obtenido correctamente.")
    return str(token)


def _graph_recipients(
    recipients: Sequence[str]
) -> List[dict[str, dict[str, str]]]:
    """Construye destinatarios en formato Microsoft Graph."""
    return [
        {"emailAddress": {"address": address}}
        for address in recipients
    ]


def send_report_email(
    file_path: Path,
    subject: str,
    email_html: str,
    logo_path: Optional[Path],
    config: Config,
    logger: logging.Logger
) -> None:
    """Envía el Excel generado como adjunto mediante Microsoft Graph.

    Args:
        file_path: Ruta del archivo Excel.
        subject: Asunto ya renderizado.
        email_html: Cuerpo HTML ya renderizado.
        logo_path: Logo opcional para adjuntar de forma inline.
        config: Configuración Graph y correo.
        logger: Logger de ejecución.
    """
    if not file_path.is_file():
        raise FileNotFoundError(
            f"No existe el archivo a adjuntar: {file_path}"
        )

    graph_token = get_graph_access_token(config, logger)

    with file_path.open("rb") as attachment:
        encoded_attachment = base64.b64encode(
            attachment.read()
        ).decode("utf-8")

    attachments: List[Dict[str, Any]] = [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": file_path.name,
            "contentType": EXCEL_CONTENT_TYPE,
            "contentBytes": encoded_attachment,
        }
    ]

    if logo_path and f"cid:{LOGO_CONTENT_ID}" in email_html:
        encoded_logo = base64.b64encode(
            logo_path.read_bytes()
        ).decode("utf-8")
        attachments.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": logo_path.name,
                "contentType": _image_content_type(logo_path),
                "contentBytes": encoded_logo,
                "isInline": True,
                "contentId": LOGO_CONTENT_ID,
            }
        )

    payload = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": email_html,
            },
            "toRecipients": _graph_recipients(
                config.email_to
            ),
            "ccRecipients": _graph_recipients(
                config.email_cc
            ),
            "attachments": attachments,
        },
        "saveToSentItems": config.graph_save_to_sent_items,
    }

    url = (
        "https://graph.microsoft.com/v1.0/users/"
        f"{quote(config.graph_sender_email, safe='@')}/sendMail"
    )

    logger.info(
        "Enviando correo por Microsoft Graph | "
        "remitente: %s | para: %s | cc: %s",
        config.graph_sender_email,
        ", ".join(config.email_to),
        ", ".join(config.email_cc) if config.email_cc else "<sin cc>",
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

    if response.status_code not in {200, 202}:
        raise RuntimeError(
            "Error enviando correo por Microsoft Graph. "
            f"HTTP {response.status_code}: {response.text[:1500]}"
        )

    logger.info("Correo enviado correctamente por Microsoft Graph.")


def build_parser() -> argparse.ArgumentParser:
    """Crea argumentos opcionales para ejecución fuera de PyFlow."""
    parser = argparse.ArgumentParser(
        description=(
            "Consulta SAP HANA, genera Data ABA.xlsx "
            "y lo envía mediante Microsoft Graph."
        )
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Genera el Excel sin enviar el correo."
    )
    parser.add_argument(
        "--output-folder",
        help="Sobrescribe temporalmente OUTPUT_FOLDER."
    )
    parser.add_argument(
        "--output-file",
        help="Sobrescribe temporalmente OUTPUT_FILE."
    )
    return parser


def apply_cli_overrides(args: argparse.Namespace) -> None:
    """Aplica argumentos CLI como variables de entorno."""
    if args.no_email:
        os.environ["SEND_EMAIL"] = "false"
    if args.output_folder:
        os.environ["OUTPUT_FOLDER"] = args.output_folder
    if args.output_file:
        os.environ["OUTPUT_FILE"] = args.output_file


def main() -> int:
    """Ejecuta extracción, Excel, resumen HTML y envío por Graph."""
    parser = build_parser()
    args = parser.parse_args()
    apply_cli_overrides(args)

    logger = setup_logger()
    started_at = time.time()
    output_path: Optional[Path] = None
    row_count = 0
    order_count = 0

    logger.info("=" * 80)
    logger.info("INICIO PROCESO AUTOMÁTICO DATA ABA")
    logger.info("Script: ABA_Reporte_Diario.py")
    logger.info("=" * 80)
    emit_progress(2, "Inicio del proceso")

    try:
        logger.info("Inicializando configuración...")
        config = Config.from_env()
        log_config(config, logger)
        emit_progress(10, "Configuración validada")

        template_path, logo_path = resolve_input_assets()
        logger.info("Plantilla tomada de input: %s", template_path)
        logger.info("Logo tomado de input: %s", logo_path)

        sql = load_query(config, logger)
        emit_progress(18, "Consulta SQL cargada")

        dataframe = execute_query(sql, config, logger)
        row_count = len(dataframe)
        emit_progress(65, f"Consulta completada: {row_count} registros")

        output_path = generate_excel(dataframe, config, logger)
        emit_progress(82, "Archivo Excel generado")

        metrics = calculate_report_metrics(
            dataframe,
            output_path,
            period_start=config.start_date,
            period_end=config.end_date
        )
        order_count = int(metrics["total_ordenes"])
        logger.info(
            "Métricas calculadas sobre %s órdenes únicas.",
            f"{order_count:,}"
        )

        email_html = render_input_template(
            template_path,
            metrics,
            config
        )
        subject = render_subject(config.email_subject, metrics)
        emit_progress(88, "Resumen ejecutivo generado")

        if config.send_email:
            logger.info("Iniciando envío de correo...")
            send_report_email(
                output_path,
                subject,
                email_html,
                logo_path,
                config,
                logger
            )
            emit_progress(98, "Correo enviado correctamente")
        else:
            logger.info(
                "SEND_EMAIL=false. El archivo fue generado "
                "sin enviar correo."
            )
            emit_progress(98, "Ejecución sin envío de correo")

        elapsed = time.time() - started_at
        logger.info("=" * 80)
        logger.info("PROCESO FINALIZADO CORRECTAMENTE")
        logger.info("Registros exportados: %s", f"{row_count:,}")
        logger.info("Órdenes únicas: %s", f"{order_count:,}")
        logger.info("Archivo generado: %s", output_path)
        logger.info("Duración total: %.2f segundos", elapsed)
        logger.info("=" * 80)
        emit_progress(100, "Proceso finalizado correctamente")
        return 0

    except Exception as exc:
        elapsed = time.time() - started_at
        logger.exception("El proceso terminó con error: %s", exc)
        logger.info("=" * 80)
        logger.info("RESUMEN FINAL CON ERROR")
        logger.info("Registros obtenidos: %s", f"{row_count:,}")
        logger.info("Órdenes únicas calculadas: %s", f"{order_count:,}")
        logger.info(
            "Archivo generado: %s",
            output_path if output_path else "No generado"
        )
        logger.info("Duración total: %.2f segundos", elapsed)
        logger.info("=" * 80)
        emit_progress(100, "Proceso finalizado con error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
