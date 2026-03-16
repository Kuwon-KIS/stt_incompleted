"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List


# ============= SFTP Models =============

class SFTPRequest(BaseModel):
    host: str
    port: int = 22
    username: str
    password: str | None = None
    key: str | None = None
    path: str = "."


# ============= Process Models =============

class ProcessRequest(BaseModel):
    """Request model for single file processing."""
    
    # SFTP target file
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    key: str | None = None
    credential_name: str | None = None
    remote_path: str | None = None
    
    # LLM call configuration
    call_type: str | None = None
    llm_url: str | None = None
    llm_auth_header: str | None = None
    
    # vLLM specific
    model_path: str | None = None
    
    # Agent specific
    agent_name: str | None = None
    use_streaming: bool | None = None
    
    # Callback settings
    callback_url: str | None = None
    callback_auth_header: str | None = None
    
    # Optional inline text for testing
    inline_text: str | None = None
    
    # Template and prompt configuration
    template_name: str | None = None
    question: str | None = None
    custom_prompt: str | None = None
    
    def resolve_config(self, config):
        """Resolve all None values from config defaults."""
        # SFTP settings
        if self.host is None:
            self.host = config.SFTP_HOST
        if self.port is None:
            self.port = config.SFTP_PORT
        if self.username is None:
            self.username = config.SFTP_USERNAME
        if self.password is None:
            self.password = config.SFTP_PASSWORD
        if self.key is None:
            self.key = config.SFTP_KEY
        if self.credential_name is None:
            self.credential_name = config.SFTP_CREDENTIAL_NAME
        
        # LLM settings
        if self.call_type is None:
            self.call_type = config.CALL_TYPE
        if self.llm_url is None:
            self.llm_url = config.LLM_URL
        if self.llm_auth_header is None:
            self.llm_auth_header = config.LLM_AUTH_HEADER
        
        # vLLM specific
        if self.model_path is None:
            self.model_path = config.MODEL_PATH
        
        # Agent specific
        if self.agent_name is None:
            self.agent_name = config.AGENT_NAME
        if self.use_streaming is None:
            self.use_streaming = config.USE_STREAMING
        
        # Callback settings
        if self.callback_url is None:
            self.callback_url = config.CALLBACK_URL
        if self.callback_auth_header is None:
            self.callback_auth_header = config.CALLBACK_AUTH_HEADER
        
        # Template settings
        if self.template_name is None:
            self.template_name = config.TEMPLATE_NAME
        
        return self


# ============= Batch Process Models =============

class BatchProcessRequest(BaseModel):
    """Request model for batch file processing within a date range."""
    
    # SFTP settings
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    key: str | None = None
    credential_name: str | None = None
    root_path: str = "/"
    
    # Date range (YYYYMMDD format)
    start_date: str
    end_date: str
    
    # LLM call configuration
    call_type: str | None = None
    llm_url: str | None = None
    llm_auth_header: str | None = None
    model_path: str | None = None
    agent_name: str | None = None
    use_streaming: bool | None = None
    
    # Callback settings
    callback_url: str | None = None
    callback_auth_header: str | None = None
    
    # Template and prompt
    template_name: str | None = None
    question: str | None = None
    custom_prompt: str | None = None
    
    def resolve_config(self, config):
        """Resolve all None values from config defaults."""
        # SFTP settings
        if self.host is None:
            self.host = config.SFTP_HOST
        if self.port is None:
            self.port = config.SFTP_PORT
        if self.username is None:
            self.username = config.SFTP_USERNAME
        if self.password is None:
            self.password = config.SFTP_PASSWORD
        if self.key is None:
            self.key = config.SFTP_KEY
        if self.credential_name is None:
            self.credential_name = config.SFTP_CREDENTIAL_NAME
        
        # LLM settings
        if self.call_type is None:
            self.call_type = config.CALL_TYPE
        if self.llm_url is None:
            self.llm_url = config.LLM_URL
        if self.llm_auth_header is None:
            self.llm_auth_header = config.LLM_AUTH_HEADER
        if self.model_path is None:
            self.model_path = config.MODEL_PATH
        if self.agent_name is None:
            self.agent_name = config.AGENT_NAME
        if self.use_streaming is None:
            self.use_streaming = config.USE_STREAMING
        
        # Callback settings
        if self.callback_url is None:
            self.callback_url = config.CALLBACK_URL
        if self.callback_auth_header is None:
            self.callback_auth_header = config.CALLBACK_AUTH_HEADER
        
        # Template settings
        if self.template_name is None:
            self.template_name = config.TEMPLATE_NAME
        
        return self


# ============= Template Models =============

class TemplateCreateRequest(BaseModel):
    """Request model for creating or updating a template."""
    name: str
    content: str


# ============= Proxy Model =============

class ProxyRequest(BaseModel):
    """Request model for proxy endpoint."""
    method: str = "GET"
    url: str
    headers: dict | None = None
    data: dict | None = None


# ============= Response Models =============

class JobStatusResponse(BaseModel):
    """Response model for batch job status."""
    job_id: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    date_range: str | None = None
    error: str | None = None
    results: List[Dict[str, Any]] | None = None
