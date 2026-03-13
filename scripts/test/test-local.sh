#!/bin/bash
# Local testing script - runs uvicorn and validates service
# Usage: ./scripts/test/test-local.sh [port]

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PORT=${1:-8002}
TIMEOUT=30

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}STT Service - Local Test${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Kill any existing process
lsof -i :$PORT 2>/dev/null | awk 'NR>1 {print $2}' | xargs -r kill -9 2>/dev/null
sleep 2

# Start service in background using conda
echo -e "${YELLOW}Starting uvicorn on port $PORT...${NC}"
conda run -n stt-py311 bash -c "cd $PROJECT_ROOT && uvicorn app.main:app --host 127.0.0.1 --port $PORT" > /tmp/uvicorn.log 2>&1 &
UVICORN_PID=$!
echo -e "${GREEN}✓ Process started (PID: $UVICORN_PID)${NC}"
echo ""

# Wait for service to start
echo -e "${YELLOW}Waiting for service to be ready...${NC}"
START_TIME=$(date +%s)
while true; do
    if curl -s http://127.0.0.1:$PORT/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is ready${NC}"
        break
    fi
    
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    if [ $ELAPSED -gt $TIMEOUT ]; then
        echo -e "${RED}✗ Service startup timeout (${TIMEOUT}s)${NC}"
        tail -20 /tmp/uvicorn.log
        kill $UVICORN_PID 2>/dev/null || true
        exit 1
    fi
    
    sleep 1
done
echo ""

# Run tests
echo -e "${BLUE}Testing endpoints:${NC}"
echo ""

tests_passed=0
tests_total=4

echo -e "${YELLOW}1. GET /health${NC}"
RESPONSE=$(curl -s http://127.0.0.1:$PORT/health)
echo "Response: $RESPONSE"
if echo "$RESPONSE" | grep -q '"status":"ok"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((tests_passed++))
else
    echo -e "${RED}✗ FAIL${NC}"
fi
echo ""

echo -e "${YELLOW}2. GET /healthz${NC}"
RESPONSE=$(curl -s http://127.0.0.1:$PORT/healthz)
echo "Response: $RESPONSE"
if echo "$RESPONSE" | grep -q '"status"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((tests_passed++))
else
    echo -e "${RED}✗ FAIL${NC}"
fi
echo ""

echo -e "${YELLOW}3. GET / (Web UI)${NC}"
if curl -s http://127.0.0.1:$PORT/ | grep -q "<!DOCTYPE" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((tests_passed++))
else
    echo -e "${RED}✗ FAIL${NC}"
fi
echo ""

echo -e "${YELLOW}4. GET /templates${NC}"
RESPONSE=$(curl -s http://127.0.0.1:$PORT/templates)
echo "Response: $RESPONSE"
if echo "$RESPONSE" | grep -q '"templates"'; then
    echo -e "${GREEN}✓ PASS${NC}"
    ((tests_passed++))
else
    echo -e "${RED}✗ FAIL${NC}"
fi
echo ""

echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}✓ Tests passed: $tests_passed/$tests_total${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Cleanup
echo -e "${YELLOW}Stopping service...${NC}"
kill $UVICORN_PID 2>/dev/null || true
sleep 1
lsof -i :$PORT 2>/dev/null | awk 'NR>1 {print $2}' | xargs -r kill -9 2>/dev/null || true

echo -e "${GREEN}✓ Done${NC}"
