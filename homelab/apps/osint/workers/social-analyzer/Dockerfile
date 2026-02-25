FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    git gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /worker

COPY workers/base/worker_base.py ./worker_base.py
RUN uv pip install --system celery[redis]>=5.4 redis>=5.0 neo4j>=5.0 meilisearch>=0.31

COPY workers/social-analyzer/requirements.txt ./requirements.txt
RUN uv pip install --system -r requirements.txt

COPY workers/social-analyzer/analyzer.py ./worker.py
