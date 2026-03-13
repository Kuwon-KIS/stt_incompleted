"""
Configuration management for STT processing system.
Loads environment variables from .env files and provides centralized config.
"""

import os
import pathlib
from dotenv import load_dotenv


def load_env():
    """Load environment variables from .env file based on APP_ENV."""
    env_file = pathlib.Path(__file__).parent.parent / ".env"
    
    if env_file.exists():
        load_dotenv(env_file)
    else:
        # Fall back to environment-specific .env file
        app_env = os.getenv("APP_ENV", "dev")
        env_file_map = {
            "prod": ".env.prod",
            "local": ".env.local",
            "dev": ".env.dev",
        }
        env_filename = env_file_map.get(app_env, ".env.dev")
        env_file = pathlib.Path(__file__).parent.parent / env_filename
        
        if env_file.exists():
            load_dotenv(env_file)


# Load environment variables on module import
load_env()


class Config:
    """Central configuration class for the application."""
    
    # Application settings
    APP_ENV = os.getenv("APP_ENV", "dev")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
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
    AGENT_NAME = os.getenv("AGENT_NAME")
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
