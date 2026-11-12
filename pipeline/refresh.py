"""Rafraîchissement complet de CAP, lancé chaque mois par Cloud Scheduler (Cloud Run Job).

Étapes, dans l'ordre (arrêt à la première erreur, rien n'est publié dans ce cas) :
  1. bronze  : Eurostat, OurAirports, corrections de l'analyste      -> cap_bronze
  2. silver  : nettoyage, qualité, fraîcheur                         -> cap_silver
  3. gold    : fenêtres 12 mois, santé des lignes, radar             -> cap_gold
  4. dossiers: chaîne d'instruction, un dossier par destination long-courrier -> site/data
  5. marché  : étude de marché de toutes les destinations, puis sessions
               enregistrées des agents IA (mode « Rejouer » du site)  -> site/public/marche, site/data/analyste
  6. inventaire GCP (tables, tailles, requêtes, ce journal)          -> site/data/gcp.json
  7. publication : paquet de données sur Cloud Storage, puis redéploiement du site (Vercel)

Usage :
  python -m pipeline.refresh                      (tout)
  python -m pipeline.refresh --from silver        (reprendre à une étape)
  python -m pipeline.refresh --no-publish         (sans publier)
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "ops" / "last_refresh.json"
PY = sys.executable

STEPS = [
    ("bronze", "Eurostat : trafic par paire d'aéroports", [PY, "ingestion/eurostat_bronze.py"]),
    ("bronze", "OurAirports : référentiel des aéroports", [PY, "ingestion/ourairports_bronze.py"]),
    ("bronze", "Corrections de l'analyste", [PY, "ingestion/reference_bronze.py"]),
    ("silver", "Couche silver", [PY, "transform/run_sql.py", "silver"]),
    ("gold", "Couche gold", [PY, "transform/run_sql.py", "gold"]),
    ("dossiers", "Dossiers (chaîne d'instruction)", [PY, "-m", "agents.batch", "--llm", os.getenv("CAP_LLM", "groq,gemini")]),
    ("marche", "Études de marché", [PY, "-m", "agents.export_market"]),
    ("marche", "Sessions enregistrées des agents IA", [PY, "-m", "agents.record_examples"]),
    ("inventaire", "Inventaire GCP", [PY, "-m", "ops.gcp_inventory"]),
]
ORDER = ["bronze", "silver", "gold", "dossiers", "marche", "inventaire"]


def publish() -> str:
    """Envoie les données du site sur Cloud Storage puis déclenche le redéploiement du site."""
    bucket_name = os.getenv("CAP_SITE_BUCKET")
    if not bucket_name:
        return "publication ignorée : CAP_SITE_BUCKET non défini"
    from google.cloud import storage

    bundle = {}
    for path in sorted((ROOT / "site" / "data").rglob("*.json")):
        bundle[str(path.relative_to(ROOT / "site")).replace("\\", "/")] = json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((ROOT / "site" / "public" / "marche").glob("*.json")):
        bundle[str(path.relative_to(ROOT / "site")).replace("\\", "/")] = json.loads(path.read_text(encoding="utf-8"))
    blob = storage.Client().bucket(bucket_name).blob("cap-site-data.json")
    blob.cache_control = "no-cache"
    blob.upload_from_string(json.dumps(bundle, ensure_ascii=False, default=str), content_type="application/json")
    message = f"{len(bundle)} fichiers publiés sur gs://{bucket_name}/cap-site-data.json"
    hook = os.getenv("VERCEL_DEPLOY_HOOK")
    if hook:
        import requests

        requests.post(hook, timeout=30).raise_for_status()
        message += " · redéploiement du site demandé"
    return message


def main() -> int:
    load_dotenv()
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="start", default="bronze", choices=ORDER)
    p.add_argument("--no-publish", action="store_true")
    args = p.parse_args()

    log = {"debut": datetime.now(timezone.utc).isoformat(), "declencheur": os.getenv("CLOUD_RUN_JOB") and
           "Cloud Scheduler (Cloud Run Job)" or "manuel", "etapes": [], "statut": "en cours"}
    todo = [s for s in STEPS if ORDER.index(s[0]) >= ORDER.index(args.start)]
    for layer, label, cmd in todo:
        if layer == "inventaire":  # l'inventaire lit ce journal : on l'écrit juste avant
            LOG.parent.mkdir(exist_ok=True)
            LOG.write_text(json.dumps({**log, "statut": "réussi"}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n=== {label} ===", flush=True)
        started = time.perf_counter()
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(proc.stdout[-4000:], proc.stderr[-2000:] if proc.returncode else "", flush=True)
        tail = [line for line in proc.stdout.strip().splitlines() if line.strip()][-1:] or [""]
        log["etapes"].append({"couche": layer, "etape": label, "duree_s": round(time.perf_counter() - started, 1),
                              "statut": "ok" if proc.returncode == 0 else "échec", "resume": tail[0][:200]})
        if proc.returncode != 0:
            log["statut"] = f"échec à l'étape « {label} »"
            break
    else:
        log["statut"] = "réussi"
        if not args.no_publish:
            log["publication"] = publish()
    log["fin"] = datetime.now(timezone.utc).isoformat()
    LOG.parent.mkdir(exist_ok=True)
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRafraîchissement : {log['statut']}")
    return 0 if log["statut"] == "réussi" else 1


if __name__ == "__main__":
    sys.exit(main())
