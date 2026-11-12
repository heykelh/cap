"""Couche d'accès aux données : le seul endroit qui sait d'où viennent les données.

Deux branchements, une même interface :
  * BigQuerySource : les tables gold de CAP (ou, chez une compagnie, ses propres tables) ;
  * SnapshotSource : un instantané JSON exporté depuis BigQuery, pour faire tourner
    la démo sans accès au cloud.

Ni la chaîne d'instruction ni les agents IA n'écrivent de SQL : ils appellent ces méthodes, et chaque méthode
exécute une requête paramétrée et relue (constantes SQL_* ci-dessous).

Chaque appel est consigné (requête, paramètres, octets lus, durée, lignes) : le journal
montre ainsi exactement ce que chaque étape ou chaque agent a demandé à BigQuery.
"""
import json
import time
from pathlib import Path
from typing import Protocol

HUBS_ICAO = [
    "EHAM", "EDDF", "EDDM", "LEMD", "LEBL", "LIRF", "LSZH", "LOWW", "EBBR",
    "EKCH", "LTFM", "LPPT", "EIDW", "ESSA", "ENGM", "EFHK",
]
PARIS_ICAO = ["LFPG", "LFPO"]

SQL_OPPORTUNITY = "SELECT * FROM `cap_gold.opportunities` WHERE partner_iata = @iata LIMIT 1"

SQL_HUB_FLOWS = """SELECT rep_icao, rep_iata, rep_city, partner_icao, partner_iata, pax_l12, pax_p12,
       flights_l12, lf_l12, growth_pax, window_end, masked_months_l12
FROM `cap_gold.route_window`
WHERE partner_iata = @iata AND rep_icao IN UNNEST(@hubs) AND flights_l12 >= 52
ORDER BY pax_l12 DESC"""

SQL_PARIS_TO_HUBS = """SELECT partner_icao, partner_iata, partner_city, pax_l12, flights_l12, lf_l12,
       masked_months_l12, window_end
FROM `cap_gold.route_window`
WHERE rep_icao = 'LFPG' AND partner_icao IN UNNEST(@hubs)
ORDER BY pax_l12 DESC"""

SQL_OVERRIDES = """SELECT partner_iata, airport_from, status, season, source, verified_on, comment
FROM `cap_bronze.paris_network_overrides`
WHERE partner_iata = @iata"""

SQL_FRESHNESS = "SELECT rep_country, last_month, share_ok, rows_masked FROM `cap_silver.data_freshness`"

SQL_AIRPORT = """SELECT a.icao, a.iata, a.airport_name, a.city, a.country_iso2, a.lat, a.lon,
       ROUND(ST_DISTANCE(a.geo, cdg.geo) / 1000) AS distance_from_cdg_km
FROM `cap_silver.airports` AS a
CROSS JOIN (SELECT geo FROM `cap_silver.airports` WHERE icao = 'LFPG') AS cdg
WHERE a.iata = @iata
ORDER BY IF(a.airport_type = 'large_airport', 0, IF(a.airport_type = 'medium_airport', 1, 2))
LIMIT 1"""

# Étude de marché : toutes les origines observées (Paris + 16 hubs) vers une destination.
SQL_MARKET_ORIGINS = """SELECT rep_icao, rep_iata, rep_city, rep_country, partner_icao, partner_iata,
       pax_l12, pax_p12, seats_l12, flights_l12, lf_l12, lf_p12, growth_pax, growth_seats,
       masked_months_l12, window_end
FROM `cap_gold.route_window`
WHERE partner_iata = @iata AND rep_icao IN UNNEST(@origins)
ORDER BY pax_l12 DESC"""

SQL_MARKET_MONTHLY = """SELECT FORMAT_DATE('%Y-%m', month) AS month,
       SUM(IF(rep_icao IN UNNEST(@paris), passengers, 0)) AS paris,
       SUM(IF(rep_icao IN UNNEST(@hubs), passengers, 0)) AS hubs,
       COUNTIF(rep_icao IN UNNEST(@paris) AND quality_flag = 'valeur_masquee') AS paris_masked
FROM `cap_silver.routes_monthly`
WHERE partner_iata = @iata AND (rep_icao IN UNNEST(@paris) OR rep_icao IN UNNEST(@hubs))
GROUP BY month
ORDER BY month"""

SQL_CDG_HEALTH = "SELECT * FROM `cap_gold.cdg_route_health` WHERE partner_iata = @iata LIMIT 1"


class DataSource(Protocol):
    name: str

    def opportunity(self, iata: str) -> dict | None: ...
    def hub_flows(self, iata: str) -> list[dict]: ...
    def paris_to_hubs(self, hub_icaos: list[str]) -> list[dict]: ...
    def freshness(self) -> list[dict]: ...
    def overrides(self, iata: str) -> list[dict]: ...
    def take_jobs(self) -> list[dict]: ...


def _plain(row) -> dict:
    out = {}
    for k, v in dict(row).items():
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


def _clean_sql(sql: str) -> str:
    return "\n".join(line.rstrip() for line in sql.strip().splitlines())


class _Recorder:
    """Garde la trace des requêtes depuis le dernier appel à take_jobs()."""

    def __init__(self):
        self._jobs: list[dict] = []

    def _record(self, job: dict) -> None:
        self._jobs.append(job)

    def take_jobs(self) -> list[dict]:
        jobs, self._jobs = self._jobs, []
        return jobs


