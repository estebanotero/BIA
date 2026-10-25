"""Prueba local del caso Catalogo_Linaje, sin Fabric.

Qué prueba:
  1. tablas_sql: FROM y JOIN, CTE, materialized lake views, nombres con lakehouse y backticks;
     tablas_desde_m sobre una expresión M de importación.
  2. armar_linaje sobre la metadata del ejemplo del pipeline medallion: aristas de cada tramo
     (copia, carga, transforma, lee, compone, usa), dueños, items del inventario y hallazgos
     (FALTA_DEPENDS_ON_GOLD, REFERENCIA_DESCONOCIDA, PII_EN_MODELO, SILVER_SIN_USO, LEE_ENTIDAD_INACTIVA, ...).
  3. impacto (aguas abajo), vecindario, diagrama Mermaid, informe y detección de ciclos.
  4. Opcional, si hay pyspark: el notebook completo con Spark y Delta. El SQL de gold se analiza
     con el parser de Spark, las columnas reales detectan PII en gold y se escriben catalogo.*.

No prueba cat.usp_GET_FUENTES ni la lectura de reportes con sempy.

Requisitos: ninguno para 1 a 3. Punto 4: pyspark==3.5.3 y delta-spark==3.2.1, Java 17+
    python prueba_local.py
"""
import json
import os
import shutil
import types

AQUI = os.path.dirname(os.path.abspath(__file__))
NB_PATH = os.path.join(AQUI, "..", "notebooks", "NB_CAT_01_armar_linaje.ipynb")
NB = json.load(open(NB_PATH, encoding="utf-8"))
CODIGO = ["".join(c["source"]) for c in NB["cells"] if c["cell_type"] == "code"]
g = {}
exec(next(s for s in CODIGO if s.startswith("# --- funciones")), g)
f = types.SimpleNamespace(**g)


def ok(cond, msg):
    assert cond, msg
    print("  OK ", msg)


# ---------------------------------------------------------------------------
print("1. Qué tablas lee cada SQL")
ok(f.tablas_sql("SELECT a FROM silver.ventas v LEFT JOIN silver.cotizacion_dolar c ON 1=1")[0]
   == ["silver.cotizacion_dolar", "silver.ventas"], "FROM y JOIN")
ok(f.tablas_sql("WITH base AS (SELECT * FROM silver.ventas), otra AS (SELECT 1 FROM base) "
                "SELECT * FROM otra JOIN `gold`.`dim_producto` p ON 1=1")[0] == ["gold.dim_producto", "silver.ventas"],
   "los nombres de CTE no son tablas y los backticks se limpian")
ok(f.tablas_sql("""CREATE MATERIALIZED LAKE VIEW IF NOT EXISTS gold.agg
                   COMMENT "x" AS SELECT 1 FROM gold.fact_ventas f JOIN LH_GOLD.gold.dim_producto p ON 1=1""")[0]
   == ["gold.dim_producto", "gold.fact_ventas"], "materialized lake view: solo el SELECT, sin el lakehouse")
ok(f.tablas_sql("SELECT 'FROM silver.trampa' AS x -- JOIN silver.otra\nFROM silver.ok")[0] == ["silver.ok"],
   "textos y comentarios no cuentan")
ok(f.tablas_desde_m('let S = Lakehouse.Contents(null){[workspaceId="w"]}[Data], '
                    'T = S{[Schema="gold",Item="dim_cliente"]}[Data] in T') == ["gold.dim_cliente"],
   "expresión M de importación desde el lakehouse")

# ---------------------------------------------------------------------------
print("2. Linaje del modelo de ejemplo")


def ent(code, obj, bronze, silver, pii=(), activa=True):
    return {"entity_code": code, "source_system_code": "erp", "source_type": "SQL", "source_object": obj,
            "connection_ref": "conexion-erp", "bronze_table": bronze, "silver_table": silver, "silver_mode": "MERGE",
            "delete_mode": "NONE", "load_group": "default", "is_active": activa,
            "columns": [{"target_column": c, "is_pii": 1} for c in pii]}


