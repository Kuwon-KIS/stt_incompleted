# Dev 환경 테스트 가이드: SFTP + Mock Agent API

## 개요
- **SFTP**: Build 서버에 연결 (실제 파일)
- **Agent**: Mock API (로컬 localhost:8002)
- **목적**: Dev 환경에서 통합 테스트

## 환경 설정

### 로컬 Mock Agent API 사용 방법

`.env.dev` 파일의 `AGENT_URL` 수정:
```bash
# 변경 전 (실제 Agent 서버)
AGENT_URL=https://agent-dev.internal:9000/v1/analyze

# 변경 후 (로컬 Mock API 사용)
AGENT_URL=http://localhost:8002/mock/agent
```

그 후 app 실행:
```bash
APP_ENV=dev python -m uvicorn app.main:app --host 127.0.0.1 --port 8002
```

## API 입/출력 형식

### 1. Mock Agent API

**엔드포인트**
```
POST http://localhost:8002/mock/agent/{agent_name}/messages
```

**요청 (Input)**
```json
{
  "parameters": {
    "user_query": "이 통화 기록에서 미흡한 점을 분석해주세요",
    "context": "고객과의 통화 기록\n시간: 2026-03-16\n상담사: 홍길동\n..."
  },
  "use_streaming": false
}
```

**응답 (Output)**
```json
{
  "result": "{\"message_id\": \"msg_xxx\", \"chat_thread_id\": \"thread_xxx\", \"answer\": {\"answer\": {\"category\": \"사후판매\", \"summary\": \"...\", \"omission_num\": \"2\", \"omission_steps\": [...], \"omission_reasons\": [...]}}}",
  "status": "success",
  "processing_time_ms": 150
}
```

**Result 필드 상세 구조**
```json
{
  "message_id": "msg_3c23cc7f",
  "chat_thread_id": "thread_f7ed35e6",
  "answer": {
    "answer": {
      "category": "사후판매",
      "summary": "고객 상담 요약",
      "omission_num": "2",
      "omission_steps": [
        "투자자정보 확인",
        "설명서 필수 사항 설명"
      ],
      "omission_reasons": [
        "투자자정보를 파악하는 구간이 명확하지 않습니다.",
        "금융투자상품의 내용 및 구조를 상세하게 설명하는 구간이 없습니다."
      ]
    }
  }
}
```

## 테스트 방법

### 방법 1: curl을 사용한 직접 테스트

```bash
# Mock Agent API 테스트
curl -X POST http://localhost:8002/mock/agent/dev-test-agent/messages \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "user_query": "이 텍스트에서 미흡한 점을 찾아주세요",
      "context": "고객과의 통화 내용"
    },
    "use_streaming": false
  }' | python3 -m json.tool
```

### 방법 2: Python 스크립트로 테스트

```python
import requests
import json

# Mock Agent API 호출
response = requests.post(
    "http://localhost:8002/mock/agent/dev-test-agent/messages",
    json={
        "parameters": {
            "user_query": "미흡한 점 분석",
            "context": "고객 상담문"
        },
        "use_streaming": False
    }
)

# 응답 확인
result_data = response.json()
print(json.dumps(result_data, ensure_ascii=False, indent=2))

# Result 필드 파싱
result_str = result_data['result']
agent_response = json.loads(result_str)
print(f"Category: {agent_response['answer']['answer']['category']}")
print(f"Omissions: {agent_response['answer']['answer']['omission_num']}")
```

### 방법 3: 프로세싱 엔드포인트로 통합 테스트

```bash
# 1. 로컬 환경에서 서버 실행 (AGENT_URL을 localhost로 변경한 후)
APP_ENV=dev python -m uvicorn app.main:app --host 127.0.0.1 --port 8002

# 2. 단일 파일 처리 (inline_text로 테스트)
curl -X POST http://localhost:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "inline_text": "고객과의 통화 기록\n시간: 2026-03-16\n상담사: 홍길동\n내용: 상품 설명",
    "callback_url": "http://localhost:8002/mock/callback"
  }' | python3 -m json.tool
```

## 테스트 설정 옵션

Dev 환경에서 다양한 조합으로 테스트할 수 있습니다:

| 구성 | SFTP | Agent | 사용 시나리오 |
|------|------|-------|------------|
| `.env.dev` (기본) | Build 서버 | 실제 Agent | 완전 통합 테스트 (실제 환경) |
| `.env.dev` + localhost | Build 서버 | Mock API (localhost) | SFTP는 실제, Agent 개발/테스트 |
| `.env.local` | Mock | Mock API | 로컬 완전 단독 테스트 |

**Mock Agent API를 사용하려면**: `.env.dev` 파일에서 `AGENT_URL=http://localhost:8002/mock/agent` 로 설정

## Mock Agent API 응답 형식 검증 체크리스트

✅ **필수 필드**
- ✓ `result`: JSON string (문자열로 된 JSON)
- ✓ `status`: "success"
- ✓ `processing_time_ms`: 숫자

✅ **Result 내부 구조 (파싱 후)**
- ✓ `message_id`: 메시지 ID
- ✓ `chat_thread_id`: 대화 스레드 ID
- ✓ `answer.answer.category`: 상담 카테고리
- ✓ `answer.answer.summary`: 상담 요약
- ✓ `answer.answer.omission_num`: 미흡 사항 개수 (문자열)
- ✓ `answer.answer.omission_steps`: 미흡 단계 배열
- ✓ `answer.answer.omission_reasons`: 미흡 사유 배열 (개수 일치)

## 디버깅 팁

### 1. Agent API 호출 로그 확인
```bash
# 서버 시작 시 DEBUG 로그 활성화
LOG_LEVEL=DEBUG APP_ENV=dev-with-mocks python -m uvicorn app.main:app --log-level debug
```

### 2. Mock API 반응 시간
- Mock API는 즉시 응답 (150ms)
- 실제 Agent API는 더 오래 걸릴 수 있음

### 3. SFTP 연결 테스트
```python
from app.sftp_client import create_sftp_client

client = create_sftp_client(
    host="sftp-dev.internal",
    port=22,
    username="app_dev"
)
# SFTP 연결 테스트...
client.close()
```

## 주의사항

⚠️ **Dev-with-mocks 환경의 한계**
- Agent 응답은 고정된 샘플 데이터
- 실제 SFTP 파일 내용에 따라 다른 분석 결과를 받을 수 없음
- 실제 Agent 서버 연결 테스트는 `.env.dev` 사용

⚠️ **프로덕션 배포**
- 배포 시에는 반드시 `.env.prod` 사용
- Mock API는 배포 환경에서 사용하지 않을 것

## 참고: 기존 Mock 엔드포인트

다음 Mock 엔드포인트들도 사용 가능합니다:

- `/mock/callback`: 콜백 결과 수신 (POST)
- `/mock/vllm`: vLLM 대체 (POST)  
- `/process/batch/test`: 배치 처리 테스트
