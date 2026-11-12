"""Tests du modèle économique : formules, cohérence, garde-fous."""
import json

import pytest

from economics import evaluate_route, load_assumptions, sensitivity
from economics.model import RouteInputs, inputs_from_assumptions


@pytest.fixture
def a():
    return load_assumptions()


@pytest.fixture
def base(a):
    return inputs_from_assumptions(a, "CDG", "MNL", 10733, 3, "A350-900", market_pax_per_year=339958)


def test_every_assumption_is_sourced(a):
    for key, item in a.items.items():
        assert item.source, key
        assert item.method, key


def test_breakeven_is_cost_over_yield(a, base):
    r = evaluate_route(base)
    expected = a["cost_eur_per_ask"].value / a["yield_eur_per_rpk"].value
    assert r.breakeven_load_factor == pytest.approx(expected)


def test_result_is_zero_at_breakeven(base):
    r = evaluate_route(base)
    at_be = evaluate_route(RouteInputs(**{**base.__dict__, "load_factor": r.breakeven_load_factor}))
    assert at_be.operating_result_eur == pytest.approx(0, abs=1)


def test_volumes(base):
    r = evaluate_route(base)
    assert r.flights_per_year == 2 * 3 * 52
    assert r.seats_per_year == 312 * 324
    assert r.ask == pytest.approx(r.seats_per_year * 10733)
    assert r.passengers_per_year == pytest.approx(r.seats_per_year * base.load_factor)


def test_costs_add_up(base):
    r = evaluate_route(base)
    assert r.fuel_cost_eur + r.other_cost_eur == pytest.approx(r.total_cost_eur)
    assert r.revenue_eur - r.total_cost_eur == pytest.approx(r.operating_result_eur)


def test_doubling_frequency_doubles_everything(base):
    r1 = evaluate_route(base)
    r2 = evaluate_route(RouteInputs(**{**base.__dict__, "frequencies_per_week": 6}))
    assert r2.operating_result_eur == pytest.approx(2 * r1.operating_result_eur)
    assert r2.breakeven_load_factor == pytest.approx(r1.breakeven_load_factor)


def test_fuel_price_increase_lowers_result(base):
    r = evaluate_route(base)
    up = evaluate_route(RouteInputs(**{**base.__dict__, "fuel_price_change": 0.2}))
    assert up.operating_result_eur < r.operating_result_eur
    assert up.breakeven_load_factor > r.breakeven_load_factor


def test_market_share(base):
    r = evaluate_route(base)
    assert r.required_market_share == pytest.approx(r.passengers_per_year / 339958)


def test_region_load_factor(a):
    x = inputs_from_assumptions(a, "CDG", "ACC", 4833, 3, "B787-9", region="Afrique")
    assert x.load_factor == a.load_factor_by_region["Afrique"]


def test_sensitivity_sorted_and_signed(base):
    rows = sensitivity(base)
    amplitudes = [r["amplitude_meur"] for r in rows]
    assert amplitudes == sorted(amplitudes, reverse=True)
    lf = next(r for r in rows if r["hypothese"].startswith("Remplissage"))
    assert lf["resultat_haut_meur"] > lf["resultat_bas_meur"]
    fuel = next(r for r in rows if r["hypothese"].startswith("Prix du carburant"))
    assert fuel["resultat_haut_meur"] < fuel["resultat_bas_meur"]


def test_trace_is_complete_and_serializable(base):
    r = evaluate_route(base)
    names = {t["indicateur"] for t in r.trace}
    for needed in ["Recette (€)", "Coûts totaux (€)", "Remplissage d'équilibre", "Part de marché nécessaire"]:
        assert needed in names
    json.dumps(r.trace, ensure_ascii=False)


@pytest.mark.parametrize("field,value", [
    ("distance_km", 0), ("frequencies_per_week", -1), ("load_factor", 1.2), ("seats_per_flight", 0),
])
def test_invalid_inputs_are_rejected(base, field, value):
    with pytest.raises(ValueError):
        evaluate_route(RouteInputs(**{**base.__dict__, field: value}))


def test_unknown_aircraft(a):
    with pytest.raises(KeyError):
        inputs_from_assumptions(a, "CDG", "MNL", 10733, 3, "A380")
