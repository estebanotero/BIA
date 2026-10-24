"""Prueba local del caso Performance_Modelo_Semantico, sin Fabric.

Qué prueba:
  1. NB_PERF_01: normalización de columnas y severidades del BPA, y el armado de
     diagnostico.json con la forma que devuelven vertipaq_analyzer y run_model_bpa
     en semantic-link-labs 0.17.1 (más las medidas de modelo.json de NB_DOC_01).
  2. NB_PERF_02: validación de consultas.csv (con la plantilla y con filas armadas
     para que fallen), las métricas de una traza falsa (con RequestID y sin él), la
     huella del resultado y el resumen por consulta.
  3. NB_PERF_03: la comparación de dos corridas, el veredicto en tres escenarios
     (mejora, regresión, resultado distinto) y el informe en Markdown.
  4. Plantillas: propuestas.csv tiene las columnas que pide la skill.

No prueba semantic-link, la traza real ni un modelo de Fabric.

Requisitos (probado con Python 3.13, con pandas 2.3.3 y 3.0.5):
    pip install pandas
    python prueba_local.py
"""
import json
import os

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
CASO = os.path.join(AQUI, "..")
PLANTILLAS = os.path.join(CASO, "skill", "optimizar-modelo-semantico", "plantillas")


def funciones(nb):
    """Ejecuta solo la celda '# --- funciones' del notebook y devuelve su espacio de nombres."""
    data = json.load(open(os.path.join(CASO, "notebooks", f"{nb}.ipynb"), encoding="utf-8"))
    celda = next("".join(c["source"]) for c in data["cells"]
                 if c["cell_type"] == "code" and "".join(c["source"]).startswith("# --- funciones"))
    g = {}
    exec(celda, g)
    return g


def ok(msg):
    print("  OK ", msg)


# ---------------------------------------------------------------------------
print("1. NB_PERF_01 · diagnóstico")
f1 = funciones("NB_PERF_01_diagnosticar")

assert f1["carpeta_modelo"]("/lakehouse/default/Files/doc_modelos/", "Ventas y Stock") == \
    "/lakehouse/default/Files/doc_modelos/Ventas_y_Stock"
ok("carpeta_modelo usa la misma convención que NB_DOC_01")

n = f1["normalizar_columnas"](pd.DataFrame(columns=["Table Name", "% DB", "Total Size"]))
assert list(n.columns) == ["table_name", "pct_db", "total_size"], n.columns
ok("normalizar_columnas deja nombres válidos para Delta")

MB = 1024 ** 2
vpa = {
    "Model Summary": pd.DataFrame([{"Dataset Name": "Ventas", "Total Size": 100 * MB, "Table Count": 3,
                                    "Column Count": 20, "Compatibility Level": 1604, "Default Mode": "Import"}]),
    "Tables": pd.DataFrame([
        {"Table Name": "Ventas", "Type": "Table", "Row Count": 10_000_000, "Total Size": 90 * MB, "% DB": 90.0},
        {"Table Name": "Producto", "Type": "Table", "Row Count": 5_000, "Total Size": 8 * MB, "% DB": 8.0},
        {"Table Name": "LocalDateTable_x", "Type": "Calculated Table", "Row Count": 3_650, "Total Size": 2 * MB, "% DB": 2.0},
    ]),
    "Columns": pd.DataFrame([
        {"Table Name": "Ventas", "Column Name": "IdTransaccion", "Type": "Data", "Cardinality": 10_000_000,
         "Total Size": 48 * MB, "Dictionary Size": 30 * MB, "Data Type": "String", "Encoding": "Hash"},
        {"Table Name": "Ventas", "Column Name": "Importe", "Type": "Data", "Cardinality": 80_000,
         "Total Size": 20 * MB, "Dictionary Size": 1 * MB, "Data Type": "Double", "Encoding": "Value"},
        {"Table Name": "Producto", "Column Name": "Producto", "Type": "Data", "Cardinality": 5_000,
         "Total Size": 1 * MB, "Dictionary Size": 0.5 * MB, "Data Type": "String", "Encoding": "Hash"},
    ]),
    "Relationships": pd.DataFrame([{"From Object": "'Ventas'[IdProducto]", "To Object": "'Producto'[IdProducto]",
                                    "Multiplicity": "m:1", "Used Size": 1000, "Max From Cardinality": 5000,
                                    "Max To Cardinality": 5000, "Missing Rows": 12}]),
    "Partitions": pd.DataFrame([{"Table Name": "Ventas", "Partition Name": "Ventas", "Mode": "Import"}]),
}
bpa = f1["normalizar_bpa"](pd.DataFrame([
    {"Category": "Performance", "Rule Name": "Set IsAvailableInMdx to false on non-attribute columns",
     "Severity": "⚠️", "Object Type": "Column", "Object Name": "'Ventas'[IdTransaccion]"},
    {"Category": "Performance", "Rule Name": "Avoid bi-directional relationships",
     "Severity": "❌", "Object Type": "Relationship", "Object Name": "x"},
    {"Category": "Formatting", "Rule Name": "Provide format string for measures",
     "Severity": "ℹ️", "Object Type": "Measure", "Object Name": "[Ventas]"},
]))
assert set(bpa["Severity"]) == {"Warning", "Error", "Info"}, bpa["Severity"].tolist()
ok("normalizar_bpa convierte los íconos de severidad")

