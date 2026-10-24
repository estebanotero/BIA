/* =====================================================================
   Monitoreo de la plataforma · Base de control
   Destino: la misma SQL database de control (DB_TDM_Platform), esquema mon.
   Crea:
     - mon.SLA_CARGA     a qué hora tiene que estar lista cada LOAD_GROUP
     - mon.ALERTA        alertas abiertas y su historia (una fila por aparición)
     - mon.STG_ALERTA    staging que escribe NB_MON_01 en cada corrida
     - mon.usp_SYNC_ALERTAS  abre, actualiza y cierra alertas
     - vistas mon.v_*    para NB_MON_01, el reporte operativo y la skill

   Requisito: haber corrido antes 01_ddl_control.sql de Pipeline_Metadata_Medallion
   (log.RUN, log.RUN_STEP, meta.ENTITY). La vista del inventario se crea solo
   si existe config.DOMAIN_OBJECTS (Inventario_Workspace).

   Es idempotente: crea solo lo que no existe y recrea vistas y SP.
   No borra datos. Correlo primero en desarrollo.
   ===================================================================== */

IF SCHEMA_ID('mon') IS NULL EXEC('CREATE SCHEMA mon');
GO

-- ---------------------------------------------------------------------
-- 1. Configuración: SLA por grupo de carga
-- ---------------------------------------------------------------------

/* Una fila por LOAD_GROUP con hora límite. Las horas van en UTC
   (Argentina = UTC-3: si gold tiene que estar a las 07:00, poné '10:00').
   DIAS_SEMANA: días ISO en que aplica, 1 = lunes ... 7 = domingo. */
IF OBJECT_ID('mon.SLA_CARGA') IS NULL
CREATE TABLE mon.SLA_CARGA (
    LOAD_GROUP         VARCHAR(50)   NOT NULL CONSTRAINT PK_SLA_CARGA PRIMARY KEY,
    HORA_LIMITE_UTC    CHAR(5)       NOT NULL
        CONSTRAINT CK_SLA_HORA CHECK (HORA_LIMITE_UTC LIKE '[0-2][0-9]:[0-5][0-9]'),
    DIAS_SEMANA        VARCHAR(7)    NOT NULL CONSTRAINT DF_SLA_DIAS DEFAULT ('12345'),
    MAX_DURACION_MIN   INT           NULL,      -- una corrida RUNNING más tiempo que esto se considera colgada
    DUENO              NVARCHAR(200) NULL,      -- equipo o persona a la que se avisa (texto, no una dirección)
    IS_ACTIVE          BIT           NOT NULL CONSTRAINT DF_SLA_ACTIVE DEFAULT (1),
    UPDATED_AT         DATETIME2(0)  NOT NULL CONSTRAINT DF_SLA_UPDATED DEFAULT (SYSUTCDATETIME())
);
GO

-- ---------------------------------------------------------------------
-- 2. Alertas
-- ---------------------------------------------------------------------

/* Una fila por aparición de una alerta. CLAVE identifica "la misma" alerta
   entre corridas (ej. MDP_PASO_FALLIDO|silver|erp_clientes): mientras siga
   apareciendo se actualiza la misma fila; cuando deja de aparecer se cierra
   (RESUELTA_AT). Si vuelve, abre una fila nueva. */
IF OBJECT_ID('mon.ALERTA') IS NULL
CREATE TABLE mon.ALERTA (
    ALERTA_ID          BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ALERTA PRIMARY KEY,
    CLAVE              VARCHAR(300)   NOT NULL,
    ORIGEN             VARCHAR(10)    NOT NULL,  -- MDP | INV | AGT | PERF
    SEVERIDAD          VARCHAR(10)    NOT NULL
        CONSTRAINT CK_ALERTA_SEVERIDAD CHECK (SEVERIDAD IN ('ALTA', 'MEDIA', 'BAJA')),
    CODIGO             VARCHAR(50)    NOT NULL,  -- regla que la generó, ej. MDP_SLA_INCUMPLIDO
    OBJETO             NVARCHAR(300)  NOT NULL,  -- entidad, LOAD_GROUP, agente, modelo, workspace
    MENSAJE            NVARCHAR(2000) NOT NULL,
    DETECTADA_AT       DATETIME2(0)   NOT NULL,
    ULTIMA_VEZ_AT      DATETIME2(0)   NOT NULL,
    VECES              INT            NOT NULL CONSTRAINT DF_ALERTA_VECES DEFAULT (1),
    RESUELTA_AT        DATETIME2(0)   NULL
);
GO

-- Solo una alerta abierta por clave
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_ALERTA_ABIERTA')
    CREATE UNIQUE INDEX UX_ALERTA_ABIERTA ON mon.ALERTA (CLAVE) WHERE RESUELTA_AT IS NULL;
GO

