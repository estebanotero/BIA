"""Prueba local de los notebooks NB_PRF_* con Spark + Delta, sin Fabric.

Arma un bronze inventado como lo dejaría NB_MDP_10 (con _run_id e _ingested_at) y corre:
  1  NB_PRF_01: tipos sugeridos, PII por nombre y por contenido, claves simples y compuestas,
     catálogo con PK y FK declaradas, solo la última copia de bronze
  2  NB_PRF_02: una FK declarada con huérfanos, una relación inferida por nombre y el rol de cada tabla
  3  NB_PRF_03: una propuesta con una regla FAIL que no se cumple, una pérdida por conversión de tipo
     y una columna PII sin marcar

No prueba la copia exploratoria del pipeline ni el script de catálogo en SQL Server.

Requisitos (probado con Python 3.13, Java 21):
    python -m venv venv && venv/bin/pip install -U pip setuptools wheel
    venv/bin/pip install pyspark==3.5.3 delta-spark==3.2.1
    venv/bin/python prueba_local.py
"""
import json, os, shutil, types, datetime as dt
NB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notebooks")
work = os.path.abspath("work_prueba_local"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work); os.chdir(work)

from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip
spark = configure_spark_with_delta_pip(SparkSession.builder.master("local[2]")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .config("spark.sql.warehouse.dir", work + "/wh")
    .config("spark.sql.shuffle.partitions", "2")).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")


class Exit(Exception):
    def __init__(s, v): s.v = v


nu = types.SimpleNamespace(notebook=types.SimpleNamespace(exit=lambda v: (_ for _ in ()).throw(Exit(v))))


def run_nb(name, args):
    g = {"spark": spark, "notebookutils": nu, "display": lambda df: df.show(truncate=80)}
    for c in json.load(open(f"{NB}/{name}.ipynb"))["cells"]:
        if c["cell_type"] != "code":
            continue
        try:
            exec("".join(c["source"]), g)
        except Exit as e:
            return json.loads(e.v)
        if "parameters" in c["metadata"].get("tags", []):
            g.update(args)
    return None


T = dt.datetime


def bronze(tabla, run, ingesta, filas, esquema):
    df = spark.createDataFrame(filas, esquema)
    from pyspark.sql import functions as F
    (df.withColumn("_run_id", F.lit(run)).withColumn("_ingested_at", F.lit(ingesta).cast("timestamp"))
       .write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(tabla))


# Clientes desde SQL (tipado). La copia vieja (x0) tiene una fila que ya no existe: no se tiene que perfilar.
sch_cli = "ClienteID int, Razon_Social string, CUIT string, Email string, Provincia string, FechaAlta timestamp, FechaModificacion timestamp"
bronze("bronze.erp_clientes", "x0", T(2026, 10, 1), [(99, "Vieja", None, None, "X", T(2020, 1, 1), T(2020, 1, 1))], sch_cli)
bronze("bronze.erp_clientes", "x1", T(2026, 10, 20), [
    (1, " ACME SA ", "30-71111111-1", "ventas@acme.com", "Cordoba", T(2020, 3, 1), T(2026, 10, 1, 10)),
    (2, "Perez Juan", "20-22222222-2", "jperez@mail.com", "CORDOBA", T(2021, 5, 2), T(2026, 10, 2, 11)),
    (3, "Beta SRL", "30-73333333-3", "info@beta.com.ar", "Buenos Aires", T(2022, 7, 3), T(2026, 10, 3, 12)),
    (4, "Gomez Ana", "27-44444444-4", "ana@x.com", "buenos aires ", T(2023, 1, 4), T(2026, 10, 4, 13))], sch_cli)
# Productos desde SQL, con double
bronze("bronze.erp_productos", "x1", T(2026, 10, 20), [(10, "Tornillo", "Ferreteria", 1.5), (11, "Tuerca", "Ferreteria", 0.75),
                                                       (12, "Martillo", "Herramientas", 12.0)],
       "ProductoID int, Descripcion string, Rubro string, PrecioLista double")
# Ventas desde CSV: todo texto. Fecha dd/MM/yyyy, importe con coma, un cliente huérfano (99), una cantidad negativa
sch_txt = "VentaID string, Fecha string, ClienteID string, ProductoID string, Cantidad string, Importe string, Moneda string, Anulada string"
bronze("bronze.erp_ventas", "x1", T(2026, 10, 20), [
    ("1", "15/10/2026", "1", "10", "2", "1.234,50", "ARS", "0"),
    ("2", "16/10/2026", "2", "11", "1", "99,90", "ars ", "0"),
    ("3", "17/10/2026", "3", "10", "-1", "10,00", "USD", "1"),
    ("4", "18/10/2026", "99", "12", "3", "1.000,00", "ARS", "0"),
    ("5", "19/10/2026", "4", "12", "2,5", "50,25", "ARS", "0")], sch_txt)
