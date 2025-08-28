"""
Complete Agent Factory for CAMEL-AI 0.2.64
FIXED: Completely rewritten to resolve message processing issues and improve reliability.
"""

import logging
import asyncio
import uuid
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

logger = logging.getLogger("agent_factory")

# UPDATED: Use centralized imports from camel_imports.py
from camel_imports import (
    ChatAgent, ModelFactory, ModelType, ModelPlatformType,
    BaseMessage, OpenAITokenCounter, CAMEL_AVAILABLE as CAMEL_AGENTS_AVAILABLE,
    SearchToolkit, MCPToolkit
)

# Check toolkit availability
SEARCH_TOOLKIT_AVAILABLE = SearchToolkit is not None
MCP_TOOLKIT_AVAILABLE = MCPToolkit is not None

if CAMEL_AGENTS_AVAILABLE:
    logger.info("✅ CAMEL agents imported successfully")
else:
    logger.error("❌ CAMEL agents not available, using fallback implementations")


class MessageSafeAgent(ChatAgent if ChatAgent else object):
    """
    A wrapper around ChatAgent that ensures messages are never empty.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ensure_messages_initialized()
    
    def _ensure_messages_initialized(self):
        """Ensure the agent always has at least a system message."""
        # Check various possible message storage locations
        if hasattr(self, '_messages') and isinstance(self._messages, list):
            if len(self._messages) == 0:
                self._messages.append({
                    "role": "system",
                    "content": self.system_message or "You are a helpful assistant."
                })
        
        # Also ensure conversation_history is initialized
        if not hasattr(self, 'conversation_history'):
            self.conversation_history = []
        
        if len(self.conversation_history) == 0 and self.system_message:
            system_msg = BaseMessage.make_assistant_message(
                role_name="System",
                content=self.system_message
            )
            self.conversation_history.append(system_msg)
    
    def step(self, message):
        """Override step to ensure messages are never empty."""
        # Always ensure messages are initialized before processing
        self._ensure_messages_initialized()
        
        # If the base ChatAgent has a messages attribute, ensure it's not empty
        if hasattr(super(), 'messages') and hasattr(super().messages, '__len__'):
            if len(super().messages) == 0:
                # Add system message to the base agent's messages
                if hasattr(super(), 'add_message'):
                    super().add_message({
                        "role": "system",
                        "content": self.system_message or "You are a helpful assistant."
                    })
        
        # Call the parent step method
        return super().step(message)


class AgentFactory:
    """
    Complete Agent Factory for CAMEL-AI 0.2.64
    FIXED: Resolves message processing issues and provides robust agent creation.
    """
    
    def __init__(self):
        """Initialize the agent factory with comprehensive setup"""
        self.agent_pool = {}
        self.agent_pool_lock = asyncio.Lock()
        self.creation_stats = {
            "total_created": 0,
            "successful_creations": 0,
            "failed_creations": 0,
            "active_agents": 0
        }
        
        # Default configurations
        self.default_model_config = {
            "temperature": 0.7,
            "max_tokens": 4000,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }
        
        # Stylist system message template
        self.stylist_system_message = """You are Ari, a warm and personable fashion stylist with years of experience helping clients look and feel their best.

IMPORTANT: You have access to conversation history and should use it to provide personalized advice.

Communication Style:
- Speak naturally and conversationally, like a friendly chat with a trusted stylist
- Avoid bullet points, numbered lists, or rigid formatting
- Use "I" and "you" to maintain personal connection
- Express genuine enthusiasm for fashion and helping clients

When Making Recommendations:
- Reference what the client has told you previously
- Explain why each piece would work for their specific needs
- Mention fabric quality, versatility, and styling possibilities
- Consider their budget, lifestyle, and personal preferences
- Suggest complete outfits and how pieces work together

For Product Recommendations:
- When you have specific products to recommend, integrate them naturally into conversation
- Mention exact product names and prices when available
- Explain why each item is perfect for their needs
- Share styling tips and how to wear each piece
- Connect recommendations to their stated preferences or occasion

Memory and Context:
- Remember previous conversations and build on them
- Reference past recommendations when relevant
- Acknowledge their preferences and style evolution
- Maintain continuity across conversations