def gold(code, target, sql, deps=None):
    return {"gold_code": code, "target_table": target, "load_mode": "OVERWRITE", "sql_text": sql,
            "depends_on_gold": deps, "load_group": "default", "is_active": True}


FUENTES = {
    "entities": [
        ent("erp_clientes", "dbo.Clientes", "bronze.erp_clientes", "silver.clientes", pii=("cuit", "email")),
        ent("erp_productos", "dbo.Productos", "bronze.erp_productos", "silver.productos"),
        ent("erp_ventas", "dbo.Ventas", "bronze.erp_ventas", "silver.ventas"),
        ent("erp_proveedores", "dbo.Proveedores", "bronze.erp_proveedores", "silver.proveedores"),
        ent("erp_viejo", "dbo.Viejo", "bronze.erp_viejo", "silver.viejo", activa=False),
    ],
    "gold_objects": [
        gold("dim_cliente", "gold.dim_cliente", "SELECT cliente_id, razon_social, email FROM silver.clientes"),
        gold("dim_producto", "gold.dim_producto", "SELECT producto_id, rubro FROM silver.productos"),
        gold("fact_ventas", "gold.fact_ventas",
             "WITH v AS (SELECT * FROM silver.ventas) SELECT v.*, c.razon_social FROM v "
             "JOIN gold.dim_cliente c ON c.cliente_id = v.cliente_id LEFT JOIN staging.ajustes a ON 1=1",
             deps="dim_producto"),
        gold("agg_ventas_mes", "gold.agg_ventas_mes",
             "CREATE MATERIALIZED LAKE VIEW IF NOT EXISTS gold.agg_ventas_mes AS "
             "SELECT p.rubro, SUM(f.importe) FROM gold.fact_ventas f JOIN gold.dim_producto p ON 1=1 GROUP BY p.rubro",
             deps="fact_ventas,dim_producto"),
        gold("hist_viejo", "gold.hist_viejo", "SELECT * FROM silver.viejo"),
    ],
    "items": [
        {"object_name": "Ventas", "artifact_type": "SemanticModel", "fabric_item_guid": "g-ventas", "workspace_id": "w1", "active_flag": True},
        {"object_name": "Tablero ventas", "artifact_type": "Report", "fabric_item_guid": "g-tablero", "workspace_id": "w1", "active_flag": True},
        {"object_name": "Finanzas", "artifact_type": "SemanticModel", "fabric_item_guid": "g-fin", "workspace_id": "w1", "active_flag": True},
        {"object_name": "LH_MEDALLION", "artifact_type": "Lakehouse", "fabric_item_guid": "g-lh", "workspace_id": "w1", "active_flag": True},
    ],
    "activos": [
        {"nodo_id": "lh:gold.fact_ventas", "dueno": "Ventas - BI", "area": "Comercial", "criticidad": "ALTA",
         "descripcion_negocio": "Una fila por venta"},
        {"nodo_id": "lh:gold.no_existe", "dueno": "Nadie", "area": None, "criticidad": "BAJA", "descripcion_negocio": None},
    ],
}


def col(nombre, sensible=False, oculta=False):
    return {"nombre": nombre, "sensible_sugerido": sensible, "oculta": oculta}


MODELO = {"modelo": "Ventas", "workspace": "WS", "generado_utc": "2026-10-25T00:00:00+00:00", "tablas": [
    {"nombre": "fact_ventas", "modo": "DirectLake", "columnas": [col("importe")],
     "origen": [{"tipo": "Entity", "esquema": "gold", "entidad": "fact_ventas", "expresion": None}]},
    {"nombre": "Clientes", "modo": "Import", "columnas": [col("Email", sensible=True), col("CUIT", sensible=True, oculta=True)],
     "origen": [{"tipo": "M", "esquema": None, "entidad": None,
                 "expresion": 'let T = S{[Schema="gold",Item="dim_cliente"]}[Data] in T'}]},
    {"nombre": "dim_producto", "modo": "DirectLake", "columnas": [col("rubro")]},     # modelo.json viejo: sin origen
    {"nombre": "Calendario", "modo": "Calculated", "columnas": [col("fecha")]},
]}
REPORTES = [{"reporte": "Tablero ventas", "modelo": "Ventas"}, {"reporte": "Tablero RRHH", "modelo": "RRHH"}]

