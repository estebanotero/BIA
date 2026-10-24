---
name: disenar-medallion-desde-perfil
description: Diseña las capas silver y gold de un lakehouse de Microsoft Fabric a partir del perfil de una base de origen (perfil.json de NB_PRF_01/02) y lo traduce a metadata del pipeline medallion (meta.ENTITY, ENTITY_COLUMN, DQ_RULE, GOLD_OBJECT). Usar cuando se pida perfilar un origen, decidir claves, tipos, PII y reglas de calidad con datos, armar el modelo estrella de gold, preparar la carga exploratoria o revisar la validación NB_PRF_03.
---

# Diseñar silver y gold desde el perfil de un origen

El framework está en `Perfilado_Origen_Medallion/` del repo BIA. Los notebooks perfilan bronze y dejan **evidencia**; vos la convertís en un **diseño** y en la **metadata** que ejecuta el pipeline de `Pipeline_Metadata_Medallion/`. No inventás nada que el perfil no muestre: lo que falta va como `[dato a confirmar]`.

Leé también la skill `metadata-medallion` (`Pipeline_Metadata_Medallion/skill/metadata-medallion/SKILL.md`): sus reglas de nombres, tipos, PII y reglas de calidad siguen valiendo. Esta skill agrega **cómo decidir con datos**, según [`reglas_perfil_a_metadata.md`](reglas_perfil_a_metadata.md).

Hay cuatro tareas. Identificá cuál te piden antes de empezar.

## A. Preparar la carga exploratoria

Entrada: el catálogo del origen (salida de `sql/01_catalogo_origen.sql`) o una lista de tablas.

1. Elegí las tablas: las que pidió el negocio y sus maestros. Si el catálogo tiene cientos, proponé un primer lote de 10 a 20 y decí cuáles quedan afuera.
2. Escribí el script con [`plantillas/alta_exploracion.sql`](plantillas/alta_exploracion.sql): una entidad por tabla, `LOAD_TYPE = 'FULL'`, `SILVER_MODE = 'APPEND'`, `LOAD_GROUP = 'exploracion'`, **sin columnas ni reglas**. `ENTITY_CODE = <sistema>_<tabla>` en minúsculas: NB_PRF_01 cruza el catálogo con esa convención.
3. Para tablas de más de ~10 millones de filas (ver `FILAS_APROX`), proponé un `SOURCE_FILTER` que traiga un período representativo (los últimos 12 meses) y decilo: el perfil va a describir ese período, no la tabla entera.
4. Recordá: se corre con `p_load_group = exploracion` y `p_layers = bronze`. Silver no se ejecuta.

## B. Diseñar silver y gold desde `perfil.json`

Entrada: `perfil.json` (o `resumen_perfil.md`) de `Files/perfil/<origen>/<corrida_id>/`, y si existe, qué necesita el negocio de gold ("ventas por cliente, producto y mes").

1. **Leé el perfil completo antes de decidir.** Por tabla: filas, `claves_candidatas` (la `preferida` primero), `rol_sugerido`; por columna: `tipo_sugerido`, `transform_sugerida`, `pii`, `notas`, `dominio`, `candidata_watermark`, `candidata_baja_logica`; y `relaciones`.
2. **Silver, tabla por tabla**, aplicando `reglas_perfil_a_metadata.md`. Cada decisión lleva **la evidencia en una línea** ("`VentaID`: PK declarada, 0 % nulos, única en 1.2 M filas").
   - Clave, `SILVER_MODE`, `LOAD_TYPE`, watermark y `ORDER_COLUMN`.
   - Columnas: nombre snake_case (`columna_silver_sugerida` como punto de partida), tipo, transformación, `IS_PII`.
   - Reglas de calidad: entre 1 y 4 por tabla, elegidas por el perfil (no una por columna).
   - Baja lógica: si hay `candidata_baja_logica`, proponé el `SOURCE_FILTER` o una columna en silver y preguntá cuál prefiere el negocio.