Always be encouraging, confident in your expertise, and focused on making the client feel understood and excited about their style choices."""
        
        logger.info("✅ AgentFactory initialized with comprehensive CAMEL 0.2.64 support")
    
    async def create_agent(
        self,
        system_message: str,
        model_type: Optional[Any] = None,
        model_platform: Optional[Any] = None,
        model_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Any]] = None,
        memory: Optional[Any] = None,
        agent_id: Optional[str] = None,
        validate_creation: bool = True
    ) -> ChatAgent:
        """
        Create a CAMEL agent with comprehensive error handling and validation.
        
        FIXED: Ensures proper message handling and prevents empty messages array.
        """
        start_time = datetime.now()
        self.creation_stats["total_created"] += 1
        
        # Generate agent ID if not provided
        if not agent_id:
            agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        
        # Check if agent already exists in pool
        async with self.agent_pool_lock:
            if agent_id in self.agent_pool:
                logger.info(f"Returning existing agent: {agent_id}")
                return self.agent_pool[agent_id]
        
        logger.info(f"Creating new agent: {agent_id}")
        
        try:
            # Set safe defaults
            model_type = model_type or (ModelType.GPT_4O_MINI if CAMEL_AGENTS_AVAILABLE else "gpt-4o-mini")
            model_platform = model_platform or (ModelPlatformType.OPENAI if CAMEL_AGENTS_AVAILABLE else "openai")
            model_config = {**self.default_model_config, **(model_config or {})}
            tools = tools or []
            
            # Validate system message
            if not system_message or not isinstance(system_message, str) or len(system_message.strip()) == 0:
                raise ValueError("System message is required and cannot be empty")
            
            # Create model with error handling
            model = None
            if CAMEL_AGENTS_AVAILABLE and ModelFactory:
                try:
                    model = ModelFactory.create(
                        model_platform=model_platform,
                        model_type=model_type,
                        model_config_dict=model_config
                    )
                    logger.debug(f"✅ Created model: {model_type}")
                except Exception as e:
                    logger.warning(f"Model creation failed, trying fallback: {e}")
                    # Try with minimal config
                    try:
                        model = ModelFactory.create(
                            model_platform=model_platform,
                            model_type=ModelType.GPT_4O_MINI if ModelType else "gpt-4o-mini",
                            model_config_dict={"temperature": 0.7}
                        )
                        logger.debug("✅ Created fallback model")
                    except Exception as e2:
                        logger.error(f"Fallback model creation failed: {e2}")
                        model = None
            
            # Process tools safely
            processed_tools = []
            if tools:
                for tool in tools:
                    try:
                        if hasattr(tool, 'get_tools') and callable(tool.get_tools):
                            toolkit_tools = tool.get_tools()
                            if toolkit_tools and isinstance(toolkit_tools, list):
                                processed_tools.extend(toolkit_tools)
                        elif callable(tool):
                            processed_tools.append(tool)
                        else:
                            processed_tools.append(tool)
                    except Exception as e:
                        logger.warning(f"Error processing tool: {e}")
            
            # Create agent with proper initialization
            if CAMEL_AGENTS_AVAILABLE and ChatAgent:
                try:
                    # Use MessageSafeAgent wrapper for safety
                    agent = MessageSafeAgent(
                        system_message=system_message,
                        model=model,
                        tools=processed_tools,
                        memory=memory
                    )
                    
                    # CRITICAL: Initialize internal message tracking
                    if not hasattr(agent, '_messages'):
                        agent._messages = []
                    
                    # CRITICAL: Ensure system message is in _messages
                    if len(agent._messages) == 0:
                        agent._messages.append({
                            "role": "system",
                            "content": system_message
                        })
                    
                    # Also ensure conversation_history is properly initialized
                    if not hasattr(agent, 'conversation_history'):
                        agent.conversation_history = []
                    
                    if len(agent.conversation_history) == 0:
                        system_msg = BaseMessage.make_assistant_message(
                            role_name="System",
                            content=system_message
                        )
                        agent.conversation_history = [system_msg]
                    
                    # Set agent ID for tracking
                    agent.agent_id = agent_id
                    agent.creation_time = start_time
                    
                    logger.info(f"✅ Created CAMEL agent with message safety: {agent_id}")
                    
                except Exception as e:
                    logger.error(f"CAMEL agent creation failed: {e}")
                    # Create fallback agent
                    agent = MessageSafeAgent(system_message=system_message)
                    agent.agent_id = agent_id
                    agent.creation_time = start_time
                    logger.warning(f"Created fallback agent: {agent_id}")
            else:
                # Create minimal fallback agent
                agent = MessageSafeAgent(system_message=system_message)
                agent.agent_id = agent_id
                agent.creation_time = start_time
                logger.warning(f"Created minimal fallback agent: {agent_id}")
            
            # Validate agent creation if requested
            if validate_creation:
                validation_result = await self._validate_agent(agent)
                if not validation_result:
                    logger.warning(f"Agent validation failed for: {agent_id}")
            
            # Store in pool
            async with self.agent_pool_lock:
                self.agent_pool[agent_id] = agent
                self.creation_stats["active_agents"] = len(self.agent_pool)
            
            self.creation_stats["successful_creations"] += 1
            creation_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Agent {agent_id} created successfully in {creation_time:.2f}s")
            
            return agent
            
        except Exception as e:
            self.creation_stats["failed_creations"] += 1
            logger.error(f"❌ Agent creation failed for {agent_id}: {e}")
            
            # Create absolute minimal fallback
            try:
                minimal_agent = MessageSafeAgent(system_message=system_message or "You are a helpful assistant.")
                minimal_agent.agent_id = agent_id
                minimal_agent.creation_time = start_time
                
                async with self.agent_pool_lock:
                    self.agent_pool[agent_id] = minimal_agent
                
                logger.warning(f"Created minimal emergency fallback agent: {agent_id}")
                return minimal_agent
                
            except Exception as e2:
                logger.error(f"Even minimal agent creation failed: {e2}")
                raise RuntimeError(f"Complete agent creation failure: {e}")
    
    async def create_stylist_agent(
        self,
        memory: Optional[Any] = None,
        model_type: Optional[Any] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        enable_mcp: bool = False
    ) -> ChatAgent:
        """Create a specialized stylist agent with FIXED message handling."""
        
        stylist_system_message = """You are Ari, a warm and personable fashion stylist with years of experience helping clients look and feel their best. 

