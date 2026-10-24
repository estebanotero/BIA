"""Prueba local de SCD tipo 2 y bajas del origen en NB_MDP_20_silver y NB_MDP_30_gold, con Spark + Delta.

Escribe bronze a mano (como lo dejaría NB_MDP_10) y corre silver y gold con notebookutils simulado:
  clientes    SCD2 con SCD2_COLUMNS, columna tipo 1 (email, PII: no queda en versiones cerradas),
              DELETE_MODE = FLAG, reproceso fuera de orden,
              reactivación y el patrón de gold (dimensión con vigencia + hecho que la cruza por fecha)
  productos   MERGE con DELETE_MODE = ABSENT: una fila rechazada por DROP no es baja, freno DELETE_MAX_PCT,
              la clave que vuelve revive; gold OVERWRITE y MERGE no muestran las bajas
  sucursales  SCD2 con DELETE_MODE = ABSENT
  rubros      tabla que venía con MERGE y pasa a SCD2

Cada chequeo imprime OK o corta con AssertionError. Requisitos: los de prueba_local.py.
"""
import json, os, shutil, types, datetime as dt
NB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notebooks")
work = os.path.abspath("work_prueba_scd2"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work); os.chdir(work)

from pyspark.sql import SparkSession, functions as F
from delta import configure_spark_with_delta_pip
spark = configure_spark_with_delta_pip(SparkSession.builder.master("local[2]")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .config("spark.sql.warehouse.dir", work + "/wh")
    .config("spark.sql.session.timeZone", "UTC")
    .config("spark.ui.showConsoleProgress", "false")
    .config("spark.sql.shuffle.partitions", "2")).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
for s in ("bronze", "silver", "gold"): spark.sql(f"CREATE SCHEMA IF NOT EXISTS {s}")


class Exit(Exception):
    def __init__(s, v): s.v = v


nu = types.SimpleNamespace(notebook=types.SimpleNamespace(exit=lambda v: (_ for _ in ()).throw(Exit(v))))


def run_nb(name, args):
    g = {"spark": spark, "notebookutils": nu, "display": lambda df: None, "print": lambda *a, **k: None}
    for c in [c for c in json.load(open(f"{NB}/{name}.ipynb"))["cells"] if c["cell_type"] == "code"]:
        try: exec("".join(c["source"]), g)
        except Exit as e: return json.loads(e.v)
        if "parameters" in c["metadata"].get("tags", []): g.update(args)


def ok(cond, msg):
    assert cond, msg
    print("OK ", msg)


T = dt.datetime
def bronze(tabla, run, ingest, rows, schema):
    (spark.createDataFrame(rows, schema).withColumn("_run_id", F.lit(run))
         .withColumn("_ingested_at", F.lit(ingest).cast("timestamp"))
         .write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(tabla))


def silver(ent, run, bronze_run_id=""):
    r = run_nb("NB_MDP_20_silver", {"run_id": run, "entity_json": json.dumps(ent), "bronze_run_id": bronze_run_id})
    assert r["status"] in ("SUCCEEDED", "FAILED"), r
    return r


def gold(code, tabla, modo, sql, key=None):
    r = run_nb("NB_MDP_30_gold", {"run_id": "g", "gold_json": json.dumps(
        {"gold_code": code, "target_table": tabla, "load_mode": modo, "merge_key": key, "sql_text": sql})})
    assert r["status"] == "SUCCEEDED", r
    return r


def filas(sql):
    return [tuple(r) for r in spark.sql(sql).collect()]


def col(src, tgt, typ, expr=None, pii=0):
    return dict(source_column=src, target_column=tgt, target_type=typ, transform_expr=expr, is_pii=pii)


# ---------------------------------------------------------------- clientes: SCD2 + FLAG
SCH_C = "ClienteID int, RazonSocial string, Provincia string, Email string, Activo boolean, FechaModificacion timestamp"
cli = {"entity_code": "erp_clientes", "bronze_table": "bronze.erp_clientes", "silver_table": "silver.clientes",
       "silver_mode": "SCD2", "primary_key": "cliente_id", "order_column": "fecha_modificacion",
       "scd2_columns": "razon_social,provincia", "delete_mode": "FLAG", "delete_flag_expr": "NOT activo",
       "delete_max_pct": None,
       "columns": [col("ClienteID", "cliente_id", "int"), col("RazonSocial", "razon_social", "string", "trim(RazonSocial)"),
                   col("Provincia", "provincia", "string"), col("Email", "email", "string", "lower(Email)", 1),
                   col("Activo", "activo", "boolean"), col("FechaModificacion", "fecha_modificacion", "timestamp")],
       "dq_rules": [{"rule_name": "id", "rule_expr": "cliente_id IS NOT NULL", "action": "FAIL"}]}
