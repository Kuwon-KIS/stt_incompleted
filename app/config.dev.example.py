"""
Development Configuration Example
로컬 개발용 설정 예시입니다.
이 파일을 참고하여 app/config.py를 작성하세요.
"""

import os
from typing import Optional

class DevelopmentConfig:
    """Development configuration - suitable for local testing"""
    
    # LLM Service Configuration
    CALL_TYPE = "vllm"  # Mock 엔드포인트 사용 시
    LLM_URL = "http://localhost:8000"  # 또는 "http://localhost:8002/mock/vllm"
    LLM_AUTH_HEADER = None  # 테스트용이므로 인증 없음
    
    # vLLM specific
    MODEL_PATH = "qwen/qwen-7b-chat"
    
    # Agent specific (vLLM을 사용하지 않을 경우)
    AGENT_NAME = None
    USE_STREAMING = False
    
    # SFTP Configuration
    SFTP_HOST = "localhost"  # 또는 실제 SFTP 서버
    SFTP_PORT = 22
    SFTP_USERNAME = "demo"
    SFTP_PASSWORD = "password"
    SFTP_KEY = None  # 키 파일 경로 또는 Base64 인코딩된 키
    SFTP_CREDENTIAL_NAME = None
    
    # Default paths
    SFTP_ROOT_PATH = "/"
    
    # Callback Configuration
    CALLBACK_URL = "http://localhost:8002/mock/callback"  # Mock 콜백 사용
    CALLBACK_AUTH_HEADER = None
    
    # Template Configuration
    TEMPLATE_NAME = "qwen_default"
    
    # Batch Processing
    BATCH_CONCURRENCY = 2  # 개발용이므로 낮게 설정


# 이것을 app/config.py로 복사하고 수정해서 사용하세요.
config = DevelopmentConfig()
