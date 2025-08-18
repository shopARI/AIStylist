"""
Battle Cache Service
Enhanced caching system for battle results with thread safety and metrics
Refactored from battle_cache.py with settings integration
"""

import time
import hashlib
import json
import asyncio
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta
from collections import OrderedDict
from enum import Enum
from dataclasses import dataclass, field

from config.settings import get_settings, BattleConfig, CacheStrategy

logger = logging.getLogger("services.battle.cache")

# =============================================================================
# CACHE ENTRY
# =============================================================================

@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""
    data: Dict[str, Any]
    timestamp: float
    hits: int = 0
    last_accessed: float = field(default_factory=time.time)
    query: str = ""
    filters: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self, ttl: int) -> bool:
        """Check if entry is expired."""
        return time.time() - self.timestamp > ttl
    
    def access(self) -> None:
        """Record an access to this entry."""
        self.hits += 1
        self.last_accessed = time.time()
    
    @property
    def age(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.timestamp
    
    @property
    def size_estimate(self) -> int:
        """Estimate memory size of entry in bytes."""
        return len(json.dumps(self.data))

# =============================================================================
# BATTLE CACHE
# =============================================================================

class BattleCache:
    """
    Enhanced cache for battle search results with advanced features.
    Thread-safe implementation with multiple eviction strategies.
    """
    
    def __init__(
        self,
        config: Optional[BattleConfig] = None,
        name: str = "BattleCache"
    ):
        """
        Initialize battle cache with configuration.
        
        Args:
            config: Battle configuration (uses settings if None)
            name: Cache name for logging
        """
        self.config = config or get_settings().battle
        self.name = name
        
        # Cache storage
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
            "total_queries": 0,
            "total_size": 0,
            "avg_entry_age": 0.0,
            "avg_hit_rate": 0.0
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = True
        
        logger.info(
            f"{name} initialized: TTL={self.config.cache_ttl}s, "
            f"max_size={self.config.cache_max_size}, "
            f"strategy={self.config.cache_strategy.value}"
        )
        
        # Start cleanup worker
        if self.config.enable_cache:
            self._cleanup_task = asyncio.create_task(self._cleanup_worker())
    
    # =========================================================================
    # CACHE OPERATIONS
    # =========================================================================
    
    def _make_key(self, query: str, filters: Dict[str, Any], limit: int) -> str:
        """
        Create a unique cache key from query parameters.
        
        Args:
            query: Search query
            filters: Search filters
            limit: Result limit
            
        Returns:
            Unique cache key
        """
        # Normalize data for consistent hashing
        key_data = {
            "query": query.lower().strip(),
            "filters": sorted(filters.items()) if filters else [],
            "limit": limit
        }
        
        # Create stable string representation
        key_string = json.dumps(key_data, sort_keys=True)
        
        # Generate hash
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    async def get(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached battle result if available and not expired.
        
        Args:
            query: Search query
            filters: Search filters
            limit: Result limit
            
        Returns:
            Cached result or None
        """
        if not self.config.enable_cache:
            return None
        
        self.stats["total_queries"] += 1
        key = self._make_key(query, filters, limit)
        
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                
                # Check expiration
                if entry.is_expired(self.config.cache_ttl):
                    del self._cache[key]
                    self.stats["expirations"] += 1
                    self.stats["misses"] += 1
                    logger.debug(f"Cache entry expired: {key[:8]}...")
                    return None
                
                # Record access
                entry.access()
                
                # Move to end for LRU
                if self.config.cache_strategy == CacheStrategy.LRU:
                    self._cache.move_to_end(key)
                
                self.stats["hits"] += 1
                
                # Update hit rate
                self._update_hit_rate()
                
                logger.debug(f"Cache hit: {key[:8]}... (hits: {entry.hits})")
                return entry.data
            
            self.stats["misses"] += 1
            self._update_hit_rate()
            return None
    
    async def set(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int,
        data: Dict[str, Any]
    ) -> None:
        """
        Cache a battle result.
        
        Args:
            query: Search query
            filters: Search filters
            limit: Result limit
            data: Battle result to cache
        """
        if not self.config.enable_cache:
            return
        
        key = self._make_key(query, filters, limit)
        
        async with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.config.cache_max_size and key not in self._cache:
                await self._evict_entry()
            
            # Create entry
            entry = CacheEntry(
                data=data,
                timestamp=time.time(),
                query=query,
                filters=filters
            )
            
            # Add or update
            if key in self._cache:
                # Update existing
                self._cache[key] = entry
            else:
                # Add new
                self._cache[key] = entry
            
            # Move to end for LRU
            if self.config.cache_strategy == CacheStrategy.LRU:
                self._cache.move_to_end(key)
            
            logger.debug(f"Cached result: {key[:8]}... (size: {len(self._cache)})")
    
    async def invalidate(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Invalidate cache entries matching criteria.
        
        Args:
            query: Optional query to match
            filters: Optional filters to match
            
        Returns:
            Number of entries invalidated
        """
        invalidated = 0
        
        async with self._lock:
            keys_to_remove = []
            
            for key, entry in self._cache.items():
                should_remove = False
                
                # Check query match
                if query and query.lower() in entry.query.lower():
                    should_remove = True
                
                # Check filter match
                if filters:
                    for k, v in filters.items():
                        if k in entry.filters and entry.filters[k] == v:
                            should_remove = True
                            break
                
                if should_remove:
                    keys_to_remove.append(key)
            
            # Remove matched entries
            for key in keys_to_remove:
                del self._cache[key]
                invalidated += 1
        
        if invalidated > 0:
            logger.info(f"Invalidated {invalidated} cache entries")
        
        return invalidated
    
    # =========================================================================
    # EVICTION STRATEGIES
    # =========================================================================
    
    async def _evict_entry(self) -> None:
        """Evict entry based on configured strategy."""
        if not self._cache:
            return
        
        key_to_evict = None
        
        if self.config.cache_strategy == CacheStrategy.LRU:
            # Remove least recently used (first item)
            key_to_evict = next(iter(self._cache))
        
        elif self.config.cache_strategy == CacheStrategy.LFU:
            # Remove least frequently used
            key_to_evict = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].hits
            )
        
        elif self.config.cache_strategy == CacheStrategy.FIFO:
            # Remove oldest (first item)
            key_to_evict = next(iter(self._cache))
        
        if key_to_evict:
            del self._cache[key_to_evict]
            self.stats["evictions"] += 1
            logger.debug(f"Evicted cache entry: {key_to_evict[:8]}...")
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    
    async def _cleanup_worker(self) -> None:
        """Background task to clean up expired entries."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cache_cleanup_interval)
                
                if self._running:
                    await self._cleanup_expired()
            
            except asyncio.CancelledError:
                logger.info(f"{self.name} cleanup worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in {self.name} cleanup: {e}")
        
        logger.info(f"{self.name} cleanup worker stopped")
    
    async def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired(self.config.cache_ttl)
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self.stats["expirations"] += 1
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
            
            # Update average age
            self._update_avg_age()
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    def _update_hit_rate(self) -> None:
        """Update average hit rate."""
        total = self.stats["total_queries"]
        if total > 0:
            self.stats["avg_hit_rate"] = self.stats["hits"] / total * 100
    
    def _update_avg_age(self) -> None:
        """Update average entry age."""
        if self._cache:
            ages = [entry.age for entry in self._cache.values()]
            self.stats["avg_entry_age"] = sum(ages) / len(ages)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.
        
        Returns:
            Statistics dictionary
        """
        # Calculate memory estimate
        total_size = sum(
            entry.size_estimate for entry in self._cache.values()
        ) if self._cache else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.config.cache_max_size,
            "ttl": self.config.cache_ttl,
            "strategy": self.config.cache_strategy.value,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "expirations": self.stats["expirations"],
            "total_queries": self.stats["total_queries"],
            "hit_rate": f"{self.stats['avg_hit_rate']:.1f}%",
            "avg_entry_age": f"{self.stats['avg_entry_age']:.1f}s",
            "memory_estimate": f"{total_size / 1024:.1f}KB",
            "enabled": self.config.enable_cache
        }
    
    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()
            logger.info(f"{self.name} cleared")
    
    async def shutdown(self) -> None:
        """Shutdown cache and cleanup resources."""
        logger.info(f"Shutting down {self.name}...")
        
        # Stop cleanup worker
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clear cache
        await self.clear()
        
        logger.info(f"{self.name} shutdown complete")
    
    # =========================================================================
    # ADVANCED FEATURES
    # =========================================================================
    
    async def warm_up(
        self,
        common_queries: List[Tuple[str, Dict[str, Any], int, Dict[str, Any]]]
    ) -> None:
        """
        Pre-warm cache with common queries.
        
        Args:
            common_queries: List of (query, filters, limit, data) tuples
        """
        logger.info(f"Warming up {self.name} with {len(common_queries)} queries")
        
        for query, filters, limit, data in common_queries:
            await self.set(query, filters, limit, data)
        
        logger.info(f"{self.name} warm-up complete")
    
    async def export_cache(self) -> List[Dict[str, Any]]:
        """
        Export cache entries for persistence.
        
        Returns:
            List of cache entries
        """
        async with self._lock:
            entries = []
            for key, entry in self._cache.items():
                entries.append({
                    "key": key,
                    "query": entry.query,
                    "filters": entry.filters,
                    "data": entry.data,
                    "timestamp": entry.timestamp,
                    "hits": entry.hits
                })
            return entries
    
    async def import_cache(
        self,
        entries: List[Dict[str, Any]],
        skip_expired: bool = True
    ) -> int:
        """
        Import cache entries from persistence.
        
        Args:
            entries: List of cache entries
            skip_expired: Skip expired entries
            
        Returns:
            Number of entries imported
        """
        imported = 0
        current_time = time.time()
        
        async with self._lock:
            for entry_data in entries:
                # Check if expired
                if skip_expired:
                    age = current_time - entry_data["timestamp"]
                    if age > self.config.cache_ttl:
                        continue
                
                # Create entry
                entry = CacheEntry(
                    data=entry_data["data"],
                    timestamp=entry_data["timestamp"],
                    hits=entry_data.get("hits", 0),
                    query=entry_data.get("query", ""),
                    filters=entry_data.get("filters", {})
                )
                
                # Add to cache
                key = entry_data["key"]
                self._cache[key] = entry
                imported += 1
        
        logger.info(f"Imported {imported} cache entries")
        return imported

# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

# Create global cache instance
_battle_cache: Optional[BattleCache] = None

def get_battle_cache() -> BattleCache:
    """
    Get the global battle cache instance.
    
    Returns:
        BattleCache instance
    """
    global _battle_cache
    if _battle_cache is None:
        _battle_cache = BattleCache(name="GlobalBattleCache")
    return _battle_cache

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'BattleCache',
    'CacheEntry',
    'get_battle_cache'
]
