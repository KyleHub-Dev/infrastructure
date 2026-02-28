"""Celery task definitions for dispatching and managing analyzer jobs."""

import logging
from datetime import datetime

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Task name → queue mapping for each observable type.
# When a new worker is added, register it here.
ANALYZERS_BY_TYPE: dict[str, list[str]] = {
    "username": [
        "workers.maigret.analyzer.analyze_username",
        "workers.social-analyzer.analyzer.analyze_username",
    ],
    "email": [
        "workers.holehe.analyzer.analyze_email",
    ],
    "domain": [
        "workers.theharvester.analyzer.analyze_domain",
    ],
}


@celery_app.task(name="app.tasks.analyzers.dispatch_analysis")
def dispatch_analysis(
    investigation_id: str,
    query: str,
    observable_type: str,
    ttl_days: int = 365,
) -> dict:
    """Dispatch OSINT analysis tasks based on observable type.

    Fans out to all registered analyzers for the given type.
    Each worker atomically increments a completion counter on the
    investigation node; the last worker to finish sets status to completed.
    """
    task_names = ANALYZERS_BY_TYPE.get(observable_type, [])

    if not task_names:
        logger.warning(
            "No analyzers registered for observable type '%s' (investigation %s)",
            observable_type,
            investigation_id,
        )
        return {"dispatched": 0, "tasks": []}

    dispatched = []
    for task_name in task_names:
        result = celery_app.send_task(
            task_name,
            kwargs={
                "observable": query,
                "investigation_id": investigation_id,
                "ttl_days": ttl_days,
            },
        )
        dispatched.append({"task_name": task_name, "task_id": result.id})
        logger.info(
            "Dispatched %s (task_id=%s) for investigation %s",
            task_name,
            result.id,
            investigation_id,
        )

    # Set status to running and record expected worker count
    try:
        from app.services.neo4j import neo4j_service

        neo4j_service.execute_write(
            """
            MATCH (inv:Investigation {id: $id})
            SET inv.status = 'running',
                inv.updated_at = $now,
                inv.expected_workers = $count,
                inv.completed_workers = 0,
                inv.failed_workers = 0
            """,
            {
                "id": investigation_id,
                "now": datetime.utcnow().isoformat(),
                "count": len(dispatched),
            },
        )
    except Exception:
        logger.exception("Failed to update investigation status to 'running'")

    return {"dispatched": len(dispatched), "tasks": dispatched}


@celery_app.task(name="app.tasks.analyzers.purge_expired_data")
def purge_expired_data() -> dict:
    """Scheduled task: purge GDPR TTL-expired data from all stores."""
    from app.services.gdpr import run_full_purge

    return run_full_purge()
