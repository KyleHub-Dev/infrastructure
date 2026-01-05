# Zitadel Auth-Server Setup

This is the documentation for setting up the central authentication server.

**Stack:**

  * **Hardware:** Hetzner Cloud VPS (CX23 - 2 vCPU, 4GB RAM)
  * **Server:** auth-debian-4gb-nbg1-1
  * **OS:** Debian 13 "Trixie" (Stable)
  * **Runtime:** Docker Engine (Official)
  * **Proxy:** Traefik v3 (via Docker Socket)
  * **App:** Zitadel + PostgreSQL 17

-----

## Step 1: Server Initialization (Hetzner)

1.  Select the **Debian 13** image in the Hetzner Panel.
2.  Add your **SSH Key** (Never log in with a password).
3.  Create the server.

### 1.1 Server Setup

Execute the **Server Setup** steps from the main README (`/README.md`). These include:
*   System Updates
*   Installation of tools (curl, git, nano, htop, fail2ban)
*   Docker Installation

-----

## Step 2: Repository Setup

We clone the entire repository to your home directory (`~/ops-stack`).

```bash
cd ~
git clone https://github.com/KyleHub-Dev/ops-stack.git
cd ops-stack/services/auth
```

## Step 3: Configuration

### 3.1 Directory Structure

`letsencrypt/` and `data/` are already present in the repo via `.gitkeep` placeholders and their contents are gitignored.

```bash
mkdir data/postgres
```

If you ever need to recreate them locally, run:

```bash
mkdir -p letsencrypt data/postgres
```

### 3.2 Environment Variables

Copy the example configuration and adjust it:

```bash
cp .env.example .env
nano .env
```

### 3.3 Set Permissions

Traefik requires an empty file with restrictive permissions, otherwise the container will not start.

```bash
touch ./letsencrypt/acme.json
chmod 600 ./letsencrypt/acme.json
```

### 3.4 Traefik Configuration Files

Static Traefik settings now live in `traefik/traefik.yml` and dynamic options (TLS defaults, optional middlewares) in `traefik/dynamic/dynamic.yml`. The ACME email still comes from your `.env` via `ACME_EMAIL`, so you only need to edit the YAML files if you want to adjust entrypoints, certificate resolver behavior, or middlewares.

-----

## Step 4: Cloudflare & Firewall Configuration

To make the server "stealthy" and enable SSL via DNS Challenge:

1.  **Cloudflare DNS:** Set an A-Record for your subdomain to the server IP. Proxy Status: **Orange (Proxied)**.
2.  **Cloudflare SSL:** Set SSL/TLS to **"Full (Strict)"**.
3.  **Cloudflare API Token:**
      * Go to [Cloudflare Profile > API Tokens](https://dash.cloudflare.com/profile/api-tokens).
      * Click **Create Token**.
      * Use the **Edit Zone DNS** template.
      * Select your domain in **Zone Resources**.
      * Copy the token and add it to your `.env` file as `CF_DNS_API_TOKEN`.
      * Ensure `CF_API_EMAIL` matches your Cloudflare account email.
4.  **Hetzner Cloud Firewall:**
      * Create a Firewall in the Hetzner Panel.
      * **Inbound:**
          * TCP 22 (SSH): Only your own IP.
          * TCP 80 & 443 (Web): **Allow only Cloudflare IPs** (List: [https://www.cloudflare.com/ips-v4](https://www.cloudflare.com/ips-v4)).
      * Apply the Firewall to the server.

-----

## Step 5: Start

```bash
cd ~/ops-stack/services/auth
docker compose up -d
```

Wait approx. 1-2 minutes for the first start (Database initialization). Check the logs with:

```bash
docker compose logs -f zitadel
```

Once Zitadel is running, you can reach it at: `https://auth.yourdomain.com/ui/console`

-----

### Updates

To update to the latest versions of Debian 13 or Docker Images:

```bash
sudo apt update && sudo apt upgrade -y
cd ~/ops-stack/services/auth
docker compose pull
docker compose up -d
docker image prune -f
```

-----

## Manual Email Verification

If SMTP is not configured or you need to manually verify a user's email address, you can do so directly in the database.

**1. Find the user by email or user_id:**

```bash
docker compose exec -it db psql -U zitadel -d zitadel -c \
  "SELECT user_id, email, is_email_verified FROM projections.users14_humans WHERE email = 'user@example.com';"
```

**2. Set the email as verified:**

```bash
docker compose exec -it db psql -U zitadel -d zitadel -c \
  "UPDATE projections.users14_humans SET is_email_verified = TRUE WHERE user_id = '<USER_ID>';"
```

Replace `<USER_ID>` with the actual user ID from step 1.
