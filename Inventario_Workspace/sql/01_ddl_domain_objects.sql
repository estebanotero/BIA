/* =====================================================================
   Inventario de items de Fabric -> config.DOMAIN_OBJECTS
   Motor: SQL database en Microsoft Fabric (mismo motor que Azure SQL DB)

   Orden de ejecución:
     PASO 0  Backup de la tabla actual            (no destructivo)
     PASO 1  Tabla staging                         (no destructivo)
     PASO 2  Tabla nueva con IDENTITY + PK         (no destructivo)
     PASO 3  Copiar datos conservando los ID       (no destructivo)
     PASO 4  Swap de nombres                       (*** CAMBIO CON IMPACTO ***)
     PASO 5  Stored procedure de MERGE             (no destructivo)

   Correlo primero en un entorno de prueba (DES).
   ===================================================================== */

/* ---------------------------------------------------------------------
   PASO 0. Backup de la tabla actual
   --------------------------------------------------------------------- */
SELECT *
INTO   config.DOMAIN_OBJECTS_BKP_20261022
FROM   config.DOMAIN_OBJECTS;

/* ---------------------------------------------------------------------
   PASO 1. Tabla staging: la pisa el notebook en cada corrida.
   Si no existe, el conector de Spark la crea solo; la dejamos creada
   para controlar los tipos de dato.
   --------------------------------------------------------------------- */
IF OBJECT_ID('config.STG_DOMAIN_OBJECTS') IS NULL
CREATE TABLE config.STG_DOMAIN_OBJECTS (
    WORKSPACE_ID      VARCHAR(36)    NOT NULL,
    OBJECT_NAME       NVARCHAR(256)  NOT NULL,
    FABRIC_ITEM_GUID  VARCHAR(36)    NOT NULL,
    SOURCE_TYPE_ID    INT            NULL,
    ARTIFACT_TYPE     NVARCHAR(100)  NOT NULL,
    EXTRACTED_AT      DATETIME2(0)   NOT NULL
);

/* ---------------------------------------------------------------------
   PASO 2. Tabla definitiva con ID numérico estable (IDENTITY)
   - ID: lo genera SQL, nunca se reutiliza.
   - FABRIC_ITEM_GUID: clave natural, única.
   - Soft delete: ACTIVE_FLAG = 0 + DELETED_AT; la fila no se borra.
   --------------------------------------------------------------------- */
CREATE TABLE config.DOMAIN_OBJECTS_NEW (
    ID                INT IDENTITY(1,1) NOT NULL,
    WORKSPACE_ID      VARCHAR(36)    NOT NULL,
    OBJECT_NAME       NVARCHAR(256)  NOT NULL,
    FABRIC_ITEM_GUID  VARCHAR(36)    NOT NULL,
    SOURCE_TYPE_ID    INT            NULL,
    ARTIFACT_TYPE     NVARCHAR(100)  NOT NULL,
    ACTIVE_FLAG       BIT            NOT NULL CONSTRAINT DF_DOMAIN_OBJECTS_ACTIVE  DEFAULT (1),
    CREATED_AT        DATETIME2(0)   NOT NULL CONSTRAINT DF_DOMAIN_OBJECTS_CREATED DEFAULT (SYSUTCDATETIME()),
    UPDATED_AT        DATETIME2(0)   NULL,
    LAST_SEEN_AT      DATETIME2(0)   NULL,
    DELETED_AT        DATETIME2(0)   NULL,
    CONSTRAINT PK_DOMAIN_OBJECTS      PRIMARY KEY CLUSTERED (ID),
    CONSTRAINT UQ_DOMAIN_OBJECTS_GUID UNIQUE (FABRIC_ITEM_GUID)
);

CREATE INDEX IX_DOMAIN_OBJECTS_WS_ACTIVE
    ON config.DOMAIN_OBJECTS_NEW (WORKSPACE_ID, ACTIVE_FLAG);

