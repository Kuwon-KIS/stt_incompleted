# Build Script Guide

## Overview

The build scripts are designed for the three-environment architecture:
- **Local (Mac)**: Direct Python execution (no Docker build)
- **Development (RHEL 8.9 - AWS EC2)**: Docker build with tar.gz export
- **Production (RHEL 8.9 - On-premise)**: Image deployment from tar.gz

## Build Scripts Location

All build scripts are located in `scripts/build/`:
```
scripts/build/
├── build.sh                 # Main unified build script
├── build-dev.sh             # Wrapper: build.sh dev [version] [options]
├── build-prod.sh            # Wrapper: build.sh prod [version] [options]
├── lib/                     # Shared utility libraries
│   ├── common.sh           # Common functions (logging, colors, etc)
│   └── docker-utils.sh     # Docker operations (load, run, validate)
├── init-environments.sh     # Initialize .env files
├── dev-server.sh            # Local development server
├── validate-setup.sh        # Validate build environment
└── test-version-param.sh    # Test version parameter handling
```

## Usage

### Quick Start - Build Only (Default)

Build image and export as compressed tar.gz. Does NOT load into Docker or run container.

```bash
# Build with default version (latest)
./scripts/build/build-dev.sh
./scripts/build/build-prod.sh

# Build with specific version
./scripts/build/build-dev.sh 1.0.0
./scripts/build/build-prod.sh 1.0.0

# Or using main build script directly
./scripts/build/build.sh dev
./scripts/build/build.sh prod 1.0.0
```

**Output:**
- Image: `stt-post-review:latest` or `stt-post-review:dev-1.0.0`
- File: `output/stt-post-review-dev-latest.tar.gz` or `output/stt-post-review-dev-1.0.0.tar.gz`
- Metadata: `output/.build_metadata`
- Deployment instructions displayed
- Ready for transfer to remote server

---

### Advanced Usage: Optional --load and --run Flags

The build scripts now support optional flags for Docker operations:

#### Syntax

```bash
./scripts/build/build-dev.sh [version] [--load] [--run]
./scripts/build/build-prod.sh [version] [--load] [--run]
./scripts/build/build.sh [env] [version] [--load] [--run]
```

#### Option 1: Build Only (Default)

```bash
./scripts/build/build-dev.sh
./scripts/build/build-dev.sh 1.0.0
./scripts/build/build-prod.sh 1.0.0
```

**What it does:**
- Builds Docker image
- Exports tar.gz to output/
- Does NOT load into Docker daemon
- Ready for deployment

---

#### Option 2: Build + Load with --load Flag

```bash
./scripts/build/build-dev.sh --load
./scripts/build/build-dev.sh 1.0.0 --load
./scripts/build/build-prod.sh 1.0.0 --load
```

**What it does:**
- Builds Docker image
- Exports tar.gz to output/
- Loads image into local Docker daemon
- Can verify with: `docker images | grep stt-post-review`

**Use cases:**
- Pre-loading image before pushing to registry
- Testing locally before deployment
- Verifying image integrity

---

#### Option 3: Build + Load + Run with --run Flag

```bash
./scripts/build/build-dev.sh --run
./scripts/build/build-dev.sh 1.0.0 --run
./scripts/build/build-prod.sh 1.0.0 --run
```

**What it does:**
- Builds Docker image
- Exports tar.gz to output/
- Loads image into Docker daemon
- Runs test container: `stt-post-review-dev-test` or `stt-post-review-prod-test`
- Waits for container to be ready (30 attempts × 1s)
- Validates 5 health check endpoints:
  - `/health`
  - `/healthz`
  - `/`
  - `/templates`
  - TCP connectivity
- Displays container info and access points

**Example output:**
```
✓ Container running: stt-post-review-dev-test
Port: 8002
Ports: 0.0.0.0:8002->8000/tcp

Access Points:
- API: http://localhost:8002
- Health: http://localhost:8002/healthz
- Templates: http://localhost:8002/templates

✓ Health Check Results:
  [PASS] /health
  [PASS] /healthz
  [PASS] /
  [PASS] /templates
  [PASS] TCP connectivity
```

**Use cases:**
- Automated testing after build
- Verify application starts correctly
- Validate endpoints respond
- CI/CD pipeline integration
- Quick smoke test during development

---

#### Usage Comparison

