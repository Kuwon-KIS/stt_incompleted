"""
FastAPI application for STT processing system.
Main entry point that integrates all modules.
"""

import logging
import time
import asyncio
import os
import pathlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any
import uuid
import requests

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

# Import modular components
from .config import config
from .models import (
    ProcessRequest, BatchProcessRequest, SFTPRequest, ProxyRequest,
    TemplateCreateRequest, JobStatusResponse
)
from .sftp_client import SFTPClient
from .detection import get_detector
from .utils import setup_logging, get_credentials_from_env, is_retriable_error
from .routes import health, process, templates, sftp, proxy, web

# Setup logging
setup_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="STT Processing System - Incomplete Sales Detection",
    description="Process transcribed audio files to detect incomplete sales elements",
    version="2.0"
)

# Include routers (web router first to handle / and /ui)
app.include_router(web.router)
app.include_router(health.router)
app.include_router(templates.router)
app.include_router(process.router)
app.include_router(sftp.router)
app.include_router(proxy.router)

# Mount static files for web UI (if directory exists)
static_dir = pathlib.Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info("mounted static files from %s", static_dir)

# Application state
START_TIME = time.time()
JOB_STORE: Dict[str, Any] = {}  # job_id -> {status, results, ...}
TEMPLATE_STORE: Dict[str, str] = {}  # template_name -> content


def load_templates():
    """Load all templates from the templates directory into memory."""
    global TEMPLATE_STORE
    TEMPLATE_STORE = {}
    
    if config.TEMPLATE_DIR.exists():
        for template_file in config.TEMPLATE_DIR.glob("*"):
            if template_file.name.startswith('.') or template_file.is_dir():
                continue
            name = template_file.stem
            content = template_file.read_text(encoding="utf-8", errors='replace')
            TEMPLATE_STORE[name] = content
            logger.info("loaded template: %s", name)
    else:
        logger.warning("templates directory not found at %s", config.TEMPLATE_DIR)


# Load templates on startup
load_templates()

# Initialize template router with the template store
templates.set_template_store(TEMPLATE_STORE, config.TEMPLATE_DIR)

# Include template router
app.include_router(templates.router)

logger.info("STT Processing System initialized (ENV=%s)", config.APP_ENV)

# Mock endpoints for local development
@app.post("/mock/agent/{agent_name}/messages")
async def mock_agent_endpoint(agent_name: str, payload: Dict[str, Any]):
    """Mock AI Agent endpoint for local testing.
    
    Returns a mock detection result without calling real AI agent.
    """
    logger.debug("Mock agent endpoint called: agent=%s", agent_name)
    
    try:
        # Extract user query and context from payload
        params = payload.get("parameters", {})
        user_query = params.get("user_query", "")
        context = params.get("context", "")
        
        # Mock detection logic - simulates agent analysis
        # In real scenario, this would call actual AI agent API
        # AgentDetector expects "result" field with completion text
        mock_completion = """분석 결과:
1. 불완전한 판매 요소 감지:
   - 상품 설명 불충분: 주요 특징과 이점을 더 명확하게 설명해야 함
   - 고객 요구사항 확인 부족: 고객의 실제 필요를 더 깊이 있게 파악해야 함
   
2. 개선 필요 부분:
   - 가격 협상 시 논거 약함
   - 구매 의사 확인이 명확하지 않음
   
3. 종합 평가: 전반적으로 양호하나 마무리 부분 개선 권장"""
        
        mock_result = {
            "result": mock_completion,
            "status": "success",
            "processing_time_ms": 150
        }
        
        logger.info("Mock agent response: agent=%s", agent_name)
        
        return mock_result
    except Exception as e:
        logger.error("Mock agent endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))