C = "silver.clientes"
def versiones(k):
    return filas(f"SELECT provincia, email, _valid_from, _valid_to, _is_current, _is_deleted FROM {C} "
                 f"WHERE cliente_id = {k} ORDER BY _valid_from, _valid_to")

bronze("bronze.erp_clientes", "c1", "2026-10-01 03:00:00", [
    (1, "ACME", "Cordoba", "A@X.COM", True, T(2026, 9, 1)),
    (2, "Beta", "Salta", "b@x.com", True, T(2026, 9, 2)),
    (3, "Gamma", "Jujuy", "g@x.com", True, T(2026, 9, 3)),
    (3, "Gamma", "Jujuy", "g@x.com", True, T(2026, 9, 3))], SCH_C)       # bronze puede repetir filas
r = silver(cli, "c1")
ok(r["status"] == "SUCCEEDED" and r["historia"]["versiones_nuevas"] == 3, "c1: carga inicial, 3 versiones")
ok(versiones(1) == [("Cordoba", "a@x.com", T(1900, 1, 1), T(9999, 12, 31, 23, 59, 59), True, False)],
   "c1: la primera versión vale desde 1900 hasta 9999 y es vigente")

bronze("bronze.erp_clientes", "c2", "2026-10-02 03:00:00", [
    (1, "ACME", "Mendoza", "a@x.com", True, T(2026, 10, 1, 10)),        # cambia provincia: versión nueva
    (2, "Beta", "Salta", "beta@x.com", True, T(2026, 10, 1, 11)),       # cambia solo email (tipo 1)
    (4, "Delta", "Chaco", "d@x.com", True, T(2026, 10, 1, 12))], SCH_C)  # clave nueva
r = silver(cli, "c2")
h = r["historia"]
ok((h["versiones_nuevas"], h["versiones_cerradas"], h["bajas"]) == (2, 1, 0), "c2: 2 versiones nuevas, 1 cerrada, 0 bajas")
v1 = versiones(1)
ok(len(v1) == 2 and v1[0][3] == T(2026, 10, 1, 10) and v1[1][2] == T(2026, 10, 1, 10) and v1[1][4] and not v1[0][4],
   "c2: cambio de provincia cierra la versión vieja donde empieza la nueva (fecha_modificacion)")
ok(v1[0][1] is None and v1[1][1] == "a@x.com", "c2: la versión cerrada no guarda el email (PII no seguida)")
ok(versiones(2) == [("Salta", "beta@x.com", T(1900, 1, 1), T(9999, 12, 31, 23, 59, 59), True, False)],
   "c2: cambio de una columna no seguida se actualiza en el lugar, sin versión nueva")
ok(versiones(4)[0][2] == T(1900, 1, 1), "c2: clave nueva vale desde 1900")

total = spark.table(C).count()
r = silver(cli, "c2")
ok(spark.table(C).count() == total and r["rows_written"] == 0, "c2 de nuevo: idempotente, no escribe nada")

r = silver(cli, "c3", bronze_run_id="c1")
ok(r["historia"]["fuera_de_orden"] == 2 and spark.table(C).count() == total,
   "reproceso de c1: las claves con versión más nueva no se tocan (fuera_de_orden = 2)")

bronze("bronze.erp_clientes", "c4", "2026-10-04 03:00:00", [
    (3, "Gamma", "Jujuy", "g@x.com", False, T(2026, 10, 3, 9)),          # se da de baja
    (5, "Epsilon", "Salta", "e@x.com", False, T(2026, 10, 3, 9))], SCH_C)  # llega ya dada de baja
r = silver(cli, "c4")
ok(r["historia"]["bajas"] == 1, "c4: una baja por FLAG")
v3 = versiones(3)
ok(len(v3) == 1 and v3[0][3] == T(2026, 10, 3, 9) and not v3[0][4] and v3[0][5] and v3[0][1] is None,
   "c4: la baja cierra la versión vigente y la marca _is_deleted (no queda versión vigente)")
ok(versiones(5) == [("Salta", None, T(1900, 1, 1), T(2026, 10, 3, 9), False, True)],
   "c4: clave que llega ya dada de baja queda como versión cerrada")

bronze("bronze.erp_clientes", "c5", "2026-10-05 03:00:00", [
    (3, "Gamma", "Jujuy", "g@x.com", True, T(2026, 10, 4, 9))], SCH_C)    # vuelve
silver(cli, "c5")
v3 = versiones(3)
ok(len(v3) == 2 and v3[1][2] == T(2026, 10, 4, 9) and v3[1][4] and not v3[1][5],
   "c5: la clave reactivada abre una versión vigente desde su fecha_modificacion")
