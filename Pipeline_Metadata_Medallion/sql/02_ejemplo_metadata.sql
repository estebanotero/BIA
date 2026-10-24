/* =====================================================================
   Pipeline metadata-driven medallion · Metadata de ejemplo
   Un ERP en SQL Server (clientes, productos, ventas) y una carpeta de
   archivos CSV ya en OneLake (cotizaciones). Reemplazá los nombres por los
   de tu origen, o pedile a Claude que lo genere con la skill metadata-medallion.

   Es idempotente: actualiza si el código ya existe, inserta si no.
   No guarda credenciales: CONNECTION_REF es el nombre de la conexión de Fabric.
   ===================================================================== */

SET XACT_ABORT ON;
BEGIN TRAN;

-- ---------------------------------------------------------------------
-- 1. Sistemas de origen
-- ---------------------------------------------------------------------
MERGE meta.SOURCE_SYSTEM AS t
USING (VALUES
    ('erp',          'SQL',   N'<nombre-de-la-conexion-fabric-al-erp>', N'ERP comercial (SQL Server vía gateway)'),
    ('cotizaciones', 'FILES', NULL,                                     N'CSV diarios de cotizaciones en un shortcut de OneLake')
) AS s (SOURCE_SYSTEM_CODE, SOURCE_TYPE, CONNECTION_REF, DESCRIPTION)
ON t.SOURCE_SYSTEM_CODE = s.SOURCE_SYSTEM_CODE
WHEN MATCHED THEN UPDATE SET SOURCE_TYPE = s.SOURCE_TYPE, CONNECTION_REF = s.CONNECTION_REF,
                             DESCRIPTION = s.DESCRIPTION, UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (SOURCE_SYSTEM_CODE, SOURCE_TYPE, CONNECTION_REF, DESCRIPTION)
                      VALUES (s.SOURCE_SYSTEM_CODE, s.SOURCE_TYPE, s.CONNECTION_REF, s.DESCRIPTION);

-- ---------------------------------------------------------------------
-- 2. Entidades
-- ---------------------------------------------------------------------
MERGE meta.ENTITY AS t
USING (
    SELECT ss.SOURCE_SYSTEM_ID, v.*
    FROM (VALUES
        -- SOURCE_SYSTEM_CODE, ENTITY_CODE, SOURCE_OBJECT, SOURCE_FILTER, FILE_FORMAT, LOAD_TYPE,
        -- WATERMARK_COLUMN, WATERMARK_TYPE, PRIMARY_KEY, ORDER_COLUMN, BRONZE_TABLE, SILVER_TABLE, SILVER_MODE
        ('erp', 'erp_clientes',  N'dbo.Clientes',  NULL,                N'parquet', 'INCREMENTAL',
         N'FechaModificacion', 'DATETIME', N'cliente_id',  N'fecha_modificacion', N'bronze.erp_clientes',  N'silver.clientes',  'MERGE'),
        ('erp', 'erp_productos', N'dbo.Productos', NULL,                N'parquet', 'FULL',
         NULL,                 NULL,       N'producto_id', NULL,                  N'bronze.erp_productos', N'silver.productos', 'MERGE'),
        ('erp', 'erp_ventas',    N'dbo.Ventas',    N'Anulada = 0',      N'parquet', 'INCREMENTAL',
         N'VentaID',           'INT',      N'venta_id',    NULL,                  N'bronze.erp_ventas',    N'silver.ventas',    'MERGE'),
        ('cotizaciones', 'cot_dolar', N'Files/shortcuts/cotizaciones/dolar', NULL, N'csv', 'INCREMENTAL',
         NULL,                 'DATETIME', N'fecha',       NULL,                  N'bronze.cot_dolar',     N'silver.cotizacion_dolar', 'MERGE')
    ) AS v (SOURCE_SYSTEM_CODE, ENTITY_CODE, SOURCE_OBJECT, SOURCE_FILTER, FILE_FORMAT, LOAD_TYPE,
            WATERMARK_COLUMN, WATERMARK_TYPE, PRIMARY_KEY, ORDER_COLUMN, BRONZE_TABLE, SILVER_TABLE, SILVER_MODE)
    JOIN meta.SOURCE_SYSTEM ss ON ss.SOURCE_SYSTEM_CODE = v.SOURCE_SYSTEM_CODE
) AS s
ON t.ENTITY_CODE = s.ENTITY_CODE
WHEN MATCHED THEN UPDATE SET
    SOURCE_SYSTEM_ID = s.SOURCE_SYSTEM_ID, SOURCE_OBJECT = s.SOURCE_OBJECT, SOURCE_FILTER = s.SOURCE_FILTER,
    FILE_FORMAT = s.FILE_FORMAT, LOAD_TYPE = s.LOAD_TYPE, WATERMARK_COLUMN = s.WATERMARK_COLUMN,
    WATERMARK_TYPE = s.WATERMARK_TYPE, PRIMARY_KEY = s.PRIMARY_KEY, ORDER_COLUMN = s.ORDER_COLUMN,
    BRONZE_TABLE = s.BRONZE_TABLE, SILVER_TABLE = s.SILVER_TABLE, SILVER_MODE = s.SILVER_MODE,
    UPDATED_AT = SYSUTCDATETIME()
    -- WATERMARK_VALUE no se toca: es el estado de carga
