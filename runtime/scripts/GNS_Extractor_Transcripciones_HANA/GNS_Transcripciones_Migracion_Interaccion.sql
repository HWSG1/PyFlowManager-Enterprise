-- MODELO V3: 18 columnas y una fila por CONVERSATION_ID.
-- Ejecutar manualmente con el extractor detenido. DROP elimina los datos de la principal.
-- Las cuatro tablas hijas mantienen su estructura y contenido.
-- Recargar los rangos históricos: cada interacción recargada reemplaza también su detalle.
-- Si se desea reiniciar todo el histórico, vaciar también las cuatro tablas hijas.
-- Restituir permisos del usuario de carga si es distinto del creador.

DROP TABLE BI_SS.GNS_API_TRANSCRIPCIONES;

CREATE COLUMN TABLE BI_SS.GNS_API_TRANSCRIPCIONES (
    CONVERSATION_ID NVARCHAR(250) NOT NULL,
    CONVERSATION_START TIMESTAMP,
    CONVERSATION_END TIMESTAMP,
    DURATION_MS BIGINT,
    ORIGINATING_DIRECTION NVARCHAR(250),
    QUEUE_ID NVARCHAR(2100),
    QUEUE_NAME NVARCHAR(2100),
    WRAP_UP_CODE_ID NVARCHAR(2100),
    WRAP_UP_CODE_ID_ULTIMA NVARCHAR(250),
    CONCLUSION_ORIGINAL NVARCHAR(2100),
    CONCLUSION_ULTIMA NVARCHAR(500),
    CONTACT_ID NVARCHAR(250),
    CONTACT_LIST_ID NVARCHAR(250),
    CAMPAIGN_ID NVARCHAR(250),
    MEDIA_TYPE NVARCHAR(250),
    PHRASES_COUNT INTEGER,
    "TEXT" NCLOB,
    FECHA_CARGA TIMESTAMP,
    PRIMARY KEY (CONVERSATION_ID)
);
