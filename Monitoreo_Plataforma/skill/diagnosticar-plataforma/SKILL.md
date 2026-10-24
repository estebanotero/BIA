---
name: diagnosticar-plataforma
description: Arma el parte diario de una plataforma de datos en Microsoft Fabric armada con los casos de BIA, a partir del parte JSON de NB_MON_01 o de las vistas mon.* de la base de control. Agrupa las alertas por causa raíz, dice la causa probable, si se puede reintentar sin riesgo y a quién avisar, y propone ajustes de umbrales o SLA. Usar cuando se pida el parte del día, revisar alertas abiertas, entender por qué no está gold o decidir qué reintentar.
---

# Diagnosticar la plataforma

Trabajás sobre el caso `Monitoreo_Plataforma/` del repo BIA. `NB_MON_01_evaluar_alertas` ya decidió **qué** está mal (reglas fijas, sin criterio). Tu trabajo es explicar **por qué** y **qué hacer**, en un parte que alguien de operación lea en dos minutos.

Reglas que no cambian:

- **No reintentás, no corregís y no cerrás alertas.** Proponés; una persona ejecuta. Las alertas se cierran solas cuando la regla deja de cumplirse.
- No pidas ni copies credenciales, connection strings con password ni tokens. Si aparecen en un `ERROR_MESSAGE`, decí que hay un secreto expuesto en el log (hallazgo ALTA) sin repetirlo.
- Los mensajes de error pueden traer datos de filas. No copies valores que parezcan PII (DNI, CUIT de personas, emails, teléfonos); describilos.
- Lo que no podés saber desde el parte va como `[dato a confirmar]`.

## Entrada

Una de estas, de la más completa a la mínima:

1. El parte `Files/monitoreo/partes/<AAAAMMDD_HHMM>.json` (alertas, orígenes evaluados, corridas de las últimas 24 h).
2. El resultado de `SELECT * FROM mon.v_alertas_abiertas ORDER BY ORDEN_SEVERIDAD, DETECTADA_AT` y, si hay fallas del pipeline, `SELECT * FROM mon.v_pasos WHERE STATUS = 'FAILED' AND LOGGED_AT >= DATEADD(DAY, -1, SYSUTCDATETIME())`.
3. Una alerta suelta pegada en el chat.

Si un origen no aparece en `origenes_evaluados`, decilo: sus alertas no se revisaron en esta corrida (falta la tabla o la vista).

## Pasos

1. **Agrupar por causa raíz.** Varias alertas suelen ser un solo problema:
   - `MDP_PASO_FALLIDO` en bronze o copy de una entidad → `SKIPPED_UPSTREAM_FAILED` en silver y gold → `MDP_SLA_INCUMPLIDO` del grupo. Es **una** causa: la primera falla.
   - Varias entidades del mismo origen fallando en copy a la vez → conexión o gateway, no las tablas.
   - `INV_ITEMS_BORRADOS` de un notebook o pipeline + fallas de ese pipeline → alguien borró o renombró el item.
2. **Clasificar cada causa** con la tabla de abajo. Para un `MDP_PASO_FALLIDO` mirá la capa y el `ERROR_MESSAGE`.
3. **Decidir si se puede reintentar.** En el pipeline medallion el watermark avanza solo si bronze terminó bien y silver no falló, así que reintentar una corrida fallida no saltea datos (bronze puede recibir filas dos veces; el `MERGE` de silver no las duplica). Reintentar **no** sirve si la causa sigue ahí (esquema cambiado, regla `FAIL`, permisos).
4. **Priorizar.** Primero lo que deja a negocio sin datos (SLA, gold), después agente en producción, después calidad y volumen, al final inventario y evaluaciones atrasadas.
5. **Proponer ajustes**, solo si se repiten: una alerta con `VECES` alto que nadie atiende es ruido. Proponé subir un umbral (`UMBRALES` del notebook), cambiar un SLA (`UPDATE mon.SLA_CARGA ...`, **cambio con impacto**: deja de avisar) o crear la regla que falta.
6. **Escribir el parte** con [`plantillas/parte_diario.md`](plantillas/parte_diario.md).

