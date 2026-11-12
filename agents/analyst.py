"""Deux agents IA : l'Analyste et le Contradicteur.

Ce sont de vrais agents : un modèle de langage décide lui-même, à chaque tour, s'il appelle un outil
(lequel, avec quels paramètres) ou s'il répond. Son parcours dépend de la question et de ce qu'il
découvre : une ligne déficitaire le pousse à tester un autre appareil, une demande concentrée à
comparer d'autres destinations, etc.

  Analyste       reçoit une question libre, consulte les outils, rédige une réponse argumentée.
  Contradicteur  relit la réponse et les données, vérifie lui-même avec les outils, puis valide ou
                 renvoie des objections ; l'Analyste doit y répondre (deux tours au plus).
  Garde-fou      code, pas IA : aucun chiffre écrit à la main, seules les références {{fN}} issues des
                 outils sont admises ; le code les remplace par les valeurs calculées.

analyse() est un générateur d'événements : le site les affiche en direct.
"""
import json
import re
import time

from .guard import PLACEHOLDER, check, render
from .toolchat import ToolChatError
from .tools import TOOL_SPECS, ToolBox, ToolError, tool_result_text

# Noms d'appareils autorisés malgré leurs chiffres (A350-900, B787-9, B777-300ER…), quel que soit le tiret.
ALLOWED_TOKENS = re.compile(r"\b[AB]\d{3}(?:-\d{1,3}(?:ER)?)?\b")
DASHES = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2212]")
MAX_TOOLS_ANALYST = 7
MAX_TOOLS_CRITIC = 3
MAX_ROUNDS = 2
MAX_GUARD_RETRIES = 2

ANALYST_SYSTEM = """Tu es l'Analyste de CAP, agent IA au service de l'équipe de planification réseau d'une compagnie basée à Paris CDG.
Tu réponds à des questions sur l'ouverture de lignes et les marchés en t'appuyant uniquement sur tes outils (données Eurostat dans BigQuery et modèle économique sourcé).

Méthode :
1. Décide quelles données consulter, puis appelle les outils.
2. Examine chaque résultat. S'il soulève une question (ligne déficitaire ou marge fine, part de marché à capter élevée, demande portée par un seul hub, demande en baisse, alternative plausible), approfondis par d'autres appels : autre appareil, autre fréquence, saison plus courte, prix des billets plus bas, destination comparable.
3. Quand tu as assez d'éléments, rédige ta réponse finale sans appeler d'outil.
Avant chaque appel d'outil, écris une phrase courte, sans aucun chiffre, qui dit ce que tu vérifies et pourquoi.

Réponse finale : en français, en markdown, 150 à 260 mots, avec exactement ces sections :
## Réponse
## Ce que montrent les données
## Risques
## Recommandation
RÈGLE ABSOLUE : tu n'écris aucun chiffre. Chaque valeur est citée par sa référence exacte telle que renvoyée par les outils, par exemple {{f4}}. Cela vaut aussi pour les paramètres que tu as choisis toi-même (fréquence, nombre de semaines, variation de recette ou de carburant) : l'outil de simulation te les renvoie avec une référence dans « parametres ». Les noms d'appareils (A350-900, B787-9…) sont permis. Pas d'année en chiffres, pas de pourcentage écrit, pas de nombre en lettres inventé. N'utilise jamais une référence que les outils ne t'ont pas donnée. Si une donnée manque, dis-le."""

CRITIC_SYSTEM = """Tu es le Contradicteur de CAP, agent IA chargé de mettre à l'épreuve les conclusions de l'Analyste avant qu'elles soient présentées à la direction.
Tu reçois la question, les appels d'outils de l'Analyste avec leurs résultats, et sa réponse.
Vérifie : les conclusions découlent-elles des chiffres ? Des fragilités sont-elles passées sous silence (recette moyenne du réseau appliquée à une ligne très longue, part de marché à capter élevée, demande concentrée sur un hub, données masquées ou anciennes, ligne déjà desservie) ? Une alternative évidente n'a-t-elle pas été testée ?
Tu peux appeler les outils pour vérifier par toi-même (trois appels au plus). Avant chaque appel, une phrase courte sans chiffre.
Termine par une dernière ligne contenant uniquement ce JSON :
{"verdict": "valide" ou "a_revoir", "objections": ["...", "..."]}
Au plus trois objections, concrètes et actionnables. Dans les objections, aucun chiffre écrit : cite les valeurs par leur référence {{fN}}. Si la réponse tient, verdict "valide" avec au plus une réserve."""