WHEN NOT MATCHED THEN INSERT
    (SOURCE_SYSTEM_ID, ENTITY_CODE, SOURCE_OBJECT, SOURCE_FILTER, FILE_FORMAT, LOAD_TYPE, WATERMARK_COLUMN,
     WATERMARK_TYPE, PRIMARY_KEY, ORDER_COLUMN, BRONZE_TABLE, SILVER_TABLE, SILVER_MODE)
    VALUES
    (s.SOURCE_SYSTEM_ID, s.ENTITY_CODE, s.SOURCE_OBJECT, s.SOURCE_FILTER, s.FILE_FORMAT, s.LOAD_TYPE, s.WATERMARK_COLUMN,
     s.WATERMARK_TYPE, s.PRIMARY_KEY, s.ORDER_COLUMN, s.BRONZE_TABLE, s.SILVER_TABLE, s.SILVER_MODE);

-- ---------------------------------------------------------------------
-- 3. Columnas de silver (se reemplazan completas por entidad)
--    Bronze guarda los nombres del origen; silver los pasa a snake_case y tipa.
-- ---------------------------------------------------------------------
DELETE c FROM meta.ENTITY_COLUMN c
JOIN meta.ENTITY e ON e.ENTITY_ID = c.ENTITY_ID
WHERE e.ENTITY_CODE IN ('erp_clientes', 'erp_productos', 'erp_ventas', 'cot_dolar');

