#!/bin/bash

################################################################################
# Docker 기반 테스트 스크립트
# 
# 사용법:
#   ./scripts/docker-test.sh                    # 기본: build + run + test
#   ./scripts/docker-test.sh --no-build         # 기존 이미지로 테스트
#   ./scripts/docker-test.sh --cleanup          # 테스트 후 컨테이너 삭제
#   ./scripts/docker-test.sh --help             # 도움말
#
# 환경:
#   DOCKER_IMAGE_NAME: 이미지 이름 (기본값: stt-system)
#   DOCKER_CONTAINER_NAME: 컨테이너 이름 (기본값: stt-api-test)
#   API_PORT: 외부 포트 (기본값: 8002)
#   CONTAINER_PORT: 내부 포트 (기본값: 8000)
#
################################################################################

set -euo pipefail

# ============================================================================
# 설정
# ============================================================================

DOCKER_IMAGE_NAME="${DOCKER_IMAGE_NAME:-stt-system}"
DOCKER_CONTAINER_NAME="${DOCKER_CONTAINER_NAME:-stt-api-test}"
API_PORT="${API_PORT:-8002}"
CONTAINER_PORT="${CONTAINER_PORT:-8000}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-./Dockerfile}"

BUILD=true
RUN=true
TEST=true
CLEANUP=false

# 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================================
# 유틸리티
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${CYAN}=== $1 ===${NC}"
}

print_help() {
    cat << EOF
STT 사후 점검 시스템 - Docker 테스트 스크립트

사용법:
  ./scripts/docker-test.sh [OPTIONS]

옵션:
  --no-build          기존 Docker 이미지 사용 (빌드 생략)
  --cleanup           테스트 후 컨테이너 및 이미지 삭제
  --only-build        빌드만 실행 (run/test 생략)
  --only-test         테스트만 실행 (run 생략, 기존 컨테이너 사용)
  --help              이 도움말 출력

환경 변수:
  DOCKER_IMAGE_NAME      Docker 이미지 이름 (기본값: stt-system)
  DOCKER_CONTAINER_NAME  Docker 컨테이너 이름 (기본값: stt-api-test)
  API_PORT               외부 포트 (기본값: 8002)
  CONTAINER_PORT         컨테이너 내부 포트 (기본값: 8000)
  DOCKERFILE_PATH        Dockerfile 경로 (기본값: ./Dockerfile)

예시:
  # 기본 실행 (빌드 → 실행 → 테스트)
  ./scripts/docker-test.sh

  # 기존 이미지로 테스트만 수행
  ./scripts/docker-test.sh --only-test

  # 테스트 후 정리
  ./scripts/docker-test.sh --cleanup

  # 다른 포트에서 실행
  API_PORT=9000 ./scripts/docker-test.sh

EOF
}

# ============================================================================
# 옵션 파싱
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-build)
            BUILD=false
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --only-build)
            RUN=false
            TEST=false
            shift
            ;;
        --only-test)
            BUILD=false
            RUN=false
            shift
            ;;
        --help)
            print_help
            exit 0
            ;;
        *)
            log_error "알 수 없는 옵션: $1"
            print_help
            exit 1
            ;;
    esac
done

# ============================================================================
# 메인 로직
# ============================================================================

