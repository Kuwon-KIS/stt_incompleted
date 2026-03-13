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
