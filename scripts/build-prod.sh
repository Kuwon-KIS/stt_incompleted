#!/bin/bash

# Production build for On-premise Linux
# Uses docker buildx for multi-architecture (amd64 + arm64)

set -e

REGISTRY="${1:-docker.io}"
USERNAME="${2:-username}"
REPO_NAME="${3:-stt-service}"
TAG="${4:-prod}"
ENV="prod"

FULL_IMAGE="$REGISTRY/$USERNAME/$REPO_NAME:$TAG"

echo "🔨 Building production Docker images (amd64 + arm64)..."
echo "   Full image: $FULL_IMAGE"
echo "   Environment: $ENV"
echo "   Platforms: linux/amd64, linux/arm64"

# Check if buildx is available
if ! docker buildx version > /dev/null 2>&1; then
    echo "❌ Error: docker buildx is required for multi-architecture production builds"
    echo "   Please install buildx or run build-dev.sh for single-architecture build"
    exit 1
fi

# Build and push to registry
echo "📤 Building and pushing to registry (requires authentication)..."
docker buildx build --platform linux/amd64,linux/arm64 \
  -t "$FULL_IMAGE" \
  --build-arg ENV="$ENV" \
  -f Dockerfile \
  --push \
  .

echo "✅ Build and push completed successfully!"
echo "   Image: $FULL_IMAGE"
echo ""
echo "🚀 Image is now available in the registry:"
echo "   docker pull $FULL_IMAGE"
echo ""
echo "📊 Supported platforms:"
echo "   - linux/amd64 (Intel/AMD 64-bit)"
echo "   - linux/arm64 (ARM 64-bit, e.g., Apple Silicon)"
