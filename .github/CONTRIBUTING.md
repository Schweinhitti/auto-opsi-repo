# Contributing

Thanks for helping improve auto-opsi-repo. The project builds third-party Windows installers
into packages for private OPSI repositories, so small changes can affect source trust,
installer integrity, redistribution duties, and administrator-level client behavior.

## Before You Start

Read the [development guide](../docs/DEVELOPMENT.md). For package work, also read
[package authoring](../docs/PACKAGE_AUTHORING.md), [security](../docs/SECURITY.md), and
[Windows client acceptance](../docs/CLIENT_ACCEPTANCE.md).

Open a focused pull request. Keep unrelated cleanup separate, explain the problem being
solved, and add focused tests for changed behavior. Don't include generated packages,
downloaded installers, local state, credentials, or private environment data.

## Local Validation

Set up Python 3.13 as described in the development guide, then run the checks that match your
change. The full local set is:

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

A live dry run can fail because an upstream service is unavailable or has changed. Record and
investigate that result. Don't weaken trust controls just to make the command pass.

## Package Recipes and Security Boundaries

Treat `catalog/packages.yaml`, package overrides, installer arguments, detection rules, and
uninstall rules as trusted code. Package contributions must:

* use reviewed official HTTPS sources and narrow host or URL-prefix allowlists;
* preserve TLS, redirect, download-size, and checksum checks;
* verify unexpected checksum or source changes instead of bypassing them;
* document silent install, detection, uninstall, architecture, and language behavior;
* increase `package_revision` when deployment logic changes without an upstream version
  change;
* classify redistribution as `allowed`, `internal_only`, or `unknown` without presenting the
  classification as legal approval; and
* keep recipes disabled while source ownership, unattended behavior, detection, uninstall,
  or redistribution status remains uncertain.

Never add secrets, tokens, vendor credentials, installer binaries, or vulnerability details
to a pull request. Review redistribution terms before exposing any built installer publicly.

## Package Validation and Windows Acceptance

For a recipe or adapter change, run the product-specific dry run, build and extract the OPSI
archive, inspect its generated sources, and run `scripts/audit-repository.py` as documented in
the package authoring guide. A valid archive doesn't prove client behavior.

New enabled recipes and changes to installer arguments, detection, uninstall logic,
templates, overrides, architecture, language, or package revision require acceptance on a
representative disposable OPSI-managed Windows x64 VM. Record first install, repeat detection,
upgrade when applicable, uninstall, reboot behavior, and the evidence requested in the
[acceptance checklist](../docs/CLIENT_ACCEPTANCE.md). If Windows acceptance hasn't run, state
that clearly in the pull request and don't claim the package is ready for broad deployment.

## Pull Requests

Complete the pull request template, list the commands you ran and their results, and call out
security, source, checksum, redistribution, or Windows acceptance impact. Maintainers may ask
for a narrower change or more evidence before accepting package policy changes.
