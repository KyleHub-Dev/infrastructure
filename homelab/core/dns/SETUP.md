# DNS Stack — Unbound + AdGuard Home + Lego + Newt

A self-hosted private DNS resolver for the homelab. Replaces the older
`apps/adguard/` stack with a recursive (no third-party upstreams)
DNSSEC-validating resolver behind AdGuard Home for filtering and
DoT/DoH endpoints.

## Architecture

```
                           Internet
                              │
             ┌────────────────┼─────────────────┐
             │                │                 │
   Mobile (Android Private    LAN router        Pangolin/Traefik
   DNS: dns.kylehub.dev)     (192.168.x.y:53)   (dashboard only)
             │                │                 │
             ▼                ▼                 ▼
   ┌──────────────────────────────────────────────────────┐
   │       Root Server (homelab/core/dns stack)           │
   │                                                      │
   │   host:853  (DoT, public)                            │
   │   host:443  (DoH, public)                            │
   │   ${LAN_IP}:53  (plain DNS, LAN-only)                │
   │   host:3000 ── NEWT tunnel ── Pangolin               │
   │                      │                               │
   │   ┌──────────────────┴────────────────┐              │
   │   │ adguard (filter + DoT/DoH server) │              │
   │   │   upstream → unbound:53            │              │
   │   └──────────────┬─────────────────────┘              │
   │                  │ dns-net                            │
   │   ┌──────────────▼─────────────────┐                 │
   │   │ unbound (recursive + DNSSEC)   │                 │
   │   │   talks to root DNS directly    │                 │
   │   └────────────────────────────────┘                 │
   │                                                      │
   │   ┌────────────────────────────────┐                 │
   │   │ lego (Cloudflare DNS-01 ACME)  │                 │
   │   │   renews dns.kylehub.dev cert  │                 │
   │   │   → restarts dns-adguard       │                 │
   │   └────────────────────────────────┘                 │
   │                                                      │
   │   ┌────────────────────────────────┐                 │
   │   │ newt (tunnel for dashboard)    │                 │
   │   └────────────────────────────────┘                 │
   └──────────────────────────────────────────────────────┘
```

## Prerequisites

Before bringing the stack up:

1. **Cloudflare DNS records** (in the `kylehub.dev` zone):

   | Record                | Type | Value                            | Proxy   |
   |-----------------------|------|----------------------------------|---------|
   | `dns.kylehub.dev`     | A    | `<this server's public IPv4>`    | **OFF** |
   | `dns.kylehub.dev`     | AAAA | `<this server's public IPv6>`    | **OFF** |
   | `adguard.kylehub.dev` | A    | `<gateway-vps Pangolin public IP>` | ON    |

   `dns.kylehub.dev` MUST be unproxied — Cloudflare cannot proxy
   port 853 (DoT). The dashboard hostname goes through Pangolin so it
   stays proxied as usual.

2. **Cloudflare API token** with `Zone:DNS:Edit` on the `kylehub.dev`
   zone. The same token gateway-vps' Traefik uses (`CF_DNS_API_TOKEN`
   in `gateway-vps/.env`) is fine — it's read-only on everything else.

3. **Pangolin resource** for the dashboard. In Pangolin admin:
   - New resource → `adguard.kylehub.dev` → upstream `http://newt:3000`
   - Auth: OIDC via Zitadel, same pattern as the old `apps/adguard`
   - Generate a NEWT_ID + NEWT_SECRET pair for this stack

4. **Privileged ports on rootless Podman** (if applicable). Ports 53,
   443, 853 are below 1024. Pick one:

   - **Run rootful Podman** (simplest): `sudo podman-compose up -d`.
   - **Allow unprivileged ports** on the host:
     ```bash
     echo "net.ipv4.ip_unprivileged_port_start=53" | \
       sudo tee /etc/sysctl.d/99-dns-ports.conf
     sudo sysctl --system
     ```

5. **Find the host's LAN IP** for the `LAN_IP` env variable:
   ```bash
   ip -4 addr show | awk '/inet 192\.168/{print $2}' | cut -d/ -f1
   ```

## Deployment

### 1. Stop the old AdGuard stack

```bash
cd /home/kyle/KyleHub/infrastructure/homelab/apps/adguard
podman-compose down
```

(The old `adguard-conf` / `adguard-work` volumes stay intact in case
we need to roll back. They get cleaned up after the new stack is
verified — see "Cleanup" below.)

### 2. Configure environment