| Command | Build | Export tar.gz | Load to Docker | Run Container | Health Check |
|---------|:-----:|:-------------:|:--------------:|:-------------:|:------------:|
| `build-dev.sh` | ✓ | ✓ | ✗ | ✗ | ✗ |
| `build-dev.sh --load` | ✓ | ✓ | ✓ | ✗ | ✗ |
| `build-dev.sh --run` | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## Practical Workflows

### Workflow 1: Quick Local Testing

Build, load, and run immediately for development testing:

```bash
./scripts/build/build-dev.sh 0.0.1 --run

# Output shows container running on http://localhost:8002
# Test your application
curl http://localhost:8002/health
curl http://localhost:8002/templates

# When done, clean up:
docker stop stt-post-review-dev-test
docker rm stt-post-review-dev-test
```

### Workflow 2: Prepare for Remote Deployment

Build and verify locally, then transfer for deployment:

```bash
# 1. Build and load locally (no run)
./scripts/build/build-prod.sh 1.0.0 --load

# 2. Verify image exists
docker images | grep stt-post-review

# 3. Transfer tar.gz to remote server
scp output/stt-post-review-prod-1.0.0.tar.gz user@server:/tmp/

# 4. On remote server, load and run
# docker load < /tmp/stt-post-review-prod-1.0.0.tar.gz
# docker run -d -p 8000:8000 stt-post-review:1.0.0
```

### Workflow 3: Build, Verify, Deploy

Full workflow with local verification:

```bash
# 1. Build with comprehensive testing
./scripts/build/build-prod.sh 1.0.0 --run

# 2. Health checks should all pass - review output

# 3. Clean up test container
docker stop stt-post-review-prod-test
docker rm stt-post-review-prod-test

# 4. Transfer verified image to production
scp output/stt-post-review-prod-1.0.0.tar.gz prod-server:/opt/images/

# 5. On production, load and run
# docker load < /opt/images/stt-post-review-prod-1.0.0.tar.gz
# docker run -d -p 8000:8000 --env-file .env.prod stt-post-review:1.0.0
```

### Workflow 4: CI/CD Pipeline Integration

Automated build with gate:

```bash
#!/bin/bash
set -e

VERSION="${1:-1.0.0}"

echo "Building version $VERSION..."
./scripts/build/build-prod.sh "$VERSION" --run

echo "Extracting container logs..."
docker logs stt-post-review-prod-test

echo "Pushing to registry..."
docker tag stt-post-review:$VERSION my-registry/stt-post-review:$VERSION
docker push my-registry/stt-post-review:$VERSION

echo "Cleaning up..."
docker stop stt-post-review-prod-test
docker rm stt-post-review-prod-test

echo "✓ Build and push complete!"
```

---

## Build Script Features

### 1. Environment Validation
- Checks if environment (dev/prod) is valid
- Verifies environment file exists: `environments/.env.{env}`
- Verifies requirements.txt exists

### 2. Existing Image Detection
- Detects existing images with same name
- Prompts user to rebuild or reuse
- Allows selective deletion of old images

### 3. Docker Build
- Builds image with: `--build-arg ENV={env}`
- Sets explicit `APP_ENV` environment variable in container
- Copies all .env files (environments/) to container

### 4. Image Export as tar.gz
- Exports Docker image to compressed archive
- **Parallel Compression**: Uses `pigz` if available (much faster)
- **Fallback**: Uses standard `gzip` if pigz not installed
- Compression level: 6 (balance between speed and size)

### 5. Build Logging
- Full build log saved to: `/tmp/stt-build-YYYYMMDD-HHMMSS.log`
- All steps and outputs logged
- Useful for debugging build failures

### 6. Build Metadata
- Saves build information file with:
  - Build date/time
  - Environment used
  - Image name and tar.gz filename
  - File size
  - Build duration
  - Deployment instructions

### 7. Optional Docker Operations (New)
- **--load flag**: Load built image into Docker daemon
- **--run flag**: Run test container with health validation
- **Health checks**: Test 5 key endpoints before declaring success
- **Port management**: Automatic conflict detection (port 8002)
- **Container info**: Display access points and logs on success

## Deployment Workflow

### Initial Setup (First Time Only)

On fresh EC2 deployment, initialize environment files:

```bash
# Initialize all environments (dev, local, prod)
./scripts/build/init-environments.sh

# Or initialize specific environments
./scripts/build/init-environments.sh dev,prod

# Edit with real values
nano environments/.env.dev
nano environments/.env.prod
```

