---
name: review-time-period
description: Revisa las horas cargadas por el colaborador en un día, semana o período y clasifica cada día como vacío, incompleto, completo o llamativo según su jornada mínima, descontando feriados, e indica las licencias que falta cargar en BIA - Absentismo. Señala posibles duplicados. Solo lectura.
---

# Review time period

## Cuándo usarlo

Cuando el colaborador quiera revisar un día, semana o período: conocer sus cargas, saber qué días le faltan cargar, desde cuándo no carga o si tiene días incompletos.

También para un pedido simple como "mostrame mis horas de esta semana": aunque el colaborador solo quiera ver sus cargas, los días se muestran con su clasificación, y los fines de semana y feriados aparecen como no laborales, nunca como días sin carga. Las licencias no son días no laborales: se cargan en BIA - Absentismo.

## Flujo

1. Resolver el período con `resolve-time-range`. Si supera los 92 días, revisarlo por tramos consecutivos de hasta 92 días, cada uno con su propio `classify_period` y su propio resumen. No sumar los totales de los tramos de memoria.
2. Obtener la jornada esperada de cada día con `identify-working-days`.
3. Resolver el usuario actual y consultar sus entradas con `getTimeEntries`, **desde un día antes del inicio hasta un día después del fin** (el filtro de fechas del Redmine de BIA está corrido un día). `classify_period` se queda solo con las cargas cuyo `spent_on` cae dentro del período.
4. Llamar a `classify_period` (MCP `bia-workdays`) con el período, la jornada, las cargas adaptadas al esquema de la herramienta (`date` = `spent_on`, `hours`, `issue` = `issue.id`, `project` = `project.name`, `activity` = `activity.name`, `comment` = `comments`) y, si las hay, las licencias aprobadas (con su `leave_type`) y los feriados de Vacation Tracker. Esa herramienta clasifica cada día, calcula los totales y detecta posibles duplicados. **No sumar ni clasificar de memoria:** usar su resultado tal como viene. Las tablas de abajo explican qué significa cada clasificación.

### Con jornada de 4, 6 u 8 horas

La jornada es un **piso**, no un techo.

| Clasificación | Cuándo |
|---|---|
| **Vacío** | Día laboral sin horas cargadas. |
| **Incompleto** | Día laboral con horas cargadas, pero menos que la jornada esperada. |
| **Completo** | Horas cargadas iguales o mayores a la jornada esperada, hasta el doble. Cargar más que la jornada es normal y no se señala. |
| **Llamativo** | Más del doble de la jornada del colaborador (por ejemplo, más de 16 h con jornada de 8). Se menciona una vez, sin frenar nada, para que confirme que no es un error o un duplicado. |
| **Probable error** | Más de 24 horas en un día. Se señala siempre. |
| **No laboral** | Fin de semana o feriado. |

### Con jornada `variable`

No hay piso diario.

| Clasificación | Cuándo |
|---|---|
| **Vacío** | Día laboral sin horas cargadas. |
| **Con carga** | Día laboral con cualquier cantidad de horas cargadas. |
| **Probable error** | Más de 24 horas en un día. |
| **No laboral** | Fin de semana o feriado. |

Las **licencias** no cambian la clasificación: un día de vacaciones con 8 h cargadas en el #1001 está completo; uno sin cargar está vacío y tiene una licencia por cargar (`leaves_to_load`). Si el mismo día hay dos licencias (por ejemplo, medio día de vacaciones y medio día Flex), cada una se concilia con su issue y aparece por separado.

5. Presentar el resultado:
   - un resumen del período: cantidad de días por clasificación y, con jornada numérica, las horas mínimas esperadas, las cargadas y las faltantes (solo se suman los faltantes de los días vacíos e incompletos);
   - el detalle de los días que requieren atención: fecha, clasificación, horas cargadas, jornada esperada y motivo (por ejemplo, "medio día Flex por cargar: 4 h en el #1002");
   - las entradas de cada día cuando el colaborador las pida o el período sea corto: proyecto, issue **con su asunto** (por ejemplo, `Cliente Ejemplo · #10001 — Ajuste tablero de despacho`), actividad, horas y comentario. Los asuntos se obtienen antes de responder (M-15): primero se separan los issues de BIA - Absentismo, cuyo nombre sale de `get_absence_issues` (los que no figuren ahí se muestran como `BIA - Absentismo · #número`, sin asunto), y solo los demás se consultan con una sola llamada a `getIssues`. Nunca se consultan issues de BIA - Absentismo.
6. Señalar observaciones sustentadas:
   - posibles duplicados: los de `possible_duplicates` de `classify_period`, que exigen la misma fecha, issue, actividad, horas y comentario (D-39);
   - horas cargadas en un día no laboral, como dato informativo; si su `plausibility` es `probable_error` (más de 24 h), señalarlo siempre;
   - licencias pendientes de aprobación, que se muestran marcadas y no se proponen.
7. Separar lo verificado de lo que no se pudo verificar (por ejemplo, feriados si Vacation Tracker no respondió).

## Formato de la respuesta (siempre)

Cualquier revisión de un período, incluidas preguntas como "¿qué días me faltan cargar?" o "mostrame mis horas", tiene estas partes:

1. **Rango y jornada:** las fechas interpretadas y la jornada usada.
2. **Fuentes:** de dónde salió cada dato (Redmine, Vacation Tracker, Nager.Date, configuración personal). Si Vacation Tracker no estuvo disponible, decirlo.
3. **Resumen:** cantidad de días por clasificación y, con jornada numérica, las horas mínimas esperadas, las cargadas y las faltantes.
4. **Días que requieren atención:** **todos** los vacíos **y** los incompletos, con sus horas. "¿Qué días me faltan?" siempre incluye los incompletos, no solo los vacíos.
5. **No laborales:** los fines de semana y los feriados (con su nombre) del período.
6. **Licencias por cargar:** cada entrada de `leaves_to_load` de `classify_period`: fecha, tipo de licencia, issue de BIA - Absentismo y horas. Ofrecer cargarlas (con `propose-time-entry` o `prepare-multi-day-entries`). Si falta el issue o las horas, decirlo.
7. **Licencias posibles:** si no se pudieron consultar las licencias, listar solo los días que una licencia podría explicar, según el campo `possible_leave` de `classify_period`. En BIA las licencias son de medio día o de día completo: un día vacío podría ser una licencia de día completo; un día con media jornada o menos cargada, una de medio día (decir cuánto faltaría en ese caso, `missing_if_half_day_leave`). Un día con más de media jornada cargada no puede explicarse con una licencia: no mencionar licencias para ese día. Cerrar con una sola pregunta.
8. **Observaciones:** días llamativos, posibles duplicados, licencias pendientes de aprobación.

## Reglas

- Diferenciar cero resultados de un error de Redmine o de Vacation Tracker.
- No señalar como problema un día con más horas que la jornada, salvo que supere el doble o las 24 horas.
- No crear, modificar ni eliminar entradas durante la revisión.
- Esta skill no lee el calendario. Al terminar, ofrecer armar propuestas para los huecos a partir del calendario, y solo si el colaborador acepta, derivar a `recover-missing-time-period`.
- Si el colaborador quiere completar faltantes con datos que ya tiene, derivar a `propose-time-entry` o `prepare-multi-day-entries`.
