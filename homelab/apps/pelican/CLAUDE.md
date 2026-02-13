# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Self-hosted Pelican game server panel deployment with Zitadel OIDC authentication, exposed via Pangolin NEWT secure tunnel (WireGuard). Pelican is a Laravel-based web app for managing Minecraft and other game servers.

## Architecture

**Dual-host design:**
- **Panel host (Podman):** Runs containerized via Podman Compose (panel, MariaDB, Redis, NEWT tunnel)
- **Wings host (Docker):** Wings runs as a native systemd service; game server containers are managed via Docker Engine

**Networking:** The panel container has no exposed host ports. All external access goes through the Pangolin NEWT tunnel. Wings connects to the panel via HTTPS using Let's Encrypt certificates.

**Authentication:** Zitadel OIDC via the `generic-oidc-providers` plugin + `kovah/laravel-socialite-oidc` Composer package (installed in the custom Dockerfile). OIDC handles authentication only; admin roles are assigned manually in the panel.

## Key Files

- `Dockerfile` — Extends official Pelican Panel image; adds Composer and installs the OIDC socialite provider
- `compose.yaml` — Four services: `pelican-panel`, `pelican-db` (MariaDB 10.11), `pelican-cache` (Redis), `newt-pelican` (tunnel)
- `.env` / `.env.example` — All configuration including DB creds, Pangolin tunnel config, app URL
- `SETUP.md` — Full deployment guide (panel, OIDC, Wings, DNS)
- `WINGS-RUNBOOK.md` — Agent-executable 7-phase Wings setup runbook
- `setup-wings.sh` — Automated Wings installation script (Docker Engine, certbot, systemd)

## Commands

```bash
# Build and start the full stack
podman-compose up -d --build

# View service status and logs
podman-compose ps
podman-compose logs pelican-panel
podman-compose logs newt-pelican

# Rebuild panel image after Dockerfile changes
podman-compose build pelican-panel

# Wings (on dedicated host)
sudo bash setup-wings.sh          # Interactive first-time setup
sudo systemctl enable --now wings  # Start Wings service
sudo systemctl status wings
sudo journalctl -u wings -f
```

## User Preferences

- **Editor:** User prefers `nano` for manual file editing. Use `nano` instead of `tee`, `sed`, or heredocs when giving interactive commands.

## Important Details

- The panel image is built from `Dockerfile` (not pulled directly), so changes require `podman-compose build`
- Rootless Podman compatibility: The Dockerfile explicitly fixes file ownership for overlay copy-up
- Environment uses `BEHIND_PROXY=true` and `TRUSTED_PROXIES` for Pangolin reverse proxy
- Volumes: `pelican-data` (app data + plugins), `pelican-logs`, `pelican-db-data`
- Wings requires an FQDN with SSL — bare IPs won't work for panel-to-node communication
- Wings requires Docker Engine (not Podman) — Podman's Docker API emulation has gaps that cause silent install failures
