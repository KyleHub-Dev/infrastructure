# DNS Stack - Unbound + AdGuard Home + Lego

A self-hosted private DNS resolver. Replaces the older `apps/adguard/`
stack with a recursive (no third-party upstreams) DNSSEC-validating
resolver behind AdGuard Home for filtering and DoT/DoH endpoints.

The Pangolin Newt for this zone lives in `homelab/core/_edge` and is
shared by all `core/*` stacks. Bring `_edge` up first (see
`_edge/README.md`).

## Architecture

```
                           Internet
                              |
             +----------------+-----------------+
             |                                  |
   Mobile (Android Private DNS:        Pangolin / Traefik
   dns.kylehub.dev, port 853)          (dashboard only)
             |                                  |
             v                                  v
   +-----------------------------------------------------+
   |        Hetzner dedicated server (this host)         |
   |                                                     |
   |   host:853  (DoT, public, IAP via DoT client-id)    |
   |   host:443  (DoH, public)                           |
   |   host:127.0.0.1:3000  (dashboard, debug only)      |
   |                                                     |
   |   +---------- dns-net ------------------------------+
   |   |                                                 |
   |   |  dns-adguard (filter + DoT/DoH server)          |
   |   |    upstream -> dns-unbound:53                   |
   |   |  also on homelab-core-edge for core-newt        |
   |   |                                                 |
   |   |  dns-unbound (recursive + DNSSEC)               |
   |   |    talks to root DNS directly                   |
   |   |                                                 |
   |   |  dns-lego (Cloudflare DNS-01 ACME)              |
   |   |    renews dns.kylehub.dev cert                  |
   |   |    -> restarts dns-adguard via podman socket    |
   |   +-------------------------------------------------+
   |                                                     |
   |   homelab-core-edge ----> core-newt (in core/_edge) |
   +-----------------------------------------------------+
```

