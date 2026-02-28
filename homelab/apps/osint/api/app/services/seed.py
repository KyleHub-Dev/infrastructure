"""Seed the database with schema and demo investigation if empty."""

import json
import logging
import os
from pathlib import Path

from app.services.neo4j import neo4j_service

logger = logging.getLogger(__name__)
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "seed_investigation.json"
SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "config" / "neo4j" / "init.cypher"

# Schema statements (inline fallback if init.cypher isn't in the container)
SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT username_unique IF NOT EXISTS FOR (u:Username) REQUIRE u.value IS UNIQUE",
    "CREATE CONSTRAINT email_unique IF NOT EXISTS FOR (e:Email) REQUIRE e.value IS UNIQUE",
    "CREATE CONSTRAINT domain_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.value IS UNIQUE",
    "CREATE CONSTRAINT ip_unique IF NOT EXISTS FOR (i:IPAddress) REQUIRE i.value IS UNIQUE",
    "CREATE CONSTRAINT platform_account_unique IF NOT EXISTS FOR (a:PlatformAccount) REQUIRE a.value IS UNIQUE",
    "CREATE CONSTRAINT investigation_id_unique IF NOT EXISTS FOR (inv:Investigation) REQUIRE inv.id IS UNIQUE",
    "CREATE INDEX observable_value IF NOT EXISTS FOR (n:Observable) ON (n.value)",
    "CREATE INDEX node_ttl IF NOT EXISTS FOR (n:Observable) ON (n.ttl)",
    "CREATE INDEX investigation_created_by IF NOT EXISTS FOR (inv:Investigation) ON (inv.created_by)",
    "CREATE INDEX investigation_status IF NOT EXISTS FOR (inv:Investigation) ON (inv.status)",
]


def ensure_schema() -> None:
    """Create Neo4j constraints and indexes if they don't exist."""
    for stmt in SCHEMA_STATEMENTS:
        try:
            neo4j_service.execute_write(stmt)
        except Exception as e:
            logger.debug("Schema statement skipped (%s): %s", e, stmt[:60])
    logger.info("Neo4j schema ensured")


def seed_if_empty() -> None:
    """Apply schema, then load demo investigation if the database has no investigations."""
    ensure_schema()

    if not FIXTURE_PATH.exists():
        logger.debug("No seed fixture found at %s, skipping", FIXTURE_PATH)
        return

    result = neo4j_service.execute_read(
        "MATCH (inv:Investigation) RETURN count(inv) AS cnt LIMIT 1"
    )
    if result and result[0].get("cnt", 0) > 0:
        logger.info("Database already has investigations, skipping seed")
        return

    logger.info("Seeding database with demo investigation...")
    data = json.loads(FIXTURE_PATH.read_text())

    # Use the configured default user so the seed is visible to the actual auth user
    seed_user = os.environ.get("SEED_USER", "demo@osint.local")

    inv = data["investigation"]
    inv["created_by"] = seed_user
    neo4j_service.execute_write(
        "CREATE (inv:Investigation $props)",
        {"props": inv},
    )

    for node in data["nodes"]:
        props = node["properties"]
        extra_labels = [l for l in node["labels"] if l != "Observable"]
        neo4j_service.execute_write(
            """
            CREATE (n:Observable $props)
            WITH n
            CALL apoc.create.addLabels(n, $labels) YIELD node
            RETURN node
            """,
            {"props": props, "labels": extra_labels},
        )

    neo4j_service.execute_write(
        """
        MATCH (inv:Investigation {id: $inv_id})
        MATCH (n:Observable {investigation_id: $inv_id})
        MERGE (inv)-[:CONTAINS]->(n)
        """,
        {"inv_id": inv["id"]},
    )

    for edge in data["edges"]:
        neo4j_service.execute_write(
            """
            MATCH (a:Observable {value: $src})
            MATCH (b:Observable {value: $tgt})
            CALL apoc.create.relationship(a, $rel_type, $props, b) YIELD rel
            RETURN rel
            """,
            {
                "src": edge["source_value"],
                "tgt": edge["target_value"],
                "rel_type": edge["rel_type"],
                "props": edge.get("rel_props", {}),
            },
        )

    logger.info(
        "Seeded %d nodes and %d edges for investigation %s (user: %s)",
        len(data["nodes"]),
        len(data["edges"]),
        inv["id"],
        seed_user,
    )
