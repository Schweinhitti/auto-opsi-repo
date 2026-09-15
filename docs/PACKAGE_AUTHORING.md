# Package authoring

[Back to the documentation index](README.md)

This guide covers new package recipes, changes to existing recipes, and new source
adapters. `catalog/packages.yaml` is the package catalog. The code in
`builder/builder/catalog.py`, `builder/builder/sources/adapters.py`,
`builder/builder/opsi.py`, and `builder/builder/versions.py` defines what the builder
actually accepts and generates.

Repository-side checks prove metadata resolution, download integrity, source generation,
OPSI archive structure, and publication. They do not prove that a vendor installer works
on Windows. `enabled: true` makes a recipe eligible for building; it is not deployment
approval. Every enabled recipe must pass [Windows client acceptance](CLIENT_ACCEPTANCE.md)
before broad deployment.

## Choose the workflow

For a new recipe, you may start with `./add-package.sh` on Linux, macOS, or WSL. The helper
appends a YAML draft but does not replace review against the loader and runtime:

- The Bash helper offers `manual`, but `manual` is not an enabled source type accepted by
  `catalog.py`.
- The helper exposes only a subset of the source types supported by the builder.
- For `uninstall.method: vendor`, the PowerShell runtime reads `uninstall.path`. Review and
  correct helper output because the current helper prompts emit other field names.

Do not use `add-package.bat` to modify the catalog in its current form. CMD `echo` writes its
literal `\n` sequences instead of YAML line breaks, and its GitHub branch writes an undefined
release-type variable. On Windows, edit `catalog/packages.yaml` manually or run the POSIX
helper under WSL, then review the result.

Always inspect the appended entry and run the catalog tests before a dry run.

For an existing recipe, edit the YAML directly. Keep a package disabled while its source,
silent installer behavior, detection, uninstall, or redistribution status is unknown. Move
it to build-enabled, acceptance-pending state only for isolated build, depot, and Windows
validation; do not broadly deploy it before approval.

## Catalog schema

The root must be a mapping with a `packages` list. Each list item must be a mapping. The
following is the required recipe contract; most constraints are enforced by
`builder/builder/catalog.py`:

| Field | Enabled recipe requirement |
|---|---|
| `id` | Non-empty string. Use lowercase letters, digits, and hyphens for consistency. |
| `opsi_product_id` | Unique; `^[a-z0-9][a-z0-9-]{0,31}$`. |
| `name`, `description` | Non-empty strings. |
| `enabled` | Boolean when present; defaults to `true`. |
| `architecture` | Exactly `[x64]`. Current enabled recipes are machine-wide Windows x64. |
| `redistribution` | Exactly `allowed`, `internal_only`, or `unknown`. This is a classification, not legal approval. |
| `package_revision` | Integer greater than or equal to 1. |
| `source.type` | One of the supported types listed below. |
| `source.allowed_hosts` | Non-empty YAML list of valid hostnames or `*.example.org` patterns. |
| `installer.type` | `exe`, `msi`, `msix`, or `zip`. |
| `detection.method` | `registry`, `file_version`, `msi`, or `custom`. |
| `uninstall.method` | `registry`, `msi`, `command`, `vendor`, `zip`, or `msix`. |

An explicitly disabled entry must still have a valid, unique `opsi_product_id`, a valid
`redistribution` value, and a non-empty `disabled_reason`. The loader then skips the rest
of the enabled schema. Treat that as a staging feature, not proof that incomplete fields
will work after enabling.

The current loader checks that `source.allowed_hosts` is truthy and validates each iterated
value, but does not first enforce that the YAML value is a list. A scalar string can pass
catalog loading and then behave incorrectly as individual characters. Always use a YAML
list, and include a test that rejects scalar input when changing this validation code.

## Source types and selection

Only these source types are accepted for enabled recipes:

- `github_release`: reads the latest 30 releases from the configured `repo` or
  `owner`/`repository`. Drafts are ignored. Prereleases are ignored unless
  `prerelease: true`. `release_type: tag` requires `tag`. `version_regex` capture group 1
  supplies the version. `asset_regex` is a full match and must select one asset on the
  newest parseable release. The builder refuses a stale release fallback.
- `winget_manifest`: reads Microsoft's `winget-pkgs` repository, chooses the newest stable
  version, then requires one unique x64, machine-scope installer matching
  `source.installer_types` or the recipe's installer type. It uses `InstallerSha256`.
  WinGet is metadata only and is never run on the client.
- `mozilla`: reads `version_field` from `version_url`, then formats
  `download_url_template` with the version and architecture.
- `microsoft`: reads VS Code update JSON fields `productVersion`, `url`, and optional
  `sha256hash` from `api_url`.
- `vendor_json_api` and `adoptium`: read dotted paths from JSON. Numeric path components
  index arrays. Set `version_field`, `url_field`, and optionally `sha256_field` and
  `detection_version_field`. Adoptium can format `{java_version}` in `api_url`.
- `direct_url`, `videolan`, and `documentfoundation`: scan `version_url` with
  `version_regex`, sort matches as versions, optionally restrict them with `track`, and
  format `download_url_template`. Templates support `{version}`, `{version_compact}`, and
  `{architecture}`.

