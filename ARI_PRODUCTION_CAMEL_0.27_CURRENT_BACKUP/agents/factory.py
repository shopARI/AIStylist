"""
Agent Factory for CAMEL 0.2.70
Production implementation with agent pooling, memory management, and cleanup
"""

import logging
import asyncio
import uuid
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
import weakref

logger = logging.getLogger("agents.factory")

# Import from CAMEL 0.2.70 wrapper
from lib.camel.v070 import (
    create_agent,
    create_stylist_agent,
    create_memory,
    CAMEL_AVAILABLE,
    ModelType
)

# Import prompts from configuration
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


class AgentPool:
    """Thread-safe agent pool with automatic cleanup"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Initialize agent pool.
        
        Args:
            max_size: Maximum pool size
            ttl_seconds: Time to live for agents in seconds
        """
        self.pool = OrderedDict()
        self.lock = asyncio.Lock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.access_count = {}
        self.creation_times = {}
    
    async def get(self, agent_id: str) -> Optional[Any]:
        """
        Get agent from pool.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent instance or None
        """
        async with self.lock:
            if agent_id in self.pool:
                # Move to end (LRU)
                self.pool.move_to_end(agent_id)
                self.access_count[agent_id] = self.access_count.get(agent_id, 0) + 1
                
                # Check TTL
                creation_time = self.creation_times.get(agent_id)
                if creation_time:
                    age = (datetime.now() - creation_time).total_seconds()
                    if age > self.ttl_seconds:
                        # Expired
                        del self.pool[agent_id]
                        del self.creation_times[agent_id]
                        del self.access_count[agent_id]
                        return None
                
                return self.pool[agent_id]
            return None
    
    async def add(self, agent_id: str, agent: Any) -> bool:
        """
        Add agent to pool.
        
        Args:
            agent_id: Agent identifier
            agent: Agent instance
            
        Returns:
            Success status
        """
        async with self.lock:
            # Check size limit
            if len(self.pool) >= self.max_size:
                # Remove least recently used
                oldest_id = next(iter(self.pool))
                del self.pool[oldest_id]
                if oldest_id in self.creation_times:
                    del self.creation_times[oldest_id]
                if oldest_id in self.access_count:
                    del self.access_count[oldest_id]
            
            self.pool[agent_id] = agent
            self.creation_times[agent_id] = datetime.now()
            self.access_count[agent_id] = 0
            return True
    
    async def remove(self, agent_id: str) -> bool:
        """
        Remove agent from pool.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Success status
        """
        async with self.lock:
            if agent_id in self.pool:
                del self.pool[agent_id]
                if agent_id in self.creation_times:
                    del self.creation_times[agent_id]
                if agent_id in self.access_count:
                    del self.access_count[agent_id]
                return True
            return False
    
    async def cleanup_expired(self) -> int:
        """
        Remove expired agents.
        
        Returns:
            Number of agents removed
        """
        async with self.lock:
            now = datetime.now()
            to_remove = []
            
            for agent_id, creation_time in self.creation_times.items():
                age = (now - creation_time).total_seconds()
                if age > self.ttl_seconds:
                    to_remove.append(agent_id)
            
            for agent_id in to_remove:
                if agent_id in self.pool:
                    del self.pool[agent_id]
                    del self.creation_times[agent_id]
                    if agent_id in self.access_count:
                        del self.access_count[agent_id]
            
            return len(to_remove)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "size": len(self.pool),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "total_accesses": sum(self.access_count.values()),
            "agent_ids": list(self.pool.keys())
        }


