# Del perfil a la metadata: reglas de decisión

Cómo traducir cada señal de `perfil.json` a una decisión de silver o gold. Son **puntos de partida**: cuando el negocio dice otra cosa, gana el negocio y se documenta por qué.

## 1. Clave, modo de silver y carga

| Señal del perfil | Decisión | Por qué |
|---|---|---|
| Clave `declarada` y `es_unica` | `PRIMARY_KEY` = esas columnas, `SILVER_MODE = 'MERGE'`, regla `<pk> IS NOT NULL` `FAIL` | La declara el origen y los datos la confirman |
| Clave `declarada` pero **no** `es_unica` | No la uses sin preguntar: el origen tiene duplicados o la copia trajo versiones. `[dato a confirmar]` | El `MERGE` perdería filas en silencio |
| Sin declarada, `simple` preferida (entero con nombre de clave) | `PRIMARY_KEY` = esa columna, `MERGE`, y anotá "clave inferida, no declarada" | Es lo más probable, pero es una foto |
| Solo `compuesta` | `PRIMARY_KEY = 'a,b'` | Típico de detalles (documento + línea) |
| Sin clave única | Eventos o logs: `APPEND`. Catálogo chico (< 100.000 filas): `OVERWRITE`. Siempre `[dato a confirmar]` | `MERGE` exige clave |
| `candidata_watermark = 'DATETIME'` (fecha de modificación sin nulos) | `LOAD_TYPE = 'INCREMENTAL'`, `WATERMARK_TYPE = 'DATETIME'`, `ORDER_COLUMN` = esa columna en snake_case | Trae solo lo cambiado |
| Solo una clave entera creciente (`VentaID`) | `INCREMENTAL` con `WATERMARK_TYPE = 'INT'` **solo si** el negocio confirma que las filas nunca se modifican | Si se modifican, el incremental por ID pierde cambios |
| Ninguna de las dos | `FULL` | Más caro, no pierde datos |
| `candidata_baja_logica` (`Anulada`, `Activo`, `Borrado`) | Recomendá llevar la columna a silver como `boolean` con `DELETE_MODE = 'FLAG'` y `DELETE_FLAG_EXPR` (ej. `anulada = true`); filtrar en origen (`SOURCE_FILTER`) solo si el negocio confirma que una fila nunca se anula después de cargada | Filtrar en origen hace que una anulación posterior no llegue nunca a silver: la fila queda viva. Con `FLAG`, silver la marca `_is_deleted` y gold la saca |
| Tabla sin baja lógica, con borrado físico en el origen y carga `FULL` | `DELETE_MODE = 'ABSENT'` con `DELETE_MAX_PCT` (10 % por defecto) `[dato a confirmar]` con el dueño | Lo que estaba vivo y no vino en la extracción completa se marca como baja; el freno evita marcar media tabla por una extracción cortada |
| Dimensión cuyos atributos cambian y los reportes miran el pasado (zona, segmento, vendedor) | `SILVER_MODE = 'SCD2'` con `SCD2_COLUMNS` = solo esos atributos. **Nunca** columnas PII en `SCD2_COLUMNS` | Sin SCD2 gold pierde a qué zona pertenecía el cliente cuando compró |

## 2. Columnas

| Señal | Decisión |
|---|---|
| `tipo_sugerido` + `transform_sugerida` | Usalos como `TARGET_TYPE` y `TRANSFORM_EXPR`. `NB_PRF_03` verifica que no se pierdan valores |
| Nota "double en el origen" | `decimal(18,2)` para montos, `decimal(18,4)` para cantidades o cotizaciones. Nunca `double` |
| Nota "ceros a la izquierda" | Queda `string`: es un código, no un número |
| Nota "fecha con barra ambigua" | `[dato a confirmar]`: ningún día pasa de 12 en la copia |
| `con_espacios > 0` | `trim(...)` en la transformación |
| Nota "normalizar con upper(trim())" | `upper(trim(col))` (o `initcap` para nombres de lugares) |
| `pii = true` | `IS_PII = 1`. Si el motivo es **solo el nombre** ("contiene 'nombre'") y es `NombreProducto`, no es PII: decilo y dejala en 0 |
| CUIT solo de empresas (prefijos 30/33/34) | `IS_PII = 0`, con la nota del perfil como evidencia |
| `pct_nulos = 100` o `long_max = 0` | No la lleves a silver; decilo |
| `descripcion_origen` | Úsala en el diseño; después alimenta la skill `documentar-modelo-semantico` |

