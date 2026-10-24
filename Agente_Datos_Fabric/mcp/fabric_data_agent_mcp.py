"""
MCP local que conecta a Claude con un Fabric data agent publicado.

Por qué un proxy local y no conectar Claude directo al endpoint:
el endpoint MCP del data agent pide un token de Entra ID en cada request y
no soporta dynamic client registration, así que no se puede agregar tal cual
como conector OAuth. Este proceso corre en tu PC por stdio, pide el token con
azure-identity (tu `az login` o un service principal) y reenvía la pregunta.

Herramienta que expone a Claude Code / Claude Desktop:
  - preguntar_agente_fabric(pregunta): le pasa la pregunta al data agent y
    devuelve su respuesta en texto. El agente consulta con TU identidad, así
    que respeta tus permisos, RLS y CLS.

No se guarda ningún secreto acá. Variables de entorno:
  FABRIC_WORKSPACE_ID      (obligatoria) ID del workspace del agente
  FABRIC_DATA_AGENT_ID     (obligatoria) ID del data agent publicado
  FABRIC_AGENT_DESCRIPTION (opcional) descripción de la herramienta para Claude;
                           conviene copiar la descripción de publicación del agente
  FABRIC_AGENT_LOG         (opcional) ruta de un .jsonl donde se anotan las
                           preguntas, para alimentar el banco de preguntas
  FABRIC_AGENT_LOG_RESPUESTAS=1  (opcional) anota también las respuestas.
                           Ojo: pueden tener datos sensibles.
  AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET
                           solo si usás service principal (DefaultAzureCredential).
                           Guardalas en un gestor de secretos, nunca en el repo.

Probado con Python 3.13, mcp 2.3 (también importa con mcp 1.x) y
azure-identity 1.26, contra un servidor MCP de prueba (pruebas/prueba_local.py).
No probado contra un data agent real.
"""

import datetime as dt
import json
import os

from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential
from mcp import ClientSession

try:  # mcp 2.x
    from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

    def _transporte(url: str, headers: dict):
        return streamable_http_client(url, http_client=create_mcp_http_client(headers=headers))
except ImportError:  # mcp 1.x
    from mcp.client.streamable_http import streamablehttp_client

    def _transporte(url: str, headers: dict):
        return streamablehttp_client(url, headers=headers)

try:  # mcp 2.x renombró FastMCP a MCPServer
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as MCPServer

SCOPE = "https://api.fabric.microsoft.com/.default"
BASE_URL = os.getenv("FABRIC_MCP_BASE_URL", "https://api.fabric.microsoft.com")  # se cambia solo en pruebas

DESCRIPCION = os.getenv(
    "FABRIC_AGENT_DESCRIPTION",
    "Responde preguntas de negocio en lenguaje natural con los datos de Microsoft Fabric "
    "(ventas, clientes, productos). Pasale una sola pregunta concreta, con período. "
    "Devuelve la respuesta del Fabric data agent en texto.",
)

mcp = MCPServer("fabric-data-agent")
_credencial = None


def credencial():
    """Primero tu sesión de Azure CLI; si no hay, variables de entorno o identidad administrada."""
    global _credencial
    if _credencial is None:
        _credencial = ChainedTokenCredential(AzureCliCredential(), DefaultAzureCredential())
    return _credencial


def url_agente() -> str:
    ws = os.environ["FABRIC_WORKSPACE_ID"]
    ag = os.environ["FABRIC_DATA_AGENT_ID"]
    return f"{BASE_URL}/v1/mcp/workspaces/{ws}/dataagents/{ag}/agent"


def _anotar(pregunta: str, respuesta: str | None, error: str | None) -> None:
    ruta = os.getenv("FABRIC_AGENT_LOG")
    if not ruta:
        return
    fila = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "pregunta": pregunta, "ok": error is None, "error": error}
    if os.getenv("FABRIC_AGENT_LOG_RESPUESTAS") == "1":
        fila["respuesta"] = respuesta
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(fila, ensure_ascii=False) + "\n")


async def consultar(pregunta: str) -> str:
    """Flujo MCP que pide el endpoint: initialize -> tools/list -> tools/call."""
    token = credencial().get_token(SCOPE).token
    headers = {"Authorization": f"Bearer {token}"}
    async with _transporte(url_agente(), headers) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            if not tools:
                raise RuntimeError("El endpoint no expone herramientas: ¿el agente está publicado?")
            tool = tools[0]  # el data agent expone una sola herramienta
            esquema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}  # mcp 2.x / 1.x
            arg = next(iter(esquema.get("properties", {})), "question")
            result = await session.call_tool(tool.name, {arg: pregunta})
            texto = "\n".join(b.text for b in (result.content or []) if getattr(b, "type", "") == "text")
            if getattr(result, "is_error", None) or getattr(result, "isError", False):
                raise RuntimeError(texto or "El data agent devolvió un error sin detalle.")
            return texto


@mcp.tool(description=DESCRIPCION)
async def preguntar_agente_fabric(pregunta: str) -> str:
    """Le hace una pregunta al Fabric data agent y devuelve su respuesta."""
    try:
        respuesta = await consultar(pregunta)
    except Exception as ex:  # devolvemos el error como texto para que Claude lo explique
        while len(getattr(ex, "exceptions", ())) == 1:  # ExceptionGroup sin depender de Python 3.11
            ex = ex.exceptions[0]  # anyio envuelve el error real en grupos de tareas
        _anotar(pregunta, None, str(ex))
        return f"ERROR al consultar el data agent: {type(ex).__name__}: {ex}"
    _anotar(pregunta, respuesta, None)
    return respuesta


if __name__ == "__main__":
    mcp.run()  # transporte stdio
