"""
Centralized CAMEL-AI imports for version 0.2.64
Uses actual APIs from CAMEL-AI 0.2.64

FIXED: Added missing VectorRetriever and StorageType imports
"""

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
StorageType = None  # FIXED: Added missing StorageType
BaseRetriever = None
AutoRetriever = None
VectorRetriever = None  # FIXED: Added missing VectorRetriever

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
        logger.info("✅ ModelFactory imported")
    except ImportError as e:
        logger.warning(f"ModelFactory import failed: {e}")
        ModelFactory = None
    
    try:
        from camel.types import (
            ModelPlatformType, 
            ModelType,
            OpenAIBackendRole,
            TaskType,
            TerminationMode
        )
        IMPORT_STATUS["types"] = True
        logger.info("✅ Types imported successfully")
    except ImportError as e:
        logger.warning(f"Types import failed: {e}")
        # Create minimal fallbacks
        class ModelType:
            GPT_4O = "gpt-4o"
            GPT_4O_MINI = "gpt-4o-mini"
            GPT_3_5_TURBO = "gpt-3.5-turbo"
        
        class ModelPlatformType:
            OPENAI = "openai"
        
        class OpenAIBackendRole:
            USER = "user"
            ASSISTANT = "assistant"
            SYSTEM = "system"
    
    # FIXED: Try to import StorageType from types
    try:
        from camel.types import StorageType
        logger.info("✅ StorageType imported")
    except ImportError:
        logger.info("StorageType not available, creating fallback")
        class StorageType:
            QDRANT = "qdrant"
            LOCAL = "local"
            MEMORY = "memory"
        StorageType = StorageType
    
    # Agent imports - try ChatAgent only (most common)
    try:
        from camel.agents import ChatAgent
        IMPORT_STATUS["agents"] = True
        logger.info("✅ ChatAgent imported")
    except ImportError as e:
        logger.warning(f"ChatAgent import failed: {e}")
        ChatAgent = None
    
    # Try BaseAgent separately since it might not exist
    try:
        from camel.agents import BaseAgent
        logger.info("✅ BaseAgent imported")
    except ImportError as e:
        logger.info("BaseAgent not available (optional)")
        BaseAgent = None
    
    # Memory imports - try each separately
    try:
        from camel.memories import LongtermAgentMemory
        logger.info("✅ LongtermAgentMemory imported")
    except ImportError as e:
        logger.warning(f"LongtermAgentMemory import failed: {e}")
        LongtermAgentMemory = None
    
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
        logger.info("✅ Memory components imported")
    except ImportError as e:
        logger.warning(f"Memory components import failed: {e}")
        # Create minimal fallbacks
        class MemoryRecord:
            def __init__(self, message=None, role_at_backend=None, **kwargs):
                self.message = message
                self.role_at_backend = role_at_backend
        
        class ScoreBasedContextCreator:
            def __init__(self, token_counter=None, token_limit=1024, **kwargs):
                self.token_limit = token_limit
        
        class ChatHistoryBlock:
            def __init__(self, **kwargs):
                pass
        
        class VectorDBBlock:
            def __init__(self, **kwargs):
                pass
    
    # Try to import BaseMemory if it exists
    try:
        from camel.memories import BaseMemory
        logger.info("✅ BaseMemory imported")
    except ImportError:
        logger.info("BaseMemory not available (optional)")
        BaseMemory = None
    
    # Message imports
    try:
        from camel.messages import BaseMessage
        IMPORT_STATUS["messages"] = True
        logger.info("✅ BaseMessage imported")
    except ImportError as e:
        logger.warning(f"BaseMessage import failed: {e}")
        # Create minimal fallback
        class BaseMessage:
            def __init__(self, role_name, content):
                self.role_name = role_name
                self.content = content
            
            @classmethod
            def make_user_message(cls, role_name="User", content=""):
                return cls(role_name, content)
            
            @classmethod
            def make_assistant_message(cls, role_name="Assistant", content=""):
                return cls(role_name, content)
        
        BaseMessage = BaseMessage
    
    # Utils
    try:
        from camel.utils import OpenAITokenCounter
        IMPORT_STATUS["utils"] = True
        logger.info("✅ OpenAITokenCounter imported")
    except ImportError as e:
        logger.warning(f"OpenAITokenCounter import failed: {e}")
        # Create minimal fallback
        class OpenAITokenCounter:
            def __init__(self, model_type):
                self.model_type = model_type
        
        OpenAITokenCounter = OpenAITokenCounter
    
    # Embeddings - optional
    try:
        from camel.embeddings import BaseEmbedding, OpenAIEmbedding
        from camel.types import EmbeddingModelType
        IMPORT_STATUS["embeddings"] = True
        logger.info("✅ Embeddings imported")
    except ImportError as e:
        logger.warning(f"Embeddings not available: {e}")
        BaseEmbedding = None
        OpenAIEmbedding = None
        EmbeddingModelType = None
    
    # Toolkits - optional
    try:
        from camel.toolkits import BaseToolkit
        logger.info("✅ BaseToolkit imported")
    except ImportError:
        logger.warning("BaseToolkit not available")
        BaseToolkit = None
    
    try:
        from camel.toolkits import SearchToolkit
        logger.info("✅ SearchToolkit imported")
    except ImportError:
        logger.warning("SearchToolkit not available")
        SearchToolkit = None
    
    try:
        from camel.toolkits import MCPToolkit
        logger.info("✅ MCPToolkit imported")
    except ImportError:
        logger.warning("MCPToolkit not available (optional)")
        MCPToolkit = None
    
    try:
        from camel.toolkits import RetrievalToolkit
        logger.info("✅ RetrievalToolkit imported")
    except ImportError:
        logger.warning("RetrievalToolkit not available")
        RetrievalToolkit = None

    if BaseToolkit or SearchToolkit or MCPToolkit or RetrievalToolkit:
        IMPORT_STATUS["toolkits"] = True
    
    # Storage imports - optional
    try:
        from camel.storages import BaseStorage
        logger.info("✅ BaseStorage imported")
    except ImportError:
        logger.warning("BaseStorage not available")
        BaseStorage = None
    
    try:
        from camel.storages import QdrantStorage
        logger.info("✅ QdrantStorage imported")
    except ImportError:
        try:
            from camel.storages import VectorStorage as QdrantStorage
            logger.info("✅ VectorStorage imported as QdrantStorage")
        except ImportError:
            logger.warning("QdrantStorage/VectorStorage not available")
            QdrantStorage = None
    
    # FIXED: Try to import VectorStorage separately
    try:
        from camel.storages import VectorStorage
        logger.info("✅ VectorStorage imported")
    except ImportError:
        logger.warning("VectorStorage not available")
        VectorStorage = None
    
    if BaseStorage or QdrantStorage or VectorStorage:
        IMPORT_STATUS["storages"] = True
    
    # FIXED: Retriever imports - try each separately
    try:
        from camel.retrievers import BaseRetriever
        logger.info("✅ BaseRetriever imported")
    except ImportError:
        logger.warning("BaseRetriever not available")
        BaseRetriever = None
    
    try:
        from camel.retrievers import AutoRetriever
        logger.info("✅ AutoRetriever imported")
    except ImportError:
        logger.warning("AutoRetriever not available")
        AutoRetriever = None
    
    # FIXED: Try to import VectorRetriever specifically
    try:
        from camel.retrievers import VectorRetriever
        logger.info("✅ VectorRetriever imported")
    except ImportError:
        logger.warning("VectorRetriever not available, creating fallback")
        # Create a minimal fallback
        class VectorRetriever:
            def __init__(self, **kwargs):
                logger.warning("Using fallback VectorRetriever")
                
        VectorRetriever = VectorRetriever
    
    if BaseRetriever or AutoRetriever or VectorRetriever:
        IMPORT_STATUS["retrievers"] = True
    
    # Set overall availability - require core components
    CAMEL_AVAILABLE = (
        IMPORT_STATUS["camel"] and 
        ModelType is not None and 
        (ChatAgent is not None or LongtermAgentMemory is not None)
    )
    
    logger.info(f"CAMEL_AVAILABLE: {CAMEL_AVAILABLE}")
    
