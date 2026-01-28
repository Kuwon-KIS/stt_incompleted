#!/bin/bash

# STT Service Remote Testing Script (Linux dev/prod 환경)
# 이 스크립트는 배포된 dev/prod 서버에서 서비스와 환경변수를 점검합니다.
# 서버의 IP나 도메인, 포트에 맞게 수정하여 사용하세요.

set -e

# 설정 (필요에 따라 수정하세요)
SERVICE_HOST="${SERVICE_HOST:-localhost}"
SERVICE_PORT="${SERVICE_PORT:-8002}"
CONTAINER_NAME="${CONTAINER_NAME:-stt-service}"
BASE_URL="http://${SERVICE_HOST}:${SERVICE_PORT}"

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# jq 가용성 확인
if command -v jq &> /dev/null; then
    HAS_JQ=true
    echo -e "${GREEN}✓ jq detected - JSON formatting enabled${NC}"
else
    HAS_JQ=false
    echo -e "${YELLOW}⚠ jq not found - raw JSON output will be displayed${NC}"
fi

# JSON 포맷팅 헬퍼 함수
format_json() {
    if [ "$HAS_JQ" = true ]; then
        jq .
    else
        cat
    fi
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}STT Service Remote Testing (Linux)${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${CYAN}Target: ${BASE_URL}${NC}"
echo -e "${CYAN}Container: ${CONTAINER_NAME}${NC}"
echo ""

# ===== Step 1: 환경 변수 확인 =====
echo -e "${YELLOW}[Step 1] 컨테이너 환경 변수 확인${NC}"
if command -v docker &> /dev/null; then
    if docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "${CONTAINER_NAME}"; then
        echo -e "${GREEN}✓ 컨테이너 '${CONTAINER_NAME}' 실행 중${NC}"
        echo ""
        echo "Key environment variables:"
        docker exec "${CONTAINER_NAME}" env | grep -E "^(APP_ENV|LLM_URL|SFTP_HOST|CALLBACK_URL|TEMPLATE_NAME|BATCH_CONCURRENCY|LOG_LEVEL)" || echo "  (환경변수 확인 실패)"
        echo ""
        echo "All environment variables:"
        docker exec "${CONTAINER_NAME}" env | sort
        echo ""
    else
        echo -e "${YELLOW}⚠ 컨테이너를 찾을 수 없습니다. 로컬 환경변수 확인만 진행합니다.${NC}"
        echo ""
    fi
else
    echo -e "${YELLOW}⚠ Docker를 사용할 수 없습니다. 서비스 기능 테스트만 진행합니다.${NC}"
    echo ""
fi

# ===== Step 2: 헬스 체크 =====
echo -e "${YELLOW}[Step 2] 서버 헬스 체크${NC}"
RESPONSE=$(curl -s "${BASE_URL}/healthz")
if [ -z "$RESPONSE" ]; then
    echo -e "${RED}✗ 서버 연결 실패${NC}"
    echo "확인사항:"
    echo "  1. 서버 주소가 올바른지 확인: ${BASE_URL}"
    echo "  2. 방화벽 설정 확인"
    echo "  3. 서비스 실행 여부 확인: docker ps"
    echo "  4. 로그 확인: docker logs ${CONTAINER_NAME}"
    exit 1
else
    echo "$RESPONSE" | format_json
    echo -e "${GREEN}✓ 서버 정상 구동 중${NC}"
fi
echo ""

# ===== Step 3: 템플릿 목록 확인 =====
echo -e "${YELLOW}[Step 3] 로드된 템플릿 목록 확인${NC}"
curl -s "${BASE_URL}/templates" | format_json
echo -e "${GREEN}✓ 템플릿 로드 확인${NC}"
echo ""

# ===== Step 4: qwen_default 템플릿 조회 =====
echo -e "${YELLOW}[Step 4] qwen_default 템플릿 조회${NC}"
curl -s "${BASE_URL}/templates/qwen_default" | format_json
echo -e "${GREEN}✓ 템플릿 조회 완료${NC}"
echo ""

# ===== Step 5: qwen_default 템플릿으로 테스트 =====
echo -e "${YELLOW}[Step 5] qwen_default 템플릿으로 테스트${NC}"
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
  }' 2>/dev/null | format_json
echo -e "${GREEN}✓ qwen_default 템플릿 테스트 완료${NC}"
echo ""

# ===== Step 6: generic 템플릿으로 테스트 =====
echo -e "${YELLOW}[Step 6] generic 템플릿으로 테스트${NC}"
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
  }' 2>/dev/null | format_json
echo -e "${GREEN}✓ generic 템플릿 테스트 완료${NC}"
echo ""

# ===== Step 7: Template 없이 테스트 =====
echo -e "${YELLOW}[Step 7] Template 없이 테스트 (raw text)${NC}"
curl -X POST "${BASE_URL}/process" \
  -H "Content-Type: application/json" \
  -d '{
    "inline_text": "FastAPI is a modern web framework",
    "call_type": "vllm",
    "model_path": "qwen/qwen-7b-chat",
    "llm_url": "http://127.0.0.1:8002/mock/vllm",
    "callback_url": "http://127.0.0.1:8002/mock/callback"
  }' 2>/dev/null | format_json
echo -e "${GREEN}✓ Raw text 테스트 완료${NC}"
echo ""

# ===== Step 8: 한글 텍스트 Unicode 테스트 =====
echo -e "${YELLOW}[Step 8] 한글 텍스트 Unicode 테스트${NC}"
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
  }' 2>/dev/null | format_json
echo -e "${GREEN}✓ 한글 테스트 완료${NC}"
echo ""

# ===== Summary =====
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ 모든 원격 점검 완료!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}사용법:${NC}"
echo "  # 기본 (localhost:8002)"
echo "  ./test_remote.sh"
echo ""
echo "  # 커스텀 호스트 및 컨테이너 이름"
echo "  SERVICE_HOST=dev.example.com SERVICE_PORT=8080 CONTAINER_NAME=stt-api ./test_remote.sh"
echo ""
echo "  # 환경변수 미리 설정"
echo "  export SERVICE_HOST=prod.example.com"
echo "  export SERVICE_PORT=8080"
echo "  export CONTAINER_NAME=stt-api"
echo "  ./test_remote.sh"
echo ""
echo -e "${YELLOW}컨테이너 관리 명령어:${NC}"
echo "  # 컨테이너 환경변수 확인"
echo "  docker exec ${CONTAINER_NAME} env | grep -E 'APP_ENV|LLM_URL|SFTP'"
echo ""
echo "  # 컨테이너 로그 확인"
echo "  docker logs -f ${CONTAINER_NAME}"
echo ""
echo "  # 컨테이너 상태 확인"
echo "  docker ps --filter \"name=${CONTAINER_NAME}\""
echo ""
