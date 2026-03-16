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
├── build-dev.sh             # Alias for: build.sh dev [version]
├── build-prod.sh            # Alias for: build.sh prod [version]
├── init-environments.sh     # Initialize .env files
├── dev-server.sh            # Local development server
├── validate-setup.sh        # Validate build environment
└── test-version-param.sh    # Test version parameter handling
```

## Usage

### Development Build (RHEL 8.9)

Build image and export as compressed tar.gz:

```bash
# Build with default version (latest)
./scripts/build/build-dev.sh

# Build with specific version
./scripts/build/build-dev.sh 1.0.0

# Build with version prefix
./scripts/build/build-dev.sh v1.0.0

# Or using main build script directly
./scripts/build/build.sh dev              # latest
./scripts/build/build.sh dev 1.0.0        # 1.0.0
```

**Output:**
- Image: `stt-service:dev-latest` or `stt-service:dev-1.0.0`
- File: `output/stt-service-dev-latest-YYYYMMDD.tar.gz` or `output/stt-service-dev-1.0.0-YYYYMMDD.tar.gz`
- Metadata: `output/build-info-dev-latest-YYYYMMDD-HHMMSS.txt`

### Production Build

```bash
# Build with default version (latest)
./scripts/build/build-prod.sh

# Build with specific version
./scripts/build/build-prod.sh 1.0.0

# Or using main build script directly
./scripts/build/build.sh prod             # latest
./scripts/build/build.sh prod 1.0.0       # 1.0.0
```

**Output:**
- Image: `stt-service:prod-latest` or `stt-service:prod-1.0.0`
- File: `output/stt-service-prod-latest-YYYYMMDD.tar.gz` or `output/stt-service-prod-1.0.0-YYYYMMDD.tar.gz`
- Metadata: `output/build-info-prod-latest-YYYYMMDD-HHMMSS.txt`

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
   The script automatically saves to `output/stt-service-dev-1.0.0-YYYYMMDD.tar.gz`

3. **Transfer to production server:**
   ```bash
   scp output/stt-service-dev-1.0.0-*.tar.gz user@prod-server:/path/to/images/
   ```

### On Production Server (RHEL 8.9)

1. **Load image from tar.gz:**
   ```bash
   docker load -i stt-service-dev-1.0.0-YYYYMMDD.tar.gz
   ```

2. **Run container:**
   ```bash
   docker run -d \
     --name stt-service \
     -p 8002:8002 \
     -e APP_ENV=prod \
     stt-service:dev-1.0.0
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
docker run -e APP_ENV=prod stt-service:dev-latest
```

## Output Directory Structure

```
output/
├── stt-service-dev-latest-20260316.tar.gz      # Compressed image
├── build-info-dev-latest-20260316-084301.txt   # Build metadata
├── stt-service-prod-latest-20260316.tar.gz     # Previous build
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
