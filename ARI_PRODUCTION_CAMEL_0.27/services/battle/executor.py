"""
Battle Executor - Executes battles between agents
Handles parallel execution and result processing
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("services.battle.executor")

class BattleExecutor:
    """
    Executes battles between CypherBot and VibeBot with Judge evaluation.
    Handles parallel agent execution and result aggregation.
    """
    
    def __init__(
        self,
        cypher_bot,
        vibe_bot,
        judge
    ):
        """
        Initialize the battle executor.
        
        Args:
            cypher_bot: CypherBot agent instance
            vibe_bot: VibeBot agent instance
            judge: Judge Ari instance
        """
        self.cypher_bot = cypher_bot
        self.vibe_bot = vibe_bot
        self.judge = judge
        
        # Execution statistics
        self.stats = {
            "battles_executed": 0,
            "cypher_wins": 0,
            "vibe_wins": 0,
            "consensus_wins": 0,
            "avg_execution_time": 0.0,
            "total_execution_time": 0.0,  # Add this line
            "total_errors": 0
        }
        
        logger.info("BattleExecutor initialized with agents")
    
    async def execute(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        prefetch_limit: int = 10,
        quality_threshold: float = 0.5,
        require_consensus: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a battle between agents.
        
        Args:
            query: Search query
            filters: Search filters
            limit: Final result limit
            user_context: User context
            ml_intelligence: ML intelligence for agents
            conversation_context: Current conversation context (products, state, etc.)
            prefetch_limit: Number of products to fetch from each agent
            quality_threshold: Minimum quality score
            require_consensus: Whether to prioritize consensus products
            
        Returns:
            Battle results dictionary
        """
        start_time = time.time()
        self.stats["battles_executed"] += 1
        
        logger.info(f"Executing battle for: '{query[:50]}...'")
        
        try:
            # Prepare battle parameters
            battle_params = {
                "query": query,
                "limit": prefetch_limit,
                "filters": filters,
                "ml_intelligence": ml_intelligence,
                "user_context": user_context,
                "conversation_context": conversation_context
            }
            
            # Log conversation context if present (for product continuation)
            if conversation_context and conversation_context.get("current_products"):
                logger.info(f"Using conversation context with {len(conversation_context['current_products'])} current products")
            
            # Log ML enhancement if present
            if ml_intelligence:
                self._log_ml_enhancement(ml_intelligence)
            
            # Execute parallel searches
            cypher_results, vibe_results = await self._parallel_search(battle_params)
            
            logger.info(f"Search complete: CypherBot={len(cypher_results)}, VibeBot={len(vibe_results)}")
            
            # Apply consensus requirement if needed
            if require_consensus:
                cypher_results, vibe_results = self._apply_consensus_filter(
                    cypher_results, vibe_results, limit
                )
            
            # Judge evaluation
            judgment = await self.judge.evaluate(
                cypher_results=cypher_results,
                vibe_results=vibe_results,
                query=query,
                ml_context=ml_intelligence,
                user_context=user_context,
                limit=limit
            )
            
            # Apply quality threshold
            final_products = self._apply_quality_filter(
                judgment.get("products", []),
                quality_threshold
            )
            
            # Update statistics
            self._update_stats(judgment.get("winner", "unknown"))
            
            # Calculate execution time
            execution_time = time.time() - start_time
            self._update_avg_time(execution_time)
            
            # Build result with both agent results for Ari's review
            result = {
                "products": final_products,
                "cypher_products": cypher_results,  # Add CypherBot raw results
                "vibe_products": vibe_results,      # Add VibeBot raw results
                "cypher_count": len(cypher_results),
                "vibe_count": len(vibe_results),
                "winner": judgment.get("winner", "unknown"),
                "reasoning": judgment.get("reasoning", ""),
                "consensus_count": judgment.get("consensus_count", 0),
                "execution_time": execution_time,
                "quality_threshold_applied": quality_threshold,
                "ml_enhanced": bool(ml_intelligence),
                "judgment": judgment  # Include full judgment for detailed reasoning
            }
            
            logger.info(f"Battle executed in {execution_time:.2f}s - Winner: {result['winner']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Battle execution error: {e}")
            self.stats["total_errors"] += 1
            
            # Return empty result on error
            return {
                "products": [],
                "cypher_count": 0,
                "vibe_count": 0,
                "winner": "error",
                "reasoning": str(e),
                "consensus_count": 0,
                "execution_time": time.time() - start_time,
                "error": True
            }
    
    async def _parallel_search(
        self,
        battle_params: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Execute searches in parallel for both agents.
        
        Returns:
            Tuple of (cypher_results, vibe_results)
        """
        logger.info("Launching parallel agent searches...")
        
        # Create search tasks
        cypher_task = asyncio.create_task(
            self.cypher_bot.search(**battle_params)
        )
        
        vibe_task = asyncio.create_task(
            self.vibe_bot.search(**battle_params)
        )
        
        # Wait for both with error handling
        results = await asyncio.gather(
            cypher_task,
            vibe_task,
            return_exceptions=True
        )
        
        # Process results
        cypher_results = []
        vibe_results = []
        
        # Handle CypherBot results
        if isinstance(results[0], Exception):
            logger.error(f"CypherBot error: {results[0]}")
        else:
            cypher_results = results[0] if results[0] else []
        
        # Handle VibeBot results
        if isinstance(results[1], Exception):
            logger.error(f"VibeBot error: {results[1]}")
            # Also print to console for immediate visibility
            print(f"   VibeBot ERROR: {results[1]}")
            import traceback
            traceback.print_exception(type(results[1]), results[1], results[1].__traceback__)
        else:
            vibe_results = results[1] if results[1] else []
        
        return cypher_results, vibe_results
    
    def _apply_consensus_filter(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter to prioritize consensus products.
        
        Returns:
            Filtered (cypher_results, vibe_results)
        """
        # Find consensus products
        cypher_ids = {r.get("id") for r in cypher_results if r.get("id")}
        vibe_ids = {r.get("id") for r in vibe_results if r.get("id")}
        consensus_ids = cypher_ids & vibe_ids
        
        if consensus_ids:
            logger.info(f"Found {len(consensus_ids)} consensus products")
            
            # If we have enough consensus, prioritize them
            if len(consensus_ids) >= limit:
                # Filter to consensus only
                cypher_filtered = [
                    r for r in cypher_results
                    if r.get("id") in consensus_ids
                ][:limit]
                
                vibe_filtered = [
                    r for r in vibe_results
                    if r.get("id") in consensus_ids
                ][:limit]
                
                return cypher_filtered, vibe_filtered
        
        # Not enough consensus, return original
        return cypher_results, vibe_results
    
    def _apply_quality_filter(
        self,
        products: List[Dict[str, Any]],
        threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Filter products by quality score.

        Returns:
            Filtered products above threshold
        """
        if threshold <= 0:
            return products

        filtered = [
            p for p in products
            if p.get("judge_score", 0) >= threshold
        ]
        
        if len(filtered) < len(products):
            logger.info(f"Quality filter: {len(products)} -> {len(filtered)} (threshold: {threshold})")
        
        return filtered
    
    def _log_ml_enhancement(self, ml_intelligence: Dict[str, Any]):
        """Log ML enhancement details."""
        intel_sources = []
        
        if "cypher_intel" in ml_intelligence:
            intel_sources.extend(ml_intelligence["cypher_intel"].keys())
        
        if "vibe_intel" in ml_intelligence:
            intel_sources.extend(ml_intelligence["vibe_intel"].keys())
        
        if "shared_intel" in ml_intelligence:
            intel_sources.extend(ml_intelligence["shared_intel"].keys())
        
        if intel_sources:
            logger.info(f"ML Enhancement active: {', '.join(intel_sources)}")
    
    def _update_stats(self, winner: str):
        """Update execution statistics."""
        if winner == "cypher":
            self.stats["cypher_wins"] += 1
        elif winner == "vibe":
            self.stats["vibe_wins"] += 1
        elif winner == "consensus":
            self.stats["consensus_wins"] += 1
    
    def _update_avg_time(self, execution_time: float):
        """Update average execution time."""
        total = self.stats["battles_executed"]
        current_avg = self.stats["avg_execution_time"]
        self.stats["total_execution_time"] += execution_time
        self.stats["avg_execution_time"] = (
            self.stats["total_execution_time"] / total
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get executor statistics.
        
        Returns:
            Statistics dictionary
        """
        total = self.stats["battles_executed"]
        
        if total > 0:
            win_rates = {
                "cypher_win_rate": self.stats["cypher_wins"] / total * 100,
                "vibe_win_rate": self.stats["vibe_wins"] / total * 100,
                "consensus_win_rate": self.stats["consensus_wins"] / total * 100
            }
        else:
            win_rates = {
                "cypher_win_rate": 0,
                "vibe_win_rate": 0,
                "consensus_win_rate": 0
            }
        
        return {
            **self.stats,
            **win_rates,
            "error_rate": (
                self.stats["total_errors"] / total * 100
                if total > 0 else 0
            )
        }
    
    def reset_stats(self):
        """Reset executor statistics."""
        self.stats = {
            "battles_executed": 0,
            "cypher_wins": 0,
            "vibe_wins": 0,
            "consensus_wins": 0,
            "avg_execution_time": 0.0,
            "total_errors": 0
        }
        logger.info("Executor statistics reset")
