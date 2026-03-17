# STT 사후 점검 시스템 - Job Persistence & Calendar UI 개선 계획

## 개요

현재 시스템의 배치 작업 이력이 메모리에만 저장되어 있어 시스템 재시작 시 데이터가 소실됩니다. 
이를 개선하기 위해 SQLite3 기반 영구 저장소를 도입하고, UI/UX를 개선하여 중복 처리를 방지하고 처리 현황을 한눈에 파악할 수 있도록 합니다.

---

## Phase 1: 데이터베이스 설계

### 1.1 DB 스키마

#### 테이블: `batch_jobs`
```sql
CREATE TABLE batch_jobs (
    id TEXT PRIMARY KEY,                    -- UUID
    status TEXT NOT NULL,                   -- 'pending', 'running', 'completed', 'failed'
    start_date TEXT NOT NULL,               -- YYYYMMDD format
    end_date TEXT NOT NULL,                 -- YYYYMMDD format
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    total_files INT DEFAULT 0,
    success_files INT DEFAULT 0,
    failed_files INT DEFAULT 0
);
```

#### 테이블: `batch_results`
```sql
CREATE TABLE batch_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    file_date TEXT NOT NULL,                -- YYYYMMDD format
    filename TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    text_content TEXT,
    category TEXT,
    summary TEXT,
    omission_num INT,
    detected_issues JSON,
    error_message TEXT,
    processing_time_ms INT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (job_id) REFERENCES batch_jobs(id)
);
```

#### 테이블: `date_status`
```sql
CREATE TABLE date_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,              -- YYYYMMDD format
    total_files INT DEFAULT 0,
    processed_files INT DEFAULT 0,
    failed_files INT DEFAULT 0,
    last_processed TIMESTAMP,
    status TEXT DEFAULT 'unprocessed',      -- 'unprocessed', 'partial', 'completed'
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

### 1.2 저장 위치
- 데이터베이스 파일: `app/data/stt_jobs.db`
- 자동 생성 및 마이그레이션 처리

---

## Phase 2: Backend API 개발

### 2.1 DB 초기화 및 관리
**새로운 엔드포인트:**
- `POST /api/admin/db/init` - 데이터베이스 초기화
- `POST /api/admin/db/reset` - 모든 데이터 초기화 (개발/테스트용)
- `GET /api/admin/db/status` - DB 상태 조회

### 2.2 Job 이력 API 개선
**기존 엔드포인트 수정:**
- `GET /process/batch/history` - 전체 작업 이력 조회 (페이징 지원)
- `GET /process/batch/history/{date}` - 특정 날짜 처리 상태 조회
- `DELETE /process/batch/{job_id}` - 작업 삭제 (권한 필요)

### 2.3 캘린더 데이터 API
**새로운 엔드포인트:**
- `GET /process/calendar/status/{year}/{month}` - 월별 처리 상태
  ```json
  {
    "year": 2026,
    "month": 3,
    "dates": {
      "2026-03-14": { "status": "completed", "total": 9, "processed": 9, "failed": 0 },
      "2026-03-15": { "status": "partial", "total": 5, "processed": 3, "failed": 0 },
      "2026-03-16": { "status": "unprocessed", "total": 0, "processed": 0, "failed": 0 }
    }
  }
  ```

### 2.4 Batch 처리 로직 수정
- `POST /process/batch/submit` 수정
  - 요청 시 각 날짜별 처리 상태 확인
  - 이미 처리된 파일은 스킵하거나, 사용자 선택에 따라 재처리
  - 결과를 DB에 저장

---

## Phase 3: Frontend UI/UX 개선

### 3.1 배치 처리 페이지 개선

#### 현재 구조
```
┌─────────────────┐
│ 시작 날짜 │ 종료 날짜 │
└─────────────────┘
```

#### 개선된 구조
```
┌──────────────────────────────────────────────┐
│ 📅 月별 처리 상태 캘린더                      │
│  (달력 형태로 각 날짜의 처리 상태 표시)      │
│                                              │
│  ■ 완료 (모든 파일 처리됨)                   │
│  ▤ 부분 (일부 파일만 처리됨)                 │
│  □ 미처리 (아직 처리 안됨)                   │
└──────────────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│ 📆 점검 범위 선택                            │
│  [ 2026-03-14 ] ~ [ 2026-03-20 ]           │
│                                              │
│  처리 옵션:                                  │
│  ○ 미처리 파일만 (권장)                     │
│  ○ 전체 파일 (재처리)                       │
│  ○ 실패 파일만                              │
└──────────────────────────────────────────────┘

