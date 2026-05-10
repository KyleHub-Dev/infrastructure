# KyleHub Storage

This stack runs RustFS as the homelab's shared S3-compatible object
storage service. It is the single source of object storage for the
core zone - other stacks (Langfuse today, future apps tomorrow)
consume it via the `homelab-core-data` network instead of running
their own MinIO.

The Pangolin Newt for this zone lives in `homelab/core/_edge` and is
shared by all `core/*` stacks. Bring `_edge` up first
(see `_edge/README.md`).

## Why this shape

RustFS is a single-binary S3-compatible object storage service. The
Docker install path uses the `rustfs/rustfs:latest` image, exposes the
S3 API on port `9000`, exposes the console on port `9001`, stores
object data under `/data`, and runs as UID `10001`.

This stack uses:

- `docker.io/rustfs/rustfs:latest`
- a host bind mount at `/srv/rustfs/data`, chowned to UID 10001 once
  on the host (see step 2 below)
- no direct host port mappings

Sources:

- https://docs.rustfs.com/installation/docker/
- https://github.com/rustfs/rustfs/blob/main/docker-compose.yml

## Architecture

```text
Client browser
      |
      v
Pangolin + Zitadel/IAP
      |
      v
core-newt (in core/_edge)
      |
      v
storage-rustfs:9001  Console     <- on homelab-core-edge

Internal S3 clients (langfuse-*, future apps)
      |
      v
storage-rustfs:9000  S3 API      <- on homelab-core-data
                                    (NOT reachable from core-newt)
```

If external S3 access is needed later, add a Pangolin Resource:

```text
s3.kylehub.dev -> storage-rustfs:9000
```

Do **not** enable IAP on the S3 API. Normal S3 clients use AWS-style
request signing and an auth gateway will break the flow.

## First run

1. Create the host storage directory:

   ```sh
   sudo mkdir -p /srv/rustfs/data
   ```

2. Set ownership so RustFS (UID `10001` inside the container) can
   write to it. Pick the variant that matches your Podman runtime:

   **Rootful Podman** (recommended; consistent with the DNS stack
   which also requires rootful):

   ```sh
   sudo chown -R 10001:10001 /srv/rustfs/data
   ```

   **Rootless Podman**:

   ```sh
   sudo chown "$(id -u):$(id -g)" /srv/rustfs/data
   podman unshare chown -R 10001:10001 /srv/rustfs/data
   ```

   `podman unshare` enters your user namespace; the `10001` inside it
   maps to a host UID in your subuid range, which the rootless
   container can read and write.

3. Copy the env template:

   ```sh
   cp .env.example .env
   ```

4. Generate strong root credentials:

   ```sh
   openssl rand -hex 16
   openssl rand -base64 48
   ```

5. Edit `.env` and set at least:

   ```sh
   RUSTFS_ACCESS_KEY=...
   RUSTFS_SECRET_KEY=...
   ```

   Pangolin / Newt credentials are NOT in this stack. The single
   Newt in `homelab/core/_edge` handles tunnelling.

6. Start the stack with the same runtime mode you used for `_edge`
   (rootless or rootful - networks live in different namespaces, so
   they must match):

   ```sh
   podman-compose up -d
   ```

7. In Pangolin, under the existing `Homelab Core` Site (created by
   `_edge`), add an HTTPS resource for the console:

   ```text
   storage.kylehub.dev -> storage-rustfs:9001
   ```

8. Enable Zitadel/IAP on the console resource.

9. Open `https://storage.kylehub.dev` and sign in with the RustFS
   credentials from `.env`.

10. **Provision per-stack service accounts** in the RustFS console.
   Do not reuse the root credentials for application access. For
   each consuming stack, create a bucket and a scoped access-key
   pair:

   - Langfuse: bucket `langfuse`, key with read/write on that bucket.
   - Future apps: same pattern, one bucket per stack.

## Public interfaces

| Endpoint                      | Purpose         | Exposure                                          |
|-------------------------------|-----------------|---------------------------------------------------|
| `https://storage.kylehub.dev` | RustFS console  | Pangolin + Zitadel/IAP                            |
| `http://storage-rustfs:9000`  | S3 API          | `homelab-core-data`, on-host containers only      |
| `https://s3.kylehub.dev`      | Optional S3 API | Pangolin, NO IAP (S3-Sig clients only)            |

## Internal verification

Check container status and logs:

```sh
podman-compose ps
podman-compose logs storage-rustfs
```

Health endpoints inside the RustFS container:

```text
http://127.0.0.1:9000/health
http://127.0.0.1:9001/rustfs/console/health
```

For S3 API verification with the MinIO client from another container
on `homelab-core-data`:

```sh
podman run --rm --network homelab-core-data \
  docker.io/minio/mc \
  alias set rustfs http://storage-rustfs:9000 <access-key> <secret-key>
```

## App integration

For apps in the core zone, attach the consumer container to
`homelab-core-data` and point at:

```text
endpoint:           http://storage-rustfs:9000
access key:         app-specific (NOT the root key)
secret key:         app-specific
path-style access:  true
region:             auto
```

Langfuse is the first consumer of this pattern; see
`../langfuse/.env.example` and `../langfuse/compose.yaml` for the
exact env layout.

## Backups

Back up the host data directory:

```text
/srv/rustfs/data
```

RustFS object data is the source of truth. The repository files only
describe how to run the service.

For a real restore test:

1. Stop the stack.
2. Restore `/srv/rustfs/data`.
3. Start the stack.
4. Verify console login.
5. Verify bucket listing with `mc ls`.
6. Upload and download a test object.

## Podman compatibility

Validate the rendered Compose config before deployment:

```sh
podman-compose --env-file .env.example config
```

The stack intentionally avoids bundled Grafana / Prometheus / Jaeger
services from the upstream RustFS examples. Observability lives in
`homelab/core/observability/`.
