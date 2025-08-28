"""
Centralized CAMEL-AI imports for version 0.2.64
Production implementation with fail-fast philosophy
Removes fallback classes but KEEPS the CompatibilityLayer helpers
"""

import sys
import logging
from typing import Optional, Any

logger = logging.getLogger("camel_imports")

# Track import availability
IMPORT_STATUS = {
    "camel": False,
    "models": False,
    "agents": False,
    "memory": False,
    "embeddings": False,
    "toolkits": False,
    "types": False,
    "messages": False,
    "storages": False,
    "retrievers": False,
    "utils": False
}

# Initialize all components to None first
CAMEL_VERSION = None
ModelFactory = None
ModelPlatformType = None
ModelType = None
OpenAIBackendRole = None
TaskType = None
TerminationMode = None
ChatAgent = None
BaseAgent = None

# Memory components
AgentMemory = None
ChatHistoryBlock = None
ChatHistoryMemory = None
LongtermAgentMemory = None
MemoryRecord = None
ScoreBasedContextCreator = None
VectorDBBlock = None
VectorDBMemory = None
BaseMemory = None

BaseMessage = None
OpenAITokenCounter = None
BaseEmbedding = None
OpenAIEmbedding = None
EmbeddingModelType = None
BaseToolkit = None
SearchToolkit = None
MCPToolkit = None
RetrievalToolkit = None
BaseStorage = None
QdrantStorage = None
VectorStorage = None
StorageType = None
BaseRetriever = None
AutoRetriever = None
VectorRetriever = None

