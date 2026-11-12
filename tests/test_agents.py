"""Tests de l'équipe d'agents sur un jeu synthétique, sans réseau ni clé d'API."""
import re
from datetime import date
from pathlib import Path

import pytest

from agents.datasource import SnapshotSource
from agents.graph import NOTE_HEADINGS, run_dossier
from agents.guard import check, render
from agents.llm import OfflineLLM
from economics import load_assumptions

FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_synthetique.json"
TODAY = date(2026, 10, 28)
REQ = {"dest": "MNL", "freq": 3, "aircraft": "A350-900", "region": "Asie et Moyen-Orient"}


def _keys(prompt: str) -> list[str]:
    block = prompt.split("Balises disponibles")[-1]
    return re.findall(r"\{\{([a-z0-9_]+)\}\}", block)


class DisciplinedLLM:
    """Utilise uniquement les balises fournies."""
    name = "LLM discipliné (test)"

    def complete(self, system, prompt):
        if "Rédige une note" in prompt:
            body = "\n\n".join(f"{h}\n\nAnalyse fondée sur {{{{verdict}}}}." for h in NOTE_HEADINGS)
            return "# Dossier\n\n" + body
        return "Constat : " + ", ".join(f"{{{{{k}}}}}" for k in _keys(prompt)) + "."


class InventiveLLM:
    """Écrit des chiffres à la main : doit être rejeté à chaque fois."""
    name = "LLM qui invente (test)"

    def __init__(self):
        self.calls = 0

    def complete(self, system, prompt):
        self.calls += 1
        return "La ligne rapportera 42 M€ avec un remplissage de 95 %. ## Opportunité"


class BrokenLLM:
    name = "LLM en panne (test)"

    def complete(self, system, prompt):
        raise TimeoutError("quota dépassé")


@pytest.fixture
def run():
    def _run(llm, request=REQ, scope="tous"):
        return run_dossier(SnapshotSource(FIXTURE), llm, load_assumptions(), request, today=TODAY, llm_scope=scope)
    return _run


def test_guard_rejects_digits_and_unknown_keys():
    assert check("Résultat {{resultat_meur}}.", {"resultat_meur"}) == []
    assert check("Résultat 5,3 M€.", {"resultat_meur"})
    assert check("Résultat {{inventee}}.", {"resultat_meur"})
    assert render("{{a}} et {{b}}", {"a": "x {{b}}", "b": "y"}) == "x y et y"


def test_offline_produces_complete_note(run):
    d = run(OfflineLLM())
    note = d["note_markdown"]
    for h in NOTE_HEADINGS:
        assert h in note
    assert "{{" not in note
    assert "Annexe : chiffres et sources" in note
    assert all(e["statut"].startswith(("ok", "gabarit")) for e in d["journal"])


def test_templates_respect_the_guard(run):
    d = run(OfflineLLM())
    assert d["synthese_economique"]["resultat_meur"] == pytest.approx(5.3, abs=0.1)
    assert "Manille" in d["note_markdown"]
    assert "5,3 M€" in d["note_markdown"]


def test_disciplined_llm_is_accepted(run):
    d = run(DisciplinedLLM())
    statuses = {e["agent"]: e["statut"] for e in d["journal"]}
    assert statuses["Économiste"].startswith("rédigé par le LLM")
    assert statuses["Rédacteur"].startswith("rédigé par le LLM")
    assert "{{" not in d["note_markdown"]


def test_inventive_llm_never_reaches_the_note(run):
    llm = InventiveLLM()
    d = run(llm)
    assert "42 M€" not in d["note_markdown"]
    assert "95 %" not in d["note_markdown"]
    writer = next(e for e in d["journal"] if e["agent"] == "Rédacteur")
    assert writer["statut"] == "gabarit"
    eco = next(e for e in d["journal"] if e["agent"] == "Économiste")
    assert eco["statut"] == "gabarit" and len(eco["rejets"]) == 2


def test_broken_llm_falls_back(run):
    d = run(BrokenLLM())
    assert "## Recommandation" in d["note_markdown"]
    assert any("erreur LLM" in r for e in d["journal"] for r in e.get("rejets", []))


def test_red_flags_and_verdict(run):
    d = run(OfflineLLM())
    codes = {a["code"] for a in d["alertes"]}
    assert {"part_marche_elevee", "hub_unique", "yield_long_courrier"} <= codes
    assert d["verdict"].startswith("approfondir")


def test_watchlist_and_declining_market(run):
    d = run(OfflineLLM(), {"dest": "IKA", "freq": 3, "aircraft": "B787-9"})
    codes = {a["code"] for a in d["alertes"]}
    assert "marche_surveille" in codes
    assert "demande_en_baisse" in codes


def test_unknown_destination_needs_distance(run):
    d = run(OfflineLLM(), {"dest": "XXX", "freq": 3, "aircraft": "A350-900"})
    assert "error" in d
    ok = run(OfflineLLM(), {"dest": "XXX", "freq": 3, "aircraft": "A350-900", "distance": 6000})
    assert "note_markdown" in ok


def test_every_fact_has_a_source(run):
    d = run(OfflineLLM())
    assert all(f["source"] for f in d["faits"].values())


def test_note_scope_calls_llm_only_for_the_note(run):
    d = run(DisciplinedLLM(), scope="note")
    statuses = {e["agent"]: e["statut"] for e in d["journal"]}
    assert statuses["Économiste"] == "gabarit (LLM réservé à la note)"
    assert statuses["Rédacteur"].startswith("rédigé par le LLM")


class CountingBrokenLLM:
    """Simule une panne réseau avec un disjoncteur, comme les vrais fournisseurs."""

    def __init__(self):
        self.calls = 0
        self.name = "LLM en panne avec disjoncteur (test)"
        self.disabled_reason = None

    def complete(self, system, prompt):
        if self.disabled_reason:
            raise RuntimeError("coupé")
        self.calls += 1
        self.disabled_reason = "délai dépassé"
        raise TimeoutError("délai dépassé")


def test_breaker_stops_after_first_failure(run):
    llm = CountingBrokenLLM()
    d = run(llm, scope="tous")
    assert llm.calls == 1
    assert "## Recommandation" in d["note_markdown"]


def test_breaker_on_real_provider_class():
    from agents.llm import _Breaker

    class Flaky(_Breaker):
        name = "flaky"

        def __init__(self):
            self.calls = 0

        def _complete(self, system, prompt):
            self.calls += 1
            raise TimeoutError("délai dépassé")

    f = Flaky()
    for _ in range(3):
        with pytest.raises(Exception):
            f.complete("s", "p")
    assert f.calls == 1

def test_chain_falls_back_to_next_provider(run):
    from agents.llm import ChainLLM

    class Saturated:
        name = "saturé"
        disabled_reason = None

        def __init__(self):
            self.calls = 0

        def complete(self, system, prompt):
            self.calls += 1
            self.disabled_reason = "503"
            raise RuntimeError("503 UNAVAILABLE")

    first = Saturated()
    chain = ChainLLM([first, DisciplinedLLM()])
    d = run(chain, scope="note")
    writer = next(e for e in d["journal"] if e["agent"] == "Rédacteur")
    assert writer["statut"].startswith("rédigé par le LLM")
    assert first.calls == 1
    assert chain.used == DisciplinedLLM.name


def test_timeout_is_read_after_env_is_loaded(monkeypatch):
    from agents.llm import timeout_s

    monkeypatch.setenv("LLM_TIMEOUT_S", "60")
    assert timeout_s() == 60
