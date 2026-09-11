#!/bin/bash
set -euo pipefail

# Build the docker-compose images
docker compose build

echo "Build complete."