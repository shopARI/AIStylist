"""
Cross-Session User Memory - Persistent user preferences and context
Solves the session isolation problem by maintaining user state across all sessions
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict

logger = logging.getLogger("services.memory.user_memory")

@dataclass
class UserPreference:
    """Single user preference with confidence tracking"""
    value: str
    category: str  # 'color', 'style', 'occasion', 'brand', etc.
    confidence: float  # 0.0-1.0 based on frequency and recency
    first_mentioned: float
    last_mentioned: float
    mention_count: int
    contexts: List[str]  # Contexts where this was mentioned

@dataclass
class UserProfile:
    """Complete user profile with persistent preferences"""
    user_id: str
    preferences: Dict[str, UserPreference]
    conversation_history: List[str]  # Recent session IDs
    style_evolution: List[Dict[str, Any]]  # How preferences change over time
    interaction_patterns: Dict[str, Any]  # Behavioral patterns
    created_at: float
    updated_at: float

class CrossSessionUserMemory:
    """
    Maintains persistent user memory across all sessions.
    Integrates with CAMEL memory systems for intelligent preference tracking.
    """
    
    def __init__(
        self,
        redis_client,
        max_user_history: int = 100,
        preference_decay_days: int = 90,
        min_confidence_threshold: float = 0.3,
        enable_redis_storage: bool = False  # DISABLED by default
    ):
        self.redis = redis_client
        self.max_user_history = max_user_history
        self.preference_decay_days = preference_decay_days
        self.min_confidence_threshold = min_confidence_threshold
        self.enable_redis_storage = enable_redis_storage

        # In-memory fallback storage when Redis is disabled
        self.memory_store = {}  # user_id -> profile_data

        storage_mode = "Redis" if enable_redis_storage else "Memory-only"
        logger.info(f"Cross-session user memory initialized ({storage_mode}, max_history: {max_user_history})")
    
    async def update_user_preferences(
        self,
        user_id: str,
        session_id: str,
        extracted_params: Dict[str, Any],
        context: str = ""
    ) -> None:
        """
        Update user preferences from current interaction.
        Uses intelligent merging to build persistent user profile.
        """
        if not user_id or user_id == "anonymous":
            return
        
        user_key = f"user_memory:{user_id}"
        current_time = time.time()
        
        try:
            # Get existing user profile from memory or Redis
            if self.enable_redis_storage:
                profile_data = await self.redis.get_json(user_key)
            else:
                profile_data = self.memory_store.get(user_id)

            if not profile_data:
                profile = UserProfile(
                    user_id=user_id,
                    preferences={},
                    conversation_history=[],
                    style_evolution=[],
                    interaction_patterns={},
                    created_at=current_time,
                    updated_at=current_time
                )
            else:
                profile = UserProfile(**profile_data)
            
            # Update conversation history
            if session_id not in profile.conversation_history:
                profile.conversation_history.append(session_id)
                if len(profile.conversation_history) > self.max_user_history:
                    profile.conversation_history = profile.conversation_history[-self.max_user_history:]
            
            # Process extracted parameters
            preference_updates = []
            for category, values in extracted_params.items():
                if not values:
                    continue
                    
                # Handle both single values and lists
                if isinstance(values, str):
                    values = [values]
                elif not isinstance(values, list):
                    continue
                
                for value in values:
                    if not value or not isinstance(value, str):
                        continue
                    
                    preference_key = f"{category}:{value.lower()}"
                    
                    if preference_key in profile.preferences:
                        # Update existing preference - handle both dict and object formats
                        pref = profile.preferences[preference_key]

                        if isinstance(pref, dict):
                            # Convert dict to UserPreference object for consistency
                            pref = UserPreference(
                                value=pref.get('value', value.lower()),
                                category=pref.get('category', category),
                                confidence=pref.get('confidence', 0.5),
                                first_mentioned=pref.get('first_mentioned', current_time),
                                last_mentioned=pref.get('last_mentioned', current_time),
                                mention_count=pref.get('mention_count', 1),
                                contexts=pref.get('contexts', [])
                            )

                        pref.mention_count += 1
                        pref.last_mentioned = current_time
                        pref.contexts.append(context[:100])  # Limit context length
                        if len(pref.contexts) > 10:
                            pref.contexts = pref.contexts[-10:]  # Keep recent contexts

                        # Update confidence based on recency and frequency
                        pref.confidence = self._calculate_confidence(
                            pref.mention_count,
                            pref.first_mentioned,
                            pref.last_mentioned,
                            current_time
                        )

                        # Store back the updated object
                        profile.preferences[preference_key] = pref
                    else:
                        # Create new preference
                        profile.preferences[preference_key] = UserPreference(
                            value=value.lower(),
                            category=category,
                            confidence=0.5,  # Start with medium confidence
                            first_mentioned=current_time,
                            last_mentioned=current_time,
                            mention_count=1,
                            contexts=[context[:100]]
                        )
                    
                    preference_updates.append({
                        'category': category,
                        'value': value.lower(),
                        'timestamp': current_time
                    })
            
            # Add to style evolution if preferences updated
            if preference_updates:
                profile.style_evolution.append({
                    'timestamp': current_time,
                    'session_id': session_id,
                    'updates': preference_updates
                })
                if len(profile.style_evolution) > 50:
                    profile.style_evolution = profile.style_evolution[-50:]
            
            # Clean up old/low-confidence preferences
            await self._cleanup_preferences(profile, current_time)
            
            # Update profile metadata
            profile.updated_at = current_time

            # Store based on configuration
            if self.enable_redis_storage:
                # Store to Redis (long TTL for user memory)
                await self.redis.set_json(
                    user_key,
                    asdict(profile),
                    ttl=365 * 24 * 3600  # 1 year TTL
                )
                logger.debug(f"Stored user profile to Redis for {user_id}")
            else:
                # Store to memory only (no Redis)
                self.memory_store[user_id] = asdict(profile)
                logger.debug(f"Stored user profile to memory for {user_id} (Redis storage disabled)")

            logger.info(f"Updated user {user_id} preferences: {len(preference_updates)} updates")
            
        except Exception as e:
            logger.error(f"Error updating user preferences for {user_id}: {e}")
    
    async def get_user_context_for_session(
        self,
        user_id: str,
        session_id: str,
        include_style_evolution: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive user context to enhance current session.
        Returns preferences, patterns, and relevant history.
        """
        if not user_id or user_id == "anonymous":
            return {}
        
        user_key = f"user_memory:{user_id}"

        try:
            # Get from memory or Redis based on configuration
            if self.enable_redis_storage:
                profile_data = await self.redis.get_json(user_key)
            else:
                profile_data = self.memory_store.get(user_id)

            if not profile_data:
                return {}
            
            profile = UserProfile(**profile_data)
            current_time = time.time()
            
            # Get active preferences (above confidence threshold)
            active_preferences = {}
            for pref_key, pref in profile.preferences.items():
                # Handle both dict and UserPreference object formats
                if isinstance(pref, dict):
                    confidence = pref.get('confidence', 0.0)
                    category = pref.get('category', 'unknown')
                    value = pref.get('value', '')
                    mention_count = pref.get('mention_count', 1)
                    last_mentioned = pref.get('last_mentioned', current_time)
                else:
                    # UserPreference object
                    confidence = pref.confidence
                    category = pref.category
                    value = pref.value
                    mention_count = pref.mention_count
                    last_mentioned = pref.last_mentioned

                if confidence >= self.min_confidence_threshold:
                    if category not in active_preferences:
                        active_preferences[category] = []
                    active_preferences[category].append({
                        'value': value,
                        'confidence': confidence,
                        'mention_count': mention_count,
                        'recency_days': (current_time - last_mentioned) / 86400
                    })
            
            # Sort preferences by confidence within each category
            for category in active_preferences:
                active_preferences[category].sort(key=lambda x: x['confidence'], reverse=True)
            
            # Get recent style evolution
            recent_evolution = []
            if include_style_evolution:
                cutoff_time = current_time - (30 * 24 * 3600)  # Last 30 days
                recent_evolution = [
                    evo for evo in profile.style_evolution
                    if evo['timestamp'] > cutoff_time
                ]
            
            # Build interaction patterns summary
            patterns = self._analyze_interaction_patterns(profile)
            
            context = {
                'user_id': user_id,
                'active_preferences': active_preferences,
                'style_evolution': recent_evolution,
                'interaction_patterns': patterns,
                'total_sessions': len(profile.conversation_history),
                'user_tenure_days': (current_time - profile.created_at) / 86400,
                'last_active_days_ago': (current_time - profile.updated_at) / 86400
            }
            
            logger.info(f"Retrieved context for user {user_id}: {len(active_preferences)} preference categories")
            return context
            
        except Exception as e:
            logger.error(f"Error getting user context for {user_id}: {e}")
            return {}
    
    async def get_preference_suggestions(
        self,
        user_id: str,
        current_query: str,
        category_filter: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Get preference suggestions based on user history.
        Useful for auto-completing or suggesting parameters.
        """
        context = await self.get_user_context_for_session(user_id, "")
        if not context or not context.get('active_preferences'):
            return {}
        
        suggestions = {}
        active_prefs = context['active_preferences']
        
        for category, prefs in active_prefs.items():
            if category_filter and category not in category_filter:
                continue
            
            # Get top preferences for this category
            top_prefs = [p['value'] for p in prefs[:5] if p['confidence'] > 0.4]
            if top_prefs:
                suggestions[category] = top_prefs
        
        return suggestions
    
    def _calculate_confidence(
        self,
        mention_count: int,
        first_mentioned: float,
        last_mentioned: float,
        current_time: float
    ) -> float:
        """
        Calculate confidence score based on frequency and recency.
        Higher frequency and recent mentions = higher confidence.
        """
        # Frequency component (0.0-0.6)
        frequency_score = min(0.6, mention_count * 0.1)
        
        # Recency component (0.0-0.4)
        days_since_last = (current_time - last_mentioned) / 86400
        if days_since_last < 1:
            recency_score = 0.4
        elif days_since_last < 7:
            recency_score = 0.3
        elif days_since_last < 30:
            recency_score = 0.2
        elif days_since_last < 90:
            recency_score = 0.1
        else:
            recency_score = 0.0
        
        return min(1.0, frequency_score + recency_score)
    
    async def _cleanup_preferences(
        self,
        profile: UserProfile,
        current_time: float
    ) -> None:
        """Clean up old or low-confidence preferences"""
        cutoff_time = current_time - (self.preference_decay_days * 24 * 3600)
        
        keys_to_remove = []
        for pref_key, pref in profile.preferences.items():
            # Handle both dict and object formats
            if isinstance(pref, dict):
                last_mentioned = pref.get('last_mentioned', current_time)
                confidence = pref.get('confidence', 0.5)
            else:
                last_mentioned = pref.last_mentioned
                confidence = pref.confidence

            # Remove if too old and low confidence
            if (last_mentioned < cutoff_time and
                confidence < self.min_confidence_threshold):
                keys_to_remove.append(pref_key)
        
        for key in keys_to_remove:
            del profile.preferences[key]
        
        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} old preferences for user {profile.user_id}")
    
    def _analyze_interaction_patterns(
        self,
        profile: UserProfile
    ) -> Dict[str, Any]:
        """Analyze user interaction patterns for insights"""
        if not profile.style_evolution:
            return {}
        
        # Analyze preference categories over time
        category_trends = defaultdict(int)
        recent_updates = 0
        current_time = time.time()
        recent_cutoff = current_time - (7 * 24 * 3600)  # Last 7 days
        
        for evolution in profile.style_evolution:
            if evolution['timestamp'] > recent_cutoff:
                recent_updates += 1
            
            for update in evolution.get('updates', []):
                category_trends[update['category']] += 1
        
        return {
            'most_mentioned_categories': dict(Counter(category_trends).most_common(5)),
            'recent_activity_count': recent_updates,
            'total_preference_updates': len(profile.style_evolution),
            'session_count': len(profile.conversation_history)
        }

# Global instance
_user_memory = None

def get_cross_session_user_memory(redis_client) -> CrossSessionUserMemory:
    """Get or create the global cross-session user memory instance"""
    global _user_memory
    if _user_memory is None:
        _user_memory = CrossSessionUserMemory(redis_client)
    return _user_memory