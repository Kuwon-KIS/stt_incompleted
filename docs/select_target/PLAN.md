# SELECT_TARGET: 캘린더 기반 범위 선택 및 자동 케이스 분류

## 개요
사용자가 캘린더 UI에서 직관적으로 날짜 범위를 선택하고, 시스템이 자동으로 처리 상태를 분석하여 최적의 작업 옵션을 제시하는 기능 구현.

---

## 1. 용어 정의

### 1.1 "완료된 작업" 정의
- **기준**: 특정 날짜 폴더의 **모든 파일이 정상 처리된 경우**만
- **상태**: DB에서 `batch_jobs` 테이블의 해당 날짜 레코드의 `status='completed'`
- **예외**: 일부 파일만 실패한 경우는 "완료"가 아님
  - 이 경우는 별도의 상세 페이지 > 개별 파일 선택 > 재수행 기능으로 처리

### 1.2 처리 범위
- **선택 범위**: 사용자가 캘린더에서 지정한 `[start_date, end_date]`
- **가능 범위**: SFTP/Mock에서 조회한 실제 처리 가능한 날짜 범위
- **완료 범위**: DB에서 조회한 이미 처리 완료된 날짜 범위

---

## 2. 데이터 모델

### 2.1 DateRange (조회용)
```python
class DateRange(BaseModel):
    min_date: str  # "20260315" 형식
    max_date: str  # "20260317" 형식
    source: str    # "mock" | "sftp"
    available_dates: List[str]  # 실제 파일이 있는 날짜 목록
```

### 2.2 DateStats (통계용)
```python
class DateStats(BaseModel):
    date: str           # "20260315"
    file_count: int     # 해당 날짜의 파일 개수
    processed_count: int # 처리된 파일 개수
    status: str         # "completed" | "partial" | "pending"
    job_id: Optional[str]  # 해당 작업의 job_id
```

### 2.3 BatchAnalysis (분석 결과)
```python
class BatchAnalysis(BaseModel):
    case: str  # "full_overlap" | "partial_overlap" | "no_overlap" | "no_data"
    user_range: Dict[str, str]  # {"start_date": "20260310", "end_date": "20260315"}
    completed_range: Optional[Dict[str, str]]  # 완료된 범위 또는 None
    overlap_dates: List[str]  # 겹치는 날짜 목록
    new_dates: List[str]      # 새로운 날짜 목록
    options: List[BatchOption]  # 사용자에게 제시할 옵션들
```

### 2.4 BatchOption (사용자 선택 옵션)
```python
class BatchOption(BaseModel):
    id: str                    # "reprocess" | "view_history" | "process_new" | "reprocess_all"
    label: str                 # 사용자에게 보여줄 텍스트
    description: str           # 상세 설명
    action_config: Dict        # 백엔드 처리 시 필요한 설정
```

---

## 3. 케이스 분류 로직

### Case 1: 전체 겹침 (full_overlap)
**조건**: 사용자 범위 ⊆ 완료된 범위
```
사용자 선택: [2026-03-10 ~ 2026-03-15]
완료 상태: [2026-03-01 ~ 2026-03-20] 완료됨

제시 옵션:
  1. "재처리" - 전체 범위 다시 처리
  2. "이전 기록 보기" - 기존 처리 결과 조회
```

**결과 표시**:
- 원본 요청 범위 `[2026-03-10 ~ 2026-03-15]` 기준으로 표시

---

### Case 2: 부분 겹침 (partial_overlap)
**조건**: 사용자 범위와 완료된 범위가 부분 겹침

**예시 1**:
```
사용자 선택: [2026-03-10 ~ 2026-03-15]
완료 상태: [2026-03-12 ~ 2026-03-15] 완료됨

겹침 부분: [2026-03-12 ~ 2026-03-15]
새 부분: [2026-03-10 ~ 2026-03-11]

제시 옵션:
  1. "새로운 부분만 처리" - 2026-03-10~11만 처리
  2. "전체 재처리" - 2026-03-10~15 모두 재처리
```

