FROM python:3.10.19-slim-trixie

ARG ENV=prod
ARG ENV_FILE=.env.${ENV}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

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

COPY requirements /app/
RUN pip install --no-cache-dir -r requirements

COPY ./app /app/app

# Copy .env file based on build argument (dev/prod)
# Environment files are organized in environments/ folder
COPY environments/ /app/environments/

# Link the specific env file to .env
RUN cp /app/environments/.env.${ENV} /app/.env || cp /app/environments/.env.dev /app/.env

EXPOSE 8002

# CMD uses environment variables from .env file embedded at build time
# Runtime docker run -e options will override these values (higher priority)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
