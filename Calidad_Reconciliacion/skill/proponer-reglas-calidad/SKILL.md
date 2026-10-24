---
name: proponer-reglas-calidad
description: Propone reglas de calidad y reconciliación para gold en Microsoft Fabric (cuadre entre capas, integridad entre hechos y dimensiones, frescura, volumen y reglas de negocio) como filas de dq.REGLA, a partir de la metadata del pipeline medallion, el perfil del origen o el pedido del negocio. También diagnostica reglas que fallan con dq.RESULTADO. Usar cuando se pida controlar que gold esté bien, que los totales cuadren, armar controles de calidad o entender por qué falló una regla.
---

# Proponer reglas de calidad y reconciliación

Trabajás sobre el caso `Calidad_Reconciliacion/` del repo BIA. `meta.DQ_RULE` (pipeline medallion) valida **fila por fila** en silver. Este caso controla lo que una fila sola no muestra: que los totales cuadren entre capas, que los hechos tengan dimensión, que gold esté al día y que los números de negocio tengan sentido. Las reglas viven en `dq.REGLA` y las corre `NB_CAL_01` después de gold.

Reglas que no cambian:

- **No cargás reglas ni corrés nada.** Entregás `alta_reglas_calidad.sql` (plantilla en `plantillas/`) para que una persona lo revise y lo corra en DES.
- **Las consultas solo leen**: `SELECT` o `WITH`, una sentencia, Spark SQL sobre el lakehouse. `NB_CAL_01` rechaza cualquier otra cosa.
- **Nunca filas, nunca personas.** Las reglas devuelven conteos y sumas. La `CLAVE` de un `COMPARA` es un período, una categoría o un código de entidad, nunca un cliente, un email ni un documento.
- Los umbrales que dependen del negocio (cuántas horas de atraso se toleran, cuánta diferencia se acepta) van como `[dato a confirmar]` hasta que el dueño los confirme.

## Tipos de regla

| Tipo | Devuelve | Falla cuando | Para |
|---|---|---|---|
| `COMPARA` | Dos consultas con las mismas métricas y, opcional, columnas de `CLAVE` | Una clave aparece de un solo lado, o una métrica supera **las dos** tolerancias (`TOLERANCIA_ABS` y `TOLERANCIA_PCT`) | Cuadre entre capas |
| `CONDICION` | Una fila con un número | El número queda fuera de `[VALOR_MIN, VALOR_MAX]` o es NULL | Integridad, frescura, volumen, negocio |

Severidad: `ERROR` frena el pipeline antes de refrescar el modelo (mejor datos de ayer que datos mal); `WARN` se registra y llega como alerta por Monitoreo. Empezá con `WARN` y pasá a `ERROR` después de unas semanas sin falsos positivos.

## A. Proponer reglas para un modelo

Entrada: `meta.GOLD_OBJECT` (el `SELECT` de cada objeto gold), `meta.ENTITY`, el `perfil.json` si está, y qué mira el negocio ("ventas por mes y rubro").

1. **Cuadre (`CUADRE`).** Por cada hecho de gold, un `COMPARA` contra su fuente en silver, por mes, con `COUNT(*)` y la suma de la métrica principal.
   - Si gold filtra o agrega a propósito, aplicá el mismo filtro en `SQL_A`, o explicá la diferencia esperada con una tolerancia.
   - Si gold convierte moneda, compará la columna original (`importe_neto`), no la convertida.
   - Si la entidad tiene `DELETE_MODE` (`FLAG` o `ABSENT`), silver guarda las bajas y gold no: filtrá `NOT coalesce(_is_deleted, false)` del lado silver. Si es `SCD2`, silver tiene varias filas por clave: contá solo `_is_current` (o la última versión), nunca la tabla entera.
   - Bronze → silver: claves que llegaron y no están en silver (`LEFT ANTI JOIN`). Ojo: bronze es historia y puede repetir claves (usá `DISTINCT`); las filas rechazadas por reglas `DROP` faltan a propósito.
2. **Integridad (`INTEGRIDAD`).** Por cada relación hecho → dimensión que use el modelo semántico: `COUNT(*)` con `LEFT ANTI JOIN`, máximo 0. Claves duplicadas en una dimensión: `SELECT COUNT(*) FROM (SELECT clave FROM dim GROUP BY clave HAVING COUNT(*) > 1)`, máximo 0.
3. **Frescura (`FRESCURA`).** Horas desde el `MAX` de la fecha de negocio de cada hecho. El máximo depende de la frecuencia del origen y los días sin actividad `[dato a confirmar]`.
4. **Volumen (`VOLUMEN`).** Filas del último período contra un rango, solo si el negocio es estable. Si no, dejalo para Monitoreo (`MDP_VOLUMEN_ANOMALO` ya compara con la mediana).
5. **Negocio (`NEGOCIO`).** Lo que diga el área: "el margen no puede ser negativo", "la suma de porcentajes da 100". Una `CONDICION` que cuenta las violaciones.
6. **Tolerancias.** `0` cuando gold es una copia transformada de silver. Una tolerancia porcentual chica (`0.01`) solo para redondeos de `decimal` a `double`. Nunca una tolerancia para tapar una diferencia que nadie entiende.
7. Escribí el script con la plantilla, una línea de decisión por regla, y cerrá con los `[dato a confirmar]`.

## B. Diagnosticar una regla que falla

Entrada: la fila de `dq.RESULTADO` (o `dq.v_ultimo_resultado`) y la regla.

| Síntoma en `DETALLE` | Causa probable | Qué hacer |
|---|---|---|
| `mes=...: solo en A` en silver → gold | Gold no corrió completo o filtra ese período | Ver `log.RUN_STEP` de la capa gold en esa corrida |
| Diferencia de filas, mismo importe | Duplicados en gold (un `JOIN` que multiplica) | Revisar el `SELECT` de `meta.GOLD_OBJECT`: un `JOIN` a una tabla sin clave única |
| Diferencia de importe, mismas filas | Conversión, redondeo o un `CASE` en gold | Comparar la columna original; si es redondeo, tolerancia chica |
| `ventas_sin_cliente > 0` | Dimensión cargada antes que el hecho, o cliente nuevo que todavía no llegó | Revisar `DEPENDS_ON_GOLD`; si es de origen, avisar al dueño |
| Frescura vencida sin fallas en el log | El origen no mandó datos | Preguntar al dueño del origen antes de tocar nada |
| `ERROR_EJECUCION` | Tabla o columna renombrada, SQL con error | Corregir la regla por script; no la desactives sin reemplazo |

Decí si hay que reprocesar (y qué capa), si la regla está mal o si el dato está mal en el origen, y a quién avisar.

## Salida

El script `alta_reglas_calidad.sql` y el informe con [`plantillas/informe_calidad.md`](plantillas/informe_calidad.md), con **Próximos pasos**.
