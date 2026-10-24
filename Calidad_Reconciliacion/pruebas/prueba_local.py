"""Prueba local del caso Calidad_Reconciliacion, sin Fabric.

Qué prueba:
  1. validar_sql y validar_regla: solo SELECT/WITH, sin DML/DDL, sin ';', claves que parecen PII.
  2. COMPARA con clave (meses que faltan de un lado, métricas fuera de tolerancia, tolerancias
     absoluta y porcentual combinadas) y sin clave (totales).
  3. CONDICION: dentro y fuera del rango, NULL, más de una fila.
  4. evaluar(): una regla rota no frena a las demás, hay_error solo con severidad ERROR y el
     JSON que lee dq.usp_LOG_RESULTADOS.
  5. La plantilla alta_reglas_calidad.sql: se leen sus reglas y todas validan.
  6. Opcional, si hay pyspark: las reglas de la plantilla corren con Spark SQL sobre un modelo
     de ejemplo (silver, gold, bronze) y detectan las fallas sembradas.

No prueba la base de control (dq.*) ni el pipeline.

Requisitos: pip install pandas   (punto 6: pyspark==3.5.3, Java 17+)
    python prueba_local.py
"""
import json
import os
import re

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
CASO = os.path.join(AQUI, "..")
NB = json.load(open(os.path.join(CASO, "notebooks", "NB_CAL_01_evaluar_reglas.ipynb"), encoding="utf-8"))
CODIGO = ["".join(c["source"]) for c in NB["cells"] if c["cell_type"] == "code"]
g = {}
exec(next(s for s in CODIGO if s.startswith("# --- funciones")), g)
f = type("F", (), g)


def ok(msg):
    print("  OK ", msg)


def regla(**kw):
    base = {"regla_code": "r", "tipo": "COMPARA", "severidad": "ERROR", "sql_a": "SELECT 1 AS x", "sql_b": "SELECT 1 AS x",
            "clave": None, "metricas": None, "tolerancia_abs": 0, "tolerancia_pct": 0, "valor_min": None, "valor_max": None}
    return {**base, **kw}


# ---------------------------------------------------------------------------
print("1. Validación")
assert f.validar_sql("SELECT COUNT(*) FROM gold.x") == []
assert f.validar_sql("  with a as (select 1) select * from a ;") == []
assert f.validar_sql("SELECT 'DROP TABLE x' AS texto") == []            # dentro de un texto no cuenta
assert f.validar_sql("-- DELETE viejo\nSELECT 1") == []                 # ni en un comentario
assert "SELECT o WITH" in f.validar_sql("DELETE FROM gold.x")[0]
assert any("DROP" in p for p in f.validar_sql("SELECT 1; DROP TABLE gold.x"))
assert any("';'" in p for p in f.validar_sql("SELECT 1; SELECT 2"))
assert any("INSERT" in p for p in f.validar_sql("WITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a"))
assert f.validar_sql("") == ["SQL vacío"]
p = f.validar_regla(regla(clave="mes,email_cliente", tipo="COMPARA", severidad="ALTA"))
assert any("severidad" in x for x in p) and any("email_cliente" in x for x in p)
assert any("valor_min" in x for x in f.validar_regla(regla(tipo="CONDICION", sql_b=None)))
ok("solo lectura, una sentencia, sin claves personales")

# ---------------------------------------------------------------------------
print("2. COMPARA")
a = pd.DataFrame({"mes": ["2026-08", "2026-09", "2026-10"], "filas": [100, 200, 300], "importe": [1000.0, 2000.0, 3000.0]})
r = f.comparar(regla(clave="mes"), a, a.copy())
assert r["estado"] == "OK" and r["valor_a"] == 600 and "3 claves" in r["detalle"]
b = pd.DataFrame({"mes": ["2026-09", "2026-10", "2026-11"], "filas": [200, 290, 5], "importe": [2000.0, 3000.0, 50.0]})
r = f.comparar(regla(clave="mes"), a, b)
assert r["estado"] == "FALLA"
for esperado in ("mes=2026-08: solo en A", "mes=2026-10: filas 300 vs 290", "mes=2026-11: solo en B"):
    assert esperado in r["detalle"], r["detalle"]
assert r["diferencia"] == -10 and abs(r["diferencia_pct"] - 3.3333) < 0.001
# Tolerancias: 290 vs 300 es 10 filas y 3,3 %. Falla solo si supera las DOS
b2 = a.assign(filas=[100, 200, 290])
assert f.comparar(regla(clave="mes", tolerancia_abs=20), a, b2)["estado"] == "OK"
assert f.comparar(regla(clave="mes", tolerancia_pct=5), a, b2)["estado"] == "OK"
assert f.comparar(regla(clave="mes", tolerancia_abs=5, tolerancia_pct=1), a, b2)["estado"] == "FALLA"
# Métricas elegidas: si solo se compara importe, la diferencia de filas no cuenta
assert f.comparar(regla(clave="mes", metricas="importe"), a, b2)["estado"] == "OK"
# Clave numérica de un lado y texto del otro: se comparan como texto
assert f.comparar(regla(clave="anio"), pd.DataFrame({"anio": [2026], "n": [1]}),
                  pd.DataFrame({"anio": ["2026"], "n": [1]}))["estado"] == "OK"
