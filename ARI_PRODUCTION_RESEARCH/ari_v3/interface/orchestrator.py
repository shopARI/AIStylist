"""
ARI V3 - Main Orchestrator

Main entry point for all user interactions.
Routes to appropriate handler based on intent.

Based on Section 0.5.3 of the pseudocode.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from .types import (
    ARIResponse,
    IntentResult,
    ResponseType,
    SearchIntent,
)
from .intent_detector import (
    DetectionStrategy,
    HybridIntentDetector,
    get_intent_detector,
)
from .conversation_handler import ConversationHandler, Message, MessageRole

if TYPE_CHECKING:
    from ari_v3.navigation.navigation_intelligence import NavigationIntelligence
    from ari_v3.onboarding.profile import OnboardingProfile
    from qdrant_client import AsyncQdrantClient
    from openai import OpenAI

logger = logging.getLogger(__name__)

# Lazy-loaded module references (avoid import on every call)
_ARIEvaluator = None
_NarrativeLLM = None


def _get_evaluator_class():
    """Lazy load ARIEvaluator to avoid import overhead."""
    global _ARIEvaluator
    if _ARIEvaluator is None:
        try:
            from ari_v3.judge import ARIEvaluator
            _ARIEvaluator = ARIEvaluator
        except ImportError:
            _ARIEvaluator = False  # Mark as unavailable
    return _ARIEvaluator if _ARIEvaluator else None


def _get_narrative_class():
    """Lazy load NarrativeLLM to avoid import overhead."""
    global _NarrativeLLM
    if _NarrativeLLM is None:
        try:
            from ari_v3.narrative import NarrativeLLM
            _NarrativeLLM = NarrativeLLM
        except ImportError:
            _NarrativeLLM = False  # Mark as unavailable
    return _NarrativeLLM if _NarrativeLLM else None


class ARIOrchestrator:
    """
    Main entry point for all user interactions.

    Routes to appropriate handler based on intent:
    - Product intents -> Navigation Intelligence (V3 pipeline)
    - Conversation intents -> Conversation Handler

    Based on pseudocode Section 0.5.3.
    """

    # Session TTL defaults
    DEFAULT_SESSION_TTL = timedelta(hours=2)
    DEFAULT_CACHE_TTL = timedelta(hours=1)
    MAX_SESSIONS = 1000
    MAX_CACHED_USERS = 500

    def __init__(
        self,
        navigation_intelligence: Optional[NavigationIntelligence] = None,
        intent_detector: Optional[HybridIntentDetector] = None,
        conversation_handler: Optional[ConversationHandler] = None,
        detection_strategy: DetectionStrategy = DetectionStrategy.RULE_FIRST,
        session_ttl: Optional[timedelta] = None,
        cache_ttl: Optional[timedelta] = None,
        qdrant_client: Optional[AsyncQdrantClient] = None,
        openai_client: Optional[OpenAI] = None,
        qdrant_collection: str = "fashion_products",
    ):
        """
        Initialize orchestrator.

        Args:
            navigation_intelligence: V3 Navigation Intelligence for product search
            intent_detector: Intent detector (creates default if not provided)
            conversation_handler: Conversation handler (creates default if not provided)
            detection_strategy: Strategy for intent detection
            session_ttl: How long to keep inactive sessions (default: 2 hours)
            cache_ttl: How long to cache user contexts (default: 1 hour)
            qdrant_client: AsyncQdrantClient for product search
            openai_client: OpenAI client for narrative generation
            qdrant_collection: Name of Qdrant collection for products
        """
        self.navigation = navigation_intelligence
        self.intent_detector = intent_detector or get_intent_detector(detection_strategy)
        self.conversation_handler = conversation_handler or ConversationHandler()
        self.session_ttl = session_ttl or self.DEFAULT_SESSION_TTL
        self.cache_ttl = cache_ttl or self.DEFAULT_CACHE_TTL

        # Product search components
        self.qdrant_client = qdrant_client
        self.openai_client = openai_client
        self.qdrant_collection = qdrant_collection

        # Cached instances (created lazily, reused) - protected by _instance_lock
        self._evaluator = None
        self._narrative_llm = None
        self._instance_lock = threading.Lock()

        # User context cache with TTL (user_id -> (context, last_access))
        self._user_context_cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
        self._cache_lock = threading.Lock()

        # Session tracking with TTL (session_id -> session_data with last_access)
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._session_lock = threading.Lock()

        # Last search session ID (for feedback tracking) - protected by _session_lock
        self._last_search_session_id: Optional[str] = None

        logger.info(
            f"ARIOrchestrator initialized with "
            f"navigation={'enabled' if navigation_intelligence else 'disabled'}, "
            f"detection_strategy={detection_strategy.value}"
        )

    async def process_input(
        self,
        session_id: str,
        user_id: str,
        query: str,
        occasion: Optional[str] = None,
        user_profile: Optional[OnboardingProfile] = None,
    ) -> ARIResponse:
        """
        Process any user input - conversation or product search.

        Based on pseudocode Section 0.5.3.

        Args:
            session_id: Session identifier
            user_id: User identifier
            query: User's query
            occasion: Optional occasion context
            user_profile: Optional onboarding profile

        Returns:
            ARIResponse
        """
        start_time = time.time()

        # Initialize/update session with TTL
        self._update_session(session_id, user_id)

        # Load user context
        user_context = self._load_user_context(user_id, user_profile)

        # Get conversation history for context
        conversation_history = self._get_conversation_history(session_id)

        try:
            # Step 1: Detect intent
            intent = await self.intent_detector.detect_intent(
                query=query,
                conversation_history=conversation_history,
            )

            logger.info(
                f"Intent: {intent.primary_intent.value} "
                f"(confidence: {intent.confidence:.2f}, method: {intent.detection_method})"
            )

            # Step 2: Route based on intent
            if intent.is_product_intent():
                response = await self._handle_product_intent(
                    session_id=session_id,
                    user_id=user_id,
                    query=query,
                    intent=intent,
                    occasion=occasion,
                    user_profile=user_profile,
                )
            else:
                response = await self._handle_conversation_intent(
                    session_id=session_id,
                    query=query,
                    intent=intent,
                    user_context=user_context,
                )

            response.execution_time = time.time() - start_time
            response.intent = intent
            response.session_id = session_id

            return response

        except Exception as e:
            logger.error(f"Error processing input: {e}", exc_info=True)
            return ARIResponse(
                response_type=ResponseType.ERROR,
                text=f"I encountered an error: {str(e)}. Let's try again.",
                error=str(e),
                execution_time=time.time() - start_time,
                session_id=session_id,
            )

    async def _handle_product_intent(
        self,
        session_id: str,
        user_id: str,
        query: str,
        intent: IntentResult,
        occasion: Optional[str] = None,
        user_profile: Optional[OnboardingProfile] = None,
    ) -> ARIResponse:
        """Handle product search intents via Navigation Intelligence."""
        if not self.navigation:
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text=(
                    "I'd love to help you find products, but my product search "
                    "isn't configured yet. Let me know when it's ready!"
                ),
                suggestions=[
                    "Tell me about your style",
                    "What can you do?",
                    "Let's chat",
                ],
            )

        try:
            # Extract filters from intent parameters
            params = intent.extracted_parameters

            # Use occasion from parameters if not explicitly provided
            if not occasion and params.occasions:
                occasion = params.occasions[0]

            # Step 1: Run navigation intelligence pipeline
            nav_context = await self.navigation.generate_navigation_context(
                user_id=user_id,
                query=query,
                occasion=occasion,
            )

            # Step 2: Search products using destination embedding
            products = []
            if not self.qdrant_client:
                logger.warning("Qdrant client not configured, cannot search products")
            else:
                # Get embedding to use for search
                query_vector = None

                # Try navigation context embedding first
                if nav_context.destination and nav_context.destination.embedding is not None:
                    embedding = nav_context.destination.embedding
                    query_vector = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)

                    # Check if embedding is valid (not all zeros)
                    import numpy as np
                    emb_arr = np.array(query_vector)
                    if np.allclose(emb_arr, 0):
                        logger.warning("Navigation embedding is all zeros, falling back to direct query embedding")
                        query_vector = None

                # Fall back to direct query embedding if navigation failed
                if query_vector is None and self.openai_client:
                    try:
                        logger.info("Using direct query embedding for search")
                        from ari_v3.navigation.constants import EMBEDDING_MODEL
                        response = self.openai_client.embeddings.create(
                            model=EMBEDDING_MODEL,
                            input=query,
                        )
                        query_vector = response.data[0].embedding
                        logger.info(f"Got direct embedding, dim={len(query_vector)}")
                    except Exception as emb_err:
                        logger.error(f"Failed to get direct embedding: {emb_err}")

                if query_vector:
                    results = await self.qdrant_client.query_points(
                        collection_name=self.qdrant_collection,
                        query=query_vector,
                        limit=50,
                    )
                    products = [hit.payload for hit in results.points]
                    logger.info(f"Found {len(products)} candidate products from {self.qdrant_collection}")
                else:
                    logger.warning("No embedding available for search")

            if not products:
                return ARIResponse(
                    response_type=ResponseType.PRODUCTS,
                    products=[],
                    text=self._format_product_response([], None, query),
                    suggestions=self._generate_product_suggestions(intent, []),
                )

            # Step 3: Evaluate and select best products (using cached evaluator)
            selected = self._evaluate_products(products, nav_context, limit=10)

            # Step 4: Generate narrative (using cached narrative LLM)
            narrative = self._generate_narrative(nav_context, selected[:5])

            # Generate a search session ID for feedback tracking (thread-safe)
            search_session_id = str(uuid.uuid4())
            with self._session_lock:
                self._last_search_session_id = search_session_id

            return ARIResponse(
                response_type=ResponseType.PRODUCTS,
                products=selected,
                narrative=narrative,
                text=self._format_product_response(selected, narrative, query),
                suggestions=self._generate_product_suggestions(intent, selected),
            )

        except Exception as e:
            logger.error(f"Navigation failed: {e}", exc_info=True)
            return ARIResponse(
                response_type=ResponseType.ERROR,
                text=(
                    f"I had trouble searching for products: {str(e)}. "
                    "Let me try again or help you with something else."
                ),
                error=str(e),
                suggestions=[
                    "Try a different search",
                    "Tell me more about what you want",
                    "Browse by category",
                ],
            )

    def _evaluate_products(
        self,
        products: List[Any],
        nav_context: Any,
        limit: int = 10,
    ) -> List[Any]:
        """Evaluate and select best products using cached evaluator (thread-safe)."""
        EvaluatorClass = _get_evaluator_class()
        if not EvaluatorClass:
            logger.warning("ARIEvaluator not available, using raw results")
            return products[:limit]

        try:
            # Thread-safe lazy initialization
            if self._evaluator is None:
                with self._instance_lock:
                    if self._evaluator is None:
                        self._evaluator = EvaluatorClass()

            selected = self._evaluator.evaluate_and_select(
                products=products,
                nav_context=nav_context,
                limit=limit,
            )
            logger.info(f"Selected {len(selected)} products after evaluation")
            return selected
        except Exception as e:
            logger.warning(f"Evaluation failed, using raw results: {e}")
            return products[:limit]

    def _generate_narrative(
        self,
        nav_context: Any,
        products: List[Any],
    ) -> Optional[Any]:
        """Generate narrative using cached narrative LLM (thread-safe)."""
        if not self.openai_client or not products:
            return None

        NarrativeClass = _get_narrative_class()
        if not NarrativeClass:
            logger.warning("NarrativeLLM not available")
            return None

        try:
            # Thread-safe lazy initialization
            if self._narrative_llm is None:
                with self._instance_lock:
                    if self._narrative_llm is None:
                        self._narrative_llm = NarrativeClass(openai_client=self.openai_client)

            narrative = self._narrative_llm.generate_narrative(
                nav_context=nav_context,
                products=products,
            )
            logger.info("Narrative generated successfully")
            return narrative
        except Exception as e:
            logger.warning(f"Narrative generation failed: {e}")
            return None

    def get_last_search_session_id(self) -> Optional[str]:
        """Get the session ID from the last product search (for feedback tracking)."""
        with self._session_lock:
            return self._last_search_session_id

    def clear_last_search_session(self) -> None:
        """Clear the last search session ID after feedback is collected."""
        with self._session_lock:
            self._last_search_session_id = None

    async def _handle_conversation_intent(
        self,
        session_id: str,
        query: str,
        intent: IntentResult,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ARIResponse:
        """Handle conversation intents via Conversation Handler."""
        try:
            response = await self.conversation_handler.handle_conversation(
                session_id=session_id,
                query=query,
                intent=intent,
                user_context=user_context,
            )

            # Determine response type
            if intent.primary_intent == SearchIntent.GREETING:
                response_type = ResponseType.GREETING
            elif intent.primary_intent == SearchIntent.GOODBYE:
                response_type = ResponseType.GOODBYE
            else:
                response_type = ResponseType.CONVERSATION

            return ARIResponse(
                response_type=response_type,
                text=response.text,
                suggestions=response.suggestions,
            )

        except Exception as e:
            logger.error(f"Conversation handling failed: {e}", exc_info=True)
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text="I'm here to help! What would you like to explore?",
                error=str(e),
                suggestions=[
                    "Search for products",
                    "Get outfit ideas",
                    "Tell me about my style",
                ],
            )

    def _update_session(self, session_id: str, user_id: str):
        """Update or create session with TTL tracking."""
        now = datetime.now()

        with self._session_lock:
            # Cleanup if too many sessions
            if len(self._sessions) >= self.MAX_SESSIONS:
                self._cleanup_expired_sessions_locked()

            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "user_id": user_id,
                    "created_at": now,
                    "query_count": 0,
                }

            self._sessions[session_id]["query_count"] += 1
            self._sessions[session_id]["last_access"] = now

    def _cleanup_expired_sessions_locked(self):
        """Remove expired sessions. Must be called with _session_lock held."""
        now = datetime.now()
        expired = []

        for session_id, session_data in self._sessions.items():
            last_access = session_data.get("last_access", session_data.get("created_at"))
            if isinstance(last_access, datetime) and now - last_access > self.session_ttl:
                expired.append(session_id)

        for session_id in expired:
            del self._sessions[session_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def _cleanup_expired_cache_locked(self):
        """Remove expired cache entries. Must be called with _cache_lock held."""
        now = datetime.now()
        expired = []

        for user_id, (_, last_access) in self._user_context_cache.items():
            if now - last_access > self.cache_ttl:
                expired.append(user_id)

        for user_id in expired:
            del self._user_context_cache[user_id]

        if expired:
            logger.debug(f"Cleaned up {len(expired)} expired cache entries")

    def _load_user_context(
        self,
        user_id: str,
        user_profile: Optional[OnboardingProfile] = None,
    ) -> Dict[str, Any]:
        """Load user context from profile or cache with TTL."""
        now = datetime.now()

        with self._cache_lock:
            # Cleanup if too many cached users
            if len(self._user_context_cache) >= self.MAX_CACHED_USERS:
                self._cleanup_expired_cache_locked()

            # Check cache first (and validate TTL)
            if user_id in self._user_context_cache:
                context, last_access = self._user_context_cache[user_id]
                if now - last_access <= self.cache_ttl:
                    # Update last access time
                    self._user_context_cache[user_id] = (context, now)
                    return context
                else:
                    # Cache expired, remove it
                    del self._user_context_cache[user_id]

            # Build context from profile
            context: Dict[str, Any] = {"user_id": user_id}

            if user_profile:
                # Extract relevant fields from profile
                if hasattr(user_profile, 'taste') and user_profile.taste:
                    taste = user_profile.taste
                    if hasattr(taste, 'style_words'):
                        context["style_words"] = taste.style_words
                    if hasattr(taste, 'color_preferences'):
                        context["color_preferences"] = taste.color_preferences
                    if hasattr(taste, 'style_avoids'):
                        context["style_avoids"] = taste.style_avoids

                if hasattr(user_profile, 'practicality') and user_profile.practicality:
                    prac = user_profile.practicality
                    if hasattr(prac, 'budget_monthly'):
                        context["budget_monthly"] = prac.budget_monthly

                if hasattr(user_profile, 'personal') and user_profile.personal:
                    personal = user_profile.personal
                    if hasattr(personal, 'style_goal'):
                        context["style_goal"] = personal.style_goal

            # Cache it with current timestamp
            self._user_context_cache[user_id] = (context, now)
            return context

    def invalidate_user_cache(self, user_id: str):
        """Invalidate cached context for a user (call when profile updates)."""
        with self._cache_lock:
            if user_id in self._user_context_cache:
                del self._user_context_cache[user_id]
                logger.debug(f"Invalidated cache for user: {user_id}")

    def _get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for intent detection context."""
        messages = self.conversation_handler.get_conversation_history(session_id)

        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages[-5:]  # Last 5 messages
        ]

    def _format_product_response(
        self,
        products: List[Any],
        narrative: Optional[Any],
        query: str,
    ) -> str:
        """Format product search response text."""
        if not products:
            return (
                f"I searched for '{query}' but couldn't find any matching products. "
                "Would you like to try a different search?"
            )

        # Use narrative if available
        if narrative:
            if hasattr(narrative, 'opening'):
                return narrative.opening
            elif hasattr(narrative, 'text'):
                return narrative.text

        # Default response
        count = len(products)
        return f"I found {count} products that match your search for '{query}'!"

    def _generate_product_suggestions(
        self,
        intent: IntentResult,
        products: List[Any],
    ) -> List[str]:
        """Generate suggestions after product search."""
        suggestions = []

        if products:
            suggestions.append("Tell me more about any of these")
            suggestions.append("Show me similar items")
            suggestions.append("Filter by price")
        else:
            suggestions.append("Try a broader search")
            suggestions.append("Browse by category")
            suggestions.append("Show me what's trending")

        return suggestions

    def set_navigation_intelligence(self, navigation: NavigationIntelligence):
        """Set the navigation intelligence after initialization."""
        self.navigation = navigation
        logger.info("Navigation Intelligence connected to orchestrator")

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session (thread-safe)."""
        with self._session_lock:
            session = self._sessions.get(session_id)
            return session.copy() if session else None

    def cleanup_expired(self):
        """Manually trigger cleanup of expired sessions and cache entries."""
        with self._session_lock:
            self._cleanup_expired_sessions_locked()
        with self._cache_lock:
            self._cleanup_expired_cache_locked()

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics (thread-safe)."""
        with self._session_lock:
            total_queries = sum(s.get("query_count", 0) for s in self._sessions.values())
            # Count active vs expired sessions
            now = datetime.now()
            active_sessions = sum(
                1 for s in self._sessions.values()
                if isinstance(s.get("last_access"), datetime)
                and now - s["last_access"] <= self.session_ttl
            )
            total_sessions = len(self._sessions)

        with self._cache_lock:
            cached_users = len(self._user_context_cache)

        conv_stats = self.conversation_handler.get_stats()

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_queries": total_queries,
            "cached_users": cached_users,
            "navigation_enabled": self.navigation is not None,
            "session_ttl_hours": self.session_ttl.total_seconds() / 3600,
            "cache_ttl_hours": self.cache_ttl.total_seconds() / 3600,
            "conversation": conv_stats,
        }


def create_orchestrator(
    navigation_intelligence: Optional[NavigationIntelligence] = None,
    detection_strategy: DetectionStrategy = DetectionStrategy.RULE_FIRST,
    qdrant_client: Optional[AsyncQdrantClient] = None,
    openai_client: Optional[OpenAI] = None,
    qdrant_collection: str = "fashion_products",
) -> ARIOrchestrator:
    """
    Factory function to create an ARIOrchestrator.

    Args:
        navigation_intelligence: V3 Navigation Intelligence for product search
        detection_strategy: Strategy for intent detection
        qdrant_client: AsyncQdrantClient for product search
        openai_client: OpenAI client for narrative generation
        qdrant_collection: Name of Qdrant collection for products

    Returns:
        Configured ARIOrchestrator
    """
    return ARIOrchestrator(
        navigation_intelligence=navigation_intelligence,
        detection_strategy=detection_strategy,
        qdrant_client=qdrant_client,
        openai_client=openai_client,
        qdrant_collection=qdrant_collection,
    )