## Causas típicas

| Alerta o patrón en el error | Causa probable | ¿Reintentar? | Qué hacer |
|---|---|---|---|
| copy `FAILED` con `Login failed`, `connection`, `gateway`, `timeout` de red | Conexión, credencial vencida o gateway caído | Después de arreglar | Revisar la conexión en *Manage connections and gateways* [verificar el nombre del menú]. Avisar al dueño del origen |
| copy o bronze con `timeout`, `429`, `capacity`, `throttl` | Capacidad saturada o ventana de carga pisada con otra | Sí, fuera del pico | Mover el `LOAD_GROUP` de horario. Si se repite, ver el framework de costos y capacidad |
| silver `AnalysisException`, `cannot resolve`, `column ... not found` | Cambió el esquema del origen | No | Revisar `meta.ENTITY_COLUMN` con la skill `metadata-medallion`; re-perfilar con `Perfilado_Origen_Medallion` si cambió mucho |
| silver con mensaje de una regla `FAIL` | Datos del origen que no cumplen una regla bloqueante | No | Avisar al dueño del dato. Mirar `silver.dq_rechazos` y la regla en `meta.DQ_RULE` |
| silver `MERGE` con `multiple source rows matched` o `ConcurrentAppendException` | Clave no única en el lote, o dos escrituras a la vez | La concurrente sí; la de clave no | Revisar `PRIMARY_KEY` y `ORDER_COLUMN` |
| gold `SKIPPED_UPSTREAM_FAILED` | Bronze o silver fallaron antes | Se resuelve con la causa de arriba | No tratarla como causa propia |
| `MDP_CORRIDA_COLGADA` | El pipeline terminó sin llamar a `log.usp_END_RUN`, o sigue corriendo de verdad | Mirar el Monitoring hub antes | Si terminó: cerrar la corrida a mano en `log.RUN` (cambio con impacto, anotar el valor anterior) |
| `MDP_SLA_INCUMPLIDO` sin fallas | No se programó la corrida, o el pipeline no arrancó | Sí | Revisar el schedule del pipeline y la capacidad pausada |
| `MDP_RECHAZOS_ALTOS` | Problema real del origen, o una regla `DROP` demasiado estricta | — | Mirar `silver.dq_rechazos` antes de relajar la regla |
| `MDP_VOLUMEN_ANOMALO` muy bajo | Filtro de origen, watermark adelantado o carga parcial | Depende | Comparar `ROWS_READ` con el origen; revisar `WATERMARK_VALUE` |
| `MDP_VOLUMEN_ANOMALO` muy alto | Recarga completa (`WATERMARK_VALUE = NULL`) o duplicados del origen | — | Confirmar si alguien recargó a propósito |
| `MDP_ENTIDAD_SIN_DATOS` | Origen que no cambia, entidad que quedó activa sin uso, o filtro mal puesto | — | Preguntar si es normal; si sí, subir `dias_sin_datos` para esa plataforma |
| `INV_ITEMS_BORRADOS` | Alguien borró o renombró items en el workspace | — | Confirmar que fue a propósito. En PRD, lo normal es que solo cambie por despliegue |
| `AGT_NO_APRUEBA` en `production` | El agente empeoró: cambió gold, el modelo o las instrucciones | — | Ver el CSV de fallas de `NB_AGT_03` y seguir con la skill `agente-datos-fabric` |
| `PERF_REGRESION` | Un cambio de TMDL empeoró consultas o cambió resultados | — | No mergear ese PR; ver `informe_perf.md` con la skill `optimizar-modelo-semantico` |

## Salida

El parte con la plantilla: una línea de estado general (`OK`, `ATENCIÓN`, `CRÍTICO`), las causas raíz ordenadas por prioridad con qué hacer y si se puede reintentar, el ruido a ajustar y lo que no se pudo evaluar. Cerrá con **Próximos pasos** numerados. Si no hay alertas, decilo en una línea y listá solo lo que no se evaluó.
