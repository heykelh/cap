"""Ingestion bronze : trafic aérien par paire d'aéroports (Eurostat, tables avia_par_xx).

Mesures conservées (mensuel) :
  PAS_BRD  passagers à bord      (unit PAS)
  ST_PAS   sièges offerts        (unit SEAT)
  CAF_PAS  vols commerciaux pax  (unit FLIGHT)

Une requête par pays et par mesure, l'une après l'autre (règles d'usage Eurostat).
Si Eurostat met la requête en file d'attente (réponse asynchrone), le script
attend que les données soient prêtes puis les récupère.

Usage :
  python ingestion/eurostat_bronze.py --countries fr --since 2024-01
  python ingestion/eurostat_bronze.py                 (tous les pays depuis 2019-01)
  python ingestion/eurostat_bronze.py --local-only    (sans BigQuery)
"""
import argparse
import gzip
import io
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://ec.europa.eu/eurostat/api/dissemination"
DATA_API = f"{BASE}/sdmx/2.1/data"
ASYNC_STATUS = f"{BASE}/1.0/async/status"
ASYNC_DATA = f"{BASE}/1.0/async/data"

# UE 27 + AELE + pays candidats déclarants. Un pays sans table est simplement ignoré.
DEFAULT_COUNTRIES = [
    "be", "bg", "cz", "dk", "de", "ee", "ie", "el", "es", "fr", "hr", "it", "cy",
    "lv", "lt", "lu", "hu", "mt", "nl", "at", "pl", "pt", "ro", "si", "sk", "fi",
    "se", "is", "no", "ch", "me", "mk", "rs", "tr",
]
# (unit, tra_meas)
MEASURES = [("PAS", "PAS_BRD"), ("SEAT", "ST_PAS"), ("FLIGHT", "CAF_PAS")]

POLL_EVERY_S = 15
POLL_MAX_S = 30 * 60


class EurostatError(RuntimeError):
    pass


def _decompress(raw: bytes) -> bytes:
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def _is_xml(raw: bytes) -> bool:
    return raw.lstrip()[:1] == b"<"


def _xml_tag(raw: bytes, tag: str) -> str | None:
    match = re.search(rf"<(?:\w+:)?{tag}>([^<]+)</(?:\w+:)?{tag}>", raw.decode("utf-8", "replace"))
    return match.group(1).strip() if match else None


def _wait_async(key: str) -> bytes:
    """Attend qu'une requête mise en file d'attente soit prête, puis récupère les données."""
    waited = 0
    while waited <= POLL_MAX_S:
        time.sleep(POLL_EVERY_S)
        waited += POLL_EVERY_S
        status_raw = requests.get(f"{ASYNC_STATUS}/{key}", timeout=60).content
        status = _xml_tag(status_raw, "status") or "INCONNU"
        print(f"      file d'attente Eurostat : {status} ({waited} s)")
        if status == "AVAILABLE":
            resp = requests.get(f"{ASYNC_DATA}/{key}", timeout=600)
            resp.raise_for_status()
            return _decompress(resp.content)
        if status in {"EXPIRED", "UNKNOWN_REQUEST", "ERROR"}:
            raise EurostatError(f"requête asynchrone {key} : statut {status}")
    raise EurostatError(f"requête asynchrone {key} : délai d'attente dépassé")


def fetch_csv(dataset: str, key: str, since: str) -> tuple[pd.DataFrame, str]:
    """Télécharge une tranche d'une table Eurostat au format SDMX-CSV."""
    url = f"{DATA_API}/{dataset}/{key}?format=SDMX-CSV&compressed=true&startPeriod={since}"
    for attempt in range(3):
        resp = requests.get(url, timeout=600)
        if resp.status_code == 404:
            return pd.DataFrame(), url
        if resp.status_code == 413:
            raise EurostatError(f"{url} : extraction trop volumineuse, réduire la période (--since)")
        if not resp.ok:
            time.sleep(10 * (attempt + 1))
            continue

        raw = _decompress(resp.content)
        if _is_xml(raw):
            async_key = _xml_tag(raw, "id")
            status = _xml_tag(raw, "status")
            if async_key and status in {"SUBMITTED", "PROCESSING"}:
                print(f"      requête mise en file d'attente par Eurostat (id {async_key})")
                raw = _wait_async(async_key)
            else:
                fault = _xml_tag(raw, "faultstring") or raw[:400].decode("utf-8", "replace")
                if "NO_RESULTS" in fault:
                    return pd.DataFrame(), url
                raise EurostatError(f"{url} : réponse inattendue : {fault}")

        df = pd.read_csv(io.BytesIO(raw), dtype=str)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        if "airp_pr" not in df.columns:
            raise EurostatError(f"{url} : colonnes inattendues : {list(df.columns)}")
        return df, url

    resp.raise_for_status()
    return pd.DataFrame(), url


def to_bronze(df: pd.DataFrame, country: str, url: str) -> pd.DataFrame:
    if df.empty:
        return df
    if "freq" in df.columns:
        df = df[df["freq"] == "M"]

    # Code de route : PAYS_ICAO_PAYS_ICAO, ex. FR_LFPG_AE_OMDB
    parts = df["airp_pr"].str.split("_", n=3, expand=True)
    if parts.shape[1] != 4:
        return pd.DataFrame()
    ok = parts.notna().all(axis=1)
    df, parts = df[ok], parts[ok]

    out = pd.DataFrame({
        "dataset_code": f"avia_par_{country}",
        "period": df["time_period"],
        "rep_country": parts[0],
        "rep_icao": parts[1],
        "partner_country": parts[2],
        "partner_icao": parts[3],
        "measure": df["tra_meas"],
        "unit": df["unit"],
        "value": pd.to_numeric(df["obs_value"], errors="coerce"),
        "obs_flag": df["obs_flag"] if "obs_flag" in df.columns else None,
        "_source_url": url,
        "_ingested_at": datetime.now(timezone.utc),
    })
    return out.dropna(subset=["value"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--countries", default=",".join(DEFAULT_COUNTRIES))
    parser.add_argument("--since", default="2019-01")
    parser.add_argument("--local-only", action="store_true")
    args = parser.parse_args()

    frames, failures = [], []
    countries = [c.strip().lower() for c in args.countries.split(",") if c.strip()]
    for country in countries:
        dataset = f"AVIA_PAR_{country.upper()}"
        for unit, measure in MEASURES:
            key = f"M.{unit}.{measure}."
            try:
                raw, url = fetch_csv(dataset, key, args.since)
                bronze = to_bronze(raw, country, url)
            except (EurostatError, requests.RequestException) as exc:
                failures.append(f"{country} {measure} : {exc}")
                print(f"{country:>3} {measure:<8} : ÉCHEC, {exc}")
                continue
            print(f"{country:>3} {measure:<8} : {len(bronze):>9,} lignes")
            if not bronze.empty:
                frames.append(bronze)

    if not frames:
        print("Aucune donnée récupérée.")
        return 1
    result = pd.concat(frames, ignore_index=True)

    out_dir = Path("data/bronze")
    out_dir.mkdir(parents=True, exist_ok=True)
    result.to_parquet(out_dir / "eurostat_routes.parquet", index=False)
    print(f"Total : {len(result):,} lignes, copie locale dans data/bronze/")

    if not args.local_only:
        from bq import load_dataframe

        n = load_dataframe(result, "eurostat_routes")
        print(f"BigQuery : cap_bronze.eurostat_routes = {n:,} lignes")

    if failures:
        print(f"{len(failures)} tranche(s) en échec :")
        for line in failures:
            print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
