#!/bin/bash
# Common utility functions for build scripts
# Source this file in other scripts: source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

# Color definitions
export RED='\033[0;31m'
export GREEN='\033[0;32m'
export YELLOW='\033[1;33m'
export BLUE='\033[0;34m'
export NC='\033[0m'

# Logging functions
log_header() {
    local msg="$1"
    echo ""
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $msg${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
}

log_step() {
    local step_num="$1"
    local step_name="$2"
    echo ""
    echo -e "${YELLOW}📌 Step $step_num: $step_name${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ Error: $1${NC}"
}

log_info() {
    echo "   $1"
}

log_warning() {
    echo -e "${YELLOW}⚠ Warning: $1${NC}"
}

# Elapsed time calculation
elapsed_time() {
    local start_time=$1
    local end_time=$(date +%s)
    local elapsed=$((end_time - start_time))
    echo "$((elapsed / 60))m $((elapsed % 60))s"
}

# Get project root from any build script
get_project_root() {
    cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd
}

# Validate Docker installation
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker not installed"
        return 1
    fi
    log_success "Docker installed: $(docker --version)"
    return 0
}

# Validate Docker daemon is running
check_docker_daemon() {
    if ! docker ps &> /dev/null; then
        log_error "Docker daemon not running"
        return 1
    fi
    log_success "Docker daemon is running"
    return 0
}

# Get image name from environment and version
get_image_tag() {
    local env=$1
    local version=$2
    echo "stt-post-review:${version}"
}

# Get tar.gz filename
get_tar_gz_filename() {
    local env=$1
    local version=$2
    echo "stt-post-review-${env}-${version}.tar.gz"
}