## 3. Reglas de calidad (`meta.DQ_RULE`)

Entre 1 y 4 por tabla. Elegilas por impacto: clave, después lo que rompe un cálculo de gold, después formato.

| Señal | Regla | Acción |
|---|---|---|
| Clave | `<pk> IS NOT NULL` | `FAIL` |
| Medida con `negativos = 0` y significado de cantidad o importe | `<col> >= 0` (o `> 0` si `ceros = 0`) | `DROP` si el negocio confirma que es imposible, si no `WARN` |
| Medida con `negativos > 0` | No pongas regla de signo: hay devoluciones o ajustes. Preguntá | — |
| Fecha con `futuras > 0` o `antiguas > 0` | `<col> BETWEEN DATE'1900-01-01' AND current_date()` (ajustá el piso al negocio) | `DROP` |
| `dominio` chico y estable (moneda, estado) | `<col> IN ('ARS','USD')` con los valores del dominio ya normalizados | `WARN`: avisa si aparece un valor nuevo sin perder la fila |
| Patrón ≥ 99 % (email, CUIT) | `<col> IS NULL OR <col> RLIKE '...'` | `WARN` |
| Columna sin nulos hoy que gold necesita | `<col> IS NOT NULL` | `WARN` |
| FK con huérfanos | **No** como regla de silver (una regla es por fila, no ve la otra tabla). Se resuelve en gold | — |

Una regla `FAIL` o `DROP` tiene que cumplirse en el perfil actual. Si hoy falla en una parte de las filas, empezá con `WARN` y anotalo.

## 4. Gold

| Señal | Decisión |
|---|---|
| `rol_sugerido = dimension` | `dim_<entidad>`, `LOAD_MODE = 'OVERWRITE'`, clave natural de la tabla |
| `hecho` | `fact_<proceso>`, `LOAD_MODE = 'MERGE'` con `MERGE_KEY` = su clave si es grande, `OVERWRITE` si es chica |
| `hecho_cabecera` + detalle con relación `N:1` | Un solo hecho a la granularidad del **detalle**, con las columnas útiles de la cabecera (fecha, cliente). Los importes de cabecera (descuento global, flete) no se suman por línea: `[dato a confirmar]` cómo prorratearlos |
| Relación con `filas_huerfanas > 0` | En el hecho, `LEFT JOIN` y `coalesce(<fk>, -1)`; en la dimensión, `UNION ALL SELECT -1 AS <clave>, 'Desconocido' ...` para que el modelo semántico no muestre filas en blanco |
| Clave natural de texto larga o de cardinalidad muy alta en el hecho | Sacala o pasala a la dimensión: pesa en Vertipaq (ver `Performance_Modelo_Semantico`) |
| Texto libre con `pct_distintos > 50` (observaciones, descripciones) | Fuera del hecho. A la dimensión solo si alguien lo filtra |
| Columnas de fecha en hechos | `dim_fecha` generada con `sequence()` entre el mínimo y el máximo del perfil, con margen |
| PII | Fuera de gold salvo pedido explícito. Si se pide, decí qué riesgo implica y dónde aplicar seguridad (RLS/OLS en el modelo semántico) |
| Nombres | Columnas en snake_case y en el idioma del negocio: las usan el modelo semántico y el agente de datos (`Agente_Datos_Fabric`) |

### `dim_fecha` de ejemplo (Spark SQL)

```sql
SELECT d AS fecha, year(d) AS anio, month(d) AS mes, date_format(d, 'yyyy-MM') AS anio_mes,
       quarter(d) AS trimestre, dayofweek(d) AS dia_semana
FROM (SELECT explode(sequence(DATE'2020-01-01', DATE'2030-12-31', INTERVAL 1 DAY)) AS d)
```
