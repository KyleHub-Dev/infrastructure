---
title: Post-Installation
sidebar_position: 6
tags:
  - Initial Setup
  - Service Configuration
  - Security
  - Backup
---

## 1. Initial Pangolin Access

### 1.1 Access Pangolin Dashboard

1. Open your web browser
2. Navigate to: `https://pangolin.yourdomain.com`
3. You should see the Pangolin setup page
4. Enter the **Setup Token** that was displayed at the end of the installation (Section 3.1.6)

:::warning
If you didn't save the setup token, you can retrieve it by running this command on the Pangolin container:
```bash
docker compose logs pangolin | grep "Token"
```
:::

### 1.2 Complete Initial Setup

Follow the on-screen prompts to:
1. Create your admin account
2. Configure basic settings
3. Set up your organization details
4. Configure notification preferences (optional)

## 2. Exposing Critical Services Through Pangolin

Now that Pangolin is accessible via `https://pangolin.yourdomain.com` and the firewall is configured, you need to set up access to your critical infrastructure services. This section will guide you through exposing services in the correct order to maintain secure access to your infrastructure.

:::info Understanding the Flow
At this point in the setup:
1. ✅ Pangolin is running and accessible via `https://pangolin.yourdomain.com`
2. ✅ OPNsense firewall rules are configured (from Step 4)
3. ✅ Only ports 80 and 443 are exposed to the internet through OPNsense
4. ⚠️ You **may** no longer have direct IP access to OPNsense or Proxmox (depends on setup):
   - **Advanced Setup (Cloudflare Proxy)**: Direct IP access is blocked - you must use subdomains
   - **Simple Setup (DNS Only)**: Direct IP access may still work, but subdomain access is recommended
5. 🎯 Next: Set up subdomain access to these services through Pangolin's dashboard
:::

### 2.1 Understanding Service Exposure Pattern

Services in your infrastructure should follow this access pattern:

```
Internet → Cloudflare/DNS → OPNsense (Firewall) → Pangolin (Traefik) → Individual Services
```

**Key principles:**
- Only Pangolin is directly exposed to the internet (ports 80/443)
- All other services are accessed via subdomains routed through Pangolin's Traefik reverse proxy
- Traefik handles SSL termination, routing, and authentication
- Services maintain their existing internal IPs and ports

### 2.2 First Priority: Set Up OPNsense Web Access

After completing the firewall configuration (Step 4), direct IP access to OPNsense may be blocked (especially if you followed the Advanced Setup). Set up subdomain access via Pangolin's dashboard.

#### 2.2.1 Create a Site in Pangolin

1. Open your browser and navigate to: `https://pangolin.yourdomain.com`
2. Log in to your Pangolin dashboard
3. Navigate to **Sites** in the left sidebar
4. Click **Create Site** or **Add Site**
5. Configure the new site:
   - **Name**: `OPNsense LAN` (or any descriptive name)
   - **Type**: Select **Local Only** (since OPNsense is on your local network)
   - **Description**: `Firewall Management Interface` (optional)
6. Click **Create** or **Save**

:::tip What is a Site?
In Pangolin, a "Site" is a logical grouping of resources (services). It helps organize your infrastructure. A "Local Only" site means the services are not running in containers managed by Pangolin, but exist elsewhere on your network.
:::

#### 2.2.2 Add OPNsense as a Resource

