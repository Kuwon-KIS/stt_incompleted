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

# Load configuration (try config.py first, fall back to defaults)
try:
    from .config import config
    logger_init = logging.getLogger(__name__)
    logger_init.info("loaded configuration from app/config.py")
except ImportError:
    # No config.py found, use defaults
    class config:
        CALL_TYPE = "vllm"
        LLM_URL = None
        LLM_AUTH_HEADER = None
        MODEL_PATH = None
        AGENT_NAME = None
        USE_STREAMING = False
        SFTP_HOST = None
        SFTP_PORT = 22
        SFTP_USERNAME = None
        SFTP_PASSWORD = None
        SFTP_KEY = None
        SFTP_CREDENTIAL_NAME = None
        SFTP_ROOT_PATH = "/"
        CALLBACK_URL = None
        CALLBACK_AUTH_HEADER = None
        TEMPLATE_NAME = None
        BATCH_CONCURRENCY = 4

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
        for template_file in TEMPLATE_DIR.glob("*"):
            # Skip files starting with . or directories
            if template_file.name.startswith('.') or template_file.is_dir():
                continue
            name = template_file.stem
            content = template_file.read_text(encoding="utf-8", errors='replace')
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
    host: str | None = None  # if None, use SFTP_HOST from config
    port: int | None = None  # if None, use SFTP_PORT from config
    # credential can come from request (for testing) or from env var (for production)
    username: str | None = None  # if None, use SFTP_USERNAME from config
    password: str | None = None  # if None, use SFTP_PASSWORD from config
    key: str | None = None  # if None, use SFTP_KEY from config
    # if credential_name is provided, load from env: SFTP_CRED_{credential_name}_{USERNAME,PASSWORD,KEY}
    credential_name: str | None = None  # if None, use SFTP_CREDENTIAL_NAME from config
    remote_path: str | None = None  # required when not using inline_text
    
    # LLM call configuration (all optional, defaults from config)
    call_type: str | None = None  # "vllm" or "agent", defaults to config.CALL_TYPE
    llm_url: str | None = None  # defaults to config.LLM_URL
    llm_auth_header: str | None = None  # defaults to config.LLM_AUTH_HEADER
    
    # vLLM specific
    model_path: str | None = None  # defaults to config.MODEL_PATH
    
    # Agent specific
    agent_name: str | None = None  # defaults to config.AGENT_NAME
    use_streaming: bool | None = None  # defaults to config.USE_STREAMING
    
    # callback url to forward model result
    callback_url: str | None = None  # defaults to config.CALLBACK_URL
    callback_auth_header: str | None = None  # defaults to config.CALLBACK_AUTH_HEADER
    
    # optional: provide inline text to bypass SFTP (useful for testing)
    inline_text: str | None = None
    
    # Template and prompt configuration
    template_name: str | None = None  # defaults to config.TEMPLATE_NAME
    question: str | None = None  # question/task to pass to the template
    custom_prompt: str | None = None  # if provided, use this instead of template
    
    def resolve_config(self):
        """Resolve all None values from config defaults."""
        # SFTP settings
        if self.host is None:
            self.host = config.SFTP_HOST
        if self.port is None:
            self.port = config.SFTP_PORT
        if self.username is None:
            self.username = config.SFTP_USERNAME
        if self.password is None:
            self.password = config.SFTP_PASSWORD
        if self.key is None:
            self.key = config.SFTP_KEY
        if self.credential_name is None:
            self.credential_name = config.SFTP_CREDENTIAL_NAME
        
        # LLM settings
        if self.call_type is None:
            self.call_type = config.CALL_TYPE
        if self.llm_url is None:
            self.llm_url = config.LLM_URL
        if self.llm_auth_header is None:
            self.llm_auth_header = config.LLM_AUTH_HEADER
        
        # vLLM specific
        if self.model_path is None:
            self.model_path = config.MODEL_PATH
        
        # Agent specific
        if self.agent_name is None:
            self.agent_name = config.AGENT_NAME
        if self.use_streaming is None:
            self.use_streaming = config.USE_STREAMING
        
        # Callback settings
        if self.callback_url is None:
            self.callback_url = config.CALLBACK_URL
        if self.callback_auth_header is None:
            self.callback_auth_header = config.CALLBACK_AUTH_HEADER
        
        # Template settings
        if self.template_name is None:
            self.template_name = config.TEMPLATE_NAME
        
        return self


