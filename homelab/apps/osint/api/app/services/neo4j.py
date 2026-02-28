"""Neo4j graph database client service.

Provides typed methods for investigation CRUD, observable management,
and graph queries for the Sigma.js frontend.
"""

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from app.config import settings

logger = logging.getLogger(__name__)


def _hash_position(node_id: str) -> dict[str, float]:
    """Deterministic initial x/y coords from node ID. Sigma.js force layout repositions these."""
    h = int(hashlib.md5(node_id.encode()).hexdigest()[:8], 16)
    return {"x": (h % 1000) / 100.0, "y": ((h >> 8) % 1000) / 100.0}


class Neo4jService:
    """Manages the Neo4j driver connection and provides domain-specific queries."""

    def __init__(self) -> None:
        self._driver = None

    def connect(self, max_retries: int = 10, retry_delay: float = 3.0) -> None:
        """Initialize the Neo4j driver, retrying until the server is reachable."""
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        for attempt in range(1, max_retries + 1):
            try:
                self._driver.verify_connectivity()
                logger.info("Connected to Neo4j at %s", settings.neo4j_uri)
                return
            except ServiceUnavailable:
                if attempt == max_retries:
                    raise
                logger.warning(
                    "Neo4j not ready (attempt %d/%d), retrying in %.0fs...",
                    attempt, max_retries, retry_delay,
                )
                time.sleep(retry_delay)

    def close(self) -> None:
        """Close the Neo4j driver."""
        if self._driver:
            self._driver.close()

    @property
    def driver(self):
        if not self._driver:
            raise RuntimeError("Neo4j driver not initialized. Call connect() first.")
        return self._driver

    def execute_read(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Execute a read transaction and return results."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def execute_write(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Execute a write transaction and return results."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    # ── Investigation CRUD ───────────────────────────────────────────

    def create_investigation(
        self,
        *,
        query: str,
        observable_type: str,
        legal_basis: str,
        purpose: str,
        justification: str,
        ttl_days: int,
        created_by: str,
    ) -> dict:
        """Create a new Investigation node and return its properties."""
        inv_id = f"inv-{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow().isoformat()
        ttl_ms = int((datetime.utcnow() + timedelta(days=ttl_days)).timestamp() * 1000)

        result = self.execute_write(
            """
            CREATE (inv:Investigation {
                id: $id,
                query: $query,
                observable_type: $observable_type,
                legal_basis: $legal_basis,
                purpose: $purpose,
                justification: $justification,
                ttl_days: $ttl_days,
                status: 'pending',
                created_by: $created_by,
                created_at: $now,
                updated_at: $now,
                ttl: $ttl_ms
            })
            RETURN inv {.*} AS investigation
            """,
            {
                "id": inv_id,
                "query": query,
                "observable_type": observable_type,
                "legal_basis": legal_basis,
                "purpose": purpose,
                "justification": justification,
                "ttl_days": ttl_days,
                "created_by": created_by,
                "now": now,
                "ttl_ms": ttl_ms,
            },
        )
        return result[0]["investigation"]

    def get_investigation(self, investigation_id: str, user: str | None = None) -> dict | None:
        """Retrieve a single investigation by ID, optionally scoped to a user."""
        where_clause = "WHERE inv.id = $id"
        params: dict[str, Any] = {"id": investigation_id}

        if user:
            where_clause += " AND inv.created_by = $user"
            params["user"] = user

        result = self.execute_read(
            f"""
            MATCH (inv:Investigation)
            {where_clause}
            OPTIONAL MATCH (inv)-[:CONTAINS]->(n)
            OPTIONAL MATCH (inv)-[:CONTAINS]->()-[r]-()
            WITH inv, count(DISTINCT n) AS node_count, count(DISTINCT r) AS edge_count
            RETURN inv {{.*, node_count: node_count, edge_count: edge_count}} AS investigation
            """,
            params,
        )
        return result[0]["investigation"] if result else None

    def list_investigations(self, user: str) -> list[dict]:
        """List all investigations for a given user."""
        result = self.execute_read(
            """
            MATCH (inv:Investigation)
            WHERE inv.created_by = $user
            OPTIONAL MATCH (inv)-[:CONTAINS]->(n)
            OPTIONAL MATCH (inv)-[:CONTAINS]->()-[r]-()
            WITH inv, count(DISTINCT n) AS node_count, count(DISTINCT r) AS edge_count
            RETURN inv {.*, node_count: node_count, edge_count: edge_count} AS investigation
            ORDER BY inv.created_at DESC
            """,
            {"user": user},
        )
        return [r["investigation"] for r in result]

    def update_investigation_status(self, investigation_id: str, status: str) -> None:
        """Update the status of an investigation."""
        self.execute_write(
            """
            MATCH (inv:Investigation {id: $id})
            SET inv.status = $status, inv.updated_at = $now
            """,
            {"id": investigation_id, "status": status, "now": datetime.utcnow().isoformat()},
        )

    def delete_investigation(self, investigation_id: str, user: str) -> bool:
        """Delete an investigation and all its contained observables (cascade).

        Returns True if the investigation was found and deleted.
        """
        result = self.execute_write(
            """
            MATCH (inv:Investigation {id: $id, created_by: $user})
            OPTIONAL MATCH (inv)-[:CONTAINS]->(n)
            DETACH DELETE n, inv
            RETURN count(inv) AS deleted
            """,
            {"id": investigation_id, "user": user},
        )
        return bool(result and result[0].get("deleted", 0) > 0)

    # ── Observable CRUD ──────────────────────────────────────────────

    def list_observables(
        self,
        user: str,
        investigation_id: str | None = None,
        entity_type: str | None = None,
    ) -> list[dict]:
        """List observables, optionally filtered by investigation or entity type."""
        conditions = ["inv.created_by = $user"]
        params: dict[str, Any] = {"user": user}

        if investigation_id:
            conditions.append("inv.id = $investigation_id")
            params["investigation_id"] = investigation_id

        type_filter = ""
        if entity_type:
            type_filter = f"AND $entity_type IN labels(n)"
            params["entity_type"] = entity_type

        where = " AND ".join(conditions)

        result = self.execute_read(
            f"""
            MATCH (inv:Investigation)-[:CONTAINS]->(n)
            WHERE {where} {type_filter}
            RETURN
                elementId(n) AS id,
                [l IN labels(n) WHERE l <> 'Observable' | l][0] AS entity_type,
                n.value AS value,
                n.metadata AS metadata,
                n.tool_source AS tool_source,
                n.confidence AS confidence,
                n.investigation_id AS investigation_id,
                n.created_at AS created_at,
                n.ttl AS ttl
            ORDER BY n.created_at DESC
            """,
            params,
        )
        return result

    def get_observable(self, observable_id: str, user: str) -> dict | None:
        """Get a single observable by its element ID, scoped to the user."""
        result = self.execute_read(
            """
            MATCH (inv:Investigation)-[:CONTAINS]->(n)
            WHERE elementId(n) = $id AND inv.created_by = $user
            RETURN
                elementId(n) AS id,
                [l IN labels(n) WHERE l <> 'Observable' | l][0] AS entity_type,
                n.value AS value,
                n.metadata AS metadata,
                n.tool_source AS tool_source,
                n.confidence AS confidence,
                n.investigation_id AS investigation_id,
                n.created_at AS created_at,
                n.ttl AS ttl
            """,
            {"id": observable_id, "user": user},
        )
        return result[0] if result else None

    def delete_observable(self, observable_id: str, user: str) -> bool:
        """Delete a single observable and its relationships."""
        result = self.execute_write(
            """
            MATCH (inv:Investigation)-[:CONTAINS]->(n)
            WHERE elementId(n) = $id AND inv.created_by = $user
            DETACH DELETE n
            RETURN count(n) AS deleted
            """,
            {"id": observable_id, "user": user},
        )
        return bool(result and result[0].get("deleted", 0) > 0)

    # ── Graph Queries (Sigma.js) ─────────────────────────────────────

    def get_investigation_graph(self, investigation_id: str, user: str) -> dict:
        """Return the full graph for an investigation in Sigma.js format.

        Returns: {"nodes": [...], "edges": [...]}
        """
        # Fetch all nodes in the investigation
        node_results = self.execute_read(
            """
            MATCH (inv:Investigation {id: $inv_id, created_by: $user})-[:CONTAINS]->(n)
            RETURN
                elementId(n) AS id,
                n.value AS label,
                [l IN labels(n) WHERE l <> 'Observable' | l][0] AS type,
                n.confidence AS confidence,
                n.tool_source AS tool_source
            """,
            {"inv_id": investigation_id, "user": user},
        )

        # Fetch all edges between nodes in the investigation
        edge_results = self.execute_read(
            """
            MATCH (inv:Investigation {id: $inv_id, created_by: $user})-[:CONTAINS]->(a)
            MATCH (inv)-[:CONTAINS]->(b)
            MATCH (a)-[r]->(b)
            WHERE type(r) <> 'CONTAINS'
            RETURN
                elementId(r) AS id,
                elementId(a) AS source,
                elementId(b) AS target,
                type(r) AS label
            """,
            {"inv_id": investigation_id, "user": user},
        )

        nodes = [
            {
                "id": n["id"],
                "label": n["label"] or "unknown",
                "type": n["type"] or "Observable",
                "size": 10 + (n.get("confidence") or 0.5) * 10,
                "tool_source": n.get("tool_source", ""),
                **_hash_position(n["id"]),
            }
            for n in node_results
        ]

        edges = [
            {"id": e["id"], "source": e["source"], "target": e["target"], "label": e["label"]}
            for e in edge_results
        ]

        return {"nodes": nodes, "edges": edges}

    def get_node_neighbors(self, node_id: str, user: str, depth: int = 1) -> dict:
        """Get neighborhood of a node up to N hops, returned in Sigma.js format."""
        depth = min(depth, 3)  # Cap at 3 hops to prevent expensive queries

        # Plain Cypher variable-length path - no APOC dependency
        node_results = self.execute_read(
            """
            MATCH (inv:Investigation)-[:CONTAINS]->(start)
            WHERE elementId(start) = $node_id AND inv.created_by = $user
            MATCH (start)-[*1..$depth]-(neighbor)
            WITH collect(DISTINCT neighbor) + [start] AS all_nodes
            UNWIND all_nodes AS n
            RETURN DISTINCT
                elementId(n) AS id,
                n.value AS label,
                [l IN labels(n) WHERE l <> 'Observable' | l][0] AS type
            """,
            {"node_id": node_id, "user": user, "depth": depth},
        )

        if not node_results:
            return {"nodes": [], "edges": []}

        # Collect IDs for edge query
        node_ids = [n["id"] for n in node_results]

        edge_results = self.execute_read(
            """
            UNWIND $node_ids AS nid
            MATCH (a)-[r]->(b)
            WHERE elementId(a) = nid
              AND elementId(b) IN $node_ids
              AND type(r) <> 'CONTAINS'
            RETURN DISTINCT
                elementId(r) AS id,
                elementId(a) AS source,
                elementId(b) AS target,
                type(r) AS label
            """,
            {"node_ids": node_ids},
        )

        nodes = [{"id": n["id"], "label": n["label"] or "unknown", "type": n["type"] or "Observable", "size": 10, **_hash_position(n["id"])} for n in node_results]
        edges = [{"id": e["id"], "source": e["source"], "target": e["target"], "label": e["label"]} for e in edge_results]

        return {"nodes": nodes, "edges": edges}


# Singleton instance
neo4j_service = Neo4jService()
