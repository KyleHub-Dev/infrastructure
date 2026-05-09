#!/bin/sh
# =====================================================================
# Post-issue / post-renew hook for lego.
# =====================================================================
# Copies the freshly minted cert + key into the shared dns-certs volume
# at the path AdGuard Home expects, then triggers `podman restart
# dns-adguard` over the mounted podman socket so AdGuard reloads the
# new TLS material (it does NOT auto-reload from disk).
#
# Env vars provided by lego on --renew-hook:
#   LEGO_CERT_DOMAIN    - the domain (e.g. dns.kylehub.dev)
#   LEGO_CERT_PATH      - path to the new cert.pem (leaf + chain)
#   LEGO_CERT_KEY_PATH  - path to the new key.pem (private key)
#
# We also accept being called manually after the first issue (run.sh
# sets the same env vars before sourcing this script).
# =====================================================================

set -eu

DOMAIN="${LEGO_CERT_DOMAIN:-${CERT_DOMAIN:-dns.kylehub.dev}}"
DEST="/certs/${DOMAIN}"
SOCK="/run/podman/podman.sock"
ADGUARD_CONTAINER="dns-adguard"

if [ -z "${LEGO_CERT_PATH:-}" ] || [ -z "${LEGO_CERT_KEY_PATH:-}" ]; then
  echo "[hook] ERROR: LEGO_CERT_PATH / LEGO_CERT_KEY_PATH not set" >&2
  exit 1
fi

mkdir -p "${DEST}"
cp -f "${LEGO_CERT_PATH}"     "${DEST}/cert.pem"
cp -f "${LEGO_CERT_KEY_PATH}" "${DEST}/key.pem"
chmod 644 "${DEST}/cert.pem" "${DEST}/key.pem"

echo "[hook] $(date -Iseconds) cert for ${DOMAIN} written to ${DEST}"

# ---- Trigger AdGuard restart ----
if [ ! -S "${SOCK}" ]; then
  echo "[hook] WARN: ${SOCK} not present — restart ${ADGUARD_CONTAINER} manually:"
  echo "[hook]       podman restart ${ADGUARD_CONTAINER}"
  exit 0
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "[hook] WARN: curl missing — restart ${ADGUARD_CONTAINER} manually:"
  echo "[hook]       podman restart ${ADGUARD_CONTAINER}"
  exit 0
fi

# Podman REST API: POST /v4.0.0/libpod/containers/{name}/restart
HTTP_STATUS=$(curl -s -o /dev/null -w '%{http_code}' \
  --unix-socket "${SOCK}" \
  -X POST "http://d/v4.0.0/libpod/containers/${ADGUARD_CONTAINER}/restart" || echo "000")

case "${HTTP_STATUS}" in
  204) echo "[hook] ${ADGUARD_CONTAINER} restart triggered (HTTP 204)" ;;
  *)   echo "[hook] WARN: podman restart returned HTTP ${HTTP_STATUS} — may need manual restart" ;;
esac
