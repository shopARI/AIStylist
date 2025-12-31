"""
Battle System Services
Orchestrates competitive battles between Neo4j and Qdrant agents
"""

import logging
from typing import Optional, Any, Dict

logger = logging.getLogger("services.battle")

# Import battle components
from .orchestrator import BattleOrchestrator
from .executor import BattleExecutor
from .optimizer import BattleOptimizer
from .metrics import BattleMetrics

# Version info
__version__ = "1.0.0"

# Create singleton instances for shared use
_orchestrator_instance: Optional[BattleOrchestrator] = None
_metrics_instance: Optional[BattleMetrics] = None

def get_battle_orchestrator(
    neo4j_client: Any = None,
    qdrant_client: Any = None,
    **kwargs
) -> BattleOrchestrator:
    """
    Get or create the global battle orchestrator.
    
    Args:
        neo4j_client: Neo4j client (required for first call)
        qdrant_client: Qdrant client (required for first call)
        **kwargs: Additional orchestrator configuration
        
    Returns:
        Global BattleOrchestrator instance
    """
    global _orchestrator_instance
    
    if _orchestrator_instance is None:
        if neo4j_client is None or qdrant_client is None:
            raise RuntimeError(
                "First call to get_battle_orchestrator requires both "
                "neo4j_client and qdrant_client"
            )
        
        _orchestrator_instance = BattleOrchestrator(
            neo4j_client=neo4j_client,
            qdrant_client=qdrant_client,
            **kwargs
        )
        logger.info("Created global BattleOrchestrator instance")
    
    return _orchestrator_instance

def get_battle_metrics() -> BattleMetrics:
    """
    Get or create the global battle metrics tracker.
    
    Returns:
        Global BattleMetrics instance
    """
    global _metrics_instance
    
    if _metrics_instance is None:
        _metrics_instance = BattleMetrics()
        logger.info("Created global BattleMetrics instance")
    
    return _metrics_instance

async def cleanup():
    """Clean up battle system resources."""
    global _orchestrator_instance, _metrics_instance
    
    if _orchestrator_instance:
        await _orchestrator_instance.cleanup()
        _orchestrator_instance = None
        
    if _metrics_instance:
        _metrics_instance.reset()
        _metrics_instance = None
    
    logger.info("Battle system cleanup complete")

# Public API
__all__ = [
    # Classes
    "BattleOrchestrator",
    "BattleExecutor", 
    "BattleOptimizer",
    "BattleMetrics",
    
    # Factory functions
    "get_battle_orchestrator",
    "get_battle_metrics",
    
    # Utilities
    "cleanup",
    
    # Constants
    "__version__",
]

logger.info(f"Battle system v{__version__} initialized")