except ImportError as e:
    logger.error(f"Failed to import CAMEL-AI components: {e}")
    CAMEL_AVAILABLE = False
    CAMEL_VERSION = None
    
    # Define None for all components to prevent NameError
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


# Compatibility layer for CAMEL APIs
class CompatibilityLayer:
    """Provides compatibility helpers for CAMEL API usage"""
    
    @staticmethod
    def create_memory(token_limit: int = 1024, enable_vector: bool = True) -> Optional[Any]:
        """Create memory using CAMEL 0.2.64 API structure"""
        if not LongtermAgentMemory or not ScoreBasedContextCreator:
            logger.warning("Memory components not available, using fallback")
            return None
            
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
            return None
    
    @staticmethod
    def create_user_message(content: str, role_name: str = "User") -> Optional[Any]:
        """Create user message using CAMEL 0.2.64 API"""
        if not BaseMessage:
            return None
            
        try:
            return BaseMessage.make_user_message(
                role_name=role_name,
                content=content
            )
        except Exception as e:
            logger.error(f"Error creating user message: {e}")
            return None
    
    @staticmethod
    def create_assistant_message(content: str, role_name: str = "Assistant") -> Optional[Any]:
        """Create assistant message using CAMEL 0.2.64 API"""
        if not BaseMessage:
            return None
            
        try:
            return BaseMessage.make_assistant_message(
                role_name=role_name,
                content=content
            )
        except Exception as e:
            logger.error(f"Error creating assistant message: {e}")
            return None
    
    @staticmethod
    def create_memory_record(message: Any, role: str) -> Optional[Any]:
        """Create memory record using CAMEL 0.2.64 API"""
        if not MemoryRecord or not OpenAIBackendRole:
            return None
            
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
            return False
            
        try:
            memory.write_records(records)
            return True
        except Exception as e:
            logger.error(f"Error writing to memory: {e}")
            return False
    
    @staticmethod
    def get_memory_context(memory: Any) -> tuple:
        """Get memory context using CAMEL 0.2.64 API"""
        if not memory or not hasattr(memory, 'get_context'):
            return [], 0
            
        try:
            context, token_count = memory.get_context()
            return context, token_count
        except Exception as e:
            logger.error(f"Error getting memory context: {e}")
            return [], 0
    
    @staticmethod
    def create_chat_agent(
        system_message: str,
        model_type: Any = None,
        tools: list = None,
        memory: Any = None
    ) -> Optional[Any]:
        """Create ChatAgent using CAMEL 0.2.64 API"""
        if not ChatAgent or not ModelFactory:
            return None
            
        model_type = model_type or (ModelType.GPT_4O if ModelType else "gpt-4o")
        
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


# Export all components - FIXED: Added missing exports
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
    
    # Storage - FIXED: Added missing storage exports
    'BaseStorage',
    'QdrantStorage',
    'VectorStorage',
    'StorageType',
    
    # Retrievers - FIXED: Added missing retriever exports
    'BaseRetriever',
    'AutoRetriever',
    'VectorRetriever',
    
    # Compatibility
    'CompatibilityLayer'
]


# Log import summary
def print_import_summary():
    """Print summary of CAMEL imports"""
    logger.info("=== CAMEL Import Summary ===")
    logger.info(f"CAMEL Available: {CAMEL_AVAILABLE}")
    logger.info(f"CAMEL Version: {CAMEL_VERSION}")
    for module, status in IMPORT_STATUS.items():
        status_icon = "✅" if status else "❌"
        logger.info(f"{status_icon} {module}: {status}")
    logger.info("===============================")


# Run summary on import
if __name__ != "__main__":
    print_import_summary()
