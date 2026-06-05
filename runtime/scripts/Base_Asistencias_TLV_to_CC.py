#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyFlow Manager - Base Asistencias TLV a CC

Objetivo:
- Leer dos archivos Excel principales: Activaciones TC y Bienvenida TC.
- Filtrar clientes contactados.
- Extraer columnas clave: DNI, CLIENTE_CRM, CLIENTE_IBS.
- Consultar SAP HANA en servidor espejo para enriquecer información del cliente.
- Generar salida en Excel o CSV para descarga desde PyFlow.

Regla HANA:
- Este flujo SOLO consulta HANA, por lo tanto usa HPR_HOST_ESPEJO.
- No realiza INSERT, UPDATE ni DELETE.
"""

import os
import sys
import re
import time
import argparse
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

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
    "HPR_HOST_ESPEJO": {"type": "global", "global_key": "HPR_HOST_ESPEJO", "label": "SAP HANA Host Espejo", "required": True},
    "HPR_PORT": {"type": "global", "global_key": "HPR_PORT", "label": "SAP HANA Port", "required": True},
    "HPR_USER": {"type": "global", "global_key": "HPR_USER", "label": "SAP HANA User", "required": True},
    "HPR_PASSWORD": {"type": "global", "global_key": "HPR_PASSWORD", "label": "SAP HANA Password", "required": True, "secret": True},

    "FILE_ACTIVACIONES": {"type": "file", "label": "Excel Activaciones TC", "required": True, "accept": ".xlsx,.xls"},
    "FILE_BIENVENIDA": {"type": "file", "label": "Excel Bienvenida TC", "required": True, "accept": ".xlsx,.xls"},

    "SHEET_NAME": {"type": "text", "label": "Nombre de hoja", "required": True, "default": "DATA (2)"},
    "MES_ACTIVACIONES": {"type": "number", "label": "Mes a filtrar en Activaciones", "required": False, "default": "5"},
    "MES_BIENVENIDA": {"type": "number", "label": "Mes a filtrar en Bienvenida", "required": False, "default": "4"},
    "CONTACTO_VALUE": {"type": "text", "label": "Valor de Contacto a filtrar", "required": True, "default": "Contactado"},

    "BASE_MENSUAL_MONTH": {"type": "number", "label": "Mes de base mensual HANA", "required": True, "default": "5"},
    "BASE_MENSUAL_YEAR": {"type": "number", "label": "Año de base mensual HANA", "required": True, "default": "2026"},

    "OUTPUT_FORMAT": {"type": "select", "label": "Formato de salida", "required": True, "options": ["xlsx", "csv"], "default": "xlsx"},
    "OUTPUT_DIR": {"type": "text", "label": "Carpeta de salida", "required": False, "default": ""},
    "OUTPUT_FILENAME": {"type": "text", "label": "Nombre de archivo salida", "required": False, "default": "Base_Asistencias_TLV_CC"},
    "MAX_INPUT_ROWS": {"type": "number", "label": "Máximo filas de entrada; 0 = sin límite", "required": False, "default": "0"},
    "HANA_CHUNK_SIZE": {"type": "number", "label": "Clientes por consulta HANA", "required": False, "default": "500"},
}

LOGGER_NAME = "base_asistencias_tlv_cc"


def env_str(name: str, default: str = "", required: bool = False) -> str:
    value = os.getenv(name)
    if value is None:
        value = default
    value = str(value).strip()
    if value.lower() in ("null", "none", "undefined"):
        value = ""
    if required and not value:
        raise ValueError(f"Falta parámetro requerido: {name}")
    return value


def env_int(name: str, default: int, required: bool = False) -> int:
    value = env_str(name, str(default), required=required)
    if value == "":
        return default
    try:
        return int(float(value))
    except Exception:
        raise ValueError(f"El parámetro {name} debe ser numérico. Valor recibido: {value!r}")


def setup_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(fmt)
    logger.addHandler(h)
    return logger


@dataclass
class Config:
    hpr_host_espejo: str
    hpr_port: int
    hpr_user: str
    hpr_password: str
    file_activaciones: str
    file_bienvenida: str
    sheet_name: str
    mes_activaciones: Optional[int]
    mes_bienvenida: Optional[int]
    contacto_value: str
    base_month: int
    base_year: int
    output_format: str
    output_dir: str
    output_filename: str
    max_input_rows: int
    hana_chunk_size: int


def load_config() -> Config:
    load_dotenv()
    return Config(
        hpr_host_espejo=env_str("HPR_HOST_ESPEJO", required=True),
        hpr_port=env_int("HPR_PORT", 30015, required=True),
        hpr_user=env_str("HPR_USER", required=True),
        hpr_password=env_str("HPR_PASSWORD", required=True),
        file_activaciones=env_str("FILE_ACTIVACIONES", required=True),
        file_bienvenida=env_str("FILE_BIENVENIDA", required=True),
        sheet_name=env_str("SHEET_NAME", "DATA (2)", required=True),
        mes_activaciones=env_int("MES_ACTIVACIONES", 0) or None,
        mes_bienvenida=env_int("MES_BIENVENIDA", 0) or None,
        contacto_value=env_str("CONTACTO_VALUE", "Contactado", required=True),
        base_month=env_int("BASE_MENSUAL_MONTH", 5, required=True),
        base_year=env_int("BASE_MENSUAL_YEAR", 2026, required=True),
        output_format=env_str("OUTPUT_FORMAT", "xlsx").lower(),
        output_dir=env_str("OUTPUT_DIR", ""),
        output_filename=env_str("OUTPUT_FILENAME", "Base_Asistencias_TLV_CC"),
        max_input_rows=env_int("MAX_INPUT_ROWS", 0),
        hana_chunk_size=env_int("HANA_CHUNK_SIZE", 500),
    )


def normalize_col(col: Any) -> str:
    text = str(col).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def clean_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    text = re.sub(r"[^0-9A-Za-z]", "", text)
    return text


def read_excel_contactados(path: str, sheet_name: str, mes: Optional[int], contacto_value: str, source_name: str, logger: logging.Logger) -> pd.DataFrame:
    if not path or not Path(path).exists():
        raise FileNotFoundError(f"No existe el archivo {source_name}: {path}")

    logger.info("Leyendo archivo %s: %s | hoja: %s", source_name, path, sheet_name)
    df = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
    df.columns = [normalize_col(c) for c in df.columns]
    df["ORIGEN_ARCHIVO"] = source_name

    required = ["DNI", "CLIENTE_CRM", "CLIENTE_IBS", "Contacto"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"El archivo {source_name} no contiene columnas requeridas: {missing}")

    before = len(df)
    df = df[df["Contacto"].astype(str).str.strip().eq(contacto_value)].copy()
    logger.info("%s | filtro Contacto=%s: %s -> %s filas", source_name, contacto_value, before, len(df))

    if mes is not None:
        if "MES" not in df.columns:
            raise ValueError(f"El archivo {source_name} no contiene columna MES para filtrar mes={mes}")
        before = len(df)
        mes_num = pd.to_numeric(df["MES"], errors="coerce")
        df = df[mes_num.eq(mes)].copy()
        logger.info("%s | filtro MES=%s: %s -> %s filas", source_name, mes, before, len(df))

    keep_cols = [c for c in ["DNI", "CLIENTE_CRM", "CLIENTE_IBS", "Contacto", "MES", "DIA", "FECHA Llamada", "usuario", "ORIGEN_ARCHIVO"] if c in df.columns]
    out = df[keep_cols].copy()
    out["DNI"] = out["DNI"].map(clean_id)
    out["CLIENTE_CRM"] = out["CLIENTE_CRM"].map(clean_id)
    out["CLIENTE_IBS"] = out["CLIENTE_IBS"].map(clean_id)
    out = out[(out["CLIENTE_CRM"] != "") | (out["CLIENTE_IBS"] != "") | (out["DNI"] != "")].copy()
    return out


def hana_connect_read(config: Config):
    if dbapi is None:
        raise RuntimeError("No está instalado hdbcli. Ejecuta: pip install hdbcli")
    return dbapi.connect(
        address=config.hpr_host_espejo,
        port=config.hpr_port,
        user=config.hpr_user,
        password=config.hpr_password,
    )


def chunks(items: List[str], size: int) -> Iterable[List[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def sql_literal_list(values: List[str]) -> str:
    safe = []
    for v in values:
        v = str(v).strip()
        if not v:
            continue
        safe.append("'" + v.replace("'", "''") + "'")
    return ",".join(safe) if safe else "''"


def build_hana_query(crm_ids: List[str], ibs_ids: List[str], base_month: int, base_year: int) -> str:
    crm_in = sql_literal_list(crm_ids)
    ibs_in = sql_literal_list(ibs_ids)
    return f"""
