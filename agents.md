# Agent Guidelines for opsi-auto-repo

This file provides guidelines for AI agents working on this repository.

## Repository Overview

An automatic private OPSI 4.3 software repository that discovers upstream Windows releases, packages installers into `.opsi` archives, generates repository metadata, and serves results over HTTP. Built alongside an existing OPSI server without changing server configuration.

Key components:
- **repo-builder**: Python app using official OPSI CLI, runs on a 6-hour cycle
- **repo-web**: nginx read-only repository mount on configurable port (default 8088)
- **Catalog**: `catalog/packages.yaml` contains all product definitions and source settings
- **Publication**: Installers download to `work/`, pass checks, get packaged via OPSI tooling

## Development Workflow

### Running Tests
```bash
python3 -m venv .venv
.venv/bin/pip install -r builder/requirements.txt pytest
.venv/bin/python -m pytest -q
```

### Code Style
- Ruff linter with target Python 3.13
- Line length: 100 characters
- Lint selects: E4, E7, E9, F, I, UP, B

### Branch & PR Process
1. Create a new branch from `main` for each feature/fix
2. Commit changes with descriptive messages
3. Push branch and create a Pull Request
4. Address review feedback and rebase if needed

## Common Tasks

### Adding a Package
1. Add entry under `packages:` in `catalog/packages.yaml`
2. Use unique lowercase OPSI product ID (max 32 characters)
3. Include source settings, installer args, detection, and uninstall config
4. Run unit tests and a product dry run
5. Perform real build and Windows acceptance test

### Configuration
- Edit `.env` for environment variables
- Run `docker compose up -d` after changing env values
- Protect `.env` with `chmod 600 .env`
- Never commit tokens

### Building
```bash
# Initial setup
cp -n .env.example .env
mkdir -p repository state work
docker compose up -d --build

# Manual build
docker compose run --rm repo-builder --once --product auto-firefox
```

## Directory Structure
- `catalog/` - Product definitions and overrides
- `builder/` - Python builder source code
- `repository/` - OPSI repository data
- `state/` - Persistent state and checksums
- `work/` - Temporary download and build workspace
- `docs/` - Documentation files
- `.github/workflows/` - CI/CD workflows

## Testing Focus
Unit tests mock external network calls and focus on:
- Catalog/version/source selection
- Hashes and ZIP paths
- Generated files and migration
- Retention and duplicate prevention
- Failure paths

See `VALIDATION.md` for integration/Docker checks and real upstream results.