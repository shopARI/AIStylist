import logging
import asyncio
import time
import hashlib
import json
from typing import Dict, List, Any, Optional, Union

from services.battle.optimizer import BattleOptimizer
from services.battle.executor import BattleExecutor
from services.battle.metrics import BattleMetrics
from services.cache.battle_cache import BattleCache
from services.cache.redis_client import RedisService, FallbackRedisService

logger = logging.getLogger("services.battle.orchestrator")

class BattleOrchestrator:
    """
    Main orchestrator for CAMEL-powered battles.
    Dependencies are injected for testability and proper lifecycle management.
    """

    def __init__(
        self,
        executor: BattleExecutor,
        cache: Optional[BattleCache] = None,
        optimizer: Optional[BattleOptimizer] = None,
        metrics: Optional[BattleMetrics] = None,
        settings: Dict[str, Any] = None,
        redis_client: Optional[Union[RedisService, FallbackRedisService]] = None
    ):
        """
        Initializes the battle orchestrator with injected components.
        """
        logger.info("Initializing Battle Orchestrator")
        
        # Replace with VerboseExecutor for mind visibility
        from services.battle.verbose_executor import VerboseBattleExecutor
        if not isinstance(executor, VerboseBattleExecutor):
            self.executor = VerboseBattleExecutor(
                cypher_bot=executor.cypher_bot,
                vibe_bot=executor.vibe_bot,
                judge=executor.judge
            )
        else:
            self.executor = executor
        self.cache = cache
        self.optimizer = optimizer
        self.metrics = metrics
        self.redis_client = redis_client
        
        self.config = {
            "default_limit": 5,
            "default_timeout": 120.0,  # Increased for large Neo4j datasets with ML intelligence
            "prefetch_multiplier": 2,
            "quality_threshold": 0.5,
            "max_concurrent_battles": 50,  # Increased from 5 for production scale
        }
        if settings:
            self.config.update(settings)

        self.battle_semaphore = asyncio.Semaphore(self.config["max_concurrent_battles"])
        
        # Redis keys for distributed state
        self.active_battles_key = "battles:active"
        self.battle_counter_key = "battles:counter"

        logger.info("Battle Orchestrator initialized successfully")

    async def execute_battle(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Executes a battle between agents.
        """
        async with self.battle_semaphore:
            # Get and increment battle counter in Redis
            battle_count = await self._increment_battle_counter()
            battle_id = f"battle_{battle_count}_{time.time()}"
            
            # Track active battle in Redis
            await self._add_active_battle(battle_id)
            
            try:
                return await self._execute_battle_internal(
                    query=query,
                    filters=filters,
                    limit=limit,
                    user_context=user_context,
                    ml_intelligence=ml_intelligence,
                    conversation_context=conversation_context,
                    timeout=timeout,
                    bypass_cache=bypass_cache,
                    battle_id=battle_id
                )
            finally:
                # Remove from active battles in Redis
                await self._remove_active_battle(battle_id)

    async def _execute_battle_internal(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        user_context: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]],
        conversation_context: Optional[Dict[str, Any]],
        timeout: Optional[float],
        bypass_cache: bool,
        battle_id: str
    ) -> Dict[str, Any]:
        """Internal battle execution logic."""
        battle_start = time.time()
        
        if self.cache and not bypass_cache:
            cache_key = self._make_cache_key(query, filters or {}, limit)
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                logger.info(f"[{battle_id}] Cache hit for query: '{query[:30]}...'")
                if self.metrics:
                    self.metrics.record_cache_hit(query, cached_result)
                return cached_result
        
        # Determine the timeout for asyncio, but do not pass it to the executor
        execution_timeout = timeout or self.config["default_timeout"]

        battle_params = {
            "query": query,
            "filters": filters,
            "limit": limit,
            "user_context": user_context,
            "ml_intelligence": ml_intelligence,
            "conversation_context": conversation_context,
            "prefetch_limit": limit * self.config["prefetch_multiplier"],
            "quality_threshold": self.config["quality_threshold"],
        }
        
        if self.optimizer:
            optimized_params = self.optimizer.optimize(
                query=query,
                user_context=user_context,
                ml_intelligence=ml_intelligence,
                base_limit=limit
            )
            battle_params.update(optimized_params)

        battle_params.pop('timeout', None)
        battle_params.pop('include_details', None)

        executor_params = {
            'query': battle_params['query'],
            'filters': battle_params.get('filters'),
            'limit': battle_params.get('limit', 5),
            'user_context': battle_params.get('user_context'),
            'ml_intelligence': battle_params.get('ml_intelligence'),
            'conversation_context': battle_params.get('conversation_context'),
            'prefetch_limit': battle_params.get('prefetch_limit', 10),
            'quality_threshold': battle_params.get('quality_threshold', 0.5),
            'require_consensus': battle_params.get('require_consensus', False)
        }
        
        try:
            logger.info(f"[{battle_id}] BATTLE START: '{query[:50]}...'")
            
            # The timeout is handled by asyncio.wait_for, not by the executor itself
            battle_results = await asyncio.wait_for(
            self.executor.execute(**executor_params), 
            timeout=execution_timeout
        )
            
            battle_time = time.time() - battle_start
            
            if self.cache and battle_results.get("products"):
                # Cache only essential data to prevent Redis pollution (was caching ~100MB per request)
                cache_data = {
                    "products": battle_results.get("products", []),  # Final products only
                    "cypher_count": battle_results.get("cypher_count", 0),
                    "vibe_count": battle_results.get("vibe_count", 0),
                    "winner": battle_results.get("winner", "unknown"),
                    "execution_time": battle_time,
                    "ml_enhanced": bool(ml_intelligence),
                    "cached_at": time.time()
                }
                await self.cache.set(cache_key, cache_data, ttl=180)  # Reduced from 300s to prevent cache buildup
                logger.info(f"Cached optimized battle result: {len(cache_data['products'])} products, ~{len(str(cache_data))} bytes")
            
            if self.metrics:
                self.metrics.record_battle(
                    query=query,
                    cypher_count=battle_results.get("cypher_count", 0),
                    vibe_count=battle_results.get("vibe_count", 0),
                    final_count=len(battle_results.get("products", [])),
                    battle_time=battle_time,
                    winner=battle_results.get("winner", "unknown"),
                    ml_enhanced=bool(ml_intelligence)
                )

            logger.info(f"[{battle_id}] Battle complete in {battle_time:.2f}s")
            return battle_results

        except asyncio.TimeoutError:
            logger.error(f"[{battle_id}] Battle timed out after {execution_timeout}s")
            if self.metrics:
                self.metrics.record_timeout(query)
            return {"error": "Battle timed out"}
            
        except Exception as e:
            logger.error(f"[{battle_id}] Battle execution failed: {e}", exc_info=True)
            if self.metrics:
                self.metrics.record_error(query, str(e))
            return {"error": "An unexpected error occurred during the battle."}
    
    def _make_cache_key(self, query: str, filters: Dict, limit: int) -> str:
        """Creates a deterministic cache key."""
        key_data = {
            "query": query.lower().strip(),
            "filters": sorted(filters.items()),
            "limit": limit
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def get_stats(self) -> Dict[str, Any]:
        """Gets orchestrator statistics."""
        total_battles = await self._get_battle_counter()
        active_battles = await self._get_active_battles()
        
        stats = {
            "total_battles": total_battles,
            "active_battles": len(active_battles),
            "config": self.config
        }
        if self.cache:
            stats["cache"] = await self.cache.get_stats()
        if self.metrics:
            stats["metrics"] = self.metrics.get_summary()
        return stats
    
    # ==================== REDIS HELPER METHODS ====================
    
    async def _increment_battle_counter(self) -> int:
        """Increment and return battle counter in Redis."""
        if self.redis_client:
            try:
                # Use Redis INCR for atomic increment
                counter_key = self.battle_counter_key
                counter = await self.redis_client.client.incr(counter_key)
                return counter
            except Exception as e:
                logger.error(f"Failed to increment battle counter: {e}")
                return int(time.time())  # Fallback to timestamp
        else:
            # Fallback for no Redis
            return int(time.time())
    
    async def _get_battle_counter(self) -> int:
        """Get current battle counter from Redis."""
        if self.redis_client:
            try:
                counter = await self.redis_client.get(self.battle_counter_key)
                return int(counter) if counter else 0
            except Exception as e:
                logger.error(f"Failed to get battle counter: {e}")
                return 0
        return 0
    
    async def _add_active_battle(self, battle_id: str) -> bool:
        """Add battle to active battles set in Redis."""
        if self.redis_client:
            try:
                # Use Redis SET add operation
                result = await self.redis_client.client.sadd(self.active_battles_key, battle_id)
                # Set TTL for cleanup (battles shouldn't run longer than 1 hour)
                await self.redis_client.client.expire(self.active_battles_key, 3600)
                return bool(result)
            except Exception as e:
                logger.error(f"Failed to add active battle {battle_id}: {e}")
                return False
        return True
    
    async def _remove_active_battle(self, battle_id: str) -> bool:
        """Remove battle from active battles set in Redis."""
        if self.redis_client:
            try:
                result = await self.redis_client.client.srem(self.active_battles_key, battle_id)
                return bool(result)
            except Exception as e:
                logger.error(f"Failed to remove active battle {battle_id}: {e}")
                return False
        return True
    
    async def _get_active_battles(self) -> List[str]:
        """Get all active battles from Redis."""
        if self.redis_client:
            try:
                battles = await self.redis_client.client.smembers(self.active_battles_key)
                return list(battles) if battles else []
            except Exception as e:
                logger.error(f"Failed to get active battles: {e}")
                return []
        return []