class AgentFactory:
    """
    Production agent factory for CAMEL 0.2.70.
    Manages agent lifecycle with pooling, memory management, and metrics.
    """
    
    def __init__(
        self,
        pool_size: int = 100,
        agent_ttl: int = 3600,
        enable_pooling: bool = True,
        enable_metrics: bool = True
    ):
        """
        Initialize agent factory.
        
        Args:
            pool_size: Maximum agent pool size
            agent_ttl: Agent time to live in seconds
            enable_pooling: Enable agent pooling
            enable_metrics: Enable metrics collection
        """
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL 0.2.70 or higher is required")
        
        self.enable_pooling = enable_pooling
        self.enable_metrics = enable_metrics
        
        # Agent pool
        self.pool = AgentPool(max_size=pool_size, ttl_seconds=agent_ttl) if enable_pooling else None
        
        # Metrics
        self.metrics = {
            "agents_created": 0,
            "agents_reused": 0,
            "creation_failures": 0,
            "pool_hits": 0,
            "pool_misses": 0,
            "total_creation_time": 0.0,
            "agents_by_type": {}
        }
        
        # Cleanup task
        self.cleanup_task = None
        if enable_pooling:
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        logger.info(f"AgentFactory initialized (pooling={enable_pooling}, metrics={enable_metrics})")
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of expired agents."""
        while True:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                if self.pool:
                    removed = await self.pool.cleanup_expired()
                    if removed > 0:
                        logger.info(f"Cleaned up {removed} expired agents")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def create_stylist_agent(
        self,
        memory: Optional[Any] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        agent_id: Optional[str] = None,
        use_pool: bool = True
    ) -> Any:
        """
        Create Ari stylist agent.
        
        Args:
            memory: Optional memory instance
            temperature: Model temperature
            max_tokens: Maximum tokens
            agent_id: Optional agent identifier
            use_pool: Whether to use agent pool
            
        Returns:
            Configured stylist agent
        """
        agent_id = agent_id or f"stylist_{uuid.uuid4().hex[:8]}"
        
        # Check pool first
        if self.enable_pooling and use_pool and self.pool:
            cached_agent = await self.pool.get(agent_id)
            if cached_agent:
                if self.enable_metrics:
                    self.metrics["agents_reused"] += 1
                    self.metrics["pool_hits"] += 1
                logger.debug(f"Reusing stylist agent: {agent_id}")
                return cached_agent
            else:
                if self.enable_metrics:
                    self.metrics["pool_misses"] += 1
        
        # Create new agent
        start_time = datetime.now()
        
        try:
            agent = create_stylist_agent(
                personality=ARI_STYLIST_PROMPT,
                memory=memory,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Set metadata
            agent.agent_id = agent_id
            agent.agent_type = "stylist"
            agent.creation_time = start_time
            
            # Add to pool
            if self.enable_pooling and use_pool and self.pool:
                await self.pool.add(agent_id, agent)
            
            # Update metrics
            if self.enable_metrics:
                creation_time = (datetime.now() - start_time).total_seconds()
                self.metrics["agents_created"] += 1
                self.metrics["total_creation_time"] += creation_time
                self._update_type_metrics("stylist", True)
            
            logger.info(f"Created stylist agent: {agent_id}")
            return agent
            
        except Exception as e:
            if self.enable_metrics:
                self.metrics["creation_failures"] += 1
                self._update_type_metrics("stylist", False)
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
            agent_id: Optional agent identifier
            
        Returns:
            CypherBot agent instance
        """
        agent_id = agent_id or f"cypher_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()
        
        try:
            agent = CypherBotAgent(neo4j_client) #, model_type="gpt-4o-mini")
            
            # Set metadata
            agent.agent_id = agent_id
            agent.creation_time = start_time
            
            # Update metrics
            if self.enable_metrics:
                creation_time = (datetime.now() - start_time).total_seconds()
                self.metrics["agents_created"] += 1
                self.metrics["total_creation_time"] += creation_time
                self._update_type_metrics("cypher", True)
            
            logger.info(f"Created CypherBot: {agent_id}")
            return agent
            
        except Exception as e:
            if self.enable_metrics:
                self.metrics["creation_failures"] += 1
                self._update_type_metrics("cypher", False)
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
            agent_id: Optional agent identifier
            
        Returns:
            VibeBot agent instance
        """
        agent_id = agent_id or f"vibe_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()
        
        try:
            agent = VibeBotAgent(qdrant_client, model_type="gpt-4o-mini")
            
            # Set metadata
            agent.agent_id = agent_id
            agent.creation_time = start_time
            
            # Update metrics
            if self.enable_metrics:
                creation_time = (datetime.now() - start_time).total_seconds()
                self.metrics["agents_created"] += 1
                self.metrics["total_creation_time"] += creation_time
                self._update_type_metrics("vibe", True)
            
            logger.info(f"Created VibeBot: {agent_id}")
            return agent
            
        except Exception as e:
            if self.enable_metrics:
                self.metrics["creation_failures"] += 1
                self._update_type_metrics("vibe", False)
            logger.error(f"Failed to create VibeBot: {e}")
            raise RuntimeError(f"VibeBot creation failed: {e}") from e
    
    async def create_judge_ari(
        self,
        agent_id: Optional[str] = None
    ) -> JudgeAriAgent:
        """
        Create Judge Ari agent.
        
        Args:
            agent_id: Optional agent identifier
            
        Returns:
            Judge Ari agent instance
        """
        agent_id = agent_id or f"judge_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()
        
        try:
            agent = JudgeAriAgent(model_type="gpt-4o-mini")
            
            # Set metadata
            agent.agent_id = agent_id
            agent.creation_time = start_time
            
            # Update metrics
            if self.enable_metrics:
                creation_time = (datetime.now() - start_time).total_seconds()
                self.metrics["agents_created"] += 1
                self.metrics["total_creation_time"] += creation_time
                self._update_type_metrics("judge", True)
            
            logger.info(f"Created Judge Ari: {agent_id}")
            return agent
            
        except Exception as e:
            if self.enable_metrics:
                self.metrics["creation_failures"] += 1
                self._update_type_metrics("judge", False)
            logger.error(f"Failed to create Judge Ari: {e}")
            raise RuntimeError(f"Judge Ari creation failed: {e}") from e
    
    async def create_battle_agents(
        self,
        neo4j_client: Any,
        qdrant_client: Any
    ) -> Dict[str, Any]:
        """
        Create all battle agents.
        
        Args:
            neo4j_client: Neo4j database client
            qdrant_client: Qdrant database client
            
        Returns:
            Dictionary with all battle agents
        """
        try:
            # Create agents in parallel
            cypher_task = asyncio.create_task(self.create_cypher_bot(neo4j_client))
            vibe_task = asyncio.create_task(self.create_vibe_bot(qdrant_client))
            judge_task = asyncio.create_task(self.create_judge_ari())
            
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
    
    async def create_specialized_agent(
        self,
        agent_type: str,
        system_message: str,
        memory: Optional[Any] = None,
        tools: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        agent_id: Optional[str] = None,
        use_pool: bool = True
    ) -> Any:
        """
        Create specialized agent with custom prompt.
        
        Args:
            agent_type: Type of agent
            system_message: System prompt
            memory: Optional memory instance
            tools: Optional list of tools
            temperature: Model temperature
            max_tokens: Maximum tokens
            agent_id: Optional agent identifier
            use_pool: Whether to use agent pool
            
        Returns:
            Configured agent
        """
        agent_id = agent_id or f"{agent_type}_{uuid.uuid4().hex[:8]}"
        
        # Check pool first
        if self.enable_pooling and use_pool and self.pool:
            cached_agent = await self.pool.get(agent_id)
            if cached_agent:
                if self.enable_metrics:
                    self.metrics["agents_reused"] += 1
                    self.metrics["pool_hits"] += 1
                logger.debug(f"Reusing {agent_type} agent: {agent_id}")
                return cached_agent
            else:
                if self.enable_metrics:
                    self.metrics["pool_misses"] += 1
        
        # Create new agent
        start_time = datetime.now()
        
        try:
            agent = create_agent(
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                memory=memory
            )
            
            # Set metadata
            agent.agent_id = agent_id
            agent.agent_type = agent_type
            agent.creation_time = start_time
            
            # Add to pool
            if self.enable_pooling and use_pool and self.pool:
                await self.pool.add(agent_id, agent)
            
            # Update metrics
            if self.enable_metrics:
                creation_time = (datetime.now() - start_time).total_seconds()
                self.metrics["agents_created"] += 1
                self.metrics["total_creation_time"] += creation_time
                self._update_type_metrics(agent_type, True)
            
            logger.info(f"Created {agent_type} agent: {agent_id}")
            return agent
            
        except Exception as e:
            if self.enable_metrics:
                self.metrics["creation_failures"] += 1
                self._update_type_metrics(agent_type, False)
            logger.error(f"Failed to create {agent_type} agent: {e}")
            raise RuntimeError(f"{agent_type} agent creation failed: {e}") from e
    
    async def create_memory_handler_agent(
        self,
        memory: Optional[Any] = None,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Create memory handler agent.
        
        Args:
            memory: Optional memory instance
            agent_id: Optional agent identifier
            
        Returns:
            Memory handler agent
        """
        return await self.create_specialized_agent(
            agent_type="memory_handler",
            system_message=MEMORY_HANDLER_PROMPT,
            memory=memory,
            temperature=0.5,
            max_tokens=2000,
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
            agent_id: Optional agent identifier
            
        Returns:
            Greeting handler agent
        """
        return await self.create_specialized_agent(
            agent_type="greeting_handler",
            system_message=GREETING_HANDLER_PROMPT,
            memory=memory,
            temperature=0.8,
            max_tokens=1500,
            agent_id=agent_id
        )
    
    async def create_product_response_agent(
        self,
        memory: Optional[Any] = None,
        agent_id: Optional[str] = None
    ) -> Any:
        """
        Create product response agent.
        
        Args:
            memory: Optional memory instance
            agent_id: Optional agent identifier
            
        Returns:
            Product response agent
        """
        return await self.create_specialized_agent(
            agent_type="product_response",
            system_message=PRODUCT_RESPONSE_PROMPT,
            memory=memory,
            temperature=0.7,
            max_tokens=3000,
            agent_id=agent_id
        )
    
    def _update_type_metrics(self, agent_type: str, success: bool):
        """Update metrics for agent type."""
        if agent_type not in self.metrics["agents_by_type"]:
            self.metrics["agents_by_type"][agent_type] = {
                "created": 0,
                "failed": 0,
                "last_created": None
            }
        
        if success:
            self.metrics["agents_by_type"][agent_type]["created"] += 1
            self.metrics["agents_by_type"][agent_type]["last_created"] = datetime.now().isoformat()
        else:
            self.metrics["agents_by_type"][agent_type]["failed"] += 1
    
    async def get_agent(self, agent_id: str) -> Optional[Any]:
        """
        Get agent by ID.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent instance or None
        """
        if self.pool:
            return await self.pool.get(agent_id)
        return None
    
    async def remove_agent(self, agent_id: str) -> bool:
        """
        Remove agent from pool.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Success status
        """
        if self.pool:
            return await self.pool.remove(agent_id)
        return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get factory metrics."""
        metrics = self.metrics.copy()
        
        # Add pool stats
        if self.pool:
            metrics["pool_stats"] = self.pool.get_stats()
        
        # Calculate averages
        if metrics["agents_created"] > 0:
            metrics["avg_creation_time"] = (
                metrics["total_creation_time"] / metrics["agents_created"]
            )
            metrics["success_rate"] = (
                metrics["agents_created"] / 
                (metrics["agents_created"] + metrics["creation_failures"]) * 100
            )
        else:
            metrics["avg_creation_time"] = 0
            metrics["success_rate"] = 0
        
        return metrics
    
    async def cleanup(self):
        """Clean up factory resources."""
        logger.info("Starting AgentFactory cleanup")
        
        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clear pool
        if self.pool:
            pool_stats = self.pool.get_stats()
            logger.info(f"Clearing agent pool with {pool_stats['size']} agents")
        
        logger.info("AgentFactory cleanup complete")


# Global factory instance
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
                _factory_instance = AgentFactory(
                    pool_size=100,
                    agent_ttl=3600,
                    enable_pooling=True,
                    enable_metrics=True
                )
                logger.info("Created global AgentFactory instance")
    
    return _factory_instance

async def cleanup_agent_factory():
    """Clean up the global agent factory."""
    global _factory_instance
    
    if _factory_instance is not None:
        async with _factory_lock:
            if _factory_instance is not None:
                await _factory_instance.cleanup()
                _factory_instance = None
                logger.info("Cleaned up global AgentFactory")


# Export public API
__all__ = [
    "AgentFactory",
    "get_agent_factory",
    "cleanup_agent_factory"
]