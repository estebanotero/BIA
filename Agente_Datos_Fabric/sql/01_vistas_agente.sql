/* =====================================================================
   Vistas para el agente de datos (esquema agente)
   ---------------------------------------------------------------------
   Dónde se corre: en el SQL analytics endpoint del lakehouse de gold
                   (por ejemplo LH_MEDALLION), desde el editor de consultas
                   SQL de Fabric. Funciona igual en un Warehouse.
   Qué hace:       crea el esquema agente y vistas de solo lectura sobre
                   gold, con nombres de negocio y sin columnas PII.
   ¿Escribe datos? No. Solo crea o reemplaza vistas (metadatos).
   Vuelta atrás:   DROP VIEW agente.<vista>; DROP SCHEMA agente;

   Por qué vistas y no las tablas gold directo:
   - El agente elige tablas por nombre y descripción. Nombres claros
     (ventas, clientes) le dan mejores consultas que fact_ventas o dim_x.
   - Fijás la granularidad y las reglas de negocio (qué importe se usa,
     qué es "venta") en un solo lugar, en vez de repetirlas en las
     instrucciones.
   - Dejás afuera las columnas sensibles aunque alguien las agregue a gold.

   Está escrito sobre las tablas gold del ejemplo de
   Pipeline_Metadata_Medallion (gold.fact_ventas, gold.dim_cliente,
   gold.dim_producto). Adaptalo a tus tablas.
   T-SQL del SQL analytics endpoint de Fabric. Sin probar en Fabric real.
   ===================================================================== */

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'agente')
    EXEC('CREATE SCHEMA agente');
GO

/* ---------------------------------------------------------------------
   agente.ventas: una fila por línea de venta
   --------------------------------------------------------------------- */
CREATE OR ALTER VIEW agente.ventas
AS
SELECT
    f.venta_id,
    f.fecha                                   AS fecha_venta,
    DATEFROMPARTS(YEAR(f.fecha), MONTH(f.fecha), 1) AS mes_venta,
    f.cliente_id,
    c.razon_social                            AS cliente,
    c.provincia                               AS provincia_cliente,
    f.producto_id,
    p.descripcion                             AS producto,
    p.rubro,
    f.cantidad,
    f.moneda                                  AS moneda_original,
    f.importe_neto                            AS importe_neto_moneda_original,
    f.importe_ars                             AS importe_neto_ars  -- importe oficial para reportar
FROM gold.fact_ventas  AS f
LEFT JOIN gold.dim_cliente  AS c ON c.cliente_id  = f.cliente_id
LEFT JOIN gold.dim_producto AS p ON p.producto_id = f.producto_id;
GO

/* ---------------------------------------------------------------------
   agente.clientes: sin CUIT ni email (quedaron fuera de gold por PII)
   --------------------------------------------------------------------- */
CREATE OR ALTER VIEW agente.clientes
AS
SELECT cliente_id, razon_social AS cliente, provincia, fecha_alta
FROM gold.dim_cliente;
GO

/* ---------------------------------------------------------------------
   agente.productos
   --------------------------------------------------------------------- */
CREATE OR ALTER VIEW agente.productos
AS
SELECT producto_id, descripcion AS producto, rubro, precio_lista
FROM gold.dim_producto;
GO

/* ---------------------------------------------------------------------
   agente.ventas_mes_rubro: agregado mensual, para las preguntas más
   comunes. Evita que el agente recalcule sumas grandes en cada pregunta.
   --------------------------------------------------------------------- */
CREATE OR ALTER VIEW agente.ventas_mes_rubro
AS
SELECT
    DATEFROMPARTS(YEAR(f.fecha), MONTH(f.fecha), 1) AS mes_venta,
    p.rubro,
    COUNT(DISTINCT f.venta_id) AS cantidad_ventas,
    SUM(f.cantidad)            AS unidades,
    SUM(f.importe_ars)         AS importe_neto_ars
FROM gold.fact_ventas  AS f
JOIN gold.dim_producto AS p ON p.producto_id = f.producto_id
GROUP BY DATEFROMPARTS(YEAR(f.fecha), MONTH(f.fecha), 1), p.rubro;
GO

/* ---------------------------------------------------------------------
   Validación: las vistas devuelven filas y los totales cierran con gold
   --------------------------------------------------------------------- */
SELECT 'agente.ventas' AS vista, COUNT(*) AS filas, SUM(importe_neto_ars) AS total_ars FROM agente.ventas
UNION ALL
SELECT 'gold.fact_ventas', COUNT(*), SUM(importe_ars) FROM gold.fact_ventas;
-- Las dos filas tienen que dar lo mismo. Si agente.ventas da más filas,
-- hay claves duplicadas en una dimensión.

/* ---------------------------------------------------------------------
   Permisos (opcional). Con el agente, cada usuario consulta con su
   propia identidad: necesita Read sobre el lakehouse y SELECT sobre las
   vistas. Si querés que solo vea el esquema agente:
   --------------------------------------------------------------------- */
-- GRANT SELECT ON SCHEMA::agente TO [grupo-agente-ventas@tu-dominio];  -- [dato a confirmar]
