"""Étude de marché et traçabilité des agents, sur données synthétiques."""
from datetime import date
from pathlib import Path

from agents.datasource import SnapshotSource
from agents.graph import run_dossier, stream_dossier
from agents.llm import OfflineLLM
from agents.market import build_study
from economics import load_assumptions

FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_synthetique.json"
REQ = {"dest": "MNL", "freq": 3, "aircraft": "A350-900", "region": "Asie et Moyen-Orient"}


def _row(rep, iata, city, pax, prev, flights=730, masked=0, lf=0.85):
    return {"rep_icao": rep, "rep_iata": iata, "rep_city": city, "rep_country": "XX", "pax_l12": pax,
            "pax_p12": prev, "flights_l12": flights, "seats_l12": int(pax / lf), "lf_l12": lf, "lf_p12": lf,
            "growth_pax": (pax / prev - 1) if prev else None, "masked_months_l12": masked, "window_end": "2024-12-01"}


AIRPORT = {"icao": "KJFK", "iata": "JFK", "airport_name": "John F. Kennedy", "city": "New York",
           "country_iso2": "US", "lat": 40.6, "lon": -73.8, "distance_from_cdg_km": 5837}


def test_destination_desservie_part_de_paris():
    rows = [_row("LFPG", "CDG", "Paris", 2_000_000, 1_800_000), _row("EGLL", "LHR", "Londres", 1, 1, flights=0),
            _row("EHAM", "AMS", "Amsterdam", 1_000_000, 1_000_000), _row("EDDF", "FRA", "Francfort", 1_000_000, 900_000)]
    s = build_study("jfk", AIRPORT, rows, [], None, {"alert": "ras", "pax_l12": 2_000_000})
    assert s["statut"] == "desservie"
    assert s["paris"]["part"] == 0.5 and s["paris"]["rang"] == 1
    assert s["trafic_total_l12"] == 4_000_000  # la ligne sans vol régulier est exclue du total
    assert any("Paris dessert déjà New York" in t for t in s["lecture"])
    assert s["scenario"]["aircraft"] == "B787-9"


def test_paris_masque_pas_de_part_inventee():
    rows = [_row("LFPG", "CDG", "Paris", 0, 0, flights=0, masked=12), _row("EHAM", "AMS", "Amsterdam", 500_000, 400_000)]
    s = build_study("ATL", {**AIRPORT, "city": "Atlanta"}, rows, [], None, None)
    assert s["statut"] == "desservie" and s["paris"]["masque"] is True and s["paris"]["part"] is None


def test_destination_non_desservie_au_radar():
    rows = [_row("LTFM", "IST", "Istanbul", 340_000, 258_000)]
    opp = {"opportunity_score": 65.9, "segment": "long-courrier", "partner_city": "Manille"}
    s = build_study("MNL", None, rows, [{"month": "2024-12", "paris": 0, "hubs": 30000, "paris_masked": 0}], opp, None)
    assert s["statut"] == "opportunite" and s["paris"]["pax_l12"] == 0
    assert s["mensuel"][0]["hubs"] == 30000
    assert any("65,9 / 100" in t for t in s["lecture"])


def test_chaque_agent_laisse_sa_trace():
    d = run_dossier(SnapshotSource(FIXTURE), OfflineLLM(), load_assumptions(), REQ, today=date(2026, 10, 28))
    by_agent = {e["agent"]: e for e in d["journal"]}
    assert set(by_agent) == {"Éclaireur", "Marché", "Concurrence", "Économiste", "Avocat du diable", "Rédacteur"}
    assert "cap_gold.route_window" in by_agent["Marché"]["requetes"][0]["sql"]
    assert by_agent["Marché"]["faits"]["marche_pax"]["valeur"] == "340 000"
    assert by_agent["Économiste"]["formules"]
    assert "{{" not in by_agent["Avocat du diable"]["texte"]
    assert "{{verdict}}" in by_agent["Rédacteur"]["brouillon"]


def test_flux_dans_l_ordre():
    events = list(stream_dossier(SnapshotSource(FIXTURE), OfflineLLM(), load_assumptions(), REQ,
                                 today=date(2026, 10, 28)))
    agents = [e["entree"]["agent"] for e in events if e["type"] == "agent"]
    assert agents == ["Éclaireur", "Marché", "Concurrence", "Économiste", "Avocat du diable", "Rédacteur"]
    assert events[-1]["type"] == "fin" and events[-1]["dossier"]["verdict"]
