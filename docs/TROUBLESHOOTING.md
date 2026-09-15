# Troubleshooting

[Back to the documentation index](README.md)

Use this page to move from symptom to cause, diagnosis, and a safe action. Preserve
`repository/`, `state/`, the catalog, and logs before changing anything during an
integrity incident. Never delete state, bypass TLS, broadly weaken source
allowlists, or ignore checksum failures.

See [Operations](OPERATIONS.md) for full procedures,
[Architecture](ARCHITECTURE.md) for failure boundaries, and
[Security](SECURITY.md) for trust decisions. OPSI-side commands are in
[Integration](INTEGRATION.md). The [project README](../README.md) is the broad
starting point. See [Configuration](CONFIGURATION.md) for exact environment
settings and [Windows client acceptance](CLIENT_ACCEPTANCE.md) for the client test
procedure.

## First response

Collect these signals before recovery:

```bash
docker compose ps
docker compose logs --tail=200 repo-builder
docker compose logs --tail=100 repo-web
./helper/status.sh
curl -fI http://HOST-IP:PORT/packages.json
```

Read `state/last-run.json`. A failure under a product ID is isolated to that
product, so other products may have updated. `Failed: repository` means metadata or
retention failed after product processing. A missing or stale last-run file with
healthy nginx means static serving works but build freshness is unknown or bad.

## Builder lock or manual overlap

**Symptom:** A one-shot run exits `2` and logs `Another builder is active`.

**Likely cause:** The periodic service or another operator holds the nonblocking
exclusive `flock` on `state/builder.lock`. The file itself normally persists after
the owner exits.

**Diagnosis:** Run `docker compose ps` and identify current builder containers or
known manual jobs. Check builder logs for an active product. Do not infer ownership
from the lock file's presence.

**Safe action:** Wait for the active cycle. For controlled manual work, stop
`repo-builder`, confirm it exited, then retry. Coordinate any other manual process.
Never delete `builder.lock` or state to defeat a live lock.

## GitHub 403 or 429 rate limit

**Symptom:** A product is listed under `Warnings` with `Upstream access/rate limit;
retry next cycle`, commonly from `api.github.com`.

**Likely cause:** The upstream API denied access or exhausted its request quota.
GitHub rate limits are treated as warnings so unrelated products continue.

**Diagnosis:** Read the host and reset value in the warning. Confirm whether
`GITHUB_TOKEN` is configured without printing it. Check official GitHub service and
rate-limit information outside the logs.

**Safe action:** Wait for the next cycle, or set a least-privilege, read-only token
in protected `.env` storage and recreate the service with `docker compose up -d`.
The builder sends that token only to `api.github.com`. Do not place tokens in URLs,
disable TLS, or treat a rate-limit response as release metadata.

## Redirect rejected or untrusted source host

**Symptom:** The product fails with `Untrusted source host`, `Only credential-free
HTTPS URLs are accepted`, or `Too many redirects`.

**Likely cause:** A vendor changed CDN or release URLs, redirected outside the
catalog's explicit host policy, used a non-HTTPS or credential-bearing URL, or
exceeded the ten-redirect limit.

**Diagnosis:** Preserve logs and inspect the vendor's current official release
documentation. Trace each redirect only through a TLS-valid diagnostic client. Map
the final official hostname to `source.allowed_hosts` or, for shared hosts, the
recipe's URL-prefix restriction.

**Safe action:** Add only a reviewed official hostname or narrow prefix, then run a
single-product dry run. Keep TLS verification enabled. Do not add arbitrary mirrors,
broad wildcards, or `disable_host_validation` merely to clear the error. A source
that cannot be pinned safely should remain disabled pending review.

## TLS certificate failure

**Symptom:** Metadata or download requests fail with certificate verification
errors.

**Likely cause:** An upstream certificate problem, interception proxy, incorrect
host time, or a private CA absent from the builder trust store.

**Diagnosis:** Check host time and inspect the certificate chain and expected name
through approved network tooling. Confirm whether the organization intentionally
uses a private CA.

**Safe action:** Fix the upstream or network issue. For an approved private CA,
mount a reviewed PEM bundle read-only and set `REQUESTS_CA_BUNDLE` to its container
path. Do not set an insecure verification mode or change URLs to plain HTTP.

## Checksum mismatch or immutable checksum changed

**Symptom:** `SHA256 verification FAILED` or `IMMUTABLE VERSION CHECKSUM CHANGED`.
A force rebuild reports the same error.

**Likely cause:** The downloaded file differs from a published checksum, or a known
upstream version now has bytes different from historical state or provenance. This
can be a vendor replacement, source mistake, cache issue, corruption, or compromise.

**Diagnosis:** Stop the builder and preserve the known-good archive, provenance,
state, catalog, and logs. Compare official vendor release information and checksum
sources. Confirm the product/version key and source URL. Do not overwrite evidence.

**Safe action:** Keep the existing package available while investigating. Restore
state if historical evidence is missing. If the change is legitimate, prefer a new
package revision and use a one-off `ALLOW_CHANGED_CHECKSUM=true` only after explicit
approval, followed by audit and Windows acceptance. `--force` never bypasses this
guard. Never delete state or disable checksum checks.

## Existing package has no checksum provenance

**Symptom:** A force rebuild fails with `Existing version has no checksum
provenance; restore state or increment revision`.

**Likely cause:** State and retained provenance do not contain evidence needed to
compare installer bytes safely.

**Diagnosis:** Check the matching `.opsi.provenance.json` and backup generations.
Do not create guessed checksum records.

**Safe action:** Restore matching state and repository data from one consistent
backup. If the existing package is trusted but evidence cannot be restored, preserve
it and use a reviewed new package revision through the normal workflow rather than
forcing replacement.

## No matching latest asset

**Symptom:** A GitHub or other source adapter reports no matching asset, multiple
matches, an absent checksum entry, or missing source fields.

**Likely cause:** Upstream renamed assets, changed archive type or architecture,
published an incomplete latest release, or changed its metadata schema. The builder
does not silently select an older release.

**Diagnosis:** Compare the newest official release assets with the catalog's exact
asset regex, architecture, installer type, checksum selector, and source adapter.
For GitHub, only the adapter's bounded release records are considered.

**Safe action:** Update the source matcher and installer recipe together after
review, then run a product dry run and normal build. Validate the resulting package
on Windows. Do not loosen the expression until unrelated assets can match or pin an
old release without recording that policy explicitly.

## Catalog or version validation failure

**Symptom:** The cycle fails before product summaries, reporting an invalid catalog,
unknown product, duplicate ID, unsupported source, invalid revision, missing
allowlist, incompatible version, or normalized version collision.

**Likely cause:** `catalog.py` rejected a trusted configuration or `versions.py`
could not map the upstream version to OPSI's 32-character format without ambiguity.
Catalog loading occurs before per-product failure isolation.

**Diagnosis:** Run a dry run and inspect the exact exception. Check required fields,
one x64 architecture, product ID syntax, revision, installer and detection fields,
allowed hosts, and the original upstream version. For collisions, compare retained
provenance for the expected archive.

**Safe action:** Correct the catalog or assign a distinct product or revision. Keep
the existing repository and state. Never rename managed archives by hand to make an
invalid version fit.

## Metadata generation or retention failure

**Symptom:** The summary contains `Failed: repository`, new archives may exist, and
`packages.json` may not advertise them.

**Likely cause:** `opsi-cli manage-repo` failed, generated no metadata, encountered
an unrecognized `.opsi` filename, ran out of disk, or could not write staging or
repository files.

**Diagnosis:** Read the exception and preceding `opsi-cli` output. Check free space,
ownership, managed archive names, and write access to `work/` and `repository/`.
Run `python3 scripts/audit-repository.py` only if current JSON metadata exists and is
parseable.

**Safe action:** Leave archives and old versions intact. The code generates metadata
before deleting retention candidates, so a failed metadata step does not authorize
manual deletion. Correct the CLI, name, capacity, or permission issue and run one
controlled normal cycle. Then audit. Do not hand-edit generated metadata.

## Published package or audit integrity failure

**Symptom:** The audit asserts on archive SHA256, MD5, zsync, provenance, metadata
size, product identity, or a referenced path. The builder may report a published
package checksum mismatch.

**Likely cause:** Storage corruption, partial external copy, manual changes, mixed
backup generations, or uncoordinated mutation outside the builder.

**Diagnosis:** Stop the builder. Preserve the affected files, state, logs, and
storage error evidence. Identify the exact failed assertion and compare with a
known-good consistent backup. Remember that publication is atomic per file, not a
whole-repository snapshot.

**Safe action:** Restore `catalog/`, `repository/`, and `state/` from the same
known-good generation, preserve ownership, rerun the audit, then dry run before
restart. Do not regenerate or edit hashes to match unexplained bytes.

## Permission denied

**Symptom:** The builder cannot create, copy, replace, lock, or delete files under
`repository/`, `state/`, or `work/`.

**Likely cause:** Bind mounts are not owned or writable by the numeric
`BUILDER_UID:BUILDER_GID`, restored files have wrong ownership, or host security
policy denies access. The container root filesystem itself is read-only.

**Diagnosis:** Compare `.env` UID and GID values with host ownership and modes for
all three directories. Inspect host policy logs where applicable. Do not rely on
`helper/run.sh`, because its `chown` failure is ignored.

**Safe action:** Stop the builder, correct owner and least-privilege modes on the
three writable bind mounts, then run a product dry run and controlled normal cycle.
Do not use world-writable permissions or run the service as root.

## Port already allocated or repository unreachable

