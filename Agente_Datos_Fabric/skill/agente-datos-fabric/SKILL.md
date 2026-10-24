---
name: agente-datos-fabric
description: Arma y mejora un Fabric data agent con preguntas y respuestas validadas por el área de negocio. Redacta instrucciones del agente y de cada fuente, propone preguntas para el banco (ejemplos y evaluación), analiza las fallas de una evaluación y propone cambios, y responde preguntas usando la herramienta preguntar_agente_fabric. Usar cuando se pida crear o mejorar el agente de datos, cargar preguntas al banco, revisar una evaluación o consultar datos de Fabric.
---

# Agente de datos en Fabric

El framework está en `Agente_Datos_Fabric/` del repo BIA. El agente que responde es un **Fabric data agent**. Vos no lo entrenás: lo mejorás con tres palancas que el área de negocio valida.

| Palanca | Dónde vive | Qué cambia |
|---|---|---|
| Instrucciones | `instrucciones_agente.md` → agente y cada fuente SQL | Reglas, terminología y a qué fuente mandar cada pregunta |
| Ejemplos (pregunta + consulta) | `banco_preguntas.csv` con uso `EJEMPLO` → *example queries* | Cómo se arma el SQL para preguntas parecidas. El agente toma los 3 más parecidos |
| Evaluaciones (pregunta + respuesta esperada) | `banco_preguntas.csv` con uso `EVALUACION` → `NB_AGT_03` | Nada en el agente: miden si mejoró o empeoró |

Si te dicen "entrenar el agente", aclaralo: acá significa curar ejemplos e instrucciones y medir con evaluaciones. No hay fine-tuning.

Hay cuatro tareas. Identificá cuál te piden antes de empezar.

## A. Redactar instrucciones

Entrada: el diccionario de datos (`diccionario.md` de la skill `documentar-modelo-semantico`), la metadata gold (`meta.GOLD_OBJECT` de `Pipeline_Metadata_Medallion`), las vistas del esquema `agente` y lo que te cuente el área.

1. Completá `plantillas/instrucciones_agente.md`. Respetá los marcadores `<!-- BLOQUE:... -->`: `NB_AGT_02` los lee por nombre.
2. **Descripción del agente**: qué responde, de qué período, cada cuánto se actualiza y **qué no tiene**. Es lo que lee Claude para decidir si llamar al agente, así que tiene que ser concreta.
3. **Instrucciones del agente**: las cinco secciones de la plantilla. Cada término de negocio con su definición exacta (qué columna, qué filtro). Si una definición no está confirmada, `[dato a confirmar]`.
4. **Instrucciones de cada fuente SQL**: tablas, granularidad, joins y filtros típicos. Nombres reales de vistas y columnas, nunca inventados.
5. Si una fuente es un **modelo semántico**, no le escribas instrucciones de fuente: el agente las ignora para generar DAX. Decí qué cargar en *Prep data for AI* del modelo (esquema para IA, instrucciones de IA, respuestas verificadas).
6. Cerrá con la lista de `[dato a confirmar]` y a quién del área preguntárselos.

## B. Proponer preguntas para el banco

Entrada: un tema o área ("preguntas de Comercial sobre ventas"), un log de preguntas reales (`FABRIC_AGENT_LOG` del proxy MCP) o el CSV de fallas de una evaluación.

1. Usá las columnas de `plantillas/banco_preguntas.csv`. Toda fila nueva va con `estado = PROPUESTA` y `origen = CLAUDE` (o `FEEDBACK` si vino del log). **Nunca pongas `VALIDADA`**: eso lo hace el área, con nombre y fecha.
2. Escribí la pregunta como la diría alguien del área, no como la escribiría un analista.
3. `uso`:
   - `EJEMPLO` para enseñar un patrón de consulta (un ranking, una comparación, un filtro difícil). La consulta va en el dialecto de la fuente: T-SQL para lakehouse y warehouse, KQL para eventhouse. Solo `SELECT` o `WITH`.
   - `EVALUACION` para medir. **Período cerrado y explícito** ("marzo de 2026", no "el mes pasado"), para que la respuesta esperada no cambie sola. `respuesta_esperada = [dato a confirmar]`: el número lo confirma el área corriendo la `consulta_referencia`.
   - Nunca la misma pregunta (ni una reformulación casi igual) como ejemplo y como evaluación: la evaluación mediría memoria. `NB_AGT_01` lo rechaza.
