# SELECT_TARGET: 전체 계획 요약

## 문서 목록

1. **PLAN.md** - 캘린더 기반 범위 선택 & 자동 케이스 분류
   - 용어 정의, 데이터 모델, API 명세, UI 설계

2. **CODE_REVIEW.md** - 기존 코드 재활용 검토
   - 기존 기능 분석, SFTP 메서드 설계, TEST_MODE 처리

3. **UPLOAD_FEATURE.md** - 사용자 폴더/파일 업로드 기능
   - 데이터 모델, DB 스키마, API 명세, UI 설계

---

## 전체 아키텍처

### 배치 처리 두 가지 모드

```
┌─ 배치 처리 ─────────────────────────────┐
│                                         │
│ Mode 1: 날짜 기반 (PLAN.md)             │
│ ├─ SFTP에서 날짜 폴더 선택               │
│ ├─ 자동 케이스 분류 (overlap 판단)      │
│ ├─ 사용자 선택지 제시                   │
│ └─ 배치 처리 실행                       │
│                                         │
│ Mode 2: 업로드 기반 (UPLOAD_FEATURE.md)│
│ ├─ 사용자 폴더 생성                     │
│ ├─ 파일 업로드/붙여넣기                 │
│ ├─ 배치 처리 실행 (옵션 없음)           │
│ └─ 결과 저장                            │
│                                         │
└─────────────────────────────────────────┘
```

---

## Phase별 의존성

```
Phase 1: SFTP 날짜 조회 API
    ↓
Phase 2: 케이스 분류 API ──→ Phase 4: 캘린더 UI (의존)
    ↓
Phase 3: Batch Create 수정
    ↓
Phase 4: 프론트엔드 캘린더 UI (완료)

Phase 5: 업로드 기능 (독립적, Phase 4와 병렬 가능)
    ↓
Phase 6: 통합 테스트 (모든 Phase 완료 후)
```

---

## 주요 변경사항

### 1. 환경변수 추가
- `TEST_MODE` (default: false)
  - true: SFTP 실패 시 Mock fallback
  - false: SFTP 실패 시 에러 응답

### 2. DB 테이블 추가
- `upload_folders` - 사용자 업로드 폴더
- `upload_files` - 업로드 파일 목록

### 3. DB 컬럼 추가
- `batch_jobs.source` - "date" 또는 "upload"
- `batch_jobs.upload_folder_id` - 업로드 폴더 참조

### 4. 파일 시스템 추가
- `app/uploads/` - 사용자 업로드 파일 저장소

---

## API 엔드포인트 총정리

### 기존 API
- GET `/api/admin/date-stats` - ✓ 그대로 사용

### 신규 API (Phase 1-3)
- GET `/api/admin/date-range` - 처리 가능 날짜 범위
- POST `/api/admin/batch-analysis` - 케이스 분류
- POST `/process/batch/create` (수정) - option_id 처리

### 신규 API (Phase 5)
- POST `/process/upload/folder` - 폴더 생성
- POST `/process/upload/files` - 파일 업로드
- GET `/process/upload/folders` - 폴더 목록
- GET `/process/upload/{id}/files` - 폴더의 파일 목록
- DELETE `/process/upload/{id}` - 폴더 삭제

---

## UI 탭 구조

```
배치 처리 페이지
├─ 📅 날짜 선택 탭
│  ├─ 캘린더 (월별 표시)
│  ├─ 범위 표시 ("가능한 범위: 2026-03-15 ~ 2026-03-30")
│  ├─ 범위 선택 (시작 ~ 종료)
│  └─ 케이스 분류 결과 & 옵션 선택
│
└─ 📁 파일 업로드 탭
   ├─ 폴더 관리 (폴더명 입력, 생성)
   ├─ 파일 업로드 (드래그&드롭)
   ├─ 파일 목록 확인
   └─ 배치 처리 시작
```

---

## 처리 흐름 비교

### 날짜 기반 (Mode 1)
```
사용자 범위 선택
    ↓ (POST /api/admin/batch-analysis)
케이스 분석 (SFTP + DB)
    ↓
Case 분류
├─ full_overlap → "재처리" vs "기록보기"
├─ partial_overlap → "새것만" vs "전체재"
├─ no_overlap → 자동 진행
└─ no_data → 에러
    ↓
사용자 선택
    ↓ (POST /process/batch/create + option_id)
배치 처리 시작
    ↓
결과 표시 (원본 요청 범위 기준)
```

### 업로드 기반 (Mode 2)
```
폴더 생성 (POST /process/upload/folder)
    ↓
파일 업로드 (POST /process/upload/files)
    ↓
파일 목록 확인 (GET /process/upload/{id}/files)
    ↓
배치 처리 시작 (POST /process/batch/create + upload_folder_id)
    ↓
결과 저장 (upload_files 상태 업데이트)
```

---

## 검토 체크리스트

### CODE_REVIEW.md 결정사항
- [x] SFTP 메서드명: `get_available_dates()` ✓
- [x] Mock 범위: 현상 유지 (3일 고정) ✓
- [x] 조회 범위: 전체 (제한 없음) ✓
- [x] SFTP 실패: TEST_MODE 환경변수로 fallback ✓

### 추가 기능
- [x] 사용자 폴더/파일 업로드 기능 포함 ✓
- [x] 두 가지 배치 모드 설계 ✓

---

## 다음 단계

1. **이 요약 검토** - 전체 구조 확인
2. **Phase 1 구현 시작** - SFTP 날짜 조회 API
3. **순차적으로 Phase 진행**

준비 완료! Phase 1 구현 시작해도 될까요? 🚀