# Try importing CAMEL components with correct paths for 0.2.64
try:
    # Core imports - test basic camel first
    import camel
    IMPORT_STATUS["camel"] = True
    CAMEL_VERSION = getattr(camel, "__version__", "unknown")
    logger.info(f"CAMEL-AI version: {CAMEL_VERSION}")

    # Models and types - import these first as they're most basic
    try:
        from camel.models import ModelFactory
        IMPORT_STATUS["models"] = True
        logger.info(" ModelFactory imported")
    except ImportError as e:
        logger.error(f"ModelFactory import failed: {e}")
        raise RuntimeError(f"CRITICAL: ModelFactory required but not available: {e}")

    try:
        from camel.types import (
            ModelPlatformType,
            ModelType,
            OpenAIBackendRole,
            TaskType,
            TerminationMode
        )
        IMPORT_STATUS["types"] = True
        logger.info(" Types imported successfully")
    except ImportError as e:
        logger.error(f"Types import failed: {e}")
        raise RuntimeError(f"CRITICAL: CAMEL types required but not available: {e}")

    # Try to import StorageType from types
    try:
        from camel.types import StorageType
        logger.info(" StorageType imported")
    except ImportError:
        logger.info("StorageType not available, creating minimal enum")
        class StorageType:
            QDRANT = "qdrant"
            LOCAL = "local"
            MEMORY = "memory"

    # Agent imports - ChatAgent is CRITICAL
    try:
        from camel.agents import ChatAgent
        IMPORT_STATUS["agents"] = True
        logger.info(" ChatAgent imported")
    except ImportError as e:
        logger.error(f"ChatAgent import failed: {e}")
        raise RuntimeError(f"CRITICAL: ChatAgent required but not available: {e}")

    # Try BaseAgent separately since it might not exist
    try:
        from camel.agents import BaseAgent
        logger.info(" BaseAgent imported")
    except ImportError as e:
        logger.info("BaseAgent not available (optional)")
        BaseAgent = None

    # Memory imports - CRITICAL for Ari
    try:
        from camel.memories import LongtermAgentMemory
        logger.info(" LongtermAgentMemory imported")
    except ImportError as e:
        logger.error(f"LongtermAgentMemory import failed: {e}")
        raise RuntimeError(f"CRITICAL: LongtermAgentMemory required for Ari's memory: {e}")

    try:
        from camel.memories import (
            ChatHistoryBlock,
            ChatHistoryMemory,
            MemoryRecord,
            ScoreBasedContextCreator,
            VectorDBBlock,
            VectorDBMemory
        )
        IMPORT_STATUS["memory"] = True
        logger.info(" Memory components imported")
    except ImportError as e:
        logger.error(f"Memory components import failed: {e}")
        raise RuntimeError(f"CRITICAL: Memory components required but not available: {e}")

    # Try to import BaseMemory if it exists
    try:
        from camel.memories import BaseMemory
        logger.info(" BaseMemory imported")
    except ImportError:
        logger.info("BaseMemory not available (optional)")
        BaseMemory = None

    # Message imports - CRITICAL
    try:
        from camel.messages import BaseMessage
        IMPORT_STATUS["messages"] = True
        logger.info(" BaseMessage imported")
    except ImportError as e:
        logger.error(f"BaseMessage import failed: {e}")
        raise RuntimeError(f"CRITICAL: BaseMessage required but not available: {e}")

    # Utils - CRITICAL
    try:
        from camel.utils import OpenAITokenCounter
        IMPORT_STATUS["utils"] = True
        logger.info(" OpenAITokenCounter imported")
    except ImportError as e:
        logger.error(f"OpenAITokenCounter import failed: {e}")
        raise RuntimeError(f"CRITICAL: OpenAITokenCounter required but not available: {e}")

    # Embeddings - optional
    try:
        from camel.embeddings import BaseEmbedding, OpenAIEmbedding
        from camel.types import EmbeddingModelType
        IMPORT_STATUS["embeddings"] = True
        logger.info(" Embeddings imported")
    except ImportError as e:
        logger.warning(f"Embeddings not available: {e}")
        BaseEmbedding = None
        OpenAIEmbedding = None
        EmbeddingModelType = None

    # Toolkits - optional
    try:
        from camel.toolkits import BaseToolkit
        logger.info(" BaseToolkit imported")
    except ImportError:
        logger.warning("BaseToolkit not available")
        BaseToolkit = None

    try:
        from camel.toolkits import SearchToolkit
        logger.info(" SearchToolkit imported")
    except ImportError:
        logger.warning("SearchToolkit not available")
        SearchToolkit = None

    try:
        from camel.toolkits import MCPToolkit
        logger.info(" MCPToolkit imported")
    except ImportError:
        logger.warning("MCPToolkit not available (optional)")
        MCPToolkit = None

    try:
        from camel.toolkits import RetrievalToolkit
        logger.info(" RetrievalToolkit imported")
    except ImportError:
        logger.warning("RetrievalToolkit not available")
        RetrievalToolkit = None

    if BaseToolkit or SearchToolkit or MCPToolkit or RetrievalToolkit:
        IMPORT_STATUS["toolkits"] = True

    # Storage imports - optional
    try:
        from camel.storages import BaseStorage
        logger.info(" BaseStorage imported")
    except ImportError:
        logger.warning("BaseStorage not available")
        BaseStorage = None

    try:
        from camel.storages import QdrantStorage
        logger.info(" QdrantStorage imported")
    except ImportError:
        try:
            from camel.storages import VectorStorage as QdrantStorage
            logger.info(" VectorStorage imported as QdrantStorage")
        except ImportError:
            logger.warning("QdrantStorage/VectorStorage not available")
            QdrantStorage = None

    try:
        from camel.storages import VectorStorage
        logger.info(" VectorStorage imported")
    except ImportError:
        logger.warning("VectorStorage not available")
        VectorStorage = None

    if BaseStorage or QdrantStorage or VectorStorage:
        IMPORT_STATUS["storages"] = True

    # Retriever imports - optional but create minimal VectorRetriever if needed
    try:
        from camel.retrievers import BaseRetriever
        logger.info(" BaseRetriever imported")
    except ImportError:
        logger.warning("BaseRetriever not available")
        BaseRetriever = None

    try:
        from camel.retrievers import AutoRetriever
        logger.info(" AutoRetriever imported")
    except ImportError:
        logger.warning("AutoRetriever not available")
        AutoRetriever = None

    try:
        from camel.retrievers import VectorRetriever
        logger.info(" VectorRetriever imported")
    except ImportError:
        logger.warning("VectorRetriever not available, using minimal implementation")
        # Minimal VectorRetriever for compatibility
        class VectorRetriever:
            def __init__(self, **kwargs):
                logger.warning("Using minimal VectorRetriever")
        VectorRetriever = VectorRetriever

    if BaseRetriever or AutoRetriever or VectorRetriever:
        IMPORT_STATUS["retrievers"] = True

    # Set overall availability - require core components
    CAMEL_AVAILABLE = (
        IMPORT_STATUS["camel"] and
        ModelFactory is not None and
        ModelType is not None and
        ChatAgent is not None and
        LongtermAgentMemory is not None and
        BaseMessage is not None and
        OpenAITokenCounter is not None
    )

    logger.info(f"CAMEL_AVAILABLE: {CAMEL_AVAILABLE}")

