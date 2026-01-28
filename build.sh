#!/bin/bash

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수: 사용법 출력
usage() {
    echo -e "${BLUE}사용법:${NC}"
    echo "  ./build.sh <repository> [tag] [--push|--save]"
    echo ""
    echo -e "${BLUE}예시:${NC}"
    echo "  ./build.sh docker.io/username/myapp latest --push"
    echo "  ./build.sh ghcr.io/username/myapp v1.0.0 --save"
    echo ""
    echo -e "${BLUE}옵션:${NC}"
    echo "  repository  : Docker 레지스트리 주소 (필수)"
    echo "  tag         : 이미지 태그 (기본값: latest)"
    echo "  --push      : 빌드 후 레지스트리에 푸시 (선택사항)"
    echo "  --save      : 빌드 후 tar 파일로 저장 (선택사항, Linux 서버 전송용)"
    echo ""
    echo -e "${BLUE}환경변수 (docker run 시 설정):${NC}"
    echo "  APP_ENV              : production 또는 development (기본값: production)"
    echo "  CALL_TYPE            : vllm 또는 agent (기본값: vllm)"
    echo "  LLM_URL              : vLLM/Agent 서버 주소"
    echo "  LLM_AUTH_HEADER      : 인증 헤더 (예: Bearer token)"
    echo "  MODEL_PATH           : vLLM 모델 경로 (예: qwen/qwen-7b-chat)"
    echo "  AGENT_NAME           : Agent 이름"
    echo "  USE_STREAMING        : true/false"
    echo "  SFTP_HOST            : SFTP 서버 주소"
    echo "  SFTP_PORT            : SFTP 포트 (기본값: 22)"
    echo "  SFTP_USERNAME        : SFTP 사용자명"
    echo "  SFTP_PASSWORD        : SFTP 비밀번호"
    echo "  SFTP_KEY             : SSH 개인키 (파일 경로 또는 Base64)"
    echo "  SFTP_ROOT_PATH       : SFTP 루트 경로"
    echo "  CALLBACK_URL         : 콜백 URL"
    echo "  TEMPLATE_NAME        : 프롬프트 템플릿 이름"
    echo "  BATCH_CONCURRENCY    : 병렬 처리 개수 (기본값: 4)"
    echo ""
    echo -e "${BLUE}실행 예시 (환경변수 설정):${NC}"
    echo "  docker run -e APP_ENV=production \\"
    echo "    -e LLM_URL=http://vllm-server:8000 \\"
    echo "    -e MODEL_PATH=qwen/qwen-7b-chat \\"
    echo "    -e SFTP_HOST=sftp.example.com \\"
    echo "    -e CALLBACK_URL=http://callback-server:3000/callback \\"
    echo "    $IMAGE"
    exit 1
}

