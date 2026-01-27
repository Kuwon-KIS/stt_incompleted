"""
Production Configuration Example
프로덕션용 설정 예시입니다.
이 파일을 참고하여 app/config.py를 작성하세요.
"""

import os
from typing import Optional

class ProductionConfig:
    """Production configuration - all values from environment variables"""
    
    # LLM Service Configuration (환경변수에서 읽음)
    CALL_TYPE = os.getenv("CALL_TYPE", "vllm")
    LLM_URL = os.getenv("LLM_URL")  # 반드시 설정 필요
    LLM_AUTH_HEADER = os.getenv("LLM_AUTH_HEADER")  # 필요시 설정
    
    # vLLM specific
    MODEL_PATH = os.getenv("MODEL_PATH")  # vLLM 사용 시 반드시 설정
    
    # Agent specific
    AGENT_NAME = os.getenv("AGENT_NAME")  # Agent 사용 시 반드시 설정
    USE_STREAMING = os.getenv("USE_STREAMING", "false").lower() == "true"
    
    # SFTP Configuration (환경변수에서 읽음)
    SFTP_HOST = os.getenv("SFTP_HOST")
    SFTP_PORT = int(os.getenv("SFTP_PORT", "22"))
    SFTP_USERNAME = os.getenv("SFTP_USERNAME")
    SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
    SFTP_KEY = os.getenv("SFTP_KEY")  # SSH 키 파일 경로 또는 Base64 인코딩된 키
    SFTP_CREDENTIAL_NAME = os.getenv("SFTP_CREDENTIAL_NAME")
    
    # Default paths
    SFTP_ROOT_PATH = os.getenv("SFTP_ROOT_PATH", "/")
    
    # Callback Configuration
    CALLBACK_URL = os.getenv("CALLBACK_URL")  # 반드시 설정 필요
    CALLBACK_AUTH_HEADER = os.getenv("CALLBACK_AUTH_HEADER")
    
    # Template Configuration
    TEMPLATE_NAME = os.getenv("TEMPLATE_NAME")
    
    # Batch Processing
    BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "8"))


# 이것을 app/config.py로 복사해서 사용하세요.
config = ProductionConfig()
