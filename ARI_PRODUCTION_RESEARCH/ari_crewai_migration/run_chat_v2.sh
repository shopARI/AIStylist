#!/bin/bash
#
# Run the interactive chat interface for ARI with Flow V2 (pure flow - no agent overhead)
#
# Usage: ./run_chat_v2.sh
#

# Load environment variables from .env file
if [ -f ../.env ]; then
    export $(grep -v '^#' ../.env | xargs)
fi

# Override with explicit database credentials (in case .env is missing them)
# Updated Jan 2026: Use localhost for Lambda Labs (fully self-contained)
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-shopari1234}"
export QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
export QDRANT_API_KEY="${QDRANT_API_KEY:-}"

# Enable Flow V2 (pure flow implementation)
export USE_FLOW_V2=true

echo "=========================================================================="
echo "Starting ARI - Flow V2 (Pure Flow - No Agent Overhead)"
echo "=========================================================================="
echo ""
echo "Configuration:"
echo "  - Flow Version: V2 (pure flow with direct LLM calls)"
echo "  - Model: ${OPENAI_MODEL:-gpt-4o}"
echo "  - Embeddings: text-embedding-ada-002"
echo "  - Neo4j: ${NEO4J_URI}"
echo "  - Qdrant: ${QDRANT_URL}"
echo ""
echo "Features:"
echo "  - Faster execution (2-3x speedup vs V1)"
echo "  - Better search quality (19x improvement with ada-002)"
echo "  - Cleaner architecture (no agent overhead)"
echo ""
echo "Type 'user0' to bypass onboarding for testing"
echo "=========================================================================="
echo ""

# Set PYTHONPATH with ari_crewai_migration first, then parent for shared models
export PYTHONPATH="$(dirname "$0"):$(dirname "$0")/.."

# Change to our directory and run
cd "$(dirname "$0")"
../crewai_env/bin/python cli/chat_interface_v2.py
