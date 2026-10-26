---
name: identify-working-days
description: Calcula, para cada día de un período, cuántas horas como mínimo debería tener cargadas el colaborador según su jornada declarada, los días laborales de BIA y los feriados (de Vacation Tracker o, como respaldo, de Nager.Date), e identifica sus licencias en Vacation Tracker, que en BIA se cargan en el proyecto BIA - Absentismo. Solo lectura.
---

# Identify working days

## Cuándo usarlo

Antes de revisar huecos de carga de un período, o cuando haga falta saber cuántas horas corresponden a un día.

## Resultado

Para cada día del período:

- jornada esperada: horas mínimas (0 si ese día no corresponde trabajar), o "sin piso" si la jornada es `variable`;
- motivo: día laboral, fin de semana o feriado (con su nombre);
- licencias del día: aprobada (con su tipo de licencia y si es de día completo, de medio día o parcial) o pendiente;
- fuente de cada dato;
- datos que no se pudieron verificar.

## 1. Jornada: configuración personal

1. Leer `jornada_horas` y `entra_id` del archivo de configuración personal (ya validado antes de atender el pedido):
   - macOS y Linux: `~/.bia-time-agent/config.yaml`
   - Windows: `%USERPROFILE%\.bia-time-agent\config.yaml`
2. Si `jornada_horas` es 4, 6 u 8, ese es el mínimo de horas de cada día laboral.
3. Si es `variable`, los días laborales no tienen piso: solo importa si tienen alguna carga.
4. Leer solo ese archivo. No leer otros archivos locales.

## 2. Días laborales: regla de BIA

En BIA se trabaja de lunes a viernes. Sábados y domingos tienen jornada esperada 0.

**El día de la semana de cada fecha se obtiene siempre con `get_calendar_days` (MCP `bia-workdays`), nunca de memoria.** Esa herramienta devuelve, para cada día del período, su día de la semana, si es fin de semana y si es feriado nacional, calculado por código.

## 3. Identidad y licencias: Vacation Tracker

1. Armar el ID de Vacation Tracker del colaborador: `microsoft-` seguido de su `entra_id`.
2. Consultar `get_leaves` para el período con `user` igual a ese ID y `status: all`. Nunca consultar licencias sin el filtro `user`.
3. Obtener con `getCurrentUser` el correo del colaborador en Redmine y compararlo con el `user.email` de cada licencia devuelta.
   - Si alguna licencia tiene otro correo, o si Vacation Tracker responde que no encuentra al usuario, frenarse: avisar que el `entra_id` del archivo podría estar mal y no usar ninguna licencia.
4. Según el estado de cada licencia:
   - `approved`: se pasa a `classify_period` con su tipo de licencia (`leave_type`, el nombre del tipo en Vacation Tracker, por ejemplo `Vacation` o `Flex`). Si tiene `partialDay` con horario, con esas horas; si no, como día completo. `classify_period` solo acepta medio día o día completo: otras horas vuelven como `horas_no_estandar`, sin horas, y se preguntan.
   - `pending`: se muestra marcada como pendiente y **no** se pasa a `classify_period`.
   - `denied`: se ignora.
5. **Las licencias no descuentan horas de la jornada (D-46).** En BIA, toda licencia de Vacation Tracker también se carga en Redmine, en el proyecto **BIA - Absentismo**, en el issue de su tipo. Un día de licencia ya cargado ahí está completo; si no está cargado, `classify_period` lo informa en `leaves_to_load` (una entrada por licencia, con issue, tipo y horas), conciliando cada licencia con las cargas de su propio issue. La tabla de tipos e issues sale de `get_absence_issues` (MCP `bia-workdays`): nunca buscar esos issues en Redmine ni leer sus descripciones.
6. No encontrar licencias no prueba que no existan: informarlo como "sin licencias registradas en Vacation Tracker para el período".

## 4. Feriados: Vacation Tracker

1. Determinar la ubicación del colaborador:
   - si alguna de sus licencias trae `user.location`, usar esa. Si en el período no hay licencias, consultar las del año en curso con el mismo filtro `user`;
   - si no tiene ninguna licencia en el año, consultar `get_holidays` sin ubicación para los años del período. Si todas las ubicaciones tienen los mismos feriados en el período, usar esa lista: la ubicación no cambia el resultado;
   - si las listas difieren, mostrar los nombres de las ubicaciones y preguntarle al colaborador cuál es la suya. No adivinarla.
2. Con la ubicación conocida, consultar `get_holidays` para esa ubicación y cada año que abarque el período.
3. Un feriado de la ubicación es día no laborable: jornada esperada 0.

## 5. Si Vacation Tracker no está disponible: plan alternativo

Vacation Tracker es la fuente de verdad, porque refleja la política de BIA. Si no responde (por ejemplo, porque la aplicación no puede autenticarse), seguir este orden:

**Feriados**
1. Usar los feriados que devuelve `get_calendar_days` (o `get_public_holidays`) del MCP local `bia-workdays`. Son los feriados nacionales de Argentina desde Nager.Date, una fuente pública.
2. Usarlos como días no laborables, pero aclarar siempre en el resultado que son "feriados nacionales de una fuente pública, que pueden no incluir días no laborables propios de BIA".
3. Si `bia-workdays` responde pero no pudo obtener los feriados (un aviso en `warnings`), informarlo y **no** excluir días en silencio: preguntar al colaborador si algún día del período fue feriado.
4. Si el MCP `bia-workdays` no está disponible, no seguir: aplicar la regla del núcleo (informarlo, pedir que se verifique su registro y se reinicie la aplicación, y no calcular ni registrar nada).

**Licencias**
1. Las ya cargadas en BIA - Absentismo están verificadas por Redmine: `classify_period` las reconoce solas.
2. Usar las declaradas en `ausencias` del archivo de configuración personal, si existen, pasando su `licencia` como `leave_type`.
3. Si no hay ninguna declarada, las licencias quedan sin verificar: `classify_period` indica en qué días una licencia podría explicar el hueco (`possible_leave`), y solo por esos días se pregunta, junto con su tipo de licencia, para proponer la carga en el issue que corresponde.

En BIA las licencias son de **medio día** (la mitad de la jornada) o de **día completo**. En `ausencias`, cada licencia se declara con `tipo: medio_dia` o `tipo: dia_completo`, y opcionalmente su `licencia` (`vacaciones`, `flex`, `dias_de_estudio` u `otras_licencias`).

Indicar siempre qué fuente se usó para cada dato y por qué no se usó Vacation Tracker.

## Reglas

- No inventar jornada, feriados ni licencias.
- Nunca preguntar, inferir ni mostrar el motivo de una licencia.
- No usar, mostrar ni comentar datos de otras personas.
- Esta skill no consulta horas cargadas: eso lo hace `review-time-period`.
