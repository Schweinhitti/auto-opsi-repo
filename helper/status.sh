#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Service status ==="
docker compose ps

echo ""
echo "=== Container health ==="
for svc in repo-builder repo-web; do
    health=$(docker compose ps -q "$svc" 2>/dev/null | xargs docker inspect --format='{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
    echo "  $svc: $health"
done

echo ""
echo "=== Last build summary ==="
if [ -f "state/last-run.json" ]; then
    python3 -c "
import json, sys
with open('state/last-run.json') as f:
    d = json.load(f)
print(f\"  Updated: {d.get('updated', 0)}\")
print(f\"  Unchanged: {d.get('unchanged', 0)}\")
print(f\"  Failed: {d.get('failed', 0)}\")
print(f\"  Warnings: {d.get('warnings', 0)}\")
print(f\"  Disabled: {d.get('disabled', 0)}\")
" 2>/dev/null || echo "  Could not parse last-run.json"
else
    echo "  No last-run.json found (no completed runs yet)"
fi

echo ""
echo "=== Repository file count ==="
if [ -d "repository" ]; then
    count=$(find repository -name '*.opsi' 2>/dev/null | wc -l)
    echo "  Packages in repository: $count"
else
    echo "  Repository directory not found"
fi
