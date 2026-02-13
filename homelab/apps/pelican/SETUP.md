# Pelican Panel Setup

> **Last Updated:** 2026-02-12

Complete setup guide for a self-hosted Pelican Panel with Zitadel OIDC authentication, exposed via Pangolin NEWT tunnel.

---

## Architecture Overview

```
                         Internet
                            |
               ┌────────────┼────────────┐
               │                         │
    ┌──────────┴──────────┐    ┌─────────┴─────────┐
    │  Pangolin Gateway   │    │  DNS A Record      │
    │  (Panel traffic)    │    │  wings.kylehub.dev │
    └──────────┬──────────┘    └─────────┬─────────┘
               │ WireGuard Tunnel        │ Direct (port 443)
    ┌──────────┴──────────┐    ┌─────────┴─────────┐
    │   NEWT Agent        │    │   Wings (systemd)  │
    └──────────┬──────────┘    │   :443 (TLS)      │
               │ pelican-net   │   + game ports     │
    ┌──────────┼──────────┐    └─────────┬─────────┘
    │          │          │              │ Docker API
┌───┴───┐ ┌───┴────┐ ┌───┴───┐    ┌─────┴─────┐
│ Panel │ │MariaDB │ │ Redis │    │ Game      │
│  :80  │ │ :3306  │ │ :6379 │    │ Servers   │
└───────┘ └────────┘ └───────┘    └───────────┘
   Panel Host (Podman)             Wings Host (Docker)
```

---

## Prerequisites

**Panel host:**
- Podman and Podman Compose installed (`podman-compose`)
- A Pangolin Gateway with a site configured for the panel domain
- A Zitadel instance (for OIDC, configured in Part 2)

