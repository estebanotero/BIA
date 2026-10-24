"""Prueba local del caso Monitoreo_Plataforma, sin Fabric.

Qué prueba (con datos armados a mano, una situación por regla):
  1. Pipeline medallion: paso fallido (y que no alerte si después corrió bien),
     corrida colgada, SLA incumplido y SLA cumplido tarde, rechazos altos,
     volumen anómalo y entidad sin datos.
  2. Inventario: items borrados en la ventana e inventario sin correr.
  3. Agente: evaluación que no aprueba (production = ALTA) y agente sin evaluar.
  4. Performance: regresión en la última comparación de un modelo.
  5. evaluar(): orígenes evaluados según las fuentes que hay, orden por severidad,
     claves únicas, y una plataforma sana sin alertas.
  6. El parte que lee la skill y que el notebook tenga la celda de parámetros marcada.

No prueba la base de control (vistas, mon.usp_SYNC_ALERTAS), el conector JDBC ni
notebookutils.

Requisitos: pip install pandas
    python prueba_local.py
"""
import datetime as dt
import json
import os

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
NB = os.path.join(AQUI, "..", "notebooks", "NB_MON_01_evaluar_alertas.ipynb")
DATA = json.load(open(NB, encoding="utf-8"))
CODIGO = ["".join(c["source"]) for c in DATA["cells"] if c["cell_type"] == "code"]

g = {}
exec(next(s for s in CODIGO if s.startswith("# --- funciones")), g)
evaluar, parte, U = g["evaluar"], g["parte"], g["UMBRALES_POR_DEFECTO"]

AHORA = dt.datetime(2026, 10, 26, 12, 0)    # lunes, 12:00 UTC
H = lambda horas: AHORA - dt.timedelta(hours=horas)


def ok(msg):
    print("  OK ", msg)


def codigos(alertas):
    return sorted(a["CODIGO"] for a in alertas)


# ---------------------------------------------------------------------------
print("1. Pipeline medallion")
corridas = pd.DataFrame([
    # grupo default: corrió bien hoy a las 09:30 (SLA 10:00)
    {"RUN_ID": "r1", "LOAD_GROUP": "default", "STATUS": "SUCCEEDED", "STARTED_AT": H(3), "ENDED_AT": H(2.5)},
    # grupo ventas: falló hoy, sin corrida buena -> SLA incumplido
    {"RUN_ID": "r2", "LOAD_GROUP": "ventas", "STATUS": "FAILED", "STARTED_AT": H(4), "ENDED_AT": H(3.5)},
    # grupo stock: terminó bien a las 11:00, límite 10:00 -> tarde
    {"RUN_ID": "r3", "LOAD_GROUP": "stock", "STATUS": "SUCCEEDED", "STARTED_AT": H(2), "ENDED_AT": H(1)},
    # grupo nocturno: RUNNING hace 5 horas, máximo 120 min -> colgada
    {"RUN_ID": "r4", "LOAD_GROUP": "nocturno", "STATUS": "RUNNING", "STARTED_AT": H(5), "ENDED_AT": None},
])
sla = pd.DataFrame([
    {"LOAD_GROUP": "default", "HORA_LIMITE_UTC": "10:00", "DIAS_SEMANA": "12345", "MAX_DURACION_MIN": None, "DUENO": None, "IS_ACTIVE": True},
    {"LOAD_GROUP": "ventas", "HORA_LIMITE_UTC": "10:00", "DIAS_SEMANA": "12345", "MAX_DURACION_MIN": None, "DUENO": "Equipo ventas", "IS_ACTIVE": True},
    {"LOAD_GROUP": "stock", "HORA_LIMITE_UTC": "10:00", "DIAS_SEMANA": "12345", "MAX_DURACION_MIN": None, "DUENO": None, "IS_ACTIVE": True},
    {"LOAD_GROUP": "nocturno", "HORA_LIMITE_UTC": "23:00", "DIAS_SEMANA": "1234567", "MAX_DURACION_MIN": 120, "DUENO": None, "IS_ACTIVE": True},
    # sábado y domingo solamente: hoy (lunes) no aplica
    {"LOAD_GROUP": "finde", "HORA_LIMITE_UTC": "08:00", "DIAS_SEMANA": "67", "MAX_DURACION_MIN": None, "DUENO": None, "IS_ACTIVE": True},
])


def paso(run, capa, obj, estado, horas, leidas=100, escritas=100, rech=0, err=None, grupo="default"):
    return {"RUN_ID": run, "LOAD_GROUP": grupo, "LAYER": capa, "OBJECT_CODE": obj, "STATUS": estado,
            "ROWS_READ": leidas, "ROWS_WRITTEN": escritas, "ROWS_REJECTED": rech,
            "ERROR_MESSAGE": err, "LOGGED_AT": H(horas)}


