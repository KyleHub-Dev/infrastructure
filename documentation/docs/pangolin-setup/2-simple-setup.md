---
title: Simple Setup (DNS Only)
sidebar_position: 3
tags:
  - DNS Only
  - Gray Cloud
  - HTTP-01 Challenge
  - Beginner Friendly
  - Simple Configuration
---

# Simple Setup (DNS Only)

This setup guide is for users who want a **straightforward configuration** with direct DNS resolution (gray cloud icon in Cloudflare). This is the recommended approach for beginners, development environments, and home labs.

## What You'll Get

- ✅ Direct connection from internet to your server
- ✅ Simpler configuration with fewer steps
- ✅ Automatic SSL certificates via HTTP-01 challenge
- ✅ No additional Traefik configuration needed
- ✅ Easier troubleshooting

## What You Won't Get

- ❌ DDoS protection from Cloudflare
- ❌ Hidden server IP address
- ❌ Cloudflare's CDN and caching features
- ❌ Advanced security features

:::tip Want More Protection?
If you need enhanced security for a production environment, consider the [Advanced Setup (Cloudflare Proxy)](./3-advanced-setup.md) instead.
:::

## 1. Cloudflare DNS Configuration

Before configuring network access, you need to set up DNS records in Cloudflare to point to your Pangolin server.

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
- **Proxy status**: **DNS only (gray cloud icon)** ⚠️
- **TTL**: Auto

**Record 2: Wildcard Subdomain**
- **Type**: A
- **Name**: `*` (wildcard for all subdomains)
- **IPv4 address**: Your **OPNsense WAN IP** (e.g., `203.0.113.50`)
- **Proxy status**: **DNS only (gray cloud icon)** ⚠️
- **TTL**: Auto

:::warning Critical Setting
Make sure both records are set to **DNS only (gray cloud icon)**. Do NOT enable proxy (orange cloud) for this setup path.
:::

### 1.2 Verify DNS Propagation

After creating the records, verify they are resolving correctly:

```bash
# Test base domain
dig yourdomain.com +short

# Test wildcard (using pangolin subdomain as example)
dig pangolin.yourdomain.com +short

# Both should return your OPNsense WAN IP (e.g., 203.0.113.50)
# NOT Cloudflare IPs
```

DNS propagation typically takes a few minutes but can take up to 24 hours in some cases.

## 2. Default Configuration

:::tip No Additional Configuration Needed
With DNS Only mode, Pangolin's default configuration already works correctly. Traefik will automatically use HTTP-01 challenge for SSL certificates.
:::

The Pangolin installer has already configured Traefik to use **HTTP-01 challenge** for Let's Encrypt SSL certificates. This is the default behavior and requires:
- Port 80 (HTTP) accessible from the internet for certificate validation
- Port 443 (HTTPS) for secure access
- Direct DNS resolution (which you've set up above)

No additional Traefik or Cloudflare configuration is required.

## 3. Next Steps

:::success Configuration Complete
Your DNS is now configured for Simple Setup (DNS Only). Continue with firewall configuration to allow traffic through.
:::

Continue to: **[Network & Firewall Configuration](./4-network-firewall.md)** (use Option A for DNS Only)