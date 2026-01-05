#!/bin/bash
set -a # Automatically export all variables

# Load .env but evaluate nested variables
# We do this by sourcing it, but since .env isn't always valid shell syntax (no 'export', sometimes spaces),
# we need to be careful.
# However, the user's .env seems simple enough.
# Let's try a robust approach: explicitly expanding known nested vars.

if [ -f .env ]; then
  source .env
fi

# Manually fix the nested variable if the shell didn't expand it during assignment (which it won't for simple K=V lines read by source if they rely on earlier lines without 'export')
# Actually, in bash, `source .env` works if the file is KEY=VAL.
# But `PANGOLIN_DASHBOARD_URL=https://${PANGOLIN_SUBDOMAIN}.${DOMAIN_ROOT}`
# The shell will try to expand valid variables at parse time.
# If PANGOLIN_SUBDOMAIN is defined *before*, it works.
# Let's check the order in .env.

# .env order:
# DOMAIN_ROOT=...
# PANGOLIN_SUBDOMAIN=...
# PANGOLIN_DASHBOARD_URL=...
# This order is correct for `source`.

# However, `export $(grep ...)` does NOT expand. It blindly sets the value.
# So I must use `source .env`.

# Let's verify what happens when we source it.
source .env

# Re-evaluate the dashboard URL to be safe, in case it was read literally.
PANGOLIN_DASHBOARD_URL="https://${PANGOLIN_SUBDOMAIN}.${DOMAIN_ROOT}"

# Now run envsubst
envsubst '${PANGOLIN_SERVER_SECRET} ${PANGOLIN_DASHBOARD_URL} ${PANGOLIN_SUBDOMAIN} ${DOMAIN_ROOT} ${VPS_PUBLIC_IP}' < config/config.yml.template > config/config.yml

echo "Successfully generated config/config.yml from .env values."
echo "Dashboard URL set to: $PANGOLIN_DASHBOARD_URL"