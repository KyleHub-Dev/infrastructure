# <img src="logo.png" alt="KyleHub Logo" width="40" height="40" align="center"> KyleHub Infrastructure

Welcome to the central nervous system of **KyleHub**. This repository defines the Infrastructure-as-Code (IaC) for the KyleHub platform, connecting the public-facing Gateway (VPS) with the private Powerhouse (Homelab).

## Overview

This platform uses a **Hybrid Cloud Architecture** to combine the stability and reach of a cloud VPS with the compute power and storage of a private homelab.

*   **Public Gateway (VPS):** Handles ingress, Zero Trust authentication, and secure routing.
*   **Private Powerhouse (Homelab):** Runs heavy workloads (AI, LLMs, Storage) without exposing open ports.

## Repository Structure

This monorepo is designed to be deployed partially to different environments using Git Sparse Checkout.

```text
infrastructure/
├── Makefile                 # Central Control Panel
├── documentation/           # Docusaurus Documentation Source
│
├── gateway-vps/             # REMOTE VPS (The "Front Door")
│   ├── compose.yaml         # Runs: Pangolin Server, Zitadel
│   └── services/            # Service-specific configs (Auth, Mail)
│
└── homelab-core/            # HOMELAB (The "Engine Room")
    ├── compose.yaml         # Runs: Newt Agent, Langfuse, AI Services
    └── services/            # Service-specific configs
```

## Quick Start

We use a `Makefile` to simplify daily operations. You do not need to memorize Docker Compose file paths.

### 1. On the Gateway (Remote VPS)
```bash
# Deploy or Update the Gateway Stack
make deploy-vps

# View Logs
make logs-vps
```

### 2. On the Homelab (Home Server)
```bash
# Deploy or Update the Home Stack
make deploy-home

# View Logs
make logs-home
```

### 3. Documentation
```bash
# Build and Sync READMEs to Docusaurus
make sync-docs
```

## Core Services

| Service | Type | Location | Description |
| :--- | :--- | :--- | :--- |
| **Zitadel** | Identity | VPS | Centralized SSO & OIDC Provider. |
| **Pangolin** | Network | VPS | Zero Trust Gateway & Reverse Proxy. |
| **Newt** | Agent | Homelab | Tunnels private apps to the Gateway. |
| **Langfuse** | AI Ops | Homelab | LLM Engineering Platform. |
| **Proton Bridge** | Mail | VPS | Headless Email Relay for notifications. |

## Deployment Strategy

*   **Monorepo:** All infrastructure code lives here.
*   **Sparse Checkout:** Servers only pull the folder they need (`gateway-vps` OR `homelab-core`), keeping secrets and configs isolated.
*   **Identity Kit:** Custom applications link to this infrastructure via the [Identity Kit](https://github.com/KyleHub-Dev/identity-kit) for seamless authentication.

---
*Maintained by the KyleHub Organization.*