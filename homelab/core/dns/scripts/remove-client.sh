#!/usr/bin/env bash
# =====================================================================
# remove-client.sh - Revoke an AdGuard client
# =====================================================================
# Removes the Persistent Client by name OR identifier and strips the
# identifier from Allowed Clients.
#
# Usage:
#   ./remove-client.sh <name-or-identifier>
# =====================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "Usage: $0 <name-or-identifier>" >&2
  exit 1
fi

ADGUARD_URL="${ADGUARD_URL:-http://127.0.0.1:3000}"
: "${ADGUARD_USER:?ADGUARD_USER required}"
: "${ADGUARD_PASS:?ADGUARD_PASS required}"

api() {
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -fsSL -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
      -H 'Content-Type: application/json' \
      -X "$method" "${ADGUARD_URL}${path}" -d "$body"
  else
    curl -fsSL -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
      -X "$method" "${ADGUARD_URL}${path}"
  fi
}

# Find the client by name or by identifier
CLIENTS=$(api GET /control/clients)
MATCH=$(echo "$CLIENTS" | jq -r --arg t "$TARGET" '
  .clients[]? | select(.name == $t or (.ids // [] | index($t))) | .name
' | head -1)

if [ -z "$MATCH" ]; then
  echo "ERROR: no client matching '$TARGET' (by name or identifier)" >&2
  exit 1
fi

# Collect every identifier from that client to also strip from access list
IDS=$(echo "$CLIENTS" | jq -r --arg n "$MATCH" '
  .clients[] | select(.name == $n) | .ids[]?
')

# 1) Remove from access list
CURRENT=$(api GET /control/access/list)
NEW=$(echo "$CURRENT" | jq --argjson ids "$(echo "$IDS" | jq -R . | jq -s .)" '
  .allowed_clients = ((.allowed_clients // []) - $ids)
')
api POST /control/access/set "$NEW" >/dev/null

# 2) Delete persistent client
DELETE_BODY=$(jq -n --arg n "$MATCH" '{name: $n}')
api POST /control/clients/delete "$DELETE_BODY" >/dev/null

echo "Removed client: $MATCH"
echo "Stripped identifiers from Allowed Clients:"
echo "$IDS" | sed 's/^/  - /'