filas = [
    # erp_clientes falló en silver y no volvió a correr -> alerta
    paso("r2", "silver", "erp_clientes", "FAILED", 3.5, err="AnalysisException: cannot resolve 'zona'\nstack...", grupo="ventas"),
    # erp_pedidos falló y después corrió bien -> sin alerta
    paso("r0", "silver", "erp_pedidos", "FAILED", 6, err="timeout"),
    paso("r1", "silver", "erp_pedidos", "SUCCEEDED", 2.5),
    # erp_facturas: 20 % rechazado
    paso("r1", "silver", "erp_facturas", "SUCCEEDED", 2.5, leidas=1000, escritas=800, rech=200),
    # una falla vieja, fuera de la ventana -> sin alerta
    paso("rx", "bronze", "erp_viejo", "FAILED", 72, err="viejo"),
]
# erp_stock: 6 cargas de ~1000 filas y la última de 50 -> volumen anómalo
for i, n in enumerate([1000, 980, 1020, 1010, 990, 50]):
    filas.append(paso(f"s{i}", "silver", "erp_stock", "SUCCEEDED", 24 * (6 - i) + 1, leidas=n, escritas=n))
pasos = pd.DataFrame(filas)

frescura = pd.DataFrame([
    {"ENTITY_CODE": "erp_pedidos", "ULTIMA_CARGA_CON_DATOS": H(2.5)},
    {"ENTITY_CODE": "erp_proveedores", "ULTIMA_CARGA_CON_DATOS": H(24 * 5)},
    {"ENTITY_CODE": "erp_nueva", "ULTIMA_CARGA_CON_DATOS": None},
])

mdp = {"corridas": corridas, "pasos": pasos, "sla": sla, "frescura": frescura}
alertas, origenes = evaluar(mdp, AHORA)
assert origenes == ["MDP"], origenes
por = {(a["CODIGO"], a["OBJETO"]): a for a in alertas}

assert ("MDP_PASO_FALLIDO", "silver.erp_clientes") in por
assert "cannot resolve 'zona'" in por[("MDP_PASO_FALLIDO", "silver.erp_clientes")]["MENSAJE"]
assert "stack" not in por[("MDP_PASO_FALLIDO", "silver.erp_clientes")]["MENSAJE"]
assert ("MDP_PASO_FALLIDO", "silver.erp_pedidos") not in por
assert ("MDP_PASO_FALLIDO", "bronze.erp_viejo") not in por
ok("paso fallido: alerta el que sigue fallando, no el que se recuperó ni el de fuera de la ventana")

assert por[("MDP_CORRIDA_COLGADA", "r4")]["SEVERIDAD"] == "ALTA"
assert "máximo 120" in por[("MDP_CORRIDA_COLGADA", "r4")]["MENSAJE"]
ok("corrida colgada con el máximo del SLA del grupo")

assert por[("MDP_SLA_INCUMPLIDO", "ventas")]["SEVERIDAD"] == "ALTA"
assert "Equipo ventas" in por[("MDP_SLA_INCUMPLIDO", "ventas")]["MENSAJE"]
assert por[("MDP_SLA_INCUMPLIDO", "ventas")]["CLAVE"] == "MDP_SLA_INCUMPLIDO|ventas|2026-10-26"
assert por[("MDP_SLA_TARDE", "stock")]["SEVERIDAD"] == "MEDIA"
assert not any(o in ("default", "nocturno", "finde") for c, o in por if c.startswith("MDP_SLA"))
ok("SLA: incumplido (ALTA), tarde (MEDIA), cumplido, hora no alcanzada y día que no aplica")

assert ("MDP_RECHAZOS_ALTOS", "erp_facturas") in por and "20.0 %" in por[("MDP_RECHAZOS_ALTOS", "erp_facturas")]["MENSAJE"]
assert ("MDP_RECHAZOS_ALTOS", "erp_pedidos") not in por
ok("rechazos sobre el umbral")

assert por[("MDP_VOLUMEN_ANOMALO", "erp_stock")]["SEVERIDAD"] == "BAJA"
assert not any(c == "MDP_VOLUMEN_ANOMALO" and o != "erp_stock" for c, o in por)
ok("volumen anómalo solo con historia suficiente")

assert ("MDP_ENTIDAD_SIN_DATOS", "erp_proveedores") in por and ("MDP_ENTIDAD_SIN_DATOS", "erp_nueva") in por
assert ("MDP_ENTIDAD_SIN_DATOS", "erp_pedidos") not in por
ok("entidad sin datos (vieja y nunca cargada)")

# Una plataforma sana no tiene alertas
sana = {"corridas": corridas[corridas["RUN_ID"] == "r1"], "pasos": pasos[pasos["OBJECT_CODE"] == "erp_pedidos"],
        "sla": sla[sla["LOAD_GROUP"] == "default"], "frescura": frescura[frescura["ENTITY_CODE"] == "erp_pedidos"]}
assert evaluar(sana, AHORA)[0] == []
ok("plataforma sana: sin alertas")

