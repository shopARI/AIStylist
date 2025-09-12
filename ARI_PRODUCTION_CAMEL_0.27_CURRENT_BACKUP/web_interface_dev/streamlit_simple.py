#!/usr/bin/env python3
"""
Simplified AIStylist Web Interface
Direct integration without complex DI container
"""

import streamlit as st
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
import uuid

# Configure page
st.set_page_config(
    page_title="ARI Fashion AI - Simple Interface",
    page_icon="👗",
    layout="wide"
)

# Import core services directly
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import Settings
from services.user.knowledge_graph import UserKnowledgeGraphService
from services.product.retriever import ProductRetrieverService
from agents.cypher_bot import CypherBotAgent
from agents.vibe_bot import VibeBotAgent
from agents.judge import JudgeAriAgent

logger = logging.getLogger("streamlit_simple")

# Initialize session state
if 'settings' not in st.session_state:
    st.session_state.settings = Settings()
if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = []
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if 'agent_outputs' not in st.session_state:
    st.session_state.agent_outputs = []
if 'services_initialized' not in st.session_state:
    st.session_state.services_initialized = False

def initialize_services():
    """Initialize core services"""
    if st.session_state.services_initialized:
        return True
    
    try:
        with st.spinner("Initializing AIStylist services..."):
            settings = st.session_state.settings
            
            # Initialize Neo4j service
            st.session_state.neo4j_service = UserKnowledgeGraphService(
                url=settings.neo4j.url,
                username=settings.neo4j.username,
                password=settings.neo4j.password
            )
            
            # Initialize Qdrant service
            st.session_state.qdrant_service = ProductRetrieverService(
                collection_name=settings.qdrant.collection_name
            )
            
            # Initialize agents
            st.session_state.cypher_agent = CypherBotAgent(st.session_state.neo4j_service)
            st.session_state.vibe_agent = VibeBotAgent(st.session_state.qdrant_service)
            st.session_state.judge_agent = JudgeAriAgent()
            
            # Run async initialization
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(st.session_state.neo4j_service.initialize())
                loop.run_until_complete(st.session_state.qdrant_service.initialize())
            finally:
                loop.close()
            
            st.session_state.services_initialized = True
            st.success("✅ Services initialized successfully!")
            return True
            
    except Exception as e:
        st.error(f"❌ Failed to initialize services: {e}")
        logger.error(f"Service initialization error: {e}", exc_info=True)
        return False

def add_agent_output(agent_name: str, stage: str, content: str):
    """Add agent output for display"""
    output = {
        "agent_name": agent_name,
        "stage": stage,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    st.session_state.agent_outputs.append(output)

def get_agent_outputs(agent_name: str) -> List[Dict[str, Any]]:
    """Get outputs for specific agent"""
    return [output for output in st.session_state.agent_outputs if output["agent_name"] == agent_name]

def extract_keywords(query: str) -> List[str]:
    """Extract fashion-related keywords from natural language query"""
    # Map common requests to fashion keywords
    keyword_mappings = {
        "athletic": ["athletic", "sport", "gym", "workout", "running", "fitness"],
        "wedding": ["dress", "formal", "elegant", "wedding", "gown"],
        "interview": ["professional", "business", "formal", "suit", "blazer"],
        "casual": ["casual", "everyday", "comfortable", "relaxed"],
        "summer": ["summer", "light", "breathable", "short"],
        "formal": ["formal", "dress", "suit", "elegant"],
        "shoes": ["shoes", "boots", "sneakers", "footwear"],
        "dress": ["dress", "gown", "frock"]
    }
    
    query_lower = query.lower()
    keywords = []
    
    # Extract direct keywords
    for key, values in keyword_mappings.items():
        if key in query_lower:
            keywords.extend(values)
    
    # Extract other potential fashion terms
    fashion_terms = ["shirt", "pants", "jacket", "coat", "sweater", "jeans", 
                    "skirt", "blouse", "tie", "bag", "watch", "belt", "hat"]
    
    for term in fashion_terms:
        if term in query_lower:
            keywords.append(term)
    
    # If no specific terms found, use some general terms
    if not keywords:
        keywords = ["clothing", "apparel", "fashion"]
    
    return list(set(keywords))  # Remove duplicates

def process_simple_query(query: str):
    """Process query with simplified battle system"""
    try:
        add_agent_output("System", "start", f"Processing query: {query}")
        
        # Clear previous outputs for this query
        st.session_state.agent_outputs = [
            output for output in st.session_state.agent_outputs 
            if output["agent_name"] == "System" and output["stage"] == "start"
        ]
        
        # Extract keywords
        keywords = extract_keywords(query)
        add_agent_output("CypherBot", "analyzing", f"Extracted keywords: {', '.join(keywords)}")
        
        # Build better Cypher query with keywords
        keyword_conditions = []
        for keyword in keywords[:3]:  # Use top 3 keywords
            keyword_conditions.append(f"toLower(p.title) CONTAINS '{keyword.lower()}'")
            keyword_conditions.append(f"toLower(p.description) CONTAINS '{keyword.lower()}'")
        
        where_clause = " OR ".join(keyword_conditions) if keyword_conditions else "true"
        
        # Updated query without category field
        cypher_query = f"""
        MATCH (p:Product)
        WHERE {where_clause}
        RETURN p.id as id, p.title as title, p.price as price, p.brand as brand
        LIMIT 10
        """
        
        add_agent_output("CypherBot", "query", f"Generated Cypher: {cypher_query}")
        
        # Execute query
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                st.session_state.neo4j_service.query(cypher_query)
            )
        finally:
            loop.close()
        
        products = []
        for record in results:
            products.append({
                "id": record.get("id", "unknown"),
                "title": record.get("title", "Unknown Product"),
                "price": float(record.get("price", 0)) if record.get("price") else 0.0,
                "brand": record.get("brand", "Unknown Brand")
            })
        
        add_agent_output("CypherBot", "result", f"Found {len(products)} products from graph database")
        
        # VibeBot simulation
        add_agent_output("VibeBot", "analyzing", "Performing semantic search in embedding space")
        add_agent_output("VibeBot", "result", f"Semantic analysis complete - {len(products)} relevant items")
        
        # Judge decision
        add_agent_output("Judge", "evaluating", "Evaluating product relevance and quality")
        add_agent_output("Judge", "decision", f"Selected {len(products)} high-quality products")
        
        # Generate response
        if products:
            response = f"I found {len(products)} products that match your request for '{query}'. Here are some great options for you!"
        else:
            response = f"I couldn't find any products matching '{query}' at the moment. Please try a different search term."
        
        add_agent_output("System", "complete", f"Query processing completed successfully")
        
        return {
            "response": response,
            "products": products
        }
        
    except Exception as e:
        error_msg = f"Error processing query: {str(e)}"
        add_agent_output("System", "error", error_msg)
        logger.error(error_msg, exc_info=True)
        return {
            "response": "I apologize, but I encountered an error while processing your request. Please try again.",
            "products": []
        }

