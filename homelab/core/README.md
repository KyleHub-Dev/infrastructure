# homelab/core

Shared core infrastructure for the homelab zone. Each subdirectory is
an independent Podman Compose stack that can be brought up and torn
down on its own. They are connected through two shared external
networks documented in [`_edge/README.md`](./_edge/README.md).

## Stacks

| Stack                              | Status                       | Public hostname (via Pangolin)                                              | Purpose                                       |
|------------------------------------|------------------------------|-----------------------------------------------------------------------------|-----------------------------------------------|
| [`_edge/`](./_edge/)               | Required first               | n/a                                                                         | Shared Newt agent + network model             |
| [`dns/`](./dns/)                   | Active                       | DoT/DoH on `dns.kylehub.dev`, dashboard `adguard.kylehub.dev`               | Recursive DNS + filtering                     |
| [`storage/`](./storage/)           | Active                       | `storage.kylehub.dev`                                                       | RustFS - central S3-compatible object storage |
| [`observability/`](./observability/) | **Design under review**    | (none yet)                                                                  | OTLP ingest, Loki, Prometheus, Grafana        |
| [`langfuse/`](./langfuse/)         | Prepared, not yet deployed   | `langfuse.kylehub.dev`                                                      | LLM-app observability                         |
| [`git/`](./git/)                   | **Prepared, not deployed**   | (none - see SETUP.md)                                                       | Forgejo - refactored for consistency only    |

## Bring-up order

The full step-by-step runbook is in [`DEPLOY.md`](./DEPLOY.md).
Short form:

1. **Edge first** - see [`_edge/README.md`](./_edge/README.md). Run
   `_edge/bootstrap.sh`, fill in `NEWT_ID` / `NEWT_SECRET`,
   `podman-compose up -d`.
2. **Storage** - RustFS is the S3 backbone consumed by every other
   stack; deploy this before any S3 client.
3. **DNS** - public DoT/DoH + AdGuard dashboard.
4. `langfuse` waits until you have RustFS bucket + scoped credentials.
5. `observability` is on hold pending design review.
6. `git` is not deployed.

Pangolin Resources are created in the admin UI under the single
`Homelab Core` Site as each stack comes up.

## Pangolin model

Every public-facing service in this zone is reached through one
Pangolin Site (`Homelab Core`) and one Newt agent (`core-newt`).
Resources point at the container hostnames listed in
[`_edge/README.md`](./_edge/README.md). Initial auth posture for all
Resources is Zitadel IAP; native per-service OIDC is a per-stack
follow-up decision.

## Conventions

- **Container names** are prefixed by stack: `dns-*`, `storage-*`,
  `obs-*`, `langfuse-*`, `git-*`. The single exception is the central
  Newt (`core-newt`) which is zone-scoped, not stack-scoped.
- **Image pinning**: stateful images (databases, ClickHouse, Forgejo)
  are pinned to major+minor. Stateless tooling (Newt, Otel, Loki,
  Prometheus, Grafana, Unbound, AdGuard, Lego, RustFS) tracks
  `:latest` for now and can be pinned later when versions stabilise.
- **Secrets** live in per-stack `.env` files, never in compose files.
  All `.env` files are gitignored at the repository root.
- **Object storage**: a single central RustFS instance in `storage/`.
  No per-stack MinIO/SeaweedFS. New stacks consume RustFS via
  `homelab-core-data` with stack-specific access keys.
- **Host ports**: none, except where required for traffic that
  cannot tunnel through Pangolin (DoT 853, DoH 443 in the dns stack).