modelo_doc = {"generado_utc": "2026-10-24T12:00:00+00:00",
              "medidas": [{"tabla": "Medidas", "nombre": "Ventas", "expresion": "SUM(Ventas[Importe])",
                           "descripcion_actual": "Importe vendido"}]}
diag = f1["armar_diagnostico"](vpa, bpa, None, modelo_doc, top_n=2)
assert [c["columna"] for c in diag["top_columnas"]] == ["IdTransaccion", "Importe"]
assert diag["top_columnas"][0]["pct_modelo"] == 48.0
assert diag["relaciones"][0]["filas_sin_match"] == 12
assert len(diag["bpa_performance"]) == 2 and diag["modos_particion"] == ["Import"]
assert diag["medidas"][0]["expresion"] == "SUM(Ventas[Importe])"
json.dumps(diag, default=str)
ok("armar_diagnostico: top de columnas, % del modelo, relaciones, BPA de performance y medidas de NB_DOC_01")

sin_missing = dict(vpa, Relationships=vpa["Relationships"].drop(columns=["Missing Rows"]))
assert f1["armar_diagnostico"](sin_missing, bpa, None, None)["relaciones"][0]["filas_sin_match"] is None
ok("armar_diagnostico tolera vertipaq sin 'Missing Rows' (read_stats_from_data=False o Direct Lake)")

# ---------------------------------------------------------------------------
print("2. NB_PERF_02 · consultas y traza")
f2 = funciones("NB_PERF_02_medir_consultas")

plantilla = pd.read_csv(os.path.join(PLANTILLAS, "consultas.csv"), dtype=str, keep_default_na=False)
activas, probs = f2["validar_consultas"](plantilla)
assert not probs and activas["id"].tolist() == ["Q01", "Q02", "Q03"], (probs, activas["id"].tolist())
ok("la plantilla consultas.csv es válida y Q04 (activa = no) queda afuera")

malas = pd.DataFrame([
    {"id": "Q1", "nombre": "a", "origen": "", "dax": "SELECT 1", "activa": "si"},
    {"id": "Q1", "nombre": "b", "origen": "", "dax": "EVALUATE ROW(\"x\", 1)", "activa": "si"},
    {"id": "Q 3", "nombre": "c", "origen": "", "dax": "DEFINE VAR x = 1 EVALUATE ROW(\"x\", x)", "activa": "sí"},
])
_, probs = f2["validar_consultas"](malas)
assert any("repetidos" in p for p in probs) and any("DEFINE o EVALUATE" in p for p in probs) \
    and any("Q 3" in p for p in probs), probs
assert f2["validar_consultas"](malas.drop(columns=["activa"]))[1][0].startswith("Faltan columnas")
ok("validar_consultas detecta ids repetidos, ids inválidos, DAX que no es consulta y columnas faltantes")

m1, m2 = f2["marca"]("Q01", 1, "frio"), f2["marca"]("Q02", 1, "frio")
assert f2["marcar"]("EVALUATE ROW(\"x\", 1)", m1).startswith("/* perf:Q01:frio:1 */\n")
t = pd.Timestamp("2026-10-24 12:00:00")


def ms(n):
    return pd.Timedelta(milliseconds=n)


