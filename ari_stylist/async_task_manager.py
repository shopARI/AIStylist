"""
FIXED Async Task Manager for AI Stylist

Replaces problematic AsyncCAMELService with proper async task management.
Resolves recursion issues and improves resource cleanup.
"""

import asyncio
import logging
import weakref
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
import time
import traceback

logger = logging.getLogger("async_task_manager")


class AsyncTaskManager:
    """
    FIXED task manager that properly handles async operations without recursion issues.
    Replaces the problematic AsyncCAMELService.
    """
    
    def __init__(self, max_concurrent_tasks=10):
        """Initialize with proper resource management."""
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks = {}
        self.task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.shutdown_event = asyncio.Event()
        
        # Task cleanup tracking
        self.task_registry = weakref.WeakSet()
        self.cleanup_interval = 60  # Clean up every minute
        self.last_cleanup = time.time()
        
        # Performance tracking
        self.task_stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "timeout_tasks": 0,
            "cleanup_count": 0
        }
        
        logger.info(f"AsyncTaskManager initialized with max {max_concurrent_tasks} concurrent tasks")
    
    def timeout_handler(timeout_seconds=30):
        """Decorator to add timeout protection to async functions."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout_seconds
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Function {func.__name__} timed out after {timeout_seconds}s")
                    raise
            return wrapper
        return decorator
    
    def recursion_safe(max_depth=50):
        """Decorator to prevent excessive recursion in async functions."""
        def decorator(func):
            call_depth = {}
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                task_id = id(asyncio.current_task())
                current_depth = call_depth.get(task_id, 0)
                
                if current_depth >= max_depth:
                    logger.error(f"Recursion limit reached in {func.__name__}")
                    raise RecursionError(f"Maximum recursion depth exceeded in {func.__name__}")
                
                call_depth[task_id] = current_depth + 1
                try:
                    return await func(*args, **kwargs)
                finally:
                    call_depth[task_id] = current_depth
                    if current_depth == 0:
                        # Clean up when back to root level
                        call_depth.pop(task_id, None)
            
            return wrapper
        return decorator
    
    async def execute_with_protection(
        self,
        coro,
        task_name: str,
        timeout: float = 30.0,
        retry_count: int = 1,
        callback: Optional[Callable] = None
    ) -> Any:
        """
        Execute a coroutine with full protection against common async issues.
        
        Args:
            coro: Coroutine to execute
            task_name: Name for logging and tracking
            timeout: Timeout in seconds
            retry_count: Number of retry attempts
            callback: Optional callback for result/error handling
            
        Returns:
            Result of the coroutine execution
        """
        async with self.task_semaphore:
            task_id = f"{task_name}_{int(time.time())}_{id(coro)}"
            
            self.task_stats["total_tasks"] += 1
            
            for attempt in range(retry_count):
                try:
                    # Create and track the task
                    task = asyncio.create_task(coro, name=task_id)
                    self.active_tasks[task_id] = task
                    self.task_registry.add(task)
                    
                    # Execute with timeout
                    try:
                        result = await asyncio.wait_for(task, timeout=timeout)
                        
                        # Success
                        self.task_stats["successful_tasks"] += 1
                        
                        if callback:
                            try:
                                await self._safe_callback(callback, result, None)
                            except Exception as e:
                                logger.error(f"Callback error for {task_name}: {e}")
                        
                        return result
                        
                    except asyncio.TimeoutError:
                        self.task_stats["timeout_tasks"] += 1
                        logger.warning(f"Task {task_name} timed out after {timeout}s (attempt {attempt + 1})")
                        
                        # Cancel the task
                        if not task.done():
                            task.cancel()
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                        
                        if attempt == retry_count - 1:
                            error = TimeoutError(f"Task {task_name} timed out after {retry_count} attempts")
                            if callback:
                                await self._safe_callback(callback, None, error)
                            raise error
                    
                except asyncio.CancelledError:
                    logger.info(f"Task {task_name} was cancelled")
                    raise
                    
                except Exception as e:
                    self.task_stats["failed_tasks"] += 1
                    logger.error(f"Task {task_name} failed on attempt {attempt + 1}: {e}")
                    
                    if attempt == retry_count - 1:
                        if callback:
                            await self._safe_callback(callback, None, e)
                        raise
                    
                    # Wait before retry
                    if attempt < retry_count - 1:
                        await asyncio.sleep(min(2 ** attempt, 5))  # Exponential backoff, max 5s
                
                finally:
                    # Cleanup
                    self.active_tasks.pop(task_id, None)
                    
                    # Periodic cleanup
                    current_time = time.time()
                    if current_time - self.last_cleanup > self.cleanup_interval:
                        asyncio.create_task(self._cleanup_tasks())
                        self.last_cleanup = current_time
    
    async def _safe_callback(self, callback, result, error):
        """Safely execute callback without blocking main execution."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await asyncio.wait_for(callback(result, error), timeout=5.0)
            else:
                callback(result, error)
        except Exception as e:
            logger.error(f"Callback execution failed: {e}")
    
    async def _cleanup_tasks(self):
        """Clean up completed and cancelled tasks."""
        try:
            cleanup_count = 0
            
            # Clean up active tasks
            completed_tasks = [
                task_id for task_id, task in self.active_tasks.items()
                if task.done()
            ]
            
            for task_id in completed_tasks:
                self.active_tasks.pop(task_id, None)
                cleanup_count += 1
            
            self.task_stats["cleanup_count"] += cleanup_count
            
            if cleanup_count > 0:
                logger.debug(f"Cleaned up {cleanup_count} completed tasks")
                
        except Exception as e:
            logger.error(f"Error in task cleanup: {e}")
    
    async def process_message_safe(
        self,
        agent,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> str:
        """
        Process a message with an agent safely.
        
        Args:
            agent: CAMEL agent instance
            message: Message to process
            context: Optional context
            timeout: Timeout in seconds
            
        Returns:
            Processed response
        """
        @self.recursion_safe(max_depth=10)
        @self.timeout_handler(timeout)
        async def _process():
            if not agent:
                raise ValueError("Agent is required for message processing")
            
            # Build prompt with context if provided
            full_message = self._build_prompt_safe(message, context) if context else message
            
            # Execute agent step in thread pool to avoid blocking
            try:
                # For CAMEL agents, we need to handle this carefully
                if hasattr(agent, 'step'):
                    # Run agent step in thread pool to prevent blocking
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        agent.step,
                        full_message
                    )
                    
                    # Extract response content
                    if hasattr(result, 'msg') and hasattr(result.msg, 'content'):
                        return result.msg.content
                    elif hasattr(result, 'content'):
                        return result.content
                    else:
                        return str(result)
                else:
                    raise AttributeError("Agent does not have step method")
                    
            except Exception as e:
                logger.error(f"Agent step failed: {e}")
                raise
        
        return await self.execute_with_protection(
            _process(),
            task_name="process_message",
            timeout=timeout
        )
    
    def _build_prompt_safe(self, message: str, context: Dict[str, Any]) -> str:
        """Build a prompt safely without causing memory issues."""
        try:
            prompt_parts = []
            
            # Add conversation history (limited)
            if "conversation_history" in context and context["conversation_history"]:
                history = context["conversation_history"][-5:]  # Limit to last 5 messages
                prompt_parts.append("Recent conversation:")
                
                for msg in history:
                    role = "User" if msg.get("role") == "user" else "Assistant"
                    content = msg.get("content", "")[:200]  # Limit content length
                    prompt_parts.append(f"{role}: {content}")
                
                prompt_parts.append("")
            
            # Add user preferences (limited)
            if "user_preferences" in context and context["user_preferences"]:
                prefs = context["user_preferences"]
                prompt_parts.append("User preferences:")
                
                for key, value in list(prefs.items())[:5]:  # Limit to 5 preferences
                    prompt_parts.append(f"- {key}: {str(value)[:100]}")  # Limit value length
                
                prompt_parts.append("")
            
            # Add product context (limited)
            if "products" in context and context["products"]:
                products = context["products"][:3]  # Limit to 3 products
                prompt_parts.append("Current products:")
                
                for i, product in enumerate(products, 1):
                    title = product.get('title', 'Product')[:50]  # Limit title length
                    price = product.get('price', 0)
                    prompt_parts.append(f"{i}. {title} - ${price}")
                
                prompt_parts.append("")
            
            # Add current message
            prompt_parts.append(f"Current message: {message}")
            
            # Join with single newlines to save space
            return "\n".join(prompt_parts)
            
        except Exception as e:
            logger.error(f"Error building prompt: {e}")
            return message  # Fallback to original message
    
    async def create_agent_safe(
        self,
        agent_factory,
        system_message: str,
        memory=None,
        model_type=None,
        timeout: float = 30.0
    ):
        """Create an agent safely with timeout protection."""
        @self.recursion_safe(max_depth=5)
        @self.timeout_handler(timeout)
        async def _create():
            if not agent_factory:
                raise ValueError("Agent factory is required")
            
            try:
                agent = await agent_factory.create_stylist_agent(
                    memory=memory,
                    model_type=model_type,
                    enable_mcp=True
                )
                
                if not agent:
                    raise RuntimeError("Agent creation returned None")
                
                return agent
                
            except Exception as e:
                logger.error(f"Agent creation failed: {e}")
                raise
        
        return await self.execute_with_protection(
            _create(),
            task_name="create_agent",
            timeout=timeout
        )
    
    async def setup_memory_safe(
        self,
        memory_manager,
        user_id: Optional[str] = None,
        timeout: float = 30.0
    ):
        """Set up memory safely with timeout protection."""
        @self.recursion_safe(max_depth=3)
        @self.timeout_handler(timeout)
        async def _setup():
            if not memory_manager:
                raise ValueError("Memory manager is required")
            
            try:
                memory = await memory_manager.create_memory(
                    user_id=user_id,
                    enable_mcp=True
                )
                
                if not memory:
                    raise RuntimeError("Memory creation returned None")
                
                return memory
                
            except Exception as e:
                logger.error(f"Memory setup failed: {e}")
                raise
        
        return await self.execute_with_protection(
            _setup(),
            task_name="setup_memory",
            timeout=timeout
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get task manager statistics."""
        return {
            "active_tasks": len(self.active_tasks),
            "max_concurrent": self.max_concurrent_tasks,
            "stats": self.task_stats.copy(),
            "shutdown_requested": self.shutdown_event.is_set()
        }
    
    async def shutdown(self, timeout: float = 30.0):
        """Gracefully shutdown the task manager."""
        logger.info("Shutting down AsyncTaskManager...")
        
        # Set shutdown flag
        self.shutdown_event.set()
        
        # Cancel all active tasks
        if self.active_tasks:
            logger.info(f"Cancelling {len(self.active_tasks)} active tasks...")
            
            for task_id, task in self.active_tasks.items():
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.active_tasks.values(), return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Some tasks did not complete within shutdown timeout")
            
            # Force cleanup
            self.active_tasks.clear()
        
        logger.info("AsyncTaskManager shutdown complete")


# Singleton instance
_task_manager = None


def get_task_manager() -> AsyncTaskManager:
    """Get or create the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = AsyncTaskManager()
    return _task_manager


async def cleanup_task_manager():
    """Clean up the global task manager."""
    global _task_manager
    if _task_manager:
        await _task_manager.shutdown()
        _task_manager = None


# Convenience functions for backward compatibility
async def process_message_with_protection(agent, message: str, context: Optional[Dict[str, Any]] = None):
    """Process message with full async protection."""
    manager = get_task_manager()
    return await manager.process_message_safe(agent, message, context)


async def create_agent_with_protection(agent_factory, system_message: str, memory=None, model_type=None):
    """Create agent with full async protection."""
    manager = get_task_manager()
    return await manager.create_agent_safe(agent_factory, system_message, memory, model_type)


async def setup_memory_with_protection(memory_manager, user_id: Optional[str] = None):
    """Set up memory with full async protection."""
    manager = get_task_manager()
    return await manager.setup_memory_safe(memory_manager, user_id)


logger.info("✅ Fixed Async Task Manager loaded successfully")
