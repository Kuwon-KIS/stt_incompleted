# SELECT_TARGET: 사용자 폴더/파일 업로드 기능

## 1. 개요

사용자가 날짜 범위 선택 대신, 직접 폴더를 만들고 텍스트 파일을 업로드 또는 붙여넣기해서 배치 처리할 수 있는 기능.

**사용 시나리오**:
- 특정 고객 데이터만 처리하고 싶은 경우
- 날짜가 아닌 다른 기준으로 파일을 그룹화하는 경우
- SFTP에 없는 로컬 파일 처리

---

## 2. 데이터 모델

### 2.1 업로드 폴더 (Upload Folder)
```python
class UploadFolder(BaseModel):
    folder_id: str              # UUID (e.g., "abc123...")
    folder_name: str            # 사용자 입력 (e.g., "고객_김철수_20260315")
    created_at: datetime
    updated_at: datetime
    file_count: int             # 폴더 내 파일 개수
    total_size: int             # 전체 파일 크기 (bytes)
    status: str                 # "pending" | "processing" | "completed" | "failed"
    job_id: Optional[str]       # 연결된 배치 작업 ID
    created_by: Optional[str]   # 사용자 (향후 확장)
```

### 2.2 업로드 파일 (Upload File)
```python
class UploadFile(BaseModel):
    file_id: str                # UUID
    folder_id: str              # 폴더 ID (Foreign Key)
    filename: str               # 원본 파일명
    file_size: int              # 파일 크기 (bytes)
    file_hash: str              # MD5 해시 (중복 방지)
    status: str                 # "uploaded" | "processing" | "completed" | "failed"
    upload_date: datetime
    processing_result: Optional[Dict]  # 처리 결과
```

### 2.3 배치 요청 (수정된 모델)
```python
class BatchCreateRequest(BaseModel):
    """기존 모델 확장"""
    # 기존 필드
    start_date: Optional[str] = None      # YYYYMMDD (날짜 기반)
    end_date: Optional[str] = None
    option_id: Optional[str] = None
    
    # 신규 필드
    source: str = "date"                   # "date" | "upload"
    upload_folder_id: Optional[str] = None # 업로드 폴더 ID (source="upload" 시 필수)
```

---

## 3. 데이터베이스 스키마

### 3.1 테이블 추가

```sql
-- 업로드 폴더 테이블
CREATE TABLE upload_folders (
    folder_id TEXT PRIMARY KEY,
    folder_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_count INTEGER DEFAULT 0,
    total_size INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',  -- pending | processing | completed | failed
    job_id TEXT,
    notes TEXT,
    FOREIGN KEY (job_id) REFERENCES batch_jobs(job_id)
);

-- 업로드 파일 테이블
CREATE TABLE upload_files (
    file_id TEXT PRIMARY KEY,
    folder_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT DEFAULT 'uploaded',  -- uploaded | processing | completed | failed
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processing_result TEXT,  -- JSON
    FOREIGN KEY (folder_id) REFERENCES upload_folders(folder_id)
    CONSTRAINT UNIQUE (folder_id, file_hash)  -- 폴더 내 중복 파일 방지
);

-- batch_jobs 테이블에 source 컬럼 추가
ALTER TABLE batch_jobs ADD COLUMN source TEXT DEFAULT 'date';  -- date | upload
ALTER TABLE batch_jobs ADD COLUMN upload_folder_id TEXT;
```

---

## 4. 파일 저장소

### 4.1 디렉토리 구조
```
app/
├─ uploads/                          # 사용자 업로드 베이스 디렉토리
│  ├─ {folder_id}/                  # 폴더별 디렉토리
│  │  ├─ metadata.json              # 폴더 메타데이터
│  │  ├─ {filename}                 # 업로드된 파일
│  │  └─ ...
│  └─ ...
├─ ...
```

### 4.2 파일 경로 생성
```python
UPLOADS_BASE_DIR = "/app/uploads"  # Docker 볼륨으로 영구 저장

def get_folder_path(folder_id: str) -> str:
    return f"{UPLOADS_BASE_DIR}/{folder_id}"

def get_file_path(folder_id: str, filename: str) -> str:
    return f"{get_folder_path(folder_id)}/{filename}"
```

---

## 5. API 명세

### 5.1 POST /process/upload/folder
**목적**: 새로운 업로드 폴더 생성

```
Request:
{
  "folder_name": "고객_김철수_20260315"
}

Response 201:
{
  "folder_id": "abc123...",
  "folder_name": "고객_김철수_20260315",
  "created_at": "2026-03-17T10:00:00",
  "status": "pending",
  "file_count": 0
}

Response 400:
{
  "detail": "폴더명은 필수입니다"
}
```

**구현 로직**:
1. 폴더명 검증 (빈값, 특수문자 등)
2. UUID 생성 (folder_id)
3. 디렉토리 생성: `uploads/{folder_id}/`
4. DB 레코드 생성
5. metadata.json 작성

---

### 5.2 POST /process/upload/files
**목적**: 폴더에 파일 업로드

