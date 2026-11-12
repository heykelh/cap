"""Diagnostic du fournisseur de LLM : latence réelle, modèle et réglage de réflexion retenus.

Usage :
  python -m agents.llm_check --llm gemini
  python -m agents.llm_check --llm groq
  python -m agents.llm_check --llm gemini,groq
  python -m agents.llm_check --llm groq --list-models
"""
import argparse
import sys
import time

from dotenv import load_dotenv

from .llm import get_llm


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--llm", default="gemini")
    p.add_argument("--list-models", action="store_true", help="liste les modèles accessibles avec ta clé (Groq)")
    args = p.parse_args()

    llm = get_llm(args.llm)
    if args.list_models:
        if not hasattr(llm, "list_models"):
            print("Liste des modèles disponible pour Groq uniquement : --llm groq --list-models")
            return 1
        for model_id in llm.list_models():
            print(f"  {model_id}")
        return 0
    print(f"Fournisseur : {llm.name} · délai maximal : {getattr(llm, 'timeout', 0):.0f} s")
    started = time.perf_counter()
    try:
        text = llm.complete("Réponds en une phrase courte, en français.", "Dis bonjour à l'équipe Network.")
    except Exception as exc:
        print(f"Échec après {time.perf_counter() - started:.1f} s : {str(exc)[:300]}")
        return 1
    print(f"Réponse en {time.perf_counter() - started:.1f} s : {text}")
    if getattr(llm, "used", None):
        print(f"Fournisseur qui a répondu : {llm.used}")
    modes = getattr(llm, "_thinking_modes", None)
    if modes:
        print(f"Réglage de réflexion retenu : {modes[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
