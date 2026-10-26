# Repo bia-da-agentic: clonarlo y entenderlo

**En corto:** `bia-da-agentic` es el repo de Azure DevOps donde vive BIA Time Agent (y donde irían los próximos agentes de Data Analytics, como Ayudin). Es privado: se clona con la cuenta de BIA. Esta página dice cómo clonarlo en Windows y qué hay en cada carpeta. Los conceptos están en la [guía de la wiki de Copilot](guia_wiki_copilot.md).

Revisión del 2026-10-26 sobre `main` en el commit `dbdbcd1` (merge del PR 733, BIA Time Agent v0.20.0).

## 1. Clonarlo en Windows

Requisitos: Git para Windows (trae Git Credential Manager) y una cuenta de BIA con acceso al proyecto *BIA - Data Analytics*.

```powershell
# PowerShell 7+. Git para Windows, si no está:
winget install --id Git.Git -e

# Carpeta corta, sin espacios y fuera de OneDrive
mkdir $HOME\dev
cd $HOME\dev
git config --global core.longpaths true
git clone "https://cloudbia@dev.azure.com/cloudbia/BIA%20-%20Data%20Analytics/_git/bia-da-agentic"
cd bia-da-agentic
```

La primera vez se abre el navegador para iniciar sesión con la cuenta de Microsoft de BIA. Git Credential Manager guarda la sesión.

**Dónde clonarlo:** fuera de Escritorio y Documentos, que en las PCs corporativas suelen sincronizarse con OneDrive y chocan con `.git` y `node_modules`. Ruta corta por el límite de 260 caracteres de Windows (de ahí `core.longpaths`). Ejemplo en uso: `C:\Users\<usuario>\dev\bia-da-agentic`.

**Si el login falla:** crear un Personal Access Token en Azure DevOps (*User settings > Personal access tokens*) con permiso **Code (Read)** y vencimiento corto, y usarlo como contraseña cuando Git la pida. Nunca pegarlo en un chat ni guardarlo en un archivo del repo.

**Sin consola:** en la página del repo, *Clone > Clone in VS Code*.

### Validación

```powershell
git log -1 --oneline
# dbdbcd1 (HEAD -> main, origin/main, origin/HEAD) Merge PR 733: BIA Time Agent v0.20.0, ...
```

## 2. Qué hay en cada carpeta

| Carpeta o archivo | Qué es | En la analogía de la wiki |
|---|---|---|
| `agent.yaml` | Definición única del agente: núcleo de reglas, herramientas, modelo y reglas de BIA | El reglamento |
| `.claude/skills/` | Las 13 skills (y la versión del agente para Claude, generada). Copia en [`BIA_Time_Agent/`](../BIA_Time_Agent/README.md) | Los procedimientos |
| `.github/agents/` | El agente para GitHub Copilot, generado desde `agent.yaml` | — |
| `mcp/bia-workdays/` | MCP propio: fechas, feriados, redondeos, sumas y clasificaciones | La calculadora |
| `mcp/bia-m365/` | MCP propio: metadatos de Microsoft 365 vía Microsoft Graph, solo lectura | Una ventanilla |
| `mcp/bia-calendar/` | Lógica del calendario que usa `bia-m365` | — |
| `scripts/` | `build.mjs` (genera, valida e instala) y `baseline-carga.mjs` (línea base) | — |
| `templates/` | Plantilla de la configuración personal (`config.yaml`) | — |
| `docs/` | Seguridad, criterios de aceptación, guiones de prueba, línea base y mejoras pendientes | — |
| `README.md`, `package.json` | Punto de entrada y comandos npm | — |

`agent.yaml` es la única fuente: `npm run build` genera el agente para Copilot y para Claude, y falla si el agente supera los 30.000 caracteres de Copilot.

| Comando | Qué hace |
|---|---|
| `npm run build` | Regenera los archivos del agente desde `agent.yaml` |
| `npm run check` | Valida las skills y que los generados estén al día |
| `npm test` | Pruebas automáticas de los MCP propios |
| `npm run install-user` | Instala agente, skills y MCP propios en la máquina y crea la configuración personal |

Para instalar y usar BIA Time Agent, seguir [Instalación y uso](copilot-javier-ramos/Agentes-de-IA/BIA-Time-Agent/Instalación-y-uso.md). La wiki marca Windows como pendiente de validar (D-20).

## Próximos pasos

1. Leer el `README.md` del repo y `agent.yaml` para ver el núcleo de reglas.
2. Usar esta estructura (definición única, skills y MCP propios con pruebas) como base del MVP de Ayudin.
