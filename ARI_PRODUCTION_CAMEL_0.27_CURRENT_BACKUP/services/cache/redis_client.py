"""
Redis Client Service for Production Scaling
Provides centralized Redis access with connection pooling and failover
"""

import logging
import asyncio
import json
from typing import Optional, Dict, Any, List, Union
import time
from dataclasses import asdict

logger = logging.getLogger("services.cache.redis_client")

try:
    import redis.asyncio as redis
    from redis.asyncio import ConnectionPool
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available. Install with: pip install redis")


class RedisService:
    """
    Production Redis service with connection pooling and failover.
    Handles session storage, caching, and battle state management.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        db: int = 0,
        max_connections: int = 100,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30,
        decode_responses: bool = True
    ):
        """
        Initialize Redis service.
        
        Args:
            url: Redis URL (overrides host/port)
            host: Redis host
            port: Redis port
            password: Redis password
            db: Redis database number
            max_connections: Maximum connections in pool
            socket_timeout: Socket timeout
            socket_connect_timeout: Socket connect timeout
            retry_on_timeout: Retry on timeout
            health_check_interval: Health check interval
            decode_responses: Decode responses to strings
        """
        if not REDIS_AVAILABLE:
            raise RuntimeError("Redis is required but not installed")
        
        self.url = url
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_on_timeout = retry_on_timeout
        self.health_check_interval = health_check_interval
        self.decode_responses = decode_responses
        
        # Redis client and pool
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        
        # Health tracking
        self.is_healthy = False
        self.last_health_check = 0
        self.consecutive_failures = 0
        
        # Statistics
        self.stats = {
            "operations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "last_error": None,
            "uptime": 0
        }
        self.start_time = time.time()
        
        logger.info("Redis service initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize Redis connection and pool.
        
        Returns:
            Success status
        """
        try:
            # Create connection pool
            if self.url:
                self.pool = ConnectionPool.from_url(
                    self.url,
                    max_connections=self.max_connections,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_connect_timeout,
                    retry_on_timeout=self.retry_on_timeout,
                    decode_responses=self.decode_responses,
                    health_check_interval=self.health_check_interval
                )
            else:
                self.pool = ConnectionPool(
                    host=self.host,
                    port=self.port,
                    password=self.password,
                    db=self.db,
                    max_connections=self.max_connections,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_connect_timeout,
                    retry_on_timeout=self.retry_on_timeout,
                    decode_responses=self.decode_responses,
                    health_check_interval=self.health_check_interval
                )
            
            # Create Redis client
            self.client = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.client.ping()
            self.is_healthy = True
            self.consecutive_failures = 0
            
            logger.info("Redis service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            self.is_healthy = False
            self.consecutive_failures += 1
            return False
    
    async def close(self):
        """Close Redis connection gracefully."""
        if self.client:
            try:
                await self.client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
        
        if self.pool:
            try:
                await self.pool.disconnect()
            except Exception as e:
                logger.error(f"Error closing Redis pool: {e}")
    
    async def health_check(self) -> bool:
        """
        Check Redis health.
        
        Returns:
            True if healthy
        """
        current_time = time.time()
        
        # Skip if recently checked
        if current_time - self.last_health_check < self.health_check_interval:
            return self.is_healthy
        
        try:
            if self.client:
                await asyncio.wait_for(self.client.ping(), timeout=2.0)
                self.is_healthy = True
                self.consecutive_failures = 0
            else:
                self.is_healthy = False
            
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            self.is_healthy = False
            self.consecutive_failures += 1
        
        self.last_health_check = current_time
        return self.is_healthy
    
    # ==================== BASIC OPERATIONS ====================
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get value by key.
        
        Args:
            key: Redis key
            
        Returns:
            Value or None
        """
        try:
            if not await self.health_check():
                return None
            
            self.stats["operations"] += 1
            result = await self.client.get(key)
            
            if result is not None:
                self.stats["cache_hits"] += 1
            else:
                self.stats["cache_misses"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            return None
    
    async def set(
        self,
        key: str,
        value: Union[str, dict, list],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value by key.
        
        Args:
            key: Redis key
            value: Value to store
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        try:
            if not await self.health_check():
                return False
            
            # Serialize complex types
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            self.stats["operations"] += 1
            
            if ttl:
                await self.client.setex(key, ttl, value)
            else:
                await self.client.set(key, value)
            
            return True
            
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key.
        
        Args:
            key: Redis key
            
        Returns:
            Success status
        """
        try:
            if not await self.health_check():
                return False
            
            self.stats["operations"] += 1
            result = await self.client.delete(key)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists.
        
        Args:
            key: Redis key
            
        Returns:
            True if key exists
        """
        try:
            if not await self.health_check():
                return False
            
            self.stats["operations"] += 1
            result = await self.client.exists(key)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set TTL for key.
        
        Args:
            key: Redis key
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        try:
            if not await self.health_check():
                return False
            
            self.stats["operations"] += 1
            result = await self.client.expire(key, ttl)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    # ==================== JSON OPERATIONS ====================
    
    async def get_json(self, key: str) -> Optional[Union[dict, list]]:
        """
        Get JSON value by key.
        
        Args:
            key: Redis key
            
        Returns:
            Parsed JSON or None
        """
        try:
            value = await self.get(key)
            if value is None:
                return None
            
            return json.loads(value)
            
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Redis JSON decode error for key {key}: {e}")
            return None
    
    async def set_json(
        self,
        key: str,
        value: Union[dict, list],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set JSON value by key.
        
        Args:
            key: Redis key
            value: JSON serializable value
            ttl: Time to live in seconds
            
        Returns:
            Success status
        """
        try:
            json_str = json.dumps(value)
            return await self.set(key, json_str, ttl)
            
        except (json.JSONEncodeError, Exception) as e:
            logger.error(f"Redis JSON encode error for key {key}: {e}")
            return False
    
    # ==================== HASH OPERATIONS ====================
    
    async def hget(self, key: str, field: str) -> Optional[str]:
        """Get hash field value."""
        try:
            if not await self.health_check():
                return None
            
            self.stats["operations"] += 1
            return await self.client.hget(key, field)
            
        except Exception as e:
            logger.error(f"Redis HGET error for {key}.{field}: {e}")
            self.stats["errors"] += 1
            return None
    
    async def hset(self, key: str, field: str, value: str) -> bool:
        """Set hash field value."""
        try:
            if not await self.health_check():
                return False
            
            self.stats["operations"] += 1
            await self.client.hset(key, field, value)
            return True
            
        except Exception as e:
            logger.error(f"Redis HSET error for {key}.{field}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def hgetall(self, key: str) -> Dict[str, str]:
        """Get all hash fields."""
        try:
            if not await self.health_check():
                return {}
            
            self.stats["operations"] += 1
            return await self.client.hgetall(key)
            
        except Exception as e:
            logger.error(f"Redis HGETALL error for {key}: {e}")
            self.stats["errors"] += 1
            return {}
    
    # ==================== LIST OPERATIONS ====================
    
    async def lpush(self, key: str, *values) -> bool:
        """Push values to left of list."""
        try:
            if not await self.health_check():
                return False
            
            self.stats["operations"] += 1
            await self.client.lpush(key, *values)
            return True
            
        except Exception as e:
            logger.error(f"Redis LPUSH error for {key}: {e}")
            self.stats["errors"] += 1
            return False
    
    async def rpop(self, key: str) -> Optional[str]:
        """Pop value from right of list."""
        try:
            if not await self.health_check():
                return None
            
            self.stats["operations"] += 1
            return await self.client.rpop(key)
            
        except Exception as e:
            logger.error(f"Redis RPOP error for {key}: {e}")
            self.stats["errors"] += 1
            return None
    
    async def llen(self, key: str) -> int:
        """Get list length."""
        try:
            if not await self.health_check():
                return 0
            
            self.stats["operations"] += 1
            return await self.client.llen(key)
            
        except Exception as e:
            logger.error(f"Redis LLEN error for {key}: {e}")
            self.stats["errors"] += 1
            return 0
    
    # ==================== BATCH OPERATIONS ====================
    
    async def mget(self, keys: List[str]) -> List[Optional[str]]:
        """Get multiple values by keys."""
        try:
            if not await self.health_check():
                return [None] * len(keys)
            
            self.stats["operations"] += len(keys)
            result = await self.client.mget(keys)
            
            # Count hits/misses
            for value in result:
                if value is not None:
                    self.stats["cache_hits"] += 1
                else:
                    self.stats["cache_misses"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Redis MGET error: {e}")
            self.stats["errors"] += 1
            return [None] * len(keys)
    
    async def mset(self, mapping: Dict[str, Union[str, dict, list]]) -> bool:
        """Set multiple key-value pairs."""
        try:
            if not await self.health_check():
                return False
            
            # Serialize complex types
            processed_mapping = {}
            for key, value in mapping.items():
                if isinstance(value, (dict, list)):
                    processed_mapping[key] = json.dumps(value)
                else:
                    processed_mapping[key] = value
            
            self.stats["operations"] += len(mapping)
            await self.client.mset(processed_mapping)
            return True
            
        except Exception as e:
            logger.error(f"Redis MSET error: {e}")
            self.stats["errors"] += 1
            return False
    
    # ==================== PATTERN OPERATIONS ====================
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching pattern (use with caution in production)."""
        try:
            if not await self.health_check():
                return []
            
            self.stats["operations"] += 1
            return await self.client.keys(pattern)
            
        except Exception as e:
            logger.error(f"Redis KEYS error for pattern {pattern}: {e}")
            self.stats["errors"] += 1
            return []
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            keys = await self.keys(pattern)
            if not keys:
                return 0
            
            deleted = 0
            for key in keys:
                if await self.delete(key):
                    deleted += 1
            
            return deleted
            
        except Exception as e:
            logger.error(f"Redis delete pattern error for {pattern}: {e}")
            return 0
    
    # ==================== STATISTICS ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Redis service statistics."""
        current_time = time.time()
        uptime = current_time - self.start_time
        
        stats = self.stats.copy()
        stats.update({
            "uptime_seconds": uptime,
            "is_healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "last_health_check": self.last_health_check,
            "cache_hit_rate": (
                self.stats["cache_hits"] / 
                (self.stats["cache_hits"] + self.stats["cache_misses"])
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0
                else 0
            )
        })
        
        return stats


# ==================== FALLBACK SERVICE ====================

class FallbackRedisService:
    """
    Fallback service when Redis is not available.
    Provides in-memory caching with limited functionality.
    """
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.ttl_cache: Dict[str, float] = {}
        logger.warning("Using fallback Redis service (in-memory cache)")
    
    async def initialize(self) -> bool:
        return True
    
    async def close(self):
        pass
    
    async def health_check(self) -> bool:
        return True
    
    def _cleanup_expired(self):
        """Remove expired keys."""
        current_time = time.time()
        expired_keys = [
            key for key, expiry in self.ttl_cache.items()
            if current_time > expiry
        ]
        
        for key in expired_keys:
            self.cache.pop(key, None)
            self.ttl_cache.pop(key, None)
    
    async def get(self, key: str) -> Optional[str]:
        self._cleanup_expired()
        return self.cache.get(key)
    
    async def set(self, key: str, value: Union[str, dict, list], ttl: Optional[int] = None) -> bool:
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        self.cache[key] = value
        if ttl:
            self.ttl_cache[key] = time.time() + ttl
        
        return True
    
    async def delete(self, key: str) -> bool:
        self.cache.pop(key, None)
        self.ttl_cache.pop(key, None)
        return True
    
    async def exists(self, key: str) -> bool:
        self._cleanup_expired()
        return key in self.cache
    
    async def get_json(self, key: str) -> Optional[Union[dict, list]]:
        value = await self.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except:
            return None
    
    async def set_json(self, key: str, value: Union[dict, list], ttl: Optional[int] = None) -> bool:
        return await self.set(key, value, ttl)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "fallback_mode": True,
            "cache_size": len(self.cache),
            "is_healthy": True
        }


# ==================== FACTORY FUNCTION ====================

def create_redis_service(
    url: Optional[str] = None,
    host: str = "localhost",
    port: int = 6379,
    password: Optional[str] = None,
    **kwargs
) -> Union[RedisService, FallbackRedisService]:
    """
    Create Redis service with fallback.
    
    Args:
        url: Redis URL
        host: Redis host
        port: Redis port  
        password: Redis password
        **kwargs: Additional Redis configuration
        
    Returns:
        Redis service (real or fallback)
    """
    try:
        if REDIS_AVAILABLE:
            return RedisService(
                url=url,
                host=host,
                port=port,
                password=password,
                **kwargs
            )
        else:
            logger.warning("Redis not available, using fallback service")
            return FallbackRedisService()
    except Exception as e:
        logger.error(f"Failed to create Redis service: {e}")
        return FallbackRedisService()


# Export for DI container
__all__ = [
    "RedisService",
    "FallbackRedisService", 
    "create_redis_service",
    "REDIS_AVAILABLE"
]