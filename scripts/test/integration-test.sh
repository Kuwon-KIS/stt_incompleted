#!/bin/bash

################################################################################
# STT 사후 점검 시스템 - 통합 테스트 스크립트
# 
# 사용법:
#   ./scripts/integration-test.sh                  # 기본값 (localhost:8002)
#   ./scripts/integration-test.sh 192.168.1.100 8080  # 리모트 서버
#   ./scripts/integration-test.sh stt-api.example.com 443  # HTTPS
#
# Docker 사용:
#   docker build -t stt-system .
#   docker run -d -p 8002:8002 --name stt-api stt-system
#   ./scripts/integration-test.sh localhost 8002
#
# 환경 변수:
#   API_HOST: API 서버 호스트 (기본값: localhost)
#   API_PORT: API 포트 (기본값: 8002)
#   API_PROTOCOL: HTTP/HTTPS (기본값: http)
#   TEST_DATE_START: 배치 시작 날짜 (기본값: 20260328)
#   TEST_DATE_END: 배치 종료 날짜 (기본값: 20260329)
#   TIMEOUT: 작업 완료 대기 시간 초 (기본값: 15)
#
################################################################################

set -euo pipefail

# ============================================================================
# 설정
# ============================================================================

# 기본값
API_HOST="${API_HOST:-${1:-localhost}}"
API_PORT="${API_PORT:-${2:-8002}}"
API_PROTOCOL="${API_PROTOCOL:-http}"
TEST_DATE_START="${TEST_DATE_START:-20260328}"
TEST_DATE_END="${TEST_DATE_END:-20260329}"
TIMEOUT="${TIMEOUT:-15}"

# 구성된 URL
API_BASE_URL="${API_PROTOCOL}://${API_HOST}:${API_PORT}"

