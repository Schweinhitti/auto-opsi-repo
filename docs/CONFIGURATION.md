# Configuration

[Back to the documentation index](README.md)

Docker Compose reads project settings from `.env`. Start with an exact copy of
the tracked example, then edit the copy:

```bash
cp -n .env.example .env
chmod 600 .env
```

Don't commit `.env` or tokens.

## Environment variables

These are the exact `.env.example` defaults:

| Variable | Default | Meaning and constraint |
|---|---:|---|
| `UPDATE_INTERVAL_SECONDS` | `21600` | Delay after a builder cycle. Must be an integer of at least `60`; smaller values are rejected. |
| `KEEP_VERSIONS` | `2` | Number of version and revision archives retained per product. Must be an integer of at least `1`. |
| `GITHUB_TOKEN` | empty | Optional GitHub token used only for requests to `api.github.com`. An empty value uses unauthenticated API limits. Use a token with no more access than required for the configured sources. |
| `ALLOW_CHANGED_CHECKSUM` | `false` | When set to the case-insensitive string `true`, permits a changed installer SHA256 for a known upstream version. Leave `false` unless the change has been investigated and explicitly accepted. `--force` doesn't bypass this check. |
| `MAX_DOWNLOAD_BYTES` | `2147483648` | Maximum bytes accepted for one installer, exactly 2 GiB by default. The value is parsed as an integer. Downloads over the limit fail. |
| `BUILDER_UID` | `1000` | Numeric UID used by `repo-builder`. It must be able to write `repository/`, `state/`, and `work/`. |
| `BUILDER_GID` | `1000` | Numeric GID used by `repo-builder`. It must match the writable directory ownership or permissions. |
| `HTTP_BIND_ADDRESS` | `0.0.0.0` | Host address for the nginx published port. The default exposes the port on every host interface. |
| `HTTP_PORT` | `8088` | Host port mapped to nginx port 80. Select an unused port permitted by the host firewall. |
| `OPSI_BASE_IMAGE` | `uibmz/opsi-server:4.3` | Compose declares this builder argument, but the current `builder/Dockerfile` doesn't consume it and directly uses the same image reference. Changing this variable alone doesn't change the image. |
| `LOG_LEVEL` | `INFO` | Python builder logging level passed to `logging.basicConfig`. Use a level recognized by Python logging, such as `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |

Compose also sets internal paths that aren't operator settings:
`REPO_ROOT=/data` and `CATALOG_PATH=/app/catalog/packages.yaml`.

## Directory ownership

The builder container runs as `BUILDER_UID:BUILDER_GID`. Its three writable bind
mounts are:

| Host path | Container path | Contents |
|---|---|---|
| `repository/` | `/data/repository` | Published archives, sidecars, and repository metadata |
| `state/` | `/data/state` | Package state, historical checksums, lock, and last-run summary |
| `work/` | `/data/work` | Temporary downloads and build data |

Create and assign them with numeric IDs that match `.env`:

```bash
mkdir -p repository state work
chown -R BUILDER_UID:BUILDER_GID repository state work
```

Replace the placeholders before running the command. `catalog/` is mounted
read-only into the builder, and `repository/` is mounted read-only into nginx.

## Applying changes

First validate the rendered Compose model:

```bash
docker compose config --quiet
```

Environment changes aren't injected into an existing container. Recreate the
affected services:

```bash
docker compose up -d
```

Compose recreates a service when its effective configuration changed. Use
`docker compose up -d --force-recreate` when an explicit recreation is needed.
Rebuild the builder after project source or Dockerfile changes:

```bash
docker compose build --pull repo-builder
docker compose up -d repo-builder
```

`OPSI_BASE_IMAGE` is not currently an effective override because the Dockerfile
doesn't declare or use the Compose build argument. To change the base image,
review and edit `builder/Dockerfile`, then rebuild. Don't assume that changing
only `.env` selected a different OPSI tooling image.

The catalog is bind-mounted read-only and loaded at the start of each builder
cycle, so a catalog edit doesn't require an image rebuild. It is seen by the
next cycle or one-shot run.

Changing `UPDATE_INTERVAL_SECONDS` restarts the wait schedule only when the
builder container is recreated. Changing `BUILDER_UID` or `BUILDER_GID` also
requires matching host ownership before recreation. Changing the bind address
or port recreates `repo-web`; update firewall rules and OPSI integration URLs at
the same time.

## Private CA trust

The builder verifies TLS by default and accepts only credential-free HTTPS
upstream URLs. There is no insecure TLS bypass setting. To trust a private CA,
create `compose.override.yaml` and mount a PEM bundle read-only:

```yaml
services:
  repo-builder:
    environment:
      REQUESTS_CA_BUNDLE: /certs/ca-bundle.pem
    volumes:
      - ./certs/ca-bundle.pem:/certs/ca-bundle.pem:ro
```

The bundle must contain every trust root needed for the configured upstream
sites, not only the private root. Validate and recreate the builder:

```bash
docker compose config --quiet
docker compose up -d repo-builder
docker compose logs --tail=50 repo-builder
```

## Network exposure

The default `HTTP_BIND_ADDRESS=0.0.0.0` and `HTTP_PORT=8088` publish an
unauthenticated plain-HTTP endpoint on every host interface. The nginx service
allows GET and HEAD and rejects other methods, but that isn't authentication or
transport security. Restrict exposure to trusted systems or add an authenticated
HTTPS reverse proxy. See [Security](SECURITY.md) and [Integration](INTEGRATION.md).
