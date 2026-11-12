"""Instruire un dossier d'ouverture avec l'équipe d'agents.

Exemples :
  python -m agents.run --dest MNL --freq 3 --aircraft A350-900 --region "Asie et Moyen-Orient"
  python -m agents.run --dest MNL --freq 3 --llm gemini
  python -m agents.run --dest MNL --freq 3 --llm gemini --llm-agents tous
  python -m agents.run --dest CLT --freq 5 --aircraft B787-9 --source snapshot --snapshot reference/snapshots/demo.json

Résultats écrits dans data/dossiers/ : la note (.md) et le dossier complet (.json).
"""
import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from economics import load_assumptions

from .datasource import BigQuerySource, SnapshotSource
from .graph import run_dossier
from .llm import LLMError, get_llm


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser(description="Dossier d'ouverture de ligne au départ de CDG")
    p.add_argument("--dest", required=True)
    p.add_argument("--freq", type=float, required=True, help="allers-retours par semaine")
    p.add_argument("--aircraft", default="A350-900")
    p.add_argument("--region")
    p.add_argument("--load-factor", type=float)
    p.add_argument("--weeks", type=float)
    p.add_argument("--distance", type=float, help="obligatoire si la destination n'est pas au radar")
    p.add_argument("--market-pax", type=float)
    p.add_argument("--llm", default="offline", help="gemini, groq ou offline")
    p.add_argument("--llm-agents", default="note", choices=["note", "tous"],
                   help="note : le LLM rédige seulement la note finale (rapide) ; tous : chaque agent rédige")
    p.add_argument("--source", default="bigquery", choices=["bigquery", "snapshot"])
    p.add_argument("--snapshot", default="reference/snapshots/demo.json")
    p.add_argument("--today", help="date de référence AAAA-MM-JJ (par défaut aujourd'hui)")
    args = p.parse_args()

    try:
        llm = get_llm(args.llm)
    except LLMError as exc:
        print(f"{exc} : passage en mode hors ligne.")
        llm = get_llm("offline")
    source = BigQuerySource() if args.source == "bigquery" else SnapshotSource(args.snapshot)
    request = {"dest": args.dest, "freq": args.freq, "aircraft": args.aircraft, "region": args.region,
               "load_factor": args.load_factor, "weeks": args.weeks, "distance": args.distance,
               "market_pax": args.market_pax}
    today = date.fromisoformat(args.today) if args.today else date.today()

    print(f"\nInstruction du dossier CDG-{args.dest.upper()} · données : {source.name} · LLM : {llm.name}")
    started = time.perf_counter()
    dossier = run_dossier(source, llm, load_assumptions(), request, today=today,
                          llm_scope=args.llm_agents, progress=print)
    print(f"Terminé en {time.perf_counter() - started:.1f} s")

    print("\nJournal des agents")
    for e in dossier["journal"]:
        extra = f" · rejets : {len(e['rejets'])}" if e.get("rejets") else ""
        print(f"  {e['agent']:<18} {e.get('statut', '')}{extra}")
        for r in e.get("rejets", []):
            print(f"      rejeté : {r}")
    if dossier.get("error"):
        print(f"\nÉchec : {dossier['error']}")
        return 1

    out = Path("data/dossiers")
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = out / f"CDG-{dossier['destination']}-{stamp}"
    base.with_suffix(".md").write_text(dossier["note_markdown"], encoding="utf-8")
    base.with_suffix(".json").write_text(json.dumps(dossier, ensure_ascii=False, indent=2, default=str),
                                         encoding="utf-8")
    print(f"\nRecommandation : {dossier['verdict']}")
    print(f"Alertes : {', '.join(a['code'] for a in dossier['alertes']) or 'aucune'}")
    print(f"Note : {base.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
