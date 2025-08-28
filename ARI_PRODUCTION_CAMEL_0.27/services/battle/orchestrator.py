import logging
import asyncio
import time
import hashlib
import json
from typing import Dict, List, Any, Optional

from services.battle.optimizer import BattleOptimizer
from services.battle.executor import BattleExecutor
from services.battle.metrics import BattleMetrics
from services.cache.battle_cache import BattleCache

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
        settings: Dict[str, Any] = None
    ):
        """
        Initializes the battle orchestrator with injected components.
        """
        logger.info("Initializing Battle Orchestrator")
        
        self.executor = executor
        self.cache = cache
        self.optimizer = optimizer
        self.metrics = metrics
        
        self.config = {
            "default_limit": 5,
            "default_timeout": 30.0,
            "prefetch_multiplier": 2,
            "quality_threshold": 0.5,
            "max_concurrent_battles": 5,
        }
        if settings:
            self.config.update(settings)

        self.battle_semaphore = asyncio.Semaphore(self.config["max_concurrent_battles"])
        
        self.active_battles = set()
        self.total_battles_executed = 0

        logger.info("Battle Orchestrator initialized successfully")

    async def execute_battle(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Executes a battle between agents.
        """
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
                    battle_id=battle_id
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
            
            if self.cache and battle_results.get("final_products"):
                await self.cache.set(cache_key, battle_results, ttl=300)
            
            if self.metrics:
                self.metrics.record_battle(
                    query=query,
                    cypher_count=len(battle_results.get("cypher_products", [])),
                    vibe_count=len(battle_results.get("vibe_products", [])),
                    final_count=len(battle_results.get("final_products", [])),
                    battle_time=battle_time,
                    winner=battle_results.get("judgment", {}).get("winner"),
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
        stats = {
            "total_battles": self.total_battles_executed,
            "active_battles": len(self.active_battles),
            "config": self.config
        }
        if self.cache:
            stats["cache"] = await self.cache.get_stats()
        if self.metrics:
            stats["metrics"] = self.metrics.get_summary()
        return stats
