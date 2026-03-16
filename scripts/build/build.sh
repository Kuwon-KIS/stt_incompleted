#!/bin/bash
# Docker build script - builds image based on environment with image export
# Usage: ./scripts/build/build.sh [dev|local|prod] [version]
# 
# Examples:
#   ./scripts/build/build.sh dev              # stt-service:dev-latest
#   ./scripts/build/build.sh dev 1.0.0        # stt-service:dev-1.0.0
#   ./scripts/build/build.sh prod v1.0.0      # stt-service:prod-v1.0.0
#
# Features:
#   - Build Docker image for specific environment
#   - Optional version specification (defaults to 'latest')
#   - Export as compressed .tar.gz for deployment
#   - Parallel compression with pigz (if available)
#   - Build logging and metadata tracking
#   - Optional rebuild with existing image detection

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

# Setup paths
OUTPUT_DIR="./output"
BUILD_LOG="/tmp/stt-build-$(date +%Y%m%d-%H%M%S).log"
START_TIME=$(date +%s)

# Parse arguments
ENV="${1:-dev}"
VERSION="${2:-latest}"
IMAGE_NAME="stt-service"
IMAGE_TAG="${ENV}-${VERSION}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

# ============================================================================
# Utility Functions
# ============================================================================

log_header() {
    local msg="$1"
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $msg${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo "$msg" >> "$BUILD_LOG"
}

log_step() {
    local step_num="$1"
    local step_name="$2"
    echo ""
    echo -e "${YELLOW}📌 Step $step_num: $step_name${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Step $step_num: $step_name" >> "$BUILD_LOG"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
    echo "[SUCCESS] $1" >> "$BUILD_LOG"
}

log_error() {
    echo -e "${RED}❌ Error: $1${NC}"
    echo "[ERROR] $1" >> "$BUILD_LOG"
    exit 1
}

log_info() {
    echo "   $1"
    echo "$1" >> "$BUILD_LOG"
}

elapsed_time() {
    local end_time=$(date +%s)
    local elapsed=$((end_time - START_TIME))
    echo "$((elapsed / 60))m $((elapsed % 60))s"
}

# ============================================================================
# Main Logic
# ============================================================================

log_header "STT Service Docker Build"

# Step 1: Validate environment
log_step "1" "Validate environment"

if [[ ! " dev local prod " =~ " ${ENV} " ]]; then
    log_error "Invalid environment: $ENV"
fi
log_info "Environment: $ENV"

# Check environment file
ENV_FILE="environments/.env.${ENV}"
if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
fi
log_success "Environment file found: $ENV_FILE"

# Check requirements.txt
if [ ! -f "requirements.txt" ]; then
    log_error "requirements.txt not found"
fi
log_success "requirements.txt found"

# Step 2: Check for existing images
log_step "2" "Check for existing images"

if docker images | grep -q "^${IMAGE_NAME}"; then
    log_info "Found existing images:"
    docker images | grep "^${IMAGE_NAME}" | awk '{printf "   %s:%s (%s)\n", $1, $2, $3}'
    echo ""
    read -p "Rebuild and delete existing images? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rmi $(docker images | grep "^${IMAGE_NAME}" | awk '{print $3}') || true
        log_success "Existing images deleted"
    else
        log_info "Using existing images"
    fi
else
    log_success "No existing images found"
fi

# Step 3: Create output directory
log_step "3" "Create output directory"

mkdir -p "$OUTPUT_DIR"
log_success "Output directory: $OUTPUT_DIR"

# Step 4: Build Docker image
log_step "4" "Build Docker image"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "  Image: $FULL_IMAGE"
echo "  Dockerfile: ./Dockerfile"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if docker build \
    --build-arg ENV="$ENV" \
    -t "$FULL_IMAGE" \
    -f Dockerfile \
    . 2>&1 | tee -a "$BUILD_LOG"; then
    log_success "Docker image build completed"
else
    log_error "Docker image build failed"
fi

# Display image info
echo ""
docker images | grep "$IMAGE_NAME" | grep "$ENV"

# Step 5: Export image as tar.gz
log_step "5" "Export image as compressed tar.gz"

TAR_FILENAME="${IMAGE_NAME}-${IMAGE_TAG}-$(date +%Y%m%d).tar.gz"
TAR_FILEPATH="${OUTPUT_DIR}/${TAR_FILENAME}"

echo "Export format: tar.gz"
log_info "Filename: $TAR_FILENAME"

# Use pigz for parallel compression if available
if command -v pigz &> /dev/null; then
    CORES=$(nproc)
    log_info "Using pigz for parallel compression (cores: $CORES)"
    docker save "$FULL_IMAGE" | pigz -6 -p $CORES > "$TAR_FILEPATH" 2>&1 | tee -a "$BUILD_LOG"
else
    log_info "Using gzip for compression (pigz not available)"
    docker save "$FULL_IMAGE" | gzip -6 > "$TAR_FILEPATH" 2>&1 | tee -a "$BUILD_LOG"
fi

if [ -f "$TAR_FILEPATH" ]; then
    TAR_SIZE=$(du -h "$TAR_FILEPATH" | awk '{print $1}')
    log_success "Image exported (size: $TAR_SIZE)"
    log_info "File: $TAR_FILEPATH"
else
    log_error "Failed to export image"
fi

# Step 6: Save build metadata
log_step "6" "Save build metadata"

BUILD_INFO_FILE="${OUTPUT_DIR}/build-info-${IMAGE_TAG}-$(date +%Y%m%d-%H%M%S).txt"
{
    echo "=========================================="
    echo "STT Service Docker Build Information"
    echo "=========================================="
    echo "Build Date: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Environment: $ENV"
    echo "Image Name: $FULL_IMAGE"
    echo "Tar.gz File: $TAR_FILENAME"
    echo "File Size: $TAR_SIZE"
    echo "Build Time: $(elapsed_time)"
    echo ""
    echo "Image Details:"
    docker images | grep "$FULL_IMAGE"
    echo ""
    echo "Deployment Instructions:"
    echo "  1. Copy tar.gz to target server:"
    echo "     scp $TAR_FILEPATH user@target:/path/to/images/"
    echo ""
    echo "  2. Load image on target server:"
    echo "     docker load -i $TAR_FILENAME"
    echo ""
    echo "  3. Run container:"
    case "$ENV" in
        dev)
            echo "     docker run -p 8002:8002 -e APP_ENV=dev $FULL_IMAGE"
            ;;
        prod)
            echo "     docker run -p 8002:8002 -e APP_ENV=prod $FULL_IMAGE"
            ;;
        local)
            echo "     docker run -p 8002:8002 -e APP_ENV=local $FULL_IMAGE"
            ;;
    esac
    echo ""
    echo "Build Log: $BUILD_LOG"
} > "$BUILD_INFO_FILE"

log_success "Build metadata saved: $BUILD_INFO_FILE"

# Step 7: Display summary
log_header "Build Complete! 🎉"

echo ""
echo -e "${BLUE}📊 Build Statistics${NC}"
echo "─────────────────────────────────────"
echo "  Image: $FULL_IMAGE"
echo "  Output: $TAR_FILENAME"
echo "  Size: $TAR_SIZE"
echo "  Time: $(elapsed_time)"
echo ""

echo -e "${BLUE}📦 Generated Files${NC}"
echo "─────────────────────────────────────"
ls -lh "${OUTPUT_DIR}" | grep -E "tar\.gz|build-info" | head -5 | awk '{print "  " $9 " (" $5 ")"}'
echo ""

echo -e "${BLUE}🚀 Deployment${NC}"
echo "─────────────────────────────────────"
echo "Copy to target server:"
echo "  scp $TAR_FILEPATH user@target:/path/"
echo ""
echo "Load on target:"
echo "  docker load -i $TAR_FILENAME"
echo ""

echo -e "${GREEN}✅ All steps completed successfully!${NC}"
echo ""
echo "📝 Detailed log: $BUILD_LOG"
