"""
Health check endpoints for service monitoring.
"""

import time
import logging
from fastapi import APIRouter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])
START_TIME = time.time()


@router.get("/")
async def read_root():
    """Root endpoint - basic health check."""
    logger.debug("Root health check called")
    return {"message": "ok", "service": "stt-processing"}


@router.get("/healthz")
async def healthz():
    """Kubernetes-style liveness/readiness probe with uptime."""
    uptime = time.time() - START_TIME
    now = datetime.now(timezone.utc).isoformat()
    
    logger.debug("Healthz probe called: uptime=%.2fs", uptime)
    
    return {
        "status": "ok",
        "uptime_seconds": int(uptime),
        "time": now,
        "version": "2.0"
    }
