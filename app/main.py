from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import logging
import time
import asyncio
import os
import pathlib
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import uuid
from .sftp_client import SFTPClient

logger = logging.getLogger(__name__)
# improve log format with timestamp
logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s %(message)s', level=logging.INFO)

app = FastAPI()
START_TIME = time.time()

# In-memory job store for batch processing: job_id -> {"status": "pending|running|completed", "results": [...], ...}
JOB_STORE: Dict[str, Any] = {}

# Template store: template_name -> template_content (loaded from files)
TEMPLATE_STORE: Dict[str, str] = {}
TEMPLATE_DIR = pathlib.Path(__file__).parent / "templates"

def load_templates():
    """Load all templates from the templates directory into memory."""
    global TEMPLATE_STORE
    TEMPLATE_STORE = {}
    if TEMPLATE_DIR.exists():
        for template_file in TEMPLATE_DIR.glob("*.txt"):
            name = template_file.stem
            content = template_file.read_text(encoding="utf-8")
            TEMPLATE_STORE[name] = content
            logger.info("loaded template: %s", name)
    else:
        logger.warning("templates directory not found at %s", TEMPLATE_DIR)

# Load templates on startup
load_templates()

class ProxyRequest(BaseModel):
    method: str = "GET"
    url: str
    headers: dict | None = None
    data: dict | None = None

@app.get("/")
async def read_root():
    logger.info("health root called")
    return {"message": "ok"}


@app.get("/healthz")
async def healthz():
    """Liveness/Readiness style health endpoint with uptime."""
    uptime = time.time() - START_TIME
    now = datetime.now(timezone.utc).isoformat()
    logger.info("healthz called: uptime=%.2fs", uptime)
    return {"status": "ok", "uptime_seconds": int(uptime), "time": now}

