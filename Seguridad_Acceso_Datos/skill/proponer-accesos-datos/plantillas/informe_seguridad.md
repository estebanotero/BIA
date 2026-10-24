# Accesos a los datos · <ambiente> · <AAAA-MM-DD>

**Veredicto:** OK | CORREGIR | CRÍTICO
**Relevamiento:** `relevamiento.json` del <fecha> · <n> objetos · <n> columnas PII · <n> hallazgos (ALTA <n> · MEDIA <n> · BAJA <n>)

<Una o dos frases: el riesgo principal y qué se propone.>

## Grupos propuestos

| Grupo de Entra ID | Para quién | Workspace | Lee | PII | Dueño que aprueba |
|---|---|---|---|---|---|
| `grp-...` | | | | | `[dato a confirmar]` |

## PII

| Objeto | Columnas PII (motivo) | ¿Debería estar ahí? | Propuesta | Etiqueta |
|---|---|---|---|---|

Excepciones revisadas (no son PII): `esquema.tabla.columna`: motivo.

## RLS

| Tabla | Columna | Grupo | Valores | Dónde (endpoint, modelo) |
|---|---|---|---|---|

## Hallazgos

| # | Severidad | Código | Objeto | Qué hacer | Responsable |
|---|---|---|---|---|---|

## Cambios con impacto

| Cambio | A quién afecta | Cómo avisar | Vuelta atrás |
|---|---|---|---|
| Bajar un rol de workspace | | | Volver a asignarlo |
| Aplicar RLS | Todos los que leen la tabla por el endpoint | | `DROP SECURITY POLICY` (al final del script) |

## Próximos pasos

1. <acción, responsable>
