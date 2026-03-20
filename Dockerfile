FROM python:3.11.14-slim-trixie

# Build-time environment selection (default: prod)
# Usage: docker build --build-arg ENV=dev .
ARG ENV=prod

# Set working directory
WORKDIR /app

# Python and pip environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=${ENV}

# system deps needed for building cryptography/paramiko
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libssl-dev \
       libffi-dev \
       python3-dev \
       openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application Python code (excluding static files first)
COPY ./app/main.py ./app/
COPY ./app/__init__.py ./app/
COPY ./app/config.py ./app/
COPY ./app/models.py ./app/
COPY ./app/sftp_client.py ./app/
COPY ./app/utils ./app/utils
COPY ./app/database ./app/database
COPY ./app/detection ./app/detection
COPY ./app/routes ./app/routes
COPY ./app/templates ./app/templates

# Copy static files (CSS, JS, HTML, vendor libraries) in separate layer
# Copy app/static/ - CSS, JS, HTML
# Copy app/static/vendor/flatpickr/ - Locally cached flatpickr for on-prem deployment (no CDN access)
COPY ./app/static ./app/static

# Copy environment configuration directory (must exist with .gitkeep for git tracking)
# All .env files inside are git-ignored for security
COPY environments/ ./environments/

# Create data and logs directories with proper permissions
RUN mkdir -p /app/app/data/logs && chmod 755 /app/app/data/logs

# Persistent volumes for data and logs
VOLUME ["/app/app/data"]

# Runtime environment loading:
# - APP_ENV environment variable determines which .env file to load
# - Can be overridden at runtime: docker run -e APP_ENV=dev ...
# - config.py loads from environments/.env.${APP_ENV}

EXPOSE 8002

# Health check (interval: 30초, timeout: 10초, 3회 실패 시 unhealthy)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8002/health')" || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
