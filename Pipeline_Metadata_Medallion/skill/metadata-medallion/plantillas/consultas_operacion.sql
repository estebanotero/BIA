/* Consultas de operación del pipeline medallion (solo lectura).
   Pegale el resultado a Claude con la skill metadata-medallion para el diagnóstico. */

-- 1. Últimas 20 corridas
SELECT TOP (20) RUN_ID, LOAD_GROUP, STATUS, STARTED_AT, ENDED_AT,
       DATEDIFF(MINUTE, STARTED_AT, ENDED_AT) AS MINUTOS
FROM log.RUN
ORDER BY STARTED_AT DESC;

-- 2. Pasos con problemas de la última corrida que no terminó bien
SELECT s.LAYER, s.OBJECT_CODE, s.STATUS, s.ROWS_READ, s.ROWS_WRITTEN, s.ROWS_REJECTED,
       s.DQ_WARNINGS, s.ERROR_MESSAGE
FROM log.RUN_STEP s
WHERE s.RUN_ID = (SELECT TOP (1) RUN_ID FROM log.RUN WHERE STATUS <> 'SUCCEEDED' ORDER BY STARTED_AT DESC)
  AND s.STATUS <> 'SUCCEEDED'
ORDER BY CASE s.LAYER WHEN 'copy' THEN 1 WHEN 'bronze' THEN 2 WHEN 'silver' THEN 3 ELSE 4 END, s.OBJECT_CODE;

-- 3. Estado de cada entidad: watermark y último resultado de silver
SELECT e.ENTITY_CODE, e.LOAD_TYPE, e.WATERMARK_VALUE, e.IS_ACTIVE,
       u.STATUS AS ULTIMO_SILVER, u.ROWS_WRITTEN, u.ROWS_REJECTED, u.LOGGED_AT
FROM meta.ENTITY e
OUTER APPLY (SELECT TOP (1) STATUS, ROWS_WRITTEN, ROWS_REJECTED, LOGGED_AT
             FROM log.RUN_STEP
             WHERE OBJECT_CODE = e.ENTITY_CODE AND LAYER = 'silver'
             ORDER BY LOGGED_AT DESC) u
ORDER BY e.ENTITY_CODE;

-- 4. Entidades con rechazos de calidad en los últimos 7 días
SELECT OBJECT_CODE, SUM(ROWS_REJECTED) AS RECHAZADAS, COUNT(*) AS CORRIDAS
FROM log.RUN_STEP
WHERE LAYER = 'silver' AND ROWS_REJECTED > 0 AND LOGGED_AT >= DATEADD(DAY, -7, SYSUTCDATETIME())
GROUP BY OBJECT_CODE
ORDER BY RECHAZADAS DESC;

-- 5. Metadata inconsistente
EXEC meta.usp_VALIDATE_METADATA;

/* En el lakehouse (Spark SQL), para ver las filas rechazadas sin columnas PII:
   SELECT rule_name, row_json, rejected_at FROM silver.dq_rechazos
   WHERE entity_code = '<entidad>' AND run_id = '<RUN_ID>' LIMIT 50; */