```bash
cd /home/kyle/KyleHub/infrastructure/homelab/core/dns
cp .env.example .env
nano .env
```

Required values:
- `PANGOLIN_ENDPOINT`, `NEWT_ID`, `NEWT_SECRET`  — from Pangolin
- `ACME_EMAIL`                                   — your address
- `CF_DNS_API_TOKEN`                             — Cloudflare token
- `LAN_IP`                                       — host LAN IPv4
- `CERT_DOMAIN`                                  — defaults to `dns.kylehub.dev`

### 3. Bring up the stack

```bash
podman-compose up -d
podman-compose ps
```

Expected: 4 containers running (`dns-unbound`, `dns-adguard`,
`dns-lego`, `dns-newt`). `dns-unbound` should report healthy within
~15s.

### 4. Watch lego issue the cert

```bash
podman-compose logs -f lego
```

You should see, within a minute or two:
```
[lego] No cert at /data/certificates/dns.kylehub.dev.crt, requesting...
[INFO] [dns.kylehub.dev] acme: Obtaining bundled SAN certificate...
[INFO] [dns.kylehub.dev] Server responded with a certificate.
[hook] cert for dns.kylehub.dev written to /certs/dns.kylehub.dev
[hook] dns-adguard restart triggered (HTTP 204)
```

Verify the cert ended up where AdGuard can see it:
```bash
podman exec dns-adguard ls -la /opt/adguardhome/conf/certs/dns.kylehub.dev/
# expect: cert.pem, key.pem (mode 644)
```

### 5. AdGuard Home initial setup

Open `https://adguard.kylehub.dev` (via Pangolin) — Zitadel SSO →
AdGuard setup wizard. (For the very first wizard step you may need to
hit `http://<server-lan-ip>:3000` directly until the upstream/cert is
configured; revert to Pangolin once the dashboard is set up.)

In the wizard:

1. **Admin web interface**: `0.0.0.0:3000` (default)
2. **DNS server**: `0.0.0.0:53`
3. **Admin user / password**: store in your password manager.

After the wizard finishes and you log in:

#### a. Upstream DNS → Unbound only

`Settings → DNS settings → Upstream DNS servers`:

```
unbound:53
```

That's it — no Cloudflare, Google, or Quad9 fallback. Adding fallbacks
re-introduces the third-party leak we are trying to avoid.

`Bootstrap DNS servers`: `1.1.1.1` and `8.8.8.8` are fine here. They
are used **only** to resolve the names of upstream DoT/DoH servers,
and since our upstream is the IP-addressable name `unbound`, this list
isn't used in practice.

Click "Test upstreams" — should return OK.

#### b. Encryption settings → DoT + DoH

`Settings → Encryption settings`:

| Field                                | Value                                                |
|--------------------------------------|------------------------------------------------------|
| Enable encryption                    | ✅                                                    |
| Server name                          | `dns.kylehub.dev`                                    |
| Redirect to HTTPS                    | ✅                                                    |
| HTTPS port                           | `443`                                                |
| TLS port (DoT)                       | `853`                                                |
| Certificates → Set a certificate path| ✅                                                    |
| Path to certificate file             | `/opt/adguardhome/conf/certs/dns.kylehub.dev/cert.pem` |
| Set a private key path               | ✅                                                    |
| Path to private key                  | `/opt/adguardhome/conf/certs/dns.kylehub.dev/key.pem`  |

Click "Save". AdGuard validates the cert chain and starts listening on
443/853.

#### c. Filters → blocklists

`Filters → DNS blocklists`. Recommended starter set:

- AdGuard DNS filter
- AdAway Default Blocklist
- OISD (Big or Small)

#### d. Optional: client identifiers

`Settings → Client settings → Persistent clients`:

For DoT-style clients you can set per-client rules using AdGuard's
"Client tag" mechanism — useful if you want different blocklists for
your phone vs. router. Not required for first deploy.

## Verification

### Recursive resolution (Unbound)
```bash
podman exec dns-unbound drill @127.0.0.1 -p 53 +dnssec example.com | grep -E "rcode|flags"
# Expect: rcode: NOERROR; flags include "ad" (DNSSEC validated)
```

### Internal chain (AdGuard → Unbound)
```bash
# Anywhere on the host
dig @${LAN_IP} example.com +short
# Expect: a normal IP address answer
```

### DoT on the public hostname
```bash
# From any machine outside the homelab
kdig -d @dns.kylehub.dev +tls example.com
# or
dig @dns.kylehub.dev +tls example.com
```

