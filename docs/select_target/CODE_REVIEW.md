# SELECT_TARGET: 기존 코드 재활용 검토

## 1. 기존 코드 재활용 현황

### 1.1 ✅ 재활용 가능한 항목

#### (1) Date Statistics API
**위치**: `app/routes/admin.py` GET `/api/admin/date-stats`
**현재 기능**:
- 날짜별 처리 현황 조회 (완료/부분/실패 상태)
- DB 집계 데이터 제공
- 범위 필터링 지원

**재활용 방법**:
- ✅ 그대로 사용 (기존 API가 이미 요구사항 충족)
- 단, PLAN.md의 `DateStats` 모델과 응답 형식 재검토 필요

**코드 위치**:
```python
# app/database/manager.py:408
def get_date_statistics(self, start_date=None, end_date=None)
    # 단일 정보 소스 (SSOT - Single Source of Truth)
    # 캘린더/대시보드 모두 사용
```

---

#### (2) SFTP 날짜 조회 기능
**위치**: `app/sftp_client.py`
**기존 메서드**:
- `MockSFTPClient.listdir(path)` - Mock 날짜 반환
- `SFTPClient.listdir(path)` - 실제 SFTP 조회
- `list_directories(path)` - 디렉토리만 필터링 (실제 미구현, Mock만)

**현재 상태**:
```python
# Mock: 3일 범위 (과거 2일 + 오늘)
mock_dates = [
    (today - timedelta(days=2)).strftime("%Y%m%d"),
    (today - timedelta(days=1)).strftime("%Y%m%d"),
    today.strftime("%Y%m%d"),
]

# Real: listdir("/"/)로 루트 조회
entries = self.sftp.listdir("/")  # 날짜 폴더 목록
```

**재활용 방법**:
- ✅ 기본 구조 유지
- ⚠️ Real SFTP에서 날짜 폴더 필터링 로직 추가 필요
  - 현재: 모든 항목 반환
  - 필요: "YYYYMMDD" 형식 날짜만 필터링

**추가 구현 필요**:
```python
def get_available_dates(self, path: str = "/") -> List[str]:
    """Get list of date folders (YYYYMMDD format) from SFTP."""
    entries = self.listdir(path)
    dates = []
    for entry in entries:
        if self._is_valid_date_format(entry):  # YYYYMMDD 검증
            dates.append(entry)
    return sorted(dates)

def _is_valid_date_format(self, value: str) -> bool:
    """Check if value is valid YYYYMMDD date."""
    try:
        datetime.strptime(value, "%Y%m%d")
        return True
    except ValueError:
        return False
```

---

### 1.2 ⚠️ 부분 재활용 / 수정 필요

#### (3) Date Range 계산
**현재 없음**: 사용 가능 범위 반환 API 없음

**필요 개발**:
- `GET /api/admin/date-range` 신규 개발
- 기존 date-stats와 SFTP 조합

**구현 방식**:
```python
# app/routes/admin.py에 신규 추가
@router.get("/date-range")
async def get_date_range():
    """Returns available date range from SFTP or Mock."""
    try:
        if config.APP_ENV == "local":
            # Mock 클라이언트에서 범위 조회
            client = MockSFTPClient(...)
            dates = client.get_available_dates()
        else:
            # Real SFTP에서 범위 조회
            client = SFTPClient(...)
            dates = client.get_available_dates()
        
        return {
            "min_date": min(dates),
            "max_date": max(dates),
            "available_dates": dates,
            "source": "mock" if config.APP_ENV == "local" else "sftp"
        }
    except Exception as e:
        logger.error(f"Failed to get date range: {e}")
        raise
```

---

#### (4) Batch Analysis (케이스 분류)
**현재 없음**: 케이스 자동 분류 로직 없음

**필요 개발**:
- `POST /api/admin/batch-analysis` 신규 개발
- DB의 `get_date_statistics()` + SFTP의 `get_available_dates()` 조합

**구현 로직**:
```python
def analyze_batch_case(user_start_date, user_end_date):
    """분석 로직"""
    # 1. DB에서 완료된 범위 조회
    completed_dates = db.get_completed_date_range(user_start_date, user_end_date)
    
    # 2. SFTP에서 가용 날짜 조회
    available_dates = sftp.get_available_dates()
    
    # 3. Case 분류
    if all(d in completed_dates for d in available_dates[user_start:user_end]):
        return "full_overlap"
    elif any(d in completed_dates for d in available_dates[user_start:user_end]):
        return "partial_overlap"
    else:
        return "no_overlap"
```

---

### 1.3 ❌ 새로 개발 필요

#### (5) Batch Create 로직 수정
**현재**: `POST /process/batch/create` - 기본 배치 생성만 수행
**필요**: option_id 기반 분기 처리

