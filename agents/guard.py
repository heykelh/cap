"""Garde-fou : aucun chiffre écrit par un LLM ne peut atteindre le dossier.

Règles appliquées à tout texte produit par un agent :
  1. chaque balise {{clé}} doit exister dans le catalogue de faits ;
  2. une fois les balises retirées, le texte ne doit contenir aucun chiffre.
Le texte est ensuite rendu en remplaçant les balises par les valeurs calculées.
"""
import re

PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


def check(text: str, known_keys: set[str]) -> list[str]:
    problems = []
    unknown = sorted({k for k in PLACEHOLDER.findall(text) if k not in known_keys})
    if unknown:
        problems.append(f"balises inconnues : {', '.join(unknown)}")
    stripped = PLACEHOLDER.sub("", text)
    digits = re.findall(r"[^\s]*\d[^\s]*", stripped)
    if digits:
        problems.append(f"chiffres écrits à la main : {', '.join(sorted(set(digits))[:8])}")
    if not stripped.strip():
        problems.append("texte vide")
    return problems


def render(text: str, values: dict[str, str], depth: int = 2) -> str:
    out = text
    for _ in range(depth):
        out = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), out)
    return out
