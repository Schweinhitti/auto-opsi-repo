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

Run the same checks used by `.github/workflows/ci.yml`, then the relevant Docker checks:

```bash
.venv/bin/python -m compileall -q builder scripts tests
.venv/bin/ruff check .
.venv/bin/pytest -q
docker compose config --quiet
bash -n add-package.sh builder/entrypoint.sh helper/build.sh helper/cleanup.sh helper/dry-run.sh helper/logs.sh helper/run.sh helper/status.sh helper/test.sh
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
python -m compileall -q builder scripts tests
ruff check .
pytest -q
docker compose config --quiet
bash -n add-package.sh builder/entrypoint.sh helper/build.sh helper/cleanup.sh helper/dry-run.sh helper/logs.sh helper/run.sh helper/status.sh helper/test.sh
```

Before the Python checks, pinact verifies that workflow actions use real immutable commits and
that their readable release comments match those commits.

CI does not build Docker images, test nginx, contact live upstream services, or perform
Windows acceptance. Run the applicable local checks before requesting review.

### Security, dependency, and maintenance workflows

- `.github/workflows/spelling.yml` runs `crate-ci/typos` on pull requests.
- `.github/workflows/size.yml` labels pull requests from `size/xs` through `size/xl`. More
  than 1000 changed lines produces a warning message, but `fail_if_xl` is false.
- `.github/workflows/devskim.yml` and `.github/workflows/defender-for-devops.yml` run static
  analysis and upload their findings to GitHub code scanning. GitHub CodeQL Default Setup
  separately scans Actions and Python with the extended query suite; no duplicate advanced
  CodeQL workflow is stored in this repository.
- `.github/workflows/dependency-review.yml` checks dependency changes in pull requests to
  `main` and fails on high or critical known vulnerabilities.
- `.github/workflows/scorecard.yml` runs OpenSSF Scorecard only on trusted pushes to `main`,
  its weekly schedule, or manual dispatch, then uploads the SARIF result to code scanning.
- `.github/dependabot.yml` checks builder pip dependencies, root GitHub Actions, and the
  builder Docker ecosystem daily at 04:00. Minor and patch updates are grouped per ecosystem;
  major updates remain separate pull requests. Dependabot does not auto-merge them.
- `.github/workflows/cve-lite-fix.yml` runs daily at 06:00 and by manual dispatch. It checks
  out the default branch and runs OWASP CVE Lite with fixes and pull-request creation
  enabled. This privileged workflow has `contents: write` and `pull-requests: write`; its
  proposed changes must be reviewed.

Workflow action references use immutable commit SHA pins with readable release comments.
These jobs report or propose changes, but their presence and findings do not establish that a
dependency update, image, or Windows package is safe. Review the output and run the normal
checks.

### Community and intake

`.github/ISSUE_TEMPLATE/` provides structured bug and feature forms, disables blank issues,
and links to private security reporting, documentation, and support guidance. The pull request
template asks contributors for scope and validation details. `CONTRIBUTING.md`, `SECURITY.md`,
`SUPPORT.md`, and `CODE_OF_CONDUCT.md` set the contribution, disclosure, support, and conduct
expectations. `CODEOWNERS` defines the default review ownership for repository changes.

## GHCR image automation

`.github/workflows/ghcr-publish.yml` builds `builder/Dockerfile` with Docker Buildx for:

- pull requests whose base branch is `main`;
- pushes to `main`.

The image name is `ghcr.io/${{ github.repository }}`. Docker metadata creates tags from the
branch or pull request, a short SHA tag, and a raw tag equal to the full commit SHA. The
image gets a `version` label containing the pull-request number when available.

Pull requests build the image without logging in or pushing, regardless of whether the source
branch is in this repository or a fork. That job has only `contents: read`. Pushes to `main`
run the publish job, which logs in to GHCR, pushes the image, and generates a provenance
attestation from the pushed image digest. Its permissions are `contents: read` plus
`packages: write`, `id-token: write`, and `attestations: write`.

The workflow builds only the repo-builder image, not the `repo-web` nginx image or an OPSI
package catalog release. It does not explicitly create a `latest` tag or a versioned release
channel. `.github/release.yml` configures categories for GitHub's generated release notes,
but no workflow publishes GitHub Releases or release notes.

## Change completion

For Python or workflow changes, pass compilation, Ruff, pytest, and relevant Docker checks.
For a recipe or adapter change, also complete the product sequence in
[Package authoring](PACKAGE_AUTHORING.md). Any client-facing package change finishes only
after [Windows client acceptance](CLIENT_ACCEPTANCE.md). The existing repository-side record
and known limits are in [Validation record](VALIDATION.md).
