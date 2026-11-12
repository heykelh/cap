"""Compte de résultat annuel d'une ligne, transparent et traçable.

Conventions :
  * une fréquence = un aller-retour par semaine (donc 2 vols) ;
  * distance orthodromique (grand cercle), comme les statistiques de trafic aérien ;
  * siège-km (SKO / ASK) = sièges offerts x distance ;
  * passager-km (PKT / RPK) = sièges-km x taux de remplissage.

Chaque résultat garde la formule et les valeurs utilisées (trace), pour que
l'analyste et l'agent Rédacteur puissent justifier chaque chiffre.
"""
from dataclasses import dataclass, field, replace

from .assumptions import Assumptions


@dataclass(frozen=True)
class RouteInputs:
    origin: str
    destination: str
    distance_km: float
    frequencies_per_week: float
    seats_per_flight: int
    load_factor: float
    yield_eur_per_rpk: float
    cost_eur_per_ask: float
    fuel_eur_per_ask: float
    weeks_per_year: float = 52
    fuel_price_change: float = 0.0
    market_pax_per_year: float | None = None
    aircraft: str = ""

    def validate(self) -> None:
        checks = {
            "distance_km": self.distance_km > 0,
            "frequencies_per_week": self.frequencies_per_week > 0,
            "seats_per_flight": self.seats_per_flight > 0,
            "load_factor": 0 < self.load_factor <= 1,
            "yield_eur_per_rpk": self.yield_eur_per_rpk > 0,
            "cost_eur_per_ask": self.cost_eur_per_ask > 0,
            "fuel_eur_per_ask": 0 <= self.fuel_eur_per_ask <= self.cost_eur_per_ask,
            "weeks_per_year": 0 < self.weeks_per_year <= 53,
            "fuel_price_change": self.fuel_price_change > -1,
        }
        bad = [name for name, ok in checks.items() if not ok]
        if bad:
            raise ValueError(f"Valeurs invalides : {bad}")


@dataclass
class RouteResult:
    inputs: RouteInputs
    flights_per_year: float
    seats_per_year: float
    ask: float
    rpk: float
    passengers_per_year: float
    revenue_eur: float
    fuel_cost_eur: float
    other_cost_eur: float
    total_cost_eur: float
    operating_result_eur: float
    operating_margin: float
    breakeven_load_factor: float
    rask_eur: float
    cask_eur: float
    required_market_share: float | None
    trace: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "route": f"{self.inputs.origin}-{self.inputs.destination}",
            "vols_par_an": round(self.flights_per_year),
            "sieges_par_an": round(self.seats_per_year),
            "passagers_par_an": round(self.passengers_per_year),
            "recette_meur": round(self.revenue_eur / 1e6, 1),
            "couts_meur": round(self.total_cost_eur / 1e6, 1),
            "resultat_meur": round(self.operating_result_eur / 1e6, 1),
            "marge_pct": round(self.operating_margin * 100, 1),
            "remplissage_equilibre_pct": round(self.breakeven_load_factor * 100, 1),
            "part_de_marche_necessaire_pct": (
                None if self.required_market_share is None else round(self.required_market_share * 100, 1)
            ),
        }


def inputs_from_assumptions(
    a: Assumptions,
    origin: str,
    destination: str,
    distance_km: float,
    frequencies_per_week: float,
    aircraft: str,
    *,
    load_factor: float | None = None,
    region: str | None = None,
    weeks_per_year: float | None = None,
    seats_per_flight: int | None = None,
    market_pax_per_year: float | None = None,
    fuel_price_change: float = 0.0,
) -> RouteInputs:
    """Construit les entrées à partir des hypothèses sourcées, avec surcharges possibles."""
    if load_factor is None:
        load_factor = a.load_factor_by_region.get(region, a["load_factor"].value) if region else a["load_factor"].value
    return RouteInputs(
        origin=origin,
        destination=destination,
        distance_km=distance_km,
        frequencies_per_week=frequencies_per_week,
        seats_per_flight=seats_per_flight or a.seats(aircraft),
        load_factor=load_factor,
        yield_eur_per_rpk=a["yield_eur_per_rpk"].value,
        cost_eur_per_ask=a["cost_eur_per_ask"].value,
        fuel_eur_per_ask=a["fuel_eur_per_ask"].value,
        weeks_per_year=weeks_per_year or a["weeks_per_year"].value,
        fuel_price_change=fuel_price_change,
        market_pax_per_year=market_pax_per_year,
        aircraft=aircraft,
    )


