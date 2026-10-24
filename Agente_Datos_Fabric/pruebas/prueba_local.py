"""Prueba local del caso Agente_Datos_Fabric, sin Fabric.

Qué prueba:
  1. NB_AGT_01: las reglas de validación del banco de preguntas, con la plantilla
     y con filas armadas para que fallen.
  2. NB_AGT_02: el plan de sincronización de ejemplos y la lectura de bloques de
     instrucciones_agente.md.
  3. NB_AGT_03: el resumen de una evaluación, la decisión de aprobar y que el
     prompt del juez tenga los marcadores que pide el SDK.
  4. mcp/fabric_data_agent_mcp.py: levanta un servidor MCP falso con la misma
     ruta y la misma forma que el endpoint del data agent (una sola herramienta,
     token Bearer obligatorio) y le hace una pregunta a través del proxy.
  5. Opcional, si hay pyspark y delta-spark: la escritura de NB_AGT_01 en Delta
     (MERGE, filas que pasan a OBSOLETA).

No prueba el SDK de Fabric ni un data agent real.

Requisitos (probado con Python 3.13, mcp 2.3, azure-identity 1.26, pandas 3.0):
    pip install -r ../mcp/requirements.txt pandas uvicorn
    python prueba_local.py
Para el punto 5 además (probado con Java 21):
    pip install pyspark==3.5.3 delta-spark==3.2.1 "pandas<3" setuptools
"""
import asyncio
import datetime as dt
import json
import os
import socket
import sys
import threading
import time

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
CASO = os.path.join(AQUI, "..")
PLANTILLAS = os.path.join(CASO, "skill", "agente-datos-fabric", "plantillas")


def celdas(nb):
    data = json.load(open(os.path.join(CASO, "notebooks", f"{nb}.ipynb"), encoding="utf-8"))
    return ["".join(c["source"]) for c in data["cells"] if c["cell_type"] == "code"]


def funciones(nb):
    """Ejecuta solo la celda '# --- funciones' del notebook y devuelve su espacio de nombres."""
    g = {}
    exec(next(s for s in celdas(nb) if s.startswith("# --- funciones")), g)
    return g


def ok(msg):
    print("  OK ", msg)


# ---------------------------------------------------------------------------
print("1. NB_AGT_01 · validación del banco")
f1 = funciones("NB_AGT_01_cargar_banco")
plantilla = pd.read_csv(os.path.join(PLANTILLAS, "banco_preguntas.csv"), dtype=str, keep_default_na=False)
banco, probs = f1["validar_banco"](plantilla, hoy=dt.date(2026, 10, 24))
assert not [p for p in probs if p["nivel"] == "ERROR"], probs
assert list(banco.estado_efectivo) == ["VALIDADA", "VALIDADA", "PROPUESTA", "PROPUESTA"]
ok("la plantilla no tiene errores y las PROPUESTA no se validan solas")

base = plantilla.iloc[0].to_dict()
def fila(**cambios):
    d = dict(base); d.update(cambios); return d

casos = pd.DataFrame([
    fila(pregunta_id="E1", validado_por=""),                                           # sin validador
    fila(pregunta_id="E2", consulta_referencia="DELETE FROM agente.ventas"),           # escritura
    fila(pregunta_id="E3", lenguaje="DAX", consulta_referencia="EVALUATE ventas"),     # DAX como ejemplo
    fila(pregunta_id="E4", uso="EVALUACION", respuesta_esperada=""),                   # evaluación sin respuesta
    fila(pregunta_id="E5", uso="EVALUACION", respuesta_esperada="[dato a confirmar]"), # pendiente
    fila(pregunta_id="E6", pregunta="¿Cuánto vendimos en pesos por rubro en marzo de 2026", uso="EVALUACION",
         respuesta_esperada="1.000"),                                                  # fuga con VTA-001
    fila(pregunta_id="A1", pregunta="Ventas de cliente juan@ejemplo.com en 2026", vigente_hasta="2026-01-31"),
    fila(pregunta_id="E7", consulta_referencia="SELECT 1; DROP TABLE x"),              # escritura escondida
])
casos = pd.concat([plantilla.iloc[[0]], casos], ignore_index=True)
banco, probs = f1["validar_banco"](casos, hoy=dt.date(2026, 10, 24))
errores = {p["pregunta_id"] for p in probs if p["nivel"] == "ERROR"}
avisos = {p["pregunta_id"] for p in probs if p["nivel"] == "AVISO"}
for pid in ("E1", "E2", "E3", "E4", "E5", "E7"):
    assert pid in errores, (pid, probs)