# Detalle con clave compuesta (VentaID, Linea)
bronze("bronze.erp_ventas_detalle", "x1", T(2026, 10, 20), [("1", "1", "10"), ("1", "2", "11"), ("2", "1", "11"), ("3", "1", "10")],
       "VentaID string, Linea string, ProductoID string")

# Catálogo del origen como lo devuelve sql/01_catalogo_origen.sql (exportado a CSV)
os.makedirs("Files/perfil/erp/catalogo")
cab = "ESQUEMA,TABLA,COLUMNA,ORDINAL,TIPO,ADMITE_NULOS,ES_IDENTITY,ES_PK,FK_ESQUEMA_REF,FK_TABLA_REF,FK_COLUMNA_REF,FILAS_APROX,DESCRIPCION_TABLA,DESCRIPCION_COLUMNA"
open("Files/perfil/erp/catalogo/catalogo.csv", "w").write("\n".join([cab,
    "dbo,Clientes,ClienteID,1,int,0,1,1,,,,4,Maestro de clientes,Identificador del cliente",
    "dbo,Clientes,Email,4,varchar(200),1,0,0,,,,4,Maestro de clientes,",
    "dbo,Ventas,VentaID,1,int,0,1,1,,,,5,Cabecera de ventas,",
    "dbo,Ventas,ClienteID,3,int,0,0,0,dbo,Clientes,ClienteID,5,Cabecera de ventas,Cliente que compra"]) + "\n")

salida = os.path.abspath("Files/perfil")
comunes = {"ORIGEN": "erp", "CARPETA_SALIDA": salida, "PREFIJO_BRONZE": "erp_"}

# ---------------------------------------------------------------- 1. Perfil
r1 = run_nb("NB_PRF_01_perfilar", {**comunes, "TABLAS": "bronze.erp_*",
                                     "CATALOGO": "Files/perfil/erp/catalogo/catalogo.csv"})
col = {(r["tabla"].split(".")[-1], r["columna"]): r.asDict() for r in spark.table("perfil.columna").collect()}
cl = spark.table("perfil.clave_candidata").collect()
def ok(cond, msg):
    print(("OK   " if cond else "FALLA") + " " + msg)
    if not cond:
        raise SystemExit(1)

ok(col[("erp_clientes", "ClienteID")]["filas"] == 4, "solo la última copia de bronze (4 filas, no 5)")
ok(col[("erp_clientes", "ClienteID")]["es_unica"] and col[("erp_clientes", "ClienteID")]["es_pk_declarada"], "ClienteID única y PK declarada")
ok(col[("erp_clientes", "Email")]["pii"] and "emails" in col[("erp_clientes", "Email")]["pii_motivo"], "Email PII por contenido")
ok(col[("erp_clientes", "Email")]["top_valores"] is None and col[("erp_clientes", "Email")]["min"] is None, "sin ejemplos ni min/max de PII")
ok(col[("erp_clientes", "CUIT")]["pii"] and "personas" in col[("erp_clientes", "CUIT")]["pii_motivo"], "CUIT con personas es PII")
ok(col[("erp_clientes", "FechaAlta")]["tipo_sugerido"] == "date", "timestamp sin hora -> date")
ok(col[("erp_clientes", "FechaModificacion")]["candidata_watermark"] == "DATETIME", "FechaModificacion candidata a watermark")
ok("upper(trim())" in (col[("erp_clientes", "Provincia")]["notas"] or ""), "Provincia: variantes de mayúsculas")
ok(col[("erp_productos", "PrecioLista")]["tipo_sugerido"] == "decimal(18,4)", "double -> decimal(18,4)")
ok(col[("erp_ventas", "Fecha")]["transform_sugerida"] == "to_date(trim(`Fecha`), 'd/M/yyyy')", "fecha dd/MM/yyyy con transform")
ok(col[("erp_ventas", "Importe")]["tipo_sugerido"].startswith("decimal") and "replace" in col[("erp_ventas", "Importe")]["transform_sugerida"], "importe con coma decimal")
ok(col[("erp_ventas", "VentaID")]["tipo_sugerido"] == "int", "VentaID texto -> int")
ok(col[("erp_ventas", "Anulada")]["candidata_baja_logica"], "Anulada candidata a baja lógica")
ok(col[("erp_ventas", "ClienteID")]["fk_declarada"] == "dbo.Clientes.ClienteID", "FK declarada leída del catálogo")
ok(any(r["tabla"] == "bronze.erp_ventas_detalle" and r["columnas"] == "VentaID,Linea" and r["preferida"] for r in cl), "clave compuesta preferida VentaID,Linea")
ok([r["columnas"] for r in cl if r["tabla"] == "bronze.erp_clientes" and r["preferida"]] == ["ClienteID"], "en una tabla chica la preferida es ClienteID, no Email")

