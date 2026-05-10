#!/usr/bin/env bash
# =====================================================================
# core/_edge/bootstrap.sh - idempotent prep for the edge stack.
# =====================================================================
# What this does:
#   1. Creates the two shared external Podman networks if missing:
#        - homelab-core-edge   (user-facing traffic <-> core-newt)
#        - homelab-core-data   (service-to-service backbone)
#   2. Copies .env.example to .env if .env does not exist yet.
#
# Safe to re-run: every operation is idempotent.
#
# After running:
#   1. Edit .env, set NEWT_ID and NEWT_SECRET (provisioned in Pangolin
#      under Sites -> New Site -> "Homelab Core").
#   2. podman-compose up -d
#
# See README.md for the full network model.
# =====================================================================

set -euo pipefail

cd "$(dirname "$0")"

for net in homelab-core-edge homelab-core-data; do
  if podman network exists "$net" 2>/dev/null; then
    echo "[ok]   network $net already exists"
  else
    podman network create "$net" >/dev/null
    echo "[new]  network $net created"
  fi
done

if [[ -f .env ]]; then
  echo "[ok]   .env already exists - leaving as is"
else
  cp .env.example .env
  echo "[new]  .env copied from .env.example"
  echo ""
  echo "Next steps:"
  echo "  1. edit .env and set NEWT_ID + NEWT_SECRET (from Pangolin)"
  echo "  2. podman-compose up -d"
fi
