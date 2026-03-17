#!/bin/bash

# Test script for Job Persistence Phase 2 - Database API Testing
# Usage: bash scripts/test_db_api.sh

set -e

BASE_URL="http://127.0.0.1:8002"
SLEEP_INTERVAL=2
LOG_FILE="/tmp/stt_test_$(date +%s).log"

echo "========================================="
echo "STT Job Persistence - Phase 2 테스트"
echo "========================================="
echo "📝 로그 파일: $LOG_FILE"
echo ""

# Kill any existing server on port 8002
pkill -9 -f "stt-py311.*8002" 2>/dev/null || true
sleep 1

# Start server in background
echo "🚀 테스트 서버 시작..."
cd /Users/a113211/workspace/stt_incompleted
conda run -n stt-py311 bash -c "APP_ENV=local python -m uvicorn app.main:app --host 127.0.0.1 --port 8002" 2>&1 &
SERVER_PID=$!
sleep 4

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 테스트 정리 중..."
    kill $SERVER_PID 2>/dev/null || true
    sleep 1
}

trap cleanup EXIT

# Step 1: 헬스 체크
echo "1️⃣  서버 헬스 체크..."
HEALTH=$(curl -s "$BASE_URL/health" || echo "failed")
if [[ $HEALTH == *"ok"* ]]; then
    echo "✅ 서버 정상 (응답: $HEALTH)"
else
    echo "❌ 서버 실패: $HEALTH"
    exit 1
fi
echo ""

# Step 2: DB 리셋
echo "2️⃣  DB 리셋..."
RESET=$(curl -s -X POST "$BASE_URL/api/admin/db/reset")
echo "✅ $RESET"
echo ""

# Step 3: DB 상태 확인
echo "3️⃣  DB 초기 상태 확인..."
STATUS=$(curl -s "$BASE_URL/api/admin/db/status")
echo "📊 $STATUS"
echo ""

# Step 4: 배치 제출
echo "4️⃣  배치 작업 제출 (20260314-20260314)..."
SUBMIT=$(curl -s -X POST "$BASE_URL/process/batch/submit" \
  -H "Content-Type: application/json" \
  -d '{"start_date": "20260314", "end_date": "20260314"}')
echo "📝 $SUBMIT"

# Extract job_id
JOB_ID=$(echo "$SUBMIT" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)
echo "🔗 Job ID: $JOB_ID"
echo ""

# Step 5: 배치 상태 모니터링 (최대 20초)
echo "5️⃣  배치 상태 모니터링 (최대 20초)..."
for i in {1..10}; do
    sleep $SLEEP_INTERVAL
    STATUS=$(curl -s "$BASE_URL/process/batch/status/$JOB_ID")
    JOB_STATUS=$(echo "$STATUS" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    echo "   ⏱️  ($((i*$SLEEP_INTERVAL))초) 상태: $JOB_STATUS"
    
    if [[ "$JOB_STATUS" == "completed" ]]; then
        echo "✅ 배치 완료!"
        break
    fi
done
echo ""

# Step 6: DB 최종 상태 확인
echo "6️⃣  DB 최종 상태 확인..."
FINAL_STATUS=$(curl -s "$BASE_URL/api/admin/db/status")
echo "📊 $FINAL_STATUS"
JOBS=$(echo "$FINAL_STATUS" | grep -o '"jobs":[0-9]*' | cut -d':' -f2)
RESULTS=$(echo "$FINAL_STATUS" | grep -o '"results":[0-9]*' | cut -d':' -f2)
DATES=$(echo "$FINAL_STATUS" | grep -o '"dates":[0-9]*' | cut -d':' -f2)
echo "   - Jobs: $JOBS, Results: $RESULTS, Dates: $DATES"
echo ""

# Step 7: 캘린더 API 확인
echo "7️⃣  캘린더 API (2026년 3월) 확인..."
CALENDAR=$(curl -s "$BASE_URL/process/calendar/status/2026/03")
echo "📅 $CALENDAR"
echo ""

# Step 8: 배치 상세 결과 확인
echo "8️⃣  배치 상세 결과 확인..."
DETAIL=$(curl -s "$BASE_URL/process/batch/status/$JOB_ID")
FINAL_JOB_STATUS=$(echo "$DETAIL" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
TOTAL_FILES=$(echo "$DETAIL" | grep -o '"total_files":[0-9]*' | cut -d':' -f2)
SUCCESS_FILES=$(echo "$DETAIL" | grep -o '"success_files":[0-9]*' | cut -d':' -f2)
echo "   최종 상태: $FINAL_JOB_STATUS"
echo "   처리 파일: $TOTAL_FILES (성공: $SUCCESS_FILES)"
echo ""

# Summary
echo "========================================="
if [[ "$FINAL_JOB_STATUS" == "completed" && "$RESULTS" -gt 0 && "$DATES" -gt 0 ]]; then
    echo "✅ 테스트 완료 - 모든 항목 정상!"
    echo "   ✓ DB 저장 완료"
    echo "   ✓ 배치 처리 완료"
    echo "   ✓ 캘린더 데이터 생성 완료"
else
    echo "⚠️  테스트 부분 완료"
    echo "   상태: $FINAL_JOB_STATUS"
    echo "   결과: $RESULTS개 저장됨"
    echo "   캘린더: $DATES개 날짜"
fi
echo "========================================="
