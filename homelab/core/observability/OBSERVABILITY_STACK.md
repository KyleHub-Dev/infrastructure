# Observability stack reference

> **STATUS: design under review - DO NOT DEPLOY YET.**
>
> The structural refactor (container prefixes, network attachments,
> removal of the broken Newt mock, drop of the wrong-path filelog
> receiver) is in place so this stack is consistent with the rest of
> `homelab/core/*`. The overall design still needs a second pass
> before first deploy:
>
> - Scope: which apps push telemetry, which are scraped?
> - Auth: Pangolin IAP in front of Grafana, native Grafana OIDC
>   against Zitadel, or both?
> - Retention sizing on the Hetzner host (`obs-loki-data`,
>   `obs-prometheus-data`, `obs-grafana-data` volumes).
> - Whether `homelab-apps-edge` apps should reach `obs-otel` via
>   `homelab-core-data` or via a dedicated cross-zone telemetry net.
>
> Skip this stack in the deploy runbook until that conversation has
> happened. See `core/DEPLOY.md`.

---

> **Source of truth:** `compose.yaml` and `config/*` in this directory.
> This file is reference-only - cheatsheet for sending data in,
> querying it back out, and the day-to-day maintenance.

## Topology (current)

```
   apps (homelab/apps/* and external producers)
     |
     | OTLP gRPC :4317 / HTTP :4318  (over homelab-core-data)
     v
  obs-otel  ----logs---->  obs-loki :3100
              \--metrics->  obs-prometheus :9090 (scrapes :8889 on obs-otel)
                                       |
                                       v
                               obs-grafana :3000
                          (exposed via core-newt -> Pangolin)
```

Scope today: receive telemetry pushed by user-developed webapps. Infra
scraping (node-exporter, cAdvisor, postgres-exporter, etc.) is
intentionally out of scope until the user defines what infra signals
matter. Add scrape jobs to `config/prometheus.yml` when needed.

---

## Sending logs from an application

### Option 1 - structured JSON to stdout (simplest)

Print one JSON object per line; the app's container can be wired to
ship to OTel via a sidecar or Loki driver. Useful when the app does
not directly speak OTLP.

```python
import json, sys
def emit(event: dict) -> None:
    print(json.dumps(event), file=sys.stdout, flush=True)
```

### Option 2 - direct OTLP HTTP

```python
import httpx, json, time

async def send_to_otel(event: dict) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            "http://obs-otel:4318/v1/logs",
            json={
                "resourceLogs": [{
                    "resource": {
                        "attributes": [
                            {"key": "service.name",
                             "value": {"stringValue": "my-app"}},
                        ],
                    },
                    "scopeLogs": [{
                        "logRecords": [{
                            "timeUnixNano": str(int(time.time() * 1e9)),
                            "body": {"stringValue": json.dumps(event)},
                            "attributes": [
                                {"key": "level",
                                 "value": {"stringValue": event.get("level", "info")}},
                            ],
                        }],
                    }],
                }],
            },
            headers={"Content-Type": "application/json"},
        )
```

The producing container must be on the `homelab-core-data` network so
it can resolve `obs-otel`.

---

## LogQL cheatsheet

```logql
# All logs from a service
{service="my-app"}

# Errors only
{service="my-app"} |= "error" | json | level = "error"

# Slow requests (>2 s) when log lines are JSON with duration_ms
{service="my-app"} | json | duration_ms > 2000

# Specific user
{service="my-app"} | json | user_id = "user_456"

# Error rate, last 5 min
sum(rate({level="error"}[5m])) by (service)

# Top 10 slowest endpoints
topk(10, avg by (http_path) (
  {service="my-app"} | json | unwrap duration_ms
))
```

---

## Maintenance

### Backup Grafana

```sh
# Export dashboards
podman exec obs-grafana grafana-cli admin export-dashboards /tmp/dashboards
podman cp obs-grafana:/tmp/dashboards ./backups/

# Or back up the volume
podman run --rm -v obs-grafana-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/grafana-backup.tar.gz /data
```

### Loki retention

```sh
# Disk usage
podman exec obs-loki du -sh /loki/chunks

# Force compaction (rare)
curl -X POST http://obs-loki:3100/compactor/ring/forget
```

### Update images

```sh
podman-compose pull
podman-compose up -d
```

---

## Troubleshooting

**Logs not appearing in Loki**
1. `podman-compose logs obs-otel` - look for receiver / exporter errors.
2. Verify Loki: `curl http://obs-loki:3100/ready` from inside obs-net.
3. Confirm the `service.name` attribute is being set on the producer.

**High memory in obs-otel**
Lower `processors.batch.send_batch_size` in `config/otel-collector.yaml`,
or raise the OTLP client's sampling rate.

**Grafana cannot reach data sources**
Data source URLs in `config/grafana/provisioning/datasources/datasources.yml`
use container names (`obs-loki`, `obs-prometheus`), not `localhost`.
Verify network attachment: `podman exec obs-grafana getent hosts obs-loki`.
