# Operations

[Back to the documentation index](README.md)

This runbook covers routine operation, monitoring, audit, backup, restore, update,
and safe recovery. Read [Architecture](ARCHITECTURE.md) for the data flow and
[Security](SECURITY.md) before exposing the service. Use
[Troubleshooting](TROUBLESHOOTING.md) when a command fails. The
[project README](../README.md) contains installation context. New operators should
start with [Getting started](GETTING_STARTED.md), and environment details belong in
[Configuration](CONFIGURATION.md).

## Operating invariants

Keep these rules true during every administrative action:

* Only one normal writer may run. Dry runs are read-only and do not take the lock.
* Never delete `state/` to clear an error or remove `builder.lock` to defeat a live
  lock.
* Never disable TLS verification or accept a checksum change without investigation.
* Preserve the existing repository and state before a repair, update, or override.
* Stop the periodic builder before a manual normal build or offline repackage.
* Treat nginx health and builder freshness as separate signals.
* Do not claim a filesystem backup is consistent unless the builder was stopped or
  the filesystem supplied a consistent snapshot of all required paths.

## Initial start

Create the writable directories, align their ownership with the configured builder
identity, validate Compose, and start the stack:

```bash
cd /path/to/opsi-auto-repo
cp -n .env.example .env
mkdir -p repository state work
id -u
id -g
# Set BUILDER_UID and BUILDER_GID in .env to the directory owners.
docker compose config --quiet
docker compose up -d --build
```

`./helper/run.sh` wraps directory creation and `docker compose up -d`, but inspect
`.env` and directory ownership yourself. Its attempted `chown` is allowed to fail,
so a successful helper exit does not prove the builder can write its mounts.

The first builder cycle starts immediately. Confirm both service and build state:

```bash
docker compose ps
docker compose logs --tail=100 repo-builder
curl -f http://HOST-IP:PORT/
./helper/status.sh
```

The nginx healthcheck only requests `/` from inside `repo-web`. It proves nginx can
serve its mount, not that the latest builder cycle succeeded or that the OPSI server
can reach the host address.

## Run modes

### Periodic service

`docker compose up -d repo-builder` runs one cycle immediately, then waits the
configured interval after each cycle completes. The default is 21,600 seconds.
`UPDATE_INTERVAL_SECONDS` must be at least 60. Failed products are listed and tried
again on the next cycle.

### Dry run

```bash
docker compose run --rm repo-builder --dry-run
docker compose run --rm repo-builder --dry-run --product auto-firefox
./helper/dry-run.sh auto-firefox
```

A dry run fetches release metadata and checksum documents and reports proposed
changes. It does not download installers, build packages, write state, create data
directories, or acquire the writer lock. It can overlap a normal cycle because it
does not mutate the managed data.

### One normal cycle

For an all-product manual cycle, prevent overlap with the periodic service:

```bash
docker compose stop repo-builder
docker compose run --rm repo-builder --once
docker compose up -d repo-builder
```

For one product:

```bash
docker compose stop repo-builder
docker compose run --rm repo-builder --once --product auto-firefox
docker compose up -d repo-builder
```

Normal one-shot exit codes are:

| Code | Meaning | Operator response |
|---|---|---|
| `0` | Selected cycle and repository metadata completed without failures | Review warnings, then continue |
| `1` | At least one product or repository operation failed | Read the printed `Failed` section and logs; other products may have succeeded |
| `2` | Another normal builder holds the nonblocking file lock | Wait, or stop the known periodic service and retry after it exits |

An invalid CLI selection or global cycle exception also exits nonzero and is logged.

### Force rebuild

```bash
docker compose stop repo-builder
docker compose run --rm repo-builder --once \
  --product auto-firefox --force auto-firefox
docker compose up -d repo-builder
```

`--force` requests rebuilding an existing package. It does not bypass source
checks, installer checks, published archive validation, or immutable checksum
history. `--force auto-firefox` alone does not select only Firefox. `--force-all`
rebuilds all products selected by the cycle.

