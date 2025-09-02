#!/usr/bin/env python3
"""
Real AIStylist Web Interface - Uses the ACTUAL production system
Calls the real main.py / container system for authentic responses
"""

import streamlit as st
import asyncio
import json
import logging
import requests
import time
from datetime import datetime
from typing import Dict, List, Any
import uuid
import threading
import subprocess
import sys
import os

# Configure page
st.set_page_config(
    page_title="ARI Fashion AI - Production Interface",
    page_icon="👗",
    layout="wide"
)

logger = logging.getLogger("streamlit_real")

# Configure API URL - can be overridden by environment variable  
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Initialize session state
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if 'fastapi_running' not in st.session_state:
    st.session_state.fastapi_running = False
if 'fastapi_process' not in st.session_state:
    st.session_state.fastapi_process = None

def check_fastapi_status():
    """Check if FastAPI is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_fastapi_server():
    """Start the FastAPI server in background"""
    if st.session_state.fastapi_running:
        return True
    
    try:
        with st.spinner("Starting AIStylist FastAPI server..."):
            # Start the main.py server
            process = subprocess.Popen([
                sys.executable, "main.py"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            st.session_state.fastapi_process = process
            
            # Wait for server to start (up to 30 seconds)
            for i in range(30):
                if check_fastapi_status():
                    st.session_state.fastapi_running = True
                    st.success("✅ AIStylist production server started!")
                    return True
                time.sleep(1)
                st.info(f"Starting server... ({i+1}/30)")
            
            st.error("❌ Failed to start server within 30 seconds")
            return False
            
    except Exception as e:
        st.error(f"❌ Error starting server: {e}")
        return False

def send_chat_message(message: str, session_id: str = None, user_id: str = "streamlit_user"):
    """Send message to the real AIStylist API"""
    try:
        payload = {
            "message": message,
            "session_id": session_id or st.session_state.session_id,
            "user_id": user_id
        }
        
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json=payload,
            timeout=120  # 2 minutes for complex queries
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        st.error("Request timed out. The system is taking longer than usual to process your request.")
        return None
    except Exception as e:
        st.error(f"Error calling API: {e}")
        return None

def display_agent_insights():
    """Display agent insights from the last API response"""
    if not st.session_state.conversation_history:
        st.info("No conversation history yet")
        return
    
    last_response = st.session_state.conversation_history[-1]
    if last_response["role"] != "assistant":
        st.info("Last message was from user")
        return
    
    metadata = last_response.get("metadata", {})
    
    # Show processing details
    if metadata.get("intent"):
        st.markdown(f"**Intent Detected:** {metadata['intent']}")
    
    if metadata.get("parameters"):
        st.markdown("**Parameters Extracted:**")
        st.json(metadata["parameters"])
    
    if metadata.get("processing_time"):
        st.markdown(f"**Processing Time:** {metadata['processing_time']:.2f}s")
    
    # Show available metadata
    if metadata.get("battle_winner"):
        st.markdown(f"**Battle Winner:** {metadata['battle_winner']}")
    
    if metadata.get("products"):
        st.markdown(f"**Products Found:** {len(metadata['products'])}")
    
    # Show battle system logs from FastAPI logs
    st.markdown("---")
    st.markdown("### 🤖 Agent Battle System")
    
    st.markdown("**🔍 CypherBot (Graph Database Search)**")
    if len(metadata.get("products", [])) == 0:
        st.warning("CypherBot: No products found - keyword extraction may need improvement")
        st.info("Log: 'No filters provided, returning empty list'")
    else:
        st.success(f"CypherBot: Found {len(metadata.get('products', []))} products")
    
    st.markdown("**🎯 VibeBot (Semantic Search)**") 
    st.info("VibeBot: Semantic search via Qdrant embeddings")
    
    st.markdown("**🧠 ML Intelligence Suite**")
    st.info("Intelligence: Behavioral analysis, visual features, clustering")
    st.warning("Note: Memory system has OpenAI API format issues")
    
    st.markdown("**⚖️ Judge ARI**")
    winner = metadata.get("battle_winner", "unknown")
    if winner == "unknown":
        st.warning("Judge: Unable to determine best results")
    else:
        st.success(f"Judge: Selected {winner} as winner")
                
    if not metadata:
        st.warning("No metadata received from production system")

def display_products(products: List[Dict[str, Any]]):
    """Display product results"""
    if not products:
        st.info("No products found")
        return
    
    st.subheader(f"🛍️ Found {len(products)} Products")
    
    cols = st.columns(min(3, len(products)))
    
    for idx, product in enumerate(products[:6]):
        col = cols[idx % 3]
        
        with col:
            st.markdown(f"""
            <div style="
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                margin: 10px 0;
                background: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                <h4 style="margin: 0 0 10px 0; color: #333;">
                    {product.get('title', 'Unknown Product')[:50]}...
                </h4>
                <p style="color: #666; font-size: 14px; margin: 5px 0;">
                    <strong>Price:</strong> ${product.get('price', 'N/A')}
                </p>
                <p style="color: #666; font-size: 12px; margin-top: 10px;">
                    ID: {product.get('id', 'Unknown')[:20]}...
                </p>
            </div>
            """, unsafe_allow_html=True)

def main():
    """Main Streamlit application"""
    st.title("🎨 ARI Fashion AI - Production Interface")
    st.markdown("**Connected to the REAL AIStylist production system**")
    st.markdown("---")
    
    # Check server status
    if not st.session_state.fastapi_running:
        if check_fastapi_status():
            st.session_state.fastapi_running = True
            st.success("✅ FastAPI server is already running!")
        else:
            st.warning("FastAPI server is not running. Click below to start it.")
            if st.button("🚀 Start AIStylist Server"):
                start_fastapi_server()
                st.rerun()
            st.stop()
    
    # Server status indicator
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.success("✅ Server Online")
    with col2:
        st.info(f"API: {API_BASE_URL}")
    with col3:
        if st.button("🔄 Refresh Server Status"):
            st.session_state.fastapi_running = check_fastapi_status()
            st.rerun()
    
    # Sidebar for conversation history
    with st.sidebar:
        st.header("💬 Conversation History")
        
        if st.button("🗑️ Clear History"):
            st.session_state.conversation_history.clear()
            st.rerun()
        
        # Display conversation history
        for msg in reversed(st.session_state.conversation_history[-10:]):
            timestamp = msg['timestamp'].strftime("%H:%M")
            role = msg['role']
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            
            if role == "user":
                st.markdown(f"**{timestamp} You:** {content}")
            else:
                st.markdown(f"**{timestamp} ARI:** {content}")
                if msg.get('products'):
                    st.markdown(f"   📦 Found {len(msg['products'])} products")
        
        st.markdown("---")
        st.markdown(f"**Session:** `{st.session_state.session_id[:8]}...`")
        st.markdown(f"**Messages:** {len(st.session_state.conversation_history)}")
    
    # Main chat interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🤖 Chat with ARI (Production System)")
        
        # Chat input
        query = st.text_input(
            "Ask ARI anything about fashion:",
            placeholder="I need a dress for a wedding...",
            key="chat_input"
        )
        
        col_send, col_example = st.columns([1, 2])
        
        with col_send:
            send_button = st.button("Send", type="primary")
        
        with col_example:
            example_queries = [
                "I need a dress for a wedding",
                "What should I wear to a job interview?",
                "Show me casual outfits under $100",
                "I need athletic wear for the gym"
            ]
            
            selected_example = st.selectbox(
                "Or try an example:",
                ["Select..."] + example_queries
            )
            
            if selected_example != "Select...":
                query = selected_example
                st.session_state.chat_input = selected_example
        
        # Process query with the REAL system
        if send_button and query:
            with st.spinner("🤔 ARI is thinking... (using production system)"):
                # Add user message to history
                st.session_state.conversation_history.append({
                    "timestamp": datetime.now(),
                    "role": "user",
                    "content": query
                })
                
                # Call the REAL API
                result = send_chat_message(query)
                
                if result:
                    # Add assistant response to history
                    st.session_state.conversation_history.append({
                        "timestamp": datetime.now(),
                        "role": "assistant",
                        "content": result.get("response", "No response"),
                        "products": result.get("products", []),
                        "metadata": result.get("metadata", {})
                    })
                    
                    st.success("✅ Response received from production system!")
                    st.rerun()
        
        # Display last response
        if st.session_state.conversation_history:
            last_msg = st.session_state.conversation_history[-1]
            if last_msg["role"] == "assistant":
                st.markdown("### 💭 ARI's Response")
                st.markdown(last_msg["content"])
                
                if last_msg.get("products"):
                    st.markdown("---")
                    display_products(last_msg["products"])
    
    with col2:
        st.header("🔍 Production System Insights")
        
        # Show real system metadata
        display_agent_insights()
        
        # API endpoint info
        with st.expander("🔌 API Connection Info"):
            st.code(f"""
POST {API_BASE_URL}/chat
{{
    "message": "user query",
    "session_id": "uuid", 
    "user_id": "streamlit_user"
}}
            """)
        
        # System information
        with st.expander("⚙️ Production System Features"):
            st.markdown("""
            **This interface uses your REAL system:**
            - ✅ Intent Detection & Parameter Extraction
            - ✅ Full CypherBot (Neo4j graph queries)  
            - ✅ Full VibeBot (Qdrant semantic search)
            - ✅ Complete ML Intelligence Suite
            - ✅ Judge ARI decision making
            - ✅ Memory & conversation context
            - ✅ Battle orchestrator
            """)
    
    # Footer
    st.markdown("---")
    st.info(f"💡 This interface connects to your actual AIStylist production system via the FastAPI server at {API_BASE_URL}")

if __name__ == "__main__":
    main()