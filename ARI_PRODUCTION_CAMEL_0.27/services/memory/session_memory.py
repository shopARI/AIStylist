"""
Enhanced Session Memory System
Provides persistent memory across chat sessions with intelligent limits
"""

import logging
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger("services.memory.session_memory")

@dataclass
class ConversationTurn:
    """Single conversation turn"""
    timestamp: float
    user_message: str
    assistant_response: str
    intent: str
    products_found: int
    metadata: Dict[str, Any]

@dataclass 
class SessionSummary:
    """Summary of conversation patterns"""
    preferred_categories: List[str]
    preferred_colors: List[str]
    preferred_occasions: List[str]
    preferred_price_range: Dict[str, float]
    recent_topics: List[str]
    total_conversations: int
    last_active: float

class EnhancedSessionMemory:
    """
    Enhanced session memory with persistence and intelligent limits
    """
    
    def __init__(
        self,
        redis_client,
        max_turns_per_session: int = 50,
        max_session_age_days: int = 30,
        summary_after_turns: int = 10,
        enable_redis_storage: bool = False  # DISABLED by default
    ):
        self.redis = redis_client
        self.max_turns_per_session = max_turns_per_session
        self.max_session_age_days = max_session_age_days
        self.summary_after_turns = summary_after_turns
        self.enable_redis_storage = enable_redis_storage

        # In-memory fallback storage when Redis is disabled
        self.memory_store = {}  # session_id -> conversation_data

        storage_mode = "Redis" if enable_redis_storage else "Memory-only"
        logger.info(f"Enhanced session memory initialized ({storage_mode}, max_turns: {max_turns_per_session}, max_age: {max_session_age_days} days)")
    
    async def store_conversation(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        assistant_response: str,
        intent: str = "unknown",
        products_found: int = 0,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Store a conversation turn with intelligent memory management"""
        
        turn = ConversationTurn(
            timestamp=time.time(),
            user_message=user_message,
            assistant_response=assistant_response,
            intent=intent,
            products_found=products_found,
            metadata=metadata or {}
        )
        
        # Store in memory or Redis based on configuration
        session_key = f"session_memory:{session_id}"

        try:
            # Get existing conversation from memory or Redis
            if self.enable_redis_storage:
                conversation_data = await self.redis.get_json(session_key)
            else:
                conversation_data = self.memory_store.get(session_id)

            if not conversation_data:
                conversation_data = {
                    "user_id": user_id,
                    "created_at": time.time(),
                    "turns": [],
                    "summary": None
                }

            # Add new turn
            conversation_data["turns"].append(asdict(turn))
            conversation_data["last_active"] = time.time()

            # Apply memory limits
            await self._apply_memory_limits(conversation_data)

            # Generate summary if needed
            if len(conversation_data["turns"]) % self.summary_after_turns == 0:
                conversation_data["summary"] = await self._generate_summary(conversation_data["turns"])

            # Store based on configuration
            if self.enable_redis_storage:
                # Store to Redis (30 day TTL)
                await self.redis.set_json(
                    session_key,
                    conversation_data,
                    ttl=self.max_session_age_days * 24 * 3600
                )
                logger.debug(f"Stored conversation turn to Redis for session {session_id}")
            else:
                # Store to memory only (no Redis)
                self.memory_store[session_id] = conversation_data
                logger.debug(f"Stored conversation turn to memory for session {session_id} (Redis storage disabled)")

            logger.info(f"Stored conversation turn for session {session_id} (total turns: {len(conversation_data['turns'])})")

        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
    
    async def get_session_context(
        self,
        session_id: str,
        context_turns: int = 5
    ) -> str:
        """Get recent conversation context for the session"""

        session_key = f"session_memory:{session_id}"

        try:
            # Get from memory or Redis based on configuration
            if self.enable_redis_storage:
                conversation_data = await self.redis.get_json(session_key)
            else:
                conversation_data = self.memory_store.get(session_id)

            if not conversation_data:
                return ""
            
            turns = conversation_data.get("turns", [])
            summary = conversation_data.get("summary", {})
            
            context_parts = []
            
            # Add session summary if available
            if summary:
                context_parts.append("Previous conversation patterns:")
                if summary.get("preferred_categories"):
                    context_parts.append(f"- Often looks for: {', '.join(summary['preferred_categories'][:3])}")
                if summary.get("preferred_colors"):
                    context_parts.append(f"- Preferred colors: {', '.join(summary['preferred_colors'][:3])}")
                if summary.get("recent_topics"):
                    context_parts.append(f"- Recent interests: {', '.join(summary['recent_topics'][:3])}")
            
            # Add recent conversation turns
            recent_turns = turns[-context_turns:] if turns else []
            if recent_turns:
                context_parts.append("Recent conversation:")
                for turn in recent_turns:
                    context_parts.append(f"User: {turn['user_message'][:100]}...")
                    context_parts.append(f"Assistant: {turn['assistant_response'][:100]}...")
            
            return " ".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error getting session context: {e}")
            return ""
    
    async def get_user_preferences(
        self,
        session_id: str,
        user_id: str = None
    ) -> Dict[str, Any]:
        """Extract user preferences from conversation history"""

        session_key = f"session_memory:{session_id}"

        try:
            # Get from memory or Redis based on configuration
            if self.enable_redis_storage:
                conversation_data = await self.redis.get_json(session_key)
            else:
                conversation_data = self.memory_store.get(session_id)

            if not conversation_data:
                return {}
            
            summary = conversation_data.get("summary", {})
            if summary:
                return {
                    "categories": summary.get("preferred_categories", []),
                    "colors": summary.get("preferred_colors", []),
                    "occasions": summary.get("preferred_occasions", []),
                    "price_range": summary.get("preferred_price_range", {})
                }
            
            # Extract from recent turns if no summary
            preferences = {"categories": [], "colors": [], "occasions": []}
            turns = conversation_data.get("turns", [])
            
            for turn in turns[-10:]:  # Last 10 turns
                metadata = turn.get("metadata", {})
                if metadata.get("parameters"):
                    params = metadata["parameters"]
                    if params.get("categories"):
                        preferences["categories"].extend(params["categories"])
                    if params.get("colors"):
                        preferences["colors"].extend(params["colors"])
                    if params.get("occasions"):
                        preferences["occasions"].extend(params["occasions"])
            
            # Remove duplicates and limit
            for key in preferences:
                if isinstance(preferences[key], list):
                    preferences[key] = list(set(preferences[key]))[:5]
            
            return preferences
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}
    
    async def _apply_memory_limits(self, conversation_data: Dict[str, Any]) -> None:
        """Apply memory limits to prevent unbounded growth"""
        
        turns = conversation_data.get("turns", [])
        
        # Remove old turns if exceeding limit
        if len(turns) > self.max_turns_per_session:
            # Keep most recent turns and important ones
            recent_turns = turns[-self.max_turns_per_session//2:]
            
            # Try to keep turns with high product counts (important searches)
            important_turns = [
                turn for turn in turns[:-self.max_turns_per_session//2]
                if turn.get("products_found", 0) > 3
            ]
            
            conversation_data["turns"] = important_turns[-10:] + recent_turns
            logger.info(f"Applied memory limits: kept {len(conversation_data['turns'])} turns")
    
    async def _generate_summary(self, turns: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate intelligent summary of conversation patterns"""
        
        try:
            categories = []
            colors = []
            occasions = []
            topics = []
            price_ranges = []
            
            for turn in turns:
                # Extract from metadata
                metadata = turn.get("metadata", {})
                params = metadata.get("parameters", {})
                
                if params.get("categories"):
                    categories.extend(params["categories"])
                if params.get("colors"):
                    colors.extend(params["colors"])
                if params.get("occasions"):
                    occasions.extend(params["occasions"])
                
                # Extract topics from user messages
                user_msg = turn.get("user_message", "").lower()
                if "wedding" in user_msg:
                    topics.append("weddings")
                elif "work" in user_msg or "office" in user_msg:
                    topics.append("work")
                elif "casual" in user_msg:
                    topics.append("casual")
                elif "party" in user_msg or "night out" in user_msg:
                    topics.append("party")
            
            # Count frequencies and get top preferences
            def get_top_items(items: List[str], limit: int = 5) -> List[str]:
                from collections import Counter
                if not items:
                    return []
                return [item for item, count in Counter(items).most_common(limit)]
            
            summary = {
                "preferred_categories": get_top_items(categories),
                "preferred_colors": get_top_items(colors),
                "preferred_occasions": get_top_items(occasions),
                "recent_topics": get_top_items(topics, 3),
                "total_conversations": len(turns),
                "last_active": time.time()
            }
            
            logger.info(f"Generated conversation summary: {len(categories)} categories, {len(colors)} colors mentioned")
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {}
    
    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get session statistics"""

        session_key = f"session_memory:{session_id}"

        try:
            # Get from memory or Redis based on configuration
            if self.enable_redis_storage:
                conversation_data = await self.redis.get_json(session_key)
            else:
                conversation_data = self.memory_store.get(session_id)

            if not conversation_data:
                return {"exists": False}
            
            turns = conversation_data.get("turns", [])
            summary = conversation_data.get("summary", {})
            
            return {
                "exists": True,
                "total_turns": len(turns),
                "created_at": conversation_data.get("created_at"),
                "last_active": conversation_data.get("last_active"),
                "has_summary": bool(summary),
                "preferred_categories": summary.get("preferred_categories", [])[:3],
                "recent_activity": len([
                    t for t in turns 
                    if t.get("timestamp", 0) > time.time() - 3600  # Last hour
                ])
            }
            
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {"exists": False, "error": str(e)}

# Global instance
_session_memory = None

def get_enhanced_session_memory(redis_client) -> EnhancedSessionMemory:
    """Get or create the global enhanced session memory instance"""
    global _session_memory
    if _session_memory is None:
        _session_memory = EnhancedSessionMemory(redis_client)
    return _session_memory