```
Request (multipart/form-data):
- folder_id: "abc123..."
- files: [file1.txt, file2.txt, ...]

Response 200:
{
  "folder_id": "abc123...",
  "uploaded_files": [
    {
      "file_id": "def456...",
      "filename": "file1.txt",
      "file_size": 1024,
      "status": "uploaded"
    },
    ...
  ],
  "failed_files": [
    {
      "filename": "file3.txt",
      "error": "파일이 너무 큽니다 (MAX: 10MB)"
    }
  ],
  "folder_stats": {
    "file_count": 2,
    "total_size": 2048
  }
}

Response 400:
{
  "detail": "폴더를 찾을 수 없습니다"
}
```

**구현 로직**:
1. 폴더 존재 확인
2. 각 파일별 처리:
   - 파일 크기 검증 (MAX: 10MB 등)
   - 파일 타입 검증 (텍스트 파일만)
   - MD5 해시 계산 (중복 방지)
   - 중복 파일 체크
   - 디스크에 저장
   - DB 레코드 생성
3. 폴더 통계 업데이트

---

### 5.3 GET /process/upload/folders
**목적**: 업로드 폴더 목록 조회 (페이지네이션)

```
Request:
GET /process/upload/folders?skip=0&limit=10&status=pending

Response 200:
{
  "folders": [
    {
      "folder_id": "abc123...",
      "folder_name": "고객_김철수_20260315",
      "created_at": "2026-03-17T10:00:00",
      "file_count": 5,
      "total_size": 51200,
      "status": "pending"
    },
    ...
  ],
  "total": 25,
  "skip": 0,
  "limit": 10
}
```

---

### 5.4 GET /process/upload/{folder_id}/files
**목적**: 특정 폴더의 파일 목록 조회

```
Request:
GET /process/upload/abc123.../files

Response 200:
{
  "folder_id": "abc123...",
  "folder_name": "고객_김철수_20260315",
  "status": "pending",
  "files": [
    {
      "file_id": "def456...",
      "filename": "file1.txt",
      "file_size": 1024,
      "status": "uploaded",
      "upload_date": "2026-03-17T10:05:00"
    },
    ...
  ],
  "folder_stats": {
    "file_count": 5,
    "total_size": 51200,
    "completed": 0,
    "failed": 0
  }
}
```

---

### 5.5 DELETE /process/upload/{folder_id}
**목적**: 업로드 폴더 및 파일 삭제

```
Request:
DELETE /process/upload/abc123...?force=false

Response 200:
{
  "status": "deleted",
  "folder_id": "abc123...",
  "deleted_file_count": 5,
  "freed_size": 51200
}

Response 409:
{
  "detail": "폴더가 처리 중입니다. force=true로 강제 삭제하거나 완료 후 삭제해주세요"
}
```

---

### 5.6 POST /process/batch/create (수정)
**목적**: 업로드 폴더 기반 배치 처리

```
Request:
{
  "source": "upload",
  "upload_folder_id": "abc123..."
}

Response 201:
{
  "job_id": "xyz789...",
  "status": "queued",
  "source": "upload",
  "upload_folder_id": "abc123...",
  "file_count": 5,
  "processing_dates": null  # 업로드 모드에서는 날짜 범위 없음
}
```

---

## 6. 데이터 흐름

```
┌─ 사용자 업로드 흐름 ──────────────────┐
│                                       │
│ 1. 폴더 생성                          │
│    [POST /process/upload/folder]     │
│    → folder_id, 디렉토리 생성        │
│                                       │
│ 2. 파일 업로드                       │
│    [POST /process/upload/files]      │
│    → 파일 저장, DB 기록              │
│                                       │
│ 3. 파일 목록 확인                    │
│    [GET /process/upload/{id}/files] │
│    → 폴더 내 파일 목록 표시          │
│                                       │
│ 4. 배치 처리 시작                    │
│    [POST /process/batch/create]     │
│    {source: "upload", folder_id: ...}
│    → job_id 반환                    │
│                                       │
│ 5. 처리 진행 중                      │
│    [WebSocket 또는 Polling]         │
│    → upload_files status 업데이트   │
│    → upload_folders status 업데이트 │
│                                       │
│ 6. 결과 확인                         │
│    [GET /process/upload/{id}]       │
│    → 처리 결과 조회                  │
│                                       │
│ 7. 폴더 삭제                         │
│    [DELETE /process/upload/{id}]    │
│    → 폴더 및 파일 삭제              │
│                                       │
└───────────────────────────────────────┘
```

---

## 7. 프론트엔드 UI

