#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Running unit tests ==="
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r builder/requirements.txt pytest
fi

.venv/bin/python -m compileall -q builder
.venv/bin/pytest -q

echo ""
echo "=== Running compose config validation ==="
docker compose config --quiet

echo ""
echo "=== Running nginx config validation ==="
docker compose run --rm repo-web nginx -t

echo ""
echo "=== All tests passed ==="