**Generated template structure:**
```
environments/
├── .env.dev    # Development settings
├── .env.local  # Local development
├── .env.prod   # Production settings
└── .gitkeep    # Ensures directory is tracked in git
```

⚠️ **Important**: All `.env.* files are git-ignored. Never commit credentials.

### From Development (Build) Server

1. **Build image on RHEL 8.9 EC2 with specific version:**
   ```bash
   ./scripts/build/build-dev.sh 1.0.0
   ```

2. **Copy tar.gz to output directory:**
   The script automatically saves to `output/stt-post-review-dev-1.0.0-YYYYMMDD.tar.gz`

3. **Transfer to production server:**
   ```bash
   scp output/stt-post-review-dev-1.0.0-*.tar.gz user@prod-server:/path/to/images/
   ```

### On Production Server (RHEL 8.9)

1. **Load image from tar.gz:**
   ```bash
   docker load -i stt-post-review-dev-1.0.0-YYYYMMDD.tar.gz
   ```

2. **Run container:**
   ```bash
   docker run -d \
     --name stt-post-review \
     -p 8002:8002 \
     -e APP_ENV=prod \
     stt-post-review:dev-1.0.0
   ```

   **Note:** Image built with `dev` settings but run with `APP_ENV=prod` to load `.env.prod`

### Version Naming Convention

**Recommended version format:**
- `latest` - Default, bleeding edge
- `1.0.0` - Semantic versioning
- `v1.0.0` - With prefix (also supported)
- `20260316` - Date-based versioning
- `release-2026-q1` - Release identifier

## Environment Variables

### Build Time
- `ENV`: Set via `--build-arg ENV={dev|prod}` (default: prod)
- Sets `APP_ENV` in Dockerfile to match build environment

### Runtime Override
- `-e APP_ENV=prod`: Override environment at runtime
- All .env files present in container at `/app/environments/`
- `config.py` loads `environments/.env.${APP_ENV}`

**Example:**
```bash
# Build with dev settings
./scripts/build/build-dev.sh

# But run with production environment
docker run -e APP_ENV=prod stt-post-review:latest
```

## Output Directory Structure

```
output/
├── stt-post-review-dev-latest-20260316.tar.gz      # Compressed image
├── build-info-dev-latest-20260316-084301.txt   # Build metadata
├── stt-post-review-prod-latest-20260316.tar.gz     # Previous build
└── build-info-prod-latest-20260316-083015.txt  # Previous metadata
```

## Performance Tips

### Enable Parallel Compression (pigz)

On RHEL 8.9:
```bash
# Install pigz
sudo yum install -y pigz

# Or with conda
conda install -c conda-forge pigz
```

**Performance improvement:** 2-3x faster compression (depending on CPU cores)

### Check Build Progress

Monitor real-time build in another terminal:
```bash
tail -f /tmp/stt-build-*.log
```

### Pre-build Steps

Verify everything before building:
```bash
# Check environment file
cat environments/.env.dev

# Check Dockerfile
cat Dockerfile

# Verify dependencies
cat requirements.txt
```

## Troubleshooting

### Build Fails with "Environment file not found"

Check if environment file exists:
```bash
ls -la environments/.env.*
```

### Docker image not found after export

Verify tar.gz was created:
```bash
ls -lh output/*.tar.gz
```

### Compression too slow

Install pigz for parallel compression:
```bash
brew install pigz  # macOS
sudo yum install pigz  # RHEL
```

### Docker daemon not running (on RHEL 8.9)

```bash
sudo systemctl start docker
sudo systemctl status docker
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Build STT Service
  run: |
    ./scripts/build/build-dev.sh
    
- name: Upload artifacts
  uses: actions/upload-artifact@v2
  with:
    name: docker-images
    path: output/*.tar.gz
```

### Jenkins Pipeline

```groovy
stage('Build') {
  steps {
    sh './scripts/build/build-dev.sh'
    archiveArtifacts artifacts: 'output/**/*.tar.gz'
  }
}
```

## References

- [Dockerfile](../Dockerfile) - Container configuration
- [config.py](../app/config.py) - Environment loading logic
- [Requirements](../requirements.txt) - Production dependencies
- [Environment Setup](./ENVIRONMENT_SETUP.md) - .env file configuration