Versions are parsed with `packaging.version.Version`, not sorted as strings. A leading `v`
is removed for OPSI. Local labels are encoded into an OPSI-compatible dotted form. The
normalized version must contain only ASCII letters, digits, and periods and must not exceed
32 characters. Invalid or unknown formats fail rather than selecting a guessed version.

For WinGet, match `installer_types` to manifest values such as those already present in the
catalog, not just `exe` or `msi`. The final recipe `installer.type` still controls the
bundled filename and Windows install command.

## URL and checksum policy

Use official HTTPS endpoints. `allowed_hosts` applies to the selected installer URL and
each redirect. Keep it narrow. For shared hosts, add `allowed_url_prefixes` so a URL must
also remain under the reviewed project path.

`source.disable_host_validation: true` keeps URL scheme checks but disables hostname
pinning for that recipe. It is an explicit exception for a reviewed official mirror
network, not a quick fix for an unexpected redirect. Record why it is needed.

Prefer a vendor-published SHA256 source:

- Use `checksum_url_template` plus optional `checksum_filename_template` for standard
  checksum files. The selected filename must have one unique hash.
- For GitHub, use `checksum_asset_regex` and optional `checksum_line_regex`. Capture group 1
  must be the selected file's SHA256. GitHub's `sha256:` asset digest is also checked when
  present.
- JSON and WinGet adapters can supply SHA256 directly.

The actual download is hashed even when no vendor hash is available. A changed hash for a
known upstream version is blocked. `--force` does not bypass this check. Do not broaden a
host allowlist or set `ALLOW_CHANGED_CHECKSUM=true` until you have independently established
why the source changed and retained the previous package and checksum evidence.

## Installer, detection, and uninstall

### Installer

- `exe` runs the bundled executable with the exact `installer.silent_args` list.
- `msi` runs `msiexec.exe /i` with the configured arguments.
- Both `exe` and `msi` require non-empty unattended arguments.
- `installer.uninstall_previous: true` runs this package's uninstaller before install. Use
  it only when vendor upgrade behavior requires removal first.
- `zip` requires a dedicated `installer.target_dir`. The archive is checked for traversal,
  drive paths, links, and expansion limits before its payload is copied to that directory.
- `msix` uses `Add-AppxProvisionedPackage -Online -SkipLicense`.

Exit codes `0`, `3010`, and `1641` are accepted by the client helper. Reboot scheduling is
still an administrator policy and must be tested.

### Detection

- `registry` requires `display_name_regex` and checks both 64-bit and 32-bit HKLM uninstall
  views. Make the regex specific enough to select only the intended product. It normally
  reads `DisplayVersion`.
- `version_from_display_name_regex` captures the installed version from `DisplayName` when
  a vendor's `DisplayVersion` is unsuitable.
- `version_replacements` maps vendor separators before comparison.
- `file_version` requires an environment-expandable executable `path` and reads its product
  version.
- `msi` requires a brace-wrapped 36-character hexadecimal and hyphen `product_code` and
  matches that uninstall registry key.
- `custom` requires an override snippet named by `detection.script`.

Numeric installed versions equal to or newer than the requested detection version skip the
install. Unknown comparison formats cause installation instead of a false success. For a
standard detector, post-install detection runs only after installer exit code `0` and fails
the action if the requested version is absent. Accepted reboot codes `3010` and `1641`
bypass that built-in post-install check, so the post-reboot acceptance check is mandatory.

### Uninstall

- `registry` uses matching uninstall entries. It prefers Windows Installer GUID removal,
  then `QuietUninstallString`, then `UninstallString` plus configured `silent_args`.
  `uninstall.display_name_regex` may narrow removal independently of detection.
- `msi` requires `uninstall.product_code` and runs `msiexec.exe /x` quietly with no restart.
- `command` requires an explicit `uninstall.command`; optional `silent_args` are appended.
- `vendor` requires an environment-expandable `uninstall.path`; optional `silent_args` are
  passed to that executable.
- `zip` removes `installer.target_dir` after a safety check.
- `msix` requires `uninstall.package_name` and removes matching provisioned packages for all
  users.

Registry and explicit commands must identify a quoted executable or an unquoted token ending
in `.exe`. Ambiguous unquoted commands fail. Standard uninstall checks for a remaining
application only when the resulting exit code is `0`; accepted reboot codes rely on the
post-reboot acceptance check.

## Overrides and custom adapters

Overrides are trusted administrator code. Put them under
`catalog/overrides/<opsi_product_id>/`. A product may replace `control.toml.j2`,
`setup.opsiscript.j2`, or `uninstall.opsiscript.j2`. The fields
`pre_install_opsi_script`, `post_install_opsi_script`, `pre_uninstall_opsi_script`, and
`post_uninstall_opsi_script` name snippets relative to that product directory. Paths cannot
escape the directory. Templates receive `p`, `version`, and `revision`.

With `detection.method: custom`, the named snippet replaces the standard setup detection and
installer exit-code block. It owns detection, conditionally calls `Winbatch_install`, and
must report failures correctly. Test both its skip and install branches on Windows.

