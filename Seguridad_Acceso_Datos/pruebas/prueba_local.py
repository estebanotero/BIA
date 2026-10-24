"""Prueba local del caso Seguridad_Acceso_Datos, sin Fabric.

Qué prueba:
  1. Detección de PII: por IS_PII de la metadata, por nombre igual a una columna IS_PII,
     por patrón de nombre, y excepciones revisadas.
  2. Validación de la matriz de accesos y de RLS (plantillas incluidas): personas en lugar
     de grupos, roles y objetos que no existen, [dato a confirmar], dos roles de workspace.
  3. Permisos deseados: tabla completa, por columnas sin PII (CLS), objeto omitido si todo
     es PII, y la fila más amplia gana cuando dos filas cubren el mismo objeto.
  4. Scripts generados: GRANT/REVOKE, RLS en el endpoint (con '*' = ve todo) y roles TMDL.
  5. Revisión: roles del workspace contra la matriz, PII en gold y agente, permisos SQL
     de más, PII expuesta, permisos por esquema y faltantes.
  6. Que los dos notebooks tengan la misma celda de funciones y la celda de parámetros marcada.

No prueba el SQL analytics endpoint, sempy_labs ni que los scripts corran en Fabric.

Requisitos: pip install pandas
    python prueba_local.py
"""
import json
import os

import pandas as pd

AQUI = os.path.dirname(os.path.abspath(__file__))
CASO = os.path.join(AQUI, "..")
PLANTILLAS = os.path.join(CASO, "skill", "proponer-accesos-datos", "plantillas")


def celdas(nb):
    data = json.load(open(os.path.join(CASO, "notebooks", f"{nb}.ipynb"), encoding="utf-8"))
    return data["cells"]


def funciones_de(nb):
    return next("".join(c["source"]) for c in celdas(nb)
                if c["cell_type"] == "code" and "".join(c["source"]).startswith("# --- funciones"))


g = {}
exec(funciones_de("NB_SEG_01_relevar_accesos"), g)
f = type("F", (), g)


def ok(msg):
    print("  OK ", msg)


# Catálogo del SQL analytics endpoint armado a mano
filas = [
    ("bronze", "erp_clientes", "BASE TABLE", ["Id", "Nombre", "EMail", "Zona"]),
    ("silver", "clientes", "BASE TABLE", ["cliente_id", "razon_social", "email", "cuit", "zona"]),
    ("silver", "pedidos", "BASE TABLE", ["pedido_id", "cliente_id", "importe", "fecha"]),
    ("silver", "contactos", "BASE TABLE", ["email", "telefono"]),
    ("gold", "dim_cliente", "BASE TABLE", ["cliente_id", "razon_social", "zona", "email_contacto"]),
    ("gold", "dim_producto", "BASE TABLE", ["producto_id", "nombre_producto"]),
    ("gold", "fact_ventas", "BASE TABLE", ["cliente_id", "producto_id", "zona", "importe"]),
    ("agente", "ventas", "VIEW", ["zona", "mes", "importe"]),
    ("agente", "clientes", "VIEW", ["cliente_id", "cuit"]),
]
catalogo = pd.DataFrame([{"TABLE_SCHEMA": s, "TABLE_NAME": t, "TABLE_TYPE": ty, "COLUMN_NAME": c}
                         for s, t, ty, cols in filas for c in cols])
pii_meta = pd.DataFrame({"SILVER_TABLE": ["silver.clientes", "silver.clientes"], "TARGET_COLUMN": ["email", "cuit"]})

# ---------------------------------------------------------------------------
print("1. PII")
cat = f.columnas_pii(catalogo, pii_meta, f.PATRONES_POR_DEFECTO, ["gold.dim_producto.nombre_producto"])
pii = {(s, t, c): m for s, t, c, m, p in zip(cat["TABLE_SCHEMA"], cat["TABLE_NAME"], cat["COLUMN_NAME"],
                                             cat["pii_motivo"], cat["pii"]) if p}
assert pii[("silver", "clientes", "cuit")] == "IS_PII en meta.ENTITY_COLUMN"
assert pii[("agente", "clientes", "cuit")] == "mismo nombre que una columna IS_PII de silver"
assert pii[("bronze", "erp_clientes", "EMail")] == "mismo nombre que una columna IS_PII de silver"
assert "nombre" in pii[("bronze", "erp_clientes", "Nombre")]
assert ("gold", "dim_cliente", "email_contacto") in pii
assert ("gold", "dim_producto", "nombre_producto") not in pii
assert ("silver", "clientes", "razon_social") not in pii and ("gold", "fact_ventas", "zona") not in pii
ok(f"{len(pii)} columnas PII: metadata, mismo nombre, patrón, y la excepción revisada queda afuera")

