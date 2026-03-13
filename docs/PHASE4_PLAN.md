# Phase 4 Plan: Testing, Docker Build & AWS Deployment

**Timeline**: Week 4 (approximately 5-7 days)  
**Status**: 📋 PLANNED  
**Objective**: Take modularized codebase from Phase 3 and prepare for production deployment

## Phase 4 Phases

### Phase 4.1: Local Testing & Validation (Day 1-2)

#### 4.1.1 Unit Testing with pytest

**Create**: `tests/test_routes.py`
```python
# Test each route module independently
- test_health_endpoints()
  - Verify /health returns expected JSON with uptime
  - Verify /healthz returns Kubernetes-compatible format

- test_process_endpoints()
  - Test POST /process with mock SFTP (requires fixtures)
  - Test POST /process/batch/submit returns job_id
  - Test GET /process/batch/status/{id} returns correct status

- test_templates_endpoints()
  - Test GET /templates lists all templates
  - Test POST /templates creates new template
  - Test DELETE /templates/{name} removes template
  - Test template refresh reloads from disk

- test_sftp_endpoints()
  - Test POST /sftp/list with mock SFTPClient

- test_web_endpoints()
  - Test GET / returns HTML
  - Test GET /ui returns HTML
```

**Tools Required**:
- pytest (test framework)
- pytest-asyncio (async route testing)
- unittest.mock (mock SFTP connections)

**Coverage Goal**: >80% of route logic

#### 4.1.2 Integration Testing

**Create**: `tests/test_integration.py`
```python
# Test full workflows
- test_batch_processing_flow()
  - Submit batch job
  - Poll status until completion
  - Verify results structure
  - Handle timeout (should fail gracefully)

- test_template_workflow()
  - Create template via POST
  - Use template in process request
  - Verify template applied correctly
  - Delete template and confirm removal

- test_detection_strategies()
  - Test vLLM strategy with mock API
  - Test Agent strategy with mock API
  - Verify detection result structure
```

**Mock Endpoints Needed**:
- Mock vLLM at http://127.0.0.1:8001/v1/chat/completions
- Mock Agent at http://127.0.0.1:8003/{agent_name}/messages
- Mock Callback at http://127.0.0.1:8004/callback

#### 4.1.3 Web UI Testing

**Manual Testing Checklist**:
- [ ] Dashboard page loads
  - [ ] Health status displays
  - [ ] Recent jobs show (if any)
  - [ ] Statistics visible
- [ ] Batch Processing page works
  - [ ] Date range picker works
  - [ ] Submit button creates job
  - [ ] Progress bar updates
  - [ ] Results download as CSV
- [ ] Template Management page
  - [ ] Template list displays
  - [ ] Can create new template
  - [ ] Can edit existing template
  - [ ] Can delete template
  - [ ] Template preview works
- [ ] Job History page
  - [ ] Shows all submitted jobs
  - [ ] Search/filter works
  - [ ] Can view job details
  - [ ] Can download results

**Browser Testing**: Chrome, Safari, Firefox on macOS

#### 4.1.4 Error Handling Validation

**Test Scenarios**:
```python
test_error_scenarios = [
    ("Invalid SFTP credentials", should_return_500_with_message),
    ("Non-existent template", should_return_404),
    ("Malformed JSON request", should_return_400),
    ("Timeout on external API", should_return_504_or_timeout),
    ("Invalid date range", should_return_400_with_validation_error),
    ("Job not found", should_return_404),
]
```

### Phase 4.2: Docker Build & Local Container Testing (Day 2-3)

#### 4.2.1 Docker Build Verification

**Test**: `./build-dev.sh`
```bash
# Should produce image: stt-service:dev-latest

# Build test
./build-dev.sh

# Container test
docker run --rm -p 8002:8002 \
  -e APP_ENV=dev \
  -e DEBUG=false \
  stt-service:dev-latest &

sleep 5
curl http://localhost:8002/healthz

docker stop <container_id>
```

