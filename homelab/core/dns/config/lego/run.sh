#!/bin/sh
# =====================================================================
# Entrypoint for the dns-lego container.
# =====================================================================
# 1. Issues a Let's Encrypt cert for ${CERT_DOMAIN} via Cloudflare DNS-01
#    on first run (no-op if a cert is already on disk).
# 2. Loops every 12h, calling `lego renew --days 30`, which is a no-op
#    until the cert is within 30 days of expiry.
# 3. After a successful issue or renewal, runs renew-hook.sh which
#    copies the cert into the shared certs volume and restarts
#    dns-adguard so it picks up the new TLS material.
# =====================================================================

set -eu

: "${CERT_DOMAIN:?CERT_DOMAIN is required}"
: "${ACME_EMAIL:?ACME_EMAIL is required}"
: "${CF_DNS_API_TOKEN:?CF_DNS_API_TOKEN is required}"

LEGO_DATA="/data"
HOOK="/scripts/renew-hook.sh"
CERT_FILE="${LEGO_DATA}/certificates/${CERT_DOMAIN}.crt"
KEY_FILE="${LEGO_DATA}/certificates/${CERT_DOMAIN}.key"

# Ensure curl is available (the renew-hook needs it to talk to the
# podman socket). goacme/lego is alpine-based but minimal.
if ! command -v curl >/dev/null 2>&1; then
  echo "[lego] Installing curl for the renew-hook..."
  apk add --no-cache curl >/dev/null 2>&1 || \
    echo "[lego] WARN: failed to install curl — adguard restart hook will be a no-op"
fi

# ---- Initial issue ----
if [ ! -f "${CERT_FILE}" ]; then
  echo "[lego] No cert at ${CERT_FILE}, requesting from Let's Encrypt..."
  lego --accept-tos \
       --email "${ACME_EMAIL}" \
       --domains "${CERT_DOMAIN}" \
       --dns cloudflare \
       --path "${LEGO_DATA}" \
       run

  # Run the hook manually for the first issue (lego only fires
  # --renew-hook on renewals, not on initial issue).
  LEGO_CERT_DOMAIN="${CERT_DOMAIN}" \
  LEGO_CERT_PATH="${CERT_FILE}" \
  LEGO_CERT_KEY_PATH="${KEY_FILE}" \
    sh "${HOOK}" || echo "[lego] First-issue hook failed (non-fatal)"
else
  echo "[lego] Existing cert found at ${CERT_FILE}"
fi

# ---- Renewal loop ----
echo "[lego] Entering renewal loop (check every 12h, renew within 30d of expiry)"
while true; do
  sleep 43200
  echo "[lego] $(date -Iseconds) checking renewal for ${CERT_DOMAIN}..."
  if lego --accept-tos \
          --email "${ACME_EMAIL}" \
          --domains "${CERT_DOMAIN}" \
          --dns cloudflare \
          --path "${LEGO_DATA}" \
          renew \
          --days 30 \
          --renew-hook "${HOOK}"; then
    echo "[lego] Renewal check complete"
  else
    echo "[lego] WARN: renewal check failed (will retry in 12h)"
  fi
done