# 인자 검증
if [ $# -lt 1 ]; then
    echo -e "${RED}오류: 레지스트리 주소를 입력해주세요.${NC}"
    usage
fi

REPOSITORY=$1
TAG=${2:-latest}
PUSH=false
SAVE=false

# --push 또는 --save 옵션 확인
if [ "$2" = "--push" ] || [ "$3" = "--push" ]; then
    PUSH=true
fi
if [ "$2" = "--save" ] || [ "$3" = "--save" ]; then
    SAVE=true
fi

IMAGE="${REPOSITORY}:${TAG}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker Build & Push Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Repository:${NC} $REPOSITORY"
echo -e "${GREEN}Tag:${NC} $TAG"
echo -e "${GREEN}Full Image:${NC} $IMAGE"
echo -e "${GREEN}Push:${NC} $([[ $PUSH == true ]] && echo "Yes" || echo "No")"
echo -e "${GREEN}Save as TAR:${NC} $([[ $SAVE == true ]] && echo "Yes" || echo "No")"
echo -e "${BLUE}========================================${NC}"
echo ""

# Docker buildx 확인
echo -e "${YELLOW}Docker buildx 버전 확인 중...${NC}"
if ! docker buildx version > /dev/null 2>&1; then
    echo -e "${RED}오류: Docker buildx가 설치되어 있지 않습니다.${NC}"
    echo "다음 명령어로 설치해주세요:"
    echo "  docker run --rm --privileged multiarch/qemu-user-static --reset -p yes"
    exit 1
fi
echo -e "${GREEN}✓ Docker buildx 확인 완료${NC}"
echo ""

# Builder 인스턴스 생성 또는 사용
BUILDER_NAME="multiarch-builder"
echo -e "${YELLOW}Builder 설정 중...${NC}"

if docker buildx ls 2>/dev/null | grep -q "^$BUILDER_NAME "; then
    echo -e "${GREEN}✓ 기존 builder '$BUILDER_NAME' 사용${NC}"
    docker buildx use "$BUILDER_NAME" 2>/dev/null || true
else
    echo -e "${YELLOW}새로운 builder '$BUILDER_NAME' 생성 중...${NC}"
    # 기존에 부분적으로 존재하는 builder 제거 시도
    docker buildx rm "$BUILDER_NAME" 2>/dev/null || true
    sleep 1
    # 새로운 builder 생성
    docker buildx create --name "$BUILDER_NAME" --use 2>/dev/null || {
        # 실패 시 --append 옵션으로 재시도
        echo -e "${YELLOW}--append 옵션으로 재시도 중...${NC}"
        docker buildx create --append --name "$BUILDER_NAME" --use || true
    }
    echo -e "${GREEN}✓ Builder 설정 완료${NC}"
fi
echo ""

# 빌드 명령어 구성
if [ "$PUSH" = true ]; then
    # 레지스트리 푸시: 멀티플랫폼 지원
    BUILD_CMD="docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t $IMAGE \
  --push \
  ."
    echo -e "${YELLOW}빌드 및 푸시 시작 (멀티플랫폼: linux/amd64,linux/arm64)...${NC}"
elif [ "$SAVE" = true ]; then
    # TAR 파일로 저장: linux/amd64로 명시 지정 (buildx 사용)
    BUILD_CMD="docker buildx build \
  --platform linux/amd64 \
  --load \
  -t $IMAGE \
  ."
    echo -e "${YELLOW}빌드를 진행 중... (TAR 파일 저장용, linux/amd64 플랫폼)${NC}"
else
    # 로컬 저장: 호스트 아키텍처로 빌드
    BUILD_CMD="docker build \
  -t $IMAGE \
  ."
    echo -e "${YELLOW}빌드만 진행 중... (로컬 저장, 호스트 아키텍처)${NC}"
fi

echo -e "${BLUE}실행 명령:${NC}"
echo "$BUILD_CMD"
echo ""

# 빌드 실행
if eval "$BUILD_CMD"; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✓ 빌드 완료!${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    if [ "$PUSH" = true ]; then
        echo -e "${GREEN}✓ 이미지가 $REPOSITORY에 푸시되었습니다.${NC}"
        echo ""
        echo -e "${BLUE}다음 명령어로 이미지를 사용할 수 있습니다:${NC}"
        echo "  docker run $IMAGE"
    elif [ "$SAVE" = true ]; then
        # TAR 파일로 저장
        TAR_FILENAME="${REPOSITORY##*/}-${TAG}.tar"
        echo -e "${YELLOW}TAR 파일로 저장 중...${NC}"
        docker save -o "$TAR_FILENAME" "$IMAGE"
        TAR_SIZE=$(du -h "$TAR_FILENAME" | awk '{print $1}')
        echo ""
        echo -e "${GREEN}✓ 이미지가 TAR 파일로 저장되었습니다.${NC}"
        echo -e "${GREEN}파일명:${NC} $TAR_FILENAME"
        echo -e "${GREEN}파일크기:${NC} $TAR_SIZE"
        echo ""
        echo -e "${BLUE}Linux 서버에서 로드하는 방법:${NC}"
        echo "  docker load -i $TAR_FILENAME"
        echo ""
        echo -e "${BLUE}현재 위치:${NC}"
        echo "  $(pwd)/$TAR_FILENAME"
    else
        echo -e "${YELLOW}주의: --load 옵션으로 빌드되어 로컬에서만 사용 가능합니다.${NC}"
        echo "      여러 아키텍처를 지원하려면 --push 옵션으로 레지스트리에 푸시하세요.${NC}"
        echo ""
        echo -e "${BLUE}이미지를 로컬에서 사용하려면:${NC}"
        echo "  docker run $IMAGE"
        echo ""
        echo -e "${BLUE}로컬 저장 없이 레지스트리에 푸시하려면:${NC}"
        echo "  ./build.sh $REPOSITORY $TAG --push"
        echo ""
        echo -e "${BLUE}TAR 파일로 저장하여 다른 서버에 전송하려면:${NC}"
        echo "  ./build.sh $REPOSITORY $TAG --save"
    fi
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}✗ 빌드 실패${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
