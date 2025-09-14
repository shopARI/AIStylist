"""
Unified Memory Coordinator - Orchestrates all memory systems
Integrates session memory, user memory, CAMEL vector memory, and agent memory
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple

from services.memory.session_memory import get_enhanced_session_memory, ConversationTurn
from services.memory.user_memory import get_cross_session_user_memory, UserProfile
from services.memory.camel_vector_memory import get_camel_vector_memory, ConversationContext

logger = logging.getLogger("services.memory.coordinator")

class UnifiedMemoryCoordinator:
    """
    Central coordinator for all memory systems in the ARI Fashion Stylist.
    
    Manages:
    - Session Memory: Recent conversation context within a session
    - User Memory: Cross-session user preferences and patterns  
    - Vector Memory: Semantic long-term conversation storage
    - Agent Memory: CAMEL agent learning and pattern recognition
    
    Provides unified interface for storing and retrieving all types of memory.
    """
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        
        # Initialize all memory components
        self.session_memory = get_enhanced_session_memory(redis_client)
        self.user_memory = get_cross_session_user_memory(redis_client)
        self.vector_memory = get_camel_vector_memory(redis_client)
        
        logger.info("Unified Memory Coordinator initialized with all memory systems")
    
    async def store_conversation(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        assistant_response: str,
        intent: str,
        extracted_params: Dict[str, Any],
        products_found: int,
        metadata: Dict[str, Any] = None,
        user_satisfaction: Optional[float] = None
    ) -> bool:
        """
        Store conversation across all memory systems.
        This is the main entry point for memory storage.
        """
        metadata = metadata or {}
        current_time = time.time()
        
        try:
            # Prepare tasks for parallel execution
            tasks = []
            
            # 1. Store in session memory (enhanced conversational memory)
            session_task = self.session_memory.store_conversation(
                session_id=session_id,
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                intent=intent,
                products_found=products_found,
                metadata=metadata
            )
            tasks.append(("session", session_task))
            
            # 2. Update user memory (cross-session preferences)
            if user_id and user_id != "anonymous":
                user_task = self.user_memory.update_user_preferences(
                    user_id=user_id,
                    session_id=session_id,
                    extracted_params=extracted_params,
                    context=f"{user_message[:200]}..."
                )
                tasks.append(("user", user_task))
            
            # 3. Store in vector memory (semantic long-term storage)
            vector_context = ConversationContext(
                session_id=session_id,
                user_id=user_id or "anonymous",
                query=user_message,
                intent=intent,
                extracted_params=extracted_params,
                products_found=products_found,
                user_satisfaction=user_satisfaction,
                timestamp=current_time,
                metadata=metadata
            )
            vector_task = self.vector_memory.store_conversation_context(vector_context)
            tasks.append(("vector", vector_task))
            
            # Execute all storage tasks
            success_count = 0
            for task_name, task in tasks:
                try:
                    result = await task
                    if result:
                        success_count += 1
                    logger.debug(f"{task_name} memory storage: {'success' if result else 'failed'}")
                except Exception as e:
                    logger.error(f"Error in {task_name} memory storage: {e}")
            
            overall_success = success_count >= 2  # Success if at least 2/3 systems work
            
            logger.info(f"Conversation stored across {success_count}/{len(tasks)} memory systems")
            return overall_success
            
        except Exception as e:
            logger.error(f"Error in unified memory storage: {e}")
            return False
    
    async def get_enhanced_context(
        self,
        session_id: str,
        user_id: str,
        current_query: str,
        intent: str = None,
        include_similar_conversations: bool = True,
        include_user_preferences: bool = True,
        max_similar_contexts: int = 3
    ) -> Dict[str, Any]:
        """
        Get comprehensive context from all memory systems.
        This is the main entry point for memory retrieval.
        
        Returns unified context combining:
        - Recent session context  
        - User preferences and patterns
        - Semantically similar past conversations
        - Conversation analysis and insights
        """
        try:
            context = {
                'session_context': {},
                'user_context': {},
                'similar_conversations': [],
                'memory_insights': {},
                'timestamp': time.time()
            }
            
            # Prepare parallel retrieval tasks
            tasks = []
            
            # 1. Get session context (recent conversation in this session)
            session_task = self.session_memory.get_session_context(session_id, context_turns=5)
            tasks.append(("session", session_task))
            
            # 2. Get user context (cross-session preferences and patterns)  
            if include_user_preferences and user_id and user_id != "anonymous":
                user_task = self.user_memory.get_user_context_for_session(
                    user_id=user_id,
                    session_id=session_id,
                    include_style_evolution=True
                )
                tasks.append(("user", user_task))
            
            # 3. Get similar conversations (semantic search)
            if include_similar_conversations:
                similar_task = self.vector_memory.retrieve_relevant_contexts(
                    query=current_query,
                    user_id=user_id or "anonymous",
                    intent=intent,
                    limit=max_similar_contexts
                )
                tasks.append(("similar", similar_task))
            
            # Execute retrieval tasks
            for task_name, task in tasks:
                try:
                    result = await task
                    if task_name == "session":
                        context['session_context'] = result or ""
                    elif task_name == "user":
                        context['user_context'] = result or {}
                    elif task_name == "similar":
                        context['similar_conversations'] = result or []
                    
                    logger.debug(f"{task_name} context retrieved successfully")
                    
                except Exception as e:
                    logger.error(f"Error retrieving {task_name} context: {e}")
                    # Set empty defaults on error
                    if task_name == "session":
                        context['session_context'] = ""
                    elif task_name == "user":
                        context['user_context'] = {}
                    elif task_name == "similar":
                        context['similar_conversations'] = []
            
            # 4. Generate memory insights
            context['memory_insights'] = await self._generate_memory_insights(
                context['user_context'],
                context['similar_conversations'],
                current_query
            )
            
            logger.info(f"Enhanced context retrieved - Session: {bool(context['session_context'])}, "
                       f"User: {len(context['user_context'])}, Similar: {len(context['similar_conversations'])}")
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting enhanced context: {e}")
            return {
                'session_context': "",
                'user_context': {},
                'similar_conversations': [],
                'memory_insights': {},
                'timestamp': time.time(),
                'error': str(e)
            }
    
    async def get_user_preference_suggestions(
        self,
        user_id: str,
        current_query: str,
        category_filter: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Get intelligent preference suggestions based on user history.
        Combines user memory and similar conversation patterns.
        """
        try:
            # Get direct user preferences
            user_suggestions = await self.user_memory.get_preference_suggestions(
                user_id=user_id,
                current_query=current_query,
                category_filter=category_filter
            )
            
            # Enhance with similar conversation patterns
            if user_id and user_id != "anonymous":
                similar_contexts = await self.vector_memory.retrieve_relevant_contexts(
                    query=current_query,
                    user_id=user_id,
                    limit=5
                )
                
                # Extract additional suggestions from similar conversations
                for context in similar_contexts:
                    for category, values in context.extracted_params.items():
                        if category_filter and category not in category_filter:
                            continue
                        
                        if category not in user_suggestions:
                            user_suggestions[category] = []
                        
                        if isinstance(values, list):
                            for value in values:
                                if isinstance(value, str) and value not in user_suggestions[category]:
                                    user_suggestions[category].append(value)
                        elif isinstance(values, str) and values not in user_suggestions[category]:
                            user_suggestions[category].append(values)
                        
                        # Limit suggestions per category
                        user_suggestions[category] = user_suggestions[category][:7]
            
            logger.info(f"Generated preference suggestions for user {user_id}: {len(user_suggestions)} categories")
            return user_suggestions
            
        except Exception as e:
            logger.error(f"Error getting preference suggestions: {e}")
            return {}
    
    async def analyze_user_behavior(
        self,
        user_id: str,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Comprehensive user behavior analysis across all memory systems.
        """
        try:
            if not user_id or user_id == "anonymous":
                return {}
            
            analysis = {
                'user_id': user_id,
                'analysis_period_days': days_back,
                'conversation_patterns': {},
                'preference_evolution': {},
                'satisfaction_trends': {},
                'memory_summary': {}
            }
            
            # Get user conversation patterns from vector memory
            analysis['conversation_patterns'] = await self.vector_memory.get_user_conversation_patterns(
                user_id=user_id,
                days_back=days_back
            )
            
            # Get user context for preference analysis
            user_context = await self.user_memory.get_user_context_for_session(
                user_id=user_id,
                session_id="",  # Analysis mode
                include_style_evolution=True
            )
            
            if user_context:
                analysis['preference_evolution'] = {
                    'active_preferences': user_context.get('active_preferences', {}),
                    'style_evolution': user_context.get('style_evolution', []),
                    'interaction_patterns': user_context.get('interaction_patterns', {}),
                    'user_tenure_days': user_context.get('user_tenure_days', 0)
                }
            
            # Memory system summary
            analysis['memory_summary'] = {
                'total_conversations': analysis['conversation_patterns'].get('total_conversations', 0),
                'active_preference_categories': len(user_context.get('active_preferences', {})),
                'recent_activity_score': analysis['conversation_patterns'].get('avg_products_per_query', 0),
                'user_tenure_days': user_context.get('user_tenure_days', 0)
            }
            
            logger.info(f"Completed behavior analysis for user {user_id}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing user behavior: {e}")
            return {}
    
    async def cleanup_old_memories(
        self,
        max_age_days: int = 90,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Clean up old memories across all systems.
        Returns count of items cleaned per system.
        """
        cleanup_stats = {
            'session_memory': 0,
            'user_memory': 0,
            'vector_memory': 0,
            'errors': 0
        }
        
        try:
            cutoff_time = time.time() - (max_age_days * 24 * 3600)
            
            if not dry_run:
                logger.info(f"Starting memory cleanup (max_age: {max_age_days} days)")
            else:
                logger.info(f"Dry run memory cleanup analysis (max_age: {max_age_days} days)")
            
            # Note: Specific cleanup implementations would depend on the memory systems
            # This is a framework for coordinated cleanup across all memory types
            
            # Session memory cleanup would be handled by individual TTLs in Redis
            # User memory has built-in preference cleanup
            # Vector memory cleanup would require specific implementation
            
            logger.info(f"Memory cleanup completed: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
            cleanup_stats['errors'] += 1
            return cleanup_stats
    
    async def _generate_memory_insights(
        self,
        user_context: Dict[str, Any],
        similar_conversations: List[ConversationContext],
        current_query: str
    ) -> Dict[str, Any]:
        """Generate insights from memory data to inform current interaction"""
        insights = {
            'user_familiarity': 'new',  # new, returning, frequent
            'preference_strength': 'unknown',  # weak, moderate, strong
            'query_similarity_score': 0.0,
            'recommended_approach': 'standard',  # standard, personalized, exploratory
            'context_richness': 'low'  # low, medium, high
        }
        
        try:
            # Determine user familiarity
            if user_context:
                tenure_days = user_context.get('user_tenure_days', 0)
                total_sessions = user_context.get('total_sessions', 0)
                
                if tenure_days > 30 and total_sessions > 10:
                    insights['user_familiarity'] = 'frequent'
                elif tenure_days > 7 and total_sessions > 3:
                    insights['user_familiarity'] = 'returning'
            
            # Assess preference strength
            active_prefs = user_context.get('active_preferences', {})
            if active_prefs:
                avg_confidence = sum(
                    sum(p['confidence'] for p in prefs) / len(prefs)
                    for prefs in active_prefs.values()
                    if prefs
                ) / len(active_prefs) if active_prefs else 0
                
                if avg_confidence > 0.7:
                    insights['preference_strength'] = 'strong'
                elif avg_confidence > 0.4:
                    insights['preference_strength'] = 'moderate'
                else:
                    insights['preference_strength'] = 'weak'
            
            # Calculate query similarity
            if similar_conversations:
                scores = [
                    ctx.metadata.get('similarity_score', 0) 
                    for ctx in similar_conversations
                ]
                insights['query_similarity_score'] = sum(scores) / len(scores) if scores else 0
            
            # Recommend approach based on insights
            if (insights['user_familiarity'] == 'frequent' and 
                insights['preference_strength'] == 'strong'):
                insights['recommended_approach'] = 'personalized'
            elif (insights['user_familiarity'] == 'new' and 
                  insights['query_similarity_score'] < 0.3):
                insights['recommended_approach'] = 'exploratory'
            
            # Assess overall context richness
            context_score = 0
            if user_context.get('active_preferences'):
                context_score += 1
            if similar_conversations:
                context_score += 1
            if insights['query_similarity_score'] > 0.5:
                context_score += 1
            
            if context_score >= 2:
                insights['context_richness'] = 'high'
            elif context_score == 1:
                insights['context_richness'] = 'medium'
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating memory insights: {e}")
            return insights

# Global instance
_memory_coordinator = None

def get_unified_memory_coordinator(redis_client) -> UnifiedMemoryCoordinator:
    """Get or create the global unified memory coordinator"""
    global _memory_coordinator
    if _memory_coordinator is None:
        _memory_coordinator = UnifiedMemoryCoordinator(redis_client)
    return _memory_coordinator