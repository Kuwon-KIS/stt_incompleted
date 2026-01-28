FROM python:3.10.19-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production

WORKDIR /app

# system deps needed for building cryptography/paramiko
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libssl-dev \
       libffi-dev \
       python3-dev \
       openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

# Copy config.example.py as default config template
COPY ./app/config.example.py /app/app/config_template.py

# Generate config.py from environment variables if not provided
# This allows docker build/run to configure via env vars or config.py mount
RUN python3 << 'EOF'
import os
import sys

config_path = "/app/app/config.py"
config_template_path = "/app/app/config_template.py"

# If config.py doesn't exist, create one from template
if not os.path.exists(config_path):
    with open(config_template_path, 'r') as f:
        template = f.read()
    with open(config_path, 'w') as f:
        f.write(template)
    print("Generated config.py from template")
else:
    print("config.py already exists")
EOF

EXPOSE 8002

# APP_ENV can be overridden at runtime: docker run -e APP_ENV=development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
