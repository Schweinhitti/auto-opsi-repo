#!/bin/bash
set -euo pipefail

docker compose down --remove-orphans

echo "Services stopped."