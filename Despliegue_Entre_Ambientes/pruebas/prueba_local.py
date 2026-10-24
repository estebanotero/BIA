"""Prueba local del caso Despliegue_Entre_Ambientes, sin Fabric ni SQL Server.

Qué prueba:
  1. deploy/validar.py sobre un repo de implementación armado en una carpeta temporal:
     parameter.yml válido e inválido (validador real de fabric-cicd 1.4.0), GUID sin
     parametrizar, secretos y reglas de sql/.
  2. deploy/aplicar_sql.py: lotes por GO, nombres, marca de impacto, plan
     (aplicar, saltear, reaplicar, error si se editó una migración) y la ejecución con
     una conexión simulada (commit y registro si sale bien, rollback si falla).
     También que el DDL real de BIA (Pipeline_Metadata_Medallion e Inventario) pase
     por esas reglas como se espera.
  3. deploy/desplegar_items.py con fabric-cicd simulado: qué parámetros recibe y
     que solo borra huérfanos si se pide.
  4. Los workflows de GitHub Actions: YAML válido y que llamen a scripts que existen.

No prueba el despliegue contra un workspace real, la conexión a la base ni azure/login.

Requisitos (probado con Python 3.13):
    pip install -r ../plantilla_repo/deploy/requirements.txt
    python prueba_local.py
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path

import yaml

AQUI = Path(__file__).resolve().parent
PLANTILLA = AQUI.parent / "plantilla_repo"
BIA = AQUI.parent.parent
sys.path.insert(0, str(PLANTILLA / "deploy"))

import aplicar_sql  # noqa: E402
import desplegar_items  # noqa: E402
import validar  # noqa: E402

FALLAS = []


def ok(cond, msg):
    print(("  OK   " if cond else "  FALLA ") + msg)
    if not cond:
        FALLAS.append(msg)


def silencio(f, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        r = f(*a, **k)
    return r, buf.getvalue()


NOTEBOOK = '''# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {"name": "synapse_pyspark"},
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "22222222-2222-2222-2222-222222222222",
# META       "default_lakehouse_name": "LH_MEDALLION",
# META       "default_lakehouse_workspace_id": "11111111-1111-1111-1111-111111111111"
# META     }
# META   }
# META }

# CELL ********************

SQL_SERVER = "<servidor-des>.database.fabric.microsoft.com"
'''

PLATFORM = '''{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
  "metadata": {"type": "Notebook", "displayName": "NB_MDP_00_orquestador"},
  "config": {"version": "2.0", "logicalId": "aaaaaaaa-0000-0000-0000-000000000001"}
}
'''


def armar_repo(raiz: Path):
    nb = raiz / "workspace" / "NB_MDP_00_orquestador.Notebook"
    nb.mkdir(parents=True)
    (nb / ".platform").write_text(PLATFORM, encoding="utf-8")
    (nb / "notebook-content.py").write_text(NOTEBOOK, encoding="utf-8")
    shutil.copy(PLANTILLA / "workspace" / "parameter.yml", raiz / "workspace" / "parameter.yml")
    (raiz / "sql").mkdir()
    shutil.copy(BIA / "Pipeline_Metadata_Medallion" / "sql" / "01_ddl_control.sql", raiz / "sql" / "001_ddl_control.sql")


def correr_validar(raiz, *extra):
    r, salida = silencio(validar.main, ["--raiz", str(raiz), *extra])
    return r, salida


# ---------------------------------------------------------------------------
print("1. validar.py")
with tempfile.TemporaryDirectory() as tmp:
    raiz = Path(tmp)
    armar_repo(raiz)
    r, salida = correr_validar(raiz)
    ok(r == 0, "repo de ejemplo con la plantilla de parameter.yml: 0 errores")
    ok("Parameter file validation passed" in salida, "fabric-cicd valida parameter.yml para TEST y PRD")

    nbc = raiz / "workspace" / "NB_MDP_00_orquestador.Notebook" / "notebook-content.py"
    nbc.write_text(NOTEBOOK + 'OTRO = "99999999-9999-9999-9999-999999999999"\n', encoding="utf-8")
    r, salida = correr_validar(raiz)
    ok(r == 0 and "ADVERTENCIA GUID 99999999" in salida, "GUID sin parametrizar: advertencia")
    r, salida = correr_validar(raiz, "--estricto")
    ok(r == 1 and "ERROR" in salida and "99999999" in salida, "GUID sin parametrizar con --estricto: error")
    nbc.write_text(NOTEBOOK, encoding="utf-8")

    p = raiz / "workspace" / "parameter.yml"
    datos = yaml.safe_load(p.read_text(encoding="utf-8"))
    datos["find_replace"][1]["replace_value"]["PRD"] = "$items.Lakehouse"      # variable mal escrita
    p.write_text(yaml.safe_dump(datos, allow_unicode=True), encoding="utf-8")
    r, salida = correr_validar(raiz)
    ok(r == 1 and "no es válido para PRD" in salida, "variable $items mal escrita en PRD: error")
    shutil.copy(PLANTILLA / "workspace" / "parameter.yml", p)

    (raiz / "workspace" / "config.json").write_text(
        '{"cs": "Server=x;Database=y;Password=Sup3rSecreta!;"}', encoding="utf-8")
    r, salida = correr_validar(raiz)
    ok(r == 1 and "password en connection string" in salida, "password en un archivo: error")
    (raiz / "workspace" / "config.json").write_text('{"cs": "Server=x;Password=<desde Key Vault>;"}', encoding="utf-8")
    r, salida = correr_validar(raiz)
    ok(r == 0, "marcador <...> en lugar del password: no es secreto")

    (raiz / "sql" / "2_alta.sql").write_text("SELECT 1;", encoding="utf-8")
    r, salida = correr_validar(raiz)
    ok(r == 1 and "NNN_descripcion.sql" in salida, "migración con nombre inválido: error")
    (raiz / "sql" / "2_alta.sql").unlink()

    r, salida = correr_validar(BIA / "Despliegue_Entre_Ambientes" / "plantilla_repo")
    ok(r == 0, "la plantilla del repo pasa su propia validación")

# ---------------------------------------------------------------------------
print("2. aplicar_sql.py")
sql = "CREATE TABLE a (x INT);\nGO\n-- solo comentario\nGO\nCREATE PROCEDURE p AS SELECT 1;\ngo -- fin\n"
ok(aplicar_sql.lotes(sql) == ["CREATE TABLE a (x INT);", "CREATE PROCEDURE p AS SELECT 1;"],
   "separa lotes por GO (mayúsculas o no, con comentario) y descarta lotes vacíos")
ok(aplicar_sql.lotes("SELECT 'GOTO';\nSELECT 2") == ["SELECT 'GOTO';\nSELECT 2"], "no corta por GO dentro de una línea")

with tempfile.TemporaryDirectory() as tmp:
    c = Path(tmp)
    (c / "001_crear.sql").write_text("-- repetible\nIF OBJECT_ID('t') IS NULL CREATE TABLE t (x INT);", encoding="utf-8")
    (c / "002_borrar.sql").write_text("DROP TABLE viejo;", encoding="utf-8")
    (c / "003_comentado.sql").write_text("/* DROP TABLE viejo; */ -- TRUNCATE TABLE x\nSELECT 1;", encoding="utf-8")
    migs, errores = aplicar_sql.leer_migraciones(c)
    ok(any("002_borrar.sql" in e and "DROP TABLE" in e for e in errores), "DROP TABLE sin marca de impacto: error")
    ok(not any("003" in e for e in errores), "DROP o TRUNCATE dentro de comentarios no cuentan")
    (c / "002_borrar.sql").write_text("-- impacto: tabla sin uso desde 2026-09; backup en log.BKP_VIEJO\nDROP TABLE viejo;",
                                      encoding="utf-8")
    (c / "003_otro.sql").write_text("SELECT 1;", encoding="utf-8")
    migs, errores = aplicar_sql.leer_migraciones(c)
    ok(errores == ["Número 003 repetido en sql/"], "con la marca de impacto pasa; número repetido: error")
    (c / "003_otro.sql").unlink()
    migs, errores = aplicar_sql.leer_migraciones(c)
    h = {m.archivo: m.hash for m in migs}

    plan, err = aplicar_sql.planificar(migs, {})
    ok([a for a, _ in plan] == ["APLICAR"] * 3 and not err, "base nueva: aplica todo")
    plan, err = aplicar_sql.planificar(migs, {"001_crear.sql": "otro", "002_borrar.sql": h["002_borrar.sql"]})
    ok([a for a, _ in plan] == ["REAPLICAR", "SALTEAR", "APLICAR"], "repetible cambiado: reaplica; igual: saltea")
    plan, err = aplicar_sql.planificar(migs, {"002_borrar.sql": "otro"})
    ok(len(err) == 1 and "002_borrar.sql" in err[0], "migración no repetible editada después de aplicarse: error")

ddl_mdp = (BIA / "Pipeline_Metadata_Medallion" / "sql" / "01_ddl_control.sql").read_text(encoding="utf-8")
n_go = sum(1 for linea in ddl_mdp.splitlines() if linea.strip().upper() == "GO")
ok(len(aplicar_sql.lotes(ddl_mdp)) >= n_go, f"DDL de control de BIA: {len(aplicar_sql.lotes(ddl_mdp))} lotes")
with tempfile.TemporaryDirectory() as tmp:
    shutil.copy(BIA / "Pipeline_Metadata_Medallion" / "sql" / "01_ddl_control.sql", Path(tmp) / "001_ddl_control.sql")
    shutil.copy(BIA / "Inventario_Workspace" / "sql" / "01_ddl_domain_objects.sql", Path(tmp) / "002_inventario.sql")
    _, errores = aplicar_sql.leer_migraciones(Path(tmp))
    ok(not any("001" in e for e in errores), "el DDL de control de BIA no tiene cambios con impacto")
    ok(any("002_inventario.sql" in e and "SP_RENAME" in e for e in errores),
       "el script del inventario (swap con sp_rename) pide la marca de impacto")


class Cursor:
    def __init__(self, falla_en=None):
        self.ejecutado, self.falla_en = [], falla_en

    def execute(self, sql, *params):
        if self.falla_en and self.falla_en in sql:
            raise Exception("Invalid object name")
        self.ejecutado.append((sql, params))
        return self

    def nextset(self):
        return False


class Conexion:
    def __init__(self, cursor):
        self.c, self.commits, self.rollbacks = cursor, 0, 0

    def cursor(self):
        return self.c

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


m = aplicar_sql.Migracion("001_a.sql", "CREATE TABLE a (x INT);\nGO\nCREATE VIEW v AS SELECT x FROM a;", "h" * 64, False, False)
cur = Cursor()
conn = Conexion(cur)
aplicar_sql.ejecutar(conn, m, "abc123")
ok(conn.commits == 1 and any("INSERT INTO log.MIGRACION" in s for s, _ in cur.ejecutado), "sale bien: commit y registro")
cur = Cursor(falla_en="CREATE VIEW")
conn = Conexion(cur)
try:
    aplicar_sql.ejecutar(conn, m, None)
    fallo = False
except RuntimeError as e:
    fallo = "001_a.sql, lote 2" in str(e)
ok(fallo and conn.rollbacks == 1 and conn.commits == 0
   and not any("INSERT INTO log.MIGRACION" in s for s, _ in cur.ejecutado),
   "falla el lote 2: rollback, sin registro, y el error dice archivo y lote")

# ---------------------------------------------------------------------------
print("3. desplegar_items.py (fabric-cicd simulado)")
llamadas = {}


class FakeWorkspace:
    def __init__(self, **kw):
        llamadas["init"] = kw


falso = types.ModuleType("fabric_cicd")
falso.FabricWorkspace = FakeWorkspace
falso.publish_all_items = lambda ws, **kw: llamadas.setdefault("publish", kw)
falso.unpublish_all_orphan_items = lambda ws, **kw: llamadas.setdefault("unpublish", kw)
real = sys.modules.get("fabric_cicd")
sys.modules["fabric_cicd"] = falso
try:
    args = desplegar_items.argumentos(["--ambiente", "PRD", "--workspace-id", "ws-prd"])
    desplegar_items.desplegar(args, credencial=object())
    ok(llamadas["init"]["environment"] == "PRD" and llamadas["init"]["workspace_id"] == "ws-prd",
       "FabricWorkspace recibe el ambiente (clave de parameter.yml) y el workspace")
    ok("SQLDatabase" not in llamadas["init"]["item_type_in_scope"] and "DataAgent" not in llamadas["init"]["item_type_in_scope"],
       "la base de control y el data agent quedan fuera del alcance por defecto")
    ok("publish" in llamadas and "unpublish" not in llamadas, "sin --borrar-huerfanos no borra nada")
    llamadas.clear()
    args = desplegar_items.argumentos(["--ambiente", "TEST", "--workspace-id", "ws", "--borrar-huerfanos",
                                       "--excluir", "^TMP_"])
    desplegar_items.desplegar(args, credencial=object())
    ok(llamadas.get("unpublish", {}).get("item_name_exclude_regex") == "^TMP_",
       "con --borrar-huerfanos borra respetando --excluir")
    for argv, motivo in [(["--ambiente", "DES", "--workspace-id", "x"], "DES"),
                         (["--ambiente", "PRD"], "sin workspace")]:
        os.environ.pop("FABRIC_WORKSPACE_ID", None)
        try:
            silencio(desplegar_items.argumentos, argv)
            rechazo = False
        except SystemExit:
            rechazo = True
        ok(rechazo, f"rechaza {motivo}")
finally:
    if real is not None:
        sys.modules["fabric_cicd"] = real
    else:
        del sys.modules["fabric_cicd"]

# ---------------------------------------------------------------------------
print("4. Workflows")
wf = PLANTILLA / ".github" / "workflows"
for nombre in ["ci.yml", "desplegar.yml", "_desplegar_ambiente.yml"]:
    texto = (wf / nombre).read_text(encoding="utf-8")
    datos = yaml.safe_load(texto)
    ok(isinstance(datos.get("jobs"), dict), f"{nombre}: YAML válido con jobs")
    for script in ["validar.py", "aplicar_sql.py", "desplegar_items.py"]:
        if script in texto:
            ok((PLANTILLA / "deploy" / script).is_file(), f"{nombre} llama a deploy/{script}, que existe")
dep = yaml.safe_load((wf / "desplegar.yml").read_text(encoding="utf-8"))
ok(dep["jobs"]["prd"]["needs"] == "test", "PRD corre solo después de TEST")
amb = yaml.safe_load((wf / "_desplegar_ambiente.yml").read_text(encoding="utf-8"))
ok(amb["jobs"]["desplegar"]["environment"] == "${{ inputs.ambiente }}",
   "cada ambiente usa su environment de GitHub (variables y aprobación)")
ok(dep.get("permissions", {}).get("id-token") == "write", "OIDC habilitado: sin secretos de Azure en GitHub")

print()
if FALLAS:
    print(f"{len(FALLAS)} pruebas fallaron")
    sys.exit(1)
print("Todo OK")
