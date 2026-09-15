# Architecture

[Back to the documentation index](README.md)

This page is the maintainer reference for module ownership, data flow, persistence,
publication, and failure boundaries. For commands and recovery procedures, see
[Operations](OPERATIONS.md). For failure lookup, see
[Troubleshooting](TROUBLESHOOTING.md). Security assumptions are in
[Security](SECURITY.md). The [project README](../README.md) remains the overview.

## System boundary

The project has two containers and one external consumer:

1. `repo-builder` reads the trusted catalog, queries upstream release services,
   downloads installers, builds OPSI archives, and writes repository and state data.
2. `repo-web` mounts only `repository/`, read-only, and serves it through nginx.
3. An existing OPSI server reads the HTTP repository and imports packages as a
   separate administrative operation. The builder never changes that server or
   schedules client deployments.

The main flow is:

```text
catalog/packages.yaml                upstream HTTPS services
          |                                    |
          +----------> repo-builder <----------+
                             |
                  work/ temporary files
                             |
                  official opsi-cli tools
                             |
                  repository/ + state/
                             |
                  repo-web, GET and HEAD
                             |
                    existing OPSI server
                             |
                       Windows clients
```

Repository building and OPSI depot import are deliberately independent. See
[Integration](INTEGRATION.md) for the import boundary and the `autoSetup = false`
deployment safeguard.

## Module ownership

| Path | Owns | Does not own |
|---|---|---|
| `builder/builder/main.py` | CLI modes, cycle scheduling, writer lock, per-product orchestration, summaries, last-run status | Source-specific parsing or OPSI archive format |
| `builder/builder/catalog.py` | Catalog schema and cross-field validation | Whether a vendor release is current |
| `builder/builder/sources/` | Upstream metadata resolution into a release version, URL, checksum, and optional detection version | Download publication or package retention |
| `builder/builder/download.py` | HTTPS policy, redirect checks, limits, retries, payload SHA256, file format checks, advisory signature status, safe ZIP extraction | Trusting unknown signer identities or malware scanning |
| `builder/builder/versions.py` | PEP 440 ordering and conversion to OPSI-compatible versions | Product revision policy |
| `builder/builder/opsi.py` | Template rendering, source tree generation, official `opsi-cli` invocation, archive round-trip validation | HTTP serving or state history |
| `builder/builder/repository.py` | Inventory, per-file publication, metadata staging, and retention | Whole-repository transactions |
| `builder/builder/state.py` | Atomic JSON replacement and state schema migration | Repository artifact validation |
| `builder/builder/repackage.py` | Offline packaging-revision recovery from a verified retained archive | Discovery of new upstream releases |
| `scripts/audit-repository.py` | Read-only checks of published archives, sidecars, provenance, and JSON metadata references | Repair or upstream authenticity validation |
| `nginx/default.conf` | Static repository HTTP behavior | Authentication or TLS termination |
| `docker-compose.yml` | Runtime identity, mounts, limits, healthcheck, logging, and host port | Host firewall and external reverse proxy policy |
| `helper/*.sh` | Operator shortcuts for build, test, start, status, logs, dry run, and container cleanup | Package or state mutation beyond the wrapped Compose commands |

## Builder cycle

`builder.main.main()` creates `state/`, `work/`, and `repository/` for normal runs,
then starts either one cycle or a periodic loop. A normal writer opens
`state/builder.lock` and requests a nonblocking exclusive `flock`. Under that lock,
it removes owned crash leftovers from `work/` before calling `run()`.

`run()` performs these steps:

1. Load and validate every catalog entry before product processing starts.
2. Read `state/packages.json`, or initialize state schema 2 when it is absent.
3. Reconstruct retained checksum evidence from every
   `*.opsi.provenance.json` sidecar. Conflicting evidence stops the cycle.
4. Process enabled selected products in catalog order.
5. Resolve upstream metadata and normalize the version.
6. Compare the desired version and package revision with repository inventory.
   Downgrades are blocked and reported as warnings.
7. When a provenance sidecar exists, verify its upstream version and archive SHA256 before
   skipping an existing artifact. A normalized-version collision is an error. An existing
   archive without provenance is currently skipped unless forced; audit and restore its
   evidence rather than treating that skip as an integrity check.
8. Download into a product-specific temporary directory under `work/`. Validate
   HTTPS and redirects, size and time limits, published SHA256 when available,
   immutable historical SHA256, and installer format.
9. Render `OPSI/control.toml`, setup and uninstall scripts, runtime helpers,
   catalog-derived `config.json`, bundled installer, and provenance.
10. Run `opsi-cli package make`, extract the resulting archive again, compare
    control fields and bundled installer bytes, and verify the MD5 sidecar.
11. Publish the archive and sidecars, then atomically update package state.
12. Continue with the next product even if the current product failed.
13. After all selected products, generate repository metadata while excluding
    retention candidates. Only after metadata succeeds are old packages and their
    sidecars removed.