# ---------------------------------------------------------------------------
print("2. Inventario")
inv = pd.DataFrame([
    {"WORKSPACE_ID": "ws1", "OBJECT_NAME": "NB_MDP_10_bronze", "ARTIFACT_TYPE": "Notebook", "ACTIVE_FLAG": True, "DELETED_AT": None, "LAST_SEEN_AT": H(80)},
    {"WORKSPACE_ID": "ws1", "OBJECT_NAME": "PL_VIEJO", "ARTIFACT_TYPE": "DataPipeline", "ACTIVE_FLAG": False, "DELETED_AT": H(5), "LAST_SEEN_AT": H(80)},
])
a, o = evaluar({"inventario": inv}, AHORA)
assert o == ["INV"] and codigos(a) == ["INV_ITEMS_BORRADOS", "INV_SIN_CORRER"], codigos(a)
assert "PL_VIEJO (DataPipeline)" in next(x for x in a if x["CODIGO"] == "INV_ITEMS_BORRADOS")["MENSAJE"]
inv2 = inv.assign(LAST_SEEN_AT=H(3), DELETED_AT=None)
assert evaluar({"inventario": inv2}, AHORA)[0] == []
ok("items borrados e inventario sin correr; sin alertas si está al día")

# ---------------------------------------------------------------------------
print("3. Agente")
ev = pd.DataFrame([
    {"agente": "AG_VENTAS", "etapa": "production", "evaluado_en": H(48), "acierto": 0.90, "aprueba": True, "motivos": ""},
    {"agente": "AG_VENTAS", "etapa": "production", "evaluado_en": H(2), "acierto": 0.80, "aprueba": False, "motivos": "Acierto 80.0% menor al umbral 85%"},
    {"agente": "AG_STOCK", "etapa": "sandbox", "evaluado_en": H(24 * 10), "acierto": 0.95, "aprueba": True, "motivos": ""},
])
a, o = evaluar({"eval_agente": ev}, AHORA)
por = {(x["CODIGO"], x["OBJETO"]): x for x in a}
assert por[("AGT_NO_APRUEBA", "AG_VENTAS")]["SEVERIDAD"] == "ALTA"
assert por[("AGT_SIN_EVALUAR", "AG_STOCK")]["SEVERIDAD"] == "BAJA"
assert ("AGT_NO_APRUEBA", "AG_STOCK") not in por
ok("agente en producción que no aprueba (ALTA) y agente sin evaluar (BAJA)")

# ---------------------------------------------------------------------------
print("4. Performance (todo como texto, igual que perf.comparacion)")
comp = pd.DataFrame([
    {"modelo": "Ventas", "id": "q1", "estado": "regresion", "corrida_antes": "antes", "corrida_despues": "pr10", "veredicto": "NO", "fecha_utc": "2026-10-20T10:00:00+00:00"},
    {"modelo": "Ventas", "id": "q1", "estado": "mejora", "corrida_antes": "antes", "corrida_despues": "pr12", "veredicto": "SI", "fecha_utc": "2026-10-25T10:00:00+00:00"},
    {"modelo": "Stock", "id": "q7", "estado": "resultado_distinto", "corrida_antes": "antes", "corrida_despues": "pr3", "veredicto": "NO", "fecha_utc": "2026-10-25T10:00:00+00:00"},
    {"modelo": "Stock", "id": "q8", "estado": "igual", "corrida_antes": "antes", "corrida_despues": "pr3", "veredicto": "NO", "fecha_utc": "2026-10-25T10:00:00+00:00"},
]).astype(str)
a, o = evaluar({"perf_comparacion": comp}, AHORA)
assert [x["OBJETO"] for x in a] == ["Stock"] and "q7 (resultado_distinto)" in a[0]["MENSAJE"]
ok("solo cuenta la última comparación de cada modelo")

# ---------------------------------------------------------------------------
print("5. evaluar() con todas las fuentes")
todas = {**mdp, "inventario": inv, "eval_agente": ev, "perf_comparacion": comp}
alertas, origenes = evaluar(todas, AHORA)
assert origenes == ["MDP", "INV", "AGT", "PERF"]
sev = [x["SEVERIDAD"] for x in alertas]
assert sev == sorted(sev, key=["ALTA", "MEDIA", "BAJA"].index)
assert len({x["CLAVE"] for x in alertas}) == len(alertas)
assert all(len(x["CLAVE"]) <= 300 and len(x["MENSAJE"]) <= 2000 for x in alertas)
assert evaluar({"pasos": pasos}, AHORA)[1] == []   # sin corridas no se evalúa MDP (y no se cierran sus alertas)
ok(f"{len(alertas)} alertas ordenadas por severidad, claves únicas, orígenes según las fuentes")

# ---------------------------------------------------------------------------
print("6. Parte y notebook")
p = parte(alertas, origenes, AHORA)
json.dumps(p, ensure_ascii=False, default=str)
assert p["alertas_por_severidad"]["ALTA"] == sum(x["SEVERIDAD"] == "ALTA" for x in alertas)
param = next(c for c in DATA["cells"] if c["cell_type"] == "code")
assert param["metadata"].get("tags") == ["parameters"]
assert all(k in "".join(param["source"]) for k in ("SQL_SERVER", "DRY_RUN", "UMBRALES"))
assert set(U) >= {"ventana_horas", "max_pct_rechazo", "dias_sin_datos"}
ok("el parte se serializa y la celda de parámetros está marcada")

print("Todo OK")
