#!/usr/bin/env python3
"""
Mock Agent API 형식 검증 스크립트
"""
import json
import sys

# Mock agent API의 result 필드 (실제 응답)
result_str = r'{"message_id": "msg_3c23cc7f", "chat_thread_id": "thread_f7ed35e6", "answer": {"answer": {"category": "사후판매", "summary": "김철수 고객님에게 IMA 투자신탁 상품을 판매하는 내용입니다. 투자 성향과 위험도를 확인하고 상품 설명을 진행했습니다.", "omission_num": "2", "omission_steps": ["투자자정보 확인", "설명서 필수 사항 설명"], "omission_reasons": ["투자자정보를 파악하는 구간이 명확하지 않습니다.", "금융투자상품의 내용 및 구조를 상세하게 설명하는 구간이 없습니다."]}}}'

print("=" * 60)
print("Mock Agent API 응답 형식 검증")
print("=" * 60)

try:
    data = json.loads(result_str)
    
    print("\n✅ 1. 최상위 필드:")
    print(f"   - message_id: {data['message_id']}")
    print(f"   - chat_thread_id: {data['chat_thread_id']}")
    
    print("\n✅ 2. answer.answer 내부 구조:")
    answer_data = data['answer']['answer']
    print(f"   - category: {answer_data['category']}")
    print(f"   - summary: {answer_data['summary'][:40]}...")
    print(f"   - omission_num: {answer_data['omission_num']} (type: {type(answer_data['omission_num']).__name__})")
    
    print("\n✅ 3. 미흡 사항 (omission_steps + omission_reasons):")
    steps = answer_data['omission_steps']
    reasons = answer_data['omission_reasons']
    
    for i, (step, reason) in enumerate(zip(steps, reasons), 1):
        print(f"\n   [{i}] {step}")
        print(f"       → {reason}")
    
    print("\n" + "=" * 60)
    print("형식 검증 결과")
    print("=" * 60)
    
    checks = [
        ("필드 이름 정확", 
         all(k in answer_data for k in ['category', 'summary', 'omission_num', 'omission_steps', 'omission_reasons'])),
        ("omission_num 타입 (str)", isinstance(answer_data['omission_num'], str)),
        ("omission_steps/reasons 개수 일치", len(steps) == len(reasons)),
        ("omission_num과 배열 개수 일치", int(answer_data['omission_num']) == len(steps)),
    ]
    
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"   {status} {check_name}")
    
    all_passed = all(result for _, result in checks)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ 모든 검증 통과! API 형식이 올바릅니다.")
    else:
        print("❌ 일부 검증 실패")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ 오류: {e}")
    sys.exit(1)
