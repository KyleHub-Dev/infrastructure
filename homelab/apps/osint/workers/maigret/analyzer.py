"""Maigret OSINT worker - username enumeration across 3000+ sites.

Wraps the Maigret CLI tool and normalizes its JSON output into
graph-ready discovery objects.
"""

import glob
import json
import os
import tempfile

from celery import Celery
from worker_base import WorkerBase

app = Celery("worker")
app.config_from_object({
    "broker_url": __import__("os").environ.get("REDIS_URL", "redis://osint-redis:6379/0"),
    "result_backend": __import__("os").environ.get("REDIS_URL", "redis://osint-redis:6379/0"),
    "task_serializer": "json",
    "accept_content": ["json"],
})


class MaigretWorker(WorkerBase):
    TOOL_NAME = "maigret"

    def analyze(self, observable: str, **kwargs) -> dict:
        """Run Maigret against a username."""
        output_dir = tempfile.mkdtemp()

        cmd = [
            "maigret", observable,
            "-J", "simple",
            "--folderoutput", output_dir,
            "--timeout", "10",
            "-a",
            "--no-color",
            "--no-progressbar",
        ]

        result = self.run_cli_tool(cmd, timeout=600)

        # Maigret writes report_<username>.json in the output dir
        json_files = glob.glob(os.path.join(output_dir, "*.json"))
        for json_file in json_files:
            try:
                with open(json_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                continue

        # Fallback: try parsing stdout
        if result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        return {"error": result.stderr, "raw_stdout": result.stdout}

    # Maps maigret ids keys to (entity_type, relationship)
    _IDS_FIELD_MAP: dict[str, tuple[str, str]] = {
        "fullname": ("Person", "HAS_NAME"),
        "full_name": ("Person", "HAS_NAME"),
        "nickname": ("Username", "ALSO_KNOWN_AS"),
        "email": ("Email", "HAS_EMAIL"),
        "phone": ("Phone", "HAS_PHONE"),
        "location": ("Person", "LOCATED_IN"),
        "blog_url": ("Domain", "HAS_WEBSITE"),
    }

    def normalize(self, raw_output: dict, target: str, investigation_id: str) -> list[dict]:
        """Normalize Maigret output into discovery objects.

        Maigret simple JSON format is a flat dict:
        {
            "SiteName": {
                "url_user": "https://...",
                "status": {"status": "Claimed", "ids": {...}, ...},
                ...
            }
        }

        The status.ids dict contains parsed profile data (names, emails,
        locations, etc.) when maigret runs with the -a flag.
        """
        discoveries = []
        seen_entities: set[str] = set()

        # Handle flat dict format (site_name -> site_data)
        if raw_output and not any(k in raw_output for k in ("sites", "results", "error")):
            sites = [{"name": k, **v} for k, v in raw_output.items() if isinstance(v, dict)]
        else:
            sites = raw_output.get("sites", raw_output.get("results", []))
            if isinstance(sites, dict):
                sites = [{"name": k, **v} for k, v in sites.items()]

        for site in sites:
            # Status can be a string or a nested dict with a "status" key
            status_raw = site.get("status", "")
            if isinstance(status_raw, dict):
                status = status_raw.get("status", "")
            else:
                status = str(status_raw)

            if status.lower() not in ("claimed", "found", "true"):
                continue

            url = site.get("url_user", site.get("url", ""))
            platform = site.get("name", "unknown")

            # Platform account discovery
            discoveries.append({
                "target_entity": target,
                "observable_type": "username",
                "tool_source": self.TOOL_NAME,
                "confidence_score": 0.9,
                "investigation_id": investigation_id,
                "entity_type": "PlatformAccount",
                "entity_value": url,
                "entity_metadata": {
                    "platform": platform,
                    "status": status,
                    "http_status": site.get("http_status"),
                    "rank": site.get("rank"),
                },
                "relationship": "REGISTERED_ON",
                "ttl_timestamp": 0,
            })

            # Extract parsed profile data from status.ids
            ids = {}
            if isinstance(status_raw, dict):
                ids = status_raw.get("ids", {})
            if not isinstance(ids, dict):
                continue

            for field, (entity_type, relationship) in self._IDS_FIELD_MAP.items():
                value = ids.get(field)
                if not value or not isinstance(value, str) or len(value.strip()) < 2:
                    continue
                value = value.strip()

                # Deduplicate across sites
                dedup_key = (entity_type, value.lower())
                if dedup_key in seen_entities:
                    continue
                seen_entities.add(dedup_key)

                # Skip values that are just the target username repeated
                if value.lower() == target.lower():
                    continue

                discoveries.append({
                    "target_entity": target,
                    "observable_type": "username",
                    "tool_source": self.TOOL_NAME,
                    "confidence_score": 0.7,
                    "investigation_id": investigation_id,
                    "entity_type": entity_type,
                    "entity_value": value,
                    "entity_metadata": {
                        "source_platform": platform,
                        "field": field,
                    },
                    "relationship": relationship,
                    "ttl_timestamp": 0,
                })

        return discoveries


worker = MaigretWorker()


@app.task(name="workers.maigret.analyzer.analyze_username", queue="queue_maigret")
def analyze_username(observable: str, investigation_id: str, ttl_days: int | None = None):
    """Celery task: run Maigret username enumeration."""
    return worker.execute(observable, investigation_id, ttl_days)