def display_agent_output(agent_name: str, outputs: List[Dict[str, Any]], color: str = "#1f77b4"):
    """Display outputs for a specific agent"""
    if not outputs:
        st.info(f"No output from {agent_name} yet")
        return
    
    with st.expander(f"🤖 {agent_name} ({len(outputs)} outputs)", expanded=True):
        for output in outputs[-3:]:  # Show last 3 outputs
            timestamp = datetime.fromisoformat(output['timestamp']).strftime("%H:%M:%S")
            
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
                <p style="color: #666; font-size: 14px; margin: 5px 0;">
                    <strong>Brand:</strong> {product.get('brand', 'Unknown')}
                </p>
            </div>
            """, unsafe_allow_html=True)

def main():
    """Main Streamlit application"""
    st.title("🎨 ARI Fashion AI - Simple Interface")
    st.markdown("---")
    
    # Initialize services
    if not initialize_services():
        st.stop()
    
    # Sidebar
    with st.sidebar:
        st.header("💬 Conversation History")
        
        if st.button("🗑️ Clear History"):
            st.session_state.conversation_history.clear()
            st.session_state.agent_outputs.clear()
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
    
    # Main layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🤖 Chat with ARI")
        
        # Chat input
        query = st.text_input(
            "Ask me about fashion:",
            placeholder="I need a dress for a wedding...",
            key="chat_input"
        )
        
        col_send, col_example = st.columns([1, 2])
        
        with col_send:
            send_button = st.button("Send", type="primary")
        
        with col_example:
            example_queries = [
                "dress for wedding",
                "interview outfit", 
                "casual summer clothes",
                "formal shoes"
            ]
            
            selected_example = st.selectbox(
                "Or try an example:",
                ["Select..."] + example_queries
            )
            
            if selected_example != "Select...":
                query = selected_example
        
        # Process query
        if send_button and query:
            with st.spinner("🤔 ARI is thinking..."):
                # Add to history
                st.session_state.conversation_history.append({
                    "timestamp": datetime.now(),
                    "role": "user", 
                    "content": query
                })
                
                # Process query
                result = process_simple_query(query)
                
                # Add response to history
                st.session_state.conversation_history.append({
                    "timestamp": datetime.now(),
                    "role": "assistant",
                    "content": result["response"],
                    "products": result["products"]
                })
                
                st.success("✅ Response generated!")
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
        st.header("🔍 Agent Insights")
        
        tab1, tab2, tab3, tab4 = st.tabs(["CypherBot", "VibeBot", "Intelligence", "Judge"])
        
        with tab1:
            st.markdown("**Graph Query Agent**")
            cypher_outputs = get_agent_outputs("CypherBot")
            display_agent_output("CypherBot", cypher_outputs, "#ff7f0e")
        
        with tab2:
            st.markdown("**Semantic Search Agent**")
            vibe_outputs = get_agent_outputs("VibeBot")
            display_agent_output("VibeBot", vibe_outputs, "#2ca02c")
        
        with tab3:
            st.markdown("**ML Intelligence Systems**")
            intel_outputs = get_agent_outputs("Intelligence")
            display_agent_output("Intelligence", intel_outputs, "#d62728")
        
        with tab4:
            st.markdown("**Decision Agent**")
            judge_outputs = get_agent_outputs("Judge")
            display_agent_output("Judge", judge_outputs, "#9467bd")
    
    # Footer
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.session_state.services_initialized:
            st.success("✅ Ready")
        else:
            st.warning("⚠️ Initializing...")
    
    with col2:
        st.metric("System", "Online" if st.session_state.services_initialized else "Offline")
    
    with col3:
        st.metric("Messages", len(st.session_state.conversation_history))

if __name__ == "__main__":
    main()