3. **Gold**: modelo estrella. Una dimensión por tabla `dimension`, un hecho por proceso de negocio (`hecho`, `hecho_cabecera` + su detalle). Para cada hecho declarás la **granularidad** ("una fila por línea de venta") y su clave. Relaciones `declarada_con_huerfanos` o con `filas_huerfanas > 0`: `LEFT JOIN` en el hecho y miembro desconocido en la dimensión (ver reglas). Sin PII en gold.
4. Entregá **dos archivos**:
   - `diseno_<origen>.md` con [`plantillas/diseno_medallion.md`](plantillas/diseno_medallion.md): decisiones con evidencia, diagrama Mermaid del modelo estrella, PII y `[dato a confirmar]`.
   - `alta_<origen>.sql` con la plantilla de la skill `metadata-medallion` (`plantillas/alta_entidad.sql`), incluida la sección 5 de gold. Mismos `ENTITY_CODE` que la carga exploratoria: el `MERGE` los actualiza y pasa `LOAD_GROUP` a `default`.
5. Cerrá con los pasos: correr `alta_<origen>.sql` en la base de control **de desarrollo**, `EXEC meta.usp_VALIDATE_METADATA`, y después `NB_PRF_03_validar_propuesta` con la salida de `meta.usp_GET_RUN_CONFIG 'default', 'validacion'`.

## C. Revisar la validación (`NB_PRF_03`)

Entrada: `validacion.md` o el JSON de salida de `NB_PRF_03`.

1. Cada `BLOQUEANTE` necesita un cambio en el script antes de seguir. Patrones:
   - Regla `FAIL` que no se cumple hoy: **no la relajes sin mirar los datos**. Si el perfil muestra que los valores son reales (devoluciones con cantidad negativa), cambiá la regla y explicalo; si son errores, pasala a `DROP` y avisá a quien es dueño del origen.
   - `PRIMARY_KEY` con nulos o fuera de las columnas: la clave está mal elegida o falta en `ENTITY_COLUMN`.
   - Expresión que no compila: nombre de columna de bronze mal escrito (bronze reemplaza espacios y `,;{}()=` por `_`).
2. `ADVERTENCIA` de pérdida por tipo: mirá el `patrones` y el `top_valores` de esa columna en el perfil y corregí `TARGET_TYPE` o `TRANSFORM_EXPR` (un `int` que tiene `2,5` es un `decimal` con coma).
3. `ADVERTENCIA` de clave repetida en una copia: la clave no es la del origen, o el origen tiene versiones. Proponé la clave compuesta del perfil o un `ORDER_COLUMN`.
4. PII sin marcar: marcala, salvo que el perfil lo haya marcado solo por nombre y los datos muestren otra cosa; decilo.
5. Devolvé el script corregido completo, no un parche.

## D. Comparar corridas de perfil (cambios en el origen)

Entrada: el resultado de la consulta 5 de `sql/02_consultas_perfil.sql`.

- Columna nueva: decidí si va a silver (si la entidad tiene `ENTITY_COLUMN`, no llega sola).
- Columna eliminada o cambio de tipo: va a romper silver; proponé el cambio de metadata y el reproceso (ver el runbook de `Pipeline_Metadata_Medallion`).
- Salto de nulos o PII nueva: avisá y proponé una regla `WARN` para monitorearlo.

## Reglas para las cuatro tareas

- La evidencia viene del perfil. Si no está, `[dato a confirmar]`. Nunca inventes significados de negocio de una columna: el nombre es una pista, no una definición.
- Un perfil es una foto de una copia: un `UNIQUE` en 5.000 filas no garantiza la clave en producción. Si la clave no está declarada en el catálogo, decilo.
- Nunca pongas valores de columnas PII en los archivos que generás (el perfil ya no los trae; no los pidas).
- **Nunca** pongas credenciales ni connection strings en la metadata.
- Todo lo que generás es para revisión humana y se corre primero en desarrollo. Vos no ejecutás nada contra la base de control ni el lakehouse.
