"""Outils mis à la disposition des agents IA.

Un agent IA choisit lui-même quels outils appeler, avec quels paramètres et dans quel ordre.
Les outils, eux, sont déterministes : requêtes BigQuery paramétrées et modèle économique.

Règle de traçabilité : chaque chiffre renvoyé par un outil reçoit une référence ({{f1}}, {{f2}}…).
L'agent voit la valeur pour raisonner, mais ne peut la citer dans sa réponse que par sa référence.
Le garde-fou rejette tout chiffre écrit à la main ; le code remplace ensuite les références.
"""
import json
import time
from dataclasses import replace

from economics import evaluate_route, sensitivity
from economics.model import inputs_from_assumptions

from .batch import COUNTRY_TO_REGION
from .facts import fmt_int, fmt_pct, fmt_pct_signed
from .market import build_study, study_live

SQL_SEARCH = """SELECT partner_iata, partner_city, partner_country, segment, opportunity_score,
       distance_from_cdg_km, pax_l12_hubs, growth_hubs, lf_l12_hubs, hubs_list, hubs_serving
FROM `cap_gold.opportunities`
WHERE partner_iata IS NOT NULL
  AND (@segment IS NULL OR segment = @segment)
  AND distance_from_cdg_km BETWEEN @dmin AND @dmax
ORDER BY opportunity_score DESC
LIMIT 200"""

TOOL_SPECS = [
    {
        "name": "chercher_destinations",
        "description": "Cherche dans le radar les destinations que Paris CDG ne dessert pas mais que les grands hubs "
                       "européens desservent, classées par score d'opportunité. Filtres facultatifs.",
        "parameters": {
            "type": "object",
            "properties": {
                "segment": {"type": "string", "enum": ["long-courrier", "moyen-courrier"]},
                "region": {"type": "string", "enum": list({r for r in COUNTRY_TO_REGION.values()})},
                "pays": {"type": "array", "items": {"type": "string"}, "description": "codes ISO à deux lettres, ex. PH"},
                "distance_min_km": {"type": "number"},
                "distance_max_km": {"type": "number"},
                "limite": {"type": "integer", "minimum": 1, "maximum": 10},
            },
        },
    },
    {
        "name": "etude_marche",
        "description": "Étude de marché d'une destination (code IATA), que Paris la desserve ou non : trafic de Paris "
                       "et des 16 grands hubs européens sur 12 mois, part et rang de Paris, évolution, premiers hubs, "
                       "santé de la ligne si elle existe, score au radar sinon.",
        "parameters": {"type": "object", "properties": {"iata": {"type": "string"}}, "required": ["iata"]},
    },
    {
        "name": "simuler_ligne",
        "description": "Compte de résultat annuel d'une ligne Paris CDG vers la destination, avec le modèle CAP "
                       "(hypothèses du communiqué Air France-KLM 2025). Permet de tester fréquence, appareil, "
                       "remplissage, prix des billets, carburant, saisonnalité.",
        "parameters": {
            "type": "object",
            "properties": {
                "iata": {"type": "string"},
                "frequences_par_semaine": {"type": "number", "minimum": 1, "maximum": 14},
                "appareil": {"type": "string", "enum": ["A350-900", "B787-9", "B777-300ER", "B777-200ER"]},
                "remplissage": {"type": "number", "minimum": 0.5, "maximum": 0.98,
                                "description": "part des sièges occupés, ex. 0.85 ; par défaut la moyenne de la région"},
                "variation_recette_pct": {"type": "number", "minimum": -40, "maximum": 40},
                "variation_carburant_pct": {"type": "number", "minimum": -50, "maximum": 80},
                "semaines_par_an": {"type": "number", "minimum": 8, "maximum": 52},
            },
            "required": ["iata", "frequences_par_semaine", "appareil"],
        },
    },
    {
        "name": "sensibilites",
        "description": "Classe les hypothèses qui font le plus varier le résultat d'une ligne (remplissage, prix des "
                       "billets, coûts, carburant), pour un scénario donné.",
        "parameters": {
            "type": "object",
            "properties": {
                "iata": {"type": "string"},
                "frequences_par_semaine": {"type": "number", "minimum": 1, "maximum": 14},
                "appareil": {"type": "string", "enum": ["A350-900", "B787-9", "B777-300ER", "B777-200ER"]},
            },
            "required": ["iata", "frequences_par_semaine", "appareil"],
        },
    },
]
TOOL_NAMES = {t["name"] for t in TOOL_SPECS}


