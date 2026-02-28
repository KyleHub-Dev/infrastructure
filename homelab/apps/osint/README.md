# OSINT Platform - Self-Hosted Intelligence Gathering & Visualization

> A GDPR-compliant, self-hosted OSINT platform for targeted intelligence investigations.
> Single data point in → automated scraping → unified relational graph out.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PANGOLIN IAP                                 │
│                   (Remote-User Auth Header)                         │
│                                                                     │
│  ┌──────────┐                                                       │
│  │   NEWT   │◄── Only ingress point into the container stack        │
│  │  Tunnel  │                                                       │
│  └────┬─────┘                                                       │
│       │                                                             │
├───────┼─────────────────────────────────────────────────────────────┤
│       │              INTERNAL NETWORK (osint-net)                   │
│       │                                                             │
│  ┌────▼──────────────────────┐     ┌──────────────────────────┐     │
│  │    API Gateway (FastAPI)  │────▶│   Redis (Message Broker)  │    │
│  │    /api/v1/*              │     │   + Celery Beat           │    │
│  │    Remote-User Auth       │     └──────────┬───────────────┘    │
│  └───────────────────────────┘                │                     │
│                                    ┌──────────▼───────────────┐     │
│  ┌───────────────────────────┐     │   Celery Workers         │     │
│  │   Frontend (React)        │     │   ┌─────────────────┐    │     │
│  │   Sigma.js Graph Viz      │     │   │ maigret-worker   │    │    │
│  │   /dashboard              │     │   │ holehe-worker    │    │    │
│  └───────────────────────────┘     │   │ harvester-worker │    │    │
│                                    │   │ social-worker    │    │    │
│  ┌───────────────────────────┐     │   └─────────────────┘    │     │
│  │   Neo4j (Graph DB)        │     └──────────────────────────┘     │
│  │   Relationship mapping    │                                      │
│  └───────────────────────────┘                                      │
│                                                                     │
│  ┌───────────────────────────┐                                      │
│  │   Meilisearch             │                                      │
│  │   Raw metadata & search   │                                      │
│  └───────────────────────────┘                                      │
│                                                                     │
│  ┌───────────────────────────┐                                      │
│  │   Tor Proxy (SOCKS5)      │                                      │
│  │   Outbound anonymization  │                                      │
│  └───────────────────────────┘                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **IntelOwl-inspired + Celery** | Purpose-built analyzer framework with high-throughput async task routing |
| **Neo4j + Meilisearch** | Polyglot persistence - graph for relationships, Meili for full-text search (Rust, ~50MB vs ES's JVM heap) |
| **Sigma.js (WebGL)** | Handles 10k–100k+ nodes without browser lag, unlike Canvas-based libs |
| **Pangolin + NEWT** | Zero exposed ports; auth handled at IAP layer via `Remote-User` header |
| **Containerized workers** | Each OSINT tool in its own image - independent deps, independent scaling |
| **GDPR by design** | TTL enforcement, data minimization, DPIA logging, RBAC, audit trail |

## Quick Start

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your Pangolin/NEWT credentials and Neo4j password

# 2. Start the stack
podman compose up -d

# 3. Access via your Pangolin domain
# Dashboard:  https://osint.yourdomain.com
# API:        https://osint.yourdomain.com/api/v1
# Neo4j:      https://osint.yourdomain.com/neo4j  (browser UI)
```

## Project Structure

```
osint/
├── README.md                          # This file
├── ARCHITECTURE.md                    # Detailed architecture documentation
├── COMPLIANCE.md                      # GDPR & EU AI Act compliance guide
├── DEPLOYMENT.md                      # Deployment & operations guide
├── compose.yaml                       # Podman Compose - full stack
├── .env.example                       # Environment variable template
├── .gitignore                         # Git ignore rules
│
├── api/                               # FastAPI backend (API Gateway)
│   ├── Dockerfile
│   ├── pyproject.toml                 # Dependencies (managed by uv)
│   └── app/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app entrypoint
│       ├── config.py                  # Settings & environment config
│       ├── auth.py                    # Remote-User header auth middleware
│       ├── models/                    # Pydantic models & schemas
│       │   ├── __init__.py
│       │   ├── investigation.py       # Investigation/case models
│       │   └── observable.py          # Observable entity models
│       ├── routers/                   # API route handlers
│       │   ├── __init__.py
│       │   ├── investigations.py      # CRUD for investigations
│       │   ├── observables.py         # Submit & query observables
│       │   └── graph.py              # Graph query endpoints
│       ├── services/                  # Business logic
│       │   ├── __init__.py
│       │   ├── neo4j.py              # Neo4j client
│       │   ├── meilisearch.py        # Meilisearch client
│       │   └── gdpr.py              # TTL enforcement, DPIA logging
│       └── tasks/                     # Celery task definitions
│           ├── __init__.py
│           ├── celery_app.py          # Celery configuration
│           └── analyzers.py           # Analyzer task dispatch
│
├── workers/                           # Containerized OSINT tool workers
│   ├── base/
│   │   ├── Dockerfile                 # Base worker image
│   │   └── worker_base.py            # Shared Celery worker base class
│   ├── maigret/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── analyzer.py               # Maigret wrapper + normalizer
│   ├── holehe/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── analyzer.py               # Holehe wrapper + normalizer
│   ├── theharvester/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── analyzer.py               # TheHarvester wrapper + normalizer
│   └── social-analyzer/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── analyzer.py               # Social Analyzer wrapper + normalizer
│
├── frontend/                          # React dashboard (pnpm)
│   ├── Dockerfile
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── vite.config.ts
│   └── src/
│       ├── index.html
│       ├── main.tsx
│       ├── App.tsx
│       └── components/
│           └── .gitkeep
│
├── config/                            # Service configuration
│   ├── neo4j/
│   │   └── init.cypher               # Neo4j schema initialization
│   └── meilisearch/
│       └── index-config.json          # Meilisearch index configuration
│
└── docs/                              # Additional documentation
    └── research/
        └── OSINT Platform Design and Compliance.md   # Original research
```

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **IAP / Auth** | Pangolin + NEWT | Identity-Aware Proxy, `Remote-User` header forwarding |
| **API Gateway** | FastAPI (Python) | REST API, auth middleware, task dispatch |
| **Task Queue** | Celery + Redis | Async job orchestration, worker routing |
| **Graph Database** | Neo4j | Entity relationship storage, link analysis queries |
| **Document Store** | Meilisearch | Raw JSON payloads, full-text search (Rust, lightweight) |
| **Workers** | Podman containers | Isolated OSINT tool execution (Maigret, Holehe, etc.) |
| **Frontend** | React + Sigma.js | Dashboard, WebGL graph visualization |
| **Anonymization** | Tor SOCKS5 Proxy | Outbound traffic anonymization for scrapers |

## Legal Notice

This platform is designed exclusively for **targeted, lawful investigations** supported by a documented legitimate interest under GDPR Article 6(1)(f). Untargeted bulk collection, social scoring, and automated biometric profiling are **strictly prohibited** by design and by European law. See [COMPLIANCE.md](./COMPLIANCE.md) for the full legal compliance framework.

---

*Built for the homelab. Designed for compliance. Engineered for scale.*