/* ---------------------------------------------------------------------
   PASO 3. Copiar lo que ya existe conservando los ID actuales.
   Si la tabla actual tiene GUID duplicados este INSERT falla por la
   UNIQUE: revisalo antes con
     SELECT FABRIC_ITEM_GUID, COUNT(*) FROM config.DOMAIN_OBJECTS
     GROUP BY FABRIC_ITEM_GUID HAVING COUNT(*) > 1;
   --------------------------------------------------------------------- */
SET IDENTITY_INSERT config.DOMAIN_OBJECTS_NEW ON;

INSERT INTO config.DOMAIN_OBJECTS_NEW
      (ID, WORKSPACE_ID, OBJECT_NAME, FABRIC_ITEM_GUID, SOURCE_TYPE_ID,
       ARTIFACT_TYPE, ACTIVE_FLAG, CREATED_AT, LAST_SEEN_AT)
SELECT CAST(ID AS INT), WORKSPACE_ID, OBJECT_NAME, FABRIC_ITEM_GUID, SOURCE_TYPE_ID,
       ARTIFACT_TYPE, COALESCE(ACTIVE_FLAG, 1), SYSUTCDATETIME(), SYSUTCDATETIME()
FROM   config.DOMAIN_OBJECTS;

SET IDENTITY_INSERT config.DOMAIN_OBJECTS_NEW OFF;

-- El próximo ID sigue después del máximo copiado
DECLARE @max INT = (SELECT COALESCE(MAX(ID), 0) FROM config.DOMAIN_OBJECTS_NEW);
DBCC CHECKIDENT ('config.DOMAIN_OBJECTS_NEW', RESEED, @max);

/* ---------------------------------------------------------------------
   PASO 4. *** CAMBIO CON IMPACTO ***
   Reemplaza la tabla vieja por la nueva. Si algo (vista, FK, reporte,
   pipeline) apunta a config.DOMAIN_OBJECTS, sigue funcionando porque el
   nombre final es el mismo, pero revisá FKs que referencien la vieja.
   Vuelta atrás: renombrar al revés, o restaurar desde el backup del PASO 0.
   --------------------------------------------------------------------- */
BEGIN TRAN;
    EXEC sp_rename 'config.DOMAIN_OBJECTS',     'DOMAIN_OBJECTS_OLD';
    EXEC sp_rename 'config.DOMAIN_OBJECTS_NEW', 'DOMAIN_OBJECTS';
COMMIT;
-- Cuando confirmes que todo anda:  DROP TABLE config.DOMAIN_OBJECTS_OLD;
GO

