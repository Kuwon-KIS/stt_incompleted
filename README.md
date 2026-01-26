# FastAPI + Paramiko + vLLM 배치 처리 시스템

이 프로젝트는 SFTP에서 텍스트 파일을 읽고, vLLM 모델을 호출한 뒤, 결과를 콜백 URL로 전송하는 기능을 제공합니다. 단일 파일 처리 및 병렬 배치 처리를 모두 지원합니다.

## 파일 구조

```
.
├── Dockerfile                 # Python 3.10.19-slim-trixie 기반 컨테이너 이미지
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

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "port": 22,
    "username": "user",
    "password": "pass",
    "remote_path": "/path/to/file.txt",
    "vllm_url": "http://localhost:8002/mock/vllm",
    "callback_url": "http://localhost:8002/mock/callback",
    "inline_text": "hello world"
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

#### 6.4 Template을 사용한 처리 (GPT-4-mini)

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.example.com",
    "username": "user",
    "password": "pass",
    "remote_path": "/path/to/file.txt",
    "vllm_url": "http://gpt4mini-api:8000/infer",
    "callback_url": "http://callback-handler:5000/process",
    "inline_text": "Machine learning is a subset of artificial intelligence.",
    "template_name": "gpt4mini_default",
    "question": "Explain what ML is."
  }'
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
    "inline_text": "Hello world",
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

### 7. 동기 배치 처리 (한 번에 결과 반환)

```bash
curl -X POST http://localhost:8002/process/batch \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "host": "sftp.example.com",
        "username": "user",
        "password": "pass",
        "remote_path": "/file1.txt",
        "vllm_url": "http://localhost:8002/mock/vllm",
        "callback_url": "http://localhost:8002/mock/callback",
        "inline_text": "item 1"
      },
      {
        "host": "sftp.example.com",
        "username": "user",
        "password": "pass",
        "remote_path": "/file2.txt",
        "vllm_url": "http://localhost:8002/mock/vllm",
        "callback_url": "http://localhost:8002/mock/callback",
        "inline_text": "item 2"
      }
    ],
    "concurrency": 2
  }'
```

응답:
```json
{
  "results": [
    {
      "index": 0,
      "success": true,
      "result": {
        "status": "ok",
        "model_output": {"summary": "item 1", "tokens": 2},
        "callback_status": 200
      }
    },
    {
      "index": 1,
      "success": true,
      "result": {
        "status": "ok",
        "model_output": {"summary": "item 2", "tokens": 2},
        "callback_status": 200
      }
    }
  ]
}
```

### 6. 비동기 배치 처리 (job_id 반환)

작업 제출:
```bash
curl -X POST http://localhost:8002/process/batch/submit \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "host": "sftp.example.com",
        "username": "user",
        "password": "pass",
        "remote_path": "/file1.txt",
        "vllm_url": "http://vllm-api:8000/infer",
        "callback_url": "http://callback-handler:5000/process",
        "inline_text": "processing item 1"
      }
    ],
    "concurrency": 2
  }'
```

응답:
```json
{"job_id": "f8743538-6b32-401a-85fe-6f68b7387add", "status": "submitted"}
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
  "results": [
    {
      "index": 0,
      "success": true,
      "result": {
        "status": "ok",
        "model_output": {
          "summary": "processing item 1",
          "tokens": 3
        },
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

## 예제: GPT-4-mini 모델 사용

```bash
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp.your-server.com",
    "username": "sftp_user",
    "password": "sftp_pass",
    "remote_path": "/documents/research.txt",
    "vllm_url": "http://gpt4mini-server:8000/v1/chat/completions",
    "vllm_auth_header": "Bearer gpt-token",
    "callback_url": "http://your-backend:5000/results",
    "template_name": "gpt4mini_default",
    "question": "What are the main research findings?"
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