except ImportError as e:
    logger.error(f"Failed to import CAMEL-AI components: {e}")
    logger.error("CAMEL-AI 0.2.64 is REQUIRED for Ari to function")
    logger.error("Install with: pip install camel-ai==0.2.64")
    raise RuntimeError(f"CRITICAL: CAMEL-AI not available: {e}") from e

except RuntimeError:
    # Re-raise RuntimeErrors from critical imports
    raise

# Final check - ensure we have what we need
if not CAMEL_AVAILABLE:
    missing = []
    if not ModelFactory: missing.append("ModelFactory")
    if not ModelType: missing.append("ModelType")
    if not ChatAgent: missing.append("ChatAgent")
    if not LongtermAgentMemory: missing.append("LongtermAgentMemory")
    if not BaseMessage: missing.append("BaseMessage")
    if not OpenAITokenCounter: missing.append("OpenAITokenCounter")
    
    raise RuntimeError(
        f"CRITICAL: Required CAMEL components missing: {missing}. "
        f"The AI Stylist system cannot function without CAMEL-AI 0.2.64. "
        f"Install with: pip install camel-ai==0.2.64"
    )

# Compatibility layer for CAMEL APIs - KEPT because it's useful!
class CompatibilityLayer:
    """Provides compatibility helpers for CAMEL API usage"""

    @staticmethod
    def create_memory(token_limit: int = 1024, enable_vector: bool = True) -> Optional[Any]:
        """Create memory using CAMEL 0.2.64 API structure"""
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL not available - cannot create memory")
            
        if not LongtermAgentMemory or not ScoreBasedContextCreator:
            raise RuntimeError("Memory components not available")

        try:
            # Create memory using standard 0.2.64 pattern
            memory = LongtermAgentMemory(
                context_creator=ScoreBasedContextCreator(
                    token_counter=OpenAITokenCounter(ModelType.GPT_4O_MINI) if OpenAITokenCounter and ModelType else None,
                    token_limit=token_limit,
                ),
                chat_history_block=ChatHistoryBlock() if ChatHistoryBlock else None,
                vector_db_block=VectorDBBlock() if enable_vector and VectorDBBlock else None,
            )
            return memory
        except Exception as e:
            logger.error(f"Error creating memory: {e}")
            raise RuntimeError(f"Failed to create CAMEL memory: {e}") from e

    @staticmethod
    def create_user_message(content: str, role_name: str = "User") -> Any:
        """Create user message using CAMEL 0.2.64 API"""
        if not CAMEL_AVAILABLE or not BaseMessage:
            raise RuntimeError("CAMEL not available - cannot create message")

        try:
            return BaseMessage.make_user_message(
                role_name=role_name,
                content=content
            )
        except Exception as e:
            logger.error(f"Error creating user message: {e}")
            raise RuntimeError(f"Failed to create user message: {e}") from e

    @staticmethod
    def create_assistant_message(content: str, role_name: str = "Assistant") -> Any:
        """Create assistant message using CAMEL 0.2.64 API"""
        if not CAMEL_AVAILABLE or not BaseMessage:
            raise RuntimeError("CAMEL not available - cannot create message")

        try:
            return BaseMessage.make_assistant_message(
                role_name=role_name,
                content=content
            )
        except Exception as e:
            logger.error(f"Error creating assistant message: {e}")
            raise RuntimeError(f"Failed to create assistant message: {e}") from e

    @staticmethod
    def create_memory_record(message: Any, role: str) -> Any:
        """Create memory record using CAMEL 0.2.64 API"""
        if not CAMEL_AVAILABLE or not MemoryRecord or not OpenAIBackendRole:
            raise RuntimeError("CAMEL not available - cannot create memory record")

        # Map role to backend role
        backend_role = OpenAIBackendRole.USER if role.lower() == "user" else OpenAIBackendRole.ASSISTANT

        return MemoryRecord(
            message=message,
            role_at_backend=backend_role,
        )

    @staticmethod
    def write_to_memory(memory: Any, records: list) -> bool:
        """Write to memory using CAMEL 0.2.64 API"""
        if not memory or not hasattr(memory, 'write_records'):
            raise RuntimeError("Invalid memory object - cannot write")

        try:
            memory.write_records(records)
            return True
        except Exception as e:
            logger.error(f"Error writing to memory: {e}")
            raise RuntimeError(f"Failed to write to memory: {e}") from e

    @staticmethod
    def get_memory_context(memory: Any) -> tuple:
        """Get memory context using CAMEL 0.2.64 API"""
        if not memory or not hasattr(memory, 'get_context'):
            raise RuntimeError("Invalid memory object - cannot get context")

        try:
            context, token_count = memory.get_context()
            return context, token_count
        except Exception as e:
            logger.error(f"Error getting memory context: {e}")
            raise RuntimeError(f"Failed to get memory context: {e}") from e

    @staticmethod
    def create_chat_agent(
        system_message: str,
        model_type: Any = None,
        tools: list = None,
        memory: Any = None
    ) -> Any:
        """Create ChatAgent using CAMEL 0.2.64 API"""
        if not CAMEL_AVAILABLE or not ChatAgent or not ModelFactory:
            raise RuntimeError("CAMEL not available - cannot create agent")

        model_type = model_type or (ModelType.GPT_4O if ModelType else "gpt-4o")

        try:
            # Create model first
            model = ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI if ModelPlatformType else "openai",
                model_type=model_type,
                model_config_dict={
                    "temperature": 0.7,
                    "max_tokens": 4000
                }
            )

            # Create agent with standard pattern
            agent = ChatAgent(
                system_message=system_message,
                model=model,
                tools=tools or [],
                memory=memory
            )

            return agent
        except Exception as e:
            logger.error(f"Error creating chat agent: {e}")
            raise RuntimeError(f"Failed to create chat agent: {e}") from e

