#!/usr/bin/env python3
"""Export an investigation from Neo4j as a JSON fixture for seeding.

Usage:
    python scripts/export_investigation.py <investigation_id>

Requires NEO4J_URI and NEO4J_AUTH environment variables (or .env file).
"""

import json
import os
import sys
from pathlib import Path

from neo4j import GraphDatabase


def main():
    inv_id = sys.argv[1] if len(sys.argv) > 1 else "inv-66c55026ce05"

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    auth_str = os.environ.get("NEO4J_AUTH", "neo4j/changeme")
    user, password = auth_str.split("/", 1)

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # Investigation node
        inv_result = session.run(
            "MATCH (inv:Investigation {id: $id}) RETURN inv {.*} AS inv",
            {"id": inv_id},
        ).single()
        if not inv_result:
            print(f"Investigation {inv_id} not found")
            sys.exit(1)
        investigation = dict(inv_result["inv"])

        # Observable nodes
        node_records = session.run(
            """
            MATCH (inv:Investigation {id: $id})-[:CONTAINS]->(n)
            RETURN labels(n) AS labels, n {.*} AS properties
            """,
            {"id": inv_id},
        ).data()
        nodes = [{"labels": r["labels"], "properties": dict(r["properties"])} for r in node_records]

        # Edges
        edge_records = session.run(
            """
            MATCH (inv:Investigation {id: $id})-[:CONTAINS]->(a)
            MATCH (inv)-[:CONTAINS]->(b)
            MATCH (a)-[r]->(b) WHERE type(r) <> 'CONTAINS'
            RETURN a.value AS source_value, b.value AS target_value,
                   type(r) AS rel_type, properties(r) AS rel_props
            """,
            {"id": inv_id},
        ).data()
        edges = [
            {
                "source_value": r["source_value"],
                "target_value": r["target_value"],
                "rel_type": r["rel_type"],
                "rel_props": dict(r["rel_props"]),
            }
            for r in edge_records
        ]

    driver.close()

    # Normalize created_by for demo
    investigation["created_by"] = "demo@osint.local"

    fixture = {"investigation": investigation, "nodes": nodes, "edges": edges}

    out_path = Path(__file__).parent.parent / "api" / "app" / "fixtures" / "seed_investigation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False, default=str))

    print(f"Exported {len(nodes)} nodes, {len(edges)} edges to {out_path}")


if __name__ == "__main__":
    main()
