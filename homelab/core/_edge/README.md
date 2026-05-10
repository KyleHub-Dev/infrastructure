# core/_edge - Shared infrastructure for the Homelab Core zone

This stack defines the minimum shared infrastructure that every other
`homelab/core/*` stack depends on:

- **One** Pangolin Newt agent (`core-newt`), registered as the Pangolin
  Site **"Homelab Core"**. Every Pangolin Resource for this zone is
  attached to that single Site - no per-stack Newts, no per-stack Sites.
- **Two** external Podman networks that connect the otherwise-isolated
  service stacks. Both networks are **created manually**, outside any
  compose file, and referenced as `external: true` everywhere.

This stack must be running before any other `core/*` stack is started.

---

## Network model

```
                                     internet
                                        |
                              gateway-vps (Pangolin)
                                        |
                              WireGuard / Newt protocol
                                        |
+---------------------------------------|-----------------------------+
|                                  core-newt                          |
|                                        |                            |
|     ====== homelab-core-edge ==========|=========================   |
|     |          (user-facing traffic)                            |   |
|     |                                                           |   |
|     |   dns-adguard:3000     (AdGuard dashboard)                |   |
|     |   storage-rustfs:9001  (RustFS console)                   |   |
|     |   obs-grafana:3000     (Grafana UI)                       |   |
|     |   langfuse-web:3000    (Langfuse UI)                      |   |
|     |   git-forgejo:3000     (Forgejo - prepared, NOT deployed) |   |
|     ============================================================   |
|                                                                    |
|     ====== homelab-core-data ======================================+
|     |   (service-to-service backbone, NOT reachable from Newt)    |
|     |                                                             |
|     |   storage-rustfs:9000   <- S3 API                           |
|     |   obs-otel:4317 / 4318  <- OTLP ingest                      |
|     |                                                             |
|     |   clients on this network:                                  |
|     |     langfuse-web      (S3 uploads, future telemetry)        |
|     |     langfuse-worker   (S3 read/write, future telemetry)     |
|     |     future homelab/apps/* (telemetry producers)             |
|     ===============================================================+
|                                                                    |
|     Each service stack also keeps its own private bridge network   |
|     (e.g. langfuse-net, obs-net, dns-net, git-net) for databases,  |
|     caches, and workers that have NO cross-stack consumers.        |
+--------------------------------------------------------------------+
```

### `homelab-core-edge`

Carries user-facing traffic between `core-newt` and each stack's
front-end container. Anything attached to this network is by design
reachable from the Newt and therefore eligible to be exposed as a
Pangolin Resource.

| Container        | Stack         | Pangolin Resource           | Notes                                    |
|------------------|---------------|-----------------------------|------------------------------------------|
| `core-newt`      | _edge         | n/a (the Newt itself)       | sole Newt for the core zone             |
| `dns-adguard`    | dns           | `adguard.kylehub.dev`       | dashboard only; DoT/DoH bypass Pangolin |
| `storage-rustfs` | storage       | `storage.kylehub.dev`       | RustFS console (port 9001)              |
| `obs-grafana`    | observability | `grafana.kylehub.dev`       | UI                                       |
| `langfuse-web`   | langfuse      | `langfuse.kylehub.dev`      | UI + API                                 |
| `git-forgejo`    | git           | none (stack stays down)     | structurally prepared; see git/SETUP.md |

### `homelab-core-data`

Carries internal service-to-service traffic that must NOT pass through
Pangolin. Reasons:

- **Latency** - same-host container DNS resolves in microseconds; a
  WireGuard round-trip via the gateway VPS adds ~10-50 ms.
- **Bandwidth** - every byte routed through Pangolin counts twice
  against the gateway VPS egress (in via WireGuard, out via WireGuard).
  S3 PUT/GET volumes from Langfuse can grow quickly.
- **Auth model mismatch** - the central Newt's IAP path expects
  Pangolin resource tokens; normal S3 / OTLP clients use AWS-Sig or
  bearer tokens. An auth gateway breaks them.

`core-newt` is **deliberately not** attached to this network, so
internal-only services cannot be accidentally re-exposed via Pangolin.

| Container         | Stack         | Listens on                | Reason                            |
|-------------------|---------------|---------------------------|-----------------------------------|
| `storage-rustfs`  | storage       | `9000` (S3 API)           | shared object storage backbone    |
| `obs-otel`        | observability | `4317` (gRPC), `4318` (HTTP) | OTLP telemetry ingest          |
| `langfuse-web`    | langfuse      | client only               | uploads media/events to RustFS    |
| `langfuse-worker` | langfuse      | client only               | reads/writes RustFS, future OTLP  |