### 7.1 업로드 탭 (새로운 탭)
```
┌─ 배치 처리 페이지 (상단 탭) ────────────┐
│                                        │
│ [📅 날짜 선택] [📁 파일 업로드]        │  ← 두 개의 탭
│                                        │
│ === 파일 업로드 탭 콘텐츠 ===          │
│                                        │
│ 📁 폴더 관리                           │
│ ┌────────────────────────────────┐   │
│ │ 폴더명 입력: [_____________]    │   │
│ │ [폴더 생성]                    │   │
│ └────────────────────────────────┘   │
│                                        │
│ 📄 파일 업로드                         │
│ ┌────────────────────────────────┐   │
│ │ [드래그&드롭 또는 클릭]         │   │
│ │ ┌──────────────────────────┐  │   │
│ │ │ file1.txt (1.2KB) ✓      │  │   │
│ │ │ file2.txt (2.3KB) ✓      │  │   │
│ │ │ file3.txt (750B) ⚠️      │  │   │ (오류: 중복)
│ │ └──────────────────────────┘  │   │
│ │ 총 크기: 3.45KB / 최대: 100MB  │   │
│ │ [파일 추가] [모두 제거]        │   │
│ └────────────────────────────────┘   │
│                                        │
│ 🎯 처리 시작                          │
│ ┌────────────────────────────────┐   │
│ │ 선택한 폴더: "고객_김철수"      │   │
│ │ 파일 수: 2개                    │   │
│ │ [배치 처리 시작]               │   │
│ └────────────────────────────────┘   │
│                                        │
└────────────────────────────────────────┘
```

---

## 8. 배치 처리 통합

### 8.1 기존 배치 처리와의 차이
| 항목 | 날짜 기반 | 업로드 기반 |
|------|----------|-----------|
| 범위 지정 | 시작~종료 날짜 | 업로드 폴더 |
| 파일 소스 | SFTP | 로컬 uploads/ |
| 케이스 분류 | full/partial/no overlap | 불필요 (항상 새로운 처리) |
| 옵션 선택 | 필요 | 불필요 |
| 결과 저장 | date_status 통계 | batch_results |

### 8.2 처리 로직 (app/routes/process.py)
```python
async def run_batch_sync(job_id: str, req: BatchCreateRequest):
    """수정된 배치 처리"""
    
    if req.source == "date":
        # 기존 로직: date-based processing
        # date_status, calendar 범위 사용
        ...
    
    elif req.source == "upload":
        # 신규 로직: upload-folder-based processing
        folder = db.get_upload_folder(req.upload_folder_id)
        files = db.get_upload_files(req.upload_folder_id)
        
        for file in files:
            # 파일 처리
            result = process_file(file.file_path)
            
            # 결과 저장
            db.update_upload_file_status(file.file_id, result)
        
        # 폴더 상태 업데이트
        db.update_upload_folder_status(folder.folder_id, "completed")
```

---

## 9. 구현 순서 (Phase 5)

1. **DB 스키마** (15분)
   - upload_folders, upload_files 테이블 생성
   - batch_jobs 테이블 수정 (source, upload_folder_id 컬럼)

2. **파일 저장소** (10분)
   - uploads/ 디렉토리 구조
   - 경로 유틸 함수

3. **DB Manager 메서드** (30분)
   - create_upload_folder()
   - add_upload_files()
   - get_upload_folder()
   - get_upload_files()
   - update_upload_file_status()
   - list_upload_folders()

4. **백엔드 API** (1시간)
   - POST /process/upload/folder
   - POST /process/upload/files
   - GET /process/upload/folders
   - GET /process/upload/{id}/files
   - DELETE /process/upload/{id}
   - POST /process/batch/create 수정

5. **배치 처리 로직** (45분)
   - 업로드 폴더 기반 처리
   - 파일 상태 업데이트

6. **프론트엔드 UI** (1.5시간)
   - 업로드 탭 UI
   - 파일 드래그&드롭
   - 폴더 관리 UI
   - 배치 처리 통합

---

## 10. 파일 검증 규칙

### 10.1 파일 크기
- 단일 파일 최대: 10MB
- 폴더 총합 최대: 100MB

### 10.2 파일 타입
- 허용: .txt (텍스트)
- 검증: MIME type 확인 (text/plain)

### 10.3 중복 방지
- 방법: MD5 해시 (filename + content)
- 정책: 동일 파일 업로드 시 스킵 (경고)

### 10.4 파일명 정규화
- 한글 지원
- 특수문자 제거/대체
- 띄어쓰기 유지
- 최대 길이: 255자

---

## 11. 에러 처리

| 상황 | 응답 | 동작 |
|------|------|------|
| 폴더명 빈값 | 400 Bad Request | 재시도 요청 |
| 파일 크기 초과 | 413 Payload Too Large | 파일 제거 후 재업로드 |
| 파일 타입 오류 | 415 Unsupported Media Type | 파일 대체 |
| 폴더 미존재 | 404 Not Found | 폴더 재생성 |
| 처리 중 삭제 요청 | 409 Conflict | force 옵션 제시 |

---

## 12. 향후 확장

- [ ] 파일 미리보기 (텍스트 일부 표시)
- [ ] 파일 템플릿 다운로드
- [ ] 배치 처리 결과 CSV 내보내기
- [ ] 폴더 공유 (다른 사용자와)
- [ ] 폴더 버전 관리 (이전 버전 복구)
- [ ] 자동 정리 (N일 이상 미사용 폴더 삭제)