def normalize(text: str) -> str:
    """Les modèles écrivent souvent A350‑900 avec un tiret insécable : on unifie les tirets."""
    return DASHES.sub("-", text or "")


def _clean(text: str) -> str:
    return ALLOWED_TOKENS.sub("", normalize(text))


def _guard(text: str, known: set[str]) -> list[str]:
    problems = check(_clean(text), known)
    if not text.strip():
        return ["réponse vide"]
    if text.count("## ") < 3:
        problems.append("sections attendues : Réponse, Ce que montrent les données, Risques, Recommandation")
    return problems


def _mask(text: str, values: dict) -> str:
    """Narration affichée : références rendues, chiffres non vérifiés masqués."""
    rendered = render(normalize(text), values)
    tokens = set(values.values())
    out = []
    for word in re.split(r"(\s+)", rendered):
        if re.search(r"\d", ALLOWED_TOKENS.sub("", word)) and not any(word.strip(".,;:()") in t for t in tokens):
            out.append("[…]")
        else:
            out.append(word)
    return "".join(out)


def _parse_verdict(text: str) -> dict:
    for match in reversed(list(re.finditer(r"\{[^{}]*\"verdict\"[^{}]*(\[[^\]]*\])?[^{}]*\}", text, re.S))):
        try:
            data = json.loads(match.group(0))
            return {"verdict": "a_revoir" if data.get("verdict") == "a_revoir" else "valide",
                    "objections": [str(o) for o in data.get("objections", [])][:3]}
        except json.JSONDecodeError:
            continue
    return {"verdict": "valide", "objections": [], "illisible": True}


def _assistant_msg(out: dict) -> dict:
    msg = {"role": "assistant", "content": out["content"] or ""}
    if out["tool_calls"]:
        msg["tool_calls"] = out["tool_calls"]
    return msg


def _agent_turns(agent: str, messages: list, tb: ToolBox, chat, max_tools: int, trace: list):
    """Fait tourner un agent jusqu'à ce qu'il réponde sans outil. Produit des événements, retourne le texte."""
    used = 0
    while True:
        tools = TOOL_SPECS if used < max_tools else None
        out = chat.chat(messages, tools)
        messages.append(_assistant_msg(out))
        if out["content"].strip() and out["tool_calls"]:
            yield {"type": "message", "agent": agent, "texte": _mask(out["content"], tb.values())}
        if not out["tool_calls"]:
            return normalize(out["content"])
        for call in out["tool_calls"]:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            used += 1
            yield {"type": "appel", "agent": agent, "outil": name, "arguments": args}
            try:
                result, jobs, ms = tb.run(name, args)
                content = tool_result_text(result)
                ok = True
            except (ToolError, ValueError) as exc:
                result, jobs, ms, ok = {"erreur": str(exc)}, [], 0, False
                content = tool_result_text(result)
            trace.append({"agent": agent, "outil": name, "arguments": args, "resultat": result})
            yield {"type": "resultat", "agent": agent, "outil": name, "ok": ok, "resultat": result,
                   "requetes": jobs, "duree_ms": ms}
            messages.append({"role": "tool", "tool_call_id": call.get("id", name), "name": name, "content": content})
        if used >= max_tools:
            messages.append({"role": "user", "content": "Limite d'appels atteinte : rédige maintenant ta réponse finale."})


def _fallback_answer(tb: ToolBox) -> str:
    lines = ["## Réponse", "L'Analyste n'a pas produit de réponse conforme au garde-fou. Voici les chiffres "
             "réellement obtenus par les outils, sans interprétation.", "", "## Ce que montrent les données"]
    lines += [f"- {f['libelle']} : {{{{{k}}}}}" for k, f in list(tb.facts.items())[:14]]
    return "\n".join(lines)


