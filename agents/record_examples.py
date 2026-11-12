"""Enregistre des sessions réelles des agents IA, pour le mode « Rejouer » du site.

Pose quelques questions à l'Analyste et au Contradicteur (vrais appels à l'IA et à BigQuery)
et sauvegarde chaque session complète dans site/data/analyste/.

Usage :
  python -m agents.record_examples
  python -m agents.record_examples --question "Faut-il ouvrir Paris-Dakar ?"   (ajoutée aux sessions existantes)
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from economics import load_assumptions

from .analyst import analyse
from .datasource import BigQuerySource
from .toolchat import ToolChat
from .tools import ToolBox

QUESTIONS = [
    "Faut-il ouvrir une ligne Paris-Manille ? À quelles conditions serait-elle rentable ?",
    "Avec un seul B787-9 disponible, quelle destination d'Asie ou du Moyen-Orient ouvrir en priorité depuis Paris ?",
    "Paris-Bogota ou Paris-Medellín : laquelle des deux ouvrir, et pourquoi ?",
    "Comment se porte le marché Paris-New York, et Paris y garde-t-il sa place face aux autres hubs européens ?",
]


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--question", action="append")
    p.add_argument("--out", default="site/data/analyste")
    p.add_argument("--pause", type=float, default=20.0)
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    source, assumptions = BigQuerySource(), load_assumptions()
    # On complète la liste existante : une question déjà enregistrée est remplacée, les autres sont gardées.
    index_path = out / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    for i, q in enumerate(args.question or QUESTIONS):
        started = time.perf_counter()
        events = []
        for e in analyse(q, ToolBox(source, assumptions), ToolChat()):
            e["t_ms"] = round((time.perf_counter() - started) * 1000)
            events.append(e)
        name = slug(q)
        (out / f"{name}.json").write_text(json.dumps({"question": q, "enregistre_le": date.today().isoformat(),
                                                      "evenements": events}, ensure_ascii=False, default=str),
                                          encoding="utf-8")
        fin = next((e for e in events if e["type"] == "fin"), {})
        ok = any(e["type"] == "reponse" and not e.get("secours") for e in events)
        print(f"{'OK ' if ok else '!! '} {q[:70]:<70} {fin.get('appels_outils', 0)} outils · "
              f"{fin.get('duree_ms', 0) / 1000:.0f} s · {fin.get('llm', '')}")
        index = [x for x in index if x["id"] != name] + [{"id": name, "question": q, "ok": ok}]
        if i < len(args.question or QUESTIONS) - 1:
            time.sleep(args.pause)
    index = [x for x in index if (out / f"{x['id']}.json").exists()]
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(index)} session(s) disponibles sur le site.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
