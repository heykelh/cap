"""Chaîne d'instruction d'un dossier d'ouverture : un workflow déterministe en six étapes (LangGraph).

Ce ne sont pas des agents : l'ordre est fixe et seule la dernière étape fait appel à un modèle de langage,
pour rédiger. C'est voulu : un business plan doit être reproductible. Les vrais agents IA, qui choisissent
eux-mêmes leurs outils, sont dans analyst.py.

  charger → éclaireur → marché → concurrence → économiste → avocat du diable
          → rédacteur ⇄ contrôle (2 réécritures maximum) → note finale

Répartition des rôles :
  * le code calcule (requêtes paramétrées, modèle économique, règles d'alerte, verdict) ;
  * le LLM rédige, avec des balises {{clé}} uniquement ;
  * le contrôle rejette tout texte avec un chiffre écrit à la main ou une balise inconnue.
"""
import operator
import time
from datetime import date
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from economics import evaluate_route, sensitivity
from economics.model import inputs_from_assumptions

from . import facts as F
from .guard import PLACEHOLDER, check, render
from .llm import OfflineLLM

SYSTEM = (
    "Tu es un analyste de l'équipe Network Planning d'une grande compagnie aérienne. "
    "Tu écris en français, de façon factuelle, sobre et précise. "
    "RÈGLE ABSOLUE : tu n'écris jamais de chiffre. Pour toute valeur, tu utilises exactement "
    "une balise de la liste fournie, sous la forme {{cle}}. N'invente aucune balise. "
    "Écris les nombres ordinaux et quantités en lettres si besoin (« un », « deux »). "
    "Pas de tiret long, utilise les deux-points ou des virgules. Pas de formule de politesse."
)
MAX_DRAFTS = 2
NOTE_HEADINGS = ["## Opportunité", "## Marché", "## Concurrence", "## Rentabilité", "## Risques", "## Recommandation"]


class State(TypedDict, total=False):
    history: Annotated[list, operator.add]
    request: dict
    data: dict
    catalog: Any
    sections: dict
    flags: list
    verdict: str
    draft: str
    problems: list
    attempts: int
    note: str
    error: str
    writer_error: str
    journal: Annotated[list, operator.add]


def _verdict(flags: list[dict], result) -> str:
    if result.operating_margin < 0:
        return "ne pas ouvrir en l'état : la ligne est déficitaire au remplissage visé"
    if any(f["gravite"] == "haute" for f in flags):
        return "approfondir avant décision : au moins un risque majeur est à lever"
    return "instruire l'ouverture : la ligne est rentable et les risques identifiés sont maîtrisables"