**Expected Output**:
- Image builds successfully
- No build errors or warnings (except pydantic warning)
- Container starts and listens on port 8002
- Health endpoint responds

#### 4.2.2 Environment Variable Testing in Container

**Test Matrix**:
```
Env Var Settings          | Expected Behavior
─────────────────────────┼──────────────────
APP_ENV=local            | Uses localhost vLLM
APP_ENV=dev              | Uses AWS EC2 vLLM
APP_ENV=prod             | Uses HA load balancer
LOG_LEVEL=DEBUG          | Verbose logging
LOG_LEVEL=WARN           | Minimal logging
```

#### 4.2.3 Static Files in Container

**Verify**:
- [ ] Web UI loads from `/static` mount
- [ ] CSS and JS files accessible
- [ ] Static files served with correct mime types

#### 4.2.4 Volume Mount Testing

**Test**:
```bash
# Create local templates directory
mkdir -p ~/templates
echo "Test template content" > ~/templates/test.txt

# Mount into container
docker run -v ~/templates:/app/templates ... stt-service:dev

# Verify template loads
curl http://localhost:8002/templates
# Should include "test" in response
```

### Phase 4.3: AWS Deployment (Day 3-4)

#### 4.3.1 Pre-deployment Checklist

- [ ] AWS account with ECR registry setup
- [ ] EC2 instances ready (vLLM server, SFTP server)
- [ ] RDS instance created (if using database)
- [ ] VPC/Security groups configured for inbound traffic
- [ ] SSH keys for SFTP configured
- [ ] vLLM service running on EC2 (port 8001 open)

#### 4.3.2 ECR Push

**Process**:
```bash
# Configure AWS credentials
aws configure

# Build and push to ECR (from build-prod.sh logic)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account_id>.dkr.ecr.us-east-1.amazonaws.com

# Tag image
docker tag stt-service:prod-latest <account_id>.dkr.ecr.us-east-1.amazonaws.com/stt-service:latest

# Push
docker push <account_id>.dkr.ecr.us-east-1.amazonaws.com/stt-service:latest
```

#### 4.3.3 Deploy to EC2

**Option A: Direct Docker Run**
```bash
# SSH into EC2
ssh -i ~/.ssh/stt-key.pem ubuntu@<instance_ip>

# Pull and run
docker pull <account_id>.dkr.ecr.us-east-1.amazonaws.com/stt-service:latest

docker run -d \
  --name stt-service \
  --restart always \
  -p 8002:8002 \
  -e APP_ENV=prod \
  -e SFTP_HOST=<sftp_server_ip> \
  -e LLM_URL=http://<vllm_server_ip>:8001/v1/chat/completions \
  <account_id>.dkr.ecr.us-east-1.amazonaws.com/stt-service:latest
```

**Option B: Docker Compose (Recommended)**
```yaml
# Create docker-compose-prod.yml
version: '3.8'
services:
  stt-service:
    image: <account_id>.dkr.ecr.us-east-1.amazonaws.com/stt-service:latest
    ports:
      - "8002:8002"
    environment:
      APP_ENV: prod
      SFTP_HOST: ${SFTP_HOST}
      LLM_URL: http://${LLM_HOST}:8001/v1/chat/completions
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### 4.3.4 AWS RDS Integration (Optional)

If adding persistent job storage:

```python
# app/database.py (new)
from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.ext.declarative import declarative_base

# Create RDS connection
engine = create_engine(f"postgresql://{user}:{pwd}@{rds_endpoint}:5432/stt_db")

class BatchJob(Base):
    __tablename__ = "batch_jobs"
    job_id = Column(String, primary_key=True)
    status = Column(String)
    results = Column(JSON)
    created_at = Column(DateTime)

