"""
Health check endpoints for service monitoring.
"""

import time
import logging
import asyncio
from fastapi import APIRouter
from ..config import config
from ..sftp_client import create_sftp_client
import requests

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


async def check_sftp_connection() -> dict:
    """Check SFTP server connectivity.
    
    Returns:
        {
            "connected": bool,
            "status": "ok" | "error" | "unavailable" | "mock",
            "host": str,
            "port": int,
            "error": str (if any)
        }
    """
    try:
        # LOCAL environment uses Mock SFTP - no real connection needed
        if config.APP_ENV == "local":
            return {
                "connected": True,
                "status": "mock",
                "host": "mock",
                "port": None,
                "error": None,
                "message": "Mock Mode - 실제 연결 없음"
            }
        
        if not config.SFTP_HOST:
            return {
                "connected": False,
                "status": "unavailable",
                "host": None,
                "port": None,
                "error": "SFTP_HOST not configured"
            }
        
        # Attempt to create and check SFTP connection
        client = create_sftp_client(
            host=config.SFTP_HOST,
            port=config.SFTP_PORT,
            username=config.SFTP_USERNAME,
            password=config.SFTP_PASSWORD,
            pkey=config.SFTP_KEY,
            timeout=5  # Short timeout for health check
        )
        
        # Test connection by listing root
        client.listdir("/")
        client.close()
        
        return {
            "connected": True,
            "status": "ok",
            "host": config.SFTP_HOST,
            "port": config.SFTP_PORT,
            "error": None
        }
        
    except Exception as e:
        logger.warning("SFTP connection check failed: %s", str(e))
        return {
            "connected": False,
            "status": "error",
            "host": config.SFTP_HOST,
            "port": config.SFTP_PORT,
            "error": str(e)
        }


async def check_agent_connection() -> dict:
    """Check AI Agent API connectivity.
    
    Returns:
        {
            "connected": bool,
            "status": "ok" | "error" | "unavailable" | "mock",
            "url": str,
            "error": str (if any)
        }
    """
    try:
        if not config.AGENT_URL:
            return {
                "connected": False,
                "status": "unavailable",
                "url": None,
                "error": "AGENT_URL not configured"
            }
        
        # LOCAL environment uses Mock Agent - mark as mock mode
        if config.APP_ENV == "local":
            return {
                "connected": True,
                "status": "mock",
                "url": config.AGENT_URL,
                "error": None,
                "message": "Mock Mode - 로컬 테스트용"
            }
        
        # For dev/prod environments, check actual connection
        # Try to call the agent endpoint
        response = requests.get(
            config.AGENT_URL,
            timeout=5,
            headers={"Authorization": config.AGENT_AUTH_HEADER} if config.AGENT_AUTH_HEADER else {}
        )
        
        # Treat 404 as acceptable (endpoint exists, just no GET method)
        if response.status_code in [200, 404]:
            return {
                "connected": True,
                "status": "ok",
                "url": config.AGENT_URL,
                "error": None
            }
        else:
            return {
                "connected": False,
                "status": "error",
                "url": config.AGENT_URL,
                "error": f"HTTP {response.status_code}"
            }
            
    except requests.exceptions.ConnectionError as e:
        logger.warning("Agent connection check failed: %s", str(e))
        return {
            "connected": False,
            "status": "error",
            "url": config.AGENT_URL,
            "error": f"Connection error: {str(e)}"
        }
    except Exception as e:
        logger.warning("Agent connection check error: %s", str(e))
        return {
            "connected": False,
            "status": "error",
            "url": config.AGENT_URL,
            "error": str(e)
        }


@router.get("/api/system-status")
async def system_status():
    """Get system deployment status including external service connectivity.
    
    Returns info about SFTP and Agent connections for dashboard display.
    """
    try:
        # Run checks concurrently
        sftp_status, agent_status = await asyncio.gather(
            asyncio.to_thread(lambda: asyncio.run(check_sftp_connection())),
            check_agent_connection(),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(sftp_status, Exception):
            sftp_status = {
                "connected": False,
                "status": "error",
                "host": config.SFTP_HOST,
                "port": config.SFTP_PORT,
                "error": str(sftp_status)
            }
        
        if isinstance(agent_status, Exception):
            agent_status = {
                "connected": False,
                "status": "error",
                "url": config.AGENT_URL,
                "error": str(agent_status)
            }
        
        uptime = int(time.time() - START_TIME)
        
        return {
            "status": "ok",
            "app_env": config.APP_ENV,
            "uptime_seconds": uptime,
            "deployment": {
                "sftp": sftp_status,
                "agent": agent_status,
                "call_type": config.CALL_TYPE
            }
        }
        
    except Exception as e:
        logger.exception("System status check failed: %s", e)
        return {
            "status": "error",
            "app_env": config.APP_ENV,
            "error": str(e),
            "deployment": {
                "sftp": {"connected": False, "status": "error"},
                "agent": {"connected": False, "status": "error"}
            }
        }