When no existing source type fits a vendor protocol:

1. Add the exact type string to `SOURCE_TYPES` in `builder/builder/catalog.py`.
2. Add a branch in `resolve(package, http)` in
   `builder/builder/sources/adapters.py` that returns `Release(version, url, sha256,
   architecture, filename, detection_version)` as needed.
3. Use the provided HTTP object so request limits, redirects, and host validation remain in
   effect. Do not execute downloaded metadata or scrape an unrelated download site.
4. Leave final URL validation in the shared adapter path.
5. Add unit tests for selection, ambiguity, no-match behavior, versions, allowed hosts, and
   checksum parsing. Add a recipe that supplies every field the adapter reads.
6. Run the complete development and product sequence below.

## Revisions, force, and offline repackaging

An upstream version identifies vendor software. `package_revision` identifies this
project's packaging logic for that same software.

- Increase `package_revision` when silent arguments, detection, uninstall, templates,
  overrides, or other deployment logic changes without an upstream version change.
- A normal build resolves upstream and creates the selected version and revision.
- `--force PRODUCT` rebuilds an already selected product/revision. It does not filter the
  run and does not bypass historical checksum checks. Combine it with `--product PRODUCT`
  when you want only one product.
- Prefer a new revision over replacing an existing archive name. Clients and caches may be
  reading the old file.
- Offline `builder.repackage` is only for a higher packaging revision when upstream metadata
  is unavailable. It verifies the old archive and installer against provenance, keeps the
  original upstream version and download evidence, and does not claim a new release.

Example offline recovery:

```bash
docker compose stop repo-builder
docker compose run --rm --entrypoint python repo-builder -m builder.repackage auto-example
docker compose up -d repo-builder
```

## Disabled recipe workflow

Use these lifecycle states explicitly:

- **Disabled draft:** `enabled: false`; research or recipe work is incomplete.
- **Build-enabled, acceptance pending:** `enabled: true`; server-side build and isolated
  depot/client tests are allowed, but broad deployment is not approved.
- **Approved:** server-side verification and every applicable Windows acceptance criterion
  passed with recorded evidence.

1. Add or retain the intended recipe with `enabled: false`, a valid redistribution class,
   and a specific `disabled_reason`.
2. Research an official metadata and installer route, unattended arguments, architecture,
   language, detection, uninstall, checksums, and redistribution terms.
3. Fill in the complete enabled schema while it remains disabled. Review any mirror-policy
   exception explicitly.
4. Add or update tests and inspect generated sources.
5. Set `enabled: true` to enter build-enabled, acceptance-pending state, then run the full
   local checks and a product dry run.
6. Build and audit the package on the server.
7. Import it into a test depot without enabling automatic client setup.
8. Complete Windows acceptance. Do not approve broad deployment on server evidence alone.

## Verification sequence

Run from the repository root. See [Development](DEVELOPMENT.md) for environment setup and
the full local CI set.

1. Validate code, YAML loading, and generated content with the tests:

   ```bash
   .venv/bin/python -m compileall -q builder scripts tests
   .venv/bin/ruff check .
   .venv/bin/pytest -q
   docker compose config --quiet
   ```

2. Resolve only the changed product without writing installers, state, locks, or packages:

   ```bash
   docker compose run --rm repo-builder --dry-run --product auto-example
   ```

   Pass means exit code 0, the product appears under `Updated` or `Unchanged`, and it does
   not appear under `Failed`. Confirm the reported version and URL are the intended stable,
   x64, machine installer. A rate-limit warning is not a successful source check.

3. Inspect generated sources. `scripts/render-example.py` demonstrates no-installer source
   generation for Firefox. For the changed product, build it, then extract the resulting
   archive with the OPSI CLI into `work/inspect-auto-example`:

   ```bash
   docker compose run --rm repo-builder --once --product auto-example
   docker compose run --rm --entrypoint opsi-cli repo-builder \
     package extract /data/repository/auto-example_VERSION-REVISION.opsi \
     /data/work/inspect-auto-example
   ```

   Read `OPSI/control.toml`, `CLIENT_DATA/config.json`, `setup.opsiscript`,
   `uninstall.opsiscript`, `install.ps1`, and `uninstall.ps1`. Pass means IDs, versions,
   arguments, detection fields, uninstall fields, override text, and bundled installer type
   exactly match the reviewed recipe. Remove the inspection directory when finished.

4. Audit published files:

   ```bash
   .venv/bin/python scripts/audit-repository.py
   ```

   Pass means the command exits 0 and reports matching package SHA256, MD5, zsync,
   provenance, sizes, and metadata references. Also check the product is not listed under
   `Failed` in `state/last-run.json`.

5. Follow [Integration](INTEGRATION.md) to list and import the product into a test depot.
   Keep `autoSetup = false`.

6. Complete [Windows client acceptance](CLIENT_ACCEPTANCE.md). Approval requires every
   applicable binary criterion to pass and recorded evidence for any approved limitation.

Related evidence and policy are in [Validation record](VALIDATION.md) and
[Source and format verification](SOURCES.md).
