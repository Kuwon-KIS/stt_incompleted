#!/bin/bash
# Build script for production environment
# Usage: ./scripts/build/build-prod.sh [--push]

set -e

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

ENV="prod"
IMAGE_NAME="stt-service"
IMAGE_TAG="${ENV}-latest"
SHOULD_PUSH=${1:-}

echo "🔨 Building Docker image for $ENV environment..."
echo "   Image: $IMAGE_NAME:$IMAGE_TAG"

docker build \
    --build-arg ENV=$ENV \
    -t $IMAGE_NAME:$IMAGE_TAG \
    -f Dockerfile \
    .

echo "✅ Build complete!"

if [ "$SHOULD_PUSH" = "--push" ]; then
    echo "📤 Pushing image to registry..."
    # Note: Configure your registry in docker-compose or update this script
    docker push $IMAGE_NAME:$IMAGE_TAG
    echo "✅ Push complete!"
fi

echo ""
echo "Image ready: $IMAGE_NAME:$IMAGE_TAG"
