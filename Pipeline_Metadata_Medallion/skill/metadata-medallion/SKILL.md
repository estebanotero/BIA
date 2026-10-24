---
name: metadata-medallion
description: Genera y revisa la metadata del framework de pipelines metadata-driven medallion en Microsoft Fabric (meta.ENTITY, ENTITY_COLUMN, DQ_RULE, GOLD_OBJECT) a partir del DDL o una muestra de un origen, y diagnostica corridas con log.RUN y log.RUN_STEP. También configura historia (SCD tipo 2) y bajas del origen. Usar cuando se pida sumar una tabla u origen al lakehouse, armar un objeto gold, guardar la historia de una dimensión, reflejar filas borradas o anuladas en el origen, o entender por qué falló una carga.
---

# Metadata del pipeline medallion en Fabric

El framework está en `Pipeline_Metadata_Medallion/` del repo BIA. El pipeline y los notebooks no cambian: todo lo que hace se define con filas en la base de control (`sql/01_ddl_control.sql`). Tu trabajo es escribir esas filas bien, o leer el log y decir qué pasó.

Hay tres tareas. Identificá cuál te piden antes de empezar.

## A. Sumar un origen o una tabla (bronze + silver)

Entrada: el DDL de la tabla de origen (`CREATE TABLE`, `sp_help`, `INFORMATION_SCHEMA.COLUMNS`), una muestra de filas o una lista de columnas. Si es una carpeta de archivos, la ruta en OneLake y un archivo de ejemplo.

Si te pasan un `perfil.json` (caso `Perfilado_Origen_Medallion/`), usá también la skill `disenar-medallion-desde-perfil`: las decisiones de abajo se toman con la evidencia del perfil en lugar de suponerlas.

1. Por cada tabla decidí y **explicá en una línea** cada decisión:
   - `LOAD_TYPE`: `INCREMENTAL` si hay una columna confiable que siempre crece (fecha de modificación, ID autoincremental). Si no, `FULL`. Ante la duda, `FULL`: es más caro pero no pierde datos.
   - `WATERMARK_COLUMN` y `WATERMARK_TYPE` (`DATETIME` o `INT`). Una fecha de **alta** no sirve si las filas se modifican después; decilo.
   - `PRIMARY_KEY` con los nombres de **silver** (snake_case). Si no la ves en el DDL, poné `[dato a confirmar]` en el comentario y usá `SILVER_MODE = 'APPEND'` hasta confirmarla.
   - `SILVER_MODE`: `MERGE` si hay clave, `OVERWRITE` para catálogos chicos sin clave, `APPEND` para eventos o logs que nunca se modifican. `SCD2` solo si el negocio necesita ver cómo era la fila en el pasado (zona, segmento, vendedor de un cliente), con `SCD2_COLUMNS` = esos atributos y **nunca** columnas PII.
   - Bajas (`DELETE_MODE`): `FLAG` con `DELETE_FLAG_EXPR` si el origen tiene una columna de anulación (preferilo a `SOURCE_FILTER`, que nunca refleja una anulación posterior); `ABSENT` solo con `LOAD_TYPE = 'FULL'` y borrado físico en el origen, con `DELETE_MAX_PCT` `[dato a confirmar]`; si no, `NONE`. Ver la sección 10 del README.
   - `ORDER_COLUMN`: la columna que dice cuál versión de una fila es la más nueva (normalmente la misma del watermark, en snake_case).
   - Origen `FILES` en CSV o JSON: incremental **sin** `WATERMARK_COLUMN` (usa la fecha de modificación del archivo). Con Delta como origen, hace falta `WATERMARK_COLUMN`.
2. Columnas (`meta.ENTITY_COLUMN`), una fila por columna que tenga que llegar a silver:
   - `TARGET_COLUMN` en snake_case y en español si el origen está en español. Sin tildes ni espacios.
   - `TARGET_TYPE` en tipos de Spark SQL: `int`, `bigint`, `decimal(p,s)`, `string`, `date`, `timestamp`, `boolean`. Montos siempre `decimal`, nunca `double`.
   - `TRANSFORM_EXPR` solo si hace falta (`trim`, `upper`, `to_date(col, 'dd/MM/yyyy')`, normalizar códigos). Usa los nombres de **bronze**: los del origen con espacios y `,;{}()=` reemplazados por `_`.
   - `IS_PII = 1` para datos personales: DNI, CUIT/CUIL de personas, email, teléfono, domicilio, fecha de nacimiento, datos de salud, sueldos, CBU. Si dudás, marcala y decilo.
3. Reglas de calidad (`meta.DQ_RULE`), entre 1 y 4 por tabla, en Spark SQL sobre las columnas de silver:
   - Clave no nula → `FAIL`.
   - Valores imposibles (cantidad ≤ 0, fecha futura en una venta) → `DROP`.
   - Formato dudoso que no impide usar la fila (CUIT sin 11 dígitos) → `WARN`.
