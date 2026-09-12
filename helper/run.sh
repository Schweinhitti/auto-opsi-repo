#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Starting OPSI auto-repo services ==="

# Ensure directories have correct ownership for builder UID/GID
mkdir -p repository state work

# Ensure .env exists with correct builder UID/GID
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example"
    cp .env.example .env
    # Fix builder UID/GID if using defaults and current user differs
    if [ "${BUILDER_UID:-1000}" != "1000" ] || [ "${BUILDER_GID:-1000}" != "1000" ]; then
        echo "Setting BUILDER_UID/GID in .env to current user"
        sed -i "s/BUILDER_UID=1000/BUILDER_UID=${BUILDER_UID:-$(id -u)}/" .env
        sed -i "s/BUILDER_GID=1000/BUILDER_GID=${BUILDER_GID:-$(id -g)}/" .env
    fi
fi

# Ensure directories have correct ownership
chown -R "${BUILDER_UID:-1000}:${BUILDER_GID:-1000}" repository state work 2>/dev/null || true

docker compose up -d

echo ""
echo "=== Waiting for services to be ready ==="
# Wait for nginx healthcheck with timeout
for i in $(seq 1 30); do
    if docker compose ps -q repo-web | xargs -r wget -q -O /dev/null http://127.0.0.1/ 2>/dev/null; then
        echo "  Nginx is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  WARNING: Nginx not ready after 30 seconds"
    fi
    sleep 1
done

echo ""
echo "=== Service status ==="
docker compose ps

echo ""
echo "=== Repository accessible at http://localhost:${HTTP_PORT:-8088} ==="
echo "=== Monitor logs with: ./helper/logs.sh ==="