class ToolError(ValueError):
    pass


class ToolBox:
    """Exécute les outils et tient le registre des chiffres cités par référence."""

    def __init__(self, source, assumptions):
        self.source = source
        self.a = assumptions
        self.facts: dict[str, dict] = {}
        self._studies: dict[str, dict] = {}
        self._extra_jobs: list[dict] = []
        self.stats = {"appels": 0, "requetes": 0, "octets": 0}

    # --- registre des chiffres -------------------------------------------------------

    def ref(self, valeur: str, libelle: str, outil: str) -> dict:
        for key, f in self.facts.items():  # même chiffre, même libellé : même référence
            if f["valeur"] == valeur and f["libelle"] == libelle:
                return {"valeur": valeur, "ref": "{{" + key + "}}"}
        key = f"f{len(self.facts) + 1}"
        self.facts[key] = {"valeur": valeur, "libelle": libelle, "outil": outil}
        return {"valeur": valeur, "ref": "{{" + key + "}}"}

    def values(self) -> dict[str, str]:
        return {k: f["valeur"] for k, f in self.facts.items()}

    # --- exécution -----------------------------------------------------------------

    def run(self, name: str, args: dict) -> tuple[dict, list[dict], int]:
        """Retourne (résultat pour l'agent, requêtes BigQuery exécutées, durée en ms)."""
        if name not in TOOL_NAMES:
            raise ToolError(f"outil inconnu : {name}")
        started = time.perf_counter()
        self.source.take_jobs()
        try:
            result = getattr(self, name)(**args)
        except TypeError as exc:
            raise ToolError(f"paramètres invalides pour {name} : {exc}") from exc
        jobs, self._extra_jobs = self._extra_jobs + self.source.take_jobs(), []
        self.stats["appels"] += 1
        self.stats["requetes"] += sum(1 for j in jobs if j.get("execute_sur") == "BigQuery")
        self.stats["octets"] += sum(j.get("octets_lus") or 0 for j in jobs)
        return result, jobs, round((time.perf_counter() - started) * 1000)

    def _iata(self, iata) -> str:
        iata = str(iata or "").strip().upper()
        if not (len(iata) == 3 and iata.isalpha()):
            raise ToolError("code IATA attendu (trois lettres)")
        return iata

    def _study(self, iata: str) -> dict:
        if iata in self._studies:
            return self._studies[iata]
        if hasattr(self.source, "market_origins"):
            study = study_live(self.source, iata)
            self._extra_jobs.extend(study.pop("requetes", []))
        else:  # instantané : étude reconstituée à partir des flux des hubs
            opp = self.source.opportunity(iata)
            flows = self.source.hub_flows(iata)
            if not opp and not flows:
                study = {"introuvable": True}
            else:
                rows = [{**f, "rep_country": None, "seats_l12": None, "lf_p12": None} for f in flows]
                study = build_study(iata, None, rows, [], opp, None)
        if study.get("introuvable"):
            raise ToolError(f"aucune donnée pour {iata}")
        self._studies[iata] = study
        return study

    def _context(self, iata: str) -> tuple[float, float | None, str | None]:
        study = self._study(iata)
        if not study.get("distance_km"):
            raise ToolError(f"distance inconnue pour {iata}")
        country = study.get("pays")
        return float(study["distance_km"]), (study.get("trafic_total_l12") or None), COUNTRY_TO_REGION.get(
            (country or "").upper())

    # --- outils ----------------------------------------------------------------------

    def chercher_destinations(self, segment=None, region=None, pays=None, distance_min_km=0,
                              distance_max_km=20000, limite=6):
        limite = max(1, min(int(limite or 6), 10))
        if hasattr(self.source, "_query"):
            src = self.source
            rows = src._query(SQL_SEARCH, [src._s("segment", segment), src._bq.ScalarQueryParameter("dmin", "FLOAT64", float(distance_min_km or 0)),
                                           src._bq.ScalarQueryParameter("dmax", "FLOAT64", float(distance_max_km or 20000))],
                              "chercher_destinations")
        else:
            rows = [d["opportunity"] for d in self.source._data["destinations"].values() if d.get("opportunity")]
            rows = [r for r in rows if (not segment or r.get("segment") == segment)
                    and float(distance_min_km or 0) <= float(r.get("distance_from_cdg_km") or 0) <= float(distance_max_km or 20000)]
            rows.sort(key=lambda r: r.get("opportunity_score") or 0, reverse=True)
        if pays:
            wanted = {p.upper() for p in pays}
            rows = [r for r in rows if (r.get("partner_country") or "").upper() in wanted]
        if region:
            rows = [r for r in rows if COUNTRY_TO_REGION.get((r.get("partner_country") or "").upper()) == region]
        out = []
        for r in rows[:limite]:
            city = r.get("partner_city") or r["partner_iata"]
            out.append({
                "iata": r["partner_iata"], "ville": city, "pays": r.get("partner_country"), "segment": r.get("segment"),
                "score": self.ref(f"{r.get('opportunity_score') or 0:.1f}".replace(".", ",") + " / 100",
                                  f"score d'opportunité de {city}", "chercher_destinations"),
                "distance": self.ref(f"{fmt_int(r.get('distance_from_cdg_km'))} km", f"distance CDG-{city}",
                                     "chercher_destinations"),
                "passagers_hubs_12_mois": self.ref(fmt_int(r.get("pax_l12_hubs")),
                                                   f"passagers des hubs vers {city} sur 12 mois", "chercher_destinations"),
                "evolution": self.ref(fmt_pct_signed(r.get("growth_hubs")), f"évolution du trafic des hubs vers {city}",
                                      "chercher_destinations"),
                "hubs": r.get("hubs_list"),
            })
        return {"nombre_trouve": len(rows), "destinations": out}

    def etude_marche(self, iata):
        iata = self._iata(iata)
        s = self._study(iata)
        city = s["ville"]
        top = [o for o in s["origines"] if o["reguliere"]][:5]
        result = {
            "iata": iata, "ville": city, "pays": s.get("pays"),
            "statut": {"desservie": "desservie depuis Paris", "opportunite": "non desservie, au radar",
                       "non_desservie": "non desservie, hors radar"}[s["statut"]],
            "distance": self.ref(f"{fmt_int(s.get('distance_km'))} km", f"distance CDG-{city}", "etude_marche"),
            "trafic_total_12_mois": self.ref(fmt_int(s["trafic_total_l12"]),
                                             f"passagers Paris + hubs vers {city} sur 12 mois", "etude_marche"),
            "evolution_un_an": self.ref(fmt_pct_signed(s.get("croissance")), f"évolution du trafic vers {city}",
                                        "etude_marche"),
            "paris_passagers_12_mois": self.ref(fmt_int(s["paris"]["pax_l12"]), f"passagers Paris-{city} sur 12 mois",
                                                "etude_marche"),
            "part_de_paris": (self.ref(fmt_pct(s["paris"]["part"]), f"part de Paris vers {city}", "etude_marche")
                              if s["paris"]["part"] is not None else "non calculable (volumes masqués ou absents)"),
            "premieres_origines": [
                {"aeroport": o["iata"], "ville": o["ville"],
                 "passagers": self.ref(fmt_int(o["pax_l12"]), f"passagers {o['iata']}-{city} sur 12 mois", "etude_marche"),
                 "evolution": self.ref(fmt_pct_signed(o["croissance"]), f"évolution {o['iata']}-{city}", "etude_marche")}
                for o in top],
        }
        if s.get("opportunite"):
            result["score_radar"] = self.ref(
                f"{s['opportunite']['opportunity_score'] or 0:.1f}".replace(".", ",") + " / 100",
                f"score d'opportunité de {city}", "etude_marche")
        if s.get("sante"):
            result["sante_ligne_cdg"] = s["sante"].get("alert")
        return result

    def _inputs(self, iata, frequences_par_semaine, appareil, remplissage=None, variation_recette_pct=0,
                variation_carburant_pct=0, semaines_par_an=None):
        iata = self._iata(iata)
        if appareil not in self.a.aircraft:
            raise ToolError(f"appareil inconnu : {appareil}")
        distance, market, region = self._context(iata)
        x = inputs_from_assumptions(self.a, "CDG", iata, distance, float(frequences_par_semaine), appareil,
                                    load_factor=remplissage, region=region, weeks_per_year=semaines_par_an,
                                    market_pax_per_year=market, fuel_price_change=(variation_carburant_pct or 0) / 100)
        if variation_recette_pct:
            x = replace(x, yield_eur_per_rpk=x.yield_eur_per_rpk * (1 + variation_recette_pct / 100))
        return iata, x

    def simuler_ligne(self, iata, frequences_par_semaine, appareil, remplissage=None, variation_recette_pct=0,
                      variation_carburant_pct=0, semaines_par_an=None):
        iata, x = self._inputs(iata, frequences_par_semaine, appareil, remplissage, variation_recette_pct,
                               variation_carburant_pct, semaines_par_an)
        r = evaluate_route(x)
        label = (f"{iata}, {x.frequencies_per_week:g} A/R par semaine en {appareil}"
                 + (f", remplissage {x.load_factor:.0%}" if remplissage else "")
                 + (f", recette {variation_recette_pct:+g} %" if variation_recette_pct else "")
                 + (f", carburant {variation_carburant_pct:+g} %" if variation_carburant_pct else "")
                 + (f", {x.weeks_per_year:g} semaines" if semaines_par_an else ""))
        meur = lambda v: f"{v / 1e6:.1f}".replace(".", ",") + " M€"  # noqa: E731
        g = lambda v: f"{v:g}".replace(".", ",")  # noqa: E731
        params = {
            "appareil": appareil,
            "frequences_par_semaine": self.ref(g(x.frequencies_per_week), f"allers-retours par semaine ({label})", "simuler_ligne"),
            "vols_par_an": self.ref(fmt_int(2 * x.frequencies_per_week * x.weeks_per_year), f"vols par an ({label})", "simuler_ligne"),
            "semaines_par_an": self.ref(g(x.weeks_per_year), f"semaines d'exploitation ({label})", "simuler_ligne"),
        }
        if variation_recette_pct:
            params["variation_recette"] = self.ref(fmt_pct_signed(variation_recette_pct / 100), f"variation de la recette ({label})", "simuler_ligne")
        if variation_carburant_pct:
            params["variation_carburant"] = self.ref(fmt_pct_signed(variation_carburant_pct / 100), f"variation du carburant ({label})", "simuler_ligne")
        return {
            "scenario": label,
            "parametres": params,
            "passagers_par_an": self.ref(fmt_int(r.passengers_per_year), f"passagers par an ({label})", "simuler_ligne"),
            "recette": self.ref(meur(r.revenue_eur), f"recette annuelle ({label})", "simuler_ligne"),
            "couts": self.ref(meur(r.total_cost_eur), f"coûts annuels ({label})", "simuler_ligne"),
            "resultat_exploitation": self.ref(meur(r.operating_result_eur), f"résultat d'exploitation ({label})",
                                              "simuler_ligne"),
            "marge": self.ref(fmt_pct(r.operating_margin), f"marge ({label})", "simuler_ligne"),
            "remplissage_vise": self.ref(fmt_pct(x.load_factor), f"remplissage visé ({label})", "simuler_ligne"),
            "remplissage_equilibre": self.ref(fmt_pct(r.breakeven_load_factor), f"remplissage d'équilibre ({label})",
                                              "simuler_ligne"),
            "part_de_marche_a_capter": (self.ref(fmt_pct(r.required_market_share), f"part de marché à capter ({label})",
                                                 "simuler_ligne") if r.required_market_share is not None else "n.d."),
            "beneficiaire": r.operating_result_eur > 0,
        }

    def sensibilites(self, iata, frequences_par_semaine, appareil):
        iata, x = self._inputs(iata, frequences_par_semaine, appareil)
        rows = sensitivity(x)
        meur = lambda v: f"{v:.1f}".replace(".", ",") + " M€"  # noqa: E731
        return {"scenario": f"{iata}, {x.frequencies_per_week:g} A/R en {appareil}", "hypotheses_par_influence": [
            {"hypothese": s["hypothese"],
             "resultat_scenario_defavorable": self.ref(meur(s["resultat_bas_meur"]), f"résultat si {s['hypothese']} défavorable ({iata})", "sensibilites"),
             "resultat_scenario_favorable": self.ref(meur(s["resultat_haut_meur"]), f"résultat si {s['hypothese']} favorable ({iata})", "sensibilites")}
            for s in rows]}


def _compact(v):
    if isinstance(v, dict) and set(v) == {"valeur", "ref"}:
        return f"{v['valeur']} {v['ref']}"
    if isinstance(v, dict):
        return {k: _compact(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_compact(x) for x in v]
    return v


def tool_result_text(result: dict) -> str:
    """Résultat transmis au modèle : compact (chaque valeur suivie de sa référence) pour économiser le quota."""
    return json.dumps(_compact(result), ensure_ascii=False, default=str, separators=(",", ":"))

