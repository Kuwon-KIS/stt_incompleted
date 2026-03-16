#!/bin/bash
# Build development environment image with tar.gz export
# Usage: ./scripts/build/build-dev.sh [version]
# 
# Examples:
#   ./scripts/build/build-dev.sh           # stt-service:dev-latest
#   ./scripts/build/build-dev.sh 1.0.0     # stt-service:dev-1.0.0

VERSION="${1:-latest}"
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
exec ./scripts/build/build.sh dev "$VERSION"