# ---------------------------------------------------------------------------
print("2. Validación de matrices")
plantilla = pd.read_csv(os.path.join(PLANTILLAS, "matriz_accesos.csv"), dtype=str, keep_default_na=False)
ap, probs = f.validar_matriz(plantilla, catalogo)
assert len(ap) == 0 and probs == [], probs                       # nada aprobado en la plantilla
todo = plantilla.assign(aprobada="si")
ap, probs = f.validar_matriz(todo, catalogo)
assert probs == [], probs
ok(f"plantilla válida ({len(todo)} filas) y sin nada aprobado por defecto")

mala = pd.DataFrame([
    {"grupo": "juan@empresa.com", "tipo_permiso": "LECTURA", "alcance": "gold", "ve_pii": "no", "aprobada": "si", "notas": ""},
    {"grupo": "grp-x", "tipo_permiso": "WORKSPACE", "alcance": "Owner", "ve_pii": "", "aprobada": "si", "notas": ""},
    {"grupo": "grp-x", "tipo_permiso": "WORKSPACE", "alcance": "Viewer", "ve_pii": "", "aprobada": "si", "notas": ""},
    {"grupo": "grp-y", "tipo_permiso": "LECTURA", "alcance": "platino", "ve_pii": "no", "aprobada": "si", "notas": ""},
    {"grupo": "grp-z", "tipo_permiso": "ESCRITURA", "alcance": "gold", "ve_pii": "no", "aprobada": "si", "notas": ""},
    {"grupo": "grp-w", "tipo_permiso": "LECTURA", "alcance": "gold", "ve_pii": "[dato a confirmar]", "aprobada": "si", "notas": ""},
])
_, probs = f.validar_matriz(mala, catalogo)
texto = " | ".join(probs)
for esperado in ("parece una persona", "'Owner' no válido", "más de un rol de workspace", "'platino' no existe",
                 "'ESCRITURA' no válido", "[dato a confirmar]"):
    assert esperado in texto, (esperado, texto)
ok(f"{len(probs)} problemas detectados en una matriz mala")

rls_pl = pd.read_csv(os.path.join(PLANTILLAS, "matriz_rls.csv"), dtype=str, keep_default_na=False)
rls_ap, probs = f.validar_rls(rls_pl.assign(aprobada="si"), catalogo)
assert probs == [] and len(rls_ap) == 4, probs
_, probs = f.validar_rls(pd.DataFrame([{"grupo": "g", "tabla_sql": "gold.fact_ventas", "tabla_modelo": "",
                                         "columna": "region", "valores": "", "aprobada": "si"}]), catalogo)
assert any("no existe" in p for p in probs) and any("sin valores" in p for p in probs)
ok("matriz RLS: plantilla válida, columna inexistente y valores vacíos")

# ---------------------------------------------------------------------------
print("3. Permisos deseados")
des = f.permisos_deseados(ap, cat)
fila = lambda gr, s, o: des[(des["grupo"] == gr) & (des["esquema"] == s) & (des["objeto"] == o)].iloc[0]
assert fila("grp-fabric-ingenieria", "silver", "clientes")["columnas"] is None          # ve PII
an = fila("grp-fabric-analistas", "silver", "clientes")["columnas"]
assert an == ["cliente_id", "razon_social", "zona"], an                               # CLS
assert fila("grp-fabric-analistas", "silver", "pedidos")["columnas"] is None           # sin PII: completa
assert fila("grp-fabric-analistas", "silver", "contactos")["omitido"]                  # todo PII
assert fila("grp-negocio-ventas-norte", "agente", "clientes")["columnas"] == ["cliente_id"]
assert not (des["esquema"] == "bronze").any() or set(des[des["esquema"] == "bronze"]["grupo"]) == {"grp-fabric-ingenieria"}
amplia = pd.DataFrame([
    {"grupo": "g", "tipo_permiso": "LECTURA", "alcance": "silver", "ve_pii": "no", "aprobada": "si", "notas": ""},
    {"grupo": "g", "tipo_permiso": "LECTURA", "alcance": "silver.clientes", "ve_pii": "si", "aprobada": "si", "notas": ""},
])
d2 = f.permisos_deseados(amplia, cat)
assert d2[d2["objeto"] == "clientes"].iloc[0]["columnas"] is None and len(d2[d2["objeto"] == "clientes"]) == 1
ok("tabla completa, CLS sin PII, omitido si todo es PII, y gana la fila más amplia")