@app.post("/proxy")
async def proxy(req: ProxyRequest):
    try:
        logger.info("proxy request to %s method=%s", req.url, req.method)
        resp = requests.request(req.method, req.url, headers=req.headers, json=req.data, timeout=10)
        logger.info("proxy response status=%s for %s", resp.status_code, req.url)
        return {"status_code": resp.status_code, "headers": dict(resp.headers), "text": resp.text}
    except Exception as e:
        logger.exception("proxy failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

class SFTPRequest(BaseModel):
    host: str
    port: int = 22
    username: str
    password: str | None = None
    key: str | None = None
    path: str = "."

@app.post("/sftp/list")
async def sftp_list(req: SFTPRequest):
    try:
        logger.info("sftp list request host=%s path=%s", req.host, req.path)
        client = SFTPClient(host=req.host, port=req.port, username=req.username, password=req.password, pkey=req.key)
        files = client.listdir(req.path)
        client.close()
        logger.info("sftp list success host=%s count=%d", req.host, len(files))
        return {"files": files}
    except Exception as e:
        logger.exception("sftp list failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class ProcessRequest(BaseModel):
    # sftp target file
    host: str
    port: int = 22
    # credential can come from request (for testing) or from env var (for production)
    username: str | None = None
    password: str | None = None
    key: str | None = None
    # if credential_name is provided, load from env: SFTP_CRED_{credential_name}_{USERNAME,PASSWORD,KEY}
    credential_name: str | None = None
    remote_path: str
    # vLLM endpoint to call (expects POST with {"input": <text>})
    vllm_url: str
    vllm_auth_header: str | None = None  # e.g. "Bearer <token>"
    # callback url to forward model result
    callback_url: str
    callback_auth_header: str | None = None  # e.g. "Bearer <token>"
    # optional: provide inline text to bypass SFTP (useful for testing)
    inline_text: str | None = None
    # Template and prompt configuration
    template_name: str | None = None  # e.g. "qwen_default", "gpt4mini_default"
    question: str | None = None  # question/task to pass to the template
    custom_prompt: str | None = None  # if provided, use this instead of template


def process_sync(req: ProcessRequest) -> dict:
    """Synchronous helper that does the SFTP read, calls vLLM, and posts callback.

    Returns a dict with result or raises Exceptions.
    """
    logger.info("process_sync start remote_path=%s host=%s", req.remote_path, req.host)

    # Resolve SFTP credentials: from env if credential_name given, else from request
    sftp_username = req.username
    sftp_password = req.password
    sftp_key = req.key
    if req.credential_name:
        cred_prefix = f"SFTP_CRED_{req.credential_name.upper()}"
        sftp_username = os.getenv(f"{cred_prefix}_USERNAME") or sftp_username
        sftp_password = os.getenv(f"{cred_prefix}_PASSWORD") or sftp_password
        sftp_key = os.getenv(f"{cred_prefix}_KEY") or sftp_key
        logger.info("loaded SFTP credentials from env prefix=%s", cred_prefix)

    # 1) fetch file over SFTP unless inline_text provided
    if req.inline_text is not None:
        text = req.inline_text
        logger.info("using inline_text length=%d", len(text))
    else:
        client = SFTPClient(host=req.host, port=req.port, username=sftp_username, password=sftp_password, pkey=sftp_key)
        try:
            text = client.read_file(req.remote_path)
        finally:
            client.close()

    logger.info("fetched remote file length=%d", len(text) if text is not None else 0)

    # Build the prompt for LLM
    if req.custom_prompt:
        prompt = req.custom_prompt
        logger.info("using custom_prompt length=%d", len(prompt))
    elif req.template_name:
        if req.template_name not in TEMPLATE_STORE:
            raise ValueError(f"Template '{req.template_name}' not found. Available: {list(TEMPLATE_STORE.keys())}")
        template = TEMPLATE_STORE[req.template_name]
        # Replace {text} and {question} placeholders
        prompt = template.format(text=text, question=req.question or "")
        logger.info("built prompt from template=%s length=%d", req.template_name, len(prompt))
    else:
        # Default: use text as-is
        prompt = text
        logger.info("using raw text as prompt")

    # 2) call vLLM with simple retry
    logger.info("calling vLLM url=%s", req.vllm_url)
    def is_retriable_status(status_code: int) -> bool:
        return 500 <= status_code < 600 or status_code == 429

    from urllib.parse import urlparse

    # internal sync handlers for mock endpoints to avoid HTTP loopback
    def mock_vllm_sync(payload: dict) -> dict:
        text = payload.get("input", "")
        tokens = len(text.split())
        summary = text[:200]
        return {"summary": summary, "tokens": tokens}

    def mock_callback_sync(payload: dict) -> dict:
        logger.info("mock callback sync received keys=%s", list(payload.keys()))
        return {"status": "accepted"}

    def http_post_with_retries(url: str, json_payload: dict, attempts: int = 3, backoff_base: float = 1.0, timeout: int = 30, auth_header: str | None = None):
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                # if target is local mock endpoint, call sync handler directly to avoid loopback
                parsed = urlparse(url)
                netloc = f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
                if parsed.hostname in ("localhost", "127.0.0.1") and parsed.port == 8002 and parsed.path in ("/mock/vllm", "/mock/callback"):
                    # Simple in-process response object that mimics requests.Response enough for our use
                    class SimpleResp:
                        def __init__(self, json_obj, status_code: int = 200, headers: dict | None = None):
                            self._json = json_obj
                            self.status_code = status_code
                            self.headers = headers or {"content-type": "application/json"}

                        def json(self):
                            return self._json

                        @property
                        def text(self):
                            return str(self._json)

                        def raise_for_status(self):
                            if self.status_code >= 400:
                                raise requests.HTTPError(f"status={self.status_code}")

                    if parsed.path == "/mock/vllm":
                        resp = SimpleResp(mock_vllm_sync(json_payload))
                    else:
                        resp = SimpleResp(mock_callback_sync(json_payload))
                else:
                    headers = {}
                    if auth_header:
                        headers["Authorization"] = auth_header
                    resp = requests.post(url, json=json_payload, headers=headers if headers else None, timeout=timeout)
                if is_retriable_status(resp.status_code):
                    last_exc = requests.HTTPError(f"status={resp.status_code}")
                    logger.warning("retriable response %s from %s (attempt %d)", resp.status_code, url, attempt)
                    time.sleep(backoff_base * (2 ** (attempt - 1)))
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                last_exc = e
                logger.warning("http attempt %d failed for %s: %s", attempt, url, e)
                if attempt < attempts:
                    time.sleep(backoff_base * (2 ** (attempt - 1)))
        # all attempts failed
        raise last_exc

    vresp = http_post_with_retries(req.vllm_url, {"input": prompt}, attempts=3, backoff_base=1.0, timeout=30, auth_header=req.vllm_auth_header)
    model_output = vresp.json() if vresp.headers.get("content-type", "").startswith("application/json") else {"text": vresp.text}

    # 3) forward result to callback_url with retry
    logger.info("vLLM returned; forwarding to callback %s", req.callback_url)
    cresp = http_post_with_retries(req.callback_url, {"model_output": model_output, "remote_path": req.remote_path}, attempts=2, backoff_base=0.5, timeout=10, auth_header=req.callback_auth_header)
    logger.info("callback posted status=%s", cresp.status_code)

    return {"status": "ok", "model_output": model_output, "callback_status": cresp.status_code}


@app.post("/process")
async def process(req: ProcessRequest):
    """Async wrapper around process_sync using the default thread pool."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, process_sync, req)
        return result
    except requests.HTTPError as he:
        logger.exception("Upstream HTTP error: %s", he)
        raise HTTPException(status_code=502, detail=f"Upstream HTTP error: {he}")
    except Exception as e:
        logger.exception("processing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class BatchProcessRequest(BaseModel):
    items: List[ProcessRequest]
    concurrency: int = 4


@app.post("/process/batch")
async def process_batch(req: BatchProcessRequest):
    """Process multiple items in parallel using ThreadPoolExecutor.

    Returns per-item results with success flag and details.
    """
    if not req.items:
        return {"results": []}

    max_workers = max(1, req.concurrency)
    logger.info("batch processing %d items with concurrency=%d", len(req.items), max_workers)

    results = []
    loop = asyncio.get_event_loop()

    # Run in a thread pool to allow blocking IO
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_sync, item): idx for idx, item in enumerate(req.items)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                res = fut.result()
                results.append({"index": idx, "success": True, "result": res})
            except Exception as e:
                logger.exception("batch item %d failed: %s", idx, e)
                results.append({"index": idx, "success": False, "error": str(e)})

    # sort results by original index
    results.sort(key=lambda r: r["index"]) 
    return {"results": results}


@app.post("/mock/vllm")
async def mock_vllm(body: dict):
    """Simple mock vLLM that echoes the first 200 chars and counts tokens (rough)."""
    text = body.get("input", "")
    # naive token count
    tokens = len(text.split())
    summary = text[:200]
    return {"summary": summary, "tokens": tokens}


@app.post("/mock/callback")
async def mock_callback(body: dict):
    """Mock callback that just logs and returns accepted."""
    logger.info("mock callback received: keys=%s", list(body.keys()))
    return {"status": "accepted"}


async def run_batch_async(job_id: str, req: "BatchProcessRequest"):
    """Background task to execute batch processing and store results."""
    JOB_STORE[job_id]["status"] = "running"
    JOB_STORE[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    results = []
    max_workers = max(1, req.concurrency)
    logger.info("batch job %s: processing %d items with concurrency=%d", job_id, len(req.items), max_workers)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_sync, item): idx for idx, item in enumerate(req.items)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                res = fut.result()
                results.append({"index": idx, "success": True, "result": res})
            except Exception as e:
                logger.exception("batch job %s item %d failed: %s", job_id, idx, e)
                results.append({"index": idx, "success": False, "error": str(e)})

    results.sort(key=lambda r: r["index"])
    JOB_STORE[job_id]["results"] = results
    JOB_STORE[job_id]["status"] = "completed"
    JOB_STORE[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("batch job %s completed", job_id)


@app.post("/process/batch/submit")
async def process_batch_submit(req: BatchProcessRequest):
    """Submit a batch job and return job_id. The job runs asynchronously in background."""
    if not req.items:
        return {"job_id": None, "message": "no items"}

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    JOB_STORE[job_id] = {"status": "pending", "created_at": now, "results": None, "started_at": None, "completed_at": None}
    logger.info("batch job %s submitted with %d items", job_id, len(req.items))

    # Schedule background task (fire and forget)
    asyncio.create_task(run_batch_async(job_id, req))

    return {"job_id": job_id, "status": "submitted"}


@app.get("/process/batch/status/{job_id}")
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
        "results": job.get("results") if job["status"] == "completed" else None,
    }


# ============= Template Management API =============

@app.get("/templates")
async def list_templates():
    """List all available prompt templates."""
    return {
        "templates": list(TEMPLATE_STORE.keys()),
        "count": len(TEMPLATE_STORE),
    }


@app.get("/templates/{template_name}")
async def get_template(template_name: str):
    """Get the content of a specific template."""
    if template_name not in TEMPLATE_STORE:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

    return {
        "name": template_name,
        "content": TEMPLATE_STORE[template_name],
    }


class TemplateCreateRequest(BaseModel):
    name: str
    content: str


@app.post("/templates")
async def create_template(req: TemplateCreateRequest):
    """Create or update a template."""
    if not req.name or not req.content:
        raise HTTPException(status_code=400, detail="name and content are required")

    # Save to memory
    TEMPLATE_STORE[req.name] = req.content

    # Also save to file for persistence
    template_file = TEMPLATE_DIR / f"{req.name}.txt"
    template_file.write_text(req.content, encoding="utf-8")
    logger.info("created/updated template: %s", req.name)

    return {"name": req.name, "status": "created"}


@app.delete("/templates/{template_name}")
async def delete_template(template_name: str):
    """Delete a template."""
    if template_name not in TEMPLATE_STORE:
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

    del TEMPLATE_STORE[template_name]

    # Also delete from file
    template_file = TEMPLATE_DIR / f"{template_name}.txt"
    if template_file.exists():
        template_file.unlink()
        logger.info("deleted template: %s", template_name)

    return {"name": template_name, "status": "deleted"}


@app.post("/templates/refresh")
async def refresh_templates():
    """Reload all templates from disk."""
    load_templates()
    return {
        "status": "refreshed",
        "templates": list(TEMPLATE_STORE.keys()),
        "count": len(TEMPLATE_STORE),
    }
