---
name: recover-missing-time-period
description: Orquesta la recuperación de un período atrasado ("recuperá desde mi última carga", "completá la semana pasada", o cuando el colaborador acepta la oferta de una revisión). Detecta los huecos, recolecta evidencias del calendario solo para esos días, propone cargas con su confianza, pide confirmación por lote, registra, verifica y resume. Escribe en Redmine solo después de la confirmación.
---

# Recover missing time period

## Cuándo usarlo

Cuando el colaborador pide recuperar o completar las horas de un período ("recuperá desde mi última carga", "completá la semana pasada", "proponeme cargas para octubre") o acepta la oferta de armar propuestas que hace una revisión. Los pedidos de revisar o ver ("revisá desde mi última carga", "¿qué me faltó cargar en octubre?") son de `review-time-period`: no leen el calendario.

## Flujo

1. **Período:** resolverlo con `resolve-time-range`. Si supera 31 días, procesarlo por tramos y confirmar cada tramo antes de pasar al siguiente.
2. **Huecos:** con `review-time-period`, identificar los días vacíos e incompletos, descontando feriados, y las licencias por cargar. **Días no laborales trabajados (D-47):** si el colaborador pide recuperar un fin de semana o un feriado porque trabajó, ese día entra en la recuperación aunque no sea un hueco. Mencionar una sola vez que fue no laboral y seguir, sin pedir otra confirmación. Ese día no tiene horas esperadas: no hay faltante, y se propone lo que muestren sus evidencias, menos lo ya cargado. Si no hay huecos ni días no laborales pedidos, informarlo y terminar.
3. **Licencias, en períodos largos:** si hay más de cinco días con huecos y no se pudieron verificar las licencias, preguntar primero por las licencias posibles (según `classify_period`), con una sola pregunta, y recién después leer el calendario. Así no se buscan evidencias, ni se gastan créditos, en días que fueron de licencia.
4. **Licencias por cargar:** proponerlas en BIA - Absentismo, con el issue y las horas de cada entrada de `leaves_to_load` (D-46). Un día de licencia de día completo no necesita evidencias: no leer su calendario.
5. **Evidencias:** con `collect-work-evidence`, solo para las horas de los días vacíos e incompletos que no explica una licencia, y para los días no laborales trabajados que pidió el colaborador (D-47).
6. **Destinos que el código no resuelve:** con `classify-work-context`, solo para las citas sin issue escrito en la cita ni regla uno a uno: prefijo de cliente (`match_client_prefix`), historial de la serie y contexto del día. Cada destino que encuentres es una **pista** (`hints`: id de la cita, issue, confianza y motivo). Verificar con una sola consulta `getIssues` los issues escritos en las citas (`issueRefs`), para pasarlos como `verified_issues`.
7. **Vista del día, por código (D-55):** llamar a `build_day_view` de `bia-workdays` con la jornada, los días a revisar tal como los devolvió `classify_period` (`review_days`: fecha, horas esperadas y estado), las citas, las llamadas, la asistencia (con sus `intervals`), las cargas ya registradas (con su comentario), el mapa `uno_a_uno` de la configuración, los `verified_issues` y las `hints`. Devuelve, por día, cada cita con su estado (sugerida, a decidir o descartada) y su motivo, su destino y de dónde sale, su duración y su fuente, las superposiciones reales, las cargas propuestas con la granularidad y la conciliación ya aplicadas, las llamadas emergentes y los totales.
8. **Mostrarla tal cual:** las horas, las duraciones y sus fuentes, las superposiciones y los totales salen **solo** de `build_day_view`. Nunca recalcularlos, redondearlos de nuevo ni cambiar una fuente (por ejemplo, decir "agendada" donde la vista dice "medida"). Si `has_work_evidence` es verdadero, no sugerir una licencia de día completo. Para las citas a decidir, explicar el motivo y ofrecer alternativas (con el asunto de cada issue); para el trabajo sin reunión (documentos, correos, chats), preguntar la duración.
9. **Decisiones del colaborador:** cuando el colaborador elige un destino, reparte una superposición, indica una duración o descarta algo, volver a llamar a `build_day_view` con esas respuestas en `decisions` (el `id` del ítem en la vista y, si es solo para un día de una cita larga, la fecha), y con el trabajo sin reunión que confirme, con su duración, en `extra_activities`. Las decisiones mandan sobre todo lo demás. Mostrar la vista actualizada; nunca ajustar los números a mano.
10. **Propuestas:** con `propose-time-entry`, las cargas de `loads` de la vista, con su confianza, evidencias y alternativas.
11. **Vista por estados y confirmación:** con `prepare-multi-day-entries`, mostrar las propuestas agrupadas por estado y pedir confirmación, por lote o una por una.
12. **Registro:** con `create-time-entry`, solo lo confirmado.
13. **Verificación:** volver a consultar las cargas de los días revisados.
14. **Resumen del período:** días revisados, cargas creadas, propuestas pendientes, descartadas y huecos que siguen sin evidencia.

## Qué ve el colaborador

Antes de confirmar, una sola vista con:

- el resumen de huecos del período (días y horas faltantes);
- las propuestas agrupadas por estado: **sugeridas** (con su confianza), **ambiguas**, **sin issue**, **ya registradas**;
- los días con huecos que no tienen evidencia, marcados como "sin evidencia: completar a mano";
- cuánto de cada hueco cubrirían las propuestas.

## Reglas

- Nunca registrar nada sin confirmación (D-11). Las reglas del lote están en `prepare-multi-day-entries`.
- Recolectar evidencias solo de los días con huecos (minimización de datos).
- Lo que no se puede resolver queda explícito como pendiente, nunca se completa con suposiciones.
- Si una fuente falla (por ejemplo, Microsoft 365 sin sesión), seguir con lo que haya y decir claramente que la revisión es parcial.
- No reintentar cargas automáticamente.