4. Cubrí las preguntas frecuentes **y** las difíciles: ambigüedades ("ventas" bruto o neto), períodos, rankings, comparaciones, preguntas que el agente debe rechazar porque el dato no existe (con `respuesta_esperada` del estilo "No hay datos de stock").
5. Sin datos personales en preguntas ni respuestas: nada de nombres de personas, emails, DNI o CUIT.
6. Proporción orientativa por área: 10 a 20 ejemplos y 20 a 40 evaluaciones para empezar.

## C. Analizar una evaluación

Entrada: `<fecha>_<evaluation_id>_fallas.csv` de `NB_AGT_03` y, si hay, el resumen de `agente_ctl.eval_historial`.

1. Clasificá cada falla en **una** causa:

| Causa | Señal | Cambio que proponés |
|---|---|---|
| Término mal entendido | Usó otra columna o filtro para un concepto de negocio | Instrucción del agente (terminología) |
| Fuente equivocada | Fue al lakehouse cuando era un KPI del modelo, o al revés | Descripción de fuentes e instrucciones de ruteo |
| Patrón de SQL difícil | Ranking, período o join mal armado | Un ejemplo nuevo **con otra pregunta** del mismo patrón |
| Esquema confuso | Columnas ambiguas o tablas de más | Vista nueva o renombrada en `sql/01_vistas_agente.sql`, o sacar tablas de la selección |
| Respuesta esperada vieja o mal | El agente tiene razón | Volver al área para revalidar esa fila |
| Juez equivocado | Mismo dato con otro formato, marcado como incorrecto | Ajustar `CRITIC_PROMPT` o el formato de la respuesta esperada |
| Dudosa | El juez no contestó yes/no | Revisar a mano |

2. Entregá una tabla con `pregunta_id`, causa, evidencia (la parte de la respuesta que lo muestra) y cambio propuesto.
3. Agrupá los cambios por palanca y ordenalos por cuántas fallas arreglan.
4. **Nunca propongas copiar la pregunta que falló como ejemplo.** Arregla esa pregunta y nada más, y la evaluación deja de medir algo real. El ejemplo tiene que enseñar el patrón con otra pregunta.
5. Cerrá con qué tiene que validar el área antes de aplicar nada.

## D. Responder preguntas con el agente

Si tenés la herramienta `preguntar_agente_fabric`:

1. Mandá una pregunta concreta por llamada, con período. Si el usuario no dio período, preguntale antes.
2. Para análisis que necesitan varios datos, hacé varias preguntas simples y combiná vos las respuestas. Decí qué calculaste vos y qué vino del agente.
3. Citá siempre que el dato viene del agente de Fabric y el período.
4. Si el agente dice que no sabe o devuelve un error, decilo. No completes con estimaciones.
5. Si la respuesta parece rara (un orden de magnitud distinto, un mes vacío), decilo y sugerí anotarla como candidata para el banco (tarea B, `origen = FEEDBACK`).

## Reglas

- No escribís en Fabric. Generás archivos (CSV, Markdown, SQL) que una persona revisa; los notebooks los aplican con `DRY_RUN` primero.
- No inventes nombres de tablas, columnas ni cifras. Si falta algo, `[dato a confirmar]`.
- Lo que valida el área es lo que vale. Si el área dice que una respuesta es correcta y el dato dice otra cosa, señalalo, pero no cambies la fila.
