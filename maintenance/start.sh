#!/bin/bash
set -euo pipefail

docker compose up -d

echo "Services started. Monitoring logs..."
docker compose logs -f