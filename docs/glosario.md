# Glosario

**En corto:** los términos que se repiten en el repo, en una línea cada uno y en orden alfabético. Si un término de un caso no está acá, lo define el README de ese caso.

| Término | Qué es en este repo |
|---|---|
| Base de control | SQL database de Fabric con la configuración y el registro de todos los casos (esquemas `config`, `meta`, `log`, `mon`, `dq`, `cat`). Una por ambiente, por ejemplo `DB_TDM_Platform` |
| Bronze, silver, gold | Capas del lakehouse (arquitectura medallion). Bronze: copia del origen sin cambios. Silver: datos limpios, tipados y con claves. Gold: modelo para consumir (hechos y dimensiones) |
| CLS | *Column-level security*: ocultar columnas (por ejemplo PII) a un grupo de usuarios |
| `CONFIG_JSON` | Configuración de una corrida que arma `meta.usp_GET_RUN_CONFIG` y leen los notebooks del pipeline |
| DES, TEST, PRD | Ambientes de desarrollo, prueba y producción. Todo se arma en DES y llega a TEST y PRD por PR |
| Direct Lake | Modo de un modelo semántico que lee las tablas Delta del lakehouse sin importarlas |
| fabric-cicd | Librería de Microsoft que despliega items de Fabric desde un repo Git, usada en `Despliegue_Entre_Ambientes` |
| Lakehouse | Item de Fabric con tablas Delta y archivos. Acá, `LH_MEDALLION` |
| MCP | *Model Context Protocol*: estándar para que un agente (Claude, Copilot) use herramientas externas. Ver [conceptos de agentes](../Agentes_Data_Analytics/conceptos_agentes.md) |
| Metadata-driven | El pipeline no tiene una actividad por tabla: lee qué cargar de `meta.*` y se repite por cada entidad |
| Modelo semántico | Modelo de Power BI (tablas, relaciones, medidas) sobre gold que usan los reportes y el agente de datos |
| OIDC | Login de GitHub Actions contra Azure sin guardar secretos, usado para desplegar |
| `parameter.yml` | Archivo de fabric-cicd que reemplaza los IDs de DES por los de cada ambiente |
| PBIP, TMDL | Formato de proyecto de Power BI en carpetas (PBIP) y lenguaje de texto del modelo (TMDL). Permiten versionar y revisar el modelo por PR |
| PII | Datos personales (nombre, documento, correo, teléfono). Se detectan con `Comun/patrones_sensibles.json` y no llegan a las vistas del agente |
| RLS | *Row-level security*: cada grupo ve solo sus filas (por ejemplo, su región) |
| SCD tipo 2 | Historia de una dimensión: cada cambio abre una fila nueva con vigencia (`_valid_from`, `_valid_to`, `_is_current`) |
| Skill | Instrucciones empaquetadas (`SKILL.md` + plantillas) que Claude carga cuando la tarea coincide con su descripción. Ver el [catálogo](catalogo_skills.md) |
| Watermark | Último valor cargado de un origen incremental (`WATERMARK_VALUE`), para traer solo lo nuevo |
| Workspace | Espacio de Fabric que agrupa items (lakehouse, notebooks, pipelines, modelos). Uno por ambiente |
