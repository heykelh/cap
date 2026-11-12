"""Supprime l'expiration automatique des tables CAP (à lancer une fois, après activation de la facturation).

Sans facturation, BigQuery fait expirer chaque table au bout de 60 jours. Une fois la facturation
activée, les tables déjà créées gardent leur date d'expiration : ce script la retire, ainsi que
l'expiration par défaut des datasets.

Usage :
  python -m ops.remove_expiration
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))


def main() -> int:
    load_dotenv()
    from bq import get_client

    client = get_client()
    for ds_id in ["cap_bronze", "cap_silver", "cap_gold"]:
        ds = client.get_dataset(ds_id)
        ds.default_table_expiration_ms = None
        client.update_dataset(ds, ["default_table_expiration_ms"])
        for item in client.list_tables(ds_id):
            table = client.get_table(item.reference)
            if table.expires:
                table.expires = None
                client.update_table(table, ["expires"])
                print(f"{ds_id}.{table.table_id:<26} expiration retirée")
            else:
                print(f"{ds_id}.{table.table_id:<26} déjà permanente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
