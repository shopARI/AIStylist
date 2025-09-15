#!/usr/bin/env python3
"""
AIStylist Multi-Agent Web Interface
Real-time chat interface with visibility into all agent thinking processes
"""

import streamlit as st
import asyncio
import json
import time
import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
import pandas as pd

# Configure page
st.set_page_config(
    page_title="ARI Fashion AI - Multi-Agent Interface",
    page_icon="👗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Import our application services
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from di.streamlit_container import initialize_streamlit_container, cleanup_streamlit_container
from services.streamlit_service import StreamlitApplicationService

# Configure logging to capture agent outputs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamlit_app")

@dataclass
class AgentOutput:
    """Structure for capturing agent outputs"""
    agent_name: str
    timestamp: datetime
    stage: str
    content: str
    metadata: Dict[str, Any] = None

class AgentOutputCollector:
    """Collects outputs from all agents during processing"""
    
    def __init__(self):
        self.outputs: List[AgentOutput] = []
        self.current_session = str(uuid.uuid4())
        
    def add_output(self, agent_name: str, stage: str, content: str, metadata: Dict = None):
        """Add an agent output"""
        output = AgentOutput(
            agent_name=agent_name,
            timestamp=datetime.now(),
            stage=stage,
            content=content,
            metadata=metadata or {}
        )
        self.outputs.append(output)
        
    def get_outputs_by_agent(self, agent_name: str) -> List[AgentOutput]:
        """Get all outputs for a specific agent"""
        return [output for output in self.outputs if output.agent_name == agent_name]
    
    def clear(self):
        """Clear all outputs"""
        self.outputs.clear()

# Initialize session state
def init_session_state():
    """Initialize Streamlit session state"""
    if 'container' not in st.session_state:
        st.session_state.container = None
    if 'app_service' not in st.session_state:
        st.session_state.app_service = None
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if 'agent_collector' not in st.session_state:
        st.session_state.agent_collector = AgentOutputCollector()
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'last_query_results' not in st.session_state:
        st.session_state.last_query_results = {}

def initialize_application():
    """Initialize the application container and services"""
    if st.session_state.container is None:
        try:
            with st.spinner("Initializing AIStylist system..."):
                # Run async initialization in a thread
                import asyncio
                import threading
                
                def run_async_init():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        container = loop.run_until_complete(initialize_streamlit_container())
                        app_service = container.application_service()
                        return container, app_service
                    finally:
                        loop.close()
                
                container, app_service = run_async_init()
                
                st.session_state.container = container
                st.session_state.app_service = app_service
                
                st.success(" AIStylist system initialized successfully!")
                return True
        except Exception as e:
            st.error(f" Failed to initialize system: {e}")
            logger.error(f"Initialization error: {e}", exc_info=True)
            return False
    return True

def display_agent_output(agent_name: str, outputs: List[Dict[str, Any]], color: str = "#1f77b4"):
    """Display outputs for a specific agent"""
    if not outputs:
        st.info(f"No output from {agent_name} yet")
        return
    
    # Create expandable section for each agent
    with st.expander(f" {agent_name} ({len(outputs)} outputs)", expanded=True):
        for output in outputs[-3:]:  # Show last 3 outputs
            timestamp = datetime.fromisoformat(output['timestamp']).strftime("%H:%M:%S")
            
            # Color-coded output based on agent
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, {color}20, transparent);
                border-left: 4px solid {color};
                padding: 10px;
                margin: 5px 0;
                border-radius: 5px;
            ">
                <small><strong>{timestamp}</strong> - {output['stage']}</small><br>
                <div style="font-family: monospace; font-size: 12px; margin-top: 5px;">
                    {output['content']}
                </div>
            </div>
            """, unsafe_allow_html=True)

def display_products(products: List[Dict[str, Any]]):
    """Display product results in an attractive format"""
    if not products:
        st.info("No products found")
        return
    
    st.subheader(f"🛍️ Found {len(products)} Products")
    
    # Display products in columns
    cols = st.columns(min(3, len(products)))
    
    for idx, product in enumerate(products[:6]):  # Show max 6 products
        col = cols[idx % 3]
        
        with col:
            # Product card
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
                <p style="color: #666; font-size: 14px; margin: 5px 0;">
                    <strong>Category:</strong> {product.get('category', 'Unknown')}
                </p>
                <p style="color: #666; font-size: 12px; margin-top: 10px;">
                    ID: {product.get('id', 'Unknown')[:20]}...
                </p>
            </div>
            """, unsafe_allow_html=True)

def process_query(query: str, user_id: str = "streamlit_user"):
    """Process a query and collect agent outputs"""
    st.session_state.processing = True
    
    try:
        # Add query to conversation history
        st.session_state.conversation_history.append({
            "timestamp": datetime.now(),
            "role": "user",
            "content": query
        })
        
        # Process the message in async context
        def run_async_query():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(st.session_state.app_service.process_message(
                    session_id=st.session_state.session_id,
                    message=query,
                    user_id=user_id
                ))
            finally:
                loop.close()
        
        response = run_async_query()
        
        # Add response to conversation history
        st.session_state.conversation_history.append({
            "timestamp": datetime.now(),
            "role": "assistant",
            "content": response.response,
            "products": response.products,
            "metadata": response.metadata
        })
        
        # Store results for agent display
        st.session_state.last_query_results = {
            "response": response.response,
            "products": response.products,
            "metadata": response.metadata
        }
        
        return response
        
    except Exception as e:
        st.error(f"Error processing query: {e}")
        logger.error(f"Query processing error: {e}", exc_info=True)
        return None
    finally:
        st.session_state.processing = False

