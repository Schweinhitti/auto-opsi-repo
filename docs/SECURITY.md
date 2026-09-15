# Security

[Back to the documentation index](README.md)

This page defines the trust boundaries and security limits of the repository
stack. It is an operating model, not a claim that every upstream installer is safe
or legally redistributable. Pair it with [Operations](OPERATIONS.md),
[Troubleshooting](TROUBLESHOOTING.md), and the data flow in
[Architecture](ARCHITECTURE.md). See [Integration](INTEGRATION.md) for the separate
OPSI server boundary, [Configuration](CONFIGURATION.md) for deployment settings,
[Package authoring](PACKAGE_AUTHORING.md) for recipe review, and the
[project README](../README.md) for deployment context.

## Assets and security goals

Protect these assets:

* Catalog policy and product overrides, which become administrator-level client
  behavior.
* Installer and archive integrity evidence in `state/` and provenance sidecars.
* Published `.opsi` archives and OPSI-generated metadata.
* `GITHUB_TOKEN`, private CA material, `.env`, and local Compose overrides.
* Availability of retained known-good packages and metadata.
* The existing OPSI server and its decision to import or deploy packages.

The design aims to reject unexpected source locations and payload changes, keep
partial files out of the public namespace, isolate product failures, and keep the
web process unable to modify repository data. It does not promise malware-free
installers, trusted publisher identity, atomic snapshots, client deployment safety,
or redistribution rights.

## Trust boundaries

### Maintainer to catalog and overrides

`catalog/packages.yaml`, Jinja overrides, OPSI snippets, installer arguments, and
detection rules are trusted code and policy. Maintainers can direct downloads,
change packaged scripts, and affect administrator-level execution on Windows
clients. Catalog validation catches malformed structure and unsafe path traversal,
but it is not a sandbox for untrusted contributors.

Require review for source ownership, exact allowlists, silent install behavior,
detection, uninstall, package revision, and redistribution classification. Restrict
write access to the project and deployment host.

### Builder to upstream services

Upstream metadata and installer bytes are untrusted network input. `download.py`
accepts only credential-free HTTPS URLs on port 443, verifies certificates through
Requests, checks every redirect before following it, limits redirects to ten, and
enforces configured official host allowlists unless a catalog entry explicitly
disables hostname validation.

Metadata reads default to an 8 MiB limit. Installer reads use
`MAX_DOWNLOAD_BYTES`, default 2 GiB. Connections use 15-second connect and
90-second read timeouts. A complete stream is limited to 30 minutes. Retry policy
is bounded for 429 and selected 5xx responses, and interrupted installer bodies are
retried from the beginning rather than appended.

`disable_host_validation` still requires credential-free HTTPS, but it removes a
major pinning control. Use it only for a reviewed vendor that intentionally rotates
among official mirrors and cannot support a stable narrow allowlist. Never turn it
on as generic redirect recovery.

### Builder to GitHub

The optional `GITHUB_TOKEN` is added as a bearer token only when the current request
host is exactly `api.github.com`. Redirect requests are re-evaluated by hostname and
do not inherit that header. Use the narrowest read-only token possible, store it in
protected `.env` or the site's secret system, rotate it, and never print it in
diagnostics.

The token improves API limits. It does not add trust to release assets or permit
checksum exceptions.

### Builder to OPSI tooling

The builder invokes `opsi-cli` with argument arrays, no Linux shell, closed stdin,
checked exit status, and a one-hour timeout. The official OPSI CLI creates and
extracts archives and generates repository metadata. The builder then verifies
control identity, bundled installer bytes, archive MD5, and expected sidecars.

The configured OPSI base image is part of the software supply chain. Review updates
and pin tested digests for production. A detached PGP signature is not trusted
automatically because this project does not pin signer keys or implement a PGP
trust policy.

### Builder to persistent storage

The builder has write access to `repository/`, `state/`, and `work/`. Its container
root filesystem and catalog mount are read-only. `state/packages.json` carries
historical installer hashes that may outlive retained archives, so it is security
evidence, not disposable cache.

Only one normal writer is serialized with `flock`. Dry runs have no lock because
they do not write managed data. Per-file temporary copy, `fsync`, and `os.replace`
keep incomplete files hidden. This is not a repository-wide transaction. Backups
must stop the builder or use a consistent filesystem snapshot.

### Web server to repository consumers

`repo-web` sees `repository/` read-only. nginx allows only `GET` and `HEAD`, denies
dot-prefixed files, uses exact path lookup, and adds `X-Content-Type-Options:
nosniff`. It has no upload route, application API, authentication, or TLS in this
repository.

The default host bind is `0.0.0.0:8088`. Plain HTTP provides no confidentiality,
server authentication, or transport integrity against a network attacker. Bind to
the depot network and enforce host firewall policy, or place nginx behind an
authenticated HTTPS reverse proxy. Keep the backend unreachable from untrusted
networks when the proxy is the intended boundary.

At the proxy, allow only `GET` and `HEAD`, preserve exact paths, reject request
bodies, set suitable request and response limits, and avoid caching mutable URLs in
a way that can mix archives with sidecars. Use a trusted certificate chain and
enable certificate verification on OPSI. Do not solve HTTPS trust errors by turning
verification off.

### Repository to existing OPSI server

The OPSI server is an external administrative trust boundary. It pulls metadata and
packages only after separate repository configuration and import commands. This
project does not authenticate to it, mutate it, or schedule clients.

