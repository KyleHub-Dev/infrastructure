# OSINT Platform - Architecture Documentation

## Overview

The platform follows a **decoupled microservices architecture** split into four distinct layers:

1. **Orchestration Layer** - API Gateway + Celery task queue
2. **Worker Layer** - Containerized OSINT tool executors
3. **Persistence Layer** - Neo4j (graph) + Meilisearch (document search)
4. **Presentation Layer** - React dashboard with Sigma.js graph visualization

## Layer Details

### 1. Orchestration Layer

**API Gateway (FastAPI)**
- Receives investigation requests via REST API
- Authenticates users via Pangolin's `Remote-User` header (IAP)
- Dispatches OSINT tasks to categorized Celery queues
- Serves graph data and search results to the frontend

**Celery + Redis**
- Redis acts as the high-speed message broker
- Tasks are routed to named queues by observable type:
  - `queue_username` - Maigret, Social Analyzer
  - `queue_email` - Holehe
  - `queue_domain` - TheHarvester
- Celery Beat handles scheduled jobs (GDPR TTL cleanup, stale task reaping)

### 2. Worker Layer (OSINT Tool Containers)

Each OSINT tool runs in its own isolated container acting as a Celery worker. Workers:

1. Receive a task message from their queue (e.g., `{"observable": "jdoe_89", "type": "username"}`)
2. Execute the underlying CLI tool via subprocess
3. Parse raw output (CSV, JSON, stdout text)
4. **Normalize** results into a unified JSON schema (UCO/MISP-inspired)
5. Write normalized entities → Neo4j (graph edges + nodes)
6. Write raw payloads → Meilisearch (full-text searchable)

**Current Workers:**

| Worker | Tool | Queue | Input Types |
|---|---|---|---|
| `worker-maigret` | Maigret | `queue_username` | username |
| `worker-holehe` | Holehe | `queue_email` | email |
| `worker-theharvester` | TheHarvester | `queue_domain` | domain |
| `worker-social` | Social Analyzer | `queue_username` | username |

**Adding a new worker** requires only:
1. Create a new directory under `workers/`
2. Write `analyzer.py` (extend `WorkerBase`)
3. Write `Containerfile` and `requirements.txt`
4. Add the service to `compose.yaml` with the appropriate queue

### 3. Persistence Layer

**Neo4j (Property Graph Database)**
- Stores entities as nodes: `:Person`, `:Username`, `:Email`, `:Domain`, `:IPAddress`, `:PlatformAccount`
- Stores connections as edges: `OWNS`, `REGISTERED_ON`, `RESOLVES_TO`, `ASSOCIATED_WITH`
- Enables multi-hop link analysis queries via Cypher
- TTL fields on all nodes for automated GDPR-compliant data expiry

**Meilisearch (Document Store)**
- Indexes raw JSON outputs from every analyzer run
- Provides instant, typo-tolerant full-text search across all scraped data
- Lightweight (Rust-based, ~50–100MB RAM vs Elasticsearch's 512MB–2GB JVM heap)
- Linked back to Neo4j via `node_id` reference fields

**Why Meilisearch over Elasticsearch?**
The research document recommended Elasticsearch, but for a homelab deployment the JVM overhead is excessive. Meilisearch provides the full-text search capability needed for raw payload retrieval at a fraction of the resource cost. The platform doesn't need ES-level aggregation pipelines or complex analytics DSL - it needs fast document search with filtering, which Meilisearch handles excellently.

### 4. Presentation Layer

**React + Sigma.js Dashboard**
- Sigma.js renders the Neo4j graph via WebGL (handles 10k–100k+ nodes)
- Interactive node context menus trigger secondary analysis pivots
- Investigation management UI (create, monitor, review)
- Real-time task status via polling/SSE
- Responsive, analyst-focused design

## Authentication & Access

```
Internet → Pangolin IAP → NEWT Tunnel → osint-net (internal)
                 │
                 └─ Injects `Remote-User: user@domain.com` header
                    on every authenticated request
```

- **No ports are exposed** on the container stack
- NEWT is the **sole ingress point** into `osint-net`
- The FastAPI middleware reads `Remote-User` and attaches the identity to the request context
- All API writes (create investigation, trigger scan) are attributed to the authenticated user
- RBAC is enforced at the API layer based on the authenticated identity

## Data Flow: End-to-End

```
1. Analyst submits:  POST /api/v1/investigations
                     { "query": "jdoe_89", "type": "username" }

2. API Gateway:      Creates Investigation record in Neo4j
                     Dispatches tasks to queue_username

3. Celery Router:    Fans out to: worker-maigret, worker-social

4. worker-maigret:   Runs `maigret jdoe_89 --json simple`
                     Parses JSON output
                     Normalizes → UCO schema
                     Writes nodes/edges → Neo4j
                     Writes raw JSON → Meilisearch

5. worker-social:    Runs Social Analyzer against jdoe_89
                     Same normalize → persist flow

6. API Gateway:      Returns investigation status + results
                     Frontend polls / receives updates

7. Frontend:         Renders discovered entities as interactive
                     Sigma.js graph. Analyst clicks a discovered
                     email node → triggers pivot → dispatches
                     Holehe task to queue_email → cycle continues
```

## Network Topology

All services communicate on the internal `osint-net` bridge network. No service exposes ports to the host. The only external-facing component is the NEWT tunnel container, which establishes an outbound connection to the Pangolin endpoint.

```
osint-net (bridge)
├── osint-api         ← FastAPI (port 8000 internal)
├── osint-frontend    ← Nginx serving React (port 80 internal)
├── osint-redis       ← Redis (port 6379 internal)
├── osint-neo4j       ← Neo4j (bolt:7687, http:7474 internal)
├── osint-meili       ← Meilisearch (port 7700 internal)
├── osint-tor         ← Tor SOCKS5 (port 9050 internal)
├── osint-worker-*    ← Celery workers (no ports)
└── osint-newt        ← NEWT tunnel (outbound only)
```
