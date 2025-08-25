"""
Extended CAMEL 0.2.70 Compatibility Layer
Provides additional helpers and migration utilities
"""

import logging
import asyncio
from typing import Optional, Any, Dict, List, Union, Callable
from dataclasses import dataclass
import json

logger = logging.getLogger("camel.compatibility")

# Import core from main module
from . import (
    ChatAgent, BaseMessage, create_agent, create_memory,
    ModelType, ModelPlatformType, CAMEL_AVAILABLE
)


@dataclass
class AgentResponse:
    """Standardized agent response wrapper."""
    content: str
    raw_response: Any
    success: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AsyncAgentWrapper:
    """
    Wrapper to make CAMEL agents fully async-compatible.
    Handles both sync and async methods transparently.
    """
    
    def __init__(self, agent: ChatAgent):
        """
        Initialize wrapper with CAMEL agent.
        
        Args:
            agent: CAMEL ChatAgent instance
        """
        self.agent = agent
        self._method_cache = {}
        self._detect_methods()
    
    def _detect_methods(self):
        """Detect which methods the agent has."""
        self._method_cache['step'] = hasattr(self.agent, 'step')
        self._method_cache['step_async'] = hasattr(self.agent, 'step_async')
        self._method_cache['astep'] = hasattr(self.agent, 'astep')
        self._method_cache['reset'] = hasattr(self.agent, 'reset')
        
        # Log detected methods
        logger.debug(f"Agent methods detected: {self._method_cache}")
    
    async def step(self, message: Union[str, BaseMessage]) -> AgentResponse:
        """
        Execute agent step asynchronously.
        
        Args:
            message: Input message (string or BaseMessage)
            
        Returns:
            Standardized response
        """
        try:
            # Ensure message is BaseMessage
            if isinstance(message, str):
                from . import create_user_message
                message = create_user_message(message)
            
            # Try async methods first
            if self._method_cache.get('step_async'):
                response = await self.agent.step_async(message)
            elif self._method_cache.get('astep'):
                response = await self.agent.astep(message)
            elif self._method_cache.get('step'):
                # Run sync method in thread pool
                response = await asyncio.to_thread(self.agent.step, message)
            else:
                raise RuntimeError("Agent has no step method")
            
            # Extract content from response
            content = self._extract_content(response)
            
            return AgentResponse(
                content=content,
                raw_response=response,
                success=True,
                metadata=self._extract_metadata(response)
            )
            
        except Exception as e:
            logger.error(f"Agent step failed: {e}")
            return AgentResponse(
                content="",
                raw_response=None,
                success=False,
                error=str(e)
            )
    
    def _extract_content(self, response: Any) -> str:
        """Extract content from various response types."""
        if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
            return response.msg.content
        elif hasattr(response, 'content'):
            return response.content
        elif isinstance(response, str):
            return response
        elif isinstance(response, dict) and 'content' in response:
            return response['content']
        else:
            return str(response)
    
    def _extract_metadata(self, response: Any) -> Optional[Dict[str, Any]]:
        """Extract metadata from response."""
        metadata = {}
        
        if hasattr(response, 'info'):
            metadata['info'] = response.info
        if hasattr(response, 'terminated'):
            metadata['terminated'] = response.terminated
        if hasattr(response, 'tokens_used'):
            metadata['tokens_used'] = response.tokens_used
        
        return metadata if metadata else None
    
    async def reset(self):
        """Reset agent state."""
        if self._method_cache.get('reset'):
            if asyncio.iscoroutinefunction(self.agent.reset):
                await self.agent.reset()
            else:
                await asyncio.to_thread(self.agent.reset)
    
    def get_system_message(self) -> str:
        """Get agent's system message."""
        if hasattr(self.agent, 'system_message'):
            if isinstance(self.agent.system_message, str):
                return self.agent.system_message
            elif hasattr(self.agent.system_message, 'content'):
                return self.agent.system_message.content
        return ""


