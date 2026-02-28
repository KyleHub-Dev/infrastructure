"""Social Analyzer OSINT worker - social media profiling across 1000+ sites.

Profiles targets across social media platforms with built-in
string analysis and image detection capabilities.
"""

import json
import logging
from importlib import import_module
from urllib.parse import urlparse

from celery import Celery
from worker_base import WorkerBase

logger = logging.getLogger(__name__)

app = Celery("worker")
app.config_from_object({
    "broker_url": __import__("os").environ.get("REDIS_URL", "redis://osint-redis:6379/0"),
    "result_backend": __import__("os").environ.get("REDIS_URL", "redis://osint-redis:6379/0"),
    "task_serializer": "json",
    "accept_content": ["json"],
})


class SocialAnalyzerWorker(WorkerBase):
    TOOL_NAME = "social-analyzer"

    def analyze(self, observable: str, **kwargs) -> dict:
        """Run Social Analyzer against a username via Python API.

        Uses run_as_object() instead of CLI to avoid stdout issues
        (--output json + --silent suppresses all output).
        """
        try:
            SocialAnalyzer = import_module("social-analyzer").SocialAnalyzer
            sa = SocialAnalyzer(silent=True)
            results = sa.run_as_object(
                username=observable,
                silent=True,
                metadata=True,
                filter="good",
                profiles="detected",
                mode="fast",
            )
            if results:
                return results
            return {"detected": []}
        except Exception:
            logger.exception("Python API failed, falling back to CLI")
            return self._analyze_cli(observable)

    def _analyze_cli(self, observable: str) -> dict:
        """Fallback: run via CLI without --silent so JSON is printed."""
        cmd = [
            "social-analyzer",
            "--username", observable,
            "--metadata",
            "--output", "json",
        ]

        result = self.run_cli_tool(cmd, timeout=300)

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"error": result.stderr, "raw_stdout": result.stdout}

    def normalize(self, raw_output: dict, target: str, investigation_id: str) -> list[dict]:
        """Normalize Social Analyzer output.

        Result structure:
        {
            "detected": [
                {"link": "https://...", "rate": "%100.0", "status": "good",
                 "title": "...", "type": "...", "country": "...", "rank": N,
                 "metadata": [...], "extracted": [...]}
            ]
        }
        """
        discoveries = []

        profiles = raw_output.get("detected", [])
        if isinstance(profiles, dict):
            profiles = list(profiles.values())

        for profile in profiles:
            if not isinstance(profile, dict):
                continue

            url = profile.get("link", "")
            if not url:
                continue

            # Extract platform name from URL domain (no "name" field in output)
            try:
                domain = urlparse(url).netloc
                platform = domain.removeprefix("www.")
            except Exception:
                platform = "unknown"

            # Parse rate string like "%100.0" into a confidence score
            confidence = 0.75
            rate = profile.get("rate", "")
            if isinstance(rate, str) and rate.startswith("%"):
                try:
                    confidence = min(float(rate[1:]) / 100.0, 1.0)
                except ValueError:
                    pass

            discoveries.append({
                "target_entity": target,
                "observable_type": "username",
                "tool_source": self.TOOL_NAME,
                "confidence_score": confidence,
                "investigation_id": investigation_id,
                "entity_type": "PlatformAccount",
                "entity_value": url,
                "entity_metadata": {
                    "platform": platform,
                    "title": profile.get("title", ""),
                    "type": profile.get("type", ""),
                    "country": profile.get("country", ""),
                    "rank": profile.get("rank", ""),
                    "extracted": profile.get("extracted", []),
                    "metadata": profile.get("metadata", []),
                },
                "relationship": "REGISTERED_ON",
                "ttl_timestamp": 0,
            })

        return discoveries


worker = SocialAnalyzerWorker()


@app.task(name="workers.social-analyzer.analyzer.analyze_username", queue="queue_social")
def analyze_username(observable: str, investigation_id: str, ttl_days: int | None = None):
    """Celery task: run Social Analyzer profiling."""
    return worker.execute(observable, investigation_id, ttl_days)