def evaluate_route(x: RouteInputs) -> RouteResult:
    x.validate()
    trace: list[dict] = []

    def step(name: str, formula: str, value: float) -> float:
        trace.append({"indicateur": name, "formule": formula, "valeur": value})
        return value

    flights = step("Vols par an", f"2 x {x.frequencies_per_week} fréquences x {x.weeks_per_year} semaines",
                   2 * x.frequencies_per_week * x.weeks_per_year)
    seats = step("Sièges par an", f"{flights:.0f} vols x {x.seats_per_flight} sièges", flights * x.seats_per_flight)
    ask = step("Sièges-km", f"{seats:.0f} sièges x {x.distance_km:.0f} km", seats * x.distance_km)
    rpk = step("Passagers-km", f"sièges-km x remplissage {x.load_factor:.3f}", ask * x.load_factor)
    pax = step("Passagers par an", f"sièges x remplissage {x.load_factor:.3f}", seats * x.load_factor)
    revenue = step("Recette (€)", f"passagers-km x {x.yield_eur_per_rpk} €", rpk * x.yield_eur_per_rpk)

    fuel_per_ask = x.fuel_eur_per_ask * (1 + x.fuel_price_change)
    other_per_ask = x.cost_eur_per_ask - x.fuel_eur_per_ask
    fuel = step("Carburant (€)", f"sièges-km x {fuel_per_ask:.4f} € (variation prix {x.fuel_price_change:+.0%})",
                ask * fuel_per_ask)
    other = step("Autres coûts (€)", f"sièges-km x {other_per_ask:.4f} €", ask * other_per_ask)
    cost = step("Coûts totaux (€)", "carburant + autres coûts", fuel + other)
    result = step("Résultat d'exploitation (€)", "recette - coûts", revenue - cost)
    margin = step("Marge d'exploitation", "résultat / recette", result / revenue)
    cask = cost / ask
    breakeven = step("Remplissage d'équilibre", f"coût par siège-km {cask:.4f} / yield {x.yield_eur_per_rpk}",
                     cask / x.yield_eur_per_rpk)

    share = None
    if x.market_pax_per_year:
        share = step("Part de marché nécessaire",
                     f"passagers {pax:.0f} / marché estimé {x.market_pax_per_year:.0f}",
                     pax / x.market_pax_per_year)

    return RouteResult(
        inputs=x,
        flights_per_year=flights,
        seats_per_year=seats,
        ask=ask,
        rpk=rpk,
        passengers_per_year=pax,
        revenue_eur=revenue,
        fuel_cost_eur=fuel,
        other_cost_eur=other,
        total_cost_eur=cost,
        operating_result_eur=result,
        operating_margin=margin,
        breakeven_load_factor=breakeven,
        rask_eur=revenue / ask,
        cask_eur=cask,
        required_market_share=share,
        trace=trace,
    )


# Variations testées : remplissage en points, autres en pourcentage.
SENSITIVITIES = [
    ("Remplissage -5 pts / +5 pts", "load_factor", -0.05, 0.05, "points"),
    ("Yield -10 % / +10 %", "yield_eur_per_rpk", -0.10, 0.10, "pct"),
    ("Coût hors carburant -5 % / +5 %", "other_cost", -0.05, 0.05, "pct"),
    ("Prix du carburant -20 % / +20 %", "fuel_price_change", -0.20, 0.20, "abs"),
]


def _shift(x: RouteInputs, field_name: str, delta: float, mode: str) -> RouteInputs:
    if field_name == "load_factor":
        return replace(x, load_factor=min(1.0, max(0.01, x.load_factor + delta)))
    if field_name == "yield_eur_per_rpk":
        return replace(x, yield_eur_per_rpk=x.yield_eur_per_rpk * (1 + delta))
    if field_name == "other_cost":
        other = (x.cost_eur_per_ask - x.fuel_eur_per_ask) * (1 + delta)
        return replace(x, cost_eur_per_ask=other + x.fuel_eur_per_ask)
    if field_name == "fuel_price_change":
        return replace(x, fuel_price_change=x.fuel_price_change + delta)
    raise ValueError(field_name)


def sensitivity(x: RouteInputs) -> list[dict]:
    """Effet de chaque hypothèse sur le résultat d'exploitation (diagramme en tornade)."""
    base = evaluate_route(x).operating_result_eur
    rows = []
    for label, field_name, low, high, mode in SENSITIVITIES:
        r_low = evaluate_route(_shift(x, field_name, low, mode)).operating_result_eur
        r_high = evaluate_route(_shift(x, field_name, high, mode)).operating_result_eur
        rows.append({
            "hypothese": label,
            "resultat_bas_meur": round(r_low / 1e6, 1),
            "resultat_haut_meur": round(r_high / 1e6, 1),
            "amplitude_meur": round(abs(r_high - r_low) / 1e6, 1),
            "resultat_base_meur": round(base / 1e6, 1),
        })
    return sorted(rows, key=lambda r: r["amplitude_meur"], reverse=True)
