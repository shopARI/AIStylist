"""
CAMEL 0.2.70 Compatibility Layer
Provides smooth migration from 0.2.64 to 0.2.70 while maintaining backward compatibility
Builds on the CompatibilityLayer from camel_imports.py
"""

import logging
import asyncio
from typing import Optional, Any, Dict, List, Callable
from functools import wraps

logger = logging.getLogger("lib.camel.v070.compatibility")

# Import from our v070 module
from . import (
    CAMEL_VERSION,
    CAMEL_AVAILABLE,
    ModelFactory,
    ModelPlatformType,
    ModelType,
    ChatAgent,
    BaseMessage,
    LongtermAgentMemory,
    ScoreBasedContextCreator,
    ChatHistoryBlock,
    VectorDBBlock,
    MemoryRecord,
    OpenAITokenCounter,
    OpenAIBackendRole,
    create_model,
    create_agent,
    create_memory,
    create_user_message,
    create_assistant_message,
    create_memory_record
)

# Import settings
from config.settings import get_settings

# =============================================================================
# MIGRATION HELPERS
# =============================================================================

class MigrationHelper:
    """
    Helps migrate from CAMEL 0.2.64 patterns to 0.2.70.
    Provides deprecation warnings and automatic conversions.
    """
    
    @staticmethod
    def check_version() -> tuple[bool, str]:
        """
        Check if CAMEL version is compatible.
        
        Returns:
            Tuple of (is_compatible, message)
        """
        if not CAMEL_AVAILABLE:
            return False, "CAMEL not available"
        
        version_parts = CAMEL_VERSION.split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1])
        patch = int(version_parts[2]) if len(version_parts) > 2 else 0
        
        if major == 0 and minor == 2:
            if patch >= 70:
                return True, f"CAMEL {CAMEL_VERSION} is compatible"
            elif patch >= 64:
                return True, f"CAMEL {CAMEL_VERSION} may work with compatibility layer"
            else:
                return False, f"CAMEL {CAMEL_VERSION} is too old (need 0.2.64+)"
        
        return False, f"Unknown CAMEL version format: {CAMEL_VERSION}"
    
    @staticmethod
    def convert_model_type(old_model: Any) -> ModelType:
        """
        Convert old model specification to ModelType enum.
        
        Args:
            old_model: Old model specification (string, enum, or model object)
            
        Returns:
            ModelType enum value
        """
        if isinstance(old_model, ModelType):
            return old_model
        
        if isinstance(old_model, str):
            model_map = {
                "gpt-4": ModelType.GPT_4,
                "gpt-4o": ModelType.GPT_4O,
                "gpt-4o-mini": ModelType.GPT_4O_MINI,
                "gpt-3.5-turbo": ModelType.GPT_3_5_TURBO
            }
            return model_map.get(old_model.lower(), ModelType.GPT_4O_MINI)
        
        if hasattr(old_model, 'model_type'):
            return old_model.model_type
        
        logger.warning(f"Unknown model type: {old_model}, defaulting to GPT_4O_MINI")
        return ModelType.GPT_4O_MINI
    
    @staticmethod
    def convert_system_message(message: Any) -> str:
        """
        Convert various message formats to string.
        
        Args:
            message: Message in any format
            
        Returns:
            String message
        """
        if isinstance(message, str):
            return message
        
        if hasattr(message, 'content'):
            return message.content
        
        if hasattr(message, '__str__'):
            return str(message)
        
        logger.warning(f"Unknown message format: {type(message)}, using string conversion")
        return str(message)

# =============================================================================
# ENHANCED COMPATIBILITY LAYER
# =============================================================================

