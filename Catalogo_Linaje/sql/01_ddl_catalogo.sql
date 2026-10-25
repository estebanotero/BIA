/* =====================================================================
   Catálogo y linaje · Base de control
   Destino: la misma SQL database de control (DB_TDM_Platform), esquema cat.
   Crea:
     - cat.ACTIVO            dueño, área, criticidad y descripción de negocio de cada activo
                             (tabla de gold, modelo semántico, reporte) del linaje
     - cat.usp_GET_FUENTES   todo lo que necesita NB_CAT_01 en un JSON (para el Lookup):
                             entidades y columnas PII (meta), objetos gold, items del
                             inventario (config, si está instalado) y activos (cat)

   Mismo patrón que Pipeline_Metadata_Medallion: el notebook no se conecta a la base.
   Recibe las fuentes por parámetro y escribe el linaje en el lakehouse (esquema catalogo).

   Requiere el esquema meta del pipeline medallion (01_ddl_control.sql, versión con
   DELETE_MODE). El inventario (config.DOMAIN_OBJECTS) es opcional.
   Es idempotente: crea solo lo que no existe y recrea el SP. No borra datos.
   Correlo primero en desarrollo.
   ===================================================================== */

IF SCHEMA_ID('cat') IS NULL EXEC('CREATE SCHEMA cat');
GO

/* Un activo por nodo del linaje. NODO_ID es el id que arma NB_CAT_01:
     lh:<esquema>.<tabla>       ej. lh:gold.fact_ventas
     modelo:<modelo>            ej. modelo:Ventas
     reporte:<reporte>          ej. reporte:Tablero comercial
   DUENO es un rol, un equipo o un grupo de seguridad, no una persona con su email:
   la gente cambia de puesto y el catálogo no tiene que guardar datos personales. */
IF OBJECT_ID('cat.ACTIVO') IS NULL
CREATE TABLE cat.ACTIVO (
    ACTIVO_ID           INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_CAT_ACTIVO PRIMARY KEY,
    NODO_ID             NVARCHAR(400)  NOT NULL CONSTRAINT UQ_CAT_ACTIVO_NODO UNIQUE,
    DUENO               NVARCHAR(200)  NOT NULL,      -- ej. 'Comercial - BI', 'grp-datos-ventas'
    AREA                NVARCHAR(100)  NULL,
    CRITICIDAD          VARCHAR(10)    NOT NULL CONSTRAINT DF_CAT_ACTIVO_CRIT DEFAULT ('MEDIA')
        CONSTRAINT CK_CAT_ACTIVO_CRIT CHECK (CRITICIDAD IN ('ALTA', 'MEDIA', 'BAJA')),
        -- ALTA: lo usa dirección o un proceso regulatorio; un cambio se avisa antes
    DESCRIPCION_NEGOCIO NVARCHAR(1000) NULL,
    IS_ACTIVE           BIT            NOT NULL CONSTRAINT DF_CAT_ACTIVO_ACTIVE DEFAULT (1),
    CREATED_AT          DATETIME2(0)   NOT NULL CONSTRAINT DF_CAT_ACTIVO_CREATED DEFAULT (SYSUTCDATETIME()),
    UPDATED_AT          DATETIME2(0)   NOT NULL CONSTRAINT DF_CAT_ACTIVO_UPDATED DEFAULT (SYSUTCDATETIME()),
    CONSTRAINT CK_CAT_ACTIVO_NODO CHECK (NODO_ID LIKE 'lh:%.%' OR NODO_ID LIKE 'modelo:%' OR NODO_ID LIKE 'reporte:%')
);
GO

/* Todo en una fila (columna FUENTES_JSON), para un Lookup con First row only.
   Incluye entidades y gold inactivos (con is_active) para detectar lo que todavía los lee. */
