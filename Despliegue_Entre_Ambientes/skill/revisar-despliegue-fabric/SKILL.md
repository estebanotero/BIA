---
name: revisar-despliegue-fabric
description: Revisa un PR del repo de una implementación de Microsoft Fabric antes de que se despliegue a TEST y PRD con fabric-cicd. Clasifica los items y migraciones que cambian, detecta IDs de DES sin parametrizar, cambios con impacto en la base de control y riesgos de datos, y arma el checklist de despliegue con su vuelta atrás. También diagnostica un despliegue fallido a partir del log de GitHub Actions. Usar cuando se pida revisar un PR de Fabric, preparar un pase a producción, completar parameter.yml o entender por qué falló el workflow Desplegar.
---

# Revisar un despliegue de Fabric

Trabajás sobre el repo de una implementación armado con la plantilla de `Despliegue_Entre_Ambientes` del repo BIA:

```text
workspace/     items de Fabric exportados por la integración Git (carpetas <Nombre>.<Tipo>/) + parameter.yml
sql/           migraciones NNN_descripcion.sql de la base de control
deploy/        validar.py, aplicar_sql.py, desplegar_items.py
```

Reglas que no cambian:

- **No desplegás ni aprobás.** Leés el diff, corrés `python deploy/validar.py` si podés, y entregás un informe. El despliegue lo dispara el merge y PRD lo aprueba una persona en el environment de GitHub.
- No pidas ni escribas IDs de conexión con credenciales, secretos ni connection strings con password. Si aparece uno en el diff, es un hallazgo **bloqueante**.
- Si no podés saber algo desde el repo (por ejemplo, el ID de un lakehouse en PRD), escribí `[dato a confirmar]`.

## Tarea A. Revisar un PR

Entrada: el diff del PR (o `git diff main...HEAD`) y, si está, la salida de `validar.py`.

1. **Inventario del cambio.** Tabla con cada item o migración tocado: tipo (`Notebook`, `DataPipeline`, `Lakehouse`, `SemanticModel`, `Report`, `VariableLibrary`, migración SQL), acción (nuevo, modificado, borrado, renombrado) y caso de BIA al que pertenece si se reconoce por el prefijo (`NB_MDP_`, `NB_PRF_`, `NB_DOC_`, `NB_PERF_`, `NB_AGT_`, `NB_INV_`).
2. **Parametrización.** Buscá GUID nuevos en los archivos de items (salvo `logicalId` de `.platform`). Para cada uno decí qué es (workspace, lakehouse, conexión, modelo) mirando la clave que lo contiene (`default_lakehouse`, `default_lakehouse_workspace_id`, `connection`, `workspaceId`, `artifactId`) y proponé la entrada de `parameter.yml`:
   - Workspace → `$workspace.$id`.
   - Item del mismo workspace → `$items.<Tipo>.<Nombre>.$id` (o `$sqlendpoint` para el endpoint SQL).
   - Conexión → un ID por ambiente: las conexiones no son items, se crean en *Manage connections and gateways*.
   - Servidores y nombres escritos en notebooks (`SQL_SERVER`, rutas `abfss://`) → `find_replace` con el valor de DES.
3. **Migraciones.** Para cada archivo nuevo de `sql/`:
   - Nombre `NNN_descripcion.sql` y número siguiente al último.
   - Idempotente o no. Si lo es (crea solo lo que falta, `CREATE OR ALTER`), sugerí la marca `-- repetible`.
   - Cambios con impacto (`DROP TABLE/SCHEMA`, `TRUNCATE`, `sp_rename`, `DELETE` o `UPDATE` sin `WHERE` acotado, cambio de tipo de columna, `WATERMARK_VALUE = NULL`): exigí la marca `-- impacto: <motivo y vuelta atrás>` y un backup previo en el mismo script.
   - Una migración ya aplicada **no se edita**: si el diff modifica una, es bloqueante.
4. **Riesgos de datos.** Señalá explícitamente:
   - Borrado o renombre de un `Lakehouse` o de tablas que leen otros items (fabric-cicd no borra lakehouses, pero un renombre crea uno nuevo vacío).
   - Cambios en `meta.ENTITY` que reinician watermarks o pasan una entidad a `OVERWRITE`.
   - Vistas `agente.*` que exponen columnas nuevas: ¿son PII?
   - Cambios en modelos semánticos que pisan descripciones cargadas por XMLA (ver `Documentar_Modelo_Semantico`).
5. **Orden.** Las migraciones corren antes que los items. Si un notebook o pipeline nuevo usa un SP o tabla que crea una migración del mismo PR, está bien. Si es al revés (la migración borra algo que un item publicado todavía usa), proponé partir el cambio en dos PR.
6. **Informe.** Completá [`plantillas/checklist_despliegue.md`](plantillas/checklist_despliegue.md): veredicto (`LISTO`, `LISTO CON CONDICIONES`, `BLOQUEADO`), hallazgos ordenados por severidad, entradas de `parameter.yml` propuestas, pasos manuales antes y después, y la vuelta atrás.

## Tarea B. Diagnosticar un despliegue fallido

Entrada: el log del job que falló en GitHub Actions.

| Dónde falló | Causa típica | Qué proponer |
|---|---|---|
| `azure/login` | Falta la credencial federada para ese environment, o `AZURE_CLIENT_ID`/`AZURE_TENANT_ID` mal cargados | Revisar el *subject* de la credencial federada: `repo:<org>/<repo>:environment:<TEST o PRD>` |
| `validar.py --estricto` | GUID de DES sin parametrizar | La entrada de `parameter.yml` (tarea A, paso 2) |
| `aplicar_sql.py` antes de ejecutar | Migración editada después de aplicarse, número repetido, falta marca de impacto | Archivo nuevo en lugar de editar; marca y backup |
| `aplicar_sql.py`, "lote N" | Error de T-SQL o permisos | Si es permisos: la identidad necesita usuario en la base y rol `db_ddladmin` + `db_datawriter` [verificar el mínimo]. Nada quedó a medias: el archivo corre en una transacción |
| Token de la base | Scope o permisos de la identidad | El scope está como `[verificar]` en `aplicar_sql.py` |
| `desplegar_items.py` | Item que referencia otro que no existe en el destino, `$items...` de un item que no está en el repo, o la identidad sin rol en el workspace | Agregar el item, corregir el nombre, o dar rol **Contributor** al service principal en el workspace |

Respondé con: qué falló, la causa más probable con la línea del log que la muestra, el cambio exacto y si se puede volver a correr el workflow sin riesgo (las migraciones aplicadas no se repiten; los items se vuelven a publicar igual).
