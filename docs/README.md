# Documentation

Start with the [project overview](PROJECT_OVERVIEW.md) for the system boundary and
component summary.

## Operators

- [Getting started](GETTING_STARTED.md): prepare the host, configure the stack, run the
  first cycle, and verify builder and web health.
- [Configuration](CONFIGURATION.md): environment variables, ownership, private CA trust,
  network exposure, and applying changes.
- [Operations](OPERATIONS.md): routine runs, monitoring, audits, retention, recovery,
  backup, restore, and controlled updates.
- [Troubleshooting](TROUBLESHOOTING.md): symptom-to-action guidance for source, package,
  repository, Docker, network, OPSI, and Windows failures.
- [Security](SECURITY.md): trust boundaries, integrity controls, container hardening,
  network risks, and redistribution responsibilities.

## OPSI administrators

- [Integration](INTEGRATION.md): connect the HTTP repository to an existing OPSI 4.3
  server, import products, and optionally automate depot imports.
- [Windows client acceptance](CLIENT_ACCEPTANCE.md): prove install, repeat detection,
  upgrade, uninstall, and reboot behavior on a representative managed client.
- [Validation record](VALIDATION.md): dated repository-side checks and the limits of that
  evidence.

## Package maintainers and contributors

- [Package authoring](PACKAGE_AUTHORING.md): add or change recipes, source adapters,
  generated OPSI sources, revisions, and package verification.
- [Development](DEVELOPMENT.md): set up Python 3.13, run local checks, and understand
  GitHub Actions and GHCR image automation.
- [Source and format verification](SOURCES.md): OPSI command references, metadata origins,
  and source-policy notes.

## System reference

- [Architecture](ARCHITECTURE.md): module ownership, builder data flow, failure boundaries,
  persistence, artifacts, HTTP behavior, publication, and retention.
- [Repository tree](TREE.txt): tracked source layout and ownership at a glance.

For a package change, start with [Package authoring](PACKAGE_AUTHORING.md), complete its
server-side checks, then record the Windows result using
[Windows client acceptance](CLIENT_ACCEPTANCE.md). A valid `.opsi` archive is not evidence
that its bundled vendor installer works on a Windows client.
