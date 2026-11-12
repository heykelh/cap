"""Ingestion bronze : corrections du réseau de Paris tenues par l'analyste.

Source : reference/paris_network_overrides.csv (versionné dans Git).
Colonnes :
  partner_iata   code IATA de la destination (ex. CPT)
  airport_from   CDG ou ORY
  status         desservie | non_desservie | a_verifier
  season         ex. hiver, été, toute l'année
  source         d'où vient l'information (ex. horaires airfrance.fr)
  verified_on    date de vérification, AAAA-MM-JJ
  comment        texte libre

Seules les lignes au statut « desservie » excluent une destination du radar.
Une ligne « desservie » sans source ni date est refusée.

Usage :
  python ingestion/reference_bronze.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PATH = Path("reference/paris_network_overrides.csv")
STATUSES = {"desservie", "non_desservie", "a_verifier"}


def main() -> int:
    df = pd.read_csv(PATH, dtype=str, keep_default_na=False)
    df["partner_iata"] = df["partner_iata"].str.strip().str.upper()
    df["status"] = df["status"].str.strip().str.lower()

    errors = []
    bad_status = df[~df["status"].isin(STATUSES)]
    for _, row in bad_status.iterrows():
        errors.append(f"{row['partner_iata']} : statut inconnu « {row['status']} »")
    served = df[df["status"] == "desservie"]
    for _, row in served[(served["source"] == "") | (served["verified_on"] == "")].iterrows():
        errors.append(f"{row['partner_iata']} : « desservie » exige une source et une date de vérification")
    if errors:
        print("Fichier refusé :")
        for line in errors:
            print(f"  - {line}")
        return 1

    df["_source_file"] = str(PATH)
    df["_ingested_at"] = datetime.now(timezone.utc)

    from bq import load_dataframe

    n = load_dataframe(df, "paris_network_overrides")
    print(f"BigQuery : cap_bronze.paris_network_overrides = {n} lignes "
          f"({len(served)} desservie(s), {int((df['status'] == 'a_verifier').sum())} à vérifier)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
