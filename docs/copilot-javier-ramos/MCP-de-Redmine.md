[[_TOC_]]

[[_TOSP_]]


# Cómo levantar el MCP de Redmine en Windows (PowerShell)

Guía para que el equipo pueda replicar en sus máquinas Windows lo que mostramos en la Weekly: conversar con Redmine en lenguaje natural (buscar issues, cargar horas, etc.) usando Copilot CLI + un servidor MCP de Redmine.

> Requisitos previos: PowerShell 7+ (recomendado), acceso a Redmine, y una **licencia activa de GitHub Copilot**. Sin licencia no vas a poder instalar/usar Copilot CLI (nos pasó en la Weekly: quien no tenía licencia quedó afuera de esta parte, aunque sí pudo seguir el resto por chat en Copilot 365/VS Code).

> ⚠️ **Ojo con la confusión**: la extensión **GitHub Copilot en VS Code** (la que ya usan a diario) y **GitHub Copilot CLI** (lo que instalamos acá, para usar desde la terminal) son dos productos distintos. Tener uno instalado no significa tener el otro.

---

## Paso 1 — Verificar/instalar Node.js

### Antes de empezar: verificá tu versión de PowerShell

El requisito recomendado es usar **PowerShell 7+**. Ojo que Windows trae de fábrica Windows PowerShell 5.1, así que es fácil creer que estás en 7 y no estarlo. Validá con:

```powershell
$PSVersionTable.PSVersion
```

Si el `Major` es menor a 7, actualizá con:

```powershell
winget upgrade Microsoft.PowerShell
```

> Aporte de **@<84D51FA6-8E6D-696A-BC9C-4ADD79FDC3F7>** post-Weekly: le pasó exactamente esto — tenía una versión vieja y la guía no explicaba cómo chequearlo.

Abrí **PowerShell** y verificá versiones:

```powershell
node --version
npm --version
npx --version
```

Necesitamos **Node.js 18 o superior**. Si no está instalado:

```powershell
winget install OpenJS.NodeJS.LTS
```

Cerrá y volvé a abrir PowerShell después de instalar, y verificá de nuevo con los comandos de arriba.

---

## Paso 2 — Instalar GitHub Copilot CLI

En Windows hay dos formas oficiales (con `winget` o con `npm`):

```powershell
# Opción A: winget (recomendado)
winget install GitHub.Copilot

# Opción B: npm
npm install -g @github/copilot
```

Verificá la instalación:

```powershell
copilot --version
```

Si el comando no se reconoce, **cerrá completamente la ventana de PowerShell y abrí una nueva** (no alcanza con "seguir escribiendo"): el instalador modifica el PATH y solo se recarga en una sesión nueva.

> 🔴 **Problema real en la Weekly**: a varias personas `npm install -g @github/copilot` les tiró **"Security error / security exception"**, incluso ejecutando PowerShell como Administrador (clic derecho → **Run as Administrator**). Si te pasa esto:
> - Probá primero con **`winget install GitHub.Copilot`** (Opción A) en lugar de `npm`.
> - Si igual falla, probá al revés: `npm install -g @github/copilot` en lugar de `winget` (a algunos les funcionó uno y no el otro, sin un patrón claro — puede depender de política corporativa/antivirus).
> - Si ninguno anda, pegale a Copilot (en VS Code o la app) los 3 comandos de verificación (`node --version`, `npm --version`, `npx --version`) junto con el error exacto que te tiró la terminal, y pedile que te arme un script para solucionarlo. Es la técnica más rápida para destrabarse con errores puntuales de entorno.
> - **Esto es justamente lo que hicimos en la Weekly**: le pasamos a Copilot los 3 comandos y los mensajes de error obtenidos, y nos indicó ejecutar:
>   ```powershell
>   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
>   ```
>   Esto relaja la política de ejecución de scripts de PowerShell para el usuario actual (necesaria para que `npm`/`npx` puedan correr sus scripts `.ps1`). Corré ese comando y volvé a intentar la instalación.

Luego iniciá sesión:

```powershell
copilot
```

Dentro de Copilot CLI, ejecutá `/login` y seguí las instrucciones en el navegador.

---

## Paso 3 — Generar tu API key de Redmine

1. Ingresá a tu instancia de Redmine (ej. `https://redmine.biapplications.com.ar`).
2. Iniciá sesión con tu usuario.
3. Andá a **Mi cuenta**.
4. En la sección **API access key**, hacé clic en **Mostrar** o **Generar una clave**.
5. Copiala y guardala en un gestor de contraseñas. **No la compartas por chat ni la subas a ningún repo.**

