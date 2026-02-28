"""Holehe OSINT worker - email-to-account discovery.

Checks if an email address is registered on 120+ platforms by
exploiting password reset / signup API flows (without alerting the target).
"""

import asyncio
import importlib

from celery import Celery
from worker_base import WorkerBase

app = Celery("worker")
app.config_from_object({
    "broker_url": __import__("os").environ.get("REDIS_URL", "redis://osint-redis:6379/0"),
    "result_backend": __import__("os").environ.get("REDIS_URL", "redis://osint-redis:6379/0"),
    "task_serializer": "json",
    "accept_content": ["json"],
})


class HoleheWorker(WorkerBase):
    TOOL_NAME = "holehe"

    def analyze(self, observable: str, **kwargs) -> dict:
        """Run Holehe against an email address using its Python API."""
        try:
            holehe_modules = importlib.import_module("holehe.modules")
            from holehe.core import holehe as holehe_check

            results = asyncio.run(holehe_check(observable))
            return {"email": observable, "results": results}
        except Exception:
            # Fallback to CLI
            result = self.run_cli_tool(["holehe", observable, "--no-color"], timeout=120)
            return {"email": observable, "raw_stdout": result.stdout, "raw_stderr": result.stderr}

    def normalize(self, raw_output: dict, target: str, investigation_id: str) -> list[dict]:
        """Normalize Holehe output into discovery objects."""
        discoveries = []

        results = raw_output.get("results", [])
        for entry in results:
            if not isinstance(entry, dict):
                continue

            exists = entry.get("exists", entry.get("rateLimit", False))
            if not exists:
                continue

            platform = entry.get("name", entry.get("domain", "unknown"))
            discoveries.append({
                "target_entity": target,
                "observable_type": "email",
                "tool_source": self.TOOL_NAME,
                "confidence_score": 0.85,
                "investigation_id": investigation_id,
                "entity_type": "PlatformAccount",
                "entity_value": f"{platform}:{target}",
                "entity_metadata": {
                    "platform": platform,
                    "exists": True,
                    "method": entry.get("method", "unknown"),
                },
                "relationship": "REGISTERED_ON",
                "ttl_timestamp": 0,
            })

        return discoveries


worker = HoleheWorker()


@app.task(name="workers.holehe.analyzer.analyze_email", queue="queue_holehe")
def analyze_email(observable: str, investigation_id: str, ttl_days: int | None = None):
    """Celery task: run Holehe email-to-account discovery."""
    return worker.execute(observable, investigation_id, ttl_days)
