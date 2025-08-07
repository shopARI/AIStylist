"""
Enhanced Asynchronous AI Stylist Application

Main application entry point for the AI Stylist system with persistent memory support.
Implements user identification and cross-session memory.
Compatible with CAMEL-AI 0.2.59+.

MIGRATED: Now uses AgentFactory instead of AsyncCAMELService for CAMEL 0.2.59+ compatibility.
INTEGRATED: Now uses HybridDataStore for product operations (Qdrant) and UserKnowledgeGraph for users (Neo4j).
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
import httpx
import datetime
import uuid


# Configure logging first, before any other imports
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhanced_ai_stylist_app_async")

# Import new agent factory instead of AsyncCAMELService
from agent_factory import get_agent_factory

# Import the new memory integration 
from memory_integration_async import (
    MemoryManager,
    setup_stylist_memory_async,  # Backward compatibility function
    save_memory_for_user_async,  # Backward compatibility function
    optimize_memory_async,  # Backward compatibility function
    extract_preferences_from_memory_async  # Backward compatibility function
)

# Import the enhanced stylist agent
from stylist_agent_async import create_stylist_agent_async

# UPDATED IMPORTS: Use UserKnowledgeGraph and HybridDataStore
from user_knowledge_graph_async import UserKnowledgeGraphAsync
from hybrid_data_store import HybridDataStore
from product_retriever_async import ProductRetrieverAsync

# Import battle system components
from battle_agents import BattleAgents
from competitive_search_system import CompetitiveSearchSystem

# Import the enhanced chat manager
from chat_session_manager_async import EnhancedChatManagerAsync

# Import the enhanced recommender manager
from enhanced_recommender_manager_async import EnhancedRecommenderManagerAsync


class EnhancedAIStylistApp:
    """
    Enhanced AI Stylist application with persistent memory and user identification.
    Implements cross-session memory and improved personalization.
    Compatible with CAMEL-AI 0.2.59+.
    
    MIGRATED: Now properly integrates with CAMEL 0.2.59+ using AgentFactory.
    INTEGRATED: Uses HybridDataStore for intelligent routing of product/user operations.
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        """Initialize with CAMEL-AI 0.2.64 verification and HybridDataStore"""
        logger.info("Initializing Enhanced AI Stylist with HybridDataStore integration...")
        
        # VERIFY CAMEL VERSION
        try:
            from camel import __version__ as camel_version
            if not camel_version.startswith('0.2.64'):
                logger.warning(f"CAMEL version {camel_version} may not be fully compatible")
            else:
                logger.info(f"✅ CAMEL-AI version {camel_version} verified")
        except:
            logger.warning("Could not verify CAMEL-AI version")
    
        # Use provided credentials or environment variables with defaults
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "shopari1234")
        
        # Read Qdrant configuration from environment
        self.qdrant_url = os.environ.get("QDRANT_URL")
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY")
        self.qdrant_collection_name = os.environ.get("QDRANT_COLLECTION_NAME", "fashion_products")
        
        # UPDATED: Set up UserKnowledgeGraph for user operations only
        logger.info(f"Connecting to Neo4j at {self.neo4j_url} for user operations")
        self.user_kg = UserKnowledgeGraphAsync(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password
        )
        
        # Set up ProductRetriever for Qdrant operations
        logger.info("Initializing product retriever for Qdrant operations...")
        if self.qdrant_url and self.qdrant_api_key:
            logger.info(f"Using remote Qdrant at {self.qdrant_url}")
            self.product_retriever = ProductRetrieverAsync(
                qdrant_url=self.qdrant_url,
                qdrant_api_key=self.qdrant_api_key,
                collection_name=self.qdrant_collection_name
            )
        else:
            logger.info("Using local Qdrant instance")
            self.product_retriever = ProductRetrieverAsync(
                collection_name=self.qdrant_collection_name
            )
        
        # NEW: Initialize HybridDataStore for intelligent routing
        logger.info("Initializing HybridDataStore for intelligent operation routing...")
        self.data_store = HybridDataStore(
            neo4j_client=self.user_kg,
            qdrant_client=self.product_retriever
        )
        
        # NEW: Initialize Battle System for competitive product search
        logger.info("Initializing Battle System for competitive search...")
        self.battle_agents = BattleAgents(
            neo4j_client=self.user_kg,
            qdrant_retriever=self.product_retriever
        )
        self.competitive_search = CompetitiveSearchSystem(self.battle_agents)
        
        # MIGRATED: Use AgentFactory instead of AsyncCAMELService
        self.agent_factory = get_agent_factory()
        logger.info("Initialized AgentFactory for CAMEL 0.2.59+")
        
        # MIGRATED: Initialize MemoryManager for new memory APIs
        self.memory_manager = MemoryManager(self.user_kg)
        logger.info("Initialized MemoryManager for CAMEL 0.2.59+")
        
        # Initialize the enhanced memory system with backward compatibility wrapper
        logger.info("Setting up enhanced memory system...")
        self.memory_setup_func = self._setup_memory_for_user
        
        # UPDATED: Initialize recommender manager with HybridDataStore
        logger.info("Initializing enhanced recommender manager with HybridDataStore...")
        self.enhanced_recommender_manager = EnhancedRecommenderManagerAsync(
            data_store=self.data_store,  # Pass HybridDataStore for product operations
            user_kg=self.user_kg,  # Pass UserKG for user operations
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func,
            stylist_agent=None  # Will be set per session
        )
        
        # UPDATED: Pass components to chat manager
        logger.info("Creating enhanced chat manager with ML integration and HybridDataStore...")
        self.chat_manager = EnhancedChatManagerAsync(
            stylist_agent=None,  # Will be set per session
            user_kg=self.user_kg,  # For user operations
            data_store=self.data_store,  # For product operations
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func,
            parent_app=self,  # Pass self reference for ML access
            competitive_search=self.competitive_search  # Pass competitive search system
        )
        
        # Track active sessions
        self.active_sessions = {}
        
        # User registry for cross-session support
        self.registered_users = {}
        
        # Memory optimization settings
        self.memory_optimization_interval = 3600  # 1 hour
        self.memory_optimization_task = None
        
        # Start the memory optimization task
        self.memory_optimization_task = asyncio.create_task(self._memory_optimization_worker())
        
        # Verify and update database schema
        asyncio.create_task(self._setup_database_schema())
        
        logger.info("✅ Enhanced AI Stylist initialized with HybridDataStore and Battle System!")
    
    async def _setup_memory_for_user(self, user_id=None, neo4j_client=None):
        """
        Backward compatibility wrapper for memory setup.
        Uses the new MemoryManager internally.
        """
        return await self.memory_manager.create_memory(
            user_id=user_id,
            enable_mcp=True
        )
    
    async def _setup_database_schema(self):
        """Set up and verify the database schema"""
        try:
            # Ensure the Neo4j schema is set up for user operations
            if hasattr(self.user_kg, 'ensure_schema'):
                await self.user_kg.ensure_schema()
            
            # Get basic database statistics
            stats = await self.data_store.get_stats()
            logger.info(f"HybridDataStore statistics: {stats}")
                
        except Exception as e:
            logger.error(f"Error setting up database schema: {e}")
            logger.warning("Continuing with limited database functionality")
    
    async def _memory_optimization_worker(self):
        """
        Background task to periodically optimize memory for all sessions
        """
        try:
            while True:
                # Sleep for the optimization interval
                await asyncio.sleep(self.memory_optimization_interval)
                
                # Get active sessions with persistent memory
                persistent_sessions = {
                    session_id: session
                    for session_id, session in self.active_sessions.items()
                    if hasattr(session, 'user_id') and session.user_id and hasattr(session, 'memory') and session.memory
                }
                
                logger.info(f"Running memory optimization for {len(persistent_sessions)} sessions")
                
                # Optimize memory for each session
                for session_id, session in persistent_sessions.items():
                    try:
                        # MIGRATED: Use optimize_memory_async from memory_integration_v2
                        await optimize_memory_async(
                            memory=session.memory,
                            user_id=session.user_id,
                            neo4j_client=self.user_kg
                        )
                        logger.info(f"Optimized memory for session {session_id}, user {session.user_id}")
                    except Exception as e:
                        logger.error(f"Error optimizing memory for session {session_id}: {e}")
                
        except asyncio.CancelledError:
            # Task was cancelled - log and exit gracefully
            logger.info("Memory optimization task cancelled")
        
        except Exception as e:
            logger.error(f"Error in memory optimization worker: {e}")
    
    async def create_session(self, user_id=None):
        """Create a new chat session with proper error handling."""
        try:
            # Check existing sessions
            if user_id and user_id in self.registered_users:
                existing_session_id = self.registered_users[user_id]
                if existing_session_id in self.active_sessions:
                    return existing_session_id
            
            # Create session through chat manager
            session = await self.chat_manager.get_or_create_session(user_id=user_id)
            
            # Ensure session has ID
            if not hasattr(session, 'session_id') or not session.session_id:
                session.session_id = str(uuid.uuid4())
            
            # Create memory and agent
            if not hasattr(session, 'memory') or not session.memory:
                memory = await self.memory_manager.create_memory(
                    user_id=user_id, enable_mcp=True
                )
                session.memory = memory
            
            if not hasattr(session, 'stylist_agent') or not session.stylist_agent:
                agent_factory = get_agent_factory()  # Use sync version
                stylist_agent = await agent_factory.create_stylist_agent(
                    memory=session.memory, enable_mcp=True
                )
                session.stylist_agent = stylist_agent
            
            # Store session
            self.active_sessions[session.session_id] = session
            if user_id:
                self.registered_users[user_id] = session.session_id
            
            # Update the enhanced recommender manager with this session's stylist agent
            if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                # Update the ensemble recommender with the session's stylist agent
                if hasattr(self.enhanced_recommender_manager, 'ensemble') and self.enhanced_recommender_manager.ensemble:
                    self.enhanced_recommender_manager.ensemble.stylist_agent = session.stylist_agent
                    logger.info("Updated ensemble recommender with session stylist agent")
            
            logger.info(f"Created new session: {session.session_id} for user: {user_id}")
            
            return session.session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            # Create minimal fallback
            session_id = str(uuid.uuid4())
            return session_id
    
    async def send_message(self, session_id, message):
        """
        Send a message to the stylist and get a response.
        
        Args:
            session_id: Session ID
            message: User message
            
        Returns:
            Tuple of (response, additional data)
        """
        if not session_id:
            logger.error("No session ID provided")
            return "I'm sorry, there was an issue with your session. Let's start a new conversation.", {
                "error": "No session ID provided"
            }
            
        # Check if session exists
        if session_id not in self.active_sessions:
            try:
                # Try to get the session from the chat manager
                session = await self.chat_manager.get_or_create_session(session_id=session_id)
                
                if not hasattr(session, 'stylist_agent') or not session.stylist_agent:
                    # MIGRATED: Create agent using new patterns
                    memory = await self.memory_manager.create_memory(
                        user_id=session.user_id if hasattr(session, 'user_id') else None,
                        enable_mcp=True
                    )
                    
                    stylist_agent = await self.agent_factory.create_stylist_agent(
                        memory=memory,
                        enable_mcp=True
                    )
                    session.stylist_agent = stylist_agent
                    session.memory = memory
                    
                    # Update the enhanced recommender manager
                    if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                        if hasattr(self.enhanced_recommender_manager, 'ensemble') and self.enhanced_recommender_manager.ensemble:
                            self.enhanced_recommender_manager.ensemble.stylist_agent = stylist_agent
                
                # Add to active sessions
                self.active_sessions[session_id] = session
                logger.info(f"Recovered session: {session_id}")
                
                # Register user with this session if applicable
                if hasattr(session, 'user_id') and session.user_id:
                    self.registered_users[session.user_id] = session_id
                
            except Exception as e:
                logger.error(f"Error recovering session {session_id}: {e}")
                return "I'm sorry, I couldn't find your previous conversation. Let's start a new one.", {
                    "error": f"Session not found: {session_id}"
                }
        
        # Get the session
        session = self.active_sessions[session_id]
        
        # Process the message using the chat manager
        try:
            logger.info(f"🚀 Processing message for session {session_id} with FULL ML integration and Battle System")
            response, data = await self.chat_manager.process_message(
                session_id=session_id,
                user_id=session.user_id if hasattr(session, 'user_id') else None,
                message=message
            )
            
            # If products were recommended, record interactions
            if 'products' in data and session_id in self.active_sessions:
                session = self.active_sessions[session_id]
                user_id = session.user_id if hasattr(session, 'user_id') else None
                
                if user_id and hasattr(session, 'record_product_interaction'):
                    for product in data['products']:
                        if 'id' in product:
                            await session.record_product_interaction(
                                product_id=product['id'],
                                interaction_type="recommended"
                            )
            
            # Save memory state if user_id is available
            if hasattr(session, 'user_id') and session.user_id and hasattr(session, 'memory') and session.memory:
                try:
                    # MIGRATED: Use MemoryManager for saving
                    await self.memory_manager.save_memory(
                        memory=session.memory,
                        user_id=session.user_id
                    )
                    logger.info(f"Saved memory state for user {session.user_id}")
                except Exception as e:
                    logger.error(f"Error saving memory state: {e}")
            
            return response, data
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I'm sorry, I encountered an issue while processing your request. Could you try rephrasing or asking something else?", {
                "error": str(e)
            }
    
    async def get_session(self, session_id):
        """Get a session by ID with proper error handling."""
        if not session_id:
            return None
            
        # Check active sessions first
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
            
        # Try to get from chat manager
        try:
            session = await self.chat_manager.get_or_create_session(session_id=session_id)
            if session:
                self.active_sessions[session_id] = session
                return session
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            
        return None
    
    async def get_product_recommendations(self, session_id, product_id=None, query=None, limit=5, occasion=None):
        """
        Enhanced recommendation system using HybridDataStore and Battle System
        
        This is the CORE ML ENSEMBLE METHOD that should be used for all recommendations
        
        Args:
            session_id: Session ID
            product_id: Optional product ID for similar products
            query: Optional search query
            limit: Maximum number of recommendations
            occasion: Optional occasion to filter recommendations
            
        Returns:
            List of recommended products
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return []
            
        user_id = session.user_id if hasattr(session, 'user_id') else None
        
        # Extract occasion from query if not provided
        if query and not occasion:
            occasions = ["wedding", "party", "work", "casual", "formal", "date", "dinner", "beach"]
            seasons = ["summer", "winter", "fall", "spring"]
            
            query_lower = query.lower()
            
            for occ in occasions:
                if occ in query_lower:
                    occasion = occ
                    break
                    
            if not occasion:
                for season in seasons:
                    if season in query_lower:
                        for occ in occasions:
                            if occ in query_lower:
                                occasion = f"{season} {occ}"
                                break
        
        # Try different recommendation strategies
        
        # 1. If query is provided, use competitive search system
        if query:
            try:
                logger.info(f"🎯 Using Battle System for query: {query}")
                
                # Build filters from occasion and user preferences
                filters = {}
                if occasion:
                    filters['occasion'] = occasion
                
                if hasattr(session, 'get_or_fetch_user_preferences'):
                    user_preferences = await session.get_or_fetch_user_preferences()
                    if user_preferences.get('budget_range'):
                        filters['min_price'] = user_preferences['budget_range'].get('min')
                        filters['max_price'] = user_preferences['budget_range'].get('max')
                
                # Execute battle search
                battle_results = await self.competitive_search.execute_battle(
                    query=query,
                    filters=filters,
                    limit=limit,
                    user_context=user_preferences if 'user_preferences' in locals() else None
                )
                
                # Extract winning results
                judgment = battle_results.get('judgment', {})
                winner = judgment.get('winner', 'vector')
                
                if winner == 'cypher':
                    results = battle_results['agents']['cypher']['products']
                    logger.info(f"🏆 CypherBot won with {len(results)} products")
                else:
                    results = battle_results['agents']['vector']['products']
                    logger.info(f"🏆 VibeBot won with {len(results)} products")
                
                if results:
                    # Filter valid products
                    filtered_results = self._filter_valid_products(results)
                    if filtered_results:
                        await self._record_product_interactions(session, filtered_results)
                        return filtered_results[:limit]
                        
            except Exception as e:
                logger.error(f"Battle system failed: {e}")
        
        # 2. If product_id provided, get similar products
        if product_id:
            try:
                logger.info(f"Getting similar products for: {product_id}")
                similar = await self.data_store.get_similar_products(product_id, limit)
                if similar:
                    filtered = self._filter_valid_products(similar)
                    if filtered:
                        await self._record_product_interactions(session, filtered)
                        return filtered
            except Exception as e:
                logger.error(f"Similar products search failed: {e}")
        
        # 3. Try enhanced recommender system
        if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
            try:
                logger.info("Using enhanced recommender system")
                results = await self.enhanced_recommender_manager.get_recommendations(
                    user_id=user_id,
                    session_id=session_id,
                    product_id=product_id,
                    query=query or occasion,
                    limit=limit
                )
                if results:
                    filtered = self._filter_valid_products(results)
                    if filtered:
                        await self._record_product_interactions(session, filtered)
                        return filtered
            except Exception as e:
                logger.error(f"Enhanced recommender failed: {e}")
        
        # 4. Fallback to popular products
        try:
            logger.info("Falling back to popular products")
            popular = await self.data_store.get_popular_products(limit)
            if popular:
                filtered = self._filter_valid_products(popular)
                if filtered:
                    await self._record_product_interactions(session, filtered)
                    return filtered
        except Exception as e:
            logger.error(f"Popular products fallback failed: {e}")
        
        logger.warning("All recommendation methods failed")
        return []

    def _filter_valid_products(self, products):
        """Filter out invalid products (test products, zero prices, etc.)"""
        if not products:
            return []
            
        filtered_results = []
        for product in products:
            if (product.get('price', 0) > 0 and 
                product.get('title') and 
                'test' not in product.get('title', '').lower() and
                'untitled' not in product.get('title', '').lower()):
                filtered_results.append(product)
        
        return filtered_results

    async def _record_product_interactions(self, session, products):
        """Record product interactions for recommendations"""
        try:
            if hasattr(session, 'record_product_interaction'):
                for product in products:
                    if 'id' in product:
                        await session.record_product_interaction(
                            product_id=product['id'],
                            interaction_type="recommended"
                        )
        except Exception as e:
            logger.error(f"Error recording product interactions: {e}")

    async def record_product_interaction(self, session_id, product_id, interaction_type="viewed"):
        """
        Record a product interaction for a user using HybridDataStore.
        
        Args:
            session_id: Session ID
            product_id: Product ID
            interaction_type: Type of interaction (e.g., "viewed", "liked", "purchased")
            
        Returns:
            True if successful, False otherwise
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False
            
        try:
            # Use session's record_product_interaction method if available
            if hasattr(session, 'record_product_interaction'):
                return await session.record_product_interaction(
                    product_id=product_id,
                    interaction_type=interaction_type
                )
            
            # Get user ID from session
            user_id = session.user_id if hasattr(session, 'user_id') else None
            
            if not user_id:
                logger.warning(f"Cannot record interaction: no user ID for session {session_id}")
                return False
            
            # Record interaction through data store
            return await self.data_store.record_interaction(
                user_id=user_id,
                product_id=product_id,
                interaction_type=interaction_type
            )
            
        except Exception as e:
            logger.error(f"Error recording product interaction: {e}")
            return False
    
    async def add_user_preference(self, session_id, preference_type, preference_value):
        """
        Add a user preference using UserKnowledgeGraph.
        
        Args:
            session_id: Session ID
            preference_type: Type of preference (e.g., "color", "style", "budget")
            preference_value: Value of the preference
            
        Returns:
            True if successful, False otherwise
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return False
            
        try:
            # Use session's add_preference method if available
            if hasattr(session, 'add_preference'):
                return await session.add_preference(
                    preference_type=preference_type,
                    preference_value=preference_value
                )
            
            # Get user ID from session
            user_id = session.user_id if hasattr(session, 'user_id') else None
            
            if not user_id:
                logger.warning(f"Cannot add preference: no user ID for session {session_id}")
                return False
            
            # Add preference through user_kg
            return await self.user_kg.update_user_preference(
                user_id=user_id,
                preference_type=preference_type,
                preference_value=preference_value
            )
            
        except Exception as e:
            logger.error(f"Error adding user preference: {e}")
            return False
    
    async def get_user_preferences(self, session_id):
        """
        Get user preferences for a session using UserKnowledgeGraph.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary of user preferences
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return {}
            
        try:
            # Use session's get_or_fetch_user_preferences method if available
            if hasattr(session, 'get_or_fetch_user_preferences'):
                return await session.get_or_fetch_user_preferences()
            
            # Get user ID from session
            user_id = session.user_id if hasattr(session, 'user_id') else None
            
            if not user_id:
                logger.warning(f"Cannot get preferences: no user ID for session {session_id}")
                return {}
            
            # Get from user_kg directly
            preferences = await self.user_kg.get_user_preferences(user_id)
            return preferences
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}
    
    async def close(self):
        """Clean up resources and close connections"""
        try:
            # Cancel the memory optimization task
            if self.memory_optimization_task:
                self.memory_optimization_task.cancel()
                try:
                    await self.memory_optimization_task
                except asyncio.CancelledError:
                    pass
            
            # Final memory persistence for all sessions
            for session_id, session in self.active_sessions.items():
                if hasattr(session, 'user_id') and session.user_id and hasattr(session, 'memory') and session.memory:
                    try:
                        logger.info(f"Performing final memory persistence for user {session.user_id}")
                        # MIGRATED: Use MemoryManager for final save
                        await self.memory_manager.save_memory(session.memory, session.user_id)
                    except Exception as e:
                        logger.error(f"Error in final memory persistence for session {session_id}: {e}")
            
            # Close session resources
            for session_id, session in self.active_sessions.items():
                if hasattr(session, 'close'):
                    try:
                        await session.close()
                    except Exception as e:
                        logger.error(f"Error closing session {session_id}: {e}")
            
            # Close data store connections
            if hasattr(self.user_kg, 'close'):
                await self.user_kg.close()
            
            # Clean up AgentFactory resources
            await self.agent_factory.cleanup()
            
            # Clean up enhanced recommender resources
            if hasattr(self, 'enhanced_recommender_manager'):
                for name, recommender in self.enhanced_recommender_manager.recommenders.items():
                    if hasattr(recommender, 'close'):
                        try:
                            await recommender.close()
                        except Exception as e:
                            logger.error(f"Error closing recommender {name}: {e}")
                
            logger.info("Closed Enhanced AI Stylist resources")
        except Exception as e:
            logger.error(f"Error closing resources: {e}")