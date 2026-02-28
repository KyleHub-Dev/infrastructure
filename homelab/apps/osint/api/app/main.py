"""OSINT Platform - API Gateway

FastAPI application serving as the central API for the OSINT platform.
Handles authentication (via Pangolin Remote-User), investigation management,
observable submission, and graph queries.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import RemoteUserMiddleware
from app.config import settings
from app.routers import graph, investigations, observables
from app.services.meilisearch import meili_service
from app.services.neo4j import neo4j_service
from app.services.seed import seed_if_empty

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service connections on startup/shutdown."""
    neo4j_service.connect()
    meili_service.connect()
    seed_if_empty()
    logger.info("OSINT API started - Neo4j and Meilisearch connected")
    yield
    neo4j_service.close()
    logger.info("OSINT API shutting down")


app = FastAPI(
    title="OSINT Platform API",
    description="Self-hosted OSINT intelligence gathering and visualization platform.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# --- Middleware ---

app.add_middleware(RemoteUserMiddleware, header_name=settings.auth_header)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restricted by NEWT tunnel - only Pangolin can reach this
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---

app.include_router(investigations.router, prefix="/api/v1/investigations", tags=["Investigations"])
app.include_router(observables.router, prefix="/api/v1/observables", tags=["Observables"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["Graph"])


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "osint-api"}
