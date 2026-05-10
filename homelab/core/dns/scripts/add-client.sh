#!/usr/bin/env bash
# =====================================================================
# add-client.sh - Provision a new AdGuard Home client end-to-end
# =====================================================================
# Generates a random token, registers a Persistent Client with that
# identifier, and appends the identifier to the Allowed Clients list
# (the access lock). Prints the DoT/DoH hostname to set on the device.
#
# Usage:
#   ./add-client.sh <friendly-name> [<extra-tags...>]
#
# Examples:
#   ./add-client.sh phone-kyle
#   ./add-client.sh laptop-andrea user_andrea os_macos
#
# Requirements (set in dns/.env, NOT committed):
#   ADGUARD_URL   - default http://127.0.0.1:3000 (works on Hetzner host)
#   ADGUARD_USER  - admin user from the wizard
#   ADGUARD_PASS  - admin password from the wizard
#   CERT_DOMAINS  - comma-separated; primary domain is used for hostname
#
# Run on the Hetzner host (or anywhere with reachable AdGuard API).
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

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "Usage: $0 <friendly-name> [<tags...>]" >&2
  echo "Example: $0 phone-kyle" >&2
  exit 1
fi
shift || true
EXTRA_TAGS=("$@")

ADGUARD_URL="${ADGUARD_URL:-http://127.0.0.1:3000}"
: "${ADGUARD_USER:?ADGUARD_USER required - set in dns/.env}"
: "${ADGUARD_PASS:?ADGUARD_PASS required - set in dns/.env}"

PRIMARY_DOMAIN="${CERT_DOMAINS%%,*}"
PRIMARY_DOMAIN="${PRIMARY_DOMAIN:-dns.kylehub.dev}"

for cmd in curl jq openssl; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: $cmd is required" >&2; exit 1; }
done

TOKEN=$(openssl rand -hex 8)
IDENTIFIER="${NAME}-${TOKEN}"
HOSTNAME="${IDENTIFIER}.${PRIMARY_DOMAIN}"

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

# Build tags JSON array
TAGS_JSON='[]'
if [ ${#EXTRA_TAGS[@]} -gt 0 ]; then
  TAGS_JSON=$(printf '%s\n' "${EXTRA_TAGS[@]}" | jq -R . | jq -s .)
fi

# 1) Add persistent client
PERSISTENT_BODY=$(jq -n \
  --arg name "$NAME" \
  --arg id "$IDENTIFIER" \
  --argjson tags "$TAGS_JSON" \
  '{
    name: $name,
    ids: [$id],
    tags: $tags,
    use_global_settings: true,
    use_global_blocked_services: true,
    upstreams: [],
    filtering_enabled: true,
    safebrowsing_enabled: false,
    parental_enabled: false
  }')

if ! api POST /control/clients/add "$PERSISTENT_BODY" >/dev/null 2>&1; then
  # If the client already exists, update instead. Idempotency-friendly.
  echo "Note: persistent client may already exist; trying update path..." >&2
  UPDATE_BODY=$(jq -n \
    --arg name "$NAME" \
    --argjson data "$PERSISTENT_BODY" \
    '{name: $name, data: $data}')
  api POST /control/clients/update "$UPDATE_BODY" >/dev/null
fi

# 2) Append to access list
CURRENT=$(api GET /control/access/list)
NEW=$(echo "$CURRENT" | jq --arg id "$IDENTIFIER" \
  '.allowed_clients = (.allowed_clients // [] | . + [$id] | unique)')
api POST /control/access/set "$NEW" >/dev/null

# 3) Output
cat <<EOF

==========================================================
  Client provisioned successfully
==========================================================
  Friendly name : ${NAME}
  Identifier    : ${IDENTIFIER}
  DoT/DoH host  : ${HOSTNAME}

  Configure on the device:
    Android Private DNS : ${HOSTNAME}
    iOS profile / Linux : tls://${HOSTNAME}
    DoH URL             : https://${PRIMARY_DOMAIN}/dns-query/${IDENTIFIER}

  Treat this hostname like a password. Anyone who knows it
  can use this DNS resolver. To revoke, run:
    ./remove-client.sh ${IDENTIFIER}
==========================================================
EOF
