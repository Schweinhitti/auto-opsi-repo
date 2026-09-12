#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Running unit tests ==="

# Always ensure .venv has the required dependencies
python3 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q -r builder/requirements.txt pytest

.venv/bin/python -m compileall -q builder
.venv/bin/pytest -q

echo ""
echo "=== All tests passed ==="