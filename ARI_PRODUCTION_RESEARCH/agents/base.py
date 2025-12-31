"""
Base Agent Protocol for Battle System
Defines the interface all battle agents must implement
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Protocol
from datetime import datetime

logger = logging.getLogger("agents.base")

class BattleAgentProtocol(Protocol):
    """
    Protocol defining the interface for battle agents.
    All battle agents must implement these methods.
    """
    
    name: str
    style: str
    agent: Any  # CAMEL ChatAgent instance
    stats: Dict[str, Any]
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using agent's strategy.
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Optional filters
            ml_intelligence: ML insights for this agent
            user_context: User information
            
        Returns:
            List of products with agent metadata
        """
        ...
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics.
        
        Returns:
            Statistics dictionary
        """
        ...


class BaseBattleAgent(ABC):
    """
    Abstract base class for battle agents.
    Provides common functionality and enforces interface.
    """
    
    def __init__(self, backend_client: Any, name: str, style: str):
        """
        Initialize base battle agent.
        
        Args:
            backend_client: Backend database client
            name: Agent name
            style: Agent style/approach
        """
        self.backend_client = backend_client
        self.name = name
        self.style = style
        self.agent = None  # CAMEL agent instance
        
        # Initialize statistics
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0,
            "created_at": datetime.now().isoformat()
        }
        
        # Initialize CAMEL agent
        self._initialize_agent()
    
    @abstractmethod
    def _initialize_agent(self):
        """
        Initialize the CAMEL agent with appropriate system message.
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using agent's strategy.
        Must be implemented by subclasses.
        
        Args:
            query: Search query
            limit: Maximum results
            filters: Optional filters
            ml_intelligence: ML insights for this agent
            user_context: User information
            
        Returns:
            List of products with agent metadata
        """
        pass
    
    @abstractmethod
    async def _get_agent_strategy(
        self,
        query: str,
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Use CAMEL agent to determine search strategy.
        Must be implemented by subclasses.
        
        Returns:
            Strategy description from agent
        """
        pass
    
    @abstractmethod
    async def _execute_strategy(
        self,
        strategy: str,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute the chosen search strategy.
        Must be implemented by subclasses.
        
        Returns:
            List of products
        """
        pass
    
    def _update_stats(
        self,
        products_found: int,
        search_time: float,
        success: bool = True
    ):
        """
        Update agent statistics.
        
        Args:
            products_found: Number of products found
            search_time: Time taken for search
            success: Whether search was successful
        """
        if success:
            self.stats["successful_searches"] += 1
            self.stats["total_products_found"] += products_found
            
            # Update average search time
            total_searches = self.stats["successful_searches"]
            current_avg = self.stats["avg_search_time"]
            self.stats["avg_search_time"] = (
                (current_avg * (total_searches - 1) + search_time) / total_searches
            )
        else:
            self.stats["failed_searches"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics.
        
        Returns:
            Statistics dictionary including success rate
        """
        total = self.stats["total_searches"]
        success_rate = (
            self.stats["successful_searches"] / total * 100
            if total > 0 else 0
        )
        
        return {
            "agent": self.name,
            "style": self.style,
            **self.stats,
            "success_rate": success_rate,
            "uptime": self._calculate_uptime()
        }
    
    def _calculate_uptime(self) -> float:
        """
        Calculate agent uptime in seconds.
        
        Returns:
            Uptime in seconds
        """
        if "created_at" in self.stats:
            try:
                created = datetime.fromisoformat(self.stats["created_at"])
                return (datetime.now() - created).total_seconds()
            except:
                return 0.0
        return 0.0
    
    def reset_stats(self):
        """Reset agent statistics."""
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0,
            "created_at": datetime.now().isoformat()
        }
        logger.info(f"{self.name} statistics reset")


class AgentCapabilities:
    """
    Defines capabilities that agents can have.
    Used for routing and optimization.
    """
    
    # Search capabilities
    GRAPH_SEARCH = "graph_search"
    VECTOR_SEARCH = "vector_search"
    SEMANTIC_SEARCH = "semantic_search"
    VISUAL_SEARCH = "visual_search"
    
    # Intelligence processing
    ML_ENHANCED = "ml_enhanced"
    CONTEXT_AWARE = "context_aware"
    PERSONALIZED = "personalized"
    
    # Data sources
    NEO4J = "neo4j"
    QDRANT = "qdrant"
    MEMORY = "memory"
    
    @classmethod
    def get_cypher_capabilities(cls) -> set:
        """Get CypherBot capabilities."""
        return {
            cls.GRAPH_SEARCH,
            cls.ML_ENHANCED,
            cls.CONTEXT_AWARE,
            cls.PERSONALIZED,
            cls.NEO4J
        }
    
    @classmethod
    def get_vibe_capabilities(cls) -> set:
        """Get VibeBot capabilities."""
        return {
            cls.VECTOR_SEARCH,
            cls.SEMANTIC_SEARCH,
            cls.VISUAL_SEARCH,
            cls.ML_ENHANCED,
            cls.CONTEXT_AWARE,
            cls.QDRANT
        }


class AgentMetrics:
    """
    Standard metrics for agent performance tracking.
    """
    
    def __init__(self):
        self.search_times = []
        self.result_counts = []
        self.success_count = 0
        self.failure_count = 0
        self.total_count = 0
    
    def record_search(
        self,
        search_time: float,
        result_count: int,
        success: bool = True
    ):
        """Record a search operation."""
        self.total_count += 1
        self.search_times.append(search_time)
        self.result_counts.append(result_count)
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "total_searches": self.total_count,
            "success_rate": (
                self.success_count / self.total_count * 100
                if self.total_count > 0 else 0
            ),
            "avg_search_time": (
                sum(self.search_times) / len(self.search_times)
                if self.search_times else 0
            ),
            "avg_result_count": (
                sum(self.result_counts) / len(self.result_counts)
                if self.result_counts else 0
            ),
            "max_search_time": max(self.search_times) if self.search_times else 0,
            "min_search_time": min(self.search_times) if self.search_times else 0
        }
    
    def reset(self):
        """Reset all metrics."""
        self.search_times.clear()
        self.result_counts.clear()
        self.success_count = 0
        self.failure_count = 0
        self.total_count = 0


# Export public API
__all__ = [
    "BattleAgentProtocol",
    "BaseBattleAgent",
    "AgentCapabilities",
    "AgentMetrics"
]
