/* =====================================================================
   Calidad y reconciliación · Base de control
   Destino: la misma SQL database de control (DB_TDM_Platform), esquema dq.
   Crea:
     - dq.REGLA                 reglas de cuadre entre capas y de condición sobre gold
     - dq.RESULTADO             un resultado por regla y corrida
     - dq.usp_GET_REGLAS        las reglas activas de un LOAD_GROUP en un JSON (para el Lookup)
     - dq.usp_LOG_RESULTADOS    registra lo que devuelve NB_CAL_01 y dice si hay que frenar
     - dq.v_ultimo_resultado    el último resultado de cada regla (lo lee Monitoreo)

   Mismo patrón que Pipeline_Metadata_Medallion: el notebook no se conecta a la base.
   Recibe las reglas por parámetro y devuelve los resultados por exit; el pipeline
   los lee y los registra con los SP.

   Es idempotente: crea solo lo que no existe y recrea SP y vistas. No borra datos.
   Correlo primero en desarrollo.
   ===================================================================== */

IF SCHEMA_ID('dq') IS NULL EXEC('CREATE SCHEMA dq');
GO

-- ---------------------------------------------------------------------
-- 1. Reglas
-- ---------------------------------------------------------------------

/* Dos tipos:
   COMPARA:   SQL_A y SQL_B (Spark SQL, solo SELECT) devuelven las mismas columnas de
              métricas (ej. filas, importe) y, opcionalmente, las columnas de CLAVE
              (ej. periodo). Falla si alguna métrica difiere más que la tolerancia.
   CONDICION: SQL_A devuelve una fila con un número en la primera columna.
              Falla si queda fuera de [VALOR_MIN, VALOR_MAX].
   Una métrica falla solo si supera las DOS tolerancias (absoluta y porcentual). */
IF OBJECT_ID('dq.REGLA') IS NULL
CREATE TABLE dq.REGLA (
    REGLA_ID           INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DQ_REGLA PRIMARY KEY,
    REGLA_CODE         VARCHAR(100)   NOT NULL CONSTRAINT UQ_DQ_REGLA_CODE UNIQUE,  -- ej. cuadre_ventas_silver_gold
    DESCRIPCION        NVARCHAR(500)  NOT NULL,                                     -- qué controla, en lenguaje de negocio
    LOAD_GROUP         VARCHAR(50)    NOT NULL CONSTRAINT DF_DQ_REGLA_GROUP DEFAULT ('default'),
    CATEGORIA          VARCHAR(20)    NOT NULL
        CONSTRAINT CK_DQ_REGLA_CATEGORIA CHECK (CATEGORIA IN ('CUADRE', 'INTEGRIDAD', 'FRESCURA', 'VOLUMEN', 'NEGOCIO')),
    TIPO               VARCHAR(10)    NOT NULL
        CONSTRAINT CK_DQ_REGLA_TIPO CHECK (TIPO IN ('COMPARA', 'CONDICION')),
    SQL_A              NVARCHAR(MAX)  NOT NULL,
    SQL_B              NVARCHAR(MAX)  NULL,
    CLAVE              NVARCHAR(200)  NULL,      -- COMPARA: columnas de cruce separadas por coma (período, categoría). Nunca datos de personas
    METRICAS           NVARCHAR(500)  NULL,      -- COMPARA: columnas a comparar; NULL = todas las que no son CLAVE
    TOLERANCIA_ABS     DECIMAL(38,4)  NOT NULL CONSTRAINT DF_DQ_REGLA_TABS DEFAULT (0),
    TOLERANCIA_PCT     DECIMAL(9,4)   NOT NULL CONSTRAINT DF_DQ_REGLA_TPCT DEFAULT (0),
    VALOR_MIN          DECIMAL(38,4)  NULL,      -- CONDICION
    VALOR_MAX          DECIMAL(38,4)  NULL,      -- CONDICION
    SEVERIDAD          VARCHAR(10)    NOT NULL
        CONSTRAINT CK_DQ_REGLA_SEVERIDAD CHECK (SEVERIDAD IN ('ERROR', 'WARN')),
        -- ERROR: frena el pipeline (no se refresca el modelo). WARN: se registra y se avisa
    DUENO              NVARCHAR(200)  NULL,      -- área responsable del dato
    IS_ACTIVE          BIT            NOT NULL CONSTRAINT DF_DQ_REGLA_ACTIVE DEFAULT (1),
    CREATED_AT         DATETIME2(0)   NOT NULL CONSTRAINT DF_DQ_REGLA_CREATED DEFAULT (SYSUTCDATETIME()),
    UPDATED_AT         DATETIME2(0)   NOT NULL CONSTRAINT DF_DQ_REGLA_UPDATED DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT CK_DQ_REGLA_COMPARA   CHECK (TIPO <> 'COMPARA'   OR SQL_B IS NOT NULL),
    CONSTRAINT CK_DQ_REGLA_CONDICION CHECK (TIPO <> 'CONDICION' OR VALOR_MIN IS NOT NULL OR VALOR_MAX IS NOT NULL)
);
GO

