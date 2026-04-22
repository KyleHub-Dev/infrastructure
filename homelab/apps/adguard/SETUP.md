# AdGuard Home Setup with NEWT Tunnel & Pangolin

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     PANGOLIN VPS (HA)                           │
│                  (Reverse Proxy + Auth)                         │
│                                                                 │
│  adguard.my-domain.com → Cloudflare → Pangolin → NEWT tunnel  │
└─────────────────────────────────────────────────────────────────┘
                              │ WireGuard
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              DEDICATED ROOT SERVER (AdGuard)                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Docker Compose                                           │  │
│  │  ├─ newt (WireGuard tunnel to Pangolin)                │  │
│  │  └─ adguard (DNS service)                              │  │
│  │      ├─ Port 853:853 (DoT) - PUBLIC                    │  │
│  │      ├─ Port 53:53 (DNS) - Internal only               │  │
│  │      └─ Port 3000:3000 (Dashboard) - Via NEWT tunnel   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  dns.my-domain.com:853 → Root server IP (public DNS)           │
└─────────────────────────────────────────────────────────────────┘
```

## Deployment Steps

### 1. Prepare Environment

```bash
cd /home/kyle/infrastructure/homelab/apps/adguard
cp .env.example .env
```

### 2. Fill in .env with Your Values

```bash
nano .env
```

Required variables:
- `PANGOLIN_ENDPOINT`: Your Pangolin VPS endpoint (IP:port or domain)
- `NEWT_ID`: NEWT tunnel ID from Pangolin
- `NEWT_SECRET`: NEWT tunnel secret from Pangolin

Get these from your Pangolin setup/documentation.

### 3. Start the Stack

```bash
podman-compose up -d
```

### 4. Initial AdGuard Setup

1. Access the web UI initially (before Zitadel lockdown):
   - Local: `http://localhost:3000`
   - Or wait for Pangolin to route it

2. Complete the initial setup:
   - Set admin username/password
   - Configure upstream DNS servers
   - Enable DoT on port 853

### 5. Configure Pangolin Resource

In your Pangolin configuration, add a resource for the AdGuard dashboard:

```yaml
# Pseudo-config - adjust to your Pangolin setup
resources:
  adguard:
    # External domain
    domain: adguard.my-domain.com
    # Route through NEWT tunnel to AdGuard dashboard
    upstream: http://newt:3000
    # Enable OIDC protection via Zitadel
    auth:
      provider: oidc
      issuer: https://zitadel.my-domain.com
      client_id: ${ADGUARD_OIDC_CLIENT_ID}
      client_secret: ${ADGUARD_OIDC_CLIENT_SECRET}
      scopes:
        - openid
        - profile
        - email
```

### 6. Configure Cloudflare DNS

**For DNS (public, no proxy):**
```
dns.my-domain.com  A  [DNS only]  →  <root-server-public-ip>
```

**For Dashboard (proxied through Cloudflare, then Pangolin):**
```
adguard.my-domain.com  A  [Cloudflare proxy ON]  →  <pangolin-vps-endpoint>
```

### 7. Test DNS Resolution

Test DoT (DNS over TLS) with your phone or client:

```bash
# From local machine
dig @dns.my-domain.com +tls example.com

# Or on Android: Settings → Network → Private DNS → dns.my-domain.com
```

## AdGuard Configuration (Post-Setup)

### Enable DoT (DNS over TLS)

1. Go to Settings → Encryption settings
2. Enable "Serve plain DNS"
3. Certificates: Use Let's Encrypt or self-signed
   - For public DoT, Let's Encrypt is recommended
   - You can use Pangolin's certs if available

### DNS Rewrites (Local Domain Mapping)

1. Filters → DNS rewrites
2. Add entries like:
   ```
   *.local → 192.168.1.100 (your reverse proxy IP)
   dashboard.lab → 192.168.1.50
   ```

### Upstream DNS Servers

1. Settings → Upstream DNS servers
2. Recommended fastest setup:
   ```
   1.1.1.1 (Cloudflare)
   8.8.8.8 (Google)
   9.9.9.9 (Quad9)
   ```

## Port Mapping Summary

| Port | Protocol | Access | Purpose |
|------|----------|--------|---------|
| **53** | TCP/UDP | Internal only | Regular DNS |
| **853** | TCP/UDP | **PUBLIC** | DNS over TLS (DoT) |
| **3000** | TCP | Via NEWT tunnel | Web dashboard (Pangolin-protected) |

## Monitoring & Logs

```bash
# View logs
podman-compose logs -f adguard

# Check container health
podman-compose ps

# Access AdGuard stats
curl http://localhost:3000/api/stats
```

## Troubleshooting

**Dashboard not accessible through Pangolin:**
- Verify NEWT tunnel is established: `podman-compose logs newt`
- Check Pangolin routing configuration
- Ensure Zitadel OIDC is configured correctly

**DNS queries not resolving:**
- Verify port 853 is publicly exposed: `netstat -tuln | grep 853`
- Test locally first: `dig @localhost example.com`
- Check upstream DNS servers in AdGuard settings

**NEWT tunnel failing:**
- Verify `.env` credentials are correct
- Check network connectivity: `ping <PANGOLIN_ENDPOINT>`
- Review NEWT logs: `podman-compose logs newt`

## Security Notes

✅ **Gateway IP hidden** - Pangolin behind Cloudflare
✅ **DNS queries private** - Direct connection, no Cloudflare inspection
✅ **Dashboard authenticated** - OIDC via Zitadel (via Pangolin)
✅ **DoT encryption** - TLS protects DNS queries end-to-end
✅ **WireGuard tunnel** - NEWT provides encrypted tunnel from VPS to root server

---

**Next:** Configure Zitadel OIDC client for AdGuard dashboard access.
