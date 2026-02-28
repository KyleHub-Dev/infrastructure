# OSINT Platform - Deployment & Operations Guide

## Prerequisites

- Podman 4.0+ with `podman compose` (or `podman-compose`)
- A running Pangolin instance with NEWT support
- At least **4GB RAM** available for the stack (8GB recommended)
- `vm.max_map_count` does **not** need to be changed (Meilisearch, unlike Elasticsearch, has no such requirement)

## Initial Setup

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Description | Example |
|---|---|---|
| `PANGOLIN_ENDPOINT` | Your Pangolin instance URL | `https://pangolin.yourdomain.com` |
| `NEWT_ID` | NEWT tunnel ID from Pangolin | `nt_abc123...` |
| `NEWT_SECRET` | NEWT tunnel secret | `nts_xyz789...` |
| `NEO4J_AUTH` | Neo4j credentials (`user/password`) | `neo4j/your-strong-password` |
| `DEFAULT_TTL_DAYS` | GDPR data retention period | `365` |

### 2. Pangolin Route Configuration

In your Pangolin dashboard, create routes for the OSINT site:

| Route | Target (Internal) | Purpose |
|---|---|---|
| `/` | `osint-frontend:80` | React dashboard |
| `/api/*` | `osint-api:8000` | FastAPI backend |
| `/neo4j` | `osint-neo4j:7474` | Neo4j Browser (optional, admin only) |

> All routes inherit Pangolin's authentication policy.
> The API reads the `Remote-User` header injected by Pangolin on every request.

### 3. Start the Stack

```bash
# Build and start all services
podman compose up -d --build

# Check status
podman compose ps

# View logs
podman compose logs -f osint-api
podman compose logs -f osint-worker-maigret
```

### 4. Initialize Neo4j Schema

On first run, apply the graph schema constraints:

```bash
podman compose exec osint-neo4j cypher-shell -u neo4j -p 'your-password' < config/neo4j/init.cypher
```

## Operations

### Monitoring

```bash
# All service statuses
podman compose ps

# Worker queue depth
podman compose exec osint-redis redis-cli LLEN queue_username
podman compose exec osint-redis redis-cli LLEN queue_email
podman compose exec osint-redis redis-cli LLEN queue_domain

# Neo4j node count
podman compose exec osint-neo4j cypher-shell -u neo4j -p 'your-password' \
  "MATCH (n) RETURN labels(n) AS type, count(n) AS count ORDER BY count DESC"
```

### Scaling Workers

To add more concurrency for a specific tool:

```bash
# Scale maigret workers to 3 containers
podman compose up -d --scale osint-worker-maigret=3
```

### Updating a Single Worker

```bash
# Rebuild and restart only the maigret worker
podman compose build osint-worker-maigret
podman compose up -d osint-worker-maigret
```

### Backup

```bash
# Neo4j dump
podman compose exec osint-neo4j neo4j-admin database dump neo4j --to-path=/data/backups/

# Meilisearch snapshot
curl -X POST http://localhost:7700/snapshots  # (from inside osint-net)

# Redis AOF
podman compose exec osint-redis redis-cli BGSAVE
```

### GDPR Data Purge

Expired data is automatically purged by the Celery Beat scheduler. To manually trigger:

```bash
podman compose exec osint-api python -m app.services.gdpr --purge-expired
```

## Resource Estimates

| Service | RAM (idle) | RAM (active) | Notes |
|---|---|---|---|
| FastAPI | ~50MB | ~100MB | Lightweight ASGI |
| Redis | ~30MB | ~100MB | Capped at 256MB |
| Neo4j | ~300MB | ~512MB | Heap capped at 512MB |
| Meilisearch | ~50MB | ~150MB | Rust, no JVM overhead |
| Each Worker | ~80MB | ~200MB | Depends on tool |
| Tor Proxy | ~20MB | ~50MB | Minimal |
| NEWT | ~15MB | ~30MB | Tunnel only |
| **Total** | **~700MB** | **~1.5–2GB** | 4 workers running |

## Troubleshooting

| Issue | Likely Cause | Fix |
|---|---|---|
| NEWT not connecting | Wrong credentials in `.env` | Verify `NEWT_ID`, `NEWT_SECRET`, `PANGOLIN_ENDPOINT` |
| Neo4j OOM | Heap too large for host | Reduce `NEO4J_server_memory_heap_max__size` in compose |
| Worker task timeout | OSINT tool taking >5min (e.g., Maigret) | Increase `task_time_limit` in worker config |
| Meilisearch not indexing | Index not created | Check API logs; indexes are auto-created on first write |
| `Remote-User` empty | Pangolin not injecting header | Check Pangolin route config and auth policy |

## Adding a New OSINT Tool

1. Create `workers/your-tool/` with `Containerfile`, `requirements.txt`, `analyzer.py`
2. Extend `WorkerBase` in your analyzer (see `workers/base/worker_base.py`)
3. Add the service to `compose.yaml` listening on the appropriate queue
4. Rebuild: `podman compose build osint-worker-your-tool && podman compose up -d`
