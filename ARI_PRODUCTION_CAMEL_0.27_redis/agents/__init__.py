"""
Battle Agents Package
Modernized CAMEL 0.2.7 implementation with RolePlay and memory for fashion recommendation battles
"""

import logging
from typing import Optional, Any

logger = logging.getLogger("agents")

# Import modernized agent implementations
try:
    from .cypher_bot_modernized import CypherBotModernized
    from .vibe_bot_modernized import VibeBotModernized
    from .judge_modernized import JudgeAriModernized
    MODERNIZED_AGENTS_AVAILABLE = True
    logger.info("Modernized CAMEL 0.2.7 agents loaded successfully")
except ImportError as e:
    logger.error(f"Failed to import modernized agents: {e}")
    MODERNIZED_AGENTS_AVAILABLE = False

# Import legacy agents for backwards compatibility
try:
    from .cypher_bot import CypherBotAgent
    from .vibe_bot import VibeBotAgent
    LEGACY_AGENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Legacy agents not available: {e}")
    LEGACY_AGENTS_AVAILABLE = False

# Version info
__version__ = "2.0.0"  # Updated for CAMEL 0.2.7
__author__ = "ARI Fashion System"

# Check CAMEL availability
try:
    import camel
    CAMEL_VERSION = "0.2.7"
    CAMEL_AVAILABLE = True
    logger.info(f"Agents package initialized with CAMEL {CAMEL_VERSION}")
except ImportError as e:
    logger.error(f"CAMEL 0.2.7 not available: {e}")
    CAMEL_AVAILABLE = False

# Agent registry for dynamic creation (prioritize modernized agents)
AGENT_REGISTRY = {}

if MODERNIZED_AGENTS_AVAILABLE:
    AGENT_REGISTRY.update({
        "cypher": CypherBotModernized,
        "cypherbot": CypherBotModernized,
        "vibe": VibeBotModernized,
        "vibebot": VibeBotModernized,
        "judge": JudgeAriModernized,
        "judgearai": JudgeAriModernized,
    })

# Fallback to legacy agents if modernized not available
if LEGACY_AGENTS_AVAILABLE and not MODERNIZED_AGENTS_AVAILABLE:
    AGENT_REGISTRY.update({
        "cypher": CypherBotAgent,
        "cypherbot": CypherBotAgent,
        "vibe": VibeBotAgent,
        "vibebot": VibeBotAgent,
    })

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
        "camel_available": CAMEL_AVAILABLE,
        "camel_version": CAMEL_VERSION if CAMEL_AVAILABLE else None,
        "modernized_agents": MODERNIZED_AGENTS_AVAILABLE,
        "legacy_agents": LEGACY_AGENTS_AVAILABLE,
        "agents_available": list(AGENT_REGISTRY.keys()),
        "errors": []
    }
    
    if not CAMEL_AVAILABLE:
        health["errors"].append("CAMEL 0.2.7 not available")
        health["status"] = "degraded"
    
    if not MODERNIZED_AGENTS_AVAILABLE:
        health["errors"].append("Modernized agents not available")
        if not LEGACY_AGENTS_AVAILABLE:
            health["status"] = "unhealthy"
        else:
            health["status"] = "degraded"
    
    if not AGENT_REGISTRY:
        health["errors"].append("No agents available")
        health["status"] = "unhealthy"
    
    return health

# Public API
__all__ = [
    # Modernized agent classes (preferred)
    "CypherBotModernized",
    "VibeBotModernized", 
    "JudgeAriModernized",
    
    # Legacy agent classes (backwards compatibility)
    "CypherBotAgent",
    "VibeBotAgent",
    
    # Factory and utilities
    "create_agent",
    "get_available_agents",
    "health_check",
    
    # Constants
    "AGENT_REGISTRY",
    "MODERNIZED_AGENTS_AVAILABLE",
    "LEGACY_AGENTS_AVAILABLE",
    "CAMEL_AVAILABLE",
    "CAMEL_VERSION",
    "__version__",
]

# Log package initialization
if MODERNIZED_AGENTS_AVAILABLE:
    logger.info(f"Agents package v{__version__} initialized with {len(AGENT_REGISTRY)} modernized agent types (CAMEL 0.2.7)")
elif LEGACY_AGENTS_AVAILABLE:
    logger.warning(f"Agents package v{__version__} initialized with {len(AGENT_REGISTRY)} legacy agent types")
else:
    logger.error(f"Agents package v{__version__} initialized with NO working agents")
