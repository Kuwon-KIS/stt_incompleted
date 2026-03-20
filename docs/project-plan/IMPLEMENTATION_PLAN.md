# STT 불완전판매요소 탐지 시스템 - 개선 계획

**작성일**: 2026년 3월 13일  
**목표**: 기존 API 기반 시스템을 웹 인터페이스와 함께 제공하는 엔터프라이즈 시스템으로 확장

---

## 배치 처리 관련 신규 실행 계획

- BATCH_TAB_SFTP_OPTIMIZATION_PLAN.md
- BATCH_LAST_DATE_DEFAULT_PLAN.md
- BATCH_EMPTY_DATE_FILTER_TOGGLE_PLAN.md

---

## 📋 프로젝트 개요

### 현재 상태
- ✅ FastAPI 기반 REST API (단일/배치 파일 처리)
- ✅ SFTP 클라이언트 (음성 녹취 텍스트 파일 수신)
- ✅ LLM 통합 (vLLM, AI Agent)
- ✅ Prompt 템플릿 시스템
- ✅ Docker 컨테이너화
- ❌ 웹 사용자 인터페이스
- ❌ 명확한 환경별 빌드 구분
- ❌ 탐지 모듈 명시적 구조화

### 목표
1. **사용성 향상**: API 기반에서 웹 UI로 진화
2. **운영 효율성**: 로컬/개발/운영 환경 명확한 분리
3. **코드 품질**: 탐지 모듈 명시적 구조화 및 전략 패턴 도입

---

## 🏗️ 1단계: 프로젝트 구조 재설계

### 목표 구조

```
stt_incompleted/
├── docs/                          # 📄 문서 관리
│   ├── IMPLEMENTATION_PLAN.md     # 이 파일
│   ├── ARCHITECTURE.md            # 시스템 아키텍처
│   ├── API_GUIDE.md               # API 가이드
│   ├── DEPLOYMENT.md              # 배포 가이드
│   └── development/
│       ├── LOCAL_SETUP.md         # 로컬 개발 환경 설정
│       └── ENV_CONFIGURATION.md   # 환경 변수 설정 가이드
├── app/                           # 🐍 백엔드 애플리케이션
│   ├── main.py                    # FastAPI 메인 앱
│   ├── config.py                  # ⭐ 설정 관리 (새로 분리)
│   ├── sftp_client.py             # SFTP 클라이언트
│   ├── models.py                  # ⭐ Pydantic 모델 (새로 분리)
│   ├── detection/                 # ⭐ 불완전판매요소 탐지 모듈 (새로 추가)
│   │   ├── __init__.py
│   │   ├── base.py                # 기본 인터페이스
│   │   ├── vllm_detector.py       # vLLM 구현
│   │   └── agent_detector.py      # AI Agent 구현
│   ├── routes/                    # ⭐ 라우터 분리 (새로 추가)
│   │   ├── __init__.py
│   │   ├── process.py             # 처리 엔드포인트
│   │   ├── templates.py           # 템플릿 관리
│   │   ├── sftp.py                # SFTP 관리
│   │   ├── batch.py               # 배치 처리
│   │   ├── health.py              # 헬스 체크
│   │   └── web.py                 # ⭐ 웹 UI 라우트 (새로 추가)
│   ├── templates/                 # Prompt 템플릿
│   │   ├── qwen_default.tmpl
│   │   └── generic.tmpl
│   ├── static/                    # ⭐ 정적 파일 (새로 추가)
│   │   ├── css/
│   │   ├── js/
│   │   └── index.html
│   └── utils.py                   # ⭐ 유틸리티 함수 (새로 추가)
├── frontend/                      # ⭐ 프론트엔드 (새로 추가)
│   ├── README.md
│   ├── index.html
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── app.js
│       ├── api.js
│       └── components/
│           ├── batch-processor.js
│           ├── template-manager.js
│           └── job-monitor.js
├── scripts/                       # ⭐ 스크립트 정리 (새로 추가)
│   ├── build-local.sh
│   ├── build-dev.sh
│   ├── build-prod.sh
│   └── deploy.sh
├── environments/                  # ⭐ 환경별 설정 (새로 추가)
│   ├── .env.local                 # 로컬 (맥북) 개발
│   ├── .env.dev                   # 개발 (Linux, AWS EC2)
│   └── .env.prod                  # 운영 (Linux, On-premise)
├── tests/                         # ⭐ 테스트 추가 (새로 추가)
│   ├── test_detection.py
│   ├── test_sftp.py
│   └── test_routes.py
├── Dockerfile                     # Docker 이미지
├── docker-compose.yaml            # ⭐ Docker Compose (새로 추가)
├── requirements.txt
├── README.md
└── .dockerignore
```

