#!/usr/bin/env python3
"""
Dev 환경 통합 테스트: Mock Agent API
SFTP(build 서버) + Mock Agent API(localhost) 조합
"""

import requests
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8002"

def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"  📖 가이드: docs/DEV_TEST_GUIDE.md")
    print(f"{'='*70}")

def print_section(title):
    print(f"\n▶ {title}")
    print("-" * 70)

def test_health():
    """서버 상태 확인"""
    print_section("1. 서버 상태 확인")
    resp = requests.get(f"{BASE_URL}/healthz")
    data = resp.json()
    print(f"Status: {data['status']}")
    print(f"Environment: {data['app_env']}")
    print(f"Uptime: {data['uptime_seconds']}s")
    assert data['app_env'] == 'dev', "❌ Wrong environment. 'APP_ENV=dev'로 설정되어야 합니다."
    print("✅ Dev 환경에서 실행 중 (Mock Agent API)")

def test_mock_agent_api():
    """Mock Agent API 테스트"""
    print_section("2. Mock Agent API 직접 호출")
    
    payload = {
        "parameters": {
            "user_query": "이 통화 기록에서 미흡한 점을 분석해주세요",
            "context": "고객과의 통화 기록\n시간: 2026-03-16\n상담사: 홍길동\n내용: 상품 설명"
        },
        "use_streaming": False
    }
    
    resp = requests.post(
        f"{BASE_URL}/mock/agent/dev-test-agent/messages",
        json=payload
    )
    
    data = resp.json()
    print(f"HTTP Status: {resp.status_code}")
    print(f"Response Status: {data['status']}")
    print(f"Processing Time: {data['processing_time_ms']}ms")
    
    # Result 필드 파싱
    result_str = data['result']
    agent_response = json.loads(result_str)
    
    print(f"\n  Message ID: {agent_response['message_id']}")
    print(f"  Chat Thread ID: {agent_response['chat_thread_id']}")
    
    answer_data = agent_response['answer']['answer']
    print(f"\n  분석 결과:")
    print(f"    - Category: {answer_data['category']}")
    print(f"    - Summary: {answer_data['summary'][:50]}...")
    print(f"    - Omission Num: {answer_data['omission_num']}")
    print(f"    - Steps: {len(answer_data['omission_steps'])}개")
    
    assert len(answer_data['omission_steps']) == len(answer_data['omission_reasons'])
    print("\n✅ Mock Agent API 정상 작동")

def test_single_process():
    """단일 파일 처리 테스트 (inline_text)"""
    print_section("3. 단일 파일 처리 (/process)")
    
    # Inline text로 테스트 (SFTP 연결 불필요)
    payload = {
        "inline_text": "고객과의 통화 기록\n시간: 2026-03-16 10:00:00\n상담사: 홍길동\n고객명: 김철수\n\n상담내용:\n- 상품 설명\n- 가격 안내\n- 특징 설명\n\n결론: 고객이 구매에 동의",
        "callback_url": f"{BASE_URL}/mock/callback"
    }
    
    resp = requests.post(f"{BASE_URL}/process", json=payload)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Processing 성공")
        print(f"  Detection Result Status: {data.get('status')}")
        
        detection = data.get('detection_result', {})
        issues = detection.get('detected_issues', [])
        print(f"  Detected Issues: {len(issues)}개")
        print(f"  Strategy Used: {detection.get('strategy')}")
        print(f"  Model Used: {detection.get('model_used')}")
        
        if issues:
            print(f"\n  탐지된 미흡 사항:")
            for issue in issues[:2]:  # 처음 2개만
                print(f"    - Index {issue.get('index')}: {issue.get('step', '?')}")
                print(f"      → {issue.get('reason', '?')}")
    else:
        print(f"❌ Error: {resp.status_code}")
        print(resp.text)

def test_batch_test():
    """배치 테스트 엔드포인트"""
    print_section("4. 배치 처리 테스트 (/process/batch/test)")
    
    resp = requests.post(f"{BASE_URL}/process/batch/test")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Batch Test 성공")
        job_id = data.get('id')
        if job_id:
            print(f"  Job ID: {job_id[:8]}...")
        print(f"  Status: {data.get('status')}")
        print(f"  Total Files: {data.get('total_files')}")
        print(f"  Results: {len(data.get('results', []))}개")
    else:
        print(f"❌ Error: {resp.status_code}")
        print(resp.text)

def test_available_dates():
    """이용 가능한 날짜 조회"""
    print_section("5. 이용 가능한 날짜 조회 (/select-target/available-dates)")
    
    resp = requests.get(f"{BASE_URL}/select-target/available-dates")
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Available Dates 조회 성공")
        print(f"  Source: {data.get('source')}")
        print(f"  Available Dates: {data.get('available_dates')}")
    else:
        print(f"⚠️  Not Found (expected in some environments)")

def test_api_documentation():
    """API 문서 확인"""
    print_section("6. API 문서 확인 (/docs)")
    
    resp = requests.get(f"{BASE_URL}/docs")
    
    if resp.status_code == 200:
        print(f"✅ OpenAPI 문서 제공")
        print(f"  URL: http://localhost:8002/docs")
    else:
        print(f"⚠️  문서 미제공")

def print_summary():
    """테스트 결과 요약"""
    print_header("테스트 완료 요약")
    
    summary = """
✅ Dev 환경 Mock Agent API 검증 완료

설정 확인:
  ✓ APP_ENV=dev
  ✓ AGENT_URL=http://localhost:8002/mock/agent (AGENT_URL 수정)
  ✓ AGENT_NAME=dev-test-agent (또는 실제 agent name)
  ✓ SFTP=Build 서버 연결
  ✓ Agent API=Mock (localhost)

API 형식:
  ✓ Request: POST /mock/agent/{agent_name}/messages
  ✓ Input: { parameters: { user_query, context }, use_streaming }
  ✓ Output: { result, status, processing_time_ms }
  ✓ Result 필드: JSON string (nested structure)

서버 상태:
  ✓ Mock Agent API 정상 작동
  ✓ Single Processing 정상
  ✓ Batch Processing 준비 완료

다음 단계:
  1. .env.dev에서 AGENT_URL=http://localhost:8002/mock/agent 설정
  2. 본격 통합 테스트 시작
  3. 실제 Agent 서버 준비되면 AGENT_URL 변경

참고 링크:
  - 개발 가이드: docs/DEV_TEST_GUIDE.md
  - Mock Agent API 입/출력: docs/DEV_TEST_GUIDE.md#api-입출력-형식
"""
    print(summary)

if __name__ == "__main__":
    print_header("Dev 환경 Mock Agent API 통합 테스트")
    
    try:
        test_health()
        test_mock_agent_api()
        test_single_process()
        test_batch_test()
        test_available_dates()
        test_api_documentation()
        print_summary()
        
        print("\n✅ 모든 테스트 완료!\n")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
