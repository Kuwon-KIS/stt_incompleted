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
from .routes import health

# Setup logging
setup_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="STT Processing System - Incomplete Sales Detection",
    description="Process transcribed audio files to detect incomplete sales elements",
    version="2.0"
)

# Include routers
app.include_router(health.router)

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

logger.info("STT Processing System initialized (ENV=%s)", config.APP_ENV)


# ============= Proxy Endpoint =============

@app.post("/proxy")
async def proxy(req: ProxyRequest):
    """Forward requests to external endpoints (for testing/debugging)."""
    try:
        logger.info("proxy request to %s method=%s", req.url, req.method)
        resp = requests.request(
            req.method, req.url,
            headers=req.headers,
            json=req.data,
            timeout=10
        )
        logger.info("proxy response status=%s for %s", resp.status_code, req.url)
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "text": resp.text
        }
    except Exception as e:
        logger.exception("proxy failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============= SFTP Endpoints =============

@app.post("/sftp/list")
async def sftp_list(req: SFTPRequest):
    """List files in an SFTP directory."""
    try:
        logger.info("sftp list request host=%s path=%s", req.host, req.path)
        client = SFTPClient(
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password,
            pkey=req.key
        )
        files = client.listdir(req.path)
        client.close()
        logger.info("sftp list success host=%s count=%d", req.host, len(files))
        return {"files": files}
    except Exception as e:
        logger.exception("sftp list failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============= Single File Processing =============

def _resolve_credentials(req: ProcessRequest):
    """Resolve SFTP credentials from request or environment."""
    sftp_username = req.username
    sftp_password = req.password
    sftp_key = req.key
    
    if req.credential_name:
        creds = get_credentials_from_env(
            req.credential_name,
            default_username=req.username,
            default_password=req.password,
            default_key=req.key
        )
        sftp_username = creds["username"]
        sftp_password = creds["password"]
        sftp_key = creds["key"]
        logger.info("loaded SFTP credentials from env: %s", req.credential_name)
    
    return sftp_username, sftp_password, sftp_key


def _fetch_text(req: ProcessRequest, sftp_username: str, sftp_password: str, sftp_key: str) -> str:
    """Fetch text content from SFTP or inline."""
    if req.inline_text is not None:
        logger.info("using inline_text length=%d", len(req.inline_text))
        return req.inline_text
    
    if not req.remote_path:
        raise ValueError("remote_path is required when not using inline_text")
    
    client = SFTPClient(
        host=req.host,
        port=req.port,
        username=sftp_username,
        password=sftp_password,
        pkey=sftp_key
    )
    try:
        text = client.read_file(req.remote_path)
        logger.info("fetched remote file length=%d", len(text) if text else 0)
        return text
    finally:
        client.close()


def _build_prompt(req: ProcessRequest, text: str) -> str:
    """Build prompt from template or custom prompt."""
    if req.custom_prompt:
        logger.info("using custom_prompt length=%d", len(req.custom_prompt))
        return req.custom_prompt
    
    if req.template_name:
        if req.template_name not in TEMPLATE_STORE:
            available = list(TEMPLATE_STORE.keys())
            raise ValueError(
                f"Template '{req.template_name}' not found. Available: {available}"
            )
        template = TEMPLATE_STORE[req.template_name]
        prompt = template.format(text=text, question=req.question or "")
        logger.info("built prompt from template=%s length=%d", req.template_name, len(prompt))
        return prompt
    
    # Default: use text as-is
    logger.info("using raw text as prompt")
    return text


async def _call_detection_api(req: ProcessRequest, prompt: str) -> Dict[str, Any]:
    """Call detection API (vLLM or Agent)."""
    logger.info("calling detection service: type=%s", req.call_type)
    
    detector = get_detector(req.call_type, config)
    
    # For vLLM, use the constructed prompt
    # For Agent, use both text and prompt
    result = await detector.detect(text=prompt, prompt=prompt)
    
    logger.info("detection completed: strategy=%s, issues=%d",
                result.get("strategy"), len(result.get("detected_issues", [])))
    
    return result


def _send_callback(req: ProcessRequest, detection_result: Dict[str, Any]) -> bool:
    """Send results to callback URL."""
    if not req.callback_url:
        logger.debug("no callback_url, skipping callback")
        return True
    
    try:
        headers = {"Content-Type": "application/json"}
        if req.callback_auth_header:
            headers["Authorization"] = req.callback_auth_header
        
        payload = {
            "remote_path": req.remote_path,
            "detection_result": detection_result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info("sending callback to %s", req.callback_url)
        resp = requests.post(req.callback_url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        
        logger.info("callback sent successfully: status=%d", resp.status_code)
        return True
    except Exception as e:
        logger.exception("callback failed: %s", e)
        return False


async def process_sync(req: ProcessRequest) -> Dict[str, Any]:
    """Synchronous processing helper for single file."""
    req = req.resolve_config(config)
    
    logger.info("process_sync start: remote_path=%s, host=%s", req.remote_path, req.host)
    
    try:
        # 1. Resolve credentials
        sftp_username, sftp_password, sftp_key = _resolve_credentials(req)
        
        # 2. Fetch text
        text = _fetch_text(req, sftp_username, sftp_password, sftp_key)
        
        # 3. Build prompt
        prompt = _build_prompt(req, text)
        
        # 4. Call detection API
        detection_result = await _call_detection_api(req, prompt)
        
        # 5. Send callback (non-blocking failure)
        _send_callback(req, detection_result)
        
        logger.info("process_sync completed successfully")
        
        return {
            "success": True,
            "remote_path": req.remote_path,
            "detection_result": detection_result
        }
    
    except Exception as e:
        logger.exception("process_sync failed: %s", e)
        raise


@app.post("/process")
async def process(req: ProcessRequest):
    """Process a single file for incomplete sales element detection."""
    try:
        result = await process_sync(req)
        return result
    except Exception as e:
        logger.exception("process endpoint failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============= Batch Processing (Synchronous) =============

@app.post("/process/batch")
async def process_batch(req: BatchProcessRequest):
    """Process all files within a date range (synchronous)."""
    try:
        req = req.resolve_config(config)
        logger.info("batch processing: date range=%s to %s", req.start_date, req.end_date)
        
        # Resolve credentials
        sftp_username, sftp_password, sftp_key = _resolve_credentials(req)
        
        # Connect and discover files
        client = SFTPClient(
            host=req.host,
            port=req.port,
            username=sftp_username,
            password=sftp_password,
            pkey=sftp_key
        )
        
        results = []
        
        try:
            # Convert dates to integers for comparison
            start_date_int = int(req.start_date)
            end_date_int = int(req.end_date)
            
            # List all directories
            all_dirs = client.list_directories(req.root_path)
            logger.debug("found %d directories in %s", len(all_dirs), req.root_path)
            
            # Filter by date range
            target_dates = []
            for dir_name in all_dirs:
                if len(dir_name) == 8 and dir_name.isdigit():
                    dir_date = int(dir_name)
                    if start_date_int <= dir_date <= end_date_int:
                        target_dates.append(dir_name)
            
            target_dates.sort()
            logger.info("found %d date folders in range [%s, %s]",
                       len(target_dates), req.start_date, req.end_date)
            
            # Collect files from target folders
            file_paths = []
            for date_folder in target_dates:
                folder_path = f"{req.root_path}/{date_folder}".replace("//", "/")
                txt_files = client.list_files(folder_path, suffix=None)
                logger.debug("found %d files in %s", len(txt_files), folder_path)
                
                for filename in txt_files:
                    full_path = f"{folder_path}/{filename}"
                    file_paths.append((date_folder, filename, full_path))
            
            logger.info("total files to process: %d", len(file_paths))
            
            if not file_paths:
                logger.warning("no files found in date range")
                return {"results": [], "total": 0}
        
        finally:
            client.close()
        
        # Process files in parallel
        max_workers = max(1, req.concurrency)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, (date_folder, filename, full_path) in enumerate(file_paths):
                # Create ProcessRequest for this file
                process_req = ProcessRequest(
                    host=req.host,
                    port=req.port,
                    username=sftp_username,
                    password=sftp_password,
                    key=sftp_key,
                    credential_name=None,  # Already resolved
                    remote_path=full_path,
                    call_type=req.call_type,
                    llm_url=req.llm_url,
                    llm_auth_header=req.llm_auth_header,
                    model_path=req.model_path,
                    agent_name=req.agent_name,
                    use_streaming=req.use_streaming,
                    callback_url=req.callback_url,
                    callback_auth_header=req.callback_auth_header,
                    template_name=req.template_name,
                    question=req.question,
                    custom_prompt=req.custom_prompt,
                    inline_text=None
                )
                
                future = executor.submit(asyncio.run, process_sync(process_req))
                futures[future] = (idx, date_folder, filename)
            
            for fut in as_completed(futures):
                idx, date_folder, filename = futures[fut]
                try:
                    res = fut.result()
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": True,
                        "result": res
                    })
                except Exception as e:
                    logger.exception("batch file %s failed: %s", filename, e)
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": False,
                        "error": str(e)
                    })
        
        # Sort results by original index
        results.sort(key=lambda r: r["index"])
        
        return {"results": results, "total": len(file_paths)}
    
    except Exception as e:
        logger.exception("batch processing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============= Batch Processing (Asynchronous) =============

async def run_batch_async(job_id: str, req: BatchProcessRequest):
    """Background task to execute batch processing asynchronously."""
    JOB_STORE[job_id]["status"] = "running"
    JOB_STORE[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    
    req = req.resolve_config(config)
    
    results = []
    try:
        # Resolve credentials
        sftp_username, sftp_password, sftp_key = _resolve_credentials(req)
        
        logger.info("batch job %s: processing date range %s to %s",
                   job_id, req.start_date, req.end_date)
        
        client = SFTPClient(
            host=req.host,
            port=req.port,
            username=sftp_username,
            password=sftp_password,
            pkey=sftp_key
        )
        
        try:
            # Convert dates to integers for comparison
            start_date_int = int(req.start_date)
            end_date_int = int(req.end_date)
            
            # List all directories
            all_dirs = client.list_directories(req.root_path)
            
            # Filter by date range
            target_dates = []
            for dir_name in all_dirs:
                if len(dir_name) == 8 and dir_name.isdigit():
                    dir_date = int(dir_name)
                    if start_date_int <= dir_date <= end_date_int:
                        target_dates.append(dir_name)
            
            target_dates.sort()
            logger.info("batch job %s: found %d date folders", job_id, len(target_dates))
            
            # Collect files from target folders
            file_paths = []
            for date_folder in target_dates:
                folder_path = f"{req.root_path}/{date_folder}".replace("//", "/")
                txt_files = client.list_files(folder_path, suffix=None)
                
                for filename in txt_files:
                    full_path = f"{folder_path}/{filename}"
                    file_paths.append((date_folder, filename, full_path))
            
            logger.info("batch job %s: total files to process: %d", job_id, len(file_paths))
        
        finally:
            client.close()
        
        # Process files in parallel
        max_workers = max(1, req.concurrency)
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, (date_folder, filename, full_path) in enumerate(file_paths):
                process_req = ProcessRequest(
                    host=req.host,
                    port=req.port,
                    username=sftp_username,
                    password=sftp_password,
                    key=sftp_key,
                    credential_name=None,
                    remote_path=full_path,
                    call_type=req.call_type,
                    llm_url=req.llm_url,
                    llm_auth_header=req.llm_auth_header,
                    model_path=req.model_path,
                    agent_name=req.agent_name,
                    use_streaming=req.use_streaming,
                    callback_url=req.callback_url,
                    callback_auth_header=req.callback_auth_header,
                    template_name=req.template_name,
                    question=req.question,
                    custom_prompt=req.custom_prompt,
                    inline_text=None
                )
                
                future = executor.submit(asyncio.run, process_sync(process_req))
                futures[future] = (idx, date_folder, filename)
            
            for fut in as_completed(futures):
                idx, date_folder, filename = futures[fut]
                try:
                    res = fut.result()
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": True,
                        "result": res
                    })
                except Exception as e:
                    logger.exception("batch job %s file %s failed: %s", job_id, filename, e)
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": False,
                        "error": str(e)
                    })
        
        results.sort(key=lambda r: r["index"])
    
    except Exception as e:
        logger.exception("batch job %s failed: %s", job_id, e)
        JOB_STORE[job_id]["error"] = str(e)
    
    JOB_STORE[job_id]["results"] = results
    JOB_STORE[job_id]["status"] = "completed"
    JOB_STORE[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("batch job %s completed with %d results", job_id, len(results))


@app.post("/process/batch/submit")
async def process_batch_submit(req: BatchProcessRequest):
    """Submit a batch job and return job_id (asynchronous processing)."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    JOB_STORE[job_id] = {
        "status": "pending",
        "created_at": now,
        "results": None,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "date_range": f"{req.start_date} to {req.end_date}"
    }
    
    logger.info("batch job %s submitted for date range %s to %s",
               job_id, req.start_date, req.end_date)
    
    # Schedule background task
    asyncio.create_task(run_batch_async(job_id, req))
    
    return {
        "job_id": job_id,
        "status": "submitted",
        "date_range": f"{req.start_date} to {req.end_date}"
    }


@app.get("/process/batch/status/{job_id}")
async def process_batch_status(job_id: str):
    """Check the status of a batch job."""
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = JOB_STORE[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        date_range=job.get("date_range"),
        error=job.get("error"),
        results=job.get("results") if job["status"] == "completed" else None
    )


# ============= Template Management =============

@app.get("/templates")
async def list_templates():
    """List all available prompt templates."""
    return {
        "templates": list(TEMPLATE_STORE.keys()),
        "count": len(TEMPLATE_STORE)
    }


@app.get("/templates/{template_name}")
async def get_template(template_name: str):
    """Get the content of a specific template."""
    if template_name not in TEMPLATE_STORE:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
    
    return {
        "name": template_name,
        "content": TEMPLATE_STORE[template_name]
    }


@app.post("/templates")
async def create_template(req: TemplateCreateRequest):
    """Create or update a template."""
    if not req.name or not req.content:
        raise HTTPException(status_code=400, detail="name and content are required")
    
    # Save to memory
    TEMPLATE_STORE[req.name] = req.content
    
    # Also save to file for persistence
    template_file = config.TEMPLATE_DIR / f"{req.name}.txt"
    template_file.write_text(req.content, encoding="utf-8")
    logger.info("created/updated template: %s", req.name)
    
    return {"name": req.name, "status": "created"}


@app.delete("/templates/{template_name}")
async def delete_template(template_name: str):
    """Delete a template."""
    if template_name not in TEMPLATE_STORE:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")
    
    del TEMPLATE_STORE[template_name]
    
    # Also delete from file
    template_file = config.TEMPLATE_DIR / f"{template_name}.txt"
    if template_file.exists():
        template_file.unlink()
        logger.info("deleted template: %s", template_name)
    
    return {"name": template_name, "status": "deleted"}


@app.post("/templates/refresh")
async def refresh_templates():
    """Reload all templates from disk."""
    load_templates()
    return {
        "status": "refreshed",
        "templates": list(TEMPLATE_STORE.keys()),
        "count": len(TEMPLATE_STORE)
    }


# ============= Mock Endpoints (for testing) =============

@app.post("/mock/vllm")
async def mock_vllm(body: dict):
    """Mock vLLM endpoint that mimics /v1/chat/completions format."""
    messages = body.get("messages", [{}])
    user_content = messages[0].get("content", "") if messages else ""
    tokens = len(user_content.split())
    summary = user_content[:200]
    
    return {
        "choices": [
            {
                "message": {
                    "content": summary,
                    "role": "assistant"
                }
            }
        ],
        "usage": {
            "completion_tokens": tokens,
            "prompt_tokens": tokens
        }
    }


@app.post("/mock/agent/{agent_name}/messages")
async def mock_agent(agent_name: str, body: dict):
    """Mock agent endpoint."""
    user_query = body.get("parameters", {}).get("user_query", "")
    
    return {
        "result": f"Agent '{agent_name}' processed: {user_query[:100]}",
        "agent": agent_name,
        "use_streaming": body.get("use_streaming", False)
    }


@app.post("/mock/callback")
async def mock_callback(body: dict):
    """Mock callback that just logs and returns accepted."""
    logger.info("mock callback received: keys=%s", list(body.keys()))
    return {"status": "accepted"}
