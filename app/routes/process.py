"""
Process endpoint routes for single file and batch processing.
"""

import logging
import asyncio
import time
import os
import uuid
import csv
import io
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any

from ..config import config
from ..models import ProcessRequest, BatchProcessRequest
from ..sftp_client import SFTPClient, create_sftp_client
from ..detection import get_detector
from ..utils import get_credentials_from_env
from ..database import DatabaseManager, BatchJob, BatchResult, DateStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["process"])

# Initialize database manager
db = DatabaseManager()


def determine_date_status(total_files: int, processed_files: int, failed_files: int) -> str:
    """
    Determine date processing status based on statistics.
    
    - ready: 처리된 파일 없음 (total_files == 0)
    - done: 모든 파일 성공 (failed_files == 0 and processed_files == total_files)
    - incomplete: 일부 파일 실패 (failed_files > 0 and processed_files > 0)
    - failed: 모든 파일 실패 (processed_files == 0 and total_files > 0)
    """
    if total_files == 0:
        return "ready"
    
    if failed_files == 0 and processed_files == total_files:
        return "done"
    
    if failed_files > 0 and processed_files > 0:
        return "incomplete"
    
    if processed_files == 0 and total_files > 0:
        return "failed"
    
    return "incomplete"  # 기본값


# ===== TEST ENDPOINT =====
@router.post("/batch/test")
async def process_batch_test():
    """간단한 테스트 엔드포인트 - Mock 데이터만 반환"""
    logger.info("🧪 테스트 배치 엔드포인트 호출됨")
    
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Mock results 생성
    mock_results = [
        {
            "date": "20260314",
            "filename": "20260314_001.txt",
            "success": True,
            "text": "테스트 텍스트 1",
            "category": "사후판매",
            "summary": "테스트 요약 1",
            "omission_num": "1",
            "detected_issues": [
                {
                    "step": "투자자정보 확인",
                    "reason": "확인 구간이 명확하지 않음",
                    "category": "설명의무"
                }
            ]
        }
    ]
    
    # Create job in database
    job = BatchJob(
        id=job_id,
        status="completed",
        start_date="20260314",
        end_date="20260314",
        created_at=now,
        started_at=now,
        completed_at=now,
        total_files=1,
        success_files=1,
        failed_files=0
    )
    db.create_job(job)
    
    # Store results in database
    for result_data in mock_results:
        result = BatchResult(
            job_id=job_id,
            file_date=result_data["date"],
            filename=result_data["filename"],
            success=result_data["success"],
            text_content=result_data.get("text"),
            category=result_data.get("category"),
            summary=result_data.get("summary"),
            omission_num=int(result_data.get("omission_num", 0)),
            detected_issues=result_data.get("detected_issues", []),
            processing_time_ms=100,
            created_at=now
        )
        db.create_result(result)
    
    logger.info("✅ 테스트 배치 완료: job_id=%s", job_id)
    return {
        "job_id": job_id,
        "status": "completed",
        "results": mock_results
    }


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
        
        client = create_sftp_client(host=req.host, port=req.port, username=creds["username"],
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
    logger.info("calling detection service type=%s", config.CALL_TYPE)
    
    try:
        # This would be async in production, but kept sync for now
        detector = get_detector(config.CALL_TYPE, config)
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
                "call_type": config.CALL_TYPE,
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


# ===== Batch Processing - ASYNC ARCHITECTURE =====

async def run_batch_async(job_id: str, req: BatchProcessRequest):
    """Async batch processing function.
    
    This is the core async function that handles batch processing with proper event loop architecture.
    All file processing happens in a SINGLE event loop using asyncio.gather() for concurrency.
    
    Supports SELECT_TARGET case-based options:
    - option_id='reprocess': Force reprocess (force=true)
    - option_id='view_history': View history (no processing)
    - option_id='process_new': Process new dates only
    - option_id='reprocess_all': Reprocess all dates in range
    """
    logger.info("=" * 80)
    logger.info("[BATCH_ASYNC_START] job_id=%s, date_range=%s~%s, option_id=%s", 
                job_id, req.start_date, req.end_date, req.option_id)
    import sys; sys.stdout.flush()
    
    try:
        # Step 1: Handle option_id for SELECT_TARGET feature
        logger.info("[BATCH_STEP_1_START] Checking option_id")
        sys.stdout.flush()
        if req.option_id == "view_history":
            logger.info("[BATCH_OPTION] option_id='view_history': returning without processing")
            db.update_job_status(job_id, "completed")
            logger.info("[BATCH_SUCCESS] Job completed (view_history mode)")
            logger.info("=" * 80)
            return
        logger.info("[BATCH_STEP_1_OK] option_id check completed: %s", req.option_id)
        sys.stdout.flush()
        
        # Step 2: Adjust force_reprocess based on option_id
        logger.info("[BATCH_STEP_2_START] Adjusting force_reprocess")
        sys.stdout.flush()
        if req.option_id == "reprocess" or req.option_id == "reprocess_all":
            req.force_reprocess = True
            logger.info("[BATCH_OPTION] option_id='%s': setting force_reprocess=true", req.option_id)
        logger.info("[BATCH_STEP_2_OK] force_reprocess adjusted")
        sys.stdout.flush()
        
        logger.info("[BATCH_STATUS_UPDATE] Updating status to 'running'")
        sys.stdout.flush()
        try:
            db.update_job_status(job_id, "running")
            logger.info("[BATCH_STATUS_OK] Status updated successfully")
            sys.stdout.flush()
        except Exception as db_err:
            logger.exception("[BATCH_STATUS_ERROR] Failed to update job status: %s", db_err)
            sys.stdout.flush()
            raise

        results = []
        date_files = {}
        logger.info("[BATCH_READY] Ready to process (APP_ENV=%s)", config.APP_ENV)
        sys.stdout.flush()
        
        # APP_ENV=local이면 Mock 배치 처리 (async 병렬 처리)
        if config.APP_ENV == "local":
            logger.info("[BATCH_MODE] Mock mode: creating sample results with async processing...")
            
            # 날짜 범위 내의 모든 날짜 생성
            current = datetime.strptime(req.start_date, "%Y%m%d")
            end = datetime.strptime(req.end_date, "%Y%m%d")
            
            files_to_process = []
            file_idx = 0
            
            while current <= end:
                date_str = current.strftime("%Y%m%d")
                date_files[date_str] = {"total": 0, "success": 0, "failed": 0}
                
                # 각 날짜마다 3개의 파일
                for i in range(1, 4):
                    filename = f"{date_str}_{i:03d}.txt"
                    
                    # Mock detection result
                    mock_issues = [
                        {
                            "step": "투자자정보 확인",
                            "reason": "투자자 정보 확인 구간이 명확하지 않습니다.",
                            "category": "설명의무"
                        }
                    ] if i % 2 == 0 else [
                        {
                            "step": "설명서 필수 사항 설명",
                            "reason": "금융투자상품의 내용 및 구조 설명이 불충분합니다.",
                            "category": "설명의무"
                        },
                        {
                            "step": "위험도 안내",
                            "reason": "상품의 위험 요소가 충분히 설명되지 않았습니다.",
                            "category": "설명의무"
                        }
                    ]
                    
                    files_to_process.append({
                        "index": file_idx,
                        "date": date_str,
                        "filename": filename,
                        "mock_issues": mock_issues
                    })
                    file_idx += 1
                
                current += timedelta(days=1)
            
            # Async helper to process mock file
            async def process_mock_file_async(file_info):
                """Async mock 파일 처리 함수"""
                try:
                    date_str = file_info["date"]
                    filename = file_info["filename"]
                    mock_issues = file_info["mock_issues"]
                    
                    logger.debug("[BATCH_MOCK_FILE] Processing: %s", filename)
                    
                    # Simulate async processing delay
                    await asyncio.sleep(0.1)
                    
                    now = datetime.now(timezone.utc)
                    result_item = {
                        "index": file_info["index"],
                        "date": date_str,
                        "filename": filename,
                        "success": True,
                        "text": f"고객과의 통화 기록\n시간: {date_str}\n상담사: 홍길동\n고객명: 김철수\n\n상담내용:\n- 상품 설명\n- 가격 안내\n- 특징 설명",
                        "category": "사후판매",
                        "summary": f"[{filename}] STT 사후 점검",
                        "omission_num": str(len(mock_issues)),
                        "detected_issues": mock_issues,
                        "processing_time_ms": 100,
                        "created_at": now
                    }
                    logger.debug("[BATCH_MOCK_OK] %s processed successfully", filename)
                    return result_item, True, None
                    
                except Exception as e:
                    logger.error("[BATCH_MOCK_FILE_ERROR] Failed to process mock file: %s", str(e), exc_info=True)
                    return None, False, str(e)
            
            # Process all mock files concurrently
            logger.info("[BATCH_MOCK_ASYNC_START] Processing %d mock files concurrently", len(files_to_process))
            
            tasks = [process_mock_file_async(f) for f in files_to_process]
            results_tuples = await asyncio.gather(*tasks, return_exceptions=False)
            
            for result_item, success, error in results_tuples:
                if success:
                    results.append(result_item)
                    date_str = result_item["date"]
                    date_files[date_str]["total"] += 1
                    date_files[date_str]["success"] += 1
                    logger.info("[BATCH_MOCK_RESULT_OK] File processed: %s", result_item.get("filename"))
                else:
                    logger.warning("[BATCH_MOCK_RESULT_ERROR] Mock file processing failed: %s", error)
                    # Still need to track this as a failure
                    if result_item:
                        date_files[result_item["date"]]["failed"] += 1
                        date_files[result_item["date"]]["total"] += 1
            
            logger.info("[BATCH_MOCK_ASYNC_COMPLETE] Mock batch processing complete: %d files processed", len(results))
        else:
            # Real batch processing - SFTP에서 파일 조회 및 AI 처리 (ASYNC VERSION)
            logger.info("[BATCH_MODE] Real mode: reading from SFTP and processing with AI (async)")
            
            try:
                # 1. SFTP 클라이언트 초기화
                logger.info("[BATCH_SFTP_INIT] Initializing SFTP client: %s:%d", 
                           config.SFTP_HOST, config.SFTP_PORT)
                sftp_client = SFTPClient(
                    host=config.SFTP_HOST,
                    port=config.SFTP_PORT,
                    username=config.SFTP_USERNAME,
                    password=config.SFTP_PASSWORD,
                    pkey=config.SFTP_KEY
                )
                
                # 2. 날짜 범위별 파일 조회
                current = datetime.strptime(req.start_date, "%Y%m%d")
                end = datetime.strptime(req.end_date, "%Y%m%d")
                
                files_to_process = []
                
                while current <= end:
                    date_str = current.strftime("%Y%m%d")
                    # Handle trailing slash in SFTP_ROOT_PATH to avoid double slashes
                    root_path = config.SFTP_ROOT_PATH.rstrip('/')
                    date_path = f"{root_path}/{date_str}"
                    date_files[date_str] = {"total": 0, "success": 0, "failed": 0}
                    
                    logger.info("[BATCH_SFTP_LIST] Listing files in: %s", date_path)
                    
                    try:
                        # 해당 날짜 디렉토리에서 .txt 파일 조회 (파일명만 반환)
                        file_names = sftp_client.list_files(path=date_path, suffix=".txt")
                        logger.info("[BATCH_FILES_FOUND] Found %d files for date %s", len(file_names), date_str)
                        
                        # Collect files for async processing
                        for file_name in file_names:
                            files_to_process.append({
                                "date": date_str,
                                "date_path": date_path,
                                "filename": file_name
                            })
                        
                        current += timedelta(days=1)
                    
                    except Exception as dir_error:
                        logger.warning("[BATCH_DIR_ERROR] Failed to access directory %s: %s", 
                                     date_path, str(dir_error))
                        current += timedelta(days=1)
                
                # 3. Async helper to process single file
                async def process_file_async(file_info):
                    """Async 단일 파일 처리 함수 - 같은 event loop에서 실행됨"""
                    try:
                        date_str = file_info["date"]
                        date_path = file_info["date_path"]
                        file_name = file_info["filename"]
                        file_path = f"{date_path}/{file_name}"
                        
                        logger.debug("[BATCH_FILE_PROCESS] Processing: %s", file_name)
                        
                        # 파일 내용 읽기 (blocking I/O를 executor로 처리)
                        loop = asyncio.get_event_loop()
                        content = await loop.run_in_executor(
                            None,
                            sftp_client.read_file,
                            file_path
                        )
                        
                        # AI 처리 (async detector.detect 호출)
                        detector = get_detector(config.CALL_TYPE, config)
                        default_prompt = "판매 대화의 불완전판매요소를 검사해주세요."
                        logger.info("[BATCH_FILE_DETECT] Calling detector for %s (call_type=%s)", 
                                   file_name, config.CALL_TYPE)
                        
                        ai_result = await detector.detect(content, default_prompt)
                        logger.info("[BATCH_FILE_DETECT_OK] Detector returned: category=%s, issues=%d", 
                                   ai_result.get("category", "unknown"), 
                                   len(ai_result.get("detected_issues", [])))
                        
                        # 결과 변환
                        now = datetime.now(timezone.utc)
                        result_item = {
                            "date": date_str,
                            "filename": file_name,
                            "success": True,
                            "text": content,
                            "category": ai_result.get("category", "unknown"),
                            "summary": ai_result.get("summary", ""),
                            "omission_num": str(ai_result.get("omission_num", 0)),
                            "detected_issues": ai_result.get("detected_issues", []),
                            "processing_time_ms": ai_result.get("processing_time_ms", 0),
                            "created_at": now
                        }
                        logger.debug("[BATCH_FILE_OK] %s processed successfully", file_name)
                        return result_item, True, None
                        
                    except Exception as file_error:
                        logger.error("[BATCH_FILE_ERROR] Failed to process %s: %s", 
                                     file_name, str(file_error), exc_info=True)
                        return None, False, str(file_error)
                
                # 4. Process all files concurrently using asyncio.gather
                logger.info("[BATCH_ASYNC_START] Processing %d files concurrently", len(files_to_process))
                
                if files_to_process:
                    tasks = [process_file_async(f) for f in files_to_process]
                    results_tuples = await asyncio.gather(*tasks, return_exceptions=False)
                    
                    for result_item, success, error in results_tuples:
                        if success:
                            results.append(result_item)
                            date_str = result_item["date"]
                            date_files[date_str]["total"] += 1
                            date_files[date_str]["success"] += 1
                            logger.info("[BATCH_RESULT_OK] File processed successfully: %s", result_item.get("filename"))
                        else:
                            logger.warning("[BATCH_RESULT_ERROR] File processing failed: %s", error)
                            # Track failed file if we have date info
                            if result_item:
                                date_files[result_item["date"]]["failed"] += 1
                                date_files[result_item["date"]]["total"] += 1
                else:
                    logger.info("[BATCH_NO_FILES] No files found to process")
                
                logger.info("[BATCH_ASYNC_COMPLETE] Async processing complete: %d files processed", len(results))
                
            except Exception as sftp_error:
                logger.exception("[BATCH_REAL_ERROR] Real mode processing failed: %s", sftp_error)
                raise
        
        # ===== 공통 DB 저장 로직 (Local/Real 모드 모두) =====
        logger.info("[BATCH_DB_INSERT_START] Saving %d results to database", len(results))
        for idx, result_data in enumerate(results):
            try:
                logger.debug("[BATCH_DB_INSERT_DETAIL_%d] Processing result: %s", idx, result_data.get("filename"))
                result = BatchResult(
                    job_id=job_id,
                    file_date=result_data["date"],
                    filename=result_data["filename"],
                    success=result_data["success"],
                    text_content=result_data.get("text"),
                    category=result_data.get("category"),
                    summary=result_data.get("summary"),
                    omission_num=int(result_data.get("omission_num", 0)),
                    detected_issues=result_data.get("detected_issues", []),
                    processing_time_ms=result_data.get("processing_time_ms", 0),
                    created_at=result_data.get("created_at", datetime.now(timezone.utc))
                )
                db.create_result(result)
                logger.info("[BATCH_DB_INSERT_OK_%d] Saved result for %s", idx, result_data.get("filename"))
            except Exception as db_error:
                logger.error("[BATCH_DB_ERROR] Failed to save result for %s: %s", 
                           result_data.get("filename"), str(db_error), exc_info=True)
        logger.info("[BATCH_DB_INSERT_OK] Saved %d results to database", len(results))
        
        # 날짜별 상태 업데이트 (공통)
        logger.info("[BATCH_DATE_STATUS_UPDATE] Updating status for %d dates", len(date_files))
        for date_str, stats in date_files.items():
            try:
                db.get_or_create_date_status(date_str)
                status = determine_date_status(stats["total"], stats["success"], stats["failed"])
                db.update_date_status(
                    date_str,
                    total=stats["total"],
                    processed=stats["success"],
                    failed=stats["failed"],
                    status=status
                )
                logger.debug("[BATCH_DATE_STATUS] date=%s, total=%d, success=%d, status=%s", 
                            date_str, stats["total"], stats["success"], status)
            except Exception as status_error:
                logger.error("[BATCH_STATUS_ERROR] Failed to update date status for %s: %s", 
                           date_str, str(status_error))
        logger.info("[BATCH_DATE_STATUS_OK] Updated status for %d dates", len(date_files))
        logger.info("[BATCH_STATS_UPDATE] Updating job statistics")
        db.update_job_stats(
            job_id,
            total=len(results),
            success=sum(1 for r in results if r.get("success")),
            failed=sum(1 for r in results if not r.get("success"))
        )
        logger.info("[BATCH_STATS_OK] Job stats updated: total=%d, success=%d", 
                   len(results), sum(1 for r in results if r.get("success")))
        
        logger.info("[BATCH_STATUS_UPDATE] Updating status to 'completed'")
        db.update_job_status(job_id, "completed")
        logger.info("[BATCH_COMPLETE] Batch processing completed successfully: job_id=%s, results=%d", 
                   job_id, len(results))
        logger.info("=" * 80)
    
    except Exception as e:
        logger.exception("[BATCH_ERROR] ❌ Batch processing failed: %s", e)
        try:
            db.update_job_status(job_id, "failed", error_message=str(e))
            logger.info("[BATCH_ERROR_STATUS_SAVED] Error status saved to database")
        except Exception as db_error:
            logger.exception("[BATCH_ERROR_DB_FAILED] Failed to save error status: %s", db_error)
        logger.info("=" * 80)





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
    """Submit a batch job with conflict detection and handling options.
    
    Supports SELECT_TARGET case-based options:
    - option_id='reprocess': Force reprocess completed range
    - option_id='view_history': View existing results (no reprocessing)
    - option_id='process_new': Process only new/unprocessed dates
    - option_id='reprocess_all': Reprocess entire range (even partial overlap)
    
    3가지 케이스 처리:
    1. 전체 겹침 (정확히 동일한 범위): force_reprocess=False면 기존 반환, True면 재처리
    2. 부분 겹침: handle_overlap로 처리 방식 결정 ("new"/"reprocess_all"/"skip_overlap")
    3. 안 겹침: 새 작업 생성
    """
    logger.info("[BATCH_SUBMIT] Received: start=%s, end=%s, force_reprocess=%s, handle_overlap=%s, option_id=%s",
               req.start_date, req.end_date, req.force_reprocess, req.handle_overlap, req.option_id)
    
    # Validate option_id if provided
    if req.option_id:
        valid_options = {"reprocess", "view_history", "process_new", "reprocess_all"}
        if req.option_id not in valid_options:
            logger.error("[BATCH_INVALID_OPTION] Invalid option_id: %s", req.option_id)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid option_id: {req.option_id}. Valid options: {valid_options}"
            )
        logger.info("[BATCH_OPTION] Using option_id: %s", req.option_id)
    
    # 1. 겹치는 기존 작업 조회
    existing_jobs = db.get_jobs_by_date_range(req.start_date, req.end_date)
    
    # 완료/실행 중인 작업만 필터링
    active_jobs = [job for job in existing_jobs 
                   if job["status"] in ["running", "completed"]]
    
    # 2. 겹침 여부 판단
    if active_jobs:
        # 전체 겹침인지 부분 겹침인지 확인
        exact_match = any(
            job["start_date"] == req.start_date and job["end_date"] == req.end_date
            for job in active_jobs
        )
        
        # ===== 케이스 1: 전체 겹침 (정확히 동일한 범위) =====
        if exact_match:
            matching_job = next(
                (job for job in active_jobs 
                 if job["start_date"] == req.start_date and job["end_date"] == req.end_date),
                active_jobs[0]
            )
            
            if req.force_reprocess:
                # 강제 재처리: 새로운 job 생성 (이 경우 아래로 진행)
                logger.info("[BATCH_EXACT_OVERLAP_REPROCESS] Force reprocess enabled for %s-%s",
                           req.start_date, req.end_date)
            else:
                # 기존 작업 반환
                logger.info("[BATCH_EXACT_OVERLAP_SKIP] Returning existing job: %s",
                           matching_job["id"])
                return {
                    "job_id": matching_job["id"],
                    "status": "duplicate",
                    "case": "exact_overlap",
                    "message": f"정확히 동일한 범위의 작업이 이미 {matching_job['status']} 상태입니다",
                    "date_range": f"{req.start_date} to {req.end_date}",
                    "original_created_at": matching_job["created_at"].isoformat() if hasattr(matching_job["created_at"], "isoformat") else str(matching_job["created_at"]),
                    "force_reprocess": req.force_reprocess,
                    "handle_overlap": req.handle_overlap
                }
        
        # ===== 케이스 2: 부분 겹침 =====
        else:
            logger.info("[BATCH_PARTIAL_OVERLAP] Partial overlap detected for %s-%s",
                       req.start_date, req.end_date)
            
            if req.handle_overlap == "new":
                # 기존 방식: 부분 겹침 무시하고 새 작업 생성 (아래로 진행)
                logger.info("[BATCH_PARTIAL_NEW] Creating new job (ignoring overlap)")
                # 아래로 진행하여 새 job 생성
            
            elif req.handle_overlap == "reprocess_all":
                # 전체 재처리: 새로운 job 생성 (아래로 진행)
                logger.info("[BATCH_PARTIAL_REPROCESS_ALL] Creating new job for full reprocess")
                # 아래로 진행하여 새 job 생성
            
            elif req.handle_overlap == "skip_overlap":
                # 겹치는 부분 제외하고 처리 (새 job이지만 메타데이터와 함께)
                logger.info("[BATCH_PARTIAL_SKIP_OVERLAP] Creating new job, skipping overlapping dates")
                # 아래로 진행하여 새 job 생성
            
            else:
                # 잘못된 옵션
                logger.warning("[BATCH_INVALID_OPTION] Invalid handle_overlap: %s", req.handle_overlap)
                return {
                    "job_id": None,
                    "status": "error",
                    "case": "partial_overlap",
                    "message": f"잘못된 handle_overlap 값입니다. 'new', 'reprocess_all', 'skip_overlap' 중 선택하세요",
                    "date_range": f"{req.start_date} to {req.end_date}",
                    "error": f"Invalid handle_overlap: {req.handle_overlap}"
                }
            
            # 부분 겹침일 때는 새 job을 생성하므로 아래로 진행
    
    # ===== 케이스 3: 겹침 없음 또는 재처리 옵션 선택 시 새 작업 생성 =====
    logger.info("[BATCH_NO_OVERLAP] Creating new job for range %s-%s",
               req.start_date, req.end_date)
    
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    logger.info("[BATCH_SUBMIT_DB] Creating job record: job_id=%s", job_id)
    job = BatchJob(
        id=job_id,
        status="pending",
        start_date=req.start_date,
        end_date=req.end_date,
        created_at=now
    )
    try:
        db.create_job(job)
        logger.info("[BATCH_SUBMIT_DB_OK] Job created: %s", job_id)
    except Exception as e:
        logger.exception("[BATCH_SUBMIT_DB_ERROR] Failed to create job: %s", e)
        raise

    # 배치 처리 실행 (async로)
    logger.info("[BATCH_SUBMIT_ASYNC] Executing batch processing: %s", job_id)
    try:
        await run_batch_async(job_id, req)
        logger.info("[BATCH_ASYNC_OK] Batch execution completed: %s", job_id)
    except Exception as e:
        logger.exception("[BATCH_ASYNC_ERROR] Batch execution failed: %s", e)

    response = {
        "job_id": job_id,
        "status": "submitted",
        "case": "no_overlap",
        "date_range": f"{req.start_date} to {req.end_date}",
        "force_reprocess": req.force_reprocess,
        "handle_overlap": req.handle_overlap
    }
    logger.info("[BATCH_SUBMIT_RESPONSE] New job submitted: %s", job_id)
    return response


