#!/bin/bash
# Quick launcher for CrewAI Agent Chat

echo "Activating virtual environment..."
source ../crewai_env/bin/activate

echo "Starting CrewAI Agent Chat..."
echo ""

python crewai_agent_chat.py
