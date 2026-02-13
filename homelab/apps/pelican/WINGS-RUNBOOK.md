# Wings Setup Runbook

> Agent-executable runbook for setting up Pelican Wings on the host.
> **Assumes:** Pelican Panel is already running and accessible via `APP_URL`.

---

## Required User Input

Collect these values before starting:

| Variable | Description | Example |
|----------|-------------|---------|
| `WINGS_DOMAIN` | Domain for Wings node | `wings.kylehub.dev` |
| `PANEL_URL` | Panel URL (already running) | `https://pelican.kylehub.dev` |
| `LE_EMAIL` | Email for Let's Encrypt | `admin@kylehub.dev` |
| `GAME_PORTS` | Game server port range | `25565-25665` |

---

## Phase 1: Preflight Checks (Agent)

Run these checks and report results before proceeding.

```bash
# 1. Check the Panel is reachable from the host
curl -sSo /dev/null -w "%{http_code}" https://<PANEL_URL>

# 2. Check if Docker Engine is installed and running
systemctl is-active docker
docker version

# 3. Check if Wings is already installed
test -f /usr/local/bin/wings && wings --version

# 4. Check if port 443 is already in use (Wings API)
ss -tlnp | grep ':443 '

# 5. Check if port 80 is available (certbot HTTP-01 challenge)
ss -tlnp | grep ':80 '

# 6. Check if certbot is installed
command -v certbot

# 7. Get the server's public IP (user needs this for DNS)
curl -s https://ifconfig.me

# 8. Check firewall status
sudo ufw status 2>/dev/null || (systemctl is-active firewalld && firewall-cmd --list-ports)
```

### Preflight Decision Table

| Check | OK | Action if NOT OK |
|-------|-----|------------------|
| Panel reachable | HTTP 200/301/302 | Stop. Panel must be running first. |
| Docker running | `active` + version output | Install Docker Engine (see Phase 3.1). **Do not use Podman** -  Wings requires Docker for reliable game server container management. |
| Wings already installed | binary not found | If found, ask user if they want to reinstall |
| Port 443 free | no output | If in use, identify what's using it and **ask user** how to proceed |
| Port 80 free | no output | If in use, certbot standalone won't work. Use `--webroot` or stop the conflicting service temporarily |
| Public IP obtained | IP returned | **Tell user** this IP for the DNS A record |

---

## Phase 2: User Action -  DNS Records

**Tell the user to do the following in Cloudflare (or their DNS provider).**
The agent cannot do this.

### Wings A Record

> Create this DNS record in Cloudflare. Set it to **DNS only** (grey cloud icon, NOT proxied).
>
> | Type | Name | Content | Proxy |
> |------|------|---------|-------|
> | **A** | `wings` | `<PUBLIC_IP from preflight>` | DNS only (grey cloud) |
>
> This makes `wings.kylehub.dev` resolve to your server.

### Verify DNS (Agent)

Wait for the user to confirm, then verify:

```bash
dig +short <WINGS_DOMAIN> A
```

The result must match the server's public IP. If not, DNS hasn't propagated yet -  wait and retry.

---

## Phase 3: Installation (Agent)

Run these steps sequentially.

### 3.1 Firewall

```bash
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=80/tcp          # temporary, for certbot challenge
sudo firewall-cmd --permanent --add-port=<GAME_PORTS>/tcp
sudo firewall-cmd --permanent --add-port=<GAME_PORTS>/udp
sudo firewall-cmd --reload
```

### 3.2 Docker Engine

Wings requires Docker Engine (not Podman) for reliable game server container management.

```bash
# Install Docker CE (Ubuntu)
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

sudo systemctl enable --now docker
```

Verify: `sudo docker version`

### 3.3 Wings Directories

```bash
sudo mkdir -p /etc/pelican /var/lib/pelican
```

### 3.4 Download Wings

```bash
sudo curl -L -o /usr/local/bin/wings \
    "https://github.com/pelican-dev/wings/releases/latest/download/wings_linux_amd64"
sudo chmod +x /usr/local/bin/wings
```

Verify: `wings --version`

### 3.5 SSL Certificate

```bash
sudo certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email <LE_EMAIL> \
    -d <WINGS_DOMAIN>
```

Verify:

```bash
sudo certbot certificates | grep -A2 <WINGS_DOMAIN>
```

Expected output shows cert and key paths under `/etc/letsencrypt/live/<WINGS_DOMAIN>/`.

Enable auto-renewal:

```bash
sudo systemctl enable --now certbot-renew.timer
```

### 3.6 Remove Temporary Port 80 Rule

