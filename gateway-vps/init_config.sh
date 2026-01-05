#!/bin/sh
set -e  # Exit immediately if a command exits with a non-zero status

# Check if .env file exists
if [ -f .env ]; then
  set -a    # Automatically export all variables
  . ./.env  # Use '.' instead of 'source' for POSIX compliance
  set +a    # Stop automatically exporting variables
else
  echo "Error: .env file not found." >&2
  exit 1
fi

# Check if the template file exists
if [ ! -f config/config.yml.template ]; then
  echo "Error: config/config.yml.template not found." >&2
  exit 1
fi

# Perform variable substitution
envsubst '${PANGOLIN_SERVER_SECRET} ${PANGOLIN_DASHBOARD_URL} ${PANGOLIN_SUBDOMAIN} ${DOMAIN_ROOT} ${VPS_PUBLIC_IP} ${PANGOLIN_LICENSE_KEY}' < config/config.yml.template > config/config.yml

echo "Successfully generated config/config.yml from .env values."
echo "Dashboard URL set to: $PANGOLIN_DASHBOARD_URL"