def build_graph(source, llm, assumptions, today: date | None = None, llm_scope: str = "note",
                progress=None):
    """llm_scope : "note" (le LLM ne rédige que la note finale) ou "tous" (chaque étape rédige)."""
    today = today or date.today()
    say = progress or (lambda message: None)

    def write(agent: str, task: str, keys: list[str], template: str, cat: F.Catalog,
              required: list[str] | None = None) -> tuple[str, dict]:
        """Demande un texte au LLM, le contrôle, réessaie une fois, sinon prend le gabarit."""
        known = set(cat.facts)
        entry = {"agent": agent, "llm": llm.name, "tentatives": 0, "statut": "gabarit", "rejets": []}
        if llm_scope != "tous":
            entry["statut"] = "gabarit (LLM réservé à la note)"
            say(f"  {agent:<18} calculé")
            return template, entry
        started = time.perf_counter()
        say(f"  {agent:<18} rédaction en cours…")
        prompt = (f"{task}\n\nBalises disponibles (balise : signification) :\n{cat.describe(keys)}\n\n"
                  "Réponds uniquement par le texte demandé.")
        for _ in range(2):
            try:
                text = llm.complete(SYSTEM, prompt)
            except Exception as exc:  # quota, réseau : on continue avec le gabarit
                entry["rejets"].append(f"erreur LLM : {str(exc)[:120]}")
                break
            if text is None:
                break
            entry["tentatives"] += 1
            problems = check(text, known)
            missing = [k for k in (required or []) if f"{{{{{k}}}}}" not in text]
            if missing:
                problems.append(f"balises obligatoires absentes : {', '.join(missing)}")
            if not problems:
                entry["statut"] = "rédigé par le LLM, contrôle réussi"
                entry["duree_s"] = round(time.perf_counter() - started, 1)
                say(f"  {agent:<18} rédigé en {entry['duree_s']} s")
                return text, entry
            entry["rejets"].append("; ".join(problems))
            prompt += f"\n\nTon texte précédent a été rejeté : {'; '.join(problems)}. Corrige."
        entry["duree_s"] = round(time.perf_counter() - started, 1)
        say(f"  {agent:<18} gabarit après {entry['duree_s']} s")
        return template, entry

    # --- Nœuds -----------------------------------------------------------------

    def trace(entry: dict, cat: F.Catalog, before: set, text: str, started: float, jobs: list) -> dict:
        """Complète l'entrée du journal : requêtes exécutées, faits produits, texte rendu, durée."""
        values = cat.values()
        entry["requetes"] = jobs
        entry["faits"] = {k: {"valeur": render(f.value, values), "libelle": f.label}
                          for k, f in cat.facts.items() if k not in before}
        entry["texte"] = render(text, values)
        entry["duree_ms"] = round((time.perf_counter() - started) * 1000)
        entry["source"] = source.name
        return entry

    def load(state: State) -> State:
        req = state["request"]
        dest = req["dest"].upper()
        source.take_jobs()
        opp = source.opportunity(dest)
        distance = req.get("distance") or (opp or {}).get("distance_from_cdg_km")
        if not distance and hasattr(source, "airport"):
            airport = source.airport(dest)
            distance = (airport or {}).get("distance_from_cdg_km")
        if not distance:
            return {"error": f"{dest} est absente du radar et aucune distance n'a été fournie.",
                    "journal": [{"agent": "Éclaireur", "statut": "échec", "source": source.name,
                                 "requetes": source.take_jobs()}]}
        data = {"dest": dest, "opportunity": opp, "distance": float(distance), "jobs_load": source.take_jobs()}
        return {"data": data, "catalog": F.Catalog(), "sections": {}}

    def scout(state: State) -> State:
        d, cat = state["data"], state["catalog"]
        started, before = time.perf_counter(), set(cat.facts)
        F.scout_facts(cat, d["dest"], d["opportunity"], source.name)
        keys = [k for k in ["ville", "destination", "radar_statut", "segment", "score", "distance"] if k in cat.facts]
        keys += cat.keys_with_prefix("rang_")
        template = ("{{ville}} ({{destination}}) est {{radar_statut}}, segment {{segment}}, avec un score de "
                    "{{score}}, à {{distance}} de CDG.") if "ville" in cat.facts else \
            "{{destination}} est {{radar_statut}} : le dossier repose sur les paramètres saisis."
        text, entry = write("Éclaireur", "Présente en deux phrases pourquoi cette destination ressort du radar, "
                            "en citant le score et les critères où elle est la mieux classée.", keys, template, cat)
        trace(entry, cat, before, text, started, d["jobs_load"])
        return {"sections": {**state["sections"], "eclaireur": text}, "journal": [entry]}

    def market(state: State) -> State:
        d, cat = state["data"], state["catalog"]
        started, before = time.perf_counter(), set(cat.facts)
        d = {**d, "hub_flows": source.hub_flows(d["dest"])}
        m = F.market_facts(cat, d["opportunity"], d["hub_flows"], source.name)
        keys = ["marche_pax", "marche_croissance", "nb_hubs", "premier_hub", "part_premier_hub", "donnees_jusqu_a"]
        keys += [k for k in cat.facts if k.startswith("hub")]
        template = ("Les hubs européens concurrents ont transporté {{marche_pax}} passagers vers la destination "
                    "sur la dernière année publiée (jusqu'à {{donnees_jusqu_a}}), soit {{marche_croissance}} sur un an. "
                    "Le premier hub, {{premier_hub}}, en porte {{part_premier_hub}}.")
        text, entry = write("Marché", "Analyse en trois phrases la taille et la dynamique de la demande observée, "
                            "et dis si elle est concentrée sur un hub. Rappelle que ce trafic est un indicateur "
                            "de la demande, pas la demande de Paris elle-même.", keys, template, cat)
        trace(entry, cat, before, text, started, source.take_jobs())
        return {"data": {**d, "market": m}, "sections": {**state["sections"], "marche": text}, "journal": [entry]}

    def competition(state: State) -> State:
        d, cat = state["data"], state["catalog"]
        started, before = time.perf_counter(), set(cat.facts)
        d = {**d, "paris_to_hubs": source.paris_to_hubs([f["rep_icao"] for f in d["hub_flows"]])}
        c = F.competition_facts(cat, d["opportunity"], d["paris_to_hubs"], source.name)
        keys = ["paris_vers_hubs_pax", "paris_vers_hubs_masques", "cdg_vols_actuels", "nb_hubs"]
        keys += cat.keys_with_prefix("liaison")
        template = ("Sans vol direct, un voyageur parisien rejoint cette destination en correspondance, notamment par "
                    "les hubs concurrents. CDG est reliée à ces hubs avec {{paris_vers_hubs_pax}} passagers sur douze "
                    "mois, toutes destinations finales confondues : la part qui continue vers cette destination "
                    "n'est pas mesurable avec les données publiques et devra être estimée sur les données de "
                    "réservation de la compagnie.")
        text, entry = write("Concurrence", "Explique en trois phrases comment les voyageurs de Paris rejoignent "
                            "aujourd'hui cette destination et ce qu'une ligne directe changerait. Précise que le "
                            "trafic Paris-hubs couvre toutes les destinations finales : la part vers cette "
                            "destination n'est pas mesurable avec les données publiques.", keys, template, cat)
        trace(entry, cat, before, text, started, source.take_jobs())
        return {"data": {**d, "competition": c}, "sections": {**state["sections"], "concurrence": text},
                "journal": [entry]}

    def economist(state: State) -> State:
        d, cat, req = state["data"], state["catalog"], state["request"]
        started, before = time.perf_counter(), set(cat.facts)
        market_pax = req.get("market_pax") or (d.get("market") or {}).get("pax") or None
        x = inputs_from_assumptions(
            assumptions, "CDG", d["dest"], d["distance"], req["freq"], req["aircraft"],
            load_factor=req.get("load_factor"), region=req.get("region"), weeks_per_year=req.get("weeks"),
            market_pax_per_year=market_pax,
        )
        result = evaluate_route(x)
        sens = sensitivity(x)
        F.economics_facts(cat, result, sens, assumptions, req.get("region"))
        keys = ["frequences", "appareil", "sieges", "passagers_an", "recette_meur", "couts_meur", "resultat_meur",
                "marge", "remplissage_vise", "remplissage_equilibre", "marge_securite", "part_marche"]
        keys += cat.keys_with_prefix("sens_") + ["hyp_yield", "hyp_cask"]
        template = ("Avec {{frequences}} allers-retours par semaine en {{appareil}}, la ligne transporte "
                    "{{passagers_an}} passagers par an, pour une recette de {{recette_meur}} et un résultat "
                    "d'exploitation de {{resultat_meur}} (marge {{marge}}). L'équilibre est atteint à "
                    "{{remplissage_equilibre}} de remplissage, pour {{remplissage_vise}} visés.")
        text, entry = write("Économiste", "Commente en trois phrases la rentabilité calculée par le modèle et "
                            "l'hypothèse à laquelle le résultat est le plus sensible.", keys, template, cat,
                            required=["resultat_meur", "remplissage_equilibre"])
        entry["calcul"] = "modèle CAP déterministe"
        trace(entry, cat, before, text, started, [])
        entry["formules"] = result.trace
        return {"data": {**d, "result": result, "sensitivity": sens},
                "sections": {**state["sections"], "economiste": text}, "journal": [entry]}

    def devil(state: State) -> State:
        d, cat = state["data"], state["catalog"]
        started, before = time.perf_counter(), set(cat.facts)
        d = {**d, "overrides": source.overrides(d["dest"])}
        flags = F.red_flags(cat, opp=d["opportunity"], market=d["market"], competition=d["competition"],
                            result=d["result"], sens=d["sensitivity"], overrides=d["overrides"], today=today,
                            watchlist=F.load_watchlist())
        verdict = _verdict(flags, d["result"])
        cat.add("verdict", verdict, "recommandation calculée par les règles CAP", "règles CAP")
        alert_keys = cat.keys_with_prefix("alerte")
        template = "\n".join(f"- {{{{{k}}}}}" for k in alert_keys) or "- Aucun signal d'alerte déclenché par les règles."
        text, entry = write("Avocat du diable", "Rédige la liste des objections, une puce par alerte, de la plus "
                            "grave à la moins grave. Reprends chaque alerte avec sa balise et ajoute en une phrase "
                            "la question que l'équipe devra trancher.", alert_keys + ["verdict"], template, cat,
                            required=alert_keys)
        entry["alertes"] = [f["code"] for f in flags]
        trace(entry, cat, before, text, started, source.take_jobs())
        entry["regles"] = [{"code": f["code"], "gravite": f["gravite"], "texte": render(f["texte"], cat.values())}
                           for f in flags]
        return {"data": d, "flags": flags, "verdict": verdict, "sections": {**state["sections"], "avocat": text},
                "journal": [entry]}

    def writer(state: State) -> State:
        cat, s = state["catalog"], state["sections"]
        attempts = state.get("attempts", 0) + 1
        context = "\n\n".join(f"[{k}]\n{v}" for k, v in s.items())
        task = ("Rédige une note d'une page en Markdown, avec exactement ces titres dans cet ordre : "
                + ", ".join(NOTE_HEADINGS) + ". Commence par un titre de niveau un. Appuie-toi sur les "
                "analyses ci-dessous, en gardant leurs balises. La section Recommandation reprend {{verdict}}.\n\n"
                + context)
        if state.get("problems"):
            task += f"\n\nLa version précédente a été rejetée : {'; '.join(state['problems'])}. Corrige."
        error = None
        started = time.perf_counter()
        if not isinstance(llm, OfflineLLM):
            say(f"  {'Rédacteur':<18} rédaction de la note, essai {attempts}…")
        # Consigne allégée : seules les balises déjà utilisées par les sections, plus le verdict.
        useful = set(PLACEHOLDER.findall(context)) | {"verdict", "ville", "destination"}
        keys = [k for k in cat.facts if k in useful]
        try:
            text = llm.complete(SYSTEM, task + f"\n\nBalises disponibles :\n{cat.describe(keys)}")
        except Exception as exc:  # quota, réseau : la note sera produite par le gabarit
            text, error = None, f"erreur LLM : {str(exc)[:120]}"
        if text is not None:
            say(f"  {'Rédacteur':<18} brouillon reçu en {time.perf_counter() - started:.1f} s, contrôle…")
        return {"draft": text, "attempts": attempts, "writer_error": error,
                "writer_ms": round((time.perf_counter() - started) * 1000)}

    def control(state: State) -> State:
        cat, draft = state["catalog"], state.get("draft")
        if draft is None:
            return {"problems": [state.get("writer_error") or "pas de LLM : note produite par le gabarit"]}
        problems = check(draft, set(cat.facts))
        missing = [h for h in NOTE_HEADINGS if h not in draft]
        if missing:
            problems.append(f"titres absents : {', '.join(missing)}")
        if "{{verdict}}" not in draft:
            problems.append("la recommandation doit reprendre {{verdict}}")
        return {"problems": problems, "history": [{"essai": state.get("attempts"), "brouillon": draft,
                                                    "rejets": problems, "duree_ms": state.get("writer_ms")}]}

    def route_after_control(state: State) -> str:
        if not state["problems"]:
            return "finalize"
        if state.get("draft") is not None and state["attempts"] < MAX_DRAFTS:
            return "writer"
        return "fallback"

    def template_note(state: State) -> str:
        s = state["sections"]
        return "\n\n".join([
            "# Dossier d'ouverture : Paris CDG vers {{ville}} ({{destination}})"
            if "ville" in state["catalog"].facts else "# Dossier d'ouverture : Paris CDG vers {{destination}}",
            "## Opportunité", s["eclaireur"],
            "## Marché", s["marche"],
            "## Concurrence", s["concurrence"],
            "## Rentabilité", s["economiste"],
            "## Risques", s["avocat"],
            "## Recommandation", "Recommandation des règles CAP : {{verdict}}.",
        ])

    def annex(cat: F.Catalog) -> str:
        lines = ["", "", "---", "", "## Annexe : chiffres et sources", "",
                 "| Indicateur | Valeur | Source |", "|---|---|---|"]
        for f in cat.facts.values():
            if f.key.startswith("alerte") or f.key == "verdict":
                continue
            value = render(f.value, cat.values())
            lines.append(f"| {f.label} | {value} | {f.source} |")
        return "\n".join(lines)

    def finalize(state: State) -> State:
        cat = state["catalog"]
        note = render(state["draft"], cat.values()) + annex(cat)
        history = state.get("history", [])
        return {"note": note, "journal": [{"agent": "Rédacteur", "llm": llm.name, "tentatives": state["attempts"],
                                           "statut": "rédigé par le LLM, contrôle réussi",
                                           "rejets": [r for h in history for r in h["rejets"]],
                                           "essais": history, "brouillon": state["draft"],
                                           "texte": render(state["draft"], cat.values()),
                                           "requetes": []}]}

    def fallback(state: State) -> State:
        cat = state["catalog"]
        note = render(template_note(state), cat.values()) + annex(cat)
        rejets = state.get("problems") or []
        draft = template_note(state)
        return {"note": note, "journal": [{"agent": "Rédacteur", "llm": llm.name,
                                           "tentatives": state.get("attempts", 0),
                                           "statut": "gabarit", "rejets": rejets,
                                           "essais": state.get("history", []), "brouillon": draft,
                                           "texte": render(draft, cat.values()), "requetes": []}]}

    # --- Assemblage --------------------------------------------------------------

    g = StateGraph(State)
    for name, fn in [("load", load), ("scout", scout), ("market", market), ("competition", competition),
                     ("economist", economist), ("devil", devil), ("writer", writer), ("control", control),
                     ("finalize", finalize), ("fallback", fallback)]:
        g.add_node(name, fn)
    g.add_edge(START, "load")
    g.add_conditional_edges("load", lambda s: END if s.get("error") else "scout")
    for a, b in [("scout", "market"), ("market", "competition"), ("competition", "economist"),
                 ("economist", "devil"), ("devil", "writer"), ("writer", "control")]:
        g.add_edge(a, b)
    g.add_conditional_edges("control", route_after_control, ["writer", "finalize", "fallback"])
    g.add_edge("finalize", END)
    g.add_edge("fallback", END)
    return g.compile()


