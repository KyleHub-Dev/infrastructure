"""Celery task definitions for dispatching and managing analyzer jobs."""

import logging

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
    Each analyzer runs in its own containerized worker.
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

    # Update investigation status to running
    try:
        from app.services.neo4j import neo4j_service

        neo4j_service.update_investigation_status(investigation_id, "running")
    except Exception:
        logger.exception("Failed to update investigation status to 'running'")

    return {"dispatched": len(dispatched), "tasks": dispatched}


@celery_app.task(name="app.tasks.analyzers.purge_expired_data")
def purge_expired_data() -> dict:
    """Scheduled task: purge GDPR TTL-expired data from all stores."""
    from app.services.gdpr import run_full_purge

    return run_full_purge()
