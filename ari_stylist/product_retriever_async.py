"""
Enhanced Product Retriever for AI Stylist - Qdrant Implementation
Provides full product operations for the vector migration
"""

import os
import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from product_field_mapping import map_fashion_product

import numpy as np
from datetime import datetime
import uuid

logger = logging.getLogger("product_retriever_async")

# Try to import Qdrant client
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Range, ScoredPoint
    QDRANT_AVAILABLE = True
except ImportError:
    logger.warning("Qdrant client not installed. Install with: pip install qdrant-client")
    QDRANT_AVAILABLE = False

# Try to import OpenAI for embeddings - UPDATED FOR v1.0+
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("OpenAI not installed. Install with: pip install openai")
    OPENAI_AVAILABLE = False


class ProductRetrieverAsync:
    """
    Enhanced asynchronous product retriever using Qdrant for vector-based search.
    Implements full product operations as specified in the migration plan.
    """
    
    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        collection_name: str = None,
        embedding_model: str = "text-embedding-3-small"
    ):
        """
        Initialize the enhanced product retriever.
        
        Args:
            qdrant_url: Qdrant server URL
            qdrant_api_key: Qdrant API key
            collection_name: Name of the product collection
            embedding_model: OpenAI embedding model to use
        """
        # Use environment variable if collection_name not provided
        self.collection_name = collection_name or os.environ.get("QDRANT_COLLECTION_NAME", "fashion_products")
        self.embedding_model = embedding_model
        
        # Get config from environment if not provided
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        
        # Initialize OpenAI client - NEW FOR v1.0+
        self.openai_client = None
        if OPENAI_AVAILABLE:
            self.openai_client = OpenAI()
        
        # Initialize clients
        self.client = None
        self._init_client()
        
        # Cache for embeddings
        self.embedding_cache = {}
        
        logger.info(f"ProductRetrieverAsync initialized with collection: {self.collection_name}")
    
    def _init_client(self):
        """Initialize Qdrant client"""
        if not QDRANT_AVAILABLE:
            logger.error("Qdrant client not available")
            return
        
        try:
            self.client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key,
            )
            
            # Ensure collection exists
            self._ensure_collection()
            
            logger.info("Qdrant client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            self.client = None
    
    def _ensure_collection(self):
        """Ensure the product collection exists"""
        if not self.client:
            return
        
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection with proper schema
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=1536,  # OpenAI embedding size
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Collection already exists: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error ensuring collection: {e}")
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using OpenAI"""
        if not OPENAI_AVAILABLE or not self.openai_client:
            # Return random embedding for testing
            return np.random.rand(1536).tolist()
        
        # Check cache
        if text in self.embedding_cache:
            return self.embedding_cache[text]
        
        try:
            # Use OpenAI v1.0+ API to get embedding
            response = await asyncio.to_thread(
                self.openai_client.embeddings.create,
                input=text,
                model=self.embedding_model
            )
            
            # Extract embedding using new response format
            embedding = response.data[0].embedding
            
            # Cache the embedding
            self.embedding_cache[text] = embedding
            
            return embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            # Return random embedding as fallback
            return np.random.rand(1536).tolist()
    
    async def index_product(self, product: Dict[str, Any]) -> bool:
        """
        Index a product in Qdrant
        
        Args:
            product: Product dictionary with required fields
            
        Returns:
            bool: Success status
        """
        if not self.client or not product.get('id'):
            return False
        
        try:
            # Create searchable text from product
            search_text = self._create_search_text(product)
            
            # Get embedding
            embedding = await self.get_embedding(search_text)
            if not embedding:
                return False
            
            # Create point
            point = PointStruct(
                id=product['id'],
                vector=embedding,
                payload={
                    "id": product['id'],
                    "title": product.get('title', ''),
                    "description": product.get('description', ''),
                    "price": float(product.get('price', 0)),
                    "category": product.get('category', ''),
                    "subcategory": product.get('subcategory', ''),
                    "brand": product.get('brand', ''),
                    "colors": product.get('colors', []),
                    "sizes": product.get('sizes', []),
                    "tags": product.get('tags', []),
                    "materials": product.get('materials', []),
                    "collections": product.get('collections', []),
                    "images": product.get('images', []),
                    "created_at": product.get('created_at', datetime.now().isoformat()),
                    "updated_at": datetime.now().isoformat(),
                    "popularity_score": float(product.get('popularity_score', 0)),
                    "return_rate": float(product.get('return_rate', 0)),
                    "in_stock": product.get('in_stock', True),
                    "visited_num": int(product.get('visited_num', 0))
                }
            )
            
            # Upsert to Qdrant
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Indexed product: {product['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing product: {e}")
            return False
    
    async def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product details by ID
        
        Args:
            product_id: Product ID
            
        Returns:
            Product dictionary or None
        """
        if not self.client:
            return None
        
        try:
            # Retrieve point by ID
            points = await asyncio.to_thread(
                self.client.retrieve,
                collection_name=self.collection_name,
                ids=[product_id]
            )
            
            if points:
                return map_fashion_product(points[0].payload)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            return None
    
    async def get_products_by_filter(
        self,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        colors: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        in_stock: Optional[bool] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get products by metadata filters
        
        Returns:
            List of products matching filters
        """
        if not self.client:
            return []
        
        try:
            # Build filter conditions for fashion_products fields
            must_conditions = []
            
            if category:
                # Fashion products use 'categories' field
                must_conditions.append(
                    FieldCondition(key="categories", match={"any": [category]})
                )
            
            if subcategory:
                # Map to product_type
                must_conditions.append(
                    FieldCondition(key="product_type", match={"value": subcategory})
                )
            
            if brand:
                must_conditions.append(
                    FieldCondition(key="brand", match={"value": brand})
                )
            
            if min_price is not None or max_price is not None:
                price_range = Range(
                    gte=min_price if min_price is not None else 0,
                    lte=max_price if max_price is not None else 999999
                )
                must_conditions.append(
                    FieldCondition(key="price", range=price_range)
                )
            
            if colors:
                # Fashion products use 'primary_color' field
                for color in colors:
                    must_conditions.append(
                        FieldCondition(key="primary_color", match={"value": color})
                    )
            
            if tags:
                # Map to collections
                for tag in tags:
                    must_conditions.append(
                        FieldCondition(key="collections", match={"any": [tag]})
                    )
            
            # Create filter
            filter_obj = None
            if must_conditions:
                filter_obj = Filter(must=must_conditions)
            
            # Search with filters (using a dummy vector for filter-only search)
            dummy_vector = [0.0] * 1536
            
            response = await asyncio.to_thread(
                self.client.query_points,
                collection_name=self.collection_name,
                query=dummy_vector,
                query_filter=filter_obj,
                limit=limit,
                score_threshold=0.3  # Accept all scores since we're filtering
            )
            
            # Extract points from QueryResponse
            points = response.points if hasattr(response, "points") else []
            
            # Map products
            products = [map_fashion_product(point.payload) for point in points if hasattr(point, 'payload')]
            
            logger.info(f"Found {len(products)} products with filters")
            return products
            
        except Exception as e:
            logger.error(f"Error getting products by filter: {e}")
            return []
    
    async def get_similar_products(
        self,
        product_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get products similar to a given product
        
        Args:
            product_id: Reference product ID
            limit: Number of similar products
            
        Returns:
            List of similar products
        """
        if not self.client:
            return []
        
        try:
            # Get the reference product
            ref_product = await self.get_product_details(product_id)
            if not ref_product:
                return []
            
            # Create search text
            search_text = self._create_search_text(ref_product)
            
            # Get embedding
            embedding = await self.get_embedding(search_text)
            if not embedding:
                return []
            
            # Search for similar products
            response = await asyncio.to_thread(
                self.client.query_points,
                collection_name=self.collection_name,
                query=embedding,
                limit=limit + 1,  # Get one extra to exclude self
                score_threshold=0.6
            )
            
            # Extract points from QueryResponse
            points = response.points if hasattr(response, "points") else []
            
            # Extract products and exclude the reference product
            similar_products = []
            for point in points:
                if hasattr(point, 'payload') and point.payload.get('product_id') != product_id:
                    similar_products.append(map_fashion_product(point.payload))
            
            return similar_products[:limit]
            
        except Exception as e:
            logger.error(f"Error getting similar products: {e}")
            return []
    
    async def get_popular_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get popular products based on popularity score
        
        Returns:
            List of popular products
        """
        if not self.client:
            return []
        
        try:
            # Filter by high fashion_confidence (mapped to popularity_score)
            filter_obj = Filter(
                must=[
                    FieldCondition(
                        key="fashion_confidence",
                        range=Range(gte=0.7)
                    )
                ]
            )
            
            # Use dummy vector for filter-based search
            dummy_vector = [0.0] * 1536
            
            response = await asyncio.to_thread(
                self.client.query_points,
                collection_name=self.collection_name,
                query=dummy_vector,
                query_filter=filter_obj,
                limit=limit,
                score_threshold=0.3
            )
            
            # Extract points from QueryResponse
            points = response.points if hasattr(response, "points") else []
            
            # Map and sort products
            products = [map_fashion_product(point.payload) for point in points if hasattr(point, 'payload')]
            products.sort(key=lambda x: x.get('popularity_score', 0), reverse=True)
            
            return products
            
        except Exception as e:
            logger.error(f"Error getting popular products: {e}")
            return []
    
    async def search_by_natural_language(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search products using natural language query
        
        Args:
            query: Natural language search query
            limit: Maximum results
            filters: Optional metadata filters
            
        Returns:
            List of matching products
        """
        if not self.client:
            return []
        
        try:
            # Get query embedding
            embedding = await self.get_embedding(query)
            if not embedding:
                return []
            
            # Build filter from provided filters
            filter_obj = None
            if filters:
                must_conditions = []
                
                # Map standard fields to fashion_products fields
                if 'category' in filters:
                    must_conditions.append(
                        FieldCondition(key="categories", match={"any": [filters['category']]})
                    )
                
                if 'min_price' in filters:
                    must_conditions.append(
                        FieldCondition(
                            key="price",
                            range=Range(gte=filters['min_price'])
                        )
                    )
                
                if 'max_price' in filters:
                    must_conditions.append(
                        FieldCondition(
                            key="price",
                            range=Range(lte=filters['max_price'])
                        )
                    )
                
                if must_conditions:
                    filter_obj = Filter(must=must_conditions)
            
            # Search
            response = await asyncio.to_thread(
                self.client.query_points,
                collection_name=self.collection_name,
                query=embedding,
                query_filter=filter_obj,
                limit=limit,
                score_threshold=0.3  # Lower threshold for fashion products
            )
            
            # Extract points from QueryResponse
            points = response.points if hasattr(response, "points") else []
            
            # Map products
            products = [map_fashion_product(point.payload) for point in points if hasattr(point, 'payload')]
            
            logger.info(f"Found {len(products)} products for query: {query}")
            return products
            
        except Exception as e:
            logger.error(f"Error in natural language search: {e}")
            return []
    
    async def bulk_index_products(self, products: List[Dict[str, Any]], batch_size: int = 100) -> Tuple[int, int]:
        """
        Bulk index products for migration
        
        Args:
            products: List of products to index
            batch_size: Batch size for indexing
            
        Returns:
            Tuple of (successful, failed) counts
        """
        if not self.client:
            return 0, len(products)
        
        successful = 0
        failed = 0
        
        # Process in batches
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            points = []
            
            for product in batch:
                try:
                    # Create search text
                    search_text = self._create_search_text(product)
                    
                    # Get embedding
                    embedding = await self.get_embedding(search_text)
                    if not embedding:
                        failed += 1
                        continue
                    
                    # Create point
                    point = PointStruct(
                        id=product.get('id', str(uuid.uuid4())),
                        vector=embedding,
                        payload=self._prepare_payload(product)
                    )
                    
                    points.append(point)
                    
                except Exception as e:
                    logger.error(f"Error preparing product for indexing: {e}")
                    failed += 1
            
            # Bulk upsert
            if points:
                try:
                    await asyncio.to_thread(
                        self.client.upsert,
                        collection_name=self.collection_name,
                        points=points
                    )
                    successful += len(points)
                    logger.info(f"Indexed batch of {len(points)} products")
                except Exception as e:
                    logger.error(f"Error bulk indexing: {e}")
                    failed += len(points)
        
        logger.info(f"Bulk indexing complete: {successful} successful, {failed} failed")
        return successful, failed
    
    def _create_search_text(self, product: Dict[str, Any]) -> str:
        """Create searchable text from product data"""
        parts = []
        
        # Add main fields
        if product.get('title'):
            parts.append(product['title'])
        
        if product.get('description'):
            parts.append(product['description'])
        
        if product.get('category'):
            parts.append(f"Category: {product['category']}")
        
        if product.get('brand'):
            parts.append(f"Brand: {product['brand']}")
        
        # Add list fields
        if product.get('colors'):
            colors = product['colors'] if isinstance(product['colors'], list) else [product['colors']]
            parts.append(f"Colors: {', '.join(colors)}")
        
        if product.get('tags'):
            tags = product['tags'] if isinstance(product['tags'], list) else [product['tags']]
            parts.append(f"Tags: {', '.join(tags)}")
        
        if product.get('materials'):
            materials = product['materials'] if isinstance(product['materials'], list) else [product['materials']]
            parts.append(f"Materials: {', '.join(materials)}")
        
        return " ".join(parts)
    
    def _prepare_payload(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare product payload for Qdrant"""
        return {
            "id": product.get('id', str(uuid.uuid4())),
            "title": product.get('title', ''),
            "description": product.get('description', ''),
            "price": float(product.get('price', 0)),
            "category": product.get('category', ''),
            "subcategory": product.get('subcategory', ''),
            "brand": product.get('brand', ''),
            "colors": self._ensure_list(product.get('colors', [])),
            "sizes": self._ensure_list(product.get('sizes', [])),
            "tags": self._ensure_list(product.get('tags', [])),
            "materials": self._ensure_list(product.get('materials', [])),
            "collections": self._ensure_list(product.get('collections', [])),
            "images": self._ensure_list(product.get('images', [])),
            "created_at": product.get('created_at', datetime.now().isoformat()),
            "updated_at": datetime.now().isoformat(),
            "popularity_score": float(product.get('popularity_score', 0)),
            "return_rate": float(product.get('return_rate', 0)),
            "in_stock": product.get('in_stock', True),
            "visited_num": int(product.get('visited_num', 0))
        }
    
    def _ensure_list(self, value: Any) -> List[Any]:
        """Ensure value is a list"""
        if isinstance(value, list):
            return value
        elif value:
            return [value]
        return []
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection"""
        if not self.client:
            return {}
        
        try:
            info = await asyncio.to_thread(
                self.client.get_collection,
                collection_name=self.collection_name
            )
            
            return {
                "vectors_count": info.vectors_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "points_count": info.points_count,
                "segments_count": info.segments_count,
                "status": info.status
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {}


# """
# Enhanced Product Retriever for AI Stylist - Qdrant Implementation
# Provides full product operations for the vector migration
# """

# import os
# import logging
# import json
# import asyncio
# from typing import Dict, List, Any, Optional, Tuple
# from product_field_mapping import map_fashion_product

# import numpy as np
# from datetime import datetime
# import uuid

# logger = logging.getLogger("product_retriever_async")

# # Try to import Qdrant client
# try:
#     from qdrant_client import QdrantClient
#     from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Range, ScoredPoint
#     QDRANT_AVAILABLE = True
# except ImportError:
#     logger.warning("Qdrant client not installed. Install with: pip install qdrant-client")
#     QDRANT_AVAILABLE = False

# # Try to import OpenAI for embeddings - UPDATED FOR v1.0+
# try:
#     from openai import OpenAI
#     OPENAI_AVAILABLE = True
# except ImportError:
#     logger.warning("OpenAI not installed. Install with: pip install openai")
#     OPENAI_AVAILABLE = False


# class ProductRetrieverAsync:
#     """
#     Enhanced asynchronous product retriever using Qdrant for vector-based search.
#     Implements full product operations as specified in the migration plan.
#     """
    
#     def __init__(
#         self,
#         qdrant_url: Optional[str] = None,
#         qdrant_api_key: Optional[str] = None,
#         collection_name: str = "fashion_products",
#         embedding_model: str = "text-embedding-3-small"
#     ):
#         """
#         Initialize the enhanced product retriever.
        
#         Args:
#             qdrant_url: Qdrant server URL
#             qdrant_api_key: Qdrant API key
#             collection_name: Name of the product collection
#             embedding_model: OpenAI embedding model to use
#         """
#         self.collection_name = collection_name
#         self.embedding_model = embedding_model
        
#         # Get config from environment if not provided
#         self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333")
#         self.qdrant_api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        
#         # Initialize OpenAI client - NEW FOR v1.0+
#         self.openai_client = None
#         if OPENAI_AVAILABLE:
#             self.openai_client = OpenAI()
        
#         # Initialize clients
#         self.client = None
#         self._init_client()
        
#         # Cache for embeddings
#         self.embedding_cache = {}
        
#         logger.info(f"ProductRetrieverAsync initialized with collection: {collection_name}")
    
#     def _init_client(self):
#         """Initialize Qdrant client"""
#         if not QDRANT_AVAILABLE:
#             logger.error("Qdrant client not available")
#             return
        
#         try:
#             self.client = QdrantClient(
#                 url=self.qdrant_url,
#                 api_key=self.qdrant_api_key,
#             )
            
#             # Ensure collection exists
#             self._ensure_collection()
            
#             logger.info("Qdrant client initialized successfully")
#         except Exception as e:
#             logger.error(f"Failed to initialize Qdrant client: {e}")
#             self.client = None
    
#     def _ensure_collection(self):
#         """Ensure the product collection exists"""
#         if not self.client:
#             return
        
#         try:
#             # Check if collection exists
#             collections = self.client.get_collections()
#             collection_names = [c.name for c in collections.collections]
            
#             if self.collection_name not in collection_names:
#                 # Create collection with proper schema
#                 self.client.create_collection(
#                     collection_name=self.collection_name,
#                     vectors_config=VectorParams(
#                         size=1536,  # OpenAI embedding size
#                         distance=Distance.COSINE
#                     )
#                 )
#                 logger.info(f"Created collection: {self.collection_name}")
#             else:
#                 logger.info(f"Collection already exists: {self.collection_name}")
#         except Exception as e:
#             logger.error(f"Error ensuring collection: {e}")
    
#     async def get_embedding(self, text: str) -> Optional[List[float]]:
#         """Get embedding for text using OpenAI"""
#         if not OPENAI_AVAILABLE or not self.openai_client:
#             # Return random embedding for testing
#             return np.random.rand(1536).tolist()
        
#         # Check cache
#         if text in self.embedding_cache:
#             return self.embedding_cache[text]
        
#         try:
#             # Use OpenAI v1.0+ API to get embedding
#             response = await asyncio.to_thread(
#                 self.openai_client.embeddings.create,
#                 input=text,
#                 model=self.embedding_model
#             )
            
#             # Extract embedding using new response format
#             embedding = response.data[0].embedding
            
#             # Cache the embedding
#             self.embedding_cache[text] = embedding
            
#             return embedding
#         except Exception as e:
#             logger.error(f"Error getting embedding: {e}")
#             # Return random embedding as fallback
#             return np.random.rand(1536).tolist()
    
#     async def index_product(self, product: Dict[str, Any]) -> bool:
#         """
#         Index a product in Qdrant
        
#         Args:
#             product: Product dictionary with required fields
            
#         Returns:
#             bool: Success status
#         """
#         if not self.client or not product.get('id'):
#             return False
        
#         try:
#             # Create searchable text from product
#             search_text = self._create_search_text(product)
            
#             # Get embedding
#             embedding = await self.get_embedding(search_text)
#             if not embedding:
#                 return False
            
#             # Create point
#             point = PointStruct(
#                 id=product['id'],
#                 vector=embedding,
#                 payload={
#                     "id": product['id'],
#                     "title": product.get('title', ''),
#                     "description": product.get('description', ''),
#                     "price": float(product.get('price', 0)),
#                     "category": product.get('category', ''),
#                     "subcategory": product.get('subcategory', ''),
#                     "brand": product.get('brand', ''),
#                     "colors": product.get('colors', []),
#                     "sizes": product.get('sizes', []),
#                     "tags": product.get('tags', []),
#                     "materials": product.get('materials', []),
#                     "collections": product.get('collections', []),
#                     "images": product.get('images', []),
#                     "created_at": product.get('created_at', datetime.now().isoformat()),
#                     "updated_at": datetime.now().isoformat(),
#                     "popularity_score": float(product.get('popularity_score', 0)),
#                     "return_rate": float(product.get('return_rate', 0)),
#                     "in_stock": product.get('in_stock', True),
#                     "visited_num": int(product.get('visited_num', 0))
#                 }
#             )
            
#             # Upsert to Qdrant
#             await asyncio.to_thread(
#                 self.client.upsert,
#                 collection_name=self.collection_name,
#                 points=[point]
#             )
            
#             logger.info(f"Indexed product: {product['id']}")
#             return True
            
#         except Exception as e:
#             logger.error(f"Error indexing product: {e}")
#             return False
    
#     async def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
#         """
#         Get product details by ID
        
#         Args:
#             product_id: Product ID
            
#         Returns:
#             Product dictionary or None
#         """
#         if not self.client:
#             return None
        
#         try:
#             # Retrieve point by ID
#             points = await asyncio.to_thread(
#                 self.client.retrieve,
#                 collection_name=self.collection_name,
#                 ids=[product_id]
#             )
            
#             if points:
#                 return points[0].payload
            
#             return None
            
#         except Exception as e:
#             logger.error(f"Error getting product details: {e}")
#             return None
    
#     async def get_products_by_filter(
#         self,
#         category: Optional[str] = None,
#         subcategory: Optional[str] = None,
#         brand: Optional[str] = None,
#         min_price: Optional[float] = None,
#         max_price: Optional[float] = None,
#         colors: Optional[List[str]] = None,
#         tags: Optional[List[str]] = None,
#         in_stock: Optional[bool] = None,
#         limit: int = 10
#     ) -> List[Dict[str, Any]]:
#         """
#         Get products by metadata filters
        
#         Returns:
#             List of products matching filters
#         """
#         if not self.client:
#             return []
        
#         try:
#             # Build filter conditions
#             must_conditions = []
            
#             if category:
#                 must_conditions.append(
#                     FieldCondition(key="category", match={"value": category})
#                 )
            
#             if subcategory:
#                 must_conditions.append(
#                     FieldCondition(key="subcategory", match={"value": subcategory})
#                 )
            
#             if brand:
#                 must_conditions.append(
#                     FieldCondition(key="brand", match={"value": brand})
#                 )
            
#             if min_price is not None or max_price is not None:
#                 price_range = Range(
#                     gte=min_price if min_price is not None else 0,
#                     lte=max_price if max_price is not None else 999999
#                 )
#                 must_conditions.append(
#                     FieldCondition(key="price", range=price_range)
#                 )
            
#             if colors:
#                 for color in colors:
#                     must_conditions.append(
#                         FieldCondition(key="colors", match={"any": [color]})
#                     )
            
#             if tags:
#                 for tag in tags:
#                     must_conditions.append(
#                         FieldCondition(key="tags", match={"any": [tag]})
#                     )
            
#             if in_stock is not None:
#                 must_conditions.append(
#                     FieldCondition(key="in_stock", match={"value": in_stock})
#                 )
            
#             # Create filter
#             filter_obj = None
#             if must_conditions:
#                 filter_obj = Filter(must=must_conditions)
            
#             # Search with filters (using a dummy vector for filter-only search)
#             dummy_vector = [0.0] * 1536
            
#             results = await asyncio.to_thread(
#                 self.client.query_points,
#                 collection_name=self.collection_name,
#                 query=dummy_vector,
#                 query_filter=filter_obj,
#                 limit=limit,
#                 score_threshold=0.3  # Accept all scores since we're filtering
#             )
#             logger.info(f"Query returned type: {type(results)}, has points: {hasattr(results, "points") if results else False}")
#             # Extract points from QueryResponse
#             if hasattr(results, "points"):
#                 results = results.points
            
#             # Extract products from results
#             logger.info(f"Processing {len(results) if hasattr(results, \'__len__\') else \'unknown\'} results")
#             products = [map_fashion_product(hit.payload) for hit in results]
            
#             logger.info(f"Found {len(products)} products with filters")
#             return products
            
#         except Exception as e:
#             logger.error(f"Error getting products by filter: {e}")
#             return []
    
#     async def get_similar_products(
#         self,
#         product_id: str,
#         limit: int = 5
#     ) -> List[Dict[str, Any]]:
#         """
#         Get products similar to a given product
        
#         Args:
#             product_id: Reference product ID
#             limit: Number of similar products
            
#         Returns:
#             List of similar products
#         """
#         if not self.client:
#             return []
        
#         try:
#             # Get the reference product
#             ref_product = await self.get_product_details(product_id)
#             if not ref_product:
#                 return []
            
#             # Create search text
#             search_text = self._create_search_text(ref_product)
            
#             # Get embedding
#             embedding = await self.get_embedding(search_text)
#             if not embedding:
#                 return []
            
#             # Search for similar products
#             results = await asyncio.to_thread(
#                 self.client.query_points,
#                 collection_name=self.collection_name,
#                 query=embedding,
#                 limit=limit + 1,  # Get one extra to exclude self
#                 score_threshold=0.6
#             )
#             logger.info(f"Query returned type: {type(results)}, has points: {hasattr(results, "points") if results else False}")
#             # Extract points from QueryResponse
#             if hasattr(results, "points"):
#                 results = results.points
            
#             # Extract products and exclude the reference product
#             similar_logger.info(f"Processing {len(results) if hasattr(results, \'__len__\') else \'unknown\'} results")
#             products = []
#             for hit in results:
#                 if hit.payload.get('id') != product_id:
#                     similar_products.append(hit.payload)
            
#             return similar_products[:limit]
            
#         except Exception as e:
#             logger.error(f"Error getting similar products: {e}")
#             return []
    
#     async def get_popular_products(self, limit: int = 10) -> List[Dict[str, Any]]:
#         """
#         Get popular products based on popularity score
        
#         Returns:
#             List of popular products
#         """
#         if not self.client:
#             return []
        
#         try:
#             # Filter by high popularity score
#             filter_obj = Filter(
#                 must=[
#                     FieldCondition(
#                         key="popularity_score",
#                         range=Range(gte=0.7)
#                     )
#                 ]
#             )
            
#             # Use dummy vector for filter-based search
#             dummy_vector = [0.0] * 1536
            
#             results = await asyncio.to_thread(
#                 self.client.query_points,
#                 collection_name=self.collection_name,
#                 query=dummy_vector,
#                 query_filter=filter_obj,
#                 limit=limit,
#                 score_threshold=0.3
#             )
#             logger.info(f"Query returned type: {type(results)}, has points: {hasattr(results, "points") if results else False}")
#             # Extract points from QueryResponse
#             if hasattr(results, "points"):
#                 results = results.points
            
#             # Sort by popularity score
#             logger.info(f"Processing {len(results) if hasattr(results, \'__len__\') else \'unknown\'} results")
#             products = [map_fashion_product(hit.payload) for hit in results]
#             products.sort(key=lambda x: x.get('popularity_score', 0), reverse=True)
            
#             return products
            
#         except Exception as e:
#             logger.error(f"Error getting popular products: {e}")
#             return []
    
#     async def search_by_natural_language(
#         self,
#         query: str,
#         limit: int = 10,
#         filters: Optional[Dict[str, Any]] = None
#     ) -> List[Dict[str, Any]]:
#         """
#         Search products using natural language query
        
#         Args:
#             query: Natural language search query
#             limit: Maximum results
#             filters: Optional metadata filters
            
#         Returns:
#             List of matching products
#         """
#         if not self.client:
#             return []
        
#         try:
#             # Get query embedding
#             embedding = await self.get_embedding(query)
#             logger.info(f"Got embedding for query \'{query}\': {embedding is not None}")
#             if not embedding:
#                 return []
            
#             # Build filter from provided filters
#             filter_obj = None
#             if filters:
#                 must_conditions = []
                
#                 if 'category' in filters:
#                     must_conditions.append(
#                         FieldCondition(key="category", match={"value": filters['category']})
#                     )
                
#                 if 'min_price' in filters:
#                     must_conditions.append(
#                         FieldCondition(
#                             key="price",
#                             range=Range(gte=filters['min_price'])
#                         )
#                     )
                
#                 if 'max_price' in filters:
#                     must_conditions.append(
#                         FieldCondition(
#                             key="price",
#                             range=Range(lte=filters['max_price'])
#                         )
#                     )
                
#                 if must_conditions:
#                     filter_obj = Filter(must=must_conditions)
            
#             # Search
#             results = await asyncio.to_thread(
#                 self.client.query_points,
#                 collection_name=self.collection_name,
#                 query=embedding,
#                 query_filter=filter_obj,
#                 limit=limit,
#                 score_threshold=0.5
#             )
#             logger.info(f"Query returned type: {type(results)}, has points: {hasattr(results, "points") if results else False}")
#             # Extract points from QueryResponse
#             if hasattr(results, "points"):
#                 results = results.points
            
#             # Extract and return products
#             logger.info(f"Processing {len(results) if hasattr(results, \'__len__\') else \'unknown\'} results")
#             products = [map_fashion_product(hit.payload) for hit in results]
            
#             logger.info(f"Found {len(products)} products for query: {query}")
#             return products
            
#         except Exception as e:
#             logger.error(f"Error in natural language search: {e}")
#             return []
    
#     async def bulk_index_products(self, products: List[Dict[str, Any]], batch_size: int = 100) -> Tuple[int, int]:
#         """
#         Bulk index products for migration
        
#         Args:
#             products: List of products to index
#             batch_size: Batch size for indexing
            
#         Returns:
#             Tuple of (successful, failed) counts
#         """
#         if not self.client:
#             return 0, len(products)
        
#         successful = 0
#         failed = 0
        
#         # Process in batches
#         for i in range(0, len(products), batch_size):
#             batch = products[i:i + batch_size]
#             points = []
            
#             for product in batch:
#                 try:
#                     # Create search text
#                     search_text = self._create_search_text(product)
                    
#                     # Get embedding
#                     embedding = await self.get_embedding(search_text)
#                     if not embedding:
#                         failed += 1
#                         continue
                    
#                     # Create point
#                     point = PointStruct(
#                         id=product.get('id', str(uuid.uuid4())),
#                         vector=embedding,
#                         payload=self._prepare_payload(product)
#                     )
                    
#                     points.append(point)
                    
#                 except Exception as e:
#                     logger.error(f"Error preparing product for indexing: {e}")
#                     failed += 1
            
#             # Bulk upsert
#             if points:
#                 try:
#                     await asyncio.to_thread(
#                         self.client.upsert,
#                         collection_name=self.collection_name,
#                         points=points
#                     )
#                     successful += len(points)
#                     logger.info(f"Indexed batch of {len(points)} products")
#                 except Exception as e:
#                     logger.error(f"Error bulk indexing: {e}")
#                     failed += len(points)
        
#         logger.info(f"Bulk indexing complete: {successful} successful, {failed} failed")
#         return successful, failed
    
#     def _create_search_text(self, product: Dict[str, Any]) -> str:
#         """Create searchable text from product data"""
#         parts = []
        
#         # Add main fields
#         if product.get('title'):
#             parts.append(product['title'])
        
#         if product.get('description'):
#             parts.append(product['description'])
        
#         if product.get('category'):
#             parts.append(f"Category: {product['category']}")
        
#         if product.get('brand'):
#             parts.append(f"Brand: {product['brand']}")
        
#         # Add list fields
#         if product.get('colors'):
#             colors = product['colors'] if isinstance(product['colors'], list) else [product['colors']]
#             parts.append(f"Colors: {', '.join(colors)}")
        
#         if product.get('tags'):
#             tags = product['tags'] if isinstance(product['tags'], list) else [product['tags']]
#             parts.append(f"Tags: {', '.join(tags)}")
        
#         if product.get('materials'):
#             materials = product['materials'] if isinstance(product['materials'], list) else [product['materials']]
#             parts.append(f"Materials: {', '.join(materials)}")
        
#         return " ".join(parts)
    
#     def _prepare_payload(self, product: Dict[str, Any]) -> Dict[str, Any]:
#         """Prepare product payload for Qdrant"""
#         return {
#             "id": product.get('id', str(uuid.uuid4())),
#             "title": product.get('title', ''),
#             "description": product.get('description', ''),
#             "price": float(product.get('price', 0)),
#             "category": product.get('category', ''),
#             "subcategory": product.get('subcategory', ''),
#             "brand": product.get('brand', ''),
#             "colors": self._ensure_list(product.get('colors', [])),
#             "sizes": self._ensure_list(product.get('sizes', [])),
#             "tags": self._ensure_list(product.get('tags', [])),
#             "materials": self._ensure_list(product.get('materials', [])),
#             "collections": self._ensure_list(product.get('collections', [])),
#             "images": self._ensure_list(product.get('images', [])),
#             "created_at": product.get('created_at', datetime.now().isoformat()),
#             "updated_at": datetime.now().isoformat(),
#             "popularity_score": float(product.get('popularity_score', 0)),
#             "return_rate": float(product.get('return_rate', 0)),
#             "in_stock": product.get('in_stock', True),
#             "visited_num": int(product.get('visited_num', 0))
#         }
    
#     def _ensure_list(self, value: Any) -> List[Any]:
#         """Ensure value is a list"""
#         if isinstance(value, list):
#             return value
#         elif value:
#             return [value]
#         return []
    
#     async def get_collection_stats(self) -> Dict[str, Any]:
#         """Get statistics about the collection"""
#         if not self.client:
#             return {}
        
#         try:
#             info = await asyncio.to_thread(
#                 self.client.get_collection,
#                 collection_name=self.collection_name
#             )
            
#             return {
#                 "vectors_count": info.vectors_count,
#                 "indexed_vectors_count": info.indexed_vectors_count,
#                 "points_count": info.points_count,
#                 "segments_count": info.segments_count,
#                 "status": info.status
#             }
            
#         except Exception as e:
#             logger.error(f"Error getting collection stats: {e}")
#             return {}