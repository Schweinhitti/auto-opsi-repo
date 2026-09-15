# Getting Started

[Back to the documentation index](README.md)

This guide takes a Linux operator from a new checkout to a validated first build.
It doesn't connect the repository to an OPSI server. Complete that separate step
with [Integration](INTEGRATION.md) after the repository is healthy.

## Prerequisites

Provide all of the following:

* A Linux host with Docker Engine and the modern Compose plugin, invoked as
  `docker compose`.
* Permission to build images, pull images, create containers, and manage bind
  mounts. Access to Docker is effectively host-level access and should be
  restricted.
* Outbound DNS and HTTPS access on TCP port 443 to the official source hosts in
  `catalog/packages.yaml`, plus Docker registry access for image pulls. The
  builder accepts credential-free HTTPS upstream URLs and checks configured host
  allowlists across redirects.
* An inbound TCP port for nginx. The default is `8088`. The OPSI server or its
  container must be able to reach the selected host address and port. Host
  loopback isn't suitable when OPSI runs in a separate container.
* At least 15 to 25 GB for the initial catalog, retained package versions, and
  temporary build copies. Actual use depends on enabled products, installer
  sizes, and `KEEP_VERSIONS`.
* Writable local directories for `repository/`, `state/`, and `work/`.

Linux amd64 and arm64 hosts can build the current Windows x64 packages. Windows
x64 package output doesn't mean the recipes have passed Windows acceptance.
Run the checks in [Client Acceptance](CLIENT_ACCEPTANCE.md) before broad use.

## 1. Create the local configuration

From the repository root:

```bash
cp -n .env.example .env
mkdir -p repository state work
id -u
id -g
```

Set `BUILDER_UID` and `BUILDER_GID` in `.env` to the numeric owner and group of
the three writable directories. The Compose default is `1000:1000`, but it is
correct only when those IDs own the directories. Apply the selected IDs:

```bash
chown -R BUILDER_UID:BUILDER_GID repository state work
chmod 600 .env
```

Replace the placeholders with numbers, for example `1000:1000`. Don't make the
directories world-writable to hide an ownership mismatch. The builder runs as
the configured UID and GID, writes packages to `repository/`, persistent records
to `state/`, and temporary data to `work/`.

Review every setting in [Configuration](CONFIGURATION.md), especially
`HTTP_BIND_ADDRESS`, `HTTP_PORT`, and `GITHUB_TOKEN`.

## 2. Check Compose and fetch the images

```bash
docker compose config --quiet
docker compose build --pull repo-builder
docker compose pull repo-web
```

Pass conditions:

* `docker compose config --quiet` exits with status 0.
* The builder image finishes building from `uibmz/opsi-server:4.3`.
* The `nginx:stable-alpine` image pulls successfully.

## 3. Run the first dry run

Keep the periodic service stopped while checking upstream metadata:

```bash
docker compose run --rm repo-builder --dry-run
```

You can limit the check to one OPSI product ID:

```bash
docker compose run --rm repo-builder --dry-run --product auto-firefox
```

A dry run resolves releases and reports proposed work without downloading
installers or writing package, lock, or state files. It prints `Updated:`,
`Unchanged:`, `Failed:`, `Warnings:`, and `Disabled:` sections.

The dry run passes when the command exits with status 0 and `Failed:` has no
entries. Warnings and disabled products need review, but aren't counted as build
failures. A GitHub rate-limit warning can require a token or another cycle.

## 4. Start the first normal build

```bash
docker compose up -d
docker compose logs -f repo-builder
```

The long-running builder starts a normal cycle immediately, then waits
`UPDATE_INTERVAL_SECONDS` after each cycle. Press `Ctrl+C` to stop following the
logs; this doesn't stop the container.

A normal cycle exits with status 1 when a selected product or repository
metadata operation failed. A separate one-shot writer exits with status 2 when
another builder owns the lock. The periodic container remains running after a
failed cycle and tries again after the configured interval.

The first builder cycle passes when all of these are true:

* The final summary contains no entries under `Failed:`.
* Expected products appear under `Updated:` or `Unchanged:`.
* `state/last-run.json` exists and its `finished` value represents the completed
  normal cycle.
* Repository metadata and any built `.opsi` files appear under `repository/`.

Don't start `docker compose run --rm repo-builder --once` while the periodic
builder is active. Wait for the cycle, or stop it before a manual run:

```bash
docker compose stop repo-builder
docker compose run --rm repo-builder --once
docker compose up -d repo-builder
```

## 5. Verify builder and web health

```bash
docker compose ps
./helper/status.sh
curl -f http://HOST-IP:HTTP_PORT/
docker compose logs --tail=50 repo-builder
docker compose logs --tail=50 repo-web
```

Replace `HOST-IP` and `HTTP_PORT` with the reachable address and configured port.
The complete happy path passes when:

* `repo-builder` is running.
* `repo-web` is running and reported healthy by `docker compose ps`.
* `curl -f` exits with status 0 and returns the repository listing.
* `./helper/status.sh` can parse `state/last-run.json`, and its `Failed` count is
  zero.
* Recent builder logs show a completed summary rather than an active exception.

Only `repo-web` has a Compose healthcheck. `helper/status.sh` can therefore show
`repo-builder: unknown`; use the last-run summary and builder logs for builder
health. A healthy nginx container proves only that HTTP works. It doesn't prove
that upstream resolution, download, packaging, or metadata generation succeeded.

## About `helper/run.sh`

`./helper/run.sh` creates missing data directories, copies `.env.example` when
`.env` is absent, runs `docker compose up -d`, and prints status. It is a
convenience shortcut, not the preferred first-install procedure above.

Be aware of these source-level behaviors:

* The script doesn't source `.env` into its own shell. Its `chown` and displayed
  port use exported shell variables or their `1000:1000` and `8088` fallbacks,
  which can differ from values Compose reads from `.env`.
* Its ownership adjustment suppresses `chown` errors. Check ownership yourself.
* It runs `docker compose up -d` without `--build`, so it doesn't force a rebuild
  after source changes.
* Its nginx wait pipeline appends the container ID as another `wget` argument.
  Treat its ready message or 30-second warning as advisory and verify with
  `docker compose ps` plus `curl`.

## Security before integration

By default, nginx binds `0.0.0.0:8088`, serves plain HTTP, and has no
authentication. Limit the host firewall and bind address to the depot network.
Use an authenticated HTTPS reverse proxy when traffic crosses an untrusted
network. See [Security](SECURITY.md), then follow [Integration](INTEGRATION.md).
