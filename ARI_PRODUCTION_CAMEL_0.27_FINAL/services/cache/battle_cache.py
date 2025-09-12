"""
Battle Cache Service
Enhanced caching for battle results with multiple backend support
Based on battle_cache.py patterns
"""

import logging
import asyncio
import time
import hashlib
import json
import pickle
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
import os

logger = logging.getLogger("services.battle.cache")

# Try to import Redis for distributed caching
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.info("Redis not available, using in-memory cache only")


class CacheBackend(Enum):
    """Cache backend types."""
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"  # Memory + Redis


@dataclass
class CacheEntry:
    """Enhanced cache entry with metadata."""
    key: str
    data: Any
    created_at: float
    expires_at: float
    hits: int = 0
    last_accessed: float = field(default_factory=time.time)
    size_bytes: int = 0
    tags: List[str] = field(default_factory=list)
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() > self.expires_at
    
    def access(self):
        """Record an access."""
        self.hits += 1
        self.last_accessed = time.time()
    
    def time_to_live(self) -> float:
        """Get remaining TTL in seconds."""
        ttl = self.expires_at - time.time()
        return max(0, ttl)


class MemoryCache:
    """
    In-memory LRU cache implementation.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300
    ):
        """
        Initialize memory cache.
        
        Args:
            max_size: Maximum cache entries
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                
                if entry.is_expired():
                    del self._cache[key]
                    self.stats["expirations"] += 1
                    self.stats["misses"] += 1
                    return None
                
                # Move to end (LRU)
                self._cache.move_to_end(key)
                entry.access()
                self.stats["hits"] += 1
                return entry.data
            
            self.stats["misses"] += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """Set value in cache."""
        ttl = ttl or self.default_ttl
        
        async with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                # Evict least recently used
                evicted_key = next(iter(self._cache))
                del self._cache[evicted_key]
                self.stats["evictions"] += 1
            
            # Calculate size
            try:
                size_bytes = len(pickle.dumps(value))
            except:
                size_bytes = 0
            
            # Create entry
            entry = CacheEntry(
                key=key,
                data=value,
                created_at=time.time(),
                expires_at=time.time() + ttl,
                size_bytes=size_bytes,
                tags=tags or []
            )
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self.stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "expirations": 0
            }
    
    async def get_by_tags(self, tags: List[str]) -> List[str]:
        """Get keys by tags."""
        async with self._lock:
            keys = []
            for key, entry in self._cache.items():
                if any(tag in entry.tags for tag in tags):
                    if not entry.is_expired():
                        keys.append(key)
            return keys
    
    async def cleanup_expired(self) -> int:
        """Remove expired entries."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self.stats["expirations"] += 1
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        total_size = sum(entry.size_bytes for entry in self._cache.values())
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "expirations": self.stats["expirations"],
            "hit_rate": f"{hit_rate:.1f}%",
            "memory_usage": f"{total_size / 1024:.1f}KB"
        }


class RedisCache:
    """
    Redis-based distributed cache.
    """
    
    def __init__(
        self,
        redis_url: str,
        default_ttl: int = 300,
        key_prefix: str = "battle:"
    ):
        """
        Initialize Redis cache.
        
        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
            key_prefix: Prefix for all keys
        """
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis not available")
        
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.client = None
        
        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0
        }
    
    async def connect(self):
        """Connect to Redis."""
        try:
            self.client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False
            )
            await self.client.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
    
    def _make_key(self, key: str) -> str:
        """Create full key with prefix."""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self.client:
            return None
        
        try:
            full_key = self._make_key(key)
            data = await self.client.get(full_key)
            
            if data:
                self.stats["hits"] += 1
                # Deserialize
                return pickle.loads(data)
            else:
                self.stats["misses"] += 1
                return None
                
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self.stats["errors"] += 1
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """Set value in cache."""
        if not self.client:
            return
        
        ttl = ttl or self.default_ttl
        
        try:
            full_key = self._make_key(key)
            # Serialize
            data = pickle.dumps(value)
            
            # Set with TTL
            await self.client.setex(full_key, ttl, data)
            
            # Store tags separately if provided
            if tags:
                for tag in tags:
                    tag_key = f"{self.key_prefix}tag:{tag}"
                    await self.client.sadd(tag_key, key)
                    await self.client.expire(tag_key, ttl)
                    
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            self.stats["errors"] += 1
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.client:
            return False
        
        try:
            full_key = self._make_key(key)
            result = await self.client.delete(full_key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def clear(self):
        """Clear all cache entries with prefix."""
        if not self.client:
            return
        
        try:
            # Get all keys with prefix
            pattern = f"{self.key_prefix}*"
            keys = []
            
            async for key in self.client.scan_iter(pattern):
                keys.append(key)
            
            if keys:
                await self.client.delete(*keys)
                
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    async def get_by_tags(self, tags: List[str]) -> List[str]:
        """Get keys by tags."""
        if not self.client:
            return []
        
        try:
            all_keys = set()
            
            for tag in tags:
                tag_key = f"{self.key_prefix}tag:{tag}"
                keys = await self.client.smembers(tag_key)
                all_keys.update(keys)
            
            return list(all_keys)
            
        except Exception as e:
            logger.error(f"Redis get_by_tags error: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "backend": "redis",
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "errors": self.stats["errors"],
            "hit_rate": f"{hit_rate:.1f}%"
        }


class BattleCache:
    """
    Main battle cache with support for multiple backends.
    """
    
    def __init__(
        self,
        backend: CacheBackend = CacheBackend.MEMORY,
        redis_url: Optional[str] = None,
        max_memory_size: int = 1000,
        default_ttl: int = 300,
        enable_cleanup: bool = True,
        cleanup_interval: int = 60
    ):
        """
        Initialize battle cache.
        
        Args:
            backend: Cache backend type
            redis_url: Redis URL for distributed cache
            max_memory_size: Max entries for memory cache
            default_ttl: Default TTL in seconds
            enable_cleanup: Enable automatic cleanup
            cleanup_interval: Cleanup interval in seconds
        """
        self.backend = backend
        self.default_ttl = default_ttl
        self.enable_cleanup = enable_cleanup
        self.cleanup_interval = cleanup_interval
        
        # Initialize memory cache
        self.memory_cache = MemoryCache(
            max_size=max_memory_size,
            default_ttl=default_ttl
        )
        
        # Initialize Redis cache if needed
        self.redis_cache = None
        if backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
            if not redis_url:
                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            
            if REDIS_AVAILABLE:
                self.redis_cache = RedisCache(
                    redis_url=redis_url,
                    default_ttl=default_ttl
                )
            else:
                logger.warning("Redis requested but not available, falling back to memory")
                self.backend = CacheBackend.MEMORY
        
        # Cleanup task
        self._cleanup_task = None
        self._running = True
        
        logger.info(f"Battle cache initialized with backend: {self.backend.value}")
    
    async def initialize(self):
        """Initialize cache connections."""
        # Connect to Redis if needed
        if self.redis_cache:
            await self.redis_cache.connect()
        
        # Start cleanup task
        if self.enable_cleanup:
            self._cleanup_task = asyncio.create_task(self._cleanup_worker())
    
    async def _cleanup_worker(self):
        """Background cleanup worker."""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                
                if not self._running:
                    break
                
                # Clean memory cache
                expired = await self.memory_cache.cleanup_expired()
                if expired > 0:
                    logger.debug(f"Cleaned {expired} expired entries from memory cache")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")
    
    def make_key(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> str:
        """
        Create cache key from parameters.
        
        Args:
            query: Search query
            filters: Search filters
            user_id: Optional user ID for personalization
            
        Returns:
            Cache key
        """
        key_data = {
            "query": query.lower().strip(),
            "filters": filters or {},
            "user_id": user_id
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        # Try memory first
        if self.backend in [CacheBackend.MEMORY, CacheBackend.HYBRID]:
            value = await self.memory_cache.get(key)
            if value is not None:
                return value
        
        # Try Redis
        if self.backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
            if self.redis_cache:
                value = await self.redis_cache.get(key)
                
                # Populate memory cache in hybrid mode
                if value is not None and self.backend == CacheBackend.HYBRID:
                    await self.memory_cache.set(key, value, ttl=60)  # Short TTL
                
                return value
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds
            tags: Optional tags
        """
        ttl = ttl or self.default_ttl
        
        # Set in memory
        if self.backend in [CacheBackend.MEMORY, CacheBackend.HYBRID]:
            await self.memory_cache.set(key, value, ttl, tags)
        
        # Set in Redis
        if self.backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
            if self.redis_cache:
                await self.redis_cache.set(key, value, ttl, tags)
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted
        """
        deleted = False
        
        # Delete from memory
        if self.backend in [CacheBackend.MEMORY, CacheBackend.HYBRID]:
            deleted = await self.memory_cache.delete(key) or deleted
        
        # Delete from Redis
        if self.backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
            if self.redis_cache:
                deleted = await self.redis_cache.delete(key) or deleted
        
        return deleted
    
    async def clear(self):
        """Clear all cache entries."""
        # Clear memory
        if self.backend in [CacheBackend.MEMORY, CacheBackend.HYBRID]:
            await self.memory_cache.clear()
        
        # Clear Redis
        if self.backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
            if self.redis_cache:
                await self.redis_cache.clear()
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """
        Invalidate cache entries by tags.
        
        Args:
            tags: Tags to invalidate
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        
        # Get keys by tags
        keys = []
        
        if self.backend in [CacheBackend.MEMORY, CacheBackend.HYBRID]:
            keys.extend(await self.memory_cache.get_by_tags(tags))
        
        if self.backend in [CacheBackend.REDIS, CacheBackend.HYBRID]:
            if self.redis_cache:
                keys.extend(await self.redis_cache.get_by_tags(tags))
        
        # Delete keys
        keys = list(set(keys))  # Deduplicate
        
        for key in keys:
            if await self.delete(key):
                count += 1
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "backend": self.backend.value,
            "memory": self.memory_cache.get_stats()
        }
        
        if self.redis_cache:
            stats["redis"] = self.redis_cache.get_stats()
        
        return stats
    
    async def shutdown(self):
        """Shutdown cache."""
        logger.info("Shutting down battle cache")
        
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect Redis
        if self.redis_cache:
            await self.redis_cache.disconnect()
        
        logger.info("Battle cache shutdown complete")


# Global instance
_battle_cache: Optional[BattleCache] = None


def get_battle_cache(
    backend: Optional[CacheBackend] = None,
    redis_url: Optional[str] = None
) -> BattleCache:
    """
    Get global battle cache instance.
    
    Args:
        backend: Optional backend override
        redis_url: Optional Redis URL
        
    Returns:
        BattleCache instance
    """
    global _battle_cache
    
    if _battle_cache is None:
        # Get configuration
        from config.settings import get_settings
        settings = get_settings()
        
        # Determine backend
        if backend is None:
            if redis_url or os.getenv("REDIS_URL"):
                backend = CacheBackend.HYBRID
            else:
                backend = CacheBackend.MEMORY
        
        _battle_cache = BattleCache(
            backend=backend,
            redis_url=redis_url,
            max_memory_size=settings.battle.cache_max_size,
            default_ttl=settings.battle.cache_ttl,
            enable_cleanup=True,
            cleanup_interval=settings.battle.cache_cleanup_interval
        )
    
    return _battle_cache


# Exports
__all__ = [
    'BattleCache',
    'CacheBackend',
    'CacheEntry',
    'MemoryCache',
    'RedisCache',
    'get_battle_cache'
]