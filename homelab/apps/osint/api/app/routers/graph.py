"""Graph query endpoints for the Sigma.js frontend visualization."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.services.meilisearch import meili_service
from app.services.neo4j import neo4j_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/investigation/{investigation_id}")
async def get_investigation_graph(investigation_id: str, request: Request):
    """Return the full graph (nodes + edges) for a given investigation.

    Response format is optimized for Sigma.js consumption:
    {
        "nodes": [
            {"id": "...", "label": "jdoe_89", "type": "Username", "x": 0, "y": 0, "size": 10}
        ],
        "edges": [
            {"id": "...", "source": "...", "target": "...", "label": "REGISTERED_ON"}
        ]
    }
    """
    user: str = request.state.user

    # Verify investigation exists and belongs to user
    investigation = neo4j_service.get_investigation(investigation_id, user=user)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    graph = neo4j_service.get_investigation_graph(investigation_id, user=user)
    return graph


@router.get("/neighbors/{node_id}")
async def get_node_neighbors(
    node_id: str,
    request: Request,
    depth: int = Query(default=1, ge=1, le=3, description="Hop depth (max 3)"),
):
    """Get the neighborhood of a specific node (1–3 hops).

    Used for interactive graph exploration — clicking a node loads
    its connections without fetching the entire investigation graph.
    """
    user: str = request.state.user

    graph = neo4j_service.get_node_neighbors(node_id, user=user, depth=depth)

    if not graph["nodes"]:
        raise HTTPException(status_code=404, detail="Node not found or not accessible")

    return graph


@router.get("/search")
async def search_graph(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query"),
    investigation_id: str | None = Query(default=None, description="Scope to investigation"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Full-text search across all observables via Meilisearch.

    Returns matching documents with references for cross-linking
    with the graph visualization.
    """
    # Build filter
    filters = None
    if investigation_id:
        # Verify ownership
        user: str = request.state.user
        investigation = neo4j_service.get_investigation(investigation_id, user=user)
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")
        filters = f"investigation_id = '{investigation_id}'"

    results = meili_service.search(query=q, filters=filters, limit=limit)

    return {
        "query": q,
        "total_hits": results.get("estimatedTotalHits", 0),
        "hits": [
            {
                "id": hit.get("id"),
                "investigation_id": hit.get("investigation_id"),
                "target_entity": hit.get("target_entity"),
                "entity_value": hit.get("entity_value"),
                "entity_type": hit.get("entity_type"),
                "tool_source": hit.get("tool_source"),
                "indexed_at": hit.get("indexed_at"),
            }
            for hit in results.get("hits", [])
        ],
    }


@router.get("/stats/{investigation_id}")
async def get_investigation_stats(investigation_id: str, request: Request):
    """Return summary statistics for an investigation's graph.

    Useful for dashboard overview cards without loading the full graph.
    """
    user: str = request.state.user

    investigation = neo4j_service.get_investigation(investigation_id, user=user)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Get type breakdown
    type_breakdown = neo4j_service.execute_read(
        """
        MATCH (inv:Investigation {id: $inv_id, created_by: $user})-[:CONTAINS]->(n)
        WITH [l IN labels(n) WHERE l <> 'Observable' | l][0] AS entity_type
        RETURN entity_type, count(*) AS count
        ORDER BY count DESC
        """,
        {"inv_id": investigation_id, "user": user},
    )

    # Get tool breakdown
    tool_breakdown = neo4j_service.execute_read(
        """
        MATCH (inv:Investigation {id: $inv_id, created_by: $user})-[:CONTAINS]->(n)
        RETURN n.tool_source AS tool, count(*) AS count
        ORDER BY count DESC
        """,
        {"inv_id": investigation_id, "user": user},
    )

    return {
        "investigation_id": investigation_id,
        "status": investigation.get("status"),
        "node_count": investigation.get("node_count", 0),
        "edge_count": investigation.get("edge_count", 0),
        "by_type": {r["entity_type"]: r["count"] for r in type_breakdown if r.get("entity_type")},
        "by_tool": {r["tool"]: r["count"] for r in tool_breakdown if r.get("tool")},
    }
