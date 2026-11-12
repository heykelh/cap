"""Connexion BigQuery et chargement d'un DataFrame dans une table (sandbox compatible).

Le sandbox ne supporte pas le DML : on ne modifie jamais une table,
on la remplace entièrement (load job en WRITE_TRUNCATE).
"""
import os

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
LOCATION = os.getenv("BQ_LOCATION", "EU")
BRONZE_DATASET = os.getenv("BQ_BRONZE_DATASET", "cap_bronze")


def get_client():
    from google.cloud import bigquery

    if not PROJECT_ID:
        raise RuntimeError("GCP_PROJECT_ID manquant dans le fichier .env")
    return bigquery.Client(project=PROJECT_ID, location=LOCATION)


def ensure_dataset(client, dataset_id: str) -> None:
    from google.cloud import bigquery

    ds = bigquery.Dataset(f"{client.project}.{dataset_id}")
    ds.location = LOCATION
    client.create_dataset(ds, exists_ok=True)


def load_dataframe(df: pd.DataFrame, table: str, dataset_id: str = BRONZE_DATASET) -> int:
    """Remplace la table par le contenu du DataFrame. Retourne le nombre de lignes."""
    from google.cloud import bigquery

    client = get_client()
    ensure_dataset(client, dataset_id)
    table_id = f"{client.project}.{dataset_id}.{table}"
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    return client.get_table(table_id).num_rows
