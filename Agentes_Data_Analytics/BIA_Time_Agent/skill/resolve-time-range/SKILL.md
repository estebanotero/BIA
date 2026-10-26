---
name: resolve-time-range
description: Convierte expresiones de tiempo como "ayer", "el martes", "la semana pasada", "los últimos 10 días" o "desde mi última carga" en un rango de fechas exacto y lo muestra para que el colaborador lo valide. Solo lectura.
---

# Resolve time range

## Cuándo usarlo

Cuando el colaborador pide revisar, recuperar o cargar horas de un período expresado en lenguaje natural.

## Resultado

- Fecha de inicio y fecha de fin (AAAA-MM-DD), ambas inclusive.
- La expresión original y cómo se interpretó.
- La fecha de hoy usada como referencia.
- Para "desde mi última carga": la fecha de la última carga encontrada.

## Flujo

1. Obtener la fecha de hoy con `get_today` (MCP `bia-workdays`). Nunca suponerla ni tomarla de memoria. Si la herramienta no responde, no pedir la fecha ni calcularla: aplicar la regla del núcleo para cuando `bia-workdays` no está disponible.
2. Resolver la expresión con estas convenciones:
   - "hoy" y "ayer": un solo día.
   - Un día de la semana sin otra referencia ("el martes"): el más reciente, anterior o igual a hoy.
   - "Esta semana": de lunes a hoy. "La semana pasada": de lunes a domingo de la semana anterior.
   - "Este mes": del día 1 a hoy. "El mes pasado": el mes calendario anterior completo.
   - "Los últimos N días": los N días corridos que terminan hoy, incluido hoy.
   - Fechas o rangos explícitos: tal como los dio el colaborador.
3. Para "desde mi última carga":
   1. Consultar con `getTimeEntries` las entradas del usuario autenticado de los últimos 31 días.
   2. Si no hay ninguna, ampliar a los últimos 90 días. Si sigue sin haber, informarlo y pedir una fecha de inicio. No ampliar más por cuenta propia.
   3. Tomar la fecha más reciente con horas cargadas. El rango empieza el día siguiente y termina hoy.
   4. Si la última carga es de **hoy** (o posterior), no hay días después de ella: no armar un rango invertido. Informar que la última carga es de hoy y ofrecer revisar un período anterior (por ejemplo, esta semana o el mes), sin afirmar que los días anteriores están completos.
4. Para expresiones que dependen del día de la semana ("el martes", "esta semana", "la semana pasada"), obtener los días de la semana con `get_calendar_days`. Nunca calcularlos de memoria.
5. Mostrar el rango resuelto antes de usarlo. Si la expresión admite más de una lectura, mostrar las alternativas y pedir que elija.

## Reglas

- No extender un rango a fechas futuras.
- Si el rango supera los 92 días, confirmarlo con el colaborador y avisarle que se va a revisar **por tramos consecutivos de hasta 92 días**, porque las herramientas de `bia-workdays` no aceptan más. Cada tramo tiene su propio resultado; nunca sumar tramos de memoria.
- Esta skill no decide qué días son laborables: eso lo hace `identify-working-days`.
