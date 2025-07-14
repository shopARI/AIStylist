"""
User Knowledge Graph for AI Stylist
Neo4j integration focused exclusively on user data, preferences, and interactions.
Products have been migrated to Qdrant.
"""

import logging
import json
import datetime
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
import uuid

logger = logging.getLogger("user_knowledge_graph")

try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    logger.warning("neo4j AsyncGraphDatabase not available")
    NEO4J_AVAILABLE = False
    
    # Mock implementation for development
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


class UserKnowledgeGraphAsync:
    """
    Neo4j integration focused on user data management.
    All product operations have been removed - products are now in Qdrant only.
    """
    
    def __init__(self, url, username, password):
        """Initialize with connection pooling and timeout settings."""
        logger.info(f"Initializing User Knowledge Graph connection to {url}")
        self.url = url
        self.username = username
        self.password = password
        self.driver = None
        
        # Connection settings
        self.query_timeout = 30.0
        self.max_retry_attempts = 3
        self.retry_delay = 1.0
        
        # Query concurrency control
        self._query_lock = asyncio.Semaphore(10)
        
        # Initialize connection
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize connection with retry logic."""
        for attempt in range(self.max_retry_attempts):
            try:
                if NEO4J_AVAILABLE:
                    self.driver = AsyncGraphDatabase.driver(
                        self.url, 
                        auth=(self.username, self.password),
                        max_connection_lifetime=300,
                        max_connection_pool_size=50,
                        connection_timeout=10,
                        resolver=None
                    )
                    logger.info("Successfully initialized Neo4j driver for users")
                    return
                else:
                    logger.warning("Neo4j not available, using mock driver")
                    self.driver = AsyncGraphDatabase.driver(self.url, auth=(self.username, self.password))
                    return
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retry_attempts - 1:
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
                logger.info("User Knowledge Graph connection closed successfully")
            except asyncio.TimeoutError:
                logger.warning("Neo4j connection close timed out")
            except Exception as e:
                logger.error(f"Error closing Neo4j connection: {e}")
    
    async def query(self, query_str, params=None, timeout=None):
        """Execute a Cypher query with timeout and error handling."""
        if not self.driver:
            logger.error("No active Neo4j connection")
            return []
        
        timeout = timeout or self.query_timeout
        params = params or {}
        
        async with self._query_lock:
            for attempt in range(self.max_retry_attempts):
                try:
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
        """Create schema focused on user data and relationships."""
        if not self.driver:
            logger.error("No active Neo4j connection")
            return False
        
        try:
            # User-focused constraints
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MemoryState) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:UserPreference) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (i:ProductInteraction) REQUIRE i.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (s:StyleProfile) REQUIRE s.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (seg:UserSegment) REQUIRE seg.name IS UNIQUE"
            ]
            
            # Indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.created_at)",
                "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.last_active)",
                "CREATE INDEX IF NOT EXISTS FOR (i:ProductInteraction) ON (i.timestamp)",
                "CREATE INDEX IF NOT EXISTS FOR (i:ProductInteraction) ON (i.type)",
                "CREATE INDEX IF NOT EXISTS FOR (p:UserPreference) ON (p.type)",
                "CREATE INDEX IF NOT EXISTS FOR (p:UserPreference) ON (p.updated_at)"
            ]
            
            # Create constraints
            for constraint in constraints:
                try:
                    await asyncio.wait_for(self.query(constraint), timeout=15.0)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.error(f"Error creating constraint: {e}")
            
            # Create indexes
            for index in indexes:
                try:
                    await asyncio.wait_for(self.query(index), timeout=15.0)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.error(f"Error creating index: {e}")
            
            logger.info("User schema creation completed")
            return True
            
        except Exception as e:
            logger.error(f"Error in schema creation: {e}")
            return False
    
    # ==================== USER OPERATIONS ====================
    
    async def create_or_update_user(self, user_id: str, user_data: Optional[Dict[str, Any]] = None) -> bool:
        """Create or update user with enhanced profile data."""
        if not user_id:
            logger.error("No user ID provided")
            return False
        
        try:
            query = """
            MERGE (u:User {id: $user_id})
            SET u.last_active = $timestamp,
                u.updated_at = $timestamp
            WITH u
            FOREACH (ignoreMe IN CASE WHEN u.created_at IS NULL THEN [1] ELSE [] END |
                SET u.created_at = $timestamp
            )
            """
            
            params = {
                "user_id": user_id,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Add additional user data if provided
            if user_data:
                for key, value in user_data.items():
                    if key not in ["id", "created_at"]:  # Protect immutable fields
                        query += f"\nSET u.{key} = ${key}"
                        params[key] = value
            
            query += "\nRETURN u.id as user_id"
            
            result = await self.query(query, params, timeout=5.0)
            
            return bool(result and result[0].get("user_id") == user_id)
            
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            return False
    
    async def get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive user details including preferences and segments."""
        if not user_id:
            logger.error("No user ID provided")
            return None
        
        try:
            query = """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:HAS_PREFERENCE]->(p:UserPreference)
            OPTIONAL MATCH (u)-[:BELONGS_TO]->(seg:UserSegment)
            OPTIONAL MATCH (u)-[:HAS_STYLE]->(style:StyleProfile)
            WITH u, 
                 collect(DISTINCT {type: p.type, value: p.value, updated_at: p.updated_at}) as preferences,
                 collect(DISTINCT seg.name) as segments,
                 style
            RETURN 
                u.id as id,
                u.created_at as created_at,
                u.last_active as last_active,
                u.email as email,
                u.name as name,
                u.location as location,
                u.age_group as age_group,
                u.gender as gender,
                preferences,
                segments,
                style.profile as style_profile,
                style.updated_at as style_updated_at
            """
            
            result = await self.query(query, {"user_id": user_id}, timeout=10.0)
            
            if not result:
                logger.warning(f"User not found: {user_id}")
                return None
            
            user_data = result[0]
            
            # Clean up preferences
            clean_preferences = {}
            for pref in user_data.get("preferences", []):
                if pref.get("type") and pref.get("value"):
                    clean_preferences[pref["type"]] = pref["value"]
            
            user_data["preferences"] = clean_preferences
            
            return user_data
            
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return None
    
    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get structured user preferences."""
        if not user_id:
            return {}
        
        try:
            query = """
            MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(p:UserPreference)
            RETURN p.type as type, p.value as value, p.confidence as confidence
            ORDER BY p.updated_at DESC
            """
            
            result = await self.query(query, {"user_id": user_id})
            
            preferences = {
                "preferred_categories": [],
                "preferred_brands": [],
                "preferred_colors": [],
                "preferred_tags": [],
                "budget_range": {},
                "size_preferences": {},
                "style_attributes": []
            }
            
            for record in result:
                pref_type = record.get("type")
                pref_value = record.get("value")
                
                if pref_type == "category":
                    preferences["preferred_categories"].append(pref_value)
                elif pref_type == "brand":
                    preferences["preferred_brands"].append(pref_value)
                elif pref_type == "color":
                    preferences["preferred_colors"].append(pref_value)
                elif pref_type == "tag":
                    preferences["preferred_tags"].append(pref_value)
                elif pref_type == "budget_min":
                    preferences["budget_range"]["min"] = float(pref_value)
                elif pref_type == "budget_max":
                    preferences["budget_range"]["max"] = float(pref_value)
                elif pref_type == "size":
                    size_data = json.loads(pref_value) if isinstance(pref_value, str) else pref_value
                    preferences["size_preferences"].update(size_data)
                elif pref_type == "style":
                    preferences["style_attributes"].append(pref_value)
            
            return preferences
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}
    
    async def update_user_preference(
        self,
        user_id: str,
        preference_type: str,
        preference_value: Any,
        confidence: float = 1.0
    ) -> bool:
        """Update or create a user preference."""
        try:
            pref_id = f"{user_id}_{preference_type}"
            
            query = """
            MATCH (u:User {id: $user_id})
            MERGE (p:UserPreference {id: $pref_id})
            SET p.type = $type,
                p.value = $value,
                p.confidence = $confidence,
                p.updated_at = $timestamp
            MERGE (u)-[:HAS_PREFERENCE]->(p)
            RETURN p.id as pref_id
            """
            
            params = {
                "user_id": user_id,
                "pref_id": pref_id,
                "type": preference_type,
                "value": json.dumps(preference_value) if isinstance(preference_value, (dict, list)) else str(preference_value),
                "confidence": confidence,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            result = await self.query(query, params)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error updating user preference: {e}")
            return False
    
    # ==================== INTERACTION OPERATIONS ====================
    
    async def record_product_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Record user interaction with a product."""
        try:
            interaction_id = f"{user_id}_{product_id}_{interaction_type}_{datetime.datetime.now().timestamp()}"
            
            query = """
            MATCH (u:User {id: $user_id})
            CREATE (i:ProductInteraction {
                id: $interaction_id,
                product_id: $product_id,
                type: $interaction_type,
                timestamp: $timestamp,
                metadata: $metadata
            })
            CREATE (u)-[:HAS_INTERACTION]->(i)
            
            // Update interaction counts
            WITH u, i
            SET u.total_interactions = COALESCE(u.total_interactions, 0) + 1,
                u.last_interaction = $timestamp
            
            // Create or update interaction type count
            WITH u, i
            CALL apoc.create.setProperty(u, $interaction_type + '_count', 
                COALESCE(u[$interaction_type + '_count'], 0) + 1) 
            YIELD node
            
            RETURN i.id as interaction_id
            """
            
            # Fallback query without APOC
            fallback_query = """
            MATCH (u:User {id: $user_id})
            CREATE (i:ProductInteraction {
                id: $interaction_id,
                product_id: $product_id,
                type: $interaction_type,
                timestamp: $timestamp,
                metadata: $metadata
            })
            CREATE (u)-[:HAS_INTERACTION]->(i)
            SET u.total_interactions = COALESCE(u.total_interactions, 0) + 1,
                u.last_interaction = $timestamp
            RETURN i.id as interaction_id
            """
            
            params = {
                "user_id": user_id,
                "product_id": product_id,
                "interaction_id": interaction_id,
                "interaction_type": interaction_type,
                "timestamp": datetime.datetime.now().isoformat(),
                "metadata": json.dumps(metadata) if metadata else "{}"
            }
            
            # Try with APOC first, fallback if not available
            try:
                result = await self.query(query, params)
            except Exception:
                result = await self.query(fallback_query, params)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error recording product interaction: {e}")
            return False
    
    async def get_user_interactions(
        self,
        user_id: str,
        interaction_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user's product interactions."""
        try:
            if interaction_type:
                query = """
                MATCH (u:User {id: $user_id})-[:HAS_INTERACTION]->(i:ProductInteraction {type: $type})
                RETURN i.product_id as product_id,
                       i.type as type,
                       i.timestamp as timestamp,
                       i.metadata as metadata
                ORDER BY i.timestamp DESC
                SKIP $offset LIMIT $limit
                """
                params = {
                    "user_id": user_id,
                    "type": interaction_type,
                    "limit": limit,
                    "offset": offset
                }
            else:
                query = """
                MATCH (u:User {id: $user_id})-[:HAS_INTERACTION]->(i:ProductInteraction)
                RETURN i.product_id as product_id,
                       i.type as type,
                       i.timestamp as timestamp,
                       i.metadata as metadata
                ORDER BY i.timestamp DESC
                SKIP $offset LIMIT $limit
                """
                params = {
                    "user_id": user_id,
                    "limit": limit,
                    "offset": offset
                }
            
            result = await self.query(query, params)
            
            # Parse metadata
            interactions = []
            for record in result:
                interaction = dict(record)
                if interaction.get("metadata"):
                    try:
                        interaction["metadata"] = json.loads(interaction["metadata"])
                    except:
                        interaction["metadata"] = {}
                interactions.append(interaction)
            
            return interactions
            
        except Exception as e:
            logger.error(f"Error getting user interactions: {e}")
            return []
    
    # ==================== SEGMENTATION OPERATIONS ====================
    
    async def assign_user_segment(self, user_id: str, segment_name: str) -> bool:
        """Assign user to a segment for targeted recommendations."""
        try:
            query = """
            MATCH (u:User {id: $user_id})
            MERGE (seg:UserSegment {name: $segment_name})
            ON CREATE SET seg.created_at = $timestamp
            MERGE (u)-[:BELONGS_TO]->(seg)
            RETURN seg.name as segment
            """
            
            params = {
                "user_id": user_id,
                "segment_name": segment_name,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            result = await self.query(query, params)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error assigning user segment: {e}")
            return False
    
    async def get_user_segments(self, user_id: str) -> List[str]:
        """Get all segments a user belongs to."""
        try:
            query = """
            MATCH (u:User {id: $user_id})-[:BELONGS_TO]->(seg:UserSegment)
            RETURN seg.name as segment
            ORDER BY seg.name
            """
            
            result = await self.query(query, {"user_id": user_id})
            return [r["segment"] for r in result]
            
        except Exception as e:
            logger.error(f"Error getting user segments: {e}")
            return []
    
    # ==================== ANALYTICS OPERATIONS ====================
    
    async def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive user statistics."""
        try:
            query = """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:HAS_INTERACTION]->(i:ProductInteraction)
            WITH u, count(i) as total_interactions,
                 collect(DISTINCT i.type) as interaction_types
            OPTIONAL MATCH (u)-[:HAS_PREFERENCE]->(p:UserPreference)
            WITH u, total_interactions, interaction_types, count(p) as preference_count
            RETURN {
                user_id: u.id,
                created_at: u.created_at,
                last_active: u.last_active,
                total_interactions: total_interactions,
                interaction_types: interaction_types,
                preference_count: preference_count,
                days_active: duration.between(datetime(u.created_at), datetime()).days
            } as stats
            """
            
            result = await self.query(query, {"user_id": user_id})
            
            if result:
                return result[0]["stats"]
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {}
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """Get database statistics for users only."""
        stats = {
            "user_statistics": {}
        }
        
        try:
            # User counts
            user_queries = [
                ("user_count", "MATCH (n:User) RETURN count(n) as count"),
                ("interaction_count", "MATCH (n:ProductInteraction) RETURN count(n) as count"),
                ("preference_count", "MATCH (n:UserPreference) RETURN count(n) as count"),
                ("segment_count", "MATCH (n:UserSegment) RETURN count(n) as count"),
            ]
            
            for stat_name, query in user_queries:
                try:
                    result = await self.query(query, timeout=5.0)
                    if result:
                        stats["user_statistics"][stat_name] = result[0]["count"]
                except Exception as e:
                    logger.debug(f"Could not get {stat_name}: {e}")
                    stats["user_statistics"][stat_name] = 0
            
            # Active users
            active_query = """
            MATCH (u:User)
            WHERE u.last_active > datetime() - duration('P30D')
            RETURN count(u) as count
            """
            
            try:
                result = await self.query(active_query, timeout=5.0)
                if result:
                    stats["user_statistics"]["active_users_30d"] = result[0]["count"]
            except:
                stats["user_statistics"]["active_users_30d"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {"error": str(e)}
    
    async def cleanup_inactive_users(self, days_inactive: int = 365) -> int:
        """Clean up data for inactive users."""
        try:
            query = """
            MATCH (u:User)
            WHERE u.last_active < datetime() - duration($duration)
            WITH u
            OPTIONAL MATCH (u)-[r]->(n)
            DELETE r, n
            DELETE u
            RETURN count(u) as deleted_count
            """
            
            params = {
                "duration": f"P{days_inactive}D"
            }
            
            result = await self.query(query, params)
            
            if result:
                deleted = result[0]["deleted_count"]
                logger.info(f"Cleaned up {deleted} inactive users")
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
            return 0