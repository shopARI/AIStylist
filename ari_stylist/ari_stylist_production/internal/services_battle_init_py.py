"""
Battle Service Package
Orchestrates fashion recommendation battles with caching and optimization
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("services.battle")

# Import battle components
from .orchestrator import BattleOrchestrator
from .optimizer import BattleOptimizer
from .executor import BattleExecutor
from .metrics import BattleMetrics

# Import cache (global instance)
from battle_cache import battle_cache

# Version info
__version__ = "1.0.0"

# Check dependencies
try:
    from agents import CypherBotAgent, VibeBotAgent, JudgeAriAgent
    AGENTS_AVAILABLE = True
except ImportError:
    logger.error("Battle agents not available")
    AGENTS_AVAILABLE = False

def create_battle_system(
    neo4j_client: Any,
    qdrant_client: Any,
    enable_cache: bool = True,
    enable_optimization: bool = True,
    enable_metrics: bool = True
) -> BattleOrchestrator:
    """
    Create a complete battle system.
    
    Args:
        neo4j_client: Neo4j database client
        qdrant_client: Qdrant database client
        enable_cache: Enable battle result caching
        enable_optimization: Enable parameter optimization
        enable_metrics: Enable metrics collection
        
    Returns:
        Configured BattleOrchestrator
    """
    if not AGENTS_AVAILABLE:
        raise RuntimeError("Battle agents not available - cannot create battle system")
    
    try:
        orchestrator = BattleOrchestrator(
            neo4j_client=neo4j_client,
            qdrant_client=qdrant_client,
            enable_cache=enable_cache,
            enable_optimization=enable_optimization,
            enable_metrics=enable_metrics
        )
        
        logger.info(
            f"Battle system created - cache: {enable_cache}, "
            f"optimization: {enable_optimization}, metrics: {enable_metrics}"
        )
        
        return orchestrator
        
    except Exception as e:
        logger.error(f"Failed to create battle system: {e}")
        raise RuntimeError(f"Battle system creation failed: {e}") from e

async def health_check() -> Dict[str, Any]:
    """
    Perform health check on battle service.
    
    Returns:
        Health status dictionary
    """
    health = {
        "status": "healthy",
        "agents_available": AGENTS_AVAILABLE,
        "cache_stats": None,
        "errors": []
    }
    
    # Check cache
    try:
        cache_stats = battle_cache.get_stats()
        health["cache_stats"] = cache_stats
    except Exception as e:
        health["errors"].append(f"Cache check failed: {e}")
        health["status"] = "degraded"
    
    # Check agents availability
    if not AGENTS_AVAILABLE:
        health["errors"].append("Battle agents not available")
        health["status"] = "unhealthy"
    
    return health

# Public API
__all__ = [
    # Core classes
    "BattleOrchestrator",
    "BattleOptimizer",
    "BattleExecutor",
    "BattleMetrics",
    
    # Factory
    "create_battle_system",
    
    # Utils
    "health_check",
    "battle_cache",
    
    # Constants
    "__version__",
    "AGENTS_AVAILABLE"
]

logger.info(f"Battle service v{__version__} initialized")
