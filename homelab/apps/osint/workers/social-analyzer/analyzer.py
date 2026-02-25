"""Social Analyzer OSINT worker — social media profiling across 1000+ sites.

Profiles targets across social media platforms with built-in
string analysis and image detection capabilities.
"""

import json

from celery import Celery
from worker_base import WorkerBase

app = Celery("worker")
app.config_from_object({
    "broker_url": __import__("os").environ.get("REDIS_URL", "redis://redis:6379/0"),
    "result_backend": __import__("os").environ.get("REDIS_URL", "redis://redis:6379/0"),
    "task_serializer": "json",
    "accept_content": ["json"],
})


class SocialAnalyzerWorker(WorkerBase):
    TOOL_NAME = "social-analyzer"

    def analyze(self, observable: str, **kwargs) -> dict:
        """Run Social Analyzer against a username."""
        cmd = [
            "social-analyzer",
            "--username", observable,
            "--metadata",
            "--output", "json",
            "--silent",
        ]

        result = self.run_cli_tool(cmd, timeout=300)

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"error": result.stderr, "raw_stdout": result.stdout}

    def normalize(self, raw_output: dict, target: str, investigation_id: str) -> list[dict]:
        """Normalize Social Analyzer output."""
        discoveries = []

        profiles = raw_output.get("detected", raw_output.get("results", []))
        if isinstance(profiles, dict):
            profiles = list(profiles.values())

        for profile in profiles:
            if not isinstance(profile, dict):
                continue

            url = profile.get("link", profile.get("url", ""))
            if not url:
                continue

            discoveries.append({
                "target_entity": target,
                "observable_type": "username",
                "tool_source": self.TOOL_NAME,
                "confidence_score": 0.75,
                "investigation_id": investigation_id,
                "entity_type": "PlatformAccount",
                "entity_value": url,
                "entity_metadata": {
                    "platform": profile.get("name", profile.get("site", "unknown")),
                    "title": profile.get("title", ""),
                    "extracted_info": profile.get("extracted", {}),
                },
                "relationship": "REGISTERED_ON",
                "ttl_timestamp": 0,
            })

        return discoveries


worker = SocialAnalyzerWorker()


@app.task(name="workers.social-analyzer.analyzer.analyze_username", queue="queue_username")
def analyze_username(observable: str, investigation_id: str, ttl_days: int | None = None):
    """Celery task: run Social Analyzer profiling."""
    return worker.execute(observable, investigation_id, ttl_days)
