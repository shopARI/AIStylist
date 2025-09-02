"""
Streamlit-specific DI Container
Uses enhanced ApplicationService with agent monitoring capabilities
"""

import logging
from dataclasses import asdict
from typing import Dict, Any, Optional

from dependency_injector import containers, providers

# Import base container components  
from di.container import DIContainer
from services.streamlit_service import StreamlitApplicationService
from services.ml.intelligence.coordinator import IntelligenceCoordinator

logger = logging.getLogger("di.streamlit_container")

class SimpleIntelligenceCoordinator:
    """Simplified intelligence coordinator for Streamlit - no async initialization"""
    
    def __init__(self, *args, **kwargs):
        self.systems = {}
    
    async def process_intelligence(self, *args, **kwargs):
        return {}

class StreamlitDIContainer(DIContainer):
    """
    Extended DI container for Streamlit interface with enhanced monitoring
    """
    
    # Override the intelligence coordinator with a simple version
    intelligence_coordinator = providers.Singleton(SimpleIntelligenceCoordinator)
    
    # Override the application service with the enhanced version
    application_service = providers.Singleton(
        StreamlitApplicationService,
        conversation_handler=DIContainer.conversation_handler,
        battle_orchestrator=DIContainer.battle_orchestrator,
        user_kg_service=DIContainer.user_kg_service,
        intelligence_coordinator=intelligence_coordinator
    )

async def initialize_streamlit_container() -> StreamlitDIContainer:
    """
    Initialize the Streamlit-specific container
    """
    logger.info("Initializing Streamlit DI container...")
    container = StreamlitDIContainer()
    container.wire(modules=[
        "streamlit_app",
        "services.streamlit_service"
    ])
    
    # Initialize core services
    await container.user_kg_service().initialize()
    await container.product_retriever_service().initialize()
    
    logger.info("Streamlit container initialized successfully")
    return container

async def cleanup_streamlit_container(container: StreamlitDIContainer):
    """
    Clean up Streamlit container resources
    """
    logger.info("Cleaning up Streamlit container...")
    await container.user_kg_service().close()
    await container.product_retriever_service().close()
    
    # Cleanup hybrid data store
    try:
        hybrid_store = container.hybrid_data_store()
        if hasattr(hybrid_store, 'close'):
            await hybrid_store.close()
    except Exception as e:
        logger.error(f"Error cleaning up hybrid data store: {e}")
    
    logger.info("Streamlit container cleanup complete")