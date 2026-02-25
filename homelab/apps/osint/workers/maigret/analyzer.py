"""Maigret OSINT worker — username enumeration across 3000+ sites.

Wraps the Maigret CLI tool and normalizes its JSON output into
graph-ready discovery objects.
"""

import json
import tempfile

from celery import Celery
from worker_base import WorkerBase

app = Celery("worker")
app.config_from_object({
    "broker_url": __import__("os").environ.get("REDIS_URL", "redis://redis:6379/0"),
    "result_backend": __import__("os").environ.get("REDIS_URL", "redis://redis:6379/0"),
    "task_serializer": "json",
    "accept_content": ["json"],
})


class MaigretWorker(WorkerBase):
    TOOL_NAME = "maigret"

    def analyze(self, observable: str, **kwargs) -> dict:
        """Run Maigret against a username."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        cmd = [
            "maigret", observable,
            "--json", "simple",
            "--timeout", "10",
            "-a",
            "--no-color",
            "-o", output_path,
        ]

        result = self.run_cli_tool(cmd, timeout=600)

        try:
            with open(output_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            # Fallback: try parsing stdout
            if result.stdout.strip():
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError:
                    pass
            return {"error": result.stderr, "raw_stdout": result.stdout}

    def normalize(self, raw_output: dict, target: str, investigation_id: str) -> list[dict]:
        """Normalize Maigret output into discovery objects."""
        discoveries = []

        sites = raw_output.get("sites", raw_output.get("results", []))
        if isinstance(sites, dict):
            sites = [{"name": k, **v} for k, v in sites.items()]

        for site in sites:
            status = site.get("status", "")
            if status.lower() not in ("claimed", "found", True, "true"):
                continue

            discoveries.append({
                "target_entity": target,
                "observable_type": "username",
                "tool_source": self.TOOL_NAME,
                "confidence_score": 0.9,
                "investigation_id": investigation_id,
                "entity_type": "PlatformAccount",
                "entity_value": site.get("url", site.get("url_user", "")),
                "entity_metadata": {
                    "platform": site.get("name", site.get("site", "unknown")),
                    "status": status,
                    **{k: v for k, v in site.items() if k not in ("name", "url", "status", "site", "url_user")},
                },
                "relationship": "REGISTERED_ON",
                "ttl_timestamp": 0,  # Set by execute()
            })

        return discoveries


worker = MaigretWorker()


@app.task(name="workers.maigret.analyzer.analyze_username", queue="queue_username")
def analyze_username(observable: str, investigation_id: str, ttl_days: int | None = None):
    """Celery task: run Maigret username enumeration."""
    return worker.execute(observable, investigation_id, ttl_days)