**예시 2**:
```
사용자 선택: [2026-03-10 ~ 2026-03-15]
완료 상태: [2026-03-10 ~ 2026-03-12] 완료됨

겹침 부분: [2026-03-10 ~ 2026-03-12]
새 부분: [2026-03-13 ~ 2026-03-15]

제시 옵션:
  1. "새로운 부분만 처리" - 2026-03-13~15만 처리
  2. "전체 재처리" - 2026-03-10~15 모두 재처리
```

**결과 표시**:
- 원본 요청 범위 `[2026-03-10 ~ 2026-03-15]` 기준으로 표시
- 처리 완료 후: 요청했던 범위 내 모든 날짜의 결과를 반영

---

### Case 3: 겹침 없음 (no_overlap)
**조건**: 사용자 범위와 완료된 범위가 겹치지 않음
```
사용자 선택: [2026-03-10 ~ 2026-03-15]
완료 상태: [2026-02-01 ~ 2026-02-28] 완료됨

제시 옵션:
  - 자동 처리 (옵션 제시 없음, 바로 처리 시작)
```

---

### Case 4: 데이터 없음 (no_data)
**조건**: 선택 범위 내에 처리할 파일이 없음
```
사용자 선택: [2026-03-10 ~ 2026-03-15]
가능한 범위: [2026-03-20 ~ 2026-03-30]

에러 메시지: "선택한 범위에 처리할 파일이 없습니다. 가능한 범위: 2026-03-20 ~ 2026-03-30"
```

---

## 4. API 명세

### 4.1 GET /api/admin/date-range
**목적**: 처리 가능한 날짜 범위 조회
```
Response 200:
{
  "min_date": "20260315",
  "max_date": "20260317",
  "source": "sftp",  // "mock" | "sftp"
  "available_dates": ["20260315", "20260316", "20260317"]
}

Response 500:
{
  "detail": "SFTP 조회 실패: ..."
}
```

**구현 위치**: `app/routes/admin.py`

**로직**:
- `APP_ENV=local`: Mock 데이터 범위 반환 (과거 2일 ~ 현재)
- `APP_ENV=prod|dev`: SFTP 조회
  - `SFTPClient.listdir()` 호출
  - 유효한 날짜 폴더만 필터링

---

### 4.2 GET /api/admin/date-stats
**목적**: 각 날짜별 처리 현황 조회
```
Response 200:
[
  {
    "date": "20260315",
    "file_count": 15,
    "processed_count": 15,
    "status": "completed",
    "job_id": "abc123..."
  },
  {
    "date": "20260316",
    "file_count": 12,
    "processed_count": 8,
    "status": "partial",
    "job_id": "def456..."
  }
]
```

**구현 위치**: `app/routes/admin.py`

**로직**:
- DB 조회: `date_status` 테이블 집계
- 각 날짜의 전체 파일 개수 = SFTP에서 실제 개수
- 처리된 개수 = DB 기록

---

### 4.3 POST /api/admin/batch-analysis
**목적**: 사용자 범위에 대한 케이스 분석
```
Request:
{
  "start_date": "20260310",
  "end_date": "20260315"
}

Response 200:
{
  "case": "partial_overlap",
  "user_range": {
    "start_date": "20260310",
    "end_date": "20260315"
  },
  "completed_range": {
    "start_date": "20260312",
    "end_date": "20260315"
  },
  "overlap_dates": ["20260312", "20260313", "20260314", "20260315"],
  "new_dates": ["20260310", "20260311"],
  "options": [
    {
      "id": "process_new",
      "label": "새로운 부분만 처리",
      "description": "2026-03-10~11 (2일)만 처리합니다",
      "action_config": {
        "type": "process_new",
        "start_date": "20260310",
        "end_date": "20260311"
      }
    },
    {
      "id": "reprocess_all",
      "label": "전체 재처리",
      "description": "2026-03-10~15 (6일) 전체를 처리합니다",
      "action_config": {
        "type": "reprocess_all",
        "start_date": "20260310",
        "end_date": "20260315",
        "force": true
      }
    }
  ]
}
```

