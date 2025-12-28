---
title: Troubleshooting
sidebar_position: 7
tags:
  - Troubleshooting
  - SSL Certificates
  - Error 521
  - DNS Issues
  - Debugging
---

## 1. Troubleshooting

### 1.1 Cannot Access Pangolin Dashboard

**Check DNS Resolution:**
```bash
# Verify DNS is pointing to your server
dig pangolin.yourdomain.com +short
# Should return your server's public IP
```

**Check Port Forwarding:**
- Verify OPNsense port forwards are active
- Check that WAN firewall rules allow ports 80 and 443
- Ensure Pangolin container is running: `docker compose ps`

**Check Traefik Logs:**
```bash
docker compose logs traefik
```

### 1.2 SSL Certificate Issues

This section covers issues related to Let's Encrypt SSL certificate generation, which is critical for Pangolin to work properly.

#### 1.2.1 Empty or Missing Traefik Logs

**Symptom:** Running `docker compose logs traefik` shows no output or very little output.

**Diagnosis:**

```bash
# Inside Pangolin container
cd ~

# 1. Check if containers are running
docker compose ps
# Traefik should show "Up" status, not "Exited"

# 2. Validate docker-compose configuration
docker compose config
# This will show syntax errors if any exist

# 3. Check container details
docker ps -a | grep traefik

# 4. Check for port conflicts
ss -tlnp | grep :443
# Should only show docker-proxy, nothing else
```

**Common Causes:**
- YAML syntax errors in `docker-compose.override.yml`
- Port 443 already in use by another service
- Missing or incorrect environment variables

**Solutions:**

```bash
# Remove override file temporarily to test
cd ~
cp docker-compose.override.yml docker-compose.override.yml.backup
rm docker-compose.override.yml
docker compose down
docker compose up -d
docker compose logs -f traefik

# If Traefik starts successfully, the issue is in the override file
# Recreate it carefully with correct indentation (2 spaces, not tabs)
```

#### 1.2.2 Error 521 (Web Server is Down) with Cloudflare Proxy

**Symptom:** Cloudflare shows "Error 521: Web server is down" when accessing your domain.

**What This Means:**
- Cloudflare can reach your server (firewall rules are working) ✅
- But Traefik is not responding with valid SSL certificates ❌
- Cloudflare's Full (Strict) mode requires valid origin certificates

**Diagnosis:**

```bash
# Inside Pangolin container
cd ~

# 1. Check if DNS-01 is configured
cat config/traefik/traefik_config.yml | grep -A 5 "certificatesResolvers"
# Should show "dnsChallenge", NOT "httpChallenge"

# 2. Check if environment variables are set
cat .env | grep CF_
# Should show CF_API_EMAIL and CF_DNS_API_TOKEN

# 3. Check Traefik logs for certificate errors
docker compose logs traefik | grep -i "certificate\|acme\|error"

# 4. Look for specific error messages
docker compose logs traefik | tail -50
```

**Common Error Messages and Solutions:**

**Error: "unable to generate a certificate... httpChallenge"**
```bash
# This means Traefik is still using HTTP-01 challenge (wrong for Cloudflare proxy)
# Solution: Edit config/traefik/traefik_config.yml and change httpChallenge to dnsChallenge
nano config/traefik/traefik_config.yml
# See Section 4.3.3 for correct configuration
```

**Error: "Invalid response from https://... /.well-known/acme-challenge/"**
```bash
# This confirms HTTP-01 challenge is being used (won't work with Cloudflare proxy)
# Follow Section 4.3.3 to switch to DNS-01 challenge
```

**Error: "error: 403 :: urn:ietf:params:acme:error:unauthorized"**
```bash
# Either wrong Cloudflare API token or HTTP-01 challenge being used
# 1. Verify API token is correct in .env file
# 2. Verify dnsChallenge is configured in traefik_config.yml
# 3. Delete old certificates and restart:
rm -f config/letsencrypt/acme.json
docker compose down
docker compose up -d
```

