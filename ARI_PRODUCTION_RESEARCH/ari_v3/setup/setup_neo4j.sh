#!/bin/bash
# =============================================================================
# ARI V3 - Neo4j Graph Database Setup Script
# =============================================================================
# This script sets up Neo4j for user profile storage and style relationships.
# Neo4j stores user preferences, purchase history, and style graph connections.
#
# Prerequisites:
#   - Docker installed and running
#   - At least 4GB RAM available (8GB recommended)
#   - Ports 7474 (HTTP) and 7687 (Bolt) available
# =============================================================================

set -e  # Exit on any error

# Configuration - modify these if needed
NEO4J_VERSION="5.26.0"
NEO4J_HTTP_PORT="${NEO4J_HTTP_PORT:-7474}"
NEO4J_BOLT_PORT="${NEO4J_BOLT_PORT:-7687}"
NEO4J_CONTAINER_NAME="ari-neo4j"
NEO4J_DATA_DIR="${NEO4J_DATA_DIR:-$HOME/neo4j_data}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-ari_secure_password_2024}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "ARI V3 - Neo4j Setup"
echo "=============================================="
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check Docker is installed and running
# -----------------------------------------------------------------------------
echo "[1/6] Checking Docker..."

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
# Step 2: Check if Neo4j container already exists
# -----------------------------------------------------------------------------
echo "[2/6] Checking for existing Neo4j container..."

if docker ps -a --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER_NAME}$"; then
    echo -e "${YELLOW}Container '${NEO4J_CONTAINER_NAME}' already exists.${NC}"

    if docker ps --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER_NAME}$"; then
        echo "Container is already running."
        echo ""
        echo "To restart: docker restart ${NEO4J_CONTAINER_NAME}"
        echo "To stop:    docker stop ${NEO4J_CONTAINER_NAME}"
        echo "To remove:  docker rm -f ${NEO4J_CONTAINER_NAME}"
        echo ""

        read -p "Do you want to remove and recreate the container? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Removing existing container..."
            docker rm -f ${NEO4J_CONTAINER_NAME}
        else
            echo "Keeping existing container. Exiting."
            exit 0
        fi
    else
        echo "Container exists but is stopped."
        read -p "Do you want to start it? (Y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            docker start ${NEO4J_CONTAINER_NAME}
            echo -e "${GREEN}Neo4j started successfully.${NC}"
            exit 0
        else
            read -p "Do you want to remove and recreate it? (y/N): " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                docker rm ${NEO4J_CONTAINER_NAME}
            else
                exit 0
            fi
        fi
    fi
fi

echo ""

# -----------------------------------------------------------------------------
# Step 3: Create data directories
# -----------------------------------------------------------------------------
echo "[3/6] Creating data directories..."

mkdir -p "${NEO4J_DATA_DIR}/data"
mkdir -p "${NEO4J_DATA_DIR}/logs"
mkdir -p "${NEO4J_DATA_DIR}/import"
mkdir -p "${NEO4J_DATA_DIR}/plugins"

echo "Data will be stored in: ${NEO4J_DATA_DIR}"
echo ""

# -----------------------------------------------------------------------------
# Step 4: Pull Neo4j image
# -----------------------------------------------------------------------------
echo "[4/6] Pulling Neo4j Docker image..."

docker pull neo4j:${NEO4J_VERSION}
echo ""

# -----------------------------------------------------------------------------
# Step 5: Start Neo4j container
# -----------------------------------------------------------------------------
echo "[5/6] Starting Neo4j container..."

docker run -d \
    --name ${NEO4J_CONTAINER_NAME} \
    --restart unless-stopped \
    -p ${NEO4J_HTTP_PORT}:7474 \
    -p ${NEO4J_BOLT_PORT}:7687 \
    -v ${NEO4J_DATA_DIR}/data:/data \
    -v ${NEO4J_DATA_DIR}/logs:/logs \
    -v ${NEO4J_DATA_DIR}/import:/var/lib/neo4j/import \
    -v ${NEO4J_DATA_DIR}/plugins:/plugins \
    -e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD} \
    -e NEO4J_PLUGINS='["apoc"]' \
    -e NEO4J_dbms_security_procedures_unrestricted=apoc.* \
    -e NEO4J_dbms_memory_heap_initial__size=512m \
    -e NEO4J_dbms_memory_heap_max__size=2g \
    -e NEO4J_dbms_memory_pagecache_size=512m \
    neo4j:${NEO4J_VERSION}

echo ""

# -----------------------------------------------------------------------------
# Step 6: Wait for Neo4j to be ready
# -----------------------------------------------------------------------------
echo "[6/6] Waiting for Neo4j to initialize (this may take 30-60 seconds)..."

MAX_ATTEMPTS=30
ATTEMPT=1

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    if curl -s "http://localhost:${NEO4J_HTTP_PORT}" > /dev/null 2>&1; then
        break
    fi
    echo "  Attempt ${ATTEMPT}/${MAX_ATTEMPTS} - waiting..."
    sleep 2
    ATTEMPT=$((ATTEMPT + 1))
done

# -----------------------------------------------------------------------------
# Verification
# -----------------------------------------------------------------------------
if docker ps --format '{{.Names}}' | grep -q "^${NEO4J_CONTAINER_NAME}$"; then
    if curl -s "http://localhost:${NEO4J_HTTP_PORT}" > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}=============================================="
        echo "Neo4j is running successfully!"
        echo "==============================================${NC}"
        echo ""
        echo "Browser:    http://localhost:${NEO4J_HTTP_PORT}"
        echo "Bolt URI:   bolt://localhost:${NEO4J_BOLT_PORT}"
        echo "Username:   neo4j"
        echo "Password:   ${NEO4J_PASSWORD}"
        echo ""
        echo "Add to your .env file:"
        echo "  NEO4J_URI=bolt://localhost:${NEO4J_BOLT_PORT}"
        echo "  NEO4J_URL=bolt://localhost:${NEO4J_BOLT_PORT}"
        echo "  NEO4J_USERNAME=neo4j"
        echo "  NEO4J_USER=neo4j"
        echo "  NEO4J_PASSWORD=${NEO4J_PASSWORD}"
        echo "  NEO4J_DATABASE=neo4j"
        echo ""
        echo "Container management:"
        echo "  Stop:     docker stop ${NEO4J_CONTAINER_NAME}"
        echo "  Start:    docker start ${NEO4J_CONTAINER_NAME}"
        echo "  Logs:     docker logs ${NEO4J_CONTAINER_NAME}"
        echo "  Remove:   docker rm -f ${NEO4J_CONTAINER_NAME}"
        echo ""
        echo -e "${YELLOW}IMPORTANT: Change the password in production!${NC}"
        echo "  Use the Neo4j browser at http://localhost:${NEO4J_HTTP_PORT}"
        echo "  or run: docker exec ${NEO4J_CONTAINER_NAME} cypher-shell -u neo4j -p ${NEO4J_PASSWORD} \"ALTER CURRENT USER SET PASSWORD FROM '${NEO4J_PASSWORD}' TO 'your_new_password'\""
    else
        echo -e "${YELLOW}Container is running but web interface not responding yet.${NC}"
        echo "Wait a minute and try: http://localhost:${NEO4J_HTTP_PORT}"
    fi
else
    echo -e "${RED}ERROR: Container failed to start.${NC}"
    echo "Check logs with: docker logs ${NEO4J_CONTAINER_NAME}"
    exit 1
fi