1. After creating the site. Click on the Resouces Tab in the left Sidebar. 
3. Click **Add Resource**
4. Configure the OPNsense resource:
  - **Name**: `OPNsense Dashboard` (or any descriptive name)
  - **Resource Type**: `HTTPS Resource` (should be selected by default)
  - **Subdomain**: `opnsense` (or what ever u configured as your alternative hostname during opnsense setup)
  - **Method/Protocol**: `https`
  - **IP/Hostname** `192.168.1.1` (OPNsense's internal/LAN IP)
  - **Port**: `443` (OPNsense web interface port)
5. Click **Save** or **Create**

#### 2.2.3 Verify OPNsense Access

1. Pangolin will automatically configure Traefik routing and request an SSL certificate
2. Wait 30-60 seconds for the certificate to be issued
3. Open a new browser tab and navigate to: `https://opnsense.yourdomain.com`
4. You should now see the OPNsense login page with a valid SSL certificate (issued by Let's Encrypt)
5. Log in with your OPNsense credentials

:::success OPNsense Access Configured
You now have secure access to OPNsense web interface via `https://opnsense.yourdomain.com`. This will be your primary method for managing firewall rules and network configuration. No manual Traefik configuration or service restarts were needed!
:::

### 2.3 Second Priority: Set Up Proxmox Web Access

Similar to OPNsense, we'll set up secure access to Proxmox via Pangolin's reverse proxy. This allows you to access Proxmox through a subdomain while maintaining security.

#### 2.3.1 Add Proxmox as a Resource

1. Click on the **Resources** tab in the left sidebar
2. Click **Add Resource**
3. Configure the Proxmox resource:
   - **Name**: `Proxmox VE` (or any descriptive name)
   - **Resource Type**: `HTTPS Resource` (should be selected by default)
   - **Subdomain**: `proxmox` (you can choose any subdomain you prefer)
   - **Site**: `OPNsense LAN` (this is the Site i configured in 2.1)
   - **Method/Protocol**: `https`
   - **IP/Hostname**: Your Proxmox host's **public IP** (e.g., `XXX.XXX.XXX.XXX`)
   - **Port**: `8006` (Proxmox web interface port)

:::warning Why Public IP Instead of LAN IP?
Unlike OPNsense which sits on your internal network (`192.168.1.1`), your Proxmox host is currently directly on the WAN with a public IP. We're routing through the public IP temporarily. This will be secured via firewall rules in the next sections to ensure only Pangolin can access the Proxmox web interface.
:::

5. Click **Save** or **Create**

#### 2.3.4 Verify Proxmox Access

1. Pangolin will automatically configure Traefik routing and request an SSL certificate
2. Wait 30-60 seconds for the certificate to be issued
3. Open a new browser tab and navigate to: `https://proxmox.yourdomain.com`
4. You should now see the Proxmox login page with a valid SSL certificate (issued by Let's Encrypt)
5. Log in with your Proxmox credentials (username and your password)

:::success Proxmox Access Configured
You now have secure access to Proxmox web interface via `https://proxmox.yourdomain.com` with automatic SSL certificate management. No manual Traefik configuration or service restarts were needed!
:::

### 2.4 Lock Down Proxmox Access (Critical Security Step)

Now that you're accessing Proxmox through Pangolin's reverse proxy, you need to restrict direct access to the Proxmox web interface on port 8006. We'll use multiple layers of security:

#### 2.4.1 Understanding the Setup

This guide will walk you through creating a secure firewall policy for a common server setup: a single server with two IP addresses, where one IP is for a public-facing reverse proxy and the other is for a backend application that should not be accessible from the internet.

**The Goal:**

- Allow public web traffic (HTTP/HTTPS) to the Proxy IP
- Allow the Proxy IP to communicate with the Backend IP
- Block the public from directly accessing the Backend IP
- Block all other unwanted traffic, including all IPv6 traffic (for simplicity and security)

#### 2.4.2 Before You Start: Gather Your Information

You will need the following details. Write them down to avoid confusion:

- **`[YOUR_PROXY_IPV4]`**: The public IPv4 address your users will connect to (e.g., `65.109.38.249` the secondary IP Address used for OPNsense & Cloudflare configuration)
- **`[YOUR_BACKEND_IPV4]`**: The private IPv4 address your backend application uses (e.g., `65.109.38.216` the "main" IP Address that is connected to the Proxmox Host)
- **`[YOUR_APP_PORT]`**: The specific port your backend application listens on (e.g., `8006` for Proxmox)

:::tip Finding Your IPs
You can find these IPs in:
- **Hetzner Cloud Console** → Your server → **Networking** tab (will show all assigned IPs)
- Or run `ip addr show` on your Proxmox host to see all network interfaces
:::

#### 2.4.3 The Strategy: Deny by Default

A secure firewall works like a club with a strict bouncer. The default policy is "nobody gets in." We will then create specific, ordered rules to allow only the guests we want. The firewall checks rules from top to bottom and stops at the first match.

#### 2.4.4 Step-by-Step Firewall Configuration

Create the following rules in your Hetzner firewall control panel in this exact order:

**Rule #1: Block All IPv6 Traffic**

Purpose: This is our first and most important security step. If you don't use IPv6, you must explicitly block it. This single rule prevents your backend from being exposed via its IPv6 address.

| Field | Value | Notes |
|-------|-------|-------|
| Name | `BLOCK ALL IPv6` | A clear, descriptive name |
| Version Protokoll | `ipv6` | This rule applies only to IPv6 |
| Quell-IP (Source IP) | `::/0` (leave blank) | This is the IPv6 equivalent of "any address" |
| Ziel-IP (Destination IP) | (leave blank) | Applies to all destinations on this server |
| Aktion (Action) | `discard` | Silently drops the traffic |

**Rule #2: Allow Public Access to the Reverse Proxy**

Purpose: This is the main entry point for your users. It allows incoming web traffic from anyone on the internet, but only to your proxy's IP address and only on the standard web ports.

| Field | Value | Notes |
|-------|-------|-------|
| Name | `Allow Public to Proxy` | |
| Version Protokoll | `ipv4` | |
| Quell-IP (Source IP) | `0.0.0.0/0` | "Any" IPv4 address on the internet |
| Ziel-IP (Destination IP) | `[YOUR_PROXY_IPV4]/32` | Use your proxy's IP here |
| Ziel-Port (Destination Port) | `80, 443` | **Crucial!** Restricts access to HTTP and HTTPS ports only |
| Aktion (Action) | `accept` | |

**Rule #3: Allow Proxy to Communicate with Backend**

Purpose: This critical rule allows your reverse proxy to forward traffic to your backend application. Without this, your service will not work.

| Field | Value | Notes |
|-------|-------|-------|
| Name | `Allow Proxy to Backend` | |
| Version Protokoll | `ipv4` | |
| Quell-IP (Source IP) | `[YOUR_PROXY_IPV4]/32` | Use your proxy's IP here |
| Ziel-IP (Destination IP) | `[YOUR_BACKEND_IPV4]/32` | Use your backend's IP here |
| Ziel-Port (Destination Port) | `[YOUR_APP_PORT]` | **Crucial!** Use the specific port of your application (e.g., `8006` for Proxmox) |
| Aktion (Action) | `accept` | |

**Rule #4 (Optional): Allow Server Self-Communication**

Purpose: Sometimes, services running on the server need to communicate with each other using their network addresses. This rule allows that.

| Field | Value | Notes |
|-------|-------|-------|
| Name | `Allow self-communication` | |
| Version Protokoll | `ipv4` | |
| Quell-IP (Source IP) | `[YOUR_BACKEND_IPV4]/32` | You can add your proxy IP here as well if needed |
| Ziel-IP (Destination IP) | `[YOUR_BACKEND_IPV4]/32` | |
| Aktion (Action) | `accept` | |

**Rule #5: Deny All Other IPv4 Traffic**

Purpose: This is your safety net. After explicitly allowing the traffic we want, this final rule blocks everything else. Any IPv4 packet that did not match one of the accept rules above will be stopped here.

| Field | Value | Notes |
|-------|-------|-------|
| Name | `Deny all else (v4)` | |
| Version Protokoll | `ipv4` | |
| Quell-IP (Source IP) | `0.0.0.0/0` | "Any" IPv4 address |
| Ziel-IP (Destination IP) | (leave blank) | Applies to all destinations on this server |
| Aktion (Action) | `discard` | |

#### 2.4.5 Final Review

Once configured, your firewall policy should look like this. **The order is critical** for it to function correctly:

| # | Name | Protocol | Source | Destination | Dest. Port | Action |
|---|------|----------|--------|-------------|------------|--------|
| 1 | `BLOCK ALL IPv6` | ipv6 | `::/0` | | all | discard |
| 2 | `Allow Public to Proxy` | ipv4 | `0.0.0.0/0` | `[YOUR_PROXY_IPV4]/32` | `80, 443` | accept |
| 3 | `Allow Proxy to Backend` | ipv4 | `[YOUR_PROXY_IPV4]/32` | `[YOUR_BACKEND_IPV4]/32` | `[YOUR_APP_PORT]` | accept |
| 4 | `Allow self-communication` | ipv4 | `[YOUR_BACKEND_IPV4]/32` | `[YOUR_BACKEND_IPV4]/32` | all | accept |
| 5 | `Deny all else (v4)` | ipv4 | `0.0.0.0/0` | | all | discard |

:::warning Rule Order Matters
The firewall evaluates rules from top to bottom and stops at the first match. Do not reorder these rules or the security policy will not work as intended.
:::

#### 2.4.6 Verify Security Configuration

Test that your security configuration is working:

1. **Test Pangolin Access** (should work):
   ```
   https://proxmox.yourdomain.com
   ```
   ✅ Should show Proxmox login page

2. **Test Direct IP Access** (should fail):
   ```
   https://YOUR_PUBLIC_IP:8006
   ```
   ❌ Should time out or be refused

3. **Check Firewall Logs** (optional):
   - Hetzner: Check firewall statistics in Hetzner Console
   - OPNsense: Navigate to **Firewall → Log Files → Live View**
   - Proxmox: Check logs with `tail -f /var/log/pve-firewall.log`

:::success Security Locked Down
Your Proxmox web interface is now:
- ✅ Accessible only through Pangolin's reverse proxy (`https://proxmox.yourdomain.com`)
- ✅ Protected by Let's Encrypt SSL certificate
- ✅ Blocked from direct internet access on port 8006
- ✅ Protected by multiple firewall layers
:::


### 2.6 Adding Additional Services to Pangolin

Now that critical infrastructure is secured, you can add other services following the same pattern using Pangolin's dashboard.

#### 2.6.1 General Service Addition Pattern

For any service you want to expose (e.g., AdGuard Home, Homer dashboard, Firefly III):

1. **Navigate to Sites** in Pangolin dashboard
2. Select an existing site or click **Create Site** to create a new one:
   - **Name**: Descriptive name for the service group (e.g., "Network Services", "Management Tools")
   - **Type**: **Local Only** (for services on your network)
3. **Add a Resource** to the site:
   - Click **Add Resource** in the Resources section
4. **Configure the resource**:
   - **Name**: Service name (e.g., "AdGuard Home", "Homer Dashboard")
   - **Subdomain**: Your chosen subdomain (e.g., `adguard`, `home`)
   - **Internal URL/Address**: Service's internal URL (e.g., `http://192.168.1.3:80`)
   - **Protocol**: HTTP or HTTPS (depending on the service)
   - **SSL Verification**: Disable if service uses self-signed certificate
5. **Save** the resource
6. **Wait 30-60 seconds** for SSL certificate issuance
7. **Access the service**: `https://yoursubdomain.yourdomain.com`

:::tip No Restarts Needed
When using Pangolin's dashboard to add services, Traefik automatically picks up the changes. No need to manually restart services or edit configuration files!
:::

#### 2.6.2 Service Configuration Examples

**Example 1: AdGuard Home** (HTTP service with built-in authentication)

- **Name**: `AdGuard Home`
- **Subdomain**: `adguard`
- **Internal URL**: `http://192.168.1.3:80`
- **Protocol**: HTTP
- **SSL Verification**: Enabled (not needed for HTTP)

Result: Access via `https://adguard.yourdomain.com`

**Example 2: Homer Dashboard** (HTTP service, public)

- **Name**: `Homer Dashboard`
- **Subdomain**: `home`
- **Internal URL**: `http://192.168.1.10:8080`
- **Protocol**: HTTP
- **SSL Verification**: Enabled

Result: Access via `https://home.yourdomain.com`

**Example 3: Service with HTTPS and Self-Signed Certificate**

- **Name**: `Internal Service`
- **Subdomain**: `internal`
- **Internal URL**: `https://192.168.1.20:443`
- **Protocol**: HTTPS
- **SSL Verification**: **Disabled** (required for self-signed certs)

Result: Access via `https://internal.yourdomain.com`

:::info Adding Authentication
If a service doesn't have built-in authentication and you want to protect it:
1. Check if Pangolin offers authentication options in the resource configuration (may vary by version)
2. Alternatively, use manual Traefik middleware configuration for advanced authentication needs
3. Consider using Pangolin's built-in access control features if available
:::

### 2.7 Connecting Servers to Pangolin (Optional)

If you want to monitor and manage servers with Pangolin's agent system:

1. In Pangolin dashboard, navigate to **Servers** or **Agents**
2. Click **Add Server**
3. Copy the provided installation command:

```bash
curl -fsSL https://get.digpangolin.com/agent.sh | bash -s -- \
  --url=https://pangolin.yourdomain.com \
  --token=<your-unique-token>
```

4. SSH into the target server (Proxmox host, LXC containers, VMs)
5. Run the installation command
6. Verify the connection in Pangolin dashboard

:::info Agent vs Service Exposure
These are two different concepts:
- **Agent**: Allows Pangolin to monitor and manage a server (CPU, memory, containers, etc.)
- **Service Exposure**: Makes a web interface accessible via subdomain through Traefik
- You can use both, either, or neither depending on your needs
:::

## 3. Security Best Practices

### 3.1 Access Control

- **Strong Authentication**: Use strong, unique passwords (minimum 16 characters)
- **API Tokens**: Regularly rotate API tokens and limit their scope
- **Session Management**: Configure appropriate session timeouts in Pangolin

### 3.2 Network Security

- **Minimize Exposure**: Only ports 80 and 443 should be accessible from WAN
- **Internal Access**: All other services should only be accessible through Pangolin or via VPN
- **Monitoring**: Regularly review access logs in Pangolin and OPNsense

### 3.3 SSL/TLS Configuration

- Pangolin's Traefik automatically handles SSL certificates via Let's Encrypt
- Certificates auto-renew before expiration
- Monitor certificate status in Pangolin dashboard

### 3.4 Regular Updates

Keep Pangolin and its dependencies up to date:

```bash
# Update Pangolin (run inside Pangolin container)
docker compose pull
docker compose up -d

# Update system packages
apt update && apt upgrade -y
```