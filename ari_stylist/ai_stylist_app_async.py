"""
Enhanced Asynchronous AI Stylist Application

Main application entry point for the AI Stylist system with persistent memory support.
Implements user identification and cross-session memory.
Compatible with CAMEL-AI 0.2.43.
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

# Import AsyncCAMELService
from async_camel_service import AsyncCAMELService

# Import the enhanced memory integration
from memory_integration_async import (
    setup_stylist_memory_async,
    save_memory_for_user_async,
    optimize_memory_async,
    extract_preferences_from_memory_async
)

# Import the enhanced stylist agent
from stylist_agent_async import create_stylist_agent_async

# Import the enhanced Neo4j integration
from neo4j_integration_async import ProductKnowledgeGraphAsync

# Import the enhanced chat manager
from chat_session_manager_async import EnhancedChatManagerAsync

# Import the enhanced recommender manager
from enhanced_recommender_manager_async import EnhancedRecommenderManagerAsync

# Import the product retriever
try:
    # Import the async product retriever
    from product_retriever_async import ProductRetrieverAsync
    logger.info("Using ProductRetrieverAsync (CAMEL-AI 0.2.43 compatible)")
except ImportError:
    logger.warning("Failed to import ProductRetrieverAsync module")
    # Define a fallback minimal ProductRetrieverAsync if needed
    class ProductRetrieverAsync:
        def __init__(self, **kwargs):
            self.initialized = False
            logger.warning("Using minimal ProductRetrieverAsync placeholder")
            
        async def setup_product_indexing(self, *args, **kwargs):
            logger.warning("Product indexing not available")
            
        async def search_products(self, *args, **kwargs):
            return []

class EnhancedAIStylistApp:
    """
    Enhanced AI Stylist application with persistent memory and user identification.
    Implements cross-session memory and improved personalization.
    Compatible with CAMEL-AI 0.2.43.
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        """
        Initialize the Enhanced AI Stylist application.
        
        Args:
            neo4j_url: Neo4j connection URL
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
        """
        logger.info("Initializing Enhanced AI Stylist...")
        
        # Use provided credentials or environment variables with defaults
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "shopari1234")
        
        # Read Qdrant configuration from environment
        self.qdrant_url = os.environ.get("QDRANT_URL")
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY")
        self.qdrant_collection_name = os.environ.get("QDRANT_COLLECTION_NAME", "products")
        
        # Set up Neo4j integration with enhanced features
        logger.info(f"Connecting to Neo4j at {self.neo4j_url}")
        self.product_kg = ProductKnowledgeGraphAsync(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password
        )
        
        # Set up product retriever with vector-based search
        logger.info("Initializing product retriever...")
        
        # Use remote Qdrant if configurations are available
        if self.qdrant_url and self.qdrant_api_key:
            logger.info(f"Using remote Qdrant at {self.qdrant_url}")
            # Initialize retriever with CAMEL-AI 0.2.43 compatible parameters
            self.product_retriever = ProductRetrieverAsync(
                vector_storage_path="product_data/embeddings",
                qdrant_url=self.qdrant_url,
                qdrant_api_key=self.qdrant_api_key,
                qdrant_collection_name=self.qdrant_collection_name
            )
        else:
            logger.info("Using local vector storage (remote Qdrant configuration not provided)")
            # Initialize local retriever with CAMEL-AI 0.2.43 compatible parameters
            self.product_retriever = ProductRetrieverAsync(
                vector_storage_path="product_data/embeddings"
            )
        
        # Initialize the CAMEL service
        self.camel_service = AsyncCAMELService()
        
        # Initialize the enhanced memory system
        logger.info("Setting up enhanced memory system...")
        self.memory_setup_func = setup_stylist_memory_async
        
        # Initialize enhanced chat manager with components
        logger.info("Creating enhanced chat manager...")
        self.chat_manager = EnhancedChatManagerAsync(
            stylist_agent=None,  # Will be set per session
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func
        )
        
        # Track active sessions
        self.active_sessions = {}
        
        # User registry for cross-session support
        self.registered_users = {}
        
        # Initialize the enhanced recommender manager
        logger.info("Initializing enhanced recommender manager...")
        self.enhanced_recommender_manager = EnhancedRecommenderManagerAsync(
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func,
            stylist_agent=None  # Will be set per session
        )
        
        # Memory optimization settings
        self.memory_optimization_interval = 3600  # 1 hour
        self.memory_optimization_task = None
        
        # Start the memory optimization task
        self.memory_optimization_task = asyncio.create_task(self._memory_optimization_worker())
        
        # Verify and update database schema
        asyncio.create_task(self._setup_database_schema())
        
        logger.info("Enhanced AI Stylist initialized and ready for conversations!")
    
    async def _setup_database_schema(self):
        """Set up and verify the database schema"""
        try:
            # Ensure the Neo4j schema is set up for enhanced features
            if hasattr(self.product_kg, 'ensure_schema'):
                await self.product_kg.ensure_schema()
            
            # Verify schema completeness
            schema_valid, missing_elements = await self.product_kg.verify_database_schema()
            if not schema_valid:
                logger.warning(f"Database schema incomplete. Missing: {missing_elements}")
                logger.warning("Some functionality may be limited due to missing schema elements")
            else:
                logger.info("Database schema verification successful")
                
            # Get basic database statistics
            stats = await self.product_kg.get_database_statistics()
            if stats:
                if 'product_count' in stats:
                    logger.info(f"Database contains {stats['product_count']} products")
                if 'user_count' in stats.get('user_statistics', {}):
                    logger.info(f"Database contains {stats['user_statistics']['user_count']} users")
                
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
                        await optimize_memory_async(
                            memory=session.memory,
                            user_id=session.user_id,
                            neo4j_client=self.product_kg
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
        """
        Create a new chat session with persistent memory support.
        
        Args:
            user_id: Optional user ID for personalization
            
        Returns:
            session_id: The ID of the created session
        """
        # Check if user already has an active session
        if user_id and user_id in self.registered_users:
            existing_session_id = self.registered_users[user_id]
            if existing_session_id in self.active_sessions:
                logger.info(f"Returning existing session for user {user_id}: {existing_session_id}")
                return existing_session_id
        
        # Create stylist agent with memory for this session
        try:
            # Register user in Neo4j if provided
            if user_id and self.product_kg:
                try:
                    await self.product_kg.create_or_update_user(user_id)
                    logger.info(f"Registered user in Neo4j: {user_id}")
                except Exception as e:
                    logger.error(f"Error registering user in Neo4j: {e}")
            
            # Create a new session with the chat manager
            session = await self.chat_manager.get_or_create_session(user_id=user_id)
            
            # Update stylist agent if needed
            if not hasattr(session, 'stylist_agent') or not session.stylist_agent:
                # Create a new agent using the CAMEL service
                memory = await self.camel_service.setup_memory(
                    memory_setup_func=self.memory_setup_func,
                    user_id=user_id,
                    neo4j_client=self.product_kg
                )
                
                session.memory = memory
                
                # Create a new agent
                stylist_agent = await create_stylist_agent_async(
                    memory=memory
                )
                session.stylist_agent = stylist_agent
                logger.info("Created stylist agent for new session")
            
            # Add to active sessions
            self.active_sessions[session.session_id] = session
            
            # Register user with this session
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
            # Create a minimal session as fallback
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
                    # Create a new agent if needed using AsyncCAMELService
                    memory = await self.camel_service.setup_memory(
                        memory_setup_func=self.memory_setup_func,
                        user_id=session.user_id if hasattr(session, 'user_id') else None,
                        neo4j_client=self.product_kg
                    )
                    
                    stylist_agent = await create_stylist_agent_async(memory)
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
            logger.info(f"Processing message for session {session_id}")
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
                    await save_memory_for_user_async(
                        memory=session.memory,
                        user_id=session.user_id,
                        neo4j_client=self.product_kg
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
        """
        Get a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            ChatSession object or None if not found
        """
        if not session_id:
            return None
            
        # Check active sessions first
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
            
        # Try to get from chat manager
        try:
            return await self.chat_manager.get_or_create_session(session_id=session_id)
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None
    
    async def get_product_recommendations(self, session_id, product_id=None, query=None, limit=5, occasion=None):
        """
        Enhanced recommendation system with direct product search prioritized
        
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
            
        try:
            # Get user ID from session
            user_id = session.user_id if hasattr(session, 'user_id') else None
            
            # Add occasion from query if provided
            if query and not occasion:
                # Extract occasion from query
                occasions = ["wedding", "party", "work", "casual", "formal", "date", "dinner", "beach"]
                seasons = ["summer", "winter", "fall", "spring"]
                
                query_lower = query.lower()
                
                # Check for occasions
                for occ in occasions:
                    if occ in query_lower:
                        occasion = occ
                        break
                        
                # Check for seasons + occasions
                if not occasion:
                    for season in seasons:
                        if season in query_lower:
                            for occ in occasions:
                                if occ in query_lower:
                                    occasion = f"{season} {occ}"
                                    break
            
            # DIRECT PRODUCT SEARCH FIRST - similar to original implementation
            search_results = []
            
            # If product_id is provided, use it for similar product search
            if product_id:
                # Get recommendations based on a specific product
                if hasattr(self.product_kg, 'get_similar_products'):
                    similar_products = await self.product_kg.get_similar_products(product_id, limit=limit)
                    
                    if similar_products:
                        # Record product view interaction if session supports it
                        if hasattr(session, 'record_product_interaction'):
                            await session.record_product_interaction(
                                product_id=product_id,
                                interaction_type="viewed"
                            )
                        
                        return similar_products
                        
                elif hasattr(self.product_retriever, 'search_similar_products'):
                    # Fall back to retriever if available
                    similar_products = await self.product_retriever.search_similar_products(product_id, limit=limit)
                    
                    if similar_products:
                        return similar_products
            
            # If query or occasion, use direct filter search
            if query or occasion:
                # Extract potential tag from query or use occasion
                search_tag = None
                if occasion:
                    search_tag = occasion
                elif query:
                    # Simple extraction of potential tags from query
                    tag_candidates = query.lower().split()
                    for tag in tag_candidates:
                        if len(tag) > 3 and tag not in ["need", "want", "looking", "for", "some", "with"]:
                            search_tag = tag
                            break
                
                # Extract potential category from query
                category = None
                category_list = ["dress", "shirt", "pants", "jeans", "skirt", "blouse", 
                            "sweater", "jacket", "coat", "suit", "blazer", "t-shirt", 
                            "hoodie", "shorts", "swimwear", "activewear", "shoes"]
                
                query_lower = query.lower() if query else ""
                for cat in category_list:
                    if cat in query_lower:
                        category = cat
                        break
                
                # Direct search with product_kg
                if hasattr(self.product_kg, 'get_product_by_filter'):
                    filter_products = await self.product_kg.get_product_by_filter(
                        category=category,
                        tag=search_tag,
                        limit=limit
                    )
                    
                    if filter_products:
                        # Record interactions if session supports it
                        if hasattr(session, 'record_product_interaction'):
                            for product in filter_products:
                                if 'id' in product:
                                    await session.record_product_interaction(
                                        product_id=product['id'],
                                        interaction_type="recommended"
                                    )
                        
                        return filter_products
            
            # Fallback to vector search if available
            if query and hasattr(self.product_retriever, 'search_by_natural_language'):
                vector_products = await self.product_retriever.search_by_natural_language(
                    query=query,
                    limit=limit
                )
                
                if vector_products:
                    return vector_products
            
            # Use enhanced recommendations as a fallback
            if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                recommendations = await self.enhanced_recommender_manager.get_recommendations(
                    user_id=user_id,
                    session_id=session_id,
                    product_id=product_id,
                    query=query or occasion,
                    limit=limit
                )
                
                if recommendations:
                    # If insufficient results, add fallback to occasion-specific search
                    if len(recommendations) < 3 and occasion:
                        fallback_products = await self.product_kg.get_product_by_filter(
                            tag=occasion,
                            limit=limit - len(recommendations)
                        )
                        
                        # Add products not already in recommendations
                        existing_ids = {p.get('id') for p in recommendations}
                        for product in fallback_products:
                            if product.get('id') not in existing_ids:
                                recommendations.append(product)
                                existing_ids.add(product.get('id'))
                    
                    # Record recommendations
                    if hasattr(session, 'record_product_interaction'):
                        for product in recommendations:
                            if 'id' in product:
                                await session.record_product_interaction(
                                    product_id=product['id'],
                                    interaction_type="recommended"
                                )
                    
                    return recommendations
            
            # Final fallbacks if still no results
            
            # Find a category to recommend from user preferences
            user_preferences = {}
            if hasattr(session, 'get_or_fetch_user_preferences'):
                user_preferences = await session.get_or_fetch_user_preferences()
            
            if user_preferences and user_preferences.get("preferred_categories"):
                category = user_preferences["preferred_categories"][0]
                if hasattr(self.product_kg, 'get_products_by_category'):
                    category_products = await self.product_kg.get_products_by_category(category, limit=limit)
                    if category_products:
                        return category_products
            
            # Fall back to popular products
            if hasattr(self.product_kg, 'get_popular_products'):
                return await self.product_kg.get_popular_products(limit=limit)
            elif hasattr(self.product_kg, 'get_trending_products'):
                return await self.product_kg.get_trending_products(limit=limit)
            
            # Last resort: general search
            return await self.product_kg.get_product_by_filter(limit=limit)
                
        except Exception as e:
            logger.error(f"Error getting product recommendations: {e}")
            return []

    async def record_product_interaction(self, session_id, product_id, interaction_type="viewed"):
        """
        Record a product interaction for a user.
        
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
            
            # Use enhanced recommender manager
            if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                # Record interaction in recommender
                result = self.enhanced_recommender_manager.record_interaction(
                    user_id=user_id,
                    product_id=product_id,
                    interaction_type=interaction_type
                )
                
                # Also record in Neo4j directly for better persistence
                if hasattr(self.product_kg, 'create_or_update_user'):
                    try:
                        # Get product details
                        product = await self.product_kg.get_product_details(product_id)
                        
                        if product and hasattr(session, 'memory') and session.memory:
                            from memory_integration_async import add_product_interaction_to_memory_async
                            
                            # Add interaction to memory with Neo4j persistence
                            await add_product_interaction_to_memory_async(
                                memory=session.memory,
                                product=product,
                                interaction_type=interaction_type,
                                persist_to_neo4j=True,
                                user_id=user_id,
                                neo4j_client=self.product_kg
                            )
                    except Exception as e:
                        logger.error(f"Error recording interaction in Neo4j and memory: {e}")
                
                return result
            
            return True
        except Exception as e:
            logger.error(f"Error recording product interaction: {e}")
            return False
    
    async def add_user_preference(self, session_id, preference_type, preference_value):
        """
        Add a user preference.
        
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
            
            # Add to memory if available
            if hasattr(session, 'memory') and session.memory:
                from memory_integration_async import add_user_preference_to_memory_async
                
                # Add preference to memory with Neo4j persistence
                await add_user_preference_to_memory_async(
                    memory=session.memory,
                    preference_type=preference_type,
                    preference_value=preference_value,
                    persist_to_neo4j=True,
                    user_id=user_id,
                    neo4j_client=self.product_kg
                )
            
            # Use enhanced recommender manager
            if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                # Add preference to recommender
                return self.enhanced_recommender_manager.add_user_preference(
                    user_id=user_id,
                    preference_type=preference_type,
                    preference_value=preference_value
                )
            
            return True
        except Exception as e:
            logger.error(f"Error adding user preference: {e}")
            return False
    
    async def get_user_preferences(self, session_id):
        """
        Get user preferences for a session.
        
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
            
            # Get from Neo4j directly
            if hasattr(self.product_kg, 'get_user_preferences'):
                preferences = await self.product_kg.get_user_preferences(user_id)
                return preferences
            
            # Get from memory if available
            if hasattr(session, 'memory') and session.memory:
                preferences = await extract_preferences_from_memory_async(session.memory)
                return preferences
            
            return {}
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
                        await save_memory_for_user_async(session.memory, session.user_id, self.product_kg)
                    except Exception as e:
                        logger.error(f"Error in final memory persistence for session {session_id}: {e}")
            
            # Close session resources
            for session_id, session in self.active_sessions.items():
                if hasattr(session, 'close'):
                    try:
                        await session.close()
                    except Exception as e:
                        logger.error(f"Error closing session {session_id}: {e}")
            
            # Close Neo4j connection
            if hasattr(self.product_kg, 'close'):
                await self.product_kg.close()
            
            # Close CAMEL service
            await self.camel_service.close()
            
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