# Update routes/process.py to use database instead of JOB_STORE
```

### Phase 4.4: Monitoring & Logging (Day 4-5)

#### 4.4.1 Structured Logging

**Setup**: Configure JSON logging for log aggregation
```python
# app/utils.py - update setup_logging()
import logging.config
import json

# Use python-json-logger for JSON output
# Each log message includes: timestamp, level, service, job_id (if available)

# Example log format:
# {"timestamp": "2026-03-13T...", "level": "INFO", "service": "stt-service", "message": "..."}
```

**Benefits**:
- CloudWatch Logs can parse JSON format
- Can filter logs by job_id, level, etc.
- Easier integration with monitoring dashboards

#### 4.4.2 CloudWatch Monitoring

**Metrics to Track**:
- `/healthz` response time (should be <100ms)
- `/process/batch/submit` response time
- Batch processing success rate
- Average batch size processed
- SFTP connection errors
- LLM API errors

**Setup CloudWatch Alarms**:
```bash
# Alert if health check fails
aws cloudwatch put-metric-alarm \
  --alarm-name stt-service-health-check \
  --alarm-description "Alert when health check fails" \
  --metric-name HealthCheckStatus \
  --threshold 1 \
  --comparison-operator LessThanThreshold

# Alert if error rate > 5%
aws cloudwatch put-metric-alarm \
  --alarm-name stt-service-error-rate \
  --metric-name ErrorRate \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold
```

#### 4.4.3 Log Aggregation (CloudWatch Logs)

**Process**:
1. CloudWatch Logs Agent on EC2 sends logs to CloudWatch
2. Create log group: `/aws/stt-service/prod`
3. Filter patterns for errors: `[ERROR]` or `[EXCEPTION]`
4. Set up log retention: 30 days

#### 4.4.4 Performance Profiling

**Tools**:
- Python's `cProfile` for identifying slow routes
- Uvicorn's built-in timing for request duration

**Command to profile**:
```bash
# Profile batch processing
python -m cProfile -s cumulative -o batch_profile.prof \
  /usr/local/bin/uvicorn app.main:app

# Analyze results
python -c "import pstats; p = pstats.Stats('batch_profile.prof'); p.sort_stats('cumulative').print_stats(20)"
```

### Phase 4.5: Integration & Troubleshooting (Day 5)

#### 4.5.1 Real SFTP Testing

**Setup Test Data**:
```bash
# Create test SFTP directory structure
/uploads/20260301/file1.txt
/uploads/20260301/file2.txt
/uploads/20260302/file1.txt
...
```

**Test Batch Processing**:
```bash
curl -X POST http://localhost:8002/process/batch/submit \
  -H "Content-Type: application/json" \
  -d '{
    "host": "sftp-server.internal",
    "username": "sftp_user",
    "password": "sftp_pass",
    "root_path": "/uploads",
    "start_date": "20260301",
    "end_date": "20260305",
    "call_type": "vllm",
    "concurrency": 4
  }'
```

#### 4.5.2 Troubleshooting Guide

**Issue**: Container won't start
- **Check**: `docker logs <container_id>`
- **Common causes**: 
  - Missing environment variables
  - Port already in use
  - Invalid log level
- **Fix**: Set all required env vars, check port with `lsof -i :8002`

**Issue**: Batch job fails with SFTP error
- **Check**: SFTP credentials, server connectivity
- **Verify**: 
  - `curl -s http://localhost:8002/sftp/list` works
  - SFTP server accepts connections
- **Fix**: Update SFTP credentials in env or request

**Issue**: LLM API calls timeout
- **Check**: vLLM server status
- **Verify**: 
  - `curl http://<vllm_ip>:8001/v1/chat/completions -X POST`
  - Network connectivity between services
- **Fix**: Check vLLM logs, increase timeout in config

**Issue**: Web UI loads but buttons don't work
- **Check**: Browser console for JavaScript errors
- **Verify**: 
  - API endpoints accessible (check CORS headers)
  - Static files mounted correctly
- **Fix**: Check `/static` directory, verify CORS middleware