class MessageConverter:
    """Convert between different message formats."""
    
    @staticmethod
    def dict_to_base_message(
        msg_dict: Dict[str, Any],
        role_name: str = "User"
    ) -> BaseMessage:
        """
        Convert dictionary to BaseMessage.
        
        Args:
            msg_dict: Message dictionary
            role_name: Role name
            
        Returns:
            BaseMessage instance
        """
        from . import create_user_message, create_assistant_message
        
        role = msg_dict.get('role', 'user').lower()
        content = msg_dict.get('content', '')
        
        if role in ['user', 'human']:
            return create_user_message(content, role_name)
        else:
            return create_assistant_message(content, role_name)
    
    @staticmethod
    def base_message_to_dict(message: BaseMessage) -> Dict[str, Any]:
        """
        Convert BaseMessage to dictionary.
        
        Args:
            message: BaseMessage instance
            
        Returns:
            Message dictionary
        """
        return {
            'role': message.role_name if hasattr(message, 'role_name') else 'user',
            'content': message.content if hasattr(message, 'content') else str(message),
            'metadata': message.metadata if hasattr(message, 'metadata') else {}
        }
    
    @staticmethod
    def conversation_to_messages(
        conversation: List[Dict[str, Any]]
    ) -> List[BaseMessage]:
        """
        Convert conversation history to BaseMessage list.
        
        Args:
            conversation: List of message dicts
            
        Returns:
            List of BaseMessage instances
        """
        messages = []
        for msg in conversation:
            messages.append(MessageConverter.dict_to_base_message(msg))
        return messages


