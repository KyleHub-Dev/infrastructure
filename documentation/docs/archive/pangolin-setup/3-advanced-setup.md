---
title: Advanced Setup (Cloudflare Proxy)
sidebar_position: 4
tags:
  - Cloudflare Proxy
  - Orange Cloud
  - DNS-01 Challenge
  - Production Setup
  - DDoS Protection
  - Advanced Configuration
---

# Advanced Setup (Cloudflare Proxy)

This setup guide is for users who want **enhanced security and DDoS protection** by routing traffic through Cloudflare's network (orange cloud icon in Cloudflare). This is the recommended approach for production environments.

## What You'll Get

- ✅ DDoS protection from Cloudflare
- ✅ Hidden server IP address (Cloudflare IPs shown instead)
- ✅ Cloudflare's CDN and caching features
- ✅ Advanced security features (bot protection, rate limiting, etc.)
- ✅ Additional layer of SSL/TLS encryption

## What You Need to Know

- ⚠️ More complex configuration with additional steps
- ⚠️ Requires DNS-01 challenge for SSL certificates
- ⚠️ Requires Cloudflare API token configuration
- ⚠️ Bound to Cloudflare's [terms of service](https://www.cloudflare.com/de-de/website-terms/)

:::tip Need Something Simpler?
If you're just getting started or running a development environment, consider the [Simple Setup (DNS Only)](./2-simple-setup.md) instead.
:::

## 1. Cloudflare DNS Configuration

Before configuring network access, you need to set up DNS records in Cloudflare with proxy enabled.

### 1.1 Create DNS A Records

