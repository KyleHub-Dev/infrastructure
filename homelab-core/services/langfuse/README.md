# Langfuse Self-Hosted Deployment

This directory contains the production-ready Docker Compose setup for Langfuse.

## Quick Start

1.  **Configure Environment**:
    ```bash
    cp .env.example .env
    # Edit .env and fill in the required secrets (NEXTAUTH_SECRET, SALT, ENCRYPTION_KEY, etc.)
    # Generate secrets using: openssl rand -hex 32
    ```

2.  **Start Services**:
    ```bash
    docker compose up -d
    ```

3.  **Initialize MinIO (First Run Only)**:
    Since this is a fresh install, MinIO starts empty.
    *   Access MinIO Console at `http://<your-server-ip>:9091` (or `localhost:9091` if local).
    *   Login with `minio` / `miniosecret` (or your configured credentials).
    *   Create a bucket named `langfuse`.
    *   *Note: Data persists in the `langfuse_minio_data` volume.*

## Zitadel (OIDC) Setup Guide

To enable Single Sign-On (SSO) with Zitadel:

1.  **Create Project**:
    *   Log in to your Zitadel Console.
    *   Create a new Project (e.g., "Langfuse").

2.  **Create Application**:
    *   In the Project, click **New**.
    *   Name: `Langfuse Web`
    *   Type: **Web**
    *   Auth Method: **Code** (PKCE is recommended, but Langfuse backend uses Code flow).
    *   **Redirect URIs**:
        *   `https://langfuse.kylehub.dev/api/auth/callback/zitadel`
        *   *(Note: The suffix `zitadel` matches the `AUTH_CUSTOM_ID` variable in `.env`)*.
    *   **Post Logout URIs**:
        *   `https://langfuse.kylehub.dev`

3.  **Get Credentials**:
    *   After creation, copy the **Client ID** and **Client Secret**.
    *   Update `.env` with these values:
        *   `AUTH_CUSTOM_CLIENT_ID`
        *   `AUTH_CUSTOM_CLIENT_SECRET`
        *   `AUTH_CUSTOM_ISSUER`: Your Zitadel instance URL (e.g., `https://auth.kylehub.dev`).

4.  **Roles & Permissions**:
    *   **Note**: Langfuse OIDC does *not* automatically map Zitadel roles to Langfuse roles (Admin/Member) without Enterprise SCIM.
    *   **First User**: The first user to log in (or defined in `LANGFUSE_INIT_...` variables) will be an Admin.
    *   **Subsequent Users**: Will join as "Members" (if public signup is enabled) or must be invited.
    *   **Recommendation**: Use the `LANGFUSE_INIT_USER_...` variables in `.env` to provision the initial Admin account automatically.

## Connect DNO Crawler / Applications

In your application (e.g., DNO Crawler), set these environment variables:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...  # Get from Langfuse UI (Project Settings)
LANGFUSE_SECRET_KEY=sk-lf-...  # Get from Langfuse UI (Project Settings)
LANGFUSE_HOST=https://langfuse.kylehub.dev
```

## Storage Architecture

*   **Metadata & Text Logs**: Stored in **Postgres** & **Clickhouse** (on fast NVMe storage).
*   **Blobs (PDFs, Images)**: Stored in **MinIO** (can be mapped to bulk storage, e.g., `/mnt/bx11/langfuse_blobs`).
    *   This ensures fast dashboard performance while allowing cheap, unlimited storage for large artifacts.
