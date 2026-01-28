#!/bin/bash

# STT Service Local Testing Script
# 이 스크립트는 로컬에서 빌드하고 Mock API로 테스트하는 모든 명령어를 포함합니다.
# 배포 후 서버에서도 동일한 방식으로 테스트할 수 있습니다.

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
echo -e "${BLUE}STT Service Testing Script${NC}"
echo -e "${BLUE}========================================${NC}"

# ===== Step 1: Docker 빌드 =====
echo -e "\n${YELLOW}[Step 1] Docker 이미지 빌드 중...${NC}"
docker build -t stt-test:local . 2>&1 | tail -5
echo -e "${GREEN}✓ 빌드 완료${NC}"

# ===== Step 2: 컨테이너 실행 =====
echo -e "\n${YELLOW}[Step 2] Docker 컨테이너 실행 중...${NC}"
docker rm -f stt-test 2>/dev/null || true
sleep 1
docker run -d -p 8002:8002 --name stt-test stt-test:local
sleep 3
echo -e "${GREEN}✓ 컨테이너 시작 완료${NC}"

# ===== Step 3: 헬스 체크 =====
echo -e "\n${YELLOW}[Step 3] 헬스 체크${NC}"
curl -s http://localhost:8002/healthz | format_json
echo -e "${GREEN}✓ 서버 정상${NC}"

# ===== Step 4: 템플릿 목록 확인 =====
echo -e "\n${YELLOW}[Step 4] 로드된 템플릿 목록 확인${NC}"
curl -s http://localhost:8002/templates | format_json
echo -e "${GREEN}✓ 템플릿 로드 확인${NC}"

# ===== Step 5: qwen_default 템플릿 내용 확인 =====
echo -e "\n${YELLOW}[Step 5] qwen_default 템플릿 조회${NC}"
curl -s http://localhost:8002/templates/qwen_default | format_json
echo -e "${GREEN}✓ 템플릿 조회 완료${NC}"

# ===== Step 6: qwen_default 템플릿으로 테스트 =====
echo -e "\n${YELLOW}[Step 6] qwen_default 템플릿으로 Mock API 테스트${NC}"
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

# ===== Step 7: generic 템플릿으로 테스트 =====
echo -e "\n${YELLOW}[Step 7] generic 템플릿으로 Mock API 테스트${NC}"
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

# ===== Step 8: Template 없이 테스트 =====
echo -e "\n${YELLOW}[Step 8] Template 없이 테스트 (raw text)${NC}"
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

# ===== Step 9: 한글 텍스트 Unicode 테스트 =====
echo -e "\n${YELLOW}[Step 9] 한글 텍스트 Unicode 테스트${NC}"
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

# ===== Cleanup =====
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✓ 모든 테스트 완료!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}컨테이너 정지 및 정리:${NC}"
echo "  docker stop stt-test"
echo "  docker rm stt-test"
echo ""
echo -e "${YELLOW}로그 확인:${NC}"
echo "  docker logs -f stt-test"
echo ""