**구현 위치**: `app/routes/admin.py`

**로직**:
1. 요청한 범위의 완료 상태 조회
2. Case 분류 로직 실행
3. 각 case별 options 생성
4. 응답

---

### 4.4 POST /process/batch/create (기존 기능 확장)
**목적**: batch-analysis 결과를 받아 작업 생성
```
Request:
{
  "start_date": "20260310",
  "end_date": "20260315",
  "option_id": "process_new"  // 또는 "reprocess_all" 등
}

Response 201:
{
  "job_id": "abc123...",
  "status": "queued",
  "start_date": "20260310",
  "end_date": "20260315",
  "processing_dates": ["20260310", "20260311"],  // 실제 처리할 날짜
  "requested_dates": ["20260310", "20260315"]     // 요청한 범위
}
```

**구현 위치**: `app/routes/process.py` (기존 create_batch 함수 수정)

---

## 5. 프론트엔드 UI 설계

### 5.1 캘린더 구성 (flatpickr 사용)
```
┌─────────────────────────────┐
│ 2026년 3월                   │
├─────────────────────────────┤
│ Sun Mon Tue Wed Thu Fri Sat │
│             1   2   3   4   │  
│   5   6   7   8   9  10  11 │  
│  12  13  14  15* 16* 17  18 │  * = 처리 가능 (파일 있음)
│  19  20  21  22  23  24  25 │  
│  26  27  28  29  30  31     │
└─────────────────────────────┘
```

**표시 정보**:
- 처리 가능한 날짜: 마크 + 파일 개수 배지
- 선택된 날짜: 강조 표시
- 범위 선택: 시작 ~ 끝 날짜 범위에 배경색 적용

### 5.2 UI 레이아웃
```
┌─ 배치 처리 페이지 ─────────────────────────┐
│                                            │
│ 📅 날짜 범위 선택                          │
│ ┌────────────────────────────────────┐  │
│ │ 가능한 범위: 2026-03-15 ~ 2026-03-30 │  │
│ │ (현재 SFTP에서 조회 가능한 범위)     │  │
│ └────────────────────────────────────┘  │
│                                          │
│ [캘린더 UI]                               │
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ 선택: 2026-03-10 ~ 2026-03-15      │  │
│ │ 파일 수: 15개                       │  │
│ │ 기존 완료: 2026-03-12 ~ 2026-03-15│  │
│ └────────────────────────────────────┘  │
│                                          │
│ [분석 버튼] [초기화]                      │
│                                          │
│ === 케이스 분류 결과 (조건부 표시) ===   │
│ ┌────────────────────────────────────┐  │
│ │ ⚠️ 일부 범위가 이미 처리되었습니다  │  │
│ │                                    │  │
│ │ ⭐ 다음 중 하나를 선택해주세요:     │  │
│ │ □ 새로운 부분만 처리 (2일)         │  │
│ │   설명: 2026-03-10~11만 처리        │  │
│ │                                    │  │
│ │ □ 전체 재처리 (6일)                │  │
│ │   설명: 2026-03-10~15 모두 재처리   │  │
│ │                                    │  │
│ │ [선택한 옵션 적용]                   │  │
│ └────────────────────────────────────┘  │
│                                          │
└────────────────────────────────────────┘
```

---

## 6. 구현 순서

### Phase 1: SFTP 날짜 조회 API (선행 필수)
1. SFTP 클라이언트 확장
   - `get_available_dates()` 메서드
   - YYYYMMDD 형식 필터링

2. DB 메서드 추가
   - `get_completed_date_range()` - 완료된 날짜 범위

