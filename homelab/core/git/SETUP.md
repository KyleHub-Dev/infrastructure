# KyleHub Git

## Status: prepared, NOT deployed

This stack exists in the repo but is intentionally not brought up.
The structural refactor (container prefixes, attachment to
`homelab-core-edge`, removal of the per-stack Newt) was applied so
the stack is drop-in deployable later, but the unblocking conditions
below are still open.

The concern is operational coupling: if the homelab or wider infra
has to move, the primary source forge would move with it. That makes
the Git host a bottleneck for recovering or rebuilding the rest of
the infrastructure. GitHub does not have that problem because the
repositories are reachable from outside the homelab regardless of
local infra state.

Current direction:

- Keep GitHub as the practical primary home for repos that are tied
  to infrastructure recovery, private work, or broad ecosystem
  expectations.
- Use Codeberg for new FOSS projects where the project is truly free
  software and the community/non-profit forge alignment matters.
- Do not self-host Forgejo as the canonical source of truth unless
  there is a stronger reason than dissatisfaction with GitHub's UX
  or ownership.

If this stack is revisited later, solve these first:

- Offsite backups and tested restores.
- A bootstrap path that does not depend on the Forgejo instance itself.
- Clear rules for which repos are canonical here versus mirrored elsewhere.
- External SSH/HTTPS access that works during partial infra failure.

For now, Codeberg for new FOSS plus GitHub for continuity is the
simpler and lower-risk path.

---

This stack runs Forgejo and is wired to the central Pangolin Newt in
`homelab/core/_edge` (when deployed).

## Why this shape

Forgejo's official Docker/OCI documentation publishes versioned container images such as `codeberg.org/forgejo/forgejo:15`; there is intentionally no `latest` tag because major upgrades require manual verification. The docs also show Postgres as the durable database option and note that the first registered user becomes the initial administrator.

This stack uses:

- `codeberg.org/forgejo/forgejo:15-rootless`
- `postgres:16-alpine`
- `fosrl/newt:latest`
- named Podman volumes for Forgejo and Postgres data

Sources:

- https://forgejo.org/docs/latest/admin/installation/
- https://forgejo.org/docs/latest/admin/installation/docker/
- https://forgejo.org/faq/

## First run

1. Copy the env template:

   ```sh
   cp .env.example .env
   ```

2. Edit `.env` and set at least:

   ```sh
   POSTGRES_PASSWORD=...
   ```

   Pangolin / Newt credentials are NOT in this stack any more. The
   single Newt in `homelab/core/_edge` handles tunnelling for the
   whole core zone - bring it up first per `_edge/README.md`.

3. Start the stack:

   ```sh
   podman compose up -d
   ```

   `podman compose` uses the installed compose provider. On this host that is `podman-compose 1.5.0`, so this is equivalent:

   ```sh
   podman-compose up -d
   ```

4. In Pangolin, under the existing `Homelab Core` Site (created by
   `homelab/core/_edge`), add an HTTPS resource:

   ```text
   git.kylehub.dev -> git-forgejo:3000
   ```

   `git-forgejo` is reachable because the compose attaches it to
   the `homelab-core-edge` external network alongside `core-newt`.

5. Open `https://git.kylehub.dev`. If the install page appears, keep the Postgres settings from `.env`, verify the public URL is `https://git.kylehub.dev/`, and submit the install form.

6. Create your user account.

The first user that registers becomes the site administrator. After that account exists, set this in `.env` and restart:

```sh
FORGEJO_DISABLE_REGISTRATION=true
podman compose up -d
```

## Creating organizations

As your admin user:

1. Click the `+` menu in the top navigation.
2. Choose `New Organization`.
3. Pick the organization name, visibility, and membership defaults.
4. Create teams inside the organization if you want GitHub-like owner/member/reviewer separation.

Recommended org layout for your use case:

- `KyleHub` for public or canonical personal projects
- `homelab` for infrastructure repositories
- `archive` for imported or read-only mirrors

Forgejo does not have GitHub-style nested organizations or groups, so use organization names and repository topics deliberately.

## GitHub-like UI

Forgejo will never be exactly GitHub, but you can make it feel closer than Codeberg:

- Use the `gitea-auto`, `gitea-light`, or `gitea-dark` theme from user settings.
- Set `FORGEJO_DEFAULT_THEME=gitea-auto` if you want new users to start there.
- Keep the default repository layout; it is closer to GitHub than Codeberg's branded instance.

The stack currently enables both Forgejo and Gitea theme families:

```text
forgejo-auto,forgejo-light,forgejo-dark,gitea-auto,gitea-light,gitea-dark
```

Deeper CSS/template customization is possible through Forgejo's custom path, but templates can break across upgrades. Start with built-in themes first.

Customization docs:

- https://forgejo.org/docs/latest/contributor/customization/

## Git access

HTTPS Git works through the Pangolin HTTPS route:

```sh
git clone https://git.kylehub.dev/<owner>/<repo>.git
```

SSH is enabled inside the Podman network on port `2222`. To make SSH clone URLs work, either:

- expose `forgejo:2222` through Pangolin TCP routing if your Pangolin setup supports it, or
- uncomment the `2222:2222/tcp` port mapping in `compose.yaml` and forward `git.kylehub.dev:2222` to the host.

Then clone with:

```sh
git clone ssh://git@git.kylehub.dev:2222/<owner>/<repo>.git
```

## Mirroring to GitHub

For public projects where GitHub should be a mirror:

1. Create an empty GitHub repository.
2. In Forgejo, open the repository settings.
3. Add a push mirror to `https://github.com/<user-or-org>/<repo>.git`.
4. Use a GitHub fine-grained token with write access to that repository.

Treat GitHub as read-only once mirroring is enabled. Push mirrors can overwrite the destination.

## Backups

Back up both named volumes:

- `git_forgejo-data`
- `git_postgres-data`

For a real restore test, stop the stack, restore both volumes together, start the stack, and verify login plus repository clone.

## Podman compatibility

Validated on this host with:

```text
podman version 5.8.2
podman-compose version 1.5.0
```

Validation command:

```sh
podman-compose --env-file .env.example config
```

The stack uses named volumes instead of host bind mounts for Forgejo and Postgres data, which avoids most SELinux label and rootless ownership issues. The Forgejo container uses the rootless image and runs as `${FORGEJO_UID:-1000}:${FORGEJO_GID:-1000}`.

## CI runners

This stack intentionally does not start a Forgejo Actions runner yet.

Runners execute workflow code from repositories. Add one later with a separate trust boundary, ideally on a different host or VM. Forgejo supports runner registration at system, organization, user, and repository scope; org or repo scope is usually safer than one global runner for everything.

Runner docs:

- https://forgejo.org/docs/next/admin/actions/registration/
