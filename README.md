# BIA: Ingeniería y Arquitectura de Datos

Frameworks reutilizables para **Ingeniería** y **Arquitectura de Datos** sobre Microsoft Fabric, con Claude como asistente en cada paso. Cada caso tiene su carpeta con el contexto, las decisiones, los artefactos (SQL, notebooks, skills) y cómo validarlo y operarlo.

El patrón es el mismo en todos: **un notebook deja los datos listos, Claude trabaja con una skill, una persona revisa y un notebook carga solo lo aprobado.** Claude no escribe directo en la base de control, el lakehouse ni el modelo publicado.

Además, [Agentes_Data_Analytics/](Agentes_Data_Analytics/README.md) junta lo de los agentes del equipo (BIA Time Agent, Ayudin), que es un tema aparte.

## Empezá acá

| Querés… | Leé |
|---|---|
| Entender cómo encajan todos los casos | [Arquitectura](docs/arquitectura.md) y el [glosario](docs/glosario.md) |
| Traer un origen nuevo hasta gold | [Perfilar un origen](Perfilado_Origen_Medallion/README.md), después [Pipeline medallion](Pipeline_Metadata_Medallion/README.md) (la secuencia completa está en [Arquitectura](docs/arquitectura.md#2-secuencia-recomendada-para-un-origen-nuevo)) |
| Saber qué skill de Claude usar | [Catálogo de skills](docs/catalogo_skills.md) |
| Sumar o cambiar un caso | [Convenciones](docs/convenciones.md) |
| Saber qué está probado | [Estado de prueba](docs/estado_pruebas.md) |
| Entender agentes, MCP y skills, o BIA Time Agent | [Agentes de Data Analytics](Agentes_Data_Analytics/README.md) |

## Casos de datos

### Plataforma

| Caso | Para qué | Prefijo | Skill de Claude |
|---|---|---|---|
| [Inventario de un workspace](Inventario_Workspace/README.md) | Sincronizar los items de uno o más workspaces con la base de control (staging + `MERGE`, IDs estables y bajas lógicas) | `NB_INV_` | — |
| [Desplegar entre ambientes (CI/CD)](Despliegue_Entre_Ambientes/README.md) | Llevar lo que se arma en DES a TEST y PRD: repo por implementación, `parameter.yml`, migraciones de la base de control y GitHub Actions con fabric-cicd y aprobación para PRD | — | `revisar-despliegue-fabric` |
| [Monitorear la plataforma](Monitoreo_Plataforma/README.md) | Juntar el estado de todos los casos en el esquema `mon`, abrir y cerrar alertas con reglas fijas (fallas, SLA, calidad, volumen, agente, performance), avisar por un solo canal y armar el parte diario | `NB_MON_` | `diagnosticar-plataforma` |
| [Catálogo y linaje](Catalogo_Linaje/README.md) | Unir inventario, metadata, perfil y modelos en un grafo origen → bronze → silver → gold → modelo → reporte: impacto de un cambio, procedencia de un número, dueños, y hallazgos como dependencias faltantes o PII que llega a gold | `NB_CAT_` | `explorar-linaje` |
| [Seguridad y acceso a los datos](Seguridad_Acceso_Datos/README.md) | Decidir quién ve qué con una matriz aprobada por el dueño de los datos y generar los permisos: `GRANT` por objeto o sin columnas PII (CLS), RLS en el SQL endpoint y roles RLS en TMDL. Relevar PII y roles reales contra la matriz | `NB_SEG_` | `proponer-accesos-datos` |

### Datos: del origen a gold

| Caso | Para qué | Prefijo | Skill de Claude |
|---|---|---|---|
| [Perfilar un origen](Perfilado_Origen_Medallion/README.md) | Conocer el origen con datos (claves, tipos reales, nulos, relaciones, PII) y convertir ese perfil en el diseño de silver y gold y en la metadata del pipeline | `NB_PRF_` | `disenar-medallion-desde-perfil` |
| [Pipeline metadata-driven medallion](Pipeline_Metadata_Medallion/README.md) | Cargar bronze, silver y gold con un solo pipeline y cuatro notebooks, según una base de control en SQL. Incluye historia (SCD tipo 2) y bajas del origen | `NB_MDP_` | `metadata-medallion` |
| [Calidad y reconciliación](Calidad_Reconciliacion/README.md) | Controlar gold después de cada carga: cuadre entre capas por período, hechos sin dimensión, frescura y reglas de negocio. Si una regla grave falla, el pipeline frena antes de refrescar el modelo | `NB_CAL_` | `proponer-reglas-calidad` |

### Consumo: modelo semántico y agente

| Caso | Para qué | Prefijo | Skill de Claude |
|---|---|---|---|
| [Documentar un modelo semántico](Documentar_Modelo_Semantico/README.md) | Extraer la estructura y una muestra del modelo, redactar el diccionario con Claude y cargar las descripciones revisadas | `NB_DOC_` | `documentar-modelo-semantico` |
| [Performance de un modelo semántico PBIP](Performance_Modelo_Semantico/README.md) | Medir, proponer y aplicar optimizaciones en TMDL por PR, y comparar antes y después | `NB_PERF_` | `optimizar-modelo-semantico` |
| [Agente de datos en Fabric](Agente_Datos_Fabric/README.md) | Un Fabric data agent sobre gold que Claude usa por MCP, con mejora continua a partir de preguntas validadas por cada área | `NB_AGT_` | `agente-datos-fabric` |

## Documentos transversales

| Documento | Qué tiene |
|---|---|
| [Arquitectura](docs/arquitectura.md) | Diagrama de cómo se conectan los casos, secuencia para un origen nuevo y qué pieza comparte cada uno |
| [Catálogo de skills](docs/catalogo_skills.md) | Las diez skills de datos: qué hace cada una, en qué situación usarla, cuáles se confunden y cómo se encadenan. Suma las de BIA Time Agent |
| [Convenciones](docs/convenciones.md) | Estructura de carpetas, nombres, rutas del lakehouse, una sola base de control y dónde van los artefactos de cada implementación |
| [Glosario](docs/glosario.md) | Los términos que se repiten en todo el repo, en una línea cada uno |
| [Estado de prueba](docs/estado_pruebas.md) | Qué está probado localmente y qué falta probar en Fabric real |
| [Frameworks propuestos](docs/frameworks_propuestos.md) | Lo que falta para producción (costos y capacidad), priorizado |

## Estructura

```text
BIA/
├── README.md                      esta portada
├── docs/                          lo que cruza todos los casos (arquitectura, catálogo, convenciones, glosario)
├── Comun/                         patrones_sensibles.json
├── <Caso>/                        11 casos: sql/ · notebooks/ · skill/ · pruebas/ (ver convenciones)
├── Agentes_Data_Analytics/        conceptos, bia-da-agentic y BIA_Time_Agent/
└── .github/workflows/pruebas.yml  pruebas locales en cada PR
```

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
