#!/bin/bash
# Docker utility functions
# Source: source "$(dirname "${BASH_SOURCE[0]}")/docker-utils.sh"

# Load Docker image from tar.gz
docker_load_image() {
    local tar_file=$1
    local image_tag=$2
    
    if [ ! -f "$tar_file" ]; then
        log_error "tar.gz file not found: $tar_file"
        return 1
    fi
    
    log_step "1" "Load Docker image from tar.gz"
    log_info "File: $tar_file"
    
    if docker load -i "$tar_file" 2>&1 | tail -5; then
        log_success "Docker image loaded successfully"
        return 0
    else
        log_error "Failed to load Docker image"
        return 1
    fi
}

# Validate loaded image
docker_validate_image() {
    local image_tag=$1
    
    log_step "2" "Validate Docker image"
    
    # Check if image exists
    if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${image_tag}$"; then
        log_error "Image not found: $image_tag"
        return 1
    fi
    
    log_success "Image exists: $image_tag"
    
    # Show image info
    log_info "Image details:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | grep "$image_tag" | awk '{
        printf "   Repository: %s\n   Tag: %s\n   Size: %s\n   Created: %s\n", $1, $2, $3, $4
    }'
    
    return 0
}

# Run container with basic checks
docker_run_container() {
    local image_tag=$1
    local container_name=$2
    local port=$3
    local env_arg=${4:-}
    
    log_step "3" "Run Docker container"
    log_info "Image: $image_tag"
    log_info "Container: $container_name"
    log_info "Port: $port"
    
    # Check if container already running
    if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
        log_warning "Container already running: $container_name"
        log_info "Stopping existing container..."
        docker stop "$container_name" &> /dev/null || true
        docker rm "$container_name" &> /dev/null || true
        sleep 1
    fi
    
    # Check port availability
    if lsof -Pi :$port -sTCP:LISTEN -t &> /dev/null; then
        log_error "Port $port already in use"
        return 1
    fi
    log_success "Port $port is available"
    
    # Run container
    local docker_cmd="docker run -d --name $container_name -p $port:8002"
    
    if [ -n "$env_arg" ]; then
        docker_cmd="$docker_cmd --env-file $env_arg"
    else
        docker_cmd="$docker_cmd -e APP_ENV=dev"
    fi
    
    docker_cmd="$docker_cmd $image_tag"
    
    log_info "Running: $docker_cmd"
    
    if eval "$docker_cmd" &> /dev/null; then
        log_success "Container started: $container_name"
        return 0
    else
        log_error "Failed to start container"
        return 1
    fi
}

# Wait for container to be ready
docker_wait_ready() {
    local container_name=$1
    local max_attempts=${2:-30}
    local attempt=0
    
    log_step "4" "Wait for container to be ready"
    
    while [ $attempt -lt $max_attempts ]; do
        if docker exec "$container_name" curl -s http://localhost:8002/health &> /dev/null; then
            log_success "Container is ready (attempt $((attempt + 1))/$max_attempts)"
            return 0
        fi
        
        attempt=$((attempt + 1))
        if [ $((attempt % 5)) -eq 0 ]; then
            log_info "Waiting... ($attempt/$max_attempts)"
        fi
        sleep 1
    done
    
    log_error "Container failed to become ready after $max_attempts attempts"
    return 1
}

# Health check
docker_health_check() {
    local container_name=$1
    local port=$2
    
    log_step "5" "Perform health checks"
    
    local endpoints=("/health" "/healthz" "/" "/templates")
    local failed=0
    
    for endpoint in "${endpoints[@]}"; do
        log_info "Testing: GET http://localhost:$port$endpoint"
        
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:$port$endpoint | grep -q "200"; then
            log_success "✓ $endpoint"
        else
            log_warning "✗ $endpoint (may still be initializing)"
            failed=$((failed + 1))
        fi
    done
    
    if [ $failed -eq 0 ]; then
        log_success "All health checks passed"
        return 0
    else
        log_warning "$failed endpoint(s) failed health check"
        return 0  # Not a hard failure - return success anyway
    fi
}

# Show container info
docker_show_info() {
    local container_name=$1
    local port=$2
    
    echo ""
    log_info "Container is running successfully!"
    echo ""
    echo -e "${BLUE}📋 Container Information${NC}"
    echo "─────────────────────────────────────"
    docker ps --filter "name=$container_name" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}" | tail -1 | awk '{
        printf "   ID: %s\n   Name: %s\n   Status: %s\n   Ports: %s\n", $1, $2, $3, $4
    }'
    
    echo ""
    echo -e "${BLUE}🌐 Access Points${NC}"
    echo "─────────────────────────────────────"
    echo "   Web UI:     http://localhost:$port/"
    echo "   Swagger:    http://localhost:$port/docs"
    echo "   ReDoc:      http://localhost:$port/redoc"
    echo ""
    
    echo -e "${BLUE}📝 Useful Commands${NC}"
    echo "─────────────────────────────────────"
    echo "   View logs:    docker logs -f $container_name"
    echo "   Stop:         docker stop $container_name"
    echo "   Restart:      docker restart $container_name"
    echo "   Remove:       docker rm -f $container_name"
    echo ""
}
