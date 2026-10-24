/* =====================================================================
   Pipeline metadata-driven medallion · Base de control
   Destino: SQL database de Fabric (también corre en Azure SQL Database)
   Crea los esquemas meta (configuración) y log (ejecuciones), sus tablas
   y los stored procedures que usa el pipeline PL_MDP_MEDALLION.

   Es idempotente: crea solo lo que no existe y recrea los SP.
   No borra datos. Correlo primero en el entorno de desarrollo.
   ===================================================================== */

-- ---------------------------------------------------------------------
-- 0. Esquemas
-- ---------------------------------------------------------------------
IF SCHEMA_ID('meta') IS NULL EXEC('CREATE SCHEMA meta');
IF SCHEMA_ID('log')  IS NULL EXEC('CREATE SCHEMA log');
GO

-- ---------------------------------------------------------------------
-- 1. Configuración (meta)
-- ---------------------------------------------------------------------

/* Sistemas de origen. CONNECTION_REF es el nombre de la conexión de Fabric
   (Manage connections and gateways). Acá nunca van usuarios ni claves. */
IF OBJECT_ID('meta.SOURCE_SYSTEM') IS NULL
CREATE TABLE meta.SOURCE_SYSTEM (
    SOURCE_SYSTEM_ID   INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_SOURCE_SYSTEM PRIMARY KEY,
    SOURCE_SYSTEM_CODE VARCHAR(50)   NOT NULL CONSTRAINT UQ_SOURCE_SYSTEM_CODE UNIQUE,
    SOURCE_TYPE        VARCHAR(20)   NOT NULL
        CONSTRAINT CK_SOURCE_TYPE CHECK (SOURCE_TYPE IN ('SQL', 'FILES')),
        -- SQL:   el pipeline copia con una actividad Copy a Files/landing/
        -- FILES: los archivos ya están en OneLake (shortcut, Copy job, upload)
    CONNECTION_REF     NVARCHAR(200) NULL,
    DESCRIPTION        NVARCHAR(500) NULL,
    IS_ACTIVE          BIT           NOT NULL CONSTRAINT DF_SOURCE_SYSTEM_ACTIVE DEFAULT (1),
    CREATED_AT         DATETIME2(0)  NOT NULL CONSTRAINT DF_SOURCE_SYSTEM_CREATED DEFAULT (SYSUTCDATETIME()),
    UPDATED_AT         DATETIME2(0)  NOT NULL CONSTRAINT DF_SOURCE_SYSTEM_UPDATED DEFAULT (SYSUTCDATETIME())
);
GO

