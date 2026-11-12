"""Étude de marché d'une destination quelconque, desservie par Paris ou non.

Pour une destination, CAP compare le trafic de Paris (CDG et Orly) à celui des 16 grands hubs
européens : volumes sur 12 mois, évolution, remplissage, part de Paris, série mensuelle depuis 2019,
puis la santé de la ligne si Paris la dessert, ou sa place au radar sinon.

Une seule fonction construit l'étude (build_study) ; deux façons de l'alimenter :
  * study_live : requêtes BigQuery paramétrées, une destination (API en direct) ;
  * export_market.py : quelques requêtes groupées pour toutes les destinations (mode secours).
Les phrases de lecture sont produites par des règles : aucun texte d'IA, aucun chiffre inventé.
"""
from .datasource import HUBS_ICAO, PARIS_ICAO
from .facts import fmt_int, fmt_month, fmt_pct, fmt_pct_signed

ORIGINS_ICAO = PARIS_ICAO + HUBS_ICAO

# Noms de fichiers interdits par Windows (PRN = Pristina, CON, AUX, NUL…) : on ajoute un « _ ».
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"}


def file_key(iata: str) -> str:
    iata = iata.upper()
    return f"{iata}_" if iata in WINDOWS_RESERVED else iata

HEALTH_LABELS = {
    "donnees_masquees": "volumes masqués par Eurostat la majorité des mois",
    "trafic_en_baisse": "trafic en baisse de plus de 5 % sur un an",
    "remplissage_en_baisse": "remplissage en baisse de plus de 3 points",
    "remplissage_faible": "remplissage inférieur à 70 %",
    "capacite_en_avance_sur_demande": "capacité qui progresse plus vite que la demande",
    "ras": "aucun signal d'alerte",
}


def _num(x):
    return float(x) if x is not None else None


def _served(row: dict) -> bool:
    return (row.get("flights_l12") or 0) >= 52 or (row.get("masked_months_l12") or 0) >= 10


def default_scenario(distance_km: float | None) -> dict:
    d = distance_km or 0
    if d >= 9000:
        return {"freq": 3, "aircraft": "A350-900"}
    if d >= 6000:
        return {"freq": 4, "aircraft": "B787-9"}
    return {"freq": 5, "aircraft": "B787-9"}


