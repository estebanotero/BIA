/* =====================================================================
   Dueños de activos del catálogo · <plataforma o área> · <AAAA-MM-DD>
   Generado con la skill explorar-linaje. Revisalo antes de correrlo.

   DUENO es un rol, un equipo o un grupo de seguridad, nunca el email de una persona.
   [dato a confirmar]:
   - <activo>: <pregunta pendiente>

   Correr primero en desarrollo. Es idempotente: actualiza si el NODO_ID ya existe.
   ===================================================================== */

SET XACT_ABORT ON;
BEGIN TRAN;

MERGE cat.ACTIVO AS t
USING (VALUES
    -- NODO_ID tal como aparece en catalogo.nodo
    (N'lh:gold.fact_ventas',      N'Comercial - BI', N'Comercial', 'ALTA',
     N'Una fila por venta neta, en pesos. Base del tablero comercial y del cierre mensual'),
    (N'lh:gold.dim_cliente',      N'Comercial - BI', N'Comercial', 'MEDIA',
     N'Un cliente por fila, con su provincia actual'),
    (N'modelo:Ventas',            N'Comercial - BI', N'Comercial', 'ALTA',
     N'Modelo semántico de ventas que usan dirección y los equipos comerciales'),
    (N'reporte:Tablero comercial', N'<dato a confirmar>', N'Comercial', 'ALTA', NULL)
) AS s (NODO_ID, DUENO, AREA, CRITICIDAD, DESCRIPCION_NEGOCIO)
ON t.NODO_ID = s.NODO_ID
WHEN MATCHED THEN UPDATE SET DUENO = s.DUENO, AREA = s.AREA, CRITICIDAD = s.CRITICIDAD,
                             DESCRIPCION_NEGOCIO = s.DESCRIPCION_NEGOCIO, IS_ACTIVE = 1,
                             UPDATED_AT = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (NODO_ID, DUENO, AREA, CRITICIDAD, DESCRIPCION_NEGOCIO)
                      VALUES (s.NODO_ID, s.DUENO, s.AREA, s.CRITICIDAD, s.DESCRIPCION_NEGOCIO);

COMMIT;

-- Lo que quedó cargado
SELECT NODO_ID, DUENO, AREA, CRITICIDAD FROM cat.ACTIVO WHERE IS_ACTIVE = 1 ORDER BY CRITICIDAD, NODO_ID;
