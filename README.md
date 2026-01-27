# FastAPI + Paramiko + vLLM 배치 처리 시스템

이 프로젝트는 SFTP에서 텍스트 파일을 읽고, vLLM 모델을 호출한 뒤, 결과를 콜백 URL로 전송하는 기능을 제공합니다. 단일 파일 처리 및 병렬 배치 처리를 모두 지원합니다.

## 파일 구조

```
.
├── Dockerfile                 # Python 3.10.19-slim-trixie 기반 컨테이너 이미지
├── build.sh                   # Docker buildx를 사용한 멀티 아키텍처 빌드 스크립트
├── requirements.txt           # Python 종속성 (fastapi, uvicorn, paramiko, requests)
├── app/
│   ├── main.py               # FastAPI 애플리케이션 및 엔드포인트
│   └── sftp_client.py        # Paramiko 기반 SFTP 클라이언트
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

4. **Prompt Template 관리** (새로운 기능)
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

## 설정

### 로컬 설정 파일 (config.py)

이 프로젝트는 로컬 설정 파일 `app/config.py`를 지원합니다. 모든 파라미터를 API 요청에 넣을 필요 없이 설정 파일에 기본값을 저장할 수 있습니다.

1. **설정 파일 생성**

   `app/config.example.py`를 복사하여 `app/config.py`를 생성하세요:

   ```bash
   cp app/config.example.py app/config.py
   ```

2. **개발용 또는 프로덕션용 설정**

   `app/config.py`를 열어서 `DevelopmentConfig` 또는 `ProductionConfig`에 맞게 수정하세요:

   ```python
   # Development (기본값)
   class DevelopmentConfig(Config):
       LLM_URL = "http://localhost:8000"
       MODEL_PATH = "qwen/qwen-7b-chat"
       CALLBACK_URL = "http://localhost:8002/mock/callback"
       SFTP_HOST = "localhost"

### 설정 파일 예시

#### 개발용 설정 (config.dev.example.py)

```python
class DevelopmentConfig:
    CALL_TYPE = "vllm"
    LLM_URL = "http://localhost:8000"  # Mock 서버 사용 가능
    MODEL_PATH = "qwen/qwen-7b-chat"
    
    SFTP_HOST = "localhost"
    SFTP_USERNAME = "demo"
    SFTP_PASSWORD = "password"
    
    CALLBACK_URL = "http://localhost:8002/mock/callback"
    TEMPLATE_NAME = "qwen_default"
    BATCH_CONCURRENCY = 2

config = DevelopmentConfig()
```

#### 프로덕션용 설정 (config.prod.example.py)

```python
import os

class ProductionConfig:
    # 모든 설정이 환경변수에서 읽음
    CALL_TYPE = os.getenv("CALL_TYPE", "vllm")
    LLM_URL = os.getenv("LLM_URL")  # 필수
    MODEL_PATH = os.getenv("MODEL_PATH")  # 필수
    
    SFTP_HOST = os.getenv("SFTP_HOST")  # 필수
    SFTP_USERNAME = os.getenv("SFTP_USERNAME")
    SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
    SFTP_KEY = os.getenv("SFTP_KEY")  # 또는 Base64 인코딩된 키
    
    CALLBACK_URL = os.getenv("CALLBACK_URL")  # 필수
    BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "8"))

config = ProductionConfig()
```

실제 설정 파일 생성:

```bash
# 개발용
cp app/config.dev.example.py app/config.py
# 프로덕션용
cp app/config.prod.example.py app/config.py
```

또는 `app/config.example.py`에서 원하는 부분만 복사:

```bash
cp app/config.example.py app/config.py
vi app/config.py  # 수정
```

### 환경변수

모든 설정은 환경변수로도 제어할 수 있습니다 (우선순위: 환경변수 > config.py):

```bash
# LLM 설정
export CALL_TYPE=vllm                           # "vllm" 또는 "agent"
export LLM_URL=http://vllm-server:8000
export LLM_AUTH_HEADER="Bearer token"
export MODEL_PATH=qwen/qwen-7b-chat             # vLLM 사용 시
export AGENT_NAME=my-agent                      # Agent 사용 시
export USE_STREAMING=false

# SFTP 설정
export SFTP_HOST=sftp.example.com
export SFTP_PORT=22
export SFTP_USERNAME=user
export SFTP_PASSWORD=password
export SFTP_KEY=/path/to/id_rsa                 # 또는 Base64 인코딩된 키
export SFTP_ROOT_PATH=/

# 콜백 설정
export CALLBACK_URL=http://callback-server:3000/callback
export CALLBACK_AUTH_HEADER="Bearer callback-token"

# 처리 설정
export TEMPLATE_NAME=qwen_default
export BATCH_CONCURRENCY=4
export APP_ENV=development                      # "development" 또는 "production"
```

### Docker 환경에서 환경변수 사용

```bash
docker run -d \
  -e APP_ENV=production \
  -e CALL_TYPE=vllm \
  -e LLM_URL=http://vllm-server:8000 \
  -e MODEL_PATH=qwen/qwen-7b-chat \
  -e SFTP_HOST=sftp.example.com \
  -e SFTP_USERNAME=user \
  -e SFTP_PASSWORD=password \
  -e CALLBACK_URL=http://callback-server:3000/callback \
  -e BATCH_CONCURRENCY=8 \
  -p 8002:8002 \
  stt-fastapi-sftp
```