-- ---------------------------------------------------------------------
-- 2. Resultados
-- ---------------------------------------------------------------------
IF OBJECT_ID('dq.RESULTADO') IS NULL
CREATE TABLE dq.RESULTADO (
    RESULTADO_ID       BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_DQ_RESULTADO PRIMARY KEY,
    RUN_ID             VARCHAR(64)    NOT NULL,  -- @pipeline().RunId, o 'manual'
    REGLA_CODE         VARCHAR(100)   NOT NULL,
    ESTADO             VARCHAR(20)    NOT NULL
        CONSTRAINT CK_DQ_RESULTADO_ESTADO CHECK (ESTADO IN ('OK', 'FALLA', 'ERROR_EJECUCION')),
    SEVERIDAD          VARCHAR(10)    NOT NULL,
    VALOR_A            DECIMAL(38,4)  NULL,
    VALOR_B            DECIMAL(38,4)  NULL,
    DIFERENCIA         DECIMAL(38,4)  NULL,
    DIFERENCIA_PCT     DECIMAL(18,4)  NULL,
    DETALLE            NVARCHAR(2000) NULL,      -- claves y métricas que fallaron. Nunca filas ni datos de personas
    EVALUADO_AT        DATETIME2(0)   NOT NULL CONSTRAINT DF_DQ_RESULTADO_AT DEFAULT (SYSUTCDATETIME())
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_DQ_RESULTADO_REGLA')
    CREATE INDEX IX_DQ_RESULTADO_REGLA ON dq.RESULTADO (REGLA_CODE, EVALUADO_AT DESC);
GO

-- ---------------------------------------------------------------------
-- 3. Stored procedures que usa el pipeline
-- ---------------------------------------------------------------------

/* Una fila, columna REGLAS_JSON, con las reglas activas del grupo. */
CREATE OR ALTER PROCEDURE dq.usp_GET_REGLAS
    @LOAD_GROUP VARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @json NVARCHAR(MAX) = (
        SELECT REGLA_CODE AS regla_code, DESCRIPCION AS descripcion, CATEGORIA AS categoria, TIPO AS tipo,
               SQL_A AS sql_a, SQL_B AS sql_b, CLAVE AS clave, METRICAS AS metricas,
               TOLERANCIA_ABS AS tolerancia_abs, TOLERANCIA_PCT AS tolerancia_pct,
               VALOR_MIN AS valor_min, VALOR_MAX AS valor_max, SEVERIDAD AS severidad
        FROM dq.REGLA
        WHERE IS_ACTIVE = 1 AND LOAD_GROUP = @LOAD_GROUP
        ORDER BY REGLA_CODE
        FOR JSON PATH, INCLUDE_NULL_VALUES
    );
    SELECT COALESCE(@json, N'[]') AS REGLAS_JSON;
END
GO

/* Registra los resultados de NB_CAL_01 (el exitValue del notebook) y devuelve
   HAY_ERROR = 1 si alguna regla ERROR falló o no se pudo ejecutar.
   Si el JSON no es válido, registra un resultado de error para que no pase en silencio. */
CREATE OR ALTER PROCEDURE dq.usp_LOG_RESULTADOS
    @RUN_ID VARCHAR(64), @RESULTADOS_JSON NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF ISJSON(@RESULTADOS_JSON) <> 1
    BEGIN
        INSERT dq.RESULTADO (RUN_ID, REGLA_CODE, ESTADO, SEVERIDAD, DETALLE)
        VALUES (@RUN_ID, '_notebook', 'ERROR_EJECUCION', 'ERROR', N'NB_CAL_01 no devolvió un JSON válido');
        SELECT CAST(1 AS BIT) AS HAY_ERROR, 0 AS REGLAS, 0 AS FALLAS;
        RETURN;
    END

    DECLARE @r TABLE (ESTADO VARCHAR(20), SEVERIDAD VARCHAR(10));

    INSERT dq.RESULTADO (RUN_ID, REGLA_CODE, ESTADO, SEVERIDAD, VALOR_A, VALOR_B, DIFERENCIA, DIFERENCIA_PCT, DETALLE)
    OUTPUT inserted.ESTADO, inserted.SEVERIDAD INTO @r
    SELECT @RUN_ID, r.regla_code, r.estado, r.severidad, r.valor_a, r.valor_b, r.diferencia, r.diferencia_pct,
           LEFT(r.detalle, 2000)
    FROM OPENJSON(@RESULTADOS_JSON, '$.resultados') WITH (
        regla_code     VARCHAR(100)   '$.regla_code',
        estado         VARCHAR(20)    '$.estado',
        severidad      VARCHAR(10)    '$.severidad',
        valor_a        DECIMAL(38,4)  '$.valor_a',
        valor_b        DECIMAL(38,4)  '$.valor_b',
        diferencia     DECIMAL(38,4)  '$.diferencia',
        diferencia_pct DECIMAL(18,4)  '$.diferencia_pct',
        detalle        NVARCHAR(MAX)  '$.detalle'
    ) r;

    -- Solo lo registrado en esta llamada: una corrida 'manual' repetida no arrastra resultados viejos
    SELECT
        CAST(CASE WHEN EXISTS (SELECT 1 FROM @r WHERE SEVERIDAD = 'ERROR' AND ESTADO <> 'OK')
                  THEN 1 ELSE 0 END AS BIT) AS HAY_ERROR,
        (SELECT COUNT(*) FROM @r) AS REGLAS,
        (SELECT COUNT(*) FROM @r WHERE ESTADO <> 'OK') AS FALLAS;
END
GO

-- ---------------------------------------------------------------------
-- 4. Vistas
-- ---------------------------------------------------------------------

/* Último resultado de cada regla activa (Monitoreo_Plataforma lo convierte en alertas). */
CREATE OR ALTER VIEW dq.v_ultimo_resultado AS
SELECT r.REGLA_CODE, g.DESCRIPCION, g.CATEGORIA, g.LOAD_GROUP, g.DUENO,
       r.ESTADO, r.SEVERIDAD, r.VALOR_A, r.VALOR_B, r.DIFERENCIA, r.DIFERENCIA_PCT, r.DETALLE,
       r.RUN_ID, r.EVALUADO_AT
FROM dq.REGLA g
CROSS APPLY (
    SELECT TOP (1) * FROM dq.RESULTADO x
    WHERE x.REGLA_CODE = g.REGLA_CODE
    ORDER BY x.EVALUADO_AT DESC, x.RESULTADO_ID DESC
) r
WHERE g.IS_ACTIVE = 1;
GO

-- ---------------------------------------------------------------------
-- 5. Permisos sugeridos (mínimo privilegio)
-- ---------------------------------------------------------------------
/*
-- La identidad del pipeline: lee reglas y registra resultados
GRANT EXECUTE ON dq.usp_GET_REGLAS      TO [<identidad-pipeline>];
GRANT EXECUTE ON dq.usp_LOG_RESULTADOS  TO [<identidad-pipeline>];
-- La identidad de Monitoreo
GRANT SELECT  ON dq.v_ultimo_resultado  TO [<identidad-monitoreo>];
-- Las reglas se cargan con scripts revisados (alta_reglas_calidad.sql), no desde el pipeline
*/

-- ---------------------------------------------------------------------
-- Vuelta atrás: no toca tablas de otros casos. Para sacar el framework:
--   sacar del pipeline las actividades de calidad, después DROP de dq.* y DROP SCHEMA dq.
--   Cambio con impacto: se pierde la historia de resultados (hacé backup antes).
-- ---------------------------------------------------------------------
