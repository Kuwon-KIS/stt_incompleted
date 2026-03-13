"""
Web UI endpoints serving static HTML.
"""

import logging
import pathlib

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["web"])

# Static directory path
STATIC_DIR = pathlib.Path(__file__).parent.parent / "static"


@router.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web UI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    
    return index_file.read_text(encoding="utf-8")


@router.get("/ui", response_class=HTMLResponse)
async def ui():
    """Alias for root - serve the main web UI."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Web UI not found")
    
    return index_file.read_text(encoding="utf-8")
