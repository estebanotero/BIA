---
name: prepare-multi-day-entries
description: Prepara un conjunto de cargas de horas para varios días, una actividad recurrente o las propuestas de una recuperación de período, con una vista por estados, detalle por día y total, y las reglas de confirmación por lote según la confianza. No escribe en Redmine.
---

# Prepare multi-day entries

> **En una recuperación (D-55):** lo que esta skill describe lo aplica `build_day_view` de `bia-workdays`, por código. Seguí su vista tal cual y no recalcules horas, duraciones ni totales; esta skill queda como referencia de los criterios y para los pedidos fuera de una recuperación.

## Cuándo usarlo

Cuando el colaborador solicite preparar cargas para varios días, por ejemplo una cantidad de horas de lunes a viernes o una actividad recurrente.

## Flujo

1. Determinar el período con `resolve-time-range`, y la duración, actividad, proyecto e issue, con el asunto del issue para mostrarlo en la propuesta (M-15).
2. Resolver referencias ambiguas mediante `resolve-time-context`.
3. Excluir días no laborables y feriados usando `identify-working-days`. Los días de licencia de día completo también se excluyen de cargas de proyecto: su carga va en BIA - Absentismo (D-46).
4. Consultar con `getTimeEntries` todas las cargas del colaborador en el período (con un día de margen de cada lado). Marcar los días que ya tengan una carga en ese issue, y como posible duplicado solo la que coincida en fecha, issue, actividad, horas y comentario (D-39).
5. Recién entonces, obtener la duración de cada día con `apply_granularity`, como en `propose-time-entry`, pasándole las horas que ya tiene cada día, y mostrar duración estimada, propuesta y plausibilidad (más del doble de la jornada o más de 24 horas). No redondear de memoria. En un lote que viene de una recuperación, usar en cambio el `to_load_hours` de cada unidad y la plausibilidad de cada día de `build_work_units`.
6. Presentar cada carga propuesta, los días marcados y el total.
7. Solicitar una única confirmación explícita para el conjunto exacto.
8. Derivar a `create-time-entry` solo después de la confirmación.

## Vista por estados y confirmación por lote (Fase 1b)

Cuando las propuestas vienen de `recover-missing-time-period`, mostrarlas agrupadas por estado:

| Estado | Qué es |
|---|---|
| **Sugeridas** | Tienen destino y confianza alta o media. Se muestra la confianza de cada una. |
| **Ambiguas** | Hay varias alternativas con fuerza parecida. |
| **Sin issue** | No hay un destino razonable. |
| **Ya registradas** | Ya existe la carga en Redmine. Solo informativas. |
| **Descartadas** | Las que el colaborador descartó. |

Reglas de la confirmación (D-16):

- **"Aceptá todas las de alta confianza":** entran solo las de confianza alta.
- **Confirmar un día o un proyecto entero:** puede incluir las de confianza media, cada una marcada como tal en el resumen de lo que se va a registrar.
- **Confianza baja, ambiguas y sin issue:** siempre se revisan una por una. Nunca entran en un lote.
- El colaborador puede, antes de confirmar: editar la duración (respetando la granularidad), cambiar el issue, excluir una propuesta, dividirla o combinarla (solo dentro del mismo día), o dejarla pendiente.
- Antes de registrar, mostrar el **conjunto exacto** que se va a cargar (fecha, issue, actividad, horas, comentario) y su total.

## Reglas

- Si no se puede verificar un feriado o ausencia, declararlo y no excluirlo silenciosamente.
- No ejecutar cargas parciales ni ampliar el período confirmado.
- Un día con una carga existente en ese issue se muestra marcado (y como posible duplicado si coincide en todo, D-39); el colaborador decide si se incluye en el conjunto.
- La preparación por sí sola no escribe en Redmine.
