"""Inventaire réel de ce que CAP fait tourner sur Google Cloud, pour la page « Sous le capot » du site.

Lit BigQuery (tables, lignes, tailles, dates), l'historique des requêtes des 30 derniers jours,
le SQL de chaque transformation et le journal du dernier rafraîchissement.
Écrit site/data/gcp.json.

Usage :
  python -m ops.gcp_inventory
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ingestion"))

LAYERS = {
    "cap_bronze": "Bronze : données brutes, copie fidèle des sources",
    "cap_silver": "Silver : données nettoyées, une ligne par route et par mois",
    "cap_gold": "Gold : indicateurs prêts à l'emploi, lus par la chaîne d'instruction et les agents IA",
}


def main() -> int:
    load_dotenv()
    from bq import LOCATION, get_client

    client = get_client()
    datasets = []
    for ds_id, role in LAYERS.items():
        tables = []
        for t in client.list_tables(ds_id):
            full = client.get_table(t.reference)
            tables.append({
                "table": full.table_id,
                "lignes": full.num_rows,
                "octets": full.num_bytes,
                "colonnes": len(full.schema),
                "schema": [{"nom": f.name, "type": f.field_type} for f in full.schema][:40],
                "modifiee_le": full.modified.isoformat() if full.modified else None,
                "expire_le": full.expires.isoformat() if full.expires else None,
            })
        datasets.append({"dataset": ds_id, "role": role, "tables": sorted(tables, key=lambda x: x["table"])})

    jobs = None
    try:
        rows = list(client.query(f"""
            SELECT COUNT(*) AS requetes,
                   SUM(total_bytes_processed) AS octets_lus,
                   SUM(total_slot_ms) AS slot_ms,
                   COUNTIF(cache_hit) AS en_cache
            FROM `region-{LOCATION.lower()}`.INFORMATION_SCHEMA.JOBS_BY_USER
            WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
              AND job_type = 'QUERY'
        """).result())
        if rows:
            jobs = {k: (int(v) if v is not None else 0) for k, v in dict(rows[0]).items()}
    except Exception as exc:  # droits insuffisants : la page l'indique au lieu de planter
        jobs = {"erreur": str(exc)[:200]}

    sql = []
    for layer in ["silver", "gold"]:
        for path in sorted((ROOT / "transform" / "sql" / layer).glob("*.sql")):
            sql.append({"couche": layer, "fichier": path.name,
                        "table": f"cap_{layer}.{path.stem.split('_', 1)[1]}",
                        "sql": path.read_text(encoding="utf-8")})

    refresh_path = ROOT / "ops" / "last_refresh.json"
    refresh = json.loads(refresh_path.read_text(encoding="utf-8")) if refresh_path.exists() else None

    payload = {
        "genere_le": datetime.now(timezone.utc).isoformat(),
        "projet": client.project,
        "localisation": LOCATION,
        "datasets": datasets,
        "requetes_30_jours": jobs,
        "sql": sql,
        "dernier_rafraichissement": refresh,
    }
    out = ROOT / "site" / "data" / "gcp.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    n = sum(len(d["tables"]) for d in datasets)
    print(f"Inventaire : {n} tables dans {len(datasets)} datasets -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
