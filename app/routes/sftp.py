"""
SFTP management endpoint routes.
"""

import logging

from fastapi import APIRouter, HTTPException

from ..models import SFTPRequest
from ..sftp_client import SFTPClient, create_sftp_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sftp", tags=["sftp"])


@router.post("/list")
async def sftp_list(req: SFTPRequest):
    """List files in an SFTP directory."""
    try:
        logger.info("sftp list request host=%s path=%s", req.host, req.path)
        client = create_sftp_client(host=req.host, port=req.port, username=req.username,
                                    password=req.password, pkey=req.key)
        files = client.listdir(req.path)
        client.close()
        logger.info("sftp list success host=%s count=%d", req.host, len(files))
        return {"files": files}
    except Exception as e:
        logger.exception("sftp list failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) 
