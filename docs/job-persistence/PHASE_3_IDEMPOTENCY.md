# Phase 3: Idempotency - Duplicate Processing Prevention

**작성 일자:** 2026년 3월 17일  
**상태:** ✅ 완료  
**커밋:** `2dce8c9` (병렬 처리 최적화)

---

## 📋 개요

Phase 3에서는 **중복 처리 방지 (Idempotency)** 기능을 구현하고, **병렬 처리 성능 최적화**를 진행했습니다.

### 🎯 목표
1. ✅ Agent 변경 시 재처리 가능 (탐지 방식 변경에 유연함)
2. ✅ 사용자 선택에 따른 유연한 처리
3. ✅ 병렬 처리로 성능 최적화

---

## 🔑 핵심 기능

### 1️⃣ 재처리 옵션 (`force_reprocess`)

기존 완료된 작업을 재처리할 수 있는 옵션:

```json
{
  "start_date": "20260314",
  "end_date": "20260314",
  "force_reprocess": true,  // ← 기존 완료 작업도 재처리
  "handle_overlap": "new"
}
```

**사용 사례:**
- Agent 알고리즘 변경 후 재탐지 필요
- 더 정확한 탐지 모델로 업그레이드

### 2️⃣ 겹침 처리 방식 (`handle_overlap`)

부분 겹침 시 처리 방식을 선택:

| 옵션 | 설명 | 사용 사례 |
|------|------|---------|
| `"new"` | 기존 작업 무시하고 새로 처리 (기본값) | 빠른 처리 필요 |
| `"reprocess_all"` | 겹치는 범위 포함하여 전체 재처리 | 완벽한 처리 필요 |
| `"skip_overlap"` | 겹치는 부분 제외하고 새 부분만 처리 | 효율적 처리 |

---

## 🎯 3가지 케이스

### **케이스 1: 전체 겹침 (정확히 동일한 범위)**

**상황:** 이전에 20260314를 처리했고, 같은 범위 재요청

```json
{
  "status": "duplicate",
  "case": "exact_overlap",
  "message": "정확히 동일한 범위의 작업이 이미 completed 상태입니다",
  "job_id": "기존_job_id"
}
```

**옵션별 동작:**
- `force_reprocess=false`: 기존 job_id 반환 → 재요청 방지
- `force_reprocess=true`: 새로운 job_id 생성 → 재처리

#### 테스트 결과 ✅
```bash
# 첫 번째 요청
curl -X POST /batch/submit -d '{"start_date":"20260314","end_date":"20260314"}'
→ job_id: a6fdcea0, status: "submitted"

# 같은 범위 재요청 (force_reprocess=false)
curl -X POST /batch/submit -d '{"start_date":"20260314","end_date":"20260314","force_reprocess":false}'
→ job_id: a6fdcea0, status: "duplicate"

# 강제 재처리 (force_reprocess=true)
curl -X POST /batch/submit -d '{"start_date":"20260314","end_date":"20260314","force_reprocess":true}'
→ job_id: 2b1c6d35 (새로운), status: "submitted"
```

---

### **케이스 2: 부분 겹침 (일부 날짜 겹침)**

**상황:** 20260314가 이미 처리됨, 20260313-20260315 범위 요청 (겹침)

```json
{
  "status": "partial_overlap_detected",
  "case": "partial_overlap",
  "message": "겹치는 범위가 감지되었습니다",
  "overlapping_jobs": [
    {
      "job_id": "기존_job_id",
      "status": "completed",
      "range": "20260314 to 20260314"
    }
  ],
  "available_options": {
    "new": "기존 작업 무시하고 새로 처리 (기본값)",
    "reprocess_all": "전체 범위 재처리",
    "skip_overlap": "겹치는 부분 제외하고 처리"
  }
}
```

**처리 방식:**

| handle_overlap | 동작 | 결과 |
|---|---|---|
| `"new"` | 기존 작업 무시, 전체 범위 새로 처리 | 새 job_id 생성 |
| `"reprocess_all"` | 전체 범위 재처리 | 새 job_id 생성 |
| `"skip_overlap"` | 겹치는 날짜 제외, 새 날짜만 처리 | 새 job_id 생성 |

#### 테스트 결과 ✅
```bash
# 부분 겹침 요청 (20260313-20260315, 20260314와 겹침)
curl -X POST /batch/submit -d '{"start_date":"20260313","end_date":"20260315"}'
→ job_id: 2d03f344 (새로운), status: "submitted"
```

---

### **케이스 3: 겹침 없음**

**상황:** 새로운 날짜 범위 요청

```json
{
  "job_id": "새로운_job_id",
  "status": "submitted",
  "case": "no_overlap",
  "date_range": "20260320 to 20260322"
}
```

#### 테스트 결과 ✅
```bash
# 새로운 범위 요청
curl -X POST /batch/submit -d '{"start_date":"20260320","end_date":"20260322"}'
→ job_id: 새로운_uuid, status: "submitted"
```

---

## ⚡ 성능 최적화 (병렬 처리)

### 구현 내용

**ThreadPoolExecutor 활용:**
- Mock 모드: 파일 생성을 병렬로 처리
- Real 모드: SFTP 파일 읽기 및 AI 처리를 병렬로 처리
- `max_workers=5`: 동시 처리 파일 수 제한

```python
# 병렬 처리 구현
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(process_file, f) for f in files]
    for future in as_completed(futures):
        result = future.result()
        # 결과 처리
```

### 성능 테스트 ✅

| 테스트 범위 | 파일 수 | 상태 | 처리 결과 |
|---|---|---|---|
| 5일 (20260314~20260318) | 15개 | ✅ completed | 15/15 성공 |
| 7일 (20260320~20260326) | 21개 | ✅ completed | 21/21 성공 |

