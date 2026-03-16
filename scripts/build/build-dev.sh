#!/bin/bash
# Build development environment image with optional tar.gz loading and testing
# Usage: ./scripts/build/build-dev.sh [version] [--load] [--run]
#
# Examples:
#   ./scripts/build/build-dev.sh                # Build only
#   ./scripts/build/build-dev.sh 1.0.0          # Build specific version
#   ./scripts/build/build-dev.sh 1.0.0 --load   # Build and load to Docker
#   ./scripts/build/build-dev.sh 1.0.0 --run    # Build, load, and run for testing

VERSION="${1:-latest}"
shift || true
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
exec ./scripts/build/build.sh dev "$VERSION" "$@"
