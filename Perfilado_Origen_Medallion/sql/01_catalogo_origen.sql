/* =====================================================================
   Perfilado de origen · Catálogo de un origen SQL Server / Azure SQL
   SOLO LECTURA: consulta vistas de sistema. No lee datos de las tablas.

   Devuelve una fila por columna con tipo, nulabilidad, PK, FK declarada,
   filas aproximadas y descripciones (extended property MS_Description).
   NB_PRF_01_perfilar lo usa para sumar al perfil lo que el origen declara.

   Cómo llevarlo a OneLake (cualquiera de las dos):
   - Una actividad Copy con la misma conexión de Fabric del origen,
     "Use query" = este script, destino Files/perfil/<origen>/catalogo/ en Parquet.
   - Correrlo en SSMS o Azure Data Studio, exportar a CSV con encabezado
     y subirlo a Files/perfil/<origen>/catalogo/catalogo.csv.

   Permisos: VIEW DEFINITION sobre los esquemas (para ver columnas, PK y FK) y
   VIEW DATABASE STATE (para FILAS_APROX). Sin el segundo, comentá el CTE filas.
   Requiere SQL Server 2017 o posterior (TRIM, STRING_SPLIT) o Azure SQL.
   No se ejecutó contra un SQL Server real: revisalo en desarrollo.
   ===================================================================== */

SET NOCOUNT ON;

-- Esquemas a incluir: vacío = todos menos los de sistema
DECLARE @ESQUEMAS NVARCHAR(400) = N'';   -- ej. N'dbo,ventas'

WITH pk AS (
    SELECT ic.object_id, ic.column_id, ic.key_ordinal
    FROM sys.indexes i
    JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    WHERE i.is_primary_key = 1
),
fk AS (
    -- Si una columna participa en más de una FK, se queda con la primera
    SELECT fkc.parent_object_id, fkc.parent_column_id,
           SCHEMA_NAME(rt.schema_id) AS FK_ESQUEMA_REF, rt.name AS FK_TABLA_REF, rc.name AS FK_COLUMNA_REF,
           ROW_NUMBER() OVER (PARTITION BY fkc.parent_object_id, fkc.parent_column_id ORDER BY fkc.constraint_object_id) AS rn
    FROM sys.foreign_key_columns fkc
    JOIN sys.tables  rt ON rt.object_id = fkc.referenced_object_id
    JOIN sys.columns rc ON rc.object_id = fkc.referenced_object_id AND rc.column_id = fkc.referenced_column_id
),
filas AS (
    SELECT object_id, SUM(row_count) AS FILAS_APROX
    FROM sys.dm_db_partition_stats
    WHERE index_id IN (0, 1)
    GROUP BY object_id
)
SELECT
    s.name                                   AS ESQUEMA,
    t.name                                   AS TABLA,
    c.name                                   AS COLUMNA,
    c.column_id                              AS ORDINAL,
    CASE
        WHEN ty.name IN ('varchar', 'char', 'varbinary', 'binary')
            THEN CONCAT(ty.name, '(', IIF(c.max_length = -1, 'max', CAST(c.max_length AS VARCHAR(10))), ')')
        WHEN ty.name IN ('nvarchar', 'nchar')
            THEN CONCAT(ty.name, '(', IIF(c.max_length = -1, 'max', CAST(c.max_length / 2 AS VARCHAR(10))), ')')
        WHEN ty.name IN ('decimal', 'numeric')
            THEN CONCAT(ty.name, '(', c.precision, ',', c.scale, ')')
        ELSE ty.name
    END                                      AS TIPO,
    CAST(c.is_nullable AS INT)               AS ADMITE_NULOS,
    CAST(c.is_identity AS INT)               AS ES_IDENTITY,
    IIF(pk.column_id IS NULL, 0, 1)          AS ES_PK,
    pk.key_ordinal                           AS PK_ORDINAL,
    fk.FK_ESQUEMA_REF,
    fk.FK_TABLA_REF,
    fk.FK_COLUMNA_REF,
    f.FILAS_APROX,
    CAST(ept.value AS NVARCHAR(1000))        AS DESCRIPCION_TABLA,
    CAST(epc.value AS NVARCHAR(1000))        AS DESCRIPCION_COLUMNA
FROM sys.tables t
JOIN sys.schemas s  ON s.schema_id = t.schema_id
JOIN sys.columns c  ON c.object_id = t.object_id
JOIN sys.types   ty ON ty.user_type_id = c.user_type_id
LEFT JOIN pk        ON pk.object_id = c.object_id AND pk.column_id = c.column_id
LEFT JOIN fk        ON fk.parent_object_id = c.object_id AND fk.parent_column_id = c.column_id AND fk.rn = 1
LEFT JOIN filas f   ON f.object_id = t.object_id
LEFT JOIN sys.extended_properties ept
       ON ept.major_id = t.object_id AND ept.minor_id = 0 AND ept.class = 1 AND ept.name = 'MS_Description'
LEFT JOIN sys.extended_properties epc
       ON epc.major_id = c.object_id AND epc.minor_id = c.column_id AND epc.class = 1 AND epc.name = 'MS_Description'
WHERE t.is_ms_shipped = 0
  AND s.name NOT IN ('sys', 'INFORMATION_SCHEMA')
  AND (@ESQUEMAS = N'' OR s.name IN (SELECT TRIM(value) FROM STRING_SPLIT(@ESQUEMAS, ',')))
ORDER BY s.name, t.name, c.column_id;
