"""
Competitive Search System - COMPLETE CAMEL-AI POWERED ORCHESTRATOR
Manages the battle between CypherBot (Neo4j) and VibeBot (Qdrant)
Judge Ari (CAMEL agent) evaluates the results
Compatible with CAMEL-AI 0.2.64, ready for 0.2.7
"""

import logging
import asyncio
import time
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
import random

# Import battle components
from battle_cache import battle_cache
from battle_agents import CypherBotAgent, VibeBotAgent, JudgeAriAgent

# Import CAMEL components
from camel_imports import (
    CAMEL_AVAILABLE,
    ChatAgent,
    BaseMessage,
    CompatibilityLayer,
    ModelType
)

logger = logging.getLogger("competitive_search_system")

@dataclass
class BattleResult:
    """Structured battle result data"""
    query: str
    cypher_results: List[Dict[str, Any]]
    vibe_results: List[Dict[str, Any]]
    final_results: List[Dict[str, Any]]
    battle_time: float
    ml_enhanced: bool
    cache_hit: bool = False
    battle_id: str = field(default_factory=lambda: hashlib.md5(
        f"{datetime.now().isoformat()}".encode()
    ).hexdigest()[:8])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "battle_id": self.battle_id,
            "query": self.query,
            "cypher_count": len(self.cypher_results),
            "vibe_count": len(self.vibe_results),
            "final_count": len(self.final_results),
            "battle_time": self.battle_time,
            "ml_enhanced": self.ml_enhanced,
            "cache_hit": self.cache_hit
        }

class BattleMetrics:
    """Track detailed battle metrics"""

    def __init__(self):
        self.battles = []
        self.agent_wins = Counter()
        self.consensus_count = 0
        self.total_battle_time = 0.0
        self.ml_enhancement_count = 0
        self.cache_performance = {
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0
        }
        self.error_count = 0
        self.timeout_count = 0

    def record_battle(self, result: BattleResult):
        """Record a battle result"""
        self.battles.append(result.to_dict())

        # Keep only last 1000 battles
        if len(self.battles) > 1000:
            self.battles = self.battles[-1000:]

        # Update metrics
        self.total_battle_time += result.battle_time

        if result.ml_enhanced:
            self.ml_enhancement_count += 1

        if result.cache_hit:
            self.cache_performance["hits"] += 1
        else:
            self.cache_performance["misses"] += 1

        # Update hit rate
        total_requests = self.cache_performance["hits"] + self.cache_performance["misses"]
        if total_requests > 0:
            self.cache_performance["hit_rate"] = (
                self.cache_performance["hits"] / total_requests * 100
            )

        # Count agent wins
        for product in result.final_results:
            agents = product.get("winning_agents", [])
            if len(agents) == 2:
                self.consensus_count += 1
            else:
                for agent in agents:
                    self.agent_wins[agent] += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        total_battles = len(self.battles)

        if total_battles == 0:
            return {"message": "No battles yet"}

        return {
            "total_battles": total_battles,
            "avg_battle_time": self.total_battle_time / total_battles,
            "ml_enhancement_rate": self.ml_enhancement_count / total_battles * 100,
            "cache_hit_rate": self.cache_performance["hit_rate"],
            "agent_wins": dict(self.agent_wins),
            "consensus_rate": self.consensus_count / sum(self.agent_wins.values()) * 100 if self.agent_wins else 0,
            "error_rate": self.error_count / total_battles * 100 if total_battles > 0 else 0,
            "timeout_rate": self.timeout_count / total_battles * 100 if total_battles > 0 else 0,
            "recent_battles": self.battles[-10:]
        }

