---
name: propose-time-entry
description: Arma una propuesta verificable de carga de horas en Redmine a partir de lo que describe el colaborador, separando datos confirmados, inferidos y faltantes. No escribe en Redmine.
---

# Propose time entry

> **En una recuperación (D-55):** lo que esta skill describe lo aplica `build_day_view` de `bia-workdays`, por código. Seguí su vista tal cual y no recalcules horas, duraciones ni totales; esta skill queda como referencia de los criterios y para los pedidos fuera de una recuperación.

## Cuándo usarlo

Cuando el colaborador describa qué hizo y solicite registrar horas, incluyendo casos con una reunión o una carga recurrente previamente confirmada.

## Resultado

Una propuesta verificable que incluya:

- proyecto, issue y **asunto del issue** (su `subject` en Redmine), juntos, por ejemplo `Cliente Ejemplo · #10001 — Ajuste tablero de despacho`: el asunto suele ser lo que permite reconocer el destino a simple vista (M-15);
- actividad;
- fecha;
- duración estimada y duración propuesta, con el motivo del ajuste;
- comentario (si el colaborador no lo dio, uno breve marcado como **sugerido**, para que lo confirme o lo cambie; nunca presentarlo como un dato que dio el colaborador);
- evidencia utilizada;
- datos inferidos y nivel de confianza;
- datos todavía faltantes;
- cargas que el colaborador ya tiene en esa fecha y ese issue, si las hay.

## Flujo

1. Interpretar la solicitud sin agregar datos no expresados.
2. Usar `resolve-time-context` cuando una referencia no sea explícita.
3. Validar formato, duración positiva y datos obligatorios.
4. Consultar con `getTimeEntries` todas las cargas del usuario autenticado para esa fecha, pidiendo desde el día anterior hasta el día siguiente (el filtro de fechas del Redmine de BIA está corrido un día) y quedándose solo con las de `spent_on` igual a la fecha: sirven para mostrar las cargas que ya tiene en ese issue, detectar posibles duplicados y saber cuánto lleva cargado el día.
5. Recién entonces, obtener la duración a cargar con `apply_granularity` (MCP `bia-workdays`), pasándole la duración estimada, las horas que ya tiene el día (las del paso 4) y la jornada. **No redondear de memoria.** **Excepción:** si la carga viene de una unidad de trabajo de una recuperación, la duración a registrar es su `to_load_hours` y la plausibilidad, la del día en `build_work_units`: no volver a pasar la duración estimada por `apply_granularity`, porque ignoraría lo ya cargado.
6. Tomar la plausibilidad del día del resultado de `apply_granularity` (ver más abajo).
7. Mostrar la propuesta normalizada junto con las cargas existentes encontradas.
8. Solicitar confirmación antes de derivar a `create-time-entry`.

## Granularidad de BIA

- Las horas se cargan en múltiplos de 0,5 h. Lo que no cae en un múltiplo se redondea **siempre hacia arriba**: 15–20' → 0,5 h; 40' → 1,0 h; 1 h 10' → 1,5 h; 1,25 h → 1,5 h.
- Aplica a toda carga, también cuando el colaborador da la duración exacta: si pide "cargame 40'", se propone 1,0 h.
- Mostrar siempre las dos cifras y el motivo, por ejemplo: "Duración estimada: 40' · Duración propuesta: 1,0 h (granularidad de BIA)". Si no hubo ajuste, decirlo.
- La duración propuesta se expresa en horas decimales.

## Plausibilidad del día

- La jornada es un piso, no un techo. Que con esta carga el día supere la jornada es normal y **no** se señala.
- Si con esta carga el día supera el doble de la jornada del colaborador (por ejemplo, más de 16 h con jornada de 8), mencionarlo una vez en la propuesta, sin frenar nada, para que confirme que no es un error o un duplicado.
- Si con esta carga el día supera las 24 horas, señalarlo como probable error y pedirle que lo revise antes de confirmar.
- Con jornada `variable` solo aplica el control de las 24 horas.
- No recortar ni ajustar la carga por cuenta propia: decide el colaborador.

## Posibles duplicados

- Mostrar siempre las cargas que el colaborador ya tiene en esa fecha y ese issue, como contexto.
- Solo es un **posible duplicado** una carga con la misma fecha, issue, actividad, horas y comentario (D-39): señalarla y preguntar si la nueva carga es distinta o si ya está registrada.
- No bloquear la carga: dos entradas iguales el mismo día pueden ser legítimas, por ejemplo dos reuniones. Decide el colaborador.
- Si la consulta de cargas existentes falla, informarlo en la propuesta y no afirmar que no hay duplicados.

## Propuestas a partir de evidencias (Fase 1b)

Cuando la propuesta nace de una unidad de trabajo (dentro de `recover-missing-time-period`), además incluye:

- `tipo_duracion`: medida (por asistencia o por llamada), calculada desde reunión, rango estimado o pendiente;
- `confianza`: alta, media o baja, **con el criterio aplicado** (por ejemplo, "alta: la serie se cargó al issue 12345 en 4 de las últimas 4 ocurrencias");
- las **evidencias** usadas, con su fuente y su referencia (por ejemplo, "reunión del calendario, 10:00–11:00, con participantes de cliente-ejemplo.com");
- las **alternativas** descartadas y por qué;
- un comentario breve y comprobable, basado en el asunto de la reunión, sin datos de terceros. Nunca el asunto de un evento privado;
- su **estado**: sugerida, ambigua, sin issue o ya registrada.

Una propuesta ambigua o sin issue no se completa con una suposición: muestra las alternativas o pregunta.

Una propuesta no modifica Redmine. La duración agendada de una reunión no equivale automáticamente al tiempo trabajado, y la presencia en el calendario no prueba asistencia: por eso se prefiere la duración medida, cuando la hay, diciendo su fuente.
