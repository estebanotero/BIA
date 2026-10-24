/* =====================================================================
   Pipeline metadata-driven medallion · Historia (SCD2) y bajas del origen
   Se corre DESPUÉS de 02_ejemplo_metadata.sql, sobre el mismo modelo de ejemplo:

   - erp_clientes:  SCD2. Abre versión nueva si cambia razon_social o provincia;
                    cuit y email (PII) se actualizan en la versión vigente y no
                    quedan en las versiones cerradas.
   - erp_productos: carga FULL con bajas por ausencia (DELETE_MODE = ABSENT), con
                    freno del 10 %: si falta más, silver falla en vez de marcar.
   - erp_ventas:    deja de filtrar Anulada en el origen. La columna llega a silver
                    y marca la baja (DELETE_MODE = FLAG): una venta anulada después
                    de cargada sale de gold, cosa que el SOURCE_FILTER no lograba.
   - gold:          dim_cliente (última versión de cada cliente), dim_cliente_historia
                    (una fila por versión, con clave sustituta) y fact_ventas cruzando
                    la versión vigente en la fecha de la venta.

   Cambio con impacto: silver.clientes pasa a tener varias filas por cliente.
   La primera corrida la convierte sola (cada fila queda como su primera versión).
   Todo lo que lea silver.clientes directo tiene que filtrar _is_current o
   usar gold. Para volver atrás: correr de nuevo 02_ejemplo_metadata.sql y recargar
   silver.clientes con OVERWRITE una vez (ver README, sección 10).
   Es idempotente. Correlo primero en desarrollo.
   ===================================================================== */

SET XACT_ABORT ON;
BEGIN TRAN;

-- ---------------------------------------------------------------------
-- 1. Entidades
-- ---------------------------------------------------------------------
UPDATE meta.ENTITY
SET SILVER_MODE = 'SCD2', SCD2_COLUMNS = N'razon_social,provincia', DELETE_MODE = 'NONE',
    UPDATED_AT = SYSUTCDATETIME()
WHERE ENTITY_CODE = 'erp_clientes';

UPDATE meta.ENTITY
SET DELETE_MODE = 'ABSENT', DELETE_MAX_PCT = 10, UPDATED_AT = SYSUTCDATETIME()   -- 10 %: [dato a confirmar] con el dueño
WHERE ENTITY_CODE = 'erp_productos';

UPDATE meta.ENTITY
SET SOURCE_FILTER = NULL, DELETE_MODE = 'FLAG', DELETE_FLAG_EXPR = N'anulada = true',
    UPDATED_AT = SYSUTCDATETIME()
WHERE ENTITY_CODE = 'erp_ventas';

DELETE c FROM meta.ENTITY_COLUMN c
JOIN meta.ENTITY e ON e.ENTITY_ID = c.ENTITY_ID
WHERE e.ENTITY_CODE = 'erp_ventas' AND c.TARGET_COLUMN = 'anulada';

INSERT meta.ENTITY_COLUMN (ENTITY_ID, ORDINAL, SOURCE_COLUMN, TARGET_COLUMN, TARGET_TYPE, TRANSFORM_EXPR, IS_PII)
SELECT e.ENTITY_ID, 8, N'Anulada', N'anulada', 'boolean', NULL, 0
FROM meta.ENTITY e WHERE e.ENTITY_CODE = 'erp_ventas';

/* Ojo con el watermark de erp_ventas (INT por VentaID): una venta que se anula después
   no cambia su VentaID, así que la incremental no la vuelve a traer. Para que la
   anulación llegue, el watermark tiene que ser una fecha de modificación, o la
   entidad pasar a FULL. [dato a confirmar] qué columna tiene el ERP. */

