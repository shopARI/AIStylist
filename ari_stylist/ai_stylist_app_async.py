"""
Asynchronous AI Stylist Application

Main application entry point for the AI Stylist system with async support.
Initializes all components and provides an async interface to interact with the stylist.
Compatible with CAMEL-AI 0.2.43.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple, List
import httpx

# Configure logging first, before any other imports
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_stylist_app_async")

from memory_integration_async import setup_stylist_memory_async
from stylist_agent_async import create_stylist_agent_async
from neo4j_integration_async import ProductKnowledgeGraphAsync
from chat_session_manager_async import ChatManagerAsync

# Import the enhanced recommendation systems
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

class AIStylistApp:
    """
    Main application entry point for the AI Stylist system with async support.
    Initializes all components and provides an async interface to interact with the stylist.
    Compatible with CAMEL-AI 0.2.43.
    """
    
    def __init__(self, neo4j_url=None, neo4j_username=None, neo4j_password=None):
        """
        Initialize the AI Stylist application.
        
        Args:
            neo4j_url: Neo4j connection URL
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
        """
        logger.info("Initializing Async AI Stylist...")
        
        # Use provided credentials or environment variables with defaults
        self.neo4j_url = neo4j_url or os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
        self.neo4j_username = neo4j_username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.neo4j_password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "shopari1234")
        
        # Read Qdrant configuration from environment
        self.qdrant_url = os.environ.get("QDRANT_URL")
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY")
        self.qdrant_collection_name = os.environ.get("QDRANT_COLLECTION_NAME", "products")
        
        # Set up Neo4j integration
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
        
        # Initialize chat manager with components
        logger.info("Creating chat manager...")
        self.chat_manager = ChatManagerAsync(
            stylist_agent=None,  # Will be set per session
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=setup_stylist_memory_async
        )
        
        # Track active sessions
        self.active_sessions = {}
        
        # Initialize the enhanced recommender manager
        logger.info("Initializing enhanced recommender manager...")
        self.enhanced_recommender_manager = EnhancedRecommenderManagerAsync(
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=setup_stylist_memory_async,
            stylist_agent=None  # Will be set per session
        )
        
        logger.info("Async AI Stylist initialized and ready for conversations!")
    
    async def _verify_database_schema(self):
        """Verify that the Neo4j database has the expected schema"""
        try:
            schema_valid, missing_elements = await self.product_kg.verify_database_schema()
            if not schema_valid:
                logger.warning(f"Database schema incomplete. Missing: {missing_elements}")
                logger.warning("Some functionality may be limited due to missing schema elements")
            else:
                logger.info("Database schema verification successful")
                
            # Get basic database statistics
            stats = await self.product_kg.get_database_statistics() if hasattr(self.product_kg, 'get_database_statistics') else {}
            if stats and 'product_count' in stats:
                logger.info(f"Database contains {stats['product_count']} products")
                
        except Exception as e:
            logger.error(f"Error verifying database schema: {e}")
            logger.warning("Continuing with limited database verification")
    
    async def create_session(self, user_id=None):
        """
        Create a new chat session.
        
        Args:
            user_id: Optional user ID for personalization
            
        Returns:
            session_id: The ID of the created session
        """
        # Create new memory for this session
        try:
            memory = await setup_stylist_memory_async()
            logger.info("Created session memory")
        except Exception as e:
            logger.error(f"Error creating memory: {e}")
            memory = None
        
        # Create stylist agent with this memory
        try:
            stylist_agent = await create_stylist_agent_async(memory)
            logger.info("Created stylist agent")
        except Exception as e:
            logger.error(f"Error creating stylist agent: {e}")
            stylist_agent = None
        
        # Create session with custom stylist agent
        session = await self.chat_manager.get_or_create_session(user_id=user_id)
        session.stylist_agent = stylist_agent
        session.memory = memory
        
        # Add to active sessions
        self.active_sessions[session.session_id] = session
        
        # Update the enhanced recommender manager with this session's stylist agent
        if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
            # Update the ensemble recommender with the session's stylist agent
            if hasattr(self.enhanced_recommender_manager, 'ensemble') and self.enhanced_recommender_manager.ensemble:
                self.enhanced_recommender_manager.ensemble.stylist_agent = stylist_agent
                logger.info("Updated ensemble recommender with session stylist agent")
        
        logger.info(f"Created new session: {session.session_id}")
        
        return session.session_id
    
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
                if not session.stylist_agent:
                    # Create a new agent if needed
                    memory = await setup_stylist_memory_async()
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
            except Exception as e:
                logger.error(f"Error recovering session {session_id}: {e}")
                return "I'm sorry, I couldn't find your previous conversation. Let's start a new one.", {
                    "error": f"Session not found: {session_id}"
                }
        
        # Process the message using the chat manager
        try:
            logger.info(f"Processing message for session {session_id}")
            response, data = await self.chat_manager.process_message(
                session_id=session_id,
                user_id=None,  # Session already has user ID if applicable
                message=message
            )
            
            # If products were recommended, record interactions
            if 'products' in data and session_id in self.active_sessions:
                user_id = self.active_sessions[session_id].user_id
                for product in data['products']:
                    if 'id' in product:
                        await self.record_product_interaction(
                            session_id=session_id,
                            product_id=product['id'],
                            interaction_type="recommended"
                        )
            
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
        Enhanced recommendation system with occasion-specific logic
        """
        session = await self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return []
            
        try:
            # Get user ID from session
            user_id = session.user_id
            
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
            
            # Use enhanced recommender manager
            if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                recommendations = self.enhanced_recommender_manager.get_recommendations(
                    user_id=user_id,
                    session_id=session_id,
                    product_id=product_id,
                    query=query or occasion,
                    limit=limit
                )
                
                # Record product view interactions if product_id was provided
                if product_id:
                    await self.record_product_interaction(
                        session_id=session_id,
                        product_id=product_id,
                        interaction_type="viewed"
                    )
                
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
                for product in recommendations:
                    if 'id' in product:
                        await self.record_product_interaction(
                            session_id=session_id,
                            product_id=product['id'],
                            interaction_type="recommended"
                        )
                
                return recommendations
            
            # Fallback to original implementation
            if product_id:
                # Get recommendations based on a specific product
                if hasattr(self.product_kg, 'get_similar_products'):
                    return await self.product_kg.get_similar_products(product_id, limit=limit)
                else:
                    # Fall back to retriever if available
                    return await self.product_retriever.search_similar_products(product_id, limit=limit)
            else:
                # Get recommendations based on user preferences
                user_preferences = await session.get_or_fetch_user_preferences()
                
                # Find a category to recommend
                if user_preferences and user_preferences.get("preferred_categories"):
                    category = user_preferences["preferred_categories"][0]
                    if hasattr(self.product_kg, 'get_products_by_category'):
                        return await self.product_kg.get_products_by_category(category, limit=limit)
                    
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
            # Get user ID from session
            user_id = session.user_id
            
            # Use enhanced recommender manager
            if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                # FIXED: Removed await from synchronous method
                return self.enhanced_recommender_manager.record_interaction(
                    user_id=user_id,
                    product_id=product_id,
                    interaction_type=interaction_type
                )
            
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
            # Get user ID from session
            user_id = session.user_id
            
            # Use enhanced recommender manager
            if hasattr(self, 'enhanced_recommender_manager') and self.enhanced_recommender_manager:
                # FIXED: Removed await from synchronous method
                return self.enhanced_recommender_manager.add_user_preference(
                    user_id=user_id,
                    preference_type=preference_type,
                    preference_value=preference_value
                )
            
            return True
        except Exception as e:
            logger.error(f"Error adding user preference: {e}")
            return False
    
    async def close(self):
        """Clean up resources and close connections"""
        try:
            if hasattr(self.product_kg, 'close'):
                await self.product_kg.close()
            
            # Clean up enhanced recommender resources
            if hasattr(self, 'enhanced_recommender_manager'):
                for name, recommender in self.enhanced_recommender_manager.recommenders.items():
                    if hasattr(recommender, 'close'):
                        try:
                            await recommender.close()
                        except Exception as e:
                            logger.error(f"Error closing recommender {name}: {e}")
                
            logger.info("Closed Async AI Stylist resources")
        except Exception as e:
            logger.error(f"Error closing resources: {e}")