def analyse(question: str, toolbox: ToolBox, chat):
    """Générateur d'événements pour une question posée aux agents."""
    started = time.perf_counter()
    trace: list[dict] = []
    yield {"type": "debut", "question": question, "llm": chat.name}
    analyst_msgs = [{"role": "system", "content": ANALYST_SYSTEM}, {"role": "user", "content": question}]
    final_raw, critic_rounds = None, []
    try:
        for round_ in range(1, MAX_ROUNDS + 1):
            yield {"type": "tour", "agent": "Analyste", "tour": round_}
            draft = yield from _agent_turns("Analyste", analyst_msgs, toolbox, chat, MAX_TOOLS_ANALYST, trace)
            for retry in range(MAX_GUARD_RETRIES + 1):
                problems = _guard(draft, set(toolbox.facts))
                yield {"type": "garde_fou", "agent": "Analyste", "ok": not problems, "rejets": problems,
                       "brouillon": draft}
                if not problems:
                    break
                if retry == MAX_GUARD_RETRIES:
                    draft = None
                    break
                analyst_msgs.append({"role": "user", "content": "Garde-fou : réponse rejetée (" + " ; ".join(problems)
                                     + "). Réécris la réponse complète en citant chaque valeur uniquement par sa référence."})
                draft = yield from _agent_turns("Analyste", analyst_msgs, toolbox, chat, MAX_TOOLS_ANALYST, trace)
            if draft is None:
                break
            final_raw = draft

            if round_ == MAX_ROUNDS:
                break
            yield {"type": "tour", "agent": "Contradicteur", "tour": round_}
            values = toolbox.values()
            dossier = {"question": question,
                       "appels_de_l_analyste": [t for t in trace if t["agent"] == "Analyste"][-12:],
                       "reponse_de_l_analyste": render(draft, values)}
            critic_msgs = [{"role": "system", "content": CRITIC_SYSTEM},
                           {"role": "user", "content": json.dumps(dossier, ensure_ascii=False, default=str)}]
            critique = yield from _agent_turns("Contradicteur", critic_msgs, toolbox, chat, MAX_TOOLS_CRITIC, trace)
            verdict = _parse_verdict(critique)
            objections = []
            for o in verdict["objections"]:
                objections.append(render(o, toolbox.values()) if not check(_clean(o), set(toolbox.facts))
                                  else _mask(o, toolbox.values()))
            verdict["objections_affichees"] = objections
            critic_rounds.append(verdict)
            yield {"type": "verdict", "agent": "Contradicteur", **verdict}
            if verdict["verdict"] == "valide":
                break
            analyst_msgs.append({"role": "user", "content": "Le Contradicteur conteste ta réponse :\n- "
                                 + "\n- ".join(verdict["objections"])
                                 + "\nRéponds à ces objections : vérifie avec les outils si nécessaire, puis donne ta "
                                   "réponse finale complète, avec les mêmes sections et les mêmes règles."})
    except ToolChatError as exc:
        yield {"type": "erreur", "message": "Les fournisseurs d'IA sont saturés en ce moment (limite de débit ou "
               "surcharge). Réessayez dans une minute, ou rejouez une session enregistrée.", "detail": str(exc)[:300]}
        if not toolbox.facts:
            return

    fallback = final_raw is None
    raw = final_raw or _fallback_answer(toolbox)
    used = sorted(set(PLACEHOLDER.findall(raw)), key=lambda k: int(k[1:]) if k[1:].isdigit() else 0)
    yield {
        "type": "reponse",
        "texte": render(raw, toolbox.values()),
        "brouillon": raw,
        "secours": fallback,
        "faits": [{"ref": k, **toolbox.facts[k]} for k in used if k in toolbox.facts],
    }
    yield {"type": "fin", "duree_ms": round((time.perf_counter() - started) * 1000), "appels_outils": len(trace),
           "tours_contradicteur": len(critic_rounds), "llm": chat.name,
           "requetes_bigquery": toolbox.stats["requetes"], "octets_lus": toolbox.stats["octets"]}
