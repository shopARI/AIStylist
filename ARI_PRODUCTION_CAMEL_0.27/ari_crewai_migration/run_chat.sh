#!/bin/bash
#
# Run the interactive chat interface for ARI Product Search
#
# Usage: ./run_chat.sh
#

# Set database credentials
export NEO4J_URI="neo4j://34.135.40.119:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="shopari1234"
export QDRANT_URL="https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io:6333"
export QDRANT_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg"
export OPENAI_API_KEY="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"

echo "Starting ARI Product Search Chat Interface..."
echo ""

# Use the crewai virtual environment Python
../crewai_env/bin/python chat_interface.py
