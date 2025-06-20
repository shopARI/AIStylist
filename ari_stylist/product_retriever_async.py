"""
Asynchronous Product Retriever for AI Stylist.

This module implements an asynchronous product retriever using Qdrant vector search.
Compatible with CAMEL-AI 0.2.64.

FIXED: Uses centralized imports and proper error handling.
"""

import os
import logging
import json
import uuid
import datetime
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple

# FIXED: Use centralized imports with error handling
from camel_imports import (
    CAMEL_AVAILABLE,
    OpenAIEmbedding,
    EmbeddingModelType,
    RetrievalToolkit
)

# For Qdrant integration
try:
    import qdrant_client
    from qdrant_client.http import models
    from qdrant_client.http.exceptions import UnexpectedResponse
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logging.warning("Qdrant not installed. Install with: pip install qdrant-client")

# For async HTTP calls
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logging.warning("httpx not installed. Install with: pip install httpx")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("product_retriever_async")

class ProductRetrieverAsync:
    """
    Asynchronous product retriever using Qdrant for vector-based search.
    Optimized for remote Qdrant collections.
    Compatible with CAMEL-AI 0.2.64.
    
    FIXED: Uses proper error handling for all CAMEL components.
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
        
        FIXED: Added proper error handling for CAMEL components.
        
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
            
        logger.info(f"Initializing ProductRetrieverAsync with Qdrant at: {self.qdrant_url}")
        
        # Check CAMEL availability
        if not CAMEL_AVAILABLE:
            logger.warning("CAMEL-AI not fully available, using fallback implementations")
        
        try:
            # FIXED: Initialize embedding model with error handling
            if CAMEL_AVAILABLE and OpenAIEmbedding and EmbeddingModelType:
                self.embedding_model = OpenAIEmbedding(
                    model_type=EmbeddingModelType.TEXT_EMBEDDING_ADA_2
                )
                logger.info("Embedding model initialized successfully")
            else:
                logger.error("CAMEL embedding components not available")
                self.embedding_model = None
                self.initialized = False
                return
            
            # Initialize Qdrant client (synchronous client for now)
            if QDRANT_AVAILABLE:
                try:
                    self.qdrant_client = qdrant_client.QdrantClient(
                        url=self.qdrant_url,
                        api_key=self.qdrant_api_key
                    )
                    logger.info(f"Connected to Qdrant instance: {self.qdrant_url}")
                    
                    # Check if collection exists, create if it doesn't
                    self._ensure_collection_exists_sync()
                except Exception as e:
                    logger.error(f"Error connecting to Qdrant: {e}")
                    self.qdrant_client = None
                
                # HTTP client for async operations with Qdrant REST API
                if HTTPX_AVAILABLE:
                    try:
                        self.http_client = httpx.AsyncClient(
                            base_url=self.qdrant_url,
                            headers={"api-key": self.qdrant_api_key} if self.qdrant_api_key else None,
                            timeout=60.0
                        )
                    except Exception as e:
                        logger.error(f"Error creating HTTP client: {e}")
                        self.http_client = None
                else:
                    logger.warning("httpx not available for async operations")
                    self.http_client = None
            else:
                self.qdrant_client = None
                self.http_client = None
                logger.warning("Qdrant client not available")
            
            # FIXED: Set up retrieval toolkit with error handling
            if CAMEL_AVAILABLE and RetrievalToolkit:
                try:
                    self.retrieval_toolkit = RetrievalToolkit()
                    self.retrieval_tools = self.retrieval_toolkit.get_tools()
                    logger.info("Retrieval toolkit initialized successfully")
                except Exception as e:
                    logger.warning(f"Error initializing retrieval toolkit: {e}")
                    self.retrieval_toolkit = None
                    self.retrieval_tools = []
            else:
                logger.warning("CAMEL RetrievalToolkit not available")
                self.retrieval_toolkit = None
                self.retrieval_tools = []
            
            logger.info("ProductRetrieverAsync initialized successfully")
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing ProductRetrieverAsync: {e}")
            # Create empty placeholders for graceful degradation
            self.embedding_model = None
            self.qdrant_client = None
            self.http_client = None
            self.retrieval_toolkit = None
            self.retrieval_tools = []
            self.initialized = False
    
    def _ensure_collection_exists_sync(self) -> bool:
        """
        Ensure that the Qdrant collection exists, creating it if necessary.
        This is a synchronous method used during initialization.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.qdrant_client or not QDRANT_AVAILABLE:
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
    
    async def ensure_collection_exists(self) -> bool:
        """
        Asynchronous version to ensure that the Qdrant collection exists.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.http_client or not HTTPX_AVAILABLE:
            return self._ensure_collection_exists_sync()
            
        try:
            # Check if collection exists using REST API
            response = await self.http_client.get("/collections")
            if response.status_code != 200:
                logger.error(f"Failed to get collections: {response.text}")
                return False
                
            collections = response.json()
            collection_names = [c["name"] for c in collections["collections"]]
            collection_exists = self.qdrant_collection_name in collection_names
            
            if not collection_exists:
                logger.info(f"Creating collection '{self.qdrant_collection_name}'...")
                # Create the collection using REST API
                create_payload = {
                    "vectors": {
                        "size": 1536,
                        "distance": "Cosine"
                    }
                }
                response = await self.http_client.put(
                    f"/collections/{self.qdrant_collection_name}",
                    json=create_payload
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to create collection: {response.text}")
                    return False
                    
                logger.info(f"Collection '{self.qdrant_collection_name}' created successfully")
            
            return True
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            return False
    
    async def setup_product_indexing(self, product_kg) -> bool:
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
        
        # Ensure collection exists
        await self.ensure_collection_exists()
        
        logger.info("Product indexing setup successful")
        return True
    
    async def search_products(
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
        
        if not self.initialized:
            logger.error("ProductRetrieverAsync not properly initialized")
            return []
        
        if not self.embedding_model:
            logger.error("Embedding model not available")
            return []
        
        try:
            # Generate embedding for the query
            query_embedding = self.embedding_model.embed(query)
            
            # Search the Qdrant collection
            search_results = []
            
            if self.http_client and HTTPX_AVAILABLE:
                # Use async REST API
                search_payload = {
                    "vector": query_embedding,
                    "limit": limit,
                    "with_payload": True,
                    "score_threshold": similarity_threshold
                }
                
                try:
                    response = await self.http_client.post(
                        f"/collections/{self.qdrant_collection_name}/points/search",
                        json=search_payload
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Search failed: {response.text}")
                        return []
                    
                    search_results = response.json()["result"]
                except Exception as e:
                    logger.error(f"Error in async search: {e}")
                    search_results = []
            elif self.qdrant_client and QDRANT_AVAILABLE:
                # Fall back to synchronous client if async fails
                try:
                    sync_results = self.qdrant_client.search(
                        collection_name=self.qdrant_collection_name,
                        query_vector=query_embedding,
                        limit=limit,
                        score_threshold=similarity_threshold
                    )
                    
                    search_results = [
                        {"id": hit.id, "score": hit.score, "payload": hit.payload}
                        for hit in sync_results
                    ]
                except Exception as e:
                    logger.error(f"Error in sync search: {e}")
                    search_results = []
            else:
                logger.warning("No Qdrant client available for search")
                return []
            
            logger.info(f"Found {len(search_results)} results from Qdrant")
            
            # Extract product IDs from search results
            product_ids = [
                hit["payload"].get("product_id") 
                for hit in search_results 
                if "payload" in hit and "product_id" in hit["payload"]
            ]
            
            # If we have a product knowledge graph, fetch product details
            products = []
            if self.product_kg and product_ids:
                for product_id in product_ids:
                    try:
                        if hasattr(self.product_kg, 'get_product_details'):
                            product = await self.product_kg.get_product_details(product_id)
                            if product:
                                products.append(product)
                        else:
                            logger.warning("Product KG does not support get_product_details")
                    except Exception as e:
                        logger.error(f"Error fetching product {product_id}: {e}")
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    async def search_by_natural_language(
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
        return await self.search_products(query, limit, similarity_threshold=0.6)
    
    async def search_similar_products(
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
            if hasattr(self.product_kg, 'get_product_details'):
                product = await self.product_kg.get_product_details(product_id)
            else:
                logger.error("Product KG does not support get_product_details")
                return []
            
            if not product:
                logger.warning(f"Product not found: {product_id}")
                return []
                
            # Use the product title and description as search query
            query = f"{product.get('title', '')} {product.get('description', '')}"
            
            # Search for similar products
            similar_products = await self.search_products(
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
    
    async def index_product(self, product: Dict[str, Any]) -> bool:
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
            
        if not self.embedding_model:
            logger.error("Embedding model not available")
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
            if self.http_client and HTTPX_AVAILABLE:
                # Use async REST API
                point_id = str(uuid.uuid4())
                point_payload = {
                    "points": [
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": {
                                "product_id": product_id,
                                "text": doc_text,
                                "title": product.get('title', ''),
                                "timestamp": str(datetime.datetime.now())
                            }
                        }
                    ]
                }
                
                try:
                    response = await self.http_client.put(
                        f"/collections/{self.qdrant_collection_name}/points",
                        json=point_payload
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Failed to index product: {response.text}")
                        return False
                        
                    return True
                except Exception as e:
                    logger.error(f"Error in async indexing: {e}")
                    return False
            elif self.qdrant_client and QDRANT_AVAILABLE:
                # Fall back to synchronous client
                try:
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
                except Exception as e:
                    logger.error(f"Error in sync indexing: {e}")
                    return False
            else:
                logger.error("No Qdrant client available for indexing")
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
        return self.retrieval_tools if self.retrieval_tools else []
    
    async def close(self):
        """Close all resources"""
        if self.http_client and HTTPX_AVAILABLE:
            try:
                await self.http_client.aclose()
            except Exception as e:
                logger.error(f"Error closing HTTP client: {e}")