### DoH on the public hostname
```bash
curl -v -H 'accept: application/dns-message' \
  'https://dns.kylehub.dev/dns-query?dns=AAABAAABAAAAAAAAA3d3dwdleGFtcGxlA2NvbQAAAQAB' \
  -o /dev/null
# Expect: HTTP/2 200, content-type: application/dns-message
```

### Mobile end-to-end
Android → Settings → Network & Internet → Private DNS → Provider name
→ `dns.kylehub.dev` → Save. Then browse for a minute and check
AdGuard `Top clients` — your phone should appear.

### Cert renewal smoke test
```bash
podman exec dns-lego ls -la /data/certificates/
podman exec dns-lego openssl x509 -in /data/certificates/dns.kylehub.dev.crt \
  -noout -dates
# Expect notAfter > 60 days from now after a fresh issue.
```

### Dashboard via Pangolin
`https://adguard.kylehub.dev` → Zitadel → AdGuard UI loads cleanly,
TLS cert is the Pangolin/Traefik cert (not the dns.kylehub.dev one —
those are two different chains).

## Cleanup (after ~2 weeks of stable operation)

```bash
# Remove the old app stack
rm -rf /home/kyle/KyleHub/infrastructure/homelab/apps/adguard

# Remove the old volumes
podman volume rm adguard-work adguard-conf
```

## Troubleshooting

### `dns-lego` keeps failing with `dns: NS ns.example.com.: dns: lookup ...`

Cloudflare API token is missing or lacks `Zone:DNS:Edit`. Check
`podman-compose logs lego` for the exact error and re-issue the
token via Cloudflare → My Profile → API Tokens.

### `dns-adguard` won't start, port `${LAN_IP}:53` already in use

Most distros run `systemd-resolved` on 127.0.0.53 and sometimes also
on the LAN IP. Check with `sudo lsof -i :53` and disable the
conflicting service:
```bash
sudo systemctl disable --now systemd-resolved
sudo rm /etc/resolv.conf
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
```

### Mobile's "Private DNS" says "Couldn't connect"

1. `dns.kylehub.dev` Cloudflare proxy is ON — turn it OFF.
2. The cert hasn't been issued yet — `podman-compose logs lego`.
3. Your ISP blocks outbound 853 — try DoH on 443 instead, or use a
   non-residential connection.

### Cert renewed but AdGuard still serves the old one

The renew-hook didn't restart AdGuard. Check
`podman-compose logs lego` for the hook output. Manual fix:
```bash
podman restart dns-adguard
```

### Need to roll back to the old `apps/adguard` stack

The old volumes (`adguard-conf`, `adguard-work`) are untouched until
you run "Cleanup". To roll back:
```bash
cd homelab/core/dns && podman-compose down
cd homelab/apps/adguard && podman-compose up -d
```

## Caveats

- **Image choice — `mvance/unbound` vs `nlnetlabs/unbound`:** The plan
  originally specified the official NLnet Labs image. We use
  `mvance/unbound:latest` because its config layout (`/opt/unbound/etc/
  unbound/`) is the de-facto standard for compose-based homelab
  setups, has stable paths, and ships `drill` for the healthcheck.
  Switching is a one-line change later — `unbound.conf` is portable.

- **IPv6:** the compose binds v6 inside the bridge but the host's v6
  reachability is up to your ISP/server. Add an `AAAA` record for
  `dns.kylehub.dev` if the box has public v6 — cellular clients
  often arrive over v6 and will fall back to v4 if AAAA isn't present.

- **Backups:** the named volumes worth backing up are
  `dns-adguard-conf` (filter lists, clients, rewrites, admin user)
  and `dns-unbound-data` (DNSSEC trust anchor). `dns-lego-data`
  contains certs but they re-issue automatically on restart, so
  backup is optional.

- **Cert volume permissions:** lego writes mode 644 inside `/certs/`.
  AdGuard mounts it read-only. If you ever see "permission denied"
  reading the cert, exec into adguard and check ownership — it should
  not require root to read.

- **ISP blocking:** some German residential ISPs block outbound 53/853.
  Not relevant on the chosen separate-root-server topology, but called
  out for awareness if you ever move the stack home.

- **No remote routers in scope:** if you later need to point a remote
  router (e.g. parents' house) at this resolver, use DoT on 853, not
  plain 53. Plain 53 is bound to LAN only by design.