WITH BASE_MENSUAL AS (
    SELECT DISTINCT COD_CLIENTE_IBS, CAST(COD_CLIENTE_CRM AS INT) AS COD_CLIENTE_CRM
    FROM BI_SS.BASES_ASISTENCIAS_CC
    WHERE MONTH(FECHA_CARGA) = {int(base_month)}
      AND YEAR(FECHA_CARGA) = {int(base_year)}
      AND UPPER(TIPO_BASE) NOT LIKE '%PYME%'
),
TEL_HANA AS (
    SELECT * FROM (
        SELECT TEL.COD_CLIENTE_IBS, TEL.COD_CLIENTE_CRM,
            CASE WHEN TEL.IDENTIDAD IN ('N/A','NA') OR TEL.IDENTIDAD IS NULL THEN
                CASE WHEN LENGTH(REPLACE(TRIM(DCS.IDENTIFICACION1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(DCS.IDENTIFICACION1),'-',''))
                ELSE REPLACE(TRIM(DCS.IDENTIFICACION1),'-','') END
            ELSE TEL.IDENTIDAD END AS IDENTIDAD,
            TEL.TEL, TEL.PRIORIDAD, TEL.FECHA_ULTIMA_ACTUALIZACION, TEL.N
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY COD_CLIENTE_CRM, TEL ORDER BY PRIORIDAD ASC) AS N
            FROM (
                SELECT COD_CLIENTE_IBS, COD_CLIENTE_CRM,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION_1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION_1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION_1),'-','') END AS IDENTIDAD,
                    REPLACE(REPLACE(TRIM(TEL_CELULAR),'-',''),' ','') AS TEL, 20 AS PRIORIDAD, FECHA_ULTIMA_ACTUALIZACION
                FROM DS_STG.CRM_DIM_CLIENTES WHERE SEGMENTO_BANCA = 'SEGMENTO PERSONAS'
                UNION
                SELECT COD_CLIENTE_IBS, COD_CLIENTE_CRM,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION_1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION_1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION_1),'-','') END,
                    REPLACE(REPLACE(TRIM(TEL_PRINCIPAL),'-',''),' ',''), 21, FECHA_ULTIMA_ACTUALIZACION
                FROM DS_STG.CRM_DIM_CLIENTES WHERE SEGMENTO_BANCA = 'SEGMENTO PERSONAS'
                UNION
                SELECT COD_CLIENTE_IBS, COD_CLIENTE_CRM,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION_1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION_1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION_1),'-','') END,
                    REPLACE(REPLACE(TRIM(TEL_RESIDENCIA),'-',''),' ',''), 22, FECHA_ULTIMA_ACTUALIZACION
                FROM DS_STG.CRM_DIM_CLIENTES WHERE SEGMENTO_BANCA = 'SEGMENTO PERSONAS'
                UNION
                SELECT COD_CLIENTE_IBS, COD_CLIENTE_CRM,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION_1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION_1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION_1),'-','') END,
                    RIGHT(REPLACE(REPLACE(TRIM(TEL_AREA),'-',''),' ',''),8), 23, FECHA_ULTIMA_ACTUALIZACION
                FROM DS_STG.CRM_DIM_CLIENTES WHERE SEGMENTO_BANCA = 'SEGMENTO PERSONAS'
                UNION
                SELECT COD_CLIENTE_IBS, COD_CLIENTE_CRM,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION_1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION_1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION_1),'-','') END,
                    REPLACE(REPLACE(TRIM(TELEFONO_OFICINA),'-',''),' ',''), 24, FECHA_ULTIMA_ACTUALIZACION
                FROM DS_STG.CRM_DIM_CLIENTES WHERE SEGMENTO_BANCA = 'SEGMENTO PERSONAS'
            )
            WHERE LENGTH(TEL) = 8
              AND TEL NOT IN ('20000000','29999999','99999999','88888888','77777777','11111111','33333333','22222222','22200000','25252525')
              AND LENGTH(COD_CLIENTE_IBS) > 1 AND LENGTH(COD_CLIENTE_CRM) > 1 AND IDENTIDAD IS NOT NULL
        ) TEL
        LEFT JOIN DS_STG.DIM_CLIENTES_SGMT1 DCS ON TEL.COD_CLIENTE_IBS = DCS.COD_CLIENTE
    ) WHERE N = 1
),
TEL_HANA_SISCARD AS (
    SELECT * FROM (
        SELECT TEL.*, CDC.COD_CLIENTE_CRM
        FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY COD_CLIENTE_IBS, TEL ORDER BY PRIORIDAD ASC) AS N
            FROM (
                SELECT COD_CLIENTE AS COD_CLIENTE_IBS,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION1),'-','') END AS IDENTIDAD,
                    REPLACE(REPLACE(TRIM(TEL_CEL),'-',''),' ','') AS TEL, 30 AS PRIORIDAD, ULTIMA_FECHA_ACTUALIZACION
                FROM DS_STG.DIM_CLIENTES_SGMT1 WHERE BANCA_SEGMENTACION = 'PERSONAS'
                UNION
                SELECT COD_CLIENTE,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION1),'-','') END,
                    REPLACE(REPLACE(TRIM(TEL_CASA),'-',''),' ',''), 31, ULTIMA_FECHA_ACTUALIZACION
                FROM DS_STG.DIM_CLIENTES_SGMT1 WHERE BANCA_SEGMENTACION = 'PERSONAS'
                UNION
                SELECT COD_CLIENTE,
                    CASE WHEN LENGTH(REPLACE(TRIM(IDENTIFICACION1),'-','')) = 12 THEN CONCAT(0, REPLACE(TRIM(IDENTIFICACION1),'-','')) ELSE REPLACE(TRIM(IDENTIFICACION1),'-','') END,
                    REPLACE(REPLACE(TRIM(TEL_OFICINA),'-',''),' ',''), 32, ULTIMA_FECHA_ACTUALIZACION
                FROM DS_STG.DIM_CLIENTES_SGMT1 WHERE BANCA_SEGMENTACION = 'PERSONAS'
            ) WHERE LENGTH(TEL) = 8
              AND TEL NOT IN ('20000000','29999999','88888888','77777777','99999999','11111111','33333333','22222222','22200000','25252525')
        ) TEL LEFT JOIN DS_STG.CRM_DIM_CLIENTES CDC ON TEL.COD_CLIENTE_IBS = CDC.COD_CLIENTE_IBS
    ) WHERE N = 1
),
ACUMULADO_TEL AS (
    SELECT * FROM (
        SELECT PPAL.*, ROW_NUMBER() OVER (PARTITION BY IDENTIDAD, TEL ORDER BY PRIORIDAD_CANAL ASC, NUM_COLUM ASC) AS N
        FROM (
            SELECT IDENTIDAD, COD_CLIENTE_IBS, COD_CLIENTE_CRM, TEL, PRIORIDAD AS NUM_COLUM, CASE WHEN LEFT(TEL,1) = '2' THEN 'FIJO' ELSE 'CEL' END AS TIPO_TEL, 2 AS PRIORIDAD_CANAL FROM TEL_HANA
            UNION
            SELECT IDENTIDAD, COD_CLIENTE_IBS, COD_CLIENTE_CRM, TEL, PRIORIDAD AS NUM_COLUM, CASE WHEN LEFT(TEL,1) = '2' THEN 'FIJO' ELSE 'CEL' END AS TIPO_TEL, 4 AS PRIORIDAD_CANAL FROM TEL_HANA_SISCARD
        ) PPAL WHERE LEFT(PPAL.TEL,1) NOT IN ('1','°','5','4','6','0','º')
    ) WHERE N = 1
),
TEL_PRIORIZADO AS (
    SELECT COD_CLIENTE_IBS, MAX(COD_CLIENTE_CRM) AS COD_CLIENTE_CRM, MAX(IDENTIDAD) AS DNI,
        MAX(CASE WHEN RN = 1 THEN TEL END) AS PHONE,
        MAX(CASE WHEN RN = 2 THEN TEL END) AS PHONE2,
        MAX(CASE WHEN RN = 3 THEN TEL END) AS PHONE3,
        MAX(CASE WHEN RN = 4 THEN TEL END) AS PHONE4
    FROM (
        SELECT COD_CLIENTE_IBS, COD_CLIENTE_CRM, IDENTIDAD, TEL,
            ROW_NUMBER() OVER (PARTITION BY COD_CLIENTE_IBS ORDER BY CASE WHEN TIPO_TEL = 'CEL' THEN 1 ELSE 2 END, PRIORIDAD_CANAL ASC, NUM_COLUM ASC) AS RN
        FROM ACUMULADO_TEL
    ) WHERE RN <= 4 GROUP BY COD_CLIENTE_IBS
),
ASYS_VAP AS (
    SELECT CLIENTE AS COD_CLIENTE_IBS,
        MAX(CASE WHEN (UPPER(FUNDES) LIKE '%ASISTENCIA%' OR UPPER(FUNDES) LIKE '%AUXILIO VIAL%' OR UPPER(FUNDES) LIKE '%AUXILIO VIP%' OR UPPER(FUNDES) LIKE '%AUXILIO PLUS%' OR UPPER(FUNDES) LIKE '%MUJER%' OR UPPER(FUNDES) LIKE '%PYME%') AND UPPER(DESCRIPCION_ESTADO) = 'ACTIVO' THEN 1 ELSE 0 END) AS TIENE_ASYS,
        MAX(CASE WHEN UPPER(DESCRIPCION_ESTADO) IN ('INACTIVO','CANCELADO') THEN 1 ELSE 0 END) AS TIENE_ASYS_CANCELADA_INACTIVA
    FROM DS_STG.FACT_DEBITOS_AUTOMATICOS
    WHERE FECHA_INGRESO >= '2020-01-01' AND USUARIO_APERTURA NOT IN ('ATLAGDSD')
    GROUP BY CLIENTE
),
VAP_DIM AS (
    SELECT NUMERO_CLIENTE AS COD_CLIENTE_IBS, MAX(CASE WHEN ESTADO_ACTUAL = 'A' THEN 1 ELSE 0 END) AS TIENE_VAP
    FROM DS_STG.DIM_VIDA_ATLANTIDA_PLUS GROUP BY NUMERO_CLIENTE
),
FALLECIDOS AS (
    SELECT COD_CLIENTE_IBS, MAX(FECHA) AS CTE_FALLECIDO FROM BI_SS.FN_CTES_FALLECIDOS() GROUP BY COD_CLIENTE_IBS
),
ULTIMA_ASIGNACION AS (
    SELECT COD_CLIENTE_IBS, MAX(FECHA_CARGA) AS FEC_ULTIMA_ASIGNACION FROM BI_SS.BASES_ASISTENCIAS_CC GROUP BY COD_CLIENTE_IBS
),
CLIENTES_BASE AS (
    SELECT CDC.COD_CLIENTE_IBS, CAST(CDC.COD_CLIENTE_CRM AS INT) AS COD_CLIENTE_CRM, CDC.IDENTIFICACION_1 AS DNI,
        LOWER(TRIM(CDC.E_MAIL)) AS EMAIL, CDC.PRIMER_NOMBRE, CDC.PRIMER_APELLIDO, CDC.SEGMENTO_BANCA, CDC.GENERO,
        CDC.DEPARTAMENTO, CDC.ESTADO_CIVIL, CDC.EMPLEADO,
        CASE WHEN TRIM(CDC.FECHA_NACIMIENTO) IS NULL OR TRIM(CDC.FECHA_NACIMIENTO) = '' OR LENGTH(TRIM(CDC.FECHA_NACIMIENTO)) < 4 OR LEFT(TRIM(CDC.FECHA_NACIMIENTO),4) NOT BETWEEN '1900' AND TO_VARCHAR(YEAR(CURRENT_DATE))
            THEN NULL ELSE YEAR(CURRENT_DATE) - CAST(LEFT(TRIM(CDC.FECHA_NACIMIENTO),4) AS INT) END AS EDAD
    FROM DS_STG.CRM_DIM_CLIENTES CDC
    WHERE CDC.COD_CLIENTE_IBS IS NOT NULL AND LENGTH(CDC.COD_CLIENTE_IBS) > 1
      AND (TO_VARCHAR(CDC.COD_CLIENTE_CRM) IN ({crm_in}) OR TO_VARCHAR(CDC.COD_CLIENTE_IBS) IN ({ibs_in}))
)
SELECT
    COALESCE(TP.DNI, C.DNI) AS DNI,
    C.EMAIL, TP.PHONE, TP.PHONE2, TP.PHONE3, TP.PHONE4,
    C.PRIMER_NOMBRE AS "PRIMER NOMBRE", C.PRIMER_APELLIDO AS "SEGUNDO NOMBRE",
    C.COD_CLIENTE_CRM AS CLIENTE_CRM, C.COD_CLIENTE_IBS AS CLIENTE_IBS,
    'SERVICIO AL CLIENTE' AS DIVISION, NULL AS FECHA, NULL AS HORA, NULL AS ID_INTERACCION, NULL AS AGENTE, NULL AS CONCLUSION,
    C.SEGMENTO_BANCA AS BANCA, C.GENERO, 'CLIENTES CONTACTADOS ACTIVACIONES Y BIENVENIDA TC' AS BASE,
    CAST(CURRENT_DATE AS DATE) AS INICIO_BASE, NULL AS VENCIMIENTO_BASE, 'ASISTENCIAS Y VAP' AS PRODUCTO_PRINCIPAL,
    C.DEPARTAMENTO, C.ESTADO_CIVIL, C.EDAD, 'CONTACTADOS BIENVENIDA Y ACTIVACIONES TC' AS CAMPANIA,
    CAST(CURRENT_DATE AS DATE) AS FECHA_DE_CARGA, 'ATLÁNTIDA' AS "TIME/ZONE", F.CTE_FALLECIDO, UA.FEC_ULTIMA_ASIGNACION,
    CASE WHEN BM.COD_CLIENTE_IBS IS NOT NULL THEN 'SI' ELSE 'NO' END AS ESTA_EN_BASE_MENSUAL,
    CASE WHEN UPPER(C.EMPLEADO) = 'SI' THEN 'SI' ELSE 'NO' END AS ES_EMPLEADO,
    CASE WHEN COALESCE(VD.TIENE_VAP,0) = 1 THEN 'SI' ELSE 'NO' END AS TIENE_VAP,
    CASE WHEN COALESCE(AV.TIENE_ASYS,0) = 1 THEN 'SI' ELSE 'NO' END AS TIENE_ASYS,
    CASE WHEN COALESCE(AV.TIENE_ASYS_CANCELADA_INACTIVA,0) = 1 THEN 'SI' ELSE 'NO' END AS TIENE_ASYS_CANCELADA_INACTIVA
