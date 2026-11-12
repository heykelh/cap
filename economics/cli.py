"""Évaluer une ligne en ligne de commande.

Exemples :
  python -m economics.cli --dest MNL --distance 10733 --freq 3 --aircraft A350-900
  python -m economics.cli --dest MNL --distance 10733 --freq 3 --aircraft A350-900 --region "Asie et Moyen-Orient" --market-pax 339958
  python -m economics.cli --dest MNL --freq 3 --aircraft A350-900 --from-bigquery
"""
import argparse
import json
import sys

from .assumptions import load_assumptions
from .model import evaluate_route, inputs_from_assumptions, sensitivity


def fetch_from_bigquery(dest_iata: str) -> tuple[float, float]:
    """Distance depuis CDG et trafic des hubs concurrents (proxy du marché), depuis la table gold."""
    sys.path.insert(0, "ingestion")
    from bq import get_client
    from google.cloud import bigquery

    client = get_client()
    query = """
        SELECT distance_from_cdg_km, pax_l12_hubs
        FROM `cap_gold.opportunities`
        WHERE partner_iata = @iata
        LIMIT 1
    """
    config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("iata", "STRING", dest_iata)])
    rows = list(client.query(query, job_config=config).result())
    if not rows:
        raise SystemExit(f"{dest_iata} absent de cap_gold.opportunities : passer --distance à la main.")
    return float(rows[0].distance_from_cdg_km), float(rows[0].pax_l12_hubs)


def main() -> int:
    p = argparse.ArgumentParser(description="Compte de résultat d'une ligne au départ de Paris CDG")
    p.add_argument("--dest", required=True, help="code IATA de la destination, ex. MNL")
    p.add_argument("--freq", type=float, required=True, help="allers-retours par semaine")
    p.add_argument("--aircraft", default="A350-900")
    p.add_argument("--distance", type=float, help="distance orthodromique en km")
    p.add_argument("--region", help="région pour le remplissage par défaut, ex. « Asie et Moyen-Orient »")
    p.add_argument("--load-factor", type=float, help="remplissage visé, ex. 0.85")
    p.add_argument("--weeks", type=float, help="semaines d'exploitation par an (ligne saisonnière)")
    p.add_argument("--seats", type=int, help="sièges par vol (remplace la configuration de l'appareil)")
    p.add_argument("--market-pax", type=float, help="taille du marché estimée, passagers par an")
    p.add_argument("--fuel-change", type=float, default=0.0, help="variation du prix du carburant, ex. 0.1")
    p.add_argument("--from-bigquery", action="store_true", help="distance et marché lus dans cap_gold.opportunities")
    p.add_argument("--json", action="store_true", help="sortie JSON complète, trace incluse")
    args = p.parse_args()

    distance, market = args.distance, args.market_pax
    if args.from_bigquery:
        distance, hubs_pax = fetch_from_bigquery(args.dest.upper())
        market = market or hubs_pax
    if not distance:
        p.error("--distance est obligatoire sans --from-bigquery")

    a = load_assumptions()
    x = inputs_from_assumptions(
        a, "CDG", args.dest.upper(), distance, args.freq, args.aircraft,
        load_factor=args.load_factor, region=args.region, weeks_per_year=args.weeks,
        seats_per_flight=args.seats, market_pax_per_year=market, fuel_price_change=args.fuel_change,
    )
    r = evaluate_route(x)
    sens = sensitivity(x)

    if args.json:
        print(json.dumps({"synthese": r.summary(), "trace": r.trace, "sensibilites": sens,
                          "hypotheses": {k: v.cite() for k, v in a.items.items()},
                          "limites": a.known_limits}, ensure_ascii=False, indent=2))
        return 0

    s = r.summary()
    print(f"\n{s['route']} · {args.freq:g} fréquences/semaine · {args.aircraft} ({x.seats_per_flight} sièges)"
          f" · {distance:,.0f} km".replace(",", " "))
    print(f"  Vols par an               {s['vols_par_an']:>12,}".replace(",", " "))
    print(f"  Passagers par an          {s['passagers_par_an']:>12,}".replace(",", " "))
    print(f"  Recette                   {s['recette_meur']:>10.1f} M€")
    print(f"  Coûts                     {s['couts_meur']:>10.1f} M€")
    print(f"  Résultat d'exploitation   {s['resultat_meur']:>10.1f} M€   (marge {s['marge_pct']:.1f} %)")
    print(f"  Remplissage visé          {x.load_factor * 100:>10.1f} %")
    print(f"  Remplissage d'équilibre   {s['remplissage_equilibre_pct']:>10.1f} %")
    if s["part_de_marche_necessaire_pct"] is not None:
        print(f"  Part de marché nécessaire {s['part_de_marche_necessaire_pct']:>10.1f} %  "
              f"(du trafic des hubs concurrents vers cette destination)")
    print("\nSensibilité du résultat (M€) :")
    for row in sens:
        print(f"  {row['hypothese']:<34} {row['resultat_bas_meur']:>7.1f}  /  {row['resultat_haut_meur']:>7.1f}")
    print(f"\nHypothèses : {a.version}. Limites : voir --json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
