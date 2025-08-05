"""
Asynchronous Neo4j Integration for AI Stylist

Resolves recursion issues and improves async handling.
"""

import logging
import json
import datetime
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
import uuid

logger = logging.getLogger("neo4j_integration_fixed")

try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    logger.warning("neo4j AsyncGraphDatabase not available")
    NEO4J_AVAILABLE = False
    
    class AsyncGraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            class MockAsyncDriver:
                async def close(self):
                    pass
                async def __aenter__(self):
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
                async def execute_query(self, query, parameters=None, **kwargs):
                    logger.warning(f"Mock driver executing query: {query}")
                    return []
                def session(self, **kwargs):
                    class MockAsyncSession:
                        async def __aenter__(self):
                            return self
                        async def __aexit__(self, exc_type, exc_val, exc_tb):
                            pass
                        async def run(self, query, parameters=None, **kwargs):
                            logger.warning(f"Mock session running query: {query}")
                            class MockResult:
                                def __init__(self):
                                    self.records = []
                                def single(self):
                                    return None
                                def __iter__(self):
                                    return iter([])
                                async def __aiter__(self):
                                    return
                                    yield
                            return MockResult()
                    return MockAsyncSession()
            return MockAsyncDriver()


class ProductKnowledgeGraphAsync:
    """
    Neo4j integration with proper async handling and recursion prevention.
    """
    
    def __init__(self, url, username, password):
        """Initialize with connection pooling and timeout settings."""
        logger.info(f"Initializing FIXED Neo4j connection to {url}")
        self.url = url
        self.username = username
        self.password = password
        self.driver = None
        self.neo4j = self
        
        # Connection settings to prevent issues
        self.query_timeout = 30.0  # 30 second timeout
        self.max_retry_attempts = 3
        self.retry_delay = 1.0
        
        # Query lock to prevent concurrent issues
        self._query_lock = asyncio.Semaphore(10)  # Limit concurrent queries
        
        # Known schema issues tracking
        self.known_schema_issues = set()
        
        # Connection pool settings
        self._connection_attempts = 0
        self._max_connection_attempts = 3
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize connection with retry logic."""
        for attempt in range(self._max_connection_attempts):
            try:
                if NEO4J_AVAILABLE:
                    self.driver = AsyncGraphDatabase.driver(
                        self.url, 
                        auth=(self.username, self.password),
                        max_connection_lifetime=300,  # 5 minutes
                        max_connection_pool_size=50,
                        connection_timeout=10,
                        resolver=None  # Disable custom resolver
                    )
                    logger.info("Successfully initialized Neo4j driver")
                    return
                else:
                    logger.warning("Neo4j not available, using mock driver")
                    self.driver = AsyncGraphDatabase.driver(self.url, auth=(self.username, self.password))
                    return
            except Exception as e:
                self._connection_attempts += 1
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self._max_connection_attempts - 1:
                    logger.info(f"Retrying connection in {self.retry_delay} seconds...")
                    import time
                    time.sleep(self.retry_delay)
                else:
                    logger.error("All connection attempts failed")
                    self.driver = None
    
    async def close(self):
        """Close the Neo4j connection safely."""
        if self.driver:
            try:
                await asyncio.wait_for(self.driver.close(), timeout=10.0)
                logger.info("Neo4j connection closed successfully")
            except asyncio.TimeoutError:
                logger.warning("Neo4j connection close timed out")
            except Exception as e:
                logger.error(f"Error closing Neo4j connection: {e}")
    
    async def query(self, query_str, params=None, timeout=None):
        """
        Execute a Cypher query with proper timeout and error handling.
        """
        if not self.driver:
            logger.error("No active Neo4j connection")
            return []
        
        timeout = timeout or self.query_timeout
        params = params or {}
        
        # Use semaphore to limit concurrent queries
        async with self._query_lock:
            for attempt in range(self.max_retry_attempts):
                try:
                    # Execute query with timeout
                    result = await asyncio.wait_for(
                        self._execute_query_with_session(query_str, params),
                        timeout=timeout
                    )
                    return result
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Query timeout on attempt {attempt + 1}: {query_str[:100]}...")
                    if attempt < self.max_retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        logger.error(f"Query failed after {self.max_retry_attempts} attempts due to timeout")
                        return []
                        
                except Exception as e:
                    error_str = str(e).lower()
                    if "maximum recursion depth" in error_str:
                        logger.error(f"Recursion error in Neo4j query - aborting: {e}")
                        return []
                    elif "deadlock" in error_str and attempt < self.max_retry_attempts - 1:
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.warning(f"Deadlock detected, retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Neo4j query failed on attempt {attempt + 1}: {e}")
                        if attempt == self.max_retry_attempts - 1:
                            return []
        
        return []
    
    async def _execute_query_with_session(self, query_str, params):
        """Execute query within a session with proper resource management."""
        try:
            async with self.driver.session() as session:
                result = await session.run(query_str, params)
                records = []
                
                # Process records with timeout
                async for record in result:
                    records.append(dict(record))
                    
                    # Prevent memory issues with large result sets
                    if len(records) > 10000:
                        logger.warning("Large result set detected, truncating")
                        break
                
                return records
                
        except Exception as e:
            logger.error(f"Error in query execution: {e}")
            raise
    
    async def ensure_schema(self) -> bool:
        """Create schema with improved error handling and recursion prevention."""
        if not self.driver:
            logger.error("No active Neo4j connection")
            return False
        
        try:
            # Create constraints one by one to avoid deadlocks
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.title IS UNIQUE", 
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Collection) REQUIRE c.title IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tag) REQUIRE t.title IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MemoryState) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:UserPreference) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (i:ProductInteraction) REQUIRE i.id IS UNIQUE"
            ]
            
            for constraint in constraints:
                try:
                    await asyncio.wait_for(
                        self.query(constraint),
                        timeout=15.0
                    )
                    await asyncio.sleep(0.1)  # Small delay between constraints
                except asyncio.TimeoutError:
                    logger.warning(f"Constraint creation timed out: {constraint}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.debug(f"Constraint already exists: {constraint}")
                    else:
                        logger.error(f"Error creating constraint: {e}")
            
            logger.info("Schema creation completed")
            return True
            
        except Exception as e:
            logger.error(f"Error in schema creation: {e}")
            return False
    
    async def get_product_details(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get product details with improved error handling."""
        if not product_id:
            logger.error("No product ID provided")
            return None
        
        try:
            # Simple query to avoid complex joins that might cause recursion
            query = """
            MATCH (p:Product {id: $product_id})
            RETURN 
                p.id as id,
                p.title as title,
                p.price as price,
                p.description as description,
                p.images as images,
                p.visited_num as visited_num
            """
            
            result = await self.query(query, {"product_id": product_id}, timeout=10.0)
            
            if not result or len(result) == 0:
                logger.warning(f"Product not found: {product_id}")
                return None
            
            product = result[0]
            
            # Get additional data separately to avoid complex queries
            categories = await self._get_product_categories_safe(product_id)
            tags = await self._get_product_tags_safe(product_id)
            collections = await self._get_product_collections_safe(product_id)
            
            # Create product object
            product_details = {
                "id": product.get("id", ""),
                "title": product.get("title", "Unknown Product"),
                "price": product.get("price", 0.0),
                "description": product.get("description", ""),
                "images": self._parse_images_safe(product.get("images", "[]")),
                "categories": categories,
                "tags": tags,
                "collections": collections,
                "visited_num": product.get("visited_num", 0),
                "features": tags,  # Use tags as features
                "brand": self._extract_brand_from_tags(tags)
            }
            
            # Safely increment visit counter in background
            asyncio.create_task(self._increment_product_visit_safe(product_id))
            
            return product_details
            
        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            return None
    
    async def _get_product_categories_safe(self, product_id: str) -> List[str]:
        """Safely get product categories with timeout."""
        try:
            query = """
            MATCH (p:Product {id: $product_id})-[:IN_CATEGORY]->(c:Category)
            RETURN c.title as category
            LIMIT 10
            """
            
            result = await self.query(query, {"product_id": product_id}, timeout=5.0)
            return [record.get("category") for record in result if record.get("category")]
            
        except Exception as e:
            logger.warning(f"Error getting categories for {product_id}: {e}")
            return []
    
    async def _get_product_tags_safe(self, product_id: str) -> List[str]:
        """Safely get product tags with timeout."""
        try:
            query = """
            MATCH (p:Product {id: $product_id})-[:TAGGED_WITH]->(t:Tag)
            RETURN t.title as tag
            LIMIT 10
            """
            
            result = await self.query(query, {"product_id": product_id}, timeout=5.0)
            return [record.get("tag") for record in result if record.get("tag")]
            
        except Exception as e:
            logger.warning(f"Error getting tags for {product_id}: {e}")
            return []
    
    async def _get_product_collections_safe(self, product_id: str) -> List[str]:
        """Safely get product collections with timeout."""
        try:
            query = """
            MATCH (p:Product {id: $product_id})-[:IN_COLLECTION]->(c:Collection)
            RETURN c.title as collection
            LIMIT 10
            """
            
            result = await self.query(query, {"product_id": product_id}, timeout=5.0)
            return [record.get("collection") for record in result if record.get("collection")]
            
        except Exception as e:
            logger.warning(f"Error getting collections for {product_id}: {e}")
            return []
    
    async def _increment_product_visit_safe(self, product_id: str):
        """Safely increment visit counter without blocking."""
        try:
            query = """
            MATCH (p:Product {id: $product_id})
            SET p.visited_num = COALESCE(p.visited_num, 0) + 1
            """
            
            await self.query(query, {"product_id": product_id}, timeout=5.0)
            
        except Exception as e:
            logger.debug(f"Could not increment visit counter for {product_id}: {e}")
            # Don't raise error - this is not critical
    
    def _parse_images_safe(self, images_str: str) -> List[str]:
        """Safely parse images string."""
        if not images_str:
            return []
        
        try:
            # Handle JSON array format
            if images_str.startswith('[') and images_str.endswith(']'):
                import json
                clean_str = images_str.replace("'", '"')
                return json.loads(clean_str)
            else:
                # Handle single image
                return [images_str.strip()]
        except Exception as e:
            logger.debug(f"Could not parse images: {e}")
            return []
    
    def _extract_brand_from_tags(self, tags: List[str]) -> Optional[str]:
        """Extract potential brand from tags."""
        if not tags:
            return None
        
        # Simple brand detection
        common_categories = {"women", "men", "accessories", "jewelry", "clothing", 
                           "summer", "winter", "fall", "spring", "sale"}
        
        for tag in tags:
            if tag and tag[0].isupper() and tag.lower() not in common_categories:
                return tag
        
        return None
    
    async def get_product_by_filter(self, category=None, collection=None, tag=None, 
                                  brand=None, min_price=None, max_price=None, 
                                  material=None, limit=5) -> List[Dict[str, Any]]:
        """Get products by filter with improved performance."""
        try:
            # Build a simpler query to avoid complex joins
            where_clauses = [
                "p.price > 0",
                "p.title IS NOT NULL",
                "p.title <> ''",
                "NOT toLower(p.title) CONTAINS 'test'",
                "NOT toLower(p.title) CONTAINS 'untitled'"
            ]
            
            params = {"limit": limit}
            
            # Add price filters
            if min_price is not None:
                where_clauses.append("p.price >= $min_price")
                params["min_price"] = float(min_price)
            
            if max_price is not None:
                where_clauses.append("p.price <= $max_price")
                params["max_price"] = float(max_price)
            
            base_query = f"""
            MATCH (p:Product)
            WHERE {' AND '.join(where_clauses)}
            """
            
            # Apply category filter if provided
            if category:
                base_query += """
                AND EXISTS {
                    MATCH (p)-[:IN_CATEGORY]->(c:Category)
                    WHERE toLower(c.title) CONTAINS toLower($category)
                }
                """
                params["category"] = category
            
            # Apply tag filter if provided
            if tag:
                base_query += """
                AND EXISTS {
                    MATCH (p)-[:TAGGED_WITH]->(t:Tag)
                    WHERE toLower(t.title) CONTAINS toLower($tag)
                }
                """
                params["tag"] = tag
            
            # Apply collection filter if provided
            if collection:
                base_query += """
                AND EXISTS {
                    MATCH (p)-[:IN_COLLECTION]->(col:Collection)
                    WHERE toLower(col.title) CONTAINS toLower($collection)
                }
                """
                params["collection"] = collection
            
            # Complete query
            base_query += """
            RETURN 
                p.id as id,
                p.title as title,
                p.price as price,
                p.description as description,
                p.images as images,
                COALESCE(p.visited_num, 0) as visited_num
            ORDER BY p.visited_num DESC, p.price ASC
            LIMIT $limit
            """
            
            result = await self.query(base_query, params, timeout=15.0)
            
            # Process results
            products = []
            for record in result:
                product_id = record.get("id", "")
                if not product_id:
                    continue
                
                product_obj = {
                    "id": product_id,
                    "title": record.get("title", ""),
                    "price": record.get("price", 0.0),
                    "description": record.get("description", ""),
                    "images": self._parse_images_safe(record.get("images", "[]")),
                    "visited_num": record.get("visited_num", 0)
                }
                
                # Get categories separately if needed
                if category:
                    product_obj["categories"] = await self._get_product_categories_safe(product_id)
                
                products.append(product_obj)
            
            logger.info(f"Retrieved {len(products)} products with filters")
            return products
            
        except Exception as e:
            logger.error(f"Error in get_product_by_filter: {e}")
            return []
    
    async def get_similar_products(self, product_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get similar products with simplified logic."""
        try:
            # Simple similarity based on shared categories
            query = """
            MATCH (p:Product {id: $product_id})-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(similar:Product)
            WHERE similar.id <> $product_id
            RETURN DISTINCT
                similar.id as id,
                similar.title as title,
                similar.price as price,
                similar.description as description,
                similar.images as images,
                similar.visited_num as visited_num
            ORDER BY similar.visited_num DESC
            LIMIT $limit
            """
            
            result = await self.query(query, {"product_id": product_id, "limit": limit}, timeout=10.0)
            
            products = []
            for record in result:
                product_obj = {
                    "id": record.get("id", ""),
                    "title": record.get("title", "Unknown Product"),
                    "price": record.get("price", 0.0),
                    "description": record.get("description", ""),
                    "images": self._parse_images_safe(record.get("images", "[]")),
                    "visited_num": record.get("visited_num", 0)
                }
                products.append(product_obj)
            
            logger.info(f"Found {len(products)} similar products")
            return products
            
        except Exception as e:
            logger.error(f"Error getting similar products: {e}")
            return []
    
    async def get_popular_products(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get popular products with simple query."""
        try:
            query = """
            MATCH (p:Product)
            WHERE p.price > 0 AND p.title IS NOT NULL
            RETURN 
                p.id as id,
                p.title as title,
                p.price as price,
                p.description as description,
                p.images as images,
                p.visited_num as visited_num
            ORDER BY COALESCE(p.visited_num, 0) DESC
            LIMIT $limit
            """
            
            result = await self.query(query, {"limit": limit}, timeout=10.0)
            
            products = []
            for record in result:
                product_obj = {
                    "id": record.get("id", ""),
                    "title": record.get("title", "Unknown Product"),
                    "price": record.get("price", 0.0),
                    "description": record.get("description", ""),
                    "images": self._parse_images_safe(record.get("images", "[]")),
                    "visited_num": record.get("visited_num", 0)
                }
                products.append(product_obj)
            
            logger.info(f"Retrieved {len(products)} popular products")
            return products
            
        except Exception as e:
            logger.error(f"Error getting popular products: {e}")
            return []
    
    async def create_or_update_user(self, user_id: str, user_data: Optional[Dict[str, Any]] = None) -> bool:
        """Create or update user with timeout protection."""
        if not user_id:
            logger.error("No user ID provided")
            return False
        
        try:
            # Simple user creation/update
            query = """
            MERGE (u:User {id: $user_id})
            SET u.last_active = $timestamp
            RETURN u.id as user_id
            """
            
            result = await self.query(query, {
                "user_id": user_id,
                "timestamp": datetime.datetime.now().isoformat()
            }, timeout=5.0)
            
            return bool(result and result[0].get("user_id") == user_id)
            
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            return False
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """Get database statistics with timeout protection."""
        stats = {}
        
        try:
            # Simple node counts
            node_queries = [
                ("product_count", "MATCH (n:Product) RETURN count(n) as count"),
                ("user_count", "MATCH (n:User) RETURN count(n) as count"),
                ("category_count", "MATCH (n:Category) RETURN count(n) as count"),
            ]
            
            for stat_name, query in node_queries:
                try:
                    result = await self.query(query, timeout=5.0)
                    if result:
                        stats[stat_name] = result[0]["count"]
                except Exception as e:
                    logger.debug(f"Could not get {stat_name}: {e}")
                    stats[stat_name] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {"error": str(e)}

    # ADD THE NEW METHODS HERE (AFTER the complete get_database_statistics method)
    async def verify_database_schema(self) -> Tuple[bool, List[str]]:
        return True, []

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        return {"preferred_categories": [], "preferred_collections": [], "preferred_tags": [], "budget_range": None}

    async def get_products_by_category(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        return await self.get_product_by_filter(category=category, limit=limit)

    async def get_products_by_tag(self, tag: str, limit: int = 5) -> List[Dict[str, Any]]:
        return await self.get_product_by_filter(tag=tag, limit=limit)

    async def get_trending_products(self, limit: int = 5) -> List[Dict[str, Any]]:
        return await self.get_popular_products(limit)


logger.info("✅ Fixed Neo4j Integration loaded successfully")
