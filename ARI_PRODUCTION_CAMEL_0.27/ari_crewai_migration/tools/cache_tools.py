"""
Redis Cache Tools for CrewAI Migration
Wraps Redis caching functionality into CrewAI-compatible tools.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from crewai import tool
import redis.asyncio as redis

logger = logging.getLogger("crewai.tools.cache")


@tool("Lookup Redis Cache")
def cache_lookup_tool(cache_key: str) -> Optional[Dict]:
    """
    Check Redis cache for cached results.

    Args:
        cache_key: Cache key to lookup

    Returns:
        Cached data or None if not found

    Example:
        cached_data = cache_lookup_tool("search:black_dress:5")
    """
    try:
        # Get Redis connection from environment
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        # Create synchronous Redis client for tool
        import redis as sync_redis
        client = sync_redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )

        # Get cached data
        cached = client.get(cache_key)

        if cached:
            data = json.loads(cached)
            logger.info(f"Cache hit for key: {cache_key}")
            return data
        else:
            logger.info(f"Cache miss for key: {cache_key}")
            return None

    except Exception as e:
        logger.error(f"Cache lookup failed: {e}")
        return None


@tool("Store in Redis Cache")
def cache_store_tool(cache_key: str, data: Dict[str, Any], ttl: int = 180) -> bool:
    """
    Store results in Redis cache with TTL.

    Args:
        cache_key: Cache key
        data: Data to cache
        ttl: Time to live in seconds (default 180s = 3 minutes)

    Returns:
        Success boolean

    Example:
        success = cache_store_tool(
            cache_key="search:black_dress:5",
            data={"products": [...]},
            ttl=180
        )
    """
    try:
        # Get Redis connection from environment
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        # Create synchronous Redis client
        import redis as sync_redis
        client = sync_redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )

        # Store data with TTL
        serialized = json.dumps(data)
        client.set(cache_key, serialized, ex=ttl)

        logger.info(f"Cached data at key: {cache_key} (TTL={ttl}s)")
        return True

    except Exception as e:
        logger.error(f"Cache store failed: {e}")
        return False


@tool("Invalidate Cache")
def cache_invalidate_tool(cache_pattern: str) -> int:
    """
    Invalidate cache keys matching pattern.

    Args:
        cache_pattern: Redis key pattern (supports wildcards)

    Returns:
        Number of keys deleted

    Example:
        deleted = cache_invalidate_tool("search:*")
    """
    try:
        # Get Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        import redis as sync_redis
        client = sync_redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )

        # Find matching keys
        keys = client.keys(cache_pattern)

        if keys:
            deleted = client.delete(*keys)
            logger.info(f"Deleted {deleted} cache keys matching pattern: {cache_pattern}")
            return deleted
        else:
            logger.info(f"No keys found matching pattern: {cache_pattern}")
            return 0

    except Exception as e:
        logger.error(f"Cache invalidation failed: {e}")
        return 0


@tool("Get Cache Statistics")
def cache_stats_tool() -> Dict[str, Any]:
    """
    Get Redis cache statistics.

    Returns:
        Dictionary with cache statistics (size, keys, memory usage)

    Example:
        stats = cache_stats_tool()
    """
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        import redis as sync_redis
        client = sync_redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )

        # Get Redis info
        info = client.info()

        stats = {
            "total_keys": client.dbsize(),
            "memory_used": info.get('used_memory_human', 'unknown'),
            "connected_clients": info.get('connected_clients', 0),
            "uptime_days": info.get('uptime_in_days', 0),
            "version": info.get('redis_version', 'unknown')
        }

        logger.info(f"Cache stats: {stats['total_keys']} keys, {stats['memory_used']} memory")
        return stats

    except Exception as e:
        logger.error(f"Cache stats failed: {e}")
        return {}
