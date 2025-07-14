"""
Enhanced Asynchronous AI Stylist Application

Main application entry point for the AI Stylist system with persistent memory support.
Implements user identification and cross-session memory.
Compatible with CAMEL-AI 0.2.59+.

MIGRATED: Now uses AgentFactory instead of AsyncCAMELService for CAMEL 0.2.59+ compatibility.
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
    logger.info("Using ProductRetrieverAsync (CAMEL-AI 0.2.59+ compatible)")
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
    Compatible with CAMEL-AI 0.2.59+.
    
    MIGRATED: Now properly integrates with CAMEL 0.2.59+ using AgentFactory.
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        # Add at the beginning of __init__ method

        """Initialize with CAMEL-AI 0.2.64 verification"""
        logger.info("Initializing Enhanced AI Stylist with CAMEL-AI 0.2.64...")
        
        # VERIFY CAMEL VERSION
        try:
            from camel import __version__ as camel_version
            if not camel_version.startswith('0.2.64'):
                logger.warning(f"CAMEL version {camel_version} may not be fully compatible")
            else:
                logger.info(f"✅ CAMEL-AI version {camel_version} verified")
        except:
            logger.warning("Could not verify CAMEL-AI version")
    
  
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
            # Initialize retriever with CAMEL-AI 0.2.59+ compatible parameters
            self.product_retriever = ProductRetrieverAsync(
                vector_storage_path="product_data/embeddings",
                qdrant_url=self.qdrant_url,
                qdrant_api_key=self.qdrant_api_key,
                qdrant_collection_name=self.qdrant_collection_name
            )
        else:
            logger.info("Using local vector storage (remote Qdrant configuration not provided)")
            # Initialize local retriever with CAMEL-AI 0.2.59+ compatible parameters
            self.product_retriever = ProductRetrieverAsync(
                vector_storage_path="product_data/embeddings"
            )
        
        # MIGRATED: Use AgentFactory instead of AsyncCAMELService
        self.agent_factory = get_agent_factory()
        logger.info("Initialized AgentFactory for CAMEL 0.2.59+")
        
        # MIGRATED: Initialize MemoryManager for new memory APIs
        self.memory_manager = MemoryManager(self.product_kg)
        logger.info("Initialized MemoryManager for CAMEL 0.2.59+")
        
        # Initialize the enhanced memory system with backward compatibility wrapper
        logger.info("Setting up enhanced memory system...")
        self.memory_setup_func = self._setup_memory_for_user
        
        # Initialize the enhanced recommender manager
        logger.info("Initializing enhanced recommender manager...")
        self.enhanced_recommender_manager = EnhancedRecommenderManagerAsync(
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func,
            stylist_agent=None  # Will be set per session
        )
        
        # Pass parent app reference to chat manager for ML integration
        logger.info("Creating enhanced chat manager with ML integration...")
        self.chat_manager = EnhancedChatManagerAsync(
            stylist_agent=None,  # Will be set per session
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=self.memory_setup_func,
            parent_app=self  # Pass self reference for ML access
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
        
        logger.info("✅ Enhanced AI Stylist initialized with CAMEL 0.2.59+ support!")
    
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
                        # MIGRATED: Use optimize_memory_async from memory_integration_v2
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
        """FIXED: Create a new chat session with proper error handling."""
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
            
            return session.session_id
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            # Create minimal fallback
            session_id = str(uuid.uuid4())
            return session_id
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
                # MIGRATED: Create memory using MemoryManager
                memory = await self.memory_manager.create_memory(
                    user_id=user_id,
                    enable_mcp=True
                )
                
                session.memory = memory
                
                # MIGRATED: Create agent using AgentFactory
                stylist_agent = await self.agent_factory.create_stylist_agent(
                    memory=memory,
                    model_type=None,  # Will use default GPT-4O
                    enable_mcp=True
                )
                session.stylist_agent = stylist_agent
                logger.info("Created stylist agent for new session using AgentFactory")
            
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
            logger.info(f"🚀 Processing message for session {session_id} with FULL ML integration")
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
        """FIXED: Get a session by ID with proper error handling."""
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
        Enhanced recommendation system with proper fallback chain
        
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
        
        # Define all recommendation methods in priority order
        recommendation_methods = []
        
        # Method 1: Similar products (if product_id provided)
        if product_id:
            recommendation_methods.extend([
                ("similar_products_kg", self._try_similar_products_kg, product_id, limit),
                ("similar_products_retriever", self._try_similar_products_retriever, product_id, limit),
            ])
        
        # Method 2: Direct filter-based search (if query/occasion provided)
        if query or occasion:
            recommendation_methods.extend([
                ("direct_filter_search", self._try_direct_filter_search, query, occasion, limit),
                ("vector_search", self._try_vector_search, query, limit),
            ])
        
        # Method 3: Enhanced recommender system
        if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
            recommendation_methods.append(
                ("enhanced_recommender", self._try_enhanced_recommender, user_id, session_id, product_id, query or occasion, limit)
            )
        
        # Method 4: User preference-based fallbacks
        recommendation_methods.extend([
            ("user_preference_categories", self._try_user_preference_categories, session, limit),
            ("user_preference_tags", self._try_user_preference_tags, session, limit),
        ])
        
        # Method 5: General fallback methods
        recommendation_methods.extend([
            ("popular_products", self._try_popular_products, limit),
            ("trending_products", self._try_trending_products, limit),
            ("category_fallback", self._try_category_fallback, query, limit),
            ("general_search", self._try_general_search, limit),
        ])
        
        # Try each method until we get sufficient results
        for method_name, method_func, *args in recommendation_methods:
            try:
                logger.info(f"Trying recommendation method: {method_name}")
                results = await method_func(*args)
                
                if results and len(results) > 0:
                    # Filter out test/untitled products and zero-priced items
                    filtered_results = self._filter_valid_products(results)
                    
                    if filtered_results:
                        logger.info(f"✅ Got {len(filtered_results)} valid recommendations from {method_name}")
                        
                        # Record interactions if applicable
                        await self._record_product_interactions(session, filtered_results)
                        
                        return filtered_results[:limit]
                        
            except Exception as e:
                logger.warning(f"Method {method_name} failed: {e}")
                continue  # Try next method
        
        # If we get here, all methods failed
        logger.warning("All recommendation methods failed - returning empty list")
        return []

    # Helper methods for each recommendation strategy

    async def _try_similar_products_kg(self, product_id, limit):
        """Try getting similar products from knowledge graph"""
        if hasattr(self.product_kg, 'get_similar_products'):
            return await self.product_kg.get_similar_products(product_id, limit=limit)
        return []

    async def _try_similar_products_retriever(self, product_id, limit):
        """Try getting similar products from retriever"""
        if hasattr(self.product_retriever, 'search_similar_products'):
            return await self.product_retriever.search_similar_products(product_id, limit=limit)
        return []

    async def _try_direct_filter_search(self, query, occasion, limit):
        """Try direct filter search with product_kg"""
        if not hasattr(self.product_kg, 'get_product_by_filter'):
            return []
            
        # Extract potential parameters from query
        category = None
        tag = occasion
        
        if query:
            # Extract potential category from query
            category_list = ["dress", "shirt", "pants", "jeans", "skirt", "blouse", 
                            "sweater", "jacket", "coat", "suit", "blazer", "t-shirt", 
                            "hoodie", "shorts", "swimwear", "activewear", "shoes"]
            
            query_lower = query.lower()
            for cat in category_list:
                if cat in query_lower:
                    category = cat
                    break
            
            # Extract potential tag from query if no occasion
            if not tag:
                tag_candidates = query.lower().split()
                for potential_tag in tag_candidates:
                    if len(potential_tag) > 3 and potential_tag not in ["need", "want", "looking", "for", "some", "with"]:
                        tag = potential_tag
                        break
        
        # Try the search
        return await self.product_kg.get_product_by_filter(
            category=category,
            tag=tag,
            limit=limit
        )

    async def _try_vector_search(self, query, limit):
        """Try vector search with product retriever"""
        if query and hasattr(self.product_retriever, 'search_by_natural_language'):
            return await self.product_retriever.search_by_natural_language(
                query=query,
                limit=limit
            )
        return []

    async def _try_enhanced_recommender(self, user_id, session_id, product_id, query, limit):
        """Try enhanced recommender manager"""
        try:
            return await self.enhanced_recommender_manager.get_recommendations(
                user_id=user_id,
                session_id=session_id,
                product_id=product_id,
                query=query,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Enhanced recommender failed: {e}")
            return []

    async def _try_user_preference_categories(self, session, limit):
        """Try recommendations based on user's preferred categories"""
        try:
            if hasattr(session, 'get_or_fetch_user_preferences'):
                user_preferences = await session.get_or_fetch_user_preferences()
                
                if user_preferences and user_preferences.get("preferred_categories"):
                    category = user_preferences["preferred_categories"][0]
                    if hasattr(self.product_kg, 'get_products_by_category'):
                        return await self.product_kg.get_products_by_category(category, limit=limit)
        except Exception as e:
            logger.error(f"User preference categories fallback failed: {e}")
        return []

    async def _try_user_preference_tags(self, session, limit):
        """Try recommendations based on user's preferred tags"""
        try:
            if hasattr(session, 'get_or_fetch_user_preferences'):
                user_preferences = await session.get_or_fetch_user_preferences()
                
                if user_preferences and user_preferences.get("preferred_tags"):
                    tag = user_preferences["preferred_tags"][0]
                    if hasattr(self.product_kg, 'get_products_by_tag'):
                        return await self.product_kg.get_products_by_tag(tag, limit=limit)
        except Exception as e:
            logger.error(f"User preference tags fallback failed: {e}")
        return []

    async def _try_popular_products(self, limit):
        """Try getting popular products"""
        try:
            if hasattr(self.product_kg, 'get_popular_products'):
                return await self.product_kg.get_popular_products(limit=limit)
        except Exception as e:
            logger.error(f"Popular products fallback failed: {e}")
        return []

    async def _try_trending_products(self, limit):
        """Try getting trending products"""
        try:
            if hasattr(self.product_kg, 'get_trending_products'):
                return await self.product_kg.get_trending_products(limit=limit)
        except Exception as e:
            logger.error(f"Trending products fallback failed: {e}")
        return []

    async def _try_category_fallback(self, query, limit):
        """Try fallback based on common categories"""
        try:
            # Default categories to try if no other method works
            default_categories = ["dress", "shirt", "pants", "accessories"]
            
            # If query contains a category, try that first
            if query:
                query_lower = query.lower()
                for category in default_categories:
                    if category in query_lower:
                        if hasattr(self.product_kg, 'get_products_by_category'):
                            results = await self.product_kg.get_products_by_category(category, limit=limit)
                            if results:
                                return results
            
            # Try the first default category
            if hasattr(self.product_kg, 'get_products_by_category'):
                return await self.product_kg.get_products_by_category(default_categories[0], limit=limit)
        except Exception as e:
            logger.error(f"Category fallback failed: {e}")
        return []

    async def _try_general_search(self, limit):
        """Final fallback - get any valid products"""
        try:
            if hasattr(self.product_kg, 'get_product_by_filter'):
                return await self.product_kg.get_product_by_filter(limit=limit)
        except Exception as e:
            logger.error(f"General search fallback failed: {e}")
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
            # Don't let interaction recording failures break the recommendation flow

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
                            # MIGRATED: Use MemoryManager for product interactions
                            await self.memory_manager.add_product_interaction(
                                memory=session.memory,
                                product=product,
                                interaction_type=interaction_type,
                                user_id=user_id
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
                # MIGRATED: Use MemoryManager for preferences
                await self.memory_manager.add_preference(
                    memory=session.memory,
                    preference_type=preference_type,
                    preference_value=preference_value,
                    user_id=user_id
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
                # MIGRATED: Use extract_preferences_from_memory_async from v2
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
            
            # Close Neo4j connection
            if hasattr(self.product_kg, 'close'):
                await self.product_kg.close()
            
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