assert any("VTA-001" in e and "E6" in e for e in errores), probs
assert "A1" in avisos and banco.set_index("pregunta_id").loc["A1", "estado_efectivo"] == "OBSOLETA"
ok("detecta validador faltante, escritura, DAX como ejemplo, pendientes, fuga ejemplo/evaluación")
ok("una fila vencida queda OBSOLETA y el email genera aviso")
_, probs = f1["validar_banco"](plantilla.drop(columns=["uso"]))
assert probs[0]["nivel"] == "ERROR" and "Faltan columnas" in probs[0]["mensaje"]
ok("una columna faltante corta la validación")

# ---------------------------------------------------------------------------
print("2. NB_AGT_02 · plan de ejemplos e instrucciones")
f2 = funciones("NB_AGT_02_sincronizar_ejemplos")
deseados = {"¿Cuánto vendimos en marzo?": "SELECT 1", "Top 10 clientes": "SELECT 2", "Nueva": "SELECT 3"}
actuales = [{"id": "a", "question": "cuánto vendimos en marzo", "query": "SELECT 1"},
            {"id": "b", "question": "Top 10 clientes", "query": "SELECT viejo"},
            {"id": "c", "question": "Pregunta cargada a mano", "query": "SELECT 9"}]
plan = {a["question"]: a["accion"] for a in f2["plan_ejemplos"](deseados, actuales)}
assert plan == {"¿Cuánto vendimos en marzo?": "SIN_CAMBIOS", "Top 10 clientes": "ACTUALIZAR",
                "Nueva": "AGREGAR", "Pregunta cargada a mano": "NO_GESTIONADO"}, plan
plan = {a["question"]: a["accion"] for a in f2["plan_ejemplos"](deseados, actuales, True)}
assert plan["Pregunta cargada a mano"] == "BORRAR"
ok("agrega, actualiza, deja igual y solo borra lo no gestionado si se lo pedís")
bloques = f2["leer_bloques"](open(os.path.join(PLANTILLAS, "instrucciones_agente.md"), encoding="utf-8").read())
assert set(bloques) == {"descripcion", "instrucciones_agente",
                        "fuente:LH_MEDALLION:descripcion", "fuente:LH_MEDALLION:instrucciones"}, list(bloques)
assert bloques["instrucciones_agente"].startswith("## Objetivo")
ok(f"lee los {len(bloques)} bloques de instrucciones_agente.md")
assert f2["nombre_fuente"]({"displayName": "LH"}) == "LH" and f2["nombre_fuente"]({"display_name": "X"}) == "X"
assert f2["filas_a_dicts"](pd.DataFrame([{"Id": 1, "Question": "q", "Query": "s"}])) == [{"id": 1, "question": "q", "query": "s"}]
ok("adapta nombres de claves y columnas del SDK")

# ---------------------------------------------------------------------------
print("3. NB_AGT_03 · resumen y decisión")
f3 = funciones("NB_AGT_03_evaluar_y_publicar")
for marca in ("{query}", "{expected_answer}", "{actual_answer}"):
    assert marca in f3["CRITIC_PROMPT"]
ok("el prompt del juez tiene los tres marcadores del SDK")
detalle = pd.DataFrame({"evaluation_judgement": [True] * 17 + [False] * 2 + [None]})
r = f3["resumen_corrida"](detalle)
assert r == {"total": 20, "correctas": 17, "incorrectas": 2, "dudosas": 1, "acierto": 0.85}, r
assert f3["decidir"](r, None, 0.85, 2.0) == (True, [])
aprueba, motivos = f3["decidir"](r, 0.90, 0.85, 2.0)
assert not aprueba and "Cae 5.0 pp" in motivos[0]
assert f3["decidir"](r, 0.86, 0.85, 2.0)[0]
assert not f3["decidir"]({"total": 0, "acierto": 0.0}, None, 0.85, 2.0)[0]
ok("aprueba con 85 %, rechaza una caída de 5 pp, tolera 1 pp y rechaza un banco vacío")

# ---------------------------------------------------------------------------
print("4. Proxy MCP contra un data agent falso")
import uvicorn
from starlette.responses import PlainTextResponse
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer

WS, AG, TOKEN = "ws-123", "ag-456", "token-de-prueba"
falso = MCPServer("data-agent-falso")


@falso.tool(name="AG_VENTAS", description="Agente de ventas de prueba")
def responder(userQuestion: str) -> str:
    return f"Respuesta a: {userQuestion}"


app = falso.streamable_http_app(streamable_http_path=f"/v1/mcp/workspaces/{WS}/dataagents/{AG}/agent")