ok(filas(f"SELECT count(*) FROM (SELECT cliente_id FROM {C} WHERE _is_current GROUP BY cliente_id HAVING count(*) > 1)")
   == [(0,)], "nunca hay dos versiones vigentes de la misma clave")
ok(filas(f"""SELECT count(*) FROM {C} a JOIN {C} b ON a.cliente_id = b.cliente_id AND a._valid_from < b._valid_from
             AND a._valid_to > b._valid_from""") == [(0,)], "los intervalos de vigencia no se pisan")

# patrón de gold: dimensión con vigencia y hecho que la cruza por fecha
gold("dim_cliente_historia", "gold.dim_cliente_historia", "OVERWRITE",
     """SELECT xxhash64(cliente_id, _valid_from) AS cliente_sk, cliente_id, razon_social, provincia,
               _valid_from AS vigente_desde, _valid_to AS vigente_hasta, _is_current AS es_actual
        FROM silver.clientes""")
spark.createDataFrame([(10, 1, dt.date(2026, 9, 15)), (11, 1, dt.date(2026, 10, 2))],
                      "venta_id int, cliente_id int, fecha date").write.format("delta").saveAsTable("silver.ventas")
ok(filas("""SELECT v.venta_id, d.provincia FROM silver.ventas v
            JOIN gold.dim_cliente_historia d ON d.cliente_id = v.cliente_id
             AND CAST(v.fecha AS TIMESTAMP) >= d.vigente_desde AND CAST(v.fecha AS TIMESTAMP) < d.vigente_hasta
            ORDER BY v.venta_id""") == [(10, "Cordoba"), (11, "Mendoza")],
   "gold: cada venta toma la provincia vigente en su fecha")
ok("email" not in spark.table("gold.dim_cliente_historia").columns, "gold: sin columnas PII")

# ---------------------------------------------------------------- productos: MERGE + ABSENT
SCH_P = "ProductoID int, Descripcion string, Precio decimal(18,2)"
prd = {"entity_code": "erp_productos", "bronze_table": "bronze.erp_productos", "silver_table": "silver.productos",
       "silver_mode": "MERGE", "primary_key": "producto_id", "order_column": None, "load_type": "FULL",
       "scd2_columns": None, "delete_mode": "ABSENT", "delete_flag_expr": None, "delete_max_pct": 50,
       "columns": [col("ProductoID", "producto_id", "int"), col("Descripcion", "descripcion", "string"),
                   col("Precio", "precio", "decimal(18,2)")],
       "dq_rules": [{"rule_name": "precio_no_negativo", "rule_expr": "precio >= 0", "action": "DROP"}]}
P = "silver.productos"
D = __import__("decimal").Decimal
def bajas_prd():
    return filas(f"SELECT producto_id FROM {P} WHERE _is_deleted ORDER BY 1")
GOLD_PRD = "SELECT producto_id, descripcion, precio, _is_deleted FROM silver.productos"

bronze("bronze.erp_productos", "p1", "2026-10-01 03:00:00",
       [(i, f"P{i}", D("10.00")) for i in (1, 2, 3, 4)], SCH_P)
silver(prd, "p1")
gold("dim_producto", "gold.dim_producto", "OVERWRITE", GOLD_PRD)
gold("fact_producto", "gold.fact_producto", "MERGE", GOLD_PRD, key="producto_id")
ok(spark.table(P).count() == 4 and bajas_prd() == [], "p1: 4 productos vivos")

bronze("bronze.erp_productos", "p2", "2026-10-02 03:00:00",
       [(1, "P1", D("10.00")), (2, "P2", D("-1.00")), (3, "P3", D("11.00"))], SCH_P)
r = silver(prd, "p2")
ok(r["historia"]["bajas_por_ausencia"] == 1 and bajas_prd() == [(4,)],
   "p2: el 4 no vino en la extracción completa y queda dado de baja")
ok(r["rows_rejected"] == 1 and filas(f"SELECT _is_deleted FROM {P} WHERE producto_id = 2") == [(False,)],
   "p2: el 2 vino pero lo rechazó una regla DROP: no es una baja")
fecha_baja = filas(f"SELECT _deleted_at FROM {P} WHERE producto_id = 4")[0][0]
ok(fecha_baja is not None, "p2: la baja tiene _deleted_at")
gold("dim_producto", "gold.dim_producto", "OVERWRITE", GOLD_PRD)
gold("fact_producto", "gold.fact_producto", "MERGE", GOLD_PRD, key="producto_id")
ok(filas("SELECT producto_id FROM gold.dim_producto ORDER BY 1") == [(1,), (2,), (3,)], "gold OVERWRITE: sin la baja")
ok(filas("SELECT producto_id FROM gold.fact_producto ORDER BY 1") == [(1,), (2,), (3,)], "gold MERGE: borra la baja")
ok("_is_deleted" not in spark.table("gold.fact_producto").columns, "gold: _is_deleted no se guarda")

