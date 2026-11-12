"""Faits déterministes : tout ce qui est chiffré est calculé ici, jamais par un LLM.

Chaque fait entre dans un catalogue { clé: valeur formatée en français }.
Le rédacteur écrit avec des balises {{clé}} ; le code les remplace par ces valeurs.
"""
import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

WATCHLIST_PATH = Path(__file__).resolve().parents[1] / "reference" / "market_watchlist.csv"


# --- Formatage français -------------------------------------------------------

def fmt_int(x) -> str:
    return "n.d." if x is None else f"{round(x):,}".replace(",", " ")


def fmt_pct(x, digits=1) -> str:
    return "n.d." if x is None else f"{x * 100:.{digits}f} %".replace(".", ",")


def fmt_pct_signed(x, digits=1) -> str:
    return "n.d." if x is None else f"{x * 100:+.{digits}f} %".replace(".", ",")


def fmt_pts(x) -> str:
    return "n.d." if x is None else f"{x * 100:+.1f} pts".replace(".", ",")


def fmt_meur(x) -> str:
    return "n.d." if x is None else f"{x / 1e6:.1f} M€".replace(".", ",")


def fmt_km(x) -> str:
    return "n.d." if x is None else f"{fmt_int(x)} km"


def fmt_month(x) -> str:
    if not x:
        return "n.d."
    d = date.fromisoformat(str(x)[:10])
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre"]
    return f"{mois[d.month - 1]} {d.year}"


# --- Catalogue ---------------------------------------------------------------

@dataclass
class Fact:
    key: str
    value: str
    label: str
    source: str


class Catalog:
    def __init__(self):
        self.facts: dict[str, Fact] = {}

    def add(self, key: str, value: str, label: str, source: str) -> None:
        if not re.fullmatch(r"[a-z0-9_]+", key):
            raise ValueError(f"Clé de fait invalide : {key}")
        self.facts[key] = Fact(key, value, label, source)

    def values(self) -> dict[str, str]:
        return {k: f.value for k, f in self.facts.items()}

    def describe(self, keys: list[str] | None = None) -> str:
        """Liste lisible par un LLM : balise, signification (jamais la valeur)."""
        keys = keys or list(self.facts)
        return "\n".join(f"{{{{{k}}}}} : {self.facts[k].label}" for k in keys if k in self.facts)

    def keys_with_prefix(self, prefix: str) -> list[str]:
        return [k for k in self.facts if k.startswith(prefix)]


# --- Faits par étape ---------------------------------------------------------

def scout_facts(cat: Catalog, dest: str, opp: dict | None, src: str) -> None:
    cat.add("destination", dest, "code IATA de la destination", "requête")
    if not opp:
        cat.add("radar_statut", "absente du radar", "statut de la destination dans le radar", src)
        return
    cat.add("ville", opp.get("partner_city") or dest, "ville de destination", src)
    cat.add("pays", opp.get("partner_country") or "n.d.", "code pays de la destination", src)
    cat.add("segment", opp.get("segment") or "n.d.", "segment (court, moyen, long-courrier)", src)
    cat.add("score", f"{opp.get('opportunity_score', 0):.1f} / 100".replace(".", ","),
            "score d'opportunité du radar, calculé dans le segment", src)
    cat.add("distance", fmt_km(opp.get("distance_from_cdg_km")), "distance orthodromique depuis CDG", src)
    cat.add("radar_statut", "classée au radar", "statut de la destination dans le radar", src)
    comps = [("volume", "s_volume"), ("croissance", "s_growth"), ("remplissage", "s_lf"), ("hubs", "s_hubs")]
    for name, col in comps:
        if opp.get(col) is not None:
            cat.add(f"rang_{name}", fmt_pct(opp[col], 0),
                    f"rang centile de la destination sur le critère {name} dans son segment", src)


