# Pelican Panel Setup

> **Last Updated:** 2026-02-12

Complete setup guide for a self-hosted Pelican Panel with Zitadel OIDC authentication, exposed via Pangolin NEWT tunnel.

---

## Architecture Overview

```
                    Internet
                       |
              ┌────────┴────────┐
              │  Pangolin Gateway│
              │  (VPS / Cloud)   │
              └────────┬────────┘
                       │ WireGuard Tunnel
              ┌────────┴────────┐
              │   NEWT Agent     │
              └────────┬────────┘
                       │ pelican-net
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────┴────┐   ┌─────┴─────┐  ┌────┴────┐
   │  Panel  │   │  MariaDB  │  │  Redis  │
   │  :80    │   │  :3306    │  │  :6379  │
   └─────────┘   └───────────┘  └─────────┘
```

---

## Prerequisites

- Docker and Docker Compose installed on the host
- A Pangolin Gateway with a site configured for the panel domain
- A Zitadel instance (for OIDC, configured in Part 2)

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
docker compose up -d
```

### 6. Verify

```bash
# Check all containers are healthy
docker compose ps

# Check panel logs for errors
docker compose logs pelican-panel

# Check NEWT connection
docker compose logs newt-pelican
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

---

## Part 3: Wings (Game Node) Setup

If you want to run game servers on the same host as the panel, use the included `setup-wings.sh` script.

> **Note:** The script uses Podman with a Docker socket symlink. Ensure `podman-docker` is installed for compatibility with game eggs.

```bash
sudo bash setup-wings.sh
```

After the script completes:

1. Log into the Pelican Panel
2. Go to **Admin -> Nodes -> Create New**
3. Set the FQDN to `127.0.0.1` (same host) or the LAN IP
4. After creating the node, go to its **Configuration** tab
5. Copy the generated YAML and save it to `/etc/pelican/config.yml`
6. Start Wings:

```bash
sudo systemctl enable --now wings
```

---

## Troubleshooting

### Panel shows 502 or is unreachable

- Verify NEWT is connected: `docker compose logs newt-pelican`
- Check Pangolin Dashboard to confirm the tunnel is online
- Ensure the Pangolin site target is `http://pelican-panel:80`

### Database connection errors

- Verify MariaDB is healthy: `docker compose ps pelican-db`
- Check that `DB_PASSWORD` in `.env` is set (panel and MariaDB share this variable)
- View MariaDB logs: `docker compose logs pelican-db`

### OIDC login fails or redirects with error

- Confirm the redirect URI in Zitadel matches exactly: `https://<APP_URL>/auth/oauth/callback/zitadel`
- Verify "User Info inside ID Token" is enabled in Zitadel token settings
- Check that the **Base URL** in the plugin matches your Zitadel instance URL (no trailing slash)
- View panel logs for OAuth errors: `docker compose logs pelican-panel | grep -i oauth`

### Wings can't connect to the panel

- Wings connects via `APP_URL`, so the panel must be reachable from the host
- If using Pangolin, ensure the host's IP is allowed to access the panel through the gateway
