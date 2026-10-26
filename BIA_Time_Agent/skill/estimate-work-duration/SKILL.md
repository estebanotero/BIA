---
name: estimate-work-duration
description: Arma las unidades de trabajo (actividades del mismo destino y del mismo día), estima su duración y aplica la granularidad de BIA (múltiplos de 0,5 h hacia arriba), mostrando siempre la duración estimada, la propuesta y el motivo. Solo lectura.
---

# Estimate work duration

> **En una recuperación (D-55):** lo que esta skill describe lo aplica `build_day_view` de `bia-workdays`, por código. Seguí su vista tal cual y no recalcules horas, duraciones ni totales; esta skill queda como referencia de los criterios y para los pedidos fuera de una recuperación.

## Cuándo usarlo

Dentro de `recover-missing-time-period`, después de `classify-work-context`.

## Resultado

Una lista de **unidades de trabajo**, cada una con:

- `actividades` agrupadas;
- `fecha` y `destino` (cliente, proyecto e issue);
- `duracion_estimada`: la suma de sus actividades, en minutos;
- `duracion_propuesta`: en horas decimales, múltiplo de 0,5;
- `ajuste`: el motivo de la diferencia (por ejemplo, "granularidad de BIA") o "ninguno";
- `tipo_duracion`: medida (por asistencia o por llamada), calculada desde reunión, rango estimado o pendiente;
- `alerta_plausibilidad`: si con esta unidad el día supera el doble de la jornada o las 24 horas;
- su confianza: todas sus actividades tienen la misma;
- si `build_work_units` informa que separar por confianza sumó horas en ese issue y día (`rounding_notes`), mostrarlo en la propuesta: "al separar por confianza, el total de este issue pasa de X h a Y h", para que el colaborador decida si las combina.

## Flujo

1. **Agrupar con `build_work_units`** (MCP `bia-workdays`): una unidad reúne las actividades del **mismo día**, el **mismo issue** y la **misma confianza** (D-23, D-44). Confianza distinta, unidades distintas. Nunca se agrupan días distintos: 10' el lunes y 10' el martes en el mismo issue son dos unidades. Pasarle las actividades clasificadas (fecha, issue, confianza y minutos), las horas ya cargadas por día y la jornada, y usar su resultado tal como viene. No agrupar ni sumar de memoria.
2. **No agrupar** actividades de destinos distintos, ni actividades ambiguas o sin issue: quedan como unidades separadas para que el colaborador decida.
3. **Sumar y redondear:** lo hace `build_work_units`, nunca el modelo: suma los minutos de las actividades de cada unidad y aplica la granularidad de BIA (múltiplos de 0,5 h, siempre hacia arriba, D-21). Por ejemplo, 15–20' → 0,5 h; 40' → 1,0 h; 1 h 10' → 1,5 h. Las actividades que se superponen 15 minutos o más (con sus horarios reales) no se pasan hasta que el colaborador decida cómo repartir; las superposiciones menores se informan y se suman (D-55).
4. **Conciliar:** pasarle a `build_work_units`, en `existing`, las cargas de esos días **con su issue**. Devuelve, para cada unidad, cuánto ya está cargado (`covered_by_existing_hours`), cuánto falta exactamente (`pending_hours`, informativo), **lo que se registra** (`to_load_hours`, con la granularidad de BIA) y su estado (`reconciliation`: `sin_carga`, `parcial` o `ya_registrada`), consumiendo cada hora cargada una sola vez y cubriendo primero las unidades de mayor confianza.
5. **Micro-actividades de destinos distintos en el mismo día:** `build_work_units` las detecta (unidades de menos de 30 minutos estimados en issues distintos del mismo día), las marca con `needs_decision` y las resume en `micro_activity_notes`, con las horas si se separan y si se agrupan. **No proponer esas unidades** hasta que el colaborador decida si las agrupa en un destino, las reparte o las descarta; con su decisión, volver a llamar a `build_work_units` con las actividades ya resueltas.
6. **Plausibilidad del día:** tomarla de `build_work_units` (`days[].day_total_hours` y `days[].plausibility`), que suma lo ya cargado y **todas** las unidades pendientes de ese día. No volver a calcularla con `apply_granularity`: contra cada unidad por separado perdería alertas (por ejemplo, 15 h cargadas más dos unidades de 1 h son 17 h, un día llamativo). Más del doble de la jornada: mencionarlo una vez. Más de 24 horas: señalarlo como probable error. Con jornada `variable`, solo el control de 24 horas. Superar la jornada no se señala.
7. Un evento de día completo no da una duración: la unidad queda con duración **pendiente**, para que la indique el colaborador.

## Reglas

- La duración **agendada** de una reunión es una estimación confirmable, nunca un hecho. Si `merge_calls_with_events` dio una duración **medida** (tu asistencia, o la llamada de la reunión en la que participaste), se usa esa, diciendo su fuente: la de la llamada es lo que duró la reunión, no necesariamente tu asistencia. Con participación desconocida, no hay medida.
- Mostrar siempre la duración estimada y la propuesta, con el motivo.
- No recortar ni ajustar unidades para "entrar" en la jornada: la jornada es un piso, no un techo.