Keep `autoSetup = false` unless an administrator explicitly chooses automatic
client deployment. Test reachability from inside the OPSI container. For plain HTTP
on a trusted isolated network, the documented OPSI configuration has no certificate
to verify. For HTTPS, use `verifyCert = true` with a trusted CA.

### OPSI package to Windows client

Generated setup and uninstall scripts execute with OPSI's administrative context.
They run bundled project PowerShell helpers and the bundled vendor installer. No
script downloaded from upstream is executed by the builder. Custom catalog
overrides and custom detection snippets are trusted executable input.

Successful vendor exit is not enough. Generated behavior uses conservative version
comparison and performs standard post-action detection when the installer or uninstaller
returns `0`. Recognized reboot codes `3010` and `1641` bypass that built-in post-action
detection, so administrators must verify detection after the approved reboot. Test install,
second setup, upgrade, uninstall, and reboot behavior on representative managed Windows
systems.

## Integrity controls and limits

### Checksums

The builder verifies release-provided SHA256 when available and always computes the
downloaded installer SHA256. Historical hashes in state and retained provenance
prevent silent byte changes for the same upstream version. Accepted exceptional
changes are recorded in checksum override history.

Archive SHA256 in provenance protects published package bytes. MD5 and zsync are
OPSI transfer compatibility artifacts. MD5 is not the installer authenticity
control. `--force` requests a rebuild but does not bypass any checksum guard.

Checksums prove byte identity against the selected evidence. They do not prove the
vendor account, release process, DNS, CDN, or signing infrastructure is trustworthy.
A checksum hosted beside a compromised binary may be compromised too.

### Signatures

For EXE and MSI files, `osslsigncode verify` produces an advisory status:
`SIGNED`, `UNSIGNED`, or `UNKNOWN`. `SIGNED` means the Linux verification command
succeeded. `UNKNOWN` can mean missing tooling, timeout, unsupported format, or trust
uncertainty. None of these statuses replaces Windows publisher policy, online
revocation checks, reputation systems, or malware scanning.

The project does not pin expected publisher names or certificate fingerprints and
does not establish trust for detached PGP signatures. Add site controls outside the
builder if those guarantees are required.

### File and archive handling

Downloads go to private product-specific directories under `work/`. Failed partial
installers are removed. EXE and MSI magic is checked, ZIP and MSIX must parse as ZIP,
and tiny payloads are rejected. ZIP extraction rejects absolute paths, parent
traversal, Windows drive paths, colon-bearing names, symlinks, and expanded content
over 4 GiB.

OPSI archives are extracted after creation. The builder compares expected control
identity and the bundled installer hash before publication. Hidden staging names
are denied by nginx.

## Container hardening

Both services use a read-only root filesystem, drop all capabilities initially,
set `no-new-privileges`, use an init process where configured, and mount temporary
runtime paths as `tmpfs`. Neither container mounts the Docker socket.

`repo-builder` runs as numeric `BUILDER_UID:BUILDER_GID` with no added capabilities.
Only catalog is mounted read-only; the three data directories are writable.

`repo-web` receives only `NET_BIND_SERVICE`, `SETUID`, `SETGID`, and `CHOWN`, needed
by the nginx image startup model. Its repository and nginx configuration mounts are
read-only. Its healthcheck is internal HTTP only.

Docker daemon access remains host-equivalent privilege. Restrict membership and
socket access, patch the host, review images, and keep secrets out of image layers
and Compose output shared with untrusted users.

## Availability and failure isolation

A product exception is caught and recorded without stopping later products.
GitHub rate limits become warnings; rate limits from other hosts fail that product.
Catalog load, state or provenance reconstruction, global settings, and startup can
fail before product isolation applies.

Repository metadata is staged outside the served directory. Retention deletion runs
only after metadata generation and publication succeeds. Network or one-product
failures leave existing published packages available. nginx can remain healthy
while builds are stale, so monitor `state/last-run.json` separately.

Local Docker logs rotate at three 10 MB files. Send logs and alert state to external
systems when incident history must survive that limit.

## Redistribution and legal boundary

Each catalog entry is classified as `allowed`, `internal_only`, or `unknown`.
`internal_only` and `unknown` still permit a private build in code and emit a
warning. These labels are administrator records, not legal findings and not grants
of permission.

Before public exposure, review the exact installer license, vendor terms,
trademarks, geographic or account restrictions, update mechanisms, source-offer
requirements, and required notices. An open-source application does not
automatically make every distributed installer or bundled dependency freely
redistributable. Keep uncertain products private or disabled until reviewed.

## Security response checklist

For an unexpected source, checksum, archive, or metadata event:

1. Stop `repo-builder` while leaving known-good static artifacts available if that
   matches local incident policy.
2. Preserve catalog, repository, state, `.env`, logs, and storage evidence.
3. Restrict repository exposure if published bytes may be unsafe.
4. Compare official vendor records, retained provenance, historical state, and a
   known-good backup.
5. Restore matching repository and state generations when integrity is uncertain.
6. Never approve a hash merely because the download is repeatable.
7. Audit the restored or rebuilt repository.
8. Test on an isolated Windows acceptance system before OPSI import or deployment.

Detailed symptom-specific actions are in [Troubleshooting](TROUBLESHOOTING.md).
