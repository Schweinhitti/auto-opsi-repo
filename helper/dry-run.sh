#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PRODUCT="${1:-}"

echo "=== Running builder dry run ==="

CMD=(docker compose run --rm repo-builder --dry-run)
if [ -n "$PRODUCT" ]; then
    CMD+=(--product "$PRODUCT")
fi

"${CMD[@]}"

echo ""
echo "=== Dry run complete ==="