```bash
sudo firewall-cmd --permanent --remove-port=80/tcp
sudo firewall-cmd --reload
```

> **Note:** If certbot renewal needs port 80 later, the `certbot-renew` timer handles it via pre/post hooks.
> Alternatively, keep port 80 open if you prefer unattended renewals without hooks.

### 3.7 Systemd Service

```bash
sudo tee /etc/systemd/system/wings.service > /dev/null <<'EOF'
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

sudo systemctl daemon-reload
```

---

## Phase 4: User Action -  Create Node in Panel

**Tell the user to do the following in the Pelican Panel web UI.**
The agent cannot do this.

> 1. Log into the Pelican Panel at `<PANEL_URL>`
> 2. Go to **Admin -> Nodes -> Create New**
> 3. Fill in:
>    - **FQDN:** `<WINGS_DOMAIN>`
>    - **Communicate Over SSL:** Use SSL Connection
>    - **Behind Proxy:** Not Behind Proxy
> 4. Click **Create**
> 5. Go to the new node's **Configuration** tab
> 6. **Copy the entire YAML configuration** and send it back here (paste it)

---

## Phase 5: Apply Config & Start Wings (Agent)

Once the user provides the YAML from the Panel:

### 5.1 Write the Base Config

```bash
# Write the YAML the user provided to the config file
sudo tee /etc/pelican/config.yml > /dev/null <<'EOF'
<PASTE USER-PROVIDED YAML HERE>
EOF
```

### 5.2 Patch SSL Settings

The Panel-generated config will have `port: 8080` and `ssl: enabled: false` by default.
These values must be changed.

Verify current values:

```bash
grep -A5 'api:' /etc/pelican/config.yml
```

Patch the config -  replace the `api` block's port and ssl section:

- Set `port: 443`
- Set `ssl.enabled: true`
- Set `ssl.cert: /etc/letsencrypt/live/<WINGS_DOMAIN>/fullchain.pem`
- Set `ssl.key: /etc/letsencrypt/live/<WINGS_DOMAIN>/privkey.pem`

Verify after patching:

```bash
grep -A8 'api:' /etc/pelican/config.yml
```

Expected:

```yaml
api:
  host: 0.0.0.0
  port: 443
  ssl:
    enabled: true
    cert: /etc/letsencrypt/live/<WINGS_DOMAIN>/fullchain.pem
    key: /etc/letsencrypt/live/<WINGS_DOMAIN>/privkey.pem
```

### 5.3 Start Wings

```bash
sudo systemctl enable --now wings
```

---

## Phase 6: Verification (Agent)

```bash
# 1. Wings service is running
sudo systemctl is-active wings

# 2. Wings is listening on 443
ss -tlnp | grep ':443 '

# 3. SSL handshake works
curl -sSo /dev/null -w "%{http_code}" https://<WINGS_DOMAIN>:443
# Expect 401 or 403 (no auth token) -  this means Wings is serving TLS correctly

# 4. Wings logs show no errors
sudo journalctl -u wings --no-pager -n 20

# 5. Wings can reach the Panel
curl -sSo /dev/null -w "%{http_code}" <PANEL_URL>
```

### Verification Decision Table

| Check | Expected | If NOT |
|-------|----------|--------|
| Service active | `active` | Check logs: `journalctl -u wings -n 50` |
| Listening on :443 | wings process shown | Config has wrong port, or port conflict |
| SSL handshake | HTTP 401/403 | Cert paths wrong in config, or cert not issued |
| Logs clean | No errors/panics | Read full logs, check config.yml syntax |
| Panel reachable | HTTP 200/301/302 | Wings can't reach Panel -  check DNS/firewall from host |

**Tell the user:** Check the Pelican Panel → Admin → Nodes. The node should now show as **Online**.

---

## Phase 7 (Optional): Game Server DNS

**Tell the user to do the following if they want clean domains for game servers.**

> For each Minecraft Java server, create two DNS records in Cloudflare:
>
> **A Record** (DNS only / grey cloud):
>
> | Type | Name | Content |
> |------|------|---------|
> | A | `modded-mc` | `<PUBLIC_IP>` |
>
> **SRV Record:**
>
> | Service | Protocol | Name | Priority | Weight | Port | Target |
> |---------|----------|------|----------|--------|------|--------|
> | `_minecraft` | `_tcp` | `modded-mc` | 0 | 0 | `25565` | `modded-mc.kylehub.dev` |
>
> Repeat for each server with a different subdomain and port.

### Verify SRV (Agent)

```bash
dig +short _minecraft._tcp.<subdomain>.<domain> SRV
# Expected: 0 0 25565 modded-mc.kylehub.dev.
```
