#!/bin/bash

# Development build for AWS EC2 Linux
# Uses docker buildx for single amd64 architecture

set -e

REGISTRY="${1:-docker.io}"
USERNAME="${2:-username}"
REPO_NAME="${3:-stt-service}"
TAG="${4:-dev}"
ENV="dev"

FULL_IMAGE="$REGISTRY/$USERNAME/$REPO_NAME:$TAG"

echo "🔨 Building development Docker image (amd64)..."
echo "   Full image: $FULL_IMAGE"
echo "   Environment: $ENV"

# Check if buildx is available
if ! docker buildx version > /dev/null 2>&1; then
    echo "⚠️  docker buildx not found. Using regular docker build (linux/amd64 only)"
    docker build -t "$FULL_IMAGE" \
      --build-arg ENV="$ENV" \
      -f Dockerfile \
      .
else
    # Use buildx for cross-platform build
    docker buildx build --platform linux/amd64 \
      -t "$FULL_IMAGE" \
      --build-arg ENV="$ENV" \
      -f Dockerfile \
      --load \
      .
fi

echo "✅ Build completed successfully!"
echo "   Image: $FULL_IMAGE"
echo ""
echo "📤 To push to registry (requires authentication):"
echo "   docker push $FULL_IMAGE"
echo ""
echo "🧪 To run locally for testing:"
echo "   docker run -p 8002:8002 $FULL_IMAGE"
