"""
Conversation Handler Service - Production Version
Combines best features from current and enhanced_session.py
Includes persistence workers and memory optimization
"""

import logging
import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict, deque
import hashlib
import os

from openai import AsyncOpenAI
from services.cache.redis_client import RedisService, FallbackRedisService

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
class Message:
    """Conversation message with metadata."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {}
        }


@dataclass
class ConversationContext:
    """Enhanced context for current conversation."""
    session_id: str
    user_id: Optional[str]
    state: ConversationState
    current_intent: Optional[str] = None
    current_products: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_persistence: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    interaction_count: int = 0
    
    def needs_persistence(self, interval_seconds: int = 300) -> bool:
        """Check if context needs persistence."""
        return (datetime.now() - self.last_persistence).total_seconds() > interval_seconds


@dataclass
class ProductInteraction:
    """Track product interactions."""
    product_id: str
    interaction_type: str  # viewed, recommended, purchased, liked
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class PersistenceWorker:
    """Handles background persistence of conversations."""
    
    def __init__(
        self,
        neo4j_client: Any,
        persistence_interval: int = 300,
        batch_size: int = 10
    ):
        """
        Initialize persistence worker.
        
        Args:
            neo4j_client: Neo4j client for persistence
            persistence_interval: Seconds between persistence
            batch_size: Batch size for persistence
        """
        self.neo4j_client = neo4j_client
        self.persistence_interval = persistence_interval
        self.batch_size = batch_size
        self.persistence_queue = asyncio.Queue()
        self.running = False
        self.worker_task = None
        
    async def start(self):
        """Start persistence worker."""
        if not self.running:
            self.running = True
            self.worker_task = asyncio.create_task(self._persistence_loop())
            logger.info("Persistence worker started")
    
    async def stop(self):
        """Stop persistence worker."""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining items
        await self._flush_queue()
        logger.info("Persistence worker stopped")
    
    async def persist(self, data: Dict[str, Any]):
        """Add data to persistence queue."""
        await self.persistence_queue.put(data)
    
    async def _persistence_loop(self):
        """Main persistence loop."""
        batch = []
        
        while self.running:
            try:
                # Collect batch with timeout
                deadline = asyncio.create_task(asyncio.sleep(self.persistence_interval))
                
                while len(batch) < self.batch_size:
                    try:
                        get_task = asyncio.create_task(self.persistence_queue.get())
                        done, pending = await asyncio.wait(
                            {get_task, deadline},
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        if deadline in done:
                            # Timeout reached
                            if not get_task.done():
                                get_task.cancel()
                            break
                        else:
                            # Got item
                            batch.append(get_task.result())
                            
                    except Exception as e:
                        logger.error(f"Error collecting batch: {e}")
                        break
                
                # Persist batch
                if batch:
                    await self._persist_batch(batch)
                    batch = []
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in persistence loop: {e}")
                await asyncio.sleep(10)  # Back off on error
    
    async def _persist_batch(self, batch: List[Dict[str, Any]]):
        """Persist a batch of data."""
        if not self.neo4j_client:
            return
        
        try:
            # Group by type
            conversations = []
            interactions = []
            preferences = []
            
            for item in batch:
                item_type = item.get("type")
                if item_type == "conversation":
                    conversations.append(item)
                elif item_type == "interaction":
                    interactions.append(item)
                elif item_type == "preference":
                    preferences.append(item)
            
            # Persist each type
            if conversations:
                await self._persist_conversations(conversations)
            if interactions:
                await self._persist_interactions(interactions)
            if preferences:
                await self._persist_preferences(preferences)
                
            logger.debug(f"Persisted batch: {len(conversations)} conversations, "
                        f"{len(interactions)} interactions, {len(preferences)} preferences")
                        
        except Exception as e:
            logger.error(f"Error persisting batch: {e}")
    
    async def _persist_conversations(self, conversations: List[Dict[str, Any]]):
        """Persist conversation data."""
        query = """
        UNWIND $conversations AS conv
        MERGE (s:Session {id: conv.session_id})
        SET s.user_id = conv.user_id,
            s.state = conv.state,
            s.message_count = conv.message_count,
            s.updated_at = datetime(conv.updated_at)
        WITH s, conv
        UNWIND conv.messages AS msg
        CREATE (m:Message {
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: datetime(msg.timestamp)
        })
        CREATE (s)-[:HAS_MESSAGE]->(m)
        """
        
        await self.neo4j_client.query(query, {"conversations": conversations})
    
    async def _persist_interactions(self, interactions: List[Dict[str, Any]]):
        """Persist interaction data."""
        query = """
        UNWIND $interactions AS inter
        MATCH (u:User {id: inter.user_id})
        CREATE (i:ProductInteraction {
            product_id: inter.product_id,
            type: inter.interaction_type,
            timestamp: datetime(inter.timestamp),
            session_id: inter.session_id
        })
        CREATE (u)-[:HAS_INTERACTION]->(i)
        """
        
        await self.neo4j_client.query(query, {"interactions": interactions})
    
    async def _persist_preferences(self, preferences: List[Dict[str, Any]]):
        """Persist preference updates."""
        query = """
        UNWIND $preferences AS pref
        MATCH (u:User {id: pref.user_id})
        MERGE (p:Preference {type: pref.type, user_id: pref.user_id})
        SET p.value = pref.value,
            p.confidence = pref.confidence,
            p.updated_at = datetime(pref.updated_at)
        MERGE (u)-[:HAS_PREFERENCE]->(p)
        """
        
        await self.neo4j_client.query(query, {"preferences": preferences})
    
    async def _flush_queue(self):
        """Flush remaining items in queue."""
        batch = []
        while not self.persistence_queue.empty():
            try:
                item = self.persistence_queue.get_nowait()
                batch.append(item)
            except asyncio.QueueEmpty:
                break
        
        if batch:
            await self._persist_batch(batch)


class MemoryOptimizer:
    """Optimizes conversation memory to prevent overflow."""
    
    def __init__(self, max_messages: int = 100, summary_threshold: int = 50):
        """
        Initialize memory optimizer.
        
        Args:
            max_messages: Maximum messages to keep
            summary_threshold: Threshold for summarization
        """
        self.max_messages = max_messages
        self.summary_threshold = summary_threshold
        
    async def optimize(
        self,
        messages: List[Message],
        summarizer: Optional[Any] = None
    ) -> List[Message]:
        """
        Optimize message history.
        
        Args:
            messages: Current messages
            summarizer: Optional CAMEL agent for summarization
            
        Returns:
            Optimized message list
        """
        if len(messages) <= self.summary_threshold:
            return messages
        
        # Keep recent messages
        recent = messages[-self.summary_threshold:]
        old = messages[:-self.summary_threshold]
        
        if not old or not summarizer:
            return recent
        
        try:
            # Create summary of old messages
            summary_content = self._create_summary_prompt(old)
            
            # Use summarizer if available
            if summarizer:
                from lib.camel.v070 import create_message
                response = await summarizer.step(
                    create_message("user", summary_content)
                )
                summary = response.content if hasattr(response, 'content') else str(response)
            else:
                # Basic summary
                summary = f"Summary of {len(old)} previous messages discussing: "
                topics = self._extract_topics(old)
                summary += ", ".join(topics[:5])
            
            # Create summary message
            summary_msg = Message(
                role=MessageRole.SYSTEM,
                content=f"[Conversation Summary] {summary}",
                metadata={"type": "summary", "message_count": len(old)}
            )
            
            # Return summary + recent
            return [summary_msg] + recent
            
        except Exception as e:
            logger.error(f"Error optimizing memory: {e}")
            return messages[-self.max_messages:]
    
    def _create_summary_prompt(self, messages: List[Message]) -> str:
        """Create summarization prompt."""
        content = "Summarize this conversation in 2-3 sentences:\n\n"
        
        for msg in messages[:20]:  # Sample first 20
            role = msg.role.value
            text = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            content += f"{role}: {text}\n"
        
        content += "\nFocus on: user preferences, key decisions, and important context."
        return content
    
    def _extract_topics(self, messages: List[Message]) -> List[str]:
        """Extract main topics from messages."""
        topics = []
        keywords = defaultdict(int)
        
        # Count keyword frequency
        for msg in messages:
            if msg.role == MessageRole.USER:
                words = msg.content.lower().split()
                for word in words:
                    if len(word) > 4:  # Skip short words
                        keywords[word] += 1
        
        # Get top keywords as topics
        sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)
        topics = [word for word, _ in sorted_keywords[:10]]
        
        return topics


class ConversationHandler:
    """
    Enhanced conversation handler with persistence and optimization.
    Combines best features from both implementations.
    """
    
    def __init__(
        self,
        neo4j_service: Optional[Any] = None,
        qdrant_service: Optional[Any] = None,
        agent_factory: Optional[Any] = None,
        redis_client: Optional[Union[RedisService, FallbackRedisService]] = None,
        enable_persistence: bool = True,
        persistence_interval: int = 300,
        enable_optimization: bool = True,
        optimization_threshold: int = 100,
        max_history_length: int = 200
    ):
        """
        Initialize enhanced conversation handler.
        
        Args:
            neo4j_service: Neo4j service for persistence
            qdrant_service: Qdrant service (unused but kept for compatibility)
            agent_factory: Agent factory for creating agents
            enable_persistence: Enable background persistence
            persistence_interval: Persistence interval in seconds
            enable_optimization: Enable memory optimization
            optimization_threshold: Message threshold for optimization
            max_history_length: Maximum conversation history
        """
        self.neo4j_service = neo4j_service
        self.qdrant_service = qdrant_service
        self.agent_factory = agent_factory
        self.redis_client = redis_client
        self.max_history_length = max_history_length
        
        # Redis keys for distributed storage
        self.sessions_key_prefix = "conversation:session:"
        self.conversations_key_prefix = "conversation:messages:"
        self.interactions_key_prefix = "conversation:interactions:"
        self.default_ttl = 86400 * 7  # 7 days TTL
        
        # Persistence worker
        self.persistence_worker = None
        if enable_persistence and neo4j_service:
            self.persistence_worker = PersistenceWorker(
                neo4j_service,
                persistence_interval
            )
        
        # Memory optimizer
        self.memory_optimizer = None
        if enable_optimization:
            self.memory_optimizer = MemoryOptimizer(
                max_messages=max_history_length,
                summary_threshold=optimization_threshold
            )
        
        # Meta-question patterns (from original)
        self.meta_patterns = {
            "memory": [
                "what did i", "remember when", "last time", "previously",
                "earlier", "before", "did i mention", "have i told you"
            ],
            "preferences": [
                "my style", "my size", "my preferences", "what i like",
                "my favorite", "i usually"
            ],
            "history": [
                "what have we discussed", "our conversation",
                "what we talked about", "summarize our chat"
            ],
            "clarification": [
                "what do you mean", "can you explain",
                "i don't understand", "what is"
            ],
            "capability": [
                "can you", "are you able to", "do you", "how do you"
            ]
        }
        
        # State transition rules (from original)
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
        
        # CRITICAL: Initialize missing attributes that are used throughout the class
        self.sessions = {}  # In-memory session cache
        self.conversations = {}  # In-memory conversation cache  
        self.interactions = defaultdict(list)  # In-memory interactions cache
        
        # Initialize OpenAI client for conversational responses
        self.openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Statistics
        self.stats = {
            "total_sessions": 0,
            "total_messages": 0,
            "total_interactions": 0,
            "persistence_count": 0,
            "optimization_count": 0
        }
        
        logger.info(f"ConversationHandler initialized (persistence={'enabled' if enable_persistence else 'disabled'}, "
                   f"optimization={'enabled' if enable_optimization else 'disabled'})")
    
    async def start(self):
        """Start background workers."""
        if self.persistence_worker:
            await self.persistence_worker.start()
    
    async def stop(self):
        """Stop background workers and cleanup."""
        if self.persistence_worker:
            # Persist all active sessions before stopping
            await self._persist_all_sessions()
            await self.persistence_worker.stop()
    
    async def _persist_all_sessions(self):
        """Persist all active sessions."""
        for session_id, context in self.sessions.items():
            await self._persist_session(session_id, context)
    
    async def _persist_session(self, session_id: str, context: ConversationContext):
        """Persist a single session."""
        if not self.persistence_worker:
            return
        
        try:
            # Prepare conversation data
            messages = self.conversations.get(session_id, [])
            conversation_data = {
                "type": "conversation",
                "session_id": session_id,
                "user_id": context.user_id,
                "state": context.state.value,
                "message_count": context.message_count,
                "updated_at": context.updated_at.isoformat(),
                "messages": [msg.to_dict() for msg in messages[-20:]]  # Last 20 messages
            }
            
            await self.persistence_worker.persist(conversation_data)
            
            # Persist interactions
            session_interactions = self.interactions.get(session_id, [])
            for interaction in session_interactions:
                interaction_data = {
                    "type": "interaction",
                    "session_id": session_id,
                    "user_id": context.user_id,
                    "product_id": interaction.product_id,
                    "interaction_type": interaction.interaction_type,
                    "timestamp": interaction.timestamp.isoformat()
                }
                await self.persistence_worker.persist(interaction_data)
            
            # Update persistence time
            context.last_persistence = datetime.now()
            self.stats["persistence_count"] += 1
            
        except Exception as e:
            logger.error(f"Error persisting session {session_id}: {e}")
    
    async def get_response(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None
    ) -> str:
        """
        Main entry point for getting response.
        
        Args:
            session_id: Session identifier
            message: User message
            user_id: Optional user identifier
            
        Returns:
            Response string
        """
        # Handle message and get response type
        response_type, metadata = await self.handle_message(session_id, message, user_id)
        
        # Generate appropriate response
        if response_type == "meta":
            return metadata.get("response", "I'm here to help!")
        elif response_type == "greeting":
            return metadata.get("response", "Hello! How can I help you today?")
        elif response_type == "goodbye":
            return metadata.get("response", "Goodbye!")
        elif response_type == "search":
            return "Let me search for that for you..."
        elif response_type == "compare":
            return "Let's compare these options..."
        elif response_type == "browse":
            return "Here are some options to browse..."
        else:
            return "How can I help you find the perfect style today?"
    
    async def handle_message(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Handle incoming message and determine response strategy.
        Enhanced with persistence and optimization.
        
        Args:
            session_id: Session identifier
            message: User message
            user_id: Optional user identifier
            
        Returns:
            Tuple of (response_type, metadata)
        """
        # Get or create session
        context = self.get_or_create_session(session_id, user_id)
        
        # Create and add message
        user_message = Message(
            role=MessageRole.USER,
            content=message,
            metadata={"user_id": user_id}
        )
        
        await self._add_message(session_id, user_message)
        
        # Update context
        context.message_count += 1
        context.updated_at = datetime.now()
        self.stats["total_messages"] += 1
        
        # Check if optimization needed
        if self.memory_optimizer and len(self.conversations[session_id]) > self.memory_optimizer.summary_threshold:
            await self._optimize_session_memory(session_id)
        
        # Check if persistence needed
        if context.needs_persistence() and self.persistence_worker:
            asyncio.create_task(self._persist_session(session_id, context))
        
        # Check for meta-questions (only fashion-related)
        meta_type = self._detect_meta_question(message)
        if meta_type:
            response = await self._handle_meta_question(session_id, message, meta_type)
            return ("meta", {"type": meta_type, "response": response})
        
        # Check for greeting
        if self._is_greeting(message) and context.state == ConversationState.NEW:
            context.state = ConversationState.GREETING
            response = await self._generate_greeting(context)
            return ("greeting", {"response": response})
        
        # Check for goodbye
        if self._is_goodbye(message):
            context.state = ConversationState.ENDED
            await self._persist_session(session_id, context)  # Final persist
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
            # Generate LLM-based conversational response
            conversational_response = await self.generate_conversational_response(session_id, message, user_id)
            return ("conversation", {"state": context.state.value, "response": conversational_response})
    
    async def _add_message(self, session_id: str, message: Message):
        """Add message to conversation with optimization."""
        # Ensure conversations is initialized for this session
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        self.conversations[session_id].append(message)
        
        # Trim if too long
        if len(self.conversations[session_id]) > self.max_history_length:
            self.conversations[session_id] = self.conversations[session_id][-self.max_history_length:]
        
        # Async save to Redis in background if available
        if self.redis_client:
            asyncio.create_task(self._save_conversations_to_redis(session_id, self.conversations[session_id]))
    
    async def _optimize_session_memory(self, session_id: str):
        """Optimize session memory."""
        if not self.memory_optimizer or session_id not in self.conversations:
            return
        
        try:
            messages = self.conversations[session_id]
            
            # Get summarizer agent if available
            summarizer = None
            if self.agent_factory:
                summarizer = await self.agent_factory.create_memory_handler_agent()
            
            # Optimize messages
            optimized = await self.memory_optimizer.optimize(messages, summarizer)
            self.conversations[session_id] = optimized
            
            self.stats["optimization_count"] += 1
            logger.info(f"Optimized session {session_id}: {len(messages)} -> {len(optimized)} messages")
            
        except Exception as e:
            logger.error(f"Error optimizing session memory: {e}")
    
    def get_or_create_session(
        self,
        session_id: str,
        user_id: Optional[str] = None
    ) -> ConversationContext:
        """Get or create session context (synchronous for better compatibility)."""
        # Check in-memory cache first
        if session_id in self.sessions:
            context = self.sessions[session_id]
            # Update user_id if provided and missing
            if user_id and not context.user_id:
                context.user_id = user_id
            return context
        
        # Create new session
        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            state=ConversationState.NEW
        )
        
        # Store in memory and initialize related structures
        self.sessions[session_id] = context
        self.conversations[session_id] = []
        self.interactions[session_id] = []
        
        # Async save to Redis in background if available
        if self.redis_client:
            asyncio.create_task(self._save_session_to_redis(session_id, context))
            asyncio.create_task(self._save_conversations_to_redis(session_id, []))
        
        self.stats["total_sessions"] += 1
        logger.info(f"Created session: {session_id}")
        return context
    
    async def record_product_interaction(
        self,
        session_id: str,
        product_id: str,
        interaction_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record product interaction.
        
        Args:
            session_id: Session identifier
            product_id: Product identifier
            interaction_type: Type of interaction
            metadata: Optional metadata
        """
        interaction = ProductInteraction(
            product_id=product_id,
            interaction_type=interaction_type,
            metadata=metadata
        )
        
        # Ensure interactions is initialized for this session
        if session_id not in self.interactions:
            self.interactions[session_id] = []
        
        self.interactions[session_id].append(interaction)
        
        # Update context
        if session_id in self.sessions:
            context = self.sessions[session_id]
            context.interaction_count += 1
            
            # Persist if needed
            if self.persistence_worker and context.user_id:
                interaction_data = {
                    "type": "interaction",
                    "session_id": session_id,
                    "user_id": context.user_id,
                    "product_id": product_id,
                    "interaction_type": interaction_type,
                    "timestamp": interaction.timestamp.isoformat()
                }
                await self.persistence_worker.persist(interaction_data)
        
        self.stats["total_interactions"] += 1
    
    def update_product_context(
        self,
        session_id: str,
        products: List[str]
    ):
        """Update current product context."""
        if session_id in self.sessions:
            self.sessions[session_id].current_products = products
            
            # Record as recommendations
            for product_id in products:
                asyncio.create_task(
                    self.record_product_interaction(
                        session_id, product_id, "recommended"
                    )
                )
    
    def extract_preferences_from_history(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """Extract user preferences from conversation."""
        preferences = {}
        
        if session_id not in self.conversations:
            return preferences
        
        # Analyze messages
        for msg in self.conversations[session_id]:
            if msg.role == MessageRole.USER:
                content_lower = msg.content.lower()
                
                # Extract colors
                colors = []
                color_words = ["red", "blue", "green", "black", "white", "pink", "purple", "yellow", "gray", "brown", "navy", "beige"]
                for color in color_words:
                    if color in content_lower:
                        colors.append(color)
                
                if colors:
                    preferences["colors"] = list(set(preferences.get("colors", []) + colors))
                
                # Extract styles
                styles = []
                style_words = ["casual", "formal", "sporty", "elegant", "trendy", "classic", "bohemian", "minimalist", "vintage", "modern"]
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
                    max_price = max(int(p) for p in prices)
                    preferences["max_budget"] = max(preferences.get("max_budget", 0), max_price)
                
                # Extract occasions
                occasions = []
                occasion_words = ["wedding", "party", "work", "date", "casual", "formal", "beach", "gym"]
                for occasion in occasion_words:
                    if occasion in content_lower:
                        occasions.append(occasion)
                
                if occasions:
                    preferences["occasions"] = list(set(preferences.get("occasions", []) + occasions))
        
        # Update session preferences
        if session_id in self.sessions:
            self.sessions[session_id].preferences.update(preferences)
        
        return preferences
    
    # Include all meta-question handling methods from original...
    def _detect_meta_question(self, message: str) -> Optional[str]:
        """Detect if message is a meta-question related to fashion/shopping context."""
        message_lower = message.lower()
        
        # Fashion/shopping related keywords to check context
        fashion_context_keywords = [
            "fashion", "style", "clothing", "outfit", "dress", "shirt", "pants", "shoes",
            "size", "color", "brand", "shop", "buy", "purchase", "wear", "look",
            "trend", "material", "fabric", "design", "preference", "like", "budget",
            "what did i buy", "what have we looked at", "my style preferences", "what clothes",
            "fashion advice", "style suggestions", "outfit recommendations"
        ]
        
        # Exclude obvious general knowledge questions that aren't about fashion/shopping
        general_knowledge_patterns = [
            "quantum", "physics", "science", "mathematics", "history", "geography", "biology",
            "chemistry", "philosophy", "literature", "music", "art history", "politics",
            "economics", "technology", "computer", "programming", "how does", "why does",
            "what causes", "theory of", "explain the concept", "what happens when",
            "how do you feel", "what's your day like", "tell me about yourself",
            "weather", "news", "current events", "sports", "movies", "books",
            "superposition", "super-position", "principle", "this like", "is this mroe like",
            "similar to", "reminds me of", "like the", "analogous to"
        ]
        
        # Check if message is general knowledge (not fashion-related)
        is_general_knowledge = any(pattern in message_lower for pattern in general_knowledge_patterns)
        
        # Check if message has fashion context
        has_fashion_context = any(keyword in message_lower for keyword in fashion_context_keywords)
        
        # Only classify as meta-question if it's clearly fashion/shopping related AND not general knowledge
        if has_fashion_context and not is_general_knowledge:
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
        context = self.sessions.get(session_id)
        
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
    
    async def _handle_memory_question(self, session_id: str, message: str) -> str:
        """Handle memory-related question."""
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
        
        if prefs:
            return f"Based on our conversation, your preferences include: {'; '.join(prefs)}"
        
        return "Tell me more about your style preferences!"
    
    def _handle_history_question(self, session_id: str) -> str:
        """Handle conversation history question."""
        history = self.conversations.get(session_id, [])
        
        if not history:
            return "We're just getting started! What can I help you find?"
        
        user_messages = [msg for msg in history if msg.role == MessageRole.USER]
        
        summary = f"We've exchanged {len(user_messages)} messages. "
        
        context = self.sessions.get(session_id)
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
            base_greeting = "Welcome back! It's great to see you again. "
        
        return base_greeting + "I'm here to help you discover amazing styles and find pieces you'll love. What are you looking for today?"
    
    def _determine_state_transition(
        self,
        context: ConversationContext,
        message: str
    ) -> Optional[ConversationState]:
        """Determine state transition based on message."""
        message_lower = message.lower()
        
        # Fashion/shopping context keywords (more specific to actual shopping intent)
        shopping_context_keywords = [
            "dress", "shirt", "pants", "shoes", "clothing", "outfit", "fashion", "style", 
            "buy", "purchase", "shop", "wear", "size", "brand", "collection", "item", "product",
            "looking for", "need a", "want a", "show me", "find me"
        ]
        
        # Additional check: exclude general conversational phrases about colors/preferences
        general_conversation_phrases = [
            "favorite color", "what's your favorite", "do you like", "what do you think",
            "tell me about", "explain", "how do", "what is", "why is"
        ]
        
        # Only check for shopping state transitions if message has shopping context
        # but exclude general conversation about preferences/colors
        has_shopping_context = (
            any(keyword in message_lower for keyword in shopping_context_keywords) and
            not any(phrase in message_lower for phrase in general_conversation_phrases)
        )
        
        if has_shopping_context:
            # Keywords for state detection (more specific)
            search_keywords = ["looking for", "search", "find", "need", "want", "show me"]
            browse_keywords = ["browse", "explore", "what do you have", "options"]
            compare_keywords = ["compare", "versus", "vs", "better", "difference", "which"]
            decide_keywords = ["i'll take", "buy", "purchase", "get this", "want this", "order"]
            feedback_keywords = ["love it", "hate it", "perfect", "not what", "exactly", "amazing"]
            
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
        
        # No shopping context or state transition detected
        return None
    
    async def generate_conversational_response(
        self,
        session_id: str,
        message: str,
        user_id: Optional[str] = None
    ) -> str:
        """Generate LLM-based conversational response for general topics."""
        try:
            # Get conversation history for context
            conversation_history = self.conversations.get(session_id, [])
            
            # Build conversation context - only include last 5 exchanges to stay within token limits
            messages = [
                {
                    "role": "system",
                    "content": """You are Ari, a friendly and knowledgeable fashion stylist AI. You can discuss any topic that users bring up, not just fashion. Be helpful, informative, and conversational. 

When users ask about non-fashion topics (like science, philosophy, general knowledge, etc.), engage naturally and provide helpful information while maintaining your warm personality.

Keep responses concise and friendly. If the conversation naturally flows back to fashion or style, you can mention your expertise in that area, but don't force it."""
                }
            ]
            
            # Add recent conversation history for context
            for msg in conversation_history[-5:]:  # Last 5 messages for context
                if msg.role == MessageRole.USER:
                    messages.append({"role": "user", "content": msg.content})
                elif msg.role == MessageRole.ASSISTANT:
                    messages.append({"role": "assistant", "content": msg.content})
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Generate response using OpenAI
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=300,
                temperature=0.7,
                timeout=30
            )
            
            generated_response = response.choices[0].message.content.strip()
            
            # Log for debugging
            logger.info(f"Generated conversational response for topic in message: '{message[:50]}...'")
            
            return generated_response
            
        except Exception as e:
            logger.error(f"Error generating conversational response: {e}")
            # Fallback to friendly default
            return "I'm here to help with any questions you have! Whether it's about fashion, style, or just chatting about life, I'm happy to talk. What's on your mind?"
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive handler statistics."""
        # Get active session count from Redis
        active_sessions_count = 0
        if self.redis_client:
            try:
                # Count sessions by scanning for session keys
                session_keys = await self.redis_client.keys(f"{self.sessions_key_prefix}*")
                active_sessions_count = len(session_keys)
            except Exception as e:
                logger.error(f"Error getting active sessions count: {e}")
        
        return {
            "active_sessions": active_sessions_count,
            "total_sessions": self.stats["total_sessions"],
            "total_messages": self.stats["total_messages"],
            "total_interactions": self.stats["total_interactions"],
            "persistence_count": self.stats["persistence_count"],
            "optimization_count": self.stats["optimization_count"],
            "redis_storage": bool(self.redis_client),
            "avg_messages_per_session": (
                self.stats["total_messages"] / self.stats["total_sessions"]
                if self.stats["total_sessions"] > 0 else 0
            )
        }
    
    async def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old sessions with final persistence."""
        current_time = datetime.now()
        sessions_to_remove = []
        
        for session_id, context in self.sessions.items():
            age = (current_time - context.updated_at).total_seconds() / 3600
            
            if age > max_age_hours:
                # Persist before removing
                await self._persist_session(session_id, context)
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.sessions[session_id]
            if session_id in self.conversations:
                del self.conversations[session_id]
            if session_id in self.interactions:
                del self.interactions[session_id]
        
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions")
    
    # ==================== REDIS HELPER METHODS ====================
    
    async def _get_session_from_redis(self, session_id: str) -> Optional[ConversationContext]:
        """Get session context from Redis."""
        if not self.redis_client:
            return None
        
        try:
            session_key = f"{self.sessions_key_prefix}{session_id}"
            session_data = await self.redis_client.get_json(session_key)
            
            if session_data:
                # Convert back to ConversationContext
                context = ConversationContext(
                    session_id=session_data['session_id'],
                    user_id=session_data.get('user_id'),
                    state=ConversationState(session_data['state']),
                    current_intent=session_data.get('current_intent'),
                    current_products=session_data.get('current_products', []),
                    preferences=session_data.get('preferences', {}),
                    metadata=session_data.get('metadata', {}),
                    created_at=datetime.fromisoformat(session_data['created_at']),
                    updated_at=datetime.fromisoformat(session_data['updated_at']),
                    last_persistence=datetime.fromisoformat(session_data.get('last_persistence', session_data['updated_at'])),
                    message_count=session_data.get('message_count', 0),
                    interaction_count=session_data.get('interaction_count', 0)
                )
                return context
        except Exception as e:
            logger.error(f"Error getting session {session_id} from Redis: {e}")
        
        return None
    
    async def _save_session_to_redis(self, session_id: str, context: ConversationContext) -> bool:
        """Save session context to Redis."""
        if not self.redis_client:
            return False
        
        try:
            session_key = f"{self.sessions_key_prefix}{session_id}"
            session_data = {
                'session_id': context.session_id,
                'user_id': context.user_id,
                'state': context.state.value,
                'current_intent': context.current_intent,
                'current_products': context.current_products,
                'preferences': context.preferences,
                'metadata': context.metadata,
                'created_at': context.created_at.isoformat(),
                'updated_at': context.updated_at.isoformat(),
                'last_persistence': context.last_persistence.isoformat(),
                'message_count': context.message_count,
                'interaction_count': context.interaction_count
            }
            
            return await self.redis_client.set_json(session_key, session_data, ttl=self.default_ttl)
        except Exception as e:
            logger.error(f"Error saving session {session_id} to Redis: {e}")
            return False
    
    async def _get_conversations_from_redis(self, session_id: str) -> List[Message]:
        """Get conversation messages from Redis."""
        if not self.redis_client:
            return []
        
        try:
            conv_key = f"{self.conversations_key_prefix}{session_id}"
            messages_data = await self.redis_client.get_json(conv_key)
            
            if messages_data and isinstance(messages_data, list):
                messages = []
                for msg_data in messages_data:
                    message = Message(
                        role=MessageRole(msg_data['role']),
                        content=msg_data['content'],
                        timestamp=datetime.fromisoformat(msg_data['timestamp']),
                        metadata=msg_data.get('metadata'),
                        message_id=msg_data['id']
                    )
                    messages.append(message)
                return messages
        except Exception as e:
            logger.error(f"Error getting conversations for {session_id} from Redis: {e}")
        
        return []
    
    async def _save_conversations_to_redis(self, session_id: str, messages: List[Message]) -> bool:
        """Save conversation messages to Redis."""
        if not self.redis_client:
            return False
        
        try:
            conv_key = f"{self.conversations_key_prefix}{session_id}"
            messages_data = [msg.to_dict() for msg in messages]
            
            return await self.redis_client.set_json(conv_key, messages_data, ttl=self.default_ttl)
        except Exception as e:
            logger.error(f"Error saving conversations for {session_id} to Redis: {e}")
            return False
    
    async def _get_interactions_from_redis(self, session_id: str) -> List[ProductInteraction]:
        """Get product interactions from Redis."""
        if not self.redis_client:
            return []
        
        try:
            int_key = f"{self.interactions_key_prefix}{session_id}"
            interactions_data = await self.redis_client.get_json(int_key)
            
            if interactions_data and isinstance(interactions_data, list):
                interactions = []
                for int_data in interactions_data:
                    interaction = ProductInteraction(
                        product_id=int_data['product_id'],
                        interaction_type=int_data['interaction_type'],
                        timestamp=datetime.fromisoformat(int_data['timestamp']),
                        metadata=int_data.get('metadata')
                    )
                    interactions.append(interaction)
                return interactions
        except Exception as e:
            logger.error(f"Error getting interactions for {session_id} from Redis: {e}")
        
        return []
    
    async def _save_interactions_to_redis(self, session_id: str, interactions: List[ProductInteraction]) -> bool:
        """Save product interactions to Redis."""
        if not self.redis_client:
            return False
        
        try:
            int_key = f"{self.interactions_key_prefix}{session_id}"
            interactions_data = []
            
            for interaction in interactions:
                interactions_data.append({
                    'product_id': interaction.product_id,
                    'interaction_type': interaction.interaction_type,
                    'timestamp': interaction.timestamp.isoformat(),
                    'metadata': interaction.metadata
                })
            
            return await self.redis_client.set_json(int_key, interactions_data, ttl=self.default_ttl)
        except Exception as e:
            logger.error(f"Error saving interactions for {session_id} to Redis: {e}")
            return False

    async def shutdown(self):
        """Graceful shutdown with persistence."""
        logger.info("Shutting down ConversationHandler")
        
        # Persist all active sessions
        await self._persist_all_sessions()
        
        # Stop workers
        await self.stop()
        
        logger.info("ConversationHandler shutdown complete")


# Export public API
__all__ = [
    'ConversationHandler',
    'ConversationContext',
    'ConversationState',
    'Message',
    'MessageRole',
    'ProductInteraction',
    'PersistenceWorker',
    'MemoryOptimizer'
]