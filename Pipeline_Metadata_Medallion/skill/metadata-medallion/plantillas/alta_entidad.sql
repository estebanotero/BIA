/* =====================================================================
   Alta o cambio de entidades en el pipeline medallion
   Origen: <sistema>  ·  Pedido por: <persona>  ·  Fecha: <AAAA-MM-DD>
   Generado con la skill metadata-medallion. Revisalo antes de correrlo.

   Decisiones:
   - <entidad>: <FULL | INCREMENTAL por columna X>, clave <...>, silver <MERGE | SCD2 | OVERWRITE | APPEND>,
     bajas <NONE | FLAG con <expr> | ABSENT con freno <n> %>
   [dato a confirmar]:
   - <pregunta pendiente>

   Correr primero en desarrollo. No modifica WATERMARK_VALUE.
   ===================================================================== */

SET XACT_ABORT ON;
BEGIN TRAN;

-- 1. Sistema de origen (CONNECTION_REF = nombre de la conexión de Fabric, nunca credenciales)
MERGE meta.SOURCE_SYSTEM AS t
USING (VALUES
    ('<codigo_sistema>', '<SQL | FILES>', N'<nombre-de-la-conexion-fabric>', N'<descripción>')
) AS s (SOURCE_SYSTEM_CODE, SOURCE_TYPE, CONNECTION_REF, DESCRIPTION)
ON t.SOURCE_SYSTEM_CODE = s.SOURCE_SYSTEM_CODE
WHEN MATCHED THEN UPDATE SET SOURCE_TYPE = s.SOURCE_TYPE, CONNECTION_REF = s.CONNECTION_REF,
                             DESCRIPTION = s.DESCRIPTION, UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (SOURCE_SYSTEM_CODE, SOURCE_TYPE, CONNECTION_REF, DESCRIPTION)
                      VALUES (s.SOURCE_SYSTEM_CODE, s.SOURCE_TYPE, s.CONNECTION_REF, s.DESCRIPTION);

-- 2. Entidades
MERGE meta.ENTITY AS t
USING (
    SELECT ss.SOURCE_SYSTEM_ID, v.*
    FROM (VALUES
        ('<codigo_sistema>', '<sistema_tabla>', N'<esquema.tabla | Files/carpeta>', NULL /* filtro */, N'parquet',
         '<FULL | INCREMENTAL>', N'<ColumnaWatermark>' /* o NULL */, '<DATETIME | INT>' /* o NULL */,
         N'<clave_silver>', N'<columna_orden_silver>' /* o NULL */,
         N'bronze.<sistema_tabla>', N'silver.<tabla>', '<MERGE | SCD2 | OVERWRITE | APPEND>', 'default',
         NULL /* SCD2_COLUMNS: columnas que abren versión, ej. N'provincia,segmento' */,
         'NONE' /* DELETE_MODE: NONE | FLAG | ABSENT (solo con FULL) */,
         NULL /* DELETE_FLAG_EXPR, ej. N'anulada = true' */, 10 /* DELETE_MAX_PCT */)
    ) AS v (SOURCE_SYSTEM_CODE, ENTITY_CODE, SOURCE_OBJECT, SOURCE_FILTER, FILE_FORMAT, LOAD_TYPE,
            WATERMARK_COLUMN, WATERMARK_TYPE, PRIMARY_KEY, ORDER_COLUMN, BRONZE_TABLE, SILVER_TABLE, SILVER_MODE, LOAD_GROUP,
            SCD2_COLUMNS, DELETE_MODE, DELETE_FLAG_EXPR, DELETE_MAX_PCT)
    JOIN meta.SOURCE_SYSTEM ss ON ss.SOURCE_SYSTEM_CODE = v.SOURCE_SYSTEM_CODE
) AS s
ON t.ENTITY_CODE = s.ENTITY_CODE
WHEN MATCHED THEN UPDATE SET
    SOURCE_SYSTEM_ID = s.SOURCE_SYSTEM_ID, SOURCE_OBJECT = s.SOURCE_OBJECT, SOURCE_FILTER = s.SOURCE_FILTER,
    FILE_FORMAT = s.FILE_FORMAT, LOAD_TYPE = s.LOAD_TYPE, WATERMARK_COLUMN = s.WATERMARK_COLUMN,
    WATERMARK_TYPE = s.WATERMARK_TYPE, PRIMARY_KEY = s.PRIMARY_KEY, ORDER_COLUMN = s.ORDER_COLUMN,
    BRONZE_TABLE = s.BRONZE_TABLE, SILVER_TABLE = s.SILVER_TABLE, SILVER_MODE = s.SILVER_MODE,
    LOAD_GROUP = s.LOAD_GROUP, SCD2_COLUMNS = s.SCD2_COLUMNS, DELETE_MODE = s.DELETE_MODE,
    DELETE_FLAG_EXPR = s.DELETE_FLAG_EXPR, DELETE_MAX_PCT = s.DELETE_MAX_PCT,
    IS_ACTIVE = 1, UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT
    (SOURCE_SYSTEM_ID, ENTITY_CODE, SOURCE_OBJECT, SOURCE_FILTER, FILE_FORMAT, LOAD_TYPE, WATERMARK_COLUMN,
     WATERMARK_TYPE, PRIMARY_KEY, ORDER_COLUMN, BRONZE_TABLE, SILVER_TABLE, SILVER_MODE, LOAD_GROUP,
     SCD2_COLUMNS, DELETE_MODE, DELETE_FLAG_EXPR, DELETE_MAX_PCT)
    VALUES
    (s.SOURCE_SYSTEM_ID, s.ENTITY_CODE, s.SOURCE_OBJECT, s.SOURCE_FILTER, s.FILE_FORMAT, s.LOAD_TYPE, s.WATERMARK_COLUMN,
     s.WATERMARK_TYPE, s.PRIMARY_KEY, s.ORDER_COLUMN, s.BRONZE_TABLE, s.SILVER_TABLE, s.SILVER_MODE, s.LOAD_GROUP,
     s.SCD2_COLUMNS, s.DELETE_MODE, s.DELETE_FLAG_EXPR, s.DELETE_MAX_PCT);