/* Una fila por objeto de origen que se lleva a bronze y silver. */
IF OBJECT_ID('meta.ENTITY') IS NULL
CREATE TABLE meta.ENTITY (
    ENTITY_ID          INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ENTITY PRIMARY KEY,
    SOURCE_SYSTEM_ID   INT            NOT NULL CONSTRAINT FK_ENTITY_SOURCE
                                      REFERENCES meta.SOURCE_SYSTEM (SOURCE_SYSTEM_ID),
    ENTITY_CODE        VARCHAR(100)   NOT NULL CONSTRAINT UQ_ENTITY_CODE UNIQUE,  -- ej. erp_clientes
    SOURCE_OBJECT      NVARCHAR(300)  NOT NULL,  -- SQL: esquema.tabla | FILES: carpeta, ej. Files/sftp/clientes
    SOURCE_FILTER      NVARCHAR(1000) NULL,      -- SQL: condición extra del WHERE, sin la palabra WHERE
    FILE_FORMAT        VARCHAR(20)    NOT NULL CONSTRAINT DF_ENTITY_FORMAT DEFAULT ('parquet')
        CONSTRAINT CK_ENTITY_FORMAT CHECK (FILE_FORMAT IN ('parquet', 'csv', 'json', 'delta')),
    LOAD_TYPE          VARCHAR(20)    NOT NULL
        CONSTRAINT CK_ENTITY_LOAD_TYPE CHECK (LOAD_TYPE IN ('FULL', 'INCREMENTAL')),
    WATERMARK_COLUMN   SYSNAME        NULL,      -- columna de fecha o número creciente; en FILES sin columna se usa la fecha de modificación del archivo
    WATERMARK_TYPE     VARCHAR(20)    NULL
        CONSTRAINT CK_ENTITY_WM_TYPE CHECK (WATERMARK_TYPE IN ('DATETIME', 'INT')),
    WATERMARK_VALUE    NVARCHAR(50)   NULL,      -- último valor cargado; lo actualiza log.usp_END_RUN
    PRIMARY_KEY        NVARCHAR(500)  NULL,      -- columnas destino separadas por coma; obligatorio para MERGE
    ORDER_COLUMN       NVARCHAR(128)  NULL,      -- para quedarse con la última versión de cada clave
    BRONZE_TABLE       NVARCHAR(256)  NOT NULL,  -- ej. bronze.erp_clientes
    SILVER_TABLE       NVARCHAR(256)  NOT NULL,  -- ej. silver.clientes
    SILVER_MODE        VARCHAR(20)    NOT NULL CONSTRAINT DF_ENTITY_SILVER_MODE DEFAULT ('MERGE')
        CONSTRAINT CK_ENTITY_SILVER_MODE CHECK (SILVER_MODE IN ('MERGE', 'OVERWRITE', 'APPEND', 'SCD2')),
        -- SCD2: historia con _valid_from, _valid_to e _is_current por clave
    SCD2_COLUMNS       NVARCHAR(1000) NULL,      -- columnas de silver que abren versión nueva; NULL = todas menos la clave y ORDER_COLUMN
    DELETE_MODE        VARCHAR(10)    NOT NULL CONSTRAINT DF_ENTITY_DELETE_MODE DEFAULT ('NONE')
        CONSTRAINT CK_ENTITY_DELETE_MODE CHECK (DELETE_MODE IN ('NONE', 'FLAG', 'ABSENT')),
        -- FLAG: DELETE_FLAG_EXPR dice que la fila está dada de baja en el origen
        -- ABSENT: extracción completa; lo que estaba vivo y no vino es baja
    DELETE_FLAG_EXPR   NVARCHAR(1000) NULL,      -- Spark SQL sobre columnas de silver, ej. anulada = true
    DELETE_MAX_PCT     DECIMAL(5,2)   NOT NULL CONSTRAINT DF_ENTITY_DELETE_MAX_PCT DEFAULT (10)
        CONSTRAINT CK_ENTITY_DELETE_MAX_PCT CHECK (DELETE_MAX_PCT BETWEEN 0 AND 100),
        -- ABSENT: si falta más de este % de las claves vivas, silver falla en vez de marcar bajas
    LOAD_GROUP         VARCHAR(50)    NOT NULL CONSTRAINT DF_ENTITY_GROUP DEFAULT ('default'),
    IS_ACTIVE          BIT            NOT NULL CONSTRAINT DF_ENTITY_ACTIVE DEFAULT (1),
    CREATED_AT         DATETIME2(0)   NOT NULL CONSTRAINT DF_ENTITY_CREATED DEFAULT (SYSUTCDATETIME()),
    UPDATED_AT         DATETIME2(0)   NOT NULL CONSTRAINT DF_ENTITY_UPDATED DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT CK_ENTITY_MERGE_PK CHECK (SILVER_MODE NOT IN ('MERGE', 'SCD2') OR PRIMARY_KEY IS NOT NULL),
    CONSTRAINT CK_ENTITY_DELETE_FLAG CHECK (DELETE_MODE <> 'FLAG' OR DELETE_FLAG_EXPR IS NOT NULL)
);
GO

/* Ampliación para SCD2 y bajas (bases creadas antes de esta versión). Agrega columnas
   con valores por defecto que no cambian el comportamiento (DELETE_MODE = NONE) y amplía
   los CHECK. No toca datos. Para volver atrás: borrar los CHECK y columnas nuevos. */
IF COL_LENGTH('meta.ENTITY', 'SCD2_COLUMNS') IS NULL
    ALTER TABLE meta.ENTITY ADD SCD2_COLUMNS NVARCHAR(1000) NULL;
IF COL_LENGTH('meta.ENTITY', 'DELETE_MODE') IS NULL
    ALTER TABLE meta.ENTITY ADD DELETE_MODE VARCHAR(10) NOT NULL CONSTRAINT DF_ENTITY_DELETE_MODE DEFAULT ('NONE');
IF COL_LENGTH('meta.ENTITY', 'DELETE_FLAG_EXPR') IS NULL
    ALTER TABLE meta.ENTITY ADD DELETE_FLAG_EXPR NVARCHAR(1000) NULL;
IF COL_LENGTH('meta.ENTITY', 'DELETE_MAX_PCT') IS NULL
    ALTER TABLE meta.ENTITY ADD DELETE_MAX_PCT DECIMAL(5,2) NOT NULL CONSTRAINT DF_ENTITY_DELETE_MAX_PCT DEFAULT (10);
GO
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_ENTITY_SILVER_MODE' AND definition NOT LIKE '%SCD2%')
    ALTER TABLE meta.ENTITY DROP CONSTRAINT CK_ENTITY_SILVER_MODE;
IF OBJECT_ID('meta.CK_ENTITY_SILVER_MODE') IS NULL
    ALTER TABLE meta.ENTITY ADD CONSTRAINT CK_ENTITY_SILVER_MODE
        CHECK (SILVER_MODE IN ('MERGE', 'OVERWRITE', 'APPEND', 'SCD2'));
IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_ENTITY_MERGE_PK' AND definition NOT LIKE '%SCD2%')
    ALTER TABLE meta.ENTITY DROP CONSTRAINT CK_ENTITY_MERGE_PK;
IF OBJECT_ID('meta.CK_ENTITY_MERGE_PK') IS NULL
    ALTER TABLE meta.ENTITY ADD CONSTRAINT CK_ENTITY_MERGE_PK
        CHECK (SILVER_MODE NOT IN ('MERGE', 'SCD2') OR PRIMARY_KEY IS NOT NULL);
IF OBJECT_ID('meta.CK_ENTITY_DELETE_MODE') IS NULL
    ALTER TABLE meta.ENTITY ADD CONSTRAINT CK_ENTITY_DELETE_MODE CHECK (DELETE_MODE IN ('NONE', 'FLAG', 'ABSENT'));
IF OBJECT_ID('meta.CK_ENTITY_DELETE_MAX_PCT') IS NULL
    ALTER TABLE meta.ENTITY ADD CONSTRAINT CK_ENTITY_DELETE_MAX_PCT CHECK (DELETE_MAX_PCT BETWEEN 0 AND 100);
IF OBJECT_ID('meta.CK_ENTITY_DELETE_FLAG') IS NULL
    ALTER TABLE meta.ENTITY ADD CONSTRAINT CK_ENTITY_DELETE_FLAG CHECK (DELETE_MODE <> 'FLAG' OR DELETE_FLAG_EXPR IS NOT NULL);
GO

/* Columnas de silver. Si una entidad no tiene filas acá, silver toma todas
   las columnas de bronze tal cual. Si tiene, toma solo estas, en este orden. */
IF OBJECT_ID('meta.ENTITY_COLUMN') IS NULL
CREATE TABLE meta.ENTITY_COLUMN (
    ENTITY_COLUMN_ID   INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ENTITY_COLUMN PRIMARY KEY,
    ENTITY_ID          INT            NOT NULL CONSTRAINT FK_ENTITY_COLUMN_ENTITY
                                      REFERENCES meta.ENTITY (ENTITY_ID),
    ORDINAL            INT            NOT NULL,
    SOURCE_COLUMN      NVARCHAR(128)  NOT NULL,  -- nombre en bronze
    TARGET_COLUMN      NVARCHAR(128)  NOT NULL,  -- nombre en silver (snake_case)
    TARGET_TYPE        VARCHAR(50)    NOT NULL,  -- tipo Spark SQL: string, int, bigint, date, timestamp, decimal(18,2)...
    TRANSFORM_EXPR     NVARCHAR(1000) NULL,      -- expresión Spark SQL opcional; si es NULL se usa SOURCE_COLUMN
    IS_PII             BIT            NOT NULL CONSTRAINT DF_ENTITY_COLUMN_PII DEFAULT (0),
    CONSTRAINT UQ_ENTITY_COLUMN_TARGET UNIQUE (ENTITY_ID, TARGET_COLUMN)
);
GO

/* Reglas de calidad de silver, en Spark SQL sobre las columnas destino.
   WARN: cuenta y sigue · DROP: manda la fila a silver.dq_rechazos · FAIL: corta la entidad */
IF OBJECT_ID('meta.DQ_RULE') IS NULL
CREATE TABLE meta.DQ_RULE (
    DQ_RULE_ID         INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DQ_RULE PRIMARY KEY,
    ENTITY_ID          INT            NOT NULL CONSTRAINT FK_DQ_RULE_ENTITY
                                      REFERENCES meta.ENTITY (ENTITY_ID),
    RULE_NAME          VARCHAR(100)   NOT NULL,
    RULE_EXPR          NVARCHAR(1000) NOT NULL,  -- lo que debe cumplirse, ej. importe >= 0
    ACTION             VARCHAR(10)    NOT NULL
        CONSTRAINT CK_DQ_RULE_ACTION CHECK (ACTION IN ('WARN', 'DROP', 'FAIL')),
    IS_ACTIVE          BIT            NOT NULL CONSTRAINT DF_DQ_RULE_ACTIVE DEFAULT (1),
    CONSTRAINT UQ_DQ_RULE UNIQUE (ENTITY_ID, RULE_NAME)
);
GO

/* Objetos de gold. SQL_TEXT es un SELECT de Spark SQL sobre silver (o sobre
   otros objetos gold), o un CREATE MATERIALIZED LAKE VIEW si LOAD_MODE = 'MLV'. */
