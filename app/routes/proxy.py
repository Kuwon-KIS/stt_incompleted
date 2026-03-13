"""
Proxy endpoint routes for testing and debugging.
"""

import logging
import requests

from fastapi import APIRouter, HTTPException

from ..models import ProxyRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.post("")
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