-- 3. Columnas de silver: se reemplazan completas para las entidades de este script
DELETE c FROM meta.ENTITY_COLUMN c
JOIN meta.ENTITY e ON e.ENTITY_ID = c.ENTITY_ID
WHERE e.ENTITY_CODE IN ('<sistema_tabla>');

INSERT meta.ENTITY_COLUMN (ENTITY_ID, ORDINAL, SOURCE_COLUMN, TARGET_COLUMN, TARGET_TYPE, TRANSFORM_EXPR, IS_PII)
SELECT e.ENTITY_ID, v.ORDINAL, v.SOURCE_COLUMN, v.TARGET_COLUMN, v.TARGET_TYPE, v.TRANSFORM_EXPR, v.IS_PII
FROM (VALUES
    ('<sistema_tabla>', 1, N'<ColumnaOrigen>', N'<columna_silver>', '<tipo_spark>', NULL /* o expresión Spark SQL */, 0)
) AS v (ENTITY_CODE, ORDINAL, SOURCE_COLUMN, TARGET_COLUMN, TARGET_TYPE, TRANSFORM_EXPR, IS_PII)
JOIN meta.ENTITY e ON e.ENTITY_CODE = v.ENTITY_CODE;

-- 4. Reglas de calidad: se reemplazan completas para las entidades de este script
DELETE r FROM meta.DQ_RULE r
JOIN meta.ENTITY e ON e.ENTITY_ID = r.ENTITY_ID
WHERE e.ENTITY_CODE IN ('<sistema_tabla>');

INSERT meta.DQ_RULE (ENTITY_ID, RULE_NAME, RULE_EXPR, ACTION)
SELECT e.ENTITY_ID, v.RULE_NAME, v.RULE_EXPR, v.ACTION
FROM (VALUES
    ('<sistema_tabla>', '<clave>_no_nula', N'<clave_silver> IS NOT NULL', 'FAIL')
) AS v (ENTITY_CODE, RULE_NAME, RULE_EXPR, ACTION)
JOIN meta.ENTITY e ON e.ENTITY_CODE = v.ENTITY_CODE;

-- 5. Gold (solo si el pedido incluye objetos gold)
-- MERGE meta.GOLD_OBJECT AS t
-- USING (VALUES
--     ('<gold_code>', N'gold.<tabla>', '<OVERWRITE | MERGE | MLV>', N'<merge_key>' /* o NULL */,
--      N'<gold_code_previo>' /* o NULL */, N'SELECT ... FROM silver.<tabla>')
-- ) AS s (GOLD_CODE, TARGET_TABLE, LOAD_MODE, MERGE_KEY, DEPENDS_ON_GOLD, SQL_TEXT)
-- ON t.GOLD_CODE = s.GOLD_CODE
-- WHEN MATCHED THEN UPDATE SET TARGET_TABLE = s.TARGET_TABLE, LOAD_MODE = s.LOAD_MODE, MERGE_KEY = s.MERGE_KEY,
--                              DEPENDS_ON_GOLD = s.DEPENDS_ON_GOLD, SQL_TEXT = s.SQL_TEXT, IS_ACTIVE = 1,
--                              UPDATED_AT = SYSUTCDATETIME()
-- WHEN NOT MATCHED THEN INSERT (GOLD_CODE, TARGET_TABLE, LOAD_MODE, MERGE_KEY, DEPENDS_ON_GOLD, SQL_TEXT)
--                       VALUES (s.GOLD_CODE, s.TARGET_TABLE, s.LOAD_MODE, s.MERGE_KEY, s.DEPENDS_ON_GOLD, s.SQL_TEXT);

COMMIT;

EXEC meta.usp_VALIDATE_METADATA;   -- si devuelve filas, corregí antes de correr el pipeline