@router.get("/batch/status/{job_id}")
async def process_batch_status(job_id: str):
    """Check the status of a batch job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Get results for all jobs (not just completed ones)
    results = None
    db_results = db.get_results_by_job(job_id)
    if db_results:
        results = [r.to_dict() for r in db_results]

    return {
        "job_id": job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "date_range": f"{job.start_date} to {job.end_date}",
        "error": job.error_message,
        "total_files": job.total_files,
        "success_files": job.success_files,
        "failed_files": job.failed_files,
        "results": results
    }


@router.get("/calendar/status/{year}/{month}")
async def get_calendar_status(year: int, month: int):
    """Get processing status for a calendar month (UI calendar display format).
    
    This endpoint converts unified date statistics into calendar format.
    Both this endpoint and /api/admin/date-stats use the same underlying data.
    
    - This endpoint returns: Dict format (date -> stats) - optimized for calendar grid UI
    - /api/admin/date-stats returns: Array format - optimized for dashboard table UI
    
    Status values:
    - ready: 미처리
    - done: 전체 성공
    - incomplete: 일부 실패
    - failed: 전체 실패
    """
    try:
        month_status = db.get_month_status(year, month)
        return {
            "year": year,
            "month": month,
            "dates": month_status
        }
    except Exception as e:
        logger.exception("Failed to get calendar status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/results/{job_id}/download")
async def download_batch_results(job_id: str):
    """Download batch processing results as CSV.
    
    Returns a CSV file with all results for the specified job.
    Columns: date, filename, status, category, omission_num, summary, error_message
    """
    try:
        # Get job
        job = db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Get results
        results = db.get_results_by_job(job_id)
        
        # Generate CSV content
        output = io.StringIO()
        fieldnames = [
            'date', 'filename', 'status', 'category', 'omission_num', 
            'summary', 'detected_issues', 'error_message'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in results:
            writer.writerow({
                'date': result.file_date,
                'filename': result.filename,
                'status': 'success' if result.success else 'failed',
                'category': result.category or '-',
                'omission_num': result.omission_num or '-',
                'summary': result.summary or '-',
                'detected_issues': str(result.detected_issues) if result.detected_issues else '-',
                'error_message': result.error_message or '-'
            })
        
        # Prepare streaming response
        csv_content = output.getvalue()
        output.close()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_results_{job_id[:8]}_{timestamp}.csv"
        
        return StreamingResponse(
            iter([csv_content.encode('utf-8-sig')]),  # BOM for Excel compatibility
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to download results: %s", e)
        raise HTTPException(status_code=500, detail=str(e))