logs = pd.DataFrame([
    # Q01: 2 consultas SE externas + 1 interna (no cuenta) + 1 hit de caché
    {"Event Class": "QueryBegin", "Event Subclass": "DAXQuery", "Text Data": f"/* {m1} */ EVALUATE", "Request ID": "r1", "Start Time": t},
    {"Event Class": "VertiPaqSEQueryEnd", "Event Subclass": "VertiPaqScan", "Text Data": "SELECT", "Request ID": "r1", "Duration": 300, "Start Time": t + ms(1)},
    {"Event Class": "VertiPaqSEQueryEnd", "Event Subclass": "VertiPaqScanInternal", "Text Data": "SELECT", "Request ID": "r1", "Duration": 250, "Start Time": t + ms(1)},
    {"Event Class": "VertiPaqSEQueryEnd", "Event Subclass": "VertiPaqScan", "Text Data": "SELECT", "Request ID": "r1", "Duration": 100, "Start Time": t + ms(2)},
    {"Event Class": "VertiPaqSEQueryCacheMatch", "Event Subclass": "VertiPaqCacheExactMatch", "Text Data": "", "Request ID": "r1", "Start Time": t + ms(3)},
    {"Event Class": "QueryEnd", "Event Subclass": "DAXQuery", "Text Data": f"/* {m1} */ EVALUATE", "Request ID": "r1",
     "Duration": 1000, "Cpu Time": 900, "Start Time": t, "End Time": t + ms(1000)},
    # Q02: DirectQuery (fallback)
    {"Event Class": "DirectQueryEnd", "Event Subclass": None, "Text Data": "SELECT ...", "Request ID": "r2", "Duration": 700, "Start Time": t + ms(2000)},
    {"Event Class": "QueryEnd", "Event Subclass": "DAXQuery", "Text Data": f"/* {m2} */ EVALUATE", "Request ID": "r2",
     "Duration": 800, "Cpu Time": 50, "Start Time": t + ms(1990), "End Time": t + ms(2800)},
])
met = f2["metricas_de_traza"](logs, [m1, m2, "perf:Q09:frio:1"]).set_index("marca")
q1 = met.loc[m1]
assert (q1["total_ms"], q1["se_ms"], q1["fe_ms"], q1["se_consultas"], q1["se_cache_hits"]) == (1000, 400, 600, 2, 1), q1
assert met.loc[m2, "dq_consultas"] == 1 and met.loc[m2, "dq_ms"] == 700
assert not met.loc["perf:Q09:frio:1", "encontrada"]
ok("metricas_de_traza: total, SE sin internas, FE, consultas SE, hits de caché, DirectQuery y marcas sin eventos")

sin_rq = f2["metricas_de_traza"](logs.drop(columns=["Request ID"]), [m1]).iloc[0]
assert (sin_rq["total_ms"], sin_rq["se_ms"]) == (1000, 400), sin_rq
ok("metricas_de_traza sin RequestID usa la ventana de tiempo de la consulta")

r1 = pd.DataFrame({"'Fecha'[Mes]": ["ene", "feb"], "[Ventas]": [10.0000001, 20.0]})
r2 = pd.DataFrame({"[Ventas]": [20.0, 10.0], "'Fecha'[Mes]": ["feb", "ene"]})
r3 = pd.DataFrame({"[Ventas]": [20.0, 11.0], "'Fecha'[Mes]": ["feb", "ene"]})
h = f2["huella_resultado"]
assert h(r1) == h(r2) != h(r3) and h(pd.DataFrame()) == "vacio"
ok("huella_resultado no depende del orden de filas ni columnas, tolera 1e-7 y detecta un valor distinto")

med = pd.DataFrame([
    {"id": "Q01", "modo": "frio", "rep": i, "encontrada": True, "total_ms": v, "se_ms": v // 2, "fe_ms": v // 2,
     "se_consultas": 3, "dq_consultas": 0, "huella": "aaa"} for i, v in enumerate([900, 1000, 1100, 5000, 950], 1)
] + [
    {"id": "Q02", "modo": "frio", "rep": 1, "encontrada": True, "total_ms": 200, "se_ms": 100, "fe_ms": 100,
     "se_consultas": 1, "dq_consultas": 0, "huella": "bbb"},
    {"id": "Q02", "modo": "frio", "rep": 2, "encontrada": True, "total_ms": 210, "se_ms": 100, "fe_ms": 110,
     "se_consultas": 1, "dq_consultas": 0, "huella": "ccc"},
    {"id": "Q02", "modo": "frio", "rep": 3, "encontrada": False, "total_ms": None, "se_ms": None, "fe_ms": None,
     "se_consultas": None, "dq_consultas": None, "huella": "bbb"},
])
res = f2["resumir"](med).set_index("id")
assert res.loc["Q01", "total_ms_mediana"] == 1000 and res.loc["Q01", "n"] == 5 and res.loc["Q01", "huella_estable"]
assert res.loc["Q02", "n"] == 2 and not res.loc["Q02", "huella_estable"]
ok("resumir: mediana robusta a un valor atípico, descarta ejecuciones sin traza y marca huellas inestables")

# ---------------------------------------------------------------------------
print("3. NB_PERF_03 · comparación")
f3 = funciones("NB_PERF_03_comparar")