/* ---------------------------------------------------------------------
   PASO 5. Stored procedure que sincroniza staging -> tabla definitiva
   - Altas: items nuevos (ID automático).
   - Cambios: renombres / cambio de tipo, y reactivación si reaparece.
   - Bajas: soft delete SOLO de los workspaces presentes en staging
     (así no se "borra" el inventario de otros workspaces).
   - Guardia: si staging viene vacía, no hace nada (evita marcar todo
     como borrado si list_items falló o no tenía permisos).
   --------------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE config.usp_SYNC_DOMAIN_OBJECTS
    @MinRowsExpected INT = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @now  DATETIME2(0) = SYSUTCDATETIME();
    DECLARE @rows INT = (SELECT COUNT(*) FROM config.STG_DOMAIN_OBJECTS);

    IF @rows < @MinRowsExpected
    BEGIN
        RAISERROR('Staging con %d filas (< %d). No se sincroniza.', 16, 1, @rows, @MinRowsExpected);
        RETURN;
    END;

    -- Por si el origen trae duplicados
    ;WITH src AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY FABRIC_ITEM_GUID ORDER BY EXTRACTED_AT DESC) AS rn
        FROM   config.STG_DOMAIN_OBJECTS
    )
    SELECT WORKSPACE_ID, OBJECT_NAME, FABRIC_ITEM_GUID, SOURCE_TYPE_ID, ARTIFACT_TYPE
    INTO   #src
    FROM   src
    WHERE  rn = 1;

    DECLARE @log TABLE (ACCION NVARCHAR(10));

    BEGIN TRAN;

        MERGE config.DOMAIN_OBJECTS AS t
        USING #src AS s
           ON t.FABRIC_ITEM_GUID = s.FABRIC_ITEM_GUID

        -- Existe: actualizo si cambió algo o si estaba dado de baja
        WHEN MATCHED AND (
                 t.OBJECT_NAME   <> s.OBJECT_NAME
              OR t.ARTIFACT_TYPE <> s.ARTIFACT_TYPE
              OR t.WORKSPACE_ID  <> s.WORKSPACE_ID
              OR ISNULL(t.SOURCE_TYPE_ID, -1) <> ISNULL(s.SOURCE_TYPE_ID, -1)
              OR t.ACTIVE_FLAG = 0)
        THEN UPDATE SET
              t.OBJECT_NAME    = s.OBJECT_NAME,
              t.ARTIFACT_TYPE  = s.ARTIFACT_TYPE,
              t.WORKSPACE_ID   = s.WORKSPACE_ID,
              t.SOURCE_TYPE_ID = s.SOURCE_TYPE_ID,
              t.ACTIVE_FLAG    = 1,
              t.DELETED_AT     = NULL,
              t.UPDATED_AT     = @now,
              t.LAST_SEEN_AT   = @now

        -- Nuevo: alta (el ID lo pone IDENTITY)
        WHEN NOT MATCHED BY TARGET THEN
            INSERT (WORKSPACE_ID, OBJECT_NAME, FABRIC_ITEM_GUID, SOURCE_TYPE_ID,
                    ARTIFACT_TYPE, ACTIVE_FLAG, CREATED_AT, LAST_SEEN_AT)
            VALUES (s.WORKSPACE_ID, s.OBJECT_NAME, s.FABRIC_ITEM_GUID, s.SOURCE_TYPE_ID,
                    s.ARTIFACT_TYPE, 1, @now, @now)

        -- No vino en esta corrida y es de un workspace inventariado: baja lógica
        WHEN NOT MATCHED BY SOURCE
             AND t.ACTIVE_FLAG = 1
             AND t.WORKSPACE_ID IN (SELECT DISTINCT WORKSPACE_ID FROM #src)
        THEN UPDATE SET
              t.ACTIVE_FLAG = 0,
              t.DELETED_AT  = @now,
              t.UPDATED_AT  = @now

        OUTPUT $action INTO @log;

        -- Items sin cambios: solo marco que se vieron
        UPDATE t
           SET LAST_SEEN_AT = @now
          FROM config.DOMAIN_OBJECTS t
          JOIN #src s ON s.FABRIC_ITEM_GUID = t.FABRIC_ITEM_GUID
         WHERE t.LAST_SEEN_AT IS NULL OR t.LAST_SEEN_AT < @now;

    COMMIT;

    -- Resumen para el log del notebook / pipeline
    SELECT
        @rows                                                           AS FILAS_STAGING,
        SUM(CASE WHEN ACCION = 'INSERT' THEN 1 ELSE 0 END)              AS ALTAS,
        SUM(CASE WHEN ACCION = 'UPDATE' THEN 1 ELSE 0 END)              AS CAMBIOS_O_BAJAS
    FROM @log;
END;
GO

/* ---------------------------------------------------------------------
   Consultas útiles
   --------------------------------------------------------------------- */
-- Inventario vigente
-- SELECT * FROM config.DOMAIN_OBJECTS WHERE ACTIVE_FLAG = 1 ORDER BY ID;
-- Bajas recientes
-- SELECT * FROM config.DOMAIN_OBJECTS WHERE DELETED_AT >= DATEADD(day, -7, SYSUTCDATETIME());
-- Tipos de Fabric que no están en config.SOURCE_TYPES (SOURCE_TYPE_ID nulo)
-- SELECT ARTIFACT_TYPE, COUNT(*) FROM config.DOMAIN_OBJECTS WHERE SOURCE_TYPE_ID IS NULL GROUP BY ARTIFACT_TYPE;