AGENT_OF_NODE = {"scout": "Éclaireur", "market": "Marché", "competition": "Concurrence",
                 "economist": "Économiste", "devil": "Avocat du diable", "writer": "Rédacteur",
                 "control": "Rédacteur", "finalize": "Rédacteur", "fallback": "Rédacteur"}


def run_dossier(source, llm, assumptions, request: dict, today: date | None = None,
                llm_scope: str = "note", progress=None) -> dict:
    graph = build_graph(source, llm, assumptions, today=today, llm_scope=llm_scope, progress=progress)
    state = graph.invoke({"request": request, "journal": [], "history": [], "attempts": 0})
    return assemble(state, source, assumptions)


def stream_dossier(source, llm, assumptions, request: dict, today: date | None = None, llm_scope: str = "note"):
    """Même instruction que run_dossier, mais événement par événement (pour le direct sur le site).

    Produit des dictionnaires :
      {"type": "debut", "agent": ...}        un agent commence (annonce)
      {"type": "agent", "entree": {...}}     un agent a terminé (entrée complète du journal)
      {"type": "controle", "essai": n, "rejets": [...]}   verdict du garde-fou sur un brouillon
      {"type": "fin", "dossier": {...}}      dossier complet
    """
    graph = build_graph(source, llm, assumptions, today=today, llm_scope=llm_scope)
    order = ["scout", "market", "competition", "economist", "devil", "writer"]
    yield {"type": "debut", "agent": AGENT_OF_NODE["scout"]}
    final = None
    for mode, chunk in graph.stream({"request": request, "journal": [], "history": [], "attempts": 0},
                                    stream_mode=["updates", "values"]):
        if mode == "values":
            final = chunk
            continue
        for node, update in chunk.items():
            update = update or {}
            for entry in update.get("journal", []):
                yield {"type": "agent", "entree": entry}
            if node == "control":
                h = (update.get("history") or [{"essai": None, "rejets": update.get("problems", [])}])[-1]
                yield {"type": "controle", "essai": h.get("essai"), "rejets": h.get("rejets", [])}
            if node in order[:-1]:
                yield {"type": "debut", "agent": AGENT_OF_NODE[order[order.index(node) + 1]]}
    yield {"type": "fin", "dossier": assemble(final, source, assumptions)}


def assemble(state: dict, source, assumptions) -> dict:
    if state.get("error"):
        return {"error": state["error"], "journal": state.get("journal", [])}
    d, cat = state["data"], state["catalog"]
    return {
        "destination": d["dest"],
        "note_markdown": state["note"],
        "verdict": state["verdict"],
        "alertes": state["flags"],
        "synthese_economique": d["result"].summary(),
        "trace_calcul": d["result"].trace,
        "sensibilites": d["sensitivity"],
        "faits": {k: {"valeur": render(f.value, cat.values()), "libelle": f.label, "source": f.source}
                  for k, f in cat.facts.items()},
        "journal": state["journal"],
        "source_donnees": source.name,
        "hypotheses": assumptions.version,
        "limites": assumptions.known_limits,
    }
