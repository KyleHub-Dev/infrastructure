# SearXNG — Private Search Instance

Self-hosted, private SearXNG instance tunneled through Pangolin with IAP protection. All access (human or service) is authenticated at the Pangolin layer before traffic reaches SearXNG.

> **Runtime:** This stack uses **Podman** + **podman-compose**. All commands below use `podman-compose`. If you don't have it yet: `pip install podman-compose`.

## Architecture

```
Client (browser / service)
        │
        ▼
pangolin.example.com  ──  IAP  ──► Zitadel OIDC (human users)
        │                     └──► Resource Token (service-to-service)
        │
   Newt tunnel (inside container network)
        │
        ▼
  searxng:8080  (internal only, never exposed to host)
```

- **SearXNG** runs on port `8080` inside the Podman network — no host port binding.
- **Newt** dials out to Pangolin; Pangolin routes inbound traffic back through the tunnel. No inbound firewall ports needed.
- **Rate limiting is disabled** in SearXNG itself. Pangolin IAP is the access gate.

---

## Ports

| Port | Direction | Purpose |
|------|-----------|---------|
| None | Inbound | No host ports need to be opened. Newt dials *out* over HTTPS (443). |
| 443/TCP outbound | Outbound | Newt → Pangolin tunnel connection. Must be reachable from the host. |

> **Firewall summary:** Open **no inbound ports** on the host running SearXNG. The only requirement is that the host can reach `pangolin.example.com:443` outbound.

---

## Setup

### 1. Create a Tunnel in Pangolin

1. Log into your Pangolin dashboard.
2. Navigate to **Tunnels → New Tunnel**.
3. Choose **Newt** as the tunnel type.
4. Note the **Tunnel ID** and **Tunnel Secret**.
5. Under the tunnel, add a **Target**: `http://searxng:8080`
6. Create a **Resource** pointing to this tunnel and set the hostname to your desired domain (e.g. `search.example.com`).

### 2. Enable IAP on the Resource

In the Pangolin dashboard, on your `search.example.com` resource:

1. Enable **IAP (Identity-Aware Proxy)**.
2. Set the **Identity Provider** to your Zitadel instance (`auth.example.com`).
3. Configure allowed users/groups in Zitadel as needed.

Human users visiting `https://search.example.com` will be redirected to Zitadel to authenticate before gaining access.

### 3. Create Resource Tokens for Services

For machines or services that need to query SearXNG programmatically (without a browser session):

1. In Pangolin dashboard, go to your resource (`search.example.com`).
2. Navigate to **Resource Tokens → New Token**.
3. Give it a descriptive name (e.g. `osint-worker`, `home-assistant`).
4. Copy the generated token.

Services pass this token in every request:

```http
GET https://search.example.com/search?q=example&format=json
Authorization: Bearer <resource-token>
```

or via query param (if Pangolin supports it):

```
https://search.example.com/search?q=example&format=json&token=<resource-token>
```

Pangolin validates the token and proxies the request to SearXNG. SearXNG never sees the token.

### 4. Deploy

```bash
cp .env.example .env
# Edit .env — fill in SEARXNG_SECRET_KEY, NEWT_TUNNEL_ID, NEWT_TUNNEL_SECRET

# Generate a secret key
openssl rand -hex 32

podman-compose up -d
podman-compose logs -f
```

---

## JSON / API Usage

JSON output is enabled by default. Query the API from any authenticated service:

```bash
# Via resource token
curl -H "Authorization: Bearer <token>" \
  "https://search.example.com/search?q=searxng+api&format=json"

# Response fields: query, number_of_results, results[].url, .title, .content, .engine, ...
```

Available formats: `json`, `csv`, `rss`, `html`

---

## Configuration

All SearXNG config lives in `./config/`:

| File | Purpose |
|------|---------|
| `settings.yml` | Main config — engines, formats, rate limits, UI |
| `uwsgi.ini` | uWSGI server tuning |

Key settings already configured:

- `limiter: false` — no rate limiting inside SearXNG (Pangolin handles access)
- `formats: [html, json, csv, rss]` — all output formats enabled
- `safe_search: 0` — disabled (adjust if needed)
- `enable_metrics: true` — Prometheus metrics available at `/stats`

---

## Updating

```bash
podman-compose pull
podman-compose up -d
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Newt can't connect | Verify `PANGOLIN_ENDPOINT`, `NEWT_TUNNEL_ID`, `NEWT_TUNNEL_SECRET` in `.env` |
| 401 on resource | Token missing or expired — regenerate in Pangolin dashboard |
| Search returns no results | Check `podman-compose logs searxng` for engine errors |
| IAP loop / redirect loop | Ensure Zitadel OIDC client is configured in Pangolin with correct redirect URIs |