IF OBJECT_ID('meta.GOLD_OBJECT') IS NULL
CREATE TABLE meta.GOLD_OBJECT (
    GOLD_ID            INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_GOLD_OBJECT PRIMARY KEY,
    GOLD_CODE          VARCHAR(100)   NOT NULL CONSTRAINT UQ_GOLD_CODE UNIQUE,  -- ej. fact_ventas
    TARGET_TABLE       NVARCHAR(256)  NOT NULL,  -- ej. gold.fact_ventas
    LOAD_MODE          VARCHAR(20)    NOT NULL
        CONSTRAINT CK_GOLD_LOAD_MODE CHECK (LOAD_MODE IN ('OVERWRITE', 'MERGE', 'MLV')),
    MERGE_KEY          NVARCHAR(500)  NULL,      -- obligatorio si LOAD_MODE = 'MERGE'
    SQL_TEXT           NVARCHAR(MAX)  NOT NULL,
    DEPENDS_ON_GOLD    NVARCHAR(500)  NULL,      -- GOLD_CODE que deben correr antes, separados por coma
    LOAD_GROUP         VARCHAR(50)    NOT NULL CONSTRAINT DF_GOLD_GROUP DEFAULT ('default'),
    IS_ACTIVE          BIT            NOT NULL CONSTRAINT DF_GOLD_ACTIVE DEFAULT (1),
    CREATED_AT         DATETIME2(0)   NOT NULL CONSTRAINT DF_GOLD_CREATED DEFAULT (SYSUTCDATETIME()),
    UPDATED_AT         DATETIME2(0)   NOT NULL CONSTRAINT DF_GOLD_UPDATED DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT CK_GOLD_MERGE_KEY CHECK (LOAD_MODE <> 'MERGE' OR MERGE_KEY IS NOT NULL)
);
GO

-- ---------------------------------------------------------------------
-- 2. Ejecuciones (log)
-- ---------------------------------------------------------------------
IF OBJECT_ID('log.RUN') IS NULL
CREATE TABLE log.RUN (
    RUN_ID             VARCHAR(64)    NOT NULL CONSTRAINT PK_RUN PRIMARY KEY,  -- @pipeline().RunId
    PIPELINE_NAME      NVARCHAR(200)  NOT NULL,
    LOAD_GROUP         VARCHAR(50)    NOT NULL,
    STATUS             VARCHAR(20)    NOT NULL,  -- RUNNING | SUCCEEDED | FAILED
    STARTED_AT         DATETIME2(3)   NOT NULL,
    ENDED_AT           DATETIME2(3)   NULL,
    RESULT_JSON        NVARCHAR(MAX)  NULL
);
GO

IF OBJECT_ID('log.RUN_STEP') IS NULL
CREATE TABLE log.RUN_STEP (
    RUN_STEP_ID        BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_RUN_STEP PRIMARY KEY,
    RUN_ID             VARCHAR(64)    NOT NULL CONSTRAINT FK_RUN_STEP_RUN REFERENCES log.RUN (RUN_ID),
    LAYER              VARCHAR(10)    NOT NULL,  -- copy | bronze | silver | gold
    OBJECT_CODE        VARCHAR(100)   NOT NULL,  -- ENTITY_CODE o GOLD_CODE
    STATUS             VARCHAR(30)    NOT NULL,  -- SUCCEEDED | FAILED | SKIPPED | SKIPPED_NO_DATA | SKIPPED_UPSTREAM_FAILED
    ROWS_READ          BIGINT         NULL,
    ROWS_WRITTEN       BIGINT         NULL,
    ROWS_REJECTED      BIGINT         NULL,
    DQ_WARNINGS        NVARCHAR(MAX)  NULL,      -- JSON {regla: filas}
    NEW_WATERMARK      NVARCHAR(50)   NULL,
    ERROR_MESSAGE      NVARCHAR(4000) NULL,
    LOGGED_AT          DATETIME2(3)   NOT NULL CONSTRAINT DF_RUN_STEP_LOGGED DEFAULT (SYSUTCDATETIME())
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_RUN_STEP_RUN')
    CREATE INDEX IX_RUN_STEP_RUN ON log.RUN_STEP (RUN_ID, LAYER, OBJECT_CODE);
GO

-- ---------------------------------------------------------------------
-- 3. Stored procedures que usa el pipeline
-- ---------------------------------------------------------------------

/* Abre la corrida. */
CREATE OR ALTER PROCEDURE log.usp_START_RUN
    @RUN_ID VARCHAR(64), @PIPELINE_NAME NVARCHAR(200), @LOAD_GROUP VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM log.RUN WHERE RUN_ID = @RUN_ID)
        INSERT log.RUN (RUN_ID, PIPELINE_NAME, LOAD_GROUP, STATUS, STARTED_AT)
        VALUES (@RUN_ID, @PIPELINE_NAME, @LOAD_GROUP, 'RUNNING', SYSUTCDATETIME());
END
GO

