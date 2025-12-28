.PHONY: deploy-vps deploy-home logs-vps logs-home sync-docs

# --- DEPLOYMENT ---

# Run this on your VPS
deploy-vps:
	cd gateway-vps && docker compose pull && docker compose up -d --remove-orphans

# Run this on your Homelab
deploy-home:
	cd homelab-core && docker compose pull && docker compose up -d --remove-orphans

# --- LOGS ---

logs-vps:
	cd gateway-vps && docker compose logs -f

logs-home:
	cd homelab-core && docker compose logs -f

# --- DOCUMENTATION ---

sync-docs:
	cd documentation && npm run build
