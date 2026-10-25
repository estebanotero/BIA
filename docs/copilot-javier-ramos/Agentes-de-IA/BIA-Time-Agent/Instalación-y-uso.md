[[_TOC_]]

# Overview

Esta página te guía para **instalar BIA Time Agent en tu máquina y empezar a usarlo**. No hace falta saber nada del agente: seguí los pasos en orden. Lleva unos 30 minutos la primera vez.

> **Qué vas a tener al final:** un asistente en GitHub Copilot al que le podés pedir, en castellano, cosas como *"¿qué días me faltan cargar este mes?"* o *"cargame una hora hoy en el issue 12345 como meeting"*. Te muestra lo que va a hacer y **nunca carga nada sin tu confirmación**.

Para entender cómo funciona por dentro, ver **Arquitectura**.

# Antes de empezar

Necesitás:

| Qué | Cómo verificarlo |
|---|---|
| **Node.js 20 o superior** | `node --version` en la terminal |
| **Git** | `git --version` |
| **GitHub Copilot CLI** (o la app de GitHub Copilot) | `copilot --version` |
| **GPT-6 Luna habilitado** en tu GitHub Copilot | En Copilot, `/model`: tiene que aparecer *GPT-6 Luna* |
| **El MCP de Redmine** registrado con el nombre `redmine` | Ver la página *MCP de Redmine* de esta wiki. Verificá con `copilot mcp list` |
| **Tu cuenta de Redmine en UTC** | Ver el paso 2 |
| **Tu cuenta de BIA en Microsoft 365** (para recuperar horas desde el calendario) | No hace falta licencia de Microsoft 365 Copilot: el registro de aplicación de BIA ya tiene el consentimiento del administrador |

> En **Windows**, usá PowerShell. Si PowerShell no te deja correr `npm`, corré una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y abrí una terminal nueva.

# Paso 1: descargar e instalar

**macOS:**

```bash
mkdir -p ~/Projects && cd ~/Projects
git clone https://cloudbia.visualstudio.com/BIA%20-%20Data%20Analytics/_git/bia-da-agentic
cd bia-da-agentic
npm install
npm run install-user
```

**Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force $env:USERPROFILE\Projects | Out-Null
cd $env:USERPROFILE\Projects
git clone https://cloudbia.visualstudio.com/BIA%20-%20Data%20Analytics/_git/bia-da-agentic
cd bia-da-agentic
npm install
npm run install-user
```

`npm run install-user` instala el agente y sus procedimientos, crea tu **configuración personal** y, al final, te muestra **dos comandos** que empiezan con `copilot mcp add`. Corrélos tal cual, uno por uno: registran los dos servidores propios del agente (`bia-workdays` y `bia-m365`). Si tenías una versión anterior a la 0.16.0, además te va a pedir quitar `bia-calendar`: `copilot mcp remove bia-calendar`.

# Paso 2: tu configuración personal

El agente necesita dos datos tuyos, y **no atiende ningún pedido hasta que estén completos**.

Abrí el archivo:

- **macOS:** `open -e ~/.bia-time-agent/config.yaml` (o `code ~/.bia-time-agent/config.yaml` si usás VS Code)
- **Windows:** `notepad $env:USERPROFILE\.bia-time-agent\config.yaml`

Completá:

```yaml
entra_id: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d   # tu ID de Entra (ver abajo)
jornada_horas: 8                                # 4, 6, 8 o variable
```

**Cómo encontrar tu ID de Entra:** entrá a https://entra.microsoft.com, abrí tu perfil y copiá el **"ID de objeto"**. O, si tenés Azure CLI: `az ad signed-in-user show --query id -o tsv`.

**La jornada** son las horas mínimas que tenés que cargar por día hábil: 8, 6 o 4, o `variable` si tu contrato es por horas reales. Es un piso, no un techo: cargar más está bien.

**Licencias (opcional):** mientras Vacation Tracker no funcione en GitHub Copilot, podés declarar tus licencias en el mismo archivo. En BIA son de medio día o de día completo. Si además indicás la `licencia` (`vacaciones`, `flex`, `dias_de_estudio` u `otras_licencias`), el agente te propone cargarla en su issue de BIA - Absentismo:

```yaml
ausencias:
  - desde: 2026-12-21
    hasta: 2026-12-31
    tipo: dia_completo
    licencia: vacaciones
