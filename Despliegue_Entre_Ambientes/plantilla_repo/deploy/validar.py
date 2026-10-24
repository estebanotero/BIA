"""Validaciones que corren en cada PR, sin conectarse a Fabric ni a la base.

1. parameter.yml es válido para cada ambiente (validador de fabric-cicd).
2. Los GUID que aparecen en los items (workspace, lakehouse, conexiones) están
   parametrizados. Un GUID de DES sin reemplazo hace que PRD lea datos de DES.
3. No hay secretos en el repo (claves, connection strings con password, tokens).
4. Las migraciones de sql/ tienen nombre válido, número único y marca de impacto
   donde corresponde (mismas reglas que aplicar_sql.py).

Uso:
  python deploy/validar.py                      # TEST y PRD
  python deploy/validar.py --ambientes PRD --estricto
"""
import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from aplicar_sql import leer_migraciones  # noqa: E402
from desplegar_items import TIPOS_POR_DEFECTO  # noqa: E402

PATRON_GUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
GUID_CERO = "00000000-0000-0000-0000-000000000000"

PATRONES_SECRETO = {
    "password en connection string": re.compile(r"(?i)\b(password|pwd)\s*=\s*[^;<\s\"'{][^;\"']{3,}"),
    "AccountKey de storage": re.compile(r"(?i)AccountKey\s*=\s*[A-Za-z0-9+/=]{20,}"),
    "SAS token": re.compile(r"(?i)[?&]sig=[A-Za-z0-9%+/=]{20,}"),
    "API key de Anthropic": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "client secret": re.compile(r"(?i)client_?secret\s*[=:]\s*[\"'][^\"'<>{}]{8,}[\"']"),
    "clave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
EXTENSIONES_TEXTO = {".py", ".sql", ".json", ".yml", ".yaml", ".md", ".tmdl", ".pbir", ".txt", ".csv", ".ipynb", ".platform"}


def archivos_texto(raiz: Path):
    for p in raiz.rglob("*"):
        if p.is_file() and p.suffix.lower() in EXTENSIONES_TEXTO and ".git" not in p.parts:
            yield p


def guids_sin_parametrizar(repo: Path, parametro: Path) -> dict[str, list[str]]:
    """GUID -> archivos donde aparece, para los GUID que no son find_value de parameter.yml."""
    cubiertos = set()
    if parametro.is_file():
        datos = yaml.safe_load(parametro.read_text(encoding="utf-8")) or {}
        for r in datos.get("find_replace", []) or []:
            cubiertos |= {g.lower() for g in PATRON_GUID.findall(str(r.get("find_value", "")))}
    hallados: dict[str, list[str]] = {}
    for p in archivos_texto(repo):
        if p.name == ".platform" or p == parametro:
            continue        # .platform tiene el logicalId del item: fabric-cicd lo resuelve solo
        for g in {g.lower() for g in PATRON_GUID.findall(p.read_text(encoding="utf-8", errors="ignore"))}:
            if g not in cubiertos and g != GUID_CERO:
                hallados.setdefault(g, []).append(str(p.relative_to(repo)))
    return hallados


def secretos(raiz: Path) -> list[str]:
    out = []
    for p in archivos_texto(raiz):
        texto = p.read_text(encoding="utf-8", errors="ignore")
        for nombre, patron in PATRONES_SECRETO.items():
            for m in patron.finditer(texto):
                linea = texto.count("\n", 0, m.start()) + 1
                out.append(f"{p.relative_to(raiz)}:{linea}: posible {nombre}")
    return out


def validar_parametros(repo: Path, ambientes: list[str], tipos: list[str]) -> list[str]:
    from fabric_cicd._parameter._utils import validate_parameter_file   # API interna de fabric-cicd 1.4.0

    errores = []
    for amb in ambientes:
        if not validate_parameter_file(repository_directory=str(repo), item_type_in_scope=tipos, environment=amb):
            errores.append(f"parameter.yml no es válido para {amb} (ver el log de fabric-cicd arriba)")
    return errores


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raiz", default=".", help="Raíz del repo de la implementación")
    ap.add_argument("--ambientes", default="TEST,PRD")
    ap.add_argument("--estricto", action="store_true", help="GUID sin parametrizar es error, no advertencia")
    args = ap.parse_args(argv)

    raiz = Path(args.raiz)
    repo, sql = raiz / "workspace", raiz / "sql"
    errores, advertencias = [], []

    if (repo / "parameter.yml").is_file():
        errores += validar_parametros(repo, [a.strip() for a in args.ambientes.split(",")], TIPOS_POR_DEFECTO)
    else:
        advertencias.append("workspace/parameter.yml no existe: nada se reemplaza entre ambientes")

    for g, donde in sorted(guids_sin_parametrizar(repo, repo / "parameter.yml").items()):
        msg = f"GUID {g} sin parametrizar en {', '.join(sorted(donde)[:3])}"
        (errores if args.estricto else advertencias).append(msg)

    errores += secretos(raiz)
    if sql.is_dir():
        errores += leer_migraciones(sql)[1]

    for a in advertencias:
        print("ADVERTENCIA", a)
    for e in errores:
        print("ERROR      ", e)
    print(f"{len(errores)} errores, {len(advertencias)} advertencias")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
