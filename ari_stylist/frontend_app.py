"""
Frontend Application for AI Stylist Vector Migration System
Implements the battle interface between CypherBot and VibeBot
"""

import streamlit as st
import asyncio
import logging
from typing import Dict, List, Any, Optional
import json
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("frontend_app")

# Import the backend components
try:
    from hybrid_data_store import HybridDataStore
    from battle_agents import BattleAgents
    from competitive_search_system import CompetitiveSearchSystem
    from user_knowledge_graph_async import UserKnowledgeGraphAsync
    from product_retriever_async import ProductRetrieverAsync
except ImportError as e:
    logger.error(f"Failed to import backend components: {e}")
    # Create mock classes for development
    HybridDataStore = None
    BattleAgents = None
    CompetitiveSearchSystem = None
    UserKnowledgeGraphAsync = None
    ProductRetrieverAsync = None


def create_user_interface():
    """
    Create the Streamlit user interface for the Vector Migration Battle System
    """
    st.set_page_config(
        page_title="AI Stylist - Vector Migration Battle",
        page_icon="🎯",
        layout="wide"
    )
    
    # Initialize session state
    if 'battle_history' not in st.session_state:
        st.session_state.battle_history = []
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'backend_initialized' not in st.session_state:
        st.session_state.backend_initialized = False
    
    # Create the UI
    render_header()
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        render_search_interface()
    
    with col2:
        render_battle_stats()
    
    # Results area
    render_results_area()
    
    # Footer
    render_footer()


def render_header():
    """Render the application header"""
    st.title("🎯 AI Stylist - Vector Migration Battle System")
    st.markdown("""
    **Problem**: Scaling to 6M products with Neo4j  
    **Solution**: Hybrid approach with competing agents
    - **Products**: Qdrant vectors only (drop Neo4j)
    - **Users**: Neo4j graph + Qdrant vectors (hybrid)
    """)
    
    # User login/identification
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user_id = st.text_input("User ID", placeholder="Enter your user ID")
        if user_id and user_id != st.session_state.user_id:
            st.session_state.user_id = user_id
            st.success(f"Logged in as: {user_id}")


def render_search_interface():
    """Render the search interface"""
    st.header("🔍 Product Search")
    
    # Search input
    search_query = st.text_input(
        "What are you looking for?",
        placeholder="e.g., 'red dress for summer wedding'"
    )
    
    # Advanced filters
    with st.expander("Advanced Filters"):
        col1, col2 = st.columns(2)
        
        with col1:
            category = st.selectbox(
                "Category",
                ["All", "Dresses", "Shirts", "Pants", "Shoes", "Accessories"]
            )
            
            price_range = st.slider(
                "Price Range",
                0, 1000, (0, 500),
                format="$%d"
            )
        
        with col2:
            occasion = st.selectbox(
                "Occasion",
                ["Any", "Casual", "Formal", "Wedding", "Party", "Work"]
            )
            
            color = st.multiselect(
                "Colors",
                ["Red", "Blue", "Black", "White", "Green", "Yellow", "Pink"]
            )
    
    # Search button
    if st.button("🚀 Start Battle Search", type="primary", use_container_width=True):
        if search_query:
            with st.spinner("Agents are battling for the best results..."):
                # Simulate battle search
                battle_results = simulate_battle_search(
                    search_query,
                    category=category if category != "All" else None,
                    price_range=price_range,
                    occasion=occasion if occasion != "Any" else None,
                    colors=color if color else None
                )
                
                # Store in session state
                st.session_state.last_battle_results = battle_results
                st.session_state.battle_history.append({
                    'timestamp': datetime.now(),
                    'query': search_query,
                    'results': battle_results
                })
        else:
            st.warning("Please enter a search query")


def render_battle_stats():
    """Render battle statistics"""
    st.header("📊 Battle Statistics")
    
    # Overall stats
    stats = get_battle_stats()
    
    # Win rates
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "CypherBot Wins",
            f"{stats['cypher_wins']}",
            f"{stats['cypher_win_rate']:.1f}%"
        )
    
    with col2:
        st.metric(
            "VibeBot Wins",
            f"{stats['vector_wins']}",
            f"{stats['vector_win_rate']:.1f}%"
        )
    
    # Performance metrics
    st.subheader("⚡ Performance")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "Avg Response Time (Cypher)",
            f"{stats['avg_response_time']['cypher']:.2f}s"
        )
    
    with col2:
        st.metric(
            "Avg Response Time (Vector)",
            f"{stats['avg_response_time']['vector']:.2f}s"
        )
    
    # Win distribution chart
    st.subheader("🏆 Wins by Query Type")
    
    # Create a simple bar chart
    win_data = []
    for query_type, wins in stats['win_by_query_type'].items():
        win_data.append({
            'Query Type': query_type.replace('_', ' ').title(),
            'CypherBot': wins['cypher'],
            'VibeBot': wins['vector']
        })
    
    if win_data:
        st.bar_chart(
            data=win_data,
            x='Query Type',
            y=['CypherBot', 'VibeBot']
        )


