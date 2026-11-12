"""Exporter l'étude de marché de toutes les destinations, pour le mode secours du site.

Quatre requêtes groupées sur BigQuery, puis la même fonction build_study que l'API en direct.
Écrit site/public/marche/<IATA>.json (une étude par destination) et site/public/marche/index.json
(la liste utilisée par le champ de recherche).

Usage :
  python -m agents.export_market
  python -m agents.export_market --min-pax 5000
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .datasource import HUBS_ICAO, PARIS_ICAO, BigQuerySource
from .market import ORIGINS_ICAO, build_study, file_key

SQL_ORIGINS = """SELECT rep_icao, rep_iata, rep_city, rep_country, partner_icao, partner_iata,
       pax_l12, pax_p12, seats_l12, flights_l12, lf_l12, lf_p12, growth_pax, growth_seats,
       masked_months_l12, window_end
FROM `cap_gold.route_window`
WHERE rep_icao IN UNNEST(@origins) AND partner_iata IS NOT NULL
  AND partner_icao NOT IN UNNEST(@paris)
  AND (flights_l12 >= 52 OR masked_months_l12 >= 10)"""

SQL_MONTHLY = """SELECT partner_iata, FORMAT_DATE('%Y-%m', month) AS month,
       SUM(IF(rep_icao IN UNNEST(@paris), passengers, 0)) AS paris,
       SUM(IF(rep_icao IN UNNEST(@hubs), passengers, 0)) AS hubs,
       COUNTIF(rep_icao IN UNNEST(@paris) AND quality_flag = 'valeur_masquee') AS paris_masked
FROM `cap_silver.routes_monthly`
WHERE partner_iata IN UNNEST(@iatas) AND rep_icao IN UNNEST(@origins)
GROUP BY partner_iata, month"""

SQL_AIRPORTS = """SELECT a.icao, a.iata, a.airport_name, a.city, a.country_iso2, a.lat, a.lon,
       ROUND(ST_DISTANCE(a.geo, cdg.geo) / 1000) AS distance_from_cdg_km
FROM `cap_silver.airports` AS a
CROSS JOIN (SELECT geo FROM `cap_silver.airports` WHERE icao = 'LFPG') AS cdg
WHERE a.icao IN UNNEST(@icaos)"""


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--min-pax", type=int, default=10000,
                   help="trafic minimal sur 12 mois (toutes origines) pour exporter une destination")
    p.add_argument("--out", default="site/public/marche")
    p.add_argument("--dossiers", default="site/data/dossiers")
    args = p.parse_args()

    src = BigQuerySource()
    a = src._a
    origins = src._query(SQL_ORIGINS, [a("origins", ORIGINS_ICAO), a("paris", PARIS_ICAO)], "export_origins")
    by_dest: dict[str, list[dict]] = defaultdict(list)
    for r in origins:
        by_dest[r["partner_iata"]].append(r)
    keep = {iata: rows for iata, rows in by_dest.items()
            if sum(r.get("pax_l12") or 0 for r in rows) >= args.min_pax
            or any(r["rep_icao"] in PARIS_ICAO for r in rows)}
    iatas = sorted(keep)
    print(f"{len(iatas)} destinations retenues sur {len(by_dest)}")

    monthly: dict[str, list[dict]] = defaultdict(list)
    for r in src._query(SQL_MONTHLY, [a("paris", PARIS_ICAO), a("hubs", HUBS_ICAO), a("iatas", iatas),
                                      a("origins", ORIGINS_ICAO)], "export_monthly"):
        monthly[r["partner_iata"]].append(r)
    icaos = sorted({rows[0]["partner_icao"] for rows in keep.values()})
    airports = {r["icao"]: r for r in src._query(SQL_AIRPORTS, [a("icaos", icaos)], "export_airports")}
    opps = {r["partner_iata"]: r for r in src._query("SELECT * FROM `cap_gold.opportunities`", [], "export_opps")}
    health = {r["partner_iata"]: r for r in src._query("SELECT * FROM `cap_gold.cdg_route_health`", [], "export_health")}
    jobs = src.take_jobs()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dossiers = Path(args.dossiers)
    index = []
    for iata in iatas:
        rows = keep[iata]
        study = build_study(iata, airports.get(rows[0]["partner_icao"]), rows,
                            sorted(monthly.get(iata, []), key=lambda m: m["month"]), opps.get(iata),
                            health.get(iata))
        study["dossier"] = (dossiers / f"{file_key(iata)}.json").exists()
        study["source"] = f"Export BigQuery du {date.today().isoformat()}"
        (out / f"{file_key(iata)}.json").write_text(json.dumps(study, ensure_ascii=False, default=str), encoding="utf-8")
        index.append({"iata": iata, "ville": study["ville"], "aeroport": study["aeroport"], "pays": study["pays"],
                      "statut": study["statut"], "pax": study["trafic_total_l12"], "dossier": study["dossier"]})
    index.sort(key=lambda r: r["pax"], reverse=True)
    (out / "index.json").write_text(json.dumps({"exporte_le": date.today().isoformat(), "destinations": index},
                                               ensure_ascii=False), encoding="utf-8")
    scanned = sum(j["octets_lus"] for j in jobs) / 1e6
    print(f"{len(index)} études écrites dans {out}/ · {len(jobs)} requêtes, {scanned:,.0f} Mo lus")
    return 0


if __name__ == "__main__":
    sys.exit(main())
