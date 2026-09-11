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
echo "--- Removing unused Docker resources ---"
docker builder prune -f
docker image prune -f

echo ""
echo "--- Cleaning work directory ---"
rm -rf work/*
mkdir -p work
echo "work/ cleaned"

echo ""
echo "=== Cleanup complete ==="