### 신규 추가 항목 설명

| 항목 | 목적 |
|-----|-----|
| `docs/` | 모든 문서 중앙화 |
| `app/config.py` | 환경 변수 및 설정 관리 |
| `app/models.py` | Pydantic 요청/응답 모델 |
| `app/detection/` | 불완전판매요소 탐지 전략 패턴 |
| `app/routes/` | 엔드포인트별 라우터 분리 |
| `app/static/` | 웹 UI 정적 파일 |
| `frontend/` | 독립형 프론트엔드 (선택사항) |
| `scripts/` | 환경별 빌드 스크립트 |
| `environments/` | 환경별 설정 파일 |
| `docker-compose.yaml` | 로컬/개발 환경 구성 |

---

## 🔧 2단계: 빌드 스크립트 정비

### 목표
- 환경별(로컬/개발/운영) 명확한 구분
- 자동화된 배포 프로세스
- 멀티 아키텍처 지원 (arm64, amd64)

### 구현 방안

#### 2-1. 환경별 스크립트 분리

**파일: `scripts/build-local.sh`** (로컬 맥북용)
```bash
#!/bin/bash
# 로컬 맥북 개발 환경용
# - 기본 포트: 8002
# - vLLM/Agent: Mock 또는 로컬 서버
# - SFTP: 테스트 서버 또는 Mock
# - 목적: 빠른 반복 개발
docker build -t stt-service:local \
  --build-arg ENV=local \
  -f Dockerfile .
```

**파일: `scripts/build-dev.sh`** (AWS EC2 개발 서버용)
```bash
#!/bin/bash
# AWS EC2 Linux 개발 환경용
# - 기본 포트: 8002
# - vLLM/Agent: dev 서버
# - SFTP: dev 파일 서버
# - 목적: 통합 테스트 환경
docker buildx build --platform linux/amd64 \
  -t docker.io/username/stt-service:dev \
  --build-arg ENV=dev \
  --push -f Dockerfile .
```

**파일: `scripts/build-prod.sh`** (On-premise 운영 서버용)
```bash
#!/bin/bash
# On-premise Linux 운영 환경용
# - 기본 포트: 8002
# - vLLM/Agent: prod 서버
# - SFTP: prod 파일 서버 (고가용성)
# - 목적: 안정적인 프로덕션 운영
docker buildx build --platform linux/amd64,linux/arm64 \
  -t docker.io/username/stt-service:prod \
  --build-arg ENV=prod \
  --push -f Dockerfile .
```

#### 2-2. 환경별 설정 파일

**파일: `environments/.env.local`**
```ini
APP_ENV=local
LOG_LEVEL=DEBUG

# SFTP (테스트 서버)
SFTP_HOST=localhost
SFTP_PORT=2222
SFTP_USERNAME=test_user
SFTP_PASSWORD=test_password

# LLM (Mock)
CALL_TYPE=vllm
LLM_URL=http://localhost:8002/mock/vllm
MODEL_PATH=mock-model

# Callback
CALLBACK_URL=http://localhost:8002/mock/callback
```

**파일: `environments/.env.dev`**
```ini
APP_ENV=dev
LOG_LEVEL=INFO

# SFTP (개발 서버)
SFTP_HOST=sftp-dev.internal
SFTP_PORT=22
SFTP_USERNAME=app_dev

# LLM (개발 서버)
CALL_TYPE=vllm
LLM_URL=https://vllm-dev.internal:8000/v1/chat/completions
LLM_AUTH_HEADER=Bearer dev_token_xxx

# Callback
CALLBACK_URL=https://callback-dev.internal/results
```

**파일: `environments/.env.prod`**
```ini
APP_ENV=prod
LOG_LEVEL=WARN

# SFTP (운영 서버 - 고가용성)
SFTP_HOST=sftp-prod-lb.internal
SFTP_PORT=22
SFTP_USERNAME=app_prod
SFTP_KEY=/run/secrets/sftp_key

# LLM (운영 서버)
CALL_TYPE=vllm
LLM_URL=https://vllm-prod-lb.internal/v1/chat/completions
LLM_AUTH_HEADER=Bearer prod_token_xxx

# Callback
CALLBACK_URL=https://api-prod.internal/results
```

