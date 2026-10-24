# BIA: Ingeniería y Arquitectura de Datos

Frameworks reutilizables para **Ingeniería** y **Arquitectura de Datos** sobre Microsoft Fabric, con Claude como asistente en cada paso. Cada caso tiene su carpeta con el contexto, las decisiones, los artefactos (SQL, notebooks, skills) y cómo validarlo y operarlo.

El patrón es el mismo en todos: **un notebook deja los datos listos, Claude trabaja con una skill, una persona revisa y un notebook carga solo lo aprobado.** Claude no escribe directo en la base de control, el lakehouse ni el modelo publicado.

## Índice

### Plataforma

| Caso | Para qué | Prefijo | Skill de Claude |
|---|---|---|---|
| [Inventario de un workspace](Inventario_Workspace/README.md) | Sincronizar los items de uno o más workspaces con la base de control (staging + `MERGE`, IDs estables y bajas lógicas) | `NB_INV_` | — |

### Datos: del origen a gold

| Caso | Para qué | Prefijo | Skill de Claude |
|---|---|---|---|
| [Perfilar un origen](Perfilado_Origen_Medallion/README.md) | Conocer el origen con datos (claves, tipos reales, nulos, relaciones, PII) y convertir ese perfil en el diseño de silver y gold y en la metadata del pipeline | `NB_PRF_` | `disenar-medallion-desde-perfil` |
| [Pipeline metadata-driven medallion](Pipeline_Metadata_Medallion/README.md) | Cargar bronze, silver y gold con un solo pipeline y cuatro notebooks, según una base de control en SQL | `NB_MDP_` | `metadata-medallion` |

### Consumo: modelo semántico y agente

| Caso | Para qué | Prefijo | Skill de Claude |
|---|---|---|---|
| [Documentar un modelo semántico](Documentar_Modelo_Semantico/README.md) | Extraer la estructura y una muestra del modelo, redactar el diccionario con Claude y cargar las descripciones revisadas | `NB_DOC_` | `documentar-modelo-semantico` |
| [Performance de un modelo semántico PBIP](Performance_Modelo_Semantico/README.md) | Medir, proponer y aplicar optimizaciones en TMDL por PR, y comparar antes y después | `NB_PERF_` | `optimizar-modelo-semantico` |
| [Agente de datos en Fabric](Agente_Datos_Fabric/README.md) | Un Fabric data agent sobre gold que Claude usa por MCP, con mejora continua a partir de preguntas validadas por cada área | `NB_AGT_` | `agente-datos-fabric` |

### Transversal

| Documento | Qué tiene |
|---|---|
| [Convenciones](docs/convenciones.md) | Estructura de carpetas, nombres, rutas del lakehouse, una sola base de control, dónde van los artefactos de cada implementación y los desvíos corregidos |
| [Frameworks propuestos](docs/frameworks_propuestos.md) | Lo que falta para llevar esto a producción (CI/CD, monitoreo, seguridad, calidad, SCD2, catálogo, costos), priorizado y sin construir |

## Cómo se conectan los casos

```mermaid
flowchart LR
    SRC[(Origen<br/>SQL o archivos)]

    subgraph CTRL[SQL database de control]
        META[(meta.* · log.*)]
        CFG[(config.DOMAIN_OBJECTS)]
    end

    subgraph LH[LH_MEDALLION]
        B[(bronze)]
        P[(perfil)]
        S[(silver)]
        G[(gold)]
        V[(agente.*<br/>vistas sin PII)]
    end

    SM[(Modelo semántico<br/>PBIP en Git)]
    FDA[Fabric data agent]
    CL{{Claude<br/>+ skills}}

    INV[Inventario_Workspace] --> CFG
    SRC -->|1 · copia exploratoria| B
    B -->|2 · NB_PRF_01/02| P
    P -->|3 · disenar-medallion-desde-perfil| CL
    CL -->|alta_origen.sql, revisado| META
    META -->|4 · NB_PRF_03 ensayo en seco| P
    META -->|5 · PL_MDP_MEDALLION| B --> S --> G
    G --> SM
    SM -->|6 · NB_DOC_01..03| DIC[/diccionario/]
    SM -->|7 · NB_PERF_01..03| PR[/PR con TMDL<br/>e informe/]
    G --> V --> FDA
    SM --> FDA
    DIC -.->|instrucciones| FDA
    FDA -->|8 · MCP| CL
```

### Secuencia recomendada para un origen nuevo

| Paso | Caso | Qué sale | Lo usa |
|---|---|---|---|
| 0 | Pipeline medallion: base de control, lakehouse y pipeline armados en desarrollo | Base de control (`DB_TDM_Platform`), `LH_MEDALLION`, `PL_MDP_MEDALLION` | Todos los pasos siguientes |
| 1 | Perfilado: carga exploratoria (`LOAD_GROUP = exploracion`, `p_layers = bronze`) | Bronze con una copia completa | Paso 2 |
| 2 | Perfilado: `NB_PRF_01` y `NB_PRF_02` | `perfil.*`, `perfil.json`, `resumen_perfil.md` | Paso 3 |
| 3 | Perfilado: skill `disenar-medallion-desde-perfil` | `diseno_<origen>.md`, `alta_<origen>.sql` | Pasos 4 y 5 |
| 4 | Perfilado: `NB_PRF_03` con el `CONFIG_JSON` real | `perfil.validacion` sin bloqueantes | Paso 5 |
| 5 | Pipeline medallion: corrida completa | Silver y gold | Pasos 6 a 8 |
| 6 | Documentar el modelo que lee gold | `modelo.json`, diccionario, descripciones en el modelo | Pasos 7 y 8 |
| 7 | Performance del modelo (reusa `modelo.json`) | PR con cambios TMDL e `informe_perf.md` | El modelo en producción |
| 8 | Agente de datos sobre `agente.*` y el modelo | Agente publicado y evaluado | Negocio, Claude vía MCP |

