"""
Battle Agents Package
Clean CAMEL 0.2.70 implementation for fashion recommendation battles
"""

import logging
from typing import Optional, Any

logger = logging.getLogger("agents")

# Import agent implementations
from .cypher_bot import CypherBotAgent
from .vibe_bot import VibeBotAgent

# Version info
__version__ = "1.0.0"
__author__ = "ARI Fashion System"

# Check CAMEL availability
try:
    from lib.camel.v070 import CAMEL_AVAILABLE, CAMEL_VERSION
    if CAMEL_AVAILABLE:
        logger.info(f"Agents package initialized with CAMEL {CAMEL_VERSION}")
    else:
        logger.error("CAMEL not available - agents will not function")
        raise RuntimeError("CAMEL 0.2.70+ is required for agents package")
except ImportError as e:
    logger.error(f"Failed to import CAMEL integration: {e}")
    raise RuntimeError("CAMEL integration module not found") from e

# Agent registry for dynamic creation
AGENT_REGISTRY = {
    "cypher": CypherBotAgent,
    "cypherbot": CypherBotAgent,
    "vibe": VibeBotAgent,
    "vibebot": VibeBotAgent,
}

def create_agent(
    agent_type: str,
    backend_client: Any,
    **kwargs
) -> Any:
    """
    Factory function to create agents.
    
    Args:
        agent_type: Type of agent ('cypher' or 'vibe')
        backend_client: Backend client (Neo4j for CypherBot, Qdrant for VibeBot)
        **kwargs: Additional arguments for agent initialization
        
    Returns:
        Agent instance
        
    Raises:
        ValueError: Unknown agent type
        RuntimeError: Agent creation failed
    """
    agent_type_lower = agent_type.lower()
    
    if agent_type_lower not in AGENT_REGISTRY:
        raise ValueError(
            f"Unknown agent type: {agent_type}. "
            f"Available: {list(AGENT_REGISTRY.keys())}"
        )
    
    agent_class = AGENT_REGISTRY[agent_type_lower]
    
    try:
        agent = agent_class(backend_client, **kwargs)
        logger.info(f"Created {agent_type} agent successfully")
        return agent
    except Exception as e:
        logger.error(f"Failed to create {agent_type} agent: {e}")
        raise RuntimeError(f"Agent creation failed: {e}") from e

def get_available_agents() -> list:
    """
    Get list of available agent types.
    
    Returns:
        List of agent type strings
    """
    return list(set(AGENT_REGISTRY.keys()))

async def health_check() -> dict:
    """
    Perform health check on agents module.
    
    Returns:
        Health status dictionary
    """
    health = {
        "status": "healthy",
        "camel_available": False,
        "agents_available": [],
        "errors": []
    }
    
    try:
        from lib.camel.v070 import CAMEL_AVAILABLE
        health["camel_available"] = CAMEL_AVAILABLE
    except Exception as e:
        health["errors"].append(f"CAMEL check failed: {e}")
        health["status"] = "unhealthy"
    
    # Check which agents can be imported
    for agent_name in ["cypher", "vibe"]:
        try:
            if agent_name in AGENT_REGISTRY:
                health["agents_available"].append(agent_name)
        except Exception as e:
            health["errors"].append(f"{agent_name} agent unavailable: {e}")
            health["status"] = "degraded"
    
    return health

# Public API
__all__ = [
    # Agent classes
    "CypherBotAgent",
    "VibeBotAgent",
    
    # Factory and utilities
    "create_agent",
    "get_available_agents",
    "health_check",
    
    # Constants
    "AGENT_REGISTRY",
    "__version__",
]

# Log package initialization
logger.info(f"Agents package v{__version__} initialized with {len(AGENT_REGISTRY)} agent types")