---

## 🎨 3단계: 웹 인터페이스 구축

### 목표
- API 기반 배치 프로세스를 웹 UI로 제공
- 실시간 진행 상황 모니터링
- 템플릿 및 결과 관리

### 주요 기능

#### 3-1. 대시보드 페이지
- 📊 시스템 상태 (헬스, 업타임)
- 📈 최근 작업 현황 (성공/실패)
- 🎯 빠른 통계 (총 처리 파일, 평균 처리 시간)

#### 3-2. 배치 처리 페이지
- 📅 날짜 범위 선택
- 🔧 LLM 설정 (vLLM vs Agent)
- 📤 업로드 또는 SFTP 경로 지정
- 💾 템플릿 선택
- ▶️ 처리 시작 버튼
- 📊 실시간 진행률 표시 (프로그레스 바)
- 📋 결과 테이블 (다운로드 가능)

#### 3-3. 템플릿 관리 페이지
- 📝 템플릿 목록 조회
- ➕ 신규 템플릿 생성/편집
- 🗑️ 템플릿 삭제
- 👁️ 프리뷰 기능

#### 3-4. 작업 이력 페이지
- 🔍 작업 ID로 검색
- 📊 상태별 필터링 (진행중, 완료, 실패)
- 📥 결과 다운로드
- 🔄 재시도 기능

### 기술 스택

**간단한 구현 (추천 - 1주일)**
- 순수 HTML + CSS + Vanilla JS
- FastAPI의 `StaticFiles` 미들웨어 활용
- 경로: `app/static/` + `app/routes/web.py`

**중간 규모 구현 (2~3주일)**
- Vue.js 또는 React
- API 연동 (fetch/axios)
- 차트 라이브러리 (Chart.js)

---

## 🔍 4단계: 불완전판매요소 탐지 모듈화

### 목표
- Strategy 패턴으로 탐지 방식 분리
- vLLM과 AI Agent 명확한 구현 분리
- 설정 기반 선택

### 아키텍처

#### 4-1. 기본 인터페이스

**파일: `app/detection/base.py`**
```python
from abc import ABC, abstractmethod

class DetectionStrategy(ABC):
    """불완전판매요소 탐지 전략 인터페이스"""
    
    @abstractmethod
    async def detect(self, text: str, prompt: str) -> dict:
        """텍스트에서 불완전판매요소 탐지
        
        Returns:
            {
                "detected_issues": [...],
                "confidence": 0.95,
                "raw_response": "...",
                "tokens_used": 1234
            }
        """
        pass
    
    @abstractmethod
    def validate_config(self) -> bool:
        """필수 설정 검증"""
        pass
```

#### 4-2. vLLM 구현

**파일: `app/detection/vllm_detector.py`**
```python
from .base import DetectionStrategy

class VLLMDetector(DetectionStrategy):
    """vLLM을 사용한 탐지 전략
    
    특징:
    - Prompt Template 기반
    - 구조화된 프롬프트
    - 모델 경로 지정 필요
    """
    
    async def detect(self, text: str, prompt: str) -> dict:
        # 1. 프롬프트 템플릿 적용
        # 2. vLLM API 호출 (인증 헤더 포함)
        # 3. 응답 파싱
        # 4. 불완전판매요소 추출
        pass
```

#### 4-3. AI Agent 구현

**파일: `app/detection/agent_detector.py`**
```python
from .base import DetectionStrategy

class AgentDetector(DetectionStrategy):
    """AI Agent를 사용한 탐지 전략
    
    특징:
    - 사용자 입력 직접 활용
    - 기본 제공 프롬프트
    - Agent 이름으로 선택
    """
    
    async def detect(self, text: str, prompt: str) -> dict:
        # 1. 사용자 질문 활용
        # 2. Agent API 호출
        # 3. 응답 파싱
        # 4. 불완전판매요소 추출
        pass
```

#### 4-4. 팩토리 및 통합

**파일: `app/detection/__init__.py`**
```python
def get_detector(call_type: str, config: Config) -> DetectionStrategy:
    """설정에 따라 적절한 탐지 전략 반환"""
    if call_type == "vllm":
        return VLLMDetector(config)
    elif call_type == "agent":
        return AgentDetector(config)
    else:
        raise ValueError(f"Unknown call_type: {call_type}")
```