또는 `.env` 파일로:

```bash
# .env (Git에 저장되지 않음)
APP_ENV=production
CALL_TYPE=vllm
LLM_URL=http://vllm-server:8000
MODEL_PATH=qwen/qwen-7b-chat
SFTP_HOST=sftp.example.com
SFTP_USERNAME=user
SFTP_PASSWORD=password
CALLBACK_URL=http://callback-server:3000/callback

# 실행
docker run --env-file .env -p 8002:8002 stt-fastapi-sftp
```

## 빌드 및 실행

### Docker 빌드

```bash
docker build -t stt-fastapi-sftp /Users/a113211/workspace/stt_incompleted
```

### 컨테이너 실행

```bash
docker run --rm -d --name stt_fastapi_sftp -p 8002:8002 stt-fastapi-sftp
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

### 5. 환경변수를 통한 SFTP 자격증명 사용

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

### 6. Prompt Template 사용

#### 6.1 사용 가능한 템플릿 목록

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

#### 6.2 특정 템플릿 조회

```bash
curl http://localhost:8002/templates/qwen_default
```

#### 6.3 Template을 사용한 처리 (Qwen)

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

#### 6.4 Template 없이 Raw Text 사용

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

이 경우 vLLM에 전달되는 입력값:
```json
{
  "input": "file.txt의 전체 내용"
}
```

#### 6.5 Custom Prompt 사용 (인라인)

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

#### 6.6 새 Template 생성

```bash
curl -X POST http://localhost:8002/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_custom_template",
    "content": "Analyze the following:\n\nData: {text}\n\nTask: {question}\n\nResult:"
  }'
```

#### 6.7 Template 삭제

```bash
curl -X DELETE http://localhost:8002/templates/my_custom_template
```

#### 6.8 Template 새로고침 (디스크에서 다시 로드)

```bash
curl -X POST http://localhost:8002/templates/refresh
```

### 7. 동기 배치 처리 (날짜 범위로 파일 자동 발견)

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
    },
    ...
  ],
  "total": 10
}
```

### 6. 비동기 배치 처리 (job_id 반환)

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
    },
    {
      "index": 1,
      "date": "20260120",
      "filename": "file2.txt",
      "success": true,
      "result": {
        "status": "ok",
        "model_output": {"summary": "...", "tokens": 456},
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
    ├── qwen_default.txt
    ├── gpt4mini_default.txt
    └── generic.txt
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

## Docker 빌드 및 배포

### 빌드 스크립트 사용 (권장)

이 프로젝트는 `build.sh` 스크립트를 제공합니다. 이 스크립트는 Docker buildx를 사용하여 `linux/amd64`와 `linux/arm64` 아키텍처 모두를 지원하는 이미지를 빌드합니다.

#### 사전 요구사항

```bash
# Docker buildx가 설치되어 있어야 합니다
docker buildx version

# 필요한 경우 qemu 설정
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
```

#### 사용 방법

**1. 로컬에서만 빌드 (--load, 단일 아키텍처로 제한)**
```bash
chmod +x build.sh
./build.sh docker.io/your-username/stt-service latest
```

**2. 레지스트리에 직접 푸시 (권장, 멀티 아키텍처 지원)**
```bash
./build.sh docker.io/your-username/stt-service latest --push
```

**3. 커스텀 태그로 빌드 및 푸시**
```bash
./build.sh ghcr.io/your-username/stt-service v1.0.0 --push
```

#### 스크립트 옵션

- `repository` (필수): Docker 레지스트리 주소 (예: `docker.io/username/myapp`)
- `tag` (선택): 이미지 태그, 기본값은 `latest`
- `--push`: 빌드 완료 후 레지스트리에 푸시

#### 예제

```bash
# Docker Hub에 푸시
./build.sh docker.io/myusername/stt-service latest --push

# GitHub Container Registry에 푸시
./build.sh ghcr.io/myusername/stt-service v1.0.0 --push

# 특정 버전으로 빌드 및 푸시
./build.sh registry.example.com/myapp/stt-service 2026-01-27 --push
```

### 수동 빌드 (빌드 스크립트 미사용)

#### 멀티 아키텍처 빌드

```bash
# builder 생성 (최초 1회)
docker buildx create --name multiarch-builder --use

# 빌드 및 푸시
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t docker.io/your-username/stt-service:latest \
  --push \
  .
```

#### 로컬 빌드 (단일 아키텍처)

```bash
docker build -t stt-service:latest .
```

### 이미지 실행

```bash
# 기본 실행
docker run -p 8002:8002 docker.io/your-username/stt-service:latest

# 환경변수와 함께 실행
docker run -p 8002:8002 \
  -e SFTP_USERNAME=your-user \
  -e SFTP_PASSWORD=your-pass \
  docker.io/your-username/stt-service:latest
```

## 라이선스 및 참고

- FastAPI: https://fastapi.tiangolo.com/
- Paramiko: https://www.paramiko.org/
- Requests: https://requests.readthedocs.io/

