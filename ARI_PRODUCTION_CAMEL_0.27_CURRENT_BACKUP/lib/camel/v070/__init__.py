"""
CAMEL-AI 0.2.70+ Integration Module
Clean implementation without fallbacks - fail fast philosophy
Replaces camel_imports.py with modern patterns
"""

import logging
from typing import Optional, Any, Dict, List, Callable
from enum import Enum

logger = logging.getLogger("camel_v070")

# =============================================================================
# CAMEL VERSION VALIDATION
# =============================================================================

try:
    import camel
    CAMEL_VERSION = camel.__version__
    
    # Validate version
    version_parts = CAMEL_VERSION.split('.')
    major = int(version_parts[0])
    minor = int(version_parts[1])
    patch = int(version_parts[2]) if len(version_parts) > 2 else 0
    
    if not (major == 0 and minor == 2 and patch >= 70):
        raise RuntimeError(
            f"CAMEL {CAMEL_VERSION} detected. Version 0.2.70+ required. "
            f"Install with: pip install camel-ai==0.2.70"
        )
    
    logger.info(f"CAMEL {CAMEL_VERSION} initialized successfully")
    CAMEL_AVAILABLE = True
    
except ImportError as e:
    raise RuntimeError(
        "CAMEL-AI not installed. Install with: pip install camel-ai==0.2.70"
    ) from e

# =============================================================================
# CORE IMPORTS
# =============================================================================

# Models and Factory - CRITICAL
from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

# Agents - CRITICAL
from camel.agents import ChatAgent

# Messages - CRITICAL  
from camel.messages import BaseMessage

# Memory Components - CRITICAL
from camel.memories import (
    LongtermAgentMemory,
    ScoreBasedContextCreator,
    ChatHistoryBlock,
    VectorDBBlock,
    MemoryRecord
)

# Utils - CRITICAL
from camel.utils import OpenAITokenCounter

# Types
from camel.types import (
    OpenAIBackendRole,
    TaskType,
    TerminationMode
)

# Optional Components (with graceful handling)
try:
    from camel.embeddings import OpenAIEmbedding
    from camel.types import EmbeddingModelType
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    logger.warning("Embeddings not available")
    OpenAIEmbedding = None
    EmbeddingModelType = None
    EMBEDDINGS_AVAILABLE = False

try:
    from camel.storages import QdrantStorage, VectorStorage
    from camel.types import StorageType
    STORAGE_AVAILABLE = True
except ImportError:
    logger.warning("Storage components not available")
    QdrantStorage = None
    VectorStorage = None
    StorageType = None
    STORAGE_AVAILABLE = False

try:
    from camel.retrievers import VectorRetriever
    RETRIEVER_AVAILABLE = True
except ImportError:
    logger.warning("Retriever not available")
    VectorRetriever = None
    RETRIEVER_AVAILABLE = False

# =============================================================================
# HELPER FUNCTIONS FOR 0.2.70 PATTERNS
# =============================================================================

def create_model(
    model_type: ModelType = ModelType.GPT_4O_MINI,
    model_platform: ModelPlatformType = ModelPlatformType.OPENAI,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    **kwargs
) -> Any:
    """
    Create a CAMEL model using the 0.2.70 pattern.
    
    Args:
        model_type: The model type (e.g., GPT_4O_MINI)
        model_platform: The platform (e.g., OPENAI)
        temperature: Model temperature
        max_tokens: Maximum tokens
        **kwargs: Additional model config
        
    Returns:
        Model instance for use with ChatAgent
        
    Raises:
        RuntimeError: If model creation fails
    """
    try:
        config = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        model = ModelFactory.create(
            model_platform=model_platform,
            model_type=model_type,
            model_config_dict=config
        )
        
        logger.debug(f"Created model: {model_type} on {model_platform}")
        return model
        
    except Exception as e:
        raise RuntimeError(f"Failed to create model: {e}") from e