def render_results_area():
    """Render the results area"""
    if 'last_battle_results' in st.session_state:
        st.header("🎯 Battle Results")
        
        results = st.session_state.last_battle_results
        
        # Winner announcement
        winner_col1, winner_col2, winner_col3 = st.columns([1, 2, 1])
        with winner_col2:
            if results['winner'] == 'cypher':
                st.success("🏆 CypherBot Wins!")
            else:
                st.info("🏆 VibeBot Wins!")
            
            st.caption(f"Judge's Score: {results['winner_score']:.2f}")
        
        # Show products from both agents
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🤖 CypherBot Results")
            st.caption(f"Response time: {results['cypher_time']:.2f}s")
            
            for product in results['cypher_products']:
                render_product_card(product, "cypher")
        
        with col2:
            st.subheader("🎨 VibeBot Results")
            st.caption(f"Response time: {results['vector_time']:.2f}s")
            
            for product in results['vector_products']:
                render_product_card(product, "vector")
        
        # Judge's explanation
        with st.expander("👩‍⚖️ Judge Ari's Explanation"):
            st.write(results['judge_explanation'])


def render_product_card(product: Dict[str, Any], source: str):
    """Render a product card"""
    with st.container():
        col1, col2 = st.columns([1, 3])
        
        with col1:
            # Placeholder for product image
            st.image(
                "https://via.placeholder.com/100x100?text=Product",
                width=100
            )
        
        with col2:
            st.markdown(f"**{product.get('title', 'Unknown Product')}**")
            st.caption(f"${product.get('price', 0):.2f}")
            
            # Tags
            tags = product.get('tags', [])[:3]
            if tags:
                st.caption(" • ".join(tags))
            
            # Source indicator
            if source == "cypher":
                st.caption("🔍 Found via Neo4j Graph")
            else:
                st.caption("🎯 Found via Vector Search")


def render_footer():
    """Render the footer"""
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption("🎯 Vector Migration Implementation")
    
    with col2:
        if st.session_state.battle_history:
            st.caption(f"Total Battles: {len(st.session_state.battle_history)}")
    
    with col3:
        st.caption("Status: IN PROGRESS")


def simulate_battle_search(
    query: str,
    category: Optional[str] = None,
    price_range: Optional[tuple] = None,
    occasion: Optional[str] = None,
    colors: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Simulate a battle search between CypherBot and VibeBot
    
    In production, this would call the actual battle system
    """
    import random
    
    # Simulate processing time
    cypher_time = random.uniform(0.5, 2.0)
    vector_time = random.uniform(0.3, 1.5)
    
    # Generate mock products
    cypher_products = []
    vector_products = []
    
    for i in range(5):
        # CypherBot products (graph-based)
        cypher_products.append({
            'id': f'cypher_prod_{i}',
            'title': f'{category or "Fashion"} Item {i+1}',
            'price': random.uniform(50, 500),
            'tags': ['graph-match', occasion or 'casual', 'trending'],
            'score': random.uniform(0.7, 1.0)
        })
        
        # VibeBot products (vector-based)
        vector_products.append({
            'id': f'vector_prod_{i}',
            'title': f'Stylish {category or "Item"} {i+1}',
            'price': random.uniform(40, 450),
            'tags': ['vector-match', 'similar-style', colors[0] if colors else 'neutral'],
            'score': random.uniform(0.6, 0.95)
        })
    
    # Determine winner (in production, Ari would judge)
    cypher_avg_score = sum(p['score'] for p in cypher_products) / len(cypher_products)
    vector_avg_score = sum(p['score'] for p in vector_products) / len(vector_products)
    
    winner = 'cypher' if cypher_avg_score > vector_avg_score else 'vector'
    winner_score = max(cypher_avg_score, vector_avg_score)
    
    # Generate judge explanation
    judge_explanation = f"""
    After analyzing both sets of results for "{query}":
    
    CypherBot leveraged the graph structure to find products with strong relational connections,
    particularly excelling at {occasion or 'style'}-based matches.
    
    VibeBot used semantic similarity to find products that capture the essence of "{query}",
    showing strength in understanding natural language nuances.
    
    The winner is {'CypherBot' if winner == 'cypher' else 'VibeBot'} with a score of {winner_score:.2f},
    providing more relevant results for this particular query type.
    """
    
    return {
        'query': query,
        'cypher_products': cypher_products,
        'vector_products': vector_products,
        'cypher_time': cypher_time,
        'vector_time': vector_time,
        'winner': winner,
        'winner_score': winner_score,
        'judge_explanation': judge_explanation
    }


def get_battle_stats() -> Dict[str, Any]:
    """Get battle statistics"""
    # In production, this would fetch from the database
    return {
        'total_battles': 127,
        'cypher_wins': 52,
        'vector_wins': 75,
        'cypher_win_rate': 40.9,
        'vector_win_rate': 59.1,
        'avg_response_time': {
            'cypher': 1.23,
            'vector': 0.87
        },
        'win_by_query_type': {
            'specific_item': {'cypher': 15, 'vector': 8},
            'style_search': {'cypher': 10, 'vector': 25},
            'occasion_based': {'cypher': 18, 'vector': 12},
            'filter_heavy': {'cypher': 9, 'vector': 20},
            'natural_language': {'cypher': 0, 'vector': 10}
        }
    }


if __name__ == "__main__":
    # This allows the module to be run directly
    create_user_interface()
