# BIA Time Agent en VS Code (Windows)

**En corto:** cómo usar BIA Time Agent desde VS Code en Windows, con el repo `bia-da-agentic` clonado y un MCP de Redmine que ya estaba configurado. La [wiki de Javier](copilot-javier-ramos/README.md) documenta la instalación con GitHub Copilot CLI; esta página es un apunte aparte y no la modifica. El clonado está en [bia_da_agentic.md](bia_da_agentic.md).

Revisión del 2026-10-26 sobre BIA Time Agent v0.20.0 (PR 733).

> **Sin validar:** la wiki marca VS Code y Windows como pendientes de prueba (D-20). Si algo de esta página no funciona, anotarlo para Javier.

## 1. El MCP de Redmine: reutilizarlo, no duplicarlo

El agente usa el mismo servidor que la página *MCP de Redmine* (`@onozaty/redmine-mcp-server`). Si ya está configurado, se reutiliza. Dos servidores de Redmine le muestran al agente las mismas tools repetidas.

| Requisito | Por qué |
|---|---|
| Nombre exacto `redmine` | El agente y sus skills lo buscan con ese nombre |
| `REDMINE_MCP_READ_ONLY` en `"false"` | Si no, el agente no puede cargar horas (`createTimeEntry`) |
| La API key en una variable de entorno o en `${input:...}` | Nunca en un chat ni en un archivo del repo |
| Cuenta de Redmine en zona horaria UTC | Lo verifica `npm run check:redmine` |

Ejemplo de entrada en el `mcp.json` de usuario de VS Code (la key la pide VS Code al arrancar):

```json
"redmine": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@onozaty/redmine-mcp-server"],
  "env": {
    "REDMINE_URL": "https://redmine.biapplications.com.ar",
    "REDMINE_API_KEY": "${input:redmine_api_key}",
    "REDMINE_MCP_READ_ONLY": "false"
  }
}
```

VS Code y Copilot CLI guardan configuraciones separadas: lo que está en una no aparece en la otra. Para usar también la CLI, verificar con `copilot mcp list`.

## 2. Instalar y configurar

En la terminal de VS Code (PowerShell), dentro de `C:\Users\<usuario>\dev\bia-da-agentic`:

```powershell
npm install
npm run install-user
notepad $env:USERPROFILE\.bia-time-agent\config.yaml   # completar los datos personales
npm run check:redmine
```

Sin la configuración personal completa, el agente no atiende ningún pedido. `install-user` no toca Redmine: al final imprime dos comandos `copilot mcp add`, para `bia-workdays` y `bia-m365`.

## 3. Cargar el agente y las skills en VS Code

1. Abrir la carpeta del repo con *File > Open Folder*. Copilot toma el agente de `.github/agents/` y las 13 skills de `.claude/skills/`, la carpeta que comparten Copilot y Claude.
2. Registrar los MCP propios en VS Code. Los `copilot mcp add` solo registran en la CLI. En VS Code: *MCP: Open User Configuration* y agregar `bia-workdays` y `bia-m365` con el mismo comando y argumentos que imprime `install-user`, junto a `redmine`.
3. En el chat de Copilot: modo Agent, agente **bia-time-agent**, modelo GPT-6 Luna.
4. Primera prueba, solo lectura: *"¿Qué días me faltan cargar este mes?"*.

Si las skills no aparecen: actualizar VS Code y la extensión de Copilot. En algunas versiones hay que activar el setting `chat.useAgentSkills`.

## 4. Seguridad

- Cuando Copilot pida aprobar `createTimeEntry`, aprobar cada vez. Nunca *Always allow*: es la segunda barrera antes de escribir en Redmine.
- El agente muestra el conjunto exacto de cargas y espera el sí. Revisarlo antes de confirmar.

## Validación

- [ ] `npm run check:redmine` pasa.
- [ ] En el chat aparecen el agente `bia-time-agent` y las tools de `redmine`, `bia-workdays` y `bia-m365`.
- [ ] La pregunta de solo lectura responde con días reales del mes.

## Próximos pasos

1. Hacer la primera carga de prueba con confirmación.
2. Pasarle a Javier lo que funcionó y lo que no, para la validación D-20.
