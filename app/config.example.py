"""
Configuration template for dev/prod environments.
Copy this file to config.py and modify with your actual settings.
config.py will NOT be committed to git.
"""

import os
from typing import Optional

class Config:
    """Base configuration"""
    
    # LLM Service Configuration (can be overridden by env vars)
    CALL_TYPE: str = os.getenv("CALL_TYPE", "vllm")  # "vllm" or "agent"
    LLM_URL: Optional[str] = os.getenv("LLM_URL")  # e.g., "http://localhost:8000"
    LLM_AUTH_HEADER: Optional[str] = os.getenv("LLM_AUTH_HEADER")  # e.g., "Bearer token"
    
    # vLLM specific
    MODEL_PATH: Optional[str] = os.getenv("MODEL_PATH")  # e.g., "qwen/qwen-7b-chat"
    
    # Agent specific
    AGENT_NAME: Optional[str] = os.getenv("AGENT_NAME")  # e.g., "my-agent"
    USE_STREAMING: bool = os.getenv("USE_STREAMING", "false").lower() == "true"
    
    # SFTP Configuration
    SFTP_HOST: Optional[str] = os.getenv("SFTP_HOST")
    SFTP_PORT: int = int(os.getenv("SFTP_PORT", "22"))
    SFTP_USERNAME: Optional[str] = os.getenv("SFTP_USERNAME")
    SFTP_PASSWORD: Optional[str] = os.getenv("SFTP_PASSWORD")
    SFTP_KEY: Optional[str] = os.getenv("SFTP_KEY")
    SFTP_CREDENTIAL_NAME: Optional[str] = os.getenv("SFTP_CREDENTIAL_NAME")
    
    # Default paths
    SFTP_ROOT_PATH: str = os.getenv("SFTP_ROOT_PATH", "/")
    
    # Callback Configuration
    CALLBACK_URL: Optional[str] = os.getenv("CALLBACK_URL")
    CALLBACK_AUTH_HEADER: Optional[str] = os.getenv("CALLBACK_AUTH_HEADER")
    
    # Template Configuration
    TEMPLATE_NAME: Optional[str] = os.getenv("TEMPLATE_NAME")  # e.g., "qwen_default"
    
    # Batch Processing
    BATCH_CONCURRENCY: int = int(os.getenv("BATCH_CONCURRENCY", "4"))


class DevelopmentConfig(Config):
    """Development configuration - suitable for local testing"""
    
    # Defaults for local testing
    CALL_TYPE = os.getenv("CALL_TYPE", "vllm")
    LLM_URL = os.getenv("LLM_URL", "http://localhost:8000")
    MODEL_PATH = os.getenv("MODEL_PATH", "qwen/qwen-7b-chat")
    AGENT_NAME = os.getenv("AGENT_NAME")
    
    # Mock endpoints for testing
    CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:8002/mock/callback")
    
    # Local SFTP (optional for testing)
    SFTP_HOST = os.getenv("SFTP_HOST")
    SFTP_USERNAME = os.getenv("SFTP_USERNAME", "demo")
    SFTP_PASSWORD = os.getenv("SFTP_PASSWORD", "password")
    
    BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "2"))


class ProductionConfig(Config):
    """Production configuration - stricter defaults"""
    
    # Production should have explicit configuration
    CALL_TYPE = os.getenv("CALL_TYPE", "vllm")
    LLM_URL = os.getenv("LLM_URL")  # REQUIRED
    MODEL_PATH = os.getenv("MODEL_PATH")  # REQUIRED for vllm
    AGENT_NAME = os.getenv("AGENT_NAME")  # REQUIRED for agent
    
    # SFTP configuration from env or credential_name
    SFTP_HOST = os.getenv("SFTP_HOST")
    SFTP_USERNAME = os.getenv("SFTP_USERNAME")
    SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
    SFTP_KEY = os.getenv("SFTP_KEY")
    SFTP_CREDENTIAL_NAME = os.getenv("SFTP_CREDENTIAL_NAME")
    
    # Callback is required in production
    CALLBACK_URL = os.getenv("CALLBACK_URL")
    
    BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "8"))


# Determine which config to use
ENV = os.getenv("APP_ENV", "development").lower()

if ENV == "production":
    config = ProductionConfig()
elif ENV == "development":
    config = DevelopmentConfig()
else:
    config = Config()