1. Log in to your [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Select your domain (e.g., `kylehub.dev`)
3. Navigate to **DNS > Records**
4. Create the following two A records:

:::tip Which IP Address to Use?
Use the **OPNsense WAN IP** (the additional public IP assigned to OPNsense), not the Proxmox host's main IP address.

**Why?**
- OPNsense acts as your firewall and manages all incoming traffic
- The OPNsense WAN IP is the public-facing IP that handles port forwarding
- Traffic needs to reach OPNsense first, which then routes it to internal services
- Both IPs are on the same physical server, but OPNsense IP is the entry point

You can find your OPNsense WAN IP:
- In OPNsense: **Interfaces > WAN** (IPv4 address)
- From OPNsense shell: `curl ifconfig.io`
- This is the additional IP you ordered from your hosting provider
:::

**Record 1: Base Domain**
- **Type**: A
- **Name**: `@` (this represents your base domain)
- **IPv4 address**: Your **OPNsense WAN IP** (e.g., `203.0.113.50`)
- **Proxy status**: **Proxied (orange cloud icon)** 🟠
- **TTL**: Auto

**Record 2: Wildcard Subdomain**
- **Type**: A
- **Name**: `*` (wildcard for all subdomains)
- **IPv4 address**: Your **OPNsense WAN IP** (e.g., `203.0.113.50`)
- **Proxy status**: **Proxied (orange cloud icon)** 🟠
- **TTL**: Auto

:::warning Critical Setting
Make sure both records are set to **Proxied (orange cloud icon)**. This is required for Cloudflare proxy to work.
:::

### 1.2 Verify DNS Propagation

After creating the records, verify they are resolving correctly:

```bash
# Test base domain
dig yourdomain.com +short

# Test wildcard (using pangolin subdomain as example)
dig pangolin.yourdomain.com +short

# Both should return Cloudflare IPs (like 104.21.x.x or 172.67.x.x)
# NOT your direct server IP
```

DNS propagation typically takes a few minutes but can take up to 24 hours in some cases.

## 2. SSL/TLS Configuration in Cloudflare

Pangolin **only works with Full (Strict) mode** when using Cloudflare proxy.

1. In Cloudflare dashboard, navigate to **SSL/TLS > Overview**
2. Set SSL/TLS encryption mode to **Full (strict)**
3. Pangolin will continue to manage Let's Encrypt certificates via DNS-01 challenge
4. Cloudflare will encrypt traffic between clients and Cloudflare, and verify your server's certificate

:::danger SSL Mode Requirement
Pangolin **will not work** with Cloudflare's **Full** or **Automatic** SSL/TLS modes. Only **Full (Strict)** mode is supported.
:::

## 3. Configure WireGuard/Gerbil with Cloudflare Proxy

Since Cloudflare proxy obscures the destination IP, you must explicitly set your VPS IP in the Pangolin configuration for WireGuard (Gerbil) tunnels to work correctly.

### 3.1 Get Your VPS Public IP

Find your VPS public IP address. This should be the **OPNsense WAN IP** (the additional public IP that's routed to your OPNsense VM), not your Proxmox host IP.

:::tip Which IP to Use?
- **Use**: The additional public IP assigned to OPNsense's WAN interface
- **Don't use**: The Proxmox host's main IP address
- Both IPs are on the same physical server, but traffic needs to reach OPNsense first
:::

You can find this IP in several ways:

**Option 1: From OPNsense Web Interface**
1. Log in to OPNsense
2. Navigate to **Interfaces > WAN**
3. Note the IPv4 address

**Option 2: From OPNsense Console**
```bash
# From OPNsense console, option 8 (Shell)
curl ifconfig.io
```

**Option 3: From Pangolin Container**
```bash
# This will show the IP that external services see
curl ifconfig.io
```

### 3.2 Update Pangolin Configuration

Edit the Pangolin configuration file (inside the pangolin console):

```bash
nano config/config.yml
```

Add or update the `gerbil` section with your VPS IP:

```yaml
# filepath: config/config.yml
gerbil:
  base_endpoint: "YOUR_VPS_IP_ADDRESS"  # Replace with your actual VPS IP (e.g., 203.0.113.50)
```

Example:

```yaml
# filepath: config/config.yml
gerbil:
  start_port: 51820
  base_endpoint: "203.0.113.50"  # Your actual VPS public IP
```

Save the file (`Ctrl + O`, `Enter`, `Ctrl + X`).

### 3.3 Restart Pangolin Services

Apply the configuration changes:

```bash
docker compose restart
```

## 4. Configure Cloudflare API for DNS-01 Challenge

:::danger Critical Requirement
When using Cloudflare proxy (orange cloud), Traefik **MUST** use DNS-01 challenge for SSL certificates. HTTP-01 challenge will not work because Cloudflare needs to verify your certificate before proxying traffic.
:::

### 4.1 Create Cloudflare API Token

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Go to **My Profile > API Tokens**
3. Click **Create Token**
4. Use the **Edit zone DNS** template
5. Configure permissions:
   - **Permissions**: Zone / DNS / Edit
   - **Zone Resources**: Include / Specific zone / yourdomain.com
6. Click **Continue to summary**
7. Click **Create Token**
8. **Copy the token immediately** - you won't be able to see it again

### 4.2 Configure Pangolin with Cloudflare API Token

Edit the Pangolin environment file:

```bash
# Inside Pangolin container (you'll be in /root by default)
cd ~
nano .env
```

Add or update these lines:

```bash
# Cloudflare DNS-01 Challenge Configuration
CF_API_EMAIL=your-cloudflare-email@example.com
CF_DNS_API_TOKEN=your-api-token-from-step-1
```

### 4.3 Modify Traefik Configuration for DNS-01 Challenge

Pangolin manages Traefik configuration through files in `~/config/traefik/`. You need to modify the main Traefik configuration file to enable DNS-01 challenge.

```bash
# Inside Pangolin container (you'll be in /root by default)
cd ~
nano config/traefik/traefik_config.yml
```

**Find the `certificatesResolvers` section** (around line 27) that looks like this:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      httpChallenge:        # ← Remove this
        entryPoint: web     # ← Remove this
      email: "admin@kylehub.dev"
      storage: "/letsencrypt/acme.json"
      caServer: "https://acme-v02.api.letsencrypt.org/directory"
```

**Replace it** with DNS-01 challenge configuration:

```yaml
certificatesResolvers:
  letsencrypt:
    acme:
      dnsChallenge:         # ← Add this
        provider: cloudflare  # ← Add this
        resolvers:          # ← Add this
          - "1.1.1.1:53"    # ← Add this
          - "8.8.8.8:53"    # ← Add this
      email: "admin@kylehub.dev"  # Use your email
      storage: "/letsencrypt/acme.json"
      caServer: "https://acme-v02.api.letsencrypt.org/directory"
```

:::danger Critical Changes
- **Remove** the entire `httpChallenge` section (both lines)
- **Add** the `dnsChallenge` section with Cloudflare provider
- Keep the same indentation: 2 spaces per level
- Make sure YAML syntax is correct (colons followed by spaces)
:::

### 4.4 Add Cloudflare IP Trust Configuration

In the same `config/traefik/traefik_config.yml` file, find the `entryPoints` section (around line 34) and add `forwardedHeaders` with Cloudflare trusted IPs.

**Find this section:**

```yaml
entryPoints:
  web:
    address: ":80"
  websecure:
    address: ":443"
    # ... other settings ...
```

**Replace it with:**

```yaml
entryPoints:
  web:
    address: ":80"
    forwardedHeaders:
      trustedIPs:
        - "173.245.48.0/20"
        - "103.21.244.0/22"
        - "103.22.200.0/22"
        - "103.31.4.0/22"
        - "141.101.64.0/18"
        - "108.162.192.0/18"
        - "190.93.240.0/20"
        - "188.114.96.0/20"
        - "197.234.240.0/22"
        - "198.41.128.0/17"
        - "162.158.0.0/15"
        - "104.16.0.0/13"
        - "104.24.0.0/14"
        - "172.64.0.0/13"
        - "131.0.72.0/22"
  websecure:
    address: ":443"
    forwardedHeaders:
      trustedIPs:
        - "173.245.48.0/20"
        - "103.21.244.0/22"
        - "103.22.200.0/22"
        - "103.31.4.0/22"
        - "141.101.64.0/18"
        - "108.162.192.0/18"
        - "190.93.240.0/20"
        - "188.114.96.0/20"
        - "197.234.240.0/22"
        - "198.41.128.0/17"
        - "162.158.0.0/15"
        - "104.16.0.0/13"
        - "104.24.0.0/14"
        - "172.64.0.0/13"
        - "131.0.72.0/22"
    transport:
      respondingTimeouts:
        readTimeout: "30m"
    http:
      tls:
        certResolver: "letsencrypt"
```

:::tip
Make sure to preserve any existing settings under `websecure` (like `transport` and `http` sections) when adding `forwardedHeaders`.
:::

Save the file (`Ctrl + O`, `Enter`, `Ctrl + X`).

### 4.5 Create docker-compose.override.yml for Environment Variables

Create the `docker-compose.override.yml` file in your home directory to pass Cloudflare API credentials to Traefik:

```bash
# Inside Pangolin container
cd ~
nano docker-compose.override.yml
```

Add the following content:

```yaml
services:
  traefik:
    environment:
      - CF_API_EMAIL=${CF_API_EMAIL}
      - CF_DNS_API_TOKEN=${CF_DNS_API_TOKEN}
```

Save the file (`Ctrl + O`, `Enter`, `Ctrl + X`).

:::info Why Three Files?
- `config/traefik/traefik_config.yml`: Main Traefik configuration (DNS-01 challenge, trusted IPs, routing rules)
- `docker-compose.override.yml`: Environment variables for Cloudflare API credentials
- `.env`: Stores the actual API credentials
- All three work together to enable Cloudflare proxy with DNS-01 challenge
:::

### 4.6 Delete Old Certificates and Restart Services

To force Traefik to generate new certificates using DNS-01 challenge:

```bash
# Delete old certificate storage
rm -f config/letsencrypt/acme.json

# Restart all services
docker compose down
docker compose up -d
```

### 4.7 Verify Certificate Generation

Watch the Traefik logs to confirm certificates are being generated:

```bash
docker compose logs -f traefik
```

Look for messages like:
- `Trying to challenge with DNS-01`
- `Certificate obtained for domain pangolin.yourdomain.com`

This process can take 2-5 minutes. Be patient.

:::tip Common Success Messages
When everything works correctly, you'll see:
- `Starting provider *acme.Provider`
- `Testing certificate renew...`
- `Register...` (this is where Traefik waits)

**The logs will pause here - this is normal!** Traefik only generates certificates when you actually access your domain.
:::

## 5. Next Steps

:::success Configuration Complete
Your Cloudflare proxy is now configured. Continue with firewall configuration to allow traffic through.
:::

Continue to: **[Network & Firewall Configuration](./4-network-firewall.md)** (use Option B for Cloudflare Proxy)