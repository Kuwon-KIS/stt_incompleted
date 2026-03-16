# FastAPI + Paramiko + vLLM 배치 처리 시스템

이 프로젝트는 SFTP에서 텍스트 파일을 읽고, vLLM 모델을 호출한 뒤, 결과를 콜백 URL로 전송하는 기능을 제공합니다. 단일 파일 처리 및 병렬 배치 처리를 모두 지원합니다.

## 파일 구조

```
.
├── Dockerfile                 # Python 3.10.19-slim-trixie 기반 컨테이너 이미지
├── build.sh                   # Docker buildx를 사용한 멀티 아키텍처 빌드 스크립트
├── .env.local                 # 로컬(Mac) 개발/테스트 환경 설정 (mock 서버)
├── .env.dev                   # Linux dev 서버 환경 설정
├── .env.prod                  # Linux prod 서버 환경 설정
├── test_local.sh              # 로컬 환경 테스트 스크립트
├── test_remote.sh             # 배포 후 원격 서버 테스트 스크립트
├── requirements.txt           # Python 종속성 (fastapi, uvicorn, paramiko, requests)
├── app/
│   ├── main.py               # FastAPI 애플리케이션 및 엔드포인트
│   ├── sftp_client.py        # Paramiko 기반 SFTP 클라이언트
│   └── templates/            # Prompt 템플릿 디렉토리
│       ├── qwen_default.tmpl # Qwen API 호출용 기본 템플릿
│       └── generic.tmpl      # Agent API 호출용 일반 템플릿
├── output/                    # 빌드 결과 저장 디렉토리 (TAR 파일, .gitignore 등록)
└── README.md                 # 이 파일
```

## 주요 기능

1. **단일 파일 처리** (`/process`)
   - SFTP에서 파일 읽기 (또는 inline_text로 테스트)
   - **Prompt Template 지원** (qwen, gpt-4-mini 등에 맞는 프롬프트)
   - vLLM 호출 (인증 헤더 지원)
   - 결과를 콜백 URL로 전송

2. **배치 처리 (동기)** (`/process/batch`)
   - 여러 파일을 병렬로 처리
   - 동시성 조절 가능
   - 한 번에 결과 반환

3. **배치 처리 (비동기/상태 추적)**
   - `/process/batch/submit`: 배치 작업 제출 (job_id 반환)
   - `/process/batch/status/{job_id}`: 작업 상태 및 결과 조회

4. **Prompt Template 관리**
   - `/templates`: 사용 가능한 템플릿 목록
   - `/templates/{name}`: 특정 템플릿 조회
   - `POST /templates`: 새 템플릿 생성/수정
   - `DELETE /templates/{name}`: 템플릿 삭제
   - `POST /templates/refresh`: 디스크에서 다시 로드

5. **인증 지원**
   - vLLM/콜백에 Authorization 헤더 전송 가능
   - SFTP 자격증명을 환경변수로 관리 가능

6. **재시도 로직**
   - vLLM 호출 최대 3회 재시도 (exponential backoff)
   - 콜백 전송 최대 2회 재시도

7. **헬스 체크**
   - `/healthz`: 서버 상태 및 uptime 조회

8. **내부 Mock 엔드포인트**
   - `/mock/vllm`: 테스트용 가짜 vLLM
   - `/mock/callback`: 테스트용 가짜 콜백

## 설정 (환경변수)

이 프로젝트는 `.env` 파일을 사용하여 환경변수를 관리합니다. **세 가지 환경**을 명확히 구분합니다:

- **`.env.local`**: Mac/로컬 머신에서 build & test용 (mock 서버 기반)
- **`.env.dev`**: Linux dev 서버용 (실제 dev 서버 주소/계정)
- **`.env.prod`**: Linux prod 서버용 (실제 prod 서버 주소/계정)

### 설정 방식 개요

**Workflow:**
1. **로컬 Mac에서**: `.env.local`을 읽어 Docker 이미지 빌드 & 테스트
2. **Linux dev 서버**: `.env.dev`로 컨테이너 실행
3. **Linux prod 서버**: `.env.prod`로 컨테이너 실행

### 환경변수 우선순위 (높은 순서부터)

1. **Runtime override** (`docker run -e KEY=value`) ← 서버에서 추가 설정
2. **Build time embed** (이미지에 포함된 환경변수) ← .env.local/dev/prod에서 읽음
3. **코드 내부 기본값**

### 1. 로컬 개발 환경 (.env.local)

로컬 Mac 머신에서 build 및 test할 때 사용합니다. mock 서버 기반입니다.

```bash
# 파일 내용 확인
cat .env.local
```

`.env.local` 특징:
- vLLM: `http://localhost:8002/mock/vllm` (mock 사용)
- SFTP: `localhost:demo` (로컬 테스트)
- Callback: `http://localhost:8002/mock/callback` (mock 사용)
- 목적: 로컬에서 실제 외부 서비스 없이 전체 기능 테스트

### 2. Linux Dev 서버 환경 (.env.dev)

Linux dev 서버에 배포할 때 사용합니다. 실제 dev 서버의 주소와 계정을 포함합니다.

```bash
# 파일 내용 확인
cat .env.dev
```

`.env.dev` 예시:
```bash
APP_ENV=development
LLM_URL=http://vllm-dev:8000          # dev 서버의 vLLM
SFTP_HOST=sftp-dev.internal           # dev 서버의 SFTP
SFTP_USERNAME=dev_user
SFTP_PASSWORD=dev_password
CALLBACK_URL=http://callback-dev:3000/callback  # dev 콜백 서버
BATCH_CONCURRENCY=4
LOG_LEVEL=INFO
```

### 3. Linux Prod 서버 환경 (.env.prod)

Linux prod 서버에 배포할 때 사용합니다. 실제 prod 서버의 주소와 계정을 포함합니다.

```bash
# 파일 내용 확인
cat .env.prod
```

`.env.prod` 예시:
```bash
APP_ENV=production
LLM_URL=http://vllm-prod:8000         # prod 서버의 vLLM
LLM_AUTH_HEADER=Bearer your-token
SFTP_HOST=sftp-prod.example.com       # prod 서버의 SFTP
SFTP_USERNAME=prod_user
SFTP_PASSWORD=prod_password
CALLBACK_URL=http://callback-prod:3000/callback  # prod 콜백 서버
BATCH_CONCURRENCY=8
LOG_LEVEL=INFO
```

### 4. 환경변수 참고표

| 변수명 | 설명 | 기본값 | 보안 |
|--------|------|--------|------|
| `APP_ENV` | 애플리케이션 환경 | `dev` | 공개 |
| `APP_HOST` | 바인드 주소 | `0.0.0.0` | 공개 |
| `APP_PORT` | 포트번호 | `8002` | 공개 |
| `CALL_TYPE` | LLM 호출 방식 | `vllm` | 공개 |
| `LLM_URL` | vLLM 서버 주소 | 없음 | 공개 |
| `LLM_AUTH_HEADER` | 인증 헤더 | 없음 | **비밀** |
| `MODEL_PATH` | 모델 경로 (vLLM) | 없음 | 공개 |
| `AGENT_NAME` | Agent 이름 | 없음 | 공개 |
| `SFTP_HOST` | SFTP 서버 | 없음 | 공개 |
| `SFTP_PORT` | SFTP 포트 | `22` | 공개 |
| `SFTP_USERNAME` | SFTP 사용자명 | 없음 | **비밀** |
| `SFTP_PASSWORD` | SFTP 비밀번호 | 없음 | **비밀** |
| `SFTP_KEY` | SSH 개인키 경로 | 없음 | **비밀** |
| `SFTP_ROOT_PATH` | SFTP 루트 경로 | `/` | 공개 |
| `CALLBACK_URL` | 콜백 URL | 없음 | 공개 |
| `CALLBACK_AUTH_HEADER` | 콜백 인증 헤더 | 없음 | **비밀** |
| `TEMPLATE_NAME` | 기본 템플릿 | `qwen_default` | 공개 |
| `BATCH_CONCURRENCY` | 배치 동시성 | `4` | 공개 |
| `LOG_LEVEL` | 로그 레벨 | `INFO` | 공개 |

## Docker 빌드 및 배포

### 핵심: Local Build vs Linux Server Deployment

**로컬 Mac에서 빌드 및 테스트:**
```bash
./build.sh stt-service latest --env local
./test_local.sh
```

**Linux 서버에 배포:**
```bash
# dev 서버
docker run --env-file .env.dev -p 8002:8002 stt-service:latest

# prod 서버
docker run --env-file .env.prod -p 8002:8002 stt-service:latest
```

또는 빌드 시점에 각각의 이미지를 만들 수 있습니다:
```bash
# 로컬 테스트용
./build.sh stt-service local --env local

# Linux dev 배포용  
./build.sh docker.io/username/stt-service dev --env dev

# Linux prod 배포용
./build.sh docker.io/username/stt-service prod --env prod
```

### 빌드 스크립트 사용 (권장)

이 프로젝트는 `build.sh` 스크립트를 제공합니다. Docker buildx를 사용하여 `linux/amd64`와 `linux/arm64` 아키텍처를 지원합니다.

#### 사전 요구사항

```bash
# Docker buildx 설치 확인
docker buildx version

# 필요한 경우 QEMU 설정 (arm64 빌드용)
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

#### 개발 환경으로 빌드

```bash
chmod +x build.sh

# 로컬 Mac에서 테스트
./build.sh stt-service latest --env local

# Linux dev 서버용 이미지 빌드 (레지스트리에 푸시)
./build.sh docker.io/your-username/stt-service dev --env dev --push
```

#### 프로덕션 환경으로 빌드

```bash
# 방법 1: 레지스트리에 푸시 (권장)
./build.sh docker.io/your-username/stt-service v1.0.0 --env prod --push

# 방법 2: TAR 파일로 저장 (Linux 서버 전송용)
./build.sh docker.io/your-username/stt-service v1.0.0 --env prod --save

# 방법 3: GitHub Container Registry에 푸시
./build.sh ghcr.io/your-username/stt-service v1.0.0 --env prod --push
```

#### 빌드 스크립트 옵션

```
사용법: ./build.sh <repository> [tag] [--env local|dev|prod] [--push] [--save]

매개변수:
  <repository>      필수. Docker 레지스트리 주소 (docker.io/username/myapp)
  [tag]             선택. 이미지 태그, 기본값: latest
  [--env local|dev|prod]  선택. 빌드 환경 지정
                          local = .env.local (Mac 로컬 테스트용)
                          dev   = .env.dev (Linux dev 서버용)
                          prod  = .env.prod (Linux prod 서버용, 기본값)
  [--push]          선택. 빌드 후 레지스트리에 푸시 (멀티 아키텍처 지원)
  [--save]          선택. 빌드 후 TAR 파일로 저장 (output/ 디렉토리)
```

#### 빌드 예제

**로컬 Mac에서 빌드 및 테스트:**
```bash
# 로컬 개발: .env.local 읽음 (mock 서버 기반)
./build.sh stt-service latest --env local
./test_local.sh
```

**Linux 서버 배포용 이미지 빌드:**
```bash
# dev 서버용: .env.dev를 읽고 Docker Hub에 푸시
./build.sh docker.io/myusername/stt-service dev --env dev --push

# prod 서버용: .env.prod를 읽고 Docker Hub에 푸시
./build.sh docker.io/myusername/stt-service prod --env prod --push

# prod 서버용 TAR 파일 (registry 접근 불가시)
./build.sh docker.io/myusername/stt-service latest --env prod --save
```

**배포 시나리오:**
```bash
# Linux dev 서버
docker run --env-file .env.dev -p 8002:8002 docker.io/myusername/stt-service:dev

# Linux prod 서버
docker run --env-file .env.prod -p 8002:8002 docker.io/myusername/stt-service:prod
```

### TAR 파일로 저장하여 서버에 전송

Registry 접근이 불가능한 환경에서 사용합니다.

**1. 로컬 Mac에서 TAR 파일 생성**

```bash
# prod 환경용 TAR 파일 생성
./build.sh myregistry.com/stt-service v1.0.0 --env prod --save

# 결과 파일
# output/myregistry.com-stt-service-v1.0.0.tar
```

**2. Linux 서버로 파일 전송**

```bash
scp output/myregistry.com-stt-service-v1.0.0.tar user@prod-server:/path/to/
```

**3. 서버에서 이미지 로드 및 실행**

```bash
# 이미지 로드
docker load -i myregistry.com-stt-service-v1.0.0.tar

# .env.prod 파일을 서버에 복사 후 실행
docker run -d --name stt-service \
  --env-file .env.prod \
  -p 8002:8002 \
  myregistry.com/stt-service:v1.0.0
```

### 컨테이너 실행

#### 기본 실행 (Build Time 설정 사용)

```bash
# 이미지에 embed된 환경변수 사용
docker run -d --name stt-service -p 8002:8002 \
  docker.io/your-username/stt-service:latest
```

#### Environment Override (권장)

서버별 특정 설정이 필요한 경우, Build Time 설정을 override합니다:

```bash
docker run -d --name stt-service \
  -e SFTP_HOST=your-sftp-server.com \
  -e SFTP_USERNAME=your-sftp-user \
  -e SFTP_PASSWORD=your-sftp-pass \
  -e CALLBACK_URL=http://your-callback-server:3000/api/result \
  -e LLM_AUTH_HEADER="Bearer your-auth-token" \
  -p 8002:8002 \
  docker.io/your-username/stt-service:latest
```

#### docker-compose.yml 사용

```yaml
version: '3.8'

services:
  stt-service:
    image: docker.io/your-username/stt-service:latest
    ports:
      - "8002:8002"
    environment:
      # Build Time에서 읽은 .env.prod의 값들을 override
      - SFTP_HOST=production-sftp.example.com
      - SFTP_PASSWORD=production-password
      - CALLBACK_URL=http://production-callback:3000/api/result
    restart: unless-stopped
```

### 수동 빌드 (빌드 스크립트 미사용)

#### 멀티 아키텍처 빌드

```bash
# builder 생성 (최초 1회)
docker buildx create --name multiarch-builder --use

# 프로덕션 설정으로 빌드
docker buildx build \
  --build-arg ENV=production \
  --platform linux/amd64,linux/arm64 \
  -t docker.io/your-username/stt-service:latest \
  --push \
  .
```

#### 로컬 빌드 (단일 아키텍처, 테스트용)

```bash
docker build \
  --build-arg ENV=dev \
  -t stt-service:dev .
```

## 테스트

### 로컬 테스트 (개발 환경)

로컬에서 빌드부터 테스트까지 자동으로 수행하는 스크립트:

```bash
chmod +x test_local.sh
./test_local.sh
```

이 스크립트는 다음을 수행합니다:
1. Docker 이미지 빌드
2. 컨테이너 실행
3. 헬스 체크
4. 템플릿 로드 확인
5. qwen_default 템플릿 테스트
6. generic 템플릿 테스트
7. Template 없이 raw text 테스트
8. 한글 Unicode 처리 테스트

### 배포 후 테스트 (운영 환경)

배포된 서버에서 테스트하는 스크립트:

```bash
chmod +x test_remote.sh
./test_remote.sh
```

또는 커스텀 호스트/포트로 테스트:

```bash
SERVICE_HOST=example.com SERVICE_PORT=8080 ./test_remote.sh
```

환경변수로 미리 설정:

```bash
export SERVICE_HOST=your-server.com
export SERVICE_PORT=8080
./test_remote.sh
```

## 처리 흐름 아키텍처

### 전체 흐름도

```
┌─────────────────────────────────────────────────────────────────┐
│                         입력 텍스트 획득                         │
├─────────────────────────────────────────────────────────────────┤
│  1. SFTP 경로에서 파일 읽기 (/process + remote_path)           │
│     또는                                                        │
│  2. 웹 UI에서 inline text 직접 입력 (/process + inline_text)  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Text 점검/분석                              │
├─────────────────────────────────────────────────────────────────┤
│  경로 A: vLLM 방식                                              │
│  - Prompt Template에 맞게 텍스트 포맷 변환                     │
│  - vLLM 서버로 HTTP POST (LLM_URL)                             │
│  - Authorization 헤더 포함 (LLM_AUTH_HEADER)                   │
│                                                                │
│  경로 B: AI Agent 방식                                         │
│  - 사용자 텍스트를 그대로 Agent API에 전달                     │
│  - Agent 서버로 HTTP POST (LLM_URL/{AGENT_NAME})               │
│  - user_query와 context로 파라미터 구성                        │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      결과 전송 (선택사항)                        │
├─────────────────────────────────────────────────────────────────┤
│  - 콜백 URL이 제공된 경우 결과를 콜백 엔드포인트로 POST        │
│  - Authorization 헤더 포함 (CALLBACK_AUTH_HEADER)              │
│  - 최대 2회 재시도 (실패 시)                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 입력 방식

#### 1. SFTP 파일 읽기

```
요청: POST /process
{
  "host": "sftp.example.com",
  "username": "user",
  "password": "pass",
  "remote_path": "/uploads/file.txt",
  "call_type": "vllm"
}

처리:
1. SFTP 연결 (host:port, username/password)
2. remote_path에서 파일 읽기 (UTF-8)
3. 텍스트 내용 추출
4. Detection 로직으로 진행
```

#### 2. Inline Text (웹 UI / 직접 입력)

```
요청: POST /process
{
  "inline_text": "사용자가 직접 붙여넣은 텍스트 내용",
  "call_type": "vllm",
  "template_name": "qwen_default"
}

처리:
1. inline_text 필드에서 직접 텍스트 추출
2. SFTP 연결 없음 (로컬 테스트에 용이)
3. 텍스트 내용으로 Detection 로직 진행
```

### Detection (분석) 로직

#### 경로 A: vLLM 사용

```
입력 텍스트
    ▼
[Prompt Template 포맷 변환]
- template_name에 해당하는 템플릿 로드
- 텍스트를 템플릿 변수로 치환
- 포맷된 프롬프트 생성
    ▼
[vLLM 호출]
POST {LLM_URL}/v1/chat/completions
Headers:
  Authorization: {LLM_AUTH_HEADER}
  Content-Type: application/json
Body:
{
  "model": "{MODEL_PATH}",
  "messages": [{"role": "user", "content": "{formatted_prompt}"}]
}
    ▼
[응답 처리]
- vLLM 응답에서 detection 결과 추출
- 불완전판매요소 감지 결과 저장
- 재시도: 최대 3회 (exponential backoff)
    ▼
결과 반환
```

#### 경로 B: AI Agent 사용

```
입력 텍스트
    ▼
[텍스트 그대로 전달]
- 추가 포맷 변환 없음
- 사용자 질문 + 텍스트 컨텍스트
    ▼
[Agent API 호출]
POST {LLM_URL}/{AGENT_NAME}/messages
Headers:
  Authorization: {LLM_AUTH_HEADER}
  Content-Type: application/json
Body:
{
  "parameters": {
    "user_query": "{question/prompt}",
    "context": "{input_text}"
  },
  "use_streaming": {USE_STREAMING}
}
    ▼
[응답 처리]
- Agent 응답에서 detection 결과 추출
- 불완전판매요소 감지 결과 저장
- 재시도: 최대 3회
    ▼
결과 반환
```

### 선택 기준 (vLLM vs Agent)

| 항목 | vLLM | Agent |
|------|------|-------|
| **프롬프트 처리** | Template 기반 포맷 변환 | 사용자 입력 그대로 사용 |
| **구성** | API 엔드포인트 직접 호출 | 별도 Agent 시스템 |
| **유연성** | 낮음 (Template 정의 필요) | 높음 (직접 질문 가능) |
| **성능** | 빠름 | 가변적 |
| **사용 시기** | 구조화된 프롬프트 필요 | 자유도 높은 분석 필요 |
| **설정** | CALL_TYPE=vllm, MODEL_PATH | CALL_TYPE=agent, AGENT_NAME |

### 배치 처리 (여러 파일)

```
요청: POST /process/batch/submit
{
  "host": "sftp.internal",
  "username": "user",
  "password": "pass",
  "root_path": "/uploads",
  "start_date": "20260301",  ← YYYYMMDD 형식
  "end_date": "20260305",     ← YYYYMMDD 형식
  "call_type": "vllm"
}

처리:
1. SFTP 연결
2. /uploads/20260301/, /uploads/20260302/ 등 폴더 탐색
3. 각 폴더의 .txt 파일 발견
4. ThreadPoolExecutor로 동시 처리 (동시 수는 BATCH_CONCURRENCY 환경변수로 설정, 기본값: 4)
5. 각 파일마다 위의 vLLM/Agent 로직 실행
6. 결과를 job_id로 저장 (비동기)
7. 즉시 job_id 반환

상태 조회: GET /process/batch/status/{job_id}
응답: {
  "status": "running|completed|failed",
  "progress": {"processed": 5, "total": 10},
  "results": [...]
}
```

## API 엔드포인트 및 예시


### 1. 헬스 체크

```bash
curl -sS http://localhost:8002/healthz
```

응답:
```json
{"status":"ok","uptime_seconds":123,"time":"2026-01-26T12:36:08.737082+00:00"}
```

### 2. 단일 파일 처리 (inline_text로 테스트)

최소 요청 (나머지는 .env 파일에서):

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "remote_path": "/path/to/file.txt",
    "inline_text": "hello world"
  }'
```

전체 파라미터:

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "port": 22,
    "username": "user",
    "password": "pass",
    "remote_path": "/path/to/file.txt",
    "call_type": "vllm",
    "llm_url": "http://localhost:8000",
    "model_path": "qwen/qwen-7b-chat",
    "callback_url": "http://localhost:8002/mock/callback",
    "inline_text": "hello world",
    "template_name": "qwen_default"
  }'
```

### 3. 인증 헤더를 포함한 처리

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "port": 22,
    "username": "user",
    "password": "pass",
    "remote_path": "/path/to/file.txt",
    "vllm_url": "https://vllm.example.com/api/infer",
    "vllm_auth_header": "Bearer your-token-here",
    "callback_url": "https://callback.example.com/result",
    "callback_auth_header": "Bearer callback-token",
    "inline_text": "test text"
  }'
```

### 4. 환경변수를 통한 SFTP 자격증명 사용

환경에서 다음과 같이 설정:
```bash
export SFTP_CRED_PROD_USERNAME=username
export SFTP_CRED_PROD_PASSWORD=password
export SFTP_CRED_PROD_KEY=/path/to/key.pem  # 또는 패스워드만 사용
```

그 후 요청:
```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "credential_name": "prod",
    "remote_path": "/path/to/file.txt",
    "vllm_url": "http://vllm-api:8000/infer",
    "callback_url": "http://callback-handler:5000/process"
  }'
```

### 5. Prompt Template 사용

#### 5.1 사용 가능한 템플릿 목록

```bash
curl http://localhost:8002/templates
```

응답:
```json
{
  "templates": ["qwen_default", "gpt4mini_default", "generic"],
  "count": 3
}
```

#### 5.2 특정 템플릿 조회

```bash
curl http://localhost:8002/templates/qwen_default
```

#### 5.3 Template을 사용한 처리 (Qwen)

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "username": "user",
    "password": "pass",
    "remote_path": "/path/to/file.txt",
    "vllm_url": "http://qwen-api:8000/infer",
    "callback_url": "http://callback-handler:5000/process",
    "inline_text": "The quick brown fox jumps over the lazy dog.",
    "template_name": "qwen_default"
  }'
```

Template `qwen_default`의 내용:
```
You are a helpful AI assistant. Process the following text and provide a summary or answer to the question if provided.

Text: {text}
Question: {question}

Please provide a clear and concise response.
```

최종 프롬프트는 다음과 같이 생성됩니다:
```
You are a helpful AI assistant. Process the following text and provide a summary or answer to the question if provided.

Text: The quick brown fox jumps over the lazy dog.
Question: Summarize this text.

Please provide a clear and concise response.
```

#### 5.4 Template 없이 Raw Text 사용

template을 지정하지 않으면 SFTP에서 읽은 text를 그대로 vLLM에 전달합니다:

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "username": "user",
    "password": "pass",
    "remote_path": "/path/to/file.txt",
    "vllm_url": "http://vllm-api:8000/infer",
    "callback_url": "http://callback-handler:5000/process"
  }'
```

#### 5.5 새 Template 생성

```bash
curl -X POST http://localhost:8002/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_custom_template",
    "content": "Analyze the following:\n\nData: {text}\n\nTask: {question}\n\nResult:"
  }'
```

#### 5.7 Template 삭제

```bash
curl -X DELETE http://localhost:8002/templates/my_custom_template
```

#### 5.8 Template 새로고침 (디스크에서 다시 로드)

```bash
curl -X POST http://localhost:8002/templates/refresh
```

### 5.8 동기 배치 처리 (날짜 범위로 파일 자동 발견)

```bash
curl -X POST http://localhost:8002/process/batch \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "username": "user",
    "password": "pass",
    "start_date": "20260120",
    "end_date": "20260127",
    "root_path": "/data",
    "vllm_url": "http://vllm-api:8000/infer",
    "callback_url": "http://callback-handler:5000/process",
    "template_name": "qwen_default"
  }'
```

이 요청은 다음을 자동으로 처리합니다:
- `/data/20260120/` 폴더의 모든 `.txt` 파일
- `/data/20260121/` 폴더의 모든 `.txt` 파일
- ...
- `/data/20260127/` 폴더의 모든 `.txt` 파일

응답:
```json
{
  "results": [
    {
      "index": 0,
      "date": "20260120",
      "filename": "file1.txt",
      "success": true,
      "result": {
        "status": "ok",
        "model_output": {"summary": "...", "tokens": 123},
        "callback_status": 200
      }
    }
  ],
  "total": 10
}
```

### 7. 비동기 배치 처리 (job_id 반환)

작업 제출:
```bash
curl -X POST http://localhost:8002/process/batch/submit \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "username": "user",
    "password": "pass",
    "start_date": "20260120",
    "end_date": "20260127",
    "root_path": "/data",
    "vllm_url": "http://vllm-api:8000/infer",
    "callback_url": "http://callback-handler:5000/process",
    "template_name": "qwen_default"
  }'
```

응답:
```json
{
  "job_id": "f8743538-6b32-401a-85fe-6f68b7387add",
  "status": "submitted",
  "date_range": "20260120 to 20260127"
}
```

상태 조회:
```bash
curl http://localhost:8002/process/batch/status/f8743538-6b32-401a-85fe-6f68b7387add
```

응답:
```json
{
  "job_id": "f8743538-6b32-401a-85fe-6f68b7387add",
  "status": "completed",
  "created_at": "2026-01-26T12:36:08.763198+00:00",
  "started_at": "2026-01-26T12:36:08.764064+00:00",
  "completed_at": "2026-01-26T12:36:08.767477+00:00",
  "date_range": "20260120 to 20260127",
  "error": null,
  "results": [
    {
      "index": 0,
      "date": "20260120",
      "filename": "file1.txt",
      "success": true,
      "result": {
        "status": "ok",
        "model_output": {"summary": "...", "tokens": 123},
        "callback_status": 200
      }
    }
  ]
}
```

## 로깅

모든 엔드포인트는 다음과 같은 정보를 로깅합니다:
- SFTP 연결/파일 읽기
- vLLM 호출 및 재시도
- 콜백 전송 결과
- 배치 작업 진행 상황
- Template 로딩 및 프롬프트 생성

로그 포맷:
```
2026-01-26 12:36:08,763 INFO app.main batch processing 2 items with concurrency=2
2026-01-26 12:36:08,795 INFO app.main process_sync start remote_path=/tmp/foo.txt host=localhost
2026-01-26 12:36:08,795 INFO app.main using inline_text length=25
2026-01-26 12:36:08,795 INFO app.main built prompt from template=qwen_default length=150
2026-01-26 12:36:08,795 INFO app.main calling vLLM url=http://localhost:8002/mock/vllm
2026-01-26 12:36:08,795 INFO app.main vLLM returned; forwarding to callback http://localhost:8002/mock/callback
```

## Template 디렉토리 구조

```
app/
├── main.py
├── sftp_client.py
└── templates/
    ├── qwen_default
    ├── gpt4mini_default.txt
    └── generic
```

각 템플릿은 `{text}`와 `{question}` 플레이스홀더를 포함할 수 있습니다:
- `{text}`: SFTP에서 읽은 파일 내용 (또는 inline_text)
- `{question}`: 요청에서 전달된 question 필드

## 예제: Qwen 모델 사용

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.your-server.com",
    "username": "sftp_user",
    "password": "sftp_pass",
    "remote_path": "/documents/article.txt",
    "vllm_url": "http://qwen-server:8000/v1/completions",
    "vllm_auth_header": "Bearer your-token",
    "callback_url": "http://your-backend:5000/results",
    "template_name": "qwen_default",
    "question": "Summarize the key points from this article."
  }'
```

## 주의사항

1. **시크릿 관리**: 프로덕션에서는 SFTP 자격증명과 인증 토큰을 Docker secrets 또는 mounted volumes로 전달하세요.
2. **상태 저장**: 현재 배치 작업 상태는 메모리에 저장됩니다. 프로덕션에서는 Redis 또는 데이터베이스로 전환하세요.
3. **타임아웃**: 기본 vLLM 타임아웃은 30초, 콜백 타임아웃은 10초입니다. 필요 시 조정하세요.
4. **재시도**: vLLM은 최대 3회 재시도(1초 간격), 콜백은 최대 2회 재시도(0.5초 간격)합니다.

## 라이선스 및 참고

- FastAPI: https://fastapi.tiangolo.com/
- Paramiko: https://www.paramiko.org/
- Requests: https://requests.readthedocs.io/