FROM CLIENTES_BASE C
LEFT JOIN TEL_PRIORIZADO TP ON C.COD_CLIENTE_IBS = TP.COD_CLIENTE_IBS
LEFT JOIN BASE_MENSUAL BM ON C.COD_CLIENTE_IBS = BM.COD_CLIENTE_IBS
LEFT JOIN ASYS_VAP AV ON C.COD_CLIENTE_IBS = AV.COD_CLIENTE_IBS
LEFT JOIN VAP_DIM VD ON C.COD_CLIENTE_IBS = VD.COD_CLIENTE_IBS
LEFT JOIN FALLECIDOS F ON C.COD_CLIENTE_IBS = F.COD_CLIENTE_IBS
LEFT JOIN ULTIMA_ASIGNACION UA ON C.COD_CLIENTE_IBS = UA.COD_CLIENTE_IBS
WHERE C.EDAD BETWEEN 18 AND 64
  AND UPPER(C.DEPARTAMENTO) <> 'GRACIAS A DIOS'
  AND C.SEGMENTO_BANCA <> 'SEGMENTO COMERCIAL'
  AND TP.PHONE IS NOT NULL
"""


def fetch_hana_enrichment(config: Config, contactados: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    crm_ids = sorted({x for x in contactados["CLIENTE_CRM"].astype(str).tolist() if x})
    ibs_ids = sorted({x for x in contactados["CLIENTE_IBS"].astype(str).tolist() if x})

    if not crm_ids and not ibs_ids:
        logger.warning("No hay CLIENTE_CRM ni CLIENTE_IBS válidos para consultar HANA.")
        return pd.DataFrame()

    all_frames = []
    crm_chunks = list(chunks(crm_ids, config.hana_chunk_size)) or [[]]
    ibs_chunks = list(chunks(ibs_ids, config.hana_chunk_size)) or [[]]
    total = max(len(crm_chunks), len(ibs_chunks))

    logger.info("Conectando a HANA ESPEJO %s:%s para consultas SELECT...", config.hpr_host_espejo, config.hpr_port)
    conn = hana_connect_read(config)
    try:
        for i in range(total):
            crm_chunk = crm_chunks[i] if i < len(crm_chunks) else []
            ibs_chunk = ibs_chunks[i] if i < len(ibs_chunks) else []
            logger.info("Consulta HANA chunk %s/%s | CRM: %s | IBS: %s", i + 1, total, len(crm_chunk), len(ibs_chunk))
            query = build_hana_query(crm_chunk, ibs_chunk, config.base_month, config.base_year)
            df = pd.read_sql(query, conn)
            logger.info("Filas HANA recibidas chunk %s: %s", i + 1, len(df))
            all_frames.append(df)
    finally:
        conn.close()

    if not all_frames:
        return pd.DataFrame()

    out = pd.concat(all_frames, ignore_index=True)
    out.columns = [normalize_col(c) for c in out.columns]
    if "CLIENTE_CRM" in out.columns:
        out["CLIENTE_CRM"] = out["CLIENTE_CRM"].map(clean_id)
    if "CLIENTE_IBS" in out.columns:
        out["CLIENTE_IBS"] = out["CLIENTE_IBS"].map(clean_id)
    out = out.drop_duplicates(subset=[c for c in ["CLIENTE_CRM", "CLIENTE_IBS"] if c in out.columns])
    logger.info("Total único enriquecido HANA: %s", len(out))
    return out


def build_output(contactados: pd.DataFrame, enriched: pd.DataFrame, logger: logging.Logger) -> pd.DataFrame:
    if enriched.empty:
        logger.warning("HANA no devolvió enriquecimiento. Se devolverá solo la base contactada.")
        return contactados

    # Primero intenta unir por CLIENTE_CRM; si no cruza, intenta CLIENTE_IBS.
    left = contactados.copy()
    enr = enriched.copy()
    result = left.merge(enr, on="CLIENTE_CRM", how="left", suffixes=("_CONTACTADO", ""))

    missing_mask = result[[c for c in ["EMAIL", "PHONE", "PRIMER NOMBRE"] if c in result.columns]].isna().all(axis=1) if any(c in result.columns for c in ["EMAIL", "PHONE", "PRIMER NOMBRE"]) else pd.Series([True] * len(result))

    if missing_mask.any() and "CLIENTE_IBS_CONTACTADO" in result.columns and "CLIENTE_IBS" in enr.columns:
        retry_left = left.loc[missing_mask].copy()
        retry = retry_left.merge(enr, left_on="CLIENTE_IBS", right_on="CLIENTE_IBS", how="left", suffixes=("_CONTACTADO", ""))
        result.loc[missing_mask, retry.columns] = retry.values

    result = result.drop_duplicates()
    logger.info("Filas finales generadas: %s", len(result))
    return result


def write_output(df: pd.DataFrame, config: Config, logger: logging.Logger) -> str:
    out_dir = Path(config.output_dir) if config.output_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = re.sub(r"[^A-Za-z0-9_\- ]", "_", config.output_filename).strip() or "Base_Asistencias_TLV_CC"

    if config.output_format == "csv":
        path = out_dir / f"{base}_{timestamp}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        path = out_dir / f"{base}_{timestamp}.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="BASE_FINAL", index=False)

    logger.info("Archivo generado: %s", path)
    return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Base Asistencias TLV a CC desde Excel + HANA espejo")
    parser.add_argument("--file-activaciones", default=env_str("FILE_ACTIVACIONES", ""))
    parser.add_argument("--file-bienvenida", default=env_str("FILE_BIENVENIDA", ""))
    parser.add_argument("--output-format", default=env_str("OUTPUT_FORMAT", "xlsx"), choices=["xlsx", "csv"])
    args = parser.parse_args()

    if args.file_activaciones:
        os.environ["FILE_ACTIVACIONES"] = args.file_activaciones
    if args.file_bienvenida:
        os.environ["FILE_BIENVENIDA"] = args.file_bienvenida
    if args.output_format:
        os.environ["OUTPUT_FORMAT"] = args.output_format

    logger = setup_logger()
    started = time.time()

    try:
        config = load_config()
        logger.info("=" * 80)
        logger.info("INICIO BASE ASISTENCIAS TLV A CC")
        logger.info("HANA lectura: %s:%s", config.hpr_host_espejo, config.hpr_port)
        logger.info("Archivo Activaciones: %s", config.file_activaciones)
        logger.info("Archivo Bienvenida: %s", config.file_bienvenida)
        logger.info("Hoja: %s", config.sheet_name)
        logger.info("Formato salida: %s", config.output_format)
        logger.info("=" * 80)

        df_act = read_excel_contactados(config.file_activaciones, config.sheet_name, config.mes_activaciones, config.contacto_value, "ACTIVACIONES_TC", logger)
        df_bien = read_excel_contactados(config.file_bienvenida, config.sheet_name, config.mes_bienvenida, config.contacto_value, "BIENVENIDA_TC", logger)
        contactados = pd.concat([df_act, df_bien], ignore_index=True)

        before = len(contactados)
        contactados = contactados.drop_duplicates(subset=["DNI", "CLIENTE_CRM", "CLIENTE_IBS"])
        logger.info("Contactados concatenados: %s | después de duplicados: %s", before, len(contactados))

        if config.max_input_rows and len(contactados) > config.max_input_rows:
            raise ValueError(f"La base tiene {len(contactados)} filas y supera MAX_INPUT_ROWS={config.max_input_rows}. Ajusta filtro o límite.")

        enriched = fetch_hana_enrichment(config, contactados, logger)
        final_df = build_output(contactados, enriched, logger)
        output_path = write_output(final_df, config, logger)

        logger.info("=" * 80)
        logger.info("RESUMEN FINAL")
        logger.info("Contactados Activaciones: %s", len(df_act))
        logger.info("Contactados Bienvenida: %s", len(df_bien))
        logger.info("Clientes únicos consultados: %s", len(contactados))
        logger.info("Registros HANA enriquecidos: %s", len(enriched))
        logger.info("Filas archivo final: %s", len(final_df))
        logger.info("Salida: %s", output_path)
        logger.info("Duración: %.2f segundos", time.time() - started)
        logger.info("=" * 80)
        return 0

    except Exception as exc:
        logger.exception("Error general: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
