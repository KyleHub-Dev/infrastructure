---
title: Pangolin Setup Overview
sidebar_position: 1
tags:
  - Pangolin
  - Infrastructure Management
  - Docker
  - Traefik
  - Reverse Proxy
---

# Pangolin Setup Overview

:::info Official Documentation
This guide is based on the official Pangolin documentation available at [https://docs.digpangolin.com/](https://docs.digpangolin.com/). For the most up-to-date information, please refer to the official docs.
:::

This guide provides a comprehensive walkthrough for installing and configuring Pangolin as an infrastructure management platform on Proxmox VE.

## What is Pangolin?

[Pangolin](https://digpangolin.com/) is a self-hosted infrastructure management platform that provides:
- Server and service monitoring
- Docker container management
- Automated deployments
- Centralized dashboard for infrastructure overview
- Real-time alerts and notifications

## Prerequisites

Before proceeding with the Pangolin installation, ensure you have:

- Proxmox VE host with configured network bridges (see [Proxmox Setup](../proxmox-setup.mdx))
- OPNsense firewall configured (see [OPNsense Setup](../opnsense-setup.mdx))
- Domain name (optional, but recommended for HTTPS access via reverse proxy). This should be your base domain as established in the [Prerequisites for the Personal Enterprise Platform](../prerequisites.md).
- Basic understanding of Docker and containerization

## Setup Workflow

This guide is organized into the following sections:

### Core Setup (Required for All)

1. **[Getting Started](./1-getting-started.md)** - Container creation, Docker installation, Pangolin installation, and DNS configuration

### Choose Your Path

2. **[Simple Setup (DNS Only)](./2-simple-setup.md)** ⭐ **Recommended for beginners**
   - Direct connection to your server
   - Easier configuration
   - Perfect for development and learning
   - Uses HTTP-01 challenge for SSL certificates

   **OR**

3. **[Advanced Setup (Cloudflare Proxy)](./3-advanced-setup.md)** 🔒 **For production environments**
   - Traffic routed through Cloudflare's network
   - Enhanced DDoS protection
   - Requires DNS-01 challenge configuration
   - Additional security features

### Complete the Setup

4. **[Network & Firewall Configuration](./4-network-firewall.md)** - Configure OPNsense firewall rules and port forwards (varies based on your chosen path)

5. **[Post-Installation](./5-post-installation.md)** - Initial access, service management, security best practices, and backups

6. **[Troubleshooting](./6-troubleshooting.md)** - Comprehensive solutions for common issues

## Which Path Should You Choose?

### Choose Simple Setup (DNS Only) If:
- ✅ You're setting up Pangolin for the first time
- ✅ You want to get started quickly
- ✅ You're running a development or home lab environment
- ✅ You want fewer configuration steps
- ✅ You prefer simpler troubleshooting

### Choose Advanced Setup (Cloudflare Proxy) If:
- ✅ You're deploying to a production environment
- ✅ You need DDoS protection
- ✅ You want to hide your server's real IP address
- ✅ You want to leverage Cloudflare's CDN and security features
- ✅ You're comfortable with more complex configuration

:::tip You Can Switch Later
You can start with the Simple Setup and later migrate to the Advanced Setup if needed. However, starting with Advanced Setup from the beginning is recommended for production deployments.
:::

## Quick Start

Ready to begin? Start with:

1. [**Getting Started**](./1-getting-started.md) - Set up your container and install Pangolin
2. Choose either [**Simple Setup**](./2-simple-setup.md) or [**Advanced Setup**](./3-advanced-setup.md)
3. Continue with [**Network & Firewall**](./4-network-firewall.md)
4. Finish with [**Post-Installation**](./5-post-installation.md)

If you encounter any issues, refer to the [**Troubleshooting**](./6-troubleshooting.md) guide.
