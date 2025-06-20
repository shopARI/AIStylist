import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, List

from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelType, ModelPlatformType

logger = logging.getLogger("async_camel_service")

class AsyncCAMELService:
    """
    Asynchronous service wrapper for CAMEL-AI operations.
    Isolates synchronous CAMEL operations in a dedicated thread pool.
    """
    
    def __init__(self, max_workers=10):
        """Initialize with configurable thread pool"""
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="camel_worker"
        )
        self.agent_pool = {}
        self.agent_pool_lock = asyncio.Lock()
        self.memory_pool = {}
        self.memory_pool_lock = asyncio.Lock()
        
    async def get_or_create_agent(self, session_id: str, system_message: str, 
                             model_type: ModelType = None, memory=None):
        """Get an existing agent or create a new one asynchronously"""
        async with self.agent_pool_lock:
            if session_id in self.agent_pool:
                logger.info(f"Returning existing agent for session {session_id}")
                return self.agent_pool[session_id]
                
            # Ensure memory is not a coroutine by awaiting it if needed
            if memory is not None and asyncio.iscoroutine(memory):
                logger.info("Memory is a coroutine, awaiting it before creating agent")
                memory = await memory
                
            # Create in thread pool to avoid blocking
            logger.info(f"Creating new agent for session {session_id}")
            agent = await asyncio.to_thread(
                self._create_agent, 
                system_message, 
                model_type,
                memory
            )
            
            if not agent:
                logger.error(f"Failed to create agent for session {session_id}")
                raise RuntimeError("Agent creation failed")
                
            self.agent_pool[session_id] = agent
            logger.info(f"Successfully created agent for session {session_id}")
            return agent
    
    def _create_agent(self, system_message: str, model_type: ModelType, memory=None):
        """Synchronous agent creation (runs in thread pool)"""
        try:
            # Use either specified model type or default to GPT-4
            model_type = model_type or ModelType.GPT_4
            
            # Create model
            model = ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI,
                model_type=model_type,
                model_config_dict={
                    "temperature": 0.7,
                    "max_tokens": 4000,
                }
            )
            
            # Create agent
            agent = ChatAgent(
                system_message=system_message,
                model=model
            )
            
            # Attach memory if provided
            if memory:
                agent.memory = memory
                
            return agent
            
        except Exception as e:
            logger.error(f"Error creating agent: {e}", exc_info=True)
            # Fall back to a simpler model in case of failure
            try:
                logger.info("Attempting to create fallback agent with GPT-3.5")
                fallback_model = ModelFactory.create(
                    model_platform=ModelPlatformType.OPENAI,
                    model_type=ModelType.GPT_3_5_TURBO,
                    model_config_dict={"temperature": 0.7}
                )
                fallback_agent = ChatAgent(
                    system_message=system_message,
                    model=fallback_model
                )
                # Attach memory if available
                if memory:
                    fallback_agent.memory = memory
                return fallback_agent
            except Exception as e2:
                logger.error(f"Fallback agent creation failed: {e2}", exc_info=True)
                raise RuntimeError("Unable to create any agent")
    
    async def process_message(self, agent, message: str, context: Optional[Dict[str, Any]] = None):
        """Process a message with the agent asynchronously"""
        if not agent:
            logger.error("Cannot process message: agent is None")
            raise ValueError("Agent is required for message processing")
            
        try:
            # Log the processing attempt with context details
            logger.info(f"Processing message with context: {bool(context)}")
            if context:
                logger.debug(f"Context keys: {context.keys()}")
                if 'conversation_history' in context:
                    logger.debug(f"History length: {len(context['conversation_history'])}")
            
            # Prepare full prompt with context if provided
            full_message = self._build_prompt(message, context) if context else message
            logger.debug(f"Full message length: {len(full_message)}")
            
            # Run the agent step in the thread pool
            logger.debug("Sending message to agent in thread pool")
            result = await asyncio.to_thread(self._agent_step, agent, full_message)
            
            logger.info("Successfully processed message with agent")
            return result
        except Exception as e:
            logger.error(f"Error processing message with agent: {e}", exc_info=True)
            raise RuntimeError(f"Failed to process message: {str(e)}")
    
    def _agent_step(self, agent, message):
        """Run the agent step synchronously (in thread pool)"""
        try:
            return agent.step(message)
        except Exception as e:
            logger.error(f"Error in agent step: {e}", exc_info=True)
            raise
    
    def _build_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """Build a comprehensive prompt including all necessary context"""
        prompt_parts = []
        
        # Add conversation history if available
        if "conversation_history" in context and context["conversation_history"]:
            history = context["conversation_history"]
            prompt_parts.append("Previous conversation:")
            
            for msg in history:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            
            prompt_parts.append("")  # Empty line after history
        
        # Add user preferences if available
        if "user_preferences" in context and context["user_preferences"]:
            prefs = context["user_preferences"]
            prompt_parts.append("User preferences:")
            
            for key, value in prefs.items():
                prompt_parts.append(f"- {key}: {value}")
            
            prompt_parts.append("")  # Empty line after preferences
        
        # Add product context if available
        if "products" in context and context["products"]:
            products = context["products"]
            prompt_parts.append("Current products being discussed:")
            
            for i, product in enumerate(products, 1):
                prompt_parts.append(f"{i}. {product.get('title')} - ${product.get('price')}")
            
            prompt_parts.append("")  # Empty line after products
        
        # Add the current message
        prompt_parts.append(f"Current message: {message}")
        
        # Join all parts with double newlines for clear separation
        prompt = "\n\n".join(prompt_parts)
        logger.debug(f"Built prompt with {len(prompt_parts)} sections")
        
        return prompt
    
    async def setup_memory(self, memory_setup_func, user_id=None, neo4j_client=None):
        """Set up memory asynchronously"""
        logger.info(f"Setting up memory for user: {user_id}")
        
        if user_id:
            async with self.memory_pool_lock:
                if user_id in self.memory_pool:
                    logger.info(f"Returning existing memory for user {user_id}")
                    return self.memory_pool[user_id]
        
        # Run memory setup in thread pool
        try:
            logger.debug(f"Calling memory_setup_func for user {user_id}")
            memory = await memory_setup_func(user_id=user_id, neo4j_client=neo4j_client)
            
            if not memory:
                logger.error(f"Memory setup returned None for user {user_id}")
                raise ValueError("Memory setup failed")
            
            if user_id:
                async with self.memory_pool_lock:
                    self.memory_pool[user_id] = memory
                    
            logger.info(f"Successfully set up memory for user {user_id}")
            return memory
        except Exception as e:
            logger.error(f"Error setting up memory: {e}", exc_info=True)
            raise RuntimeError(f"Memory setup failed: {str(e)}")
    
    async def add_to_memory(self, memory, content, sender, metadata=None):
        """Add a message to memory asynchronously"""
        if not memory:
            logger.warning("Cannot add to memory: memory is None")
            return False
            
        try:
            # Import here to avoid circular imports
            #from memory_integration_async import add_message_to_memory_async
            from memory_integration_v2 import add_message_to_memory_async
            
            logger.debug(f"Adding {sender} message to memory")
            result = await add_message_to_memory_async(
                memory=memory,
                content=content,
                sender=sender,
                metadata=metadata
            )
            
            logger.debug(f"Added message to memory: {result}")
            return result
        except Exception as e:
            logger.error(f"Error adding to memory: {e}", exc_info=True)
            return False
    
    async def close(self):
        """Clean up resources"""
        logger.info("Closing AsyncCAMELService resources")
        self.executor.shutdown(wait=False)
        logger.info("AsyncCAMELService resources closed")
