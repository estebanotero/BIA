# Plantilla del repo de una implementación

Copiá el contenido de esta carpeta a la raíz de un repo nuevo (por ejemplo `TDM_Platform`). Es el repo que se conecta al workspace de DES y que despliega a TEST y PRD. La guía completa está en el [README del caso](../README.md).

```text
<implementacion>/
├── .github/workflows/
│   ├── ci.yml                    En cada PR: validar.py (sin credenciales)
│   ├── desplegar.yml             Merge a main → TEST → (aprobación) → PRD
│   └── _desplegar_ambiente.yml   Pasos de un ambiente: login, validar, migraciones, items
├── deploy/
│   ├── requirements.txt          fabric-cicd 1.4.0, azure-identity, pyodbc, PyYAML
│   ├── validar.py                parameter.yml, GUID sin parametrizar, secretos, reglas de sql/
│   ├── aplicar_sql.py            Migraciones de la base de control, con registro en log.MIGRACION
│   └── desplegar_items.py        Publica los items con fabric-cicd
├── workspace/                    Carpeta Git del workspace de DES (items <Nombre>.<Tipo>/)
│   └── parameter.yml             Reemplazos de DES a TEST y PRD
├── sql/                          NNN_descripcion.sql
├── origenes/<origen>/            diseno_<origen>.md (Perfilado_Origen_Medallion)
├── modelos/<modelo>/             diccionario.md, informe_perf.md
└── agentes/<AGENTE>/             instrucciones_agente.md, banco_preguntas.csv
```

## Primeras migraciones

Sugeridas, copiadas de BIA y con la marca `-- repetible` en la primera línea porque son idempotentes:

| Archivo | Origen en BIA |
|---|---|
| `sql/001_ddl_control.sql` | `Pipeline_Metadata_Medallion/sql/01_ddl_control.sql` |
| `sql/002_ddl_inventario.sql` | Pasos 1, 2 y 5 de `Inventario_Workspace/sql/01_ddl_domain_objects.sql` (staging, tabla con `IDENTITY` creada directo con su nombre final, y el SP). El backup, la copia y el swap (pasos 0, 3 y 4) solo aplican en DES, donde ya existe la tabla vieja, y se corren a mano una vez |
| `sql/003_alta_<origen>.sql` | Lo que genera la skill `disenar-medallion-desde-perfil` |

Las vistas `agente.*` no van en `sql/`: se crean en el SQL analytics endpoint del lakehouse, no en la base de control.
