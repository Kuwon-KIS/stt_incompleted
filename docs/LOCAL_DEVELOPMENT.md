# Local Development Guide

## 🚀 Quick Start

### 1. Environment Setup

```bash
# Activate conda environment
conda activate stt-py311

# Verify environment
python --version  # Should be 3.11.x
```

### 2. Running Local Service

```bash
# Navigate to project root
cd /Users/a113211/workspace/stt_incompleted

# Start the development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8002
INFO:     Application startup complete
```

### 3. Access the Web Interface

Open your browser and navigate to:
- **Web UI**: http://127.0.0.1:8002
- **API Docs (Swagger)**: http://127.0.0.1:8002/docs
- **Alternative API Docs**: http://127.0.0.1:8002/redoc

## 🌐 Web Interface

The web application is a single-page application (SPA) with 4 main sections:

### Dashboard (대시보드)
- System status indicator
- Recent jobs (last 5)
- Processing statistics
  - Total files processed
  - Success/Error counts
  - Average processing time

### Batch Processing (배치 처리)
- Configure date range (YYYYMMDD format)
- Select detection method:
  - **vLLM**: Uses vLLM server for detection
  - **AI Agent**: Uses AI Agent API
- LLM model selection
- Process batch files

### Templates (템플릿)
- View available templates:
  - `generic` - Generic template
  - `qwen_default` - Qwen model default template
- Create custom templates
- Edit and delete templates
- Template management interface

### Job History (이력)
- View all processed jobs
- Job status tracking
- Detailed results for each job
- Export/download functionality

## 📡 API Endpoints

### Health Checks
```bash
# Basic health check
curl http://127.0.0.1:8002/health
# Response: {"status":"ok"}

# Detailed health check
curl http://127.0.0.1:8002/healthz
# Response: {"status":"ok","uptime_seconds":X,"environment":"dev"}
```

### Process Text
```bash
curl -X POST http://127.0.0.1:8002/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Your transcribed text here",
    "call_type": "vllm",
    "model": "qwen"
  }'
```

### Get Templates
```bash
curl http://127.0.0.1:8002/templates
# Response: List of all available templates
```

### View Job Status
```bash
curl http://127.0.0.1:8002/jobs/{job_id}
```

## 📁 Project Structure

```
app/
├── main.py                 # Main FastAPI application
├── config.py               # Configuration management
├── models.py               # Request/Response models
├── sftp_client.py          # SFTP client implementation
├── detection/              # Detection module
├── routes/                 # API routes
│   ├── health.py          # Health check endpoints
│   ├── process.py         # Processing endpoints
│   ├── templates.py       # Template management
│   ├── sftp.py           # SFTP operations
│   ├── proxy.py          # Proxy requests
│   └── web.py            # Web interface
└── static/                # Frontend assets
    ├── index.html         # Main HTML
    ├── css/
    │   └── style.css      # Styling
    └── js/
        └── app.js         # Frontend logic
```

## 🔧 Environment Variables

Check `environments/.env.local` for development settings:
```bash
APP_ENV=local
DEBUG=true
LOG_LEVEL=INFO
```

## 🧪 Testing

### Run unit tests
```bash
./scripts/test/run-tests.sh
```

### Run integration tests
```bash
./scripts/test/test-local.sh
```

### Test specific endpoint
```bash
# Test health endpoint
curl http://127.0.0.1:8002/health

# Test templates
curl http://127.0.0.1:8002/templates

# Test UI
curl http://127.0.0.1:8002 | head -30
```

## 📝 Common Tasks

### Change LOG Level
Edit `environments/.env.local`:
```bash
LOG_LEVEL=DEBUG
```
Then restart the server.

### Add New Template
1. Create template file in `app/templates/`
2. Restart server (templates auto-load on startup)
3. View in Web UI → Templates

### Debug Mode
Edit `environments/.env.local`:
```bash
DEBUG=true
```

### View API Documentation
1. Swagger UI: http://127.0.0.1:8002/docs
2. ReDoc: http://127.0.0.1:8002/redoc

## 🐛 Troubleshooting

### Port 8002 already in use
```bash
# Kill existing process
lsof -ti:8002 | xargs kill -9

# Or use different port
python -m uvicorn app.main:app --port 8003
```

### Module not found errors
```bash
# Reinstall dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Or use conda
conda install --file requirements.txt
```

### Template not loading
1. Check file exists in `app/templates/`
2. Verify file extension (should be `.tmpl` or `.txt`)
3. Check file permissions (should be readable)
4. Restart server

### Hot reload not working
- Remove `.env` file from project root (keep only in `environments/`)
- Ensure `app/` directory structure is correct
- Restart uvicorn with `--reload` flag

## 📚 References

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Uvicorn Documentation**: https://www.uvicorn.org/
- **API Specification**: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Build Scripts**: See [BUILD_SCRIPT_GUIDE.md](BUILD_SCRIPT_GUIDE.md)

## ⚡ Performance Tips

### Faster Development
1. Use separate terminal for server
2. Use `--reload` flag for auto-restart on changes
3. Monitor logs with `tail -f /tmp/stt-build-*.log`

### Memory Usage
- Check `config.py` for pool sizes and limits
- Adjust `MAX_WORKERS` for thread pool size
- Monitor with `top` or `Activity Monitor`

## 🎯 Next Steps

1. **Explore Web UI**: Navigate through all 4 pages
2. **Try API**: Use curl or Postman to test endpoints
3. **Read Templates**: Review template files in `app/templates/`
4. **Check Logs**: Monitor console output while testing
5. **Modify Settings**: Update `.env.local` to experiment with configuration

---

**Started**: Local development server running on http://127.0.0.1:8002
**Environment**: Local (stt-py311)
**Configuration**: environments/.env.local
