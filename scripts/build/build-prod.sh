#!/bin/bash
# Build production environment image with tar.gz export
# Usage: ./scripts/build/build-prod.sh [version]
# 
# Examples:
#   ./scripts/build/build-prod.sh           # stt-service:prod-latest
#   ./scripts/build/build-prod.sh 1.0.0     # stt-service:prod-1.0.0

VERSION="${1:-latest}"
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
exec ./scripts/build/build.sh prod "$VERSION"
