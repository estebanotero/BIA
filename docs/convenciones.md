# Convenciones de BIA y desvíos detectados

**En corto:** los casos de BIA siguen, en general, el mismo patrón: *un notebook deja los datos listos, Claude trabaja con una skill, una persona revisa y un notebook carga solo lo aprobado*. Esta página fija las convenciones y lista dónde se apartaban los casos, con la corrección que se aplicó.

Revisión del 2026-10-24 sobre `main` (después del merge del PR #5). Correcciones y decisiones aplicadas el mismo día, con el OK de Eduardo.

---

## 1. Convenciones (lo que ya sigue la mayoría)

### 1.1. Estructura de una carpeta de caso

```text
<Caso>/
├── README.md          En corto · archivos · flujo · opciones · requisitos · uso · validación · runbook · próximos pasos
├── sql/               NN_<tema>.sql, idempotentes, con PASOS y vuelta atrás comentados
├── notebooks/         NB_<PREFIJO>_NN_<verbo>.ipynb
├── skill/<nombre>/    SKILL.md + plantillas/ (+ material de criterio: reglas, catálogos)
├── mcp/               Solo si Claude necesita una herramienta propia
├── ci/                Plantillas de CI, opcionales
└── pruebas/           prueba_local.py: lógica de los notebooks sin Fabric
```

### 1.2. Nombres

| Qué | Convención | Ejemplos |
|---|---|---|
| Carpeta del caso | `Palabra_Palabra` en español, sin tildes | `Pipeline_Metadata_Medallion` |
| Prefijo de notebooks | Tres o cuatro letras únicas por caso | `DOC`, `PERF`, `MDP`, `PRF`, `AGT`, `INV`, `MON`, `SEG`, `CAL`, `CAT` |
| Notebook | `NB_<PREFIJO>_<NN>_<verbo_objeto>` | `NB_PRF_01_perfilar` |
| Numeración | `01`, `02`, `03` en el orden de uso. `MDP` usa `00/10/20/30` a propósito: `00` es el orquestador y las decenas son las capas | `NB_MDP_20_silver` |
| Skill | `kebab-case`, verbo + objeto, en español | `optimizar-modelo-semantico` |
| Items de Fabric | `PL_` pipeline, `LH_` lakehouse, `DB_` SQL database, `AG_` data agent | `PL_MDP_MEDALLION`, `LH_MEDALLION`, `DB_MDP_CONTROL`, `AG_VENTAS` |
| Objetos SQL de control | Esquema por función, tablas en `MAYÚSCULAS`, SP `usp_` | `meta.ENTITY`, `log.usp_END_RUN` |
| Tablas Delta | Esquema por caso, tabla en `minúsculas` | `perfil.columna`, `agente.eval_historial` |
| Columnas técnicas en bronze, silver y gold | Empiezan con `_`. Los datos de negocio nunca empiezan con `_` | `_run_id`, `_ingested_at`, `_silver_updated_at`, `_is_deleted`, `_valid_from`, `_valid_to`, `_is_current` |

### 1.3. Dónde vive cada cosa

| Pieza | Dónde | Casos |
|---|---|---|
| Datos (bronze, silver, gold) | `LH_MEDALLION`, esquemas `bronze`, `silver`, `gold` | MDP, PRF, AGT |
| Tablas Delta de cada caso | `LH_MEDALLION`, un esquema por caso: `perfil`, `doc`, `perf`, `agente_ctl`, `catalogo` | PRF, DOC, PERF, AGT, CAT |
| Vistas para el agente | `LH_MEDALLION`, esquema `agente` (solo vistas de negocio, sin PII) | AGT |
| Archivos de trabajo | `Files/<area>/<objeto>/...` en el lakehouse por defecto del notebook | `Files/landing/<entidad>/<run_id>/`, `Files/perfil/<origen>/`, `Files/doc_modelos/<modelo>/`, `Files/doc_modelos/<modelo>/perf/<corrida>/`, `Files/agente/<AGENTE>/` |
| Configuración y estado | **Una** SQL database de control: `config` (inventario), `meta` (metadata del pipeline), `log` (corridas), `mon` (SLA y alertas), `dq` (reglas y resultados de calidad), `cat` (dueños de activos) | Inventario, MDP, PRF, MON, CAL, CAT |
| Listas compartidas | [`Comun/`](../Comun/README.md) en el repo, `Files/comun/` en el lakehouse | DOC, PRF |
| Matriz de accesos | `seguridad/` del repo de la implementación, aprobada por PR. Los scripts generados, en `Files/seguridad/scripts/` | SEG |
| Secretos | Azure Key Vault, leídos con `notebookutils.credentials.getSecret` | DOC (opción B) |

### 1.4. Reglas que comparten todos los casos

- Claude **no escribe** en la base de control, el lakehouse ni el modelo publicado: genera archivos y scripts que una persona revisa y corre.
- Todo notebook que escribe tiene `DRY_RUN = True` por defecto o escribe solo en su propio esquema.
- Lo aprobado se marca en un CSV (`revisado = si`, `aprobada = si`, `estado = VALIDADA`). Lo que dice `[dato a confirmar]` no se carga.
- Nada de PII fuera de bronze: ni en perfiles, ni en rechazos, ni en gold, ni en las vistas del agente.
- Cada README dice qué está probado y qué no.
- Los notebooks que se pueden orquestar tienen la primera celda de configuración marcada como `parameters`.
- Las librerías que cambian el formato de su salida van con versión fija (`semantic-link-labs==0.17.1`, `fabric-data-agent-sdk==0.1.33a0`).

### 1.5. Una sola base de control

Una SQL database por ambiente (la que ya existe, `DB_TDM_Platform`, o la que se cree con otro nombre) con un esquema por función:

| Esquema | Qué guarda | Quién escribe |
|---|---|---|
| `config` | Inventario de items (`DOMAIN_OBJECTS`, `SOURCE_TYPES`) | `NB_INV_01` vía `config.usp_SYNC_DOMAIN_OBJECTS` |
| `meta` | Metadata del pipeline medallion | Scripts revisados (`alta_<origen>.sql`) |
| `log` | Corridas y pasos | El pipeline, vía `log.usp_*` |
| `dq` | Reglas de calidad y reconciliación y sus resultados | Reglas: scripts revisados (`alta_reglas_calidad.sql`). Resultados: el pipeline, vía `dq.usp_LOG_RESULTADOS` |
| `cat` | Dueño, área y criticidad de cada activo del linaje | Scripts revisados (`alta_activos.sql`). El linaje en sí vive en el lakehouse (`catalogo.*`), lo escribe `NB_CAT_01` |
| `mon` | SLA por grupo de carga y alertas | `NB_MON_01` vía `mon.usp_SYNC_ALERTAS`; los SLA, una persona |

Por qué una: describen la misma plataforma y se cruzan (catálogo, monitoreo); hay una sola conexión, un solo backup y un solo despliegue por ambiente. Los permisos se separan por esquema. Dos bases solo tienen sentido si cada una tiene otro dueño u otra política de seguridad.

### 1.6. Dónde van los artefactos de cada implementación

BIA guarda **frameworks**. Lo que sale de usarlos en una plataforma concreta va a un **repo aparte por implementación** (por ejemplo `TDM_Platform`), que además es el que se conecta a Fabric y despliega [`Despliegue_Entre_Ambientes`](../Despliegue_Entre_Ambientes/README.md):

```text
<implementacion>/
├── workspace/           Items de Fabric (integración Git) + parameter.yml
├── sql/                 Migraciones de la base de control (DDL de BIA + alta_<origen>.sql)
├── origenes/<origen>/   diseno_<origen>.md, perfil y validación de referencia
├── modelos/<modelo>/    diccionario.md, informes de performance
├── agentes/<AGENTE>/    instrucciones_agente.md, banco_preguntas.csv
└── .github/workflows/   CI y despliegue
```

Así BIA sigue siendo reutilizable, los datos de una implementación no se mezclan con las plantillas y cada cambio de la plataforma tiene su PR en su repo.

## 2. Desvíos detectados

Ordenados por impacto.

| # | Desvío | Dónde | Por qué importa | Corrección propuesta | Esfuerzo | Estado |
|---|---|---|---|---|---|---|
| 1 | **El banco de preguntas y el historial de evaluaciones están en el mismo esquema que las vistas del agente** (`agente.banco_preguntas`, `agente.eval_historial` junto a `agente.ventas`) | `NB_AGT_01`, `NB_AGT_03`, `01_vistas_agente.sql` | El script sugiere `GRANT SELECT ON SCHEMA::agente` a los usuarios del agente. Con eso pueden leer las **respuestas esperadas** de la evaluación, y si alguien selecciona esas tablas en el data agent, la evaluación mide memoria | Mover las tablas de control a un esquema propio (`agente_ctl`) y dejar `agente` solo para vistas de negocio | Bajo | Aplicado |
| 2 | **Tablas Delta sin esquema** | `doc_diccionario` (`NB_DOC_03`), `perf_bpa`, `perf_vertipaq_tablas`, `perf_vertipaq_columnas`, `perf_mediciones`, `perf_comparacion` (`NB_PERF_*`) | En un lakehouse con esquemas caen en `dbo`, mezcladas con cualquier otra cosa. Los demás casos usan su esquema (`perfil.*`, `agente.*`) | `doc.diccionario` y `perf.<tabla>`, con `CREATE SCHEMA IF NOT EXISTS` | Bajo | Aplicado |
| 3 | **Notebooks sin celda de parámetros marcada** | `NB_DOC_01..03`, `NB_PERF_01..03`, `NB_Workspace_inventory_v2` | No se pueden llamar desde un pipeline o `runMultiple` pasando `MODELO`, `WORKSPACE` o `CORRIDA`: hay que editarlos. Los de MDP, PRF y AGT sí la tienen | Marcar la primera celda de configuración con el tag `parameters` | Bajo | Aplicado |
| 4 | **Versión de semantic-link-labs distinta en dos casos encadenados** | `NB_DOC_01/03` instala sin versión; `NB_PERF_01/02` fija `0.17.1` | `Performance` lee el `modelo.json` que genera `NB_DOC_01`. Si una versión nueva cambia nombres de columnas, `DOC` cambia de formato sin aviso | Fijar `semantic-link-labs==0.17.1` en `DOC` y subirla en los dos casos a la vez | Bajo | Aplicado |
| 5 | **Dos bases de control** | Inventario usa `config.*` en la SQL database que ya existe (el README de MDP la nombra `DB_TDM_Platform`); MDP propone crear otra, `DB_MDP_CONTROL`, para `meta.*` y `log.*` | El inventario de items y la metadata del pipeline describen la misma plataforma, pero no se pueden cruzar (por ejemplo, qué pipeline o lakehouse de `config.DOMAIN_OBJECTS` usa cada entidad) | **Decisión:** una sola SQL database de control con esquemas `config`, `meta` y `log`, o dejarlas separadas a propósito y decirlo en los README | Medio | Aplicado: una base (1.5) |
| 6 | **Inventario_Workspace no sigue la estructura** | Notebook en la raíz, nombre `NB_Workspace_inventory_v2`, sin `notebooks/`, sin `pruebas/` ni skill | Es el primer caso y quedó con el formato anterior a las convenciones | Mover a `notebooks/NB_INV_01_sincronizar_items.ipynb` y sumar una prueba local de la guardia de filas mínimas. La skill no hace falta | Bajo | Aplicado, sin prueba local (ver nota) |
| 7 | **`PATRONES_SENSIBLES` copiada en dos notebooks** | `NB_DOC_01` y `NB_PRF_01` (hoy idénticas) | Si se agrega un patrón en uno solo, una columna es PII para el perfil y no para el diccionario, o al revés | Fuente única: `Files/comun/patrones_sensibles.json` leído por los dos, con la lista actual como valor por defecto | Bajo | Aplicado |
| 8 | **Artefactos de instancia dentro del repo de frameworks** | `DOC` dice copiar el diccionario a `modelos/<modelo>/` de este repo; `AGT` dice `agentes/AG_VENTAS/` | Mezcla plantillas reutilizables con datos de un cliente o modelo concreto. Esas carpetas tampoco existen | **Decisión:** un repo aparte por implementación (recomendado) o una carpeta `instancias/` con su propio README | Bajo | Aplicado: repo aparte (1.6) |
| 9 | **Lakehouse sin nombre en DOC y PERF** | "Lakehouse por defecto" | Los demás casos usan `LH_MEDALLION`. No queda claro si el diccionario y las mediciones van al mismo lakehouse que gold | Decir explícitamente `LH_MEDALLION` (esquemas `doc` y `perf`) o un lakehouse de plataforma aparte | Bajo | Aplicado |
| 10 | **Pruebas locales sin un punto de entrada común ni CI** | Cada `pruebas/prueba_local.py` tiene sus requisitos (Spark y Delta en MDP y PRF, solo pandas en PERF, `mcp` en AGT) | Nadie se entera si un cambio en un caso rompe otro (por ejemplo, el formato de `CONFIG_JSON` que comparten MDP y PRF) | Un workflow de GitHub Actions que corra las cuatro pruebas en cada PR | Medio | Aplicado: `.github/workflows/pruebas.yml` |
| 11 | Nombres de carpeta con criterios mezclados | `Documentar_` (verbo), `Performance_`, `Perfilado_` (sustantivo), `Agente_` | Estético: cuesta adivinar el nombre de un caso nuevo | **No renombrar**: rompe enlaces externos (por ejemplo desde el repo Agentes). Para los casos nuevos, usar `Objeto_Accion` o el criterio que se elija | — | No se renombra |

### Lo que está bien y conviene mantener

- La secuencia entre casos está bien encadenada: Perfilado alimenta la metadata de MDP y valida con el mismo `CONFIG_JSON`; Performance reusa `modelo.json` y la carpeta de Documentar; el Agente lee gold sin PII.
- Las cinco skills tienen `name` y `description` con el "usar cuando" y siguen el mismo formato.
- Todos los README separan lectura, escritura y cambios con impacto, y dicen qué no está probado en Fabric real.

## 3. Notas sobre lo aplicado

- **Desvío 1:** las tablas pasan a `agente_ctl.banco_preguntas` y `agente_ctl.eval_historial`. Si ya existían en `agente`, copialas una vez (`CREATE TABLE agente_ctl.x AS SELECT * FROM agente.x`) y borrá las viejas después de revisar.
- **Desvío 2:** `doc.diccionario` y `perf.*` (`vertipaq_columnas`, `vertipaq_tablas`, `bpa`, `mediciones`, `comparacion`). Los notebooks crean el esquema si no existe. Si ya había tablas `doc_diccionario` o `perf_*` en `dbo`, quedan como historia: copialas al esquema nuevo si las querés seguir usando.
- **Desvío 6:** el notebook pasó a `Inventario_Workspace/notebooks/NB_INV_01_sincronizar_items.ipynb`. No sumé prueba local: la lógica importante está en el stored procedure (T-SQL), que no se puede probar sin un SQL Server; la guardia del notebook es una comparación de una línea.
- **Desvío 10:** [`.github/workflows/pruebas.yml`](../.github/workflows/pruebas.yml) corre las pruebas locales de cada caso en cada PR (seis desde que se sumó Monitoreo). El workflow corre todos los `pruebas/prueba_*.py` de cada caso. En `Pipeline_Metadata_Medallion`, `prueba_local.py` imprime los resultados pero no tiene `assert` (en CI solo detecta que algo se rompa con error); `prueba_scd2_bajas.py`, que cubre historia y bajas, sí tiene chequeos. Sumarle aserciones a la primera es una mejora pendiente.
- **Desvío 7:** [`Comun/patrones_sensibles.json`](../Comun/README.md). Si no está subido a `Files/comun/`, cada notebook usa su lista por defecto (hoy idénticas).
