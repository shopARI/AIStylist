"""
Enhanced Asynchronous Neo4j Integration for AI Stylist

Provides advanced integration with Neo4j for product retrieval, user management,
and memory persistence.
"""

import logging
import json
import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
import uuid
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo4j_integration_async")

try:
    from neo4j import AsyncGraphDatabase
except ImportError:
    logger.warning("neo4j AsyncGraphDatabase not available. Install with: pip install neo4j>=5.0.0")
    # Use a mock version (same as original)
    class AsyncGraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            logger.error("Cannot create AsyncGraphDatabase driver. Using mock version.")
            # Create a mock driver with async methods
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
    Enhanced asynchronous integration with Neo4j for product retrieval, user management,
    and memory persistence.
    """
    
    def __init__(self, url, username, password):
        """
        Initialize the Neo4j connection.
        
        Args:
            url: Neo4j connection URL
            username: Neo4j username
            password: Neo4j password
        """
        logger.info(f"Initializing Enhanced Async Neo4j connection to {url}")
        self.url = url
        self.username = username
        self.password = password
        self.driver = None
        self.neo4j = self  # For compatibility with existing code
        
        # Track known schema problems
        self.known_schema_issues = set()
        
        # Connect to Neo4j
        try:
            self.driver = AsyncGraphDatabase.driver(url, auth=(username, password))
            logger.info("Successfully initialized async Neo4j driver")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            # Don't raise exception, allow initialization to continue for graceful degradation
    
    async def _verify_connection(self):
        """Verify the Neo4j connection with a simple query"""
        if not self.driver:
            raise ConnectionError("Neo4j driver not available")
            
        async with self.driver.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            if not record or record.get("test") != 1:
                raise ConnectionError("Could not verify Neo4j connection")
    
    async def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")
    
    async def query(self, query, params=None):
        """
        Execute a Cypher query against Neo4j.
        
        Args:
            query: The Cypher query to execute
            params: Query parameters
            
        Returns:
            List of records as dictionaries
        """
        if not self.driver:
            logger.error("No active Neo4j connection")
            return []
        
        try:
            async with self.driver.session() as session:
                result = await session.run(query, params or {})
                records = []
                async for record in result:
                    records.append(dict(record))
                return records
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return []

    async def ensure_schema(self) -> bool:
        """Ensure schema with retry mechanism for deadlocks"""
        if not self.driver:
            logger.error("No active Neo4j connection")
            return False
            
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Create constraints for product nodes - using more compatible syntax
                product_constraints = [
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.title IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Collection) REQUIRE c.title IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tag) REQUIRE t.title IS UNIQUE" # Fixed: t.title instead of c.title
                ]
                
                for constraint in product_constraints:
                    try:
                        await self.query(constraint)
                    except Exception as e:
                        if "already exists" in str(e):
                            logger.info(f"Constraint already exists: {constraint}")
                        elif "There already exists an index" in str(e):
                            # If there's a conflicting index, log it but continue
                            logger.warning(f"Conflicting index exists for constraint: {constraint}")
                        else:
                            logger.error(f"Error creating constraint: {constraint} - {e}")
                
                # Create constraints for user nodes with same compatible syntax
                user_constraints = [
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MemoryState) REQUIRE m.id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:UserPreference) REQUIRE p.id IS UNIQUE",
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (i:ProductInteraction) REQUIRE i.id IS UNIQUE"
                ]
                
                for constraint in user_constraints:
                    try:
                        await self.query(constraint)
                    except Exception as e:
                        if "already exists" in str(e):
                            logger.info(f"Constraint already exists: {constraint}")
                        else:
                            logger.error(f"Error creating constraint: {constraint} - {e}")
                
                # Create basic relationship types if they don't exist
                await self._ensure_relationship_types()
                
                logger.info("Enhanced Neo4j schema created successfully")
                return True
                
            except Exception as e:
                retry_count += 1
                if "DeadlockDetected" in str(e) and retry_count < max_retries:
                    # Exponential backoff with jitter
                    import random
                    wait_time = (2 ** retry_count) + random.uniform(0, 1)
                    logger.warning(f"Deadlock detected, retrying schema setup in {wait_time:.2f} seconds (attempt {retry_count}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Error ensuring Neo4j schema after {retry_count} attempts: {e}")
                    return False
        
        return False
    
    async def _ensure_relationship_types(self):
        """
        Create basic relationship type examples if missing.
        This ensures that relationship types exist without affecting user data.
        """
        # Check which relationship types are missing
        relationship_types = ["HAS_PREFERENCE", "HAS_INTERACTION", "REFERS_TO"]
        missing_types = []
        
        for rel_type in relationship_types:
            query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count LIMIT 1"
            result = await self.query(query)
            
            # If we get a warning about unknown relationship type
            if len(result) == 0 or (len(result) > 0 and result[0].get("count", 0) == 0):
                missing_types.append(rel_type)
        
        if not missing_types:
            return
            
        logger.warning(f"Missing relationship types: {missing_types}")
        
        try:
            # Create a sample relationship network only if types are missing
            if missing_types:
                # Create test user if needed
                sample_user_query = """
                MERGE (u:User {id: 'system_test_user'})
                ON CREATE SET u.name = 'System Test User',
                             u.created_at = datetime()
                RETURN u.id as id
                """
                user_result = await self.query(sample_user_query)
                
                if not user_result:
                    logger.error("Failed to create test user for relationship types")
                    return
                
                # Create test preference if HAS_PREFERENCE is missing
                if "HAS_PREFERENCE" in missing_types:
                    pref_query = """
                    MATCH (u:User {id: 'system_test_user'})
                    MERGE (p:UserPreference {id: 'system_test_pref'})
                    ON CREATE SET p.type = 'test_type',
                                 p.value = 'test_value',
                                 p.created_at = datetime()
                    MERGE (u)-[:HAS_PREFERENCE]->(p)
                    """
                    await self.query(pref_query)
                
                # Create test interaction and REFERS_TO if needed
                if "HAS_INTERACTION" in missing_types or "REFERS_TO" in missing_types:
                    # Find a product to use
                    prod_query = "MATCH (p:Product) RETURN p.id as id LIMIT 1"
                    product_result = await self.query(prod_query)
                    
                    if product_result and len(product_result) > 0:
                        product_id = product_result[0].get("id")
                        
                        if product_id:
                            # Create interaction with both relationship types
                            interaction_query = f"""
                            MATCH (u:User {{id: 'system_test_user'}}), (p:Product {{id: '{product_id}'}})
                            MERGE (i:ProductInteraction {{id: 'system_test_interaction'}})
                            ON CREATE SET i.type = 'test_interaction',
                                         i.timestamp = datetime()
                            MERGE (u)-[:HAS_INTERACTION]->(i)
                            MERGE (i)-[:REFERS_TO]->(p)
                            """
                            await self.query(interaction_query)
                
                logger.info("Created sample relationship types for schema verification")
        except Exception as e:
            logger.error(f"Error creating relationship types: {e}")
    
    async def verify_database_schema(self) -> Tuple[bool, List[str]]:
        """
        Verify that the database contains the expected schema elements.
        Enhanced to include user management and memory persistence.
        
        Returns:
            Tuple of (schema_valid, missing_elements)
        """
        # Required elements based on our enhanced schema
        required_node_labels = ["Product", "Category", "Collection", "Tag", "User", "MemoryState", "UserPreference", "ProductInteraction"]
        required_relationship_types = ["IN_CATEGORY", "IN_COLLECTION", "TAGGED_WITH", "HAS_MEMORY", "HAS_PREFERENCE", "HAS_INTERACTION", "REFERS_TO"]
        
        missing_elements = []
        
        # Check for node labels
        labels_query = "CALL db.labels()"
        labels_result = await self.query(labels_query)
        
        if labels_result:
            existing_labels = [record.get("label") for record in labels_result]
            for label in required_node_labels:
                if label not in existing_labels:
                    missing_elements.append(f"Node label: {label}")
        else:
            # If query failed, assume all labels are missing
            missing_elements.extend([f"Node label: {label}" for label in required_node_labels])
        
        # Check for relationship types
        rels_query = "CALL db.relationshipTypes()"
        rels_result = await self.query(rels_query)
        
        if rels_result:
            existing_rels = [record.get("relationshipType") for record in rels_result]
            for rel in required_relationship_types:
                if rel not in existing_rels:
                    missing_elements.append(f"Relationship type: {rel}")
        else:
            # If query failed, assume all relationships are missing
            missing_elements.extend([f"Relationship type: {rel}" for rel in required_relationship_types])
        
        # Check if Products have the expected properties
        props_query = """
        MATCH (p:Product) 
        RETURN p LIMIT 1
        """
        props_result = await self.query(props_query)
        
        required_properties = ["id", "title", "price", "images"]
        
        if props_result and len(props_result) > 0:
            product = props_result[0].get("p", {})
            for prop in required_properties:
                if prop not in product:
                    missing_elements.append(f"Product property: {prop}")
        
        schema_valid = len(missing_elements) == 0
        
        if schema_valid:
            logger.info("Database schema verification successful")
        else:
            logger.warning(f"Database schema incomplete. Missing: {missing_elements}")
            
            # Save known schema issues to prevent repeated warnings
            self.known_schema_issues = set(missing_elements)
        
        return schema_valid, missing_elements
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the database, including user and memory data.
        
        Returns:
            Dictionary with database statistics
        """
        stats = {}
        
        # Count node types
        node_types = ["Product", "Category", "Collection", "Tag", "User", "MemoryState", "UserPreference", "ProductInteraction"]
        
        for node_type in node_types:
            query = f"MATCH (n:{node_type}) RETURN count(n) as count"
            result = await self.query(query)
            if result:
                stats[f"{node_type.lower()}_count"] = result[0]["count"]
        
        # Count relationship types
        rel_types = ["IN_CATEGORY", "IN_COLLECTION", "TAGGED_WITH", "HAS_MEMORY", "HAS_PREFERENCE", "HAS_INTERACTION", "REFERS_TO"]
        
        for rel_type in rel_types:
            query = f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count"
            result = await self.query(query)
            if result:
                stats[f"{rel_type.lower()}_count"] = result[0]["count"]
        
        # Get product price statistics
        price_query = """
        MATCH (p:Product) WHERE p.price IS NOT NULL
        RETURN min(p.price) as min_price, max(p.price) as max_price, avg(p.price) as avg_price
        """
        price_result = await self.query(price_query)
        if price_result:
            stats["price_statistics"] = {
                "min": price_result[0]["min_price"],
                "max": price_result[0]["max_price"],
                "avg": price_result[0]["avg_price"]
            }
        
        # Get user activity statistics - Fixed query syntax
        user_query = """
        MATCH (u:User)
        OPTIONAL MATCH (u)-[:HAS_INTERACTION]->(i:ProductInteraction)
        WITH u, count(i) as interaction_count
        RETURN count(u) as user_count, 
               sum(interaction_count) as total_interactions
        """
        user_result = await self.query(user_query)
        if user_result:
            stats["user_statistics"] = {
                "user_count": user_result[0]["user_count"],
                "total_interactions": user_result[0]["total_interactions"] or 0
            }
        
        # Get top product categories
        category_query = """
        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
        RETURN c.title as category, count(p) as count
        ORDER BY count DESC LIMIT 5
        """
        category_result = await self.query(category_query)
        if category_result:
            stats["top_categories"] = {record["category"]: record["count"] for record in category_result}
        
        # Get memory statistics
        memory_query = """
        MATCH (m:MemoryState)
        RETURN count(m) as memory_count
        """
        memory_result = await self.query(memory_query)
        if memory_result:
            stats["memory_statistics"] = {
                "memory_count": memory_result[0]["memory_count"]
            }
        
        return stats
    
    def _parse_images(self, images_str: str) -> List[str]:
        """
        Parse the images string into a list of URLs.
        
        Args:
            images_str: String representation of image URLs array
            
        Returns:
            List of image URLs
        """
        if not images_str:
            return []
            
        try:
            # Handle the case where images is a string representation of a JSON array
            import json
            # Clean up the string to make it valid JSON
            clean_str = images_str.replace("'", '"')
            return json.loads(clean_str)
        except Exception as e:
            logger.warning(f"Failed to parse images JSON: {e}")
            # Fall back to simple string split if JSON parsing fails
            if "[" in images_str and "]" in images_str:
                # Extract content between brackets
                content = images_str[images_str.find("[")+1:images_str.find("]")]
                # Split by comma and clean up
                return [url.strip().strip('"\'') for url in content.split(",")]
            return [images_str]  # Return as single item if all else fails
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences from Neo4j.
        Enhanced implementation for persistent user preferences.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary of user preferences
        """
        logger.info(f"Getting preferences for user: {user_id}")
        
        if not user_id:
            return {
                "preferred_categories": [],
                "preferred_collections": [],
                "preferred_tags": [],
                "budget_range": None
            }
        
        try:
            # Check if HAS_PREFERENCE relationship exists before querying
            if "Relationship type: HAS_PREFERENCE" in self.known_schema_issues:
                logger.info(f"Skipping preference query due to missing relationship type")
                return {
                    "preferred_categories": [],
                    "preferred_collections": [],
                    "preferred_tags": [],
                    "budget_range": None
                }
                
            # Query Neo4j for user preferences
            query = """
            MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:UserPreference)
            RETURN p.type as preference_type, p.value as preference_value
            """
            
            result = await self.query(query, {"user_id": user_id})
            
            if not result:
                logger.info(f"No preferences found for user {user_id}")
                return {
                    "preferred_categories": [],
                    "preferred_collections": [],
                    "preferred_tags": [],
                    "budget_range": None
                }
            
            # Process preference results
            preferences = {
                "preferred_categories": [],
                "preferred_collections": [],
                "preferred_tags": [],
                "budget_range": None,
                "color_preferences": [],
                "style_preferences": [],
                "occasion_preferences": []
            }
            
            for record in result:
                pref_type = record.get("preference_type")
                pref_value = record.get("preference_value")
                
                if not pref_type or not pref_value:
                    continue
                
                # Parse JSON value if applicable
                try:
                    if isinstance(pref_value, str):
                        pref_value = json.loads(pref_value)
                except json.JSONDecodeError:
                    # If not valid JSON, use as is
                    pass
                
                # Map preference types to our structure
                if pref_type == "category":
                    if isinstance(pref_value, list):
                        preferences["preferred_categories"].extend(pref_value)
                    else:
                        preferences["preferred_categories"].append(pref_value)
                elif pref_type == "collection":
                    if isinstance(pref_value, list):
                        preferences["preferred_collections"].extend(pref_value)
                    else:
                        preferences["preferred_collections"].append(pref_value)
                elif pref_type == "tag":
                    if isinstance(pref_value, list):
                        preferences["preferred_tags"].extend(pref_value)
                    else:
                        preferences["preferred_tags"].append(pref_value)
                elif pref_type == "budget_range":
                    preferences["budget_range"] = pref_value
                elif pref_type == "color":
                    if isinstance(pref_value, list):
                        preferences["color_preferences"].extend(pref_value)
                    else:
                        preferences["color_preferences"].append(pref_value)
                elif pref_type == "style":
                    if isinstance(pref_value, list):
                        preferences["style_preferences"].extend(pref_value)
                    else:
                        preferences["style_preferences"].append(pref_value)
                elif pref_type == "occasion":
                    if isinstance(pref_value, list):
                        preferences["occasion_preferences"].extend(pref_value)
                    else:
                        preferences["occasion_preferences"].append(pref_value)
                else:
                    # Add other preference types directly
                    preferences[pref_type] = pref_value
            
            # Remove duplicates from lists
            for key in preferences:
                if isinstance(preferences[key], list):
                    preferences[key] = list(dict.fromkeys(preferences[key]))
            
            logger.info(f"Retrieved preferences for user {user_id}")
            return preferences
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {
                "preferred_categories": [],
                "preferred_collections": [],
                "preferred_tags": [],
                "budget_range": None
            }
    
    async def create_or_update_user(self, user_id: str, user_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create or update a user in Neo4j.
        FIXED: Properly handle parameters.
        """
        if not user_id:
            logger.error("No user ID provided")
            return False
            
        try:
            # Prepare user data
            data = user_data or {}
            current_time = datetime.datetime.now().isoformat()
            
            # FIXED: Properly build parameters dictionary
            params = {
                "user_id": user_id,
                "last_active": current_time
            }
            
            set_clauses = ["u.last_active = $last_active"]
            
            # Add other data parameters
            for key, value in data.items():
                if key != "last_active":  # Already handled above
                    param_key = f"data_{key}"
                    params[param_key] = value
                    set_clauses.append(f"u.{key} = ${param_key}")
            
            # Create or update user
            query = f"""
            MERGE (u:User {{id: $user_id}})
            SET {', '.join(set_clauses)}
            RETURN u.id as user_id
            """
            
            result = await self.query(query, params)
            
            if result and result[0].get("user_id") == user_id:
                logger.info(f"Created or updated user {user_id}")
                return True
            else:
                logger.warning(f"Failed to create or update user {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating or updating user: {e}")
            return False




    async def get_user_interaction_history(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get the interaction history for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of interactions to return
            
        Returns:
            List of interaction records
        """
        if not user_id:
            logger.error("No user ID provided")
            return []
            
        try:
            # Check if required relationship types exist
            if "Relationship type: HAS_INTERACTION" in self.known_schema_issues or "Relationship type: REFERS_TO" in self.known_schema_issues:
                logger.info(f"Skipping interaction history query due to missing relationship types")
                return []
                
            # Query for user interactions
            query = """
            MATCH (u:User {id: $user_id})-[:HAS_INTERACTION]->(i:ProductInteraction)-[:REFERS_TO]->(p:Product)
            RETURN 
                i.id as interaction_id,
                i.type as interaction_type,
                i.timestamp as timestamp,
                p.id as product_id,
                p.title as product_title,
                p.price as product_price
            ORDER BY i.timestamp DESC
            LIMIT $limit
            """
            
            result = await self.query(query, {"user_id": user_id, "limit": limit})
            
            # Process results
            interactions = []
            
            for record in result:
                interaction = {
                    "id": record.get("interaction_id"),
                    "type": record.get("interaction_type"),
                    "timestamp": record.get("timestamp"),
                    "product": {
                        "id": record.get("product_id"),
                        "title": record.get("product_title"),
                        "price": record.get("product_price")
                    }
                }
                
                interactions.append(interaction)
                
            logger.info(f"Retrieved {len(interactions)} interactions for user {user_id}")
            return interactions
            
        except Exception as e:
            logger.error(f"Error getting user interaction history: {e}")
            return []
    
    async def get_personalized_product_recommendations(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get personalized product recommendations based on user interactions and preferences.
        
        Args:
            user_id: User ID
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        if not user_id:
            logger.error("No user ID provided")
            return []
            
        try:
            # Check if required relationship types exist
            if "Relationship type: HAS_PREFERENCE" in self.known_schema_issues or "Relationship type: HAS_INTERACTION" in self.known_schema_issues:
                logger.info(f"Skipping personalized recommendations due to missing relationship types")
                if hasattr(self, 'get_popular_products'):
                    return await self.get_popular_products(limit)
                else:
                    return []
                
            # Query products based on user preferences and interactions
            query = """
            // Find categories liked by this user
            MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:UserPreference)
            WHERE p.type = 'category'
            WITH u, collect(p.value) as preferred_categories
            
            // Find products interacted with by this user
            MATCH (u)-[:HAS_INTERACTION]->(i:ProductInteraction)-[:REFERS_TO]->(viewed:Product)
            WITH u, preferred_categories, collect(viewed) as viewed_products
            
            // Find similar products in preferred categories
            UNWIND preferred_categories as category
            MATCH (sim_product:Product)-[:IN_CATEGORY]->(:Category {title: category})
            WHERE NOT sim_product IN viewed_products
            
            // Return recommended products
            RETURN DISTINCT
                sim_product.id as id,
                sim_product.title as title,
                sim_product.price as price,
                sim_product.description as description,
                sim_product.images as images
            LIMIT $limit
            """
            
            result = await self.query(query, {"user_id": user_id, "limit": limit})
            
            if result:
                # Process results into product objects
                recommendations = []
                
                for record in result:
                    product_id = record.get("id")
                    
                    product_obj = {
                        "id": product_id,
                        "title": record.get("title", "Untitled Product"),
                        "price": record.get("price", 0.0),
                        "description": record.get("description", ""),
                        "images": self._parse_images(record.get("images", "[]")),
                        "categories": await self._get_product_categories(product_id)
                    }
                    
                    recommendations.append(product_obj)
                
                logger.info(f"Found {len(recommendations)} personalized recommendations for user {user_id}")
                return recommendations
                
            # If no category-based recommendations, try based on recent views
            query = """
            // Find recently viewed products
            MATCH (u:User {id: $user_id})-[:HAS_INTERACTION]->(i:ProductInteraction)-[:REFERS_TO]->(p:Product)
            WHERE i.type = 'viewed' OR i.type = 'liked'
            WITH p, i.timestamp as timestamp
            ORDER BY timestamp DESC
            LIMIT 3
            
            // Find products similar to recently viewed
            MATCH (p)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(similar:Product)
            WHERE similar.id <> p.id
            
            // Return similar products
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
            
            result = await self.query(query, {"user_id": user_id, "limit": limit})
            
            if result:
                # Process results
                recommendations = []
                
                for record in result:
                    product_id = record.get("id")
                    
                    product_obj = {
                        "id": product_id,
                        "title": record.get("title", "Untitled Product"),
                        "price": record.get("price", 0.0),
                        "description": record.get("description", ""),
                        "images": self._parse_images(record.get("images", "[]")),
                        "categories": await self._get_product_categories(product_id),
                        "visited_num": record.get("visited_num", 0)
                    }
                    
                    recommendations.append(product_obj)
                
                logger.info(f"Found {len(recommendations)} similar recommendations for user {user_id}")
                return recommendations
            
            # If still no recommendations, fall back to popular products
            logger.info(f"No personalized recommendations found, falling back to popular products")
            return await self.get_popular_products(limit)
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            # Fall back to popular products
            return await self.get_popular_products(limit)
    
    async def get_product_by_filter(self, category=None, collection=None, tag=None, 
                brand=None, min_price=None, max_price=None, material=None, limit=5):
        """
        Get products by filtering on various attributes.
        FIXED: Resolve Neo4j aggregation syntax errors.
        """
        logger.info(f"Retrieving products with filters: category={category}, "
                f"collection={collection}, tag={tag}, price={min_price}-{max_price}")
        
        # Start with a flexible query that will always return results
        query = """
        MATCH (p:Product)
        WHERE p.price > 0 
        AND p.title IS NOT NULL AND p.title <> ''
        AND NOT toLower(p.title) CONTAINS 'test' 
        AND NOT toLower(p.title) CONTAINS 'untitled'
        """
        
        params = {"limit": limit}
        
        # FIXED: Build scoring logic without aggregation syntax errors
        scoring_parts = []
        
        # Apply category filter
        if category:
            query += """
            WITH p
            OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
            WHERE toLower(c.title) CONTAINS toLower($category)
            """
            params["category"] = category
            scoring_parts.append("CASE WHEN count(c) > 0 THEN 5 ELSE 0 END")
        
        # Apply tag filter
        if tag:
            if category:  # Continue the WITH chain
                query += """
                WITH p, c
                OPTIONAL MATCH (p)-[:TAGGED_WITH]->(t:Tag)
                WHERE toLower(t.title) CONTAINS toLower($tag)
                """
            else:  # Start the WITH chain
                query += """
                WITH p
                OPTIONAL MATCH (p)-[:TAGGED_WITH]->(t:Tag)
                WHERE toLower(t.title) CONTAINS toLower($tag)
                """
            params["tag"] = tag
            scoring_parts.append("CASE WHEN count(t) > 0 THEN 5 ELSE 0 END")
        
        # Apply collection filter
        if collection:
            if category or tag:  # Continue the WITH chain
                query += """
                WITH p, c, t
                OPTIONAL MATCH (p)-[:IN_COLLECTION]->(col:Collection)
                WHERE toLower(col.title) CONTAINS toLower($collection)
                """
            else:  # Start the WITH chain
                query += """
                WITH p
                OPTIONAL MATCH (p)-[:IN_COLLECTION]->(col:Collection)
                WHERE toLower(col.title) CONTAINS toLower($collection)
                """
            params["collection"] = collection
            scoring_parts.append("CASE WHEN count(col) > 0 THEN 5 ELSE 0 END")
        
        # FIXED: Calculate score in a single WITH clause
        if scoring_parts:
            score_expression = " + ".join(scoring_parts)
            query += f"""
            WITH p, ({score_expression}) as score
            """
        else:
            query += """
            WITH p, 0 as score
            """
        
        # Add price filters if provided
        if min_price is not None:
            query += """
            WHERE p.price >= $min_price
            """
            params["min_price"] = float(min_price)
        
        if max_price is not None:
            if min_price is not None:
                query += """
                AND p.price <= $max_price
                """
            else:
                query += """
                WHERE p.price <= $max_price
                """
            params["max_price"] = float(max_price)
        
        # Order by score (relevance) first, then add some randomness and popularity
        query += """
        ORDER BY score DESC, rand() * 0.5 + COALESCE(p.visited_num, 0) * 0.5 DESC
        LIMIT $limit
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            COALESCE(p.visited_num, 0) as visited_num,
            score
        """
        
        # Execute query
        result = await self.query(query, params)
        logger.info(f"Query returned {len(result) if result else 0} products")
        
        # Process results into product objects
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            if not product_id:
                continue
                
            # Create product object
            product_obj = {
                "id": product_id,
                "title": record.get("title", ""),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0),
                "score": record.get("score", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products matching filters")
        return products




    async def _get_product_categories(self, product_id):
        """
        Get categories for a specific product.
        
        Args:
            product_id: Product ID
            
        Returns:
            List of category names
        """
        if not product_id:
            return []
            
        query = """
        MATCH (p:Product {id: $product_id})-[:IN_CATEGORY]->(c:Category)
        RETURN c.title as category
        """
        
        result = await self.query(query, {"product_id": product_id})
        
        if not result:
            return []
            
        return [record.get("category") for record in result if record.get("category")]
    
    async def get_product_details(self, product_id):
        """
        Get detailed information about a specific product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Dictionary with product details
        """
        logger.info(f"Getting details for product {product_id}")
        
        if not product_id:
            logger.error("No product ID provided")
            return None
            
        # Query product information
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
        
        result = await self.query(query, {"product_id": product_id})
        
        if not result or len(result) == 0:
            logger.warning(f"Product not found: {product_id}")
            return None
            
        product = result[0]
        
        # Get categories
        categories = await self._get_product_categories(product_id)
        
        # Get tags
        tags_query = """
        MATCH (p:Product {id: $product_id})-[:TAGGED_WITH]->(t:Tag)
        RETURN t.title as tag
        """
        
        tags_result = await self.query(tags_query, {"product_id": product_id})
        tags = [record.get("tag") for record in tags_result if record.get("tag")]
        
        # Get collections
        collections_query = """
        MATCH (p:Product {id: $product_id})-[:IN_COLLECTION]->(c:Collection)
        RETURN c.title as collection
        """
        
        collections_result = await self.query(collections_query, {"product_id": product_id})
        collections = [record.get("collection") for record in collections_result if record.get("collection")]
        
        # Create detailed product object
        product_details = {
            "id": product.get("id", ""),
            "title": product.get("title", "Untitled Product"),
            "price": product.get("price", 0.0),
            "description": product.get("description", ""),
            "images": self._parse_images(product.get("images", "[]")),
            "categories": categories,
            "tags": tags,
            "collections": collections,
            "visited_num": product.get("visited_num", 0),
            # Add feature attributes derived from tags
            "features": tags,  # Use tags as features since we don't have explicit features
            "brand": self._extract_brand_from_tags(tags)
        }
        
        # Increment the visit counter for this product
        await self._increment_product_visit(product_id)
        
        return product_details
    
    async def _increment_product_visit(self, product_id):
        """
        Increment the visit counter for a product.
        
        Args:
            product_id: Product ID
        """
        try:
            query = """
            MATCH (p:Product {id: $product_id})
            SET p.visited_num = COALESCE(p.visited_num, 0) + 1
            """
            
            await self.query(query, {"product_id": product_id})
        except Exception as e:
            logger.error(f"Failed to increment visit counter: {e}")
    
    def _extract_brand_from_tags(self, tags):
        """
        Extract a potential brand from tags.
        
        Args:
            tags: List of tags
            
        Returns:
            Potential brand name or None
        """
        if not tags:
            return None
            
        # Look for tags that might represent brands
        # This is a heuristic approach since we don't have explicit brand nodes
        potential_brands = []
        for tag in tags:
            # Simple heuristic: tags that are capitalized and not common categories
            # are likely to be brand names
            common_categories = ["women", "men", "accessories", "jewelry", "clothing", 
                               "summer", "winter", "fall", "spring", "sale"]
            
            if tag and tag[0].isupper() and tag.lower() not in common_categories:
                potential_brands.append(tag)
        
        if potential_brands:
            return potential_brands[0]  # Return the first potential brand
        
        return None
    
    async def get_similar_products(self, product_id, limit=5):
        """
        Get products similar to a given product.
        
        Args:
            product_id: Reference product ID
            limit: Maximum number of similar products to return
            
        Returns:
            List of similar products
        """
        logger.info(f"Finding products similar to {product_id}")
        
        if not product_id:
            logger.error("No product ID provided")
            return []
            
        # Get the categories and tags of the reference product
        product_details = await self.get_product_details(product_id)
        
        if not product_details:
            logger.warning(f"Reference product not found: {product_id}")
            return []
            
        categories = product_details.get("categories", [])
        tags = product_details.get("tags", [])
        
        if not categories and not tags:
            logger.warning(f"Reference product has no categories or tags")
            return []
            
        # Build a query to find products with similar categories and tags
        query_parts = ["MATCH (p:Product)"]
        where_clauses = ["p.id <> $product_id"]  # Exclude the reference product
        params = {"product_id": product_id, "limit": limit}
        
        # Add category matching if available
        if categories:
            query_parts.append("MATCH (p)-[:IN_CATEGORY]->(c:Category)")
            where_clauses.append("c.title IN $categories")
            params["categories"] = categories
        
        # Add tag matching if available
        if tags:
            query_parts.append("MATCH (p)-[:TAGGED_WITH]->(t:Tag)")
            where_clauses.append("t.title IN $tags")
            params["tags"] = tags
        
        # Add WHERE clause
        query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        # Complete the query
        query = "\n".join(query_parts)
        query += """
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num,
            COUNT(DISTINCT c) + COUNT(DISTINCT t) as similarity_score
        ORDER BY similarity_score DESC, p.visited_num DESC
        LIMIT $limit
        """
        
        # Execute the query
        result = await self.query(query, params)
        
        if not result:
            logger.warning(f"No similar products found")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0),
                "similarity_score": record.get("similarity_score", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Found {len(products)} similar products")
        return products
    
    async def get_popular_products(self, limit=5):
        """
        Get the most popular products based on visit count.
        
        Args:
            limit: Maximum number of products to return
            
        Returns:
            List of popular products
        """
        logger.info(f"Getting popular products (limit={limit})")
        
        query = """
        MATCH (p:Product)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"limit": limit})
        
        if not result:
            logger.warning("No popular products found")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} popular products")
        return products
    
    async def get_products_by_category(self, category, limit=5):
        """
        Get products in a specific category.
        
        Args:
            category: Category name
            limit: Maximum number of products to return
            
        Returns:
            List of products in the category
        """
        logger.info(f"Getting products in category: {category}")
        
        if not category:
            logger.error("No category provided")
            return []
        
        query = """
        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
        WHERE toLower(c.title) CONTAINS toLower($category)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"category": category, "limit": limit})
        
        if not result:
            logger.warning(f"No products found in category: {category}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products in category: {category}")
        return products
    
    async def get_products_by_collection(self, collection, limit=5):
        """
        Get products in a specific collection.
        
        Args:
            collection: Collection name
            limit: Maximum number of products to return
            
        Returns:
            List of products in the collection
        """
        logger.info(f"Getting products in collection: {collection}")
        
        if not collection:
            logger.error("No collection provided")
            return []
        
        query = """
        MATCH (p:Product)-[:IN_COLLECTION]->(c:Collection)
        WHERE toLower(c.title) CONTAINS toLower($collection)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"collection": collection, "limit": limit})
        
        if not result:
            logger.warning(f"No products found in collection: {collection}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products in collection: {collection}")
        return products
    
    async def get_products_by_tag(self, tag, limit=5):
        """
        Get products with a specific tag.
        
        Args:
            tag: Tag name
            limit: Maximum number of products to return
            
        Returns:
            List of products with the tag
        """
        logger.info(f"Getting products with tag: {tag}")
        
        if not tag:
            logger.error("No tag provided")
            return []
        
        query = """
        MATCH (p:Product)-[:TAGGED_WITH]->(t:Tag)
        WHERE toLower(t.title) CONTAINS toLower($tag)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"tag": tag, "limit": limit})
        
        if not result:
            logger.warning(f"No products found with tag: {tag}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products with tag: {tag}")
        return products
    
    async def get_trending_products(self, limit=5, days=30):
        """
        Get trending products based on recent visits.
        
        Args:
            limit: Maximum number of products to return
            days: Number of days to consider for trending
            
        Returns:
            List of trending products
        """
        logger.info(f"Getting trending products for last {days} days")
        
        # Get products with highest visit counts
        # In a real implementation, you'd filter by recent interactions
        query = """
        MATCH (p:Product)
        WHERE p.visited_num IS NOT NULL AND p.visited_num > 0
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"limit": limit})
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0),
                "trending": True
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} trending products")
        return products