# ---------------------------------------------------------------------------
print("4. Scripts")
sql = f.script_grants(des, "DES", "20261024_2100")
assert "GRANT SELECT ON [silver].[clientes] TO [grp-fabric-ingenieria];" in sql
assert "GRANT SELECT ON [silver].[clientes] ([cliente_id], [razon_social], [zona]) TO [grp-fabric-analistas];" in sql
assert "-- grp-fabric-analistas: silver.contactos omitido" in sql
assert "[email]" not in sql.split("*/", 1)[1] and "[cuit]" not in sql.split("*/", 1)[1]
atras = f.script_vuelta_atras_grants(des, "DES", "x")
assert atras.count("REVOKE") == sql.count("GRANT SELECT")
assert "contactos] FROM [grp-fabric-analistas]" not in atras
ok("GRANT por objeto y por columnas, sin nombrar columnas PII; un REVOKE por GRANT")

rls = f.script_rls_sql(rls_ap, "DES", "x")
assert "CREATE OR ALTER FUNCTION seg.fn_rls_gold_fact_ventas" in rls
assert "(IS_MEMBER('grp-negocio-ventas-sur') = 1 AND @valor IN ('Sur', 'Cuyo'))" in rls
assert "IS_MEMBER('grp-fabric-ingenieria') = 1\n" in rls or "IS_MEMBER('grp-fabric-ingenieria') = 1;" in rls
assert "ADD FILTER PREDICATE seg.fn_rls_gold_fact_ventas([zona]) ON [gold].[fact_ventas]" in rls
assert "DROP SECURITY POLICY seg.pol_rls_gold_fact_ventas" in rls
tmdl = f.roles_tmdl(rls_ap)
assert set(tmdl) == {"grp-negocio-ventas-norte.tmdl", "grp-negocio-ventas-sur.tmdl"}, set(tmdl)
assert "\ttablePermission 'Ventas' = 'Ventas'[zona] IN {\"Sur\", \"Cuyo\"}" in tmdl["grp-negocio-ventas-sur.tmdl"]
assert tmdl["grp-negocio-ventas-norte.tmdl"].startswith("role 'grp-negocio-ventas-norte'\n\tmodelPermission: read")
num = f.roles_tmdl(pd.DataFrame([{"grupo": "g", "tabla_sql": "", "tabla_modelo": "T", "columna": "anio",
                                  "valores": "2025,2026", "aprobada": "si"}]))
assert "IN {2025, 2026}" in num["g.tmdl"]
ok("RLS en el endpoint con '*' = ve todo, vuelta atrás, y roles TMDL con texto y números")

# ---------------------------------------------------------------------------
print("5. Revisión")
roles_ws = pd.DataFrame([
    {"User Name": "grp-fabric-plataforma", "Type": "Group", "Role Name": "Admin"},
    {"User Name": "grp-fabric-ingenieria", "Type": "Group", "Role Name": "Member"},       # matriz: Contributor
    {"User Name": "Ana Pérez", "Type": "User", "Role Name": "Admin"},
    {"User Name": "Pedro Gómez", "Type": "User", "Role Name": "Admin"},
    {"User Name": "grp-viejo", "Type": "Group", "Role Name": "Member"},
    {"User Name": "sp-despliegue", "Type": "ServicePrincipal", "Role Name": "Contributor"},
])
h = f.revisar_workspace(roles_ws, ap, max_admins=2, identidades_tecnicas=["sp-despliegue"])
cod = {(x["codigo"], x["objeto"]): x["severidad"] for x in h}
assert cod[("SEG_WS_DEMASIADOS_ADMIN", "workspace")] == "MEDIA"
assert cod[("SEG_WS_ROL_DE_MAS", "grp-fabric-ingenieria")] == "ALTA"
assert cod[("SEG_WS_USUARIO_INDIVIDUAL", "Ana Pérez")] == "MEDIA"
assert cod[("SEG_WS_FUERA_DE_MATRIZ", "grp-viejo")] == "ALTA"
assert not any(o == "sp-despliegue" for _, o in cod)
assert not any(c == "SEG_WS_FALTA_ROL" for c, _ in cod)
ok("roles del workspace: admins, rol de más, personas sueltas, fuera de matriz; identidad técnica ignorada")