> Tip: si tu organización lo permite, usá un usuario técnico con permisos mínimos (solo lectura al principio) en lugar de tu usuario personal.

---

## Paso 4 — Dar de alta el servidor MCP de Redmine

### Opción A: Wizard interactivo (igual en cualquier SO)

Dentro de Copilot CLI:

```text
/mcp add
```

Completá:

| Campo | Valor |
| --- | --- |
| Nombre | `redmine` |
| Tipo | `Local (STDIO)` |
| Comando | `npx` |
| Argumentos | `-y @onozaty/redmine-mcp-server` |
| `REDMINE_URL` | URL de tu Redmine |
| `REDMINE_API_KEY` | tu API key |
| `REDMINE_MCP_READ_ONLY` | `true` (arrancamos en modo solo lectura) |

> 🔴 **Problema real en la Weekly — sintaxis de las variables de entorno**: el campo de "Environment Variables" del wizard **no acepta punto y coma (`;`) entre variables**. Es un objeto tipo JSON, con **comas** entre pares, así:
>
> ```json
> {"REDMINE_URL":"https://redmine.tuempresa.com","REDMINE_API_KEY":"tu-api-key","REDMINE_MCP_READ_ONLY":"true"}
> ```
>
> Si ponés `;` en vez de `,`, el wizard tira el error **"REDMINE_URL Environment Variable is not set"** y, al volver a editar (`/mcp edit redmine`), **borra silenciosamente todas las variables** sin avisar cuál estaba mal escrita — hay que volver a tipearlas todas. Puntos clave:
> - Todo entre **llaves `{ }`**, nombres y valores entre **comillas dobles `" "`**, `:` entre nombre y valor, **`,`** entre variables (no `;`).
> - `REDMINE_URL` va **sin la ruta** de "My account" ni nada después del dominio — cortá hasta el último `/` del dominio (ej. `https://redmine.tuempresa.com`, no `https://redmine.tuempresa.com/my/account`).
> - Tip práctico: escribí el JSON completo antes en el Bloc de notas (Notepad) y después pegalo de una — así evitás errores de tipeo en vivo.

Guardá y verificá con:

```text
/mcp
```

### Opción B: Script de PowerShell (automatizado, sin exponer la key en el historial)

Cerrá Copilot CLI y en PowerShell ejecutá:

```powershell
$RedmineApiKey = Read-Host "API key de Redmine" -AsSecureString
$RedmineApiKeyPlain = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
  [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($RedmineApiKey)
)

$configPath = Join-Path $env:USERPROFILE ".copilot\mcp-config.json"
New-Item -ItemType Directory -Force -Path (Split-Path $configPath) | Out-Null

$config = if (Test-Path $configPath) {
  Get-Content $configPath -Raw | ConvertFrom-Json
} else {
  [PSCustomObject]@{}
}

if (-not $config.mcpServers) {
  $config | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([PSCustomObject]@{})
}

$config.mcpServers | Add-Member -Force -NotePropertyName redmine -NotePropertyValue ([PSCustomObject]@{
  type    = "stdio"
  command = "npx"
  args    = @("-y", "@onozaty/redmine-mcp-server")
  env     = [PSCustomObject]@{
    REDMINE_URL           = "https://TU-REDMINE.example.com"
    REDMINE_API_KEY       = $RedmineApiKeyPlain
    REDMINE_MCP_READ_ONLY = "true"
  }
})

$config | ConvertTo-Json -Depth 10 | Set-Content -Path $configPath -Encoding UTF8

$RedmineApiKeyPlain = $null
$RedmineApiKey = $null

Write-Host "Configuración guardada en $configPath"
```

> Reemplazá `https://TU-REDMINE.example.com` por la URL real de tu Redmine antes de correr el script.

Reiniciá `copilot` y verificá con `/mcp`.

---

## Paso 5 — Validar la conexión (solo lectura)

Dentro de Copilot CLI, probá:

```text
Usando el MCP de Redmine, listá los proyectos a los que tengo acceso. No realices modificaciones.
```

```text
Usando el MCP de Redmine, listá mis issues asignados abiertos. No realices modificaciones.
```

Si devuelve datos reales de tu Redmine, ¡ya está funcionando! 🎉

---

## Paso 6 — Habilitar escritura (para cargar horas / crear-editar issues)

Una vez validado el modo lectura, cambiá `REDMINE_MCP_READ_ONLY` a `"false"`:

- Volviendo a correr `/mcp add` con los mismos datos, o
- Editando el script del Paso 4 (cambiar el valor de `REDMINE_MCP_READ_ONLY`) y volviendo a ejecutarlo.

