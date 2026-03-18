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
from .routes import health, process, templates, sftp, proxy, web, admin
from .database import DatabaseManager

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
app.include_router(admin.router)

# Mount static files for web UI (if directory exists)
static_dir = pathlib.Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info("mounted static files from %s", static_dir)

# Initialize database
try:
    db_manager = DatabaseManager()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error("Failed to initialize database: %s", e)
    raise

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
@app.get("/mock/agent")
async def mock_agent_health():
    """Health check endpoint for mock agent."""
    logger.debug("Mock agent health check")
    return {"status": "ok", "message": "Mock Agent is running"}


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
        # Agent response format (nested): { message_id, chat_thread_id, answer: { answer: { ... } } }
        # This matches actual Agent API response structure from memo
        mock_agent_data = {
            "category": "사후판매",
            "summary": "김철수 고객님에게 IMA 투자신탁 상품을 판매하는 내용입니다. 투자 성향과 위험도를 확인하고 상품 설명을 진행했습니다.",
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
        
        # Wrap in nested answer structure to match real Agent API
        mock_agent_response = {
            "message_id": "msg_" + str(uuid.uuid4())[:8],
            "chat_thread_id": "thread_" + str(uuid.uuid4())[:8],
            "answer": {
                "answer": mock_agent_data
            }
        }
        
        import json
        mock_result = {
            "result": json.dumps(mock_agent_response, ensure_ascii=False),
            "status": "success",
            "processing_time_ms": 150
        }
        
        logger.info("Mock agent response: agent=%s, omissions=%s", 
                   agent_name, mock_agent_data.get("omission_num", "0"))
        
        return mock_result
    except Exception as e:
        logger.error("Mock agent endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))