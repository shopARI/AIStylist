"""
Dependency Injection Container
Manages service creation and lifecycle for the AI Fashion System
"""

import logging
from typing import Dict, Any, Optional, Type, TypeVar, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from contextlib import asynccontextmanager

from config.settings import Settings, get_settings

logger = logging.getLogger("di.container")

# Type variable for generic service types
T = TypeVar('T')

# =============================================================================
# SERVICE LIFECYCLE
# =============================================================================

class ServiceLifecycle(Enum):
    """Service lifecycle management strategies."""
    SINGLETON = "singleton"  # One instance for entire app lifetime
    SCOPED = "scoped"  # One instance per request/scope
    TRANSIENT = "transient"  # New instance every time

# =============================================================================
# SERVICE DESCRIPTOR
# =============================================================================

@dataclass
class ServiceDescriptor:
    """Describes a service registration."""
    service_type: Type
    factory: Callable
    lifecycle: ServiceLifecycle
    dependencies: List[str] = field(default_factory=list)
    initialized: bool = False
    instance: Optional[Any] = None

# =============================================================================
# DEPENDENCY INJECTION CONTAINER
# =============================================================================

class DIContainer:
    """
    Dependency injection container for managing service lifecycle.
    Supports singleton, scoped, and transient services.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize DI container.
        
        Args:
            settings: Application settings (uses global if None)
        """
        self.settings = settings or get_settings()
        self._services: Dict[str, ServiceDescriptor] = {}
        self._scoped_instances: Dict[str, Any] = {}
        self._initialization_lock = asyncio.Lock()
        
        logger.info("Dependency injection container initialized")
    
    # =========================================================================
    # REGISTRATION
    # =========================================================================
    
    def register_singleton(
        self,
        service_type: Type[T],
        factory: Optional[Callable[..., T]] = None,
        name: Optional[str] = None,
        dependencies: Optional[List[str]] = None
    ) -> None:
        """
        Register a singleton service.
        
        Args:
            service_type: Service class type
            factory: Optional factory function
            name: Optional service name (uses type name if None)
            dependencies: Optional list of dependency names
        """
        self._register(
            service_type=service_type,
            factory=factory or service_type,
            lifecycle=ServiceLifecycle.SINGLETON,
            name=name,
            dependencies=dependencies
        )
    
    def register_scoped(
        self,
        service_type: Type[T],
        factory: Optional[Callable[..., T]] = None,
        name: Optional[str] = None,
        dependencies: Optional[List[str]] = None
    ) -> None:
        """
        Register a scoped service.
        
        Args:
            service_type: Service class type
            factory: Optional factory function
            name: Optional service name
            dependencies: Optional list of dependency names
        """
        self._register(
            service_type=service_type,
            factory=factory or service_type,
            lifecycle=ServiceLifecycle.SCOPED,
            name=name,
            dependencies=dependencies
        )
    
    def register_transient(
        self,
        service_type: Type[T],
        factory: Optional[Callable[..., T]] = None,
        name: Optional[str] = None,
        dependencies: Optional[List[str]] = None
    ) -> None:
        """
        Register a transient service.
        
        Args:
            service_type: Service class type
            factory: Optional factory function
            name: Optional service name
            dependencies: Optional list of dependency names
        """
        self._register(
            service_type=service_type,
            factory=factory or service_type,
            lifecycle=ServiceLifecycle.TRANSIENT,
            name=name,
            dependencies=dependencies
        )
    
    def _register(
        self,
        service_type: Type,
        factory: Callable,
        lifecycle: ServiceLifecycle,
        name: Optional[str],
        dependencies: Optional[List[str]]
    ) -> None:
        """Internal registration method."""
        service_name = name or service_type.__name__
        
        if service_name in self._services:
            logger.warning(f"Service '{service_name}' already registered, overwriting")
        
        self._services[service_name] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            lifecycle=lifecycle,
            dependencies=dependencies or []
        )
        
        logger.debug(f"Registered {lifecycle.value} service: {service_name}")
    
    # =========================================================================
    # RESOLUTION
    # =========================================================================
    
    async def get(self, service_name: str) -> Any:
        """
        Get a service instance.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service instance
            
        Raises:
            KeyError: Service not registered
            RuntimeError: Circular dependency or initialization error
        """
        if service_name not in self._services:
            raise KeyError(f"Service '{service_name}' not registered")
        
        descriptor = self._services[service_name]
        
        # Handle based on lifecycle
        if descriptor.lifecycle == ServiceLifecycle.SINGLETON:
            return await self._get_singleton(service_name, descriptor)
        elif descriptor.lifecycle == ServiceLifecycle.SCOPED:
            return await self._get_scoped(service_name, descriptor)
        else:  # TRANSIENT
            return await self._create_instance(descriptor)
    
    async def _get_singleton(
        self,
        service_name: str,
        descriptor: ServiceDescriptor
    ) -> Any:
        """Get or create singleton instance."""
        if not descriptor.initialized:
            async with self._initialization_lock:
                # Double-check after acquiring lock
                if not descriptor.initialized:
                    descriptor.instance = await self._create_instance(descriptor)
                    descriptor.initialized = True
                    logger.debug(f"Created singleton: {service_name}")
        
        return descriptor.instance
    
    async def _get_scoped(
        self,
        service_name: str,
        descriptor: ServiceDescriptor
    ) -> Any:
        """Get or create scoped instance."""
        if service_name not in self._scoped_instances:
            self._scoped_instances[service_name] = await self._create_instance(descriptor)
            logger.debug(f"Created scoped instance: {service_name}")
        
        return self._scoped_instances[service_name]
    
    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a new service instance."""
        # Resolve dependencies
        dependencies = {}
        for dep_name in descriptor.dependencies:
            dependencies[dep_name] = await self.get(dep_name)
        
        # Create instance
        factory = descriptor.factory
        
        # Check if factory is async
        if asyncio.iscoroutinefunction(factory):
            instance = await factory(**dependencies, settings=self.settings)
        else:
            instance = factory(**dependencies, settings=self.settings)
        
        return instance
    
    # =========================================================================
    # SCOPE MANAGEMENT
    # =========================================================================
    
    @asynccontextmanager
    async def create_scope(self):
        """
        Create a new scope for scoped services.
        
        Usage:
            async with container.create_scope():
                service = await container.get("ScopedService")
        """
        # Clear scoped instances at start
        self._scoped_instances.clear()
        
        try:
            yield self
        finally:
            # Cleanup scoped instances
            for name, instance in self._scoped_instances.items():
                if hasattr(instance, 'cleanup'):
                    try:
                        if asyncio.iscoroutinefunction(instance.cleanup):
                            await instance.cleanup()
                        else:
                            instance.cleanup()
                    except Exception as e:
                        logger.error(f"Error cleaning up scoped service '{name}': {e}")
            
            self._scoped_instances.clear()
    
    # =========================================================================
    # LIFECYCLE MANAGEMENT
    # =========================================================================
    
    async def initialize_all(self) -> None:
        """Initialize all singleton services."""
        for name, descriptor in self._services.items():
            if descriptor.lifecycle == ServiceLifecycle.SINGLETON:
                await self.get(name)
        
        logger.info("All singleton services initialized")
    
    async def cleanup(self) -> None:
        """Cleanup all services."""
        # Cleanup singletons
        for name, descriptor in self._services.items():
            if descriptor.lifecycle == ServiceLifecycle.SINGLETON and descriptor.instance:
                if hasattr(descriptor.instance, 'cleanup'):
                    try:
                        if asyncio.iscoroutinefunction(descriptor.instance.cleanup):
                            await descriptor.instance.cleanup()
                        else:
                            descriptor.instance.cleanup()
                        logger.debug(f"Cleaned up singleton: {name}")
                    except Exception as e:
                        logger.error(f"Error cleaning up singleton '{name}': {e}")
        
        # Clear all instances
        self._scoped_instances.clear()
        for descriptor in self._services.values():
            descriptor.instance = None
            descriptor.initialized = False
        
        logger.info("All services cleaned up")

# =============================================================================
# SERVICE REGISTRATION HELPERS
# =============================================================================

def register_core_services(container: DIContainer) -> None:
    """
    Register core system services.
    
    Args:
        container: DI container
    """
    from services.connection.manager import ConnectionManager
    from services.battle.cache import BattleCache
    
    # Register connection managers
    container.register_singleton(
        ConnectionManager,
        name="Neo4jConnection"
    )
    container.register_singleton(
        ConnectionManager,
        name="QdrantConnection"
    )
    
    # Register battle cache
    container.register_singleton(
        BattleCache,
        name="BattleCache"
    )
    
    logger.info("Core services registered")

def register_battle_services(container: DIContainer) -> None:
    """
    Register battle system services.
    
    Args:
        container: DI container
    """
    from services.battle.orchestrator import BattleOrchestrator
    from services.battle.executor import BattleExecutor
    from services.battle.optimizer import BattleOptimizer
    from services.battle.metrics import BattleMetrics
    
    # Register battle components
    container.register_singleton(
        BattleOrchestrator,
        name="BattleOrchestrator",
        dependencies=["Neo4jConnection", "QdrantConnection", "BattleCache"]
    )
    
    container.register_scoped(
        BattleExecutor,
        name="BattleExecutor"
    )
    
    container.register_singleton(
        BattleOptimizer,
        name="BattleOptimizer"
    )
    
    container.register_singleton(
        BattleMetrics,
        name="BattleMetrics"
    )
    
    logger.info("Battle services registered")

def register_agent_services(container: DIContainer) -> None:
    """
    Register agent services.
    
    Args:
        container: DI container
    """
    from agents import CypherBotAgent, VibeBotAgent, JudgeAriAgent
    
    # Register agents as scoped (per-request)
    container.register_scoped(
        CypherBotAgent,
        name="CypherBot",
        dependencies=["Neo4jConnection"]
    )
    
    container.register_scoped(
        VibeBotAgent,
        name="VibeBot",
        dependencies=["QdrantConnection"]
    )
    
    container.register_scoped(
        JudgeAriAgent,
        name="JudgeAri"
    )
    
    logger.info("Agent services registered")

# =============================================================================
# GLOBAL CONTAINER
# =============================================================================

# Global container instance
_container: Optional[DIContainer] = None

def get_container() -> DIContainer:
    """
    Get the global DI container.
    
    Returns:
        DIContainer instance
    """
    global _container
    if _container is None:
        _container = DIContainer()
        
        # Register all services
        register_core_services(_container)
        register_battle_services(_container)
        register_agent_services(_container)
        
        logger.info("Global DI container initialized with all services")
    
    return _container

async def initialize_container() -> DIContainer:
    """
    Initialize the global container and all singleton services.
    
    Returns:
        Initialized DIContainer
    """
    container = get_container()
    await container.initialize_all()
    return container

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Classes
    'DIContainer',
    'ServiceLifecycle',
    'ServiceDescriptor',
    
    # Functions
    'get_container',
    'initialize_container',
    'register_core_services',
    'register_battle_services',
    'register_agent_services'
]
