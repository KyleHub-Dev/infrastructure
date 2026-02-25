"""GDPR compliance services — TTL enforcement and DPIA audit logging."""

import logging
from datetime import datetime

from app.services.neo4j import neo4j_service
from app.services.meilisearch import meili_service

logger = logging.getLogger(__name__)


def purge_expired_nodes():
    """Delete all Neo4j nodes whose TTL has expired.

    Implements GDPR Article 5(1)(e) — Storage Limitation.
    Runs as a scheduled Celery Beat task (daily).
    """
    now_ms = int(datetime.utcnow().timestamp() * 1000)

    # Delete expired nodes and cascade-delete their relationships
    query = """
    MATCH (n)
    WHERE n.ttl IS NOT NULL AND n.ttl < $now_ms
    DETACH DELETE n
    RETURN count(n) AS deleted_count
    """
    result = neo4j_service.execute_write(query, {"now_ms": now_ms})
    deleted = result[0]["deleted_count"] if result else 0
    logger.info("GDPR TTL purge: deleted %d expired nodes", deleted)
    return deleted


def purge_expired_documents():
    """Delete all Meilisearch documents whose TTL has expired.

    Runs alongside the Neo4j purge.
    """
    now_iso = datetime.utcnow().isoformat()
    # Meilisearch filter-based deletion
    meili_service.index.delete_documents({
        "filter": f"expires_at < '{now_iso}'"
    })
    logger.info("GDPR TTL purge: cleaned expired Meilisearch documents")


def run_full_purge():
    """Execute the complete GDPR TTL purge across all data stores."""
    neo4j_deleted = purge_expired_nodes()
    purge_expired_documents()
    return {"neo4j_deleted": neo4j_deleted}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GDPR Data Lifecycle Management")
    parser.add_argument("--purge-expired", action="store_true", help="Purge all expired data")
    args = parser.parse_args()

    if args.purge_expired:
        result = run_full_purge()
        print(f"Purge complete: {result}")
