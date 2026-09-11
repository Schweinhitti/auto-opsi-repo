#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

ADD_SCRIPT="$REPO_ROOT/add-package.sh"

if [ ! -f "$ADD_SCRIPT" ]; then
    echo "Error: add-package.sh not found at $ADD_SCRIPT" >&2
    exit 1
fi

echo "Launching package addition helper..."
bash "$ADD_SCRIPT"