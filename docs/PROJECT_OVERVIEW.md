# Project Overview

[Back to the documentation index](README.md)

`auto-opsi-repo` is a self-hosted Docker stack that discovers upstream Windows
releases, downloads official installers, builds real OPSI 4.3 packages, creates
repository metadata with OPSI tooling, and serves the result over HTTP. OPSI
clients receive bundled installers, so they don't need WinGet or direct Internet
access to fetch those installers.

The project runs beside an existing OPSI server. Repository building and depot
importing are separate jobs. The builder doesn't change OPSI server
configuration, import products, or schedule client deployments.

## Components

* `repo-builder` reads `catalog/packages.yaml`, resolves releases, verifies
  downloads, builds packages, publishes them to `repository/`, and records
  persistent evidence in `state/`. It runs once at startup and then waits six
  hours by default.
* `repo-web` mounts `repository/` read-only and serves it through nginx. Its
  default host endpoint is `0.0.0.0:8088` over unauthenticated plain HTTP.
* `work/` contains private temporary build data. It isn't exposed by nginx.

Only one builder writer runs at a time. Publication uses complete files and
atomic renames, while repository metadata is generated before retention removes
older archives. One product failure doesn't stop checks for the remaining
products, but any failed product or repository metadata operation makes that
one-shot cycle unsuccessful.

## Start here

* Operators: [Getting Started](GETTING_STARTED.md),
  [Configuration](CONFIGURATION.md), [Operations](OPERATIONS.md), and
  [Troubleshooting](TROUBLESHOOTING.md)
* OPSI administrators: [Integration](INTEGRATION.md),
  [Client Acceptance](CLIENT_ACCEPTANCE.md), and [Security](SECURITY.md)
* Package maintainers: [Package Authoring](PACKAGE_AUTHORING.md) and
  [Sources](SOURCES.md)
* Contributors: [Development](DEVELOPMENT.md) and [Validation](VALIDATION.md)
* System reference: [Architecture](ARCHITECTURE.md) and
  [Repository Tree](TREE.txt)

Windows client installation, repeat-install detection, upgrade, reboot, and
uninstall acceptance remain required before broad deployment. Server-side
validation is recorded in [Validation](VALIDATION.md); it doesn't replace those
client tests.