L = f.armar_linaje(FUENTES, [MODELO], REPORTES)
A = {(a["desde"], a["hacia"]): a for a in L.aristas.values()}
H = {(h["codigo"], h["objeto"]): h for h in L.hallazgos}


def arista(d, h, tipo=None, conf=None):
    a = A.get((d, h))
    return a is not None and (tipo is None or a["tipo"] == tipo) and (conf is None or a["confianza"] == conf)


ok(arista("origen:erp/dbo.Clientes", "lh:bronze.erp_clientes", "copia")
   and arista("lh:bronze.erp_clientes", "lh:silver.clientes", "carga"), "origen → bronze → silver por meta.ENTITY")
ok(arista("lh:silver.ventas", "lh:gold.fact_ventas", "transforma", "media")
   and arista("lh:gold.dim_cliente", "lh:gold.fact_ventas"), "gold lee silver y otro gold (regex: confianza media)")
ok(arista("lh:gold.fact_ventas", "modelo:Ventas/fact_ventas", "lee", "alta"), "Direct Lake: tabla del modelo por entidad")
ok(arista("lh:gold.dim_cliente", "modelo:Ventas/Clientes", "lee", "alta"), "Import: tabla del modelo por expresión M")
ok(arista("lh:gold.dim_producto", "modelo:Ventas/dim_producto", "lee", "baja"), "sin origen en modelo.json: por nombre, confianza baja")
ok(arista("modelo:Ventas/fact_ventas", "modelo:Ventas", "compone") and arista("modelo:Ventas", "reporte:Tablero ventas", "usa"),
   "tabla del modelo → modelo → reporte")
ok(L.nodos["lh:silver.clientes"]["pii"] == ["cuit", "email"], "silver sabe sus columnas PII")
ok(L.nodos["lh:gold.fact_ventas"]["dueno"] == "Ventas - BI" and L.nodos["lh:gold.fact_ventas"]["descripcion"] == "Una fila por venta",
   "dueño y descripción de cat.ACTIVO")
ok(L.nodos["modelo:Ventas"]["atributos"]["item_guid"] == "g-ventas", "el modelo toma el GUID del inventario")

ok(("FALTA_DEPENDS_ON_GOLD", "lh:gold.fact_ventas") in H and H[("FALTA_DEPENDS_ON_GOLD", "lh:gold.fact_ventas")]["severidad"] == "ALTA",
   "fact_ventas lee dim_cliente sin DEPENDS_ON_GOLD (ALTA)")
ok(("DEPENDENCIA_SIN_LECTURA", "lh:gold.fact_ventas") in H, "fact_ventas depende de dim_producto pero no lo lee")
ok(not any(h[0] == "FALTA_DEPENDS_ON_GOLD" and h[1] == "lh:gold.agg_ventas_mes" for h in H), "la MLV declara bien sus dependencias")
ok(("REFERENCIA_DESCONOCIDA", "lh:staging.ajustes") in H, "tabla que no carga nadie")
ok(("PII_EN_MODELO", "modelo:Ventas/Clientes") in H and "CUIT" not in H[("PII_EN_MODELO", "modelo:Ventas/Clientes")]["detalle"],
   "PII visible en el modelo (la oculta no cuenta)")
ok(("SILVER_SIN_USO", "lh:silver.proveedores") in H, "silver que ningún gold lee")
ok(("GOLD_SIN_CONSUMO", "lh:gold.agg_ventas_mes") in H, "gold que ningún modelo lee")
ok(("LEE_ENTIDAD_INACTIVA", "lh:silver.viejo") in H, "gold que lee una entidad inactiva")
ok(("MODELO_SIN_DOCUMENTAR", "modelo:RRHH") in H and ("ITEM_FUERA_DEL_LINAJE", "modelo:Finanzas") in H,
   "modelos sin modelo.json e items del inventario fuera del linaje")
