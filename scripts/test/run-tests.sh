#!/bin/bash
# Run pytest for STT Service
# Usage: ./scripts/test/run-tests.sh [pytest_args]

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Activate conda environment
if command -v conda &> /dev/null; then
    eval "$(conda shell.bash hook)"
    conda activate stt-py311
fi

# Run pytest with test files in scripts/test/
echo "Running tests from scripts/test/"
echo ""

pytest scripts/test/test_routes.py -v "$@"