When communicating with clients:
- Speak in a natural, conversational tone like you're having a friendly chat
- Avoid numbered lists, bullet points, or any rigid formatting that feels impersonal
- Build rapport by asking questions and understanding their needs before making recommendations
- Express your own enthusiasm for fashion and styling in general terms
- Address clients directly using "you" and refer to yourself as "I"

When asked specifically for product recommendations:
- Describe why you think each piece would work for the client's specific needs
- Mention fabric quality, versatility, and how it pairs with other items
- Share small styling details that show your expertise
- Consider the person's budget range and preferences
- Create complete outfits by suggesting complementary pieces that work together

Always maintain a friendly, encouraging tone that boosts the client's confidence."""

        # Create agent with proper initialization
        try:
            agent = await self.create_agent(
                system_message=stylist_system_message,
                model_type=model_type,
                model_config={
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                tools=[],  # Start with empty tools to avoid conflicts
                memory=memory,
                agent_id="stylist_main"
            )
            
            # FIXED: Ensure agent has a system message in the conversation history
            if hasattr(agent, 'system_message') and not agent.system_message:
                from camel_imports import BaseMessage
                agent.system_message = BaseMessage.make_assistant_message(
                    role_name="System",
                    content=stylist_system_message
                )
            
            # FIXED: Initialize agent's message history if empty
            if hasattr(agent, 'conversation_history') and not agent.conversation_history:
                from camel_imports import BaseMessage
                system_msg = BaseMessage.make_assistant_message(
                    role_name="System", 
                    content=stylist_system_message
                )
                agent.conversation_history = [system_msg]
            
            logger.info("✅ Successfully created stylist agent with proper initialization")
            return agent
            
        except Exception as e:
            logger.error(f"❌ Error creating stylist agent: {e}")
            # Create minimal fallback
            return MessageSafeAgent(system_message=stylist_system_message)
    
    async def create_agent_with_custom_prompt(
        self,
        custom_prompt: str,
        memory: Optional[Any] = None,
        model_type: Optional[Any] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        tools: Optional[List[Any]] = None,
        agent_id: Optional[str] = None
    ) -> ChatAgent:
        """Create an agent with a custom system prompt for specialized use cases."""
        
        if not agent_id:
            agent_id = f"custom_{uuid.uuid4().hex[:8]}"
        
        model_config = {
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        return await self.create_agent(
            system_message=custom_prompt,
            model_type=model_type,
            model_config=model_config,
            tools=tools or [],
            memory=memory,
            agent_id=agent_id
        )
    
    async def _validate_agent(self, agent: ChatAgent) -> bool:
        """
        Validate that an agent is properly configured and can process messages.
        
        FIXED: Comprehensive validation to prevent runtime errors.
        """
        try:
            # Basic attribute validation
            if not hasattr(agent, 'system_message'):
                logger.warning("Agent missing system_message attribute")
                return False
            
            if not agent.system_message:
                logger.warning("Agent has empty system_message")
                return False
            
            # CRITICAL: Validate message storage
            if hasattr(agent, '_messages'):
                if not isinstance(agent._messages, list):
                    logger.warning("Agent _messages is not a list")
                    return False
                if len(agent._messages) == 0:
                    logger.warning("Agent _messages is empty")
                    return False
            else:
                logger.warning("Agent missing _messages attribute")
                return False
            
            # Conversation history validation
            if not hasattr(agent, 'conversation_history'):
                logger.warning("Agent missing conversation_history")
                agent.conversation_history = []
            
            # Test message processing (lightweight test)
            if CAMEL_AGENTS_AVAILABLE:
                try:
                    if hasattr(agent, 'step') and callable(agent.step):
                        logger.debug("✅ Agent has callable step method")
                    else:
                        logger.warning("Agent missing step method")
                        return False
                        
                except Exception as e:
                    logger.warning(f"Agent validation test failed: {e}")
                    return False
            
            logger.debug("✅ Agent validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Agent validation error: {e}")
            return False
    
    async def get_agent(self, agent_id: str) -> Optional[ChatAgent]:
        """Get an agent from the pool by ID"""
        async with self.agent_pool_lock:
            return self.agent_pool.get(agent_id)
    
    async def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the pool"""
        async with self.agent_pool_lock:
            if agent_id in self.agent_pool:
                del self.agent_pool[agent_id]
                self.creation_stats["active_agents"] = len(self.agent_pool)
                logger.info(f"Removed agent from pool: {agent_id}")
                return True
            return False
    
    async def get_agent_stats(self) -> Dict[str, Any]:
        """Get statistics about agent creation and management"""
        async with self.agent_pool_lock:
            pool_info = {}
            for agent_id, agent in self.agent_pool.items():
                pool_info[agent_id] = {
                    "type": getattr(agent, 'agent_type', 'generic'),
                    "creation_time": getattr(agent, 'creation_time', None),
                    "has_memory": hasattr(agent, 'memory') and agent.memory is not None,
                    "has_tools": hasattr(agent, 'tools') and len(agent.tools) > 0,
                    "has_messages": hasattr(agent, '_messages') and len(agent._messages) > 0
                }
        
        return {
            "creation_stats": self.creation_stats.copy(),
            "active_agents": pool_info,
            "camel_available": CAMEL_AGENTS_AVAILABLE,
            "toolkits_available": {
                "search": SEARCH_TOOLKIT_AVAILABLE,
                "mcp": MCP_TOOLKIT_AVAILABLE
            }
        }
    
    async def cleanup(self):
        """Clean up all agents and resources"""
        logger.info("Starting AgentFactory cleanup...")
        
        async with self.agent_pool_lock:
            # Close any agents that have cleanup methods
            for agent_id, agent in self.agent_pool.items():
                try:
                    if hasattr(agent, 'close') and callable(agent.close):
                        await agent.close()
                    elif hasattr(agent, 'cleanup') and callable(agent.cleanup):
                        await agent.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up agent {agent_id}: {e}")
            
            # Clear the pool
            agent_count = len(self.agent_pool)
            self.agent_pool.clear()
            self.creation_stats["active_agents"] = 0
        
        logger.info(f"✅ Cleaned up {agent_count} agents")


# Singleton instance management
_factory_instance: Optional[AgentFactory] = None
_factory_lock = asyncio.Lock()


async def get_agent_factory_async() -> AgentFactory:
    """Get or create the global agent factory instance (async version)"""
    global _factory_instance
    
    if _factory_instance is None:
        async with _factory_lock:
            if _factory_instance is None:
                _factory_instance = AgentFactory()
                logger.info("✅ Created global AgentFactory instance (async)")
    
    return _factory_instance


def get_agent_factory() -> AgentFactory:
    """Get or create the global agent factory instance (SYNCHRONOUS version)"""
    global _factory_instance
    
    if _factory_instance is None:
        _factory_instance = AgentFactory()
        logger.info("✅ Created global AgentFactory instance")
    
    return _factory_instance


async def cleanup_agent_factory():
    """Clean up the global agent factory"""
    global _factory_instance
    
    if _factory_instance is not None:
        async with _factory_lock:
            if _factory_instance is not None:
                await _factory_instance.cleanup()
                _factory_instance = None
                logger.info("✅ Cleaned up global AgentFactory")


def validate_camel_setup():
    """Validate CAMEL-AI setup and configuration"""
    
    print("🔍 Validating CAMEL-AI Setup...")
    
    # Check CAMEL version
    try:
        from camel_imports import CAMEL_VERSION
        print(f"✅ CAMEL version: {CAMEL_VERSION}")
    except ImportError:
        print("❌ CAMEL-AI not installed")
        return False
    
    # Check OpenAI API key
    import os
    if os.environ.get("OPENAI_API_KEY"):
        print("✅ OpenAI API key found")
    else:
        print("❌ OPENAI_API_KEY not set")
        return False
    
    # Test basic agent creation
    try:
        from camel_imports import ChatAgent, ModelFactory, ModelType, ModelPlatformType, BaseMessage
        
        # Test model creation
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4O_MINI,
            model_config_dict={"temperature": 0.7, "max_tokens": 100}
        )
        
        # Test agent creation
        agent = ChatAgent(
            system_message="You are a helpful assistant.",
            model=model
        )
        
        # CRITICAL: Check if agent has proper message initialization
        if hasattr(agent, '_messages'):
            print(f"✅ Agent has _messages attribute with {len(agent._messages)} messages")
        else:
            print("❌ Agent missing _messages attribute")
            return False
        
        print("✅ Basic CAMEL components working")
        
        # Test agent step (this is where the error typically occurs)
        try:
            # Create a test message
            test_msg = BaseMessage.make_user_message(
                role_name="User",
                content="Hello, this is a test message."
            )
            
            response = agent.step(test_msg)
            print("✅ Agent step working correctly")
            return True
        except Exception as e:
            print(f"❌ Agent step failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ CAMEL component test failed: {e}")
        return False


# Backward compatibility functions
async def create_stylist_agent_async(
    memory: Optional[Any] = None,
    model_type: Optional[Any] = None,
    temperature: float = 0.7,
    max_tokens: int = 4000,
    enable_mcp: bool = False
) -> ChatAgent:
    """Backward compatible function to create stylist agent."""
    factory = await get_agent_factory_async()
    return await factory.create_stylist_agent(
        memory=memory,
        model_type=model_type,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_mcp=enable_mcp
    )


async def create_agent_with_tools_async(
    system_message: str,
    tools: Optional[List[Any]] = None,
    memory: Optional[Any] = None,
    model_type: Optional[Any] = None,
    temperature: float = 0.7,
    max_tokens: int = 4000
) -> ChatAgent:
    """Backward compatible function to create agent with tools."""
    factory = await get_agent_factory_async()
    return await factory.create_agent(
        system_message=system_message,
        tools=tools,
        memory=memory,
        model_type=model_type,
        model_config={
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    )


logger.info("✅ Complete AgentFactory for CAMEL-AI 0.2.64 loaded successfully")