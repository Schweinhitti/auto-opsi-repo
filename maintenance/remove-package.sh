#!/bin/bash
set -euo pipefail

PACKAGES_FILE="catalog/packages.yaml"
if [ ! -f "$PACKAGES_FILE" ]; then
    echo "Error: $PACKAGES_FILE not found!" >&2
    exit 1
fi

if [ $# -lt 1 ]; then
    echo "Usage: $0 <package-id>" >&2
    echo "  Removes the given package from $PACKAGES_FILE" >&2
    exit 1
fi

PKG_ID="$1"

echo "Searching for package '$PKG_ID' in $PACKAGES_FILE..."

if grep -q "    id: $PKG_ID$" "$PACKAGES_FILE" || grep -qE "^  - id: $PKG_ID$" "$PACKAGES_FILE"; then
    echo "Package '$PKG_ID' found in catalog."
    echo "WARNING: This will remove the package entry (id, opsi_product_id, name, etc.) from $PACKAGES_FILE."
    echo "It will NOT remove the built .opsi packages in the repository/ directory."
    read -p "Are you sure you want to continue? (y/N): " CONFIRM
    if [[ "$CONFIRM" =~ ^[yY]$ ]]; then
        echo "Removing package '$PKG_ID' from $PACKAGES_FILE..."
        # Use Python for robust YAML manipulation
        python3 - "$PKG_ID" "$PACKAGES_FILE" <<'PYEOF'
import sys, yaml, io

pkg_id = sys.argv[1]
packages_file = sys.argv[2]

with open(packages_file, "r") as f:
    data = yaml.safe_load(f)

packages = data.get("packages", [])
updated = [p for p in packages if p.get("id") != pkg_id]

if len(updated) == len(packages):
    print(f"Package '{pkg_id}' not found in YAML packages list.")
    sys.exit(1)

data["packages"] = updated

import os
import tempfile

with tempfile.NamedTemporaryFile("w", dir=os.path.dirname(packages_file), delete=False) as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    f.flush()
    os.fsync(f.fileno())

os.replace(f.name, packages_file)

print(f"Package '{pkg_id}' removed successfully.")
PYEOF
    else
        echo "Aborted."
    fi
else
    echo "Package '$PKG_ID' not found in $PACKAGES_FILE."
    exit 1
fi