async def exige_token(scope, receive, send):
    if scope["type"] == "http":
        auth = dict(scope["headers"]).get(b"authorization", b"").decode()
        if auth != f"Bearer {TOKEN}":
            await PlainTextResponse("sin token", status_code=401)(scope, receive, send)
            return
    await app(scope, receive, send)

with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); puerto = s.getsockname()[1]
servidor = uvicorn.Server(uvicorn.Config(exige_token, host="127.0.0.1", port=puerto, log_level="error", lifespan="on"))
threading.Thread(target=servidor.run, daemon=True).start()
while not servidor.started:
    time.sleep(0.05)

os.environ.update({"FABRIC_WORKSPACE_ID": WS, "FABRIC_DATA_AGENT_ID": AG,
                   "FABRIC_MCP_BASE_URL": f"http://127.0.0.1:{puerto}",
                   "FABRIC_AGENT_LOG": os.path.join(AQUI, "preguntas_prueba.jsonl"),
                   "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"})
if os.path.exists(os.environ["FABRIC_AGENT_LOG"]):
    os.remove(os.environ["FABRIC_AGENT_LOG"])
sys.path.insert(0, os.path.join(CASO, "mcp"))
import fabric_data_agent_mcp as proxy


class CredencialFalsa:
    def __init__(self, token): self.token_valor = token
    def get_token(self, *scopes):
        assert scopes == (proxy.SCOPE,)
        return type("T", (), {"token": self.token_valor})()


proxy._credencial = CredencialFalsa(TOKEN)
resp = asyncio.run(proxy.preguntar_agente_fabric("¿Cuánto vendimos en marzo de 2026?"))
assert resp == "Respuesta a: ¿Cuánto vendimos en marzo de 2026?", resp
ok("descubre la herramienta y su argumento, y devuelve el texto")
proxy._credencial = CredencialFalsa("otro")
resp = asyncio.run(proxy.preguntar_agente_fabric("pregunta sin permiso"))
assert resp.startswith("ERROR al consultar el data agent"), resp
ok("con un token rechazado devuelve un error legible en vez de romper")
log = [json.loads(l) for l in open(os.environ["FABRIC_AGENT_LOG"], encoding="utf-8")]
assert [l["ok"] for l in log] == [True, False] and "respuesta" not in log[0]
os.remove(os.environ["FABRIC_AGENT_LOG"])
ok("anota las preguntas en el .jsonl, sin las respuestas por defecto")
servidor.should_exit = True

# ---------------------------------------------------------------------------
print("5. NB_AGT_01 · escritura en Delta (opcional)")
try:
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession
except ImportError:
    print("  --  sin pyspark/delta-spark: se saltea")
else:
    import shutil, tempfile
    work = tempfile.mkdtemp(prefix="agt_")
    spark = configure_spark_with_delta_pip(
        SparkSession.builder.master("local[1]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir", work)
        .config("spark.sql.shuffle.partitions", "1")).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    csv1 = os.path.join(work, "banco.csv")

    def correr(df_csv, dry_run=False):
        df_csv.to_csv(csv1, index=False)
        g = {"spark": spark, "display": lambda d: (d.show(truncate=False) if hasattr(d, "show") else print(d))}
        for i, src in enumerate(celdas("NB_AGT_01_cargar_banco")):
            exec(src, g)
            if i == 0:
                g.update(RUTA_CSV=csv1, DRY_RUN=dry_run)

    correr(plantilla, dry_run=True)
    assert not spark.catalog.tableExists("agente_ctl.banco_preguntas")
    ok("DRY_RUN no crea la tabla")
    correr(plantilla)
    t = spark.table("agente_ctl.banco_preguntas").toPandas().set_index("pregunta_id")
    assert len(t) == 4 and t.loc["VTA-001", "estado_efectivo"] == "VALIDADA"
    v2 = plantilla[plantilla.pregunta_id != "VTA-002"].copy()
    v2.loc[v2.pregunta_id == "VTA-101", ["respuesta_esperada", "estado", "validado_por", "fecha_validacion"]] = \
        ["$ 1.234.567", "VALIDADA", "Responsable Comercial", "2026-10-24"]
    correr(v2)
    t = spark.table("agente_ctl.banco_preguntas").toPandas().set_index("pregunta_id")
    assert t.loc["VTA-002", "estado_efectivo"] == "OBSOLETA"
    assert t.loc["VTA-101", "estado_efectivo"] == "VALIDADA" and t.loc["VTA-101", "respuesta_esperada"] == "$ 1.234.567"
    ok("MERGE: actualiza la validada y deja OBSOLETA la que salió del CSV")
    spark.stop()
    shutil.rmtree(work, ignore_errors=True)

print("\nTodo OK")
