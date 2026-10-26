---
name: normalize-work-evidence
description: Agrupa las evidencias que corresponden a un mismo trabajo en actividades, evita contar dos veces reuniones recurrentes, reprogramadas o superpuestas, y conserva el vínculo con cada evidencia. Solo lectura.
---

# Normalize work evidence

> **En una recuperación (D-55):** lo que esta skill describe lo aplica `build_day_view` de `bia-workdays`, por código. Seguí su vista tal cual y no recalcules horas, duraciones ni totales; esta skill queda como referencia de los criterios y para los pedidos fuera de una recuperación.

## Cuándo usarlo

Dentro de `recover-missing-time-period`, después de `collect-work-evidence`.

## Resultado

Una lista de **actividades**, cada una con:

- `evidencias`: las referencias de las evidencias que la respaldan;
- `fecha`, `inicio` y `fin` consolidados, siempre de un solo día: un evento que cruza la medianoche o abarca varios días aporta a cada día solo su tramo (`segments` de `bia-m365`), y solo a los días a revisar;
- `señales` combinadas (asunto, dominios, serie);
- `duracion_estimada`: en minutos, con el criterio usado;
- `estado`: sin carga (por ahora; la conciliación lo ajusta después);
- `observaciones`: superposiciones, evidencias débiles, dudas.

## Flujo

1. **Una evidencia, una actividad**, salvo los casos de abajo. Si el evento tiene más de un tramo en `segments`, trabajar con cada tramo como una evidencia de su día, con sus `minutes`, y descartar los tramos de días que no se revisan.
2. **Eventos duplicados:** la identidad de una evidencia es su **referencia y su fecha**: los tramos de un mismo evento en días distintos son evidencias distintas y nunca se fusionan. Dos evidencias con la misma referencia y la misma fecha, o con el mismo asunto, la misma fecha y el mismo horario, son una sola actividad.
3. **Mismo asunto, mismo día:** dos o más eventos del mismo día con el mismo asunto (por ejemplo, dos bloques "Ajuste tablero TECPE" en horarios distintos) forman **una sola actividad**. Conservar todas las evidencias. **Antes de sumar, revisar si se superponen:** si no se superponen, la duración es la suma; si se superponen 15 minutos o más, no sumarlas: marcar la actividad como superpuesta, mostrar los horarios y pedir la duración al colaborador; si se superponen menos, se suman y la superposición solo se informa (D-55). **Nunca agrupar por asunto los eventos con asunto oculto** (`(evento privado)` o `(fuera de la oficina)`): cada uno queda como actividad separada, salvo que el colaborador confirme que son el mismo trabajo.
4. **Ocurrencias de una serie:** cada ocurrencia de una reunión recurrente es una actividad distinta en su día. Una ocurrencia reprogramada cuenta una sola vez, en el día y horario en que quedó.
5. **Superposiciones (D-55):** se calculan con los horarios reales (medidos si los hay). Si dos actividades se superponen **15 minutos o más**, ninguna se propone completa: quedan a decidir, y el colaborador indica cómo repartir. Si se superponen menos (por ejemplo, una llamada que empieza un minuto antes), solo se informa.
6. **Duración:** si `merge_calls_with_events` dio una duración medida para la cita, se usa esa (`measured_minutes`), indicando su fuente: "medida por tu asistencia" o "medida por la llamada de la reunión" (la llamada dura lo que duró la reunión, no necesariamente tu asistencia). Si la fuente es `no_participaste`, la cita va a **Descartadas**, con el motivo "la reunión tuvo llamada y no figurás entre los participantes". Si es `participacion_desconocida`, no hay medida: se usa la duración agendada, aclarando que no se pudo saber si participaste. Si es `ambigua`, una llamada de esa reunión ese día no se pudo atribuir a una sola cita (`ambiguous_calls` trae su horario y las candidatas): mostrarlo como **ambigua, con sus alternativas**, y no usar la duración agendada hasta que el colaborador diga a qué cita corresponde. Una cita con `has_ambiguous_calls` también se muestra con esa alternativa, aunque tenga otra llamada medida. Si la cita cruza la medianoche, cada día usa su parte de `measured_by_day`. Si la cita trae `attendance_outside_days` (asistencia en un día que no estaba agendado), mostrarlo y preguntar si corresponde sumarlo: no se suma solo. Si no hay medida, la del tramo del día (`minutes` de `segments`), marcada como "calculada desde la reunión, confirmable". Para eventos de día completo, la duración queda pendiente.
7. **Llamadas emergentes:** cada llamada emergente es una actividad nueva de su día, con su duración medida. Su destino sale de los números de issue que `get_teams_calls` extrae por código del título de los chats grupales (`issueRefs`; el título nunca se devuelve), de si hubo externos y de las demás señales. Sin ninguna señal, queda **sin issue**, para que el colaborador diga a qué corresponde.
8. **Trabajo sin reunión:** si en un día con hueco hay documentos modificados, correos enviados o actividad en chats que no corresponden a ninguna cita ni llamada, agruparlos por destino como una actividad **sin duración**, con su horario aproximado cuando lo hay (entre tu primer y tu último mensaje de un chat, la hora de un correo o de un documento) y la duración **pendiente**: el colaborador la indica. Nunca convertir mensajes, correos o documentos en horas por cuenta propia.
7. Conservar las marcas de evidencia débil de `collect-work-evidence`.

## Reglas

- No asignar cliente, proyecto ni issue: eso lo hace `classify-work-context`.
- No redondear: la granularidad se aplica después, sobre las unidades de trabajo.
- No juntar actividades de días distintos.
- Que una reunión haya durado una hora no prueba que el colaborador trabajó una hora: la duración siempre se muestra como confirmable.
