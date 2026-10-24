-- =====================================================================
-- Perfilado de origen · Consultas sobre el esquema perfil (Spark SQL)
-- Correlas en un notebook (%%sql) o en el SQL analytics endpoint del lakehouse.
-- Solo lectura. Reemplazá 'erp' por tu origen.
-- =====================================================================

-- 1. Corridas de perfil de un origen, la más nueva primero
SELECT corrida_id, inicio, fin, tablas, parametros
FROM perfil.corrida
WHERE origen = 'erp'
ORDER BY inicio DESC;

-- 2. Resumen por tabla de la última corrida: clave preferida, PII y columnas con notas
WITH ult AS (SELECT max(corrida_id) AS corrida_id FROM perfil.corrida WHERE origen = 'erp')
SELECT t.tabla, t.tabla_origen, t.filas, t.columnas, t.columnas_pii,
       k.columnas AS clave_preferida, k.tipo AS tipo_clave,
       sum(CASE WHEN c.notas IS NOT NULL THEN 1 ELSE 0 END) AS columnas_con_notas
FROM perfil.tabla t
JOIN ult ON ult.corrida_id = t.corrida_id
LEFT JOIN perfil.clave_candidata k
       ON k.corrida_id = t.corrida_id AND k.tabla = t.tabla AND k.preferida
LEFT JOIN perfil.columna c ON c.corrida_id = t.corrida_id AND c.tabla = t.tabla
WHERE t.origen = 'erp'
GROUP BY t.tabla, t.tabla_origen, t.filas, t.columnas, t.columnas_pii, k.columnas, k.tipo
ORDER BY t.tabla;

-- 3. Inventario de PII sugerida (para gobierno y para revisar IS_PII)
SELECT c.tabla, c.columna, c.pii_motivo, c.tipo_sugerido
FROM perfil.columna c
WHERE c.corrida_id = (SELECT max(corrida_id) FROM perfil.corrida WHERE origen = 'erp')
  AND c.pii
ORDER BY c.tabla, c.ordinal;

-- 4. Relaciones con huérfanos: van a gold con LEFT JOIN y miembro "desconocido"
SELECT tabla_hijo, columna_hijo, tabla_padre, columna_padre, estado, inclusion,
       filas_huerfanas, ejemplos_huerfanos
FROM perfil.relacion
WHERE corrida_id = (SELECT max(corrida_id) FROM perfil.corrida WHERE origen = 'erp')
  AND valores_huerfanos > 0 AND estado <> 'descartada'
ORDER BY filas_huerfanas DESC;

-- 5. Cambios entre las dos últimas corridas (drift del origen):
--    columnas nuevas o que desaparecieron, cambio de tipo y saltos de nulos de más de 5 puntos
WITH corr AS (
    SELECT corrida_id, row_number() OVER (ORDER BY inicio DESC) AS n
    FROM perfil.corrida WHERE origen = 'erp'
),
act AS (SELECT c.* FROM perfil.columna c JOIN corr ON corr.corrida_id = c.corrida_id AND corr.n = 1),
ant AS (SELECT c.* FROM perfil.columna c JOIN corr ON corr.corrida_id = c.corrida_id AND corr.n = 2)
SELECT coalesce(act.tabla, ant.tabla) AS tabla, coalesce(act.columna, ant.columna) AS columna,
       CASE WHEN ant.columna IS NULL THEN 'columna nueva'
            WHEN act.columna IS NULL THEN 'columna eliminada'
            WHEN act.tipo_bronze <> ant.tipo_bronze THEN concat('tipo: ', ant.tipo_bronze, ' -> ', act.tipo_bronze)
            WHEN act.tipo_sugerido <> ant.tipo_sugerido THEN concat('tipo sugerido: ', ant.tipo_sugerido, ' -> ', act.tipo_sugerido)
            WHEN abs(coalesce(act.pct_nulos, 0) - coalesce(ant.pct_nulos, 0)) > 5
                 THEN concat('nulos: ', ant.pct_nulos, '% -> ', act.pct_nulos, '%')
            WHEN act.pii AND NOT ant.pii THEN 'ahora parece PII'
       END AS cambio
FROM act
FULL OUTER JOIN ant ON ant.tabla = act.tabla AND ant.columna = act.columna
WHERE (SELECT count(*) FROM corr) >= 2   -- con una sola corrida no hay con qué comparar
  AND (ant.columna IS NULL OR act.columna IS NULL
   OR act.tipo_bronze <> ant.tipo_bronze OR act.tipo_sugerido <> ant.tipo_sugerido
   OR abs(coalesce(act.pct_nulos, 0) - coalesce(ant.pct_nulos, 0)) > 5
   OR (act.pii AND NOT ant.pii))
ORDER BY tabla, columna;

-- 6. Última validación de una propuesta (NB_PRF_03), bloqueantes primero
SELECT severidad, objeto, chequeo, detalle, filas
FROM perfil.validacion
WHERE validacion_id = (SELECT max(validacion_id) FROM perfil.validacion WHERE origen = 'erp')
ORDER BY CASE severidad WHEN 'BLOQUEANTE' THEN 0 WHEN 'ADVERTENCIA' THEN 1 ELSE 2 END, objeto;
