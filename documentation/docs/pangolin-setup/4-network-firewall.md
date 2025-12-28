---
title: Network & Firewall Configuration
sidebar_position: 5
tags:
  - OPNsense
  - Firewall Rules
  - Port Forwarding
  - Network Security
---


## 1. Network and Firewall Configuration

### 1.1 Required Ports

Pangolin requires only the following ports to be accessible from the internet:

- **Port 80 (HTTP)**: Required for Let's Encrypt certificate validation and HTTP to HTTPS redirect (can be disabled with Cloudflare proxy)
- **Port 443 (HTTPS)**: Main access point for Pangolin dashboard and all services

:::info Cloudflare Proxy Impact
If you enabled Cloudflare proxy (orange cloud) in Section 4.1, your firewall configuration will be different. Traffic will come from Cloudflare's IP ranges instead of directly from users. Additionally, port 80 can be disabled as it's not needed with DNS-01 challenge.
:::

All other services should be accessed **through Pangolin** and should not be directly exposed to the internet.

### 1.2 OPNsense Firewall Rules

#### 1.2.1 WAN Rules (Internet Access to Pangolin)

Configure OPNsense to allow only necessary traffic from the internet:

1. Log in to OPNsense web interface
2. Navigate to **Firewall > Rules > WAN**
3. **Remove or disable any existing "allow all" rules** to follow the principle of least privilege

:::tip Choose Your Configuration
Follow **either** Option A (for DNS only/gray cloud) **or** Option B (for Cloudflare proxy/orange cloud) based on your choice in Section 4.1.
:::

**Option A: DNS Only (Gray Cloud) Configuration**

If you chose DNS only (gray cloud) in Section 4.1, create these rules:

**Create Rule 1: Allow HTTP (Port 80)**
- Click **Add** (arrow pointing down for top of list)
- **Action**: Pass
- **Interface**: WAN
- **Direction**: in
- **TCP/IP Version**: IPv4
- **Protocol**: TCP
- **Source**: any
- **Destination**: WAN address
- **Destination port range**: HTTP (80)
- **Description**: Allow HTTP for Let's Encrypt validation
- **Category**: Pangolin
- Click **Save**

**Create Rule 2: Allow HTTPS (Port 443)**
- Click **Add**
- **Action**: Pass
- **Interface**: WAN
- **Direction**: in
- **TCP/IP Version**: IPv4
- **Protocol**: TCP
- **Source**: any
- **Destination**: WAN address
- **Destination port range**: HTTPS (443)
- **Description**: Allow HTTPS for Pangolin Dashboard
- **Category**: Pangolin
- Click **Save**

4. Click **Apply Changes**

**Option B: Cloudflare Proxy (Orange Cloud) Configuration**

If you enabled Cloudflare proxy (orange cloud) in Section 4.1, follow these steps for enhanced security:

**Step 1: Create Cloudflare IP Alias**

First, create an alias for Cloudflare's IP ranges:

1. Navigate to **Firewall > Aliases**
2. Click **Add**
3. Configure the alias:
   - **Name**: `Cloudflare_IPs`
   - **Type**: Network(s)
   - **Description**: Cloudflare proxy IP ranges
   - **Content**: Add the following IP ranges (one per line):

```
173.245.48.0/20
103.21.244.0/22
103.22.200.0/22
103.31.4.0/22
141.101.64.0/18
108.162.192.0/18
190.93.240.0/20
188.114.96.0/20
197.234.240.0/22
198.41.128.0/17
162.158.0.0/15
104.16.0.0/13
104.24.0.0/14
172.64.0.0/13
131.0.72.0/22
```

<details>
  <summary>Click to expand IPv6 ranges (optional)</summary>

If your server supports IPv6 and you enabled it during Pangolin installation, also add these IPv6 ranges:

```
2400:cb00::/32
2606:4700::/32
2803:f800::/32
2405:b500::/32
2405:8100::/32
2a06:98c0::/29
2c0f:f248::/32
```

