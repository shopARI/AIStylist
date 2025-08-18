"""
Agent Factory for CAMEL 0.2.70
Clean factory pattern for creating battle and stylist agents
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

logger = logging.getLogger("agents.factory")

# Import from CAMEL 0.2.70 module
from lib.camel.v070 import (
    create_agent,
    create_stylist_agent,
    create_battle_agent,
    create_memory,
    CAMEL_AVAILABLE,
    ModelType
)

# Import prompts
from config.prompts import (
    ARI_STYLIST_PROMPT,
    CYPHERBOT_PROMPT,
    VIBEBOT_PROMPT,
    JUDGE_ARI_PROMPT,
    MEMORY_HANDLER_PROMPT,
    GREETING_HANDLER_PROMPT,
    PRODUCT_RESPONSE_PROMPT
)

# Import agent implementations
from .cypher_bot import CypherBotAgent
from .vibe_bot import VibeBotAgent
from .judge import JudgeAriAgent

class AgentFactory:
    """
    Factory for creating all agent types with CAMEL 0.2.70.
    Centralized agent creation with consistent patterns.
    """
    
    def __init__(self):
        """Initialize the agent factory."""
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL 0.2.70+ is required for AgentFactory")
        
        self.created_agents = {}
        self.agent_metrics = {}
        self.creation_count = 0
        
        logger.info("AgentFactory initialized for CAMEL 0.2.70")
    
    async def create_stylist_agent(
        self,
        memory: Optional[Any] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Create Ari stylist agent with exact personality.
        
        Args:
            memory: Optional memory instance
            temperature: Model temperature
            max_tokens: Maximum tokens
            agent_id: Optional agent ID
            
        Returns:
            Configured stylist agent
        """
        agent_id = agent_id or f"stylist_{uuid.uuid4().hex[:8]}"
        
        try:
            # Use the EXACT prompt from config
            agent = create_stylist_agent(
                personality=ARI_STYLIST_PROMPT,
                memory=memory,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Track creation
            self._track_agent_creation(agent_id, "stylist", agent)
            
            logger.info(f"Created stylist agent: {agent_id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create stylist agent: {e}")
            raise RuntimeError(f"Stylist agent creation failed: {e}") from e
    
    async def create_cypher_bot(
        self,
        neo4j_client: Any,
        agent_id: Optional[str] = None
    ) -> CypherBotAgent:
        """
        Create CypherBot agent.
        
        Args:
            neo4j_client: Neo4j database client
            agent_id: Optional agent ID
            
        Returns:
            CypherBot agent instance
        """
        agent_id = agent_id or f"cypher_{uuid.uuid4().hex[:8]}"
        
        try:
            agent = CypherBotAgent(neo4j_client)
            
            # Track creation
            self._track_agent_creation(agent_id, "cypher", agent)
            
            logger.info(f"Created CypherBot: {agent_id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create CypherBot: {e}")
            raise RuntimeError(f"CypherBot creation failed: {e}") from e
    
    async def create_vibe_bot(
        self,
        qdrant_client: Any,
        agent_id: Optional[str] = None
    ) -> VibeBotAgent:
        """
        Create VibeBot agent.
        
        Args:
            qdrant_client: Qdrant database client
            agent_id: Optional agent ID
            
        Returns:
            VibeBot agent instance
        """
        agent_id = agent_id or f"vibe_{uuid.uuid4().hex[:8]}"
        
        try:
            agent = VibeBotAgent(qdrant_client)
            
            # Track creation
            self._track_agent_creation(agent_id, "vibe", agent)
            
            logger.info(f"Created VibeBot: {agent_id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create VibeBot: {e}")
            raise RuntimeError(f"VibeBot creation failed: {e}") from e
    
    async def create_judge_ari(
        self,
        agent_id: Optional[str] = None
    ) -> JudgeAriAgent:
        """
        Create Judge Ari agent.
        
        Args:
            agent_id: Optional agent ID
            
        Returns:
            Judge Ari agent instance
        """
        agent_id = agent_id or f"judge_{uuid.uuid4().hex[:8]}"
        
        try:
            agent = JudgeAriAgent()
            
            # Track creation
            self._track_agent_creation(agent_id, "judge", agent)
            
            logger.info(f"Created Judge Ari: {agent_id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create Judge Ari: {e}")
            raise RuntimeError(f"Judge Ari creation failed: {e}") from e
    
    async def create_specialized_agent(
        self,
        agent_type: str,
        system_message: str,
        memory: Optional[Any] = None,
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Create a specialized agent with custom prompt.
        
        Args:
            agent_type: Type of agent for tracking
            system_message: System prompt for agent
            memory: Optional memory instance
            tools: Optional list of tools
            temperature: Model temperature
            max_tokens: Maximum tokens
            agent_id: Optional agent ID
            
        Returns:
            Configured CAMEL agent
        """
        agent_id = agent_id or f"{agent_type}_{uuid.uuid4().hex[:8]}"
        
        try:
            agent = create_agent(
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                memory=memory
            )
            
            # Track creation
            self._track_agent_creation(agent_id, agent_type, agent)
            
            logger.info(f"Created specialized agent: {agent_id} ({agent_type})")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create {agent_type} agent: {e}")
            raise RuntimeError(f"{agent_type} agent creation failed: {e}") from e
    
    async def create_memory_handler_agent(
        self,
        memory: Optional[Any] = None,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Create memory handler agent for meta-questions.
        
        Args:
            memory: Optional memory instance
            agent_id: Optional agent ID
            
        Returns:
            Memory handler agent
        """
        return await self.create_specialized_agent(
            agent_type="memory_handler",
            system_message=MEMORY_HANDLER_PROMPT,
            memory=memory,
            agent_id=agent_id
        )
    
    async def create_greeting_handler_agent(
        self,
        memory: Optional[Any] = None,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Create greeting handler agent.
        
        Args:
            memory: Optional memory instance
            agent_id: Optional agent ID
            
        Returns:
            Greeting handler agent
        """
        return await self.create_specialized_agent(
            agent_type="greeting_handler",
            system_message=GREETING_HANDLER_PROMPT,
            memory=memory,
            agent_id=agent_id
        )
    
    async def create_product_response_agent(
        self,
        memory: Optional[Any] = None,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Create product response generator agent.
        
        Args:
            memory: Optional memory instance
            agent_id: Optional agent ID
            
        Returns:
            Product response agent
        """
        return await self.create_specialized_agent(
            agent_type="product_response",
            system_message=PRODUCT_RESPONSE_PROMPT,
            memory=memory,
            agent_id=agent_id
        )
    
    async def create_battle_agents(
        self,
        neo4j_client: Any,
        qdrant_client: Any
    ) -> Dict[str, Any]:
        """
        Create all battle agents at once.
        
        Args:
            neo4j_client: Neo4j database client
            qdrant_client: Qdrant database client
            
        Returns:
            Dictionary with all battle agents
        """
        try:
            # Create all agents in parallel
            cypher_task = asyncio.create_task(
                self.create_cypher_bot(neo4j_client)
            )
            vibe_task = asyncio.create_task(
                self.create_vibe_bot(qdrant_client)
            )
            judge_task = asyncio.create_task(
                self.create_judge_ari()
            )
            
            # Wait for all
            cypher_bot, vibe_bot, judge = await asyncio.gather(
                cypher_task, vibe_task, judge_task
            )
            
            return {
                "cypher": cypher_bot,
                "vibe": vibe_bot,
                "judge": judge
            }
            
        except Exception as e:
            logger.error(f"Failed to create battle agents: {e}")
            raise RuntimeError(f"Battle agents creation failed: {e}") from e
    
    def _track_agent_creation(
        self,
        agent_id: str,
        agent_type: str,
        agent_instance: Any
    ):
        """Track agent creation for metrics."""
        self.creation_count += 1
        
        self.created_agents[agent_id] = {
            "type": agent_type,
            "instance": agent_instance,
            "created_at": datetime.now().isoformat(),
            "creation_number": self.creation_count
        }
        
        # Update metrics
        if agent_type not in self.agent_metrics:
            self.agent_metrics[agent_type] = {
                "total_created": 0,
                "active": 0,
                "last_created": None
            }
        
        self.agent_metrics[agent_type]["total_created"] += 1
        self.agent_metrics[agent_type]["active"] += 1
        self.agent_metrics[agent_type]["last_created"] = datetime.now().isoformat()
    
    def get_agent(self, agent_id: str) -> Optional[Any]:
        """
        Get agent by ID.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent instance or None
        """
        agent_info = self.created_agents.get(agent_id)
        return agent_info["instance"] if agent_info else None
    
    def get_all_agents(self, agent_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all agents, optionally filtered by type.
        
        Args:
            agent_type: Optional type filter
            
        Returns:
            List of agent info dictionaries
        """
        if agent_type:
            return [
                {"id": aid, **info}
                for aid, info in self.created_agents.items()
                if info["type"] == agent_type
            ]
        else:
            return [
                {"id": aid, **info}
                for aid, info in self.created_agents.items()
            ]
    
    def remove_agent(self, agent_id: str) -> bool:
        """
        Remove agent from tracking.
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Success status
        """
        if agent_id in self.created_agents:
            agent_info = self.created_agents[agent_id]
            agent_type = agent_info["type"]
            
            # Update metrics
            if agent_type in self.agent_metrics:
                self.agent_metrics[agent_type]["active"] -= 1
            
            # Remove from tracking
            del self.created_agents[agent_id]
            
            logger.info(f"Removed agent: {agent_id}")
            return True
        
        return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get factory metrics.
        
        Returns:
            Metrics dictionary
        """
        return {
            "total_agents_created": self.creation_count,
            "active_agents": len(self.created_agents),
            "agents_by_type": self.agent_metrics,
            "agent_ids": list(self.created_agents.keys())
        }
    
    async def cleanup(self):
        """Clean up all agents."""
        for agent_id in list(self.created_agents.keys()):
            self.remove_agent(agent_id)
        
        logger.info("AgentFactory cleanup complete")


# Singleton instance
_factory_instance: Optional[AgentFactory] = None
_factory_lock = asyncio.Lock()

async def get_agent_factory() -> AgentFactory:
    """
    Get or create the global agent factory instance.
    
    Returns:
        Global AgentFactory instance
    """
    global _factory_instance
    
    if _factory_instance is None:
        async with _factory_lock:
            if _factory_instance is None:
                _factory_instance = AgentFactory()
                logger.info("Created global AgentFactory instance")
    
    return _factory_instance

# Convenience functions
async def create_stylist(memory: Optional[Any] = None) -> Any:
    """Create a stylist agent using the global factory."""
    factory = await get_agent_factory()
    return await factory.create_stylist_agent(memory=memory)

async def create_battle_system(neo4j_client: Any, qdrant_client: Any) -> Dict[str, Any]:
    """Create the complete battle system."""
    factory = await get_agent_factory()
    return await factory.create_battle_agents(neo4j_client, qdrant_client)

# Export public API
__all__ = [
    "AgentFactory",
    "get_agent_factory",
    "create_stylist",
    "create_battle_system"
]
