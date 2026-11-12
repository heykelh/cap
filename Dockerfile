# Image unique de CAP sur Google Cloud Run :
#   * service « cap-api »     : l'API en direct (commande par défaut ci-dessous) ;
#   * job « cap-refresh »     : le rafraîchissement mensuel (commande : python -m pipeline.refresh).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agents ./agents
COPY api ./api
COPY economics ./economics
COPY ingestion ./ingestion
COPY ops ./ops
COPY pipeline ./pipeline
COPY reference ./reference
COPY transform ./transform

CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}
