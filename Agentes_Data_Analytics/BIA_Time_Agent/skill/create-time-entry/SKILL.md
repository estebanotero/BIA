---
name: create-time-entry
description: Registra en Redmine cargas de horas que el colaborador ya confirmó explícitamente, una por una, e informa el resultado real. Usar solo después de una propuesta aprobada.
---

# Create time entry

## Cuándo usarlo

Solo cuando el colaborador confirmó una propuesta concreta de una o varias cargas.

## Flujo

1. Verificar que la propuesta incluya proyecto, issue, actividad, duración, fecha y comentario cuando corresponda.
2. Verificar que exista una confirmación explícita para el conjunto exacto de cargas.
3. Ejecutar `createTimeEntry` una vez por cada carga confirmada, sin agregar ni reinterpretar datos.
4. Informar el resultado individual devuelto por Redmine.

## Lotes (Fase 1b)

- Registrar las cargas de un lote **una por una**, en orden de fecha, y verificar cada respuesta de Redmine.
- Si una falla o no se puede verificar, seguir con las demás solo si son independientes, y al final informar exactamente cuáles se registraron, cuáles fallaron y cuáles no se pudieron verificar.
- Nunca declarar "lote registrado" si alguna carga no se confirmó.

## Reglas

- No ejecutar si falta confirmación, aunque la propuesta parezca completa.
- No ejecutar una carga cuya duración no sea múltiplo de 0,5 h: volver a `propose-time-entry`.
- No crear cargas parciales si la confirmación cubría otro conjunto de datos.
- No modificar ni eliminar entradas existentes.
- Si una carga falla o Redmine no confirma su resultado, informar el estado exacto y no declarar éxito global.
- No reintentar automáticamente una carga.
- Si Redmine no confirmó el resultado y el colaborador pide reintentar, volver a `propose-time-entry`: la nueva propuesta consulta si la carga original quedó registrada antes de pedir otra confirmación.
