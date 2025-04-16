"""
Product Retriever module for AI Stylist
Focused on remote Qdrant integration for vector search
Compatible with CAMEL-AI 0.2.43
"""

import os
import logging
import json
import uuid
import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

# Updated imports for CAMEL-AI 0.2.43
from camel.embeddings import OpenAIEmbedding
from camel.types import EmbeddingModelType
from camel.toolkits import RetrievalToolkit

# For Qdrant integration
import qdrant_client
from qdrant_client.http import models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("product_retriever")

class ProductRetriever:
    """
    Product retriever using Qdrant for vector-based search.
    Optimized for remote Qdrant collections.
    Compatible with CAMEL-AI 0.2.43.
    """
    
    def __init__(
        self, 
        qdrant_url: Optional[str] = None, 
        qdrant_api_key: Optional[str] = None, 
        qdrant_collection_name: str = "products",
        vector_storage_path: str = None  # Kept for backward compatibility
    ):
        """
        Initialize the product retriever with Qdrant vector search.
        
        Args:
            qdrant_url: URL of Qdrant instance
            qdrant_api_key: API key for Qdrant authentication
            qdrant_collection_name: Name of the collection in Qdrant
            vector_storage_path: Ignored, kept for backward compatibility
        """
        self.qdrant_collection_name = qdrant_collection_name
        self.product_kg = None  # Will be set in setup_product_indexing
        
        # Get Qdrant config from environment if not provided
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL")
        self.qdrant_api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        
        if not self.qdrant_url:
            logger.error("No Qdrant URL provided")
            self.initialized = False
            return
            
        logger.info(f"Initializing ProductRetriever with Qdrant at: {self.qdrant_url}")
        
        try:
            # Initialize embedding model - consistent with CAMEL-AI 0.2.43
            self.embedding_model = OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_ADA_2
            )
            
            # Initialize Qdrant client
            self.qdrant_client = qdrant_client.QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
            logger.info(f"Connected to Qdrant instance: {self.qdrant_url}")
            
            # Check if collection exists, create if it doesn't
            self._ensure_collection_exists()
            
            # Set up retrieval toolkit for function calling
            self.retrieval_toolkit = RetrievalToolkit()
            self.retrieval_tools = self.retrieval_toolkit.get_tools()
            
            logger.info("ProductRetriever initialized successfully")
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing ProductRetriever: {e}")
            # Create empty placeholders for graceful degradation
            self.embedding_model = None
            self.qdrant_client = None
            self.retrieval_toolkit = None
            self.retrieval_tools = []
            self.initialized = False
    
    def _ensure_collection_exists(self) -> bool:
        """
        Ensure that the Qdrant collection exists, creating it if necessary.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.qdrant_client:
            return False
            
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_exists = any(c.name == self.qdrant_collection_name for c in collections.collections)
            
            if not collection_exists:
                logger.info(f"Creating collection '{self.qdrant_collection_name}'...")
                # Create the collection
                self.qdrant_client.create_collection(
                    collection_name=self.qdrant_collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,  # OpenAI embedding size
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"Collection '{self.qdrant_collection_name}' created successfully")
            
            return True
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            return False
    
    def setup_product_indexing(self, product_kg) -> bool:
        """
        Set up product indexing for vector search.
        
        Args:
            product_kg: ProductKnowledgeGraph instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not product_kg:
            logger.error("No product knowledge graph provided")
            return False
            
        self.product_kg = product_kg
        logger.info("Product indexing setup successful")
        return True
    
    def search_products(
        self, 
        query: str, 
        limit: int = 5, 
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for products based on a query using vector similarity.
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            List[Dict[str, Any]]: List of product dictionaries
        """
        logger.info(f"Searching products with query: '{query}'")
        
        if not query or len(query.strip()) == 0:
            logger.warning("Empty query provided")
            return []
        
        if not self.initialized or not self.qdrant_client:
            logger.error("ProductRetriever not properly initialized")
            return []
        
        try:
            # Generate embedding for the query
            query_embedding = self.embedding_model.embed(query)
            
            # Search the Qdrant collection
            search_results = self.qdrant_client.search(
                collection_name=self.qdrant_collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=similarity_threshold
            )
            
            logger.info(f"Found {len(search_results)} results from Qdrant")
            
            # Extract product IDs from search results
            product_ids = [hit.payload.get("product_id") for hit in search_results if hit.payload.get("product_id")]
            
            # If we have a product knowledge graph, fetch product details
            products = []
            if self.product_kg and product_ids:
                for product_id in product_ids:
                    try:
                        product = self.product_kg.get_product_details(product_id)
                        if product:
                            products.append(product)
                    except Exception as e:
                        logger.error(f"Error fetching product {product_id}: {e}")
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    def search_by_natural_language(
        self, 
        query: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search products using natural language query.
        
        Args:
            query: Natural language query
            limit: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: List of product dictionaries
        """
        logger.info(f"Searching by natural language: '{query}'")
        return self.search_products(query, limit, similarity_threshold=0.6)
    
    def search_similar_products(
        self, 
        product_id: str, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find products similar to a given product.
        
        Args:
            product_id: Reference product ID
            limit: Maximum number of similar products
            
        Returns:
            List[Dict[str, Any]]: List of similar products
        """
        logger.info(f"Finding products similar to {product_id}")
        
        if not self.product_kg:
            logger.error("No product knowledge graph available")
            return []
            
        try:
            # Get product details
            product = self.product_kg.get_product_details(product_id)
            
            if not product:
                logger.warning(f"Product not found: {product_id}")
                return []
                
            # Use the product title and description as search query
            query = f"{product.get('title', '')} {product.get('description', '')}"
            
            # Search for similar products
            similar_products = self.search_products(
                query=query,
                limit=limit + 1,  # Add 1 to account for the product itself
                similarity_threshold=0.6
            )
            
            # Remove the reference product from the results
            similar_products = [p for p in similar_products if p.get('id') != product_id]
            
            return similar_products[:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar products: {e}")
            return []
    
    def index_product(self, product: Dict[str, Any]) -> bool:
        """
        Index a product for vector search.
        
        Args:
            product: Product dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Indexing product: {product.get('id', 'unknown')}")
        
        if not product or 'id' not in product:
            logger.error("Invalid product data")
            return False
            
        product_id = product.get('id')
        
        try:
            # Generate a document for the product
            doc_text = f"{product.get('title', '')} {product.get('description', '')}"
            
            # Skip if document is too short
            if len(doc_text.strip()) < 10:
                logger.warning(f"Document too short for product {product_id}")
                return False
                
            # Generate embedding
            embedding = self.embedding_model.embed(doc_text)
            
            # Store in Qdrant
            if self.qdrant_client:
                self.qdrant_client.upsert(
                    collection_name=self.qdrant_collection_name,
                    points=[
                        models.PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload={
                                "product_id": product_id,
                                "text": doc_text,
                                "title": product.get('title', ''),
                                "timestamp": str(datetime.datetime.now())
                            }
                        )
                    ]
                )
                return True
            else:
                logger.error("Qdrant client not initialized")
                return False
                
        except Exception as e:
            logger.error(f"Error indexing product {product_id}: {e}")
            return False
    
    def get_tools(self) -> List:
        """
        Get the retrieval tools for function calling.
        
        Returns:
            List: List of retrieval tools
        """
        return self.retrieval_tools