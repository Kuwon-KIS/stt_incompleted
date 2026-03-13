#!/bin/bash
# Docker build script - builds image based on environment
# Usage: ./scripts/build/build.sh [dev|local|prod]

set -e

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENV="${1:-dev}"
IMAGE_NAME="stt-service"
IMAGE_TAG="${ENV}-latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
OUTPUT_DIR="./output"

# Validate environment
if [[ ! " dev local prod " =~ " ${ENV} " ]]; then
    echo -e "${RED}❌ Invalid environment: $ENV${NC}"
    echo "Usage: ./scripts/build/build.sh [dev|local|prod]"
    exit 1
fi

# Check environment file
ENV_FILE="environments/.env.${ENV}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file not found: $ENV_FILE${NC}"
    exit 1
fi

# Check requirements.txt
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt not found${NC}"
    exit 1
fi

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Building Docker Image${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}Environment:${NC} $ENV"
echo -e "${GREEN}Image:${NC} $FULL_IMAGE"
echo -e "${GREEN}Config:${NC} $ENV_FILE"
echo -e "${BLUE}======================================${NC}"
echo ""

# Build image
echo -e "${YELLOW}Building image...${NC}"
if docker build \
    --build-arg ENV="$ENV" \
    -t "$FULL_IMAGE" \
    .; then
    echo -e "${GREEN}✓ Build successful: $FULL_IMAGE${NC}"
    echo ""
    
    # Show usage examples
    case "$ENV" in
        dev)
            echo -e "${BLUE}Run in development:${NC}"
            echo "  docker run -p 8002:8002 -e APP_ENV=dev $FULL_IMAGE"
            ;;
        local)
            echo -e "${BLUE}Run locally with volume mount:${NC}"
            echo "  docker run -p 8002:8002 -e APP_ENV=local \\"
            echo "    -v \$(pwd)/app/templates:/app/templates \\"
            echo "    $FULL_IMAGE"
            ;;
        prod)
            echo -e "${BLUE}Run in production:${NC}"
            echo "  docker run -p 8002:8002 -e APP_ENV=prod $FULL_IMAGE"
            echo ""
            echo -e "${BLUE}To push to registry:${NC}"
            echo "  docker tag $FULL_IMAGE <registry>/$FULL_IMAGE"
            echo "  docker push <registry>/$FULL_IMAGE"
            ;;
    esac
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi
