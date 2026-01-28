# FastAPI + Paramiko + vLLM 배치 처리 시스템

이 프로젝트는 SFTP에서 텍스트 파일을 읽고, vLLM 모델을 호출한 뒤, 결과를 콜백 URL로 전송하는 기능을 제공합니다. 단일 파일 처리 및 병렬 배치 처리를 모두 지원합니다.

## 파일 구조

```
.
├── Dockerfile                 # Python 3.10.19-slim-trixie 기반 컨테이너 이미지
├── build.sh                   # Docker buildx를 사용한 멀티 아키텍처 빌드 스크립트
├── test_local.sh              # 로컬 환경 테스트 스크립트
├── test_remote.sh             # 배포 후 원격 서버 테스트 스크립트
├── requirements.txt           # Python 종속성 (fastapi, uvicorn, paramiko, requests)
├── app/
│   ├── main.py               # FastAPI 애플리케이션 및 엔드포인트
│   ├── sftp_client.py        # Paramiko 기반 SFTP 클라이언트
│   ├── config.example.py     # 설정 파일 예제
│   └── templates/            # Prompt 템플릿 디렉토리
│       ├── qwen_default.tmpl # Qwen API 호출용 기본 템플릿
│       └── generic.tmpl      # Agent API 호출용 일반 템플릿
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

이 프로젝트는 `.env` 파일을 사용하여 환경변수를 관리합니다. **평문 설정을 서버에 노출하지 않기 위해** 빌드 시점에 `.env.dev` 또는 `.env.prod`를 읽고 이미지에 embed하는 방식을 사용합니다.

### 설정 방식 개요

**문제점:** `.env` 파일을 런타임에 읽으면 비밀 정보(패스워드, 토큰)가 서버의 평문 파일로 노출됩니다.

**해결책:** 
1. **Build 시점** (로컬에서): dev/prod 환경을 지정하여 해당 `.env.dev`/`.env.prod`를 읽고 Docker 이미지에 환경변수로 embed
2. **Runtime 시점** (서버에서): docker run `-e` 옵션으로 필요한 값만 override

### 환경변수 우선순위 (높은 순서부터)

1. **Runtime override** (`docker run -e KEY=value`) ← 서버에서 추가 설정
2. **Build time embed** (이미지에 포함된 환경변수) ← .env.dev/.env.prod에서 읽음
3. **코드 내부 기본값**

### 1. 개발 환경 설정 (.env.dev)

로컬 개발용 설정입니다. localhost 서비스를 사용합니다.

```bash
# 파일 내용 확인
cat .env.dev
```

`.env.dev` 예시:
```bash
APP_ENV=development
LLM_URL=http://localhost:8000
MODEL_PATH=qwen/qwen-7b-chat
SFTP_HOST=localhost
SFTP_USERNAME=demo
SFTP_PASSWORD=password
CALLBACK_URL=http://localhost:8002/mock/callback
BATCH_CONCURRENCY=2
LOG_LEVEL=DEBUG
```

### 2. 프로덕션 환경 설정 (.env.prod)

실제 서버 정보를 포함합니다. **이 파일은 Git에 추가하면 안됩니다.**

```bash
# 파일 내용 확인
cat .env.prod
```

`.env.prod` 예시:
```bash
APP_ENV=production
LLM_URL=http://vllm-server:8000
LLM_AUTH_HEADER=Bearer your-actual-token
SFTP_HOST=sftp.example.com
SFTP_USERNAME=prod_user
SFTP_PASSWORD=prod_password
CALLBACK_URL=http://callback-server:3000/callback
BATCH_CONCURRENCY=8
LOG_LEVEL=INFO
```

### 3. 환경변수 참고표

| 변수명 | 설명 | 기본값 | 보안 |
|--------|------|--------|------|
| `APP_ENV` | 애플리케이션 환경 | `development` | 공개 |
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

### 핵심: Build Time 설정 vs Runtime Override

이 프로젝트는 **보안**을 위해 두 단계로 환경변수를 관리합니다:

**1단계: Build Time (로컬에서)** 
- `.env.dev` 또는 `.env.prod`를 읽어 Docker 이미지에 embed
- `./build.sh` 사용 시 `--env dev` 또는 `--env prod` 옵션으로 지정

**2단계: Runtime (서버에서)**
- `docker run -e KEY=VALUE` 옵션으로 필요한 값만 override
- 더 높은 우선순위로 적용됨

예시:
```
Build Time:     .env.prod의 SFTP_PASSWORD=prod123 → 이미지에 embed
Runtime:        docker run -e SFTP_PASSWORD=override456 → 우선 적용
Result:         SFTP_PASSWORD=override456 사용
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

