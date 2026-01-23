#!/bin/bash
# =============================================================================
# ARI V3 - Qdrant Vector Database Setup Script
# =============================================================================
# This script sets up Qdrant for semantic and visual product search.
# Qdrant stores product embeddings and enables fast similarity search.
#
# Prerequisites:
#   - Docker installed and running
#   - At least 4GB RAM available
#   - Port 6333 available (or modify QDRANT_PORT below)
# =============================================================================

set -e  # Exit on any error

# Configuration - modify these if needed
QDRANT_VERSION="v1.12.1"
QDRANT_PORT="${QDRANT_PORT:-6333}"
QDRANT_GRPC_PORT="${QDRANT_GRPC_PORT:-6334}"
QDRANT_CONTAINER_NAME="ari-qdrant"
QDRANT_DATA_DIR="${QDRANT_DATA_DIR:-$HOME/qdrant_data}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "ARI V3 - Qdrant Setup"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check Docker is installed and running
# -----------------------------------------------------------------------------
echo "[1/5] Checking Docker..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed.${NC}"
    echo ""
    echo "Please install Docker first:"
    echo "  Ubuntu/Debian: sudo apt-get install docker.io"
    echo "  Or visit: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}ERROR: Docker daemon is not running.${NC}"
    echo ""
    echo "Please start Docker:"
    echo "  sudo systemctl start docker"
    exit 1
fi

echo -e "${GREEN}Docker is installed and running.${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 2: Check if Qdrant container already exists
# -----------------------------------------------------------------------------
echo "[2/5] Checking for existing Qdrant container..."

if docker ps -a --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER_NAME}$"; then
    echo -e "${YELLOW}Container '${QDRANT_CONTAINER_NAME}' already exists.${NC}"

    if docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER_NAME}$"; then
        echo "Container is already running."
        echo ""
        echo "To restart: docker restart ${QDRANT_CONTAINER_NAME}"
        echo "To stop:    docker stop ${QDRANT_CONTAINER_NAME}"
        echo "To remove:  docker rm -f ${QDRANT_CONTAINER_NAME}"
        echo ""

        read -p "Do you want to remove and recreate the container? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Removing existing container..."
            docker rm -f ${QDRANT_CONTAINER_NAME}
        else
            echo "Keeping existing container. Exiting."
            exit 0
        fi
    else
        echo "Container exists but is stopped."
        read -p "Do you want to start it? (Y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            docker start ${QDRANT_CONTAINER_NAME}
            echo -e "${GREEN}Qdrant started successfully.${NC}"
            exit 0
        else
            read -p "Do you want to remove and recreate it? (y/N): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker rm ${QDRANT_CONTAINER_NAME}
            else
                exit 0
            fi
        fi
    fi
fi

echo ""

# -----------------------------------------------------------------------------
# Step 3: Create data directory
# -----------------------------------------------------------------------------
echo "[3/5] Creating data directory..."

mkdir -p "${QDRANT_DATA_DIR}"
echo "Data will be stored in: ${QDRANT_DATA_DIR}"
echo ""

# -----------------------------------------------------------------------------
# Step 4: Pull Qdrant image
# -----------------------------------------------------------------------------
echo "[4/5] Pulling Qdrant Docker image..."

docker pull qdrant/qdrant:${QDRANT_VERSION}
echo ""

# -----------------------------------------------------------------------------
# Step 5: Start Qdrant container
# -----------------------------------------------------------------------------
echo "[5/5] Starting Qdrant container..."

docker run -d \
    --name ${QDRANT_CONTAINER_NAME} \
    --restart unless-stopped \
    -p ${QDRANT_PORT}:6333 \
    -p ${QDRANT_GRPC_PORT}:6334 \
    -v ${QDRANT_DATA_DIR}:/qdrant/storage \
    qdrant/qdrant:${QDRANT_VERSION}

echo ""

# -----------------------------------------------------------------------------
# Verification
# -----------------------------------------------------------------------------
echo "Waiting for Qdrant to start..."
sleep 3

# Check if container is running
if docker ps --format '{{.Names}}' | grep -q "^${QDRANT_CONTAINER_NAME}$"; then
    # Test the API
    if curl -s "http://localhost:${QDRANT_PORT}/collections" > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}=============================================="
        echo "Qdrant is running successfully!"
        echo "==============================================${NC}"
        echo ""
        echo "Dashboard:  http://localhost:${QDRANT_PORT}/dashboard"
        echo "API:        http://localhost:${QDRANT_PORT}"
        echo "gRPC:       localhost:${QDRANT_GRPC_PORT}"
        echo ""
        echo "Add to your .env file:"
        echo "  QDRANT_URL=http://localhost:${QDRANT_PORT}"
        echo "  QDRANT_HOST=localhost"
        echo "  QDRANT_PORT=${QDRANT_PORT}"
        echo ""
        echo "Container management:"
        echo "  Stop:     docker stop ${QDRANT_CONTAINER_NAME}"
        echo "  Start:    docker start ${QDRANT_CONTAINER_NAME}"
        echo "  Logs:     docker logs ${QDRANT_CONTAINER_NAME}"
        echo "  Remove:   docker rm -f ${QDRANT_CONTAINER_NAME}"
    else
        echo -e "${YELLOW}Container is running but API not responding yet.${NC}"
        echo "Wait a few more seconds and try: curl http://localhost:${QDRANT_PORT}/collections"
    fi
else
    echo -e "${RED}ERROR: Container failed to start.${NC}"
    echo "Check logs with: docker logs ${QDRANT_CONTAINER_NAME}"
    exit 1
fi