**예상 성능 개선:**
- 순차 처리: 파일 수에 선형 증가
- 병렬 처리: 5개 파일 동시 처리로 약 5배 빠름

---

## 🛠️ 구현 세부사항

### API 변경사항

#### BatchProcessRequest (app/models.py)
```python
class BatchProcessRequest(BaseModel):
    start_date: str
    end_date: str
    force_reprocess: bool = False      # ← 추가
    handle_overlap: str = "new"        # ← 추가
```

#### /batch/submit 엔드포인트 (app/routes/process.py)
```python
@router.post("/batch/submit")
async def process_batch_submit(req: BatchProcessRequest):
    # 케이스 1: 전체 겹침
    # 케이스 2: 부분 겹침
    # 케이스 3: 겹침 없음
```

### 데이터베이스

**추가된 메서드 (app/database/manager.py):**
```python
def get_jobs_by_date_range(start_date: str, end_date: str) -> List[Dict]:
    """겹치는 날짜 범위의 모든 작업 조회"""
    # SQL: WHERE start_date <= ? AND end_date >= ?
```

### UI 변경사항

#### 배치 처리 폼 (app/static/index.html)
```html
<!-- 재처리 옵션 -->
<input type="checkbox" id="force-reprocess">
기존 완료된 작업도 재처리

<!-- 겹침 처리 방식 -->
<input type="radio" name="handle-overlap" value="new"> 새로 처리
<input type="radio" name="handle-overlap" value="reprocess_all"> 전체 재처리
<input type="radio" name="handle-overlap" value="skip_overlap"> 겹치는 부분 제외
```

#### API 호출 (app/static/js/api.js)
```javascript
async submitBatch(batchData) {
    return this.post('/process/batch/submit', {
        start_date: batchData.startDate,
        end_date: batchData.endDate,
        force_reprocess: batchData.forceReprocess,
        handle_overlap: batchData.handleOverlap
    });
}
```

#### 응답 처리 (app/static/js/app.js)
```javascript
// 케이스별 처리
if (response.case === 'no_overlap') {
    // 새 작업 처리
} else if (response.case === 'exact_overlap') {
    // 전체 겹침 처리
} else if (response.case === 'partial_overlap') {
    // 부분 겹침 처리
}
```

---

## 📊 테스트 결과

### 기능 검증

| 테스트 | 입력 | 예상 결과 | 실제 결과 | 상태 |
|--------|------|---------|---------|------|
| 케이스 1 - 첫 요청 | `20260314` | 새 job 생성 | ✅ job_id 생성 | PASS |
| 케이스 1 - 중복 | `20260314` (동일) | duplicate 반환 | ✅ 기존 job_id 반환 | PASS |
| 케이스 1 - 재처리 | `20260314` + `force_reprocess=true` | 새 job 생성 | ✅ 새 job_id 생성 | PASS |
| 케이스 2 - 부분 겹침 | `20260313-20260315` | 새 job 생성 | ✅ 새 job_id 생성 | PASS |
| 케이스 3 - 새 범위 | `20260320-20260322` | 새 job 생성 | ✅ 새 job_id 생성 | PASS |
| 병렬 처리 | 15개/21개 파일 | 모두 처리 | ✅ 15/15, 21/21 | PASS |

### DB 검증

```sql
-- 3개 job 모두 정상 처리
SELECT id, status, total_files, success_files FROM batch_jobs;
# 6178c459... | completed | 21 | 21
# 0a52ac78... | completed | 21 | 21
# cda2c6db... | completed | 15 | 15
```

---

## 🔄 워크플로우

```
사용자 요청
    ↓
BatchProcessRequest 수신
    ↓
겹침 확인 (get_jobs_by_date_range)
    ↓
┌─ active_jobs 있음?
│  ├─ Y: exact_match 확인
│  │  ├─ exact_overlap (케이스 1)
│  │  │  ├─ force_reprocess=true → 새 job 생성
│  │  │  └─ force_reprocess=false → duplicate 반환
│  │  └─ partial_overlap (케이스 2)
│  │     └─ handle_overlap 옵션으로 처리 → 새 job 생성
│  └─ N: 새 job 생성 (케이스 3)
│
새 job 생성 → 배치 처리 실행 (병렬)
    ↓
ThreadPoolExecutor 병렬 처리
    ↓
결과 저장 (DB)
    ↓
상태 업데이트 (completed)
    ↓
응답 반환
```

---

## 🎓 학습 포인트

### Idempotency 원칙
- **멱등성**: 동일한 요청을 여러 번 해도 같은 결과
- **유연성**: 사용자 선택에 따른 다양한 처리 옵션
- **안정성**: 각 파일의 독립적 처리 (하나 실패해도 나머지 처리)

### 병렬 처리 고려사항
- **동시성 제어**: max_workers로 리소스 관리
- **에러 처리**: as_completed로 안정적 결과 수집
- **로깅**: thread_id로 병렬 처리 추적

---

## 📝 다음 단계 (Phase 4)

- [ ] API 응답 캐싱 (Redis)
- [ ] 대용량 파일 처리 최적화 (스트리밍)
- [ ] 사용자 권한 관리
- [ ] 배치 실패 시 재시도 로직
- [ ] 통계 대시보드 고도화

---

## ✅ 체크리스트

- [x] 3가지 케이스 구현 및 테스트
- [x] 병렬 처리 구현
- [x] UI 옵션 추가
- [x] 문서화 완료
- [x] Git 커밋

---

**커밋 히스토리:**
```
2dce8c9 - perf: Implement parallel file processing with ThreadPoolExecutor
0a715c8 - feat: Job Persistence Phase 3 - Duplicate processing prevention
```
