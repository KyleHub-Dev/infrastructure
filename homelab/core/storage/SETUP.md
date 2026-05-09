# KyleHub Storage

This stack runs RustFS as the homelab's shared S3-compatible object storage service behind a Pangolin Newt tunnel with Podman Compose.

## Why this shape

RustFS is a single binary S3-compatible object storage service. The Docker install path uses the `rustfs/rustfs:latest` image, exposes the S3 API on port `9000`, exposes the console on port `9001`, stores object data under `/data`, and runs as UID `10001`.

This stack uses:

- `docker.io/rustfs/rustfs:latest`
- `docker.io/fosrl/newt:latest`
- a host bind mount at `/srv/rustfs/data`
- a one-shot ownership container for the RustFS runtime UID
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
storage-newt
      |
      v
rustfs:9001  Console
```

The S3 API is internal by default:

```text
Internal S3 clients -> http://rustfs:9000
```

If external S3 access is required later, create a second Pangolin resource:

```text
s3.kylehub.dev -> storage-newt -> rustfs:9000
```

Do not enable Pangolin IAP on the S3 API unless every client is designed to send Pangolin resource tokens. Normal S3 clients expect AWS-style request signing, and an auth gateway can interfere with that flow.

## First run

1. Create the host storage directory:

   ```sh
   sudo mkdir -p /srv/rustfs/data
   ```

2. Copy the env template:

   ```sh
   cp .env.example .env
   ```

3. Generate strong credentials:

   ```sh
   openssl rand -hex 16
   openssl rand -base64 48
   ```

4. Edit `.env` and set at least:

   ```sh
   RUSTFS_ACCESS_KEY=...
   RUSTFS_SECRET_KEY=...
   PANGOLIN_ENDPOINT=...
   NEWT_ID=...
   NEWT_SECRET=...
   ```

5. Start the stack:

   ```sh
   podman-compose up -d
   ```

6. In Pangolin, create an HTTPS resource for the console:

   ```text
   storage.kylehub.dev -> storage-newt -> rustfs:9001
   ```

7. Enable Zitadel/IAP on the console resource.

8. Open `https://storage.kylehub.dev` and sign in with the RustFS credentials from `.env`.

## Public interfaces

| Endpoint | Purpose | Exposure |
|----------|---------|----------|
| `https://storage.kylehub.dev` | RustFS console | Pangolin + Zitadel/IAP |
| `http://rustfs:9000` | S3 API | Internal container network |
| `https://s3.kylehub.dev` | Optional S3 API | Pangolin, no IAP unless clients support resource tokens |

## Internal verification

Check container status and logs:

```sh
podman-compose ps
podman-compose logs rustfs
```

Health endpoints inside the RustFS container:

```text
http://127.0.0.1:9000/health
http://127.0.0.1:9001/rustfs/console/health
```

For S3 API verification with the MinIO client, use an endpoint reachable from where `mc` runs. The default stack does not publish host ports, so either run the client from inside the Compose network or temporarily add a localhost-only debug port during testing.

Example commands:

```sh
mc alias set rustfs <endpoint> <access-key> <secret-key>
mc mb rustfs/smoke-test
echo test > /tmp/rustfs-smoke.txt
mc cp /tmp/rustfs-smoke.txt rustfs/smoke-test/
mc cat rustfs/smoke-test/rustfs-smoke.txt
mc rm rustfs/smoke-test/rustfs-smoke.txt
mc rb rustfs/smoke-test
```

## App integration

Future homelab apps can use RustFS as S3-compatible storage by configuring:

```text
endpoint: http://rustfs:9000
access key: app-specific access key
secret key: app-specific secret key
path-style access: true
region: auto
```

For apps in separate Compose projects, either use the optional public S3 endpoint or later add a shared external Podman network for private cross-stack traffic.

Langfuse currently runs its own MinIO container. Migrating Langfuse to RustFS should be a separate change because it touches existing object data and bucket configuration.

## Backups

Back up the host data directory:

```text
/srv/rustfs/data
```

RustFS object data is the source of truth. The repository files only describe how to run the service.

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

The stack intentionally avoids bundled Grafana, Prometheus, or Jaeger services from the upstream RustFS examples. Observability belongs in the existing homelab observability stack.
