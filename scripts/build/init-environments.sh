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
# Development environment for AWS EC2 Linux
# Real services for integration testing

APP_ENV=dev
LOG_LEVEL=INFO

# SFTP (Development server)
SFTP_HOST=sftp-dev.internal
SFTP_PORT=22
SFTP_USERNAME=app_dev
SFTP_PASSWORD=
SFTP_KEY=
SFTP_ROOT_PATH=/uploads

# LLM Settings (Development vLLM server)
CALL_TYPE=vllm
LLM_URL=https://vllm-dev.internal:8000/v1/chat/completions
LLM_AUTH_HEADER=Bearer dev_token_xxx
MODEL_PATH=qwen-7b

# Agent (if using agent)
AGENT_NAME=sales-compliance-dev

# Template
TEMPLATE_NAME=qwen_default

# Callback (Development callback endpoint)
CALLBACK_URL=https://api-dev.internal/results
CALLBACK_AUTH_HEADER=Bearer dev_callback_token

# Batch processing
BATCH_CONCURRENCY=4

# Streaming
USE_STREAMING=false
EOF
            ;;
        local)
            cat > "$filepath" << 'EOF'
# Local development environment - macOS
# Mock/test configuration for development

APP_ENV=local
LOG_LEVEL=DEBUG

# SFTP (local/mock)
SFTP_HOST=localhost
SFTP_PORT=22
SFTP_USERNAME=local_user
SFTP_PASSWORD=
SFTP_KEY=
SFTP_ROOT_PATH=/tmp/uploads

# LLM Settings (local mock)
CALL_TYPE=vllm
LLM_URL=http://localhost:8000/v1/chat/completions
LLM_AUTH_HEADER=Bearer local_token
MODEL_PATH=qwen-7b

# Agent (if using agent)
AGENT_NAME=sales-compliance-local

# Template
TEMPLATE_NAME=qwen_default

# Callback (local mock endpoint)
CALLBACK_URL=http://localhost:8080/results
CALLBACK_AUTH_HEADER=Bearer local_callback_token

# Batch processing
BATCH_CONCURRENCY=2

# Streaming
USE_STREAMING=false
EOF
            ;;
        prod)
            cat > "$filepath" << 'EOF'
# Production environment - RHEL 8.9 (On-premise)
# High-performance production settings

APP_ENV=prod
LOG_LEVEL=WARNING

# SFTP (Production server)
SFTP_HOST=sftp-prod.internal
SFTP_PORT=22
SFTP_USERNAME=app_prod
SFTP_PASSWORD=
SFTP_KEY=
SFTP_ROOT_PATH=/uploads

# LLM Settings (Production vLLM server)
CALL_TYPE=vllm
LLM_URL=https://vllm-prod.internal:8000/v1/chat/completions
LLM_AUTH_HEADER=Bearer prod_token_xxx
MODEL_PATH=qwen-7b

# Agent (if using agent)
AGENT_NAME=sales-compliance-prod

# Template
TEMPLATE_NAME=qwen_default

# Callback (Production callback endpoint)
CALLBACK_URL=https://api-prod.internal/results
CALLBACK_AUTH_HEADER=Bearer prod_callback_token

# Batch processing
BATCH_CONCURRENCY=8

# Streaming
USE_STREAMING=false
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
echo "     docker run -p 8002:8002 -e APP_ENV=dev stt-post-review:dev-latest"
echo ""
