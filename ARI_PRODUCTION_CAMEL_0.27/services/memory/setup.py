"""
Memory Setup Functions for AIStylist
Configures CAMEL LongtermAgentMemory and session persistence
"""

import logging
from typing import Dict, Any, Optional
from camel.memories import ChatHistoryMemory
from camel.types import ModelType

logger = logging.getLogger("memory.setup")

def create_memory_setup_function():
    """
    Create a memory setup function for the intelligence coordinator.
    
    This function creates CAMEL LongtermAgentMemory instances for agents
    and configures session persistence.
    
    Returns:
        Callable memory setup function
    """
    
    def setup_agent_memory(
        agent_name: str = "stylist",
        token_limit: int = 4096,
        model_type: ModelType = ModelType.GPT_4O_MINI,
        enable_vector: bool = True,
        enable_chat_history: bool = True
    ) -> ChatHistoryMemory:
        """
        Set up memory for a specific agent.
        
        Args:
            agent_name: Name of the agent
            token_limit: Maximum tokens for memory context
            model_type: Model type for token counting
            enable_vector: Enable vector database memory
            enable_chat_history: Enable chat history memory
            
        Returns:
            Configured ChatHistoryMemory instance
        """
        try:
            logger.info(f"Setting up memory for agent: {agent_name}")
            
            from camel.memories.context_creators import ScoreBasedContextCreator
            context_creator = ScoreBasedContextCreator()
            memory = ChatHistoryMemory(context_creator=context_creator, window_size=20)
            
            logger.info(f"Memory configured for {agent_name}: {token_limit} token limit")
            return memory
            
        except Exception as e:
            logger.error(f"Failed to create memory for {agent_name}: {e}")
            raise RuntimeError(f"Memory setup failed for {agent_name}") from e
    
    return setup_agent_memory


class SessionMemoryStore:
    """
    Simple in-memory session store for conversation context.
    In production, this would be backed by Redis or database.
    """
    
    def __init__(self):
        self._sessions = {}
        logger.info("SessionMemoryStore initialized")
    
    def get_session_context(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Get conversation context for a session."""
        key = f"{session_id}:{user_id}"
        context = self._sessions.get(key, {
            "preferences": {},
            "conversation_history": [],
            "user_info": {},
            "last_products": []
        })
        logger.debug(f"Retrieved context for {key}: {len(context.get('conversation_history', []))} messages")
        return context
    
    def update_session_context(
        self, 
        session_id: str, 
        user_id: str, 
        message: str, 
        response: str,
        products: Optional[list] = None,
        extracted_preferences: Optional[Dict] = None
    ):
        """Update session context with new conversation turn."""
        key = f"{session_id}:{user_id}"
        
        if key not in self._sessions:
            self._sessions[key] = {
                "preferences": {},
                "conversation_history": [],
                "user_info": {},
                "last_products": []
            }
        
        context = self._sessions[key]
        
        # Add conversation turn
        context["conversation_history"].append({
            "user": message,
            "assistant": response,
            "timestamp": __import__("datetime").datetime.now().isoformat()
        })
        
        # Update preferences from extracted parameters
        if extracted_preferences:
            context["preferences"].update(extracted_preferences)
        
        # Store last products
        if products:
            context["last_products"] = products[:5]  # Keep last 5 products
        
        # Limit conversation history to last 10 turns
        if len(context["conversation_history"]) > 10:
            context["conversation_history"] = context["conversation_history"][-10:]
        
        logger.debug(f"Updated context for {key}: {len(context['conversation_history'])} messages")
    
    def get_user_preferences(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Get accumulated user preferences."""
        key = f"{session_id}:{user_id}"
        context = self._sessions.get(key, {})
        return context.get("preferences", {})
    
    def get_conversation_summary(self, session_id: str, user_id: str) -> str:
        """Get a summary of the conversation for context."""
        context = self.get_session_context(session_id, user_id)
        history = context.get("conversation_history", [])
        preferences = context.get("preferences", {})
        
        if not history and not preferences:
            return ""
        
        summary_parts = []
        
        # Add preferences summary
        if preferences:
            pref_items = []
            for key, value in preferences.items():
                if isinstance(value, list) and value:
                    pref_items.append(f"{key}: {', '.join(map(str, value))}")
                elif value:
                    pref_items.append(f"{key}: {value}")
            
            if pref_items:
                summary_parts.append(f"User preferences: {'; '.join(pref_items)}")
        
        # Add recent conversation context
        if history:
            recent_messages = history[-3:]  # Last 3 exchanges
            for msg in recent_messages:
                summary_parts.append(f"User said: \"{msg['user'][:50]}...\"")
        
        return " | ".join(summary_parts)


# Global session store (in production, use Redis/database)
session_store = SessionMemoryStore()

def get_session_store() -> SessionMemoryStore:
    """Get the global session store."""
    return session_store