# ---------------------------------------------------------------- 2. Relaciones
r2 = run_nb("NB_PRF_02_relaciones", comunes)
rel = {(r["tabla_hijo"].split(".")[-1], r["columna_hijo"], r["tabla_padre"].split(".")[-1]): r.asDict()
       for r in spark.table("perfil.relacion").collect()}
ok(rel[("erp_ventas", "ClienteID", "erp_clientes")]["estado"] == "declarada_con_huerfanos", "FK declarada con huérfanos")
ok(rel[("erp_ventas", "ClienteID", "erp_clientes")]["filas_huerfanas"] == 1, "una fila huérfana (cliente 99)")
ok(rel[("erp_ventas", "ProductoID", "erp_productos")]["estado"] == "probable", "ProductoID -> productos inferida por nombre")
ok(rel[("erp_ventas_detalle", "VentaID", "erp_ventas")]["estado"] == "probable", "detalle -> ventas inferida")
ok(("erp_clientes", "ClienteID", "erp_ventas") not in rel, "sin relaciones invertidas")
ok(all(r["columna_padre"] == "VentaID" for k, r in rel.items() if k[2] == "erp_ventas"), "a ventas solo se llega por su clave")
perfil = json.load(open(os.path.join(r2["carpeta"], "perfil.json")))
roles = {t["tabla"].split(".")[-1]: t["rol_sugerido"] for t in perfil["tablas"]}
ok(roles["erp_clientes"] == "dimension" and roles["erp_productos"] == "dimension", f"roles de dimensión {roles}")
ok(roles["erp_ventas"] in ("hecho", "hecho_cabecera"), "ventas como hecho")
ok("erDiagram" in open(os.path.join(r2["carpeta"], "resumen_perfil.md")).read(), "resumen con diagrama Mermaid")

# ---------------------------------------------------------------- 3. Validar una propuesta
def c(src, dst, typ, tr=None, pii=0):
    return {"source_column": src, "target_column": dst, "target_type": typ, "transform_expr": tr, "is_pii": pii}
cfg = {"run_id": "val", "load_group": "default", "entities": [
    {"entity_code": "erp_ventas", "bronze_table": "bronze.erp_ventas", "silver_table": "silver.ventas", "silver_mode": "MERGE",
     "primary_key": "venta_id", "order_column": None,
     "columns": [c("VentaID", "venta_id", "int"), c("Fecha", "fecha", "date", "to_date(trim(`Fecha`), 'd/M/yyyy')"),
                 c("ClienteID", "cliente_id", "int"), c("Cantidad", "cantidad", "int"),
                 c("Importe", "importe", "decimal(18,2)", "replace(replace(trim(`Importe`), '.', ''), ',', '.')")],
     "dq_rules": [{"rule_name": "venta_id_no_nulo", "rule_expr": "venta_id IS NOT NULL", "action": "FAIL"},
                  {"rule_name": "cantidad_positiva", "rule_expr": "cantidad > 0", "action": "FAIL"}]},
    {"entity_code": "erp_clientes", "bronze_table": "bronze.erp_clientes", "silver_table": "silver.clientes", "silver_mode": "MERGE",
     "primary_key": "cliente_id", "order_column": "fecha_modificacion",
     "columns": [c("ClienteID", "cliente_id", "int"), c("Email", "email", "string", "lower(trim(Email))", 0),
                 c("CUIT", "cuit", "string", None, 1)], "dq_rules": []}],
    "gold_objects": [{"gold_code": "dim_cliente", "target_table": "gold.dim_cliente", "load_mode": "OVERWRITE",
                      "merge_key": None, "depends_on_gold": None, "sql_text": "SELECT cliente_id, cuit FROM silver.clientes"}]}
r3 = run_nb("NB_PRF_03_validar_propuesta", {**comunes, "config_json": json.dumps(cfg)})
h = r3["hallazgos"]
def hay(sev, obj, txt):
    return any(x["severidad"] == sev and x["objeto"] == obj and txt in x["detalle"] for x in h)
ok(r3["hay_bloqueantes"], "la propuesta tiene bloqueantes")
ok(hay("BLOQUEANTE", "erp_ventas", "cantidad > 0"), "regla FAIL que hoy fallaría")
ok(hay("ADVERTENCIA", "erp_ventas", "cantidad: 1 valores"), "Cantidad '2,5' se pierde al convertir a int")
ok(hay("ADVERTENCIA", "erp_clientes", "email: el perfil la marcó como PII"), "Email PII sin marcar")
ok(hay("ADVERTENCIA", "dim_cliente", "cuit"), "gold usa una columna PII")
ok(hay("INFO", "dim_cliente", "No se compila todavía"), "gold sin silver: queda pendiente")
ok(not any(x["severidad"] != "INFO" and "fecha" in x["detalle"] for x in h), "la fecha convierte sin pérdidas")
print("\nTodas las pruebas pasaron.")