**Wings host (dedicated machine):**
- Docker Engine (CE) -  Wings orchestrates game server containers via the Docker API
- A public IP with a domain name (for Let's Encrypt SSL)

> **Why two different runtimes?** The panel is a standard web app stack where Podman's rootless containers work great. Wings, however, is a Docker orchestrator -  it creates, destroys, and attaches to game server containers via the Docker API. Podman's Docker socket emulation has compatibility gaps that cause silent failures (e.g., stuck installs). Use Docker Engine on Wings hosts for reliable operation.

---

## Part 1: Panel Deployment

### 1. Create the Environment File

```bash
cp .env.example .env
```

### 2. Generate Secure Passwords

```bash
# Generate DB_PASSWORD
openssl rand -base64 24

# Generate MYSQL_ROOT_PASSWORD (separate, for root access only)
openssl rand -base64 24
```

### 3. Fill in `.env`

| Variable | Description |
|----------|-------------|
| `APP_URL` | Your panel domain (e.g., `https://pelican.kylehub.dev`) |
| `ADMIN_EMAIL` | Email for the initial admin account |
| `DB_PASSWORD` | Generated password (used by both panel and MariaDB) |
| `MYSQL_ROOT_PASSWORD` | Separate root password for MariaDB |
| `PANGOLIN_SERVER` | Your Pangolin Gateway URL |
| `NEWT_ID` | NEWT ID from Pangolin Dashboard |
| `NEWT_SECRET` | NEWT Secret from Pangolin Dashboard |

### 4. Configure Pangolin Site

In your Pangolin Dashboard, create a site for Pelican and set the tunnel target to:

```
http://pelican-panel:80
```

Copy the NEWT ID and Secret into your `.env` file.

### 5. Start the Stack

```bash
podman-compose up -d --build
```

### 6. Verify

```bash
# Check all containers are healthy
podman-compose ps

# Check panel logs for errors
podman-compose logs pelican-panel

# Check NEWT connection
podman-compose logs newt-pelican
```

The panel should now be accessible at your `APP_URL`. The first visit will prompt you to create an admin account using the `ADMIN_EMAIL` address.

---

## Part 2: Zitadel OIDC Authentication

Pelican Panel supports OAuth providers via plugins. Zitadel requires the **Generic OIDC Providers** plugin from [pelican-dev/plugins](https://github.com/pelican-dev/plugins).

### Step 1: Install the Generic OIDC Plugin

1. Log into your Pelican Panel as an admin
2. Navigate to **Admin -> Plugins**
3. Use the **Import** button to upload the `generic-oidc-providers` plugin archive from the [pelican-dev/plugins](https://github.com/pelican-dev/plugins) repository
4. Enable the plugin after import

The plugin data persists in the `pelican-data` volume, so it survives container restarts.

### Step 2: Create an OIDC Application in Zitadel

1. Log into your Zitadel Management Console
2. Go to **Projects** and create a new project (e.g., `Pelican Panel`)
3. Inside the project, click **New** under Applications
4. Configure the application:

| Setting | Value |
|---------|-------|
| **Name** | `Pelican Panel` |
| **Type** | Web |
| **Authentication Method** | Code (Authorization Code flow) |

5. Set the redirect URI:

```
https://<your-panel-domain>/auth/oauth/callback/zitadel
```

For example:

```
https://pelican.kylehub.dev/auth/oauth/callback/zitadel
```

6. Optionally set a post-logout URI:

```
https://pelican.kylehub.dev/
```

7. Click **Create** and immediately copy the **Client ID** and **Client Secret** (the secret is shown only once)

### Step 3: Configure Zitadel Token Settings

1. In the Zitadel application, go to the **Token Settings** tab
2. Enable **"User Info inside ID Token"** so email claims are included in the token

### Step 4: Configure the Plugin in Pelican

1. In the Pelican admin panel, find **Generic OIDC Providers** (added by the plugin)
2. Create a new provider with these values:

| Field | Value |
|-------|-------|
| **ID** | `zitadel` |
| **Display Name** | `Zitadel` |
| **Client ID** | *(from Step 2)* |
| **Client Secret** | *(from Step 2)* |
| **Base URL** | `https://zitadel.kylehub.dev` *(your Zitadel instance URL)* |
| **Verify JWT** | `false` |
| **Create Missing Users** | `true` *(auto-create users on first OIDC login)* |
| **Link Missing Users** | `true` *(auto-link by email if user already exists)* |

The plugin auto-discovers all OIDC endpoints via `<base_url>/.well-known/openid-configuration`, so no manual endpoint configuration is needed.

### Step 5: Test the Login

1. Open your panel in an incognito/private window
2. The login page should now show a **Zitadel** button
3. Click it, authenticate with Zitadel, and confirm you're redirected back to the panel
   
### Step 6: Roles & Permissions (Important)

**What can a "Standard User" do?**
By default, a new user created via OIDC has **no administrative access**. They can only:
- Log in to the panel.
- View and manage **servers explicitly assigned to them** (as owner or subuser).
- Manage their own account details (API keys, SSH keys).
- They **cannot** create new servers (unless an admin allows it).
- They **cannot** access the Admin Control Panel.

**Do I need to create roles in Zitadel?**
No. By default, the plugin uses OIDC for **authentication** only (verifying who the user is). It does not automatically sync **authorization** (roles/permissions) from Zitadel to Pelican.

- **Standard Users:** Any user who can authenticate via Zitadel (and is granted access to the Project in Zitadel) will be created as a standard user in Pelican.
- **Admins:** You must **manually** grant "Root Admin" or specific permissions to a user inside the Pelican Panel after they have logged in for the first time.
  1. Login as your initial admin account (from Part 1).
  2. Go to **Admin -> Users**.
  3. Find the user created via Zitadel.
  4. Toggle **Root Admin** to "Yes" or assign specific permissions.

**Restricting Access:**
If you want to prevent unauthorized Zitadel users from logging in, use **Zitadel Project Grants**:
1. In Zitadel, go to your Project -> "Grants".
2. Only add the specific users or organizations you want to have access to the panel.
3. Users without a grant will be denied by Zitadel before they even reach Pelican.

### Recommended Roles & Permissions

Pelican has two permission layers: **Admin Roles** (access to the Admin panel for managing infrastructure) and **Subuser Permissions** (per-server permissions for what a user can do on an assigned server).

#### Admin Roles (Admin -> Roles)

Create these in **Admin -> Roles**. Only needed for users who manage panel infrastructure.

**Server Admin** -  for a secondary admin account (full admin access with safety guardrails):

| Model | viewList | view | create | update | delete |
|-------|----------|------|--------|--------|--------|
| Server | x | x | x | x | x |
| Node | x | x | | x | |
| Egg | x | x | x | x | x |
| User | x | x | x | x | |
| Allocation | x | x | x | x | x |
| Database | x | x | x | x | x |
| DatabaseHost | x | x | | x | |
| Mount | x | x | x | x | x |
| ApiKey | x | x | x | x | x |
| Role | x | x | | | |
| Webhook | x | x | x | x | x |

> This allows full management but prevents deleting users, nodes, or modifying roles -  keeping those as root-only safeguards.

#### Subuser Permission Sets (per-server)

Assign these when adding users to a server via **Server -> Subusers -> Add**.

**Normal User** -  casual friends who just want to play:

- **Control:** console, start, stop, restart
- **Files:** read, read-content
- **Backups:** read, download
- **Activity:** read
- **Startup:** read

**Friend** -  users who manage their own assigned server (change modpacks, manage files, reinstall):

- **Control:** console, start, stop, restart
- **Files:** read, read-content, create, update, delete, archive, sftp
- **Backups:** read, create, delete, download, restore
- **Schedules:** read, create, update, delete
- **Startup:** read, update
- **Settings:** rename, description, reinstall
- **Activity:** read
- **Allocation:** read

**Power User** -  trusted friends with full server control:

- Everything from **Friend**, plus:
- **Users:** read, create, update, delete (can manage subusers on their server)
- **Database:** read, create, update, delete, view-password
- **Allocation:** read, create, update, delete
- **Startup:** read, update, docker-image (can switch Docker images)

#### Summary

| Role | Type | Who | Key abilities |
|------|------|-----|--------------|
| Root Admin | Admin role | Primary admin | Everything |
| Server Admin | Admin role | Secondary admin | Full admin minus delete users/nodes/roles |
| Normal User | Subuser perms | Casual friends | Play, view console, read files |
| Friend | Subuser perms | Friends with a server | Manage files, reinstall, backups, SFTP |
| Power User | Subuser perms | Trusted friends | Full server control, manage subusers, databases |

---

## Part 3: Wings (Game Node) Setup

Wings runs as a native systemd service on a **dedicated host** (not in a container). It manages game server containers via Docker Engine. Because the Panel enforces SSL for all node connections, **you cannot use an IP address** as the node FQDN -  you need a domain with a valid TLS certificate.

> **Container runtime:** Wings requires **Docker Engine (CE)** on the host. Wings orchestrates game server containers (pulling images, creating/destroying containers, streaming logs) via the Docker API. Do not use Podman on the Wings host -  its Docker socket emulation has compatibility gaps that cause silent failures like stuck installs.

### Why not `127.0.0.1` or a raw IP?

- The Panel requires SSL for node connections: *"You cannot connect to an IP Address over SSL"*
- `127.0.0.1` would resolve to the Panel container's own loopback, not the host
- Private addresses can't get a public SSL certificate

### Step 1: Install Docker Engine

Install Docker CE on the Wings host (Ubuntu example):

```bash
# Install prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key and repository
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Enable and start Docker
sudo systemctl enable --now docker

# Verify
sudo docker version
```

### Step 2: Create a DNS Record for Wings

Create an **A record** in your DNS provider (e.g., Cloudflare) pointing to your server's public IP:

```
wings.kylehub.dev  →  <your-server-public-ip>
```

> **Important (Cloudflare):** Set the record to **DNS only** (grey cloud), not Proxied. Cloudflare proxy does not support the WebSocket and non-HTTP traffic that Wings and game servers require.

### Step 3: Open Firewall Ports

Wings needs port 443 for its API (HTTPS), and game servers need their allocated ports:

```bash
# Wings API (HTTPS with Let's Encrypt)
sudo ufw allow 443/tcp

# Game server port range (adjust to match your Panel allocations)
sudo ufw allow 25565:25665/tcp
sudo ufw allow 25565:25665/udp
```

> **Note:** If using `firewalld` instead of `ufw`, use `sudo firewall-cmd --permanent --add-port=443/tcp` etc.

### Step 4: Run the Setup Script

The script installs Wings, sets up certbot for automatic SSL, and configures the systemd service.

```bash
sudo bash setup-wings.sh
```

The script will prompt you for the Wings domain (e.g., `wings.kylehub.dev`) and an email for Let's Encrypt.

### Step 5: Configure the Node in the Panel

1. Log into the Pelican Panel
2. Go to **Admin -> Nodes -> Create New**
3. Set the **FQDN** to your Wings domain (e.g., `wings.kylehub.dev`)
4. Set **Communicate Over SSL** to **Use SSL Connection**
5. Set **Behind Proxy** to **Not Behind Proxy** (Wings terminates TLS directly)
6. After creating the node, go to its **Configuration** tab
7. Copy the generated YAML and save it to `/etc/pelican/config.yml`
8. **Edit** `/etc/pelican/config.yml` to add the SSL certificate paths:

```yaml
api:
  host: 0.0.0.0
  port: 443
  ssl:
    enabled: true
    cert: /etc/letsencrypt/live/<your-wings-domain>/fullchain.pem
    key: /etc/letsencrypt/live/<your-wings-domain>/privkey.pem
```

9. Start Wings:

```bash
sudo systemctl enable --now wings
```

### Step 6: Verify Wings Connectivity

```bash
# Check Wings is running
sudo systemctl status wings

# Check Wings logs
sudo journalctl -u wings -f

# Verify SSL cert is valid
curl -I https://wings.kylehub.dev:443
```

In the Panel, the node should show as **Online** on the Nodes page.

---

## Part 4: Game Server DNS (SRV Records)

Players can connect to your game servers using a clean domain like `modded-mc.kylehub.dev` instead of `203.0.113.50:25565`. This uses a combination of an **A record** (for the IP) and an **SRV record** (for the port).

> **Note:** SRV-based service discovery works for **Minecraft Java Edition**. Bedrock Edition does not support SRV records -  players must enter the IP and port manually.

### Step 1: Create an A Record

In Cloudflare (or your DNS provider), create an A record for the subdomain:

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `modded-mc` | `<your-server-public-ip>` | **DNS only** (grey cloud) |

This makes `modded-mc.kylehub.dev` resolve to your server's IP.

### Step 2: Create an SRV Record

Create an SRV record that tells Minecraft clients which port to use:

| Field | Value |
|-------|-------|
| **Type** | SRV |
| **Name** | `_minecraft._tcp.modded-mc` |
| **Priority** | 0 |
| **Weight** | 0 |
| **Port** | `25565` |
| **Target** | `modded-mc.kylehub.dev` |

In Cloudflare's dashboard, the form looks like:

| Field | Value |
|-------|-------|
| **Service** | `_minecraft` |
| **Protocol** | `_tcp` |
| **Name** | `modded-mc` |
| **Priority** | 0 |
| **Weight** | 0 |
| **Port** | `25565` |
| **Target** | `modded-mc.kylehub.dev` |

### How It Works

When a player types `modded-mc.kylehub.dev` in the Minecraft server list:

1. The client queries `_minecraft._tcp.modded-mc.kylehub.dev` for an SRV record
2. DNS responds: connect to `modded-mc.kylehub.dev` on port `25565`
3. The client resolves `modded-mc.kylehub.dev` via the A record → your server IP
4. The client connects to `<your-server-ip>:25565`

The player never has to type a port number.

### Multiple Servers

You can repeat this for each game server on a different port:

| Subdomain | SRV Port | Description |
|-----------|----------|-------------|
| `modded-mc.kylehub.dev` | 25565 | Modded Minecraft |
| `vanilla-mc.kylehub.dev` | 25566 | Vanilla Minecraft |
| `creative-mc.kylehub.dev` | 25567 | Creative server |

Each one needs its own A record (all pointing to the same IP) and its own SRV record (with the specific port).

### Verify

```bash
# Check the A record resolves
dig modded-mc.kylehub.dev A

# Check the SRV record
dig _minecraft._tcp.modded-mc.kylehub.dev SRV
```

The SRV response should show something like:

```
_minecraft._tcp.modded-mc.kylehub.dev. 300 IN SRV 0 0 25565 modded-mc.kylehub.dev.
```

> **Tip:** DNS propagation can take a few minutes. If it doesn't work immediately, wait and retry.

---

## Troubleshooting

### Panel shows 502 or is unreachable

- Verify NEWT is connected: `podman-compose logs newt-pelican`
- Check Pangolin Dashboard to confirm the tunnel is online
- Ensure the Pangolin site target is `http://pelican-panel:80`

### Database connection errors

- Verify MariaDB is healthy: `podman-compose ps pelican-db`
- Check that `DB_PASSWORD` in `.env` is set (panel and MariaDB share this variable)
- View MariaDB logs: `podman-compose logs pelican-db`

### OIDC login fails or redirects with error

- Confirm the redirect URI in Zitadel matches exactly: `https://<APP_URL>/auth/oauth/callback/zitadel`
- Verify "User Info inside ID Token" is enabled in Zitadel token settings
- Check that the **Base URL** in the plugin matches your Zitadel instance URL (no trailing slash)
- View panel logs for OAuth errors: `podman-compose logs pelican-panel | grep -i oauth`

### Wings can't connect to the panel

- Wings connects via `APP_URL`, so the panel must be reachable from the Wings host
- If using Pangolin, ensure the Wings host's IP is allowed to access the panel through the gateway
- Test from the Wings host: `curl -I https://pelican.kylehub.dev`

### Wings node shows offline in the Panel

- Check Wings is running: `sudo systemctl status wings`
- Check Wings logs: `sudo journalctl -u wings -f`
- Verify the SSL cert paths in `/etc/pelican/config.yml` match the certbot output
- Verify the FQDN in the Panel matches your DNS record exactly
- Ensure port 443 is open on the Wings host

### Server install stuck on "Installing"

This means the panel dispatched the install job to Wings, but Wings never reported back. Debug on the **Wings host**:

```bash
# 1. Check Wings logs for errors around the install time
sudo journalctl -u wings --since "1 hour ago" --no-pager

# 2. Check if Docker is running (Wings requires Docker, not Podman)
sudo systemctl status docker
sudo docker version

# 3. Check if the install container exists
sudo docker ps -a | grep install

# 4. Check if the Docker image was pulled
sudo docker images

# 5. If an install container exists, check its logs
sudo docker logs <container-id>

# 6. Test Wings → Panel connectivity (Wings must be able to call back)
curl -I https://pelican.kylehub.dev
```

Common causes:
- **Docker not installed:** Wings requires Docker Engine. Podman's Docker socket emulation has compatibility gaps that cause installs to silently hang.
- **Docker image pull failed:** Network issues on the Wings host preventing image downloads from `ghcr.io`.
- **Egg install script stuck:** Some eggs (e.g., CurseForge) download large modpacks during install -  check the install container logs.
- **Wings can't reach the panel:** Wings needs to call back to the panel to report completion.

To retry: use the panel UI **Admin -> Servers -> [server] -> Reinstall** after fixing the underlying issue.

### SSL certificate errors on Wings

- Verify certbot succeeded: `sudo certbot certificates`
- Renew manually if expired: `sudo certbot renew`
- Ensure the domain's DNS A record points to the correct public IP (DNS-only, not proxied)
- Check cert file permissions: Wings runs as root, so this is usually not an issue
