# KyleHub Infrastructure

> **Hybrid Cloud Infrastructure** — Connecting a public VPS gateway with a private homelab through secure tunnels.

[![Documentation](https://img.shields.io/badge/docs-docusaurus-blue)](https://docs.kylehub.dev)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Overview

KyleHub Infrastructure is a monorepo containing all the Infrastructure-as-Code (IaC) for the KyleHub platform. It implements a **hybrid cloud architecture** that combines the global reach of a cloud VPS with the compute power and storage capacity of a private homelab.

### Architecture Highlights

| Zone | Purpose | Components |
|------|---------|------------|
| **Gateway (VPS)** | Public ingress, authentication, routing | Pangolin, Zitadel, Traefik |
| **Homelab (Private)** | Compute, storage, AI workloads | Proxmox, NEWT Agent, Services |
| **Network** | Secure tunneling | NEWT/WireGuard tunnels, DreamMachine Pro |

**Key Principle:** The homelab has **zero open ports**. All public traffic flows through the VPS via encrypted WireGuard tunnels managed by Pangolin.

---

## Repository Structure

```text
infrastructure/
├── Makefile                    # Deployment commands
├── ARCHITECTURE.md             # Detailed architecture docs
├── documentation/              # Docusaurus documentation site
│
├── gateway-vps/                # VPS Stack (Public Gateway)
│   ├── compose.yaml            # Pangolin, Zitadel, Traefik
│   ├── .env.example            # Environment template
│   ├── init_config.sh          # Config generator
│   └── config/                 # Traefik, Pangolin configs
│
└── homelab-core/               # Homelab Stack (Private Services)
    ├── compose.yaml            # NEWT Agent, Langfuse, etc.
    └── services/               # Service-specific configs
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose installed
- Domain with DNS management (Cloudflare recommended)
- VPS with public IP (Hetzner, DigitalOcean, etc.)
- (Optional) Proxmox homelab with DreamMachine Pro / AdGuard

### 1. Clone the Repository

```bash
git clone https://github.com/KyleHub-Dev/infrastructure.git
cd infrastructure
```

### 2. Gateway VPS Deployment

```bash
cd gateway-vps

# Copy and configure environment
cp .env.example .env
nano .env  # Fill in your values

# Generate Pangolin config
./init_config.sh

# Deploy the stack
docker compose up -d
```

### 3. Homelab Deployment

```bash
cd homelab-core

# Copy and configure environment
cp .env.example .env
nano .env  # Fill in your values

# Deploy the stack
docker compose up -d
```

### 4. Post-Deployment Configuration

After both stacks are running, configure services in the Pangolin Dashboard:

1. Access `https://pangolin.yourdomain.com`
2. Complete initial setup (admin account, organization)
3. Configure Zitadel as the Identity Provider
4. Add NEWT tunnels for homelab services
5. Create resources for each service you want to expose

> 📖 **Full documentation:** See the [Docusaurus docs](documentation/) or visit [docs.kylehub.dev](https://docs.kylehub.dev)

---

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make deploy-vps` | Pull images and start the VPS stack |
| `make deploy-home` | Pull images and start the homelab stack |
| `make logs-vps` | Follow VPS container logs |
| `make logs-home` | Follow homelab container logs |
| `make sync-docs` | Build the documentation site |

---

## Core Services

### Gateway VPS

| Service | Description |
|---------|-------------|
| **Pangolin** | Zero Trust gateway, reverse proxy, tunnel management |
| **Zitadel** | Identity provider (OIDC/OAuth2), SSO for all services |
| **Traefik** | Edge router with automatic SSL via Let's Encrypt |
| **Gerbil** | WireGuard tunnel endpoint for NEWT connections |

### Homelab Core

| Service | Description |
|---------|-------------|
| **NEWT Agent** | Connects homelab to VPS via WireGuard tunnel |
| **Langfuse** | LLM observability and prompt management |
| **Proxmox** | Hypervisor for VMs and containers |
| **(Future) AdGuard Home** | Network-wide DNS and ad blocking |

---

## Configuration Flow

```
1. Deploy VPS Stack           → Pangolin, Zitadel, Traefik running
2. Complete Pangolin Setup    → Admin account, organization created
3. Configure Zitadel          → OIDC provider ready
4. Deploy Homelab Stack       → NEWT agent connects to VPS
5. Add Resources in Pangolin  → Services accessible via subdomains
6. Configure SSO              → Zitadel protects all services
```

---

## Documentation

Full documentation is available in the `documentation/` folder (Docusaurus) and covers:

- **Getting Started** — Prerequisites, initial setup
- **Gateway VPS Setup** — Complete VPS deployment guide
- **Homelab Setup** — Proxmox, networking, NEWT configuration
- **Post-Deployment** — Pangolin dashboard, Zitadel SSO, service exposure
- **Services** — Individual service setup guides
- **Troubleshooting** — Common issues and solutions

### Building the Docs

```bash
cd documentation
npm install
npm run start    # Development server
npm run build    # Production build
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

*Maintained by the KyleHub Organization*