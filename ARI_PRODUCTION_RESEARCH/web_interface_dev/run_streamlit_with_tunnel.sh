#!/bin/bash

# Set the API base URL to your tunnel URL
# Replace this with your actual tunnel URL for the FastAPI server (port 8000)
export API_BASE_URL="http://localhost:8000"

echo "🚀 Starting Streamlit with API_BASE_URL=$API_BASE_URL"
echo "📝 Edit this script to set your tunnel URL"
echo ""

# Run Streamlit
python -m streamlit run streamlit_real.py --server.port 8504 --server.address 0.0.0.0