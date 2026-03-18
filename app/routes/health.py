"""
Health check endpoints for service monitoring.
"""

import time
import logging
from fastapi import APIRouter
from ..config import config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])
START_TIME = time.time()


@router.get("/health")
async def health_check():
    """Simple health check endpoint."""
    logger.debug("Health check called")
    return {"status": "ok"}


@router.get("/healthz")
async def healthz():
    """Kubernetes-style liveness/readiness probe."""
    uptime = int(time.time() - START_TIME)
    logger.debug("Healthz probe called: uptime=%ds", uptime)
    
    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "app_env": config.APP_ENV
    }
