#!/bin/sh
# =====================================================================
# Entrypoint for the dns-lego container.
# =====================================================================
# 1. On first run (no cert on disk): issues a Let's Encrypt cert via
#    Cloudflare DNS-01 covering every name in CERT_DOMAINS.
# 2. Loops every 12h, calling `lego renew --days 30`, which is a no-op
#    until the cert is within 30 days of expiry.
# 3. After a successful issue or renewal, runs renew-hook.sh which
#    copies the cert into the shared certs volume and restarts
#    dns-adguard so it picks up the new TLS material.
# =====================================================================

# `set -f` disables filename globbing - matters because CERT_DOMAINS
# can contain a wildcard (e.g. *.dns.kylehub.dev) that we MUST pass
# verbatim to lego, not let the shell expand against the cwd.
set -euf

: "${CERT_DOMAINS:?CERT_DOMAINS is required (comma-separated, primary first)}"
: "${ACME_EMAIL:?ACME_EMAIL is required}"
: "${CF_DNS_API_TOKEN:?CF_DNS_API_TOKEN is required}"

LEGO_DATA="/data"
HOOK="/scripts/renew-hook.sh"

# Primary domain = first comma-separated entry. lego writes the cert
# files under /data/certificates/<primary>.{crt,key,issuer.crt,json}.
PRIMARY_DOMAIN="${CERT_DOMAINS%%,*}"
CERT_FILE="${LEGO_DATA}/certificates/${PRIMARY_DOMAIN}.crt"
KEY_FILE="${LEGO_DATA}/certificates/${PRIMARY_DOMAIN}.key"

# Expand CERT_DOMAINS into a sequence of `--domains <name>` args.
# lego accepts the flag multiple times, one per SAN entry.
DOMAIN_ARGS=""
IFS=','
for d in $CERT_DOMAINS; do
  # strip surrounding whitespace (in case user wrote "a, b, c")
  d_trimmed=$(printf '%s' "$d" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  [ -z "$d_trimmed" ] && continue
  DOMAIN_ARGS="$DOMAIN_ARGS --domains $d_trimmed"
done
unset IFS

echo "[lego] primary domain: ${PRIMARY_DOMAIN}"
echo "[lego] full SAN list:  ${CERT_DOMAINS}"

# ---- Locate the lego binary ----
# The goacme/lego image structure has shifted across versions
# (Alpine-based with /usr/bin/lego, scratch-based with /lego, etc.).
# Find it explicitly so an entrypoint override does not depend on PATH.
LEGO=""
for path in /usr/bin/lego /usr/local/bin/lego /lego /bin/lego; do
  if [ -x "$path" ]; then
    LEGO="$path"
    break
  fi
done
if [ -z "$LEGO" ] && command -v lego >/dev/null 2>&1; then
  LEGO="$(command -v lego)"
fi
if [ -z "$LEGO" ]; then
  echo "[lego] ERROR: lego binary not found in image" >&2
  exit 1
fi
echo "[lego] using binary at: ${LEGO}"

# ---- Ensure curl is available (used by the renew-hook to talk to the
#      Podman API socket). Best-effort install if missing. ----
if ! command -v curl >/dev/null 2>&1; then
  echo "[lego] curl not present; attempting install..."
  if command -v apk >/dev/null 2>&1; then
    apk add --no-cache curl >/dev/null 2>&1 || \
      echo "[lego] WARN: apk install failed - adguard restart hook will be a no-op"
  else
    echo "[lego] WARN: no package manager available - adguard restart hook will be a no-op"
  fi
fi

# ---- Initial issue ----
if [ ! -f "${CERT_FILE}" ]; then
  echo "[lego] No cert at ${CERT_FILE}, requesting from Let's Encrypt..."
  # shellcheck disable=SC2086  # DOMAIN_ARGS must word-split into multiple flags
  "${LEGO}" --accept-tos \
       --email "${ACME_EMAIL}" \
       ${DOMAIN_ARGS} \
       --dns cloudflare \
       --path "${LEGO_DATA}" \
       run

  # Run the hook manually for the first issue (lego only fires
  # --renew-hook on renewals, not on initial issue).
  LEGO_CERT_DOMAIN="${PRIMARY_DOMAIN}" \
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
  echo "[lego] $(date -Iseconds 2>/dev/null || date) checking renewal for ${PRIMARY_DOMAIN}..."
  # shellcheck disable=SC2086
  if "${LEGO}" --accept-tos \
          --email "${ACME_EMAIL}" \
          ${DOMAIN_ARGS} \
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
