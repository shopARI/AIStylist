"""
AI Stylist Application

Main application entry point for the AI Stylist system.
Initializes all components and provides a simple interface to interact with the stylist.
Updated for CAMEL-AI 0.2.43 compatibility.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple, List

# Configure logging first, before any other imports
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_stylist_app")

from memory_integration import setup_stylist_memory
from stylist_agent import create_stylist_agent
from neo4j_integration import ProductKnowledgeGraph
from chat_session_manager import ChatManager

# Import the ProductRetriever
try:
    # Import the product retriever
    from product_retriever import ProductRetriever
    logger.info("Using ProductRetriever (CAMEL-AI 0.2.43 compatible)")
except ImportError:
    logger.warning("Failed to import ProductRetriever module")
    # Define a fallback minimal ProductRetriever if needed
    class ProductRetriever:
        def __init__(self, **kwargs):
            self.initialized = False
            logger.warning("Using minimal ProductRetriever placeholder")
            
        def setup_product_indexing(self, *args, **kwargs):
            logger.warning("Product indexing not available")
            
        def search_products(self, *args, **kwargs):
            return []

class AIStylistApp:
    """
    Main application entry point for the AI Stylist system.
    Initializes all components and provides a simple interface to interact with the stylist.
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
        logger.info("Initializing AI Stylist...")
        
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
        self.product_kg = ProductKnowledgeGraph(
            url=self.neo4j_url,
            username=self.neo4j_username,
            password=self.neo4j_password
        )
        
        # Verify database schema
        self._verify_database_schema()
        
        # Set up product retriever with vector-based search
        logger.info("Initializing product retriever...")
        
        # Use remote Qdrant if configurations are available
        if self.qdrant_url and self.qdrant_api_key:
            logger.info(f"Using remote Qdrant at {self.qdrant_url}")
            # Initialize retriever with CAMEL-AI 0.2.43 compatible parameters
            self.product_retriever = ProductRetriever(
                vector_storage_path="product_data/embeddings",
                qdrant_url=self.qdrant_url,
                qdrant_api_key=self.qdrant_api_key,
                qdrant_collection_name=self.qdrant_collection_name
            )
        else:
            logger.info("Using local vector storage (remote Qdrant configuration not provided)")
            # Initialize local retriever with CAMEL-AI 0.2.43 compatible parameters
            self.product_retriever = ProductRetriever(
                vector_storage_path="product_data/embeddings"
            )
        
        # Configure product retriever with Neo4j connection
        logger.info("Setting up product indexing...")
        self.product_retriever.setup_product_indexing(self.product_kg)
        
        # Create chat manager with all components
        logger.info("Creating chat manager...")
        self.chat_manager = ChatManager(
            stylist_agent=None,  # Will be set per session
            product_kg=self.product_kg,
            product_retriever=self.product_retriever,
            memory_setup_func=setup_stylist_memory
        )
        
        # Track active sessions
        self.active_sessions = {}
        
        logger.info("AI Stylist initialized and ready for conversations!")
    
    def _verify_database_schema(self):
        """Verify that the Neo4j database has the expected schema"""
        try:
            schema_valid, missing_elements = self.product_kg.verify_database_schema()
            if not schema_valid:
                logger.warning(f"Database schema incomplete. Missing: {missing_elements}")
                logger.warning("Some functionality may be limited due to missing schema elements")
            else:
                logger.info("Database schema verification successful")
                
            # Get basic database statistics
            stats = self.product_kg.get_database_statistics() if hasattr(self.product_kg, 'get_database_statistics') else {}
            if stats and 'product_count' in stats:
                logger.info(f"Database contains {stats['product_count']} products")
                
        except Exception as e:
            logger.error(f"Error verifying database schema: {e}")
            logger.warning("Continuing with limited database verification")
    
    def create_session(self, user_id=None):
        """
        Create a new chat session.
        
        Args:
            user_id: Optional user ID for personalization
            
        Returns:
            session_id: The ID of the created session
        """
        # Create new memory for this session
        try:
            memory = setup_stylist_memory()
            logger.info("Created session memory")
        except Exception as e:
            logger.error(f"Error creating memory: {e}")
            memory = None
        
        # Create stylist agent with this memory
        try:
            stylist_agent = create_stylist_agent(memory)
            logger.info("Created stylist agent")
        except Exception as e:
            logger.error(f"Error creating stylist agent: {e}")
            stylist_agent = None
        
        # Create session with custom stylist agent
        session = self.chat_manager.get_or_create_session(user_id=user_id)
        session.stylist_agent = stylist_agent
        session.memory = memory
        
        # Add to active sessions
        self.active_sessions[session.session_id] = session
        
        logger.info(f"Created new session: {session.session_id}")
        
        return session.session_id
    
    def send_message(self, session_id, message):
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
                session = self.chat_manager.get_or_create_session(session_id=session_id)
                if not session.stylist_agent:
                    # Create a new agent if needed
                    memory = setup_stylist_memory()
                    stylist_agent = create_stylist_agent(memory)
                    session.stylist_agent = stylist_agent
                    session.memory = memory
                
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
            response, data = self.chat_manager.process_message(
                session_id=session_id,
                user_id=None,  # Session already has user ID if applicable
                message=message
            )
            
            return response, data
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I'm sorry, I encountered an issue while processing your request. Could you try rephrasing or asking something else?", {
                "error": str(e)
            }
    
    def get_session(self, session_id):
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
            return self.chat_manager.get_or_create_session(session_id=session_id)
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            return None
    
    def get_product_recommendations(self, session_id, product_id=None, limit=5):
        """
        Get product recommendations for a session, optionally based on a specific product.
        
        Args:
            session_id: Session ID
            product_id: Optional specific product ID to base recommendations on
            limit: Maximum number of recommendations to return
            
        Returns:
            List of recommended products
        """
        session = self.get_session(session_id)
        if not session:
            logger.error(f"Session not found: {session_id}")
            return []
            
        try:
            if product_id:
                # Get recommendations based on a specific product
                if hasattr(self.product_kg, 'get_similar_products'):
                    return self.product_kg.get_similar_products(product_id, limit=limit)
                else:
                    # Fall back to retriever if available
                    return self.product_retriever.search_similar_products(product_id, limit=limit)
            else:
                # Get recommendations based on user preferences
                user_preferences = session.get_or_fetch_user_preferences()
                
                # Find a category to recommend
                if user_preferences and user_preferences.get("preferred_categories"):
                    category = user_preferences["preferred_categories"][0]
                    if hasattr(self.product_kg, 'get_products_by_category'):
                        return self.product_kg.get_products_by_category(category, limit=limit)
                    
                # Fall back to popular products
                if hasattr(self.product_kg, 'get_popular_products'):
                    return self.product_kg.get_popular_products(limit=limit)
                elif hasattr(self.product_kg, 'get_trending_products'):
                    return self.product_kg.get_trending_products(limit=limit)
                    
                # Last resort: general search
                return self.product_kg.get_product_by_filter(limit=limit)
                
        except Exception as e:
            logger.error(f"Error getting product recommendations: {e}")
            return []
            
    def close(self):
        """Clean up resources and close connections"""
        try:
            if hasattr(self.product_kg, 'close'):
                self.product_kg.close()
                
            logger.info("Closed AI Stylist resources")
        except Exception as e:
            logger.error(f"Error closing resources: {e}")


# Example usage when module is run directly
if __name__ == "__main__":
    # Initialize the application
    app = AIStylistApp(
        neo4j_url=os.environ.get("NEO4J_URL"),
        neo4j_username=os.environ.get("NEO4J_USERNAME"),
        neo4j_password=os.environ.get("NEO4J_PASSWORD")
    )
    
    # Create a new session
    session_id = app.create_session(user_id="user123")
    
    # Example conversation
    responses = []
    
    # First message
    message = "I need something to wear to a summer wedding next month. I prefer blue colors and natural fabrics like linen or cotton. My budget is around $200."
    response, data = app.send_message(session_id, message)
    responses.append({"user": message, "stylist": response})
    
    # Follow-up question
    message = "Do you have any suggestions for accessories to go with that?"
    response, data = app.send_message(session_id, message)
    responses.append({"user": message, "stylist": response})
    
    # Print the conversation
    print("\n" + "="*50)
    print("EXAMPLE CONVERSATION")
    print("="*50)
    
    for exchange in responses:
        print(f"\nUser: {exchange['user']}")
        print(f"\nAri (Stylist): {exchange['stylist']}")
        print("\n" + "-"*50)
    
    print("\nSession active and ready for more interactions!")
    
    # Clean up resources when done
    app.close()