```

Las licencias que ya cargaste en BIA - Absentismo no hace falta declararlas: el agente las ve en Redmine.

**Prefijos de cliente (opcional):** si tus citas empiezan con un prefijo de cliente ("TEN - Ajuste tablero"), el agente lo usa para encontrar el proyecto entre los que cargaste en las últimas 8 semanas. En Redmine los proyectos siguen la convención `PREFIJO - Nombre` ("TEN - CFO Dashboard"), así que **en general no tenés que declarar nada**: el agente los encuentra solo por el prefijo.

Declará un prefijo **solo si vos lo usás distinto que en Redmine**. Separá los sinónimos con comas y poné el cliente:

```yaml
prefijos_cliente:
  COOPE, COO: Coopealianza          # vos le decís COOPE; en Redmine es "COO - ..."
  TECPE, TECP, TECM: Tecpetrol
```

Declarar un cliente siempre **suma** proyectos, nunca los resta.

**Reuniones uno a uno (opcional):** si agendás tus 1:1 con las iniciales de los dos ("1:1 JR:ACT", "JR/FPM", "Sync JR/FPM"), declará a qué issue va cada uno y el agente los resuelve solo:

```yaml
uno_a_uno:
  mis_iniciales: JR
  personas:                         # con quién → issue (y comentario opcional)
    FPM: 9725
    AS: { issue: 10725, comentario: Sync Operacion }
  mi_equipo: [ACT, DGV, EO]         # iniciales de quienes te reportan
  issue_mi_equipo: 3439
  resto: 10725                      # cualquier otro 1:1 (por ejemplo, freelance)