3. 백엔드 API
   - `GET /api/admin/date-range` 구현
   - TEST_MODE 환경변수 처리 + Mock fallback

### Phase 2: 케이스 분류 API
1. Batch Analyzer 유틸
   - 4가지 Case 분류 로직
   - Options 생성 로직

2. 백엔드 API
   - `POST /api/admin/batch-analysis` 구현

### Phase 3: Batch Create 수정
1. Option ID 기반 분기 처리
2. 날짜 기반 배치 처리 통합

### Phase 4: 프론트엔드 캘린더 UI
1. flatpickr 라이브러리 추가
2. 캘린더 UI 구현
3. 날짜별 배지(파일 개수) 표시
4. 범위 선택 & 표시
5. 케이스 분류 결과 렌더링
6. 옵션 선택 & 작업 실행

### Phase 5: 사용자 폴더/파일 업로드 기능
1. DB 스키마 (upload_folders, upload_files 테이블)
2. 파일 저장소 (uploads/ 디렉토리 구조)
3. DB Manager 메서드
4. 백엔드 API (업로드, 폴더 관리)
5. 배치 처리 로직 (upload 소스 지원)
6. 프론트엔드 UI (업로드 탭)

### Phase 6: 통합 테스트
1. 각 Case별 시나리오 테스트 (날짜 기반)
2. 업로드 폴더 기반 테스트
3. E2E 테스트

---

## 7. 데이터 흐름

```
┌─ 사용자 캘린더 선택 ──────────┐
│                              │
│ 1. 페이지 로드               │
│    ↓                         │
│    [GET /api/admin/date-range]
│    → 가능 범위, available_dates 조회
│    ↓                         │
│    [GET /api/admin/date-stats]
│    → 각 날짜별 처리 상태 조회
│    ↓                         │
│    캘린더 렌더링             │
│                              │
│ 2. 사용자 범위 선택          │
│    (캘린더에서 start ~ end 선택)
│    ↓                         │
│    선택 정보 표시            │
│                              │
│ 3. 분석 버튼 클릭           │
│    ↓                         │
│    [POST /api/admin/batch-analysis]
│    Request: {start_date, end_date}
│    Response: {case, options}
│    ↓                         │
│    Case별 옵션 UI 렌더링     │
│                              │
│ 4. 사용자 옵션 선택          │
│    ↓                         │
│    [POST /process/batch/create]
│    Request: {start_date, end_date, option_id}
│    Response: {job_id, ...}
│    ↓                         │
│    처리 시작 알림            │
│                              │
└──────────────────────────────┘
```

---

## 8. 예상 작업량

| 항목 | 예상 시간 | 난이도 |
|------|----------|--------|
| Phase 1: SFTP 날짜 조회 API | 1시간 | 낮음 |
| Phase 2: 케이스 분류 API | 1.5시간 | 중 |
| Phase 3: Batch Create 수정 | 1시간 | 낮음 |
| Phase 4: 프론트엔드 캘린더 | 2-3시간 | 중 |
| Phase 5: 업로드 기능 | 3-4시간 | 중 |
| Phase 6: 통합 테스트 | 2시간 | 중 |
| **총합** | **10-13시간** | **중** |

---

## 9. 리스크 & 완화 방안

| 리스크 | 완화 방안 |
|--------|----------|
| SFTP 조회 성능 저하 | 범위 제한 (최대 30일) + 캐싱 |
| Mock 데이터 부실 | 테스트 케이스로 충분히 검증 |
| UI/UX 복잡성 | 단계별 렌더링 (로딩 상태 명확히) |

---

## 10. 검토 체크리스트

- [ ] 케이스 분류 로직 정확도 확인
- [ ] API 응답 스키마 검증
- [ ] 프론트엔드 UI/UX 흐름 검토
- [ ] 데이터 흐름 다이어그램 재확인
- [ ] Edge case 고려 (범위 중복, 날짜 형식, 시간대 등)
