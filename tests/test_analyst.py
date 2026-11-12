"""Agents IA (Analyste, Contradicteur) avec un modèle simulé : boucle d'outils, garde-fou, objections."""
import json
import re
from pathlib import Path

from agents.analyst import analyse
from agents.datasource import SnapshotSource
from agents.toolchat import ToolChatError
from agents.tools import ToolBox
from economics import load_assumptions

FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_synthetique.json"


def call(name, **args):
    return {"id": f"c-{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def ref_of(messages, field):
    """Retrouve la référence d'un champ dans le dernier résultat d'outil qui le contient."""
    for m in reversed(messages):
        if m["role"] == "tool" and f'"{field}"' in m["content"]:
            return re.search(r"\{\{f\d+\}\}", json.loads(m["content"])[field]).group(0)
    raise AssertionError(field)


ANSWER = ("## Réponse\nLa ligne est rentable de justesse : {res}.\n## Ce que montrent les données\nMarge {marge}.\n"
          "## Risques\nRecette fragile.\n## Recommandation\nApprofondir avec un A350-900.")


class ScriptedChat:
    name = "modèle simulé"

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, tools=None):
        self.calls += 1
        step = self.script.pop(0)
        out = step(messages) if callable(step) else step
        return {"content": out.get("content", ""), "tool_calls": out.get("tool_calls", [])}


def final(messages):
    return {"content": ANSWER.format(res=ref_of(messages, "resultat_exploitation"), marge=ref_of(messages, "marge"))}


def run(script):
    tb = ToolBox(SnapshotSource(FIXTURE), load_assumptions())
    chat = ScriptedChat(script)
    return list(analyse("Faut-il ouvrir Paris-Manille ?", tb, chat)), tb, chat


def test_boucle_complete_avec_garde_fou_et_objection():
    events, tb, chat = run([
        {"content": "Je regarde d'abord le marché.", "tool_calls": [call("etude_marche", iata="MNL")]},
        {"content": "Je chiffre la ligne.", "tool_calls": [call("simuler_ligne", iata="MNL", frequences_par_semaine=3, appareil="A350-900")]},
        {"content": "## Réponse\nRésultat de 5,3 M€.\n## Données\nx\n## Risques\nx"},          # chiffre écrit : rejeté
        final,
        {"content": "Je teste une recette plus basse.", "tool_calls": [call("simuler_ligne", iata="MNL", frequences_par_semaine=3, appareil="A350-900", variation_recette_pct=-15)]},
        lambda m: {"content": 'Analyse.\n{"verdict": "a_revoir", "objections": ["Avec une recette plus basse le résultat tombe à '
                   + ref_of(m, "resultat_exploitation") + '."]}'},
        final,
    ])
    types = [e["type"] for e in events]
    assert types.count("appel") == 3 and "verdict" in types and types[-1] == "fin"
    rejets = [e for e in events if e["type"] == "garde_fou" and not e["ok"]]
    assert rejets and "chiffres écrits à la main" in rejets[0]["rejets"][0]
    verdict = next(e for e in events if e["type"] == "verdict")
    assert verdict["verdict"] == "a_revoir" and "-8,7 M€" in verdict["objections_affichees"][0]
    rep = next(e for e in events if e["type"] == "reponse")
    assert "5,3 M€" in rep["texte"] and "{{" not in rep["texte"] and not rep["secours"]
    assert {f["outil"] for f in rep["faits"]} == {"simuler_ligne"}
    assert chat.script == []


def test_contradicteur_valide_du_premier_coup():
    events, _, _ = run([
        {"tool_calls": [call("simuler_ligne", iata="MNL", frequences_par_semaine=3, appareil="A350-900")]},
        final,
        {"content": '{"verdict": "valide", "objections": []}'},
    ])
    assert next(e for e in events if e["type"] == "verdict")["verdict"] == "valide"
    assert events[-1]["tours_contradicteur"] == 1


def test_outil_en_erreur_renvoye_a_l_agent():
    events, _, _ = run([
        {"tool_calls": [call("etude_marche", iata="ZZZ")]},
        {"tool_calls": [call("simuler_ligne", iata="MNL", frequences_par_semaine=3, appareil="A350-900")]},
        final,
        {"content": '{"verdict": "valide", "objections": []}'},
    ])
    err = next(e for e in events if e["type"] == "resultat" and not e["ok"])
    assert "aucune donnée" in err["resultat"]["erreur"]
    assert next(e for e in events if e["type"] == "reponse")["secours"] is False


def test_reference_inventee_puis_echec_donne_une_reponse_de_secours():
    bad = {"content": "## Réponse\n{{f99}}\n## Données\nx\n## Risques\nx\n## Recommandation\nx"}
    events, _, _ = run([
        {"tool_calls": [call("simuler_ligne", iata="MNL", frequences_par_semaine=3, appareil="A350-900")]},
        bad, bad, bad,
    ])
    rep = next(e for e in events if e["type"] == "reponse")
    assert rep["secours"] and "{{" not in rep["texte"] and "5,3 M€" in rep["texte"]


def test_ia_indisponible():
    class Down:
        name = "aucun"

        def chat(self, *a):
            raise ToolChatError("panne")

    tb = ToolBox(SnapshotSource(FIXTURE), load_assumptions())
    events = list(analyse("Question", tb, Down()))
    assert events[-1]["type"] == "erreur"


def test_tiret_insecable_dans_un_nom_d_appareil():
    from agents.analyst import _guard
    text = "## Réponse\nUn A350\u2011900 ou un B787\u20119.\n## Données\nx\n## Risques\nx\n## Recommandation\nx"
    assert _guard(text, set()) == []
    assert _guard(text.replace("x\n## Recommandation", "12 %\n## Recommandation"), set())


def test_resultat_compact_pour_le_modele():
    from agents.tools import tool_result_text
    txt = tool_result_text({"marge": {"valeur": "5,7 %", "ref": "{{f5}}"}, "liste": [{"a": {"valeur": "1", "ref": "{{f1}}"}}]})
    assert txt == '{"marge":"5,7 % {{f5}}","liste":[{"a":"1 {{f1}}"}]}'


def test_saturation_passagere_reessayee_puis_relais(monkeypatch):
    from agents import toolchat

    monkeypatch.setattr(toolchat.time, "sleep", lambda s: None)
    chat = toolchat.ToolChat.__new__(toolchat.ToolChat)
    chat.timeout, chat.used = 1, None

    class P:
        def __init__(self, name, fails, msg):
            self.name, self.label, self.fails, self.msg, self.broken = name, name, fails, msg, None

        def chat(self, *a):
            if self.fails:
                self.fails -= 1
                raise toolchat.ToolChatError(self.msg)
            return {"content": "ok", "tool_calls": []}

    groq = P("Groq", 2, "Groq HTTP 429 : Please try again in 1.5s")
    chat.providers = [groq]
    assert chat.chat([]) ["content"] == "ok" and groq.broken is None

    dead, backup = P("Groq", 9, "Groq HTTP 429"), P("Gemini", 0, "")
    chat.providers = [dead, backup]
    assert chat.chat([])["content"] == "ok" and chat.used == "Gemini" and dead.broken is None

    bad = P("Groq", 9, "Groq HTTP 401 : clé invalide")
    chat.providers = [bad, P("Gemini", 0, "")]
    chat.chat([])
    assert bad.broken