def create_agent(
    system_message: str,
    model_type: ModelType = ModelType.GPT_4O_MINI,
    model_platform: ModelPlatformType = ModelPlatformType.OPENAI,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    tools: Optional[List[Callable]] = None,
    memory: Optional[Any] = None,
    **kwargs
) -> ChatAgent:
    """
    Create a ChatAgent using the 0.2.70 pattern.
    
    This is THE standard way to create agents in 0.2.70+
    
    Args:
        system_message: System prompt (direct string)
        model_type: Model type to use
        model_platform: Platform to use
        temperature: Model temperature
        max_tokens: Maximum tokens
        tools: List of tools/functions
        memory: Memory instance
        **kwargs: Additional model config
        
    Returns:
        Configured ChatAgent
        
    Raises:
        ValueError: Invalid parameters
        RuntimeError: Agent creation failed
    """
    if not system_message or not isinstance(system_message, str):
        raise ValueError("system_message must be a non-empty string")
    
    try:
        # Step 1: Create model
        model = create_model(
            model_type=model_type,
            model_platform=model_platform,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        # Step 2: Create agent with model
        agent = ChatAgent(
            system_message=system_message,  # Direct string in 0.2.70
            model=model,  # Model object, not type
            tools=tools or [],  # Direct list
            memory=memory
        )
        
        logger.debug(f"Created agent with {len(tools or [])} tools")
        return agent
        
    except Exception as e:
        raise RuntimeError(f"Failed to create agent: {e}") from e


def create_memory(
    token_limit: int = 2048,
    model_type: ModelType = ModelType.GPT_4O_MINI,
    enable_vector: bool = True,
    enable_chat_history: bool = True
) -> LongtermAgentMemory:
    """
    Create a LongtermAgentMemory using 0.2.70 patterns.
    
    Args:
        token_limit: Maximum tokens for context
        model_type: Model type for token counting
        enable_vector: Enable vector database
        enable_chat_history: Enable chat history
        
    Returns:
        Configured memory instance
        
    Raises:
        RuntimeError: Memory creation failed
    """
    try:
        # Create context creator
        context_creator = ScoreBasedContextCreator(
            token_counter=OpenAITokenCounter(model_type),
            token_limit=token_limit
        )
        
        # Create memory with optional components
        memory = LongtermAgentMemory(
            context_creator=context_creator,
            chat_history_block=ChatHistoryBlock() if enable_chat_history else None,
            vector_db_block=VectorDBBlock() if enable_vector else None
        )
        
        logger.debug(f"Created memory with token_limit={token_limit}")
        return memory
        
    except Exception as e:
        raise RuntimeError(f"Failed to create memory: {e}") from e


def create_user_message(content: str, role_name: str = "User") -> BaseMessage:
    """
    Create a user message.
    
    Args:
        content: Message content
        role_name: Role name
        
    Returns:
        User message
    """
    return BaseMessage.make_user_message(
        role_name=role_name,
        content=content
    )


def create_assistant_message(content: str, role_name: str = "Assistant") -> BaseMessage:
    """
    Create an assistant message.
    
    Args:
        content: Message content
        role_name: Role name
        
    Returns:
        Assistant message
    """
    return BaseMessage.make_assistant_message(
        role_name=role_name,
        content=content
    )


def create_memory_record(
    message: BaseMessage,
    role: str
) -> MemoryRecord:
    """
    Create a memory record.
    
    Args:
        message: Message to record
        role: Role (user/assistant)
        
    Returns:
        Memory record
    """
    backend_role = (
        OpenAIBackendRole.USER 
        if role.lower() == "user" 
        else OpenAIBackendRole.ASSISTANT
    )
    
    return MemoryRecord(
        message=message,
        role_at_backend=backend_role
    )

# =============================================================================
# AGENT FACTORY HELPERS
# =============================================================================

def create_stylist_agent(
    personality: str,
    memory: Optional[Any] = None,
    temperature: float = 0.7,
    max_tokens: int = 4000
) -> ChatAgent:
    """
    Create Ari stylist agent with exact personality.
    
    Args:
        personality: Ari's exact personality string
        memory: Memory instance
        temperature: Model temperature
        max_tokens: Maximum tokens
        
    Returns:
        Configured stylist agent
    """
    return create_agent(
        system_message=personality,
        model_type=ModelType.GPT_4O_MINI,
        temperature=temperature,
        max_tokens=max_tokens,
        memory=memory
    )


def create_battle_agent(
    name: str,
    system_message: str,
    model_type: ModelType = ModelType.GPT_4O_MINI
) -> ChatAgent:
    """
    Create a battle agent (CypherBot, VibeBot, or Judge).
    
    Args:
        name: Agent name for logging
        system_message: Agent personality
        model_type: Model to use
        
    Returns:
        Configured battle agent
    """
    logger.info(f"Creating battle agent: {name}")
    
    return create_agent(
        system_message=system_message,
        model_type=model_type,
        temperature=0.7,
        max_tokens=4000
    )

# =============================================================================
# COMPATIBILITY LAYER
# =============================================================================

class CompatibilityBridge:
    """
    Bridge between old 0.2.64 patterns and new 0.2.70 patterns.
    Helps with gradual migration.
    """
    
    @staticmethod
    def adapt_old_agent_creation(
        system_message: Any,
        model: Any = None,
        **kwargs
    ) -> ChatAgent:
        """
        Adapt old agent creation pattern to new.
        
        Handles:
        - SystemMessage objects → strings
        - ModelType enums → ModelFactory pattern
        - Old kwargs → new pattern
        """
        # Extract system message content
        if isinstance(system_message, str):
            sys_msg = system_message
        elif hasattr(system_message, 'content'):
            sys_msg = system_message.content
        else:
            sys_msg = str(system_message)
        
        # Handle model parameter
        if model is None:
            model_type = ModelType.GPT_4O_MINI
        elif isinstance(model, ModelType):
            model_type = model
        elif hasattr(model, 'model_type'):
            model_type = model.model_type
        else:
            model_type = ModelType.GPT_4O_MINI
        
        # Extract tools
        tools = kwargs.pop('tools', [])
        memory = kwargs.pop('memory', None)
        
        # Create with new pattern
        return create_agent(
            system_message=sys_msg,
            model_type=model_type,
            tools=tools,
            memory=memory
        )
    
    @staticmethod
    def check_async_method(agent: ChatAgent) -> str:
        """
        Check which async method the agent has.
        
        Returns:
            'step_async', 'astep', or 'step' (sync)
        """
        if hasattr(agent, 'step_async'):
            return 'step_async'
        elif hasattr(agent, 'astep'):
            return 'astep'
        else:
            return 'step'

# =============================================================================
# STATUS CHECK
# =============================================================================

def check_camel_status() -> Dict[str, Any]:
    """
    Check CAMEL installation and component status.
    
    Returns:
        Status dictionary
    """
    return {
        "version": CAMEL_VERSION,
        "available": CAMEL_AVAILABLE,
        "components": {
            "core": True,  # Always true if we get here
            "embeddings": EMBEDDINGS_AVAILABLE,
            "storage": STORAGE_AVAILABLE,
            "retriever": RETRIEVER_AVAILABLE
        },
        "model_types": [m.name for m in ModelType],
        "platforms": [p.name for p in ModelPlatformType]
    }

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Status
    'CAMEL_VERSION',
    'CAMEL_AVAILABLE',
    'check_camel_status',
    
    # Core CAMEL exports
    'ModelFactory',
    'ModelPlatformType',
    'ModelType',
    'ChatAgent',
    'BaseMessage',
    
    # Memory
    'LongtermAgentMemory',
    'ScoreBasedContextCreator',
    'ChatHistoryBlock',
    'VectorDBBlock',
    'MemoryRecord',
    
    # Utils
    'OpenAITokenCounter',
    'OpenAIBackendRole',
    
    # Helpers
    'create_model',
    'create_agent',
    'create_memory',
    'create_user_message',
    'create_assistant_message',
    'create_memory_record',
    'create_stylist_agent',
    'create_battle_agent',
    
    # Compatibility
    'CompatibilityBridge',
    
    # Optional
    'OpenAIEmbedding',
    'EmbeddingModelType',
    'QdrantStorage',
    'VectorStorage',
    'StorageType',
    'VectorRetriever'
]

# Log initialization
logger.info(f"CAMEL 0.2.70 integration ready - {len(__all__)} exports")
