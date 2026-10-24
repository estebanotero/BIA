# BIA: Ingeniería y Arquitectura de Datos

Repositorio de documentación técnica y soluciones reutilizables para tareas de
**Ingeniería de Datos** y **Arquitectura de Datos**. Aquí se irán documentando
los trabajos que surjan, junto con sus decisiones, instrucciones y artefactos
para que puedan entenderse, ejecutarse y mantenerse.

## Contenido

| Tema | Descripción |
|---|---|
| Ingeniería de datos | Ingesta, transformación, calidad, almacenamiento, orquestación y operación de datos |
| Arquitectura de datos | Diseño de soluciones, integración, modelado, gobierno, seguridad y decisiones técnicas |
| Casos y procedimientos | Guías paso a paso, scripts, notebooks, diagramas y validaciones asociados a tareas concretas |

### Casos documentados

- [Inventario de items de un workspace de Microsoft Fabric](Inventario_Workspace/README.md): sincronización del inventario con una SQL database, usando staging y `MERGE` para conservar IDs y registrar bajas lógicas.
- [Documentar un modelo semántico de Fabric con Claude](Documentar_Modelo_Semantico/README.md): notebooks que extraen la estructura y una muestra del modelo, una skill para que Claude redacte el diccionario de datos, y la carga revisada de las descripciones en el modelo.
- [Mejorar la performance de un modelo semántico PBIP con Claude](Performance_Modelo_Semantico/README.md): extiende el caso anterior con notebooks que diagnostican el modelo (Vertipaq Analyzer, Best Practice Analyzer, Direct Lake) y miden consultas DAX con traza, una skill para que Claude proponga optimizaciones y las aplique en los archivos TMDL por PR, y la comparación de antes y después.
- [Pipeline metadata-driven medallion en Fabric, con Claude](Pipeline_Metadata_Medallion/README.md): un pipeline y cuatro notebooks cargan bronze, silver y gold según una base de control en SQL; una skill para que Claude genere la metadata de cada origen y diagnostique las corridas.
- [Agente de datos en Fabric, con Claude](Agente_Datos_Fabric/README.md): dónde guardar los datos para el agente (lakehouse, warehouse o modelo semántico), un Fabric data agent que Claude usa vía MCP, y un proceso de mejora continua con preguntas y respuestas validadas por cada área de negocio, que entran al agente como ejemplos e instrucciones y lo miden como evaluaciones.

## Cómo usar este repositorio

1. Empezá por el README del caso para entender el objetivo, los requisitos y el flujo.
2. Revisá los scripts y notebooks antes de ejecutarlos; completá los valores de configuración indicados para tu entorno.
3. Probá los cambios en desarrollo y validá sus efectos antes de aplicarlos en producción.
4. Consultá la sección de seguridad y las advertencias de cada procedimiento antes de manejar credenciales o datos reales.

## Estructura

```text
BIA/
├── README.md
├── Inventario_Workspace/
│   ├── README.md
│   ├── NB_Workspace_inventory_v2.ipynb
│   └── sql/
│       └── 01_ddl_domain_objects.sql
├── Documentar_Modelo_Semantico/
│   ├── README.md
│   ├── notebooks/
│   │   ├── NB_DOC_01_extraer_modelo.ipynb
│   │   ├── NB_DOC_02_redactar_con_claude.ipynb
│   │   └── NB_DOC_03_cargar_y_publicar.ipynb
│   └── skill/
│       └── documentar-modelo-semantico/
│           ├── SKILL.md
│           └── plantillas/
├── Performance_Modelo_Semantico/
│   ├── README.md
│   ├── notebooks/
│   │   ├── NB_PERF_01_diagnosticar.ipynb
│   │   ├── NB_PERF_02_medir_consultas.ipynb
│   │   └── NB_PERF_03_comparar.ipynb
│   ├── skill/
│   │   └── optimizar-modelo-semantico/
│   │       ├── SKILL.md
│   │       ├── catalogo_optimizaciones.md
│   │       └── plantillas/
│   ├── ci/
│   │   └── bpa-pr.yml
│   └── pruebas/
│       └── prueba_local.py
├── Pipeline_Metadata_Medallion/
│   ├── README.md
│   ├── sql/
│   │   ├── 01_ddl_control.sql
│   │   └── 02_ejemplo_metadata.sql
│   ├── notebooks/
│   │   ├── NB_MDP_00_orquestador.ipynb
│   │   ├── NB_MDP_10_bronze.ipynb
│   │   ├── NB_MDP_20_silver.ipynb
│   │   └── NB_MDP_30_gold.ipynb
│   ├── skill/
│   │   └── metadata-medallion/
│   │       ├── SKILL.md
│   │       └── plantillas/
│   └── pruebas/
│       └── prueba_local.py
└── Agente_Datos_Fabric/
    ├── README.md
    ├── sql/
    │   └── 01_vistas_agente.sql
    ├── notebooks/
    │   ├── NB_AGT_01_cargar_banco.ipynb
    │   ├── NB_AGT_02_sincronizar_ejemplos.ipynb
    │   └── NB_AGT_03_evaluar_y_publicar.ipynb
    ├── mcp/
    │   ├── fabric_data_agent_mcp.py
    │   └── requirements.txt
    ├── skill/
    │   └── agente-datos-fabric/
    │       ├── SKILL.md
    │       └── plantillas/
    └── pruebas/
        └── prueba_local.py
```

Cada solución se organiza en una carpeta propia. Cuando sea útil, incluirá:

- `README.md` con contexto, requisitos, pasos y validación.
- Código o scripts ejecutables, con parámetros claramente identificados.
- Notebooks y diagramas relacionados con el caso.
- Advertencias sobre operaciones con impacto y pasos de reversión.

## Convenciones

- Documentar el problema y el resultado esperado antes de los pasos técnicos.
- Indicar servicios, permisos, dependencias y configuración necesaria.
- Usar marcadores descriptivos para valores específicos del entorno; no publicar secretos, tokens ni datos sensibles.
- Diferenciar explícitamente los pasos de lectura, escritura y los que modifican o eliminan datos.
- Incluir validaciones, limitaciones y, cuando corresponda, cómo volver atrás.
- Mantener los nombres de carpetas claros y relacionados con el caso.

## Alcance y responsabilidad

La documentación es una base de trabajo que debe revisarse frente al entorno,
las políticas y las versiones de las herramientas utilizadas. Los ejemplos no
reemplazan la revisión técnica ni la aprobación necesaria para ejecutar cambios
en ambientes compartidos o productivos.
