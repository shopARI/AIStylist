"""
Hybrid Data Store for AI Stylist
Routes queries to appropriate backend based on data type
- Products: Qdrant only
- Users: Neo4j + Qdrant hybrid
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime
import json

logger = logging.getLogger("hybrid_data_store")


class HybridDataStore:
    """
    Intelligent routing layer that directs queries to the appropriate backend.
    Products go to Qdrant only, Users use hybrid Neo4j + Qdrant approach.
    """
    
    def __init__(self, neo4j_client=None, qdrant_client=None):
        """
        Initialize the hybrid data store.
        
        Args:
            neo4j_client: UserKnowledgeGraphAsync instance (for users only)
            qdrant_client: ProductRetrieverAsync instance (for products and user vectors)
        """
        self.neo4j = neo4j_client
        self.qdrant = qdrant_client
        
        # Performance tracking
        self.query_stats = {
            "product_queries": 0,
            "user_queries": 0,
            "neo4j_calls": 0,
            "qdrant_calls": 0,
            "errors": 0,
            "avg_response_time": {
                "products": 0.0,
                "users": 0.0
            }
        }
        
        # Cache for frequently accessed data
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
        logger.info("HybridDataStore initialized with Neo4j and Qdrant clients")
    
    # ==================== PRODUCT OPERATIONS (Qdrant Only) ====================
    
    async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product details from Qdrant only.
        
        Args:
            product_id: Product identifier
            
        Returns:
            Product details or None if not found
        """
        if not self.qdrant:
            logger.error("Qdrant client not available for product operations")
            return None
            
        try:
            self.query_stats["product_queries"] += 1
            self.query_stats["qdrant_calls"] += 1
            
            # Check cache first
            cache_key = f"product:{product_id}"
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if (datetime.now() - timestamp).seconds < self._cache_ttl:
                    return cached_data
            
            # Fetch from Qdrant
            start_time = datetime.now()
            product = await self.qdrant.get_product_details(product_id)
            
            # Update stats
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_avg_response_time("products", response_time)
            
            # Cache the result
            if product:
                self._cache[cache_key] = (product, datetime.now())
            
            return product
            
        except Exception as e:
            logger.error(f"Error fetching product {product_id}: {e}")
            self.query_stats["errors"] += 1
            return None
    
    async def search_products(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search products using Qdrant vector search and metadata filtering.
        
        Args:
            query: Natural language search query
            filters: Metadata filters (price, category, etc.)
            limit: Maximum number of results
            
        Returns:
            List of matching products
        """
        if not self.qdrant:
            logger.error("Qdrant client not available for product search")
            return []
            
        try:
            self.query_stats["product_queries"] += 1
            self.query_stats["qdrant_calls"] += 1
            
            start_time = datetime.now()
            
            # Perform vector search with filters
            if query:
                results = await self.qdrant.search_by_natural_language(
                    query=query,
                    limit=limit,
                    filters=filters  # Pass filters as a parameter, not unpacked
                )
            else:
                # Pure filter-based search - unpack filters as keyword arguments
                if filters:
                    results = await self.qdrant.get_products_by_filter(
                        **filters,  # Unpack here for filter-based search
                        limit=limit
                    )
                else:
                    results = await self.qdrant.get_products_by_filter(limit=limit)
            
            # Update stats
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_avg_response_time("products", response_time)
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching products: {e}")
            self.query_stats["errors"] += 1
            return []
    
    async def get_similar_products(
        self,
        product_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get similar products using Qdrant vector similarity.
        
        Args:
            product_id: Reference product ID
            limit: Maximum number of similar products
            
        Returns:
            List of similar products
        """
        if not self.qdrant:
            logger.error("Qdrant client not available for similarity search")
            return []
            
        try:
            self.query_stats["product_queries"] += 1
            self.query_stats["qdrant_calls"] += 1
            
            start_time = datetime.now()
            similar = await self.qdrant.get_similar_products(product_id, limit)
            
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_avg_response_time("products", response_time)
            
            return similar
            
        except Exception as e:
            logger.error(f"Error finding similar products: {e}")
            self.query_stats["errors"] += 1
            return []
    
    async def get_popular_products(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get popular products based on popularity score in Qdrant.
        
        Args:
            limit: Maximum number of products
            
        Returns:
            List of popular products
        """
        if not self.qdrant:
            return []
            
        try:
            # Just call the qdrant method directly
            return await self.qdrant.get_popular_products(limit)
        except Exception as e:
            logger.error(f"Error getting popular products: {e}")
            return []
    
    # ==================== USER OPERATIONS (Neo4j + Qdrant Hybrid) ====================
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user data using hybrid approach.
        Neo4j for core data, Qdrant for preference vectors.
        
        Args:
            user_id: User identifier
            
        Returns:
            Merged user data or None if not found
        """
        if not self.neo4j:
            logger.error("Neo4j client not available for user operations")
            return None
            
        try:
            self.query_stats["user_queries"] += 1
            
            # Check cache
            cache_key = f"user:{user_id}"
            if cache_key in self._cache:
                cached_data, timestamp = self._cache[cache_key]
                if (datetime.now() - timestamp).seconds < self._cache_ttl:
                    return cached_data
            
            start_time = datetime.now()
            
            # Fetch from both sources in parallel
            neo4j_task = self._get_user_from_neo4j(user_id)
            qdrant_task = self._get_user_vector_from_qdrant(user_id)
            
            neo4j_data, vector_data = await asyncio.gather(
                neo4j_task,
                qdrant_task,
                return_exceptions=True
            )
            
            # Handle errors
            if isinstance(neo4j_data, Exception):
                logger.error(f"Neo4j error for user {user_id}: {neo4j_data}")
                neo4j_data = None
            
            if isinstance(vector_data, Exception):
                logger.warning(f"Qdrant error for user {user_id}: {vector_data}")
                vector_data = None
            
            # Neo4j is source of truth
            if not neo4j_data:
                return None
            
            # Merge data
            merged_data = self._merge_user_data(neo4j_data, vector_data)
            
            # Update stats
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_avg_response_time("users", response_time)
            
            # Cache result
            self._cache[cache_key] = (merged_data, datetime.now())
            
            return merged_data
            
        except Exception as e:
            logger.error(f"Error fetching user {user_id}: {e}")
            self.query_stats["errors"] += 1
            return None
    
    async def get_user_interactions(
        self,
        user_id: str,
        interaction_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get user interactions from Neo4j (source of truth for relationships).
        
        Args:
            user_id: User identifier
            interaction_type: Filter by type (viewed, liked, purchased)
            limit: Maximum number of interactions
            
        Returns:
            List of user interactions
        """
        if not self.neo4j:
            logger.error("Neo4j client not available for interaction queries")
            return []
            
        try:
            self.query_stats["user_queries"] += 1
            self.query_stats["neo4j_calls"] += 1
            
            return await self.neo4j.get_user_interactions(
                user_id=user_id,
                interaction_type=interaction_type,
                limit=limit
            )
            
        except Exception as e:
            logger.error(f"Error fetching user interactions: {e}")
            self.query_stats["errors"] += 1
            return []
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences from Neo4j with vector enhancement from Qdrant.
        
        Args:
            user_id: User identifier
            
        Returns:
            User preferences dictionary
        """
        if not self.neo4j:
            return {}
            
        try:
            # Get structured preferences from Neo4j
            neo4j_prefs = await self.neo4j.get_user_preferences(user_id)
            
            # Get vector-based preferences from Qdrant if available
            if self.qdrant:
                vector_prefs = await self._get_user_vector_preferences(user_id)
                
                # Merge preferences
                if vector_prefs:
                    neo4j_prefs["vector_preferences"] = vector_prefs
            
            return neo4j_prefs
            
        except Exception as e:
            logger.error(f"Error fetching user preferences: {e}")
            return {}
    
    async def create_or_update_user(
        self,
        user_id: str,
        user_data: Dict[str, Any]
    ) -> bool:
        """
        Create or update user in both Neo4j and Qdrant.
        
        Args:
            user_id: User identifier
            user_data: User data to store
            
        Returns:
            True if successful
        """
        try:
            # Update Neo4j (primary storage)
            if self.neo4j:
                neo4j_success = await self.neo4j.create_or_update_user(
                    user_id, user_data
                )
                if not neo4j_success:
                    return False
            
            # Update Qdrant vectors if preference data exists
            if self.qdrant and "preferences" in user_data:
                await self._update_user_vectors(user_id, user_data["preferences"])
            
            # Clear cache
            cache_key = f"user:{user_id}"
            self._cache.pop(cache_key, None)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating/updating user {user_id}: {e}")
            return False
    
    async def record_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record user-product interaction in Neo4j and update vectors.
        
        Args:
            user_id: User identifier
            product_id: Product identifier
            interaction_type: Type of interaction
            metadata: Additional interaction data
            
        Returns:
            True if successful
        """
        try:
            # Record in Neo4j (relationship graph)
            if self.neo4j:
                success = await self.neo4j.record_product_interaction(
                    user_id=user_id,
                    product_id=product_id,
                    interaction_type=interaction_type,
                    metadata=metadata
                )
                
                if not success:
                    return False
            
            # Update user vectors based on interaction
            if self.qdrant:
                await self._update_user_vectors_from_interaction(
                    user_id, product_id, interaction_type
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            return False
    
    # ==================== HYBRID OPERATIONS ====================
    
    async def get_recommendations_for_user(
        self,
        user_id: str,
        query: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations using hybrid approach.
        
        Args:
            user_id: User identifier
            query: Optional search query
            limit: Maximum recommendations
            
        Returns:
            List of recommended products
        """
        try:
            # Get user data and preferences
            user_data = await self.get_user(user_id)
            if not user_data:
                # Fallback to general search
                return await self.search_products(query=query, limit=limit)
            
            # Get user's interaction history from Neo4j
            interactions = await self.get_user_interactions(
                user_id, limit=50
            )
            
            # Extract interacted product IDs
            interacted_products = {
                i["product_id"] for i in interactions
                if "product_id" in i
            }
            
            # Build search filters based on preferences
            filters = self._build_preference_filters(user_data)
            
            # Search with personalization
            results = await self.search_products(
                query=query,
                filters=filters,
                limit=limit * 2  # Get more to filter out seen items
            )
            
            # Filter out already interacted products
            recommendations = [
                p for p in results
                if p.get("id") not in interacted_products
            ][:limit]
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []
    
    # ==================== PRIVATE HELPER METHODS ====================
    
    async def _get_user_from_neo4j(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user data from Neo4j."""
        try:
            self.query_stats["neo4j_calls"] += 1
            return await self.neo4j.get_user_details(user_id)
        except Exception as e:
            logger.error(f"Neo4j user fetch error: {e}")
            raise
    
    async def _get_user_vector_from_qdrant(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user preference vector from Qdrant."""
        try:
            self.query_stats["qdrant_calls"] += 1
            # This method needs to be implemented in ProductRetrieverAsync
            # For now, return None
            return None
        except Exception as e:
            logger.warning(f"Qdrant user vector fetch error: {e}")
            return None
    
    def _merge_user_data(
        self,
        neo4j_data: Dict[str, Any],
        vector_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge user data from Neo4j and Qdrant."""
        if not neo4j_data:
            return {}
        
        merged = neo4j_data.copy()
        
        if vector_data:
            merged["preference_vector"] = vector_data.get("vector")
            merged["vector_metadata"] = vector_data.get("metadata", {})
        
        return merged
    
    async def _get_user_vector_preferences(self, user_id: str) -> Dict[str, Any]:
        """Extract preferences from user's vector representation."""
        try:
            vector_data = await self._get_user_vector_from_qdrant(user_id)
            if not vector_data:
                return {}
            
            # Extract semantic preferences from metadata
            metadata = vector_data.get("metadata", {})
            return {
                "style_preferences": metadata.get("styles", []),
                "color_preferences": metadata.get("colors", []),
                "brand_affinity": metadata.get("brands", []),
                "price_sensitivity": metadata.get("price_range", {})
            }
        except Exception as e:
            logger.error(f"Error getting vector preferences: {e}")
            return {}
    
    async def _update_user_vectors(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ):
        """Update user preference vectors in Qdrant."""
        # This would need implementation in ProductRetrieverAsync
        # For now, just log
        logger.info(f"Would update user vectors for {user_id}")
    
    async def _update_user_vectors_from_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str
    ):
        """Update user vectors based on product interaction."""
        try:
            # Get product details
            product = await self.get_product(product_id)
            if not product:
                return
            
            # Weight based on interaction type
            weight = {
                "viewed": 0.3,
                "liked": 0.6,
                "purchased": 1.0
            }.get(interaction_type, 0.5)
            
            # This would need implementation
            logger.info(f"Would update user vector for {user_id} based on {product_id} interaction")
            
        except Exception as e:
            logger.error(f"Error updating user vector from interaction: {e}")
    
    def _build_preference_filters(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Build Qdrant filters from user preferences."""
        filters = {}
        preferences = user_data.get("preferences", {})
        
        # Category preferences
        if preferences.get("preferred_categories"):
            filters["category"] = preferences["preferred_categories"][0]  # Single category for now
        
        # Price range
        if preferences.get("budget_range"):
            budget = preferences["budget_range"]
            if budget.get("min"):
                filters["min_price"] = budget["min"]
            if budget.get("max"):
                filters["max_price"] = budget["max"]
        
        # Brand preferences
        if preferences.get("preferred_brands"):
            filters["brand"] = preferences["preferred_brands"][0]  # Single brand for now
        
        # Color preferences
        if preferences.get("preferred_colors"):
            filters["colors"] = preferences["preferred_colors"]
        
        return filters
    
    def _update_avg_response_time(self, category: str, new_time: float):
        """Update average response time statistics."""
        current_avg = self.query_stats["avg_response_time"][category]
        count = self.query_stats[f"{category}_queries"]
        
        # Calculate new average
        if count > 0:
            new_avg = ((current_avg * (count - 1)) + new_time) / count
            self.query_stats["avg_response_time"][category] = new_avg
    
    # ==================== STATISTICS AND MONITORING ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return self.query_stats.copy()
    
    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()
        logger.info("Cache cleared")

# """
# Hybrid Data Store for AI Stylist
# Routes queries to appropriate backend based on data type
# - Products: Qdrant only
# - Users: Neo4j + Qdrant hybrid
# """

# import logging
# import asyncio
# from typing import Dict, List, Any, Optional, Tuple, Set
# from datetime import datetime
# import json

# logger = logging.getLogger("hybrid_data_store")


# class HybridDataStore:
#     """
#     Intelligent routing layer that directs queries to the appropriate backend.
#     Products go to Qdrant only, Users use hybrid Neo4j + Qdrant approach.
#     """
    
#     def __init__(self, neo4j_client=None, qdrant_client=None):
#         """
#         Initialize the hybrid data store.
        
#         Args:
#             neo4j_client: UserKnowledgeGraphAsync instance (for users only)
#             qdrant_client: ProductRetrieverAsync instance (for products and user vectors)
#         """
#         self.neo4j = neo4j_client
#         self.qdrant = qdrant_client
        
#         # Performance tracking
#         self.query_stats = {
#             "product_queries": 0,
#             "user_queries": 0,
#             "neo4j_calls": 0,
#             "qdrant_calls": 0,
#             "errors": 0,
#             "avg_response_time": {
#                 "products": 0.0,
#                 "users": 0.0
#             }
#         }
        
#         # Cache for frequently accessed data
#         self._cache = {}
#         self._cache_ttl = 300  # 5 minutes
        
#         logger.info("HybridDataStore initialized with Neo4j and Qdrant clients")
    
#     # ==================== PRODUCT OPERATIONS (Qdrant Only) ====================
    
#     async def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
#         """
#         Get product details from Qdrant only.
        
#         Args:
#             product_id: Product identifier
            
#         Returns:
#             Product details or None if not found
#         """
#         if not self.qdrant:
#             logger.error("Qdrant client not available for product operations")
#             return None
            
#         try:
#             self.query_stats["product_queries"] += 1
#             self.query_stats["qdrant_calls"] += 1
            
#             # Check cache first
#             cache_key = f"product:{product_id}"
#             if cache_key in self._cache:
#                 cached_data, timestamp = self._cache[cache_key]
#                 if (datetime.now() - timestamp).seconds < self._cache_ttl:
#                     return cached_data
            
#             # Fetch from Qdrant
#             start_time = datetime.now()
#             product = await self.qdrant.get_product_details(product_id)
            
#             # Update stats
#             response_time = (datetime.now() - start_time).total_seconds()
#             self._update_avg_response_time("products", response_time)
            
#             # Cache the result
#             if product:
#                 self._cache[cache_key] = (product, datetime.now())
            
#             return product
            
#         except Exception as e:
#             logger.error(f"Error fetching product {product_id}: {e}")
#             self.query_stats["errors"] += 1
#             return None
    
#     async def search_products(
#         self,
#         query: Optional[str] = None,
#         filters: Optional[Dict[str, Any]] = None,
#         limit: int = 10
#     ) -> List[Dict[str, Any]]:
#         """
#         Search products using Qdrant vector search and metadata filtering.
        
#         Args:
#             query: Natural language search query
#             filters: Metadata filters (price, category, etc.)
#             limit: Maximum number of results
            
#         Returns:
#             List of matching products
#         """
#         if not self.qdrant:
#             logger.error("Qdrant client not available for product search")
#             return []
            
#         try:
#             self.query_stats["product_queries"] += 1
#             self.query_stats["qdrant_calls"] += 1
            
#             start_time = datetime.now()
            
#             # Perform vector search with filters
#             if query:
#                 results = await self.qdrant.search_by_natural_language(
#                     query=query,
#                     limit=limit,
#                     **filters
#                 )
#             else:
#                 # Pure filter-based search
#                 results = await self.qdrant.get_products_by_filter(
#                     **filters,
#                     limit=limit
#                 )
            
#             # Update stats
#             response_time = (datetime.now() - start_time).total_seconds()
#             self._update_avg_response_time("products", response_time)
            
#             return results
            
#         except Exception as e:
#             logger.error(f"Error searching products: {e}")
#             self.query_stats["errors"] += 1
#             return []
    
#     async def get_similar_products(
#         self,
#         product_id: str,
#         limit: int = 5
#     ) -> List[Dict[str, Any]]:
#         """
#         Get similar products using Qdrant vector similarity.
        
#         Args:
#             product_id: Reference product ID
#             limit: Maximum number of similar products
            
#         Returns:
#             List of similar products
#         """
#         if not self.qdrant:
#             logger.error("Qdrant client not available for similarity search")
#             return []
            
#         try:
#             self.query_stats["product_queries"] += 1
#             self.query_stats["qdrant_calls"] += 1
            
#             start_time = datetime.now()
#             similar = await self.qdrant.search_similar_products(product_id, limit)
            
#             response_time = (datetime.now() - start_time).total_seconds()
#             self._update_avg_response_time("products", response_time)
            
#             return similar
            
#         except Exception as e:
#             logger.error(f"Error finding similar products: {e}")
#             self.query_stats["errors"] += 1
#             return []
    
#     async def get_popular_products(self, limit: int = 10) -> List[Dict[str, Any]]:
#         """
#         Get popular products based on popularity score in Qdrant.
        
#         Args:
#             limit: Maximum number of products
            
#         Returns:
#             List of popular products
#         """
#         return await self.search_products(
#             filters={"popularity_score": {"$gte": 0.7}},
#             limit=limit
#         )
    
#     # ==================== USER OPERATIONS (Neo4j + Qdrant Hybrid) ====================
    
#     async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
#         """
#         Get user data using hybrid approach.
#         Neo4j for core data, Qdrant for preference vectors.
        
#         Args:
#             user_id: User identifier
            
#         Returns:
#             Merged user data or None if not found
#         """
#         if not self.neo4j:
#             logger.error("Neo4j client not available for user operations")
#             return None
            
#         try:
#             self.query_stats["user_queries"] += 1
            
#             # Check cache
#             cache_key = f"user:{user_id}"
#             if cache_key in self._cache:
#                 cached_data, timestamp = self._cache[cache_key]
#                 if (datetime.now() - timestamp).seconds < self._cache_ttl:
#                     return cached_data
            
#             start_time = datetime.now()
            
#             # Fetch from both sources in parallel
#             neo4j_task = self._get_user_from_neo4j(user_id)
#             qdrant_task = self._get_user_vector_from_qdrant(user_id)
            
#             neo4j_data, vector_data = await asyncio.gather(
#                 neo4j_task,
#                 qdrant_task,
#                 return_exceptions=True
#             )
            
#             # Handle errors
#             if isinstance(neo4j_data, Exception):
#                 logger.error(f"Neo4j error for user {user_id}: {neo4j_data}")
#                 neo4j_data = None
            
#             if isinstance(vector_data, Exception):
#                 logger.warning(f"Qdrant error for user {user_id}: {vector_data}")
#                 vector_data = None
            
#             # Neo4j is source of truth
#             if not neo4j_data:
#                 return None
            
#             # Merge data
#             merged_data = self._merge_user_data(neo4j_data, vector_data)
            
#             # Update stats
#             response_time = (datetime.now() - start_time).total_seconds()
#             self._update_avg_response_time("users", response_time)
            
#             # Cache result
#             self._cache[cache_key] = (merged_data, datetime.now())
            
#             return merged_data
            
#         except Exception as e:
#             logger.error(f"Error fetching user {user_id}: {e}")
#             self.query_stats["errors"] += 1
#             return None
    
#     async def get_user_interactions(
#         self,
#         user_id: str,
#         interaction_type: Optional[str] = None,
#         limit: int = 100
#     ) -> List[Dict[str, Any]]:
#         """
#         Get user interactions from Neo4j (source of truth for relationships).
        
#         Args:
#             user_id: User identifier
#             interaction_type: Filter by type (viewed, liked, purchased)
#             limit: Maximum number of interactions
            
#         Returns:
#             List of user interactions
#         """
#         if not self.neo4j:
#             logger.error("Neo4j client not available for interaction queries")
#             return []
            
#         try:
#             self.query_stats["user_queries"] += 1
#             self.query_stats["neo4j_calls"] += 1
            
#             return await self.neo4j.get_user_interactions(
#                 user_id=user_id,
#                 interaction_type=interaction_type,
#                 limit=limit
#             )
            
#         except Exception as e:
#             logger.error(f"Error fetching user interactions: {e}")
#             self.query_stats["errors"] += 1
#             return []
    
#     async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
#         """
#         Get user preferences from Neo4j with vector enhancement from Qdrant.
        
#         Args:
#             user_id: User identifier
            
#         Returns:
#             User preferences dictionary
#         """
#         if not self.neo4j:
#             return {}
            
#         try:
#             # Get structured preferences from Neo4j
#             neo4j_prefs = await self.neo4j.get_user_preferences(user_id)
            
#             # Get vector-based preferences from Qdrant if available
#             if self.qdrant:
#                 vector_prefs = await self._get_user_vector_preferences(user_id)
                
#                 # Merge preferences
#                 if vector_prefs:
#                     neo4j_prefs["vector_preferences"] = vector_prefs
            
#             return neo4j_prefs
            
#         except Exception as e:
#             logger.error(f"Error fetching user preferences: {e}")
#             return {}
    
#     async def create_or_update_user(
#         self,
#         user_id: str,
#         user_data: Dict[str, Any]
#     ) -> bool:
#         """
#         Create or update user in both Neo4j and Qdrant.
        
#         Args:
#             user_id: User identifier
#             user_data: User data to store
            
#         Returns:
#             True if successful
#         """
#         try:
#             # Update Neo4j (primary storage)
#             if self.neo4j:
#                 neo4j_success = await self.neo4j.create_or_update_user(
#                     user_id, user_data
#                 )
#                 if not neo4j_success:
#                     return False
            
#             # Update Qdrant vectors if preference data exists
#             if self.qdrant and "preferences" in user_data:
#                 await self._update_user_vectors(user_id, user_data["preferences"])
            
#             # Clear cache
#             cache_key = f"user:{user_id}"
#             self._cache.pop(cache_key, None)
            
#             return True
            
#         except Exception as e:
#             logger.error(f"Error creating/updating user {user_id}: {e}")
#             return False
    
#     async def record_interaction(
#         self,
#         user_id: str,
#         product_id: str,
#         interaction_type: str,
#         metadata: Optional[Dict[str, Any]] = None
#     ) -> bool:
#         """
#         Record user-product interaction in Neo4j and update vectors.
        
#         Args:
#             user_id: User identifier
#             product_id: Product identifier
#             interaction_type: Type of interaction
#             metadata: Additional interaction data
            
#         Returns:
#             True if successful
#         """
#         try:
#             # Record in Neo4j (relationship graph)
#             if self.neo4j:
#                 success = await self.neo4j.record_product_interaction(
#                     user_id=user_id,
#                     product_id=product_id,
#                     interaction_type=interaction_type,
#                     metadata=metadata
#                 )
                
#                 if not success:
#                     return False
            
#             # Update user vectors based on interaction
#             if self.qdrant:
#                 await self._update_user_vectors_from_interaction(
#                     user_id, product_id, interaction_type
#                 )
            
#             return True
            
#         except Exception as e:
#             logger.error(f"Error recording interaction: {e}")
#             return False
    
#     # ==================== HYBRID OPERATIONS ====================
    
#     async def get_recommendations_for_user(
#         self,
#         user_id: str,
#         query: Optional[str] = None,
#         limit: int = 10
#     ) -> List[Dict[str, Any]]:
#         """
#         Get personalized recommendations using hybrid approach.
        
#         Args:
#             user_id: User identifier
#             query: Optional search query
#             limit: Maximum recommendations
            
#         Returns:
#             List of recommended products
#         """
#         try:
#             # Get user data and preferences
#             user_data = await self.get_user(user_id)
#             if not user_data:
#                 # Fallback to general search
#                 return await self.search_products(query=query, limit=limit)
            
#             # Get user's interaction history from Neo4j
#             interactions = await self.get_user_interactions(
#                 user_id, limit=50
#             )
            
#             # Extract interacted product IDs
#             interacted_products = {
#                 i["product_id"] for i in interactions
#                 if "product_id" in i
#             }
            
#             # Build search filters based on preferences
#             filters = self._build_preference_filters(user_data)
            
#             # Search with personalization
#             results = await self.search_products(
#                 query=query,
#                 **filters,
#                 limit=limit * 2  # Get more to filter out seen items
#             )
            
#             # Filter out already interacted products
#             recommendations = [
#                 p for p in results
#                 if p.get("id") not in interacted_products
#             ][:limit]
            
#             return recommendations
            
#         except Exception as e:
#             logger.error(f"Error getting recommendations: {e}")
#             return []
    
#     # ==================== PRIVATE HELPER METHODS ====================
    
#     async def _get_user_from_neo4j(self, user_id: str) -> Optional[Dict[str, Any]]:
#         """Get user data from Neo4j."""
#         try:
#             self.query_stats["neo4j_calls"] += 1
#             return await self.neo4j.get_user_details(user_id)
#         except Exception as e:
#             logger.error(f"Neo4j user fetch error: {e}")
#             raise
    
#     async def _get_user_vector_from_qdrant(self, user_id: str) -> Optional[Dict[str, Any]]:
#         """Get user preference vector from Qdrant."""
#         try:
#             self.query_stats["qdrant_calls"] += 1
#             # This method needs to be implemented in ProductRetrieverAsync
#             return await self.qdrant.get_user_vector(user_id)
#         except Exception as e:
#             logger.warning(f"Qdrant user vector fetch error: {e}")
#             return None
    
#     def _merge_user_data(
#         self,
#         neo4j_data: Dict[str, Any],
#         vector_data: Optional[Dict[str, Any]]
#     ) -> Dict[str, Any]:
#         """Merge user data from Neo4j and Qdrant."""
#         if not neo4j_data:
#             return {}
        
#         merged = neo4j_data.copy()
        
#         if vector_data:
#             merged["preference_vector"] = vector_data.get("vector")
#             merged["vector_metadata"] = vector_data.get("metadata", {})
        
#         return merged
    
#     async def _get_user_vector_preferences(self, user_id: str) -> Dict[str, Any]:
#         """Extract preferences from user's vector representation."""
#         try:
#             vector_data = await self._get_user_vector_from_qdrant(user_id)
#             if not vector_data:
#                 return {}
            
#             # Extract semantic preferences from metadata
#             metadata = vector_data.get("metadata", {})
#             return {
#                 "style_preferences": metadata.get("styles", []),
#                 "color_preferences": metadata.get("colors", []),
#                 "brand_affinity": metadata.get("brands", []),
#                 "price_sensitivity": metadata.get("price_range", {})
#             }
#         except Exception as e:
#             logger.error(f"Error getting vector preferences: {e}")
#             return {}
    
#     async def _update_user_vectors(
#         self,
#         user_id: str,
#         preferences: Dict[str, Any]
#     ):
#         """Update user preference vectors in Qdrant."""
#         try:
#             # This needs implementation in ProductRetrieverAsync
#             await self.qdrant.update_user_vector(user_id, preferences)
#         except Exception as e:
#             logger.error(f"Error updating user vectors: {e}")
    
#     async def _update_user_vectors_from_interaction(
#         self,
#         user_id: str,
#         product_id: str,
#         interaction_type: str
#     ):
#         """Update user vectors based on product interaction."""
#         try:
#             # Get product details
#             product = await self.get_product(product_id)
#             if not product:
#                 return
            
#             # Weight based on interaction type
#             weight = {
#                 "viewed": 0.3,
#                 "liked": 0.6,
#                 "purchased": 1.0
#             }.get(interaction_type, 0.5)
            
#             # Update user vector (needs implementation)
#             await self.qdrant.update_user_vector_from_product(
#                 user_id, product, weight
#             )
#         except Exception as e:
#             logger.error(f"Error updating user vector from interaction: {e}")
    
#     def _build_preference_filters(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
#         """Build Qdrant filters from user preferences."""
#         filters = {}
#         preferences = user_data.get("preferences", {})
        
#         # Category preferences
#         if preferences.get("preferred_categories"):
#             filters["category"] = {"$in": preferences["preferred_categories"]}
        
#         # Price range
#         if preferences.get("budget_range"):
#             budget = preferences["budget_range"]
#             if budget.get("min"):
#                 filters["price"] = {"$gte": budget["min"]}
#             if budget.get("max"):
#                 filters.setdefault("price", {})["$lte"] = budget["max"]
        
#         # Brand preferences
#         if preferences.get("preferred_brands"):
#             filters["brand"] = {"$in": preferences["preferred_brands"]}
        
#         # Color preferences
#         if preferences.get("preferred_colors"):
#             filters["colors"] = {"$in": preferences["preferred_colors"]}
        
#         return filters
    
#     def _update_avg_response_time(self, category: str, new_time: float):
#         """Update average response time statistics."""
#         current_avg = self.query_stats["avg_response_time"][category]
#         count = self.query_stats[f"{category}_queries"]
        
#         # Calculate new average
#         new_avg = ((current_avg * (count - 1)) + new_time) / count
#         self.query_stats["avg_response_time"][category] = new_avg
    
#     # ==================== STATISTICS AND MONITORING ====================
    
#     def get_stats(self) -> Dict[str, Any]:
#         """Get performance statistics."""
#         return self.query_stats.copy()
    
#     def clear_cache(self):
#         """Clear the internal cache."""
#         self._cache.clear()
#         logger.info("Cache cleared")