main() {
    echo ""
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║   STT 사후 점검 시스템 - Docker 테스트                   ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    # Step 1: Docker 설치 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되어 있지 않습니다"
        exit 1
    fi
    log_success "Docker 설치 확인"

    # Step 2: 빌드
    if [ "$BUILD" = true ]; then
        build_docker_image
    fi

    # Step 3: 기존 컨테이너 정지
    if [ "$RUN" = true ]; then
        stop_existing_container
    fi

    # Step 4: 실행
    if [ "$RUN" = true ]; then
        run_docker_container
    fi

    # Step 5: 테스트
    if [ "$TEST" = true ]; then
        run_integration_tests
    fi

    # Step 6: 정리
    if [ "$CLEANUP" = true ]; then
        cleanup_docker
    fi

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  완료! ✓                                                  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ============================================================================
# 함수: Docker 이미지 빌드
# ============================================================================

build_docker_image() {
    log_section "Step 1: Docker 이미지 빌드"

    if [ ! -f "$DOCKERFILE_PATH" ]; then
        log_error "Dockerfile을 찾을 수 없습니다: $DOCKERFILE_PATH"
        exit 1
    fi

    log_info "이미지 빌드 중: $DOCKER_IMAGE_NAME"
    if docker build -t "$DOCKER_IMAGE_NAME" -f "$DOCKERFILE_PATH" . > /dev/null 2>&1; then
        log_success "Docker 이미지 빌드 완료"
        docker images | grep "$DOCKER_IMAGE_NAME" | head -1
    else
        log_error "Docker 이미지 빌드 실패"
        exit 1
    fi
}

# ============================================================================
# 함수: 기존 컨테이너 정지
# ============================================================================

stop_existing_container() {
    log_section "기존 컨테이너 확인"

    if docker ps -a --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER_NAME}$"; then
        log_info "기존 컨테이너 발견: $DOCKER_CONTAINER_NAME"
        
        if docker ps --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER_NAME}$"; then
            log_info "컨테이너 정지 중..."
            docker stop "$DOCKER_CONTAINER_NAME" > /dev/null
            log_success "컨테이너 정지"
        fi

        log_info "컨테이너 제거 중..."
        docker rm "$DOCKER_CONTAINER_NAME" > /dev/null
        log_success "컨테이너 제거"
    else
        log_info "기존 컨테이너 없음"
    fi
}

# ============================================================================
# 함수: Docker 컨테이너 실행
# ============================================================================

run_docker_container() {
    log_section "Step 2: Docker 컨테이너 실행"

    log_info "컨테이너 시작 중..."
    if docker run \
        -d \
        --name "$DOCKER_CONTAINER_NAME" \
        -p "${API_PORT}:${CONTAINER_PORT}" \
        -e "APP_ENV=local" \
        "$DOCKER_IMAGE_NAME" > /dev/null 2>&1; then
        log_success "컨테이너 시작 완료"
    else
        log_error "컨테이너 시작 실패"
        exit 1
    fi

    # 컨테이너 상태 확인
    log_info "컨테이너 상태: $(docker ps --filter name=$DOCKER_CONTAINER_NAME --format '{{.Status}}')"

    # 서버 준비 대기
    log_info "서버 준비 대기 중..."
    local attempts=0
    local max_attempts=30

    while [ $attempts -lt $max_attempts ]; do
        if curl -s "http://localhost:${API_PORT}/healthz" > /dev/null 2>&1; then
            log_success "서버 준비 완료"
            break
        fi
        ((attempts++))
        echo -n "."
        sleep 1
    done

    if [ $attempts -eq $max_attempts ]; then
        log_error "서버 준비 시간 초과"
        docker logs "$DOCKER_CONTAINER_NAME" | tail -20
        exit 1
    fi

    echo ""
}

# ============================================================================
# 함수: 통합 테스트 실행
# ============================================================================

run_integration_tests() {
    log_section "Step 3: 통합 테스트 실행"

    # API_HOST와 API_PORT를 override하여 테스트 스크립트 실행
    export API_HOST="localhost"
    export API_PORT="$API_PORT"
    export API_PROTOCOL="http"

    log_info "테스트 대상: http://localhost:${API_PORT}"

    if [ -f "./scripts/test/integration-test.sh" ]; then
        ./scripts/test/integration-test.sh
    else
        log_error "integration-test.sh를 찾을 수 없습니다"
        exit 1
    fi
}

# ============================================================================
# 함수: Docker 정리
# ============================================================================

cleanup_docker() {
    log_section "정리"

    log_info "컨테이너 정지 및 제거 중..."
    if docker ps -a --format '{{.Names}}' | grep -q "^${DOCKER_CONTAINER_NAME}$"; then
        docker stop "$DOCKER_CONTAINER_NAME" 2>/dev/null || true
        docker rm "$DOCKER_CONTAINER_NAME" 2>/dev/null || true
        log_success "컨테이너 제거 완료"
    fi

    log_info "이미지 제거 중..."
    if docker images --format '{{.Repository}}' | grep -q "^${DOCKER_IMAGE_NAME}$"; then
        docker rmi "$DOCKER_IMAGE_NAME" > /dev/null 2>&1
        log_success "이미지 제거 완료"
    fi
}

# ============================================================================
# 실행
# ============================================================================

main