### 통합 흐름

```python
# app/routes/process.py
detector = get_detector(req.call_type, config)
result = await detector.detect(text=file_content, prompt=constructed_prompt)
```

---

## 📦 5단계: 코드 구조화 및 모듈화

### 5-1. 설정 관리 분리

**파일: `app/config.py`**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """환경 변수 기반 설정 관리"""
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    # SFTP
    SFTP_HOST: str
    SFTP_PORT: int = 22
    # ... 기타
    
    def validate(self) -> bool:
        """필수 설정 검증"""
        pass

settings = Settings()
```

### 5-2. Pydantic 모델 분리

**파일: `app/models.py`**
```python
from pydantic import BaseModel

class ProcessRequest(BaseModel):
    remote_path: str | None = None
    inline_text: str | None = None
    # ...

class BatchProcessRequest(BaseModel):
    start_date: str
    end_date: str
    # ...
```

### 5-3. 라우터 분리

**파일: `app/routes/process.py`**
```python
from fastapi import APIRouter
router = APIRouter(prefix="/process", tags=["process"])

@router.post("")
async def process(req: ProcessRequest):
    pass
```

**파일: `app/main.py`**
```python
from app.routes import process, templates, batch, health

app.include_router(health.router)
app.include_router(process.router)
app.include_router(templates.router)
app.include_router(batch.router)
```

---

## 🧪 6단계: 테스트 및 검증

### 테스트 범위

```
tests/
├── test_detection.py        # 탐지 모듈 단위 테스트
├── test_sftp.py             # SFTP 클라이언트 테스트
├── test_routes.py           # API 엔드포인트 통합 테스트
└── conftest.py              # pytest 설정
```

---

## 📊 구현 단계별 일정

| 단계 | 작업 | 소요 기간 | 우선순위 |
|-----|------|---------|---------|
| 1 | 프로젝트 구조 재설계 | 1-2일 | 🔴 높음 |
| 2 | 빌드 스크립트 정비 | 2-3일 | 🔴 높음 |
| 3a | 웹 UI (기본) | 1주일 | 🟡 중간 |
| 3b | 웹 UI (고급) | 2-3주일 | 🟢 낮음 |
| 4 | 탐지 모듈 구조화 | 3-4일 | 🔴 높음 |
| 5 | 코드 모듈화 | 2-3일 | 🟡 중간 |
| 6 | 테스트 추가 | 3-4일 | 🟡 중간 |
| 7 | 문서화 | 지속적 | 🟢 낮음 |

**권장 순서**: 1 → 2 → 4 → 5 → 3a → 6 → 7 → (3b)

---

## ✅ 체크리스트

### 사전 작업
- [ ] 현재 코드 백업
- [ ] 새로운 폴더 구조 생성
- [ ] git 브랜치 생성 (`feature/restructure-v2`)

### Phase 1: 구조 재설계
- [ ] `docs/` 폴더 및 문서 작성
- [ ] `app/config.py` 분리
- [ ] `app/models.py` 분리
- [ ] `app/routes/` 폴더 및 라우터 분리
- [ ] `app/detection/` 모듈 작성
- [ ] `scripts/` 빌드 스크립트 작성
- [ ] `environments/` 설정 파일 작성

### Phase 2: 웹 인터페이스
- [ ] 기본 HTML/CSS/JS 구성
- [ ] 대시보드 페이지
- [ ] 배치 처리 페이지
- [ ] 템플릿 관리 페이지
- [ ] 작업 이력 페이지
- [ ] 웹소켓 또는 폴링으로 실시간 업데이트

### Phase 3: 배포
- [ ] Docker 이미지 빌드 테스트
- [ ] docker-compose.yaml 작성
- [ ] 로컬 테스트
- [ ] 개발 서버 배포 테스트
- [ ] 운영 서버 배포 가이드

---

## 📚 추가 문서 예정

- `ARCHITECTURE.md`: 시스템 아키텍처 다이어그램
- `API_GUIDE.md`: API 엔드포인트 상세 설명
- `DEPLOYMENT.md`: 배포 절차 및 운영 가이드
- `development/LOCAL_SETUP.md`: 로컬 개발 환경 설정
- `development/ENV_CONFIGURATION.md`: 환경 변수 설정 가이드

---

**다음 단계**: 이 계획을 바탕으로 구체적인 구현을 시작합니다.  
질문이나 수정 사항이 있으면 언제든지 알려주세요!
