#!/bin/bash
# Pelican Wings Installation Script for Dedicated Root
# This script prepares the host to run game servers.

set -e

echo "--- Preparing Host for Pelican Wings ---"

# 1. Prepare Podman for Wings
echo "Configuring Podman..."
# Enable the podman socket (emulating docker.sock)
systemctl enable --now podman.socket

# Ensure the symlink exists so Wings finds the 'Docker' API
if [ ! -S /var/run/docker.sock ]; then
    ln -s /run/podman/podman.sock /var/run/docker.sock
fi

# 2. Create Wings Directory
mkdir -p /etc/pelican /var/lib/pelican

# 3. Download Wings Binary
echo "Downloading Wings..."
curl -L -o /usr/local/bin/wings "https://github.com/pelican-dev/wings/releases/latest/download/wings_linux_amd64"
chmod +x /usr/local/bin/wings

# 4. Create Systemd Service
echo "Creating systemd service..."
cat <<EOF > /etc/systemd/system/wings.service
[Unit]
Description=Pelican Wings Daemon
After=podman.socket
Requires=podman.socket

[Service]
User=root
WorkingDirectory=/etc/pelican
LimitNOFILE=4096
PIDFile=/var/run/wings/wings.pid
ExecStart=/usr/local/bin/wings
Restart=on-failure
StartLimitInterval=180
StartLimitBurst=30

[Install]
WantedBy=multi-user.target
EOF

echo "--- Wings Installation Complete ---"
echo "NOTE: Using PODMAN. Ensure 'podman-docker' is installed for best compatibility with game eggs."
echo "Next steps:"
echo "1. Log into your Pelican Panel (at your APP_URL)."
echo "2. Go to Admin -> Nodes -> Create New."
echo "3. Use '127.0.0.1' as the FQDN (since it's on the same host) or the local LAN IP."
echo "4. After creating, go to the 'Configuration' tab in the Panel."
echo "5. Copy the generated YAML and save it to /etc/pelican/config.yml"
echo "6. Run: systemctl enable --now wings"