# Sin clave: una fila cada una
t = f.comparar(regla(), pd.DataFrame({"filas": [10]}), pd.DataFrame({"filas": [12]}))
assert t["estado"] == "FALLA" and t["detalle"].startswith("1 diferencias: total: filas 10 vs 12")
assert f.comparar(regla(), a, b)["estado"] == "ERROR_EJECUCION"
assert f.comparar(regla(clave="periodo"), a, b)["estado"] == "ERROR_EJECUCION"
# De 0 a algo: diferencia porcentual infinita, se informa como NULL
z = f.comparar(regla(), pd.DataFrame({"n": [0]}), pd.DataFrame({"n": [5]}))
assert z["estado"] == "FALLA" and z["diferencia_pct"] is None
ok("claves de un solo lado, tolerancias combinadas, métricas elegidas, totales y 0 → n")

# ---------------------------------------------------------------------------
print("3. CONDICION")
c = lambda v, **kw: f.condicion(regla(tipo="CONDICION", **kw), pd.DataFrame({"horas": [v]}))
assert c(10, valor_max=48)["estado"] == "OK"
x = c(60, valor_max=48)
assert x["estado"] == "FALLA" and x["detalle"] == "horas = 60, fuera de [-∞, 48]"
assert c(0, valor_min=0, valor_max=0)["estado"] == "OK"
assert c(3, valor_min=0, valor_max=0)["estado"] == "FALLA"
assert c(None, valor_max=48)["detalle"] == "La consulta devolvió NULL"
assert f.condicion(regla(tipo="CONDICION", valor_max=1), pd.DataFrame({"n": [1, 2]}))["estado"] == "ERROR_EJECUCION"
ok("rango, NULL y más de una fila")

# ---------------------------------------------------------------------------
print("4. evaluar()")
datos = {"SELECT 1 AS n": pd.DataFrame({"n": [1]}), "SELECT 5 AS n": pd.DataFrame({"n": [5]})}


def ejecutar(sql):
    if sql not in datos:
        raise RuntimeError("[TABLE_OR_VIEW_NOT_FOUND] The table or view `gold`.`no_existe` cannot be found.\nmás detalle")
    return datos[sql]


reglas = [
    regla(regla_code="ok", tipo="CONDICION", sql_a="SELECT 1 AS n", valor_max=1),
    regla(regla_code="warn_falla", tipo="CONDICION", sql_a="SELECT 5 AS n", valor_max=1, severidad="WARN"),
    regla(regla_code="rota", tipo="CONDICION", sql_a="SELECT * FROM gold.no_existe", valor_max=1, severidad="WARN"),
    regla(regla_code="peligrosa", tipo="CONDICION", sql_a="DELETE FROM gold.x", valor_max=1, severidad="WARN"),
]
s = f.evaluar(reglas, ejecutar)
est = {r["regla_code"]: r["estado"] for r in s["resultados"]}
assert est == {"ok": "OK", "warn_falla": "FALLA", "rota": "ERROR_EJECUCION", "peligrosa": "ERROR_EJECUCION"}, est
assert not s["hay_error"]                                   # todo lo que falla es WARN
rota = next(r for r in s["resultados"] if r["regla_code"] == "rota")
assert "TABLE_OR_VIEW_NOT_FOUND" in rota["detalle"] and "más detalle" not in rota["detalle"]
s2 = f.evaluar(reglas + [regla(regla_code="err", tipo="CONDICION", sql_a="SELECT 5 AS n", valor_max=1)], ejecutar)
assert s2["hay_error"] and s2["FALLA"] == 2
# El JSON que recibe dq.usp_LOG_RESULTADOS: las claves que lee OPENJSON
texto = json.dumps(s2, ensure_ascii=False, default=str)
for k in ("regla_code", "estado", "severidad", "valor_a", "valor_b", "diferencia", "diferencia_pct", "detalle"):
    assert f'"{k}"' in texto
sql_log = open(os.path.join(CASO, "sql", "01_ddl_calidad.sql"), encoding="utf-8").read()
assert "OPENJSON(@RESULTADOS_JSON, '$.resultados')" in sql_log
ok("una regla rota no frena, hay_error solo con ERROR, JSON con las claves del SP")

# ---------------------------------------------------------------------------
print("5. Plantilla alta_reglas_calidad.sql")


