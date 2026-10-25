[[_TOC_]]

# Overview

Esta página explica **cómo está construido BIA Time Agent**: qué piezas tiene, dónde corre cada una, qué pasa cuando le pedís algo y cómo se protege. Está escrita para quien llega sin contexto.

> **Versión descripta: 0.20.0** (Fase 1a y Fase 1b, con las licencias en BIA - Absentismo), en la rama `main` del repositorio `bia-da-agentic` desde el 24/10/2026 (pull request #733). Para instalarlo, ver la página **Instalación y uso**. Para el porqué de cada decisión y el historial, ver **Evolución**.

En una frase: BIA Time Agent es un **agente de GitHub Copilot** que, con un conjunto de **reglas fijas**, **procedimientos** (skills) y **herramientas autorizadas**, te ayuda a revisar y cargar tus horas en Redmine. Nunca escribe en Redmine sin tu confirmación.

# Las piezas, explicadas con una analogía

Pensá en un **asistente administrativo nuevo** que te ayuda con las horas:

| Pieza | En la analogía | Qué es en realidad |
|---|---|---|
| **El agente** | El asistente, con un **reglamento** que lee antes de cada pedido. | Un archivo de instrucciones (`bia-time-agent.agent.md`) con el **núcleo**: las reglas que se cumplen siempre. |
| **Las skills** | Los **procedimientos** que el asistente consulta para cada tarea. | 13 archivos con el paso a paso de cada tarea (revisar un período, proponer una carga, recuperar una semana...). |
| **Los MCP** | Las **ventanillas** a las que el asistente puede ir a buscar o dejar información. | Servidores que le dan herramientas concretas al agente: consultar Redmine, calcular fechas, leer tu calendario. |
| **El modelo** | La **cabeza** del asistente: entiende tu pedido y decide qué hacer. | GPT-6 Luna, fijado en el agente. |
| **La calculadora** | El asistente no hace cuentas de memoria: usa una calculadora. | El MCP `bia-workdays`: fechas, feriados, redondeos, sumas y clasificaciones salen de código, no del modelo. |
| **Vos** | El jefe: el asistente propone, vos decidís. | Toda carga se confirma explícitamente. |

# Cómo se conectan

::: mermaid
graph LR
  C([Colaborador]) --> CP["GitHub Copilot<br/>agente + skills<br/>modelo GPT-6 Luna"]
  CP --> CFG[("Configuración personal<br/>~/.bia-time-agent/config.yaml")]
  CP --> RM["MCP redmine<br/>(local)"] --> R[(Redmine)]
  CP --> WD["MCP bia-workdays<br/>(local, propio)"] --> N[(Nager.Date<br/>feriados públicos)]
  CP --> BC["MCP bia-m365<br/>(local, propio)"] --> G["Microsoft Graph<br/>solo lectura"] --> M[(Tu Microsoft 365)]
  CP -.->|pendiente D-28| VT["MCP vacation-tracker<br/>(remoto oficial)"] -.-> V[(Vacation Tracker)]
:::

## Dónde corre cada cosa

| Pieza | Dónde corre | Qué datos toca |
|---|---|---|
| GitHub Copilot (agente y skills) | Tu máquina; el modelo, en la nube de GitHub | Lo que le pedís y lo que devuelven las herramientas |
| MCP `redmine` | Tu máquina | Tus cargas de horas, con tu clave de Redmine |
| MCP `bia-workdays` | Tu máquina | Cálculos locales; a Nager.Date solo le pide el año |
| MCP `bia-m365` | Tu máquina | Solo metadatos de **tu** calendario: asunto, horario, dominios de los participantes. Habla directo con Microsoft Graph, sin IA (D-53) |
| Configuración personal | Tu máquina, fuera del repositorio | Tu ID de Entra, tu jornada y, si las declarás, tus licencias |
| MCP `vacation-tracker` | Nube del proveedor | Tus licencias y los feriados de tu ubicación. **Hoy no funciona en GitHub Copilot** por un error del proveedor (D-28): el agente usa el plan alternativo |

Todo corre en tu máquina, salvo el modelo, Redmine y, cuando funcione, Vacation Tracker (D-01).

# Qué pasa cuando le pedís algo

## Una revisión: "¿Qué días me faltan cargar este mes?"

1. **Valida tu configuración personal**, leyéndola de nuevo en cada pedido. Si falta algo o algo es inválido, se frena y te dice qué completar.
2. **Resuelve el período** con la fecha de hoy calculada por código (`get_today`).
3. **Consulta tus cargas en Redmine**, con un día de margen por el corrimiento de fechas del filtro (D-40).
4. **Clasifica cada día con `classify_period`:** vacío, incompleto, completo, llamativo o no laboral, con los totales, las licencias por cargar en BIA - Absentismo y las licencias posibles.
5. **Te muestra el resultado** con un formato fijo: rango y jornada, fuentes, resumen de horas, días que requieren atención, días no laborales, licencias por cargar y licencias posibles.
6. **Te ofrece** buscar evidencias en tu calendario para los huecos, **sin leerlo** todavía. Revisar no es recuperar (D-42).

## Una recuperación: "Recuperá las horas de la semana pasada"

1. Los pasos 1 a 4 de la revisión, para encontrar los huecos.
2. **Lee tu calendario solo para los días con huecos** (`bia-m365`), con solo metadatos: nunca los días de licencia de día completo. Para el historial de una reunión recurrente, también hasta 31 días antes, usando solo las ocurrencias de esa reunión. Un fin de semana o feriado, solo si pedís recuperarlo porque trabajaste (D-47).
3. **Suma contexto sin duración** (`get_used_documents`, `get_sent_mail`, `get_chat_activity`): documentos, correos enviados y actividad en chats de esos días, solo metadatos. Son señales para resolver destinos y detectar trabajo fuera de las reuniones, nunca horas.
4. **Mide la duración real** (`get_teams_calls` y `get_meeting_attendance` de `bia-m365`, unidas por código con `merge_calls_with_events` de `bia-workdays`): cuánto duró cada reunión de Teams, si participaste, y las llamadas que no están en tu calendario. Una cita se mide solo en sus días agendados.
5. **Agrupa y clasifica:** une lo que es lo mismo, deduce el destino de cada reunión (issue escrito en la cita, historial, prefijo de cliente, dominios, asunto) y le asigna una confianza con su criterio.
6. **Arma las unidades de trabajo con `build_work_units`:** mismo día, mismo issue y misma confianza, con la granularidad de BIA.
7. **Concilia con Redmine por saldo** (`build_work_units`): las horas que ya cargaste en un issue ese día cubren sus reuniones una sola vez, primero las de mayor confianza, y lo que falta se propone ajustado a la granularidad. Las micro-actividades en issues distintos quedan esperando tu decisión.
8. **Te muestra la vista completa:** cada evento en una categoría (sugeridas, débiles, ambiguas, sin issue, descartadas, ya registradas) y cuánto queda sin evidencia.
9. **Confirmás sobre el conjunto exacto.** "Aceptá las de alta" o "confirmá el día" son una selección: el agente te muestra exactamente qué va a cargar y espera tu sí.
10. **Registra una por una y verifica cada respuesta de Redmine.** Copilot además te pide aprobar el uso de la herramienta de carga: es la segunda barrera.

# El núcleo y las skills

El agente lleva **el núcleo** (las reglas) y **un índice de las skills**, y carga cada skill cuando la necesita (D-36). Como un modelo puede contestar sin cargar una skill, **lo que tiene que pasar siempre está en el núcleo** (D-42):

- Validar la configuración personal y volver a consultar Redmine **en cada pedido**.
- No calcular fechas, redondeos, sumas ni clasificaciones de memoria.
- El formato de toda revisión y la vista completa de toda recuperación.
- Revisar no es recuperar.
- Confirmar los lotes sobre el conjunto exacto, con una sola pregunta por confirmación.
- Sin `bia-workdays`, no improvisar cuentas ni registrar.
- `bia-m365` solo como evidencia, nunca como reemplazo de otra herramienta.
- Usar solo las skills de BIA Time Agent, aunque haya otras instaladas.

| Fase | Skills |
|---|---|
| **Base y Fase 1a** | `resolve-time-range` (fechas como "la semana pasada"), `identify-working-days` (jornada, feriados y licencias), `resolve-time-context` (a qué issue corresponde algo), `propose-time-entry`, `prepare-multi-day-entries`, `review-time-period`, `create-time-entry` |
| **Fase 1b** | `recover-missing-time-period` (la orquestadora), `collect-work-evidence`, `normalize-work-evidence`, `classify-work-context`, `estimate-work-duration`, `reconcile-evidence-with-time-entries` |

# Las herramientas

| MCP | Herramientas que usa el agente | Para qué |
|---|---|---|
| `redmine` | `getCurrentUser`, `getProject`, `getIssues`, `getTimeEntryActivities`, `getTimeEntries`, `createTimeEntry` | Consultar y registrar tus cargas. La única que escribe es `createTimeEntry`. |
| `bia-workdays` | `get_today`, `get_calendar_days`, `get_public_holidays`, `apply_granularity`, `classify_period`, `build_work_units`, `get_absence_issues`, `match_client_prefix`, `get_version`, `merge_calls_with_events`, `match_one_on_one`, `build_day_view` | Fechas, feriados, todas las cuentas de horas y los issues de licencias de BIA - Absentismo. |
| `bia-m365` | `get_calendar_events`, `get_teams_calls`, `get_meeting_attendance`, `get_used_documents`, `get_sent_mail`, `get_chat_activity` | Metadatos de tu calendario, leídos de Microsoft Graph con permisos delegados de solo lectura. Por código: ruta fija `/me/calendarView`, campos fijos, participantes reducidos a dominios, eventos privados y "fuera de la oficina" sin asunto. Del cuerpo y la ubicación devuelve **únicamente** las referencias numéricas a issues de Redmine (`issueRefs`); nunca devuelve el cuerpo ni la ubicación (D-48); del asunto, el prefijo de cliente (`subjectPrefix`, D-49). De las llamadas, solo los eventos de fin de llamada (duración, horario, si participaste): nunca mensajes, nombres ni el título del chat. De la asistencia, solo la tuya. |
| `vacation-tracker` | `get_leaves`, `get_holidays` | Tus licencias y feriados. Pendiente (D-28). |

## Las cuentas las hace el código

Un modelo de lenguaje no calcula: **estima**. En las pruebas, el modelo tomó dos sábados como días hábiles y redondeó 40 minutos a 0,5 h. Por eso todas las cuentas están en `bia-workdays`, con pruebas automáticas (D-37, D-39), y eso además permite usar un modelo barato.

## El modelo

El agente tiene fijado **GPT-6 Luna** (D-38): pasa las pruebas críticas y consume unas 17 veces menos créditos que GPT-5.4. Ojo con dos detalles:

- **En Copilot CLI, abrí el agente con `copilot --agent bia-time-agent`.** Si lo elegís con `/agent` dentro de una sesión, puede correr con otro modelo (problema conocido de Copilot CLI).
- **La app de GitHub Copilot no respeta el modelo del agente:** elegí GPT-6 Luna a mano en el selector. Nunca un modelo mini o flash.

# Seguridad y permisos

| Capa | Qué protege |
|---|---|
| **Herramientas habilitadas** | El agente solo ve las herramientas de la tabla. No tiene correo, chats ni la herramienta web. Tiene la lectura de archivos locales para su configuración personal; ese límite lo ponen sus instrucciones, no la herramienta. |
| **Solo tus datos** | Opera con tu usuario de Redmine y tu cuenta de Microsoft 365. No consulta datos de otras personas. |
| **Datos mínimos** | Del calendario, solo metadatos (nivel 0): nunca el cuerpo de una invitación ni nombres o correos de terceros (D-13). |
| **Límites por código** | `bia-m365` y `bia-workdays` tienen la ruta, los campos y las entradas fijados en el código: no dependen de que el modelo se porte bien (D-33, D-35). |
| **Microsoft 365, sin IA y sin escritura** | `bia-m365` lee Microsoft Graph directamente, con el registro de aplicación de BIA: solo permisos delegados de lectura, sin secretos (D-53). Tu sesión queda cifrada en tu máquina, con la clave en el llavero de macOS o protegida por Windows. Desde la v0.16.0 el agente no usa Work IQ. |
| **Confirmación** | Toda carga se confirma sobre el conjunto exacto. No hay forma de saltearla (D-11). |
| **Aprobación del host** | Copilot pide aprobar cada uso de `createTimeEntry`. **Nunca elijas "Always allow" para esa herramienta** (D-43). |
| **Contenido externo** | Lo que dice un issue, un comentario o un evento del calendario es un dato, nunca una instrucción. |

# El repositorio

```
bia-da-agentic/
├── agent.yaml                          La definición del agente: núcleo, herramientas, modelo, reglas de BIA
├── .claude/skills/                     Las 13 skills (y la versión del agente para Claude, generada)
├── .github/agents/                     El agente para GitHub Copilot (generado)
├── mcp/bia-workdays/                   MCP propio: fechas, feriados y cuentas de horas
├── mcp/bia-m365/                       MCP propio: Microsoft 365 vía Microsoft Graph (D-53)
├── mcp/bia-calendar/                   Lógica del calendario (la usa bia-m365)
├── scripts/build.mjs                   Genera, valida e instala
├── scripts/baseline-carga.mjs          Mide la línea base de carga de un equipo
├── templates/config.yaml               Plantilla de la configuración personal
└── docs/                               Seguridad, criterios de aceptación, guiones de prueba, línea base y mejoras pendientes
```

## ¿Por qué hay una definición y archivos "generados"?

`agent.yaml` es la **única fuente**. A partir de ella, `npm run build` genera el agente para GitHub Copilot y su equivalente para Claude. Así las reglas se escriben una sola vez. El build además **falla** si el agente supera el límite de 30.000 caracteres de Copilot, o si alguna instrucción quedó mal escrita.

## Los comandos

| Comando | Qué hace |
|---|---|
| `npm run build` | Regenera los archivos del agente desde `agent.yaml`. |
| `npm run check` | Valida las skills y que los archivos generados estén al día. |
| `npm test` | Corre las pruebas automáticas de los MCP propios (todas tienen que pasar). |
| `npm run install-user` | Instala el agente, las skills y los MCP propios en tu máquina, y crea tu configuración personal si no existe. |
| `npm run smoke:workdays` · `npm run smoke:m365` | Pruebas de humo de los MCP instalados. |

# Decisiones de diseño

Las principales, con su detalle en **Evolución**:

- **Todo local, salvo lo imprescindible** (D-01). Los MCP remotos solo como excepción (Vacation Tracker, D-05).
- **Configuración personal obligatoria**, validada en cada pedido (D-32).
- **La jornada es un piso, no un techo** (D-30). Las licencias son de medio día o día completo (D-41) y se cargan en BIA - Absentismo, en el issue de su tipo; la tabla está en código y el agente nunca pregunta el motivo (D-46).
- **El issue que escribís en la cita cuenta, sin leer la cita** (D-48): solo se extrae el número, por código, en tu máquina. **El prefijo de cliente resuelve el proyecto solo si es firme** (D-49): una palabra exacta del nombre del proyecto o el cliente que declaraste.
- **La versión es verificable** (D-50): el agente instalado lleva su versión, y `get_version` dice si estás al día.
- **Granularidad de BIA:** múltiplos de 0,5 h, siempre hacia arriba (D-21). Nunca se agrupan días distintos (D-23), ni actividades de distinta confianza (D-44).
- **Las cuentas, en código** (D-37, D-39). **Las reglas que siempre aplican, en el núcleo** (D-42).
- **Confirmación sobre el conjunto exacto** y aprobación del host como segunda barrera (D-11, D-43).

# Dónde se puede usar

| Aplicación | Estado |
|---|---|
| **GitHub Copilot CLI (macOS)** | ✅ Probado completo. Abrir con `copilot --agent bia-time-agent`. |
| **App de GitHub Copilot (macOS)** | ✅ Probado, eligiendo el modelo a mano en el selector. |
| **Windows** | 🟡 Pendiente de validar (D-20), con el guion reducido. |
| **VS Code** | 🟡 Pendiente de validar (D-20). |
| **Claude Code** | 🟡 Pendiente de validar (D-20). |

# Ejemplos de lo que podés esperar

| Le pedís | Qué hace |
|---|---|
| *"¿Qué días me faltan cargar este mes?"* | La revisión completa del mes, con los huecos, los no laborales, las licencias por cargar y las licencias posibles. |
| *"Revisá desde mi última carga"* | Encuentra tu última carga y revisa desde el día siguiente. |
| *"Cargame 40' hoy en el issue 12345 como meeting"* | Propone **1,0 h** (granularidad de BIA), revisa duplicados y pide confirmación. |
| *"Cargame 1 hora de lunes a viernes de la semana pasada en el issue 12345"* | Cinco cargas, una por día hábil, con una sola confirmación del conjunto. |
| *"Recuperá las horas del martes"* | Lee tu calendario de ese día y propone cargas con su confianza, para que confirmes. |
| *"Cambiá la carga de ayer a 2 horas"* | Te explica que modificar cargas no está habilitado en esta versión. |