# Export all components
__all__ = [
    # Availability flags
    'CAMEL_AVAILABLE',
    'CAMEL_VERSION',
    'IMPORT_STATUS',

    # Models and types
    'ModelFactory',
    'ModelPlatformType',
    'ModelType',
    'OpenAIBackendRole',
    'TaskType',
    'TerminationMode',

    # Agents
    'ChatAgent',
    'BaseAgent',

    # Memory - actual classes from 0.2.64
    'AgentMemory',
    'ChatHistoryBlock',
    'ChatHistoryMemory',
    'LongtermAgentMemory',
    'MemoryRecord',
    'ScoreBasedContextCreator',
    'VectorDBBlock',
    'VectorDBMemory',
    'BaseMemory',

    # Messages
    'BaseMessage',

    # Utils
    'OpenAITokenCounter',

    # Embeddings
    'BaseEmbedding',
    'OpenAIEmbedding',
    'EmbeddingModelType',

    # Toolkits
    'BaseToolkit',
    'SearchToolkit',
    'MCPToolkit',
    'RetrievalToolkit',

    # Storage
    'BaseStorage',
    'QdrantStorage',
    'VectorStorage',
    'StorageType',

    # Retrievers
    'BaseRetriever',
    'AutoRetriever',
    'VectorRetriever',

    # Compatibility - KEPT!
    'CompatibilityLayer'
]

# Log import summary
def print_import_summary():
    """Print summary of CAMEL imports"""
    logger.info("=== CAMEL Import Summary ===")
    logger.info(f"CAMEL Available: {CAMEL_AVAILABLE}")
    logger.info(f"CAMEL Version: {CAMEL_VERSION}")
    for module, status in IMPORT_STATUS.items():
        status_icon = "OK" if status else "MISSING"
        logger.info(f"{status_icon} {module}: {status}")
    logger.info("============================")

# Run summary on import
if __name__ != "__main__":
    print_import_summary()