If deployment logic changed without an upstream version change, increase
`package_revision` instead of replacing the same archive identity. This preserves a
clear upgrade path and avoids stale client or proxy caches.

## Manual overlap procedure

Use this sequence whenever a command can write `repository/`, `state/`, or `work/`:

1. Run `docker compose stop repo-builder`.
2. Confirm `docker compose ps` shows the service stopped.
3. Start the manual `--once` or offline repackage command.
4. If it exits `2`, another writer exists. Find the operator or process that owns
   that run and wait for it. Do not remove the lock file.
5. Inspect the command summary and `state/last-run.json` where applicable.
6. Restart with `docker compose up -d repo-builder`.

The lock is an advisory `flock` on `state/builder.lock`. The filename can remain
after a process exits; that is normal. Lock ownership belongs to an open file
descriptor, not to the mere presence of the file.

## Monitor and alert

### Service and HTTP signals

```bash
docker compose ps
curl -fI http://HOST-IP:PORT/packages.json
./helper/logs.sh builder
./helper/logs.sh web
```

The HTTP surface permits `GET` and `HEAD`. A successful request proves the selected
file is served. Test from the OPSI container or the same network zone as the OPSI
server, not only from the repository host.

### Last-run signal

Every completed non-dry-run cycle writes `state/last-run.json` with:

* `finished`, an ISO 8601 UTC timestamp.
* `summary.Updated`.
* `summary.Unchanged`.
* `summary.Failed`.
* `summary.Warnings`.
* `summary.Disabled`.

`./helper/status.sh` prints list counts. For monitoring, alert when `finished` is
older than the expected cycle duration plus local tolerance, when `Failed` is not
empty, or when a warning persists unexpectedly. A healthy nginx container with a
stale or failed last run is degraded service.

Per-product `last_checked` and successful provenance are stored in
`state/packages.json`. Use them for investigation, but use `last-run.json` as the
cycle completion record. A dry run never updates either file.

Docker uses the `json-file` driver with three 10 MB files per service. Export logs
to the site's normal log system if retention or alerting must exceed that local
window.

## Audit published data

Run the supplied read-only audit from the project root while `packages.json` is
present:

```bash
python3 scripts/audit-repository.py
```

It checks every published `.opsi` archive against `package_sha256` in provenance,
checks archive MD5 against `.md5`, requires nonempty `.zsync`, and checks that every
`packages.json` entry names an existing file with the recorded size, product ID,
and version identity. A successful result prints the archive and metadata product
counts.