# 방법 1: 로컬에만 빌드 (테스트용)
./build.sh docker.io/your-username/stt-service latest --env dev

# 방법 2: 레지스트리에 푸시 (멀티 아키텍처)
./build.sh docker.io/your-username/stt-service latest --env dev --push
```

#### 프로덕션 환경으로 빌드

```bash
# 방법 1: 로컬에만 빌드
./build.sh docker.io/your-username/stt-service v1.0.0 --env prod

# 방법 2: 레지스트리에 푸시
./build.sh docker.io/your-username/stt-service v1.0.0 --env prod --push

# 방법 3: TAR 파일로 저장 (Linux 서버 전송용)
./build.sh docker.io/your-username/stt-service v1.0.0 --env prod --save
```

#### 빌드 스크립트 옵션

```
사용법: ./build.sh <repository> [tag] [--env dev|prod] [--push] [--save]

매개변수:
  <repository>    필수. Docker 레지스트리 주소 (docker.io/username/myapp)
  [tag]           선택. 이미지 태그, 기본값: latest
  [--env dev|prod] 선택. 빌드 환경 (dev=.env.dev, prod=.env.prod)
  [--push]        선택. 빌드 후 레지스트리에 푸시 (멀티 아키텍처 지원)
  [--save]        선택. 빌드 후 TAR 파일로 저장 (output/ 디렉토리)
```

#### 빌드 예제

```bash
# 개발 환경: .env.dev를 읽고 로컬 빌드
./build.sh docker.io/myusername/stt-service dev --env dev

# 프로덕션: .env.prod를 읽고 Docker Hub에 푸시
./build.sh docker.io/myusername/stt-service v1.2.3 --env prod --push

# GitHub Container Registry에 푸시
./build.sh ghcr.io/myusername/stt-service v1.0.0 --env prod --push

# TAR 파일로 저장하여 Linux 서버로 전송
./build.sh docker.io/myusername/stt-service latest --env prod --save
# 결과: output/docker.io-myusername-stt-service-latest.tar
```

### TAR 파일로 저장하여 서버에 전송

Linux 서버에 직접 배포할 때 사용합니다.

**1. 로컬에서 TAR 파일 생성**

```bash
./build.sh myregistry.com/stt-service v1.0.0 --env prod --save

# 결과 파일
# output/myregistry.com-stt-service-v1.0.0.tar (약 500MB)
```

**2. Linux 서버로 파일 전송**

```bash
scp output/myregistry.com-stt-service-v1.0.0.tar user@remote-server:/path/to/
```

**3. 서버에서 이미지 로드 및 실행**

```bash
# 이미지 로드
docker load -i myregistry.com-stt-service-v1.0.0.tar

# 환경변수 override로 실행 (더 높은 우선순위)
docker run -d --name stt-service \
  -e SFTP_PASSWORD=server-specific-password \
  -e CALLBACK_URL=http://server-callback:3000/result \
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

최소 요청 (나머지는 config.py에서):

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
    "template_name": "qwen_default",
    "question": "Summarize this text."
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

#### 5.5 Custom Prompt 사용 (인라인)

Template을 거치지 않고 커스텀 프롬프트를 직접 전달:

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "username": "user",
    "password": "pass",
    "remote_path": "/path/to/file.txt",
    "vllm_url": "http://vllm-api:8000/infer",
    "callback_url": "http://callback-handler:5000/process",
    "custom_prompt": "Translate to Spanish: Hello world"
  }'
```

#### 5.6 새 Template 생성

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

### 6. 동기 배치 처리 (날짜 범위로 파일 자동 발견)

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
    "template_name": "qwen_default",
    "question": "Summarize the contents",
    "concurrency": 4
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
    "template_name": "qwen_default",
    "concurrency": 4
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

