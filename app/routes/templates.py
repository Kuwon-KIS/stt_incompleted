"""
Template management endpoint routes.
Handles CRUD operations for prompt templates.
"""

import logging
import pathlib
from typing import Dict

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])

# Template store (shared reference to main app's TEMPLATE_STORE)
# This will be injected from main.py
TEMPLATE_STORE: Dict[str, str] = {}
TEMPLATE_DIR: pathlib.Path = None


def set_template_store(template_store: Dict[str, str], template_dir: pathlib.Path):
    """Inject template store and directory from main app."""
    global TEMPLATE_STORE, TEMPLATE_DIR
    TEMPLATE_STORE = template_store
    TEMPLATE_DIR = template_dir


@router.get("")
async def list_templates():
    """List all available prompt templates."""
    return {
        "templates": list(TEMPLATE_STORE.keys()),
        "count": len(TEMPLATE_STORE),
    }


@router.get("/{template_name}")
async def get_template(template_name: str):
    """Get the content of a specific template."""
    if template_name not in TEMPLATE_STORE:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

    return {
        "name": template_name,
        "content": TEMPLATE_STORE[template_name],
    }


@router.post("")
async def create_template(req: dict):
    """Create or update a template.
    
    Request body:
    {
        "name": "template_name",
        "content": "template content with {text} and {question} placeholders"
    }
    """
    name = req.get("name")
    content = req.get("content")
    
    if not name or not content:
        raise HTTPException(status_code=400, detail="name and content are required")

    # Save to memory
    TEMPLATE_STORE[name] = content

    # Also save to file for persistence
    if TEMPLATE_DIR:
        template_file = TEMPLATE_DIR / f"{name}.txt"
        template_file.write_text(content, encoding="utf-8")
        logger.info("created/updated template: %s", name)

    return {"name": name, "status": "created"}


@router.delete("/{template_name}")
async def delete_template(template_name: str):
    """Delete a template."""
    if template_name not in TEMPLATE_STORE:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

    del TEMPLATE_STORE[template_name]

    # Also delete from file
    if TEMPLATE_DIR:
        template_file = TEMPLATE_DIR / f"{template_name}.txt"
        if template_file.exists():
            template_file.unlink()
            logger.info("deleted template: %s", template_name)

    return {"name": template_name, "status": "deleted"}


@router.post("/refresh")
async def refresh_templates():
    """Reload all templates from disk."""
    global TEMPLATE_STORE
    
    if not TEMPLATE_DIR:
        raise HTTPException(status_code=500, detail="Template directory not configured")
    
    TEMPLATE_STORE.clear()
    
    if TEMPLATE_DIR.exists():
        for template_file in TEMPLATE_DIR.glob("*"):
            if template_file.name.startswith('.') or template_file.is_dir():
                continue
            name = template_file.stem
            content = template_file.read_text(encoding="utf-8", errors='replace')
            TEMPLATE_STORE[name] = content
            logger.info("loaded template: %s", name)
    
    return {
        "status": "refreshed",
        "templates": list(TEMPLATE_STORE.keys()),
        "count": len(TEMPLATE_STORE),
    }