ok(("ACTIVO_INEXISTENTE", "lh:gold.no_existe") in H and ("SIN_DUENO", "lh:gold.dim_cliente") in H, "dueños: inexistente y faltante")
ok(not any(h[0] == "TABLA_MODELO_SIN_ORIGEN" for h in H), "una tabla calculada no necesita origen")
ok([h["severidad"] for h in L.hallazgos] == sorted([h["severidad"] for h in L.hallazgos], key=f.SEVERIDADES.index),
   "hallazgos ordenados por severidad")

# ---------------------------------------------------------------------------
print("3. Impacto, diagrama e informe")
imp = {(r["desde"], r["hasta"]): r["distancia"] for r in f.impacto(L)}
ok(imp[("origen:erp/dbo.Clientes", "reporte:Tablero ventas")] == 6,
   "cambiar dbo.Clientes llega al Tablero ventas a 6 pasos por el camino más corto (bronze, silver, dim_cliente, tabla del modelo, modelo, reporte)")
ok(imp[("lh:silver.clientes", "lh:gold.agg_ventas_mes")] == 3, "y a la MLV por dim_cliente → fact_ventas")
ok(("lh:silver.proveedores", "reporte:Tablero ventas") not in imp, "lo que no está conectado no aparece")
vec = f.vecindario(L, "lh:gold.dim_producto")
ok("lh:silver.productos" in vec and "lh:gold.agg_ventas_mes" in vec and "lh:silver.clientes" not in vec,
   "vecindario: ancestros y descendientes, no hermanos")
m = f.mermaid(L)
ok(m.startswith("flowchart LR") and "subgraph gold[Gold]" in m and "-.->" in m and "🔒" in m,
   "Mermaid con capas, aristas de baja confianza punteadas y candado en PII")
ok(f.mermaid(L, max_nodos=5) is None, "demasiados nodos: no hay diagrama completo")
md = f.informe_md(L, max_nodos=10)
ok("### gold.fact_ventas" in md and "| ALTA | FALTA_DEPENDS_ON_GOLD |" in md, "informe: diagrama por gold si es grande, y hallazgos")
ok(f.resumen(L)["hay_alta"] and f.resumen(L)["nodos"] == len(L.nodos), "resumen para el exit")

ciclo = f.armar_linaje({"gold_objects": [gold("a", "gold.a", "SELECT * FROM gold.b", "b"),
                                         gold("b", "gold.b", "SELECT * FROM gold.a", "a")]})
ok(any(h["codigo"] == "CICLO" for h in ciclo.hallazgos), "detecta un ciclo entre objetos gold")

# ---------------------------------------------------------------------------
try:
    import pyspark  # noqa: F401
    from delta import configure_spark_with_delta_pip
except ImportError:
    print("4. Sin pyspark: salteo el notebook completo")
    print("\nTodo OK")
    raise SystemExit(0)

print("4. Notebook completo con Spark y Delta")
from pyspark.sql import SparkSession

work = os.path.abspath("work_prueba_local")
shutil.rmtree(work, ignore_errors=True)
os.makedirs(work)
os.chdir(work)
spark = configure_spark_with_delta_pip(SparkSession.builder.master("local[2]")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .config("spark.sql.warehouse.dir", work + "/wh")
    .config("spark.ui.showConsoleProgress", "false")
    .config("spark.sql.shuffle.partitions", "2")).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
