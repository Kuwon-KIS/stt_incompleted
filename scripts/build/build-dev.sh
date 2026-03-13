#!/bin/bash
# Build script for development environment
# Usage: ./scripts/build/build-dev.sh

set -e

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

ENV="dev"
IMAGE_NAME="stt-service"
IMAGE_TAG="${ENV}-latest"

echo "🔨 Building Docker image for $ENV environment..."
echo "   Image: $IMAGE_NAME:$IMAGE_TAG"

docker build \
    --build-arg ENV=$ENV \
    -t $IMAGE_NAME:$IMAGE_TAG \
    -f Dockerfile \
    .

echo "✅ Build complete!"
echo ""
echo "To run the container:"
echo "  docker run -p 8002:8002 -e APP_ENV=$ENV $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "With environment variables:"
echo "  docker run -p 8002:8002 \\"
echo "    -e APP_ENV=$ENV \\"
echo "    -e DEBUG=true \\"
echo "    -e SFTP_HOST=your-sftp-host \\"
echo "    -e LLM_URL=http://your-vllm-server:8001/v1/chat/completions \\"
echo "    $IMAGE_NAME:$IMAGE_TAG"