/* Devuelve las copias que tiene que hacer el pipeline (solo orígenes SQL).
   Arma la consulta de origen con el watermark. Usa >= a propósito: si una
   fila se repite entre corridas, el MERGE de silver la deduplica. */
CREATE OR ALTER PROCEDURE meta.usp_GET_COPY_TASKS
    @LOAD_GROUP VARCHAR(50), @RUN_ID VARCHAR(64)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        e.ENTITY_CODE,
        s.SOURCE_SYSTEM_CODE,
        s.CONNECTION_REF,
        CONCAT(
            'SELECT * FROM ',
            ISNULL(QUOTENAME(PARSENAME(e.SOURCE_OBJECT, 2)) + '.', ''),
            QUOTENAME(PARSENAME(e.SOURCE_OBJECT, 1)),
            ' WHERE 1 = 1',
            CASE WHEN e.SOURCE_FILTER IS NOT NULL THEN CONCAT(' AND (', e.SOURCE_FILTER, ')') ELSE '' END,
            CASE
                WHEN e.LOAD_TYPE = 'INCREMENTAL' AND e.WATERMARK_VALUE IS NOT NULL AND e.WATERMARK_TYPE = 'DATETIME'
                    -- el valor sale de nuestra tabla y se valida con TRY_CONVERT antes de concatenarlo
                    AND TRY_CONVERT(DATETIME2(7), e.WATERMARK_VALUE) IS NOT NULL
                    THEN CONCAT(' AND ', QUOTENAME(e.WATERMARK_COLUMN), ' >= ''',
                                CONVERT(VARCHAR(27), TRY_CONVERT(DATETIME2(7), e.WATERMARK_VALUE), 126), '''')
                WHEN e.LOAD_TYPE = 'INCREMENTAL' AND e.WATERMARK_VALUE IS NOT NULL AND e.WATERMARK_TYPE = 'INT'
                    AND TRY_CONVERT(BIGINT, e.WATERMARK_VALUE) IS NOT NULL
                    THEN CONCAT(' AND ', QUOTENAME(e.WATERMARK_COLUMN), ' >= ',
                                TRY_CONVERT(BIGINT, e.WATERMARK_VALUE))
                ELSE ''
            END
        ) AS SOURCE_QUERY,
        CONCAT('landing/', e.ENTITY_CODE, '/', @RUN_ID) AS LANDING_FOLDER
    FROM meta.ENTITY e
    JOIN meta.SOURCE_SYSTEM s ON s.SOURCE_SYSTEM_ID = e.SOURCE_SYSTEM_ID
    WHERE e.IS_ACTIVE = 1 AND s.IS_ACTIVE = 1
      AND s.SOURCE_TYPE = 'SQL'
      AND e.LOAD_GROUP = @LOAD_GROUP
    ORDER BY e.ENTITY_CODE;
END
GO

/* Registra un paso (lo usa el pipeline para el resultado de cada Copy). */
CREATE OR ALTER PROCEDURE log.usp_LOG_STEP
    @RUN_ID VARCHAR(64), @LAYER VARCHAR(10), @OBJECT_CODE VARCHAR(100), @STATUS VARCHAR(30),
    @ROWS_READ BIGINT = NULL, @ROWS_WRITTEN BIGINT = NULL, @ERROR_MESSAGE NVARCHAR(4000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT log.RUN_STEP (RUN_ID, LAYER, OBJECT_CODE, STATUS, ROWS_READ, ROWS_WRITTEN, ERROR_MESSAGE)
    VALUES (@RUN_ID, @LAYER, @OBJECT_CODE, @STATUS, @ROWS_READ, @ROWS_WRITTEN, LEFT(@ERROR_MESSAGE, 4000));
END
GO

/* Devuelve en una sola fila (columna CONFIG_JSON) todo lo que necesita el
   notebook orquestador: entidades con sus columnas y reglas, y objetos gold.
   Se arma en una variable para que FOR JSON no se parta en varias filas. */
CREATE OR ALTER PROCEDURE meta.usp_GET_RUN_CONFIG
    @LOAD_GROUP VARCHAR(50), @RUN_ID VARCHAR(64)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @json NVARCHAR(MAX) = (
        SELECT
            @RUN_ID     AS run_id,
            @LOAD_GROUP AS load_group,
            (
                SELECT
                    e.ENTITY_CODE      AS entity_code,
                    s.SOURCE_TYPE      AS source_type,
                    CASE WHEN s.SOURCE_TYPE = 'SQL'
                         THEN CONCAT('Files/landing/', e.ENTITY_CODE, '/', @RUN_ID)
                         ELSE e.SOURCE_OBJECT END AS read_path,
                    CASE WHEN s.SOURCE_TYPE = 'SQL' THEN 'parquet' ELSE e.FILE_FORMAT END AS file_format,
                    e.LOAD_TYPE        AS load_type,
                    e.WATERMARK_COLUMN AS watermark_column,
                    e.WATERMARK_TYPE   AS watermark_type,
                    e.WATERMARK_VALUE  AS watermark_value,
                    e.PRIMARY_KEY      AS primary_key,
                    e.ORDER_COLUMN     AS order_column,
                    e.BRONZE_TABLE     AS bronze_table,
                    e.SILVER_TABLE     AS silver_table,
                    e.SILVER_MODE      AS silver_mode,
                    e.SCD2_COLUMNS     AS scd2_columns,
                    e.DELETE_MODE      AS delete_mode,
                    e.DELETE_FLAG_EXPR AS delete_flag_expr,
                    e.DELETE_MAX_PCT   AS delete_max_pct,
                    -- si la copia de esta corrida falló, bronze no lee la carpeta (puede estar incompleta)
                    CASE WHEN EXISTS (SELECT 1 FROM log.RUN_STEP r
                                      WHERE r.RUN_ID = @RUN_ID AND r.LAYER = 'copy'
                                        AND r.OBJECT_CODE = e.ENTITY_CODE AND r.STATUS = 'FAILED')
                         THEN CAST(1 AS BIT) ELSE CAST(0 AS BIT) END AS copy_failed,
                    (
                        SELECT c.SOURCE_COLUMN AS source_column, c.TARGET_COLUMN AS target_column,
                               c.TARGET_TYPE AS target_type, c.TRANSFORM_EXPR AS transform_expr,
                               c.IS_PII AS is_pii
                        FROM meta.ENTITY_COLUMN c
                        WHERE c.ENTITY_ID = e.ENTITY_ID
                        ORDER BY c.ORDINAL
                        FOR JSON PATH
                    ) AS columns,
                    (
                        SELECT r.RULE_NAME AS rule_name, r.RULE_EXPR AS rule_expr, r.ACTION AS action
                        FROM meta.DQ_RULE r
                        WHERE r.ENTITY_ID = e.ENTITY_ID AND r.IS_ACTIVE = 1
                        FOR JSON PATH
                    ) AS dq_rules
                FROM meta.ENTITY e
                JOIN meta.SOURCE_SYSTEM s ON s.SOURCE_SYSTEM_ID = e.SOURCE_SYSTEM_ID
                WHERE e.IS_ACTIVE = 1 AND s.IS_ACTIVE = 1 AND e.LOAD_GROUP = @LOAD_GROUP
                ORDER BY e.ENTITY_CODE
                FOR JSON PATH, INCLUDE_NULL_VALUES
            ) AS entities,
            (
                SELECT g.GOLD_CODE AS gold_code, g.TARGET_TABLE AS target_table, g.LOAD_MODE AS load_mode,
                       g.MERGE_KEY AS merge_key, g.SQL_TEXT AS sql_text, g.DEPENDS_ON_GOLD AS depends_on_gold
                FROM meta.GOLD_OBJECT g
                WHERE g.IS_ACTIVE = 1 AND g.LOAD_GROUP = @LOAD_GROUP
                ORDER BY g.GOLD_CODE
                FOR JSON PATH, INCLUDE_NULL_VALUES
            ) AS gold_objects
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES
    );
    SELECT @json AS CONFIG_JSON;
END
GO

/* Cierra la corrida con el JSON que devuelve el orquestador:
   registra cada paso, avanza el watermark de las entidades cuyo bronze
   terminó bien y devuelve el estado final (el pipeline lo llama con Lookup). */
CREATE OR ALTER PROCEDURE log.usp_END_RUN
    @RUN_ID VARCHAR(64), @RESULT_JSON NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF ISJSON(@RESULT_JSON) <> 1
        SET @RESULT_JSON = N'{"hay_errores": true, "error": "El orquestador no devolvió un JSON válido", "pasos": []}';

    BEGIN TRAN;

    INSERT log.RUN_STEP (RUN_ID, LAYER, OBJECT_CODE, STATUS, ROWS_READ, ROWS_WRITTEN,
                         ROWS_REJECTED, DQ_WARNINGS, NEW_WATERMARK, ERROR_MESSAGE)
    SELECT @RUN_ID, p.layer, p.object_code, p.status, p.rows_read, p.rows_written,
           p.rows_rejected, p.dq_warnings, p.new_watermark, LEFT(p.error, 4000)
    FROM OPENJSON(@RESULT_JSON, '$.pasos')
    WITH (
        layer         VARCHAR(10)    '$.layer',
        object_code   VARCHAR(100)   '$.object_code',
        status        VARCHAR(30)    '$.status',
        rows_read     BIGINT         '$.rows_read',
        rows_written  BIGINT         '$.rows_written',
        rows_rejected BIGINT         '$.rows_rejected',
        dq_warnings   NVARCHAR(MAX)  '$.dq_warnings' AS JSON,
        new_watermark NVARCHAR(50)   '$.new_watermark',
        error         NVARCHAR(MAX)  '$.error'
    ) p;

    /* El watermark avanza solo si bronze terminó bien, silver no falló y el valor
       nuevo es mayor. Así una corrida fallida se reintenta desde el mismo punto:
       bronze vuelve a recibir esas filas (es historia) y el MERGE de silver no duplica. */
    UPDATE e
    SET WATERMARK_VALUE = s.NEW_WATERMARK,
        UPDATED_AT      = SYSUTCDATETIME()
    FROM meta.ENTITY e
    JOIN log.RUN_STEP s
      ON s.RUN_ID = @RUN_ID AND s.LAYER = 'bronze' AND s.OBJECT_CODE = e.ENTITY_CODE
     AND s.STATUS = 'SUCCEEDED' AND s.NEW_WATERMARK IS NOT NULL
    WHERE e.LOAD_TYPE = 'INCREMENTAL'
      AND NOT EXISTS (SELECT 1 FROM log.RUN_STEP f
                      WHERE f.RUN_ID = @RUN_ID AND f.LAYER = 'silver'
                        AND f.OBJECT_CODE = e.ENTITY_CODE AND f.STATUS = 'FAILED')
      AND (
            e.WATERMARK_VALUE IS NULL
         OR (e.WATERMARK_TYPE = 'INT'
             AND TRY_CONVERT(BIGINT, s.NEW_WATERMARK) > TRY_CONVERT(BIGINT, e.WATERMARK_VALUE))
         OR (ISNULL(e.WATERMARK_TYPE, 'DATETIME') = 'DATETIME'
             AND TRY_CONVERT(DATETIME2(7), s.NEW_WATERMARK) > TRY_CONVERT(DATETIME2(7), e.WATERMARK_VALUE))
      );

    DECLARE @status VARCHAR(20) =
        CASE WHEN JSON_VALUE(@RESULT_JSON, '$.hay_errores') = 'true'
               OR EXISTS (SELECT 1 FROM log.RUN_STEP WHERE RUN_ID = @RUN_ID AND STATUS = 'FAILED')
             THEN 'FAILED' ELSE 'SUCCEEDED' END;

    UPDATE log.RUN
    SET STATUS = @status, ENDED_AT = SYSUTCDATETIME(), RESULT_JSON = @RESULT_JSON
    WHERE RUN_ID = @RUN_ID;

    COMMIT;

    SELECT @status AS STATUS;   -- lo lee la condición del pipeline
END
GO

/* Chequeos de consistencia de la metadata. Correlo después de cargar o
   cambiar configuración: si devuelve filas, hay algo para corregir. */
CREATE OR ALTER PROCEDURE meta.usp_VALIDATE_METADATA
AS
BEGIN
    SET NOCOUNT ON;
    SELECT 'ENTITY' AS OBJETO, e.ENTITY_CODE AS CODIGO, x.PROBLEMA
    FROM meta.ENTITY e
    JOIN meta.SOURCE_SYSTEM s ON s.SOURCE_SYSTEM_ID = e.SOURCE_SYSTEM_ID
    CROSS APPLY (VALUES
        (CASE WHEN s.SOURCE_TYPE = 'SQL' AND s.CONNECTION_REF IS NULL
              THEN 'Origen SQL sin CONNECTION_REF' END),
        (CASE WHEN s.SOURCE_TYPE = 'SQL' AND e.LOAD_TYPE = 'INCREMENTAL'
                   AND (e.WATERMARK_COLUMN IS NULL OR e.WATERMARK_TYPE IS NULL)
              THEN 'Incremental SQL sin WATERMARK_COLUMN o WATERMARK_TYPE' END),
        (CASE WHEN s.SOURCE_TYPE = 'FILES' AND e.LOAD_TYPE = 'INCREMENTAL' AND e.FILE_FORMAT = 'delta'
                   AND e.WATERMARK_COLUMN IS NULL
              THEN 'Incremental sobre Delta sin WATERMARK_COLUMN (modifiedAfter no aplica a Delta)' END),
        (CASE WHEN s.SOURCE_TYPE = 'SQL' AND PARSENAME(e.SOURCE_OBJECT, 1) IS NULL
              THEN 'SOURCE_OBJECT no es un nombre esquema.tabla válido' END),
        (CASE WHEN e.BRONZE_TABLE NOT LIKE 'bronze.%' AND e.BRONZE_TABLE NOT LIKE '%.bronze.%'
              THEN 'BRONZE_TABLE fuera del esquema bronze' END),
        (CASE WHEN e.SILVER_TABLE NOT LIKE 'silver.%' AND e.SILVER_TABLE NOT LIKE '%.silver.%'
              THEN 'SILVER_TABLE fuera del esquema silver' END),
        (CASE WHEN e.SILVER_MODE IN ('MERGE', 'SCD2') AND EXISTS (SELECT 1 FROM meta.ENTITY_COLUMN c WHERE c.ENTITY_ID = e.ENTITY_ID)
                   AND EXISTS (SELECT TRIM(value) AS k FROM STRING_SPLIT(e.PRIMARY_KEY, ',')
                               EXCEPT SELECT TARGET_COLUMN FROM meta.ENTITY_COLUMN c WHERE c.ENTITY_ID = e.ENTITY_ID)
              THEN 'PRIMARY_KEY tiene columnas que no están en ENTITY_COLUMN' END),
        (CASE WHEN e.SCD2_COLUMNS IS NOT NULL AND e.SILVER_MODE <> 'SCD2'
              THEN 'SCD2_COLUMNS solo aplica con SILVER_MODE = SCD2' END),
        (CASE WHEN e.SILVER_MODE = 'SCD2' AND EXISTS (SELECT 1 FROM meta.ENTITY_COLUMN c WHERE c.ENTITY_ID = e.ENTITY_ID)
                   AND EXISTS (SELECT TRIM(value) FROM STRING_SPLIT(ISNULL(e.SCD2_COLUMNS, ''), ',') WHERE TRIM(value) <> ''
                               EXCEPT SELECT TARGET_COLUMN FROM meta.ENTITY_COLUMN c WHERE c.ENTITY_ID = e.ENTITY_ID)
              THEN 'SCD2_COLUMNS tiene columnas que no están en ENTITY_COLUMN' END),
        (CASE WHEN e.SILVER_MODE = 'SCD2' AND EXISTS (SELECT 1 FROM meta.ENTITY_COLUMN c
                                                      WHERE c.ENTITY_ID = e.ENTITY_ID AND c.IS_PII = 1
                                                        AND (e.SCD2_COLUMNS IS NULL
                                                             OR c.TARGET_COLUMN IN (SELECT TRIM(value) FROM STRING_SPLIT(e.SCD2_COLUMNS, ','))))
              THEN 'SCD2 sigue columnas PII (SCD2_COLUMNS vacío las incluye): guardaría la historia de un dato personal' END),
        (CASE WHEN e.DELETE_MODE <> 'NONE' AND e.SILVER_MODE NOT IN ('MERGE', 'SCD2')
              THEN 'DELETE_MODE requiere SILVER_MODE MERGE o SCD2' END),
        (CASE WHEN e.DELETE_MODE = 'ABSENT' AND e.LOAD_TYPE <> 'FULL'
              THEN 'DELETE_MODE = ABSENT requiere LOAD_TYPE = FULL: en una incremental, lo que no vino no está borrado' END),
        (CASE WHEN EXISTS (SELECT 1 FROM meta.ENTITY e2 WHERE e2.SILVER_TABLE = e.SILVER_TABLE AND e2.ENTITY_ID <> e.ENTITY_ID)
              THEN 'Otra entidad escribe en la misma SILVER_TABLE' END)
    ) x(PROBLEMA)
    WHERE x.PROBLEMA IS NOT NULL
    UNION ALL
    SELECT 'GOLD_OBJECT', g.GOLD_CODE, x.PROBLEMA
    FROM meta.GOLD_OBJECT g
    CROSS APPLY (VALUES
        (CASE WHEN g.LOAD_MODE = 'MLV' AND g.SQL_TEXT NOT LIKE '%CREATE%MATERIALIZED LAKE VIEW%'
              THEN 'LOAD_MODE = MLV pero SQL_TEXT no es un CREATE MATERIALIZED LAKE VIEW' END),
        (CASE WHEN g.LOAD_MODE <> 'MLV' AND LTRIM(g.SQL_TEXT) NOT LIKE 'SELECT%' AND LTRIM(g.SQL_TEXT) NOT LIKE 'WITH%'
              THEN 'SQL_TEXT debe ser un SELECT (o WITH ... SELECT)' END),
        (CASE WHEN g.TARGET_TABLE NOT LIKE 'gold.%' AND g.TARGET_TABLE NOT LIKE '%.gold.%'
              THEN 'TARGET_TABLE fuera del esquema gold' END),
        (CASE WHEN EXISTS (SELECT TRIM(value) FROM STRING_SPLIT(ISNULL(g.DEPENDS_ON_GOLD, ''), ',') WHERE TRIM(value) <> ''
                           EXCEPT SELECT GOLD_CODE FROM meta.GOLD_OBJECT)
              THEN 'DEPENDS_ON_GOLD nombra un GOLD_CODE que no existe' END)
    ) x(PROBLEMA)
    WHERE x.PROBLEMA IS NOT NULL;
END
GO
