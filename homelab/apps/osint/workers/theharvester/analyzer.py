"""TheHarvester OSINT worker — domain-level reconnaissance.

Extracts emails, subdomains, and employee names associated with
a target domain from search engines, PGP key servers, and APIs.
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


class TheHarvesterWorker(WorkerBase):
    TOOL_NAME = "theharvester"

    def analyze(self, observable: str, **kwargs) -> dict:
        """Run TheHarvester against a domain."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            output_path = f.name

        cmd = [
            "theHarvester",
            "-d", observable,
            "-b", "all",
            "-f", output_path,
            "-l", "200",
        ]

        self.run_cli_tool(cmd, timeout=300)

        try:
            with open(output_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"error": "Failed to parse TheHarvester output", "domain": observable}

    def normalize(self, raw_output: dict, target: str, investigation_id: str) -> list[dict]:
        """Normalize TheHarvester output."""
        discoveries = []

        # Discovered emails
        for email in raw_output.get("emails", []):
            discoveries.append({
                "target_entity": target,
                "observable_type": "domain",
                "tool_source": self.TOOL_NAME,
                "confidence_score": 0.8,
                "investigation_id": investigation_id,
                "entity_type": "Email",
                "entity_value": email,
                "entity_metadata": {"source": "domain_recon"},
                "relationship": "ASSOCIATED_WITH",
                "ttl_timestamp": 0,
            })

        # Discovered subdomains
        for host in raw_output.get("hosts", []):
            domain = host if isinstance(host, str) else host.get("host", "")
            ip = "" if isinstance(host, str) else host.get("ip", "")

            discoveries.append({
                "target_entity": target,
                "observable_type": "domain",
                "tool_source": self.TOOL_NAME,
                "confidence_score": 0.85,
                "investigation_id": investigation_id,
                "entity_type": "Domain",
                "entity_value": domain,
                "entity_metadata": {"ip": ip, "source": "subdomain_enum"},
                "relationship": "RESOLVES_TO",
                "ttl_timestamp": 0,
            })

        # Discovered IPs
        for ip in raw_output.get("ips", []):
            discoveries.append({
                "target_entity": target,
                "observable_type": "domain",
                "tool_source": self.TOOL_NAME,
                "confidence_score": 0.8,
                "investigation_id": investigation_id,
                "entity_type": "IPAddress",
                "entity_value": ip,
                "entity_metadata": {"source": "domain_recon"},
                "relationship": "RESOLVES_TO",
                "ttl_timestamp": 0,
            })

        return discoveries


worker = TheHarvesterWorker()


@app.task(name="workers.theharvester.analyzer.analyze_domain", queue="queue_domain")
def analyze_domain(observable: str, investigation_id: str, ttl_days: int | None = None):
    """Celery task: run TheHarvester domain reconnaissance."""
    return worker.execute(observable, investigation_id, ttl_days)
