"""Chargement des hypothèses sourcées (reference/assumptions_*.json).

Chaque hypothèse porte sa valeur, son unité, sa méthode de calcul et sa source.
Le modèle refuse une hypothèse sans source : aucun chiffre n'est inventé.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "reference" / "assumptions_afklm_fy2025.json"
REQUIRED = ["yield_eur_per_rpk", "cost_eur_per_ask", "fuel_eur_per_ask", "load_factor", "weeks_per_year"]


@dataclass(frozen=True)
class Assumption:
    key: str
    value: float
    unit: str
    label: str
    method: str
    source: str

    def cite(self) -> str:
        return f"{self.label} : {self.method} ({self.source})"


@dataclass
class Assumptions:
    version: str
    items: dict[str, Assumption]
    load_factor_by_region: dict[str, float]
    aircraft: dict[str, dict]
    known_limits: list[str] = field(default_factory=list)

    def __getitem__(self, key: str) -> Assumption:
        return self.items[key]

    def seats(self, aircraft: str) -> int:
        if aircraft not in self.aircraft:
            known = ", ".join(sorted(self.aircraft))
            raise KeyError(f"Appareil inconnu « {aircraft} ». Appareils connus : {known}")
        return int(self.aircraft[aircraft]["seats"])


def load_assumptions(path: Path | str = DEFAULT_PATH) -> Assumptions:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    publication = raw.get("published_source", "")

    items: dict[str, Assumption] = {}
    for key, spec in raw["assumptions"].items():
        pages = spec.get("source_pages", "")
        source = f"{publication}, {pages}" if pages else spec.get("scope", "")
        items[key] = Assumption(
            key=key,
            value=float(spec["value"]),
            unit=spec["unit"],
            label=spec["label"],
            method=spec["method"],
            source=source,
        )

    missing = [k for k in REQUIRED if k not in items]
    if missing:
        raise ValueError(f"Hypothèses manquantes : {missing}")
    unsourced = [k for k, a in items.items() if not a.source or not a.method]
    if unsourced:
        raise ValueError(f"Hypothèses sans source ou sans méthode : {unsourced}")

    return Assumptions(
        version=raw["version"],
        items=items,
        load_factor_by_region={k: float(v["value"]) for k, v in raw.get("load_factor_by_region", {}).items()},
        aircraft=raw.get("aircraft", {}),
        known_limits=raw.get("known_limits", []),
    )