def main():
    """Main Streamlit application"""
    init_session_state()
    
    # Header
    st.title(" ARI Fashion AI - Multi-Agent Interface")
    st.markdown("---")
    
    # Initialize application
    if not initialize_application():
        st.stop()
    
    # Sidebar for conversation history
    with st.sidebar:
        st.header("💬 Conversation History")
        
        if st.button("🗑️ Clear History"):
            st.session_state.conversation_history.clear()
            if st.session_state.app_service:
                st.session_state.app_service.clear_agent_outputs()
            st.rerun()
        
        # Display conversation history
        for i, msg in enumerate(reversed(st.session_state.conversation_history[-10:])):
            timestamp = msg['timestamp'].strftime("%H:%M")
            role = msg['role']
            content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
            
            if role == "user":
                st.markdown(f"**{timestamp} You:** {content}")
            else:
                st.markdown(f"**{timestamp} ARI:** {content}")
                if msg.get('products'):
                    st.markdown(f"   📦 Found {len(msg['products'])} products")
        
        # Session info
        st.markdown("---")
        st.markdown(f"**Session ID:** `{st.session_state.session_id[:8]}...`")
        st.markdown(f"**Messages:** {len(st.session_state.conversation_history)}")
    
    # Main interface layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header(" Chat with ARI")
        
        # Chat input
        query = st.text_input(
            "Ask me about fashion, outfits, or products:",
            placeholder="I need a dress for a wedding...",
            key="chat_input"
        )
        
        col_send, col_example = st.columns([1, 2])
        
        with col_send:
            send_button = st.button("Send", type="primary", disabled=st.session_state.processing)
        
        with col_example:
            example_queries = [
                "I need a dress for a wedding",
                "What should I wear to a job interview?",
                "Show me casual outfits under $100",
                "I need formal shoes for men"
            ]
            
            selected_example = st.selectbox(
                "Or try an example:",
                ["Select an example..."] + example_queries,
                key="example_selector"
            )
            
            if selected_example != "Select an example...":
                query = selected_example
                st.session_state.chat_input = selected_example
        
        # Process query
        if send_button and query:
            with st.spinner("🤔 ARI is thinking..."):
                response = process_query(query)
                
                if response:
                    st.success(" Response generated!")
                    st.rerun()
        
        # Display current response and products
        if st.session_state.last_query_results:
            results = st.session_state.last_query_results
            
            st.markdown("### 💭 ARI's Response")
            st.markdown(results["response"])
            
            if results["products"]:
                st.markdown("---")
                display_products(results["products"])
            
            # Metadata
            if results.get("metadata"):
                with st.expander("📊 Technical Details"):
                    st.json(results["metadata"])
    
    with col2:
        st.header(" Agent Insights")
        
        # Tabs for different agent views
        tab1, tab2, tab3, tab4 = st.tabs(["CypherBot", "VibeBot", "Intelligence", "Judge"])
        
        with tab1:
            st.markdown("**Graph Query Agent**")
            cypher_outputs = st.session_state.app_service.get_agent_outputs("CypherBot") if st.session_state.app_service else []
            display_agent_output("CypherBot", cypher_outputs, "#ff7f0e")
            
            # Show sample Cypher queries
            if st.button("Show Sample Queries", key="cypher_samples"):
                st.code("""
                // Wedding dress query
                MATCH (p:Product)-[:BELONGS_TO]->(c:Category)
                WHERE c.name CONTAINS 'dress' 
                AND p.title =~ '(?i).*(wedding|formal|elegant).*'
                RETURN p LIMIT 10
                
                // Interview outfit query
                MATCH (p:Product)-[:SUITABLE_FOR]->(o:Occasion {name: 'interview'})
                RETURN p LIMIT 10
                """, language="cypher")
        
        with tab2:
            st.markdown("**Semantic Search Agent**")
            vibe_outputs = st.session_state.app_service.get_agent_outputs("VibeBot") if st.session_state.app_service else []
            display_agent_output("VibeBot", vibe_outputs, "#2ca02c")
            
            # Show embedding info
            if st.button("Embedding Stats", key="embedding_stats"):
                st.metric("Embedding Dimension", "1536")
                st.metric("Vector Database", "Qdrant")
                st.metric("Similarity Metric", "Cosine")
        
        with tab3:
            st.markdown("**ML Intelligence Systems**")
            intel_outputs = st.session_state.app_service.get_agent_outputs("Intelligence") if st.session_state.app_service else []
            display_agent_output("Intelligence", intel_outputs, "#d62728")
            
            # Show intelligence modules
            st.markdown("**Active Modules:**")
            st.markdown("-  Behavioral Intelligence")
            st.markdown("- 👁️ Visual Intelligence") 
            st.markdown("-  Clustering Intelligence")
            st.markdown("- 💭 Memory-RAG")
        
        with tab4:
            st.markdown("**Decision Making Agent**")
            judge_outputs = st.session_state.app_service.get_agent_outputs("Judge") if st.session_state.app_service else []
            display_agent_output("Judge", judge_outputs, "#9467bd")
            
            # Show decision criteria
            if st.button("Decision Criteria", key="judge_criteria"):
                st.markdown("""
                **Judge ARI evaluates:**
                - Relevance to query
                - Product quality scores
                - Price appropriateness  
                - Style consistency
                - Occasion suitability
                """)
    
    # Footer
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.session_state.processing:
            st.warning("🔄 Processing...")
        else:
            st.success(" Ready")
    
    with col2:
        st.metric("System Status", "Online" if st.session_state.container else "Offline")
    
    with col3:
        st.metric("Session", f"{len(st.session_state.conversation_history)} messages")

# Custom CSS for better styling
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .agent-output {
        background: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
    
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

if __name__ == "__main__":
    main()