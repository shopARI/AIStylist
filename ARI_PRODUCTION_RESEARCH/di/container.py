import logging
from dataclasses import asdict #
from typing import Dict, Any, Optional

from dependency_injector import containers, providers

from config.settings import Settings

# Import all services and agents
from services.user.knowledge_graph import UserKnowledgeGraphService
from services.product.retriever import ProductRetrieverService
from services.data.hybrid_store import HybridDataStore
from services.cache.battle_cache import BattleCache, CacheBackend
from services.cache.redis_client import create_redis_service
from services.conversation_handler import ConversationHandler
from services.application import ApplicationService
from services.visual_qdrant_client import visual_qdrant_client

# ML Intelligence Systems
from services.ml.intelligence import create_intelligence_system
# Memory Systems  
from services.memory import create_memory_setup_function

# Battle System
from services.battle.orchestrator import BattleOrchestrator
from services.battle.executor import BattleExecutor
from services.battle.optimizer import BattleOptimizer
from services.battle.metrics import BattleMetrics

# Agents
from agents.factory import get_agent_factory
from agents.cypher_bot import CypherBotAgent
from agents.vibe_bot import VibeBotAgent
from agents.vision_bot import VisionBotAgent
from agents.judge import JudgeAriAgent

logger = logging.getLogger("di.container")

class DIContainer(containers.DeclarativeContainer):
    """
    Dependency Injection container for the entire application.
    Uses the dependency-injector library for a robust and standard implementation.
    """
    settings = providers.Singleton(Settings, env_file=".env")

    # --- Core Infrastructure ---
    # Redis client for production scaling (defined early for dependencies)
    redis_client = providers.Singleton(
        create_redis_service,
        url=settings.provided.redis.url,
        host=settings.provided.redis.host,
        port=settings.provided.redis.port,
        password=settings.provided.redis.password,
        db=settings.provided.redis.db,
        max_connections=settings.provided.redis.max_connections,
        socket_timeout=settings.provided.redis.socket_timeout,
        socket_connect_timeout=settings.provided.redis.socket_connect_timeout,
        retry_on_timeout=settings.provided.redis.retry_on_timeout,
        health_check_interval=settings.provided.redis.health_check_interval,
        decode_responses=settings.provided.redis.decode_responses
    )

    # This is the CORRECT version
    user_kg_service = providers.Singleton(
        UserKnowledgeGraphService,
        url=settings.provided.neo4j.url,
        username=settings.provided.neo4j.username,
        password=settings.provided.neo4j.password
    )
    
    product_retriever_service = providers.Singleton(
        ProductRetrieverService,
        collection_name=settings.provided.qdrant.collection_name,
        redis_client=redis_client
    )

    hybrid_data_store = providers.Singleton(
        HybridDataStore,
        neo4j_client=user_kg_service,
        qdrant_client=product_retriever_service
    )


    battle_cache = providers.Singleton(
        BattleCache,
        backend=CacheBackend.MEMORY
    )

    # Visual Qdrant Client for FashionSigLIP embeddings
    visual_qdrant_service = providers.Object(visual_qdrant_client)

    # --- Agents (Scoped per request/battle) ---
    cypher_bot_agent = providers.Factory(
        CypherBotAgent,
        neo4j_client=user_kg_service
    )

    vibe_bot_agent = providers.Factory(
        VibeBotAgent,
        qdrant_client=product_retriever_service
    )

    # VisionBot with FashionSigLIP visual embeddings
    vision_bot_agent = providers.Factory(
        VisionBotAgent,
        visual_qdrant_client=visual_qdrant_service
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
        judge=judge_agent,
        vision_bot=vision_bot_agent
    )

    battle_orchestrator = providers.Singleton(
        BattleOrchestrator,
        executor=battle_executor,
        cache=battle_cache,
        optimizer=battle_optimizer,
        metrics=battle_metrics,
        settings=providers.Factory(asdict, settings.provided.battle),
        redis_client=redis_client
    )

    # --- ML Intelligence System ---
    intelligence_coordinator = providers.Singleton(
        create_intelligence_system,
        data_store=hybrid_data_store,
        user_kg=user_kg_service,
        product_retriever=product_retriever_service,
        memory_setup_func=create_memory_setup_function(),  #  MEMORY ENABLED!
        config={
            "enable_clustering": True,
            "enable_visual": True, 
            "enable_behavioral": True,
            "enable_memory_rag": True
        }
    )

    # --- Top-Level Application Services ---
    conversation_handler = providers.Singleton(
        ConversationHandler,
        agent_factory=agent_factory,
        neo4j_service=user_kg_service,
        qdrant_service=product_retriever_service,
        redis_client=redis_client
    )

    # --- Main Application Service ---
    application_service = providers.Singleton(
        ApplicationService,
        conversation_handler=conversation_handler,
        battle_orchestrator=battle_orchestrator,
        user_kg_service=user_kg_service,
        intelligence_coordinator=intelligence_coordinator,
        redis_client=redis_client
    )

async def initialize_container() -> DIContainer:
    """
    Initializes the container and all its dependent services.
    This should be called during application startup.
    
    SWE Requirement: Immediate failure if critical databases unavailable.
    """
    logger.info("Initializing DI container and services...")
    
    # Pre-flight check: Verify all critical databases BEFORE starting services
    from di.preflight_check import preflight_database_check
    settings = Settings(env_file=".env")  # Create settings instance for pre-flight check
    await preflight_database_check(settings)
    
    container = DIContainer()
    container.wire(modules=[
        "main", 
        "services.application"
    ])
    
    # Asynchronously initialize services that require it
    # (Databases already verified in pre-flight check)
    await container.user_kg_service().initialize()
    await container.product_retriever_service().initialize()
    await container.redis_client().initialize()
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
    await container.redis_client().close()
    
    # Cleanup hybrid data store
    try:
        hybrid_store = container.hybrid_data_store()
        if hasattr(hybrid_store, 'close'):
            await hybrid_store.close()
    except Exception as e:
        logger.error(f"Error cleaning up hybrid data store: {e}")
    
    logger.info("Container cleanup complete.")