"""Ingestion bronze : référentiel des aéroports (OurAirports, domaine public).

Usage :
  python ingestion/ourairports_bronze.py
  python ingestion/ourairports_bronze.py --local-only
"""
import argparse
import io
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
KEEP = ["ident", "type", "name", "latitude_deg", "longitude_deg", "iso_country",
        "iso_region", "municipality", "scheduled_service", "icao_code", "iata_code"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()

    resp = requests.get(URL, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(io.BytesIO(resp.content), dtype=str, keep_default_na=False)
    df = df[[c for c in KEEP if c in df.columns]]
    df = df[df["type"].isin(["large_airport", "medium_airport"])].copy()
    for col in ["latitude_deg", "longitude_deg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["_source_url"] = URL
    df["_ingested_at"] = datetime.now(timezone.utc)

    out_dir = Path("data/bronze")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "airports.parquet", index=False)
    print(f"Aéroports : {len(df):,} lignes")

    if not args.local_only:
        from bq import load_dataframe

        n = load_dataframe(df, "airports")
        print(f"BigQuery : cap_bronze.airports = {n:,} lignes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
