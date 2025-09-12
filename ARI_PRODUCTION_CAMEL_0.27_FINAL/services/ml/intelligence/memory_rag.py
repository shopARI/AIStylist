"""
Memory RAG Intelligence for Both Agents

Provides memory and context intelligence to both CypherBot and VibeBot.
NEVER returns products - only relevant memories and preferences.

Based on memory_rag_recommender.py patterns.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from datetime import datetime

logger = logging.getLogger("intelligence.memory_rag")


class MemoryRAGIntelligence:
    """
    Provides memory-enhanced intelligence for both battle agents.
    
    Extracts relevant context, preferences, and patterns from user memory.
    CRITICAL: Returns memory context, NEVER products!
    """
    
    def __init__(
        self,
        product_kg: Any,
        user_kg: Optional[Any] = None,
        memory_setup_func: Optional[Any] = None,
        token_limit: int = 2048
    ):
        """
        Initialize memory RAG intelligence system.
        
        Args:
            product_kg: Product knowledge graph
            user_kg: User knowledge graph
            memory_setup_func: Function to setup CAMEL memory
            token_limit: Token limit for context
        """
        logger.info("Initializing Memory RAG Intelligence")
        
        self.product_kg = product_kg
        self.user_kg = user_kg
        self.memory_setup_func = memory_setup_func
        self.token_limit = token_limit
        
        # Memory instance
        self.memory = None
        self.memory_manager = None
        
        # Cache for processed memories
        self.memory_cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        logger.info("Memory RAG Intelligence initialized")
    
    async def _ensure_memory_initialized(self):
        """Ensure memory is initialized for async operations."""
        if self.memory is None and self.memory_setup_func:
            try:
                if asyncio.iscoroutinefunction(self.memory_setup_func):
                    self.memory = await self.memory_setup_func()
                else:
                    self.memory = await asyncio.to_thread(self.memory_setup_func)
                
                logger.info("Memory initialized for RAG intelligence")
                
                # Try to import memory manager  
                try:
                    from services.memory.manager import MemoryManager
                    self.memory_manager = MemoryManager(self.product_kg)
                except ImportError:
                    logger.warning("MemoryManager not available")
                except Exception as e:
                    logger.warning(f"MemoryManager initialization failed: {e}")
                    self.memory_manager = None
                    
            except Exception as e:
                logger.error(f"Error initializing memory: {e}")
    
    async def get_relevant_context(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        query: Optional[str] = None,
        k: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Get relevant context from memory.
        
        Args:
            user_id: User ID
            session_id: Session ID
            query: Search query
            k: Number of memories to retrieve
            
        Returns:
            Context intelligence (NOT products!)
        """
        await self._ensure_memory_initialized()
        
        if not self.memory:
            logger.warning("Memory not available for context extraction")
            return None
        
        # Check cache
        cache_key = f"{user_id}:{session_id}:{query}"
        if cache_key in self.memory_cache:
            cached = self.memory_cache[cache_key]
            if (datetime.now() - cached['timestamp']).seconds < self.cache_ttl:
                return cached['data']
        
        try:
            # Get memory context
            memory_context = await self._get_memory_context(query)
            
            if not memory_context:
                return None
            
            # Extract intelligence from memory
            categories, tags, preferences, interactions = self._extract_memory_information(
                memory_context
            )
            
            # Build context intelligence
            context = {
                "memories": memory_context[:k],
                "preferences": {
                    "categories": Counter(categories).most_common(5),
                    "tags": Counter(tags).most_common(5),
                    "extracted": preferences
                },
                "interactions": interactions[:10],  # Recent 10 interactions
                "memory_count": len(memory_context),
                "confidence": 0.9 if memory_context else 0.3
            }
            
            # Cache the result
            self.memory_cache[cache_key] = {
                'data': context,
                'timestamp': datetime.now()
            }

            async def _cleanup_cache(self):
                now = datetime.now()
                expired = [k for k, v in self.memory_cache.items() 
                        if (now - v['timestamp']).seconds > self.cache_ttl]
                for key in expired:
                    del self.memory_cache[key]
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting relevant context: {e}")
            return None
    
    async def get_relevant_contexts_batch(
        self,
        queries: List[Tuple[Optional[str], Optional[str], Optional[str]]]
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Get contexts for multiple queries in batch.
        
        Args:
            queries: List of (user_id, session_id, query) tuples
            
        Returns:
            List of context dictionaries
        """
        # Process in parallel
        tasks = []
        for user_id, session_id, query in queries:
            task = self.get_relevant_context(user_id, session_id, query)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        final_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch context error: {result}")
                final_results.append(None)
            else:
                final_results.append(result)
        
        return final_results


    async def get_relevant_memories(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        query: Optional[str] = None,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get relevant memories for a query.
        
        Args:
            user_id: User ID
            session_id: Session ID
            query: Search query
            k: Number of memories
            
        Returns:
            List of relevant memories
        """
        context = await self.get_relevant_context(user_id, session_id, query, k)
        
        if context:
            return context.get("memories", [])
        
        return []
    
    async def get_session_context(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get context for a specific session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session context intelligence
        """
        if not session_id:
            return None
        
        try:
            # Get session memories
            memories = await self.get_relevant_memories(
                session_id=session_id,
                k=20
            )
            
            if not memories:
                return None
            
            # Analyze session flow
            intent = self._detect_session_intent(memories)
            stage = self._detect_conversation_stage(memories)
            topics = self._extract_topics(memories)
            mood = self._detect_mood(memories)
            
            return {
                "intent": intent,
                "conversation_stage": stage,
                "topics": topics,
                "mood": mood,
                "message_count": len(memories),
                "confidence": 0.8
            }
            
        except Exception as e:
            logger.error(f"Error getting session context: {e}")
            return None
    
    async def get_user_preferences(
        self,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get user preferences from memory.
        
        Args:
            user_id: User ID
            
        Returns:
            User preferences intelligence
        """
        if not user_id:
            return None
        
        try:
            # Get user memories
            memories = await self.get_relevant_memories(
                user_id=user_id,
                k=50  # More memories for preference extraction
            )
            
            if not memories:
                # Try to get from user knowledge graph
                if self.user_kg and hasattr(self.user_kg, 'get_user_preferences'):
                    return await self.user_kg.get_user_preferences(user_id)
                return None
            
            # Extract preferences from memories
            categories, tags, preferences, _ = self._extract_memory_information(memories)
            
            # Get top preferences
            preferred_categories = [cat for cat, _ in Counter(categories).most_common(5)]
            preferred_tags = [tag for tag, _ in Counter(tags).most_common(5)]
            
            # Extract style preferences
            styles = []
            brands = []
            colors = []
            avoid_list = []
            budget_range = {"min": float('inf'), "max": 0}
            
            for pref_type, pref_value in preferences.items():
                if pref_type == "style":
                    styles.append(pref_value)
                elif pref_type == "brand":
                    brands.append(pref_value)
                elif pref_type == "color":
                    colors.append(pref_value)
                elif pref_type == "avoid":
                    avoid_list.append(pref_value)
                elif pref_type == "budget":
                    # Parse budget values
                    try:
                        value = float(pref_value)
                        budget_range["min"] = min(budget_range["min"], value)
                        budget_range["max"] = max(budget_range["max"], value)
                    except (ValueError, TypeError):
                        pass
            
            # Fix budget range if not set
            if budget_range["min"] == float('inf'):
                budget_range = {"min": 0, "max": 1000}
            
            return {
                "preferred_styles": list(set(styles))[:5],
                "preferred_brands": list(set(brands))[:5],
                "preferred_categories": preferred_categories,
                "preferred_colors": list(set(colors))[:5],
                "preferred_tags": preferred_tags,
                "avoid_list": list(set(avoid_list)),
                "budget_range": budget_range,
                "confidence": 0.85
            }
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return None
    
    async def _get_memory_context(
        self,
        query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get context from memory system."""
        if not self.memory:
            return []
        
        try:
            # Skip memory manager - using direct CAMEL memory access only
            # The memory manager causes OpenAI API format errors
            # if self.memory_manager and hasattr(self.memory_manager, 'get_context'):
            
            # Fallback to direct memory access
            if hasattr(self.memory, 'get_context'):
                # CAMEL memory.get_context() returns (openai_messages, token_count)
                openai_messages, _ = await asyncio.to_thread(self.memory.get_context)
                
                # Convert OpenAI messages to our memory context format
                context = []
                for msg in openai_messages:
                    context.append({
                        'content': msg.get('content', ''),
                        'role': msg.get('role', 'user'),
                        'timestamp': datetime.now().isoformat()
                    })
                return context
            
            return []
            
        except Exception as e:
            # Check if it's the OpenAI API format error
            if "'$.input' is invalid" in str(e):
                logger.warning(f"OpenAI API format error in memory context, returning empty context: {e}")
                return []
            else:
                logger.error(f"Error getting memory context: {e}")
                return []
    
    def _extract_memory_information(
        self,
        memory_context: List[Dict[str, Any]]
    ) -> Tuple[List[str], List[str], Dict[str, str], List[Dict[str, Any]]]:
        """
        Extract information from memory context.
        
        Based on memory_rag_recommender.py _extract_memory_information.
        """
        categories = []
        tags = []
        preferences = {}
        interactions = []
        
        for context_item in memory_context:
            content = context_item.get('content', '')

        # may need to change this way:    
        # pattern = r'\(ID:\s*([A-Za-z0-9\-]+)\)'
        # matches = re.findall(pattern, content)

            # Extract product interactions
            if "(ID: " in content:
                product_id_start = content.find("(ID: ")
                product_id_end = content.find(")", product_id_start)
                if product_id_end >= 0:
                    product_id = content[product_id_start + 5:product_id_end]
                    
                    # Determine interaction type
                    interaction_type = "viewed"
                    if "purchased" in content.lower():
                        interaction_type = "purchased"
                    elif "liked" in content.lower():
                        interaction_type = "liked"
                    
                    interactions.append({
                        "product_id": product_id,
                        "type": interaction_type,
                        "timestamp": context_item.get('timestamp')
                    })
            
            # Extract categories
            if "Categories: " in content:
                cat_start = content.find("Categories: ")
                cat_end = content.find(".", cat_start)
                if cat_end >= 0:
                    cat_list = content[cat_start + 12:cat_end].split(', ')
                    categories.extend(cat_list)
            
            # Extract tags
            if "Tags: " in content:
                tag_start = content.find("Tags: ")
                tag_end = content.find(".", tag_start)
                if tag_end >= 0:
                    tag_list = content[tag_start + 6:tag_end].split(', ')
                    tags.extend(tag_list)
            
            # Extract preferences
            if "preference: " in content:
                pref_start = content.find("preference: ")
                pref_end = content.find(" = ", pref_start)
                if pref_end >= 0:
                    pref_type = content[pref_start + 12:pref_end].strip()
                    
                    value_end = content.find(".", pref_end)
                    if value_end < 0:
                        value_end = len(content)
                    value = content[pref_end + 3:value_end].strip()
                    
                    preferences[pref_type] = value
        
        return categories, tags, preferences, interactions
    
    def _detect_session_intent(self, memories: List[Dict[str, Any]]) -> str:
        """Detect intent from session memories."""
        if not memories:
            return "browsing"
        
        # Analyze content for intent keywords
        content = " ".join(m.get('content', '') for m in memories).lower()
        
        if any(word in content for word in ["wedding", "party", "event", "occasion"]):
            return "occasion_shopping"
        elif any(word in content for word in ["gift", "present", "birthday"]):
            return "gift_shopping"
        elif any(word in content for word in ["wardrobe", "collection", "closet"]):
            return "wardrobe_building"
        elif any(word in content for word in ["style", "look", "outfit"]):
            return "style_discovery"
        else:
            return "general_shopping"
    
    def _detect_conversation_stage(self, memories: List[Dict[str, Any]]) -> str:
        """Detect conversation stage from memories."""
        count = len(memories)
        
        if count < 3:
            return "opening"
        elif count < 10:
            return "exploration"
        elif count < 20:
            return "consideration"
        else:
            return "decision"
    
    def _extract_topics(self, memories: List[Dict[str, Any]]) -> List[str]:
        """Extract topics from memories."""
        # Simplified topic extraction
        topics = set()
        
        for memory in memories:
            content = memory.get('content', '').lower()
            
            # Extract product-related topics
            if "dress" in content:
                topics.add("dresses")
            if "shoe" in content:
                topics.add("shoes")
            if "bag" in content or "purse" in content:
                topics.add("bags")
            if "jewelry" in content or "accessory" in content:
                topics.add("accessories")
            
            # Extract style topics
            if "casual" in content:
                topics.add("casual_style")
            if "formal" in content:
                topics.add("formal_style")
            
        return list(topics)[:5]
    
    def _detect_mood(self, memories: List[Dict[str, Any]]) -> str:
        """Detect user mood from memories."""
        if not memories:
            return "neutral"
        
        # Analyze recent memories for mood indicators
        recent_content = " ".join(
            m.get('content', '') for m in memories[-5:]
        ).lower()
        
        # Positive indicators
        positive_words = ["love", "great", "perfect", "excellent", "amazing", "beautiful"]
        positive_count = sum(1 for word in positive_words if word in recent_content)
        
        # Negative indicators
        negative_words = ["don't", "not", "bad", "ugly", "hate", "terrible"]
        negative_count = sum(1 for word in negative_words if word in recent_content)
        
        # Determine mood
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    async def add_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str
    ) -> bool:
        """
        Record an interaction for learning.
        
        Args:
            user_id: User ID
            product_id: Product ID
            interaction_type: Type of interaction
            
        Returns:
            Success status
        """
        # This would update memory with interaction
        # Implementation depends on memory system
        logger.info(f"Recording interaction: {user_id} {interaction_type} {product_id}")
        return True