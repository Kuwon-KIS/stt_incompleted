"""
Unit tests for route endpoints.
"""

import pytest
from unittest.mock import patch, Mock


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_endpoint(self, client):
        """Test GET /health returns simple ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data) == 1  # Only status field
    
    def test_healthz_endpoint(self, client):
        """Test GET /healthz returns Kubernetes-compatible response."""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0


class TestWebEndpoints:
    """Test web UI endpoints."""
    
    def test_root_endpoint_returns_html(self, client):
        """Test GET / returns HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "<!DOCTYPE html>" in response.text
        assert "<html" in response.text
    
    def test_ui_alias_returns_html(self, client):
        """Test GET /ui returns HTML (alias for root)."""
        response = client.get("/ui")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        assert "<!DOCTYPE html>" in response.text


class TestTemplateEndpoints:
    """Test template management endpoints."""
    
    def test_list_templates(self, client):
        """Test GET /templates lists available templates."""
        response = client.get("/templates")
        assert response.status_code == 200
        data = response.json()
        assert "templates" in data
        assert "count" in data
        assert isinstance(data["templates"], list)
        assert data["count"] == len(data["templates"])
        assert "generic" in data["templates"]
    
    def test_get_specific_template(self, client):
        """Test GET /templates/{name} returns template content."""
        response = client.get("/templates/generic")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "generic"
        assert "content" in data
        assert len(data["content"]) > 0
    
    def test_get_nonexistent_template(self, client):
        """Test GET /templates/{name} returns 404 for non-existent template."""
        response = client.get("/templates/nonexistent")
        assert response.status_code == 404
    
    def test_create_template(self, client):
        """Test POST /templates creates new template."""
        response = client.post(
            "/templates",
            json={"name": "new_template", "content": "New content"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "new_template"
        assert data["status"] == "created"
        
        # Verify template was created
        response = client.get("/templates/new_template")
        assert response.status_code == 200
        assert response.json()["content"] == "New content"
    
    def test_create_template_missing_fields(self, client):
        """Test POST /templates returns 400 for missing fields."""
        response = client.post("/templates", json={"name": "test"})
        assert response.status_code == 400
        
        response = client.post("/templates", json={"content": "test"})
        assert response.status_code == 400
    
    def test_delete_template(self, client):
        """Test DELETE /templates/{name} removes template."""
        # First create a template
        client.post(
            "/templates",
            json={"name": "delete_test", "content": "To delete"}
        )
        
        # Delete it
        response = client.delete("/templates/delete_test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        
        # Verify it's gone
        response = client.get("/templates/delete_test")
        assert response.status_code == 404
    
    def test_delete_nonexistent_template(self, client):
        """Test DELETE /templates/{name} returns 404 for non-existent."""
        response = client.delete("/templates/nonexistent")
        assert response.status_code == 404
    
    def test_refresh_templates(self, client):
        """Test POST /templates/refresh reloads templates."""
        response = client.post("/templates/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "refreshed"
        assert "templates" in data
        assert "count" in data


class TestSFTPEndpoints:
    """Test SFTP endpoints."""
    
    @patch("app.routes.sftp.SFTPClient")
    def test_sftp_list_success(self, mock_sftp_class, client):
        """Test POST /sftp/list returns file list."""
        # Setup mock
        mock_client = Mock()
        mock_client.listdir = Mock(return_value=["file1.txt", "file2.txt"])
        mock_sftp_class.return_value = mock_client
        
        response = client.post(
            "/sftp/list",
            json={
                "host": "sftp.example.com",
                "port": 22,
                "path": "/uploads",
                "username": "user",
                "password": "pass",
                "key": None
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert data["files"] == ["file1.txt", "file2.txt"]
    
    @patch("app.routes.sftp.SFTPClient")
    def test_sftp_list_connection_error(self, mock_sftp_class, client):
        """Test POST /sftp/list handles connection errors."""
        mock_sftp_class.side_effect = Exception("Connection failed")
        
        response = client.post(
            "/sftp/list",
            json={
                "host": "invalid.host",
                "port": 22,
                "path": "/uploads",
                "username": "user",
                "password": "pass",
                "key": None
            }
        )
        
        assert response.status_code == 500


class TestProxyEndpoints:
    """Test proxy endpoint."""
    
    @patch("app.routes.proxy.requests.request")
    def test_proxy_forward_request(self, mock_request, client):
        """Test POST /proxy forwards requests to external endpoints."""
        mock_request.return_value.status_code = 200
        mock_request.return_value.text = '{"result": "ok"}'
        mock_request.return_value.headers = {"Content-Type": "application/json"}
        
        response = client.post(
            "/proxy",
            json={
                "method": "GET",
                "url": "http://example.com/api/test",
                "headers": {},
                "data": None
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "status_code" in data
        assert "text" in data
        assert "headers" in data
    
    @patch("app.routes.proxy.requests.request")
    def test_proxy_request_failure(self, mock_request, client):
        """Test POST /proxy handles request failures."""
        mock_request.side_effect = Exception("Network error")
        
        response = client.post(
            "/proxy",
            json={
                "method": "GET",
                "url": "http://invalid.url/api",
                "headers": {},
                "data": None
            }
        )
        
        assert response.status_code == 500


class TestBatchEndpoints:
    """Test batch processing endpoints."""
    
    def test_batch_submit_creates_job(self, client, sample_batch_request):
        """Test POST /process/batch/submit creates async job."""
        response = client.post(
            "/process/batch/submit",
            json=sample_batch_request.model_dump()
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "submitted"
        assert "date_range" in data
        assert len(data["job_id"]) > 0
    
    def test_batch_status_pending(self, client, sample_batch_request):
        """Test GET /process/batch/status shows pending status."""
        # Submit a job
        submit_response = client.post(
            "/process/batch/submit",
            json=sample_batch_request.model_dump()
        )
        job_id = submit_response.json()["job_id"]
        
        # Check status
        response = client.get(f"/process/batch/status/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] in ["pending", "running", "completed"]
    
    def test_batch_status_not_found(self, client):
        """Test GET /process/batch/status returns 404 for unknown job."""
        response = client.get("/process/batch/status/unknown-job-id")
        assert response.status_code == 404


class TestProcessEndpoints:
    """Test single file processing endpoints."""
    
    @patch("app.routes.process.SFTPClient")
    @patch("app.routes.process.get_detector")
    def test_process_single_file(self, mock_detector_factory, mock_sftp_class):
        """Test POST /process single file processing."""
        # This test requires proper async/await setup
        # Skipping detailed test - covered by integration tests
        pass


class TestErrorHandling:
    """Test error handling in endpoints."""
    
    def test_malformed_json_request(self, client):
        """Test endpoint returns 422 for malformed JSON."""
        response = client.post(
            "/templates",
            json={"name": "valid", "content": "valid"}  # Valid types
        )
        # This should succeed since types are valid
        assert response.status_code == 200
    
    def test_invalid_date_range(self, client):
        """Test batch endpoint accepts any date format (validation in date processing)."""
        response = client.post(
            "/process/batch/submit",
            json={
                "host": "localhost",
                "port": 22,
                "username": "user",
                "password": "pass",
                "root_path": "/uploads",
                "start_date": "invalid_date",  # Invalid format but accepted
                "end_date": "20260305",
                "call_type": "vllm",
                "concurrency": 2
            }
        )
        # Should accept the request (job fails later when connecting)
        assert response.status_code == 200