4. Escribí el script con `plantillas/alta_entidad.sql`: es idempotente (`MERGE` por código) y **nunca toca `WATERMARK_VALUE`**.
5. Cerrá con: la lista de `[dato a confirmar]`, las preguntas para cerrarlos, y el recordatorio de correrlo primero en desarrollo y después `EXEC meta.usp_VALIDATE_METADATA`.

## B. Armar un objeto gold

Entrada: qué necesita el reporte o el modelo semántico ("ventas por cliente y mes en pesos").

1. Leé qué hay en silver (las filas de `meta.ENTITY` y `meta.ENTITY_COLUMN`, o el resultado de `SHOW TABLES IN silver` y `DESCRIBE`).
2. Proponé el diseño en estrella: qué es hecho, qué es dimensión y cuál es la granularidad de cada tabla. Una dimensión por entidad de negocio, un hecho por proceso.
3. `SQL_TEXT` es un `SELECT` de Spark SQL sobre `silver.*` o sobre otros `gold.*`. **No incluyas columnas PII** en gold salvo que lo pidan explícitamente; decilo si las sacaste.
4. `LOAD_MODE`: `OVERWRITE` para dimensiones y agregados chicos; `MERGE` con `MERGE_KEY` para hechos grandes; `MLV` (con `CREATE MATERIALIZED LAKE VIEW IF NOT EXISTS gold.x AS SELECT ...`) para agregados que Fabric puede refrescar solo. Las MLV no aceptan UDF, time travel ni vistas temporales.
5. `DEPENDS_ON_GOLD` con los `GOLD_CODE` que tienen que correr antes.
   - Silver en `SCD2`: dimensión actual con la última versión de cada clave (`row_number() ... ORDER BY _valid_from DESC`), y si piden el pasado, una dimensión con historia (`xxhash64(clave, _valid_from) AS <x>_sk`, `vigente_desde`, `vigente_hasta`) que el hecho cruza por fecha. Ejemplo en `sql/03_ejemplo_historia.sql`.
   - Silver con bajas: incluí `_is_deleted` en el `SELECT` de los hechos para que gold las saque. En una dimensión que tiene hechos viejos, renombrala (`_is_deleted AS discontinuado`) para conservarlas.
6. Usá la sección 5 de `plantillas/alta_entidad.sql`.

## C. Diagnosticar una corrida

Entrada: el resultado de las consultas de `plantillas/consultas_operacion.sql`, o el JSON de salida del orquestador.

1. Ubicá el primer paso con `FAILED` en el orden copy → bronze → silver → gold. Los `SKIPPED_UPSTREAM_FAILED` son consecuencia, no causa.
2. Explicá la causa probable en una o dos oraciones a partir de `ERROR_MESSAGE`. Patrones frecuentes:
   - `Regla X (FAIL)`: hay datos que no cumplen la regla. Proponé revisarlos antes de relajar la regla.
   - `AnalysisException ... cannot resolve`: una columna de `ENTITY_COLUMN` o del `SQL_TEXT` ya no existe en el origen.
   - `CAST` o `NumberFormatException`: el `TARGET_TYPE` no coincide con los datos.
   - `ConcurrentAppendException` o similares: dos entidades escriben en la misma tabla silver.
   - Copy fallida: credenciales o gateway de la conexión de Fabric, o la consulta de origen.
   - `Bajas por ausencia: faltan N de M claves vivas ... DELETE_MAX_PCT`: la extracción completa vino corta. No subas el umbral sin confirmar con el dueño del origen que las bajas son reales.
   - `SCD2_COLUMNS nombra columnas que no están en silver`: la columna cambió de nombre en `ENTITY_COLUMN`.
3. Decí qué hacer y si se puede reintentar tal cual: el watermark solo avanza cuando bronze termina bien y silver no falla, así que volver a correr el pipeline no pierde datos.
4. Para reprocesar silver y gold sin volver a copiar: `layers = "silver,gold"` y `reprocesar_run_id = "<RUN_ID>"` en el orquestador.

## Reglas para las tres tareas

- **Nunca** pongas usuarios, contraseñas, connection strings ni claves en la metadata. `CONNECTION_REF` es el nombre de una conexión de Fabric.
- No borres filas de `meta.ENTITY` ni de `meta.GOLD_OBJECT`: para dar de baja, `IS_ACTIVE = 0`.
- No cambies `WATERMARK_VALUE`. Si te piden recargar desde una fecha, explicá el impacto (vuelve a copiar y a mergear todo desde ahí), escribí el `UPDATE` aparte y pedí confirmación.
- No inventes significados de columnas ni reglas de negocio: `[dato a confirmar]`.
- Todo lo que generás es para revisión humana, no para correr directo en producción.