**Note:** You can add these to the same `Cloudflare_IPs` alias, or create a separate alias named `Cloudflare_IPs_v6` if you prefer to manage IPv4 and IPv6 separately.

</details>

4. Click **Save**
5. Click **Apply**

:::warning IP Range Updates
Cloudflare may update their IP ranges. Check [https://www.cloudflare.com/ips/](https://www.cloudflare.com/ips/) periodically and update your alias if needed. Subscribe to Cloudflare's change notifications for updates.
:::

**Step 2: Create Firewall Rules with Cloudflare Source (HTTPS Only)**

Since Cloudflare proxy uses DNS-01 challenge for certificates, port 80 is **not required** and can be omitted for enhanced security.

**Create Rule: Allow HTTPS from Cloudflare (Port 443)**
- Click **Add** (in Firewall > Rules > WAN)
- **Action**: Pass
- **Interface**: WAN
- **Direction**: in
- **TCP/IP Version**: IPv4
- **Protocol**: TCP
- **Source**: Select "Cloudflare_IPs" (the alias you created)
- **Destination**: WAN address
- **Destination port range**: HTTPS (443)
- **Description**: Allow HTTPS from Cloudflare for Pangolin Dashboard
- **Category**: Pangolin
- Click **Save**

:::info Port 80 Not Needed
Unlike the DNS only configuration, you do **not** need to create a rule for port 80 when using Cloudflare proxy. Pangolin uses DNS-01 challenge for wildcard certificates, which doesn't require HTTP access.
:::

**Step 3: Block Direct Access (Optional but Recommended)**

For maximum security, create a rule to explicitly block any non-Cloudflare traffic to port 443:

**Create Block Rule:**
- Click **Add**
- **Action**: Block
- **Interface**: WAN
- **Direction**: in
- **TCP/IP Version**: IPv4
- **Protocol**: TCP
- **Source**: any
- **Source / Invert**: Check this box (to invert, meaning "not from Cloudflare_IPs")
- **Destination**: WAN address
- **Destination port range**: HTTPS (443)
- **Description**: Block non-Cloudflare traffic to HTTPS
- **Category**: Pangolin
- Click **Save**

:::caution Testing Required
You'll test access in Section 5.4 after completing the port forward configuration. Only implement the block rule after confirming everything works correctly.
:::

4. Click **Apply Changes**

:::caution Security Note
**For DNS Only (Gray Cloud):** These rules allow traffic from anywhere on the internet. Pangolin's authentication and Traefik's security features will protect your services. However, consider implementing additional security measures such as:
- Cloudflare Access or VPN for additional authentication layers
- GeoIP blocking to restrict access to specific countries
- Rate limiting in Pangolin/Traefik configuration

**For Cloudflare Proxy (Orange Cloud):** By restricting traffic to Cloudflare IPs only, you ensure all traffic passes through Cloudflare's security and DDoS protection. Direct access attempts will be blocked. Port 80 is not exposed, reducing attack surface.
:::

#### 1.2.2 Port Forward Configuration

Create port forwards to direct traffic to your Pangolin LXC container:

1. Navigate to **Firewall > NAT > Port Forward**
2. Click **Add**

:::tip Port Forward Configuration Based on Setup
The port forwards you need depend on your DNS configuration choice in Section 4.1.
:::

**For DNS Only (Gray Cloud) - Create Both Port Forwards:**

**Port Forward 1: HTTP (80)**
- **Interface**: WAN
- **Protocol**: TCP
- **Destination**: WAN address
- **Destination port range**: HTTP to HTTP (80 to 80)
- **Redirect target IP**: `192.168.1.50` (your Pangolin container IP)
- **Redirect target port**: HTTP (80)
- **Description**: Port forward HTTP to Pangolin
- **Category**: Pangolin
- Click **Save**

**Port Forward 2: HTTPS (443)**
- **Interface**: WAN
- **Protocol**: TCP
- **Destination**: WAN address
- **Destination port range**: HTTPS to HTTPS (443 to 443)
- **Redirect target IP**: `192.168.1.50` (your Pangolin container IP)
- **Redirect target port**: HTTPS (443)
- **Description**: Port forward HTTPS to Pangolin
- **Category**: Pangolin
- Click **Save**

**For Cloudflare Proxy (Orange Cloud) - Create HTTPS Port Forward Only:**

**Port Forward: HTTPS (443)**
- **Interface**: WAN
- **Protocol**: TCP
- **Destination**: WAN address
- **Destination port range**: HTTPS to HTTPS (443 to 443)
- **Redirect target IP**: `192.168.1.50` (your Pangolin container IP)
- **Redirect target port**: HTTPS (443)
- **Description**: Port forward HTTPS to Pangolin
- **Category**: Pangolin
- Click **Save**

:::info Port 80 Port Forward Not Needed for Cloudflare Proxy
When using Cloudflare proxy (orange cloud), you do **not** need to create a port forward for port 80. Only port 443 is required.
:::

3. Click **Apply Changes**

:::tip
The port forward rules will automatically create corresponding firewall rules. You can verify this by checking **Firewall > Rules > WAN** where you should see auto-generated rules for your port forwards.
:::

#### 1.2.3 LAN Rules (Internal Access)

Allow your internal network to access Pangolin:

1. Navigate to **Firewall > Rules > LAN**
2. Click **Add**

**LAN Rule: Allow Access to Pangolin**
- **Action**: Pass
- **Interface**: LAN
- **Direction**: in
- **TCP/IP Version**: IPv4
- **Protocol**: TCP
- **Source**: LAN net
- **Destination**: Single host or Network - `192.168.1.50`
- **Destination port range**: From HTTP to HTTPS (80 to 443)
- **Description**: Allow LAN access to Pangolin
- **Category**: Pangolin
- Click **Save**

3. Click **Apply Changes**

### 1.3 Verify Firewall Configuration and Cloudflare Proxy

Now that the firewall is configured, test that everything is working correctly:

**For DNS Only (Gray Cloud):**
```bash
# From an external network (not your LAN), test HTTPS access
curl -I https://pangolin.yourdomain.com

# Should return HTTP/2 200 or similar response

# Test that other ports are blocked
nc -zv your-server-ip 8080
# Should timeout or show "Connection refused"
```

**For Cloudflare Proxy (Orange Cloud):**
```bash
# From an external network, test HTTPS access through Cloudflare
curl -I https://pangolin.yourdomain.com
# Should return HTTP/2 200 with Cloudflare headers (cf-ray, cf-cache-status, etc.)

# Verify direct IP access is blocked (if you implemented the block rule)
curl -I https://your-server-ip
# Should timeout or be refused

# Verify port 80 is not accessible
curl -I http://your-server-ip
# Should timeout or be refused

# Test from LAN (should work regardless of WAN configuration)
curl -I https://pangolin.yourdomain.com
# Should return HTTP/2 200
```

:::tip Verification for Cloudflare Proxy
When using Cloudflare proxy, you should see Cloudflare-specific headers in the response:
- `CF-Ray`: Unique request identifier
- `CF-Cache-Status`: Cache status
- `Server`: cloudflare

If you see these headers, your Cloudflare proxy is working correctly.
:::

:::success Firewall Configuration Complete
At this point, your network and firewall are fully configured:
1. ✅ OPNsense firewall rules allow appropriate traffic
2. ✅ Port forwards direct traffic to Pangolin container
3. ✅ LAN rules allow internal access
4. ✅ (If using Cloudflare proxy) Traffic is routed through Cloudflare with proper IP forwarding

**Next Step:** Continue to Section 6 to access Pangolin dashboard and complete initial setup.
:::