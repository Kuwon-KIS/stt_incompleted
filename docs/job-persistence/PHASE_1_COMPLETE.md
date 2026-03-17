# Phase 1 완료: 데이터베이스 인프라 구축

## 구현 내용

### 1. 데이터 모델 (`app/database/models.py`)
- `BatchJob`: 배치 작업 정보
- `BatchResult`: 개별 파일 처리 결과
- `DateStatus`: 날짜별 처리 상태 추적

각 모델은 다음 기능 지원:
- 타입 힌팅
- `to_dict()` 메서드 (datetime 자동 변환)
- JSON 직렬화

### 2. 데이터베이스 관리자 (`app/database/manager.py`)
SQLite3 기반 데이터베이스 관리:

**Connection 관리**
- 자동 연결/해제
- Row factory를 이용한 딕셔너리 반환

**CRUD Operations**
- `create_job()`: 배치 작업 생성
- `get_job()`: 작업 조회
- `update_job_status()`: 상태 업데이트
- `update_job_stats()`: 통계 업데이트
- `create_result()`: 처리 결과 저장
- `get_results_by_job()`: 작업의 모든 결과 조회
- `get_or_create_date_status()`: 날짜 상태 조회/생성
- `update_date_status()`: 날짜 상태 업데이트
- `get_month_status()`: 월간 캘린더 데이터 조회

**관리 기능**
- `init_db()`: 스키마 초기화 및 인덱스 생성
- `reset_db()`: 전체 리셋 (테스트/개발용)
- `get_db_status()`: 데이터베이스 상태 조회

### 3. SQL 스키마 (`app/database/schema.py`)
3개 테이블 정의:
- `batch_jobs`: 배치 작업 메타데이터
- `batch_results`: 개별 파일 처리 결과
- `date_status`: 날짜별 처리 현황

성능 인덱스:
- `idx_batch_jobs_status`: 상태별 조회
- `idx_batch_results_job_id`: 작업별 결과 조회
- `idx_batch_results_file_date`: 날짜별 결과 조회
- `idx_date_status_date`: 날짜별 상태 조회

### 4. 관리 API (`app/routes/admin.py`)

| Endpoint | Method | 설명 |
|----------|--------|------|
| `/api/admin/db/init` | POST | 데이터베이스 초기화 |
| `/api/admin/db/reset` | POST | 전체 데이터 삭제 및 재초기화 |
| `/api/admin/db/status` | GET | 데이터베이스 상태 조회 |

### 5. 통합
- `main.py`에 admin 라우터 등록
- 애플리케이션 시작 시 자동 데이터베이스 초기화
- `DatabaseManager` 전역 인스턴스 사용 준비

## 데이터베이스 위치
- 프로덕션: `app/data/stt_jobs.db`
- 자동 생성: 디렉토리 없으면 자동 생성

## 다음 단계 (Phase 2)
- 배치 처리 엔드포인트에서 메모리 대신 DB 사용
- 캘린더 조회 API 구현
- 중복 처리 방지 로직 구현