def leer_plantilla():
    """Lee las tuplas del MERGE ... USING (VALUES ...) AS s (columnas)."""
    txt = open(os.path.join(CASO, "skill", "proponer-reglas-calidad", "plantillas", "alta_reglas_calidad.sql"),
               encoding="utf-8").read()
    cuerpo = txt[txt.index("USING (VALUES") + len("USING (VALUES"):]
    cols_txt = re.search(r"\)\s*AS s \(([^)]*)\)", cuerpo)
    columnas = [c.strip().lower() for c in cols_txt.group(1).split(",")]
    cuerpo = cuerpo[:cols_txt.start()]
    tuplas, actual, i, nivel = [], None, 0, 0
    tok = re.compile(r"N?'((?:[^']|'')*)'|(NULL)|(-?\d+(?:\.\d+)?)|(\()|(\))|(--[^\n]*)|(\s+|,)", re.S)
    while i < len(cuerpo):
        m = tok.match(cuerpo, i)
        assert m, f"no entiendo la plantilla cerca de: {cuerpo[i:i + 40]!r}"
        i = m.end()
        texto, nulo, num, abre, cierra = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if abre:
            nivel += 1
            actual = [] if nivel == 1 else actual
        elif cierra:
            nivel -= 1
            if nivel == 0:
                tuplas.append(dict(zip(columnas, actual)))
        elif nivel == 1 and texto is not None:
            actual.append(texto.replace("''", "'"))
        elif nivel == 1 and nulo:
            actual.append(None)
        elif nivel == 1 and num:
            actual.append(float(num))
    return tuplas


plantilla = leer_plantilla()
assert len(plantilla) == 5 and all(len(t) == 15 for t in plantilla)
for t in plantilla:
    assert f.validar_regla(t) == [], (t["regla_code"], f.validar_regla(t))
ok(f"{len(plantilla)} reglas de ejemplo, todas válidas")

# ---------------------------------------------------------------------------
print("6. Spark (opcional)")
try:
    from pyspark.sql import SparkSession
except ImportError:
    print("  -- sin pyspark: se saltea")
else:
    import tempfile
    tmp = tempfile.mkdtemp()
    spark = (SparkSession.builder.master("local[1]").appName("cal")
             .config("spark.sql.warehouse.dir", tmp).config("spark.ui.enabled", "false")
             .config("spark.sql.shuffle.partitions", "1").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    for db in ("bronze", "silver", "gold"):
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {db}")
    import datetime as dt
    hoy = dt.date.today()
    ventas = [(1, hoy, 1, 10, 100.0), (2, hoy, 2, 10, 200.0), (3, dt.date(2026, 9, 15), 1, 11, 50.0)]
    spark.createDataFrame(ventas, "venta_id bigint, fecha date, cliente_id int, producto_id int, importe_neto double") \
        .write.mode("overwrite").saveAsTable("silver.ventas")
    # Gold sembrado con fallas: falta la venta 2 y la 3 apunta a un cliente que no existe
    gold = [(1, hoy, 1, 10, 100.0), (3, dt.date(2026, 9, 15), 99, 11, 50.0)]
    spark.createDataFrame(gold, "venta_id bigint, fecha date, cliente_id int, producto_id int, importe_neto double") \
        .write.mode("overwrite").saveAsTable("gold.fact_ventas")
    spark.createDataFrame([(1,), (2,)], "cliente_id int").write.mode("overwrite").saveAsTable("gold.dim_cliente")
    spark.createDataFrame([(10,), (11,)], "producto_id int").write.mode("overwrite").saveAsTable("gold.dim_producto")
    spark.createDataFrame([("1",), ("2",), ("3",), ("4",)], "VentaID string").write.mode("overwrite").saveAsTable("bronze.erp_ventas")

    s = f.evaluar(plantilla, lambda sql: spark.sql(sql).toPandas())
    est = {r["regla_code"]: r for r in s["resultados"]}
    assert est["cuadre_ventas_silver_gold"]["estado"] == "FALLA"
    assert f"mes={hoy:%Y-%m}: filas 2 vs 1" in est["cuadre_ventas_silver_gold"]["detalle"], est["cuadre_ventas_silver_gold"]
    assert est["ventas_sin_cliente"]["estado"] == "FALLA" and est["ventas_sin_cliente"]["valor_a"] == 1
    assert est["ventas_sin_producto"]["estado"] == "OK"
    assert est["frescura_ventas"]["estado"] == "OK"
    assert est["claves_ventas_bronze_silver"]["estado"] == "FALLA" and est["claves_ventas_bronze_silver"]["valor_a"] == 1
    assert s["hay_error"]
    spark.stop()
    ok("las 5 reglas de la plantilla corren en Spark SQL y detectan las fallas sembradas")

print("Todo OK")