def market_facts(cat: Catalog, opp: dict | None, flows: list[dict], src: str) -> dict:
    pax = sum(f.get("pax_l12") or 0 for f in flows)
    pax_prev = sum(f.get("pax_p12") or 0 for f in flows)
    growth = (pax / pax_prev - 1) if pax_prev >= 1000 else None
    top_share = (flows[0]["pax_l12"] / pax) if flows and pax else None
    ends = sorted({str(f.get("window_end"))[:10] for f in flows if f.get("window_end")})
    cat.add("marche_pax", fmt_int(pax), "passagers sur 12 mois entre les hubs concurrents et la destination", src)
    cat.add("marche_croissance", fmt_pct_signed(growth), "évolution de ce trafic sur un an", src)
    cat.add("nb_hubs", fmt_int(len(flows)), "nombre de hubs européens qui desservent la destination", src)
    cat.add("part_premier_hub", fmt_pct(top_share), "part du premier hub dans ce trafic", src)
    if flows:
        cat.add("premier_hub", flows[0].get("rep_city") or flows[0].get("rep_iata"), "premier hub concurrent", src)
    cat.add("donnees_jusqu_a", fmt_month(ends[-1]) if ends else "n.d.", "dernier mois de données publié", src)
    for i, f in enumerate(flows[:5], start=1):
        cat.add(f"hub{i}_nom", f.get("rep_city") or f.get("rep_iata") or f.get("rep_icao"), f"hub concurrent n°{i}", src)
        cat.add(f"hub{i}_pax", fmt_int(f.get("pax_l12")), f"passagers sur 12 mois du hub n°{i}", src)
        cat.add(f"hub{i}_croissance", fmt_pct_signed(f.get("growth_pax")), f"évolution sur un an du hub n°{i}", src)
        cat.add(f"hub{i}_remplissage", fmt_pct(f.get("lf_l12")), f"remplissage du hub n°{i}", src)
    return {"pax": pax, "growth": growth, "top_share": top_share, "n_hubs": len(flows),
            "last_month": ends[-1] if ends else None}


def competition_facts(cat: Catalog, opp: dict | None, paris_hubs: list[dict], src: str) -> dict:
    feed = sum(r.get("pax_l12") or 0 for r in paris_hubs)
    masked = [r for r in paris_hubs if (r.get("masked_months_l12") or 0) >= 6]
    cat.add("paris_vers_hubs_pax", fmt_int(feed),
            "passagers CDG vers ces hubs sur 12 mois (clients potentiels en correspondance)", src)
    cat.add("paris_vers_hubs_masques", fmt_int(len(masked)), "liaisons CDG-hub dont les volumes sont masqués", src)
    for i, r in enumerate(paris_hubs[:5], start=1):
        cat.add(f"liaison{i}_hub", r.get("partner_city") or r.get("partner_iata"), f"hub relié à CDG n°{i}", src)
        cat.add(f"liaison{i}_pax", fmt_int(r.get("pax_l12")), f"passagers CDG vers le hub n°{i}", src)
    cdg = (opp or {}).get("cdg_flights_l12") or 0
    cat.add("cdg_vols_actuels", fmt_int(cdg), "vols CDG vers la destination sur 12 mois", src)
    return {"feed": feed, "masked": len(masked), "cdg_flights": cdg}


def economics_facts(cat: Catalog, result, sens: list[dict], assumptions, region: str | None) -> None:
    src = f"Modèle CAP, hypothèses {assumptions.version}"
    x = result.inputs
    cat.add("frequences", fmt_int(x.frequencies_per_week), "allers-retours par semaine", "requête")
    cat.add("appareil", x.aircraft or "n.d.", "type d'appareil", "requête")
    cat.add("sieges", fmt_int(x.seats_per_flight), "sièges par vol", assumptions.aircraft.get(x.aircraft, {}).get("source", src))
    cat.add("semaines", fmt_int(x.weeks_per_year), "semaines d'exploitation par an", src)
    cat.add("region_remplissage", region or "moyenne long-courrier", "référence de remplissage utilisée", src)
    cat.add("vols_an", fmt_int(result.flights_per_year), "vols par an", src)
    cat.add("passagers_an", fmt_int(result.passengers_per_year), "passagers par an", src)
    cat.add("recette_meur", fmt_meur(result.revenue_eur), "recette annuelle", src)
    cat.add("couts_meur", fmt_meur(result.total_cost_eur), "coûts annuels", src)
    cat.add("carburant_meur", fmt_meur(result.fuel_cost_eur), "dont carburant", src)
    cat.add("resultat_meur", fmt_meur(result.operating_result_eur), "résultat d'exploitation annuel", src)
    cat.add("marge", fmt_pct(result.operating_margin), "marge d'exploitation", src)
    cat.add("remplissage_vise", fmt_pct(x.load_factor), "remplissage visé", src)
    cat.add("remplissage_equilibre", fmt_pct(result.breakeven_load_factor), "remplissage d'équilibre", src)
    cat.add("marge_securite", fmt_pts(x.load_factor - result.breakeven_load_factor),
            "écart entre remplissage visé et équilibre", src)
    cat.add("part_marche", fmt_pct(result.required_market_share), "part du trafic des hubs concurrents à capter", src)
    for s in sens:
        key = {"Remplissage": "sens_remplissage", "Yield": "sens_yield", "Coût hors": "sens_couts",
               "Prix du ca": "sens_carburant"}[next(p for p in ["Remplissage", "Yield", "Coût hors", "Prix du ca"]
                                                    if s["hypothese"].startswith(p))]
        cat.add(f"{key}_bas", f"{s['resultat_bas_meur']:.1f} M€".replace(".", ","), f"{s['hypothese']} : scénario bas", src)
        cat.add(f"{key}_haut", f"{s['resultat_haut_meur']:.1f} M€".replace(".", ","), f"{s['hypothese']} : scénario haut", src)
    a = assumptions
    cat.add("hyp_yield", f"{a['yield_eur_per_rpk'].value * 100:.2f} c€".replace(".", ","),
            "recette par passager-km utilisée", a["yield_eur_per_rpk"].source)
    cat.add("hyp_cask", f"{a['cost_eur_per_ask'].value * 100:.2f} c€".replace(".", ","),
            "coût par siège-km utilisé", a["cost_eur_per_ask"].source)


