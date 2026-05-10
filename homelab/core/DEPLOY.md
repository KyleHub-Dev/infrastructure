# core/ - Deploy runbook

Step-by-step deployment of the core zone in the order:

1. **Edge online** (networks + central Newt)
2. **Storage** (RustFS - the central S3 backbone)
3. **DNS** (Unbound + AdGuard + Lego)

Out of scope right now:
- `git/` - prepared but not deployed; see `git/SETUP.md`.
- `observability/` - design under review; do not deploy yet.

Every command in this file is meant to be run from
`homelab/core/` on the Hetzner server, as the user that runs
`podman-compose` for the rest of the homelab.

---

## Phase 0 - One-time external setup

### 0.1 Pangolin Site

In the Pangolin admin UI on `gateway-vps`:

1. **Sites -> New Site**: name it exactly `Homelab Core`. Pick the
   same WireGuard region the other homelab tunnels use.
2. Pangolin generates a `NEWT_ID` and `NEWT_SECRET`. Store both in
   your password manager.

You will paste these into `_edge/.env` in Phase 1. Do **not** create
per-stack Sites or per-stack NEWT credentials.

### 0.2 Cloudflare API token

Cloudflare -> My Profile -> API Tokens -> Create Token:

- Permission: **Zone -> DNS -> Edit** on the `kylehub.dev` zone.

The same token gateway-vps already uses for Traefik works here too.

### 0.3 Cloudflare DNS records

In the `kylehub.dev` zone:

| Record                  | Type | Value                              | Proxy   |
|-------------------------|------|------------------------------------|---------|
| `dns.kylehub.dev`       | A    | this server's public IPv4          | **OFF** |
| `dns.kylehub.dev`       | AAAA | this server's public IPv6 (if any) | **OFF** |
| `*.dns.kylehub.dev`     | A    | this server's public IPv4          | **OFF** |
| `adguard.kylehub.dev`   | A    | gateway-vps Pangolin public IP     | ON      |
| `storage.kylehub.dev`   | A    | gateway-vps Pangolin public IP     | ON      |

The `dns.kylehub.dev` and `*.dns.kylehub.dev` records MUST be unproxied
because Cloudflare cannot proxy port 853 (DoT). The wildcard exists so
AdGuard ClientIDs work — each device uses a unique subdomain like
`phone-kyle.dns.kylehub.dev` for SNI-based per-device tagging. The
TLS cert (issued by lego in dns/) covers both the apex and the
wildcard. Everything that goes through Pangolin (`adguard.*`,
`storage.*`) stays proxied.

---

## Phase 1 - Edge online

This phase brings up the central Newt. Once it connects, every
follow-up service stack is reachable through Pangolin without needing
its own Newt.

### 1.1 Bootstrap

```sh
cd homelab/core/_edge
./bootstrap.sh
```

`bootstrap.sh` is idempotent:
- creates `homelab-core-edge` and `homelab-core-data` if missing
- copies `.env.example` to `.env` if missing

### 1.2 Fill in NEWT credentials

Edit `_edge/.env`:

```ini
PANGOLIN_ENDPOINT=https://pangolin.kylehub.dev
NEWT_ID=<paste from Pangolin>
NEWT_SECRET=<paste from Pangolin>
```

### 1.3 Start the Newt

```sh
podman-compose up -d
podman-compose logs -f core-newt
```

Look for a line like `websocket connected` / `tunnel established`,
then Ctrl-C the log follow.

### 1.4 Verify

In the Pangolin admin UI: **Sites -> Homelab Core** should show as
**online**. No Resources yet - that's expected.

---

## Phase 2 - Storage (RustFS)

### 2.1 Host prep

```sh
sudo mkdir -p /srv/rustfs/data
```

Set ownership so RustFS (UID `10001` inside the container) can write
to it. Pick the variant that matches the Podman runtime mode you used
for `_edge` (rootful and rootless live in separate namespaces - they
must match across the whole core zone):

```sh
# Rootful Podman (recommended; matches what dns/ will need)
sudo chown -R 10001:10001 /srv/rustfs/data

# Rootless Podman
sudo chown "$(id -u):$(id -g)" /srv/rustfs/data
podman unshare chown -R 10001:10001 /srv/rustfs/data
```

### 2.2 Generate root credentials

```sh
openssl rand -hex 16    # use as RUSTFS_ACCESS_KEY
openssl rand -base64 48 # use as RUSTFS_SECRET_KEY
```

### 2.3 Configure and start

```sh
cd ../storage
cp .env.example .env
# edit .env: paste the two openssl outputs into RUSTFS_ACCESS_KEY
# and RUSTFS_SECRET_KEY. Other values can stay at their defaults.
podman-compose up -d
podman-compose ps
```

`storage-rustfs` should report healthy within ~40 s.

### 2.4 Pangolin Resource

In the Pangolin admin UI, under the existing `Homelab Core` Site:

- **New Resource** -> hostname `storage.kylehub.dev`
- Upstream: `http://storage-rustfs:9001`
- Auth: **Zitadel IAP**

### 2.5 Verify

Open `https://storage.kylehub.dev` -> Zitadel SSO -> RustFS console.
Sign in with the access key + secret key you just generated.

### 2.6 Provision per-stack credentials (do this now even if no consumers yet)

In the RustFS console:

1. Create a bucket named `langfuse` (for the future Langfuse deploy).
2. Create a service account / scoped access key pair restricted to
   that bucket. Save the keys for later use in `langfuse/.env`.
3. Repeat per future consuming stack: one bucket, one scoped key.

**Never** put the root credentials into a consuming app's `.env`.

---

## Phase 3 - DNS (Unbound + AdGuard + Lego)

### 3.1 Rootless host setup (one-time, persistent)

Three host-level nudges. All idempotent on re-run.

```sh
# Allow unprivileged user processes to bind ports >= 443 (covers 443+853).
echo "net.ipv4.ip_unprivileged_port_start=443" | \
  sudo tee /etc/sysctl.d/99-rootless-ports.conf
sudo sysctl --system

# Enable the rootless Podman API socket so the lego renew-hook can
# trigger `podman restart dns-adguard` after each renewal.
systemctl --user enable --now podman.socket

# Keep user services alive across logout/reboot - critical so the
# socket is still there 60 days from now when lego renews.
sudo loginctl enable-linger "$USER"

# Sanity check
ls -l "/run/user/$(id -u)/podman/podman.sock"
```

If you ever need rootful instead, set `PODMAN_SOCKET=/run/podman/podman.sock`
in `dns/.env` and run the stack with `sudo podman-compose`.

### 3.2 Pangolin Resource (do this BEFORE first AdGuard wizard run)

Under the `Homelab Core` Site:

- **New Resource** -> hostname `adguard.kylehub.dev`
- Upstream: `http://dns-adguard:3000`
- Auth: **Zitadel IAP**

### 3.3 Configure and start

```sh
cd ../dns
cp .env.example .env
# edit .env:
#   ACME_EMAIL=<your address>
#   CF_DNS_API_TOKEN=<Cloudflare token>
#   PODMAN_SOCKET=/run/user/$(id -u)/podman/podman.sock   # adjust UID
# CERT_DOMAIN and TZ can stay at defaults.
podman-compose up -d
podman-compose logs -f dns-lego
```

You should see, within ~1-2 minutes:

```
[lego] No cert at /data/certificates/dns.kylehub.dev.crt, requesting...
[INFO] [dns.kylehub.dev] acme: Obtaining bundled SAN certificate...
[INFO] [dns.kylehub.dev] Server responded with a certificate.
[hook] cert for dns.kylehub.dev written to /certs/dns.kylehub.dev
[hook] dns-adguard restart triggered (HTTP 204)
```

### 3.4 AdGuard wizard

Open `https://adguard.kylehub.dev` (via Pangolin/Zitadel). Run through
the wizard - default ports (`0.0.0.0:3000` for the UI, `0.0.0.0:53`
internally for AdGuard's own listener) are fine. Then:

1. **Settings -> DNS settings -> Upstream DNS servers**:
   ```
   dns-unbound:53
   ```
   No third-party fallbacks - that defeats the purpose of running
   Unbound.

2. **Settings -> Encryption settings**: turn on encryption, server
   name `dns.kylehub.dev`, point cert path at
   `/opt/adguardhome/conf/certs/dns.kylehub.dev/cert.pem` and key
   path at `/opt/adguardhome/conf/certs/dns.kylehub.dev/key.pem`.

3. **Settings -> Client settings -> Persistent clients** + **Allowed
   clients**: add a DoT client identifier per family device
   (e.g. `phone-kyle`) and restrict to that list. Plain DNS port 53
   is intentionally not bound on this host, so DoT identifiers are
   the access-control mechanism.

Full wizard / cert details are in `dns/SETUP.md`.

### 3.5 Verify

```sh
# DoT from any external machine
dig @dns.kylehub.dev +tls example.com

# DoH
curl -v -H 'accept: application/dns-message' \
  'https://dns.kylehub.dev/dns-query?dns=AAABAAABAAAAAAAAA3d3dwdleGFtcGxlA2NvbQAAAQAB' \
  -o /dev/null
```

On a phone: Settings -> Network & Internet -> Private DNS -> Provider
hostname `dns.kylehub.dev` (or `phone-yourname.dns.kylehub.dev`
matching the AdGuard client identifier).

---

## Phase 4 - Observability (deferred)

The structural refactor of `observability/` is in place but the
overall design needs a second pass before deploy: scope of telemetry,
which apps push vs. which to scrape, native Grafana OIDC vs. Pangolin
IAP. Do NOT `podman-compose up` this stack yet.

Resume here once those questions are answered.

---

## Phase 5 - Git (out of scope)

`git/` is intentionally not deployed. See `git/SETUP.md` for the
unblocking conditions.

---

## Quick reference: per-stack values you must fill

| Stack         | `.env` value                         | Source                                              |
|---------------|--------------------------------------|-----------------------------------------------------|
| `_edge`       | `NEWT_ID`, `NEWT_SECRET`             | Pangolin Site "Homelab Core"                        |
| `storage`     | `RUSTFS_ACCESS_KEY`                  | `openssl rand -hex 16`                              |
| `storage`     | `RUSTFS_SECRET_KEY`                  | `openssl rand -base64 48`                           |
| `dns`         | `ACME_EMAIL`                         | your address                                        |
| `dns`         | `CF_DNS_API_TOKEN`                   | Cloudflare My Profile -> API Tokens (Zone DNS Edit) |

Everything else has a sensible default in `.env.example`.
