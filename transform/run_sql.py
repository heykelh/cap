"""Exécute les fichiers SQL d'une couche et écrit chaque résultat dans une table BigQuery.

Chaque fichier transform/sql/<couche>/NN_<table>.sql produit la table cap_<couche>.<table>.
Les fichiers sont exécutés dans l'ordre de leur numéro. Chaque table est entièrement
remplacée (compatible sandbox, pas de DML).

Usage :
  python transform/run_sql.py silver
  python transform/run_sql.py gold
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))

from bq import ensure_dataset, get_client  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent / "sql"


def run_layer(layer: str) -> int:
    from google.cloud import bigquery

    files = sorted((SQL_DIR / layer).glob("*.sql"))
    if not files:
        print(f"Aucun fichier SQL dans {SQL_DIR / layer}")
        return 1

    client = get_client()
    dataset = f"cap_{layer}"
    ensure_dataset(client, dataset)

    for path in files:
        table = re.sub(r"^\d+_", "", path.stem)
        destination = f"{client.project}.{dataset}.{table}"
        config = bigquery.QueryJobConfig(
            destination=destination,
            write_disposition="WRITE_TRUNCATE",
        )
        job = client.query(path.read_text(encoding="utf-8"), job_config=config)
        job.result()
        rows = client.get_table(destination).num_rows
        mb = (job.total_bytes_processed or 0) / 1e6
        print(f"{dataset}.{table:<22} {rows:>10,} lignes   ({mb:,.1f} Mo traités)")
    return 0


if __name__ == "__main__":
    layer_arg = sys.argv[1] if len(sys.argv) > 1 else "silver"
    sys.exit(run_layer(layer_arg))