for s in ("silver", "gold", "perfil", "doc"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {s}")
spark.sql("CREATE TABLE silver.clientes (cliente_id INT, razon_social STRING, cuit STRING, email STRING) USING DELTA")
spark.sql("CREATE TABLE gold.dim_cliente (cliente_id INT, razon_social STRING, email STRING) USING DELTA")
spark.sql("CREATE TABLE gold.fact_ventas (venta_id INT, razon_social STRING) USING DELTA")
spark.sql("CREATE TABLE perfil.tabla (corrida_id STRING, tabla STRING, filas BIGINT, descripcion_origen STRING) USING DELTA")
spark.sql("INSERT INTO perfil.tabla VALUES ('c1', 'bronze.erp_clientes', 10, 'vieja'), ('c2', 'bronze.erp_clientes', 12, 'Clientes del ERP')")
spark.sql("CREATE TABLE doc.diccionario (modelo STRING, tipo_objeto STRING, tabla STRING, descripcion STRING) USING DELTA")
spark.sql("INSERT INTO doc.diccionario VALUES ('Ventas', 'tabla', 'fact_ventas', 'Ventas por día')")
os.makedirs("Files/doc_modelos/Ventas")
json.dump(MODELO, open("Files/doc_modelos/Ventas/modelo.json", "w"))


class Exit(Exception):
    def __init__(s, v): s.v = v


nu = types.SimpleNamespace(notebook=types.SimpleNamespace(exit=lambda v: (_ for _ in ()).throw(Exit(v))))
args = {"run_id": "prueba", "fuentes_json": json.dumps(FUENTES), "reportes_json": json.dumps(REPORTES),
        "carpeta_modelos": "Files/doc_modelos", "carpeta_salida": "Files/catalogo"}
gn = {"spark": spark, "notebookutils": nu, "display": lambda df: None}
salida = None
for c in [c for c in NB["cells"] if c["cell_type"] == "code"]:
    try:
        exec("".join(c["source"]), gn)
    except Exit as e:
        salida = json.loads(e.v)
        break
    if "parameters" in c["metadata"].get("tags", []):
        gn.update(args)

ok(salida and salida["run_id"] == "prueba" and salida["hay_alta"], "el notebook devuelve el resumen por exit")
ok(gn["tablas_sql"](FUENTES["gold_objects"][2]["sql_text"], gn["arbol_spark"]) ==
   (["gold.dim_cliente", "silver.ventas", "staging.ajustes"], "parser"), "el parser de Spark lee el SQL con CTE sin ejecutarlo")
ok(gn["tablas_sql"](FUENTES["gold_objects"][3]["sql_text"], gn["arbol_spark"])[1] == "parser", "y el de la materialized lake view")
LS = gn["L"]
ok(LS.aristas[("lh:silver.ventas", "lh:gold.fact_ventas")]["confianza"] == "alta", "con el parser, la arista es de confianza alta")
pii = [h for h in LS.hallazgos if h["codigo"] == "PII_EN_GOLD"]
ok(len(pii) == 1 and pii[0]["objeto"] == "lh:gold.dim_cliente" and "email" in pii[0]["detalle"],
   "la tabla gold real con email genera PII_EN_GOLD; fact_ventas no")
ok(LS.nodos["lh:bronze.erp_clientes"]["atributos"]["filas_perfil"] == 12
   and LS.nodos["lh:bronze.erp_clientes"]["descripcion"] == "Clientes del ERP", "bronze toma el último perfil")
ok(LS.nodos["modelo:Ventas/fact_ventas"]["descripcion"] == "Ventas por día", "la tabla del modelo toma la descripción del diccionario")
ok(LS.nodos["lh:gold.hist_viejo"]["atributos"]["existe"] is False, "un gold que no existe en el lakehouse queda marcado")
n = spark.table("catalogo.nodo")
ok(n.count() == len(LS.nodos) and set(n.columns) >= {"id", "tipo", "capa", "pii", "atributos", "run_id", "generado_at"},
   "catalogo.nodo escrito")
ok(spark.sql("SELECT count(*) FROM catalogo.impacto WHERE desde = 'lh:silver.clientes' AND hasta = 'reporte:Tablero ventas'").first()[0] == 1,
   "catalogo.impacto responde qué reportes toca un cambio en silver")
ok(spark.table("catalogo.hallazgo").where("codigo = 'FALTA_DEPENDS_ON_GOLD'").count() == 1, "catalogo.hallazgo escrito")
ok("```mermaid" in open("Files/catalogo/linaje.md", encoding="utf-8").read()
   and json.load(open("Files/catalogo/linaje.json"))["run_id"] == "prueba", "linaje.md y linaje.json")
# segunda corrida: foto completa, no se duplica
for c in [c for c in NB["cells"] if c["cell_type"] == "code"]:
    try:
        exec("".join(c["source"]), gn)
    except Exit:
        break
    if "parameters" in c["metadata"].get("tags", []):
        gn.update(args)
ok(spark.table("catalogo.nodo").count() == len(LS.nodos), "correrlo de nuevo reemplaza la foto, no duplica")

print("\nTodo OK")