# 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 통계
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# ============================================================================
# 유틸리티 함수
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((TESTS_PASSED++))
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    ((TESTS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_section() {
    echo -e "\n${CYAN}=== $1 ===${NC}"
}

print_separator() {
    echo "─────────────────────────────────────────────────────────────"
}

# JSON 포맷팅 (jq 없을 때 대비)
pretty_json() {
    if command -v jq &> /dev/null; then
        jq '.' 2>/dev/null || cat
    else
        cat
    fi
}

# API 호출
api_call() {
    local method=$1
    local endpoint=$2
    local data=${3:-}
    
    local url="${API_BASE_URL}${endpoint}"
    
    if [ -z "$data" ]; then
        curl -s -X "$method" "$url"
    else
        curl -s -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data"
    fi
}

# ============================================================================
# 테스트 시작
# ============================================================================

main() {
    echo ""
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║   STT 사후 점검 시스템 - 통합 테스트                      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    log_info "테스트 대상 API: ${API_BASE_URL}"
    log_info "호스트: ${API_HOST}, 포트: ${API_PORT}"
    log_info "배치 날짜: ${TEST_DATE_START} ~ ${TEST_DATE_END}"
    print_separator
    
    # 단계별 테스트
    test_healthz
    test_date_stats
    test_calendar_status
    test_batch_create
    test_batch_status
    test_batch_download
    
    # 최종 리포트
    print_final_report
}

# ============================================================================
# TEST 1: 헬스 체크
# ============================================================================

test_healthz() {
    log_section "TEST 1: 헬스 체크"
    ((TESTS_TOTAL++))
    
    log_info "GET /healthz"
    
    local response
    response=$(api_call GET "/healthz" 2>/dev/null)
    
    if echo "$response" | grep -q '"status"'; then
        log_success "서버 상태: 정상"
        echo "$response" | pretty_json
    else
        log_error "서버 응답 없음"
        return 1
    fi
}

# ============================================================================
# TEST 2: 날짜별 통계 API
# ============================================================================

test_date_stats() {
    log_section "TEST 2: 날짜별 통계 API"
    ((TESTS_TOTAL++))
    
    log_info "GET /api/admin/date-stats"
    
    local response
    response=$(api_call GET "/api/admin/date-stats" 2>/dev/null)
    
    if echo "$response" | grep -q '"total_dates"'; then
        log_success "날짜별 통계 조회 성공"
        
        # 통계 추출
        if command -v jq &> /dev/null; then
            local total_dates=$(echo "$response" | jq -r '.total_dates')
            local total_files=$(echo "$response" | jq -r '.total_files')
            local total_success=$(echo "$response" | jq -r '.total_success')
            local total_failed=$(echo "$response" | jq -r '.total_failed')
            
            echo -e "  총 날짜: ${CYAN}${total_dates}${NC}"
            echo -e "  총 파일: ${CYAN}${total_files}${NC}"
            echo -e "  성공: ${GREEN}${total_success}${NC}"
            echo -e "  실패: ${RED}${total_failed}${NC}"
            
            # 샘플 데이터
            log_info "최근 3개 날짜 샘플:"
            echo "$response" | jq '.dates[:3]'
        else
            echo "$response" | pretty_json
        fi
    else
        log_error "날짜별 통계 조회 실패"
        echo "$response"
        return 1
    fi
}

# ============================================================================
# TEST 3: 캘린더 상태 API
# ============================================================================

test_calendar_status() {
    log_section "TEST 3: 캘린더 상태 API"
    ((TESTS_TOTAL++))
    
    local year="2026"
    local month="3"
    
    log_info "GET /process/calendar/status/${year}/${month}"
    
    local response
    response=$(api_call GET "/process/calendar/status/${year}/${month}" 2>/dev/null)
    
    if echo "$response" | grep -q '"year"'; then
        log_success "캘린더 상태 조회 성공"
        
        if command -v jq &> /dev/null; then
            local date_count=$(echo "$response" | jq '.dates | length')
            echo -e "  처리된 날짜: ${CYAN}${date_count}개${NC}"
            
            # 샘플
            log_info "최근 3개 날짜:"
            echo "$response" | jq '.dates | to_entries[:3] | .[] | {date: .key, status: .value.status, total: .value.total}'
        else
            echo "$response" | pretty_json
        fi
    else
        log_error "캘린더 상태 조회 실패"
        echo "$response"
        return 1
    fi
}

# ============================================================================
# TEST 4: 배치 처리 생성
# ============================================================================

test_batch_create() {
    log_section "TEST 4: 배치 처리 생성"
    ((TESTS_TOTAL++))
    
    log_info "POST /process/batch/submit"
    
    local payload="{
        \"start_date\": \"${TEST_DATE_START}\",
        \"end_date\": \"${TEST_DATE_END}\",
        \"force_reprocess\": false,
        \"handle_overlap\": \"new\"
    }"
    
    log_info "요청 데이터: ${TEST_DATE_START} ~ ${TEST_DATE_END}"
    
    local response
    response=$(api_call POST "/process/batch/submit" "$payload" 2>/dev/null)
    
    if echo "$response" | grep -q '"job_id"'; then
        log_success "배치 작업 생성 성공"
        
        if command -v jq &> /dev/null; then
            BATCH_JOB_ID=$(echo "$response" | jq -r '.job_id')
            local case=$(echo "$response" | jq -r '.case')
            local status=$(echo "$response" | jq -r '.status')
            
            echo -e "  작업 ID: ${CYAN}${BATCH_JOB_ID}${NC}"
            echo -e "  상태: ${CYAN}${status}${NC}"
            echo -e "  케이스: ${CYAN}${case}${NC}"
        else
            BATCH_JOB_ID=$(echo "$response" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
            echo "$response" | pretty_json
        fi
        
        # 전역 변수에 저장
        export BATCH_JOB_ID
    else
        log_error "배치 작업 생성 실패"
        echo "$response"
        return 1
    fi
}

# ============================================================================
# TEST 5: 배치 상태 확인 (완료 대기)
# ============================================================================

test_batch_status() {
    log_section "TEST 5: 배치 상태 확인"
    ((TESTS_TOTAL++))
    
    if [ -z "${BATCH_JOB_ID:-}" ]; then
        log_error "배치 작업 ID가 없습니다"
        return 1
    fi
    
    log_info "GET /process/batch/status/${BATCH_JOB_ID}"
    log_info "작업 완료 대기 중 (최대 ${TIMEOUT}초)..."
    
    local elapsed=0
    local status="submitted"
    
    while [ "$status" != "completed" ] && [ $elapsed -lt $TIMEOUT ]; do
        sleep 1
        ((elapsed++))
        
        local response
        response=$(api_call GET "/process/batch/status/${BATCH_JOB_ID}" 2>/dev/null)
        
        if command -v jq &> /dev/null; then
            status=$(echo "$response" | jq -r '.status')
            local progress=$(echo "$response" | jq -r '.total_files // 0')
        else
            status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        fi
        
        if [ "$status" = "completed" ]; then
            break
        fi
        
        # 진행 상황 표시 (10초마다)
        if [ $((elapsed % 5)) -eq 0 ]; then
            echo -e "  ${YELLOW}...${NC} 진행 중... (${elapsed}초)"
        fi
    done
    
    if [ "$status" = "completed" ]; then
        log_success "배치 작업 완료"
        
        if command -v jq &> /dev/null; then
            local response
            response=$(api_call GET "/process/batch/status/${BATCH_JOB_ID}" 2>/dev/null)
            
            local total=$(echo "$response" | jq -r '.total_files')
            local success=$(echo "$response" | jq -r '.success_files')
            local failed=$(echo "$response" | jq -r '.failed_files')
            
            echo -e "  총 파일: ${CYAN}${total}${NC}"
            echo -e "  성공: ${GREEN}${success}${NC}"
            echo -e "  실패: ${RED}${failed}${NC}"
        fi
    else
        log_warning "배치 작업이 ${TIMEOUT}초 내에 완료되지 않음 (현재 상태: ${status})"
        log_info "계속해서 다운로드 테스트를 진행합니다"
    fi
}

# ============================================================================
# TEST 6: CSV 다운로드
# ============================================================================

test_batch_download() {
    log_section "TEST 6: CSV 다운로드"
    ((TESTS_TOTAL++))
    
    if [ -z "${BATCH_JOB_ID:-}" ]; then
        log_error "배치 작업 ID가 없습니다"
        return 1
    fi
    
    log_info "GET /process/batch/results/${BATCH_JOB_ID}/download"
    
    local csv_file="/tmp/batch_results_${BATCH_JOB_ID}.csv"
    
    if api_call GET "/process/batch/results/${BATCH_JOB_ID}/download" > "$csv_file" 2>/dev/null; then
        local file_size=$(wc -c < "$csv_file")
        local line_count=$(wc -l < "$csv_file")
        
        if [ "$file_size" -gt 0 ] && grep -q "date,filename,status" "$csv_file"; then
            log_success "CSV 다운로드 성공"
            echo -e "  파일 크기: ${CYAN}${file_size} bytes${NC}"
            echo -e "  줄 수: ${CYAN}${line_count}${NC}"
            echo -e "  저장 위치: ${CYAN}${csv_file}${NC}"
            
            # 헤더 표시
            log_info "CSV 헤더:"
            head -1 "$csv_file"
            
            # 데이터 샘플 (처음 3줄)
            log_info "데이터 샘플 (처음 3행):"
            tail -n +2 "$csv_file" | head -3 | cut -d',' -f1-5
        else
            log_error "CSV 파일이 유효하지 않음"
            return 1
        fi
    else
        log_error "CSV 다운로드 실패"
        return 1
    fi
}

# ============================================================================
# 최종 리포트
# ============================================================================

print_final_report() {
    echo ""
    print_separator
    log_section "테스트 완료 리포트"
    
    echo -e "  총 테스트: ${CYAN}${TESTS_TOTAL}${NC}"
    echo -e "  성공: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "  실패: ${RED}${TESTS_FAILED}${NC}"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo ""
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║  모든 테스트 통과! ✓                                       ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
        return 0
    else
        echo ""
        echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║  일부 테스트 실패 (${TESTS_FAILED}개)                                  ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
        return 1
    fi
}

# ============================================================================
# 메인 실행
# ============================================================================

# 선택사항: 텍스트 파일로 리포트 저장
if [ "${SAVE_REPORT:-}" = "true" ]; then
    REPORT_FILE="test_report_$(date +%Y%m%d_%H%M%S).txt"
    main 2>&1 | tee "$REPORT_FILE"
    log_info "리포트 저장: ${REPORT_FILE}"
else
    main
fi

exit $?
