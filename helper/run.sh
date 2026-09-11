#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Starting OPSI auto-repo services ==="

if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example"
    cp .env.example .env
fi

mkdir -p repository state work

docker compose up -d

echo ""
echo "=== Waiting for services to be ready ==="
sleep 5

echo ""
echo "=== Service status ==="
docker compose ps

echo ""
echo "=== Repository accessible at http://localhost:8088 ==="
echo "=== Monitor logs with: ./helper/logs.sh ===="