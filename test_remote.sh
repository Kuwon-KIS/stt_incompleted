#!/bin/bash

# STT Service Remote Testing Script
# 이 스크립트는 배포된 서버에서 서비스를 테스트하는 데 사용됩니다.
# 서버의 IP나 도메인, 포트에 맞게 수정하여 사용하세요.

set -e

# 설정 (필요에 따라 수정하세요)
SERVICE_HOST="${SERVICE_HOST:-localhost}"
SERVICE_PORT="${SERVICE_PORT:-8002}"
BASE_URL="http://${SERVICE_HOST}:${SERVICE_PORT}"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}STT Service Remote Testing Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Target: ${BASE_URL}${NC}"
echo ""

# ===== Step 1: 헬스 체크 =====
echo -e "${YELLOW}[Step 1] 헬스 체크${NC}"
if curl -s "${BASE_URL}/healthz" | jq . > /dev/null 2>&1; then
    curl -s "${BASE_URL}/healthz" | jq .
    echo -e "${GREEN}✓ 서버 정상${NC}"
else
    echo -e "${RED}✗ 서버 연결 실패${NC}"
    exit 1
fi

# ===== Step 2: 템플릿 목록 확인 =====
echo -e "\n${YELLOW}[Step 2] 로드된 템플릿 목록 확인${NC}"
curl -s "${BASE_URL}/templates" | jq .
echo -e "${GREEN}✓ 템플릿 로드 확인${NC}"

# ===== Step 3: qwen_default 템플릿 조회 =====
echo -e "\n${YELLOW}[Step 3] qwen_default 템플릿 조회${NC}"
curl -s "${BASE_URL}/templates/qwen_default" | jq .
echo -e "${GREEN}✓ 템플릿 조회 완료${NC}"

# ===== Step 4: qwen_default 템플릿으로 테스트 =====
echo -e "\n${YELLOW}[Step 4] qwen_default 템플릿으로 테스트${NC}"
echo "요청 전송 중..."
curl -X POST "${BASE_URL}/process" \
  -H "Content-Type: application/json" \
  -d '{
    "inline_text": "The quick brown fox jumps over the lazy dog",
    "template_name": "qwen_default",
    "question": "What animals are mentioned?",
    "call_type": "vllm",
    "model_path": "qwen/qwen-7b-chat",
    "llm_url": "http://127.0.0.1:8002/mock/vllm",
    "callback_url": "http://127.0.0.1:8002/mock/callback"
  }' 2>/dev/null | jq .
echo -e "${GREEN}✓ qwen_default 템플릿 테스트 완료${NC}"

# ===== Step 5: generic 템플릿으로 테스트 =====
echo -e "\n${YELLOW}[Step 5] generic 템플릿으로 테스트${NC}"
curl -X POST "${BASE_URL}/process" \
  -H "Content-Type: application/json" \
  -d '{
    "inline_text": "Python is a powerful programming language for data science",
    "template_name": "generic",
    "question": "What is this about?",
    "call_type": "vllm",
    "model_path": "qwen/qwen-7b-chat",
    "llm_url": "http://127.0.0.1:8002/mock/vllm",
    "callback_url": "http://127.0.0.1:8002/mock/callback"
  }' 2>/dev/null | jq .
echo -e "${GREEN}✓ generic 템플릿 테스트 완료${NC}"

# ===== Step 6: Template 없이 테스트 =====
echo -e "\n${YELLOW}[Step 6] Template 없이 테스트 (raw text)${NC}"
curl -X POST "${BASE_URL}/process" \
  -H "Content-Type: application/json" \
  -d '{
    "inline_text": "FastAPI is a modern web framework",
    "call_type": "vllm",
    "model_path": "qwen/qwen-7b-chat",
    "llm_url": "http://127.0.0.1:8002/mock/vllm",
    "callback_url": "http://127.0.0.1:8002/mock/callback"
  }' 2>/dev/null | jq .
echo -e "${GREEN}✓ Raw text 테스트 완료${NC}"

# ===== Step 7: 한글 텍스트 Unicode 테스트 =====
echo -e "\n${YELLOW}[Step 7] 한글 텍스트 Unicode 테스트${NC}"
curl -X POST "${BASE_URL}/process" \
  -H "Content-Type: application/json" \
  -d '{
    "inline_text": "파이썬은 데이터 과학을 위한 강력한 프로그래밍 언어입니다",
    "template_name": "qwen_default",
    "question": "이것은 무엇에 관한 내용인가요?",
    "call_type": "vllm",
    "model_path": "qwen/qwen-7b-chat",
    "llm_url": "http://127.0.0.1:8002/mock/vllm",
    "callback_url": "http://127.0.0.1:8002/mock/callback"
  }' 2>/dev/null | jq .
echo -e "${GREEN}✓ 한글 테스트 완료${NC}"

# ===== Summary =====
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✓ 모든 테스트 완료!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}사용법:${NC}"
echo "  # 기본 (localhost:8002)"
echo "  ./test_remote.sh"
echo ""
echo "  # 커스텀 호스트"
echo "  SERVICE_HOST=example.com SERVICE_PORT=8080 ./test_remote.sh"
echo ""
echo "  # 환경변수 미리 설정"
echo "  export SERVICE_HOST=example.com"
echo "  export SERVICE_PORT=8080"
echo "  ./test_remote.sh"
echo ""
