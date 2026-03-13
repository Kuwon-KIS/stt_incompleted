#!/bin/bash
# Docker build script - builds image based on environment
# Usage: ./build.sh [dev|local|prod]

set -e

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ENV="${1:-dev}"
IMAGE_NAME="stt-service"
IMAGE_TAG="${ENV}-latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
OUTPUT_DIR="./output"

# Validate environment
if [[ ! " dev local prod " =~ " ${ENV} " ]]; then
    echo -e "${RED}❌ Invalid environment: $ENV${NC}"
    echo "Usage: ./build.sh [dev|local|prod]"
    exit 1
fi

# Check environment file
ENV_FILE="environments/.env.${ENV}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Environment file not found: $ENV_FILE${NC}"
    exit 1
fi

# Check requirements.txt
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt not found${NC}"
    exit 1
fi

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}Building Docker Image${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}Environment:${NC} $ENV"
echo -e "${GREEN}Image:${NC} $FULL_IMAGE"
echo -e "${GREEN}Config:${NC} $ENV_FILE"
echo -e "${BLUE}======================================${NC}"
echo ""

# Build image
echo -e "${YELLOW}Building image...${NC}"
if docker build \
    --build-arg ENV="$ENV" \
    -t "$FULL_IMAGE" \
    .; then
    echo -e "${GREEN}✓ Build successful: $FULL_IMAGE${NC}"
    echo ""
    
    # Show usage examples
    case "$ENV" in
        dev)
            echo -e "${BLUE}Run in development:${NC}"
            echo "  docker run -p 8002:8002 -e APP_ENV=dev $FULL_IMAGE"
            ;;
        local)
            echo -e "${BLUE}Run locally with volume mount:${NC}"
            echo "  docker run -p 8002:8002 -e APP_ENV=local \\"
            echo "    -v \$(pwd)/app/templates:/app/templates \\"
            echo "    $FULL_IMAGE"
            ;;
        prod)
            echo -e "${BLUE}Run in production:${NC}"
            echo "  docker run -p 8002:8002 -e APP_ENV=prod $FULL_IMAGE"
            echo ""
            echo -e "${BLUE}To push to registry:${NC}"
            echo "  docker tag $FULL_IMAGE <registry>/$FULL_IMAGE"
            echo "  docker push <registry>/$FULL_IMAGE"
            ;;
    esac
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi
PUSH=false
SAVE=false
BUILD_ENV="prod"  # 기본값: 프로덕션

# 인자 파싱 (shift로 REPOSITORY와 TAG 제거 후 처리)
shift || true
if [[ "$1" =~ ^[0-9a-zA-Z.-]+$ ]] && [[ ! "$1" =~ ^-- ]]; then
    # tag로 보이는 인자
    TAG="$1"
    shift || true
fi

# 옵션 파싱
while [[ $# -gt 0 ]]; do
    case "$1" in
        --push)
            PUSH=true
            ;;
        --save)
            SAVE=true
            ;;
        --env)
            shift
            BUILD_ENV="$1"
            if [[ "$BUILD_ENV" != "local" && "$BUILD_ENV" != "dev" && "$BUILD_ENV" != "prod" ]]; then
                echo -e "${RED}오류: --env는 'local', 'dev', 또는 'prod'여야 합니다.${NC}"
                usage
            fi
            ;;
        *)
            ;;
    esac
    shift
done

# .env 파일 확인
ENV_FILE=".env.${BUILD_ENV}"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}오류: $ENV_FILE 파일이 없습니다.${NC}"
    exit 1
fi

IMAGE="${REPOSITORY}:${TAG}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Docker Build & Push Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Repository:${NC} $REPOSITORY"
echo -e "${GREEN}Tag:${NC} $TAG"
echo -e "${GREEN}Full Image:${NC} $IMAGE"
echo -e "${GREEN}Build Env:${NC} $BUILD_ENV (.env.$BUILD_ENV)"
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
    # 레지스트리 푸시: Linux amd64만 지원 (이미지 사이즈 최소화)
    BUILD_CMD="docker buildx build \
  --build-arg ENV=$BUILD_ENV \
  --platform linux/amd64 \
  -t $IMAGE \
  --push \
  ."
    echo -e "${YELLOW}빌드 및 푸시 시작 (env=$BUILD_ENV, 플랫폼: linux/amd64)...${NC}"
elif [ "$SAVE" = true ]; then
    # TAR 파일로 저장: linux/amd64로 명시 지정 (buildx 사용)
    BUILD_CMD="docker buildx build \
  --build-arg ENV=$BUILD_ENV \
  --platform linux/amd64 \
  --load \
  -t $IMAGE \
  ."
    echo -e "${YELLOW}빌드를 진행 중... (env=$BUILD_ENV, TAR 파일 저장용, linux/amd64 플랫폼)${NC}"
else
    # 로컬 저장: 호스트 아키텍처로 빌드
    BUILD_CMD="docker build \
  --build-arg ENV=$BUILD_ENV \
  -t $IMAGE \
  ."
    echo -e "${YELLOW}빌드만 진행 중... (env=$BUILD_ENV, 로컬 저장, 호스트 아키텍처)${NC}"
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
        # TAR 파일로 저장 (output 디렉토리)
        mkdir -p "$OUTPUT_DIR"
        TAR_FILENAME="${REPOSITORY##*/}-${TAG}.tar"
        TAR_FILEPATH="$OUTPUT_DIR/$TAR_FILENAME"
        echo -e "${YELLOW}TAR 파일로 저장 중...${NC}"
        docker save -o "$TAR_FILEPATH" "$IMAGE"
        TAR_SIZE=$(du -h "$TAR_FILEPATH" | awk '{print $1}')
        echo ""
        echo -e "${GREEN}✓ 이미지가 TAR 파일로 저장되었습니다.${NC}"
        echo -e "${GREEN}파일명:${NC} $TAR_FILENAME"
        echo -e "${GREEN}파일크기:${NC} $TAR_SIZE"
        echo ""
        echo -e "${BLUE}Linux 서버에서 로드하는 방법:${NC}"
        echo "  docker load -i $TAR_FILENAME"
        echo ""
        echo -e "${BLUE}현재 위치:${NC}"
        echo "  $(pwd)/$TAR_FILEPATH"
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