class CompatibilityLayer:
    """
    Enhanced compatibility layer for CAMEL 0.2.64 → 0.2.70 migration.
    Extends the original CompatibilityLayer with new features.
    """
    
    def __init__(self):
        """Initialize compatibility layer with settings."""
        self.settings = get_settings()
        self.migration_helper = MigrationHelper()
        
        # Check version compatibility
        is_compatible, message = self.migration_helper.check_version()
        if not is_compatible:
            logger.error(f"CAMEL compatibility issue: {message}")
            raise RuntimeError(f"CAMEL compatibility issue: {message}")
        
        logger.info(f"CompatibilityLayer initialized: {message}")
    
    # =========================================================================
    # AGENT CREATION (with backward compatibility)
    # =========================================================================
    
    def create_chat_agent(
        self,
        system_message: Any,
        model_type: Any = None,
        tools: Optional[List[Callable]] = None,
        memory: Optional[Any] = None,
        **kwargs
    ) -> ChatAgent:
        """
        Create ChatAgent with backward compatibility for 0.2.64 patterns.
        
        This method handles:
        - Old SystemMessage objects → string conversion
        - Old model specifications → ModelType enum
        - Old kwargs → new model config
        
        Args:
            system_message: System prompt (any format)
            model_type: Model specification (any format)
            tools: Optional tools list
            memory: Optional memory instance
            **kwargs: Additional configuration
            
        Returns:
            Configured ChatAgent for 0.2.70
        """
        # Convert system message
        sys_msg = self.migration_helper.convert_system_message(system_message)
        
        # Convert model type
        if model_type is None:
            model_enum = ModelType.GPT_4O_MINI
        else:
            model_enum = self.migration_helper.convert_model_type(model_type)
        
        # Extract configuration from kwargs or use defaults
        temperature = kwargs.pop('temperature', self.settings.camel.agent_temperature)
        max_tokens = kwargs.pop('max_tokens', self.settings.camel.agent_max_tokens)
        
        # Create agent with new pattern
        return create_agent(
            system_message=sys_msg,
            model_type=model_enum,
            model_platform=ModelPlatformType.OPENAI,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            memory=memory,
            **kwargs
        )
    
    def create_battle_agent(
        self,
        name: str,
        system_message: Any,
        backend_client: Optional[Any] = None
    ) -> ChatAgent:
        """
        Create a battle agent with proper configuration.
        
        Args:
            name: Agent name (CypherBot, VibeBot, Judge)
            system_message: System prompt
            backend_client: Optional backend client (for context)
            
        Returns:
            Configured battle agent
        """
        sys_msg = self.migration_helper.convert_system_message(system_message)
        
        # Use battle-specific configuration
        return create_agent(
            system_message=sys_msg,
            model_type=ModelType(self.settings.camel.model_type),
            temperature=self.settings.battle.quality_threshold,  # Battle agents use quality threshold
            max_tokens=self.settings.camel.agent_max_tokens
        )
    
    # =========================================================================
    # MEMORY CREATION (with enhanced features)
    # =========================================================================
    
    def create_memory(
        self,
        token_limit: Optional[int] = None,
        enable_vector: Optional[bool] = None,
        enable_chat_history: Optional[bool] = None
    ) -> LongtermAgentMemory:
        """
        Create memory with settings-based defaults.
        
        Args:
            token_limit: Token limit (uses settings default if None)
            enable_vector: Enable vector DB (uses settings default if None)
            enable_chat_history: Enable chat history (uses settings default if None)
            
        Returns:
            Configured memory instance
        """
        # Use settings defaults if not specified
        if token_limit is None:
            token_limit = self.settings.camel.memory_token_limit
        if enable_vector is None:
            enable_vector = self.settings.camel.enable_vector_memory
        if enable_chat_history is None:
            enable_chat_history = self.settings.camel.enable_chat_history
        
        return create_memory(
            token_limit=token_limit,
            model_type=ModelType(self.settings.camel.model_type),
            enable_vector=enable_vector,
            enable_chat_history=enable_chat_history
        )
    
    # =========================================================================
    # MESSAGE CREATION (unchanged but included for completeness)
    # =========================================================================
    
    def create_user_message(self, content: str, role_name: str = "User") -> BaseMessage:
        """Create user message."""
        return create_user_message(content, role_name)
    
    def create_assistant_message(self, content: str, role_name: str = "Assistant") -> BaseMessage:
        """Create assistant message."""
        return create_assistant_message(content, role_name)
    
    def create_memory_record(self, message: BaseMessage, role: str) -> MemoryRecord:
        """Create memory record."""
        return create_memory_record(message, role)
    
    # =========================================================================
    # ASYNC COMPATIBILITY
    # =========================================================================
    
    async def async_agent_step(
        self,
        agent: ChatAgent,
        message: BaseMessage
    ) -> Any:
        """
        Execute agent step with async compatibility.
        Handles different async method names across versions.
        
        Args:
            agent: ChatAgent instance
            message: Message to process
            
        Returns:
            Agent response
        """
        # Check which async method is available
        if hasattr(agent, 'step_async'):
            return await agent.step_async(message)
        elif hasattr(agent, 'astep'):
            return await agent.astep(message)
        elif hasattr(agent, 'step'):
            # Run sync method in thread pool
            return await asyncio.to_thread(agent.step, message)
        else:
            raise RuntimeError("No suitable step method found on agent")
    
    # =========================================================================
    # MIGRATION UTILITIES
    # =========================================================================
    
    def migrate_agent_config(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Migrate old agent configuration to new format.
        
        Args:
            old_config: Old configuration dictionary
            
        Returns:
            New configuration dictionary
        """
        new_config = {}
        
        # Map old keys to new keys
        key_mapping = {
            'model': 'model_type',
            'system_msg': 'system_message',
            'max_tokens': 'max_tokens',
            'temperature': 'temperature',
            'tools': 'tools',
            'memory': 'memory'
        }
        
        for old_key, new_key in key_mapping.items():
            if old_key in old_config:
                value = old_config[old_key]
                
                # Special handling for certain keys
                if old_key == 'model':
                    value = self.migration_helper.convert_model_type(value)
                elif old_key == 'system_msg':
                    value = self.migration_helper.convert_system_message(value)
                
                new_config[new_key] = value
        
        return new_config
    
    @staticmethod
    def deprecation_warning(old_method: str, new_method: str):
        """
        Log deprecation warning for old patterns.
        
        Args:
            old_method: Old method/pattern name
            new_method: New method/pattern name
        """
        logger.warning(
            f"DEPRECATION: '{old_method}' is deprecated in CAMEL 0.2.70. "
            f"Use '{new_method}' instead."
        )

# =============================================================================
# DECORATORS FOR MIGRATION
# =============================================================================

def migrate_to_070(func: Callable) -> Callable:
    """
    Decorator to automatically migrate function calls to 0.2.70 patterns.
    
    Usage:
        @migrate_to_070
        def create_agent_old_way(system_msg, model):
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Log migration
        logger.debug(f"Migrating call to {func.__name__}")
        
        # Convert arguments if needed
        compat = CompatibilityLayer()
        
        # Check for common patterns and convert
        if 'system_msg' in kwargs:
            kwargs['system_message'] = compat.migration_helper.convert_system_message(
                kwargs.pop('system_msg')
            )
        
        if 'model' in kwargs:
            kwargs['model_type'] = compat.migration_helper.convert_model_type(
                kwargs.pop('model')
            )
        
        return func(*args, **kwargs)
    
    return wrapper

# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

# Create global compatibility layer instance
_compat_layer: Optional[CompatibilityLayer] = None

def get_compatibility_layer() -> CompatibilityLayer:
    """
    Get the global compatibility layer instance.
    
    Returns:
        CompatibilityLayer instance
    """
    global _compat_layer
    if _compat_layer is None:
        _compat_layer = CompatibilityLayer()
    return _compat_layer

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Classes
    'CompatibilityLayer',
    'MigrationHelper',
    
    # Functions
    'get_compatibility_layer',
    'migrate_to_070',
    
    # Re-exports from v070 __init__
    'create_model',
    'create_agent',
    'create_memory',
    'create_user_message',
    'create_assistant_message',
    'create_memory_record',
    'create_battle_agent',
    
    # Status
    'CAMEL_VERSION',
    'CAMEL_AVAILABLE'
]

# Initialize on import
if __name__ != "__main__":
    try:
        get_compatibility_layer()
        logger.info("CAMEL 0.2.70 compatibility layer ready")
    except Exception as e:
        logger.error(f"Failed to initialize compatibility layer: {e}")
