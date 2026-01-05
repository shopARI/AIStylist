#!/bin/bash
#
# Run the interactive chat interface for ARI with User Awareness and Onboarding
# NOTE: Prefer run_chat_v2.sh for Flow V2 (faster, cleaner)
#
# Usage: ./run_chat.sh
#

# Load environment variables from .env file
if [ -f ../.env ]; then
    export $(grep -v '^#' ../.env | xargs)
fi

# Set database credentials (localhost for Lambda Labs)
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-shopari1234}"
export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
export QDRANT_API_KEY="${QDRANT_API_KEY:-}"
# OPENAI_API_KEY loaded from .env

echo "Starting ARI - User-Aware Fashion Recommendation System..."
echo ""

# Set PYTHONPATH with ari_crewai_migration first, then parent for shared models
export PYTHONPATH="$(dirname "$0"):$(dirname "$0")/.."

# Change to our directory and run
cd "$(dirname "$0")"
../crewai_env/bin/python cli/chat_interface_v2.py
