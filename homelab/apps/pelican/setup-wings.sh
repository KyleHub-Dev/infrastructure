#!/bin/bash
# Pelican Wings Installation Script for Dedicated Host
# This script installs Docker Engine, Wings, and Let's Encrypt SSL.
#
# Wings requires Docker Engine (not Podman) to manage game server containers.

set -e

echo "--- Preparing Host for Pelican Wings ---"

# Prompt for Wings domain and email
read -rp "Enter your Wings domain (e.g., wings.kylehub.dev): " WINGS_DOMAIN
read -rp "Enter your email for Let's Encrypt: " LE_EMAIL

if [ -z "$WINGS_DOMAIN" ] || [ -z "$LE_EMAIL" ]; then
    echo "ERROR: Domain and email are required."
    exit 1
fi

# Detect package manager
if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
else
    echo "ERROR: Unsupported package manager. This script supports apt (Debian/Ubuntu) and dnf (Fedora/RHEL)."
    exit 1
fi

# 1. Install Docker Engine
if command -v docker &> /dev/null && docker version &> /dev/null; then
    echo "Docker is already installed, skipping..."
else
    echo "Installing Docker Engine..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        apt-get update
        apt-get install -y ca-certificates curl gnupg
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io
    elif [ "$PKG_MANAGER" = "dnf" ]; then
        dnf -y install dnf-plugins-core
        dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
        dnf install -y docker-ce docker-ce-cli containerd.io
    fi
    systemctl enable --now docker
fi

echo "Docker version: $(docker --version)"

# 2. Create Wings Directories
mkdir -p /etc/pelican /var/lib/pelican

# 3. Download Wings Binary
echo "Downloading Wings..."
curl -L -o /usr/local/bin/wings "https://github.com/pelican-dev/wings/releases/download/v1.0.0-beta24/wings_linux_amd64"
chmod +x /usr/local/bin/wings

# 4. Install certbot and obtain SSL certificate
echo "Setting up Let's Encrypt SSL..."
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    if [ "$PKG_MANAGER" = "apt" ]; then
        apt-get install -y certbot
    elif [ "$PKG_MANAGER" = "dnf" ]; then
        dnf install -y certbot
    fi
fi

certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email "$LE_EMAIL" \
    -d "$WINGS_DOMAIN"

# 5. Enable certbot auto-renewal timer
systemctl enable --now certbot-renew.timer

# 6. Create Systemd Service
echo "Creating systemd service..."
cat <<EOF > /etc/systemd/system/wings.service
[Unit]
Description=Pelican Wings Daemon
After=docker.service
Requires=docker.service

[Service]
User=root
WorkingDirectory=/etc/pelican
LimitNOFILE=4096
PIDFile=/var/run/wings/wings.pid
ExecStart=/usr/local/bin/wings
Restart=on-failure
StartLimitInterval=180
StartLimitBurst=30
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo ""
echo "--- Wings Installation Complete ---"
echo ""
echo "SSL certificate installed for: $WINGS_DOMAIN"
echo "  Cert: /etc/letsencrypt/live/$WINGS_DOMAIN/fullchain.pem"
echo "  Key:  /etc/letsencrypt/live/$WINGS_DOMAIN/privkey.pem"
echo ""
echo "Next steps:"
echo "1. Log into your Pelican Panel."
echo "2. Go to Admin -> Nodes -> Create New."
echo "3. Set the FQDN to: $WINGS_DOMAIN"
echo "4. Set 'Communicate Over SSL' to 'Use SSL Connection'."
echo "5. Set 'Behind Proxy' to 'Not Behind Proxy'."
echo "6. After creating, go to the 'Configuration' tab."
echo "7. Copy the generated YAML and save it to /etc/pelican/config.yml"
echo "8. Edit /etc/pelican/config.yml and set the SSL paths:"
echo ""
echo "   api:"
echo "     host: 0.0.0.0"
echo "     port: 443"
echo "     ssl:"
echo "       enabled: true"
echo "       cert: /etc/letsencrypt/live/$WINGS_DOMAIN/fullchain.pem"
echo "       key: /etc/letsencrypt/live/$WINGS_DOMAIN/privkey.pem"
echo ""
echo "9. Run: sudo systemctl enable --now wings"