**Symptom:** `repo-web` fails to start with an address allocation error, or HTTP is
unreachable on the expected port.

**Likely cause:** Another host service owns `HTTP_PORT`, the service is bound to the
wrong address, a firewall blocks it, or consumers use a stale URL.

**Diagnosis:** Inspect `docker compose ps`, repo-web logs, rendered configuration
with `docker compose config`, and approved host socket/firewall tools. Test the host
address and port from the OPSI server network.

**Safe action:** Keep the unrelated service running. Select an approved free port or
correct `HTTP_BIND_ADDRESS`, recreate `repo-web`, and update every OPSI repository
URL consistently. Restrict exposure to the depot network or an authenticated HTTPS
proxy.

## OPSI sees no packages

**Symptom:** The repository responds on the builder host, but
`opsi-package-updater` lists no products or cannot fetch the repository.

**Likely cause:** The configured host is unreachable from inside the OPSI container,
loopback was used, port or firewall differs, metadata is stale or absent, the
`local_auto` repository is inactive, or TLS trust does not match the URL.

**Diagnosis:** From the OPSI container, request the exact configured base URL and
`packages.json`. Run `opsi-package-updater list --active-repos`, then
`opsi-package-updater --repo local_auto list --products`. Compare the `.repo`
baseURL, active status, port, path, and certificate policy with
[Integration](INTEGRATION.md).

**Safe action:** Use the repository host's reachable LAN or proxy address, not
`127.0.0.1`. Correct routing, firewall, port, metadata failure, or repository
configuration. For HTTPS, install a trusted chain and enable certificate
verification. Do not disable certificate checks on an HTTPS deployment merely to
make products visible.

## Windows installer exits zero but detection fails

**Symptom:** Vendor installation returns success, but OPSI setup fails because the
product is not detected. A second setup may reinstall unexpectedly.

**Likely cause:** The catalog's registry display-name regex, MSI product code,
file-version path, version extraction, or version replacement does not match the
installed machine-wide x64 product. A bootstrapper may report a version in
`DisplayName` rather than `DisplayVersion`.

**Diagnosis:** On a representative managed Windows VM, inspect both 64-bit and
32-bit HKLM uninstall registry views, the configured file path and file version, or
the exact MSI product code. Compare the observed version with `detection_version`,
`version_from_display_name_regex`, `version_regex`, and `version_replacements`.
Capture OPSI and generated PowerShell logs. Do not infer success from vendor exit
code alone.

**Safe action:** Narrowly correct the detection recipe or reviewed custom override,
increase `package_revision`, rebuild, then test install, second setup, upgrade, and
uninstall. Keep conservative post-install detection. Do not suppress the check or
mark unknown versions successful.

## Windows install, reboot, or uninstall failure

**Symptom:** Installation or removal returns nonzero, leaves the product installed,
or requests reboot.

**Likely cause:** Silent arguments changed, machine scope differs, uninstall command
is ambiguous, a vendor prerequisite is absent, or the application needs specific
handling. Exit codes 3010 and 1641 are recognized as reboot requests, but reboot
scheduling remains OPSI policy.

**Diagnosis:** Review generated OPSI and PowerShell logs, the catalog's installer
type and arguments, uninstall method, actual registry command, and post-action
detection. Reproduce on a representative VM outside broad deployment.

**Safe action:** Correct reviewed silent arguments or product-specific override,
increase the package revision, and repeat the full Windows acceptance cycle. Handle
reboots through approved OPSI policy. Do not weaken post-install or post-uninstall
detection.

## OPSI CLI command changed

**Symptom:** Package build, extract, or repository metadata commands fail after a
base image or OPSI tooling update.

**Likely cause:** The installed `opsi-cli` command contract differs from the one
used by `opsi.py` or `repository.py`.

**Diagnosis:** Inspect the installed help rather than guessing:

```bash
docker compose run --rm --entrypoint opsi-cli repo-builder package make --help
docker compose run --rm --entrypoint opsi-cli repo-builder \
  manage-repo metafile create --help
```

**Safe action:** Keep the builder stopped, pin or restore the last tested image, or
update code and tests to the reviewed CLI contract. Dry run does not exercise
packaging, so run unit tests and a controlled package build before restarting.

## Offline repackage fails

**Symptom:** `builder.repackage` reports no archive, archive hash mismatch, no unique
installer, unchanged revision, missing detection metadata, or lock contention.

**Likely cause:** Preconditions for trusted offline reuse are absent. The command is
designed to fail rather than infer missing evidence.

**Diagnosis:** Confirm the newest retained archive and provenance agree, state has
the installer checksum, the catalog installer type matches, the package revision is
higher, and no writer is active.

**Safe action:** Restore a matching backup or perform a normal online build when
metadata becomes available. Do not extract an arbitrary installer, invent
provenance, lower the revision, or bypass the checksum comparison.
