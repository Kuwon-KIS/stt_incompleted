#!/bin/bash

# Local development build for macOS
# Creates a single-platform Docker image for local testing

set -e

REPO_NAME="${1:-stt-service}"
TAG="${2:-local}"
ENV="local"

echo "🔨 Building local Docker image..."
echo "   Repository: $REPO_NAME"
echo "   Tag: $TAG"
echo "   Environment: $ENV"

docker build -t "$REPO_NAME:$TAG" \
  --build-arg ENV="$ENV" \
  -f Dockerfile \
  .

echo "✅ Build completed successfully!"
echo "   Image: $REPO_NAME:$TAG"
echo ""
echo "📦 To run the image:"
echo "   docker run -p 8002:8002 $REPO_NAME:$TAG"
echo ""
echo "💡 To run with custom environment variables:"
echo "   docker run -p 8002:8002 -e SFTP_HOST=your-host $REPO_NAME:$TAG"
