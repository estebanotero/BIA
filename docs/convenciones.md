# Convenciones de BIA y desvíos detectados

**En corto:** los seis casos de BIA siguen, en general, el mismo patrón: *un notebook deja los datos listos, Claude trabaja con una skill, una persona revisa y un notebook carga solo lo aprobado*. Esta página fija las convenciones que ya usan la mayoría de los casos y lista dónde se apartan, con la corrección propuesta. **Las correcciones no están aplicadas**: tocan notebooks que todavía no se probaron en Fabric, y algunas son decisiones de arquitectura. Cada una necesita el OK antes de hacerse.

Revisión hecha el 2026-10-24 sobre `main` (después del merge del PR #5).

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
| Prefijo de notebooks | Tres o cuatro letras únicas por caso | `DOC`, `PERF`, `MDP`, `PRF`, `AGT` |
| Notebook | `NB_<PREFIJO>_<NN>_<verbo_objeto>` | `NB_PRF_01_perfilar` |
| Numeración | `01`, `02`, `03` en el orden de uso. `MDP` usa `00/10/20/30` a propósito: `00` es el orquestador y las decenas son las capas | `NB_MDP_20_silver` |
| Skill | `kebab-case`, verbo + objeto, en español | `optimizar-modelo-semantico` |
| Items de Fabric | `PL_` pipeline, `LH_` lakehouse, `DB_` SQL database, `AG_` data agent | `PL_MDP_MEDALLION`, `LH_MEDALLION`, `DB_MDP_CONTROL`, `AG_VENTAS` |
| Objetos SQL de control | Esquema por función, tablas en `MAYÚSCULAS`, SP `usp_` | `meta.ENTITY`, `log.usp_END_RUN` |
| Tablas Delta | Esquema por caso, tabla en `minúsculas` | `perfil.columna`, `agente.eval_historial` |

### 1.3. Dónde vive cada cosa

| Pieza | Dónde | Casos |
|---|---|---|
| Datos (bronze, silver, gold) | `LH_MEDALLION`, esquemas `bronze`, `silver`, `gold` | MDP, PRF, AGT |
| Archivos de trabajo | `Files/<area>/<objeto>/...` en el lakehouse por defecto del notebook | `Files/landing/<entidad>/<run_id>/`, `Files/perfil/<origen>/`, `Files/doc_modelos/<modelo>/`, `Files/doc_modelos/<modelo>/perf/<corrida>/`, `Files/agente/<AGENTE>/` |
| Configuración y estado | SQL database de control, esquemas `meta` y `log` | MDP (y PRF, que escribe en `meta`) |
| Secretos | Azure Key Vault, leídos con `notebookutils.credentials.getSecret` | DOC (opción B) |

### 1.4. Reglas que comparten todos los casos

- Claude **no escribe** en la base de control, el lakehouse ni el modelo publicado: genera archivos y scripts que una persona revisa y corre.
- Todo notebook que escribe tiene `DRY_RUN = True` por defecto o escribe solo en su propio esquema.
- Lo aprobado se marca en un CSV (`revisado = si`, `aprobada = si`, `estado = VALIDADA`). Lo que dice `[dato a confirmar]` no se carga.
- Nada de PII fuera de bronze: ni en perfiles, ni en rechazos, ni en gold, ni en las vistas del agente.
- Cada README dice qué está probado y qué no.

## 2. Desvíos detectados

Ordenados por impacto. "Esfuerzo" es una estimación gruesa.

| # | Desvío | Dónde | Por qué importa | Corrección propuesta | Esfuerzo |
|---|---|---|---|---|---|
| 1 | **El banco de preguntas y el historial de evaluaciones están en el mismo esquema que las vistas del agente** (`agente.banco_preguntas`, `agente.eval_historial` junto a `agente.ventas`) | `NB_AGT_01`, `NB_AGT_03`, `01_vistas_agente.sql` | El script sugiere `GRANT SELECT ON SCHEMA::agente` a los usuarios del agente. Con eso pueden leer las **respuestas esperadas** de la evaluación, y si alguien selecciona esas tablas en el data agent, la evaluación mide memoria | Mover las tablas de control a un esquema propio (`agente_ctl`) y dejar `agente` solo para vistas de negocio | Bajo |
| 2 | **Tablas Delta sin esquema** | `doc_diccionario` (`NB_DOC_03`), `perf_bpa`, `perf_vertipaq_tablas`, `perf_vertipaq_columnas`, `perf_mediciones`, `perf_comparacion` (`NB_PERF_*`) | En un lakehouse con esquemas caen en `dbo`, mezcladas con cualquier otra cosa. Los demás casos usan su esquema (`perfil.*`, `agente.*`) | `doc.diccionario` y `perf.<tabla>`, con `CREATE SCHEMA IF NOT EXISTS` | Bajo |
| 3 | **Notebooks sin celda de parámetros marcada** | `NB_DOC_01..03`, `NB_PERF_01..03`, `NB_Workspace_inventory_v2` | No se pueden llamar desde un pipeline o `runMultiple` pasando `MODELO`, `WORKSPACE` o `CORRIDA`: hay que editarlos. Los de MDP, PRF y AGT sí la tienen | Marcar la primera celda de configuración con el tag `parameters` | Bajo |
| 4 | **Versión de semantic-link-labs distinta en dos casos encadenados** | `NB_DOC_01/03` instala sin versión; `NB_PERF_01/02` fija `0.17.1` | `Performance` lee el `modelo.json` que genera `NB_DOC_01`. Si una versión nueva cambia nombres de columnas, `DOC` cambia de formato sin aviso | Fijar `semantic-link-labs==0.17.1` en `DOC` y subirla en los dos casos a la vez | Bajo |
| 5 | **Dos bases de control** | Inventario usa `config.*` en la SQL database que ya existe (el README de MDP la nombra `DB_TDM_Platform`); MDP propone crear otra, `DB_MDP_CONTROL`, para `meta.*` y `log.*` | El inventario de items y la metadata del pipeline describen la misma plataforma, pero no se pueden cruzar (por ejemplo, qué pipeline o lakehouse de `config.DOMAIN_OBJECTS` usa cada entidad) | **Decisión:** una sola SQL database de control con esquemas `config`, `meta` y `log`, o dejarlas separadas a propósito y decirlo en los README | Medio |
| 6 | **Inventario_Workspace no sigue la estructura** | Notebook en la raíz, nombre `NB_Workspace_inventory_v2`, sin `notebooks/`, sin `pruebas/` ni skill | Es el primer caso y quedó con el formato anterior a las convenciones | Mover a `notebooks/NB_INV_01_sincronizar_items.ipynb` y sumar una prueba local de la guardia de filas mínimas. La skill no hace falta | Bajo |
| 7 | **`PATRONES_SENSIBLES` copiada en dos notebooks** | `NB_DOC_01` y `NB_PRF_01` (hoy idénticas) | Si se agrega un patrón en uno solo, una columna es PII para el perfil y no para el diccionario, o al revés | Fuente única: `Files/comun/patrones_sensibles.json` leído por los dos, con la lista actual como valor por defecto | Bajo |
| 8 | **Artefactos de instancia dentro del repo de frameworks** | `DOC` dice copiar el diccionario a `modelos/<modelo>/` de este repo; `AGT` dice `agentes/AG_VENTAS/` | Mezcla plantillas reutilizables con datos de un cliente o modelo concreto. Esas carpetas tampoco existen | **Decisión:** un repo aparte por implementación (recomendado) o una carpeta `instancias/` con su propio README | Bajo |
| 9 | **Lakehouse sin nombre en DOC y PERF** | "Lakehouse por defecto" | Los demás casos usan `LH_MEDALLION`. No queda claro si el diccionario y las mediciones van al mismo lakehouse que gold | Decir explícitamente `LH_MEDALLION` (esquemas `doc` y `perf`) o un lakehouse de plataforma aparte | Bajo |
| 10 | **Pruebas locales sin un punto de entrada común ni CI** | Cada `pruebas/prueba_local.py` tiene sus requisitos (Spark y Delta en MDP y PRF, solo pandas en PERF, `mcp` en AGT) | Nadie se entera si un cambio en un caso rompe otro (por ejemplo, el formato de `CONFIG_JSON` que comparten MDP y PRF) | Un workflow de GitHub Actions que corra las cuatro pruebas en cada PR | Medio |
| 11 | Nombres de carpeta con criterios mezclados | `Documentar_` (verbo), `Performance_`, `Perfilado_` (sustantivo), `Agente_` | Estético: cuesta adivinar el nombre de un caso nuevo | **No renombrar**: rompe enlaces externos (por ejemplo desde el repo Agentes). Para los casos nuevos, usar `Objeto_Accion` o el criterio que se elija | — |

### Lo que está bien y conviene mantener

- La secuencia entre casos está bien encadenada: Perfilado alimenta la metadata de MDP y valida con el mismo `CONFIG_JSON`; Performance reusa `modelo.json` y la carpeta de Documentar; el Agente lee gold sin PII.
- Las cinco skills tienen `name` y `description` con el "usar cuando" y siguen el mismo formato.
- Todos los README separan lectura, escritura y cambios con impacto, y dicen qué no está probado en Fabric real.

## 3. Cómo aplicar las correcciones

Propuesta en dos PR, para revisar por separado:

1. **PR de bajo riesgo** (desvíos 1, 2, 3, 4, 6, 7, 9): cambios de nombres de tablas, tags y versiones, con las pruebas locales corridas antes y después.
2. **Decisiones** (desvíos 5 y 8): primero acordar el criterio, después el cambio.

El desvío 10 (CI) puede ir junto con el framework de CI/CD propuesto en [frameworks_propuestos.md](frameworks_propuestos.md).
