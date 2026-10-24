/* =====================================================================
   Alta o cambio de reglas de calidad y reconciliación (dq.REGLA)
   Grupo de carga: <LOAD_GROUP>  ·  Pedido por: <persona>  ·  Fecha: <AAAA-MM-DD>
   Generado con la skill proponer-reglas-calidad. Revisalo antes de correrlo.

   Los ejemplos son del modelo de ejemplo de Pipeline_Metadata_Medallion
   (silver.ventas, gold.fact_ventas, gold.dim_cliente, gold.dim_producto).

   Decisiones:
   - <regla>: <por qué esta tolerancia y esta severidad>
   [dato a confirmar]:
   - <pregunta pendiente>

   Idempotente: MERGE por REGLA_CODE. No toca dq.RESULTADO.
   Para dar de baja una regla: IS_ACTIVE = 0 (no borres la fila: perdés su historia).
   Correr primero en desarrollo y probar con NB_CAL_01 a mano.
   ===================================================================== */

SET XACT_ABORT ON;
BEGIN TRAN;

MERGE dq.REGLA AS t
USING (VALUES
    -- Cuadre silver → gold por mes: filas e importe. Gold es un MERGE de silver, así que tiene que dar exacto
    ('cuadre_ventas_silver_gold', N'Ventas: silver y gold tienen las mismas filas e importe por mes', 'default', 'CUADRE', 'COMPARA',
     N'SELECT date_format(fecha, ''yyyy-MM'') AS mes, COUNT(*) AS filas, SUM(importe_neto) AS importe_neto
       FROM silver.ventas GROUP BY date_format(fecha, ''yyyy-MM'')',
     N'SELECT date_format(fecha, ''yyyy-MM'') AS mes, COUNT(*) AS filas, SUM(importe_neto) AS importe_neto
       FROM gold.fact_ventas GROUP BY date_format(fecha, ''yyyy-MM'')',
     N'mes', NULL, 0, 0, NULL, NULL, 'ERROR', N'<área de ventas>'),

    -- Integridad: hechos sin dimensión. En el modelo semántico caen en "(en blanco)"
    ('ventas_sin_cliente', N'Ventas cuyo cliente no está en dim_cliente', 'default', 'INTEGRIDAD', 'CONDICION',
     N'SELECT COUNT(*) AS ventas_sin_cliente
       FROM gold.fact_ventas f LEFT ANTI JOIN gold.dim_cliente d ON d.cliente_id = f.cliente_id',
     NULL, NULL, NULL, 0, 0, 0, 0, 'ERROR', N'<área de ventas>'),

    ('ventas_sin_producto', N'Ventas cuyo producto no está en dim_producto', 'default', 'INTEGRIDAD', 'CONDICION',
     N'SELECT COUNT(*) AS ventas_sin_producto
       FROM gold.fact_ventas f LEFT ANTI JOIN gold.dim_producto d ON d.producto_id = f.producto_id',
     NULL, NULL, NULL, 0, 0, 0, 0, 'ERROR', N'<área de ventas>'),

    -- Frescura: horas desde la última venta. 48 h tolera un fin de semana corto [dato a confirmar]
    ('frescura_ventas', N'Horas desde la última venta cargada en gold', 'default', 'FRESCURA', 'CONDICION',
     N'SELECT (unix_timestamp(current_timestamp()) - unix_timestamp(CAST(MAX(fecha) AS TIMESTAMP))) / 3600 AS horas
       FROM gold.fact_ventas',
     NULL, NULL, NULL, 0, 0, NULL, 48, 'WARN', N'<área de ventas>'),

    -- Bronze → silver: claves que llegaron y no están en silver. Incluye las rechazadas por reglas DROP:
    -- si la entidad tiene reglas DROP, revisá silver.dq_rechazos antes de subir el umbral
    ('claves_ventas_bronze_silver', N'Ventas que llegaron a bronze y no están en silver', 'default', 'CUADRE', 'CONDICION',
     N'SELECT COUNT(*) AS claves_perdidas
       FROM (SELECT DISTINCT CAST(VentaID AS BIGINT) AS venta_id FROM bronze.erp_ventas) b
       LEFT ANTI JOIN silver.ventas s ON s.venta_id = b.venta_id',
     NULL, NULL, NULL, 0, 0, 0, 0, 'WARN', N'<área de ventas>')
) AS s (REGLA_CODE, DESCRIPCION, LOAD_GROUP, CATEGORIA, TIPO, SQL_A, SQL_B, CLAVE, METRICAS,
        TOLERANCIA_ABS, TOLERANCIA_PCT, VALOR_MIN, VALOR_MAX, SEVERIDAD, DUENO)
ON t.REGLA_CODE = s.REGLA_CODE
WHEN MATCHED THEN UPDATE SET
    DESCRIPCION = s.DESCRIPCION, LOAD_GROUP = s.LOAD_GROUP, CATEGORIA = s.CATEGORIA, TIPO = s.TIPO,
    SQL_A = s.SQL_A, SQL_B = s.SQL_B, CLAVE = s.CLAVE, METRICAS = s.METRICAS,
    TOLERANCIA_ABS = s.TOLERANCIA_ABS, TOLERANCIA_PCT = s.TOLERANCIA_PCT,
    VALOR_MIN = s.VALOR_MIN, VALOR_MAX = s.VALOR_MAX, SEVERIDAD = s.SEVERIDAD, DUENO = s.DUENO,
    IS_ACTIVE = 1, UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (REGLA_CODE, DESCRIPCION, LOAD_GROUP, CATEGORIA, TIPO, SQL_A, SQL_B, CLAVE, METRICAS,
                              TOLERANCIA_ABS, TOLERANCIA_PCT, VALOR_MIN, VALOR_MAX, SEVERIDAD, DUENO)
                      VALUES (s.REGLA_CODE, s.DESCRIPCION, s.LOAD_GROUP, s.CATEGORIA, s.TIPO, s.SQL_A, s.SQL_B, s.CLAVE, s.METRICAS,
                              s.TOLERANCIA_ABS, s.TOLERANCIA_PCT, s.VALOR_MIN, s.VALOR_MAX, s.SEVERIDAD, s.DUENO);

COMMIT;

-- Ver cómo quedó lo que va a recibir el notebook:
-- EXEC dq.usp_GET_REGLAS @LOAD_GROUP = 'default';