Reiniciá Copilot CLI y validá:

```text
Usando el servidor MCP "redmine", listá las herramientas disponibles para crear y actualizar issues. No ejecutes ninguna modificación.
```

---

## Paso 7 — Demo: cargar horas y buscar issues en lenguaje natural

> 🔴 **Problema real en la Weekly**: pedirle que busque un issue **por nombre/título** (ej. "el issue de Sync Operation" o "el issue de la weekly") devolvió resultados ambiguos o directamente nada, porque la búsqueda por texto del servidor MCP es limitada. **Usá siempre el ID exacto del issue** (`#1234`) cuando le pidas cargar horas o modificar algo. Para buscar, primero pedí un listado ("listame mis issues abiertos") y de ahí sacá el número.

> 💡 **Es normal que te pida autorización varias veces**: cada operación (leer, escribir, listar herramientas, etc.) puede pedir un "Allow" por separado, incluso en modo solo lectura. No es un error — es Copilot CLI mostrando y confirmando cada paso antes de ejecutarlo. Podés decir "sí a todo" en modo interactivo o usar `--allow-all-tools` si confiás en el servidor (con cuidado, sobre todo si ya está en modo escritura).

> ⏱️ **Expectativas de performance**: algunas consultas responden rápido, pero otras (sobre todo listados grandes o la primera vez que arranca el servidor vía `npx`) pueden tardar bastante más — no es que se haya colgado, dale un momento antes de cancelar.

Ejemplos para mostrar en la Weekly:

```text
Usa el MCP de Redmine para buscar el issue que usamos para cargar horas de nuestras reuniones 1:1.
```

```text
Prepará la carga de 1 hora de hoy en el issue "DA Weekly" con el comment "Esta carga la hice con mi MCP". Pedime confirmación antes de crearla.
```

> Buena práctica: siempre pedirle que muestre los datos y pida confirmación antes de crear/modificar algo en Redmine.

---

## Troubleshooting rápido

- **Comportamientos raros o comandos que no corren como en la guía**: chequeá `$PSVersionTable.PSVersion` — si estás en PowerShell 5.1 en vez de 7+, actualizá con `winget upgrade Microsoft.PowerShell`.
- **`copilot` no se reconoce**: cerrá y volvé a abrir PowerShell, o revisá que la carpeta de instalación esté en el `PATH`.
- **"Security error" al instalar con `npm`/`winget`**: probá el otro método de instalación (winget ↔ npm); si persiste, corré PowerShell como Administrador; si aun así falla, pegale a un chat de Copilot los comandos + el error exacto y pedile un script de solución.
- **El MCP no aparece conectado en `/mcp`, o dice "REDMINE_URL Environment Variable is not set"**: revisá la sintaxis de las env vars del wizard — deben ir entre `{ }`, con `,` (no `;`) entre variables, y `REDMINE_URL` sin `/` al final ni rutas extra.
- **`/mcp edit` te borró todas las variables**: es el comportamiento conocido cuando el JSON anterior tenía un error de sintaxis — volvé a tipearlas todas (mejor: armalas antes en el Bloc de notas).
- **Búsqueda de un issue por nombre no encuentra nada o trae varios**: usá el ID exacto (`#1234`) en lugar del título.
- **No puede escribir en Redmine**: verificá `REDMINE_MCP_READ_ONLY="false"` en la config **y** que el usuario de Redmine tenga permisos de escritura en ese proyecto.
- **Alternativa sin usar la CLI**: en VS Code existe la opción **"MCP: Manage Trust MCP Server"** (paleta de comandos) para dar de alta el mismo servidor MCP sin pasar por `/mcp add` — útil si preferís quedarte en VS Code, aunque en la Weekly no llegamos a verificar el detalle fino de esa ruta.
- **Ver la config actual sin exponer la key**:

```powershell
$config = Get-Content (Join-Path $env:USERPROFILE ".copilot\mcp-config.json") -Raw | ConvertFrom-Json
$server = $config.mcpServers.redmine
[PSCustomObject]@{
  command = $server.command
  args    = $server.args
  env     = [PSCustomObject]@{
    REDMINE_URL           = $server.env.REDMINE_URL
    REDMINE_API_KEY       = if ($server.env.REDMINE_API_KEY) { "[CONFIGURADA]" } else { "[AUSENTE]" }
    REDMINE_MCP_READ_ONLY = $server.env.REDMINE_MCP_READ_ONLY
  }
} | ConvertTo-Json -Depth 5
```
