FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /worker

COPY workers/base/worker_base.py ./worker_base.py

# Shared worker dependencies
RUN uv pip install --system celery[redis]>=5.4 redis>=5.0 neo4j>=5.0 meilisearch>=0.31
