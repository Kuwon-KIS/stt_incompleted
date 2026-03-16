#!/bin/bash
# Local development server startup script
# Usage: ./scripts/dev-server.sh [port]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
PORT="${1:-8002}"

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  STT Service - Local Development Server${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if port is in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Port $PORT is already in use${NC}"
    echo ""
    read -p "Kill existing process on port $PORT and continue? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        lsof -ti:$PORT | xargs kill -9 || true
        sleep 1
    else
        echo "Exiting..."
        exit 1
    fi
fi

# Check conda environment
echo -e "${YELLOW}Checking conda environment...${NC}"
if ! conda env list | grep -q "stt-py311"; then
    echo -e "${RED}✗ Conda environment 'stt-py311' not found${NC}"
    echo "Please create it first or activate another environment"
    exit 1
fi

# Activate environment
echo -e "${YELLOW}Activating conda environment...${NC}"
eval "$(conda shell.bash hook)"
conda activate stt-py311

# Check Python
PYTHON_VERSION=$(python --version 2>&1)
echo -e "${GREEN}✓ Using: $PYTHON_VERSION${NC}"

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! python -c "import fastapi; import uvicorn; print('OK')" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -q -r requirements.txt
fi

# Check environment file
if [ ! -f "environments/.env.local" ]; then
    echo -e "${YELLOW}Creating environments/.env.local...${NC}"
    cat > "environments/.env.local" << 'EOF'
# Local development environment
APP_ENV=local
DEBUG=true
LOG_LEVEL=INFO
SFTP_HOST=localhost
SFTP_PORT=22
LLM_URL=http://localhost:8001/v1/chat/completions
EOF
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Starting development server...${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Server Configuration:${NC}"
echo "  Host: 127.0.0.1"
echo "  Port: $PORT"
echo "  Environment: local"
echo "  Reload: Enabled (auto-restart on code changes)"
echo ""
echo -e "${BLUE}Access Points:${NC}"
echo "  🌐 Web UI:        http://127.0.0.1:$PORT/"
echo "  📚 Swagger Docs:  http://127.0.0.1:$PORT/docs"
echo "  📋 ReDoc:         http://127.0.0.1:$PORT/redoc"
echo ""
echo -e "${BLUE}Endpoints:${NC}"
echo "  🏥 Health:        http://127.0.0.1:$PORT/health"
echo "  📈 Status:        http://127.0.0.1:$PORT/healthz"
echo "  📝 Templates:     http://127.0.0.1:$PORT/templates"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

# Start the server
exec python -m uvicorn app.main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --reload \
    --log-level info
