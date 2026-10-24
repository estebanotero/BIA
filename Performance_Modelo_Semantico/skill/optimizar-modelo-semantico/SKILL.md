---
name: optimizar-modelo-semantico
description: Analiza la performance de un modelo semántico de Power BI / Fabric guardado como PBIP (TMDL) a partir del diagnóstico de NB_PERF_01 y las mediciones de NB_PERF_02, propone optimizaciones priorizadas en propuestas.csv y aplica las aprobadas editando los archivos .tmdl en una rama con PR. Usar cuando se pida mejorar la performance, el tamaño o la velocidad de un modelo semántico, revisar el BPA o el Vertipaq Analyzer, o optimizar medidas DAX lentas.
---

# Optimizar un modelo semántico PBIP

El framework está en `Performance_Modelo_Semantico/` del repo BIA. Extiende `Documentar_Modelo_Semantico/`: usa el mismo `modelo.json` de `NB_DOC_01` y la misma carpeta del lakehouse.

**Regla de oro:** los cambios entran por los archivos TMDL del repo PBIP y por PR. No escribas en el modelo publicado (TOM, XMLA ni el Power BI Modeling MCP en modo escritura): la próxima publicación desde PBIP o la próxima sincronización desde Git pisa esos cambios.

Hay tres tareas. Identificá cuál te piden antes de empezar.

## A. Diagnosticar y proponer

Entrada, de `Files/doc_modelos/<modelo>/perf/<corrida>/` (normalmente `antes`), copiada a una carpeta local que no se versiona (por ejemplo `.perf/` en el repo PBIP, agregada a `.gitignore`):

| Archivo | Qué mirar |
|---|---|
| `diagnostico.json` | Tamaño total, `top_columnas`, `relaciones`, `bpa_performance`, `direct_lake_fallback`, `medidas` |
| `mediciones_resumen.csv` | Consultas más lentas en `frio`, reparto `se_ms` / `fe_ms`, `se_consultas`, `dq_consultas_max` |
| `dependencias.csv` | Qué columnas tocan las consultas más lentas |
| `bpa.csv` y `vertipaq_columnas.csv` | El detalle, si el resumen no alcanza |
| La carpeta `<Modelo>.SemanticModel/definition/` del repo | El TMDL actual: es lo que vas a cambiar |

Pasos:

1. Leé todo antes de proponer. Ubicá el modo de almacenamiento (`modos_particion`) y las 3 a 5 consultas más lentas.
2. Para cada consulta lenta, decidí dónde está el problema con la tabla "Cómo leer el diagnóstico" de `catalogo_optimizaciones.md`: modelo, DAX o Direct Lake.
3. Para memoria, empezá por las columnas de `top_columnas` con más `pct_modelo`. Antes de proponer quitar una, buscá referencias en todo `definition/` (medidas, columnas calculadas, `relationships.tmdl`, `roles/`, jerarquías, `sortByColumn`, perspectivas) y en los reportes del repo (`*.Report/`). Si no tenés los reportes, decilo en `riesgo`.
4. Completá `propuestas.csv` (plantilla en `plantillas/`), una fila por cambio atómico:
   - `evidencia`: un número del diagnóstico (bytes, %, ms, cantidad de consultas SE). Sin número no hay propuesta.
   - `impacto_esperado`: cualitativo o un rango razonable. Nunca un número inventado: si no lo podés estimar, `[dato a confirmar con NB_PERF_03]`.
   - `cambia_resultado`: `si` si algún número de algún visual puede cambiar (bidireccional, precisión, reescrituras que no son equivalentes por definición).
   - `prioridad`: 1 = mayor impacto con menor riesgo. Los cambios de arquitectura (modo de almacenamiento, tablas gold nuevas) van solos, con prioridad propia.
   - Dejá `aprobada` vacía: la completa una persona.
5. Respondé con un resumen corto: tamaño actual, las 3 consultas más lentas y las propuestas ordenadas. Preguntá cuáles aprobar.

## B. Aplicar las propuestas aprobadas

Solo filas con `aprobada = si`.

1. Creá una rama `perf/<modelo>-<AAAAMMDD>` desde la rama principal del repo PBIP.
2. Un commit por propuesta, con mensaje `perf(P01): <qué cambia>`. Completá `estado = aplicada` y `commit` en `propuestas.csv`.
3. Al editar TMDL:
   - Indentación con tabulaciones, igual que el archivo.
   - No cambies `lineageTag` de objetos existentes. No toques `.pbi/`, `cache.abf` ni `diagramLayout.json`.
   - Si quitás una columna en Import, sacala también en la consulta M de la partición.
   - Si un cambio necesita Power BI Desktop (fecha/hora automática, por ejemplo), no lo hagas a mano: dejalo como paso manual en el PR.
4. Si hay una herramienta de validación disponible (Tabular Editor 2 CLI, el workflow `ci/bpa-pr.yml` o abrir el PBIP en Desktop), usala y anotá el resultado. Si no, decí que el TMDL no se validó.
5. Abrí el PR con `plantillas/pr_performance.md`. La sección de medición queda "Pendiente" hasta que exista `informe_perf.md`.

## C. Cerrar con la medición

Cuando te pasen `informe_perf.md` de `NB_PERF_03`:

1. Pegalo en el PR, en "Medición".
2. Si el veredicto es `REVISAR`: para cada regresión o resultado distinto, decí qué propuesta es la causa probable (mirá `consultas_afectadas`) y proponé revertir ese commit o ajustarlo.
3. Actualizá `estado` en `propuestas.csv`: `medida` o `revertida`.
4. No digas que algo mejoró si el informe no lo muestra.

## Reglas

- No inventes mediciones, tamaños ni porcentajes: todo número sale de los archivos del framework o se marca `[dato a confirmar]`.
- No copies valores de datos en propuestas ni en el PR: alcanza con nombres de objetos y métricas.
- No mergees: el PR lo revisa y lo mergea una persona.
