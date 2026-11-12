"""Génère en une fois les données du site : radar, dossiers d'ouverture et métadonnées.

Étapes :
  1. lit le radar long-courrier dans BigQuery (ou un instantané existant avec --from-snapshot) ;
  2. exporte l'instantané des données utiles (reference/snapshots/demo.json) ;
  3. instruit un dossier par destination avec la chaîne d'instruction (six étapes) ;
  4. écrit les fichiers lus par le site dans site/data/.

Règle : un dossier pour chaque destination long-courrier du radar (aucun plafond arbitraire).
Les étapes interrogent BigQuery en direct : le journal de chaque dossier garde la trace réelle
des requêtes (texte SQL, octets lus, durée). Un instantané est aussi exporté pour le mode secours.

Usage :
  python -m agents.batch --llm groq,gemini
  python -m agents.batch --top 20 --llm groq,gemini      (pour un essai rapide)
  python -m agents.batch --from-snapshot reference/snapshots/demo.json --llm offline

Les dossiers sont générés à l'avance : le site n'appelle aucune IA en direct,
il reste rapide et ne peut pas tomber en panne pendant une démonstration.
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from economics import load_assumptions

from .datasource import SnapshotSource, export_snapshot
from .graph import run_dossier
from .llm import LLMError, get_llm
from .market import file_key

# Région de référence pour le remplissage visé (communiqué Air France-KLM 2025, p. 29).
REGIONS = {
    "Amérique du Nord": ["US", "CA", "MX"],
    "Amérique latine": ["BR", "AR", "CL", "CO", "PE", "VE", "EC", "UY", "PY", "BO", "CR", "PA", "GT"],
    "Caraïbes et océan Indien": ["DO", "CU", "JM", "AN", "CW", "AW", "BS", "BB", "TT", "HT", "LC", "MU", "SC",
                                 "MV", "MG", "RE", "KM"],
    "Afrique": ["ZA", "NG", "GH", "KE", "ET", "RW", "TZ", "UG", "SN", "CI", "CM", "MA", "DZ", "TN", "EG", "AO",
                "MZ", "ZM", "ZW", "NA", "BW", "CD", "CG", "GA", "ML", "BF", "NE", "BJ", "TG", "GN", "MR", "SD"],
    "Asie et Moyen-Orient": ["PH", "ID", "MY", "TH", "VN", "SG", "CN", "HK", "TW", "JP", "KR", "IN", "PK", "BD",
                             "LK", "NP", "KZ", "UZ", "KG", "TJ", "TM", "MN", "AE", "QA", "SA", "KW", "BH", "OM",
                             "IR", "IQ", "JO", "LB", "IL", "AZ", "GE", "AM", "AF", "KH", "LA", "MM"],
}
COUNTRY_TO_REGION = {c: region for region, codes in REGIONS.items() for c in codes}


def default_scenario(distance_km: float) -> dict:
    """Scénario de départ, modifiable ensuite sur le site."""
    if distance_km >= 9000:
        return {"freq": 3, "aircraft": "A350-900"}
    if distance_km >= 6000:
        return {"freq": 4, "aircraft": "B787-9"}
    return {"freq": 5, "aircraft": "B787-9"}


def radar_rows_from_bigquery(top: int) -> tuple[list[dict], dict, object]:
    from .datasource import BigQuerySource

    source = BigQuerySource()
    rows = source._query(
        "SELECT * FROM `cap_gold.opportunities` WHERE partner_iata IS NOT NULL "
        "ORDER BY segment, opportunity_score DESC",
        [],
    )
    source.take_jobs()
    segments: dict[str, int] = {}
    for r in rows:
        segments[r.get("segment")] = segments.get(r.get("segment"), 0) + 1
    long_haul = [r for r in rows if r.get("segment") == "long-courrier"]
    return (long_haul[:top] if top else long_haul), segments, source


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=0, help="0 = toutes les destinations long-courrier (règle par défaut)")
    p.add_argument("--llm", default="groq,gemini")
    p.add_argument("--from-snapshot", help="réutiliser un instantané existant au lieu de BigQuery")
    p.add_argument("--snapshot-out", default="reference/snapshots/demo.json")
    p.add_argument("--out", default="site/data")
    p.add_argument("--pause", type=float, default=12.0, help="secondes entre deux dossiers rédigés par l'IA (quota gratuit)")
    p.add_argument("--retry-wait", type=float, default=65.0,
                   help="attente avant de reprendre les dossiers restés en gabarit")
    args = p.parse_args()

    today = date.today()
    segments: dict[str, int] = {}
    if args.from_snapshot:
        snapshot_path = Path(args.from_snapshot)
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        radar = [d["opportunity"] for d in data["destinations"].values() if d.get("opportunity")]
        radar.sort(key=lambda r: r.get("opportunity_score") or 0, reverse=True)
        radar = radar[: args.top] if args.top else radar
        source = SnapshotSource(snapshot_path)
    else:
        radar, segments, bq_source = radar_rows_from_bigquery(args.top)
        snapshot_path = Path(args.snapshot_out)
        coords = {r["icao"]: r for r in bq_source._query(
            "SELECT icao, lat, lon FROM `cap_silver.airports` WHERE icao IN UNNEST(@ids) OR icao = 'LFPG'",
            [bq_source._a("ids", [r["partner_icao"] for r in radar])])}
        for r in radar:
            c = coords.get(r["partner_icao"], {})
            r["lat"], r["lon"] = c.get("lat"), c.get("lon")
        n = export_snapshot(bq_source, [r["partner_iata"] for r in radar], snapshot_path,
                            exported_at=today.isoformat())
        print(f"Instantané exporté : {n} destinations dans {snapshot_path}")
        source = bq_source

    def fresh_llm():
        """Un fournisseur neuf par dossier : une panne passagère ne coupe pas tout le lot."""
        try:
            return get_llm(args.llm)
        except LLMError as exc:
            print(f"{exc} : passage en mode hors ligne.")
            return get_llm("offline")

    llm = fresh_llm()
    assumptions = load_assumptions()
    out = Path(args.out)
    (out / "dossiers").mkdir(parents=True, exist_ok=True)

    def instruct(i: int, opp: dict):
        iata = opp["partner_iata"]
        region = COUNTRY_TO_REGION.get((opp.get("partner_country") or "").upper())
        scenario = default_scenario(float(opp.get("distance_from_cdg_km") or 0))
        request = {"dest": iata, "region": region, **scenario}
        started = time.perf_counter()
        dossier = run_dossier(source, fresh_llm(), assumptions, request, today=today)
        if dossier.get("error"):
            print(f"[{i:>2}/{len(radar)}] {iata} : échec, {dossier['error']}")
            return None, False
        writer = next(e for e in dossier["journal"] if e["agent"] == "Rédacteur")
        by_llm = writer["statut"].startswith("rédigé par le LLM")
        dossier["scenario"] = {**scenario, "region": region}
        dossier["opportunity"] = opp
        (out / "dossiers" / f"{file_key(iata)}.json").write_text(
            json.dumps(dossier, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        eco = dossier["synthese_economique"]
        print(f"[{i:>2}/{len(radar)}] {iata:<4} {'IA' if by_llm else 'gabarit':<8} "
              f"{time.perf_counter() - started:5.1f} s · résultat {eco['resultat_meur']:>6.1f} M€ · "
              f"{dossier['verdict'].split(' :')[0]}")
        if not by_llm and writer.get("rejets"):
            print(f"         motif : {writer['rejets'][-1][:110]}")
        row = {
            "rang": i,
            "iata": iata,
            "ville": opp.get("partner_city"),
            "pays": opp.get("partner_country"),
            "region": region,
            "score": opp.get("opportunity_score"),
            "distance_km": opp.get("distance_from_cdg_km"),
            "hubs": opp.get("hubs_list"),
            "nb_hubs": opp.get("hubs_serving"),
            "pax_hubs": opp.get("pax_l12_hubs"),
            "croissance": opp.get("growth_hubs"),
            "remplissage": opp.get("lf_l12_hubs"),
            "resultat_meur": eco["resultat_meur"],
            "marge_pct": eco["marge_pct"],
            "verdict": dossier["verdict"],
            "alertes": [a["code"] for a in dossier["alertes"]],
            "lat": opp.get("lat"),
            "lon": opp.get("lon"),
            "redige_par_ia": by_llm,
        }
        return row, by_llm

    rows: dict[str, dict] = {}
    offline = llm.name.startswith("hors ligne")
    for i, opp in enumerate(radar, start=1):
        row, by_llm = instruct(i, opp)
        if row:
            rows[opp["partner_iata"]] = row
        if by_llm:
            time.sleep(args.pause)

    pending = [(i, o) for i, o in enumerate(radar, start=1)
               if o["partner_iata"] in rows and not rows[o["partner_iata"]]["redige_par_ia"]]
    if pending and not offline:
        print(f"\n{len(pending)} dossier(s) en gabarit : reprise dans {args.retry_wait:.0f} s (quota gratuit).")
        time.sleep(args.retry_wait)
        for i, opp in pending:
            row, by_llm = instruct(i, opp)
            if row:
                rows[opp["partner_iata"]] = row
            if by_llm:
                time.sleep(args.pause)

    radar_out = [rows[o["partner_iata"]] for o in radar if o["partner_iata"] in rows]
    stats = {"llm": sum(r["redige_par_ia"] for r in radar_out),
             "gabarit": sum(not r["redige_par_ia"] for r in radar_out),
             "echec": len(radar) - len(radar_out)}

    snapshot_meta = json.loads(snapshot_path.read_text(encoding="utf-8"))
    meta = {
        "genere_le": today.isoformat(),
        "instantane_exporte_le": snapshot_meta.get("exported_at"),
        "source_donnees": snapshot_meta.get("source"),
        "fraicheur_par_pays": snapshot_meta.get("freshness", []),
        "hypotheses": {"version": assumptions.version,
                       "valeurs": {k: {"valeur": a.value, "unite": a.unit, "libelle": a.label,
                                       "methode": a.method, "source": a.source}
                                   for k, a in assumptions.items.items()},
                       "remplissage_par_region": assumptions.load_factor_by_region,
                       "appareils": assumptions.aircraft,
                       "limites": assumptions.known_limits},
        "llm": llm.name,
        "statistiques": stats,
        "regle_dossiers": "un dossier pour chaque destination long-courrier du radar",
        "radar_par_segment": segments,
        "agents_source": source.name,
    }
    (out / "radar.json").write_text(json.dumps(radar_out, ensure_ascii=False, indent=2, default=str),
                                    encoding="utf-8")
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n{len(radar_out)} dossiers dans {out}/ · rédigés par l'IA : {stats['llm']} · "
          f"gabarit : {stats['gabarit']} · échecs : {stats['echec']}")
    return 0 if radar_out else 1


if __name__ == "__main__":
    sys.exit(main())
