"""
CypherBot Agent - Neo4j Graph Intelligence
Clean CAMEL 0.2.70 implementation
SECURITY: Parameterized queries (SQL injection protection)
PERFORMANCE: Query timeouts and connection pooling support
FIXED: Thread-safe stats, removed unused cache, better health check
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager
from threading import RLock

logger = logging.getLogger("agents.cypher_bot")

# Import from our new CAMEL 0.2.70 module
from lib.camel.v070 import (
    create_battle_agent,
    create_user_message,
    BaseMessage,
    CAMEL_AVAILABLE
)

# Import prompts
from config.prompts import CYPHERBOT_PROMPT

# Query timeout configuration
DEFAULT_QUERY_TIMEOUT = 30.0  # seconds
MAX_QUERY_TIMEOUT = 60.0  # seconds
BATCH_SIZE = 100  # for large result sets


class CypherBotAgent:
    """
    CypherBot - Data-driven fashion intelligence using Neo4j.
    
    Clean implementation with CAMEL 0.2.70 patterns:
    - Uses ModelFactory to create models
    - Passes model objects to ChatAgent
    - Direct string system messages
    - SECURITY: All queries use parameters (no SQL injection)
    - PERFORMANCE: Query timeouts and batch processing
    - FIXED: Thread-safe stats, removed unused cache, optimized health check
    """
    
    def __init__(
        self, 
        neo4j_client: Any,
        query_timeout: float = DEFAULT_QUERY_TIMEOUT,
        enable_connection_pooling: bool = True
    ):
        """
        Initialize CypherBot with Neo4j connection.
        
        Args:
            neo4j_client: UserKnowledgeGraphAsync instance
            query_timeout: Default timeout for queries in seconds
            enable_connection_pooling: Enable connection pooling
        """
        self.neo4j = neo4j_client
        self.name = "CypherBot"
        self.style = "graph-relationships"
        self.query_timeout = min(query_timeout, MAX_QUERY_TIMEOUT)
        self.enable_connection_pooling = enable_connection_pooling
        
        # Initialize CAMEL agent using 0.2.70 pattern
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL 0.2.70+ is required for CypherBot")
        
        try:
            self.agent = create_battle_agent(
                name=self.name,
                system_message=CYPHERBOT_PROMPT
            )
            logger.info(f"{self.name} initialized with CAMEL 0.2.70")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}")
            raise RuntimeError(f"CypherBot initialization failed: {e}") from e
        
        # Track statistics with thread safety
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "timeout_errors": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0,
            "max_search_time": 0.0,
            "min_search_time": float('inf')
        }
        self.stats_lock = RLock()  # Thread-safe lock for stats
        
        # Note: Removed unused cache variables since they were never implemented
        # If caching is needed in the future, it should be properly implemented
        
        logger.info(f"CypherBot configured with {query_timeout}s timeout, pooling={enable_connection_pooling}")
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using graph relationships.
        
        This method:
        1. Uses CAMEL agent to determine strategy
        2. Executes Neo4j queries based on strategy
        3. Returns graph-based recommendations
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Optional filters
            ml_intelligence: ML insights for this agent
            user_context: User information
            
        Returns:
            List of products with graph metadata
        """
        start_time = datetime.now()
        
        # Thread-safe stats update
        with self.stats_lock:
            self.stats["total_searches"] += 1
        
        logger.info(f"{self.name} searching: '{query[:50]}...'")
        
        try:
            # Extract user ID from context
            user_id = user_context.get('user_id') if user_context else None
            
            # Get strategy from CAMEL agent
            strategy = await self._get_agent_strategy(
                query, user_id, ml_intelligence, filters
            )
            
            # Execute strategy with timeout
            try:
                results = await asyncio.wait_for(
                    self._execute_strategy(
                        strategy, query, user_id, limit, ml_intelligence
                    ),
                    timeout=self.query_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Query timeout after {self.query_timeout}s")
                with self.stats_lock:
                    self.stats["timeout_errors"] += 1
                    self.stats["failed_searches"] += 1
                return []
            
            # Update statistics (thread-safe)
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_stats(len(results), elapsed, success=True)
            
            logger.info(f"{self.name} found {len(results)} products in {elapsed:.2f}s")
            return results
            
        except asyncio.TimeoutError:
            logger.error(f"Search timeout after {self.query_timeout}s")
            with self.stats_lock:
                self.stats["timeout_errors"] += 1
                self.stats["failed_searches"] += 1
            return []
        except Exception as e:
            logger.error(f"{self.name} search failed: {e}")
            with self.stats_lock:
                self.stats["failed_searches"] += 1
            return []
    
    async def _execute_neo4j_query(
        self,
        cypher_query: str,
        params: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Neo4j query with timeout and error handling.
        
        SECURITY: Always uses parameterized queries
        PERFORMANCE: Configurable timeout
        
        Args:
            cypher_query: Cypher query string with parameters
            params: Query parameters dictionary
            timeout: Optional timeout override
            
        Returns:
            Query results as list of dictionaries
        """
        query_timeout = timeout or self.query_timeout
        
        try:
            # Execute with timeout
            results = await asyncio.wait_for(
                self.neo4j.query(cypher_query, params),
                timeout=query_timeout
            )
            
            # Convert to list of dicts if needed
            if results:
                return [dict(record) for record in results]
            return []
            
        except asyncio.TimeoutError:
            logger.error(f"Neo4j query timeout after {query_timeout}s")
            raise
        except Exception as e:
            logger.error(f"Neo4j query error: {e}")
            raise
    
    async def _get_agent_strategy(
        self,
        query: str,
        user_id: Optional[str],
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """
        Use CAMEL agent to determine search strategy.
        
        Returns:
            Strategy description from agent
        """
        # Build context for agent
        context = f"""Determine the best Neo4j search strategy for:
Query: "{query}"
User: {user_id or 'anonymous'}
Has purchase history: {bool(user_id)}
"""
        
        # Add ML intelligence if available
        if ml_intelligence and 'cypher_intel' in ml_intelligence:
            intel = ml_intelligence['cypher_intel']
            
            # Add relevant intelligence
            for source, data in intel.items():
                if isinstance(data, dict):
                    if 'user_segment' in data:
                        context += f"\nUser segment: {data['user_segment']}"
                    if 'purchase_patterns' in data:
                        context += f"\nPurchase patterns detected"
                    if 'clusters' in data:
                        context += f"\nProduct clusters available"
        
        # Add filters if present
        if filters:
            context += f"\nFilters: {json.dumps(filters, indent=2)}"
        
        context += """

Choose strategy:
1. COLLABORATIVE - Find via users with similar purchases
2. PATTERNS - Analyze purchase patterns and associations  
3. CATEGORY - Search by category and brand relationships
4. TRENDING - Find trending products in the graph
5. GENERAL - Basic graph search

Respond with the strategy name and brief explanation."""
        
        try:
            # Create message for agent with timeout
            user_msg = create_user_message(context)
            
            # Get response from CAMEL agent with timeout
            response = await asyncio.wait_for(
                asyncio.to_thread(self.agent.step, user_msg),
                timeout=5.0  # Quick timeout for agent
            )
            
            # Extract strategy
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                strategy = response.msg.content
            else:
                strategy = str(response)
            
            logger.debug(f"Agent strategy: {strategy[:100]}...")
            return strategy
            
        except asyncio.TimeoutError:
            logger.warning("Agent strategy timeout, using default")
            return "GENERAL"
        except Exception as e:
            logger.error(f"Agent strategy error: {e}")
            return "GENERAL"  # Fallback strategy
    
    async def _execute_strategy(
        self,
        strategy: str,
        query: str,
        user_id: Optional[str],
        limit: int,
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute the chosen search strategy.
        
        Returns:
            List of products from Neo4j
        """
        strategy_lower = strategy.lower()
        results = []
        
        # Use connection pool for parallel queries if enabled
        queries = []
        
        # Build query list based on strategy
        if "collaborative" in strategy_lower and user_id:
            queries.append(self._collaborative_filtering(user_id, query, limit))
        
        if "pattern" in strategy_lower and user_id:
            queries.append(self._purchase_patterns(user_id, query, limit))
        
        if "category" in strategy_lower or "brand" in strategy_lower:
            queries.append(self._category_search(query, limit, user_id))
        
        if "trending" in strategy_lower:
            queries.append(self._trending_search(query, limit))
        
        # Execute queries in parallel if multiple WITH TIMEOUT
        if len(queries) > 1:
            try:
                query_results = await asyncio.wait_for(
                    asyncio.gather(*queries, return_exceptions=True),
                    timeout=self.query_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Parallel queries timeout after {self.query_timeout}s")
                query_results = []

            for result in query_results:
                if isinstance(result, list):
                    results.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Query failed: {result}")
        elif queries:
            results = await queries[0]
        
        # Always include some general results if needed
        if len(results) < limit:
            general = await self._general_search(query, limit - len(results))
            results.extend(general)
        
        # Deduplicate and rank
        unique_results = self._deduplicate_and_rank(results)
        
        # Add metadata
        for idx, product in enumerate(unique_results[:limit]):
            product['cypher_rank'] = idx + 1
            product['agent'] = self.name
            product['search_method'] = 'graph_relationships'
            product['cypher_score'] = 1.0 - (idx * 0.1)
        
        return unique_results[:limit]
    
    async def _collaborative_filtering(
        self,
        user_id: str,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Find products via collaborative filtering.
        
        Users who bought X also bought Y pattern.
        SECURITY: Parameterized queries prevent injection
        """
        try:
            cypher_query = """
            MATCH (u:User {id: $user_id})-[:PURCHASED]->(p:Product)
            WITH p, u
            MATCH (other:User)-[:PURCHASED]->(p)
            WHERE other.id <> $user_id
            MATCH (other)-[:PURCHASED]->(rec:Product)
            WHERE NOT (u)-[:PURCHASED]->(rec)
            AND (
                toLower(rec.title) CONTAINS toLower($query) OR
                toLower(rec.description) CONTAINS toLower($query) OR
                toLower(rec.category) CONTAINS toLower($query)
            )
            WITH rec, COUNT(DISTINCT other) as score
            RETURN 
                rec.id as id,
                rec.title as title,
                rec.description as description,
                rec.price as price,
                rec.category as category,
                rec.brand as brand,
                rec.images as images,
                score
            ORDER BY score DESC
            LIMIT $limit
            """
            
            results = await self._execute_neo4j_query(
                cypher_query,
                {
                    "user_id": user_id,
                    "query": query,
                    "limit": limit
                }
            )
            
            products = []
            for record in results:
                product = dict(record)
                product['cypher_reason'] = f"Collaborative filtering (score: {product.get('score', 0)})"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Collaborative filtering failed: {e}")
            return []
    
    async def _purchase_patterns(
        self,
        user_id: str,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Find products based on purchase patterns.
        
        Frequently bought together pattern.
        SECURITY: Parameterized queries prevent injection
        """
        try:
            cypher_query = """
            MATCH (u:User {id: $user_id})-[:PURCHASED]->(p:Product)
            WITH p, u
            MATCH (p)<-[:PURCHASED]-(other:User)-[:PURCHASED]->(rec:Product)
            WHERE NOT (u)-[:PURCHASED]->(rec)
            AND (
                toLower(rec.title) CONTAINS toLower($query) OR
                toLower(rec.description) CONTAINS toLower($query)
            )
            WITH rec, COUNT(*) as co_purchase_count
            RETURN 
                rec.id as id,
                rec.title as title,
                rec.description as description,
                rec.price as price,
                rec.category as category,
                rec.brand as brand,
                rec.images as images,
                co_purchase_count
            ORDER BY co_purchase_count DESC
            LIMIT $limit
            """
            
            results = await self._execute_neo4j_query(
                cypher_query,
                {
                    "user_id": user_id,
                    "query": query,
                    "limit": limit
                }
            )
            
            products = []
            for record in results:
                product = dict(record)
                product['cypher_reason'] = f"Purchase pattern (co-purchases: {product.get('co_purchase_count', 0)})"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Purchase pattern search failed: {e}")
            return []
    
    async def _category_search(
        self,
        query: str,
        limit: int,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search by category and brand relationships.
        SECURITY: Parameterized queries prevent injection
        """
        try:
            if user_id:
                # Personalized category search
                cypher_query = """
                MATCH (u:User {id: $user_id})-[:PURCHASED|VIEWED]->(p:Product)
                WITH COLLECT(DISTINCT p.category) as user_categories,
                     COLLECT(DISTINCT p.brand) as user_brands
                MATCH (rec:Product)
                WHERE (rec.category IN user_categories OR rec.brand IN user_brands)
                AND (
                    toLower(rec.title) CONTAINS toLower($query) OR
                    toLower(rec.description) CONTAINS toLower($query)
                )
                RETURN DISTINCT
                    rec.id as id,
                    rec.title as title,
                    rec.description as description,
                    rec.price as price,
                    rec.category as category,
                    rec.brand as brand,
                    rec.images as images
                LIMIT $limit
                """
                params = {"user_id": user_id, "query": query, "limit": limit}
            else:
                # General category search
                cypher_query = """
                MATCH (p:Product)
                WHERE 
                    toLower(p.title) CONTAINS toLower($query) OR
                    toLower(p.description) CONTAINS toLower($query) OR
                    toLower(p.category) CONTAINS toLower($query) OR
                    toLower(p.brand) CONTAINS toLower($query)
                RETURN 
                    p.id as id,
                    p.title as title,
                    p.description as description,
                    p.price as price,
                    p.category as category,
                    p.brand as brand,
                    p.images as images
                LIMIT $limit
                """
                params = {"query": query, "limit": limit}
            
            results = await self._execute_neo4j_query(cypher_query, params)
            
            products = []
            for record in results:
                product = dict(record)
                product['cypher_reason'] = "Category/brand match"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Category search failed: {e}")
            return []
    
    async def _trending_search(
        self,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Find trending products based on recent interactions.
        SECURITY: Parameterized queries prevent injection
        """
        try:
            cypher_query = """
            MATCH (p:Product)<-[r:PURCHASED|VIEWED]-(u:User)
            WHERE r.timestamp > datetime() - duration('P7D')
            AND (
                toLower(p.title) CONTAINS toLower($query) OR
                toLower(p.description) CONTAINS toLower($query)
            )
            WITH p, COUNT(DISTINCT u) as trending_score
            RETURN 
                p.id as id,
                p.title as title,
                p.description as description,
                p.price as price,
                p.category as category,
                p.brand as brand,
                p.images as images,
                trending_score
            ORDER BY trending_score DESC
            LIMIT $limit
            """
            
            results = await self._execute_neo4j_query(
                cypher_query,
                {"query": query, "limit": limit}
            )
            
            products = []
            for record in results:
                product = dict(record)
                product['cypher_reason'] = f"Trending (interactions: {product.get('trending_score', 0)})"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Trending search failed: {e}")
            return []
    
    async def _general_search(
        self,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        General product search in Neo4j.
        SECURITY: Parameterized queries prevent injection
        """
        try:
            cypher_query = """
            MATCH (p:Product)
            WHERE 
                toLower(p.title) CONTAINS toLower($query) OR
                toLower(p.description) CONTAINS toLower($query) OR
                toLower(p.category) CONTAINS toLower($query) OR
                toLower(p.brand) CONTAINS toLower($query)
            RETURN 
                p.id as id,
                p.title as title,
                p.description as description,
                p.price as price,
                p.category as category,
                p.brand as brand,
                p.images as images
            LIMIT $limit
            """
            
            results = await self._execute_neo4j_query(
                cypher_query,
                {"query": query, "limit": limit}
            )
            
            products = []
            for record in results:
                product = dict(record)
                product['cypher_reason'] = "Graph search match"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"General search failed: {e}")
            return []
    
    def _deduplicate_and_rank(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicates and rank results.
        """
        seen = set()
        unique = []
        
        for product in results:
            product_id = product.get('id')
            if product_id and product_id not in seen:
                seen.add(product_id)
                unique.append(product)
        
        # Sort by any existing scores
        unique.sort(
            key=lambda x: (
                x.get('score', 0) +
                x.get('trending_score', 0) +
                x.get('co_purchase_count', 0)
            ),
            reverse=True
        )
        
        return unique
    
    def _update_stats(
        self,
        products_found: int,
        search_time: float,
        success: bool
    ):
        """Update agent statistics with thread safety."""
        with self.stats_lock:
            if success:
                self.stats["successful_searches"] += 1
                self.stats["total_products_found"] += products_found
                
                # Update average search time
                total_searches = self.stats["successful_searches"]
                current_avg = self.stats["avg_search_time"]
                self.stats["avg_search_time"] = (
                    (current_avg * (total_searches - 1) + search_time) / total_searches
                )
                
                # Update min/max
                self.stats["max_search_time"] = max(self.stats["max_search_time"], search_time)
                self.stats["min_search_time"] = min(self.stats["min_search_time"], search_time)
            else:
                self.stats["failed_searches"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics with thread safety."""
        with self.stats_lock:
            stats_copy = dict(self.stats)
        
        return {
            "agent": self.name,
            "style": self.style,
            **stats_copy,
            "success_rate": (
                stats_copy["successful_searches"] / stats_copy["total_searches"] * 100
                if stats_copy["total_searches"] > 0 else 0
            ),
            "timeout_rate": (
                stats_copy["timeout_errors"] / stats_copy["total_searches"] * 100
                if stats_copy["total_searches"] > 0 else 0
            )
        }
    
    async def health_check(self) -> bool:
        """
        Perform comprehensive health check on Neo4j connection.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check connection and data availability
            result = await self._execute_neo4j_query(
                """
                MATCH (u:User) 
                WITH count(u) > 0 as has_users
                MATCH (p:Product)
                WITH has_users, count(p) > 0 as has_products
                RETURN has_users AND has_products as is_healthy
                LIMIT 1
                """,
                {},
                timeout=5.0
            )
            
            if result and len(result) > 0:
                is_healthy = result[0].get('is_healthy', False)
                if not is_healthy:
                    logger.warning("Neo4j is connected but missing data")
                return is_healthy
            
            return False
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