/* Staging: la foto de alertas de la última corrida de NB_MON_01. Se pisa siempre. */
IF OBJECT_ID('mon.STG_ALERTA') IS NULL
CREATE TABLE mon.STG_ALERTA (
    CLAVE              VARCHAR(300)   NOT NULL,
    ORIGEN             VARCHAR(10)    NOT NULL,
    SEVERIDAD          VARCHAR(10)    NOT NULL,
    CODIGO             VARCHAR(50)    NOT NULL,
    OBJETO             NVARCHAR(300)  NOT NULL,
    MENSAJE            NVARCHAR(2000) NOT NULL
);
GO

/* Sincroniza la staging con mon.ALERTA.
   @ORIGENES: orígenes que NB_MON_01 pudo evaluar en esta corrida, separados por coma
   (ej. 'MDP,INV,AGT'). Solo se cierran alertas de esos orígenes: si una tabla del
   lakehouse no existía, sus alertas abiertas quedan como estaban. */
CREATE OR ALTER PROCEDURE mon.usp_SYNC_ALERTAS
    @ORIGENES NVARCHAR(200)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    DECLARE @ahora DATETIME2(0) = SYSUTCDATETIME();
    DECLARE @nuevas TABLE (SEVERIDAD VARCHAR(10));
    DECLARE @resueltas INT;

    -- La staging puede traer la misma clave dos veces si alguien la carga a mano: se queda la primera
    ;WITH stg AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY CLAVE ORDER BY SEVERIDAD) AS rn
        FROM mon.STG_ALERTA
    )
    SELECT CLAVE, ORIGEN, SEVERIDAD, CODIGO, OBJETO, MENSAJE
    INTO #stg
    FROM stg WHERE rn = 1;

    BEGIN TRAN;

    -- Siguen abiertas: se actualizan
    UPDATE a
       SET ULTIMA_VEZ_AT = @ahora,
           VECES         = a.VECES + 1,
           SEVERIDAD     = s.SEVERIDAD,
           MENSAJE       = s.MENSAJE
      FROM mon.ALERTA a
      JOIN #stg s ON s.CLAVE = a.CLAVE
     WHERE a.RESUELTA_AT IS NULL;

    -- Nuevas
    INSERT mon.ALERTA (CLAVE, ORIGEN, SEVERIDAD, CODIGO, OBJETO, MENSAJE, DETECTADA_AT, ULTIMA_VEZ_AT)
    OUTPUT inserted.SEVERIDAD INTO @nuevas
    SELECT s.CLAVE, s.ORIGEN, s.SEVERIDAD, s.CODIGO, s.OBJETO, s.MENSAJE, @ahora, @ahora
      FROM #stg s
     WHERE NOT EXISTS (SELECT 1 FROM mon.ALERTA a WHERE a.CLAVE = s.CLAVE AND a.RESUELTA_AT IS NULL);

    -- Dejaron de aparecer: se cierran (solo de los orígenes evaluados)
    UPDATE a
       SET RESUELTA_AT = @ahora
      FROM mon.ALERTA a
     WHERE a.RESUELTA_AT IS NULL
       AND a.ORIGEN IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@ORIGENES, ','))
       AND NOT EXISTS (SELECT 1 FROM #stg s WHERE s.CLAVE = a.CLAVE);
    SET @resueltas = @@ROWCOUNT;

    COMMIT;

    SELECT
        (SELECT COUNT(*) FROM @nuevas)                                AS NUEVAS,
        (SELECT COUNT(*) FROM @nuevas WHERE SEVERIDAD = 'ALTA')       AS NUEVAS_ALTA,
        (SELECT COUNT(*) FROM mon.ALERTA WHERE RESUELTA_AT IS NULL)   AS ABIERTAS,
        @resueltas                                                    AS RESUELTAS;
END
GO

-- ---------------------------------------------------------------------
-- 3. Vistas
-- ---------------------------------------------------------------------

/* Corridas del pipeline medallion con duración y pasos por estado. */
CREATE OR ALTER VIEW mon.v_corridas AS
SELECT
    r.RUN_ID, r.PIPELINE_NAME, r.LOAD_GROUP, r.STATUS, r.STARTED_AT, r.ENDED_AT,
    DATEDIFF(MINUTE, r.STARTED_AT, COALESCE(r.ENDED_AT, SYSUTCDATETIME())) AS DURACION_MIN,
    p.PASOS, p.PASOS_FALLIDOS, p.PASOS_SALTEADOS, p.FILAS_ESCRITAS, p.FILAS_RECHAZADAS
FROM log.RUN r
OUTER APPLY (
    SELECT
        COUNT(*)                                                AS PASOS,
        SUM(CASE WHEN s.STATUS = 'FAILED' THEN 1 ELSE 0 END)    AS PASOS_FALLIDOS,
        SUM(CASE WHEN s.STATUS LIKE 'SKIPPED%' THEN 1 ELSE 0 END) AS PASOS_SALTEADOS,
        SUM(s.ROWS_WRITTEN)                                     AS FILAS_ESCRITAS,
        SUM(s.ROWS_REJECTED)                                    AS FILAS_RECHAZADAS
    FROM log.RUN_STEP s WHERE s.RUN_ID = r.RUN_ID
) p;
GO

/* Pasos con el grupo de carga de su corrida. */
CREATE OR ALTER VIEW mon.v_pasos AS
SELECT
    s.RUN_STEP_ID, s.RUN_ID, r.LOAD_GROUP, r.PIPELINE_NAME, s.LAYER, s.OBJECT_CODE, s.STATUS,
    s.ROWS_READ, s.ROWS_WRITTEN, s.ROWS_REJECTED, s.ERROR_MESSAGE, s.LOGGED_AT
FROM log.RUN_STEP s
JOIN log.RUN r ON r.RUN_ID = s.RUN_ID;
GO

/* Última vez que cada entidad activa trajo filas a silver. */
CREATE OR ALTER VIEW mon.v_frescura_entidad AS
SELECT
    e.ENTITY_CODE, e.LOAD_GROUP, e.LOAD_TYPE,
    f.ULTIMA_CARGA_CON_DATOS,
    u.ULTIMO_PASO_AT, u.ULTIMO_ESTADO
FROM meta.ENTITY e
OUTER APPLY (
    SELECT MAX(s.LOGGED_AT) AS ULTIMA_CARGA_CON_DATOS
    FROM log.RUN_STEP s
    WHERE s.OBJECT_CODE = e.ENTITY_CODE AND s.LAYER = 'silver'
      AND s.STATUS = 'SUCCEEDED' AND s.ROWS_WRITTEN > 0
) f
OUTER APPLY (
    SELECT TOP (1) s.LOGGED_AT AS ULTIMO_PASO_AT, s.STATUS AS ULTIMO_ESTADO
    FROM log.RUN_STEP s
    WHERE s.OBJECT_CODE = e.ENTITY_CODE AND s.LAYER = 'silver'
    ORDER BY s.LOGGED_AT DESC
) u
WHERE e.IS_ACTIVE = 1;
GO

/* Alertas abiertas, de la más grave a la más vieja. */
CREATE OR ALTER VIEW mon.v_alertas_abiertas AS
SELECT
    ALERTA_ID, SEVERIDAD, ORIGEN, CODIGO, OBJETO, MENSAJE, DETECTADA_AT, ULTIMA_VEZ_AT, VECES,
    DATEDIFF(HOUR, DETECTADA_AT, SYSUTCDATETIME()) AS HORAS_ABIERTA,
    CASE SEVERIDAD WHEN 'ALTA' THEN 1 WHEN 'MEDIA' THEN 2 ELSE 3 END AS ORDEN_SEVERIDAD
FROM mon.ALERTA
WHERE RESUELTA_AT IS NULL;
GO

/* Inventario de items (solo si está Inventario_Workspace). */
IF OBJECT_ID('config.DOMAIN_OBJECTS') IS NOT NULL
    EXEC('CREATE OR ALTER VIEW mon.v_inventario AS
          SELECT WORKSPACE_ID, OBJECT_NAME, ARTIFACT_TYPE, ACTIVE_FLAG,
                 CREATED_AT, UPDATED_AT, LAST_SEEN_AT, DELETED_AT
          FROM config.DOMAIN_OBJECTS');
GO

-- ---------------------------------------------------------------------
-- 4. Ejemplo de SLA (descomentá y ajustá)
-- ---------------------------------------------------------------------
/*
INSERT mon.SLA_CARGA (LOAD_GROUP, HORA_LIMITE_UTC, DIAS_SEMANA, MAX_DURACION_MIN, DUENO)
VALUES ('default', '10:00', '12345', 120, N'Equipo de datos');   -- 07:00 en Argentina
*/

-- ---------------------------------------------------------------------
-- 5. Permisos sugeridos (mínimo privilegio)
-- ---------------------------------------------------------------------
/*
-- La identidad que corre NB_MON_01: lee log/meta/config y escribe solo en mon
GRANT SELECT ON SCHEMA::log    TO [<identidad-monitoreo>];
GRANT SELECT ON SCHEMA::meta   TO [<identidad-monitoreo>];
GRANT SELECT ON SCHEMA::config TO [<identidad-monitoreo>];
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::mon TO [<identidad-monitoreo>];
GRANT EXECUTE ON mon.usp_SYNC_ALERTAS TO [<identidad-monitoreo>];
-- Quien mira el reporte: solo las vistas
GRANT SELECT ON mon.v_alertas_abiertas TO [<grupo-operacion>];
GRANT SELECT ON mon.v_corridas         TO [<grupo-operacion>];
*/

-- ---------------------------------------------------------------------
-- Vuelta atrás: no toca tablas de otros casos. Para sacar el monitoreo:
--   DROP VIEW / PROCEDURE / TABLE de mon.* y DROP SCHEMA mon.
--   Cambio con impacto: se pierde la historia de alertas (hacé backup antes).
-- ---------------------------------------------------------------------
