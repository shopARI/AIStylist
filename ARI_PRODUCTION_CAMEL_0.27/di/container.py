import logging
from dataclasses import asdict #
from typing import Dict, Any, Optional

from dependency_injector import containers, providers

from config.settings import Settings

# Import all services and agents
from services.user.knowledge_graph import UserKnowledgeGraphService
from services.product.retriever import ProductRetrieverService
from services.data.hybrid_store import HybridDataStore
from services.cache.battle_cache import BattleCache
from services.memory.fallback_manager import MemoryFallbackManager
from services.conversation_handler import ConversationHandler
from services.application import ApplicationService # We will create this new service

# Battle System
from services.battle.orchestrator import BattleOrchestrator
from services.battle.executor import BattleExecutor
from services.battle.optimizer import BattleOptimizer
from services.battle.metrics import BattleMetrics

# Agents
from agents.factory import get_agent_factory
from agents.cypher_bot import CypherBotAgent
from agents.vibe_bot import VibeBotAgent
from agents.judge import JudgeAriAgent

logger = logging.getLogger("di.container")

class DIContainer(containers.DeclarativeContainer):
    """
    Dependency Injection container for the entire application.
    Uses the dependency-injector library for a robust and standard implementation.
    """
    settings = providers.Singleton(Settings)

    # --- Core Infrastructure ---
    # This is the CORRECT version
    user_kg_service = providers.Singleton(
        UserKnowledgeGraphService,
        url=settings.provided.neo4j.url,
        username=settings.provided.neo4j.username,
        password=settings.provided.neo4j.password
    )
    
    product_retriever_service = providers.Singleton(
        ProductRetrieverService,
        collection_name=settings.provided.qdrant.collection_name
    )

    hybrid_data_store = providers.Singleton(
        HybridDataStore,
        neo4j_client=user_kg_service,
        qdrant_client=product_retriever_service
    )

    battle_cache = providers.Singleton(
        BattleCache
    )

    # --- Agents (Scoped per request/battle) ---
    cypher_bot_agent = providers.Factory(
        CypherBotAgent,
        neo4j_client=user_kg_service
    )

    vibe_bot_agent = providers.Factory(
        VibeBotAgent,
        qdrant_client=product_retriever_service
    )

    judge_agent = providers.Factory(JudgeAriAgent)

    agent_factory = providers.Resource(get_agent_factory)
    
    # --- Battle System (wired with agents) ---
    battle_metrics = providers.Singleton(BattleMetrics)
    
    battle_optimizer = providers.Singleton(BattleOptimizer)

    battle_executor = providers.Singleton(
        BattleExecutor,
        cypher_bot=cypher_bot_agent,
        vibe_bot=vibe_bot_agent,
        judge=judge_agent
    )

    battle_orchestrator = providers.Singleton(
        BattleOrchestrator,
        executor=battle_executor,
        cache=battle_cache,
        optimizer=battle_optimizer,
        metrics=battle_metrics,
        settings=providers.Factory(asdict, settings.provided.battle)
    )

    # --- Top-Level Application Services ---
    fallback_memory_manager = providers.Singleton(
        MemoryFallbackManager
    )

    conversation_handler = providers.Singleton(
        ConversationHandler,
        agent_factory=agent_factory,
        memory_manager=fallback_memory_manager,
        neo4j_service=user_kg_service,
        qdrant_service=product_retriever_service
    )

    # --- Main Application Service ---
    application_service = providers.Singleton(
        ApplicationService,
        conversation_handler=conversation_handler,
        battle_orchestrator=battle_orchestrator,
        user_kg_service=user_kg_service
    )

async def initialize_container() -> DIContainer:
    """
    Initializes the container and all its dependent services.
    This should be called during application startup.
    """
    logger.info("Initializing DI container and services...")
    container = DIContainer()
    container.wire(modules=[
        "main", 
        "services.application"
    ])
    
    # Asynchronously initialize services that require it
    await container.user_kg_service().initialize()
    await container.product_retriever_service().initialize()
    logger.info("Container and core services initialized.")
    return container

async def cleanup_container(container: DIContainer):
    """
    Cleans up resources used by services in the container.
    This should be called during application shutdown.
    """
    logger.info("Cleaning up container resources...")
    await container.user_kg_service().close()
    await container.product_retriever_service().close()
    logger.info("Container cleanup complete.")