El inventario es independiente: se puede correr en cualquier momento para tener la lista de items de la plataforma.

### Qué se comparte entre casos

| Pieza | Quién la escribe | Quién la lee |
|---|---|---|
| `meta.ENTITY`, `ENTITY_COLUMN`, `DQ_RULE`, `GOLD_OBJECT` | Perfilado (vía Claude), Pipeline medallion | Pipeline medallion, `NB_PRF_03` |
| `CONFIG_JSON` de `meta.usp_GET_RUN_CONFIG` | Base de control | `NB_MDP_00`, `NB_PRF_03` |
| `bronze.*` | Pipeline medallion | Perfilado, silver |
| `gold.*` | Pipeline medallion | Modelo semántico, vistas `agente.*` |
| `Files/doc_modelos/<modelo>/modelo.json` | `NB_DOC_01` | Skill de documentación, Performance |
| [`Comun/patrones_sensibles.json`](Comun/README.md) (nombres de columna PII) | Una persona, por PR | `NB_DOC_01`, `NB_PRF_01` |
| Base de control: `config.*`, `meta.*`, `log.*` | Inventario, Pipeline medallion, Perfilado | Pipeline medallion, `NB_PRF_03` |

## Estado de prueba

| Caso | Probado localmente | Probado en Fabric real |
|---|---|---|
| Inventario_Workspace | — | No: la versión v2 y el stored procedure sin ejecutar [dato a confirmar] |
| Perfilado_Origen_Medallion | Sí, `pruebas/prueba_local.py` (Spark 3.5.3 + Delta 3.2.1) | No |
| Pipeline_Metadata_Medallion | Sí, notebooks con `pruebas/prueba_local.py` | No: pipeline y stored procedures sin ejecutar |
| Documentar_Modelo_Semantico | — | No |
| Performance_Modelo_Semantico | Sí, lógica de los notebooks | No |
| Agente_Datos_Fabric | Sí, reglas del banco y MCP contra un agente simulado | No: SDK y vistas sin ejecutar |

Probá siempre primero en un workspace de desarrollo.

## Instalar las skills

Cada skill está en `<Caso>/skill/<nombre>/`. Para Claude Code, copiá la carpeta a `.claude/skills/` del proyecto donde trabajás; en claude.ai, subila como skill. Las cinco skills de BIA se pueden instalar juntas: cada una dice en su `description` cuándo usarla.

## Estructura

```text
BIA/
├── README.md
├── docs/
│   ├── convenciones.md
│   └── frameworks_propuestos.md
├── Comun/                         patrones_sensibles.json
├── Inventario_Workspace/          sql/ · notebooks/NB_INV_01
├── Perfilado_Origen_Medallion/    sql/ · notebooks/NB_PRF_01..03 · skill/disenar-medallion-desde-perfil/ · pruebas/
├── Pipeline_Metadata_Medallion/   sql/ · notebooks/NB_MDP_00..30 · skill/metadata-medallion/ · pruebas/
├── Documentar_Modelo_Semantico/   notebooks/NB_DOC_01..03 · skill/documentar-modelo-semantico/
├── Performance_Modelo_Semantico/  notebooks/NB_PERF_01..03 · skill/optimizar-modelo-semantico/ · ci/ · pruebas/
└── Agente_Datos_Fabric/           sql/ · notebooks/NB_AGT_01..03 · mcp/ · skill/agente-datos-fabric/ · pruebas/
```

La estructura de cada carpeta y las convenciones de nombres están en [docs/convenciones.md](docs/convenciones.md).

## Cómo usar este repositorio

1. Empezá por el README del caso: objetivo, requisitos y flujo.
2. Revisá scripts y notebooks antes de correrlos y completá los valores de tu entorno (están marcados como `<...>`).
3. Probá en desarrollo y validá con la sección *Cómo validar* de cada caso antes de pasar a producción.
4. Leé las advertencias de seguridad y de cambios con impacto antes de tocar credenciales o datos reales.

## Convenciones de documentación

- Primero el problema y el resultado esperado, después los pasos técnicos.
- Servicios, permisos, dependencias y configuración necesarios, explícitos.
- Marcadores descriptivos para los valores del entorno; nunca secretos, tokens ni datos sensibles.
- Separar los pasos de lectura, los de escritura y los que modifican o borran datos.
- Validaciones, limitaciones y cómo volver atrás.
- Lo que cambia con el tiempo (precios, límites, previews) marcado como `[verificar]` o `[dato a confirmar]`.

## Alcance y responsabilidad

La documentación es una base de trabajo que debe revisarse frente al entorno, las políticas y las versiones de las herramientas utilizadas. Los ejemplos no reemplazan la revisión técnica ni la aprobación necesaria para ejecutar cambios en ambientes compartidos o productivos.