hp = f.revisar_pii(cat)
cod = {(x["codigo"], x["objeto"]): x["severidad"] for x in hp}
assert cod == {("SEG_PII_EN_AGENTE", "agente.clientes"): "ALTA", ("SEG_PII_EN_GOLD", "gold.dim_cliente"): "MEDIA"}, cod
ok("PII en agente (ALTA) y en gold (MEDIA)")

reales = pd.DataFrame([
    {"GRANTEE": "grp-fabric-analistas", "SCHEMA_NAME": "silver", "OBJECT_NAME": "clientes", "COLUMN_NAME": None, "PERMISSION_NAME": "SELECT", "STATE_DESC": "GRANT"},
    {"GRANTEE": "grp-fabric-analistas", "SCHEMA_NAME": "silver", "OBJECT_NAME": "pedidos", "COLUMN_NAME": None, "PERMISSION_NAME": "SELECT", "STATE_DESC": "GRANT"},
    {"GRANTEE": "grp-viejo", "SCHEMA_NAME": "gold", "OBJECT_NAME": "fact_ventas", "COLUMN_NAME": None, "PERMISSION_NAME": "SELECT", "STATE_DESC": "GRANT"},
    {"GRANTEE": "grp-fabric-analistas", "SCHEMA_NAME": "gold", "OBJECT_NAME": "*", "COLUMN_NAME": None, "PERMISSION_NAME": "SELECT", "STATE_DESC": "GRANT"},
    {"GRANTEE": "grp-x", "SCHEMA_NAME": "gold", "OBJECT_NAME": "fact_ventas", "COLUMN_NAME": None, "PERMISSION_NAME": "SELECT", "STATE_DESC": "DENY"},
])
hs = f.revisar_permisos_sql(reales, des)
cod = {(x["codigo"], x["objeto"]) for x in hs}
assert ("SEG_SQL_PII_EXPUESTA", "grp-fabric-analistas → silver.clientes") in cod
assert ("SEG_SQL_PERMISO_DE_MAS", "grp-viejo → gold.fact_ventas") in cod
assert ("SEG_SQL_PERMISO_ESQUEMA", "grp-fabric-analistas → gold") in cod
assert ("SEG_SQL_PERMISO_FALTANTE", "grp-fabric-ingenieria → bronze.erp_clientes") in cod
assert not any(o.startswith("grp-x") for _, o in cod)                    # un DENY no es un acceso
por_col = pd.DataFrame([{"GRANTEE": "grp-negocio-ventas-norte", "SCHEMA_NAME": "agente", "OBJECT_NAME": "clientes",
                         "COLUMN_NAME": c, "PERMISSION_NAME": "SELECT", "STATE_DESC": "GRANT"} for c in ("cliente_id", "cuit")])
hc = f.revisar_permisos_sql(por_col, des)
assert any(x["codigo"] == "SEG_SQL_PII_EXPUESTA" and "cuit" in x["detalle"] for x in hc), hc
assert not any(o == "grp-fabric-analistas → silver.pedidos" for _, o in cod)
todos = f.ordenar(h + hp + hs)
assert [x["severidad"] for x in todos] == sorted([x["severidad"] for x in todos], key=["ALTA", "MEDIA", "BAJA"].index)
ok(f"permisos SQL: PII expuesta, de más, por esquema y faltantes; {len(todos)} hallazgos ordenados")

# ---------------------------------------------------------------------------
print("6. Notebooks")
assert funciones_de("NB_SEG_01_relevar_accesos") == funciones_de("NB_SEG_02_generar_scripts")
for nb in ("NB_SEG_01_relevar_accesos", "NB_SEG_02_generar_scripts"):
    primera = next(c for c in celdas(nb) if c["cell_type"] == "code")
    assert primera["metadata"].get("tags") == ["parameters"], nb
patrones = json.load(open(os.path.join(CASO, "..", "Comun", "patrones_sensibles.json"), encoding="utf-8"))["patrones"]
assert patrones == f.PATRONES_POR_DEFECTO, "PATRONES_POR_DEFECTO distinto de Comun/patrones_sensibles.json"
ok("misma celda de funciones, parámetros marcados y patrones iguales a Comun/")

print("Todo OK")
