# Development

[Back to the documentation index](README.md)

This project targets Python 3.13. The local Python checks cover builder logic and scripts;
Docker checks cover the runtime image, Compose configuration, OPSI tooling, and nginx.

## Python 3.13 setup

From the repository root:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r builder/requirements.txt pytest ruff
```

Confirm the interpreter before testing:

```bash
.venv/bin/python --version
```

The result must start with `Python 3.13`. Ruff is configured in `pyproject.toml` for Python
3.13, a 100-character line length, and rules `E4`, `E7`, `E9`, `F`, `I`, `UP`, and `B`.

## Local CI checks

Run the same lint and test commands used by `.github/workflows/ci.yml`, plus compilation and
Compose checks:

```bash
.venv/bin/python -m compileall -q builder scripts tests
.venv/bin/ruff check .
.venv/bin/pytest -q
docker compose config --quiet
docker compose build repo-builder
docker compose run --rm repo-web nginx -t
docker compose run --rm repo-builder --dry-run
```

Use a product filter while changing one recipe:

```bash
docker compose run --rm repo-builder --dry-run --product auto-firefox
```

The full dry run contacts live metadata and checksum endpoints. Unit tests mock network
calls. A local dry run can therefore fail because of an upstream outage, changed vendor
metadata, redirect policy, or rate limit even when unit tests pass. Record and investigate
that result instead of treating it as a unit-test failure or silently expanding trust.

Do not run a manual write cycle while the periodic `repo-builder` owns the lock. For an
intentional product build:

```bash
docker compose stop repo-builder
docker compose run --rm repo-builder --once --product auto-firefox
docker compose up -d repo-builder
```

Exit code 0 and an `Updated` or `Unchanged` summary are the binary server-side result. A
package build also makes an archive with official OPSI tooling, extracts it again, compares
control metadata, verifies the bundled installer hash, and checks its MD5 sidecar. This does
not test Windows installation behavior.

## Test focus

The tests under `tests/` cover:

- catalog schema failures and duplicate product IDs;
- version normalization and ordering;
- source selection, ambiguity, stale-release refusal, tracks, and vendor detection versions;
- URL, redirect, checksum, changed-checksum, and download behavior;
- EXE/MSI format rejection and safe ZIP extraction;
- generated control files, OPSI scripts, and product configuration;
- dry-run write isolation, package duplicate prevention, state migration, and failure
  isolation;
- metadata staging, retention, provenance, and offline repackaging safeguards;
- the core CI and dependency-automation configuration.

Add focused tests whenever an adapter, recipe exception, template, version mapping, or
failure path changes. A custom adapter needs positive selection tests and tests for ambiguous
or missing results. A deployment logic change also needs Windows acceptance because mocked
tests cannot reproduce a vendor installer.

## Repository scripts

- `scripts/render-example.py` renders inspectable Firefox OPSI sources without a fake
  installer. It exits if `work/example-source/auto-firefox` already exists.
- `scripts/audit-repository.py` is a read-only audit of published archives, provenance,
  SHA256, MD5, zsync sidecars, sizes, and repository metadata references.
- `add-package.sh` appends a recipe draft that must pass the authoritative loader and
  runtime review described in [Package authoring](PACKAGE_AUTHORING.md).
- `add-package.bat` is not a usable catalog writer in its current form because it emits
  literal `\n` text and has a broken GitHub release-type variable. Windows contributors
  should edit YAML manually or use `add-package.sh` under WSL.

## GitHub Actions

### CI

`.github/workflows/ci.yml` runs on every push and pull request with read-only repository
contents permission. On `ubuntu-latest` it checks out the repository, installs Python 3.13,
installs builder requirements plus pytest and Ruff, then runs:

```bash
ruff check .
pytest -q
```

The CI workflow does not currently run `compileall`, Docker builds, Compose validation,
nginx checks, live dry runs, or Windows acceptance. Run the applicable local checks before
requesting review.

### Spelling, size, dependencies, and CVE workflow

- `.github/workflows/spelling.yml` runs `crate-ci/typos` on pull requests.
- `.github/workflows/size.yml` labels pull requests from `size/xs` through `size/xl`. More
  than 1000 changed lines produces a warning message, but `fail_if_xl` is false.
- `.github/dependabot.yml` checks root and builder Python dependencies, GitHub Actions, and
  the builder Docker ecosystem daily at 04:00. It opens dependency pull requests within the
  configured limits.
- `.github/workflows/cve-lite-fix.yml` runs daily at 06:00 and by manual dispatch. It checks
  out the default branch and runs OWASP CVE Lite with fixes and pull-request creation
  enabled. It has `contents: write` and `pull-requests: write` permissions.

These jobs propose or check changes. Their existence does not establish that a specific
dependency update, image, or Windows package is safe. Review their output and run the normal
checks.

## GHCR image automation

`.github/workflows/ghcr-publish.yml` builds `builder/Dockerfile` with Docker Buildx for:

- pull requests whose base branch is `main`;
- pushes to `main`.

The image name is `ghcr.io/${{ github.repository }}`. Docker metadata creates tags from the
branch or pull request, a short SHA tag, and a raw tag equal to the full commit SHA. The
image gets a `version` label containing the pull-request number when available.

Push behavior is exactly conditional:

- A push event on `main` logs in with the workflow `GITHUB_TOKEN` and pushes.
- A pull request from a branch in the same repository logs in and pushes its generated tags.
- A pull request from a fork builds but does not log in or push.

The job has `contents: read` and `packages: write`. It builds only the repo-builder image,
not the `repo-web` nginx image or an OPSI package catalog release.

There is no semantic release process configured. No workflow calculates a semantic version,
creates a GitHub Release, publishes release notes, or maps package revisions to application
releases. The GHCR workflow also does not explicitly create a `latest` tag or a versioned
release channel. Treat its branch, pull-request, and commit tags as CI image artifacts.

## Change completion

For Python or workflow changes, pass compilation, Ruff, pytest, and relevant Docker checks.
For a recipe or adapter change, also complete the product sequence in
[Package authoring](PACKAGE_AUTHORING.md). Any client-facing package change finishes only
after [Windows client acceptance](CLIENT_ACCEPTANCE.md). The existing repository-side record
and known limits are in [Validation record](VALIDATION.md).