# --- Signaux de l'avocat du diable (règles, pas d'IA) --------------------------

def load_watchlist(path: Path = WATCHLIST_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {r["country"].strip().upper(): r["reason"].strip() for r in csv.DictReader(fh) if r.get("country")}


def red_flags(cat: Catalog, *, opp, market, competition, result, sens, overrides, today: date,
              watchlist: dict[str, str]) -> list[dict]:
    flags = []

    def flag(code, severity, text):
        flags.append({"code": code, "gravite": severity, "texte": text})

    share = result.required_market_share
    if share is not None and share > 0.20:
        flag("part_marche_elevee", "haute",
             "Il faut capter {{part_marche}} du trafic que les hubs concurrents réalisent déjà.")
    if result.operating_margin < 0:
        flag("deficitaire", "haute", "La ligne est déficitaire au remplissage visé ({{resultat_meur}}).")
    elif result.operating_margin < 0.05:
        flag("marge_fine", "moyenne", "La marge est fine : {{marge}}, soit {{marge_securite}} au-dessus de l'équilibre.")
    yield_row = next((s for s in sens if s["hypothese"].startswith("Yield")), None)
    if yield_row and yield_row["resultat_bas_meur"] < 0 <= result.operating_result_eur:
        flag("dependance_yield", "haute",
             "Une recette inférieure de 10 % fait basculer la ligne en perte ({{sens_yield_bas}}).")
    if result.inputs.distance_km > 9000:
        flag("yield_long_courrier", "moyenne",
             "Le modèle utilise la recette moyenne du réseau ({{hyp_yield}} par passager-km) : sur une ligne de "
             "{{distance}}, la recette par kilomètre est en général inférieure. Résultat probablement optimiste.")
    if market["n_hubs"] == 1:
        flag("hub_unique", "moyenne", "La demande observée passe par un seul hub concurrent ({{premier_hub}}).")
    elif market["top_share"] is not None and market["top_share"] > 0.7:
        flag("hub_dominant", "moyenne", "{{premier_hub}} concentre {{part_premier_hub}} du trafic observé.")
    if market["growth"] is not None and market["growth"] < 0:
        flag("demande_en_baisse", "haute", "Le trafic des hubs concurrents recule sur un an ({{marche_croissance}}).")
    if market["last_month"]:
        age = (today - date.fromisoformat(market["last_month"])).days / 30.4
        if age > 12:
            flag("donnees_anciennes", "moyenne",
                 "Les données s'arrêtent à {{donnees_jusqu_a}} : à confirmer sur des données récentes.")
    if competition["masked"]:
        flag("donnees_masquees", "basse",
             "{{paris_vers_hubs_masques}} liaison(s) CDG-hub ont des volumes masqués par Eurostat.")
    if competition["cdg_flights"]:
        flag("desserte_marginale", "basse", "CDG a déjà {{cdg_vols_actuels}} vols vers cette destination sur 12 mois.")
    country = ((opp or {}).get("partner_country") or "").upper()
    if country in watchlist:
        flag("marche_surveille", "haute", f"Marché signalé par l'analyste : {watchlist[country]}.")
    for o in overrides:
        if o.get("status") == "a_verifier":
            flag("desserte_a_verifier", "moyenne",
                 "La desserte actuelle de Paris vers cette destination est encore à vérifier par l'analyste.")
    for i, f in enumerate(flags, start=1):
        cat.add(f"alerte{i}", f["texte"], f"alerte n°{i} ({f['gravite']})", "règles CAP")
    return flags
