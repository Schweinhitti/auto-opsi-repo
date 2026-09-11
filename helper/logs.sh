#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

SERVICE="${1:-}"

case "$SERVICE" in
    builder|repo-builder)
        SERVICE="repo-builder"
        ;;
    web|repo-web)
        SERVICE="repo-web"
        ;;
    ""|"all")
        echo "=== Tailing all service logs (Ctrl+C to exit) ==="
        docker compose logs -f --tail=50
        exit 0
        ;;
    *)
        echo "Usage: $0 [builder|web|all]"
        echo ""
        echo "  builder   - Tail repo-builder logs"
        echo "  web       - Tail repo-web logs"
        echo "  all       - Tail all service logs (default)"
        exit 1
        ;;
esac

echo "=== Tailing $SERVICE logs (Ctrl+C to exit) ==="
docker compose logs -f --tail=50 "$SERVICE"