def build_study(iata: str, airport: dict | None, origins: list[dict], monthly: list[dict],
                opportunity: dict | None, health: dict | None) -> dict:
    iata = iata.upper()
    rows = []
    for r in origins:
        rows.append({
            "icao": r.get("rep_icao"),
            "iata": r.get("rep_iata") or r.get("rep_icao"),
            "ville": r.get("rep_city"),
            "pays": r.get("rep_country"),
            "paris": r.get("rep_icao") in PARIS_ICAO,
            "pax_l12": int(r.get("pax_l12") or 0),
            "pax_p12": int(r.get("pax_p12") or 0),
            "vols_l12": int(r.get("flights_l12") or 0),
            "sieges_l12": int(r.get("seats_l12") or 0),
            "remplissage": _num(r.get("lf_l12")),
            "remplissage_prec": _num(r.get("lf_p12")),
            "croissance": _num(r.get("growth_pax")),
            "mois_masques": int(r.get("masked_months_l12") or 0),
            "donnees_jusqu_a": str(r.get("window_end") or "")[:7] or None,
            "reguliere": _served(r),
        })
    rows.sort(key=lambda r: r["pax_l12"], reverse=True)
    regular = [r for r in rows if r["reguliere"]]
    paris = [r for r in rows if r["paris"]]
    paris_regular = [r for r in paris if r["reguliere"]]
    hubs_regular = [r for r in regular if not r["paris"]]

    total = sum(r["pax_l12"] for r in regular)
    total_prev = sum(r["pax_p12"] for r in regular)
    paris_pax = sum(r["pax_l12"] for r in paris_regular)
    paris_masked = any(r["mois_masques"] >= 6 for r in paris_regular)
    share = (paris_pax / total) if total and paris_pax and not paris_masked else None
    rank = next((i for i, r in enumerate(regular, start=1) if r["paris"]), None)
    growth = (total / total_prev - 1) if total_prev >= 1000 else None

    if paris_regular:
        status = "desservie"
    elif opportunity:
        status = "opportunite"
    else:
        status = "non_desservie"

    city = (airport or {}).get("city") or (opportunity or {}).get("partner_city") or iata
    distance = _num((airport or {}).get("distance_from_cdg_km") or (opportunity or {}).get("distance_from_cdg_km"))
    ends = sorted({r["donnees_jusqu_a"] for r in regular if r["donnees_jusqu_a"]})

    insights = []
    if status == "desservie":
        names = " et ".join(r["iata"] for r in paris_regular)
        if paris_masked:
            insights.append(f"Paris dessert déjà {city} depuis {names}, mais Eurostat masque les volumes de cette "
                            "liaison : la part de Paris ne peut pas être calculée sur les données publiques.")
        else:
            insights.append(f"Paris dessert déjà {city} depuis {names} : {fmt_int(paris_pax)} passagers sur "
                            f"12 mois, soit {fmt_pct(share)} du trafic observé depuis Paris et les grands hubs.")
        if rank:
            insights.append(f"Paris se classe {rank}{'er' if rank == 1 else 'e'} sur {len(regular)} origines "
                            "européennes observées vers cette destination.")
    else:
        if hubs_regular:
            top = hubs_regular[0]
            insights.append(f"Paris ne dessert pas {city} en vol régulier. {len(hubs_regular)} hub(s) européen(s) la "
                            f"relient, pour {fmt_int(total)} passagers sur 12 mois ; le premier, {top['ville'] or top['iata']}, "
                            f"en porte {fmt_pct(top['pax_l12'] / total if total else None)}.")
        else:
            insights.append(f"Ni Paris ni les 16 grands hubs européens observés ne relient {city} en vol régulier "
                            "sur la dernière année publiée.")
    if growth is not None:
        insights.append(f"Le trafic total observé évolue de {fmt_pct_signed(growth)} sur un an.")
    if status == "opportunite":
        score = f"{opportunity.get('opportunity_score') or 0:.1f}".replace(".", ",")
        insights.append(f"La destination figure au radar d'opportunités : score de {score} / 100 "
                        f"en {opportunity.get('segment')}.")
    elif status == "non_desservie" and hubs_regular:
        insights.append("Elle n'entre pas au radar : trafic des hubs inférieur au seuil de 50 000 passagers, "
                        "destination en France, ou ville déjà desservie depuis Paris par un autre aéroport.")
    if health:
        label = HEALTH_LABELS.get(health.get("alert"), health.get("alert"))
        insights.append(f"Santé de la ligne CDG : {label}.")
    if ends:
        insights.append(f"Données publiées jusqu'à {fmt_month(ends[-1] + '-01')} selon les pays déclarants.")

    return {
        "iata": iata,
        "icao": (airport or {}).get("icao") or (opportunity or {}).get("partner_icao"),
        "aeroport": (airport or {}).get("airport_name"),
        "ville": city,
        "pays": (airport or {}).get("country_iso2") or (opportunity or {}).get("partner_country"),
        "lat": _num((airport or {}).get("lat")),
        "lon": _num((airport or {}).get("lon")),
        "distance_km": distance,
        "statut": status,
        "trafic_total_l12": total,
        "trafic_total_p12": total_prev,
        "croissance": growth,
        "paris": {"pax_l12": paris_pax, "part": share, "rang": rank, "masque": paris_masked,
                  "aeroports": [r["iata"] for r in paris_regular]},
        "origines": rows,
        "mensuel": [{"mois": m["month"], "paris": int(m.get("paris") or 0), "hubs": int(m.get("hubs") or 0),
                     "paris_masque": int(m.get("paris_masked") or 0) > 0} for m in monthly],
        "opportunite": ({k: opportunity.get(k) for k in ["opportunity_score", "segment", "hubs_list",
                                                         "pax_l12_hubs", "growth_hubs", "lf_l12_hubs"]}
                        if opportunity else None),
        "sante": ({k: health.get(k) for k in ["alert", "pax_l12", "lf_l12", "lf_delta_pts", "growth_pax",
                                              "growth_seats", "flights_l12", "segment"]} if health else None),
        "lecture": insights,
        "scenario": default_scenario(distance),
        "dossier": None,
    }


def study_live(source, iata: str) -> dict:
    """Étude en direct sur BigQuery. Retourne aussi les requêtes exécutées."""
    iata = iata.upper()
    source.take_jobs()
    airport = source.airport(iata)
    origins = source.market_origins(iata)
    if not airport and not origins:
        return {"iata": iata, "introuvable": True, "requetes": source.take_jobs()}
    study = build_study(iata, airport, origins, source.market_monthly(iata), source.opportunity(iata),
                        source.cdg_health(iata))
    study["requetes"] = source.take_jobs()
    study["source"] = "BigQuery en direct"
    return study
