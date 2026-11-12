"""Exporter un instantané des vraies données BigQuery pour la démo hors cloud.

Usage :
  python -m agents.export_snapshot --top 20
  python -m agents.export_snapshot --dest MNL CLT DPS

Écrit reference/snapshots/demo.json. Le site déployé lit ce fichier : pas besoin
d'identifiants Google Cloud en production, et chaque chiffre reste celui de BigQuery.
"""
import argparse
import sys
from datetime import date

from .datasource import BigQuerySource, export_snapshot


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dest", nargs="*", default=[])
    p.add_argument("--top", type=int, default=0, help="ajoute les N premières destinations long-courrier du radar")
    p.add_argument("--out", default="reference/snapshots/demo.json")
    args = p.parse_args()

    source = BigQuerySource()
    iatas = [d.upper() for d in args.dest]
    if args.top:
        rows = source._query(
            "SELECT partner_iata FROM `cap_gold.opportunities` WHERE segment = 'long-courrier' "
            "AND partner_iata IS NOT NULL ORDER BY opportunity_score DESC LIMIT @n",
            [source._bq.ScalarQueryParameter("n", "INT64", args.top)],
        )
        iatas += [r["partner_iata"] for r in rows if r["partner_iata"] not in iatas]
    if not iatas:
        p.error("indiquer --dest ou --top")
    n = export_snapshot(source, iatas, args.out, exported_at=date.today().isoformat())
    print(f"Instantané : {n} destinations dans {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
