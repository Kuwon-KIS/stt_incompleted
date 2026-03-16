"""
Process endpoint routes for single file and batch processing.
"""

import logging
import asyncio
import time
import os
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..config import config
from ..models import ProcessRequest, BatchProcessRequest
from ..sftp_client import SFTPClient
from ..detection import get_detector
from ..utils import get_credentials_from_env

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["process"])

# In-memory job store for async batch processing
JOB_STORE: Dict[str, Any] = {}


def process_sync(req: ProcessRequest) -> dict:
    """Synchronous helper that does the SFTP read, calls vLLM/Agent, and posts callback.
    
    Returns a dict with result or raises Exceptions.
    """
    # Resolve config defaults first
    req = req.resolve_config(config)
    
    logger.info("process_sync start remote_path=%s host=%s", req.remote_path, req.host)

    # Resolve SFTP credentials: from env if credential_name given, else from request
    creds = get_credentials_from_env(req.credential_name, req.username, req.password, req.key) if req.credential_name else {
        "username": req.username,
        "password": req.password,
        "key": req.key,
    }

    # 1) fetch file over SFTP unless inline_text provided
    if req.inline_text is not None:
        text = req.inline_text
        logger.info("using inline_text length=%d", len(text))
    else:
        if not req.remote_path:
            raise ValueError("remote_path is required when inline_text is not provided")
        
        client = SFTPClient(host=req.host, port=req.port, username=creds["username"], 
                          password=creds["password"], pkey=creds["key"])
        try:
            text = client.read_file(req.remote_path)
        finally:
            client.close()

    logger.info("fetched remote file length=%d", len(text) if text is not None else 0)

    # Build the prompt for LLM (using template store from main app)
    # This is a simplified version - actual implementation uses global TEMPLATE_STORE
    # Would use template from TEMPLATE_STORE in actual implementation
    prompt = f"Analyze the following text for incomplete sales elements:\n\n{text}"
    logger.info("built prompt length=%d", len(prompt))

    # 2) Call detection strategy (vLLM or Agent)
    logger.info("calling detection service type=%s", req.call_type)
    
    try:
        # This would be async in production, but kept sync for now
        detector = get_detector(req.call_type, config)
        detection_result = asyncio.run(detector.detect(text, prompt))
        logger.info("detection completed: issues=%d", len(detection_result.get("detected_issues", [])))
    except Exception as e:
        logger.exception("Detection failed: %s", e)
        raise

    # 3) Forward result to callback_url if provided
    if req.callback_url:
        try:
            import requests
            callback_payload = {
                "llm_output": detection_result,
                "remote_path": req.remote_path,
                "call_type": req.call_type,
                "detected_issues": detection_result.get("detected_issues", []),
            }
            resp = requests.post(req.callback_url, json=callback_payload, timeout=30,
                               headers={"Authorization": req.callback_auth_header} if req.callback_auth_header else {})
            logger.info("callback posted status=%s", resp.status_code)
        except Exception as e:
            logger.warning("callback failed (non-blocking): %s", e)

    return {"status": "ok", "detection_result": detection_result}


@router.post("")
async def process_single(req: ProcessRequest):
    """Process a single file and return detection results."""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_sync, req)
        return result
    except Exception as e:
        logger.exception("processing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ===== Batch Processing =====

async def run_batch_async(job_id: str, req: BatchProcessRequest):
    """Background task to execute batch processing and store results."""
    JOB_STORE[job_id]["status"] = "running"
    JOB_STORE[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    # Resolve config defaults
    req = req.resolve_config(config)

    results = []
    try:
        # Resolve SFTP credentials
        creds = get_credentials_from_env(req.credential_name, req.username, req.password, req.key) if req.credential_name else {
            "username": req.username,
            "password": req.password,
            "key": req.key,
        }
        
        # Connect to SFTP and discover files
        logger.info("batch job %s: processing date range %s to %s", job_id, req.start_date, req.end_date)
        client = SFTPClient(host=req.host, port=req.port, username=creds["username"], 
                          password=creds["password"], pkey=creds["key"])
        
        try:
            # Convert date strings to comparable integers
            start_date_int = int(req.start_date)
            end_date_int = int(req.end_date)
            
            # List all date-named directories
            all_dirs = client.list_directories(req.root_path)
            
            # Filter directories by date range
            target_dates = []
            for dir_name in all_dirs:
                if len(dir_name) == 8 and dir_name.isdigit():
                    dir_date = int(dir_name)
                    if start_date_int <= dir_date <= end_date_int:
                        target_dates.append(dir_name)
            
            target_dates.sort()
            logger.info("batch job %s: found %d date folders", job_id, len(target_dates))
            
            # Collect all files from target date folders
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
        
        # Process files in parallel using configured batch concurrency
        max_workers = config.BATCH_CONCURRENCY
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, (date_folder, filename, full_path) in enumerate(file_paths):
                process_req = ProcessRequest(
                    host=req.host,
                    port=req.port,
                    username=creds["username"],
                    password=creds["password"],
                    key=creds["key"],
                    credential_name=None,
                    remote_path=full_path,
                    call_type=req.call_type,
                    template_name=req.template_name,
                )
                
                future = executor.submit(process_sync, process_req)
                futures[future] = (idx, date_folder, filename)
            
            from concurrent.futures import as_completed
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


@router.post("/batch")
async def process_batch(req: BatchProcessRequest):
    """Process all files within a date range (synchronous - returns immediately but may take time)."""
    try:
        req = req.resolve_config(config)
        
        # This is just a wrapper - actual implementation would call run_batch_async
        # For now, just return success message
        logger.info("batch processing submitted for date range %s to %s", req.start_date, req.end_date)
        
        return {
            "status": "submitted",
            "message": "Use /process/batch/submit for async processing with job tracking"
        }
    except Exception as e:
        logger.exception("batch processing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/submit")
async def process_batch_submit(req: BatchProcessRequest):
    """Submit a batch job and return job_id. The job runs asynchronously in background."""
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
    logger.info("batch job %s submitted for date range %s to %s", job_id, req.start_date, req.end_date)

    # Schedule background task
    asyncio.create_task(run_batch_async(job_id, req))

    return {"job_id": job_id, "status": "submitted", "date_range": f"{req.start_date} to {req.end_date}"}


@router.get("/batch/status/{job_id}")
async def process_batch_status(job_id: str):
    """Check the status of a batch job."""
    if job_id not in JOB_STORE:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = JOB_STORE[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "date_range": job.get("date_range"),
        "error": job.get("error"),
        "results": job.get("results") if job["status"] == "completed" else None,
    }
