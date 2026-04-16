"""
powerbi/deploy.py
──────────────────
Despliega las vistas SQL necesarias para Power BI en los nodos
SQL Server (Beijing y Ucrania).

Uso:
    python powerbi/deploy.py
    python powerbi/deploy.py --node beijing
    python powerbi/deploy.py --node ukraine
"""
import argparse
import sys
from pathlib import Path

try:
    import pyodbc
except ImportError:
    print("ERROR: instala pyodbc →  pip install pyodbc")
    sys.exit(1)

SQL_FILE = Path(__file__).parent / "setup_views.sql"

NODES = {
    "beijing": ("localhost", 1433),
    "ukraine": ("localhost", 1434),
}

PASSWORD = "RPA_StrongPass123!"
DATABASE = "rpa_db"
USER     = "sa"


def conn_str(host: str, port: int) -> str:
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host},{port};"
        f"DATABASE={DATABASE};"
        f"UID={USER};PWD={PASSWORD};"
        "TrustServerCertificate=yes;"
    )


def deploy(node: str, host: str, port: int) -> None:
    print(f"\n[{node}] Conectando a {host}:{port}...")
    try:
        conn   = pyodbc.connect(conn_str(host, port), autocommit=True)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[{node}] ERROR de conexión: {e}")
        return

    sql = SQL_FILE.read_text(encoding="utf-8")

    # Dividir por GO (separador de lotes T-SQL)
    batches = [b.strip() for b in sql.split("\nGO") if b.strip()]

    ok = 0
    for batch in batches:
        if not batch or batch.startswith("--"):
            continue
        try:
            cursor.execute(batch)
            ok += 1
        except Exception as e:
            if "already an object" in str(e):
                pass  # Vista ya existe, ignorar
            else:
                print(f"  WARN: {str(e)[:120]}")

    conn.close()
    print(f"[{node}] ✓ {ok} lotes ejecutados. Vistas listas.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node", choices=["beijing", "ukraine", "all"],
                        default="all", help="Nodo a actualizar (default: all)")
    args = parser.parse_args()

    targets = NODES.items() if args.node == "all" else [(args.node, NODES[args.node])]

    for node, (host, port) in targets:
        deploy(node, host, port)

    print("\nListo. Abre Power BI Desktop y conecta a localhost,1433 (base: rpa_db).")


if __name__ == "__main__":
    main()
