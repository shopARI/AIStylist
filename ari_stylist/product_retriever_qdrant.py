import os
import logging
import json
import uuid
from typing import Dict, List, Any, Optional
# Updated import to match newer CAMEL API (0.2.43)
from camel.retrievers import AutoRetriever
# Remove RetrieverConfig import as it's no longer used
from camel.types import StorageType, EmbeddingModelType
from camel.embeddings import OpenAIEmbedding
from camel.toolkits import RetrievalToolkit

# For direct Qdrant integration
import qdrant_client
from qdrant_client.http import models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("product_retriever")

class ProductRetriever:
    """
    Product retriever using CAMEL's AutoRetriever for local storage
    or direct Qdrant client for remote storage.
    Provides vector-based semantic search capabilities.
    """
    
    def __init__(self, vector_storage_path="product_data/embeddings", 
                 qdrant_url=None, qdrant_api_key=None, qdrant_collection_name="products"):
        """
        Initialize the product retriever with either local or remote Qdrant.
        
        Args:
            vector_storage_path: Path for local storage (used if qdrant_url is None)
            qdrant_url: URL of remote Qdrant instance (if provided, uses remote)
            qdrant_api_key: API key for remote Qdrant authentication
            qdrant_collection_name: Name of the collection in Qdrant
        """
        self.using_remote = bool(qdrant_url)
        self.qdrant_collection_name = qdrant_collection_name
        
        if not self.using_remote:
            logger.info(f"Initializing ProductRetriever with local storage path: {vector_storage_path}")
            # Ensure the vector storage directory exists for local mode
            os.makedirs(os.path.dirname(vector_storage_path), exist_ok=True)
        else:
            logger.info(f"Initializing ProductRetriever with remote Qdrant at: {qdrant_url}")
        
        try:
            # Initialize embedding model
            self.embedding_model = OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_ADA_2
            )
            
            # Initialize direct Qdrant client for remote connections
            if self.using_remote:
                self.qdrant_client = qdrant_client.QdrantClient(
                    url=qdrant_url,
                    api_key=qdrant_api_key
                )
                logger.info(f"Connected to remote Qdrant instance: {qdrant_url}")
                
                # Check if collection exists, create if it doesn't
                self._ensure_collection_exists()
            
            # Initialize retriever for local mode only - UPDATED for the latest CAMEL API
            if not self.using_remote:
                # Direct initialization of AutoRetriever with parameters instead of using RetrieverConfig
                self.retriever = AutoRetriever(
                    vector_storage_local_path=vector_storage_path,
                    storage_type=StorageType.QDRANT,
                    embedding_model=self.embedding_model
                )
                logger.info("AutoRetriever initialized with the latest API")
            else:
                # For remote, we'll use our own implementation
                self.retriever = None
            
            # Set up retrieval toolkit for function calling
            self.retrieval_toolkit = RetrievalToolkit()
            self.retrieval_tools = self.retrieval_toolkit.get_tools()
            
            logger.info("ProductRetriever initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ProductRetriever: {e}")
            # Create empty placeholders for graceful degradation
            self.embedding_model = None
            self.retriever = None
            self.retrieval_toolkit = None
            self.retrieval_tools = []
            if self.using_remote:
                self.qdrant_client = None
    
    # Rest of the class remains unchanged
    # ...
    
    def _ensure_collection_exists(self):
        """Ensure that the collection exists, creating it if necessary"""
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections()
            collection_exists = any(c.name == self.qdrant_collection_name for c in collections.collections)
            
            if not collection_exists:
                print(f"Creating collection '{self.qdrant_collection_name}'...")
                # Create the collection
                self.qdrant_client.create_collection(
                    collection_name=self.qdrant_collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,  # OpenAI embedding size
                        distance=models.Distance.COSINE
                    )
                )
                print(f"Collection '{self.qdrant_collection_name}' created successfully")
                return True
            return True
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            print(f"Error ensuring collection exists: {e}")
            return False
    
    # Implement other methods here (same as the original file)
    # The rest of the methods should remain the same
    
    def search_products(self, query, limit=5, similarity_threshold=0.7):
        """
        Search for products based on a query using vector similarity.
        
        Args:
            query: Search query
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score
            
        Returns:
            Retrieved product information
        """
        logger.info(f"Searching products with query: '{query}'")
        
        if not query or len(query.strip()) == 0:
            logger.warning("Empty query provided")
            return []
        
        try:
            if self.using_remote:
                # Use direct Qdrant client for remote search
                return self._search_remote_qdrant(query, limit, similarity_threshold)
            elif self.retriever:
                # Use CAMEL's AutoRetriever for local search - UPDATED API
                search_results = self.retriever.search(
                    query=query,
                    top_k=limit,
                    similarity_threshold=similarity_threshold
                )
                
                logger.info(f"Found {len(search_results) if search_results else 0} results")
                
                # Format results for compatibility with the rest of the system
                formatted_results = self._process_retrieval_results(search_results)
                
                return formatted_results
            else:
                logger.error("No search capabilities available")
                return []
                
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            return []
    
    # Add the remaining methods from your original file
    # ...
    
    def get_tools(self):
        """
        Get the retrieval tools for function calling.
        
        Returns:
            List of retrieval tools
        """
        return self.retrieval_tools