External clients (your laptop, CI, anything off-host) reach these
services only via explicit Pangolin Resources (`s3.kylehub.dev` for
S3, no equivalent for OTLP yet) - never via this network.

### Why `external: true` and manual creation?

If a network were created by a single compose file, `compose down` on
that file would destroy the network and disconnect every other stack
attached to it. That is a footgun in a multi-stack setup where stacks
are intentionally restarted independently.

Both edge networks are therefore created **once, by hand** and every
compose file references them as `external: true`. The lifecycle of
the network is decoupled from the lifecycle of any single stack.

---

## First-time setup

### 1. Create the shared networks

Run as the same user that runs `podman-compose` for the rest of the
core stacks. Both commands are idempotent on re-run:

```sh
podman network exists homelab-core-edge || podman network create homelab-core-edge
podman network exists homelab-core-data || podman network create homelab-core-data
```

Verify:

```sh
podman network ls --filter name=homelab-core-
# Expected:
#   NETWORK ID    NAME                 DRIVER
#   ...           homelab-core-data    bridge
#   ...           homelab-core-edge    bridge
```

### 2. Provision Newt credentials in Pangolin

In the Pangolin admin UI on `gateway-vps`:

1. **Sites -> New Site**: name it `Homelab Core`. Pick the same
   WireGuard region used by other tunnels.
2. Pangolin generates a `NEWT_ID` and `NEWT_SECRET`. Store both in
   your password manager.

You only do this **once** for the entire core zone.

### 3. Configure `.env` and start the Newt

```sh
cd homelab/core/_edge
cp .env.example .env
# edit .env: set PANGOLIN_ENDPOINT, NEWT_ID, NEWT_SECRET
podman-compose up -d
```

Verify the Newt is connected:

```sh
podman-compose logs core-newt | tail -n 20
# Expect a line like:
#   "websocket connected" / "tunnel established"
```

In Pangolin, the `Homelab Core` Site should now show as **online**.

### 4. Bring up the service stacks

After `_edge` is up and the networks exist, bring up the other stacks
in any order. Suggested sequence:

```sh
cd ../dns           && podman-compose up -d
cd ../storage       && podman-compose up -d
cd ../observability && podman-compose up -d
cd ../langfuse      && podman-compose up -d
# git/ stays down - see homelab/core/git/SETUP.md
```

Each stack documents its own `.env` requirements.

### 5. Define Pangolin Resources

In the Pangolin admin UI, under the `Homelab Core` Site, create
Resources pointing at the upstream container hostnames listed in
the `homelab-core-edge` table above. Initial auth posture for ALL
resources is **Zitadel IAP** (Pattern B from
`infrastructure/ARCHITECTURE.md`). Native per-service OIDC is a
follow-up decision tracked per stack.

---

## Adding a new stack to the core zone

Checklist:

1. Container names use a short, unique prefix (`<stack>-*`).
2. The user-facing front-end container attaches to `homelab-core-edge`.
3. Any container that needs to talk to RustFS or to ship telemetry
   attaches to `homelab-core-data`.
4. Internal databases, caches, and workers stay on a stack-private
   bridge network and do NOT touch the shared external networks.
5. The compose file declares each shared network it uses with
   `external: true`.
6. The new stack's README documents which Pangolin Resource to create.
7. No per-stack Newt container - the central `core-newt` handles all
   tunneling.

---

## Future: `homelab-apps-edge`

A second edge network is reserved for `homelab/apps/*`. It will
follow the same pattern as `homelab-core-edge`: manually created,
external, attached only by user-facing front-ends. A separate Newt
(`apps-newt`) and a separate Pangolin Site (`Homelab Apps`) will live
under `homelab/apps/_edge/`. There is no need to create that network
until the apps zone is ready to consume it.

---

## Decommissioning

To tear down the entire core zone:

```sh
# Stop service stacks first so they release their network attachments
cd homelab/core/langfuse      && podman-compose down
cd homelab/core/observability && podman-compose down
cd homelab/core/storage       && podman-compose down
cd homelab/core/dns           && podman-compose down
# Then the edge stack
cd homelab/core/_edge         && podman-compose down

# Finally, the shared networks
podman network rm homelab-core-edge
podman network rm homelab-core-data
```

`podman network rm` refuses to delete a network that still has
attached containers - that is your safety net against tearing the
shared infrastructure down with stacks still running.