INSERT meta.ENTITY_COLUMN (ENTITY_ID, ORDINAL, SOURCE_COLUMN, TARGET_COLUMN, TARGET_TYPE, TRANSFORM_EXPR, IS_PII)
SELECT e.ENTITY_ID, v.ORDINAL, v.SOURCE_COLUMN, v.TARGET_COLUMN, v.TARGET_TYPE, v.TRANSFORM_EXPR, v.IS_PII
FROM (VALUES
    ('erp_clientes', 1, N'ClienteID',          N'cliente_id',         'int',           NULL,                                 0),
    ('erp_clientes', 2, N'RazonSocial',        N'razon_social',       'string',        N'trim(RazonSocial)',                 0),
    ('erp_clientes', 3, N'CUIT',               N'cuit',               'string',        N'regexp_replace(CUIT, ''[^0-9]'', '''')', 1),
    ('erp_clientes', 4, N'Email',              N'email',              'string',        N'lower(trim(Email))',                1),
    ('erp_clientes', 5, N'Provincia',          N'provincia',          'string',        N'initcap(trim(Provincia))',          0),
    ('erp_clientes', 6, N'FechaAlta',          N'fecha_alta',         'date',          NULL,                                 0),
    ('erp_clientes', 7, N'FechaModificacion',  N'fecha_modificacion', 'timestamp',     NULL,                                 0),

    ('erp_productos', 1, N'ProductoID',        N'producto_id',        'int',           NULL,                                 0),
    ('erp_productos', 2, N'Descripcion',       N'descripcion',        'string',        N'trim(Descripcion)',                 0),
    ('erp_productos', 3, N'Rubro',             N'rubro',              'string',        NULL,                                 0),
    ('erp_productos', 4, N'PrecioLista',       N'precio_lista',       'decimal(18,2)', NULL,                                 0),

    ('erp_ventas', 1, N'VentaID',              N'venta_id',           'bigint',        NULL,                                 0),
    ('erp_ventas', 2, N'Fecha',                N'fecha',              'date',          NULL,                                 0),
    ('erp_ventas', 3, N'ClienteID',            N'cliente_id',         'int',           NULL,                                 0),
    ('erp_ventas', 4, N'ProductoID',           N'producto_id',        'int',           NULL,                                 0),
    ('erp_ventas', 5, N'Cantidad',             N'cantidad',           'decimal(18,4)', NULL,                                 0),
    ('erp_ventas', 6, N'ImporteNeto',          N'importe_neto',       'decimal(18,2)', NULL,                                 0),
    ('erp_ventas', 7, N'Moneda',               N'moneda',             'string',        N'upper(coalesce(Moneda, ''ARS''))', 0),

    ('cot_dolar', 1, N'fecha',                 N'fecha',              'date',          N'to_date(fecha, ''dd/MM/yyyy'')',    0),
    ('cot_dolar', 2, N'tipo',                  N'tipo',               'string',        N'lower(tipo)',                       0),
    ('cot_dolar', 3, N'compra',                N'compra',             'decimal(18,4)', NULL,                                 0),
    ('cot_dolar', 4, N'venta',                 N'venta',              'decimal(18,4)', NULL,                                 0)
) AS v (ENTITY_CODE, ORDINAL, SOURCE_COLUMN, TARGET_COLUMN, TARGET_TYPE, TRANSFORM_EXPR, IS_PII)
JOIN meta.ENTITY e ON e.ENTITY_CODE = v.ENTITY_CODE;

-- La cotización tiene una fila por fecha y tipo: clave compuesta
UPDATE meta.ENTITY SET PRIMARY_KEY = N'fecha,tipo' WHERE ENTITY_CODE = 'cot_dolar';

-- ---------------------------------------------------------------------
-- 4. Reglas de calidad
-- ---------------------------------------------------------------------
DELETE r FROM meta.DQ_RULE r
JOIN meta.ENTITY e ON e.ENTITY_ID = r.ENTITY_ID
WHERE e.ENTITY_CODE IN ('erp_clientes', 'erp_productos', 'erp_ventas', 'cot_dolar');

INSERT meta.DQ_RULE (ENTITY_ID, RULE_NAME, RULE_EXPR, ACTION)
SELECT e.ENTITY_ID, v.RULE_NAME, v.RULE_EXPR, v.ACTION
FROM (VALUES
    ('erp_clientes',  'cliente_id_no_nulo',   N'cliente_id IS NOT NULL',                 'FAIL'),
    ('erp_clientes',  'cuit_11_digitos',      N'cuit IS NULL OR length(cuit) = 11',      'WARN'),
    ('erp_productos', 'precio_no_negativo',   N'precio_lista >= 0',                      'DROP'),
    ('erp_ventas',    'venta_id_no_nulo',     N'venta_id IS NOT NULL',                   'FAIL'),
    ('erp_ventas',    'cantidad_positiva',    N'cantidad > 0',                           'DROP'),
    ('erp_ventas',    'fecha_razonable',      N'fecha BETWEEN DATE''2000-01-01'' AND current_date()', 'DROP'),
    ('cot_dolar',     'fecha_valida',         N'fecha IS NOT NULL',                      'DROP'),
    ('cot_dolar',     'venta_mayor_compra',   N'venta >= compra',                        'WARN')
) AS v (ENTITY_CODE, RULE_NAME, RULE_EXPR, ACTION)
JOIN meta.ENTITY e ON e.ENTITY_CODE = v.ENTITY_CODE;

-- ---------------------------------------------------------------------
-- 5. Gold
-- ---------------------------------------------------------------------
MERGE meta.GOLD_OBJECT AS t
USING (VALUES
    ('dim_cliente', N'gold.dim_cliente', 'OVERWRITE', NULL, NULL,
     N'SELECT cliente_id, razon_social, provincia, fecha_alta
       FROM silver.clientes'),
       -- cuit y email quedan fuera de gold: son PII y el modelo semántico no los necesita

    ('dim_producto', N'gold.dim_producto', 'OVERWRITE', NULL, NULL,
     N'SELECT producto_id, descripcion, rubro, precio_lista
       FROM silver.productos'),

    ('fact_ventas', N'gold.fact_ventas', 'MERGE', N'venta_id', N'dim_cliente,dim_producto',
     N'SELECT v.venta_id, v.fecha, v.cliente_id, v.producto_id, v.cantidad, v.importe_neto, v.moneda,
              CASE WHEN v.moneda = ''USD'' THEN v.importe_neto * c.venta ELSE v.importe_neto END AS importe_ars
       FROM silver.ventas v
       LEFT JOIN silver.cotizacion_dolar c
              ON c.fecha = v.fecha AND c.tipo = ''oficial'''),

    -- Ejemplo de gold como materialized lake view: Fabric la refresca según su programación de lineage
    ('agg_ventas_mes', N'gold.agg_ventas_mes', 'MLV', NULL, N'fact_ventas',
     N'CREATE MATERIALIZED LAKE VIEW IF NOT EXISTS gold.agg_ventas_mes
       COMMENT "Ventas netas en pesos por mes y rubro"
       AS SELECT date_trunc(''month'', f.fecha) AS mes, p.rubro, SUM(f.importe_ars) AS importe_ars
          FROM gold.fact_ventas f
          JOIN gold.dim_producto p ON p.producto_id = f.producto_id
          GROUP BY date_trunc(''month'', f.fecha), p.rubro')
) AS s (GOLD_CODE, TARGET_TABLE, LOAD_MODE, MERGE_KEY, DEPENDS_ON_GOLD, SQL_TEXT)
ON t.GOLD_CODE = s.GOLD_CODE
WHEN MATCHED THEN UPDATE SET TARGET_TABLE = s.TARGET_TABLE, LOAD_MODE = s.LOAD_MODE, MERGE_KEY = s.MERGE_KEY,
                             DEPENDS_ON_GOLD = s.DEPENDS_ON_GOLD, SQL_TEXT = s.SQL_TEXT, UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (GOLD_CODE, TARGET_TABLE, LOAD_MODE, MERGE_KEY, DEPENDS_ON_GOLD, SQL_TEXT)
                      VALUES (s.GOLD_CODE, s.TARGET_TABLE, s.LOAD_MODE, s.MERGE_KEY, s.DEPENDS_ON_GOLD, s.SQL_TEXT);

COMMIT;

-- Si devuelve filas, corregí antes de correr el pipeline
EXEC meta.usp_VALIDATE_METADATA;