def process_sync(req: ProcessRequest) -> dict:
    """Synchronous helper that does the SFTP read, calls vLLM, and posts callback.

    Returns a dict with result or raises Exceptions.
    """
    # Resolve config defaults first
    req = req.resolve_config()
    
    logger.info("process_sync start remote_path=%s host=%s", req.remote_path, req.host)

    # Resolve SFTP credentials: from env if credential_name given, else from request
    sftp_username = req.username
    sftp_password = req.password
    sftp_key = req.key
    
    if req.credential_name:
        cred_prefix = f"SFTP_CRED_{req.credential_name.upper()}"
        # Environment variables take precedence, fall back to request values
        env_username = os.getenv(f"{cred_prefix}_USERNAME")
        env_password = os.getenv(f"{cred_prefix}_PASSWORD")
        env_key = os.getenv(f"{cred_prefix}_KEY")
        
        if env_username is not None:
            sftp_username = env_username
        if env_password is not None:
            sftp_password = env_password
        if env_key is not None:
            sftp_key = env_key
        
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

    # 2) call vLLM/Agent with retry
    logger.info("calling LLM service type=%s", req.call_type)
    
    def is_retriable_status(status_code: int) -> bool:
        return 500 <= status_code < 600 or status_code == 429

    from urllib.parse import urlparse

    # internal sync handlers for mock endpoints
    def mock_vllm_sync(payload: dict) -> dict:
        text = payload.get("messages", [{}])[0].get("content", "") if "messages" in payload else payload.get("input", "")
        tokens = len(text.split())
        summary = text[:200]
        return {"choices": [{"message": {"content": summary}}], "usage": {"completion_tokens": tokens}}

    def mock_agent_sync(payload: dict) -> dict:
        user_query = payload.get("parameters", {}).get("user_query", "")
        return {"result": f"Agent processed: {user_query[:100]}"}

    def mock_callback_sync(payload: dict) -> dict:
        logger.info("mock callback sync received keys=%s", list(payload.keys()))
        return {"status": "accepted"}

    def http_post_with_retries(url: str, json_payload: dict, attempts: int = 3, backoff_base: float = 1.0, timeout: int = 30, auth_header: str | None = None):
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                # if target is local mock endpoint
                parsed = urlparse(url)
                # Check if this is a mock endpoint (includes v1/chat/completions path)
                is_mock_vllm = (parsed.hostname in ("localhost", "127.0.0.1") and 
                               parsed.port == 8002 and 
                               ("/mock/vllm" in parsed.path or parsed.path == "/mock/vllm"))
                is_mock_agent = (parsed.hostname in ("localhost", "127.0.0.1") and 
                                parsed.port == 8002 and 
                                ("/mock/agent" in parsed.path or parsed.path == "/mock/agent"))
                is_mock_callback = (parsed.hostname in ("localhost", "127.0.0.1") and 
                                   parsed.port == 8002 and 
                                   "/mock/callback" in parsed.path)
                
                if is_mock_vllm or is_mock_agent or is_mock_callback:
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

                    if is_mock_vllm:
                        resp = SimpleResp(mock_vllm_sync(json_payload))
                    elif is_mock_agent:
                        resp = SimpleResp(mock_agent_sync(json_payload))
                    else:
                        resp = SimpleResp(mock_callback_sync(json_payload))
                else:
                    headers = {"Content-Type": "application/json"}
                    if auth_header:
                        headers["Authorization"] = auth_header
                    resp = requests.post(url, json=json_payload, headers=headers, timeout=timeout)
                
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
        raise last_exc

    # Prepare LLM request based on call_type
    if req.call_type == "agent":
        if not req.agent_name:
            raise ValueError("agent_name is required for agent call_type")
        
        agent_url = f"{req.llm_url}/v2_2/api/agent/{req.agent_name}/messages"
        llm_payload = {
            "use_streaming": req.use_streaming,
            "parameters": {
                "user_query": prompt
            }
        }
        logger.info("calling agent=%s url=%s", req.agent_name, agent_url)
        llm_resp = http_post_with_retries(agent_url, llm_payload, attempts=3, backoff_base=1.0, timeout=30, auth_header=req.llm_auth_header)
        llm_output = llm_resp.json()
    else:  # vllm (default)
        if not req.model_path:
            raise ValueError("model_path is required for vllm call_type")
        
        vllm_url = f"{req.llm_url}/v1/chat/completions"
        llm_payload = {
            "model": req.model_path,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        logger.info("calling vLLM model=%s url=%s", req.model_path, vllm_url)
        llm_resp = http_post_with_retries(vllm_url, llm_payload, attempts=3, backoff_base=1.0, timeout=30, auth_header=req.llm_auth_header)
        llm_output = llm_resp.json()

    # 3) forward result to callback_url with retry
    logger.info("LLM returned; forwarding to callback %s", req.callback_url)
    cresp = http_post_with_retries(req.callback_url, {"llm_output": llm_output, "remote_path": req.remote_path, "call_type": req.call_type}, attempts=2, backoff_base=0.5, timeout=10, auth_header=req.callback_auth_header)
    logger.info("callback posted status=%s", cresp.status_code)

    return {"status": "ok", "llm_output": llm_output, "callback_status": cresp.status_code}


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
    # SFTP connection credentials (optional, defaults from config)
    host: str | None = None  # defaults to config.SFTP_HOST
    port: int | None = None  # defaults to config.SFTP_PORT
    username: str | None = None  # defaults to config.SFTP_USERNAME
    password: str | None = None  # defaults to config.SFTP_PASSWORD
    key: str | None = None  # defaults to config.SFTP_KEY
    credential_name: str | None = None  # defaults to config.SFTP_CREDENTIAL_NAME
    
    # Date range for batch processing (YYYYMMDD format)
    start_date: str  # e.g. "20260120" (required)
    end_date: str    # e.g. "20260127" (required)
    root_path: str | None = None  # defaults to config.SFTP_ROOT_PATH
    
    # LLM call configuration (optional, defaults from config)
    call_type: str | None = None  # defaults to config.CALL_TYPE
    llm_url: str | None = None  # defaults to config.LLM_URL
    llm_auth_header: str | None = None  # defaults to config.LLM_AUTH_HEADER
    
    # vLLM specific
    model_path: str | None = None  # defaults to config.MODEL_PATH
    
    # Agent specific
    agent_name: str | None = None  # defaults to config.AGENT_NAME
    use_streaming: bool | None = None  # defaults to config.USE_STREAMING
    
    # Callback settings
    callback_url: str | None = None  # defaults to config.CALLBACK_URL
    callback_auth_header: str | None = None  # defaults to config.CALLBACK_AUTH_HEADER
    
    # Template and prompt configuration
    template_name: str | None = None  # defaults to config.TEMPLATE_NAME
    question: str | None = None
    custom_prompt: str | None = None
    
    # Processing settings
    concurrency: int | None = None  # defaults to config.BATCH_CONCURRENCY
    
    def resolve_config(self):
        """Resolve all None values from config defaults."""
        # SFTP settings
        if self.host is None:
            self.host = config.SFTP_HOST
        if self.port is None:
            self.port = config.SFTP_PORT
        if self.username is None:
            self.username = config.SFTP_USERNAME
        if self.password is None:
            self.password = config.SFTP_PASSWORD
        if self.key is None:
            self.key = config.SFTP_KEY
        if self.credential_name is None:
            self.credential_name = config.SFTP_CREDENTIAL_NAME
        if self.root_path is None:
            self.root_path = config.SFTP_ROOT_PATH
        
        # LLM settings
        if self.call_type is None:
            self.call_type = config.CALL_TYPE
        if self.llm_url is None:
            self.llm_url = config.LLM_URL
        if self.llm_auth_header is None:
            self.llm_auth_header = config.LLM_AUTH_HEADER
        
        # vLLM specific
        if self.model_path is None:
            self.model_path = config.MODEL_PATH
        
        # Agent specific
        if self.agent_name is None:
            self.agent_name = config.AGENT_NAME
        if self.use_streaming is None:
            self.use_streaming = config.USE_STREAMING
        
        # Callback settings
        if self.callback_url is None:
            self.callback_url = config.CALLBACK_URL
        if self.callback_auth_header is None:
            self.callback_auth_header = config.CALLBACK_AUTH_HEADER
        
        # Template settings
        if self.template_name is None:
            self.template_name = config.TEMPLATE_NAME
        
        # Processing settings
        if self.concurrency is None:
            self.concurrency = config.BATCH_CONCURRENCY
        
        return self


@app.post("/process/batch")
async def process_batch(req: BatchProcessRequest):
    """Process all txt files within a date range.
    
    Discovers all date-named folders (YYYYMMDD) within the specified range,
    collects all .txt files from those folders, and processes them in parallel.
    """
    try:
        # Resolve config defaults first
        req = req.resolve_config()
        # Resolve SFTP credentials
        sftp_username = req.username
        sftp_password = req.password
        sftp_key = req.key
        
        if req.credential_name:
            cred_prefix = f"SFTP_CRED_{req.credential_name.upper()}"
            env_username = os.getenv(f"{cred_prefix}_USERNAME")
            env_password = os.getenv(f"{cred_prefix}_PASSWORD")
            env_key = os.getenv(f"{cred_prefix}_KEY")
            
            if env_username is not None:
                sftp_username = env_username
            if env_password is not None:
                sftp_password = env_password
            if env_key is not None:
                sftp_key = env_key
            
            logger.info("loaded SFTP credentials from env prefix=%s", cred_prefix)
        
        # Connect to SFTP and discover files
        logger.info("batch processing date range=%s to %s", req.start_date, req.end_date)
        client = SFTPClient(host=req.host, port=req.port, username=sftp_username, password=sftp_password, pkey=sftp_key)
        
        try:
            # Convert date strings to comparable integers
            start_date_int = int(req.start_date)
            end_date_int = int(req.end_date)
            
            # List all date-named directories
            all_dirs = client.list_directories(req.root_path)
            logger.debug("found %d directories in %s", len(all_dirs), req.root_path)
            
            # Filter directories by date range
            target_dates = []
            for dir_name in all_dirs:
                if len(dir_name) == 8 and dir_name.isdigit():
                    dir_date = int(dir_name)
                    if start_date_int <= dir_date <= end_date_int:
                        target_dates.append(dir_name)
            
            target_dates.sort()
            logger.info("found %d date folders in range [%s, %s]: %s", len(target_dates), req.start_date, req.end_date, target_dates)
            
            # Collect all files from target date folders (no extension filter)
            file_paths = []  # List of (date_folder, filename, full_path)
            for date_folder in target_dates:
                folder_path = f"{req.root_path}/{date_folder}".replace("//", "/")
                txt_files = client.list_files(folder_path, suffix=None)
                logger.debug("found %d files in %s", len(txt_files), folder_path)
                
                for filename in txt_files:
                    full_path = f"{folder_path}/{filename}"
                    file_paths.append((date_folder, filename, full_path))
            
            logger.info("total files to process: %d", len(file_paths))
            
            if not file_paths:
                logger.warning("no files found in date range")
                return {"results": [], "total": 0}
        
        finally:
            client.close()
        
        # Process files in parallel
        max_workers = max(1, req.concurrency)
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, (date_folder, filename, full_path) in enumerate(file_paths):
                # Create a ProcessRequest for this file
                process_req = ProcessRequest(
                    host=req.host,
                    port=req.port,
                    username=sftp_username,
                    password=sftp_password,
                    key=sftp_key,
                    credential_name=None,  # Already resolved above
                    remote_path=full_path,
                    call_type=req.call_type,
                    llm_url=req.llm_url,
                    llm_auth_header=req.llm_auth_header,
                    model_path=req.model_path,
                    agent_name=req.agent_name,
                    use_streaming=req.use_streaming,
                    callback_url=req.callback_url,
                    callback_auth_header=req.callback_auth_header,
                    template_name=req.template_name,
                    question=req.question,
                    custom_prompt=req.custom_prompt,
                    inline_text=None
                )
                
                future = executor.submit(process_sync, process_req)
                futures[future] = (idx, date_folder, filename)
            
            for fut in as_completed(futures):
                idx, date_folder, filename = futures[fut]
                try:
                    res = fut.result()
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": True,
                        "result": res
                    })
                except Exception as e:
                    logger.exception("batch file %s failed: %s", filename, e)
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": False,
                        "error": str(e)
                    })
        
        # Sort results by original index
        results.sort(key=lambda r: r["index"])
        return {"results": results, "total": len(file_paths)}
    
    except Exception as e:
        logger.exception("batch processing failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mock/vllm")
