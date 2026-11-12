"""API de CAP, déployée sur Google Cloud Run.

Points d'entrée :
  GET /health                     état du service ; ?bigquery=1 mesure un aller-retour BigQuery
  GET /marche/{iata}              étude de marché en direct sur BigQuery (toute destination)
  GET /instruire?dest=MNL         chaîne d'instruction d'un dossier (six étapes), en direct
  GET /analyste?question=...      les agents IA (Analyste, Contradicteur) répondent à une question libre
                                  en choisissant eux-mêmes leurs outils
  (les deux derniers en flux Server-Sent Events : le site affiche chaque étape à mesure)

Le site appelle cette API. Si elle ne répond pas, le site bascule sur les données exportées :
la démonstration ne dépend jamais d'un seul service.

En local :
  uvicorn api.main:app --reload --port 8080
  CAP_SOURCE=snapshot uvicorn api.main:app --port 8080      (sans BigQuery, sur l'instantané)
"""
import json
import os
import threading
import time
from collections import defaultdict, deque
from datetime import date, datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

from agents.analyst import analyse  # noqa: E402
from agents.batch import COUNTRY_TO_REGION  # noqa: E402
from agents.toolchat import ToolChat  # noqa: E402
from agents.tools import ToolBox  # noqa: E402
from agents.datasource import BigQuerySource, SnapshotSource  # noqa: E402
from agents.graph import stream_dossier  # noqa: E402
from agents.llm import LLMError, get_llm  # noqa: E402
from agents.market import default_scenario, study_live  # noqa: E402
from economics import load_assumptions  # noqa: E402

app = FastAPI(title="CAP · Network Planning Copilot", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CAP_ALLOWED_ORIGINS", "*").split(",")],
    allow_methods=["GET"],
    allow_headers=["*"],
)

ASSUMPTIONS = load_assumptions()
STARTED_AT = datetime.now(timezone.utc)
_lock = threading.Lock()
_client = None

# Limite simple par adresse IP : protège le quota de l'IA et la facture BigQuery.
LIMIT = int(os.getenv("CAP_LIMIT_PER_10MIN", "8"))
_calls: dict[str, deque] = defaultdict(deque)


def source():
    """Une source neuve par requête (chacune garde sa propre trace), un client BigQuery partagé."""
    global _client
    if os.getenv("CAP_SOURCE", "bigquery") == "snapshot":
        return SnapshotSource(os.getenv("CAP_SNAPSHOT", "reference/snapshots/demo.json"))
    with _lock:
        if _client is None:
            _client = BigQuerySource()._client
    return BigQuerySource(client=_client)


def throttle(request: Request) -> None:
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    now, q = time.time(), _calls[ip]
    while q and now - q[0] > 600:
        q.popleft()
    if len(q) >= LIMIT:
        raise HTTPException(429, "Trop de demandes : réessayez dans quelques minutes.")
    q.append(now)


def _iata(value: str) -> str:
    value = (value or "").strip().upper()
    if not (len(value) == 3 and value.isalpha()):
        raise HTTPException(400, "Code IATA attendu : trois lettres, par exemple MNL.")
    return value


@app.get("/health")
def health(bigquery: bool = False):
    src = source()
    out = {"statut": "ok", "service": "cap-api", "demarre_le": STARTED_AT.isoformat(),
           "source": src.name, "projet": getattr(src, "project", None),
           "cloud_run": os.getenv("K_SERVICE"), "revision": os.getenv("K_REVISION")}
    if bigquery and isinstance(src, BigQuerySource):
        started = time.perf_counter()
        src._query("SELECT 1 AS ok", [], "ping")
        job = src.take_jobs()[-1]
        out["bigquery"] = {"duree_ms": round((time.perf_counter() - started) * 1000), "job_id": job["job_id"]}
    return out


@app.get("/marche/{iata}")
def marche(iata: str, request: Request):
    throttle(request)
    src = source()
    if not hasattr(src, "market_origins"):
        raise HTTPException(503, "Étude en direct indisponible sur un instantané.")
    study = study_live(src, _iata(iata))
    if study.get("introuvable"):
        raise HTTPException(404, f"Aucune donnée pour {iata.upper()}.")
    return study


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@app.get("/instruire")
def instruire(request: Request, dest: str, freq: float | None = Query(None, ge=1, le=21),
              aircraft: str | None = None):
    throttle(request)
    dest = _iata(dest)
    if aircraft and aircraft not in ASSUMPTIONS.aircraft:
        raise HTTPException(400, f"Appareil inconnu. Choix : {', '.join(ASSUMPTIONS.aircraft)}")
    try:
        llm = get_llm(os.getenv("CAP_LLM", "groq,gemini"))
    except LLMError:
        llm = get_llm("offline")

    def events():
        src = source()
        opp = src.opportunity(dest)
        country = (opp or {}).get("partner_country")
        distance = (opp or {}).get("distance_from_cdg_km")
        if not opp and hasattr(src, "airport"):
            ap = src.airport(dest) or {}
            country, distance = ap.get("country_iso2"), ap.get("distance_from_cdg_km")
        src.take_jobs()
        if not distance:
            yield _sse({"type": "erreur", "message": f"{dest} est introuvable dans le référentiel des aéroports."})
            return
        scenario = default_scenario(float(distance))
        request_ = {"dest": dest, "freq": freq or scenario["freq"], "aircraft": aircraft or scenario["aircraft"],
                    "region": COUNTRY_TO_REGION.get((country or "").upper()), "distance": distance}
        yield _sse({"type": "scenario", "scenario": request_, "llm": llm.name, "source": src.name})
        started = time.perf_counter()
        try:
            for event in stream_dossier(src, llm, ASSUMPTIONS, request_, today=date.today()):
                event["t_ms"] = round((time.perf_counter() - started) * 1000)
                yield _sse(event)
        except Exception as exc:  # une erreur doit apparaître sur le site, pas couper le flux en silence
            yield _sse({"type": "erreur", "message": f"Instruction interrompue : {str(exc)[:200]}"})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/analyste")
def analyste(request: Request, question: str = Query(..., min_length=8, max_length=400)):
    throttle(request)
    chat = ToolChat()
    if not chat.available():
        raise HTTPException(503, "Aucune clé d'IA configurée pour les agents.")

    def events():
        started = time.perf_counter()
        try:
            for event in analyse(question.strip(), ToolBox(source(), ASSUMPTIONS), chat):
                event["t_ms"] = round((time.perf_counter() - started) * 1000)
                yield _sse(event)
        except Exception as exc:
            yield _sse({"type": "erreur", "message": f"Analyse interrompue : {str(exc)[:200]}"})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
