"""
Redis Memory Provider for CrewAI
Integrates CrewAI memory system with existing Redis infrastructure.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import redis.asyncio as redis

logger = logging.getLogger("crewai.memory.redis_provider")


class RedisMemoryProvider:
    """
    Custom memory provider for CrewAI that uses Redis backend.
    Maintains compatibility with existing ARI production Redis structure.
    """

    def __init__(self, redis_client, session_id: str):
        """
        Initialize Redis memory provider.

        Args:
            redis_client: Redis client instance
            session_id: Current session identifier
        """
        self.redis = redis_client
        self.session_id = session_id

        # Redis key patterns matching existing structure
        self.short_term_key = f"session:{session_id}:short_term"
        self.long_term_key = f"session:{session_id}:long_term"
        self.entity_key = f"session:{session_id}:entities"

        logger.info(f"Initialized Redis memory provider for session: {session_id}")

    async def save_short_term(self, data: Dict[str, Any]) -> bool:
        """
        Save to short-term memory (current conversation).

        Args:
            data: Memory data to save

        Returns:
            Success boolean
        """
        try:
            # Add timestamp
            data['timestamp'] = datetime.now().isoformat()

            # Push to Redis list (FIFO)
            await self.redis.lpush(self.short_term_key, json.dumps(data))

            # Trim to keep last 20 items
            await self.redis.ltrim(self.short_term_key, 0, 19)

            # Set expiry (1 hour)
            await self.redis.expire(self.short_term_key, 3600)

            logger.debug(f"Saved short-term memory: {self.short_term_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to save short-term memory: {e}")
            return False

    async def load_short_term(self, limit: int = 20) -> List[Dict]:
        """
        Load from short-term memory.

        Args:
            limit: Maximum items to load

        Returns:
            List of memory items
        """
        try:
            items = await self.redis.lrange(self.short_term_key, 0, limit - 1)

            memories = []
            for item in items:
                try:
                    memories.append(json.loads(item))
                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode memory item: {item}")

            logger.debug(f"Loaded {len(memories)} short-term memories")
            return memories

        except Exception as e:
            logger.error(f"Failed to load short-term memory: {e}")
            return []

    async def save_long_term(self, key: str, value: Any) -> bool:
        """
        Save to long-term memory (cross-session persistence).

        Args:
            key: Memory key
            value: Memory value

        Returns:
            Success boolean
        """
        try:
            data = {
                "value": value,
                "timestamp": datetime.now().isoformat(),
                "session_id": self.session_id
            }

            # Store in Redis hash
            await self.redis.hset(
                self.long_term_key,
                key,
                json.dumps(data)
            )

            # Set expiry (30 days)
            await self.redis.expire(self.long_term_key, 2592000)

            logger.debug(f"Saved long-term memory: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to save long-term memory: {e}")
            return False

    async def load_long_term(self, key: Optional[str] = None) -> Any:
        """
        Load from long-term memory.

        Args:
            key: Optional specific key to load (loads all if None)

        Returns:
            Memory data
        """
        try:
            if key:
                # Load specific key
                data = await self.redis.hget(self.long_term_key, key)
                if data:
                    return json.loads(data)
                return None
            else:
                # Load all long-term memory
                items = await self.redis.hgetall(self.long_term_key)
                memories = {}
                for k, v in items.items():
                    try:
                        memories[k] = json.loads(v)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode memory for key: {k}")

                logger.debug(f"Loaded {len(memories)} long-term memories")
                return memories

        except Exception as e:
            logger.error(f"Failed to load long-term memory: {e}")
            return {} if not key else None

    async def save_entity(self, entity_type: str, entity_value: str, metadata: Optional[Dict] = None) -> bool:
        """
        Save entity to entity memory (product, brand, category, style).

        Args:
            entity_type: Type of entity (product, brand, etc.)
            entity_value: Entity value
            metadata: Optional entity metadata

        Returns:
            Success boolean
        """
        try:
            entity_key = f"{entity_type}:{entity_value}"

            entity_data = {
                "type": entity_type,
                "value": entity_value,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            }

            # Add to Redis set
            await self.redis.sadd(self.entity_key, json.dumps(entity_data))

            # Set expiry (1 hour)
            await self.redis.expire(self.entity_key, 3600)

            logger.debug(f"Saved entity: {entity_type}={entity_value}")
            return True

        except Exception as e:
            logger.error(f"Failed to save entity: {e}")
            return False

    async def load_entities(self, entity_type: Optional[str] = None) -> List[Dict]:
        """
        Load entities from memory.

        Args:
            entity_type: Optional filter by entity type

        Returns:
            List of entities
        """
        try:
            items = await self.redis.smembers(self.entity_key)

            entities = []
            for item in items:
                try:
                    entity_data = json.loads(item)

                    # Filter by type if specified
                    if entity_type and entity_data.get('type') != entity_type:
                        continue

                    entities.append(entity_data)

                except json.JSONDecodeError:
                    logger.warning(f"Failed to decode entity: {item}")

            logger.debug(f"Loaded {len(entities)} entities")
            return entities

        except Exception as e:
            logger.error(f"Failed to load entities: {e}")
            return []

    async def clear_session_memory(self) -> bool:
        """
        Clear all memory for current session.

        Returns:
            Success boolean
        """
        try:
            # Delete all session keys
            await self.redis.delete(
                self.short_term_key,
                self.long_term_key,
                self.entity_key
            )

            logger.info(f"Cleared memory for session: {self.session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear session memory: {e}")
            return False

    async def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about memory usage.

        Returns:
            Dictionary with memory statistics
        """
        try:
            stats = {
                "session_id": self.session_id,
                "short_term_count": await self.redis.llen(self.short_term_key),
                "long_term_count": await self.redis.hlen(self.long_term_key),
                "entity_count": await self.redis.scard(self.entity_key),
                "timestamp": datetime.now().isoformat()
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}


def create_redis_memory_provider(session_id: str, redis_url: Optional[str] = None) -> RedisMemoryProvider:
    """
    Factory function to create Redis memory provider.

    Args:
        session_id: Session identifier
        redis_url: Optional Redis URL (defaults to env var)

    Returns:
        RedisMemoryProvider instance
    """
    if redis_url is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    redis_client = redis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True
    )

    return RedisMemoryProvider(redis_client, session_id)