**Issue**: Memory usage grows over time
- **Check**: `docker stats <container_id>`
- **Likely cause**: Job results accumulating in JOB_STORE
- **Fix**: Implement job cleanup (remove old jobs after 24h) or use database

#### 4.5.3 Performance Baseline

**Establish Baseline Metrics**:
```
Single file processing: < 5 seconds (network I/O dependent)
Batch submission: < 1 second
Health check: < 100ms
Template list: < 200ms
Web UI load: < 1 second (browser dependent)

Batch processing (10 files, 2 concurrent):
- Total time: ~15-20 seconds
- Per file: ~1.5-2 seconds
- Success rate: >95%
```

## Deliverables

### Code Artifacts
- [ ] `tests/test_routes.py` - Unit tests for all routes
- [ ] `tests/test_integration.py` - Integration tests
- [ ] `tests/conftest.py` - Pytest fixtures and mocks
- [ ] `.github/workflows/test.yml` - CI/CD pipeline (if using GitHub)

### Configuration Files
- [ ] `docker-compose-prod.yml` - Production deployment config
- [ ] `.env.prod.example` - Production env template
- [ ] `monitoring/cloudwatch.tf` - Terraform for AWS monitoring (optional)

### Documentation
- [ ] `docs/TESTING.md` - How to run tests locally
- [ ] `docs/DEPLOYMENT.md` - AWS deployment guide
- [ ] `docs/TROUBLESHOOTING.md` - Common issues and fixes
- [ ] `docs/MONITORING.md` - Monitoring and logging setup

### Updated Files
- [ ] `app/main.py` - May need adjustments based on testing
- [ ] `app/routes/*.py` - Bug fixes from testing
- [ ] `app/utils.py` - Enhanced error handling

## Success Criteria

- [x] Phase 3 router modularization complete
- [ ] 80%+ test coverage for routes
- [ ] All integration tests passing
- [ ] Web UI fully functional in browser
- [ ] Docker image builds and runs successfully
- [ ] Can deploy to AWS EC2 with proper env vars
- [ ] Monitoring and logging configured
- [ ] Performance baselines established

## Risks & Mitigation

| Risk | Severity | Mitigation |
|------|----------|-----------|
| SFTP server not available | High | Mock SFTP for testing, use test data |
| vLLM service failures | High | Implement retry logic, fallback detection |
| Database connection fails | Medium | Start with in-memory JOB_STORE, add DB later |
| Memory leak in batch jobs | Medium | Monitor memory usage, implement cleanup |
| Kubernetes deployment issues | Low | Use Docker Compose first, then migrate to K8s |

## Timeline Breakdown

```
Day 1 (Mon):  Unit testing, Web UI testing
Day 2 (Tue):  Integration tests, Docker build testing
Day 3 (Wed):  AWS ECR setup, Initial EC2 deployment
Day 4 (Thu):  Monitoring setup, Performance profiling
Day 5 (Fri):  Real SFTP integration, Troubleshooting, Final validation

Contingency: +1-2 days for unexpected issues
```

## Next Phases (Beyond Phase 4)

### Phase 5: Production Hardening
- Implement database for persistent job storage
- Add authentication/authorization (API keys)
- Rate limiting per user/client
- Comprehensive audit logging

### Phase 6: Scaling
- Implement message queue (RabbitMQ/SQS) for batch jobs
- Horizontal scaling with multiple workers
- Load balancing with Nginx/HAProxy
- Caching layer (Redis) for templates

### Phase 7: Features
- Scheduled batch jobs (cron-like)
- Webhook notifications for job completion
- Advanced filtering and search in job history
- Custom detection strategies/plugins

---

**Phase 4 Planning Status**: ✅ **COMPLETE**  
**Ready to Begin Phase 4.1**: YES  
**Estimated Duration**: 5-7 days  
**Dependencies**: Phase 3 completion (✅), AWS account setup
