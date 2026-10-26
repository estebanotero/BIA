---
name: reconcile-evidence-with-time-entries
description: Compara las unidades de trabajo con las cargas que el colaborador ya tiene en Redmine para detectar qué está cargado, qué falta y qué está posiblemente cargado en otro destino. En la Fase 1b, versión parcial centrada en reuniones sin carga. Solo lectura.
---

# Reconcile evidence with time entries

> **En una recuperación (D-55):** lo que esta skill describe lo aplica `build_day_view` de `bia-workdays`, por código. Seguí su vista tal cual y no recalcules horas, duraciones ni totales; esta skill queda como referencia de los criterios y para los pedidos fuera de una recuperación.

## Cuándo usarlo

Dentro de `recover-missing-time-period`, después de `estimate-work-duration`, para no proponer cargas que ya existen.

## Resultado

Cada unidad de trabajo queda en uno de estos estados:

| Estado | Cuándo |
|---|---|
| **Sin carga** | No hay ninguna carga ese día que la cubra. Se propone. |
| **Ya registrada** | Hay una carga ese día en el mismo issue, con una duración compatible. No se propone; se muestra para que el colaborador lo vea. |
| **Posiblemente en otro destino** | Hay una carga ese día cuyo comentario coincide con el asunto de la reunión, pero en otro issue. Se muestra la diferencia y decide el colaborador. |

## Flujo

1. Consultar con `getTimeEntries` las cargas del colaborador en los días revisados, desde un día antes hasta un día después (el filtro de fechas del Redmine de BIA está corrido un día), quedándose solo con las de `spent_on` dentro de esos días (si ya se consultaron en el flujo, reusar ese resultado).
2. En el **mismo issue**, usar la conciliación por saldo que ya hizo `build_work_units` (campos `reconciliation`, `covered_by_existing_hours` y `pending_hours`): no recalcularla. Cada hora cargada cubre una sola unidad, primero las de mayor confianza. Por ejemplo, con 0,5 h cargadas y dos unidades de 0,5 h en ese issue (una de confianza alta y otra media), la alta queda **ya registrada** y la media **sin carga**; mostrarle al colaborador cuál se tomó como cubierta. Una unidad `parcial` se propone por sus `to_load_hours` (lo que falta, con la granularidad de BIA; si `to_load_adjusted` es verdadero, mostrar el ajuste respecto de `pending_hours`), explicando la diferencia.
   - en **otro issue**: ver el punto siguiente;
   - en **otro issue**, con un comentario que comparte palabras significativas con el asunto: **posiblemente en otro destino**.
3. Si no hay coincidencias, la unidad queda **sin carga**.

## Reglas

- Nunca modificar ni eliminar cargas existentes, aunque parezcan mal imputadas: solo señalarlo.
- Ante la duda entre "ya registrada" y "sin carga", mostrar la carga existente y preguntar. Es preferible preguntar a duplicar.
- Fuera del alcance de la Fase 1b: horas cargadas sin evidencia y distribuciones inconsistentes entre proyectos (Fase 2).