Plain DNS (port 53) is intentionally NOT bound on this host: this is
a Hetzner dedicated server with no LAN behind it. Clients (your phone,
your family's phones) use DoT or DoH; family-device restriction is
enforced inside AdGuard via "Allowed clients" / DoT client identifiers,
not at the network layer.

## Prerequisites

Before bringing this stack up:

1. **Cloudflare DNS records** (in the `kylehub.dev` zone):

   | Record                | Type | Value                              | Proxy   |
   |-----------------------|------|------------------------------------|---------|
   | `dns.kylehub.dev`     | A    | this server's public IPv4          | **OFF** |
   | `dns.kylehub.dev`     | AAAA | this server's public IPv6 (if any) | **OFF** |
   | `adguard.kylehub.dev` | A    | gateway-vps Pangolin public IP     | ON      |

   `dns.kylehub.dev` MUST be unproxied - Cloudflare cannot proxy
   port 853 (DoT). The dashboard hostname goes through Pangolin so it
   stays proxied as usual.

2. **Cloudflare API token** with `Zone:DNS:Edit` on the `kylehub.dev`
   zone. The same token gateway-vps' Traefik uses
   (`CF_DNS_API_TOKEN` in `gateway-vps/.env`) is fine.

3. **`homelab/core/_edge` is up.** The shared external network
   `homelab-core-edge` must already exist, and `core-newt` must be
   connected to Pangolin. See `core/_edge/README.md`.

4. **Pangolin Resource** for the dashboard, under the `Homelab Core`
   Site (created by `_edge`):
   - New Resource -> `adguard.kylehub.dev` -> upstream
     `http://dns-adguard:3000`
   - Auth: Zitadel IAP (Phase-1 posture).
   - No per-stack NEWT_ID/SECRET to provision - the central
     `core-newt` already owns the Site.

5. **Rootless Podman host setup** (one-time, persistent). Two
   sysctl/systemd nudges so the rootless runtime can bind privileged
   ports and the renew-hook can reach the Podman API after the cert
   rotates:

   ```bash
   # 5a. Allow unprivileged user processes to bind ports >= 443.
   echo "net.ipv4.ip_unprivileged_port_start=443" | \
     sudo tee /etc/sysctl.d/99-rootless-ports.conf
   sudo sysctl --system

   # 5b. Enable the rootless Podman API socket. lego's renew-hook
   #     POSTs to it to restart dns-adguard with the fresh cert.
   systemctl --user enable --now podman.socket

   # 5c. Keep the user services alive across logout/reboot so the
   #     socket is still there when lego renews 60 days from now.
   sudo loginctl enable-linger "$USER"
   ```

   Verify the socket exists:
   ```bash
   ls -l "/run/user/$(id -u)/podman/podman.sock"
   ```

   Set `PODMAN_SOCKET` in `.env` to match your UID (default in
   `.env.example` is the typical `/run/user/1000/podman/podman.sock`).

   If you instead need to run rootful (privileged podman, system-wide
   socket at `/run/podman/podman.sock`): set `PODMAN_SOCKET` to that
   path and prepend `sudo` to the `podman-compose` calls below.

## Deployment

### 1. Stop the old AdGuard stack (if still running)

```bash
cd /home/kyle/infrastructure/homelab/apps/adguard
podman-compose down
```

(The old `adguard-conf` / `adguard-work` volumes stay intact in case
of rollback. Clean up after the new stack is verified - see
"Cleanup" below.)

### 2. Configure environment

```bash
cd /home/kyle/infrastructure/homelab/core/dns
cp .env.example .env
nano .env
```

Required values:
- `ACME_EMAIL`        - your address
- `CF_DNS_API_TOKEN`  - Cloudflare token
- `CERT_DOMAIN`       - defaults to `dns.kylehub.dev`

### 3. Bring up the stack

```bash
podman-compose up -d
podman-compose ps
```

Expected: 3 containers running (`dns-unbound`, `dns-adguard`,
`dns-lego`). `dns-unbound` should report healthy within ~15s.

### 4. Watch lego issue the cert

```bash
podman-compose logs -f dns-lego
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

Open `https://adguard.kylehub.dev` (via Pangolin) -> Zitadel SSO ->
AdGuard setup wizard. (For the very first wizard step you may need to
hit `http://127.0.0.1:3000` directly on the host until the upstream
and cert are configured; revert to Pangolin once the dashboard is
set up.)

In the wizard:

1. **Admin web interface**: `0.0.0.0:3000` (default).
2. **DNS server**: `0.0.0.0:53`.
3. **Admin user / password**: store in your password manager.

After the wizard finishes and you log in:

#### a. Upstream DNS -> Unbound only

`Settings -> DNS settings -> Upstream DNS servers`:

```
dns-unbound:53
```

That's it - no Cloudflare, Google, or Quad9 fallback. Adding
fallbacks re-introduces the third-party leak we are trying to avoid.

`Bootstrap DNS servers`: `1.1.1.1` and `8.8.8.8` are fine here. They
are used **only** to resolve the names of upstream DoT/DoH servers,
and since our upstream is the IP-addressable name `dns-unbound`, this
list isn't used in practice.

Click "Test upstreams" - should return OK.

#### b. Encryption settings -> DoT + DoH

`Settings -> Encryption settings`:

| Field                                | Value                                                  |
|--------------------------------------|--------------------------------------------------------|
| Enable encryption                    | yes                                                    |
| Server name                          | `dns.kylehub.dev`                                      |
| Redirect to HTTPS                    | yes                                                    |
| HTTPS port                           | `443`                                                  |
| TLS port (DoT)                       | `853`                                                  |
| Certificates -> Set certificate path | yes                                                    |
| Path to certificate file             | `/opt/adguardhome/conf/certs/dns.kylehub.dev/cert.pem` |
| Set a private key path               | yes                                                    |
| Path to private key                  | `/opt/adguardhome/conf/certs/dns.kylehub.dev/key.pem`  |

Click "Save". AdGuard validates the cert chain and starts listening
on 443/853.

#### c. Filters -> blocklists

`Filters -> DNS blocklists`. Recommended starter set:

- AdGuard DNS filter
- AdAway Default Blocklist
- OISD (Big or Small)

#### d. Family-device restriction (DoT client identifiers)

Because plain DNS (port 53) is not bound on this Hetzner host, the
only way clients reach AdGuard is via DoT (`853`) or DoH (`443`).
Restrict to your family devices using DoT client identifiers:

- On Android Private DNS, set the provider to e.g.
  `phone-kyle.dns.kylehub.dev` instead of plain `dns.kylehub.dev`.
- In AdGuard `Settings -> Client settings -> Persistent clients`,
  add the client identifier (e.g. `phone-kyle`) and set per-client
  rules.
- Under `Settings -> DNS settings -> Allowed clients`, list only
  the identifiers you want to permit.

This is a setup task in the AdGuard UI, not a compose change.

## Verification

### Recursive resolution (Unbound)
```bash
podman exec dns-unbound drill @127.0.0.1 -p 53 +dnssec example.com | grep -E "rcode|flags"
# Expect: rcode: NOERROR; flags include "ad" (DNSSEC validated)
```

### Internal chain (AdGuard -> Unbound)
```bash
# From inside the dns-net network
podman exec dns-adguard wget -qO- http://dns-unbound:53 || \
  podman exec dns-adguard nslookup example.com 127.0.0.1
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
Android -> Settings -> Network & Internet -> Private DNS -> Provider
name -> `dns.kylehub.dev` (or `phone-yourname.dns.kylehub.dev` if
using client identifiers) -> Save. Browse for a minute and check
AdGuard `Top clients` - your phone should appear.

### Cert renewal smoke test
```bash
podman exec dns-lego ls -la /data/certificates/
podman exec dns-lego openssl x509 -in /data/certificates/dns.kylehub.dev.crt \
  -noout -dates
# Expect notAfter > 60 days from now after a fresh issue.
```

### Dashboard via Pangolin
`https://adguard.kylehub.dev` -> Zitadel -> AdGuard UI loads cleanly,
TLS cert is the Pangolin/Traefik cert (not the dns.kylehub.dev one -
those are two different chains).

## Cleanup (after ~2 weeks of stable operation)

```bash
# Remove the old app stack
rm -rf /home/kyle/infrastructure/homelab/apps/adguard

# Remove the old volumes
podman volume rm adguard-work adguard-conf
```

## Troubleshooting

### `dns-lego` keeps failing with `dns: NS ns.example.com.: dns: lookup ...`

Cloudflare API token is missing or lacks `Zone:DNS:Edit`. Check
`podman-compose logs dns-lego` for the exact error and re-issue the
token via Cloudflare -> My Profile -> API Tokens.

### Cert renewed but AdGuard still serves the old one

The renew-hook didn't restart AdGuard. Check
`podman-compose logs dns-lego` for the hook output. Manual fix:
```bash
podman restart dns-adguard
```

### Mobile's "Private DNS" says "Couldn't connect"

1. `dns.kylehub.dev` Cloudflare proxy is ON - turn it OFF.
2. The cert hasn't been issued yet - `podman-compose logs dns-lego`.
3. Your ISP blocks outbound 853 - try DoH on 443 instead, or use a
   non-residential connection.

### Need to roll back to the old `apps/adguard` stack

The old volumes (`adguard-conf`, `adguard-work`) are untouched until
you run "Cleanup". To roll back:
```bash
cd homelab/core/dns       && podman-compose down
cd homelab/apps/adguard   && podman-compose up -d
```

## Caveats

- **Image choice - `mvance/unbound` vs `nlnetlabs/unbound`:** we use
  `mvance/unbound:latest` because its config layout
  (`/opt/unbound/etc/unbound/`) is the de-facto standard for
  compose-based homelab setups, has stable paths, and ships `drill`
  for the healthcheck. Switching is a one-line change later -
  `unbound.conf` is portable.

- **IPv6:** the compose binds v6 inside the bridge but the host's v6
  reachability is up to the data centre. Add an `AAAA` record for
  `dns.kylehub.dev` if the box has public v6 - cellular clients
  often arrive over v6 and will fall back to v4 if AAAA isn't present.

- **Backups:** the named volumes worth backing up are
  `dns-adguard-conf` (filter lists, clients, rewrites, admin user)
  and `dns-unbound-data` (DNSSEC trust anchor). `dns-lego-data`
  contains certs but they re-issue automatically on restart, so
  backup is optional.

- **Cert volume permissions:** lego writes mode 644 inside `/certs/`.
  AdGuard mounts it read-only. If you ever see "permission denied"
  reading the cert, exec into adguard and check ownership - it
  should not require root to read.
