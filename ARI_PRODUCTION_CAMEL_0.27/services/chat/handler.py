"""
Conversation Handler Service
Manages conversation flow and meta-questions
Based on conversation_handler.py patterns
"""

import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger("services.conversation.handler")

from config.prompts import (
    MEMORY_HANDLER_PROMPT,
    GREETING_HANDLER_PROMPT,
    PRODUCT_RESPONSE_PROMPT
)


class ConversationState(Enum):
    """States of conversation."""
    NEW = "new"
    GREETING = "greeting"
    BROWSING = "browsing"
    SEARCHING = "searching"
    COMPARING = "comparing"
    DECIDING = "deciding"
    PURCHASED = "purchased"
    FEEDBACK = "feedback"
    ENDED = "ended"


class MessageRole(Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ConversationContext:
    """Context for current conversation."""
    session_id: str
    user_id: Optional[str]
    state: ConversationState
    current_intent: Optional[str]
    current_products: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Message:
    """Conversation message."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class ConversationHandler:
    """
    Handles conversation flow, context, and meta-questions.
    """
    
    def __init__(
        self,
        memory_agent: Optional[Any] = None,
        max_history_length: int = 50
    ):
        """
        Initialize conversation handler.
        
        Args:
            memory_agent: Optional CAMEL agent for memory questions
            max_history_length: Maximum conversation history length
        """
        self.memory_agent = memory_agent
        self.max_history_length = max_history_length
        
        # Active conversations
        self.conversations: Dict[str, List[Message]] = {}
        self.contexts: Dict[str, ConversationContext] = {}
        
        # Meta-question patterns
        self.meta_patterns = {
            "memory": [
                "what did i",
                "remember when",
                "last time",
                "previously",
                "earlier",
                "before",
                "did i mention",
                "have i told you"
            ],
            "preferences": [
                "my style",
                "my size",
                "my preferences",
                "what i like",
                "my favorite",
                "i usually"
            ],
            "history": [
                "what have we discussed",
                "our conversation",
                "what we talked about",
                "summarize our chat"
            ],
            "clarification": [
                "what do you mean",
                "can you explain",
                "i don't understand",
                "what is"
            ],
            "capability": [
                "can you",
                "are you able to",
                "do you",
                "how do you"
            ]
        }
        
        # State transition rules
        self.state_transitions = {
            ConversationState.NEW: [ConversationState.GREETING, ConversationState.SEARCHING],
            ConversationState.GREETING: [ConversationState.BROWSING, ConversationState.SEARCHING],
            ConversationState.BROWSING: [ConversationState.SEARCHING, ConversationState.COMPARING],
            ConversationState.SEARCHING: [ConversationState.BROWSING, ConversationState.COMPARING, ConversationState.DECIDING],
            ConversationState.COMPARING: [ConversationState.SEARCHING, ConversationState.DECIDING],
            ConversationState.DECIDING: [ConversationState.PURCHASED, ConversationState.SEARCHING],
            ConversationState.PURCHASED: [ConversationState.FEEDBACK, ConversationState.SEARCHING],
            ConversationState.FEEDBACK: [ConversationState.SEARCHING, ConversationState.ENDED]
        }
        
        logger.info("Conversation handler initialized")
    
    def create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> ConversationContext:
        """
        Create new conversation session.
        
        Args:
            session_id: Session identifier
            user_id: Optional user identifier
            
        Returns:
            New conversation context
        """
        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            state=ConversationState.NEW
        )
        
        self.conversations[session_id] = []
        self.contexts[session_id] = context
        
        logger.info(f"Created conversation session: {session_id}")
        return context
    
    def get_or_create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> ConversationContext:
        """
        Get existing or create new session.
        
        Args:
            session_id: Session identifier
            user_id: Optional user identifier
            
        Returns:
            Conversation context
        """
        if session_id in self.contexts:
            context = self.contexts[session_id]
            # Update user ID if provided
            if user_id and not context.user_id:
                context.user_id = user_id
            return context
        
        return self.create_session(session_id, user_id)
    
    async def handle_message(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle incoming message and determine response strategy.
        
        Args:
            session_id: Session identifier
            message: User message
            user_id: Optional user identifier
            
        Returns:
            Tuple of (response_type, metadata)
        """
        # Get or create context
        context = self.get_or_create_session(session_id, user_id)
        
        # Add message to history
        self._add_message(session_id, MessageRole.USER, message)
        
        # Check for meta-questions
        meta_type = self._detect_meta_question(message)
        if meta_type:
            response = await self._handle_meta_question(
                session_id,
                message,
                meta_type
            )
            return ("meta", {"type": meta_type, "response": response})
        
        # Check for greeting
        if self._is_greeting(message) and context.state == ConversationState.NEW:
            context.state = ConversationState.GREETING
            response = await self._generate_greeting(context)
            return ("greeting", {"response": response})
        
        # Check for conversation end
        if self._is_goodbye(message):
            context.state = ConversationState.ENDED
            return ("goodbye", {"response": "It was lovely helping you today! Come back anytime you need style advice. 💕"})
        
        # Update state based on message
        new_state = self._determine_state_transition(context, message)
        if new_state:
            context.state = new_state
        
        # Determine response type based on state
        if context.state == ConversationState.SEARCHING:
            return ("search", {"needs_battle": True})
        elif context.state == ConversationState.COMPARING:
            return ("compare", {"products": context.current_products})
        elif context.state == ConversationState.BROWSING:
            return ("browse", {"preferences": context.preferences})
        else:
            return ("conversation", {"state": context.state.value})
    
    def _detect_meta_question(self, message: str) -> Optional[str]:
        """Detect if message is a meta-question."""
        message_lower = message.lower()
        
        for meta_type, patterns in self.meta_patterns.items():
            for pattern in patterns:
                if pattern in message_lower:
                    return meta_type
        
        return None
    
    async def _handle_meta_question(
        self,
        session_id: str,
        message: str,
        meta_type: str
    ) -> str:
        """Handle meta-question."""
        context = self.contexts.get(session_id)
        
        if meta_type == "memory":
            return await self._handle_memory_question(session_id, message)
        elif meta_type == "preferences":
            return self._handle_preferences_question(context)
        elif meta_type == "history":
            return self._handle_history_question(session_id)
        elif meta_type == "clarification":
            return self._handle_clarification(message)
        elif meta_type == "capability":
            return self._handle_capability_question(message)
        else:
            return "I'm here to help you find the perfect style!"
    
    async def _handle_memory_question(
        self,
        session_id: str,
        message: str
    ) -> str:
        """Handle memory-related question."""
        if self.memory_agent:
            # Use CAMEL agent for memory questions
            # Use CAMEL 0.2.7 direct agent calls
            
            try:
                response = self.memory_agent.step(message)
                if response:
                    return response.msg.content if hasattr(response, 'msg') else str(response)
            except Exception as e:
                logger.error(f"Memory agent error: {e}")
        
        # Fallback response
        history = self.conversations.get(session_id, [])
        if history:
            recent = [msg for msg in history[-10:] if msg.role == MessageRole.USER]
            if recent:
                topics = ", ".join([msg.content[:30] + "..." for msg in recent[-3:]])
                return f"We've been discussing: {topics}"
        
        return "We haven't discussed anything specific yet. What would you like to explore?"
    
    def _handle_preferences_question(self, context: Optional[ConversationContext]) -> str:
        """Handle preferences question."""
        if not context or not context.preferences:
            return "I don't have any saved preferences for you yet. Tell me about your style!"
        
        prefs = []
        if "colors" in context.preferences:
            prefs.append(f"colors: {', '.join(context.preferences['colors'])}")
        if "styles" in context.preferences:
            prefs.append(f"styles: {', '.join(context.preferences['styles'])}")
        if "sizes" in context.preferences:
            prefs.append(f"sizes: {context.preferences['sizes']}")
        
        if prefs:
            return f"Based on our conversation, your preferences include: {'; '.join(prefs)}"
        
        return "Tell me more about your style preferences!"
    
    def _handle_history_question(self, session_id: str) -> str:
        """Handle conversation history question."""
        history = self.conversations.get(session_id, [])
        
        if not history:
            return "We're just getting started! What can I help you find?"
        
        # Summarize conversation
        user_messages = [msg for msg in history if msg.role == MessageRole.USER]
        assistant_messages = [msg for msg in history if msg.role == MessageRole.ASSISTANT]
        
        summary = f"We've exchanged {len(user_messages)} messages. "
        
        # Identify main topics
        context = self.contexts.get(session_id)
        if context:
            if context.current_products:
                summary += f"We've looked at {len(context.current_products)} products. "
            if context.state != ConversationState.NEW:
                summary += f"We're currently {context.state.value}. "
        
        return summary + "What would you like to explore next?"
    
    def _handle_clarification(self, message: str) -> str:
        """Handle clarification request."""
        return "I'm here to help you find amazing fashion pieces! You can browse styles, search for specific items, or ask for outfit recommendations. What interests you?"
    
    def _handle_capability_question(self, message: str) -> str:
        """Handle capability question."""
        capabilities = [
            "find specific fashion items",
            "suggest complete outfits",
            "help you discover your style",
            "recommend products based on your preferences",
            "compare different options",
            "work within your budget"
        ]
        
        return f"I can help you {', '.join(capabilities)}. What would you like to explore?"
    
    def _is_greeting(self, message: str) -> bool:
        """Check if message is a greeting."""
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings"]
        message_lower = message.lower().strip()
        
        return any(message_lower.startswith(g) for g in greetings)
    
    def _is_goodbye(self, message: str) -> bool:
        """Check if message is a goodbye."""
        goodbyes = ["bye", "goodbye", "see you", "thanks", "thank you", "that's all", "done", "exit", "quit"]
        message_lower = message.lower().strip()
        
        return any(g in message_lower for g in goodbyes)
    
    async def _generate_greeting(self, context: ConversationContext) -> str:
        """Generate personalized greeting."""
        base_greeting = "Hi there! I'm Ari, your personal fashion stylist. "
        
        if context.user_id:
            # Personalized greeting for returning user
            base_greeting = "Welcome back! It's great to see you again. "
        
        return base_greeting + "I'm here to help you discover amazing styles and find pieces you'll love. What are you looking for today?"
    
    def _determine_state_transition(
        self,
        context: ConversationContext,
        message: str
    ) -> Optional[ConversationState]:
        """Determine state transition based on message."""
        message_lower = message.lower()
        
        # Keywords for state detection
        search_keywords = ["looking for", "search", "find", "need", "want"]
        browse_keywords = ["show me", "browse", "explore", "what do you have"]
        compare_keywords = ["compare", "versus", "vs", "better", "difference"]
        decide_keywords = ["i'll take", "buy", "purchase", "get this", "want this"]
        feedback_keywords = ["love it", "hate it", "perfect", "not what", "exactly"]
        
        current_state = context.state
        
        # Check for state transitions
        if any(keyword in message_lower for keyword in search_keywords):
            if ConversationState.SEARCHING in self.state_transitions.get(current_state, []):
                return ConversationState.SEARCHING
        
        elif any(keyword in message_lower for keyword in browse_keywords):
            if ConversationState.BROWSING in self.state_transitions.get(current_state, []):
                return ConversationState.BROWSING
        
        elif any(keyword in message_lower for keyword in compare_keywords):
            if ConversationState.COMPARING in self.state_transitions.get(current_state, []):
                return ConversationState.COMPARING
        
        elif any(keyword in message_lower for keyword in decide_keywords):
            if ConversationState.DECIDING in self.state_transitions.get(current_state, []):
                return ConversationState.DECIDING
        
        elif any(keyword in message_lower for keyword in feedback_keywords):
            if ConversationState.FEEDBACK in self.state_transitions.get(current_state, []):
                return ConversationState.FEEDBACK
        
        return None
    
    def _add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add message to conversation history."""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        message = Message(
            role=role,
            content=content,
            metadata=metadata
        )
        
        self.conversations[session_id].append(message)
        
        # Trim history if too long
        if len(self.conversations[session_id]) > self.max_history_length:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history_length:]
        
        # Update context timestamp
        if session_id in self.contexts:
            self.contexts[session_id].updated_at = datetime.now()
    
    def add_assistant_response(
        self,
        session_id: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add assistant response to history."""
        self._add_message(session_id, MessageRole.ASSISTANT, response, metadata)
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history.
        
        Args:
            session_id: Session identifier
            limit: Optional limit on messages
            
        Returns:
            List of message dictionaries
        """
        if session_id not in self.conversations:
            return []
        
        messages = self.conversations[session_id]
        
        if limit:
            messages = messages[-limit:]
        
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "metadata": msg.metadata
            }
            for msg in messages
        ]
    
    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        """Get conversation context."""
        return self.contexts.get(session_id)
    
    def update_context(
        self,
        session_id: str,
        **updates
    ):
        """Update conversation context."""
        if session_id in self.contexts:
            context = self.contexts[session_id]
            
            for key, value in updates.items():
                if hasattr(context, key):
                    setattr(context, key, value)
            
            context.updated_at = datetime.now()
    
    def extract_preferences_from_history(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """Extract user preferences from conversation."""
        preferences = {}
        
        if session_id not in self.conversations:
            return preferences
        
        # Analyze user messages for preferences
        for msg in self.conversations[session_id]:
            if msg.role == MessageRole.USER:
                content_lower = msg.content.lower()
                
                # Extract color preferences
                colors = []
                color_words = ["red", "blue", "green", "black", "white", "pink", "purple", "yellow", "gray", "brown"]
                for color in color_words:
                    if color in content_lower:
                        colors.append(color)
                
                if colors:
                    preferences["colors"] = list(set(preferences.get("colors", []) + colors))
                
                # Extract style preferences
                styles = []
                style_words = ["casual", "formal", "sporty", "elegant", "trendy", "classic", "bohemian", "minimalist"]
                for style in style_words:
                    if style in content_lower:
                        styles.append(style)
                
                if styles:
                    preferences["styles"] = list(set(preferences.get("styles", []) + styles))
                
                # Extract budget
                import re
                price_pattern = r"\$(\d+)"
                prices = re.findall(price_pattern, content_lower)
                if prices:
                    preferences["max_budget"] = max(int(p) for p in prices)
        
        return preferences
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old conversation sessions."""
        current_time = datetime.now()
        sessions_to_remove = []
        
        for session_id, context in self.contexts.items():
            age = (current_time - context.updated_at).total_seconds() / 3600
            
            if age > max_age_hours:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.contexts[session_id]
            if session_id in self.conversations:
                del self.conversations[session_id]
        
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get conversation handler statistics."""
        return {
            "active_sessions": len(self.contexts),
            "total_messages": sum(len(msgs) for msgs in self.conversations.values()),
            "state_distribution": {
                state.value: sum(1 for ctx in self.contexts.values() if ctx.state == state)
                for state in ConversationState
            }
        }


# Global instance
_conversation_handler: Optional[ConversationHandler] = None


def get_conversation_handler(memory_agent: Optional[Any] = None) -> ConversationHandler:
    """
    Get global conversation handler instance.
    
    Args:
        memory_agent: Optional CAMEL agent for memory
        
    Returns:
        ConversationHandler instance
    """
    global _conversation_handler
    
    if _conversation_handler is None:
        _conversation_handler = ConversationHandler(memory_agent=memory_agent)
    
    return _conversation_handler


# Exports
__all__ = [
    'ConversationHandler',
    'ConversationContext',
    'ConversationState',
    'Message',
    'MessageRole',
    'get_conversation_handler'
]