```python
@router.post("/batch/create")
async def create_batch(req: BatchCreateRequest):
    """수정 필요"""
    # 현재: 단순히 배치 생성
    # 수정 후:
    if req.option_id == "reprocess":
        # 기존 작업 재처리 (force=true)
    elif req.option_id == "process_new":
        # 새로운 부분만 처리 (start/end 범위 조정)
    elif req.option_id == "reprocess_all":
        # 전체 재처리
```

---

## 2. SFTP 날짜 조회 상세 검토

### 2.1 현재 Mock 구현
**위치**: `app/sftp_client.py:11-88`

```python
# 현재: 3일 고정 범위
mock_dates = [
    (today - timedelta(days=2)).strftime("%Y%m%d"),  # 과거 2일
    (today - timedelta(days=1)).strftime("%Y%m%d"),  # 어제
    today.strftime("%Y%m%d"),                         # 오늘
]

# 파일 개수도 고정 (각 날짜 3개)
mock_files = {
    date: [f"{date}_001.txt", f"{date}_002.txt", f"{date}_003.txt"]
    for date in self.mock_dates
}
```

**문제점**:
- ✅ 테스트용으로는 충분하나, 동적 범위 테스트 불가
- ✅ 파일 개수가 모두 3개로 고정

**개선 방안** (선택사항):
- Config에서 Mock 범위 설정 가능하게 변경
- 동적으로 파일 개수 생성

---

### 2.2 현재 Real SFTP 구현
**위치**: `app/sftp_client.py:91-138`

```python
def listdir(self, path: str = ".") -> List[str]:
    if not self.sftp:
        raise RuntimeError("SFTP connection not established")
    logger.debug("Listing sftp path=%s", path)
    return self.sftp.listdir(path)
```

**문제점**:
- ❌ 루트("/")에서 모든 항목 반환 (날짜 폴더 + 기타 파일 혼재 가능)
- ❌ YYYYMMDD 형식 필터링 없음

**필수 개선**:
```python
def get_available_dates(self, root_path: str = "/") -> List[str]:
    """Get sorted list of valid YYYYMMDD date folders."""
    try:
        entries = self.listdir(root_path)
        dates = []
        
        for entry in entries:
            # YYYYMMDD 형식 검증
            if self._is_valid_date_format(entry):
                dates.append(entry)
        
        logger.info(f"Available dates: {sorted(dates)}")
        return sorted(dates)
    
    except Exception as e:
        logger.error(f"Failed to get available dates: {e}")
        raise

def _is_valid_date_format(self, value: str) -> bool:
    """Validate YYYYMMDD format."""
    try:
        datetime.strptime(value, "%Y%m%d")
        return True
    except (ValueError, TypeError):
        return False
```

---

## 2.3 TEST_MODE 환경변수 처리

**구현 방식**:
```python
# app/config.py에 추가
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"

# app/routes/admin.py의 date-range API
@router.get("/date-range")
async def get_date_range():
    """Returns available date range from SFTP with fallback to Mock."""
    try:
        if config.APP_ENV == "local":
            # Local: Mock 클라이언트 사용
            client = MockSFTPClient(...)
            dates = client.get_available_dates()
        else:
            # Real: SFTP 시도
            try:
                client = SFTPClient(...)
                dates = client.get_available_dates()
            except Exception as e:
                if config.TEST_MODE:
                    # TEST_MODE=true: Mock fallback
                    logger.warning(f"SFTP failed, using Mock fallback: {e}")
                    client = MockSFTPClient(...)
                    dates = client.get_available_dates()
                else:
                    # 프로덕션: 에러 응답
                    logger.error(f"SFTP connection failed: {e}")
                    raise HTTPException(status_code=500, detail="SFTP 연결 실패")
        
        return {
            "min_date": min(dates),
            "max_date": max(dates),
            "available_dates": dates,
            "source": config.APP_ENV,
            "test_mode": config.TEST_MODE
        }
    except Exception as e:
        logger.error(f"Failed to get date range: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Docker Compose 예시**:
```yaml
environment:
  - TEST_MODE=true  # Local dev에서 SFTP 실패 시 Mock fallback