bronze("bronze.erp_productos", "p3", "2026-10-03 03:00:00", [(1, "P1", D("10.00"))], SCH_P)   # extracción a medias
r = silver(prd, "p3")
ok(r["status"] == "FAILED" and "DELETE_MAX_PCT" in r["error"] and bajas_prd() == [(4,)],
   "p3: faltan 2 de 3 claves vivas (67 % > 50 %): falla y no marca nada")

bronze("bronze.erp_productos", "p4", "2026-10-04 03:00:00",
       [(i, f"P{i}", D("10.00")) for i in (1, 2, 3)], SCH_P)
silver(prd, "p4")
ok(filas(f"SELECT _deleted_at FROM {P} WHERE producto_id = 4") == [(fecha_baja,)],
   "p4: una baja que sigue ausente conserva la fecha en que se detectó")

bronze("bronze.erp_productos", "p5", "2026-10-05 03:00:00",
       [(i, f"P{i}", D("10.00")) for i in (1, 2, 3, 4)], SCH_P)
silver(prd, "p5")
ok(bajas_prd() == [] and filas(f"SELECT _deleted_at FROM {P} WHERE producto_id = 4") == [(None,)],
   "p5: el 4 vuelve a venir y revive")
gold("fact_producto", "gold.fact_producto", "MERGE", GOLD_PRD, key="producto_id")
ok(spark.table("gold.fact_producto").count() == 4, "gold MERGE: el que revive vuelve a gold")

# ---------------------------------------------------------------- sucursales: SCD2 + ABSENT
SCH_S = "SucursalID int, Zona string"
suc = {"entity_code": "erp_sucursales", "bronze_table": "bronze.erp_sucursales", "silver_table": "silver.sucursales",
       "silver_mode": "SCD2", "primary_key": "sucursal_id", "order_column": None, "scd2_columns": None,
       "delete_mode": "ABSENT", "delete_flag_expr": None, "delete_max_pct": 60,
       "columns": [col("SucursalID", "sucursal_id", "int"), col("Zona", "zona", "string")], "dq_rules": None}
bronze("bronze.erp_sucursales", "s1", "2026-10-01 03:00:00", [(1, "Norte"), (2, "Sur")], SCH_S)
silver(suc, "s1")
bronze("bronze.erp_sucursales", "s2", "2026-10-02 03:00:00", [(1, "Centro")], SCH_S)
r = silver(suc, "s2")
ok(r["historia"]["bajas"] == 1 and r["historia"]["versiones_nuevas"] == 1, "s2: SCD2 con ABSENT: una baja y un cambio")
ok(filas("SELECT count(*) FROM silver.sucursales WHERE sucursal_id = 2 AND NOT _is_current AND _is_deleted") == [(1,)]
   and filas("SELECT zona FROM silver.sucursales WHERE _is_current") == [("Centro",)],
   "s2: la sucursal 2 queda cerrada y dada de baja; la 1 tiene versión vigente nueva")

# ---------------------------------------------------------------- rubros: de MERGE a SCD2
SCH_R = "RubroID int, Nombre string"
rub = {"entity_code": "erp_rubros", "bronze_table": "bronze.erp_rubros", "silver_table": "silver.rubros",
       "silver_mode": "MERGE", "primary_key": "rubro_id", "order_column": None, "scd2_columns": None,
       "delete_mode": "NONE", "delete_flag_expr": None, "delete_max_pct": None,
       "columns": [col("RubroID", "rubro_id", "int"), col("Nombre", "nombre", "string")], "dq_rules": None}
bronze("bronze.erp_rubros", "m1", "2026-10-01 03:00:00", [(1, "Limpieza"), (2, "Bazar")], SCH_R)
silver(rub, "m1")
bronze("bronze.erp_rubros", "m2", "2026-10-02 03:00:00", [(1, "Limpieza y hogar")], SCH_R)
r = silver(dict(rub, silver_mode="SCD2"), "m2")
ok(r["historia"].get("convertida_a_scd2") and spark.table("silver.rubros").count() == 3
   and filas("SELECT count(*) FROM silver.rubros WHERE _is_current") == [(2,)],
   "m2: la tabla MERGE pasa a SCD2 sin perder filas y registra el cambio como versión nueva")

print("\nTodo OK")
