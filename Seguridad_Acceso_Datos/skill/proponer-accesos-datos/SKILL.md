---
name: proponer-accesos-datos
description: Propone y revisa la matriz de accesos de una plataforma de datos en Microsoft Fabric armada con los casos de BIA, con roles de workspace, lectura por capa, columnas PII (CLS) y filtros por fila (RLS), a partir del relevamiento de NB_SEG_01. También revisa los scripts que genera NB_SEG_02 y prepara la revisión periódica de accesos. Usar cuando se pida definir quién ve qué, proteger PII, armar RLS, revisar permisos o preparar una auditoría de accesos.
---

# Proponer y revisar accesos a los datos

Trabajás sobre el caso `Seguridad_Acceso_Datos/` del repo BIA. `NB_SEG_01_relevar_accesos` dejó `relevamiento.json`: objetos del SQL analytics endpoint, columnas PII con su motivo, roles del workspace, permisos SQL vigentes y hallazgos. Tu trabajo es proponer **quién ve qué** en dos CSV que una persona aprueba; `NB_SEG_02` los convierte en scripts.

Reglas que no cambian:

- **No das ni quitás permisos.** Proponés filas con `aprobada = no`. Las aprueba el dueño de los datos y los scripts los corre una persona, primero en DES.
- **Siempre grupos de Entra ID, nunca personas.** Si alguien pide acceso para una persona, proponé el grupo al que debería pertenecer.
- **Mínimo privilegio.** Ante la duda, menos acceso y una nota con la pregunta. Nadie de negocio necesita bronze ni rol de workspace en PRD.
- **PII fuera de gold y de `agente`.** Si aparece, el hallazgo es sacarla del objeto, no esconderla con permisos.
- No pidas, copies ni escribas valores de datos (ni de ejemplo): solo nombres de objetos y columnas. Nada de credenciales.
- Lo que no se puede saber desde el relevamiento (quién es el dueño, qué grupo existe en Entra ID) va como `[dato a confirmar]`; esas filas no se pueden aprobar.

## A. Proponer la matriz

Entrada: `relevamiento.json` y, si existe, la matriz actual.

1. **Grupos.** Partí de este modelo y adaptalo a lo que te cuenten:

   | Grupo | Workspace DES | Workspace PRD | Lee | PII |
   |---|---|---|---|---|
   | Plataforma (2-3 personas) | Admin | Admin | todo | sí |
   | Ingeniería de datos | Contributor | Viewer o ninguno (despliega el CI/CD) | bronze, silver, gold | sí |
   | Analistas | ninguno | ninguno | silver, gold | no |
   | Negocio por área | ninguno | ninguno | `agente` y el modelo semántico (permiso del item) | no |
   | Identidad del CI/CD y de los pipelines | Contributor | Contributor | — | — |

   Las identidades técnicas van en `IDENTIDADES_TECNICAS` del notebook, no en la matriz.
2. **Lectura.** Una fila `LECTURA` por grupo y esquema (`gold`) o por objeto (`gold.fact_ventas`) cuando solo necesita algunos. `ve_pii = si` solo con un motivo en `notas` (operación, cumplimiento). `NB_SEG_02` genera `GRANT` por objeto y, sin PII, por columnas: no hace falta listar columnas.
3. **RLS.** Solo si el negocio pide que cada área vea su parte. Una fila por grupo y tabla en `matriz_rls.csv`:
   - `tabla_sql` para el endpoint (lo que lee el agente) y `tabla_modelo` para el modelo semántico (TMDL). Pueden ir las dos.
   - `valores` separados por coma, o `*` para los grupos que ven todo. **Todo grupo que lee esa tabla tiene que tener su fila**: el que no figura deja de ver filas.
   - Si el filtro depende de una tabla de asignación por usuario (RLS dinámico con `USERPRINCIPALNAME()`), proponelo en el informe como paso aparte: el notebook genera solo filtros fijos.
4. **PII revisada.** Para cada columna marcada por **nombre** (no por metadata), decí si es PII o no. Las que no lo son (`nombre_producto`, `nombre_sucursal`) van a `EXCEPCIONES_PII` del notebook, con el motivo en el informe.
5. **Etiquetas de sensibilidad.** Proponé una por objeto: *Confidencial* si tiene PII, *General* si no [verificar los nombres de etiquetas del tenant]. Se aplican a mano o con la integración de Purview; no las generes como script.
6. **Entregá** `matriz_accesos.csv` y `matriz_rls.csv` con las plantillas, y el informe con [`plantillas/informe_seguridad.md`](plantillas/informe_seguridad.md).

## B. Revisar los scripts generados

Entrada: la carpeta `Files/seguridad/scripts/<AMBIENTE>_<sello>/`.

- `permisos_lectura.sql`: ningún `GRANT` de objeto completo a un grupo con `ve_pii = no` sobre un objeto con PII. Columnas omitidas que el grupo necesita de verdad: proponé sacar la PII del objeto o una vista sin ella.
- `rls_sql_endpoint.sql`: cada tabla con política tiene su grupo de ingeniería con `*`. Avisá que la política afecta a todos los que leen por el endpoint, incluido el data agent si consulta con la identidad del usuario [verificar].
- `roles/*.tmdl`: un rol por grupo y el filtro sobre la tabla de dimensión cuando existe (filtra los hechos por la relación). Los miembros se asignan en el servicio.
- Que esté la vuelta atrás y que el orden sea: DES, validar con un usuario de cada grupo, PRD.

## C. Revisión periódica de accesos

Entrada: `relevamiento.json` reciente. Clasificá cada hallazgo (`SEG_*`) en: corregir ya (ALTA), corregir en la próxima ventana (MEDIA), aceptar con justificación (con quién y hasta cuándo). Personas con rol directo y grupos fuera de matriz son siempre "corregir". Cerrá con el responsable de cada acción.

## Hallazgos que genera NB_SEG_01

| Código | Qué significa |
|---|---|
| `SEG_PII_EN_AGENTE` / `SEG_PII_EN_GOLD` | Columnas que parecen PII en capas que no deberían tenerla |
| `SEG_WS_DEMASIADOS_ADMIN`, `SEG_WS_USUARIO_INDIVIDUAL`, `SEG_WS_FUERA_DE_MATRIZ`, `SEG_WS_ROL_DE_MAS`, `SEG_WS_FALTA_ROL` | Roles del workspace contra la matriz |
| `SEG_SQL_PII_EXPUESTA` | Un grupo sin PII tiene `SELECT` sobre el objeto entero o sobre columnas PII |
| `SEG_SQL_PERMISO_DE_MAS`, `SEG_SQL_PERMISO_ESQUEMA`, `SEG_SQL_PERMISO_FALTANTE` | Permisos del endpoint que no salen de la matriz, a nivel esquema o que faltan |

## Salida

El informe con la plantilla, los dos CSV y **Próximos pasos** con responsable. Si el relevamiento no muestra problemas, decilo en una línea y listá solo lo que no se pudo revisar (por ejemplo, permisos de items compartidos o del modelo semántico, que `NB_SEG_01` no lee).
