"""Base class for all OSINT tool worker analyzers.

Every worker extends this class and implements the `analyze()` and
`normalize()` methods. The base class handles:
- Celery integration
- Neo4j graph writes (normalized discoveries)
- Meilisearch raw payload indexing
- TTL timestamp calculation for GDPR compliance
"""

import json
import logging
import os
import subprocess
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

import meilisearch
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class WorkerBase(ABC):
    """Abstract base for OSINT tool workers."""

    TOOL_NAME: str = "unknown"

    def __init__(self):
        self.neo4j_uri = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
        neo4j_auth = os.environ.get("NEO4J_AUTH", "neo4j/changeme")
        self.neo4j_user, self.neo4j_password = neo4j_auth.split("/", 1)
        self.meili_url = os.environ.get("MEILI_URL", "http://meilisearch:7700")
        self.default_ttl_days = int(os.environ.get("DEFAULT_TTL_DAYS", "365"))
        self.tor_proxy = os.environ.get("TOR_SOCKS_PROXY", "")

    def _get_neo4j_driver(self):
        return GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password),
        )

    def _get_meili_client(self):
        return meilisearch.Client(self.meili_url)

    def calculate_ttl_ms(self, ttl_days: int | None = None) -> int:
        """Calculate a TTL timestamp in milliseconds for GDPR storage limitation."""
        days = ttl_days or self.default_ttl_days
        expires = datetime.utcnow() + timedelta(days=days)
        return int(expires.timestamp() * 1000)

    def run_cli_tool(self, command: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Execute a CLI tool as a subprocess with timeout."""
        logger.info("[%s] Running: %s", self.TOOL_NAME, " ".join(command))
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def persist_to_graph(self, discoveries: list[dict], investigation_id: str):
        """Write normalized discoveries as nodes and edges to Neo4j."""
        driver = self._get_neo4j_driver()
        try:
            with driver.session() as session:
                for discovery in discoveries:
                    session.run(
                        """
                        MERGE (target {value: $target_value})
                        ON CREATE SET target:Observable,
                                      target.created_at = timestamp()

                        MERGE (entity {value: $entity_value})
                        ON CREATE SET entity.created_at = timestamp()

                        // Set the appropriate label dynamically via APOC
                        CALL apoc.create.addLabels(entity, [$entity_type]) YIELD node

                        MERGE (target)-[r:ASSOCIATED_WITH]->(entity)
                        SET r.tool_source = $tool_source,
                            r.confidence = $confidence,
                            r.investigation_id = $investigation_id,
                            r.discovered_at = timestamp()

                        SET entity.ttl = $ttl,
                            entity.tool_source = $tool_source,
                            entity.investigation_id = $investigation_id,
                            entity.metadata = $metadata
                        """,
                        {
                            "target_value": discovery["target_entity"],
                            "entity_value": discovery["entity_value"],
                            "entity_type": discovery["entity_type"],
                            "tool_source": discovery["tool_source"],
                            "confidence": discovery.get("confidence_score", 0.5),
                            "investigation_id": investigation_id,
                            "ttl": discovery["ttl_timestamp"],
                            "metadata": json.dumps(discovery.get("entity_metadata", {})),
                        },
                    )
        finally:
            driver.close()

    def persist_to_meili(self, raw_output: dict, investigation_id: str, target: str):
        """Index the raw tool output in Meilisearch for full-text search."""
        client = self._get_meili_client()
        index = client.index("osint_documents")

        expires_at = datetime.utcnow() + timedelta(days=self.default_ttl_days)

        document = {
            "id": str(uuid.uuid4()),
            "investigation_id": investigation_id,
            "target_entity": target,
            "tool_source": self.TOOL_NAME,
            "raw_content": json.dumps(raw_output),
            "entity_type": "raw_output",
            "indexed_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        index.add_documents([document])

    @abstractmethod
    def analyze(self, observable: str, **kwargs) -> dict:
        """Run the OSINT tool and return raw output.

        Must be implemented by each worker.
        """
        ...

    @abstractmethod
    def normalize(self, raw_output: dict, target: str, investigation_id: str) -> list[dict]:
        """Normalize raw tool output into a list of discovery dicts.

        Each discovery should follow the NormalizedDiscovery schema.
        Must be implemented by each worker.
        """
        ...

    def execute(self, observable: str, investigation_id: str, ttl_days: int | None = None, **kwargs):
        """Full execution pipeline: analyze → normalize → persist."""
        # 1. Run the tool
        raw_output = self.analyze(observable, **kwargs)

        # 2. Index raw output
        self.persist_to_meili(raw_output, investigation_id, observable)

        # 3. Normalize
        discoveries = self.normalize(raw_output, observable, investigation_id)

        # 4. Apply TTL to each discovery
        ttl_ms = self.calculate_ttl_ms(ttl_days)
        for d in discoveries:
            d["ttl_timestamp"] = ttl_ms

        # 5. Persist normalized graph data
        self.persist_to_graph(discoveries, investigation_id)

        logger.info(
            "[%s] Completed: %d discoveries for '%s' in investigation %s",
            self.TOOL_NAME,
            len(discoveries),
            observable,
            investigation_id,
        )
        return {"tool": self.TOOL_NAME, "discoveries": len(discoveries)}
