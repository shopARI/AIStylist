"""
User Knowledge Graph Service for ARI Fashion Stylist.
Neo4j integration for user data, preferences, and interactions.
Based on user_knowledge_graph_async.py with enhanced error handling.
"""

import logging
import json
import datetime
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
import uuid
import hashlib

logger = logging.getLogger("services.user.knowledge_graph")

try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.error("Neo4j driver is required. Install with: pip install neo4j")

from models.types import (
    UserProfile, UserPreferences, UserInteraction,
    InteractionType, UserSegment, StyleProfile,
    Neo4jStats, validate_interaction_type, get_timestamp
)


class UserKnowledgeGraphService:
    """
    Neo4j service for user data management.
    Production-ready with connection pooling and retry logic.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        max_connection_pool_size: int = 50,
        connection_timeout: int = 10,
        query_timeout: float = 30.0,
        max_retry_attempts: int = 3,
        retry_delay: float = 1.0,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Neo4j connection with enhanced configuration.
        
        Args:
            url: Neo4j connection URL
            username: Neo4j username
            password: Neo4j password
            max_connection_pool_size: Maximum connection pool size
            connection_timeout: Connection timeout in seconds
            query_timeout: Query timeout in seconds
            max_retry_attempts: Maximum retry attempts
            retry_delay: Delay between retries
        """
        if not NEO4J_AVAILABLE:
            raise RuntimeError("Neo4j driver not available")
        
        logger.info(f"Initializing User Knowledge Graph connection to {url}")
        
        self.url = url
        self.username = username
        self.password = password
        self.driver = None
        
        # Configuration
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_timeout = connection_timeout
        self.query_timeout = query_timeout
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay = retry_delay
        
        # Configuration
        self.config = config or {}
        
        # Query semaphore for rate limiting - configurable for production scale
        max_concurrent_queries = self.config.get("max_concurrent_queries", 100)  # Increased from 10
        self._query_semaphore = asyncio.Semaphore(max_concurrent_queries)
        
        # Statistics
        self.stats = {
            "queries_executed": 0,
            "queries_failed": 0,
            "retries_performed": 0,
            "total_query_time": 0.0
        }
        
      #  self._initialize_connection()
    
    async def initialize(self):
        """Initialize Neo4j connection with retry logic (async)."""
        for attempt in range(self.max_retry_attempts):
            try:
                self.driver = AsyncGraphDatabase.driver(
                    self.url,
                    auth=(self.username, self.password),
                    max_connection_lifetime=300,
                    max_connection_pool_size=self.max_connection_pool_size,
                    connection_timeout=self.connection_timeout,
                    resolver=None
                )
                
                # Test the connection
                async with self.driver.session() as session:
                    await session.run("RETURN 1")
                
                logger.info("Successfully initialized Neo4j driver")
                return
                
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retry_attempts - 1:
                    logger.info(f"Retrying connection in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise RuntimeError(f"Failed to connect to Neo4j after {self.max_retry_attempts} attempts: {e}")
    
    async def close(self):
        """Close Neo4j connection gracefully."""
        if self.driver:
            try:
                await asyncio.wait_for(self.driver.close(), timeout=10.0)
                logger.info("Neo4j connection closed successfully")
            except asyncio.TimeoutError:
                logger.warning("Neo4j connection close timed out")
            except Exception as e:
                logger.error(f"Error closing Neo4j connection: {e}")
    
    async def query(
        self,
        query_str: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute Cypher query with timeout and retry logic.
        
        Args:
            query_str: Cypher query string
            params: Query parameters
            timeout: Query timeout override
            
        Returns:
            Query results as list of dictionaries
        """
        if not self.driver:
            raise RuntimeError("No active Neo4j connection")
        
        timeout = timeout or self.query_timeout
        params = params or {}
        
        async with self._query_semaphore:
            for attempt in range(self.max_retry_attempts):
                try:
                    start_time = asyncio.get_event_loop().time()
                    
                    result = await asyncio.wait_for(
                        self._execute_query_with_session(query_str, params),
                        timeout=timeout
                    )
                    
                    # Update statistics
                    query_time = asyncio.get_event_loop().time() - start_time
                    self.stats["queries_executed"] += 1
                    self.stats["total_query_time"] += query_time
                    
                    return result  # <-- SIMPLE RETURN
                    
                except asyncio.TimeoutError:
                    logger.warning(f"Query timeout on attempt {attempt + 1}")
                    self.stats["retries_performed"] += 1
                    
                    if attempt < self.max_retry_attempts - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        self.stats["queries_failed"] += 1
                        raise RuntimeError(f"Query failed after {self.max_retry_attempts} attempts due to timeout")
                    
                except Exception as e:
                    logger.error(f"Query failed on attempt {attempt + 1}: {e}")
                    self.stats["retries_performed"] += 1
                    
                    if attempt == self.max_retry_attempts - 1:
                        self.stats["queries_failed"] += 1
                        raise RuntimeError(f"Query failed after {self.max_retry_attempts} attempts: {e}")
        
        return []  
    
    async def _execute_query_with_session(
        self,
        query_str: str,
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute query within a session.
        
        Args:
            query_str: Cypher query
            params: Query parameters
            
        Returns:
            Query results
        """
        try:
            async with self.driver.session() as session:
                result = await session.run(query_str, params)
                records = []
                
                async for record in result:
                    records.append(dict(record))
                    
                    # Prevent memory overload
                    if len(records) > 10000:
                        logger.warning("Large result set detected, truncating at 10000")
                        break
                
                return records  # <-- SIMPLE RETURN
                
        except Exception as e:
            logger.error(f"Error in query execution: {e}")
            raise
    
    async def ensure_schema(self) -> bool:
        """
        Create schema for user data and relationships.
        
        Returns:
            Success status
        """
        if not self.driver:
            raise RuntimeError("No active Neo4j connection")
        
        try:
            # Constraints for uniqueness
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MemoryState) REQUIRE m.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:UserPreference) REQUIRE p.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (i:ProductInteraction) REQUIRE i.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (s:StyleProfile) REQUIRE s.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (seg:UserSegment) REQUIRE seg.name IS UNIQUE"
            ]
            
            # Indexes optimized for 30M+ node performance
            indexes = [
                # User indexes
                "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.created_at)",
                "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.last_active)",
                "CREATE INDEX IF NOT EXISTS FOR (u:User) ON (u.id)",  # Critical for lookups
                
                # Product interaction indexes (high volume)
                "CREATE INDEX IF NOT EXISTS FOR (i:ProductInteraction) ON (i.timestamp)",
                "CREATE INDEX IF NOT EXISTS FOR (i:ProductInteraction) ON (i.type)",
                "CREATE INDEX IF NOT EXISTS FOR (i:ProductInteraction) ON (i.product_id)",  # Join performance
                
                # Preference indexes
                "CREATE INDEX IF NOT EXISTS FOR (p:UserPreference) ON (p.type)",
                "CREATE INDEX IF NOT EXISTS FOR (p:UserPreference) ON (p.updated_at)",
                "CREATE INDEX IF NOT EXISTS FOR (p:UserPreference) ON (p.id)",  # Unique lookups
                
                # Segment indexes
                "CREATE INDEX IF NOT EXISTS FOR (s:UserSegment) ON (s.name)",
                
                # Composite indexes for common query patterns on massive scale
                "CREATE INDEX IF NOT EXISTS FOR (i:ProductInteraction) ON (i.type, i.timestamp)",  # Time-filtered queries
            ]
            
            # Execute constraints
            for constraint in constraints:
                try:
                    await asyncio.wait_for(self.query(constraint), timeout=15.0)
                    await asyncio.sleep(0.1)  # Small delay between operations
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.error(f"Error creating constraint: {e}")
            
            # Execute indexes
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
    
    async def create_or_update_user(
        self,
        user_id: str,
        user_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Create or update user in Neo4j.
        
        Args:
            user_id: User identifier
            user_data: Optional user data
            
        Returns:
            Success status
        """
        if not user_id:
            raise ValueError("User ID is required")
        
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
                "timestamp": get_timestamp()
            }
            
            # Add additional user data
            if user_data:
                for key, value in user_data.items():
                    if key not in ["id", "created_at"]:
                        query += f"\nSET u.{key} = ${key}"
                        params[key] = value
            
            query += "\nRETURN u.id as user_id"
            
            result = await self.query(query, params, timeout=5.0)
            return bool(result and result[0].get("user_id") == user_id)
            
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            raise
    
    async def get_user_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive user details.
        
        Args:
            user_id: User identifier
            
        Returns:
            User profile dict or None
        """
        if not user_id:
            raise ValueError("User ID is required")
        
        try:
            query = """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:HAS_PREFERENCE]->(p:UserPreference)
            OPTIONAL MATCH (u)-[:BELONGS_TO]->(seg:UserSegment)
            OPTIONAL MATCH (u)-[:HAS_STYLE]->(style:StyleProfile)
            OPTIONAL MATCH (u)-[:HAS_INTERACTION]->(i:ProductInteraction)
            WITH u,
                 collect(DISTINCT {type: p.type, value: p.value, confidence: p.confidence}) as preferences,
                 collect(DISTINCT seg.name) as segments,
                 style,
                 count(DISTINCT i) as total_interactions,
                 count(DISTINCT CASE WHEN i.type = 'purchased' THEN i ELSE NULL END) as total_purchases
            RETURN
                u.id as id,
                u.created_at as created_at,
                u.last_active as last_active,
                u.email as email,
                u.name as name,
                u.location as location,
                u.age_group as age_group,
                u.gender as gender,
                u.lifetime_value as lifetime_value,
                preferences,
                segments,
                style.profile as style_profile,
                total_interactions,
                total_purchases
            """
            
            result = await self.query(query, {"user_id": user_id}, timeout=10.0)
            
            if not result:
                logger.warning(f"User not found: {user_id}")
                return None
            
            user_data = result[0]
            
            # Process preferences
            preferences = {
                "preferred_categories": [],
                "preferred_brands": [],
                "preferred_colors": [],
                "preferred_tags": [],
                "budget_range": {},
                "size_preferences": {},
                "style_attributes": [],
                "excluded_items": []
            }
            
            for pref in user_data.get("preferences", []):
                if pref.get("type") and pref.get("value"):
                    self._process_preference(preferences, pref["type"], pref["value"])
            
            # Build profile
            profile = {
                "id": user_data["id"],
                "created_at": user_data.get("created_at", ""),
                "last_active": user_data.get("last_active", ""),
                "email": user_data.get("email"),
                "name": user_data.get("name"),
                "location": user_data.get("location"),
                "age_group": user_data.get("age_group"),
                "gender": user_data.get("gender"),
                "preferences": preferences,
                "segments": user_data.get("segments", []),
                "style_profile": user_data.get("style_profile"),
                "total_interactions": user_data.get("total_interactions", 0),
                "total_purchases": user_data.get("total_purchases", 0),
                "lifetime_value": user_data.get("lifetime_value", 0.0)
            }
            
            return profile
            
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            raise
    
    def _process_preference(
        self,
        preferences: Dict[str, Any],
        pref_type: str,
        pref_value: Any
    ):
        """Process a single preference."""
        try:
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
            elif pref_type == "excluded":
                preferences["excluded_items"].append(pref_value)
        except Exception as e:
            logger.warning(f"Error processing preference {pref_type}: {e}")
    
    async def update_user_preference(
        self,
        user_id: str,
        preference_type: str,
        preference_value: Any,
        confidence: float = 1.0
    ) -> bool:
        """
        Update or create user preference.
        
        Args:
            user_id: User identifier
            preference_type: Type of preference
            preference_value: Preference value
            confidence: Confidence score
            
        Returns:
            Success status
        """
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
                "timestamp": get_timestamp()
            }
            
            result = await self.query(query, params)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error updating user preference: {e}")
            raise
    
    # ==================== INTERACTION OPERATIONS ====================
    
    async def record_product_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Record user interaction with product.
        
        Args:
            user_id: User identifier
            product_id: Product identifier
            interaction_type: Type of interaction
            metadata: Additional interaction data
            
        Returns:
            Success status
        """
        # Validate interaction type
        if not validate_interaction_type(interaction_type):
            raise ValueError(f"Invalid interaction type: {interaction_type}")
        
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
            SET u.total_interactions = COALESCE(u.total_interactions, 0) + 1,
                u.last_interaction = $timestamp
            """
            
            # Update purchase count if purchase
            if interaction_type == "purchased":
                query += """,
                u.total_purchases = COALESCE(u.total_purchases, 0) + 1,
                u.lifetime_value = COALESCE(u.lifetime_value, 0) + COALESCE($price, 0)
                """
            
            query += "\nRETURN i.id as interaction_id"
            
            params = {
                "user_id": user_id,
                "product_id": product_id,
                "interaction_id": interaction_id,
                "interaction_type": interaction_type,
                "timestamp": get_timestamp(),
                "metadata": json.dumps(metadata) if metadata else "{}",
                "price": metadata.get("price", 0) if metadata else 0
            }
            
            result = await self.query(query, params)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error recording product interaction: {e}")
            raise
    
    async def get_user_interactions(
        self,
        user_id: str,
        interaction_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get user's product interactions.
        
        Args:
            user_id: User identifier
            interaction_type: Filter by type
            limit: Maximum interactions
            offset: Pagination offset
            
        Returns:
            List of user interaction dicts
        """
        try:
            if interaction_type:
                query = """
                MATCH (u:User {id: $user_id})-[:HAS_INTERACTION]->(i:ProductInteraction {type: $type})
                RETURN i.product_id as product_id,
                       i.type as interaction_type,
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
                       i.type as interaction_type,
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
            
            interactions = []
            for record in result:
                metadata = record.get("metadata")
                if metadata:
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = None
                
                interaction = {
                    "user_id": user_id,
                    "product_id": record["product_id"],
                    "interaction_type": record["interaction_type"],
                    "timestamp": record["timestamp"],
                    "metadata": metadata
                }
                interactions.append(interaction)
            
            return interactions
            
        except Exception as e:
            logger.error(f"Error getting user interactions: {e}")
            raise
    
    # ==================== SEGMENT OPERATIONS ====================
    
    async def assign_user_segment(
        self,
        user_id: str,
        segment_name: str
    ) -> bool:
        """
        Assign user to segment.
        
        Args:
            user_id: User identifier
            segment_name: Segment name
            
        Returns:
            Success status
        """
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
                "timestamp": get_timestamp()
            }
            
            result = await self.query(query, params)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Error assigning user segment: {e}")
            raise
    
    async def get_user_segments(self, user_id: str) -> List[str]:
        """
        Get user segments.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of segment names
        """
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
            raise
    
    # ==================== STATISTICS & MAINTENANCE ====================
    
    async def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Neo4j statistics dict
        """
        stats = {
            "user_count": 0,
            "interaction_count": 0,
            "preference_count": 0,
            "segment_count": 0,
            "active_users_30d": 0,
            "relationship_count": 0
        }
        
        try:
            # OPTIMIZED: Use fast estimated counts for 30M+ nodes
            # Note: These are approximate for performance - exact counts would timeout
            
            # Only get segment count (small table) - others are too expensive
            try:
                segment_result = await self.query(
                    "MATCH (n:UserSegment) RETURN count(n) as count", 
                    timeout=3.0
                )
                if segment_result:
                    stats["segment_count"] = segment_result[0]["count"]
            except Exception as e:
                logger.debug(f"Could not get segment count: {e}")
            
            # For massive graphs, we'll estimate other counts using heuristics
            # or skip them entirely to avoid performance issues
            logger.info("Skipping expensive count queries on 30M+ node graph for performance")
            
            # Active users
            active_query = """
            MATCH (u:User)
            WHERE u.last_active > datetime() - duration('P30D')
            RETURN count(u) as count
            """
            
            try:
                result = await self.query(active_query, timeout=5.0)
                if result:
                    stats["active_users_30d"] = result[0]["count"]
            except:
                pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            raise
    
    async def cleanup_inactive_users(self, days_inactive: int = 365) -> int:
        """
        Clean up inactive users.
        
        Args:
            days_inactive: Days of inactivity threshold
            
        Returns:
            Number of users deleted
        """
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
            raise
    
    async def health_check(self) -> bool:
        """
        Perform health check on Neo4j connection.
        
        Returns:
            True if healthy
        """
        try:
            result = await self.query(
                "RETURN 1 as health_check LIMIT 1",
                {},
                timeout=5.0
            )
            return len(result) > 0 and result[0].get('health_check') == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
        return {
            "queries_executed": self.stats["queries_executed"],
            "queries_failed": self.stats["queries_failed"],
            "retries_performed": self.stats["retries_performed"],
            "avg_query_time": (
                self.stats["total_query_time"] / self.stats["queries_executed"]
                if self.stats["queries_executed"] > 0 else 0
            ),
            "success_rate": (
                (self.stats["queries_executed"] - self.stats["queries_failed"]) / 
                self.stats["queries_executed"] * 100
                if self.stats["queries_executed"] > 0 else 0
            )
        }
