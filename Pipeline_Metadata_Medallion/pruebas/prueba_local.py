"""Prueba local de los notebooks NB_MDP_* con Spark + Delta, sin Fabric.

Simula notebookutils (fs.exists, notebook.exit, runMultiple en serie) y corre cuatro
corridas del orquestador sobre datos inventados:
  r1  carga inicial: regla DROP, regla WARN, PII, nombres de columna con espacios
  r2  incremental: watermark de SQL y de archivos (modifiedAfter), MERGE por clave
  r3  copia fallida: bronze no lee la carpeta y silver queda bloqueado
  r4  reproceso de silver con una regla FAIL: gold no se ejecuta

No prueba el pipeline, la base de control ni las materialized lake views.

Requisitos (probado con Python 3.13, Java 21):
    python -m venv venv && venv/bin/pip install -U pip setuptools wheel
    venv/bin/pip install pyspark==3.5.3 delta-spark==3.2.1
    venv/bin/python prueba_local.py
"""
import json, os, sys, shutil, types, datetime as dt
NB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "notebooks")
work = os.path.abspath("work_prueba_local"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work); os.chdir(work)

from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip
spark = configure_spark_with_delta_pip(SparkSession.builder.master("local[2]")
    .config("spark.sql.extensions","io.delta.sql.DeltaSparkSessionExtension")
    .config("spark.sql.catalog.spark_catalog","org.apache.spark.sql.delta.catalog.DeltaCatalog")
    .config("spark.sql.warehouse.dir", work+"/wh")
    .config("spark.sql.shuffle.partitions","2")).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
for s in ("bronze","silver","gold"): spark.sql(f"CREATE SCHEMA IF NOT EXISTS {s}")

class Exit(Exception):
    def __init__(s,v): s.v=v
def load_cells(name):
    nb=json.load(open(f"{NB}/{name}.ipynb"))
    return [c for c in nb["cells"] if c["cell_type"]=="code"]
def run_nb(name, args):
    g={"spark":spark,"notebookutils":nu,"display":lambda df: df.show(truncate=False)}
    for c in load_cells(name):
        src="".join(c["source"])
        try: exec(src,g)
        except Exit as e: return e.v
        if "parameters" in c["metadata"].get("tags",[]): g.update(args)
    return None
def runMultiple(dag, cfg=None):
    done={}; acts=list(dag["activities"])
    while acts:
        for a in list(acts):
            if all(d in done for d in a.get("dependencies",[])):
                try: done[a["name"]]={"exitVal":run_nb(a["path"],a.get("args",{})),"exception":None}
                except Exception as ex: done[a["name"]]={"exitVal":"","exception":ex}
                acts.remove(a)
    return done
nu=types.SimpleNamespace(
    fs=types.SimpleNamespace(exists=lambda p: os.path.exists(p)),
    notebook=types.SimpleNamespace(exit=lambda v:(_ for _ in ()).throw(Exit(v)), runMultiple=runMultiple, validateDAG=lambda d: True))

def landing(entity, run, rows, schema):
    spark.createDataFrame(rows, schema).write.mode("overwrite").parquet(f"Files/landing/{entity}/{run}")

cols_cli=[("ClienteID","cliente_id","int",None,0),("RazonSocial","razon_social","string","trim(RazonSocial)",0),
          ("CUIT","cuit","string","regexp_replace(CUIT, '[^0-9]', '')",1),("Email","email","string","lower(trim(Email))",1),
          ("FechaModificacion","fecha_modificacion","timestamp",None,0)]
def ent(run, wm=None, copy_failed=False):
    return {"entity_code":"erp_clientes","source_type":"SQL","read_path":f"Files/landing/erp_clientes/{run}","file_format":"parquet",
     "load_type":"INCREMENTAL","watermark_column":"FechaModificacion","watermark_type":"DATETIME","watermark_value":wm,
     "primary_key":"cliente_id","order_column":"fecha_modificacion","bronze_table":"bronze.erp_clientes","silver_table":"silver.clientes",
     "silver_mode":"MERGE","copy_failed":copy_failed,
     "columns":[dict(source_column=a,target_column=b,target_type=c,transform_expr=d,is_pii=e) for a,b,c,d,e in cols_cli],
     "dq_rules":[{"rule_name":"cliente_id_no_nulo","rule_expr":"cliente_id IS NOT NULL","action":"DROP"},
                 {"rule_name":"cuit_11","rule_expr":"cuit IS NULL OR length(cuit) = 11","action":"WARN"}]}
