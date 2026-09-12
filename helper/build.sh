#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Building OPSI auto-repo Docker images ==="
docker compose build --pull repo-builder repo-web

echo ""
echo "=== Verifying compose config ==="
docker compose config --quiet

echo ""
echo "=== Done: images built successfully ==="
