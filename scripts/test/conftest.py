"""
Pytest configuration and fixtures for STT processing system tests.
"""

import sys
import pathlib

# Add project root to Python path so we can import app module
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from httpx import AsyncClient
from fastapi.testclient import TestClient
from app.main import app, TEMPLATE_STORE, JOB_STORE
from app.models import ProcessRequest, BatchProcessRequest


@pytest.fixture(scope="function")
def client():
    """FastAPI test client."""
    from starlette.testclient import TestClient as StarletteTestClient
    return StarletteTestClient(app)


@pytest.fixture(scope="function")
def event_loop():
    """Event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_stores():
    """Reset global stores before each test."""
    global TEMPLATE_STORE, JOB_STORE
    TEMPLATE_STORE.clear()
    TEMPLATE_STORE["test_template"] = "Test content: {text}"
    TEMPLATE_STORE["generic"] = "Generic template: {text}"
    
    JOB_STORE.clear()
    yield
    TEMPLATE_STORE.clear()
    JOB_STORE.clear()


@pytest.fixture
def mock_sftp_client():
    """Mock SFTP client."""
    mock = AsyncMock()
    mock.listdir = Mock(return_value=["file1.txt", "file2.txt"])
    mock.list_directories = Mock(return_value=["20260301", "20260302"])
    mock.list_files = Mock(return_value=["file1.txt", "file2.txt"])
    mock.read_file = Mock(return_value="Sample text content")
    mock.close = Mock()
    return mock


@pytest.fixture
def mock_detection_result():
    """Mock detection result from vLLM/Agent."""
    return {
        "strategy": "vllm",
        "detected_issues": [
            {"issue": "missing_product_name", "confidence": 0.95},
            {"issue": "missing_price", "confidence": 0.87}
        ],
        "summary": "Found 2 issues in transcription",
        "raw_response": "Mock response from LLM"
    }


@pytest.fixture
def sample_process_request():
    """Sample ProcessRequest for testing."""
    return ProcessRequest(
        host="localhost",
        port=22,
        username="test_user",
        password="test_pass",
        key=None,
        credential_name=None,
        remote_path="/uploads/20260301/file1.txt",
        inline_text=None,
        call_type="vllm",
        llm_url="http://localhost:8001/v1/chat/completions",
        llm_auth_header=None,
        model_path="test_model",
        agent_name=None,
        use_streaming=False,
        callback_url=None,
        callback_auth_header=None,
        template_name="generic",
        question=None,
        custom_prompt=None
    )


@pytest.fixture
def sample_batch_request():
    """Sample BatchProcessRequest for testing."""
    return BatchProcessRequest(
        host="localhost",
        port=22,
        username="test_user",
        password="test_pass",
        key=None,
        credential_name=None,
        root_path="/uploads",
        start_date="20260301",
        end_date="20260305",
        call_type="vllm",
        llm_url="http://localhost:8001/v1/chat/completions",
        llm_auth_header=None,
        model_path="test_model",
        agent_name=None,
        use_streaming=False,
        callback_url=None,
        callback_auth_header=None,
        template_name="generic",
        question=None,
        custom_prompt=None,
        concurrency=2
    )


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for callback testing."""
    with patch("requests.post") as mock:
        mock.return_value.status_code = 200
        mock.return_value.raise_for_status = Mock()
        yield mock


@pytest.fixture
def mock_detector():
    """Mock detection strategy."""
    mock = AsyncMock()
    mock.detect = AsyncMock(return_value={
        "strategy": "vllm",
        "detected_issues": [
            {"issue": "missing_product", "confidence": 0.92}
        ]
    })
    return mock
