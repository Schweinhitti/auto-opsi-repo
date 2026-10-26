#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Starting OPSI auto-repo services ==="

# Ensure directories have correct ownership for builder UID/GID
mkdir -p repository state work

# Resolve local defaults used only when creating a new .env.
LOCAL_UID="$(id -u)"
LOCAL_GID="$(id -g)"

# Ensure .env exists with correct builder UID/GID
if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example"
    cp .env.example .env
    # Fix builder UID/GID if using defaults and current user differs
    if [ "$LOCAL_UID" != "1000" ] || [ "$LOCAL_GID" != "1000" ]; then
        echo "Setting BUILDER_UID/GID in .env to current user"
        sed -i "s/BUILDER_UID=1000/BUILDER_UID=$LOCAL_UID/" .env
        sed -i "s/BUILDER_GID=1000/BUILDER_GID=$LOCAL_GID/" .env
    fi
fi

# Use the same effective Compose configuration used for startup.
COMPOSE_CONFIG_JSON="$(docker compose config --format json)"
read -r BUILDER_UID BUILDER_GID HTTP_BIND_ADDRESS HTTP_PORT <<EOF
$(printf "%s" "$COMPOSE_CONFIG_JSON" | LOCAL_UID="$LOCAL_UID" LOCAL_GID="$LOCAL_GID" python3 -c '
import json
import os
import sys

data = json.load(sys.stdin)
services = data.get("services", {})

builder_user = str(services.get("repo-builder", {}).get("user", ""))
uid = ""
gid = ""
if ":" in builder_user:
    uid, gid = builder_user.split(":", 1)

bind = "0.0.0.0"
port = "8088"
ports = services.get("repo-web", {}).get("ports", [])
if ports:
    first = ports[0]
    if isinstance(first, dict):
        host_ip = first.get("host_ip")
        if host_ip:
            bind = str(host_ip)
        published = first.get("published")
        if published is not None and str(published):
            port = str(published)
    elif isinstance(first, str):
        value = first.strip()
        if value.count(":") >= 2:
            bind, port, _target = value.rsplit(":", 2)
        elif value.count(":") == 1:
            port, _target = value.rsplit(":", 1)

if not uid:
    uid = os.environ["LOCAL_UID"]
if not gid:
    gid = os.environ["LOCAL_GID"]

print(uid, gid, bind, port)
')
EOF

# Ensure directories have correct ownership
if ! chown -R "$BUILDER_UID:$BUILDER_GID" repository state work; then
    echo "ERROR: Failed to set ownership on repository/, state/, and work/ to ${BUILDER_UID}:${BUILDER_GID}." >&2
    echo "Check effective compose values and directory permissions with: docker compose config" >&2
    exit 1
fi

docker compose up -d

echo ""
echo "=== Waiting for services to be ready ==="
# Wait for nginx healthcheck with timeout
for i in $(seq 1 30); do
    if docker compose exec -T repo-web wget -q -O /dev/null http://127.0.0.1/; then
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
echo "=== Repository accessible at http://${HTTP_BIND_ADDRESS}:${HTTP_PORT} ==="
echo "=== Monitor logs with: ./helper/logs.sh ==="
