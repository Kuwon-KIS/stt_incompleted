#!/bin/bash
# Validate build script setup and configuration
# Usage: ./scripts/build/validate-setup.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Build Environment Validation${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Check 1: Docker installed
echo -e "${YELLOW}1. Checking Docker installation...${NC}"
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo -e "${GREEN}✓ Docker installed: $DOCKER_VERSION${NC}"
else
    echo -e "${RED}✗ Docker not installed${NC}"
    exit 1
fi
echo ""

# Check 2: Build scripts exist and are executable
echo -e "${YELLOW}2. Checking build scripts...${NC}"
BUILD_SCRIPTS=("build.sh" "build-dev.sh" "build-prod.sh")
for script in "${BUILD_SCRIPTS[@]}"; do
    if [ -x "scripts/build/$script" ]; then
        SIZE=$(du -h "scripts/build/$script" | awk '{print $1}')
        echo -e "${GREEN}✓ $script (${SIZE})${NC}"
    else
        echo -e "${RED}✗ $script not found or not executable${NC}"
        exit 1
    fi
done
echo ""

# Check 3: Environment files
echo -e "${YELLOW}3. Checking environment files...${NC}"
ENV_FILES=(".env.dev" ".env.local" ".env.prod")
ENVS_FOUND=0
for env_file in "${ENV_FILES[@]}"; do
    if [ -f "environments/$env_file" ]; then
        SIZE=$(du -h "environments/$env_file" | awk '{print $1}')
        echo -e "${GREEN}✓ environments/$env_file (${SIZE})${NC}"
        ((ENVS_FOUND++))
    else
        echo -e "${RED}✗ environments/$env_file not found${NC}"
    fi
done
if [ $ENVS_FOUND -eq 0 ]; then
    echo -e "${YELLOW}⚠ Warning: No environment files found${NC}"
fi
echo ""

# Check 4: Required files
echo -e "${YELLOW}4. Checking required files...${NC}"
REQUIRED_FILES=("Dockerfile" "requirements.txt" "app/main.py" "app/config.py")
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        SIZE=$(du -h "$file" | awk '{print $1}')
        echo -e "${GREEN}✓ $file (${SIZE})${NC}"
    else
        echo -e "${RED}✗ $file not found${NC}"
        exit 1
    fi
done
echo ""

# Check 5: Output directory
echo -e "${YELLOW}5. Checking output directory...${NC}"
if [ -d "output" ]; then
    COUNT=$(ls output/*.tar.gz 2>/dev/null | wc -l)
    if [ $COUNT -gt 0 ]; then
        echo -e "${GREEN}✓ output directory exists with $COUNT tar.gz file(s)${NC}"
        ls -lh output/*.tar.gz | awk '{print "   " $9 " (" $5 ")"}'
    else
        echo -e "${GREEN}✓ output directory exists (empty)${NC}"
    fi
else
    echo -e "${RED}✗ output directory not found${NC}"
    echo -e "${YELLOW}Creating output directory...${NC}"
    mkdir -p output
fi
echo ""

# Check 6: Compression tools
echo -e "${YELLOW}6. Checking compression tools...${NC}"
if command -v pigz &> /dev/null; then
    PIGZ_VERSION=$(pigz --version 2>&1 | head -1)
    echo -e "${GREEN}✓ pigz available (parallel compression enabled)${NC}"
    CORES=$(nproc)
    echo "   CPU cores available: $CORES"
else
    echo -e "${YELLOW}⚠ pigz not installed (will use gzip - slower)${NC}"
    echo "   Install with: brew install pigz (macOS) or yum install pigz (RHEL)"
fi
echo ""

# Check 7: .gitignore configuration
echo -e "${YELLOW}7. Checking .gitignore configuration...${NC}"
if grep -q "output/" .gitignore && grep -q "\.tar\.gz" .gitignore; then
    echo -e "${GREEN}✓ output/ and *.tar.gz properly ignored in git${NC}"
else
    echo -e "${RED}✗ .gitignore not properly configured${NC}"
fi
echo ""

# Check 8: Dockerfile analysis
echo -e "${YELLOW}8. Analyzing Dockerfile...${NC}"
if grep -q "ARG ENV=" Dockerfile; then
    echo -e "${GREEN}✓ Build argument ENV defined${NC}"
fi
if grep -q "ENV APP_ENV=" Dockerfile; then
    echo -e "${GREEN}✓ Environment variable APP_ENV set${NC}"
fi
if grep -q "COPY.*environments" Dockerfile; then
    echo -e "${GREEN}✓ All environment files copied${NC}"
fi
echo ""

# Check 9: config.py analysis
echo -e "${YELLOW}9. Analyzing config.py...${NC}"
if grep -q "environments/.env" app/config.py; then
    echo -e "${GREEN}✓ config.py references environments/ directory${NC}"
fi
if grep -q "APP_ENV" app/config.py; then
    echo -e "${GREEN}✓ config.py uses APP_ENV variable${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Setup validation complete!${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Build development image:"
echo "     ./scripts/build/build-dev.sh           # version: latest (default)"
echo "     ./scripts/build/build-dev.sh 1.0.0     # version: 1.0.0"
echo ""
echo "  2. Build production image:"
echo "     ./scripts/build/build-prod.sh          # version: latest (default)"
echo "     ./scripts/build/build-prod.sh 1.0.0    # version: 1.0.0"
echo ""
echo "  3. Check build output: ls -lh output/"
echo "  4. Review build metadata: cat output/build-info-*.txt"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo "  See docs/BUILD_SCRIPT_GUIDE.md for detailed information"
echo ""
