"""Despliega los items de workspace/ a un workspace de Fabric con fabric-cicd.

Publica lo que está en el repo y reemplaza los valores de DES por los del ambiente
según workspace/parameter.yml. Por defecto NO borra nada del workspace destino.

Uso:
  python deploy/desplegar_items.py --ambiente TEST
  python deploy/desplegar_items.py --ambiente PRD --borrar-huerfanos

Identidad: la de az login / azure/login (AzureCliCredential). El workspace destino
sale de FABRIC_WORKSPACE_ID (variable del environment de GitHub).
"""
import argparse
import os
import sys

AMBIENTES = ["DES", "TEST", "PRD"]

# Orden y alcance por defecto. Fuera de alcance a propósito:
#   SQLDatabase: la base de control se crea una vez por ambiente y su esquema lo
#                manejan las migraciones de sql/ (aplicar_sql.py).
#   DataAgent:   sigue su propio ciclo de evaluación (Agente_Datos_Fabric, NB_AGT_03).
TIPOS_POR_DEFECTO = [
    "VariableLibrary", "Lakehouse", "Environment", "Notebook",
    "SemanticModel", "Report", "DataPipeline",
]


def argumentos(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ambiente", required=True, choices=AMBIENTES)
    ap.add_argument("--workspace-id", default=os.environ.get("FABRIC_WORKSPACE_ID"))
    ap.add_argument("--repo", default="workspace", help="Carpeta con los items y parameter.yml")
    ap.add_argument("--tipos", default=",".join(TIPOS_POR_DEFECTO),
                    help="Tipos de item a desplegar, separados por coma")
    ap.add_argument("--excluir", default=None,
                    help="Regex de nombres de item que no se despliegan ni se borran (ej. '^(SANDBOX|TMP)_')")
    ap.add_argument("--borrar-huerfanos", action="store_true",
                    help="Borra del workspace los items que ya no están en el repo. Lakehouses y bases "
                         "nunca se borran: fabric-cicd lo exige con flags que este script no activa")
    args = ap.parse_args(argv)
    if not args.workspace_id:
        ap.error("falta --workspace-id o la variable FABRIC_WORKSPACE_ID")
    if args.ambiente == "DES":
        ap.error("DES se actualiza desde la integración Git del workspace, no con este script")
    args.tipos = [t.strip() for t in args.tipos.split(",") if t.strip()]
    return args


def desplegar(args, credencial=None):
    from fabric_cicd import FabricWorkspace, publish_all_items, unpublish_all_orphan_items

    if credencial is None:
        from azure.identity import AzureCliCredential
        credencial = AzureCliCredential()

    ws = FabricWorkspace(
        workspace_id=args.workspace_id,
        environment=args.ambiente,          # clave de replace_value en parameter.yml
        repository_directory=args.repo,
        item_type_in_scope=args.tipos,
        token_credential=credencial,
    )
    publish_all_items(ws, item_name_exclude_regex=args.excluir)
    if args.borrar_huerfanos:
        unpublish_all_orphan_items(ws, item_name_exclude_regex=args.excluir or "^$")
    return ws


def main(argv=None) -> int:
    args = argumentos(argv)
    print(f"Desplegando {args.repo} -> workspace {args.workspace_id} ({args.ambiente})")
    print("Tipos:", ", ".join(args.tipos), "| borrar huérfanos:", "sí" if args.borrar_huerfanos else "no")
    desplegar(args)
    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