**Error: "Could not obtain certificates... cloudflare: API error"**
```bash
# Cloudflare API credentials are wrong or expired
# 1. Create new API token in Cloudflare dashboard (Section 4.3.3 Step 1)
# 2. Update .env file with new token
# 3. Restart services:
docker compose down
docker compose up -d
```

#### 1.2.3 Cloudflare Settings Verification

**Verify Cloudflare Configuration:**

1. **SSL/TLS Mode** (Critical)
   - Go to Cloudflare Dashboard > SSL/TLS > Overview
   - Must be set to **Full (Strict)**
   - Pangolin will NOT work with "Full", "Flexible", or "Off"

2. **Proxy Status**
   - Go to Cloudflare Dashboard > DNS > Records
   - Orange cloud icon must be enabled (proxied)
   - Both `@` and `*` records should be proxied

3. **DNS Resolution**
   ```bash
   # From your local machine, check DNS
   dig pangolin.yourdomain.com +short
   # Should return Cloudflare IPs (like 104.21.x.x or 172.67.x.x)
   # NOT your server's direct IP
   ```

#### 1.2.4 Force Certificate Regeneration

If certificates are stuck or invalid:

```bash
# Inside Pangolin container
cd ~

# 1. Stop services
docker compose down

# 2. Delete old certificate storage
rm -f config/letsencrypt/acme.json

# 3. Verify configuration is correct
cat config/traefik/traefik_config.yml | grep -A 5 "dnsChallenge"
# Should show cloudflare provider and resolvers

cat .env | grep CF_
# Should show your Cloudflare email and API token

# 4. Restart and watch logs
docker compose up -d
docker compose logs -f traefik
# Watch for "Trying to challenge with DNS-01" and "Certificate obtained"
```

#### 1.2.5 DNS Only (Gray Cloud) Certificate Issues

**For DNS Only Setup:**

**Verify HTTP Challenge is Accessible:**
```bash
# From external network (not your LAN)
curl -I http://pangolin.yourdomain.com/.well-known/acme-challenge/test
# Should reach your server (404 is expected, connection refused is NOT)
```

**Check Traefik Certificate Resolver:**
```bash
# Inside Pangolin container
docker compose logs traefik | grep -i "certificate"
```

**Common Issues:**
- Port 80 not accessible from internet (required for HTTP-01 challenge)
- DNS not pointing to correct IP (should be your server's direct IP, not Cloudflare)
- OPNsense port forward for port 80 not configured
- Rate limiting from Let's Encrypt (limit is 5 certificates per domain per week)

#### 1.2.6 Certificate Generation Timeline

Understanding the timeline helps avoid panic:

- **0-30 seconds**: Traefik starts, loads configuration
- **30-60 seconds**: Traefik initiates ACME challenge
- **1-2 minutes**: DNS propagation for DNS-01 challenge (Cloudflare proxy)
- **2-3 minutes**: Let's Encrypt validates challenge
- **3-5 minutes**: Certificate obtained and activated

:::tip Be Patient
Certificate generation can take up to **5 minutes** on first run. Don't restart services unless you see actual errors in the logs.
:::

### 1.3 Services Not Accessible Through Pangolin

**Verify Service Configuration:**
- Check service is running and accessible from Pangolin container
- Verify internal IP addresses and ports are correct
- Test connectivity: `curl http://192.168.1.x:port` from Pangolin container

**Check Traefik Routing:**
```bash
# View Traefik dashboard (if enabled)
# Or check logs for routing errors
docker compose logs traefik | grep -i error
```

### 1.4 Agent Connection Issues

If servers can't connect to Pangolin:

**Check Agent URL:**
- Ensure using `https://pangolin.yourdomain.com` (not IP address)
- Verify DNS resolution from target server

**Check Firewall:**
- Ensure LAN firewall rules allow traffic to Pangolin
- Verify no firewall on target server blocking outbound HTTPS

**Check Agent Logs:**
```bash
# On target server
journalctl -u pangolin-agent -f
```