#!/bin/bash
# Initialize environment files for deployment environments
# Usage: ./scripts/build/init-environments.sh [env1,env2,...]
# Examples:
#   ./scripts/build/init-environments.sh           # Create all (dev, local, prod)
#   ./scripts/build/init-environments.sh dev,prod  # Create specific environments

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Parse arguments
ENVS_TO_INIT="${1:-dev,local,prod}"
IFS=',' read -ra ENVS <<< "$ENVS_TO_INIT"

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Initialize Environment Files${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Ensure environments directory exists
if [ ! -d "environments" ]; then
    echo -e "${YELLOW}Creating environments directory...${NC}"
    mkdir -p environments
    touch environments/.gitkeep
fi

# Create template environment files
create_env_file() {
    local env=$1
    local filepath="environments/.env.${env}"
    
    if [ -f "$filepath" ]; then
        echo -e "${YELLOW}ℹ $filepath already exists (skipping)${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}Creating $filepath...${NC}"
    
    case "$env" in
        dev)
            cat > "$filepath" << 'EOF'
# Development Environment - RHEL 8.9 (AWS EC2)
APP_ENV=dev
DEBUG=false
LOG_LEVEL=INFO

# SFTP Configuration
SFTP_HOST=your-sftp-host
SFTP_PORT=22
SFTP_USERNAME=your-username
SFTP_PASSWORD=your-password
SFTP_SOURCE_PATH=/source/path
SFTP_BATCH_PATH=/batch/path

# LLM Configuration
LLM_URL=http://localhost:8001/v1/chat/completions
LLM_MODEL=qwen

# Processing Configuration
MAX_WORKERS=4
REQUEST_TIMEOUT=300
EOF
            ;;
        local)
            cat > "$filepath" << 'EOF'
# Local Development Environment - macOS
APP_ENV=local
DEBUG=true
LOG_LEVEL=DEBUG

# SFTP Configuration (mock/disabled for local)
SFTP_HOST=localhost
SFTP_PORT=22
SFTP_USERNAME=local_user
SFTP_PASSWORD=
SFTP_SOURCE_PATH=/tmp/source
SFTP_BATCH_PATH=/tmp/batch

# LLM Configuration (mock)
LLM_URL=http://localhost:8001/v1/chat/completions
LLM_MODEL=qwen

# Processing Configuration
MAX_WORKERS=2
REQUEST_TIMEOUT=60
EOF
            ;;
        prod)
            cat > "$filepath" << 'EOF'
# Production Environment - RHEL 8.9 (On-premise)
APP_ENV=prod
DEBUG=false
LOG_LEVEL=WARNING

# SFTP Configuration
SFTP_HOST=your-prod-sftp-host
SFTP_PORT=22
SFTP_USERNAME=your-prod-username
SFTP_PASSWORD=your-prod-password
SFTP_SOURCE_PATH=/production/source
SFTP_BATCH_PATH=/production/batch

# LLM Configuration
LLM_URL=http://your-prod-llm-host:8001/v1/chat/completions
LLM_MODEL=qwen

# Processing Configuration
MAX_WORKERS=8
REQUEST_TIMEOUT=600
EOF
            ;;
        *)
            echo -e "${RED}Unknown environment: $env${NC}"
            return 1
            ;;
    esac
    
    echo -e "${GREEN}✓ Created $filepath${NC}"
}

# Initialize requested environments
echo "Initializing environments: ${ENVS[*]}"
echo ""

CREATED_COUNT=0
SKIPPED_COUNT=0

for env in "${ENVS[@]}"; do
    if create_env_file "$env"; then
        if [ -f "environments/.env.${env}" ]; then
            CREATED_COUNT=$((CREATED_COUNT + 1))
        else
            SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        fi
    fi
done

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Initialization complete${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "  Created: $CREATED_COUNT files"
echo "  Skipped (already exist): $SKIPPED_COUNT files"
echo ""

# Show current environment files
echo -e "${BLUE}Current environment files:${NC}"
ls -lh environments/.env.* 2>/dev/null || echo "  (none found)"
echo ""

# Security reminder
echo -e "${YELLOW}⚠ Security Reminder:${NC}"
echo "  - All .env.* files are git-ignored (never commit)"
echo "  - Update SFTP_PASSWORD and LLM_URL with real values"
echo "  - Never commit credentials to version control"
echo "  - Use environment variable overrides for production"
echo ""

# Next steps
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Edit environment files with real configuration:"
for env in "${ENVS[@]}"; do
    echo "     nano environments/.env.${env}"
done
echo ""
echo "  2. Build Docker image:"
echo "     ./scripts/build/build-dev.sh"
echo ""
echo "  3. Run Docker container:"
echo "     docker run -p 8002:8002 -e APP_ENV=dev stt-service:dev-latest"
echo ""
