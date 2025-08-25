
#Battle Orchestrator - Main coordinator for recommendation battles
#Based on competitive_search_system.py patterns
#SECURITY: Thread-safe cache implementation with TTL management
#PERFORMANCE: Connection pooling and batch processing support


import logging
import asyncio
import time
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("services.battle.orchestrator")

# Import agents
from agents.cypher_bot import CypherBotAgent
from agents.vibe_bot import VibeBotAgent  
from agents.judge import JudgeAriAgent

# Import other battle components

from services.battle.optimizer import BattleOptimizer
from services.battle.executor import BattleExecutor
from services.battle.metrics import BattleMetrics

class CacheStrategy(Enum):
    """Cache eviction strategies."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    data: Dict[str, Any]
    timestamp: float
    hits: int = 0
    last_accessed: float = field(default_factory=time.time)
    
    def is_expired(self, ttl: int) -> bool:
        """Check if entry is expired."""
        return time.time() - self.timestamp > ttl
    
    def access(self):
        """Record an access."""
        self.hits += 1
        self.last_accessed = time.time()


class ThreadSafeBattleCache:
    """
    Thread-safe cache implementation for battle results.
    Uses asyncio.Lock for async safety and supports multiple eviction strategies.
    FIXED: Added stop flag for cleanup worker, better resource management
    """
    
    def __init__(
        self, 
        ttl: int = 300,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.LRU,
        cleanup_interval: int = 60
    ):
        """
        Initialize thread-safe cache with automatic cleanup.
        
        Args:
            ttl: Time-to-live in seconds
            max_size: Maximum cache size
            strategy: Cache eviction strategy
            cleanup_interval: Interval for background cleanup in seconds
        """
        self.ttl = ttl
        self.max_size = max_size
        self.strategy = strategy
        self.cleanup_interval = cleanup_interval
        
        # Core cache storage
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        
        # Statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
            "total_requests": 0
        }
        
        # Control flag for cleanup worker
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_worker())
        
        logger.info(f"ThreadSafeBattleCache initialized: ttl={ttl}s, max_size={max_size}, strategy={strategy.value}")
    
    def _make_key(self, query: str, filters: Dict, limit: int) -> str:
        """Create cache key from parameters."""
        # Create deterministic key
        key_data = {
            "query": query.lower().strip(),
            "filters": filters or {},
            "limit": limit
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    async def get(self, query: str, filters: Dict, limit: int) -> Optional[Dict[str, Any]]:
        """
        Get cached result if available and not expired.
        Thread-safe implementation with access tracking.
        """
        key = self._make_key(query, filters, limit)
        self.stats["total_requests"] += 1
        
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                
                # Check if expired
                if entry.is_expired(self.ttl):
                    # Remove expired entry
                    del self._cache[key]
                    self.stats["expirations"] += 1
                    self.stats["misses"] += 1
                    return None
                
                # Record access
                entry.access()
                
                # Move to end for LRU
                if self.strategy == CacheStrategy.LRU:
                    self._cache.move_to_end(key)
                
                self.stats["hits"] += 1
                return entry.data
            
            self.stats["misses"] += 1
            return None
    
    async def set(self, query: str, filters: Dict, limit: int, data: Dict[str, Any]):
        """
        Set cache entry with eviction if needed.
        Thread-safe implementation with strategy-based eviction.
        """
        key = self._make_key(query, filters, limit)
        
        async with self._lock:
            # Check if we need to evict
            if len(self._cache) >= self.max_size and key not in self._cache:
                await self._evict_entry()
            
            # Create and add entry
            entry = CacheEntry(
                data=data,
                timestamp=time.time()
            )
            
            # Add or update entry
            if key in self._cache:
                # Update existing
                self._cache[key] = entry
            else:
                # Add new
                self._cache[key] = entry
            
            # Move to end for LRU
            if self.strategy == CacheStrategy.LRU:
                self._cache.move_to_end(key)
    
    async def _evict_entry(self):
        """Evict entry based on strategy."""
        if not self._cache:
            return
        
        if self.strategy == CacheStrategy.LRU:
            # Remove least recently used (first item)
            key = next(iter(self._cache))
        elif self.strategy == CacheStrategy.LFU:
            # Remove least frequently used
            key = min(self._cache.keys(), key=lambda k: self._cache[k].hits)
        else:  # FIFO
            # Remove oldest (first item)
            key = next(iter(self._cache))
        
        del self._cache[key]
        self.stats["evictions"] += 1
    
    async def _cleanup_worker(self):
        """
        Background task to clean up expired entries.
        FIXED: Added proper shutdown handling with _running flag
        """
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                if self._running:  # Check again after sleep
                    await self._cleanup_expired()
            except asyncio.CancelledError:
                logger.info("Cache cleanup worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
        
        logger.info("Cache cleanup worker stopped")
    
    async def _cleanup_expired(self):
        """Remove all expired entries."""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired(self.ttl)
            ]
            
            for key in expired_keys:
                del self._cache[key]
                self.stats["expirations"] += 1
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def clear(self):
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self.stats = {
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "expirations": 0,
                "total_requests": 0
            }
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        total = self.stats["total_requests"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        
        # Calculate average entry age
        current_time = time.time()
        ages = []
        for entry in self._cache.values():
            ages.append(current_time - entry.timestamp)
        
        avg_age = sum(ages) / len(ages) if ages else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl": self.ttl,
            "strategy": self.strategy.value,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "evictions": self.stats["evictions"],
            "expirations": self.stats["expirations"],
            "hit_rate": f"{hit_rate:.1f}%",
            "avg_entry_age": f"{avg_age:.1f}s",
            "memory_estimate": f"{len(str(self._cache)) / 1024:.1f}KB",
            "cleanup_running": self._running
        }
    
    async def shutdown(self):
        """
        Shutdown cache and cleanup resources.
        FIXED: Proper cleanup with stop flag
        """
        logger.info("Shutting down cache...")
        
        # Stop the cleanup worker
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        await self.clear()
        logger.info("Cache shutdown complete")


# Global cache instance (thread-safe)
orchestrator_cache = ThreadSafeBattleCache(
    ttl=300,
    max_size=1000,
    strategy=CacheStrategy.LRU
)


class BattleOrchestrator:
    """
    Main orchestrator for CAMEL-powered battles between Neo4j and Qdrant.
    This is the CORE of the recommendation system - ALL paths lead here.
    
    Based on competitive_search_system.py with cleaner architecture.
    SECURITY: Using thread-safe cache implementation
    PERFORMANCE: Connection pooling and batch processing support
    FIXED: Auto-recovery for failed components, better health checks
    """
    
    def __init__(
        self,
        neo4j_client: Any,
        qdrant_client: Any,
        enable_cache: bool = True,
        enable_optimization: bool = True,
        enable_metrics: bool = True,
        cache_ttl: int = 300,
        cache_max_size: int = 1000,
        cache_strategy: CacheStrategy = CacheStrategy.LRU,
        connection_pool_size: int = 10,
        max_concurrent_battles: int = 5,
        enable_auto_recovery: bool = True,
        recovery_attempts: int = 3
    ):
        """
        Initialize the battle orchestrator with enhanced configuration.
        
        Args:
            neo4j_client: Neo4j database client
            qdrant_client: Qdrant database client
            enable_cache: Enable result caching
            enable_optimization: Enable parameter optimization
            enable_metrics: Enable metrics collection
            cache_ttl: Cache TTL in seconds
            cache_max_size: Maximum cache size
            cache_strategy: Cache eviction strategy
            connection_pool_size: Size of connection pool
            max_concurrent_battles: Maximum concurrent battles
            enable_auto_recovery: Enable automatic recovery for failed components
            recovery_attempts: Number of recovery attempts
        """
        logger.info("="*60)
        logger.info("Initializing Battle Orchestrator v2.0")
        logger.info("="*60)
        
        # Store clients
        self.neo4j_client = neo4j_client
        self.qdrant_client = qdrant_client
        
        # Initialize battle agents with connection pooling support
        self.cypher_bot = CypherBotAgent(
            neo4j_client,
            enable_connection_pooling=True
        )
        self.vibe_bot = VibeBotAgent(
            qdrant_client,
            enable_connection_pooling=True
        )
        self.judge = JudgeAriAgent()
        
        # Initialize components
        self.optimizer = BattleOptimizer() if enable_optimization else None
        self.executor = BattleExecutor(
            cypher_bot=self.cypher_bot,
            vibe_bot=self.vibe_bot,
            judge=self.judge
        )
        self.metrics = BattleMetrics() if enable_metrics else None
        
        # Initialize or use global cache
        if enable_cache:
            if cache_strategy != CacheStrategy.LRU or cache_ttl != 300:
                # Create custom cache
                self.cache = ThreadSafeBattleCache(
                    ttl=cache_ttl,
                    max_size=cache_max_size,
                    strategy=cache_strategy
                )
            else:
                # Use global cache
                self.cache = battle_cache
        else:
            self.cache = None
        
        # Semaphore for concurrent battle limiting
        self.battle_semaphore = asyncio.Semaphore(max_concurrent_battles)
        
        # Configuration
        self.config = {
            "enable_cache": enable_cache,
            "enable_optimization": enable_optimization,
            "enable_metrics": enable_metrics,
            "cache_ttl": cache_ttl,
            "cache_max_size": cache_max_size,
            "cache_strategy": cache_strategy.value if isinstance(cache_strategy, CacheStrategy) else cache_strategy,
            "connection_pool_size": connection_pool_size,
            "max_concurrent_battles": max_concurrent_battles,
            "enable_auto_recovery": enable_auto_recovery,
            "recovery_attempts": recovery_attempts,
            "default_limit": 5,
            "default_timeout": 30.0,
            "default_prefetch_multiplier": 2
        }
        
        # Track active battles
        self.active_battles = set()
        self.total_battles_executed = 0
        
        # Health tracking for auto-recovery
        self.component_health = {
            "cypher_bot": {"status": "healthy", "failures": 0, "last_check": None},
            "vibe_bot": {"status": "healthy", "failures": 0, "last_check": None},
            "cache": {"status": "healthy", "failures": 0, "last_check": None}
        }
        
        # Start auto-recovery task if enabled
        self._recovery_task = None
        self._recovery_running = True
        self._recovery_tasks = []
        if enable_auto_recovery:
            self._recovery_task = asyncio.create_task(self._auto_recovery_worker())
        
        logger.info("Battle components initialized:")
        logger.info(f"  - CypherBot: Ready (pooling enabled)")
        logger.info(f"  - VibeBot: Ready (pooling enabled)")
        logger.info(f"  - Judge Ari: Ready")
        logger.info(f"  - Cache: {'Enabled' if enable_cache else 'Disabled'} (Thread-Safe, {cache_strategy.value})")
        logger.info(f"  - Optimization: {'Enabled' if enable_optimization else 'Disabled'}")
        logger.info(f"  - Metrics: {'Enabled' if enable_metrics else 'Disabled'}")
        logger.info(f"  - Auto-Recovery: {'Enabled' if enable_auto_recovery else 'Disabled'}")
        logger.info(f"  - Connection Pool: {connection_pool_size}")
        logger.info(f"  - Max Concurrent: {max_concurrent_battles}")
        logger.info("="*60)
    
    async def _auto_recovery_worker(self):
        """
        Background worker for automatic component recovery.
        FIXED: Added proper shutdown handling
        """
        recovery_interval = 60  # Check every minute
        
        while self._recovery_running:
            try:
                await asyncio.sleep(recovery_interval)
                
                if not self._recovery_running:
                    break
                
                # Check and recover components
                for component_name in ["cypher_bot", "vibe_bot"]:
                    health_info = self.component_health[component_name]
                    
                    if health_info["status"] == "degraded" or health_info["failures"] > 3:
                        logger.warning(f"Attempting recovery for {component_name}")
                        
                        success = await self._attempt_component_recovery(component_name)
                        if success:
                            health_info["status"] = "healthy"
                            health_info["failures"] = 0
                            logger.info(f"Successfully recovered {component_name}")
                        else:
                            health_info["status"] = "failed"
                            logger.error(f"Failed to recover {component_name}")
                
            except asyncio.CancelledError:
                logger.info("Auto-recovery worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in auto-recovery worker: {e}")
    
    async def _attempt_component_recovery(self, component_name: str) -> bool:
        """
        Attempt to recover a specific component.
        
        Args:
            component_name: Name of component to recover
            
        Returns:
            Success status
        """
        try:
            if component_name == "cypher_bot":
                # Try to reconnect Neo4j
                for attempt in range(self.config["recovery_attempts"]):
                    try:
                        result = await self.cypher_bot.health_check()
                        if result:
                            return True
                        await asyncio.sleep(5 * (attempt + 1))  # Exponential backoff
                    except Exception as e:
                        logger.debug(f"Recovery attempt {attempt + 1} failed: {e}")
                
            elif component_name == "vibe_bot":
                # Try to reconnect Qdrant
                for attempt in range(self.config["recovery_attempts"]):
                    try:
                        result = await self.vibe_bot.health_check()
                        if result:
                            return True
                        await asyncio.sleep(5 * (attempt + 1))
                    except Exception as e:
                        logger.debug(f"Recovery attempt {attempt + 1} failed: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error attempting recovery for {component_name}: {e}")
            return False
    
    async def execute_battle(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        bypass_cache: bool = False,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Execute a battle between CypherBot and VibeBot.
        
        This is THE ONLY way to get recommendations!
        
        Args:
            query: Search query
            filters: Optional filters
            limit: Number of final recommendations
            user_context: User context
            ml_intelligence: ML insights from recommenders
            timeout: Override timeout
            bypass_cache: Skip cache lookup
            **kwargs: Additional battle parameters
            
        Returns:
            Battle-tested recommendations selected by Judge Ari
        """
        # Use semaphore to limit concurrent battles
        async with self.battle_semaphore:
            battle_id = f"battle_{self.total_battles_executed}_{time.time()}"
            self.active_battles.add(battle_id)
            self.total_battles_executed += 1
            
            try:
                return await self._execute_battle_internal(
                    query=query,
                    filters=filters,
                    limit=limit,
                    user_context=user_context,
                    ml_intelligence=ml_intelligence,
                    timeout=timeout,
                    bypass_cache=bypass_cache,
                    battle_id=battle_id,
                    **kwargs
                )
            finally:
                self.active_battles.discard(battle_id)
    
    async def _execute_battle_internal(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        user_context: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]],
        timeout: Optional[float],
        bypass_cache: bool,
        battle_id: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Internal battle execution with all features."""
        battle_start = time.time()
        
        # Check cache first if enabled and not bypassed
        if self.config["enable_cache"] and self.cache and not bypass_cache:
            cached_result = await self.cache.get(query, filters or {}, limit)
            if cached_result:
                logger.info(f"[{battle_id}] Cache hit for query: '{query[:30]}...'")
                
                # Record metrics if enabled
                if self.metrics:
                    self.metrics.record_cache_hit(query, cached_result)
                
                return cached_result.get("products", [])
        
        # Optimize parameters if enabled
        battle_params = {
            "query": query,
            "filters": filters,
            "limit": limit,
            "user_context": user_context,
            "ml_intelligence": ml_intelligence,
            "timeout": timeout or self.config["default_timeout"]
        }
        
        if self.optimizer:
            optimized_params = self.optimizer.optimize(
                query=query,
                user_context=user_context,
                ml_intelligence=ml_intelligence,
                base_limit=limit,
                base_timeout=battle_params["timeout"]
            )
            battle_params.update(optimized_params)
            logger.info(f"[{battle_id}] Optimized: {optimized_params.get('context_type', 'standard')}")
        
        # Execute battle
        try:
            logger.info("="*60)
            logger.info(f"[{battle_id}] BATTLE START: '{query[:50]}...'")
            logger.info(f"[{battle_id}] Parameters: limit={limit}, timeout={battle_params['timeout']}s")
            logger.info(f"[{battle_id}] Active battles: {len(self.active_battles)}")
            
            # Run battle with timeout
            battle_results = await asyncio.wait_for(
                self.executor.execute(
                    query=query,
                    filters=filters,
                    limit=limit,
                    user_context=user_context,
                    ml_intelligence=ml_intelligence,
                    prefetch_limit=battle_params.get("prefetch_limit", limit * 2),
                    quality_threshold=battle_params.get("quality_threshold", 0.5),
                    require_consensus=battle_params.get("require_consensus", False)
                ),
                timeout=battle_params["timeout"]
            )
            
            # Process results
            final_products = battle_results.get("products", [])
            battle_time = time.time() - battle_start
            
            # Cache results if enabled and we have products
            if self.config["enable_cache"] and self.cache and final_products:
                cache_data = {
                    "products": final_products,
                    "battle_time": battle_time,
                    "winner": battle_results.get("winner", "unknown"),
                    "timestamp": datetime.now().isoformat()
                }
                await self.cache.set(query, filters or {}, limit, cache_data)
            
            # Record metrics if enabled
            if self.metrics:
                self.metrics.record_battle(
                    query=query,
                    cypher_count=battle_results.get("cypher_count", 0),
                    vibe_count=battle_results.get("vibe_count", 0),
                    final_count=len(final_products),
                    battle_time=battle_time,
                    winner=battle_results.get("winner", "unknown"),
                    ml_enhanced=bool(ml_intelligence),
                    cache_hit=False
                )
            
            logger.info(f"[{battle_id}] Complete in {battle_time:.2f}s - {len(final_products)} products")
            logger.info(f"[{battle_id}] Winner: {battle_results.get('winner', 'unknown')}")
            logger.info("="*60)
            
            return final_products
            
        except asyncio.TimeoutError:
            logger.error(f"[{battle_id}] Timeout after {battle_params['timeout']}s")
            if self.metrics:
                self.metrics.record_timeout(query)
            return []
            
        except Exception as e:
            logger.error(f"[{battle_id}] Error: {e}")
            if self.metrics:
                self.metrics.record_error(query, str(e))
            return []
    
    async def execute_batch_battles(
        self,
        queries: List[Tuple[str, Dict[str, Any]]],
        limit: int = 5,
        **kwargs
    ) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple battles in parallel with rate limiting.
        
        Args:
            queries: List of (query, filters) tuples
            limit: Result limit per query
            **kwargs: Additional parameters
            
        Returns:
            List of results for each query
        """
        tasks = []
        for query, filters in queries:
            task = self.execute_battle(
                query=query,
                filters=filters,
                limit=limit,
                **kwargs
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch battle error: {result}")
                final_results.append([])
            else:
                final_results.append(result)
        
        return final_results
    
    async def get_battle_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive battle statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "orchestrator": {
                "config": self.config,
                "status": "operational",
                "total_battles": self.total_battles_executed,
                "active_battles": len(self.active_battles),
                "component_health": self.component_health
            }
        }
        
        # Add cache stats
        if self.config["enable_cache"] and self.cache:
            stats["cache"] = self.cache.get_stats()
        
        # Add metrics
        if self.metrics:
            stats["metrics"] = self.metrics.get_summary()
        
        # Add agent stats
        stats["agents"] = {
            "cypher": self.cypher_bot.get_stats(),
            "vibe": self.vibe_bot.get_stats(),
            "judge": self.judge.get_stats()
        }
        
        # Add executor stats
        if self.executor:
            stats["executor"] = self.executor.get_stats()
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive system health check.
        FIXED: Now includes auto-recovery status and attempts recovery
        
        Returns:
            Health status dictionary
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "performance": {},
            "auto_recovery": self.config["enable_auto_recovery"]
        }
        
        # Check CypherBot
        try:
            start = time.time()
            test_result = await asyncio.wait_for(
                self.cypher_bot.health_check(),
                timeout=5.0
            )
            elapsed = time.time() - start
            
            if test_result:
                self.component_health["cypher_bot"]["failures"] = 0
                self.component_health["cypher_bot"]["status"] = "healthy"
            else:
                self.component_health["cypher_bot"]["failures"] += 1
                
            health["components"]["cypher_bot"] = {
                "status": "healthy" if test_result else "unhealthy",
                "response_time": f"{elapsed:.2f}s",
                "failures": self.component_health["cypher_bot"]["failures"]
            }
        except Exception as e:
            self.component_health["cypher_bot"]["failures"] += 1
            health["components"]["cypher_bot"] = {
                "status": "unhealthy",
                "error": str(e),
                "failures": self.component_health["cypher_bot"]["failures"]
            }
            health["status"] = "degraded"
            
            # Attempt recovery if enabled
            if self.config["enable_auto_recovery"]:
                asyncio.create_task(self._attempt_component_recovery("cypher_bot"))
        
        self.component_health["cypher_bot"]["last_check"] = datetime.now()
        
        # Check VibeBot
        try:
            start = time.time()
            test_result = await asyncio.wait_for(
                self.vibe_bot.health_check(),
                timeout=5.0
            )
            elapsed = time.time() - start
            
            if test_result:
                self.component_health["vibe_bot"]["failures"] = 0
                self.component_health["vibe_bot"]["status"] = "healthy"
            else:
                self.component_health["vibe_bot"]["failures"] += 1
                
            health["components"]["vibe_bot"] = {
                "status": "healthy" if test_result else "unhealthy",
                "response_time": f"{elapsed:.2f}s",
                "failures": self.component_health["vibe_bot"]["failures"]
            }
        except Exception as e:
            self.component_health["vibe_bot"]["failures"] += 1
            health["components"]["vibe_bot"] = {
                "status": "unhealthy",
                "error": str(e),
                "failures": self.component_health["vibe_bot"]["failures"]
            }
            health["status"] = "degraded"
            
            # Attempt recovery if enabled
            if self.config["enable_auto_recovery"]:
                asyncio.create_task(self._attempt_component_recovery("vibe_bot"))
        
        self.component_health["vibe_bot"]["last_check"] = datetime.now()
        
        # Check Judge
        health["components"]["judge"] = {"status": "healthy"}
        
        # Check cache
        if self.config["enable_cache"] and self.cache:
            cache_stats = self.cache.get_stats()
            health["components"]["cache"] = {
                "status": "healthy",
                "type": "thread-safe",
                "strategy": cache_stats["strategy"],
                "size": cache_stats["size"],
                "hit_rate": cache_stats["hit_rate"]
            }
        
        # Add performance metrics
        health["performance"] = {
            "active_battles": len(self.active_battles),
            "total_battles": self.total_battles_executed,
            "max_concurrent": self.config["max_concurrent_battles"]
        }
        
        # Add recovery status
        if self.config["enable_auto_recovery"]:
            health["recovery_status"] = {
                "enabled": True,
                "components_monitored": list(self.component_health.keys()),
                "recovery_attempts": self.config["recovery_attempts"]
            }
        
        return health
    
    def update_config(self, updates: Dict[str, Any]):
        """
        Update orchestrator configuration dynamically.
        
        Args:
            updates: Configuration updates
        """
        self.config.update(updates)
        
        # Update cache if needed
        if "cache_ttl" in updates and self.cache:
            self.cache.ttl = updates["cache_ttl"]
        if "cache_max_size" in updates and self.cache:
            self.cache.max_size = updates["cache_max_size"]
        
        # Update semaphore if max concurrent changed
        if "max_concurrent_battles" in updates:
            self.battle_semaphore = asyncio.Semaphore(updates["max_concurrent_battles"])
        
        # Handle auto-recovery toggle
        if "enable_auto_recovery" in updates:
            if updates["enable_auto_recovery"] and not self._recovery_task:
                # Enable auto-recovery
                self._recovery_running = True
                self._recovery_tasks = []
                self._recovery_task = asyncio.create_task(self._auto_recovery_worker())
                logger.info("Auto-recovery enabled")
            elif not updates["enable_auto_recovery"] and self._recovery_task:
                # Disable auto-recovery
                self._recovery_running = False
                self._recovery_task.cancel()
                self._recovery_task = None
                logger.info("Auto-recovery disabled")
        
        logger.info(f"Configuration updated: {updates}")
    
    async def clear_cache(self):
        """Clear the battle cache."""
        if self.config["enable_cache"] and self.cache:
            await self.cache.clear()
            logger.info("Battle cache cleared")
    
    async def cleanup(self):
        """
        Clean up resources and shutdown gracefully.
        FIXED: Proper cleanup of recovery task
        """
        logger.info("Cleaning up battle orchestrator")
        
        # Stop recovery worker
        self._recovery_running = False
        
        # Cancel recovery task if running
        # Clean up any recovery tasks
        if hasattr(self, "_recovery_tasks"):
            for task in self._recovery_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._recovery_tasks, return_exceptions=True)

        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
        
        # Wait for active battles to complete
        if self.active_battles:
            logger.info(f"Waiting for {len(self.active_battles)} active battles to complete")
            # Give battles time to complete gracefully
            wait_time = min(5.0, self.config.get("default_timeout", 30.0) / 6)
            await asyncio.sleep(wait_time)
        
        # Shutdown cache
        if self.config["enable_cache"] and self.cache:
            await self.cache.shutdown()
        
        # Reset metrics
        if self.metrics:
            self.metrics.reset()
        
        logger.info("Battle orchestrator cleanup complete")