def resumen(filas):
    return pd.DataFrame([{"id": i, "modo": "frio", "total_ms_mediana": t, "se_ms_mediana": t * 0.4,
                          "fe_ms_mediana": t * 0.6, "se_consultas_mediana": 3, "huella": hu} for i, t, hu in filas])


antes = resumen([("Q01", 1000, "a"), ("Q02", 500, "b"), ("Q03", 300, "c")])
tablas_a = vpa["Tables"]
tablas_d = vpa["Tables"].assign(**{"Total Size": [42 * MB, 8 * MB, 0]})
bpa_a = pd.DataFrame({"Category": ["Performance", "Performance", "Formatting"]})
bpa_d = pd.DataFrame({"Category": ["Formatting"]})

desp = resumen([("Q01", 400, "a"), ("Q02", 520, "b"), ("Q03", 300, "c")])
cons = f3["comparar_consultas"](antes, desp, "frio", 10, 10).set_index("id")
assert cons.loc["Q01", "estado"] == "mejora" and cons.loc["Q01", "variacion_pct"] == -60.0
assert cons.loc["Q02", "estado"] == "igual"
assert f3["veredicto"](cons.reset_index(), 100 * MB, 52 * MB, 10)[0] == "APROBADO"
ok("escenario mejora: Q01 -60 %, Q02 +4 % (dentro del umbral) → APROBADO")

desp = resumen([("Q01", 400, "a"), ("Q02", 800, "b"), ("Q03", 300, "c")])
cons = f3["comparar_consultas"](antes, desp, "frio", 10, 10)
v, motivos = f3["veredicto"](cons, 100 * MB, 100 * MB, 10)
assert v == "REVISAR" and "Q02" in motivos[0]
ok("escenario regresión: Q02 +60 % → REVISAR")

desp = resumen([("Q01", 400, "x"), ("Q02", 500, "b"), ("Q04", 10, "d")])
cons = f3["comparar_consultas"](antes, desp, "frio", 10, 10).set_index("id")
assert cons.loc["Q01", "estado"] == "resultado_distinto"
assert cons.loc["Q03", "estado"] == "solo_en_antes" and cons.loc["Q04", "estado"] == "solo_en_despues"
cons_ok = f3["comparar_consultas"](antes, desp, "frio", 10, 10, cambio_esperado=["Q01"]).set_index("id")
assert cons_ok.loc["Q01", "estado"] == "mejora"
ok("escenario resultado distinto: REVISAR salvo que la consulta esté en CAMBIO_DE_RESULTADO_ESPERADO")

mem = f3["comparar_memoria"](tablas_a, tablas_d)
assert mem.iloc[0]["tabla"] == "Ventas" and mem.iloc[0]["variacion_pct"] == -53.3
bpa_c = f3["comparar_bpa"](bpa_a, bpa_d).set_index("categoria")
assert bpa_c.loc["Performance", "diferencia"] == -2 and bpa_c.loc["Formatting", "diferencia"] == 0
desp = resumen([("Q01", 400, "a"), ("Q02", 500, "b"), ("Q03", 300, "c")])
cons = f3["comparar_consultas"](antes, desp, "frio", 10, 10)
v, motivos = f3["veredicto"](cons, 100 * MB, 52 * MB, 10)
md = f3["informe_md"]("Ventas", {"corrida": "antes", "commit": "abc123"}, {"corrida": "despues_pr12", "commit": "def456"},
                      "frio", cons, mem, f3["comparar_bpa"](bpa_a, bpa_d), 100 * MB, 52 * MB, v, motivos,
                      {"Q01": "Ventas por mes"})
assert "**Veredicto: APROBADO**" in md and "| Q01 Ventas por mes | 1,000 | 400 | -60.0 % |" in md
assert "| Memoria del modelo (MB) | 100.0 | 52.0 (-48.0 %) |" in md and "| Performance | 2 | 0 | -2 |" in md
ok("informe_md arma el Markdown para el PR")

# ---------------------------------------------------------------------------
print("4. Plantillas")
prop = pd.read_csv(os.path.join(PLANTILLAS, "propuestas.csv"), dtype=str, keep_default_na=False)
esperadas = ["id", "prioridad", "categoria", "objeto", "evidencia", "propuesta", "archivos_tmdl", "impacto_esperado",
             "riesgo", "cambia_resultado", "requiere_refresh", "consultas_afectadas", "aprobada", "estado", "commit"]
assert list(prop.columns) == esperadas, list(prop.columns)
assert (prop["aprobada"] == "").all()
ok("propuestas.csv tiene las columnas de la skill y 'aprobada' vacía")

print("\nTodo OK")
