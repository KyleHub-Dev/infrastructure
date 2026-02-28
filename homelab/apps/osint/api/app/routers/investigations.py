"""Investigation management endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from app.models.investigation import (
    InvestigationCreate,
    InvestigationResponse,
    InvestigationStatus,
)
from app.services.meilisearch import meili_service
from app.services.neo4j import neo4j_service
from app.tasks.analyzers import dispatch_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


def _format_investigation(raw: dict) -> InvestigationResponse:
    """Convert a raw Neo4j record into an InvestigationResponse."""
    return InvestigationResponse(
        id=raw["id"],
        query=raw["query"],
        observable_type=raw["observable_type"],
        legal_basis=raw["legal_basis"],
        purpose=raw["purpose"],
        justification=raw["justification"],
        ttl_days=raw["ttl_days"],
        status=raw.get("status", InvestigationStatus.PENDING),
        created_by=raw["created_by"],
        created_at=datetime.fromisoformat(raw["created_at"]),
        updated_at=datetime.fromisoformat(raw["updated_at"]),
        node_count=raw.get("node_count", 0),
        edge_count=raw.get("edge_count", 0),
    )


@router.post("/", response_model=InvestigationResponse, status_code=201)
async def create_investigation(body: InvestigationCreate, request: Request):
    """Create a new investigation and dispatch OSINT analysis tasks.

    Requires legal_basis and justification fields for GDPR DPIA compliance.
    """
    user: str = request.state.user

    # 1. Create investigation node in Neo4j
    raw = neo4j_service.create_investigation(
        query=body.query,
        observable_type=body.observable_type.value,
        legal_basis=body.legal_basis.value,
        purpose=body.purpose,
        justification=body.justification,
        ttl_days=body.ttl_days,
        created_by=user,
    )

    logger.info(
        "Investigation %s created by %s: query='%s' type=%s",
        raw["id"],
        user,
        body.query,
        body.observable_type.value,
    )

    # 2. Dispatch Celery tasks to worker queues (runs synchronously -
    #    this is just a lightweight fan-out via send_task, not the actual analysis)
    dispatch_analysis(
        investigation_id=raw["id"],
        query=body.query,
        observable_type=body.observable_type.value,
        ttl_days=body.ttl_days,
    )

    return _format_investigation(raw)


@router.get("/", response_model=list[InvestigationResponse])
async def list_investigations(request: Request):
    """List all investigations for the authenticated user."""
    user: str = request.state.user
    results = neo4j_service.list_investigations(user)
    return [_format_investigation(r) for r in results]


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(investigation_id: str, request: Request):
    """Get details of a specific investigation."""
    user: str = request.state.user
    raw = neo4j_service.get_investigation(investigation_id, user=user)

    if not raw:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return _format_investigation(raw)


@router.patch("/{investigation_id}", response_model=InvestigationResponse)
async def update_investigation_status(
    investigation_id: str,
    request: Request,
    status: InvestigationStatus,
):
    """Update the status of an investigation (e.g., mark as completed or archived)."""
    user: str = request.state.user

    existing = neo4j_service.get_investigation(investigation_id, user=user)
    if not existing:
        raise HTTPException(status_code=404, detail="Investigation not found")

    neo4j_service.update_investigation_status(investigation_id, status.value)

    updated = neo4j_service.get_investigation(investigation_id, user=user)
    return _format_investigation(updated)


@router.delete("/{investigation_id}", status_code=204)
async def delete_investigation(investigation_id: str, request: Request):
    """Delete an investigation and all associated data (GDPR Right to Erasure).

    Cascade deletes:
    - All Neo4j nodes and edges in the investigation subgraph
    - All Meilisearch documents referencing this investigation
    """
    user: str = request.state.user

    deleted = neo4j_service.delete_investigation(investigation_id, user=user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Also purge from Meilisearch
    try:
        meili_service.delete_by_investigation(investigation_id)
    except Exception:
        logger.exception(
            "Failed to delete Meilisearch documents for investigation %s",
            investigation_id,
        )

    logger.info("Investigation %s deleted by %s (cascade)", investigation_id, user)