[ 처리 시작 ]  [ 초기화 ]  [ 상세 설정 ]
```

### 3.2 캘린더 컴포넌트
**새로운 컴포넌트: `CalendarPicker`**
- 월별 캘린더 표시
- 날짜별 처리 상태 시각화 (색상 코드)
- 범위 선택 기능 (시작일 → 종료일 드래그 선택)
- 처리 옵션 선택
- 미리보기: 선택된 범위에서 처리할 파일 수 표시

### 3.3 처리 옵션 UI

```
처리 옵션:
┌─────────────────────────────────────┐
│ ○ 스마트 (미처리 + 실패한 파일)    │
│   - 이전에 처리 안 된 파일만 처리   │
│   - 실패했던 파일 재처리            │
│                                     │
│ ○ 전체 다시 처리 (재처리)          │
│   - 이미 처리된 파일도 모두 재처리  │
│   - 최신 버전으로 다시 분석        │
│                                     │
│ ○ 미처리만 (초기 처리)             │
│   - 새로운 파일만 처리              │
│   - 기존 처리 파일 스킵             │
└─────────────────────────────────────┘
```

### 3.4 작업 이력 페이지 개선
- 달력 뷰: 월별 처리 현황
- 리스트 뷰: 최근 작업 20개
- 검색/필터: 날짜 범위, 상태별 필터
- 재처리 기능: 과거 작업 다시 실행

---

## Phase 4: 구현 순서

### 4.1 Phase 1 (DB 설계 & 초기화) - Week 1
- [ ] SQLite3 DB 스키마 생성
- [ ] 마이그레이션 스크립트 작성
- [ ] DB 초기화 API 구현
- [ ] DB 상태 조회 API

### 4.2 Phase 2 (Backend 개선) - Week 2
- [ ] Job 저장 로직 DB 기반으로 변경
- [ ] 결과 저장 로직 DB 기반으로 변경
- [ ] 날짜별 상태 조회 API
- [ ] 월별 캘린더 데이터 API
- [ ] 이전 처리 정보 확인 로직

### 4.3 Phase 3 (Frontend 개선) - Week 3
- [ ] CalendarPicker 컴포넌트 개발
- [ ] 배치 처리 페이지 UI 개선
- [ ] 처리 옵션 UI 추가
- [ ] 작업 이력 페이지 개선
- [ ] 스마트 처리 로직 통합

### 4.4 Phase 4 (테스트 & 최적화) - Week 4
- [ ] 단위 테스트
- [ ] 통합 테스트
- [ ] 성능 최적화
- [ ] 사용자 피드백 반영

---

## Phase 5: 추가 고려사항

### 5.1 데이터 마이그레이션
- 현재 메모리 데이터를 DB로 마이그레이션하는 유틸
- 백업 기능

### 5.2 보안
- DB 접근 권한 관리
- 초기화/리셋 API에 대한 인증
- 감시 기능 (audit log)

### 5.3 성능
- DB 인덱싱 전략
- 캘린더 데이터 캐싱
- 배치 쿼리 최적화

### 5.4 백업 & 복구
- 자동 백업 스크립트
- 복구 절차 문서화

---

## 검토 및 수정 사항

### 질문 목록
1. SQLite3 외에 다른 DB 옵션 고려? (PostgreSQL, MySQL)
2. 처리 옵션 중 우선순위? (스마트, 전체, 미처리)
3. 캘린더 UI - 월별/주별/일별 어떤 수준의 상세도?
4. 데이터 보존 기간? (기록을 얼마나 오래 보관?)
5. 병렬 처리와 동시성 제어?

### 잠재적 이슈
- [ ] 대용량 데이터 처리 시 성능
- [ ] 동시 다중 배치 작업 처리
- [ ] DB 라이브러리 선택 (SQLAlchemy vs raw SQL)
- [ ] 마이그레이션 관리 (Alembic vs 수동)

---

## 예상 영향도

| 항목 | 영향도 | 비고 |
|------|--------|------|
| Backend | 높음 | API 구조 변경, DB 추가 |
| Frontend | 중간 | UI 개선, 새 컴포넌트 추가 |
| 성능 | 중간 | DB 쿼리 최적화 필요 |
| 사용성 | 높음 | 중복 처리 방지, UX 개선 |
| 유지보수 | 중간 | DB 관리 추가 |

---

## 다음 스텝

1. **검토**: 이 계획안을 검토하고 수정사항 제시
2. **확정**: 최종 계획안 결정
3. **상세설계**: 각 phase별 상세 기술 설계
4. **구현**: Phase별 순차 구현