class AgentFactory:
    """
    Factory for creating specialized agents with migration support.
    """
    
    @staticmethod
    def create_from_legacy_config(config: Dict[str, Any]) -> ChatAgent:
        """
        Create agent from legacy configuration.
        
        Args:
            config: Legacy agent configuration
            
        Returns:
            ChatAgent instance
        """
        # Extract configuration
        system_message = config.get('system_message', '')
        model_type_str = config.get('model', 'gpt-4o-mini')
        temperature = config.get('temperature', 0.7)
        max_tokens = config.get('max_tokens', 4000)
        
        # Map legacy model names
        model_map = {
            'gpt-4': ModelType.GPT_4O,
            'gpt-4-turbo': ModelType.GPT_4O,
            'gpt-3.5-turbo': ModelType.GPT_4O_MINI,
            'gpt-4o-mini': ModelType.GPT_4O_MINI
        }
        
        model_type = model_map.get(model_type_str, ModelType.GPT_4O_MINI)
        
        # Create agent
        return create_agent(
            system_message=system_message,
            model_type=model_type,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    @staticmethod
    def migrate_agent_state(
        old_agent: Any,
        new_agent: ChatAgent
    ) -> ChatAgent:
        """
        Migrate state from old agent to new.
        
        Args:
            old_agent: Old agent instance
            new_agent: New ChatAgent instance
            
        Returns:
            New agent with migrated state
        """
        # Migrate memory if present
        if hasattr(old_agent, 'memory') and old_agent.memory:
            if hasattr(new_agent, 'memory'):
                # Copy memory records
                if hasattr(old_agent.memory, 'records'):
                    for record in old_agent.memory.records:
                        if hasattr(new_agent.memory, 'add_record'):
                            new_agent.memory.add_record(record)
        
        # Migrate conversation history if present
        if hasattr(old_agent, 'stored_messages'):
            if hasattr(new_agent, 'stored_messages'):
                new_agent.stored_messages = old_agent.stored_messages.copy()
        
        return new_agent


class ModelMigration:
    """Utilities for model migration."""
    
    @staticmethod
    def get_equivalent_model(
        old_model: str,
        platform: str = 'openai'
    ) -> ModelType:
        """
        Get equivalent ModelType for old model string.
        
        Args:
            old_model: Old model identifier
            platform: Model platform
            
        Returns:
            Equivalent ModelType
        """
        # OpenAI mappings
        openai_map = {
            'gpt-4': ModelType.GPT_4O,
            'gpt-4-0125-preview': ModelType.GPT_4O,
            'gpt-4-turbo-preview': ModelType.GPT_4O,
            'gpt-4-turbo': ModelType.GPT_4O,
            'gpt-4o': ModelType.GPT_4O,
            'gpt-3.5-turbo': ModelType.GPT_4O_MINI,
            'gpt-3.5-turbo-16k': ModelType.GPT_4O_MINI,
            'gpt-4o-mini': ModelType.GPT_4O_MINI
        }
        
        if platform.lower() == 'openai':
            return openai_map.get(old_model, ModelType.GPT_4O_MINI)
        
        # Default to GPT_4O_MINI
        return ModelType.GPT_4O_MINI
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> bool:
        """
        Validate agent configuration.
        
        Args:
            config: Agent configuration
            
        Returns:
            True if valid
        """
        required = ['system_message']
        for field in required:
            if field not in config or not config[field]:
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate types
        if not isinstance(config['system_message'], str):
            logger.error("system_message must be a string")
            return False
        
        # Validate numeric ranges
        if 'temperature' in config:
            if not 0 <= config['temperature'] <= 2:
                logger.error("temperature must be between 0 and 2")
                return False
        
        if 'max_tokens' in config:
            if not 1 <= config['max_tokens'] <= 128000:
                logger.error("max_tokens must be between 1 and 128000")
                return False
        
        return True


class MemoryMigration:
    """Utilities for memory migration."""
    
    @staticmethod
    def export_memory(agent: ChatAgent) -> Dict[str, Any]:
        """
        Export agent memory to dictionary.
        
        Args:
            agent: ChatAgent with memory
            
        Returns:
            Memory export dictionary
        """
        export = {
            'records': [],
            'metadata': {}
        }
        
        if hasattr(agent, 'memory') and agent.memory:
            # Export records
            if hasattr(agent.memory, 'get_records'):
                records = agent.memory.get_records()
                for record in records:
                    export['records'].append({
                        'content': str(record),
                        'timestamp': getattr(record, 'timestamp', None)
                    })
            
            # Export metadata
            if hasattr(agent.memory, 'token_limit'):
                export['metadata']['token_limit'] = agent.memory.token_limit
        
        return export
    
    @staticmethod
    def import_memory(
        agent: ChatAgent,
        memory_export: Dict[str, Any]
    ) -> bool:
        """
        Import memory into agent.
        
        Args:
            agent: Target ChatAgent
            memory_export: Memory export dictionary
            
        Returns:
            Success status
        """
        try:
            if not hasattr(agent, 'memory') or not agent.memory:
                # Create memory if needed
                from . import create_memory
                agent.memory = create_memory()
            
            # Import records
            for record_data in memory_export.get('records', []):
                content = record_data.get('content', '')
                if content:
                    # Create message and add to memory
                    from . import create_user_message
                    message = create_user_message(content)
                    
                    if hasattr(agent.memory, 'add_message'):
                        agent.memory.add_message(message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to import memory: {e}")
            return False


# Utility functions

def ensure_camel_compatibility() -> bool:
    """
    Ensure CAMEL is properly installed and compatible.
    
    Returns:
        True if compatible
    """
    if not CAMEL_AVAILABLE:
        logger.error("CAMEL not available")
        return False
    
    # Check version
    try:
        import camel
        version = camel.__version__
        major, minor, patch = version.split('.')
        
        if int(major) == 0 and int(minor) == 2 and int(patch) >= 70:
            logger.info(f"CAMEL {version} is compatible")
            return True
        else:
            logger.error(f"CAMEL {version} is not compatible (need 0.2.70+)")
            return False
            
    except Exception as e:
        logger.error(f"Failed to check CAMEL version: {e}")
        return False


def create_async_agent(
    system_message: str,
    **kwargs
) -> AsyncAgentWrapper:
    """
    Create async-wrapped agent.
    
    Args:
        system_message: System message
        **kwargs: Additional agent parameters
        
    Returns:
        AsyncAgentWrapper instance
    """
    agent = create_agent(system_message=system_message, **kwargs)
    return AsyncAgentWrapper(agent)


# Exports
__all__ = [
    'AsyncAgentWrapper',
    'AgentResponse',
    'MessageConverter',
    'AgentFactory',
    'ModelMigration',
    'MemoryMigration',
    'ensure_camel_compatibility',
    'create_async_agent'
]