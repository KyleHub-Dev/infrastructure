"""Observable query and management endpoints."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from app.models.observable import ObservableResponse
from app.services.meilisearch import meili_service
from app.services.neo4j import neo4j_service
from app.tasks.analyzers import dispatch_analysis

logger = logging.getLogger(__name__)
router = APIRouter()

# Map Neo4j entity types to observable types for pivot dispatch
ENTITY_TYPE_TO_OBSERVABLE: dict[str, str] = {
    "Username": "username",
    "Email": "email",
    "Domain": "domain",
    "IPAddress": "ip_address",
    "PlatformAccount": "username",  # Platform accounts can be pivoted as usernames
    "Phone": "username",
    "Person": "username",
}


def _format_observable(raw: dict) -> ObservableResponse:
    """Convert a raw Neo4j record into an ObservableResponse."""
    # Parse metadata if stored as JSON string
    metadata = raw.get("metadata") or {}
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    # Convert TTL (ms timestamp) to expires_at datetime
    ttl_ms = raw.get("ttl") or 0
    if ttl_ms > 0:
        expires_at = datetime.utcfromtimestamp(ttl_ms / 1000)
    else:
        expires_at = datetime.utcnow()

    created_at_raw = raw.get("created_at")
    if isinstance(created_at_raw, str):
        created_at = datetime.fromisoformat(created_at_raw)
    elif isinstance(created_at_raw, (int, float)):
        created_at = datetime.utcfromtimestamp(created_at_raw / 1000)
    else:
        created_at = datetime.utcnow()

    return ObservableResponse(
        id=raw["id"],
        entity_type=raw.get("entity_type", "Observable"),
        value=raw.get("value", ""),
        metadata=metadata,
        tool_source=raw.get("tool_source", "unknown"),
        confidence=raw.get("confidence") or 0.5,
        investigation_id=raw.get("investigation_id", ""),
        created_at=created_at,
        expires_at=expires_at,
    )


@router.get("/", response_model=list[ObservableResponse])
async def list_observables(
    request: Request,
    investigation_id: str | None = None,
    entity_type: str | None = None,
):
    """List observables, optionally filtered by investigation or entity type."""
    user: str = request.state.user

    results = neo4j_service.list_observables(
        user=user,
        investigation_id=investigation_id,
        entity_type=entity_type,
    )
    return [_format_observable(r) for r in results]


@router.get("/{observable_id}", response_model=ObservableResponse)
async def get_observable(observable_id: str, request: Request):
    """Get a specific observable entity with its metadata."""
    user: str = request.state.user
    raw = neo4j_service.get_observable(observable_id, user=user)

    if not raw:
        raise HTTPException(status_code=404, detail="Observable not found")

    return _format_observable(raw)


@router.post("/{observable_id}/analyze")
async def trigger_pivot_analysis(observable_id: str, request: Request):
    """Trigger a secondary analysis pivot on a discovered observable.

    This enables the closed-loop intelligence gathering flow:
    1. Analyst discovers an email node in the graph
    2. Clicks "analyze" on it
    3. System dispatches appropriate analyzers (e.g., Holehe for email)
    4. Results merge back into the same investigation's graph
    """
    user: str = request.state.user
    raw = neo4j_service.get_observable(observable_id, user=user)

    if not raw:
        raise HTTPException(status_code=404, detail="Observable not found")

    entity_type = raw.get("entity_type", "")
    observable_type = ENTITY_TYPE_TO_OBSERVABLE.get(entity_type)

    if not observable_type:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pivot on entity type '{entity_type}' — no analyzers registered",
        )

    investigation_id = raw.get("investigation_id", "")
    value = raw.get("value", "")

    if not value or not investigation_id:
        raise HTTPException(status_code=400, detail="Observable missing value or investigation reference")

    # Dispatch pivot analysis asynchronously
    dispatch_analysis.delay(
        investigation_id=investigation_id,
        query=value,
        observable_type=observable_type,
    )

    logger.info(
        "Pivot analysis triggered: observable=%s type=%s investigation=%s by=%s",
        observable_id,
        observable_type,
        investigation_id,
        user,
    )

    return {
        "status": "dispatched",
        "observable_id": observable_id,
        "observable_value": value,
        "observable_type": observable_type,
        "investigation_id": investigation_id,
    }


@router.delete("/{observable_id}", status_code=204)
async def delete_observable(observable_id: str, request: Request):
    """Delete a specific observable and its relationships (GDPR Article 17)."""
    user: str = request.state.user

    deleted = neo4j_service.delete_observable(observable_id, user=user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Observable not found")

    # Also remove any Meilisearch documents for this node
    try:
        meili_service.index.delete_documents({
            "filter": f"entity_value = '{observable_id}'"
        })
    except Exception:
        logger.exception("Failed to delete Meilisearch documents for observable %s", observable_id)

    logger.info("Observable %s deleted by %s", observable_id, user)