-- ---------------------------------------------------------------------
-- 2. Gold
-- ---------------------------------------------------------------------
MERGE meta.GOLD_OBJECT AS t
USING (VALUES
    -- Una fila por cliente: su última versión. Sigue sirviendo a las relaciones del modelo semántico
    -- y a las reglas de calidad que cruzan por cliente_id
    ('dim_cliente', N'gold.dim_cliente', 'OVERWRITE', NULL, NULL,
     N'SELECT cliente_id, razon_social, provincia, fecha_alta, NOT _is_current AS dado_de_baja
       FROM (SELECT *, row_number() OVER (PARTITION BY cliente_id ORDER BY _valid_from DESC) AS rn
             FROM silver.clientes)
       WHERE rn = 1'),

    -- Una fila por versión, para analizar "cómo era el cliente cuando compró"
    ('dim_cliente_historia', N'gold.dim_cliente_historia', 'OVERWRITE', NULL, NULL,
     N'SELECT xxhash64(cliente_id, _valid_from) AS cliente_sk, cliente_id, razon_social, provincia,
              _valid_from AS vigente_desde, _valid_to AS vigente_hasta, _is_current AS es_actual
       FROM silver.clientes'),

    -- Los productos dados de baja siguen en la dimensión: hay ventas viejas que los usan.
    -- Se renombra la columna: si se llamara _is_deleted, gold los sacaría
    ('dim_producto', N'gold.dim_producto', 'OVERWRITE', NULL, NULL,
     N'SELECT producto_id, descripcion, rubro, precio_lista, coalesce(_is_deleted, false) AS discontinuado
       FROM silver.productos'),

    -- _is_deleted en el SELECT: el MERGE de gold borra las ventas anuladas
    ('fact_ventas', N'gold.fact_ventas', 'MERGE', N'venta_id', N'dim_cliente,dim_cliente_historia,dim_producto',
     N'SELECT v.venta_id, v.fecha, v.cliente_id, h.cliente_sk, v.producto_id, v.cantidad, v.importe_neto, v.moneda,
              CASE WHEN v.moneda = ''USD'' THEN v.importe_neto * c.venta ELSE v.importe_neto END AS importe_ars,
              v._is_deleted
       FROM silver.ventas v
       LEFT JOIN gold.dim_cliente_historia h
              ON h.cliente_id = v.cliente_id
             AND CAST(v.fecha AS TIMESTAMP) >= h.vigente_desde
             AND CAST(v.fecha AS TIMESTAMP) <  h.vigente_hasta
       LEFT JOIN silver.cotizacion_dolar c
              ON c.fecha = v.fecha AND c.tipo = ''oficial''')
) AS s (GOLD_CODE, TARGET_TABLE, LOAD_MODE, MERGE_KEY, DEPENDS_ON_GOLD, SQL_TEXT)
ON t.GOLD_CODE = s.GOLD_CODE
WHEN MATCHED THEN UPDATE SET TARGET_TABLE = s.TARGET_TABLE, LOAD_MODE = s.LOAD_MODE, MERGE_KEY = s.MERGE_KEY,
                             DEPENDS_ON_GOLD = s.DEPENDS_ON_GOLD, SQL_TEXT = s.SQL_TEXT, UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (GOLD_CODE, TARGET_TABLE, LOAD_MODE, MERGE_KEY, DEPENDS_ON_GOLD, SQL_TEXT)
                      VALUES (s.GOLD_CODE, s.TARGET_TABLE, s.LOAD_MODE, s.MERGE_KEY, s.DEPENDS_ON_GOLD, s.SQL_TEXT);

COMMIT;

/* Si usás Calidad_Reconciliacion: la regla cuadre_ventas_silver_gold cuenta silver.ventas
   entero, y ahora silver tiene las anuladas que gold no. Agregá el mismo filtro del lado
   silver (SQL_A), por script revisado:
     ... FROM silver.ventas WHERE NOT coalesce(_is_deleted, false) GROUP BY ...
   Las reglas que cruzan con dim_cliente siguen igual: tiene una fila por cliente. */

-- Si devuelve filas, corregí antes de correr el pipeline
EXEC meta.usp_VALIDATE_METADATA;