cot={"entity_code":"cot_dolar","source_type":"FILES","read_path":"Files/shortcuts/cot","file_format":"csv","load_type":"INCREMENTAL",
     "watermark_column":None,"watermark_type":"DATETIME","watermark_value":None,"primary_key":"fecha,tipo","order_column":None,
     "bronze_table":"bronze.cot_dolar","silver_table":"silver.cotizacion_dolar","silver_mode":"MERGE","copy_failed":False,
     "columns":[{"source_column":"fecha","target_column":"fecha","target_type":"date","transform_expr":"to_date(fecha, 'dd/MM/yyyy')","is_pii":0},
                {"source_column":"tipo","target_column":"tipo","target_type":"string","transform_expr":"lower(tipo)","is_pii":0},
                {"source_column":"venta","target_column":"venta","target_type":"decimal(18,4)","transform_expr":None,"is_pii":0}],
     "dq_rules":None}
os.makedirs("Files/shortcuts/cot"); open("Files/shortcuts/cot/a.csv","w").write("fecha,tipo,venta\n01/10/2026,Oficial,1000.5\n02/10/2026,Oficial,1001\n")
gold=[{"gold_code":"dim_cliente","target_table":"gold.dim_cliente","load_mode":"OVERWRITE","merge_key":None,
       "sql_text":"SELECT cliente_id, razon_social FROM silver.clientes","depends_on_gold":None},
      {"gold_code":"cnt","target_table":"gold.cnt","load_mode":"MERGE","merge_key":"k",
       "sql_text":"SELECT 1 AS k, count(*) AS n FROM gold.dim_cliente","depends_on_gold":"dim_cliente"}]
sch="ClienteID int, `Razon Social` string, CUIT string, Email string, FechaModificacion timestamp"
# columna con espacio para probar el saneo -> transform usa Razon_Social
cols_cli[1]=("Razon_Social","razon_social","string","trim(Razon_Social)",0)
T=dt.datetime
landing("erp_clientes","r1",[(1," ACME ","30-11111111-1","A@X.COM",T(2026,10,1)),(2,"Beta","123","b@x.com",T(2026,10,2)),
                             (None,"Sin id",None,None,T(2026,10,2)),(1,"ACME SA","30-11111111-1","a@x.com",T(2026,10,3))],sch)
def orq(run, ents, layers="bronze,silver,gold", extra=None):
    cfg={"run_id":run,"entities":ents,"gold_objects":gold}
    a={"run_id":run,"config_json":json.dumps(cfg,default=str),"layers":layers}; a.update(extra or {})
    return json.loads(run_nb("NB_MDP_00_orquestador",a))
r1=orq("r1",[ent("r1"),cot]); print("R1", json.dumps([(p["layer"],p["object_code"],p["status"],p.get("rows_written"),p.get("dq_warnings"),p.get("new_watermark")) for p in r1["pasos"]],default=str))
spark.table("silver.clientes").orderBy("cliente_id").show(truncate=False)
spark.table("silver.dq_rechazos").show(truncate=False)
spark.table("silver.cotizacion_dolar").show()
print(spark.sql("SHOW TBLPROPERTIES silver.clientes").where("key like 'mdp%'").collect())
# corrida 2: cambios a cliente 2 + uno nuevo; cot sin archivos nuevos (modifiedAfter)
wm=[p for p in r1["pasos"] if p["object_code"]=="erp_clientes" and p["layer"]=="bronze"][0]["new_watermark"]
wmc=[p for p in r1["pasos"] if p["object_code"]=="cot_dolar" and p["layer"]=="bronze"][0]["new_watermark"]
print("WM", wm, wmc)
landing("erp_clientes","r2",[(2,"Beta SRL","20-22222222-2","b@x.com",T(2026,10,5)),(3,"Gamma","x","g@x.com",T(2026,10,6))],sch)
c2=dict(cot, watermark_value=wmc)
r2=orq("r2",[ent("r2",wm),c2]); print("R2",json.dumps([(p["layer"],p["object_code"],p["status"],p.get("rows_written"),p.get("dq_warnings"),p.get("new_watermark"),p.get("error")) for p in r2["pasos"]],default=str))
spark.table("silver.clientes").orderBy("cliente_id").show(truncate=False)
spark.table("gold.cnt").show()
# corrida 3: copy fallida -> bronze SKIPPED, silver SKIPPED_NO_DATA, gold corre
r3=orq("r3",[ent("r3",wm,copy_failed=True)]); print("R3",[(p["layer"],p["status"]) for p in r3["pasos"]], r3["hay_errores"])
# corrida 4: FAIL rule -> silver FAILED, gold SKIPPED_UPSTREAM_FAILED
e4=ent("r2"); e4["dq_rules"]=[{"rule_name":"x","rule_expr":"cliente_id > 2","action":"FAIL"}]
r4=orq("r4",[e4],layers="silver,gold",extra={"reprocesar_run_id":"r2"}); print([(p["layer"],p["status"],(p.get("error") or "")[:80]) for p in r4["pasos"]], r4["hay_errores"])