```

Escribí las iniciales en **mayúsculas** en tus citas: así el agente las distingue del texto. `personas` y `mi_equipo` dan confianza alta; `resto`, media, y solo si el asunto dice "1:1".

## La zona horaria de tu cuenta de Redmine

Es un requisito, igual que el ID de Entra. En Redmine, entrá a **Mi cuenta → Preferencias → Zona horaria**, elegí **UTC** (o dejala en blanco) y guardá.

**Por qué:** el servidor de Redmine de BIA está en UTC. Si tu cuenta tiene otra zona (por ejemplo, Buenos Aires), Redmine corre un día todos los filtros por fecha: si pedís las horas de hoy, te muestra las de mañana. Es un error conocido de Redmine, y afecta a la web y a los reportes. El agente lo compensa igual, pero con la zona en UTC tus consultas en la web también dan bien.

**Lo que tenés que saber al cambiarla:** Redmine pasa a usar la hora de Londres, que va tres horas adelante. Entre las 21:00 y las 24:00 de Argentina, en Londres ya es el día siguiente, así que:

> ⚠️ **Si cargás horas en la web de Redmine después de las 21:00, revisá la fecha antes de guardar.** El formulario propone por defecto la fecha de mañana.

Pasa poco: en DA, entre julio y septiembre de 2026, solo el 0,2 % de las cargas se hicieron en esa franja. Además, las horas de los historiales se ven tres horas adelantadas. El agente no tiene este problema en ningún horario: calcula la fecha en hora de Argentina.

Para verificarlo, en la carpeta del agente:

```bash
npm run check:redmine
```

Tiene que decir `OK: los filtros de fecha de Redmine funcionan bien con tu cuenta`. Si dice "ATENCIÓN", revisá la zona horaria y volvé a correrlo.

# Paso 3: tu sesión de Microsoft 365

Para que el agente proponga cargas a partir de tus reuniones, iniciá sesión una sola vez:

```bash
npm run m365-login
```

Se abre el navegador: iniciá sesión con tu cuenta de BIA. Al terminar, la terminal muestra tu nombre y cuántos eventos tenés hoy. Desde ahí la sesión se renueva sola.

- **No hace falta licencia de Microsoft 365 Copilot ni Work IQ:** el agente lee tu Microsoft 365 directamente con su propio servidor (`bia-m365`), usando el registro de aplicación de BIA, que solo tiene permisos de lectura.
- **Tu sesión queda cifrada** en tu máquina, con la clave guardada en el llavero de macOS o protegida por Windows. Nunca se guarda en texto plano.
- **Para ver si sigue válida:** `npm run m365-status`. **Para cerrarla:** `npm run m365-logout`.

# Paso 4: verificar

```bash
npm run smoke:workdays     # tiene que listar los feriados del año
npm run check:redmine      # tiene que decir OK (zona horaria de Redmine)
npm run smoke:m365         # necesita el paso 3
```

# Paso 5: usarlo

Abrí el agente **así** (no lo elijas después con `/agent`, porque puede correr con otro modelo):

```bash
copilot --agent bia-time-agent
```

**En la app de GitHub Copilot:** abrí una conversación nueva con el agente y **elegí GPT-6 Luna en el selector de modelos**. La app no respeta el modelo del agente, y con un modelo mini o flash el agente se saltea reglas.

La primera vez que el agente lea tu configuración, Copilot te va a pedir permiso: **aprobalo**.

**Probá con:**

| Le pedís | Qué hace |
|---|---|
| *"¿Qué días me faltan cargar este mes?"* | Revisa el mes contra tu jornada, sin contar fines de semana ni feriados. |
| *"Revisá desde mi última carga"* | Encuentra tu última carga y revisa desde el día siguiente. |
| *"Cargame 40' hoy en el issue 12345 como meeting"* | Propone **1 h** (las cargas van en múltiplos de media hora, redondeando hacia arriba) y te pide confirmación. |
| *"Recuperá las horas del martes"* | Lee tu calendario de ese día y te propone cargas. Necesita el paso 3. |

# Reglas para usarlo bien

- **Revisá siempre lo que te propone antes de confirmar.** Fecha, issue, actividad, horas y comentario.
- **Nunca elijas "Always allow" para `createTimeEntry`** cuando Copilot te pida aprobar la herramienta. Esa aprobación es una segunda barrera antes de escribir en Redmine: elegí "Use this MCP tool" una vez, después de revisar.
- **En la app, elegí siempre GPT-6 Luna.** Nunca un modelo mini o flash.
- **Ojo en la web de Redmine después de las 21:00:** con tu cuenta en UTC, Redmine usa la hora de Londres, así que al cargar horas a la noche la fecha que propone por defecto es la de mañana. Revisala antes de guardar. El agente no tiene ese problema.

# Actualizar

Cuando haya una versión nueva:

```bash
cd ~/Projects/bia-da-agentic     # en Windows: cd $env:USERPROFILE\Projects\bia-da-agentic
git pull
npm install
npm run install-user
```

Después, **reiniciá Copilot del todo** (en la CLI, `/exit`; la app, cerrala por completo) **y abrí una conversación nueva**. Una conversación vieja sigue usando la versión anterior del agente.

**Para saber qué versión estás usando**, preguntale al agente:

    ¿Qué versión de BIA Time Agent estoy usando?

Te responde con la versión instalada, el commit y la rama, y uno de estos estados:

| Estado | Qué significa | Qué hacer |
|---|---|---|
| **Al día** | La instalación coincide con **tu copia local** del repo. | Nada. Para traer lo publicado más reciente, primero actualizá esa copia (`git pull` en `main`). |
| **Desactualizada** | Tu copia del repo tiene una versión más nueva que la instalada. | `npm run install-user` y reiniciar Copilot. |
| **Adelantada** | Instalaste desde otra rama una versión más nueva que tu copia del repo. | No reinstalar desde ese repo, porque bajarías de versión: primero `git pull` o volver a la rama desde la que instalaste. |
| **Inconsistente** | El agente y sus MCP no son de la misma versión. | `npm run install-user` desde `main` y reiniciar Copilot del todo. |
| **Desconocido** | Falta el registro de la instalación (instalaciones anteriores a la v0.15.0) o no se puede leer el repo. | Seguí los pasos que te indica el agente. |

El control no consulta Azure DevOps: compara contra tu copia local. Instalá siempre desde la rama `main`: `npm run install-user` te avisa si estás en otra.

# Problemas frecuentes

| Qué ves | Qué hacer |
|---|---|
| El agente dice que falta tu configuración o que un dato es inválido | Revisá `entra_id` y `jornada_horas` en tu configuración (paso 2). |
| El agente dice que `bia-workdays` no está disponible | Verificá con `copilot mcp list` que esté registrado; si no, corré el comando `copilot mcp add bia-workdays ...` que muestra `npm run install-user`. Reiniciá Copilot. |
| El agente responde corto o se saltea partes | Revisá el modelo: en la app, elegí GPT-6 Luna; en la CLI, abrí con `copilot --agent bia-time-agent`. |
| Al recuperar horas dice que no hay sesión de Microsoft 365 o que venció | Corré `npm run m365-login` en la carpeta del repo y reiniciá Copilot. |
| Los cambios de una actualización no se ven | Reiniciá Copilot del todo y abrí una conversación nueva. |
| En la web de Redmine, al filtrar horas por fecha aparecen las de otro día | Tu cuenta no está en UTC: ver el paso 2. Verificalo con `npm run check:redmine`. |
| Copilot te pide aprobar `createTimeEntry` y no confirmaste ninguna carga | Elegí **"Don't use"**: el agente tiene que mostrarte primero lo que va a cargar. |
