"""
Product Retriever Service for ARI Fashion Stylist.
Qdrant implementation for product vector search and retrieval.
Based on product_retriever_async.py with enhanced error handling.
"""

import os
import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
from datetime import datetime
import uuid

from services.cache.redis_client import RedisService, FallbackRedisService

logger = logging.getLogger("services.product.retriever")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.error("Qdrant client is required. Install with: pip install qdrant-client")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.error("OpenAI is required. Install with: pip install openai")

from models.products import (
    Product, map_fashion_product, create_search_text,
    prepare_qdrant_payload
)
from models.types import ProductFull, ProductRecommendation, QdrantStats


class ProductRetrieverService:
    """
    Asynchronous product retriever using Qdrant for vector-based search.
    Production-ready with connection pooling and caching.
    """

    def __init__(
        self,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
        embedding_timeout: float = 30.0,
        embedding_cache_size: int = 1000,
        query_timeout: float = 90.0,
        max_retry_attempts: int = 3,
        retry_delay: float = 1.0,
        redis_client: Optional[Union[RedisService, FallbackRedisService]] = None
    ):
        """
        Initialize the product retriever with enhanced configuration.
        
        Args:
            qdrant_url: Qdrant server URL
            qdrant_api_key: Qdrant API key
            collection_name: Collection name
            embedding_model: OpenAI embedding model
            embedding_cache_size: Size of embedding cache
            query_timeout: Query timeout in seconds
            max_retry_attempts: Maximum retry attempts
            retry_delay: Delay between retries
        """
        if not QDRANT_AVAILABLE:
            raise RuntimeError("Qdrant client not available")
        if not OPENAI_AVAILABLE:
            raise RuntimeError("OpenAI client not available")
        
        # Configuration
        self.embedding_timeout = embedding_timeout

        self.collection_name = collection_name or os.environ.get("QDRANT_COLLECTION_NAME", "fashion_products")
        self.embedding_model = embedding_model

        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = qdrant_api_key or os.environ.get("QDRANT_API_KEY")
        
        self.query_timeout = query_timeout
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay = retry_delay
        
        # Initialize clients
        self.openai_client = OpenAI()
        self.client = None
        self.redis_client = redis_client
        
        # Embedding cache configuration (now Redis-based)
        self.embedding_cache_size = embedding_cache_size
        self.cache_ttl = 3600  # 1 hour TTL for embeddings
        
        # Statistics
        self.stats = {
            "queries_executed": 0,
            "queries_failed": 0,
            "embeddings_generated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_query_time": 0.0
        }
        
        #self._init_client()
        logger.info(f"ProductRetrieverService initialized with collection: {self.collection_name}")
    
    async def initialize(self):
            """Initialize Qdrant client with retry logic (async)."""
            for attempt in range(self.max_retry_attempts):
                try:
                    self.client = QdrantClient(
                        url=self.qdrant_url,
                        api_key=self.qdrant_api_key,
                        timeout=120.0,  # Extended timeout for 7.4M vector searches
                        prefer_grpc=False  # HTTP is more reliable for large operations
                    )
                    
                    # Test connection
                    await asyncio.to_thread(self.client.get_collections)
                    
                    # Ensure collection exists
                    await self._ensure_collection_async()
                    
                    logger.info("Qdrant client initialized successfully")
                    return
                    
                except Exception as e:
                    logger.error(f"Failed to initialize Qdrant client (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        raise RuntimeError(f"Failed to initialize Qdrant client: {e}")

    async def close(self):
        """Gracefully closes the Qdrant client connection."""
        if self.client:
            try:
                # The Qdrant client has a close method for resource cleanup.
                # We run it in a separate thread to avoid blocking the event loop.
                await asyncio.to_thread(self.client.close)
                logger.info("Qdrant client connection closed successfully.")
            except Exception as e:
                logger.error(f"Error closing Qdrant client: {e}")
        self.client = None

    async def _ensure_collection_async(self):
        """Ensure the product collection exists (async version)."""
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
        try:
            collections = await asyncio.to_thread(self.client.get_collections)
            collection_names = [c.name for c in collections.collections]
            
            if self.collection_name not in collection_names:
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=1536,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Collection already exists: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Error ensuring collection: {e}")
            raise RuntimeError(f"Failed to ensure collection: {e}")
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Get embedding for text using OpenAI with caching and retry.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector or None
        """
        # Check Redis cache first
        if self.redis_client:
            cache_key = f"embedding:{hash(text)}"
            cached_embedding = await self.redis_client.get_json(cache_key)
            if cached_embedding:
                self.stats["cache_hits"] += 1
                return cached_embedding
        
        self.stats["cache_misses"] += 1
        
        # Retry logic for OpenAI
        for attempt in range(self.max_retry_attempts):
            try:
                # Generate embedding with timeout
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.openai_client.embeddings.create,
                        input=text,
                        model=self.embedding_model
                    ),
                    timeout=90.0
                )
                
                embedding = response.data[0].embedding
                self.stats["embeddings_generated"] += 1
                
                # Add to cache
                await self._add_to_embedding_cache(text, embedding)
                
                return embedding
                
            except asyncio.TimeoutError:
                logger.warning(f"OpenAI embedding timeout (attempt {attempt + 1})")
                if attempt == self.max_retry_attempts - 1:
                    raise RuntimeError("OpenAI embedding generation timed out")
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                logger.error(f"Error getting embedding (attempt {attempt + 1}): {e}")
                if attempt == self.max_retry_attempts - 1:
                    raise RuntimeError(f"Failed to get embedding: {e}")
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return None
            
        # except Exception as e:
        #     logger.error(f"Error getting embedding: {e}")
        #     raise RuntimeError(f"Failed to get embedding: {e}")
    
    async def _add_to_embedding_cache(self, text: str, embedding: List[float]):
        """Add embedding to Redis cache."""
        if self.redis_client:
            cache_key = f"embedding:{hash(text)}"
            await self.redis_client.set_json(cache_key, embedding, ttl=self.cache_ttl)
        # Note: Redis handles LRU eviction automatically with maxmemory policies
    

    async def get_embeddings_batch(self, texts: List[str], batch_size: int = 100) -> List[Optional[List[float]]]:
        """
        Get embeddings for multiple texts efficiently.
        
        Args:
            texts: List of texts to embed
            batch_size: Max texts per API call (OpenAI limit is 2048)
            
        Returns:
            List of embeddings (None for failures)
        """
        embeddings = []
        uncached_texts = []
        uncached_indices = []
        
        # Check cache first
        for i, text in enumerate(texts):
            if self.redis_client:
                cache_key = f"embedding:{hash(text)}"
                cached_embedding = await self.redis_client.get_json(cache_key)
                if cached_embedding:
                    self.stats["cache_hits"] += 1
                    embeddings.append(cached_embedding)
                    continue
            
            self.stats["cache_misses"] += 1
            embeddings.append(None)
            uncached_texts.append(text)
            uncached_indices.append(i)
        
        # Process uncached texts in batches
        for i in range(0, len(uncached_texts), batch_size):
            batch = uncached_texts[i:i + batch_size]
            batch_indices = uncached_indices[i:i + batch_size]
            
            for attempt in range(self.max_retry_attempts):
                try:
                    # Batch API call
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.openai_client.embeddings.create,
                            input=batch,
                            model=self.embedding_model
                        ),
                        timeout=90.0  # Longer timeout for batch
                    )
                    
                    # Process response
                    for idx, embedding_data in enumerate(response.data):
                        embedding = embedding_data.embedding
                        original_idx = batch_indices[idx]
                        original_text = batch[idx]
                        
                        embeddings[original_idx] = embedding
                        await self._add_to_embedding_cache(original_text, embedding)
                        self.stats["embeddings_generated"] += 1
                    
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    logger.error(f"Batch embedding error (attempt {attempt + 1}): {e}")
                    if attempt == self.max_retry_attempts - 1:
                        logger.error(f"Failed to embed batch of {len(batch)} texts")
                    else:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return embeddings


    # ==================== PRODUCT OPERATIONS ====================
    
    async def index_product(self, product: Dict[str, Any]) -> bool:
        """
        Index a product in Qdrant.
        
        Args:
            product: Product data
            
        Returns:
            Success status
        """
        if not self.client or not product.get('id'):
            raise ValueError("Invalid product or client not initialized")
        
        try:
            # Create search text
            search_text = create_search_text(product)
            
            # Get embedding
            embedding = await self.get_embedding(search_text)
            if not embedding:
                raise RuntimeError("Failed to generate embedding")
            
            # Prepare payload
            payload = prepare_qdrant_payload(product)
            
            # Create point
            point = PointStruct(
                id=product['id'],
                vector=embedding,
                payload=payload
            )
            
            # Upsert with retry
            for attempt in range(self.max_retry_attempts):
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(
                            self.client.upsert,
                            collection_name=self.collection_name,
                            points=[point]
                        ),
                        timeout=self.query_timeout
                    )
                    
                    logger.info(f"Indexed product: {product['id']}")
                    return True
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout indexing product (attempt {attempt + 1})")
                    if attempt < self.max_retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay)
                    else:
                        raise
                        
        except Exception as e:
            logger.error(f"Error indexing product: {e}")
            raise RuntimeError(f"Failed to index product: {e}")
    
    async def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product details by ID.
        
        Args:
            product_id: Product identifier
            
        Returns:
            Product details dict or None
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            points = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.retrieve,
                    collection_name=self.collection_name,
                    ids=[product_id]
                ),
                timeout=self.query_timeout
            )
            
            # Update statistics
            query_time = asyncio.get_event_loop().time() - start_time
            self.stats["queries_executed"] += 1
            self.stats["total_query_time"] += query_time
            
            if points:
                product_data = map_fashion_product(points[0].payload)
                product = Product(product_data)
                return product.to_full()
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            self.stats["queries_failed"] += 1
            raise RuntimeError(f"Failed to get product details: {e}")
    
    async def search_by_natural_language(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search products using natural language query.
        
        Args:
            query: Natural language search query
            limit: Maximum results
            filters: Optional filters
            score_threshold: Minimum similarity score
            
        Returns:
            List of product recommendation dicts
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Get embedding for query
            embedding = await self.get_embedding(query)
            if not embedding:
                raise RuntimeError("Failed to generate embedding for search query")
            
            # Build filter
            filter_obj = self._build_filter_from_dict(filters) if filters else None
            
            # Execute search
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.query_points,
                    collection_name=self.collection_name,
                    query=embedding,
                    query_filter=filter_obj,
                    limit=limit,
                    score_threshold=score_threshold
                ),
                timeout=self.query_timeout
            )
            
            # Update statistics
            query_time = asyncio.get_event_loop().time() - start_time
            self.stats["queries_executed"] += 1
            self.stats["total_query_time"] += query_time
            
            # Process results
            products = []
            points = response.points if hasattr(response, "points") else []
            
            for idx, point in enumerate(points):
                if hasattr(point, 'payload'):
                    product_data = map_fashion_product(point.payload)
                    product = Product(product_data)
                    
                    # Create recommendation dict
                    recommendation = product.to_recommendation(
                        score=point.score if hasattr(point, 'score') else 1.0,
                        reason=f"Semantic match for '{query[:50]}...'",
                        agent="qdrant",
                        rank=idx + 1,
                        confidence=point.score if hasattr(point, 'score') else 0.5
                    )
                    products.append(recommendation)
            
            logger.info(f"Found {len(products)} products for query: {query}")
            return products
            
        except Exception as e:
            logger.error(f"Error in natural language search: {e}")
            self.stats["queries_failed"] += 1
            raise RuntimeError(f"Natural language search failed: {e}")
    
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
        Get products by metadata filters.
        
        Args:
            Various filter parameters
            limit: Maximum results
            
        Returns:
            List of product dicts
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Build filter conditions
            must_conditions = self._build_filter_conditions(
                category=category,
                subcategory=subcategory, 
                brand=brand,
                min_price=min_price,
                max_price=max_price,
                colors=colors,
                tags=tags,
                in_stock=in_stock
            )
            
            filter_obj = {"must": must_conditions} if must_conditions else None
            
            # Try to use scroll API first (more efficient for filter-only)
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.scroll,
                        collection_name=self.collection_name,
                        scroll_filter=filter_obj,
                        limit=limit,
                        with_payload=True,
                        with_vectors=False  # Don't need vectors
                    ),
                    timeout=self.query_timeout
                )
                
                # Process scroll results
                points = response[0] if response else []
                
            except Exception as scroll_error:
                logger.debug(f"Scroll API failed, falling back to query: {scroll_error}")
                
                # Fallback to query with dummy vector
                dummy_vector = [0.0] * 1536
                
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.query_points,
                        collection_name=self.collection_name,
                        query=dummy_vector,
                        query_filter=filter_obj,
                        limit=limit,
                        score_threshold=0.0
                    ),
                    timeout=self.query_timeout
                )
                
                points = response.points if hasattr(response, "points") else []
            
            # Update statistics
            query_time = asyncio.get_event_loop().time() - start_time
            self.stats["queries_executed"] += 1
            self.stats["total_query_time"] += query_time
            
            # Process results
            products = []
            for point in points:
                if hasattr(point, 'payload'):
                    product_data = map_fashion_product(point.payload)
                    product = Product(product_data)
                    products.append(product.to_full())
            
            logger.info(f"Found {len(products)} products with filters")
            return products
            
        except Exception as e:
            logger.error(f"Error getting products by filter: {e}")
            self.stats["queries_failed"] += 1
            raise RuntimeError(f"Failed to get products by filter: {e}")
    
    async def get_similar_products(
        self,
        product_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get products similar to a given product.
        
        Args:
            product_id: Reference product ID
            limit: Maximum similar products
            
        Returns:
            List of similar product recommendation dicts
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
        try:
            # Get reference product
            ref_product = await self.get_product_details(product_id)
            if not ref_product:
                logger.warning(f"Reference product not found: {product_id}")
                return []
            
            # Create search text and get embedding
            search_text = create_search_text(ref_product)
            embedding = await self.get_embedding(search_text)
            
            if not embedding:
                raise RuntimeError("Failed to generate embedding for similarity search")
            
            # Execute search
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.query_points,
                    collection_name=self.collection_name,
                    query=embedding,
                    limit=limit + 1,  # Get one extra to exclude self
                    score_threshold=0.6
                ),
                timeout=self.query_timeout
            )
            
            # Process results
            similar_products = []
            points = response.points if hasattr(response, "points") else []
            
            for idx, point in enumerate(points):
                if hasattr(point, 'payload'):
                    # Skip the reference product itself
                    if point.payload.get('id') == product_id:
                        continue
                    
                    product_data = map_fashion_product(point.payload)
                    product = Product(product_data)
                    
                    recommendation = product.to_recommendation(
                        score=point.score if hasattr(point, 'score') else 0.8,
                        reason=f"Similar to {ref_product['title']}",
                        agent="qdrant_similarity",
                        rank=idx + 1,
                        confidence=point.score if hasattr(point, 'score') else 0.7
                    )
                    similar_products.append(recommendation)
            
            return similar_products[:limit]
            
        except Exception as e:
            logger.error(f"Error getting similar products: {e}")
            self.stats["queries_failed"] += 1
            raise RuntimeError(f"Failed to get similar products: {e}")
    
    async def get_popular_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get popular products based on popularity score.
        
        Args:
            limit: Maximum products
            
        Returns:
            List of popular product recommendation dicts
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
        try:
            # Filter for high popularity score
            filter_obj = {
                "must": [
                    {
                        "key": "fashion_confidence",
                        "range": {"gte": 0.7}
                    }
                ]
            }
            
            # Use dummy vector
            dummy_vector = [0.0] * 1536
            
            # Execute search
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.query_points,
                    collection_name=self.collection_name,
                    query=dummy_vector,
                    query_filter=filter_obj,
                    limit=limit * 2,  # Get more to sort
                    score_threshold=0.0
                ),
                timeout=self.query_timeout
            )
            
            # Process and sort by popularity
            products = []
            points = response.points if hasattr(response, "points") else []
            
            for point in points:
                if hasattr(point, 'payload'):
                    product_data = map_fashion_product(point.payload)
                    products.append((product_data, product_data.get('popularity_score', 0)))
            
            # Sort by popularity score
            products.sort(key=lambda x: x[1], reverse=True)
            
            # Create recommendations
            recommendations = []
            for idx, (product_data, pop_score) in enumerate(products[:limit]):
                product = Product(product_data)
                recommendation = product.to_recommendation(
                    score=pop_score,
                    reason="Popular item",
                    agent="qdrant_popular",
                    rank=idx + 1,
                    confidence=0.8
                )
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting popular products: {e}")
            self.stats["queries_failed"] += 1
            raise RuntimeError(f"Failed to get popular products: {e}")
    
    # ==================== BULK OPERATIONS ====================
    
    async def bulk_index_products(
        self,
        products: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> Tuple[int, int]:
        """
        Bulk index products for migration.
        
        Args:
            products: List of products
            batch_size: Batch size for indexing
            
        Returns:
            Tuple of (successful, failed) counts
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
        successful = 0
        failed = 0
        
        for i in range(0, len(products), batch_size):
            batch = products[i:i + batch_size]
            points = []
            
            for product in batch:
                try:
                    # Create search text and embedding
                    search_text = create_search_text(product)
                    embedding = await self.get_embedding(search_text)
                    
                    if not embedding:
                        failed += 1
                        continue
                    
                    # Prepare payload
                    payload = prepare_qdrant_payload(product)
                    
                    # Create point
                    point = PointStruct(
                        id=product.get('id', str(uuid.uuid4())),
                        vector=embedding,
                        payload=payload
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
    
    # ==================== HELPER METHODS ====================
    
    def _build_filter_conditions(
        self,
        category: Optional[str],
        subcategory: Optional[str],
        brand: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        colors: Optional[List[str]],
        tags: Optional[List[str]],
        in_stock: Optional[bool]
    ) -> List[Dict[str, Any]]:
        """Build filter conditions for Qdrant query."""
        must_conditions = []
        
        if category:
            must_conditions.append({
                "key": "categories",
                "match": {"any": [category]}
            })
        
        if subcategory:
            must_conditions.append({
                "key": "product_type",
                "match": {"value": subcategory}
            })
        
        if brand:
            must_conditions.append({
                "key": "brand",
                "match": {"value": brand}
            })
        
        if min_price is not None or max_price is not None:
            range_filter = {}
            if min_price is not None:
                range_filter["gte"] = min_price
            if max_price is not None:
                range_filter["lte"] = max_price
            must_conditions.append({
                "key": "price",
                "range": range_filter
            })
        
        # DISABLED: primary_color field doesn't have required index in Qdrant
        # if colors:
        #     for color in colors:
        #         must_conditions.append({
        #             "key": "primary_color",
        #             "match": {"value": color}
        #         })
        
        if tags:
            for tag in tags:
                must_conditions.append({
                    "key": "collections",
                    "match": {"any": [tag]}
                })
        
        if in_stock is not None:
            must_conditions.append({
                "key": "in_stock",
                "match": {"value": in_stock}
            })
        
        return must_conditions
    
    def _build_filter_from_dict(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build Qdrant filter from dictionary."""
        must_conditions = []
        
        # DISABLED: categories field doesn't have required index in Qdrant
        # if 'category' in filters:
        #     must_conditions.append({
        #         "key": "categories", 
        #         "match": {"any": [filters['category']]}
        #     })
        
        if 'min_price' in filters:
            must_conditions.append({
                "key": "price",
                "range": {"gte": filters['min_price']}
            })
        
        if 'max_price' in filters:
            must_conditions.append({
                "key": "price",
                "range": {"lte": filters['max_price']}
            })
        
        # DISABLED: primary_color field doesn't have required index in Qdrant
        # if 'colors' in filters and isinstance(filters['colors'], list):
        #     for color in filters['colors']:
        #         must_conditions.append({
        #             "key": "primary_color", 
        #             "match": {"value": color}
        #         })
        
        if 'tags' in filters and isinstance(filters['tags'], list):
            for tag in filters['tags']:
                must_conditions.append({
                    "key": "collections",
                    "match": {"any": [tag]}
                })
        
        return {"must": must_conditions} if must_conditions else None
    
    # ==================== STATISTICS & HEALTH ====================
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.
        
        Returns:
            Qdrant statistics dict
        """
        if not self.client:
            raise RuntimeError("Qdrant client not initialized")
        
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
                "status": info.status,
                "collection_name": self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            raise RuntimeError(f"Failed to get collection stats: {e}")
    
    async def health_check(self) -> bool:
        """
        Perform health check on Qdrant connection.
        
        Returns:
            True if healthy
        """
        try:
            collections = await asyncio.wait_for(
                asyncio.to_thread(self.client.get_collections),
                timeout=5.0
            )
            return self.collection_name in [c.name for c in collections.collections]
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        total_queries = self.stats["queries_executed"] + self.stats["queries_failed"]
        
        return {
            "queries_executed": self.stats["queries_executed"],
            "queries_failed": self.stats["queries_failed"],
            "embeddings_generated": self.stats["embeddings_generated"],
            "cache_hits": self.stats["cache_hits"],
            "cache_misses": self.stats["cache_misses"],
            "cache_hit_rate": (
                self.stats["cache_hits"] / (self.stats["cache_hits"] + self.stats["cache_misses"]) * 100
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0 else 0
            ),
            "avg_query_time": (
                self.stats["total_query_time"] / self.stats["queries_executed"]
                if self.stats["queries_executed"] > 0 else 0
            ),
            "success_rate": (
                self.stats["queries_executed"] / total_queries * 100
                if total_queries > 0 else 0
            ),
            "cache_type": "Redis" if self.redis_client else "None",
            "cache_max_size": self.embedding_cache_size
        }