The audit does not verify upstream availability, signer identity, malware status,
Windows install behavior, every metadata format, or a whole-repository snapshot.
Run it after restore, storage incidents, and controlled updates. If it fails, stop
the builder, preserve the affected files and state, and follow
[Troubleshooting](TROUBLESHOOTING.md#published-package-or-audit-integrity-failure).

## Retention and disk use

`KEEP_VERSIONS` must be at least 1 and defaults to 2. Retention sorts semantic
product versions and package revisions, then keeps the newest configured count per
product. The sequence is safety-critical:

1. Build metadata in unserved `work/`, excluding candidates for deletion.
2. Atomically replace each generated metadata file in `repository/`.
3. Delete each obsolete archive and its MD5, zsync, and provenance files.

If metadata generation fails, deletion does not run. Publication and metadata
replacement are atomic per file, not across the repository. Do not run external
cleanup against `repository/`, and do not manually rename managed archives.

Plan disk capacity for retained packages plus concurrent downloads, generated
source trees, extracted archive verification, metadata staging, and cross-filesystem
copies. `work/` is cleaned for known crash leftovers at the next locked normal
startup.

## Changed checksum response

`ALLOW_CHANGED_CHECKSUM=false` is the normal setting. On a changed checksum:

1. Stop the periodic builder.
2. Preserve `catalog/`, `repository/`, `state/`, `.env`, and the failure logs.
3. Confirm the upstream version and release through official vendor channels.
4. Determine whether the vendor legitimately replaced the installer or the source
   path, account, DNS, CDN, or content may be compromised.
5. Prefer increasing `package_revision` while retaining the known-good archive.
6. Only after explicit approval, run one isolated build with
   `-e ALLOW_CHANGED_CHECKSUM=true`. Do not make the override a standing default.
7. Audit the repository and perform Windows acceptance testing before depot import.
8. Restart the periodic builder with checksum override disabled.

An accepted override records both hashes in `state/packages.json` checksum override
history. `--force` alone cannot approve it. If checksum evidence is missing, restore
state from backup. Never erase state to make the comparison disappear.

## Offline packaging-revision recovery

Use offline repackage only when upstream metadata is unavailable and trusted
packaging logic changed for an existing version:

1. Back up catalog, repository, and state.
2. Increase the product's `package_revision`.
3. Stop the periodic builder.
4. Run:

```bash
docker compose run --rm --entrypoint python repo-builder \
  -m builder.repackage auto-git
```

5. Read the explicit `upstream was NOT checked` result.
6. Run `python3 scripts/audit-repository.py` and Windows acceptance tests.
7. Restart `docker compose up -d repo-builder`.

The command takes the normal writer lock, selects the newest retained archive,
checks its recorded archive SHA256, extracts it, checks the bundled installer
against recorded SHA256, requires a higher revision, rebuilds and validates the
archive, publishes it, updates state, and applies normal retention. It cannot claim
or discover a new software release. Missing required detection metadata requires a
normal online build.

## Backup

Back up these items together:

* `catalog/`, including trusted overrides.
* `repository/`.
* `state/`.
* `.env`.
* Custom CA bundles and Compose override files.
* The project source when locally customized.

`work/` is disposable and should not be restored. Use one of two consistency
methods:

1. Stop `repo-builder`, confirm it has exited, take the backup, then restart it.
2. Take one filesystem snapshot that consistently captures all required paths.

Preserve ownership, modes, timestamps, and secret-file protection. Keep more than
one generation and test restores away from production. The project offers per-file
atomic updates, not a repository-wide snapshot, so copying live files one by one is
not a consistent backup method.

## Restore

1. Keep the builder stopped.
2. Restore `catalog/`, `repository/`, `state/`, `.env`, local CA data, and Compose
   overrides from the same backup generation.
3. Set directory ownership to `BUILDER_UID:BUILDER_GID`. Avoid world-writable modes.
4. Validate configuration with `docker compose config --quiet`.
5. Run `python3 scripts/audit-repository.py`.
6. Run `docker compose run --rm repo-builder --dry-run`.
7. Start the stack and inspect the first cycle summary.
8. Test `packages.json` from the OPSI server network, then list repository products
   from OPSI as documented in [Integration](INTEGRATION.md).

If the audit fails, do not let a normal cycle prune or replace evidence. Restore a
known-good generation or investigate the preserved mismatch. Losing state removes
history for already-pruned installers. Retained provenance can reconstruct only the
versions still present.

## Controlled update

Before updating, review changes to the catalog, templates, builder dependencies,
base images, and OPSI CLI behavior. Increase package revisions for packaging or
client-script changes. Then:

```bash
cd /path/to/opsi-auto-repo
docker compose stop repo-builder
# Take a consistent backup here.
docker compose build --pull repo-builder
docker compose pull repo-web
docker compose config --quiet
docker compose run --rm repo-web nginx -t
docker compose run --rm repo-builder --dry-run
docker compose up -d
docker compose logs -f repo-builder
```

Pin reviewed image digests for controlled production use. After template,
installer-type, detection, or uninstall changes, test install, second setup,
upgrade, and uninstall on a representative managed Windows VM by following
[Windows client acceptance](CLIENT_ACCEPTANCE.md) before broad import.

`./helper/build.sh` attempts `docker compose build --pull repo-builder repo-web`, but
`repo-web` has an `image` and no Compose build context. Use the explicit builder build and
web pull commands in this runbook instead. `./helper/test.sh` creates the local virtual
environment, installs test dependencies, compiles the builder, and runs unit tests; it does
not run Ruff or Compose validation. `./helper/cleanup.sh` stops and removes project
containers without deleting bind-mounted data; do not follow its commented volume removal
example during an incident.