class BattleOptimizer:
    """Optimize battle parameters based on context"""

    def __init__(self):
        self.optimization_rules = {
            "luxury": {
                "prefetch_multiplier": 3,
                "quality_threshold": 0.7,
                "timeout_extension": 1.5,
                "require_consensus": True
            },
            "quick_browse": {
                "prefetch_multiplier": 1.5,
                "quality_threshold": 0.5,
                "timeout_extension": 0.7,
                "require_consensus": False
            },
            "wardrobe_building": {
                "prefetch_multiplier": 2.5,
                "quality_threshold": 0.6,
                "timeout_extension": 1.2,
                "require_consensus": True
            },
            "trending": {
                "prefetch_multiplier": 2,
                "quality_threshold": 0.5,
                "timeout_extension": 1.0,
                "require_consensus": False
            }
        }

    def optimize_parameters(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]],
        base_limit: int,
        base_timeout: float
    ) -> Dict[str, Any]:
        """Optimize battle parameters based on context"""

        # Detect context
        context_type = self._detect_context(query, user_context, ml_intelligence)

        # Get optimization rules
        rules = self.optimization_rules.get(context_type, {})

        # Apply optimizations
        return {
            "prefetch_limit": int(base_limit * rules.get("prefetch_multiplier", 2)),
            "quality_threshold": rules.get("quality_threshold", 0.5),
            "timeout": base_timeout * rules.get("timeout_extension", 1.0),
            "require_consensus": rules.get("require_consensus", False),
            "context_type": context_type
        }

    def _detect_context(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> str:
        """Detect the context type"""
        query_lower = query.lower() if query else ""

        # Check for luxury indicators
        luxury_keywords = ["luxury", "designer", "premium", "exclusive", "haute"]
        if any(keyword in query_lower for keyword in luxury_keywords):
            return "luxury"

        # Check user context for VIP
        if user_context and user_context.get("vip_client"):
            return "luxury"

        # Check ML intelligence for high-value user
        if ml_intelligence and "cypher_intel" in ml_intelligence:
            rfm = ml_intelligence["cypher_intel"].get("rfm", {})
            if rfm.get("user_value", 0) > 0.8:
                return "luxury"

        # Check for wardrobe building
        wardrobe_keywords = ["wardrobe", "capsule", "essentials", "basics", "complete"]
        if any(keyword in query_lower for keyword in wardrobe_keywords):
            return "wardrobe_building"

        # Check for trending
        trending_keywords = ["trending", "popular", "hot", "latest", "new"]
        if any(keyword in query_lower for keyword in trending_keywords):
            return "trending"

        # Default to quick browse
        return "quick_browse"

class CompetitiveSearchSystem:
    """
    Orchestrates CAMEL-AI powered battles between Neo4j and Qdrant approaches.
    This is the CORE of the recommendation system - ALL paths lead here.
    """

    def __init__(
        self,
        neo4j_client,
        qdrant_client,
        model_type=None
    ):
        """
        Initialize the competitive search system with CAMEL agents.

        Args:
            neo4j_client: UserKnowledgeGraphAsync for Neo4j
            qdrant_client: ProductRetrieverAsync for Qdrant
            model_type: CAMEL model type for agents
        """
        logger.info("="*60)
        logger.info("Initializing CAMEL-powered Competitive Search System")
        logger.info("="*60)

        # Initialize CAMEL battle agents
        self.cypher_bot = CypherBotAgent(neo4j_client, model_type)
        self.vibe_bot = VibeBotAgent(qdrant_client, model_type)
        self.judge = JudgeAriAgent(model_type)

        # Initialize optimization and metrics
        self.optimizer = BattleOptimizer()
        self.metrics = BattleMetrics()

        # Battle history for analysis
        self.battle_history = OrderedDict()
        self.max_history_size = 100

        # Configuration
        self.config = {
            "default_limit": 5,
            "default_timeout": 30.0,
            "default_prefetch_multiplier": 2,
            "enable_optimization": True,
            "enable_caching": True,
            "enable_ml_enhancement": True
        }

        logger.info("Battle system components initialized:")
        logger.info(f"  - CypherBot: {'CAMEL' if self.cypher_bot.agent else 'Fallback'} mode")
        logger.info(f"  - VibeBot: {'CAMEL' if self.vibe_bot.agent else 'Fallback'} mode")
        logger.info(f"  - Judge Ari: {'CAMEL' if self.judge.agent else 'Fallback'} mode")
        logger.info("="*60)

    async def execute_battle(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        prefetch_limit: Optional[int] = None,
        timeout: Optional[float] = None,
        quality_threshold: float = 0.5,
        require_consensus: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute a CAMEL-powered battle between Neo4j and Qdrant.

        This is THE ONLY way to get recommendations!

        Args:
            query: Search query
            filters: Optional filters
            limit: Number of final recommendations
            user_context: User context (user_id, session_id, etc.)
            ml_intelligence: ML insights from recommenders
            prefetch_limit: Override for prefetch limit
            timeout: Override for timeout
            quality_threshold: Minimum quality score for results
            require_consensus: Whether to require both agents to agree

        Returns:
            Battle-tested recommendations selected by Judge Ari
        """
        battle_start = time.time()

        # Optimize parameters if enabled
        if self.config["enable_optimization"]:
            optimization = self.optimizer.optimize_parameters(
                query, user_context, ml_intelligence,
                limit, timeout or self.config["default_timeout"]
            )

            # Apply optimizations if not overridden
            if prefetch_limit is None:
                prefetch_limit = optimization["prefetch_limit"]
            if timeout is None:
                timeout = optimization["timeout"]
            quality_threshold = optimization.get("quality_threshold", quality_threshold)
            require_consensus = optimization.get("require_consensus", require_consensus)

            logger.info(f"Battle optimization: {optimization['context_type']} context detected")
        else:
            # Use defaults
            if prefetch_limit is None:
                prefetch_limit = limit * self.config["default_prefetch_multiplier"]
            if timeout is None:
                timeout = self.config["default_timeout"]

        # Check cache if enabled
        cache_key = None
        if self.config["enable_caching"]:
            cache_key = self._create_cache_key(query, filters, limit, ml_intelligence)

            cached_result = battle_cache.get(
                cache_key["query"],
                cache_key["filters"],
                limit
            )

            if cached_result:
                # Record cache hit
                result = BattleResult(
                    query=query,
                    cypher_results=[],
                    vibe_results=[],
                    final_results=cached_result,
                    battle_time=time.time() - battle_start,
                    ml_enhanced=bool(ml_intelligence),
                    cache_hit=True
                )
                self.metrics.record_battle(result)

                logger.info(f"Cache hit for query: '{query[:30]}...'")
                return cached_result

        # Execute the actual battle
        try:
            logger.info("="*60)
            logger.info(f"BATTLE START: '{query[:50]}...'")
            logger.info(f"Parameters: limit={limit}, prefetch={prefetch_limit}, timeout={timeout}s")

            # Run battle with timeout
            battle_results = await asyncio.wait_for(
                self._execute_battle_internal(
                    query, filters, limit,
                    user_context, ml_intelligence,
                    prefetch_limit, quality_threshold,
                    require_consensus
                ),
                timeout=timeout
            )

            # Calculate battle time
            battle_time = time.time() - battle_start

            # Create battle result
            result = BattleResult(
                query=query,
                cypher_results=battle_results.get("cypher_results", []),
                vibe_results=battle_results.get("vibe_results", []),
                final_results=battle_results.get("final_results", []),
                battle_time=battle_time,
                ml_enhanced=bool(ml_intelligence),
                cache_hit=False
            )

            # Record metrics
            self.metrics.record_battle(result)

            # Cache results if enabled
            if self.config["enable_caching"] and cache_key:
                battle_cache.set(
                    cache_key["query"],
                    cache_key["filters"],
                    limit,
                    result.final_results
                )

            # Store in history
            self._store_battle_history(result)

            logger.info(f"Battle complete in {battle_time:.2f}s")
            logger.info("="*60)

            return result.final_results

        except asyncio.TimeoutError:
            self.metrics.timeout_count += 1
            logger.error(f"Battle timeout after {timeout}s")
            return []

        except Exception as e:
            self.metrics.error_count += 1
            logger.error(f"Battle error: {e}")
            return []

    async def _execute_battle_internal(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        user_context: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]],
        prefetch_limit: int,
        quality_threshold: float,
        require_consensus: bool
    ) -> Dict[str, Any]:
        """
        Internal battle execution with CAMEL agents.
        """
        # Prepare battle parameters
        battle_params = {
            "query": query,
            "limit": prefetch_limit,
            "filters": filters,
            "ml_intelligence": ml_intelligence if self.config["enable_ml_enhancement"] else None,
            "user_context": user_context
        }

        # Log ML enhancement
        if ml_intelligence and self.config["enable_ml_enhancement"]:
            intel_sources = []
            if "cypher_intel" in ml_intelligence:
                intel_sources.extend(ml_intelligence["cypher_intel"].keys())
            if "vibe_intel" in ml_intelligence:
                intel_sources.extend(ml_intelligence["vibe_intel"].keys())
            logger.info(f"ML Enhancement: {', '.join(intel_sources)}")

        # Launch both agents in parallel
        logger.info("Agents searching...")

        cypher_task = asyncio.create_task(
            self.cypher_bot.search(**battle_params)
        )

        vibe_task = asyncio.create_task(
            self.vibe_bot.search(**battle_params)
        )

        # Wait for both agents
        cypher_results, vibe_results = await asyncio.gather(
            cypher_task, vibe_task,
            return_exceptions=True
        )

        # Handle errors
        if isinstance(cypher_results, Exception):
            logger.error(f"CypherBot error: {cypher_results}")
            cypher_results = []

        if isinstance(vibe_results, Exception):
            logger.error(f"VibeBot error: {vibe_results}")
            vibe_results = []

        logger.info(
            f"Search complete: CypherBot={len(cypher_results)}, "
            f"VibeBot={len(vibe_results)}"
        )

        # Apply consensus requirement if enabled
        if require_consensus:
            consensus_results = self._find_consensus(cypher_results, vibe_results)
            logger.info(f"Consensus products: {len(consensus_results)}")

            # If we have enough consensus, use those
            if len(consensus_results) >= limit:
                cypher_results = consensus_results
                vibe_results = consensus_results

        # Judge evaluates
        logger.info("Judge Ari evaluating...")

        final_results = await self.judge.evaluate(
            cypher_results,
            vibe_results,
            query,
            ml_context=ml_intelligence,
            user_context=user_context,
            limit=limit
        )

        # Apply quality threshold
        quality_filtered = [
            r for r in final_results
            if r.get("judge_score", 0) >= quality_threshold
        ]

        if len(quality_filtered) < len(final_results):
            logger.info(
                f"Quality filter: {len(final_results)} -> {len(quality_filtered)} "
                f"(threshold: {quality_threshold})"
            )

        # Log results
        self._log_battle_results(quality_filtered)

        return {
            "cypher_results": cypher_results,
            "vibe_results": vibe_results,
            "final_results": quality_filtered
        }

    def _find_consensus(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find products both agents agree on"""
        consensus = []

        # Create ID sets
        cypher_ids = {r.get("id") for r in cypher_results if r.get("id")}
        vibe_ids = {r.get("id") for r in vibe_results if r.get("id")}

        # Find intersection
        common_ids = cypher_ids & vibe_ids

        # Combine results for common products
        for product_id in common_ids:
            # Get from both lists
            cypher_product = next(
                (r for r in cypher_results if r.get("id") == product_id),
                None
            )
            vibe_product = next(
                (r for r in vibe_results if r.get("id") == product_id),
                None
            )

            if cypher_product and vibe_product:
                # Merge information
                merged = cypher_product.copy()
                merged["vibe_score"] = vibe_product.get("vibe_score", 0)
                merged["vibe_reason"] = vibe_product.get("vibe_reason", "")
                merged["consensus"] = True
                consensus.append(merged)

        return consensus

    def _create_cache_key(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int,
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create cache key including ML intelligence signature"""
        # Create ML signature
        ml_signature = ""
        if ml_intelligence:
            intel_keys = []
            if "cypher_intel" in ml_intelligence:
                intel_keys.extend(ml_intelligence["cypher_intel"].keys())
            if "vibe_intel" in ml_intelligence:
                intel_keys.extend(ml_intelligence["vibe_intel"].keys())

            if intel_keys:
                ml_signature = hashlib.md5(
                    ",".join(sorted(intel_keys)).encode()
                ).hexdigest()[:8]

        # Modify query to include ML signature
        cache_query = f"{query}:ml={ml_signature}" if ml_signature else query

        return {
            "query": cache_query,
            "filters": filters or {},
            "limit": limit
        }

    def _log_battle_results(self, results: List[Dict[str, Any]]):
        """Log battle results summary"""
        if not results:
            logger.info("No products passed quality threshold")
            return

        # Count wins by agent
        agent_wins = Counter()
        consensus_count = 0

        for r in results:
            agents = r.get("winning_agents", [])
            if len(agents) == 2:
                consensus_count += 1
            else:
                for agent in agents:
                    agent_wins[agent] += 1

        # Log summary
        logger.info(
            f"Winners: Total={len(results)}, "
            f"CypherBot={agent_wins.get('CypherBot', 0)}, "
            f"VibeBot={agent_wins.get('VibeBot', 0)}, "
            f"Consensus={consensus_count}"
        )

        # Log top product
        if results:
            top = results[0]
            logger.info(
                f"Top: {top.get('title', 'Unknown')[:30]}... "
                f"(Score: {top.get('judge_score', 0):.2f})"
            )

    def _store_battle_history(self, result: BattleResult):
        """Store battle in history"""
        self.battle_history[result.battle_id] = result

        # Maintain size limit
        if len(self.battle_history) > self.max_history_size:
            # Remove oldest
            oldest_key = next(iter(self.battle_history))
            del self.battle_history[oldest_key]

    async def analyze_battle_performance(
        self,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Analyze battle performance over time

        Args:
            time_window: Time window to analyze (default: all time)

        Returns:
            Performance analysis
        """
        analysis = {
            "metrics": self.metrics.get_summary(),
            "cache_stats": battle_cache.get_stats(),
            "recent_battles": []
        }

        # Analyze recent battles
        for battle_id, battle in list(self.battle_history.items())[-10:]:
            analysis["recent_battles"].append({
                "id": battle_id,
                "query": battle.query[:30] + "...",
                "time": battle.battle_time,
                "results": len(battle.final_results),
                "ml_enhanced": battle.ml_enhanced
            })

        # Agent performance
        if self.metrics.agent_wins:
            total_wins = sum(self.metrics.agent_wins.values())
            analysis["agent_performance"] = {
                agent: (wins / total_wins * 100)
                for agent, wins in self.metrics.agent_wins.items()
            }

        return analysis

    def get_battle_stats(self) -> Dict[str, Any]:
        """Get comprehensive battle statistics"""
        return {
            "system_status": {
                "cypher_bot": "active" if self.cypher_bot.agent else "fallback",
                "vibe_bot": "active" if self.vibe_bot.agent else "fallback",
                "judge": "active" if self.judge.agent else "fallback",
                "camel_available": CAMEL_AVAILABLE
            },
            "configuration": self.config,
            "metrics": self.metrics.get_summary(),
            "cache": battle_cache.get_stats(),
            "optimization_rules": self.optimizer.optimization_rules,
            "battle_history_size": len(self.battle_history)
        }

    def update_config(self, config_updates: Dict[str, Any]):
        """Update system configuration"""
        self.config.update(config_updates)
        logger.info(f"Configuration updated: {config_updates}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform system health check"""
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }

        # Check CypherBot
        try:
            test_result = await self.cypher_bot.search("test", limit=1)
            health["components"]["cypher_bot"] = "healthy"
        except Exception as e:
            health["components"]["cypher_bot"] = f"unhealthy: {e}"
            health["status"] = "degraded"

        # Check VibeBot
        try:
            test_result = await self.vibe_bot.search("test", limit=1)
            health["components"]["vibe_bot"] = "healthy"
        except Exception as e:
            health["components"]["vibe_bot"] = f"unhealthy: {e}"
            health["status"] = "degraded"

        # Check Judge
        health["components"]["judge"] = "healthy" if self.judge.agent else "fallback"

        # Check cache
        cache_stats = battle_cache.get_stats()
        health["components"]["cache"] = {
            "size": cache_stats["size"],
            "hit_rate": cache_stats["hit_rate"]
        }

        return health