class BigQuerySource(_Recorder):
    name = "BigQuery (cap_gold)"

    def __init__(self, client=None):
        super().__init__()
        from google.cloud import bigquery

        self._bq = bigquery
        if client is None:
            import sys

            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingestion"))
            from bq import get_client

            client = get_client()
        self._client = client
        self.project = client.project

    def _query(self, sql: str, params: list, method: str = "requête") -> list[dict]:
        config = self._bq.QueryJobConfig(query_parameters=params)
        started = time.perf_counter()
        job = self._client.query(sql, job_config=config)
        rows = [_plain(r) for r in job.result()]
        self._record({
            "methode": method,
            "sql": _clean_sql(sql),
            "parametres": {p.name: getattr(p, "value", None) if hasattr(p, "value") else getattr(p, "values", None)
                           for p in params},
            "execute_sur": "BigQuery",
            "job_id": job.job_id,
            "octets_lus": job.total_bytes_processed or 0,
            "octets_factures": job.total_bytes_billed or 0,
            "cache": bool(job.cache_hit),
            "duree_ms": round((time.perf_counter() - started) * 1000),
            "lignes": len(rows),
        })
        return rows

    def _s(self, name, value):
        return self._bq.ScalarQueryParameter(name, "STRING", value)

    def _a(self, name, values):
        return self._bq.ArrayQueryParameter(name, "STRING", values)

    def opportunity(self, iata):
        rows = self._query(SQL_OPPORTUNITY, [self._s("iata", iata)], "opportunity")
        return rows[0] if rows else None

    def hub_flows(self, iata):
        return self._query(SQL_HUB_FLOWS, [self._s("iata", iata), self._a("hubs", HUBS_ICAO)], "hub_flows")

    def paris_to_hubs(self, hub_icaos):
        if not hub_icaos:
            return []
        return self._query(SQL_PARIS_TO_HUBS, [self._a("hubs", hub_icaos)], "paris_to_hubs")

    def freshness(self):
        return self._query(SQL_FRESHNESS, [], "freshness")

    def overrides(self, iata):
        return self._query(SQL_OVERRIDES, [self._s("iata", iata)], "overrides")

    # --- Étude de marché ------------------------------------------------------------

    def airport(self, iata):
        rows = self._query(SQL_AIRPORT, [self._s("iata", iata)], "airport")
        return rows[0] if rows else None

    def market_origins(self, iata):
        return self._query(SQL_MARKET_ORIGINS,
                           [self._s("iata", iata), self._a("origins", PARIS_ICAO + HUBS_ICAO)], "market_origins")

    def market_monthly(self, iata):
        return self._query(SQL_MARKET_MONTHLY, [self._s("iata", iata), self._a("paris", PARIS_ICAO),
                                                self._a("hubs", HUBS_ICAO)], "market_monthly")

    def cdg_health(self, iata):
        rows = self._query(SQL_CDG_HEALTH, [self._s("iata", iata)], "cdg_health")
        return rows[0] if rows else None


class SnapshotSource(_Recorder):
    """Instantané JSON : { "exported_at", "origin", "destinations": { IATA: {...} }, "freshness": [...] }"""

    def __init__(self, path: Path | str):
        super().__init__()
        self.path = Path(path)
        self._data = json.loads(self.path.read_text(encoding="utf-8"))
        self.name = f"Instantané {self.path.name} (exporté le {self._data.get('exported_at', '?')})"

    def _dest(self, iata):
        return self._data["destinations"].get(iata, {})

    def _log(self, method: str, sql: str, params: dict, rows) -> None:
        n = 0 if rows is None else (len(rows) if isinstance(rows, list) else 1)
        self._record({"methode": method, "sql": _clean_sql(sql), "parametres": params,
                      "execute_sur": "instantané", "octets_lus": 0, "octets_factures": 0, "cache": False,
                      "duree_ms": 0, "lignes": n})

    def opportunity(self, iata):
        row = self._dest(iata).get("opportunity")
        self._log("opportunity", SQL_OPPORTUNITY, {"iata": iata}, row)
        return row

    def hub_flows(self, iata):
        rows = self._dest(iata).get("hub_flows", [])
        self._log("hub_flows", SQL_HUB_FLOWS, {"iata": iata, "hubs": HUBS_ICAO}, rows)
        return rows

    def paris_to_hubs(self, hub_icaos):
        rows = []
        for dest in self._data["destinations"].values():
            rows.extend(dest.get("paris_to_hubs", []))
        seen, out = set(), []
        for r in rows:
            if r["partner_icao"] in hub_icaos and r["partner_icao"] not in seen:
                seen.add(r["partner_icao"])
                out.append(r)
        out = sorted(out, key=lambda r: r.get("pax_l12") or 0, reverse=True)
        if hub_icaos:
            self._log("paris_to_hubs", SQL_PARIS_TO_HUBS, {"hubs": hub_icaos}, out)
        return out

    def freshness(self):
        return self._data.get("freshness", [])

    def overrides(self, iata):
        rows = self._dest(iata).get("overrides", [])
        self._log("overrides", SQL_OVERRIDES, {"iata": iata}, rows)
        return rows


def export_snapshot(source: DataSource, iatas: list[str], path: Path | str, exported_at: str) -> int:
    """Copie les données utiles à une liste de destinations dans un instantané JSON."""
    destinations = {}
    for iata in iatas:
        flows = source.hub_flows(iata)
        destinations[iata] = {
            "opportunity": source.opportunity(iata),
            "hub_flows": flows,
            "paris_to_hubs": source.paris_to_hubs([f["rep_icao"] for f in flows]),
            "overrides": source.overrides(iata),
        }
    source.take_jobs()
    payload = {
        "exported_at": exported_at,
        "origin": "LFPG",
        "source": getattr(source, "name", "inconnue"),
        "destinations": destinations,
        "freshness": source.freshness(),
    }
    source.take_jobs()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return len(destinations)
