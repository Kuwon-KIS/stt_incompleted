#!/bin/bash

# STT Service Local Testing Script (Mac 로컬 환경)
# 이 스크립트는 로컬에서 build부터 테스트까지 전체 과정을 수행합니다.
# .env.local 설정을 사용하여 Mock API로 테스트합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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
echo -e "${BLUE}STT Service Local Testing (Mac)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ===== Step 1: 환경 변수 확인 =====
echo -e "${YELLOW}[Step 1] 로컬 환경 변수 확인 (.env.local)${NC}"
if [ -f ".env.local" ]; then
    echo -e "${GREEN}✓ .env.local 파일 found${NC}"
    echo ""
    echo "Key environment variables:"
    grep -E "^(APP_ENV|LLM_URL|SFTP_HOST|CALLBACK_URL|TEMPLATE_NAME|BATCH_CONCURRENCY|LOG_LEVEL)" .env.local || echo "  (파일에서 직접 확인)"
    echo ""
else
    echo -e "${RED}✗ .env.local 파일을 찾을 수 없습니다!${NC}"
    exit 1
fi

# ===== Step 2: Docker 빌드 =====
echo -e "${YELLOW}[Step 2] Docker 이미지 빌드 (local 환경)${NC}"
echo "명령어: ./build.sh stt-service local --env local"
echo ""
./build.sh stt-service local --env local 2>&1 | tail -10
echo -e "${GREEN}✓ 빌드 완료${NC}"
echo ""

# ===== Step 3: 컨테이너 실행 =====
echo -e "${YELLOW}[Step 3] Docker 컨테이너 실행 중...${NC}"
docker rm -f stt-test 2>/dev/null || true
sleep 1
docker run -d -p 8002:8002 --name stt-test stt-service:local
sleep 3
echo -e "${GREEN}✓ 컨테이너 시작 완료${NC}"
echo ""

# ===== Step 4: 헬스 체크 =====
echo -e "${YELLOW}[Step 4] 서버 헬스 체크${NC}"
RESPONSE=$(curl -s http://localhost:8002/healthz)
if [ -z "$RESPONSE" ]; then
    echo -e "${RED}✗ 서버 연결 실패${NC}"
    docker logs stt-test
    exit 1
fi
echo "$RESPONSE" | format_json
echo -e "${GREEN}✓ 서버 정상 구동 중${NC}"
echo ""

# ===== Step 5: 템플릿 목록 확인 =====
echo -e "${YELLOW}[Step 5] 로드된 템플릿 목록 확인${NC}"
curl -s http://localhost:8002/templates | format_json
echo -e "${GREEN}✓ 템플릿 로드 확인${NC}"
echo ""

# ===== Step 6: qwen_default 템플릿 내용 확인 =====
echo -e "${YELLOW}[Step 6] qwen_default 템플릿 조회${NC}"
curl -s http://localhost:8002/templates/qwen_default | format_json
echo -e "${GREEN}✓ 템플릿 조회 완료${NC}"
echo ""

# ===== Step 7: qwen_default 템플릿으로 테스트 =====
echo -e "${YELLOW}[Step 7] qwen_default 템플릿으로 Mock API 테스트${NC}"
curl -X POST http://localhost:8002/process \
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

# ===== Step 8: generic 템플릿으로 테스트 =====
echo -e "${YELLOW}[Step 8] generic 템플릿으로 Mock API 테스트${NC}"
curl -X POST http://localhost:8002/process \
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

# ===== Step 9: Template 없이 테스트 =====
echo -e "${YELLOW}[Step 9] Template 없이 테스트 (raw text)${NC}"
curl -X POST http://localhost:8002/process \
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

# ===== Step 10: 한글 텍스트 Unicode 테스트 =====
echo -e "${YELLOW}[Step 10] 한글 텍스트 Unicode 테스트${NC}"
curl -X POST http://localhost:8002/process \
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

# ===== Cleanup =====
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ 모든 로컬 테스트 완료!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}컨테이너 관리 명령어:${NC}"
echo "  # 로그 확인"
echo "  docker logs -f stt-test"
echo ""
echo "  # 컨테이너 환경변수 확인"
echo "  docker exec stt-test env | grep -E 'APP_ENV|LLM_URL|SFTP'"
echo ""
echo "  # 컨테이너 정지"
echo "  docker stop stt-test"
echo ""
echo "  # 컨테이너 삭제"
echo "  docker rm stt-test"
echo ""