```

---

### 2.3 제안: SFTP 클라이언트 확장

**신규 메서드 추가**:
1. `get_available_dates()` - 날짜 범위 반환
2. `get_file_count(date)` - 특정 날짜 파일 개수
3. `get_date_range()` - (min_date, max_date) 튜플 반환

**코드 위치**: `app/sftp_client.py` (MockSFTPClient, SFTPClient 모두)

---

## 3. 데이터베이스 메서드 검토

### 3.1 get_date_statistics() - ✅ 그대로 사용
**현재 기능**:
- 날짜별 통계 반환
- 범위 필터링 지원
- status 포함

**필요 확인**:
```python
# 응답 포맷 확인
{
    'date': '20260315',
    'total_files': 15,
    'processed_files': 15,  # ← 성공한 파일만
    'failed_files': 0,
    'status': 'done',  # 'ready'/'done'/'incomplete'/'failed'
    'last_processed': timestamp
}
```

**상태 정의 명확화 필요**:
- `status='done'` = 모든 파일 처리 완료 (= "완료된 작업")
- `status='incomplete'` = 일부 파일 처리 실패

---

### 3.2 신규 메서드 필요: get_completed_date_range()
**목적**: 범위 내에서 "완료된" 날짜 목록 반환

```python
def get_completed_date_range(self, start_date: str, end_date: str) -> List[str]:
    """Get list of dates with status='done' within range."""
    stats = self.get_date_statistics(start_date, end_date)
    completed = [s['date'] for s in stats if s['status'] == 'done']
    return sorted(completed)
```

---

## 4. 구현 계획 수정

### Phase 1: SFTP 날짜 조회 (선행 필수)
1. **app/sftp_client.py 확장**
   - `MockSFTPClient.get_available_dates()` 추가
   - `SFTPClient.get_available_dates()` 추가
   - `_is_valid_date_format()` 유틸 추가

2. **app/database/manager.py 확장**
   - `get_completed_date_range()` 메서드 추가

3. **app/routes/admin.py 신규 API**
   - `GET /api/admin/date-range` 구현

---

### Phase 2: 케이스 분류 API
1. **app/utils/batch_analyzer.py 신규**
   - `analyze_batch_case()` 함수 구현
   - Case 분류 로직

2. **app/routes/admin.py 신규 API**
   - `POST /api/admin/batch-analysis` 구현

---

### Phase 3: Batch Create 수정
1. **app/routes/process.py 수정**
   - `option_id` 기반 분기 처리

---

### Phase 4: 프론트엔드 (단, Phase 1 완료 후)
1. flatpickr 캘린더 구현
2. date-range 데이터로 범위 제한
3. date-stats 데이터로 배지 표시

---

## 5. 우선순위 재정렬

| 항목 | 우선순위 | 소요시간 | 선행 작업 |
|------|----------|----------|----------|
| SFTP date-range API | **높음** | 30분 | 없음 |
| batch-analysis API | 높음 | 1시간 | SFTP API |
| date-range DB 메서드 | 높음 | 20분 | 없음 |
| batch/create 수정 | 중간 | 1시간 | analysis API |
| 프론트엔드 | 중간 | 2시간 | 백엔드 완료 |
| **총합** | - | **4-5시간** | - |

---

## 6. 체크리스트

- [ ] SFTP 클라이언트 확장 검토 (메서드명, 동작)
- [ ] DB 메서드 신규 추가 검토
- [ ] API 응답 스키마 최종 확인
- [ ] Case 분류 로직 재확인
- [ ] Mock 데이터 범위 적절성 검토

---

## 7. 제안 및 질문

1. **Mock 범위 확장**?
   - 현재: 3일 고정
   - 결정: 그대로 유지 (local 테스트용)

2. **SFTP 조회 성능**?
   - 범위 제한 없이 전체 조회
   - 캘린더 표시: 월별 파싱 (사용자 선택)

3. **에러 처리**?
   - SFTP 연결 실패 → 에러 응답
   - TEST_MODE=true → Mock fallback

---

## 8. 추가 기능: 사용자 폴더/파일 업로드

사용자가 별도 폴더를 만들고 파일을 업로드/붙여넣기해서 배치 처리하는 기능

**새로운 데이터 흐름**:
```
사용자 업로드
├─ 폴더명 선택/입력
├─ 파일 업로드 (드래그&드롭 또는 파일 선택)
├─ 파일 목록 확인
└─ 배치 처리 시작

API 구조
├─ POST /process/upload/folder - 폴더 생성
├─ POST /process/upload/files - 파일 업로드
├─ GET /process/upload/{folder_id}/files - 파일 목록 조회
├─ POST /process/batch/create?source=upload - 업로드 폴더 기반 배치 처리
└─ DELETE /process/upload/{folder_id} - 폴더 삭제
```

**자세한 계획은 별도 문서에서 작성 예정**

---

## 9. 최종 검토 체크리스트

- [ ] SFTP 메서드 명 확인 ✓
- [ ] Mock 범위 (현상 유지) ✓
- [ ] 조회 범위 (전체) ✓
- [ ] SFTP 실패시 TEST_MODE 처리 ✓
- [ ] 사용자 폴더/파일 업로드 기능 계획 추가 ✓

검토 완료. Phase 1 구현 시작 가능?
