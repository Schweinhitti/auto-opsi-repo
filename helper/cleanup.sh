#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Cleaning up OPSI auto-repo ==="

echo "--- Stopping services ---"
docker compose stop

echo ""
echo "--- Removing stopped containers ---"
docker compose rm -f

echo ""
echo "--- Cleanup complete ---"
# Note: Docker resource pruning (builder/image) is project-specific.
# To clean only this project's resources, run:
#   docker compose down --rmi all --volumes
echo "  (Skipping global Docker resource pruning to avoid affecting other projects)"