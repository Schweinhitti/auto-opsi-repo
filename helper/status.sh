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
echo "=== Builder cycle health contract ==="
if [ -f "state/builder-status.json" ]; then
    PYTHONPATH=builder python3 -m builder.health --root "$ROOT_DIR" --json 2>/dev/null || \
        echo "  Could not evaluate builder-status.json"
    echo "  States: starting=initial grace, running=active cycle, success=last cycle ok, failed=cycle completed with errors, stale=no fresh progress."
    echo "  Recovery: inspect logs (./helper/logs.sh), run a manual cycle (./helper/build.sh), then restart builder if stale."
else
    echo "  No builder status file yet (waiting for first repo-builder startup)"
fi

echo ""
echo "=== Last build summary ==="
if [ -f "state/last-run.json" ]; then
    python3 -c "
import json
with open('state/last-run.json') as f:
    d = json.load(f)
summary = d.get('summary', d)
print(f\"  Updated: {len(summary.get('Updated', []))}\")
print(f\"  Unchanged: {len(summary.get('Unchanged', []))}\")
print(f\"  Failed: {len(summary.get('Failed', []))}\")
print(f\"  Warnings: {len(summary.get('Warnings', []))}\")
print(f\"  Disabled: {len(summary.get('Disabled', []))}\")
" 2>/dev/null || echo "  Could not parse last-run.json"
else
    echo "  No last-run.json found (no completed runs yet)"
fi