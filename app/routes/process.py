"""
Process endpoint routes for single file and batch processing.
"""

import logging
import asyncio
import time
import os
import uuid
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any

from ..config import config
from ..models import ProcessRequest, BatchProcessRequest
from ..sftp_client import SFTPClient, create_sftp_client
from ..detection import get_detector
from ..utils import get_credentials_from_env

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["process"])

# In-memory job store for async batch processing
JOB_STORE: Dict[str, Any] = {}


# ===== TEST ENDPOINT =====
@router.post("/batch/test")
async def process_batch_test():
    """간단한 테스트 엔드포인트 - Mock 데이터만 반환"""
    logger.info("🧪 테스트 배치 엔드포인트 호출됨")
    
    job_id = str(uuid.uuid4())
    
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
        },
        {
            "date": "20260314",
            "filename": "20260314_002.txt",
            "success": True,
            "text": "테스트 텍스트 2",
            "category": "상품설명",
            "summary": "테스트 요약 2",
            "omission_num": "2",
            "detected_issues": [
                {
                    "step": "리스크 설명",
                    "reason": "리스크가 충분히 설명되지 않음",
                    "category": "설명의무"
                }
            ]
        }
    ]
    
    # Job store 업데이트
    JOB_STORE[job_id] = {
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "results": mock_results,
        "error": None,
        "date_range": "20260314 to 20260316"
    }
    
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


# ===== Batch Processing =====

async def run_batch_async(job_id: str, req: BatchProcessRequest):
    """Background task to execute batch processing and store results.
    
    For APP_ENV=local (Mock mode), this creates sample results quickly.
    """
    logger.info("🚀 백그라운드 배치 작업 시작: job_id=%s, date_range=%s~%s", job_id, req.start_date, req.end_date)
    
    def run_batch_sync():
        """동기 배치 처리 함수"""
        try:
            JOB_STORE[job_id]["status"] = "running"
            JOB_STORE[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

            results = []
            
            # APP_ENV=local이면 Mock 배치 처리 (매우 빠름)
            if config.APP_ENV == "local":
                logger.info("📌 Mock 모드: 샘플 결과 생성 중...")
                
                # 날짜 범위 내의 모든 날짜 생성
                from datetime import timedelta
                current = datetime.strptime(req.start_date, "%Y%m%d")
                end = datetime.strptime(req.end_date, "%Y%m%d")
                
                mock_results = []
                file_idx = 0
                
                while current <= end:
                    date_str = current.strftime("%Y%m%d")
                    
                    # 각 날짜마다 3개의 파일 생성
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
                        
                        result_item = {
                            "index": file_idx,
                            "date": date_str,
                            "filename": filename,
                            "success": True,
                            "text": f"고객과의 통화 기록\n시간: {date_str}\n상담사: 홍길동\n고객명: 김철수\n\n상담내용:\n- 상품 설명\n- 가격 안내\n- 특징 설명",
                            "category": "사후판매",
                            "summary": f"[{filename}] 불완전판매요소 탐지 결과",
                            "omission_num": str(len(mock_issues)),
                            "detected_issues": mock_issues,
                            "processing_time_ms": 100
                        }
                        mock_results.append(result_item)
                        file_idx += 1
                    
                    current += timedelta(days=1)
                
                results = mock_results
                logger.info("✅ Mock 배치 완료: 총 %d개 파일 처리", len(results))
            else:
                # Real batch processing - 실제 환경에서는 여기서 실행
                logger.info("🔐 실제 배치 처리 모드 (구현 필요)")
                pass
            
            JOB_STORE[job_id]["results"] = results
            JOB_STORE[job_id]["status"] = "completed"
            JOB_STORE[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
            logger.info("✅ 배치 처리 완료: job_id=%s, 결과 수=%d", job_id, len(results))
        
        except Exception as e:
            logger.exception("❌ 배치 처리 실패: %s", e)
            JOB_STORE[job_id]["error"] = str(e)
            JOB_STORE[job_id]["status"] = "failed"
            JOB_STORE[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    # ThreadPoolExecutor에서 동기 함수 실행
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_batch_sync)


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
async def process_batch_submit(req: BatchProcessRequest, background_tasks: BackgroundTasks):
    """Submit a batch job and return job_id. The job runs asynchronously in background."""
    logger.info("📝 배치 제출 요청: start_date=%s, end_date=%s", req.start_date, req.end_date)
    
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    logger.info("🔄 Job store 초기화...")
    JOB_STORE[job_id] = {
        "status": "pending", 
        "created_at": now, 
        "results": None, 
        "started_at": None, 
        "completed_at": None,
        "error": None,
        "date_range": f"{req.start_date} to {req.end_date}"
    }
    logger.info("✅ Job store 초기화 완료: job_id=%s", job_id)

    # Schedule background task using FastAPI BackgroundTasks
    logger.info("🔄 백그라운드 작업 스케줄링...")
    background_tasks.add_task(run_batch_async, job_id, req)
    logger.info("✅ 백그라운드 작업 스케줄링 완료")

    response = {
        "job_id": job_id, 
        "status": "submitted", 
        "date_range": f"{req.start_date} to {req.end_date}"
    }
    logger.info("✅ 클라이언트에 응답 반환: %s", response)
    return response


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