14. Atomically write `state/packages.json` and `state/last-run.json`, then print
    `Updated`, `Unchanged`, `Failed`, `Warnings`, and `Disabled` sections.

The `try` block around each enabled product is the product failure boundary. A bad
release feed or installer does not prevent other products from running. Catalog
loading, provenance reconstruction, invalid global settings, lock acquisition, and
unexpected cycle setup errors occur outside that boundary and can fail the cycle.
Metadata and retention have their own final failure boundary. A metadata failure
leaves old versions in place and records `Failed: repository`.

## Cycle modes and exit status

| Invocation | Behavior | Writes | Exit status |
|---|---|---|---|
| Service default | Runs immediately, then waits `UPDATE_INTERVAL_SECONDS` after each completed cycle | Repository, state, work, lock | Runs until stopped; product failures are logged and retried next cycle |
| `--once` | Runs one normal cycle | Repository, state, work, lock | `0` no failures, `1` any product or repository failure, `2` lock held |
| `--dry-run` | Resolves metadata and expected changes once | No package, state, work directory, or lock writes | `0` no failures, `1` failure |
| `--product ID` | Selects one product | Depends on mode | Same as selected mode |
| `--force ID` | Rebuilds that product if selected during the cycle | Normal writes | Does not bypass checksum protection |
| `--force-all` | Rebuilds all selected products | Normal writes | Does not bypass checksum protection |

`--force ID` is a rebuild set, not a product selector. To rebuild only one product,
pass both `--product ID --force ID`.

## Persistent and temporary data

| Directory or file | Content | Backup policy |
|---|---|---|
| `catalog/` | Trusted product policy and executable overrides | Required |
| `repository/` | Published archives, sidecars, provenance, and OPSI metadata | Required |
| `state/packages.json` | Latest product records, historical installer checksums, accepted checksum override history | Required |
| `state/last-run.json` | Latest completed non-dry-run timestamp and summary | Useful operational record |
| `state/builder.lock` | Stable inode used for advisory writer serialization | Recreated as needed, never use deletion to break a live lock |
| `work/` | Downloads, source trees, extracted verification trees, metadata staging, OPSI runtime cache | Not required |
| `.env` and local Compose or CA files | Deployment settings and secrets | Required, protected storage |

State writes use a sibling temporary file, `fsync`, `os.replace`, and a directory
`fsync`. This makes each JSON replacement atomic on the filesystem. It does not
make repository and state changes one transaction.

## Artifact and HTTP contract

For an archive named `PRODUCT_VERSION-REVISION.opsi`, publication includes:

* The `.opsi` archive.
* `.opsi.md5`, generated and checked against the archive.
* `.opsi.zsync`, generated by OPSI tooling and required to exist.
* `.opsi.provenance.json`, containing source URL, installer SHA256, archive SHA256,
  sizes, versions, timestamps, and advisory signature status.

OPSI tooling also generates repository metadata, including `packages.json` and
`packages.msgpack.zstd`. Consumers must use the generated metadata contract rather
than infer current versions from filenames. Older retained archives can remain
downloadable while metadata advertises the current package.

nginx serves the repository root with directory listing enabled. Only `GET` and
`HEAD` are allowed. Unknown paths return `404`, dot-prefixed staging files are
denied, and the default content type is `application/octet-stream`. There are no
application API endpoints, upload methods, or authentication handlers in this
stack.

## Atomicity and retention ordering

Publication copies each sidecar and archive to a hidden file, calls `fsync`, and
atomically replaces its visible target. Sidecars are published before the archive.
Metadata is generated in an unserved directory using hard links where possible and
copies across filesystems. Each metadata file is then replaced separately.

Atomicity is per file only. There is no repository-wide snapshot transaction. A
reader can briefly see old metadata with a newly published archive, or a mix of old
and new metadata files while replacements occur. Existing version URLs stay valid
until retention finishes, which reduces the impact for active readers.

Retention computes the newest `KEEP_VERSIONS` version and revision pairs for each
product. It generates metadata as if older candidates were absent, publishes that
metadata successfully, and only then deletes each old archive with its MD5, zsync,
and provenance sidecars. A metadata failure prevents deletion.

## Maintainer change map

* Change catalog fields or validation together in `catalog/packages.yaml` and
  `builder/builder/catalog.py`.
* Add or change source protocols in `builder/builder/sources/`, while keeping
  download policy in `download.py`.
* Change generated client behavior in templates or trusted product overrides, then
  increase the package revision and run Windows acceptance tests.
* Change publication or retention only in `repository.py`, preserving metadata
  before deletion and the per-file atomic publication rule.
* Change state shape through `state.py` migration logic. Never discard checksum
  history as a migration shortcut.

See [Package authoring](PACKAGE_AUTHORING.md) for recipe changes,
[Development](DEVELOPMENT.md) for code checks, [Validation](VALIDATION.md) for
tested scope, and [Sources](SOURCES.md) for OPSI and upstream references.
