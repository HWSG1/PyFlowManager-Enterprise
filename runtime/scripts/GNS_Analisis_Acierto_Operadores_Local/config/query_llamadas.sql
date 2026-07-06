/*
  Ajusta este query a la tabla real en SAP HANA donde tengas las transcripciones.
  El script reemplaza {{FECHA_INICIO}} y {{FECHA_FIN}} con fechas YYYY-MM-DD.

  Columnas mínimas esperadas por el script:
  conversation_id, fecha_hora, operador, cola, wrapup, cliente_id,
  duracion_segundos, temas_genesys, sentimiento, transferencias, recurrencia, transcripcion
*/

SELECT
    CONVERSATION_ID      AS conversation_id,
    FECHA_HORA           AS fecha_hora,
    OPERADOR             AS operador,
    COLA                 AS cola,
    CONCLUSION           AS wrapup,
    CLIENTE_ID           AS cliente_id,
    DURACION_SEGUNDOS    AS duracion_segundos,
    TEMAS_GENESYS        AS temas_genesys,
    SENTIMIENTO          AS sentimiento,
    TRANSFERENCIAS       AS transferencias,
    RECURRENCIA          AS recurrencia,
    TRANSCRIPCION        AS transcripcion
FROM TU_ESQUEMA.TU_TABLA_TRANSCRIPCIONES
WHERE FECHA_HORA >= TO_TIMESTAMP('{{FECHA_INICIO}} 00:00:00', 'YYYY-MM-DD HH24:MI:SS')
  AND FECHA_HORA <  TO_TIMESTAMP('{{FECHA_FIN}} 00:00:00', 'YYYY-MM-DD HH24:MI:SS')
;