CREATE OR ALTER PROCEDURE cat.usp_GET_FUENTES
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @items NVARCHAR(MAX) = N'[]';

    -- El inventario es opcional: si no está instalado, la lista queda vacía
    IF OBJECT_ID('config.DOMAIN_OBJECTS') IS NOT NULL
        EXEC sp_executesql N'
            SET @items = ISNULL((
                SELECT OBJECT_NAME AS object_name, ARTIFACT_TYPE AS artifact_type,
                       FABRIC_ITEM_GUID AS fabric_item_guid, WORKSPACE_ID AS workspace_id,
                       CAST(ACTIVE_FLAG AS BIT) AS active_flag
                FROM config.DOMAIN_OBJECTS
                FOR JSON PATH), N''[]'');',
            N'@items NVARCHAR(MAX) OUTPUT', @items = @items OUTPUT;

    DECLARE @json NVARCHAR(MAX) = (
        SELECT
            (
                SELECT e.ENTITY_CODE AS entity_code, s.SOURCE_SYSTEM_CODE AS source_system_code,
                       s.SOURCE_TYPE AS source_type, e.SOURCE_OBJECT AS source_object,
                       s.CONNECTION_REF AS connection_ref, e.BRONZE_TABLE AS bronze_table,
                       e.SILVER_TABLE AS silver_table, e.SILVER_MODE AS silver_mode,
                       e.DELETE_MODE AS delete_mode, e.LOAD_GROUP AS load_group,
                       CAST(CASE WHEN e.IS_ACTIVE = 1 AND s.IS_ACTIVE = 1 THEN 1 ELSE 0 END AS BIT) AS is_active,
                       (
                           SELECT c.TARGET_COLUMN AS target_column, c.IS_PII AS is_pii
                           FROM meta.ENTITY_COLUMN c
                           WHERE c.ENTITY_ID = e.ENTITY_ID
                           ORDER BY c.ORDINAL
                           FOR JSON PATH
                       ) AS columns
                FROM meta.ENTITY e
                JOIN meta.SOURCE_SYSTEM s ON s.SOURCE_SYSTEM_ID = e.SOURCE_SYSTEM_ID
                ORDER BY e.ENTITY_CODE
                FOR JSON PATH, INCLUDE_NULL_VALUES
            ) AS entities,
            (
                SELECT g.GOLD_CODE AS gold_code, g.TARGET_TABLE AS target_table, g.LOAD_MODE AS load_mode,
                       g.SQL_TEXT AS sql_text, g.DEPENDS_ON_GOLD AS depends_on_gold,
                       g.LOAD_GROUP AS load_group, g.IS_ACTIVE AS is_active
                FROM meta.GOLD_OBJECT g
                ORDER BY g.GOLD_CODE
                FOR JSON PATH, INCLUDE_NULL_VALUES
            ) AS gold_objects,
            JSON_QUERY(@items) AS items,
            (
                SELECT a.NODO_ID AS nodo_id, a.DUENO AS dueno, a.AREA AS area, a.CRITICIDAD AS criticidad,
                       a.DESCRIPCION_NEGOCIO AS descripcion_negocio
                FROM cat.ACTIVO a
                WHERE a.IS_ACTIVE = 1
                ORDER BY a.NODO_ID
                FOR JSON PATH, INCLUDE_NULL_VALUES
            ) AS activos
        FOR JSON PATH, WITHOUT_ARRAY_WRAPPER, INCLUDE_NULL_VALUES
    );
    SELECT @json AS FUENTES_JSON;
END
GO

/* Permisos (ajustá el nombre de la identidad del pipeline):
-- El pipeline PL_CAT_LINAJE (o la identidad del workspace)
GRANT EXECUTE ON cat.usp_GET_FUENTES TO [<identidad-pipeline>];
-- Los dueños se cargan con scripts revisados (alta_activos.sql), no desde el pipeline
*/

-- ---------------------------------------------------------------------
-- Vuelta atrás: no toca tablas de otros casos. Para sacar el framework:
--   sacar el pipeline PL_CAT_LINAJE, después DROP PROCEDURE cat.usp_GET_FUENTES,
--   DROP TABLE cat.ACTIVO y DROP SCHEMA cat. Cambio con impacto: se pierden los
--   dueños cargados (exportá cat.ACTIVO antes). En el lakehouse: DROP de catalogo.*.
-- ---------------------------------------------------------------------
