# Maintenance Scripts

This directory contains helper scripts for maintaining the OPSI auto repository.

## Scripts

### `start.sh`

Start the docker-compose services:

```bash
./maintenance/start.sh
```

This runs `docker compose up -d` and follows the logs.

### `stop.sh`

Stop the docker-compose services:

```bash
./maintenance/stop.sh
```

This runs `docker compose down --remove-orphans` to stop all services and remove orphaned containers.

### `build.sh`

Rebuild the docker images:

```bash
./maintenance/build.sh
```

This runs `docker compose build` to rebuild images after changes to the builder/Dockerfile or environment variables.

### `add-package.sh`

Add a new package to the catalog via the interactive helper:

```bash
./maintenance/add-package.sh
```

This invokes the root `add-package.sh` script, which prompts for package details and appends a new entry to `catalog/packages.yaml`.

### `remove-package.sh`

Remove a package from the catalog:

```bash
./maintenance/remove-package.sh <package-id>
```

Removes the specified package entry from `catalog/packages.yaml`. This does **not** remove already-built `.opsi` archives from the repository directory.

## Prerequisites

- Docker Engine and modern Compose (`docker compose`)
- Python 3 with PyYAML (for `remove-package.sh`)
- Execute permissions on the scripts (`chmod +x *.sh`)