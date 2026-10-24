"""Aplica las migraciones de sql/ a la base de control de un ambiente.

Reglas:
  - Los archivos se aplican en orden de nombre: NNN_descripcion.sql (001, 002, ...).
  - Cada archivo aplicado queda en log.MIGRACION con su hash. Uno ya aplicado no se
    vuelve a correr, salvo que tenga la marca "-- repetible" (scripts idempotentes,
    como el DDL de control de BIA).
  - Un archivo ya aplicado que cambió y no es repetible es un error: las migraciones
    no se editan, se agrega un archivo nuevo.
  - DROP TABLE / SCHEMA / DATABASE, TRUNCATE TABLE y sp_rename son cambios con impacto:
    el archivo necesita la marca "-- impacto: <motivo y vuelta atrás>" o no se aplica.
  - Cada archivo corre en una transacción: si falla, no queda a medias ni se registra.

Uso:
  python deploy/aplicar_sql.py --ambiente TEST                 # aplica
  python deploy/aplicar_sql.py --ambiente TEST --solo-plan     # muestra qué aplicaría

Conexión: SQL_SERVER y SQL_DATABASE (variables del environment de GitHub) y el token
de la identidad con la que se hizo az login / azure/login. Ninguna clave en el repo.
"""
import argparse
import hashlib
import os
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

PATRON_ARCHIVO = re.compile(r"^\d{3}_[\w\-]+\.sql$")
PATRON_GO = re.compile(r"^\s*GO\s*(?:--.*)?$", re.IGNORECASE | re.MULTILINE)
PATRON_IMPACTO = re.compile(
    r"\bDROP\s+(TABLE|SCHEMA|DATABASE)\b|\bTRUNCATE\s+TABLE\b|\bsp_rename\b", re.IGNORECASE)
MARCA_REPETIBLE = re.compile(r"^\s*--\s*repetible\b", re.IGNORECASE | re.MULTILINE)
MARCA_IMPACTO = re.compile(r"^\s*--\s*impacto:\s*\S", re.IGNORECASE | re.MULTILINE)

# Scope del token para SQL database de Fabric / Azure SQL [verificar en la doc vigente]
SCOPE_SQL = "https://database.windows.net/.default"
SQL_COPT_SS_ACCESS_TOKEN = 1256

DDL_CONTROL = """
IF SCHEMA_ID('log') IS NULL EXEC('CREATE SCHEMA log');
IF OBJECT_ID('log.MIGRACION') IS NULL
CREATE TABLE log.MIGRACION (
    ARCHIVO      VARCHAR(200)  NOT NULL CONSTRAINT PK_MIGRACION PRIMARY KEY,
    HASH_SHA256  CHAR(64)      NOT NULL,
    APLICADO_UTC DATETIME2(0)  NOT NULL CONSTRAINT DF_MIGRACION_APLICADO DEFAULT SYSUTCDATETIME(),
    APLICADO_POR NVARCHAR(200) NOT NULL CONSTRAINT DF_MIGRACION_POR DEFAULT SUSER_SNAME(),
    COMMIT_SHA   VARCHAR(40)   NULL
);
"""


@dataclass
class Migracion:
    archivo: str
    texto: str
    hash: str
    repetible: bool
    impacto_marcado: bool


