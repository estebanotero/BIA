/* =====================================================================
   Carga exploratoria para perfilar un origen
   Origen: <sistema>  ·  Pedido por: <persona>  ·  Fecha: <AAAA-MM-DD>
   Generado con la skill disenar-medallion-desde-perfil. Revisalo antes de correrlo.

   Da de alta las tablas a perfilar como entidades mínimas del pipeline
   medallion: FULL, sin columnas ni reglas, en el LOAD_GROUP 'exploracion'.
   Se corre el pipeline con p_load_group = exploracion y p_layers = bronze:
   solo copia a bronze. Silver no se ejecuta.

   Cuando el diseño esté listo, alta_<origen>.sql actualiza estas mismas
   entidades (mismo ENTITY_CODE) con columnas, reglas y LOAD_GROUP 'default'.

   Tablas grandes: <tabla> filtrada a <período> con SOURCE_FILTER [dato a confirmar]
   Correr primero en desarrollo.
   ===================================================================== */

SET XACT_ABORT ON;
BEGIN TRAN;

-- 1. Sistema de origen (CONNECTION_REF = nombre de la conexión de Fabric, nunca credenciales)
MERGE meta.SOURCE_SYSTEM AS t
USING (VALUES
    ('<codigo_sistema>', 'SQL', N'<nombre-de-la-conexion-fabric>', N'<descripción>')
) AS s (SOURCE_SYSTEM_CODE, SOURCE_TYPE, CONNECTION_REF, DESCRIPTION)
ON t.SOURCE_SYSTEM_CODE = s.SOURCE_SYSTEM_CODE
WHEN MATCHED THEN UPDATE SET SOURCE_TYPE = s.SOURCE_TYPE, CONNECTION_REF = s.CONNECTION_REF,
                             DESCRIPTION = s.DESCRIPTION, UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (SOURCE_SYSTEM_CODE, SOURCE_TYPE, CONNECTION_REF, DESCRIPTION)
                      VALUES (s.SOURCE_SYSTEM_CODE, s.SOURCE_TYPE, s.CONNECTION_REF, s.DESCRIPTION);

-- 2. Entidades exploratorias. ENTITY_CODE = <sistema>_<tabla> en minúsculas (NB_PRF_01 cruza el catálogo así).
--    Solo inserta: si la entidad ya existe (ya está en producción), no la toca.
INSERT meta.ENTITY (SOURCE_SYSTEM_ID, ENTITY_CODE, SOURCE_OBJECT, SOURCE_FILTER, FILE_FORMAT, LOAD_TYPE,
                    BRONZE_TABLE, SILVER_TABLE, SILVER_MODE, LOAD_GROUP)
SELECT ss.SOURCE_SYSTEM_ID, v.ENTITY_CODE, v.SOURCE_OBJECT, v.SOURCE_FILTER, N'parquet', 'FULL',
       CONCAT(N'bronze.', v.ENTITY_CODE), v.SILVER_TABLE, 'APPEND', 'exploracion'
FROM (VALUES
    -- ENTITY_CODE,            SOURCE_OBJECT,         SOURCE_FILTER (o NULL),                         SILVER_TABLE
    ('<sistema>_<tabla1>',     N'<esquema>.<Tabla1>', NULL,                                           N'silver.<tabla1>'),
    ('<sistema>_<tabla2>',     N'<esquema>.<Tabla2>', N'<FechaColumna> >= DATEADD(MONTH, -12, GETDATE())', N'silver.<tabla2>')
) AS v (ENTITY_CODE, SOURCE_OBJECT, SOURCE_FILTER, SILVER_TABLE)
JOIN meta.SOURCE_SYSTEM ss ON ss.SOURCE_SYSTEM_CODE = '<codigo_sistema>'
WHERE NOT EXISTS (SELECT 1 FROM meta.ENTITY e WHERE e.ENTITY_CODE = v.ENTITY_CODE);

COMMIT;

EXEC meta.usp_VALIDATE_METADATA;   -- si devuelve filas, corregí antes de correr el pipeline

-- Después: pipeline PL_MDP_MEDALLION con p_load_group = exploracion, p_layers = bronze.
-- Cuando el diseño esté cargado, las entidades que no se usen quedan con:
-- UPDATE meta.ENTITY SET IS_ACTIVE = 0 WHERE LOAD_GROUP = 'exploracion' AND ENTITY_CODE IN ('<...>');
