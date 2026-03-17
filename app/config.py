"""
Configuration management for STT processing system.
Loads environment variables from .env files and provides centralized config.
"""

import os
import pathlib
from dotenv import load_dotenv


def load_env():
    """
    Load environment variables from APP_ENV-specific .env file.
    
    Priority:
    1. environments/.env.${APP_ENV} (e.g., environments/.env.prod)
    2. /app/.env (fallback for backward compatibility)
    3. No .env file (uses system environment variables only)
    
    APP_ENV can be:
    - Set at build time: --build-arg ENV=dev
    - Set at runtime: -e APP_ENV=prod
    - Default: dev
    """
    app_env = os.getenv("APP_ENV", "dev")
    
    # Environment-specific .env file path
    env_file = pathlib.Path(__file__).parent.parent / f"environments/.env.{app_env}"
    
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Fallback to root .env if environments/ doesn't exist
        fallback_env = pathlib.Path(__file__).parent.parent / ".env"
        if fallback_env.exists():
            load_dotenv(fallback_env)


# Load environment variables on module import
load_env()


class Config:
    """Central configuration class for the application."""
    
    # Application settings
    APP_ENV = os.getenv("APP_ENV", "dev")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"  # Mock fallback for SFTP errors
    
    # SFTP settings
    SFTP_HOST = os.getenv("SFTP_HOST")
    SFTP_PORT = int(os.getenv("SFTP_PORT", "22"))
    SFTP_USERNAME = os.getenv("SFTP_USERNAME")
    SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
    SFTP_KEY = os.getenv("SFTP_KEY")
    SFTP_CREDENTIAL_NAME = os.getenv("SFTP_CREDENTIAL_NAME")
    SFTP_ROOT_PATH = os.getenv("SFTP_ROOT_PATH", "/")
    
    # LLM settings
    CALL_TYPE = os.getenv("CALL_TYPE", "vllm")
    LLM_URL = os.getenv("LLM_URL")
    LLM_AUTH_HEADER = os.getenv("LLM_AUTH_HEADER")
    MODEL_PATH = os.getenv("MODEL_PATH")
    
    # Agent settings (separate from LLM)
    AGENT_URL = os.getenv("AGENT_URL")
    AGENT_NAME = os.getenv("AGENT_NAME")
    AGENT_AUTH_HEADER = os.getenv("AGENT_AUTH_HEADER")
    
    USE_STREAMING = os.getenv("USE_STREAMING", "false").lower() == "true"
    
    # Callback settings
    CALLBACK_URL = os.getenv("CALLBACK_URL")
    CALLBACK_AUTH_HEADER = os.getenv("CALLBACK_AUTH_HEADER")
    
    # Template settings
    TEMPLATE_NAME = os.getenv("TEMPLATE_NAME", "qwen_default")
    TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"
    
    # Batch processing settings
    BATCH_CONCURRENCY = int(os.getenv("BATCH_CONCURRENCY", "4"))
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration settings."""
        if cls.APP_ENV == "prod":
            # Production requires more strict validation
            required = ["SFTP_HOST", "LLM_URL", "CALLBACK_URL"]
            for key in required:
                if not getattr(cls, key, None):
                    raise ValueError(f"Required config {key} is not set for production")
        return True


config = Config()
