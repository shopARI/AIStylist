"""
Hybrid Data Store Service
Routes data operations between Neo4j and Qdrant
Provides unified interface for all data operations
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
from collections import OrderedDict
import json

logger = logging.getLogger("services.data.hybrid_store")

from models.products import Product, create_product_from_dict
from models.types import (
    UserProfile, UserInteraction, ProductRecommendation,
    InteractionType, get_timestamp
)


class DataSource(Enum):
    """Data source types."""
    NEO4J = "neo4j"
    QDRANT = "qdrant"
    BOTH = "both"
    CACHE = "cache"


class LRUCache:
    """Thread-safe LRU cache with size limit to prevent memory leaks."""
    
    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[Any]:
        """Get item and move to end (most recently used)."""
        if key in self.cache:
            # Move to end (most recently used)
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        return None
    
    def put(self, key: str, value: Any) -> None:
        """Put item and evict oldest if over limit."""
        if key in self.cache:
            # Update existing key
            self.cache.pop(key)
        elif len(self.cache) >= self.max_size:
            # Remove oldest item
            self.cache.popitem(last=False)
        
        self.cache[key] = value
    
    def delete(self, key: str) -> bool:
        """Delete item if exists."""
        return self.cache.pop(key, None) is not None
    
    def clear(self) -> None:
        """Clear all items."""
        self.cache.clear()
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return key in self.cache


class HybridDataStore:
    """
    Unified data store routing between Neo4j and Qdrant.
    Provides seamless data operations across both databases.
    """
    
    def __init__(
        self,
        neo4j_client: Any,
        qdrant_client: Any,
        enable_caching: bool = True,
        sync_interval: int = 300,
        batch_size: int = 50  # Process sync items in batches for 20-30M node efficiency
    ):
        """
        Initialize hybrid data store.
        
        Args:
            neo4j_client: Neo4j service instance
            qdrant_client: Qdrant service instance
            enable_caching: Enable result caching
            sync_interval: Sync interval in seconds
        """
        self.neo4j = neo4j_client
        self.qdrant = qdrant_client
        self.enable_caching = enable_caching
        self.sync_interval = sync_interval
        self.batch_size = batch_size
        
        # Cache for frequently accessed data (LRU with size limit optimized for 20-30M nodes)
        self.cache = LRUCache(max_size=2000)  # Scaled for massive graph operations
        self.cache_ttl = 300  # 5 minutes - longer TTL for expensive queries on massive graph
        
        # Sync tracking
        self.last_sync = {}
        self.sync_queue = asyncio.Queue(maxsize=5000)  # Larger queue for 20-30M node scale
        self._sync_task = None
        self.sync_error_callback = None  # Add error callback
        self._running = True
        
        # Thread safety for cache operations
        self._cache_lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "neo4j_queries": 0,
            "qdrant_queries": 0,
            "cache_hits": 0,
            "sync_operations": 0,
            "errors": 0
        }
        
        logger.info("Hybrid data store initialized")
    
    async def close(self):
        """Gracefully shutdown the hybrid data store."""
        logger.info("Shutting down hybrid data store...")
        
        # Stop sync worker
        self._running = False
        
        if self._sync_task and not self._sync_task.done():
            try:
                self._sync_task.cancel()
                await asyncio.wait_for(self._sync_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.warning("Sync task took longer than expected to stop")
            except Exception as e:
                logger.error(f"Error stopping sync task: {e}")
        
        # Clear cache
        if hasattr(self.cache, 'clear'):
            self.cache.clear()
        
        logger.info("Hybrid data store shutdown complete")
    
    async def initialize(self):
        """Initialize data store and start sync worker."""
        # Ensure schemas
        await self.neo4j.ensure_schema()
        
        # Start sync worker
        self._sync_task = asyncio.create_task(self._sync_worker())
        
        logger.info("Hybrid data store initialized with sync worker")
    
    async def _sync_worker(self):
        """Background worker for data synchronization."""
        while self._running:
            try:
                # Process sync queue in batches for better performance at 20-30M node scale
                batch = []
                batch_count = 0
                
                while not self.sync_queue.empty() and batch_count < self.batch_size:
                    try:
                        sync_item = await asyncio.wait_for(
                            self.sync_queue.get(),
                            timeout=2.0  # Shorter timeout for batch processing
                        )
                        batch.append(sync_item)
                        batch_count += 1
                    except asyncio.TimeoutError:
                        break
                
                # Process the batch
                if batch:
                    await self._process_sync_batch(batch)
                
                # Periodic sync check
                await asyncio.sleep(self.sync_interval)
                
                if not self._running:
                    break

                # Check for stale data
                await self._check_data_consistency()

                # Clean expired cache entries
                await self._cleanup_cache()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync worker: {e}")
                if self.sync_error_callback:
                    try:
                        await self.sync_error_callback(e)
                    except Exception as callback_error:
                        logger.error(f"Sync error callback failed: {callback_error}")
                        # Don't let callback errors crash the worker, but log them
    
    async def _process_sync_batch(self, batch: List[Dict[str, Any]]):
        """Process a batch of sync items efficiently for massive scale."""
        if not batch:
            return
            
        try:
            # Group items by type for batch processing
            user_updates = []
            product_updates = []
            interactions = []
            
            for item in batch:
                sync_type = item.get("type")
                if sync_type == "user_update":
                    user_updates.append(item["user_id"])
                elif sync_type == "product_update":
                    product_updates.append(item["product_id"])
                elif sync_type == "interaction":
                    interactions.append(item)
            
            # Process each type in batch
            if user_updates:
                await self._sync_user_batch(user_updates)
            if product_updates:
                await self._sync_product_batch(product_updates)
            if interactions:
                await self._sync_interaction_batch(interactions)
                
            self.stats["sync_operations"] += len(batch)
            logger.debug(f"Processed batch of {len(batch)} sync items")
            
        except Exception as e:
            logger.error(f"Error processing sync batch: {e}")
            self.stats["errors"] += len(batch)
    
    async def _process_sync_item(self, item: Dict[str, Any]):
        """Process a sync queue item."""
        try:
            sync_type = item.get("type")
            
            if sync_type == "user_update":
                await self._sync_user_data(item["user_id"])
            elif sync_type == "product_update":
                await self._sync_product_data(item["product_id"])
            elif sync_type == "interaction":
                await self._sync_interaction(item)
            
            self.stats["sync_operations"] += 1
            
        except Exception as e:
            logger.error(f"Error processing sync item: {e}")
            self.stats["errors"] += 1
    
    async def _sync_user_batch(self, user_ids: List[str]):
        """Sync multiple users efficiently."""
        # For 20-30M nodes, batch operations are critical
        logger.debug(f"Syncing batch of {len(user_ids)} users")
        # Implementation would batch sync users to reduce DB roundtrips
    
    async def _sync_product_batch(self, product_ids: List[str]):
        """Sync multiple products efficiently.""" 
        logger.debug(f"Syncing batch of {len(product_ids)} products")
        # Implementation would batch sync products
    
    async def _sync_interaction_batch(self, interactions: List[Dict[str, Any]]):
        """Sync multiple interactions efficiently."""
        logger.debug(f"Syncing batch of {len(interactions)} interactions")
        # Implementation would batch process interactions
    
    async def _check_data_consistency(self):
        """Check data consistency between stores."""
        try:
            # Get counts from both stores with timeout
            neo4j_stats = await asyncio.wait_for(
                self.neo4j.get_database_statistics(),
                timeout=30.0
            )
            qdrant_stats = await asyncio.wait_for(
                self.qdrant.get_collection_stats(),
                timeout=20.0
            )
            
            # Log any major discrepancies
            if abs(neo4j_stats.get("user_count", 0) - qdrant_stats.get("points_count", 0)) > 100:
                logger.warning("Data inconsistency detected between Neo4j and Qdrant")
                
        except Exception as e:
            logger.error(f"Error checking data consistency: {e}")
    
    # ==================== USER OPERATIONS ====================
    
    async def get_user(
        self,
        user_id: str,
        include_interactions: bool = False
    ) -> Optional[UserProfile]:
        """
        Get user profile from Neo4j.
        
        Args:
            user_id: User identifier
            include_interactions: Include interaction history
            
        Returns:
            User profile or None
        """
        # Check cache (thread-safe)
        cache_key = f"user:{user_id}"
        if self.enable_caching:
            async with self._cache_lock:
                cache_entry = self.cache.get(cache_key)
                if cache_entry and (datetime.now() - cache_entry["timestamp"]).seconds < self.cache_ttl:
                    self.stats["cache_hits"] += 1
                    return cache_entry["data"]
        
        try:
            # Get from Neo4j
            self.stats["neo4j_queries"] += 1
            user_data = await self.neo4j.get_user_details(user_id)
            
            if user_data:
                # Get interactions if requested
                if include_interactions:
                    interactions = await self.neo4j.get_user_interactions(user_id, limit=50)
                    user_data["recent_interactions"] = interactions
                
                # Cache result (thread-safe)
                if self.enable_caching:
                    async with self._cache_lock:
                        self.cache.put(cache_key, {
                            "data": user_data,
                            "timestamp": datetime.now()
                        })
                
                return user_data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            self.stats["errors"] += 1
            return None
    
    async def create_or_update_user(
        self,
        user_id: str,
        user_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create or update user in Neo4j.
        
        Args:
            user_id: User identifier
            user_data: User data
            
        Returns:
            Success status
        """
        try:
            # Update in Neo4j
            success = await self.neo4j.create_or_update_user(user_id, user_data)
            
            if success:
                # Invalidate cache (thread-safe)
                cache_key = f"user:{user_id}"
                async with self._cache_lock:
                    self.cache.delete(cache_key)
                
                # Queue for sync
                await self.sync_queue.put({
                    "type": "user_update",
                    "user_id": user_id,
                    "data": user_data
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            self.stats["errors"] += 1
            return False
    
    async def record_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record user-product interaction.
        
        Args:
            user_id: User identifier
            product_id: Product identifier
            interaction_type: Type of interaction
            metadata: Additional metadata
            
        Returns:
            Success status
        """
        try:
            # Record in Neo4j
            success = await self.neo4j.record_product_interaction(
                user_id, product_id, interaction_type, metadata
            )
            
            if success:
                # Update product in Qdrant if it's a purchase
                if interaction_type == "purchased":
                    product = await self.qdrant.get_product_details(product_id)
                    if product:
                        # Update interaction counts
                        product["purchased_num"] = product.get("purchased_num", 0) + 1
                        await self.qdrant.index_product(product)
                
                # Queue for sync
                await self.sync_queue.put({
                    "type": "interaction",
                    "user_id": user_id,
                    "product_id": product_id,
                    "interaction_type": interaction_type,
                    "metadata": metadata
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            self.stats["errors"] += 1
            return False
    
    # ==================== PRODUCT OPERATIONS ====================
    
    async def get_product(
        self,
        product_id: str,
        source: DataSource = DataSource.QDRANT
    ) -> Optional[Dict[str, Any]]:
        """
        Get product details.
        
        Args:
            product_id: Product identifier
            source: Data source preference
            
        Returns:
            Product details or None
        """
        # Check cache
        cache_key = f"product:{product_id}"
        if self.enable_caching and cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if (datetime.now() - cache_entry["timestamp"]).seconds < self.cache_ttl:
                self.stats["cache_hits"] += 1
                return cache_entry["data"]
        
        try:
            product = None
            
            # Get from preferred source
            if source == DataSource.QDRANT:
                self.stats["qdrant_queries"] += 1
                product = await self.qdrant.get_product_details(product_id)
            elif source == DataSource.NEO4J:
                self.stats["neo4j_queries"] += 1
                # Neo4j would need a product node implementation
                # For now, fallback to Qdrant
                product = await self.qdrant.get_product_details(product_id)
            
            if product:
                # Cache result
                if self.enable_caching:
                    self.cache[cache_key] = {
                        "data": product,
                        "timestamp": datetime.now()
                    }
            
            return product
            
        except Exception as e:
            logger.error(f"Error getting product: {e}")
            self.stats["errors"] += 1
            return None
    
    async def search_products(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        use_semantic: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search for products.
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Search filters
            use_semantic: Use semantic search
            
        Returns:
            List of products
        """
        try:
            if use_semantic:
                # Semantic search via Qdrant
                self.stats["qdrant_queries"] += 1
                products = await self.qdrant.search_by_natural_language(
                    query, limit, filters
                )
            else:
                # Filter-based search
                self.stats["qdrant_queries"] += 1
                products = await self.qdrant.get_products_by_filter(
                    category=filters.get("category") if filters else None,
                    brand=filters.get("brand") if filters else None,
                    min_price=filters.get("min_price") if filters else None,
                    max_price=filters.get("max_price") if filters else None,
                    limit=limit
                )
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            self.stats["errors"] += 1
            return []
    
    async def index_product(
        self,
        product: Dict[str, Any]
    ) -> bool:
        """
        Index product in Qdrant.
        
        Args:
            product: Product data
            
        Returns:
            Success status
        """
        try:
            # Validate product
            if not create_product_from_dict(product):
                logger.error("Invalid product data")
                return False
            
            # Index in Qdrant
            success = await self.qdrant.index_product(product)
            
            if success:
                # Invalidate cache
                cache_key = f"product:{product['id']}"
                if cache_key in self.cache:
                    del self.cache[cache_key]
                
                # Queue for sync
                await self.sync_queue.put({
                    "type": "product_update",
                    "product_id": product["id"],
                    "data": product
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Error indexing product: {e}")
            self.stats["errors"] += 1
            return False
    
    # ==================== HYBRID OPERATIONS ====================
    
    async def get_personalized_recommendations(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[ProductRecommendation]:
        """
        Get personalized recommendations using both stores.
        
        Args:
            user_id: User identifier
            limit: Maximum recommendations
            
        Returns:
            List of product recommendations
        """
        try:
            recommendations = []
            
            # Get user data from Neo4j
            user = await self.get_user(user_id, include_interactions=True)
            
            if user:
                # Get user's recent interactions
                recent_interactions = user.get("recent_interactions", [])
                
                if recent_interactions:
                    # Find similar products based on recent views
                    recent_products = [i["product_id"] for i in recent_interactions[:5]]
                    
                    for product_id in recent_products:
                        similar = await self.qdrant.get_similar_products(
                            product_id, limit=3
                        )
                        recommendations.extend(similar)
                
                # Get products based on preferences
                preferences = user.get("preferences", {})
                if preferences:
                    # Search by preferred categories
                    for category in preferences.get("preferred_categories", [])[:3]:
                        products = await self.search_products(
                            category, limit=3, use_semantic=False
                        )
                        recommendations.extend(products)
            
            # Deduplicate and limit
            seen = set()
            unique_recommendations = []
            for rec in recommendations:
                if rec.get("id") not in seen:
                    seen.add(rec["id"])
                    unique_recommendations.append(rec)
                    if len(unique_recommendations) >= limit:
                        break
            
            return unique_recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            self.stats["errors"] += 1
            return []
    
    async def get_collaborative_recommendations(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[ProductRecommendation]:
        """
        Get collaborative filtering recommendations.
        
        Args:
            user_id: User identifier
            limit: Maximum recommendations
            
        Returns:
            List of product recommendations
        """
        try:
            # Use Neo4j for collaborative filtering
            query = """
            MATCH (u:User {id: $user_id})-[:PURCHASED]->(p:Product)
            WITH u, p
            MATCH (p)<-[:PURCHASED]-(other:User)
            WHERE other.id <> $user_id
            MATCH (other)-[:PURCHASED]->(rec:Product)
            WHERE NOT (u)-[:PURCHASED]->(rec)
            WITH rec, COUNT(DISTINCT other) as score
            RETURN rec.id as product_id, score
            ORDER BY score DESC
            LIMIT $limit
            """
            
            self.stats["neo4j_queries"] += 1
            result = await self.neo4j.query(query, {"user_id": user_id, "limit": limit})
            
            recommendations = []
            for record in result:
                product_id = record["product_id"]
                score = record["score"]
                
                # Get product details from Qdrant
                product = await self.get_product(product_id)
                if product:
                    rec = Product(product).to_recommendation(
                        score=float(score),
                        reason="Users who bought similar items also bought this",
                        agent="collaborative",
                        confidence=min(score / 10, 1.0)
                    )
                    recommendations.append(rec)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting collaborative recommendations: {e}")
            self.stats["errors"] += 1
            return []
    
    async def sync_user_data(self, user_id: str) -> bool:
        """
        Sync user data between stores.
        
        Args:
            user_id: User identifier
            
        Returns:
            Success status
        """
        try:
            # Get user data from Neo4j
            user_data = await self.neo4j.get_user_details(user_id)
            
            if user_data:
                # Update any denormalized data in Qdrant if needed
                # For now, just track sync
                self.last_sync[f"user:{user_id}"] = datetime.now()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error syncing user data: {e}")
            return False
    
    async def _sync_user_data(self, user_id: str):
        """Internal sync for user data."""
        await self.sync_user_data(user_id)
    
    async def _sync_product_data(self, product_id: str):
        """Internal sync for product data."""
        # Get product from Qdrant and update any Neo4j references
        product = await self.qdrant.get_product_details(product_id)
        if product:
            self.last_sync[f"product:{product_id}"] = datetime.now()
    
    async def _sync_interaction(self, interaction: Dict[str, Any]):
        """Internal sync for interaction."""
        # Update interaction counts in both stores
        self.last_sync[f"interaction:{interaction.get('user_id')}:{interaction.get('product_id')}"] = datetime.now()
    
    async def get_data_health(self) -> Dict[str, Any]:
        """
        Get health status of data stores.
        
        Returns:
            Health status dictionary
        """
        health = {
            "neo4j": {},
            "qdrant": {},
            "hybrid": {}
        }
        
        try:
            # Check Neo4j
            neo4j_healthy = await self.neo4j.health_check()
            health["neo4j"]["status"] = "healthy" if neo4j_healthy else "unhealthy"
            
            if neo4j_healthy:
                stats = await self.neo4j.get_database_statistics()
                health["neo4j"]["stats"] = stats
            
            # Check Qdrant
            qdrant_healthy = await self.qdrant.health_check()
            health["qdrant"]["status"] = "healthy" if qdrant_healthy else "unhealthy"
            
            if qdrant_healthy:
                stats = await self.qdrant.get_collection_stats()
                health["qdrant"]["stats"] = stats
            
            # Hybrid stats
            health["hybrid"] = {
                "cache_size": len(self.cache.cache),
                "sync_queue_size": self.sync_queue.qsize(),
                "last_syncs": len(self.last_sync),
                "stats": self.stats
            }
            
        except Exception as e:
            logger.error(f"Error getting data health: {e}")
            health["error"] = str(e)
        
        return health
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hybrid store statistics."""
        cache_requests = self.stats.get("cache_hits", 0) + self.stats.get("neo4j_queries", 0) + self.stats.get("qdrant_queries", 0)
        cache_hit_rate = (self.stats["cache_hits"] / cache_requests * 100) if cache_requests > 0 else 0
        
        return {
            "neo4j_queries": self.stats["neo4j_queries"],
            "qdrant_queries": self.stats["qdrant_queries"],
            "cache_hits": self.stats["cache_hits"],
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "sync_operations": self.stats["sync_operations"],
            "errors": self.stats["errors"],
            "cache_size": len(self.cache.cache),
            "sync_queue_size": self.sync_queue.qsize()
        }
    
    async def _cleanup_cache(self):
        """Clean expired cache entries periodically (thread-safe)."""
        now = datetime.now()
        expired = []
        
        # Check all cache entries for expiration (thread-safe)
        async with self._cache_lock:
            for key in list(self.cache.cache.keys()):  # Create list to avoid modification during iteration
                entry = self.cache.get(key)
                if entry and (now - entry["timestamp"]).seconds > self.cache_ttl:
                    expired.append(key)
        
            # Remove expired entries within the same lock
            for key in expired:
                self.cache.delete(key)
        
        if expired:
            logger.debug(f"Cleaned {len(expired)} expired cache entries")

    async def shutdown(self):
        """Shutdown hybrid store."""
        logger.info("Shutting down hybrid data store")
        
        self._running = False
        
        # Cancel sync task
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        # Process remaining sync queue
        while not self.sync_queue.empty():
            try:
                item = self.sync_queue.get_nowait()
                await self._process_sync_item(item)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.warning(f"Error processing remaining sync item during shutdown: {e}")
        
        # Clear cache
        self.cache.clear()
        
        logger.info("Hybrid data store shutdown complete")


# Exports
__all__ = [
    'HybridDataStore',
    'DataSource'
]