async def mock_vllm(body: dict):
    """Mock vLLM endpoint that mimics /v1/chat/completions format."""
    messages = body.get("messages", [{}])
    user_content = messages[0].get("content", "") if messages else ""
    tokens = len(user_content.split())
    summary = user_content[:200]
    return {
        "choices": [
            {
                "message": {
                    "content": summary,
                    "role": "assistant"
                }
            }
        ],
        "usage": {
            "completion_tokens": tokens,
            "prompt_tokens": tokens
        }
    }


@app.post("/mock/agent/{agent_name}/messages")
async def mock_agent(agent_name: str, body: dict):
    """Mock agent endpoint."""
    user_query = body.get("parameters", {}).get("user_query", "")
    return {
        "result": f"Agent '{agent_name}' processed: {user_query[:100]}",
        "agent": agent_name,
        "use_streaming": body.get("use_streaming", False)
    }


@app.post("/mock/callback")
async def mock_callback(body: dict):
    """Mock callback that just logs and returns accepted."""
    logger.info("mock callback received: keys=%s", list(body.keys()))
    return {"status": "accepted"}


async def run_batch_async(job_id: str, req: "BatchProcessRequest"):
    """Background task to execute batch processing and store results."""
    JOB_STORE[job_id]["status"] = "running"
    JOB_STORE[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    # Resolve config defaults first
    req = req.resolve_config()

    results = []
    try:
        # Resolve SFTP credentials
        sftp_username = req.username
        sftp_password = req.password
        sftp_key = req.key
        
        if req.credential_name:
            cred_prefix = f"SFTP_CRED_{req.credential_name.upper()}"
            env_username = os.getenv(f"{cred_prefix}_USERNAME")
            env_password = os.getenv(f"{cred_prefix}_PASSWORD")
            env_key = os.getenv(f"{cred_prefix}_KEY")
            
            if env_username is not None:
                sftp_username = env_username
            if env_password is not None:
                sftp_password = env_password
            if env_key is not None:
                sftp_key = env_key
        
        # Connect to SFTP and discover files
        logger.info("batch job %s: processing date range %s to %s", job_id, req.start_date, req.end_date)
        client = SFTPClient(host=req.host, port=req.port, username=sftp_username, password=sftp_password, pkey=sftp_key)
        
        try:
            # Convert date strings to comparable integers
            start_date_int = int(req.start_date)
            end_date_int = int(req.end_date)
            
            # List all date-named directories
            all_dirs = client.list_directories(req.root_path)
            
            # Filter directories by date range
            target_dates = []
            for dir_name in all_dirs:
                if len(dir_name) == 8 and dir_name.isdigit():
                    dir_date = int(dir_name)
                    if start_date_int <= dir_date <= end_date_int:
                        target_dates.append(dir_name)
            
            target_dates.sort()
            logger.info("batch job %s: found %d date folders", job_id, len(target_dates))
            
            # Collect all files from target date folders (no extension filter)
            file_paths = []
            for date_folder in target_dates:
                folder_path = f"{req.root_path}/{date_folder}".replace("//", "/")
                txt_files = client.list_files(folder_path, suffix=None)
                
                for filename in txt_files:
                    full_path = f"{folder_path}/{filename}"
                    file_paths.append((date_folder, filename, full_path))
            
            logger.info("batch job %s: total files to process: %d", job_id, len(file_paths))
        
        finally:
            client.close()
        
        # Process files in parallel
        max_workers = max(1, req.concurrency)
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for idx, (date_folder, filename, full_path) in enumerate(file_paths):
                process_req = ProcessRequest(
                    host=req.host,
                    port=req.port,
                    username=sftp_username,
                    password=sftp_password,
                    key=sftp_key,
                    credential_name=None,
                    remote_path=full_path,
                    call_type=req.call_type,
                    llm_url=req.llm_url,
                    llm_auth_header=req.llm_auth_header,
                    model_path=req.model_path,
                    agent_name=req.agent_name,
                    use_streaming=req.use_streaming,
                    callback_url=req.callback_url,
                    callback_auth_header=req.callback_auth_header,
                    template_name=req.template_name,
                    question=req.question,
                    custom_prompt=req.custom_prompt,
                    inline_text=None
                )
                
                future = executor.submit(process_sync, process_req)
                futures[future] = (idx, date_folder, filename)
            
            for fut in as_completed(futures):
                idx, date_folder, filename = futures[fut]
                try:
                    res = fut.result()
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": True,
                        "result": res
                    })
                except Exception as e:
                    logger.exception("batch job %s file %s failed: %s", job_id, filename, e)
                    results.append({
                        "index": idx,
                        "date": date_folder,
                        "filename": filename,
                        "success": False,
                        "error": str(e)
                    })
        
        results.sort(key=lambda r: r["index"])
    
    except Exception as e:
        logger.exception("batch job %s failed: %s", job_id, e)
        JOB_STORE[job_id]["error"] = str(e)
    
    JOB_STORE[job_id]["results"] = results
    JOB_STORE[job_id]["status"] = "completed"
    JOB_STORE[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info("batch job %s completed with %d results", job_id, len(results))


@app.post("/process/batch/submit")
async def process_batch_submit(req: BatchProcessRequest):
    """Submit a batch job and return job_id. The job runs asynchronously in background.
    
    Processes all txt files in date-named folders within the specified date range.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    JOB_STORE[job_id] = {
        "status": "pending", 
        "created_at": now, 
        "results": None, 
        "started_at": None, 
        "completed_at": None,
        "error": None,
        "date_range": f"{req.start_date} to {req.end_date}"
    }
    logger.info("batch job %s submitted for date range %s to %s", job_id, req.start_date, req.end_date)

    # Schedule background task (fire and forget)
    asyncio.create_task(run_batch_async(job_id, req))

    return {"job_id": job_id, "status": "submitted", "date_range": f"{req.start_date} to {req.end_date}"}


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
        "date_range": job.get("date_range"),
        "error": job.get("error"),
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