def sin_comentarios(sql: str) -> str:
    """Saca comentarios /* */ y -- para buscar palabras peligrosas solo en código."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", " ", sql)


def lotes(sql: str) -> list[str]:
    """Separa por líneas GO, como sqlcmd. GO no es T-SQL: el servidor no lo entiende."""
    partes = PATRON_GO.split(sql)
    return [p.strip() for p in partes if p and sin_comentarios(p).strip()]


def leer_migraciones(carpeta: Path) -> tuple[list[Migracion], list[str]]:
    migraciones, errores = [], []
    for p in sorted(carpeta.glob("*.sql")):
        if not PATRON_ARCHIVO.match(p.name):
            errores.append(f"{p.name}: el nombre tiene que ser NNN_descripcion.sql")
            continue
        texto = p.read_text(encoding="utf-8-sig")
        m = Migracion(
            archivo=p.name,
            texto=texto,
            hash=hashlib.sha256(texto.replace("\r\n", "\n").encode("utf-8")).hexdigest(),
            repetible=bool(MARCA_REPETIBLE.search(texto)),
            impacto_marcado=bool(MARCA_IMPACTO.search(texto)),
        )
        peligrosas = sorted({x.group(0).upper() for x in PATRON_IMPACTO.finditer(sin_comentarios(texto))})
        if peligrosas and not m.impacto_marcado:
            errores.append(f"{p.name}: tiene {', '.join(peligrosas)} sin la marca '-- impacto: <motivo y vuelta atrás>'")
        migraciones.append(m)
    numeros = [m.archivo[:3] for m in migraciones]
    for n in sorted({n for n in numeros if numeros.count(n) > 1}):
        errores.append(f"Número {n} repetido en sql/")
    return migraciones, errores


def planificar(migraciones: list[Migracion], aplicadas: dict[str, str]) -> tuple[list[tuple[str, Migracion]], list[str]]:
    """Devuelve [(accion, migracion)] con accion en APLICAR, REAPLICAR, SALTEAR, y los errores."""
    plan, errores = [], []
    for m in migraciones:
        previo = aplicadas.get(m.archivo)
        if previo is None:
            plan.append(("APLICAR", m))
        elif previo == m.hash:
            plan.append(("SALTEAR", m))
        elif m.repetible:
            plan.append(("REAPLICAR", m))
        else:
            errores.append(f"{m.archivo}: ya se aplicó con otro contenido. No edites migraciones aplicadas: "
                           "agregá un archivo nuevo, o marcalo '-- repetible' si es idempotente.")
    return plan, errores


def conectar(servidor: str, base: str):
    import pyodbc
    from azure.identity import AzureCliCredential

    token = AzureCliCredential().get_token(SCOPE_SQL).token.encode("utf-16-le")
    token_struct = struct.pack(f"<I{len(token)}s", len(token), token)
    cadena = (f"Driver={{ODBC Driver 18 for SQL Server}};Server=tcp:{servidor},1433;Database={base};"
              "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=60")
    return pyodbc.connect(cadena, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}, autocommit=False)


def aplicadas_en_base(conn, crear: bool) -> dict[str, str]:
    cur = conn.cursor()
    if not crear and cur.execute("SELECT OBJECT_ID('log.MIGRACION')").fetchone()[0] is None:
        return {}                         # --solo-plan sobre una base nueva: no crea nada
    for lote in lotes(DDL_CONTROL):
        cur.execute(lote)
    conn.commit()
    return {a: h for a, h in cur.execute("SELECT ARCHIVO, HASH_SHA256 FROM log.MIGRACION").fetchall()}


def ejecutar(conn, m: Migracion, commit_sha: str | None) -> None:
    cur = conn.cursor()
    try:
        for i, lote in enumerate(lotes(m.texto), start=1):
            try:
                cur.execute(lote)
                while cur.nextset():      # consume resultados de SELECT de verificación
                    pass
            except Exception as e:
                raise RuntimeError(f"{m.archivo}, lote {i}: {e}") from e
        cur.execute("DELETE FROM log.MIGRACION WHERE ARCHIVO = ?", m.archivo)
        cur.execute("INSERT INTO log.MIGRACION (ARCHIVO, HASH_SHA256, COMMIT_SHA) VALUES (?, ?, ?)",
                    m.archivo, m.hash, commit_sha)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ambiente", required=True, help="DES, TEST o PRD (solo para el log)")
    ap.add_argument("--carpeta", default="sql")
    ap.add_argument("--servidor", default=os.environ.get("SQL_SERVER"))
    ap.add_argument("--base", default=os.environ.get("SQL_DATABASE"))
    ap.add_argument("--solo-plan", action="store_true", help="No ejecuta nada: muestra el plan")
    args = ap.parse_args(argv)

    migraciones, errores = leer_migraciones(Path(args.carpeta))
    if errores:
        print("Errores en sql/:\n- " + "\n- ".join(errores))
        return 1
    if not migraciones:
        print("No hay migraciones en", args.carpeta)
        return 0
    if not args.servidor or not args.base:
        print("Faltan SQL_SERVER y SQL_DATABASE (variables del environment de GitHub).")
        return 1

    conn = conectar(args.servidor, args.base)
    plan, errores = planificar(migraciones, aplicadas_en_base(conn, crear=not args.solo_plan))
    if errores:
        print("No se aplica nada:\n- " + "\n- ".join(errores))
        return 1

    print(f"Ambiente {args.ambiente} · {args.servidor}/{args.base}")
    for accion, m in plan:
        print(f"  {accion:<9} {m.archivo}{'  (impacto)' if m.impacto_marcado else ''}")
    if args.solo_plan:
        return 0
    for accion, m in plan:
        if accion != "SALTEAR":
            ejecutar(conn, m, os.environ.get("GITHUB_SHA"))
            print(f"  OK {m.archivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
