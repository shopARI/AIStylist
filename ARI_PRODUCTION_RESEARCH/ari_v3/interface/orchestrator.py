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
    ExplanationTrace,
    IntentResult,
    ResponseType,
    SearchIntent,
    VisualFeatureFlags,
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

# Qdrant filter imports (lazy-loaded to avoid import errors if qdrant not installed)
try:
    from qdrant_client.models import Filter, FieldCondition, MatchValue, Range
    QDRANT_FILTER_AVAILABLE = True
except ImportError:
    QDRANT_FILTER_AVAILABLE = False
    Filter = None
    FieldCondition = None
    MatchValue = None
    Range = None

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
        async_openai_client=None,
        qdrant_collection: str = "fashion_products",
        visual_flags: Optional[VisualFeatureFlags] = None,
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
            async_openai_client: Async OpenAI client for non-blocking calls
            qdrant_collection: Name of Qdrant collection for products
            visual_flags: Feature flags for visual/multimodal capabilities
        """
        self.navigation = navigation_intelligence
        self.intent_detector = intent_detector or get_intent_detector(detection_strategy)
        self.conversation_handler = conversation_handler or ConversationHandler()
        self.session_ttl = session_ttl or self.DEFAULT_SESSION_TTL
        self.cache_ttl = cache_ttl or self.DEFAULT_CACHE_TTL

        # Product search components
        self.qdrant_client = qdrant_client
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
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

        # Last search context per session (for feedback refinement)
        # session_id -> {query, params, products_shown}
        self._last_search_context: Dict[str, Dict[str, Any]] = {}

        # Explanation traces per session (for "why" questions)
        # session_id -> ExplanationTrace from last product search
        self._explanation_traces: Dict[str, ExplanationTrace] = {}

        # Visual feature flags (V3.2)
        self.visual_flags = visual_flags or VisualFeatureFlags()
        self._visual_qdrant_client = None  # Lazy-loaded visual Qdrant client

        logger.info(
            f"ARIOrchestrator initialized with "
            f"navigation={'enabled' if navigation_intelligence else 'disabled'}, "
            f"detection_strategy={detection_strategy.value}, "
            f"{self.visual_flags.summary()}"
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
            elif intent.primary_intent == SearchIntent.FEEDBACK:
                # Check if we have previous search context to refine
                response = await self._handle_feedback_intent(
                    session_id=session_id,
                    user_id=user_id,
                    query=query,
                    intent=intent,
                    user_profile=user_profile,
                    user_context=user_context,
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
        # Create explanation trace for this request
        trace = ExplanationTrace()
        trace.query_interpretation["original_query"] = query
        trace.query_interpretation["detected_intent"] = intent.primary_intent.value

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

            # Use LLM to reason about exclusions (async)
            if self.async_openai_client:
                try:
                    from .parameter_extractor import get_parameter_extractor
                    extractor = get_parameter_extractor()
                    enhanced_params = await extractor.extract_async(
                        message=query,
                        openai_client=self.async_openai_client,
                        use_llm=True,
                    )
                    # Use LLM-reasoned exclusions
                    if enhanced_params.exclusions:
                        params.exclusions = enhanced_params.exclusions
                except Exception as e:
                    logger.warning(f"LLM exclusion extraction failed: {e}")

            # Use occasion from parameters if not explicitly provided
            if not occasion and params.occasions:
                occasion = params.occasions[0]

            # Step 1: Run navigation intelligence pipeline
            nav_context = None
            try:
                nav_context = await self.navigation.generate_navigation_context(
                    user_id=user_id,
                    query=query,
                    occasion=occasion,
                )
            except Exception as nav_err:
                logger.warning(f"Navigation pipeline failed: {nav_err}, will use direct embedding")

            # Step 2: Search products using destination embedding
            products = []
            if not self.qdrant_client:
                logger.warning("Qdrant client not configured, cannot search products")
            else:
                # Get embedding to use for search
                query_vector = None

                # Try navigation context embedding first
                if nav_context and nav_context.destination and nav_context.destination.embedding is not None:
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
                    try:
                        # Build Qdrant filter based on extracted parameters
                        query_filter = self._build_qdrant_filter(params)

                        # Semantic search (always runs)
                        # Include vectors for MMR diversity calculation
                        results = await self.qdrant_client.query_points(
                            collection_name=self.qdrant_collection,
                            query=query_vector,
                            query_filter=query_filter,
                            limit=50,
                            timeout=30,  # 30 second timeout
                            with_vectors=True,  # Include embeddings for MMR
                        )
                        # Attach embeddings to product payloads for MMR
                        semantic_products = []
                        for hit in results.points:
                            product = hit.payload.copy()
                            # Attach vector as 'embedding' field for MMR selector
                            if hit.vector is not None:
                                product['embedding'] = hit.vector
                            semantic_products.append(product)

                        semantic_scores = {
                            hit.payload.get('id', hit.payload.get('_id', str(i))): hit.score
                            for i, hit in enumerate(results.points)
                        }
                        filter_desc = f" (filter: {query_filter})" if query_filter else ""
                        logger.info(f"Found {len(semantic_products)} products from semantic search{filter_desc}")

                        # Visual search (if enabled)
                        visual_products = []
                        visual_scores = {}
                        if self.visual_flags.enable_visual_search:
                            visual_products, visual_scores = await self._visual_search(
                                query=query,
                                nav_context=nav_context,
                                limit=50,
                                trace=trace,
                            )

                        # Fuse results
                        if visual_products and self.visual_flags.enable_visual_search:
                            products = self._fuse_search_results(
                                semantic_products=semantic_products,
                                semantic_scores=semantic_scores,
                                visual_products=visual_products,
                                visual_scores=visual_scores,
                                trace=trace,
                            )
                            logger.info(f"Fused {len(products)} products from semantic + visual")
                        else:
                            products = semantic_products
                            logger.info(f"Using {len(products)} products from semantic search only")

                    except Exception as qdrant_err:
                        logger.error(f"Qdrant query failed: {qdrant_err}")
                        # Return empty results instead of error
                        products = []
                else:
                    logger.warning("No embedding available for search")

            # Apply exclusions (brand, color, category, style, etc.)
            if products and params.exclusions:
                original_count = len(products)
                products = self._apply_exclusions(products, params.exclusions)
                filtered_count = original_count - len(products)
                if filtered_count > 0:
                    exclusion_summary = [f"{e.field}:{e.value}" for e in params.exclusions]
                    logger.info(f"Filtered out {filtered_count} products based on exclusions: {exclusion_summary}")

            if not products:
                return ARIResponse(
                    response_type=ResponseType.PRODUCTS,
                    products=[],
                    text=self._format_product_response([], None, query),
                    suggestions=self._generate_product_suggestions(intent, []),
                )

            # Step 3: Evaluate and select best products (using cached evaluator)
            # Pass trace to accumulate score breakdowns
            selected = self._evaluate_products(products, nav_context, limit=10, trace=trace)

            # Step 4: Generate narrative (using cached narrative LLM)
            narrative = self._generate_narrative(nav_context, selected[:5])

            # Generate a search session ID for feedback tracking (thread-safe)
            search_session_id = str(uuid.uuid4())
            with self._session_lock:
                self._last_search_session_id = search_session_id
                # Store search context for feedback refinement
                self._last_search_context[session_id] = {
                    "query": query,
                    "params": params,
                    "products_shown": [p.get('title', '')[:50] for p in selected[:5]],
                    "brands_shown": list(set(p.get('brand') or p.get('vendor') for p in selected if p.get('brand') or p.get('vendor'))),
                    "timestamp": datetime.now(),
                }
                # Store explanation trace for "why" questions
                self._explanation_traces[session_id] = trace

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
        trace: Optional[ExplanationTrace] = None,
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
                trace=trace,  # Pass trace for score breakdown tracking
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
                        self._narrative_llm = NarrativeClass(
                            openai_client=self.openai_client,
                            async_openai_client=self.async_openai_client,
                        )

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
            # Special handling for CLARIFICATION ("why this?") with explanation trace
            if intent.primary_intent == SearchIntent.CLARIFICATION:
                trace = self._explanation_traces.get(session_id)
                if trace and trace.product_breakdowns:
                    # Use explain_why with the trace
                    explanation = await self.conversation_handler.explain_why(
                        question=query,
                        trace=trace,
                        user_context=user_context,
                    )
                    return ARIResponse(
                        response_type=ResponseType.CONVERSATION,
                        text=explanation,
                        suggestions=[
                            "Show me more like this",
                            "What else do you know about my style?",
                            "Try a different search",
                        ],
                    )

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

    async def _handle_feedback_intent(
        self,
        session_id: str,
        user_id: str,
        query: str,
        intent: IntentResult,
        user_profile=None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ARIResponse:
        """
        Handle feedback about previous recommendations.

        If we have context from a previous search, this will:
        1. Understand what the feedback means (e.g., "that's not Gucci" = wanted Gucci)
        2. Refine the search with the feedback
        3. Return new, better-matched results
        """
        # Check if we have previous search context
        prev_context = self._last_search_context.get(session_id)

        if prev_context:
            logger.info(f"Feedback with previous context: {prev_context.get('query')}")

            # Use LLM to understand feedback in context
            refined_query = await self._interpret_feedback(
                original_query=prev_context.get("query", ""),
                feedback=query,
                brands_shown=prev_context.get("brands_shown", []),
            )

            if refined_query:
                logger.info(f"Refined query from feedback: {refined_query}")

                # Re-run product search with refined query
                # Create a new intent for product search
                from .types import ExtractedParameters
                refined_intent = IntentResult(
                    primary_intent=SearchIntent.PRODUCT_SEARCH,
                    confidence=0.9,
                    detection_method="feedback_refinement",
                    extracted_parameters=intent.extracted_parameters,
                )

                return await self._handle_product_intent(
                    session_id=session_id,
                    user_id=user_id,
                    query=refined_query,
                    intent=refined_intent,
                    occasion=None,
                    user_profile=user_profile,
                )

        # No previous context or couldn't refine - handle as conversation
        return await self._handle_conversation_intent(
            session_id=session_id,
            query=query,
            intent=intent,
            user_context=user_context,
        )

    async def _interpret_feedback(
        self,
        original_query: str,
        feedback: str,
        brands_shown: List[str],
    ) -> Optional[str]:
        """
        Use LLM to interpret feedback and generate a refined search query.

        Args:
            original_query: What the user originally searched for
            feedback: The feedback they gave (e.g., "that's not Gucci")
            brands_shown: Brands that were in the results

        Returns:
            Refined search query, or None if can't interpret
        """
        if not self.async_openai_client:
            return None

        try:
            prompt = f"""The user searched for: "{original_query}"
They were shown products from brands: {', '.join(brands_shown) if brands_shown else 'various brands'}
They gave this feedback: "{feedback}"

Interpret their feedback and generate a refined search query.
If they said "that's not X", they likely wanted X specifically.
If they said "too formal/casual/etc", adjust the style.

Return ONLY the refined search query, nothing else.
If you can't interpret the feedback, return "UNCLEAR"."""

            response = await self.async_openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You refine fashion search queries based on user feedback. Return only the refined query."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.3,
            )

            refined = response.choices[0].message.content.strip()
            if refined and refined != "UNCLEAR":
                return refined
            return None

        except Exception as e:
            logger.warning(f"Failed to interpret feedback: {e}")
            return None

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
                # Extract all relevant fields from profile for rich context
                if hasattr(user_profile, 'taste') and user_profile.taste:
                    taste = user_profile.taste
                    if hasattr(taste, 'style_words'):
                        context["style_words"] = taste.style_words
                    if hasattr(taste, 'color_preferences'):
                        context["color_preferences"] = taste.color_preferences
                    if hasattr(taste, 'style_avoids'):
                        context["style_avoids"] = taste.style_avoids
                    if hasattr(taste, 'adventurousness'):
                        context["adventurousness"] = taste.adventurousness
                    if hasattr(taste, 'pattern_comfort'):
                        context["pattern_comfort"] = taste.pattern_comfort

                if hasattr(user_profile, 'practicality') and user_profile.practicality:
                    prac = user_profile.practicality
                    if hasattr(prac, 'budget_monthly'):
                        context["budget_monthly"] = prac.budget_monthly
                    if hasattr(prac, 'budget_flexibility'):
                        context["budget_flexibility"] = prac.budget_flexibility

                if hasattr(user_profile, 'personal') and user_profile.personal:
                    personal = user_profile.personal
                    if hasattr(personal, 'style_goal'):
                        context["style_goal"] = personal.style_goal
                    if hasattr(personal, 'occasions'):
                        context["occasions"] = personal.occasions
                    if hasattr(personal, 'root_value'):
                        context["root_value"] = personal.root_value

                if hasattr(user_profile, 'process') and user_profile.process:
                    process = user_profile.process
                    if hasattr(process, 'brand_loyalty'):
                        context["brand_loyalty"] = process.brand_loyalty

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

    def _build_qdrant_filter(self, params) -> Optional[Filter]:
        """
        Build Qdrant filter based on extracted parameters.

        Uses Qdrant's filtering to narrow results BEFORE vector similarity,
        which is more efficient and accurate than post-filtering.

        Args:
            params: ExtractedParameters with price_tier, require_premium, price_range

        Returns:
            Qdrant Filter object or None if no filters needed
        """
        if not QDRANT_FILTER_AVAILABLE:
            logger.debug("Qdrant filter not available, skipping")
            return None

        conditions = []

        # Filter by price tier (luxury/premium/budget queries)
        if hasattr(params, 'price_tier') and params.price_tier:
            conditions.append(
                FieldCondition(
                    key="price_tier",
                    match=MatchValue(value=params.price_tier)
                )
            )
            logger.info(f"Adding price_tier filter: {params.price_tier}")

        # Filter for premium products
        if hasattr(params, 'require_premium') and params.require_premium:
            conditions.append(
                FieldCondition(
                    key="is_premium",
                    match=MatchValue(value=True)
                )
            )
            logger.info("Adding is_premium=True filter")

        # Filter by price range
        if hasattr(params, 'price_range') and params.price_range:
            price_range = params.price_range
            range_filter = {}
            if price_range.get('min'):
                range_filter['gte'] = price_range['min']
            if price_range.get('max'):
                range_filter['lte'] = price_range['max']

            if range_filter:
                conditions.append(
                    FieldCondition(
                        key="price",
                        range=Range(**range_filter)
                    )
                )
                logger.info(f"Adding price range filter: {range_filter}")

        # Filter by category if specified
        if hasattr(params, 'categories') and params.categories:
            # Use first category for now (Qdrant doesn't support OR easily)
            conditions.append(
                FieldCondition(
                    key="category",
                    match=MatchValue(value=params.categories[0])
                )
            )
            logger.info(f"Adding category filter: {params.categories[0]}")

        if not conditions:
            return None

        return Filter(must=conditions)

    def _apply_exclusions(self, products: List[Dict], exclusions: List) -> List[Dict]:
        """
        Filter products based on exclusion criteria.

        Handles exclusions by field type:
        - brand: checks brand, vendor, title
        - color: checks color, title, description
        - category: checks category, productType, title
        - style: checks style, tags, title, description
        - material: checks material, description
        - price: checks price against threshold
        - abstract: checks title, description, tags for semantic match
        - general: checks title, description
        """
        if not exclusions:
            return products

        def matches_exclusion(product: Dict, exclusion) -> bool:
            value_lower = exclusion.value.lower()
            field = exclusion.field

            # Get product fields (handle None values)
            title = (product.get('title') or '').lower()
            description = (product.get('description') or '').lower()
            brand = (product.get('brand') or product.get('vendor') or '').lower()
            color = (product.get('color') or '').lower()
            category = (product.get('category') or product.get('productType') or '').lower()
            tags = ' '.join(product.get('tags') or []).lower()
            material = (product.get('material') or '').lower()
            price = product.get('price', 0)

            if field == "brand":
                return value_lower in brand or value_lower in title
            elif field == "color":
                return value_lower in color or value_lower in title or value_lower in description
            elif field == "category":
                return value_lower in category or value_lower in title
            elif field == "style":
                return value_lower in tags or value_lower in title or value_lower in description
            elif field == "material":
                return value_lower in material or value_lower in description
            elif field == "occasion":
                return value_lower in tags or value_lower in description
            elif field == "price":
                # Handle price exclusions like "expensive", "over $100"
                try:
                    if "expensive" in value_lower or "pricey" in value_lower:
                        return price > 200  # Consider >$200 as expensive
                    elif "cheap" in value_lower:
                        return price < 30  # Consider <$30 as cheap
                    # Try to extract number
                    import re
                    match = re.search(r'\$?(\d+)', value_lower)
                    if match:
                        threshold = float(match.group(1))
                        if "over" in value_lower or "above" in value_lower:
                            return price > threshold
                        elif "under" in value_lower or "below" in value_lower:
                            return price < threshold
                except:
                    pass
                return False
            elif field == "abstract":
                # Abstract exclusions - search broadly
                all_text = f"{title} {description} {tags} {category}"
                # Check for the value and common synonyms
                return value_lower in all_text
            else:  # general
                return value_lower in title or value_lower in description

        # Filter out products matching any exclusion
        return [
            p for p in products
            if not any(matches_exclusion(p, excl) for excl in exclusions)
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
            "visual_flags": self.visual_flags.to_dict(),
        }

    # =========================================================================
    # VISUAL SEARCH METHODS (V3.2)
    # =========================================================================

    async def _visual_search(
        self,
        query: str,
        nav_context: Optional[Any],
        limit: int = 50,
        trace: Optional[ExplanationTrace] = None,
    ) -> Tuple[List[Dict], Dict[str, float]]:
        """
        Perform visual similarity search using FashionSigLIP embeddings.

        Args:
            query: Search query
            nav_context: Navigation context with user visual profile
            limit: Max products to return
            trace: Explanation trace to update

        Returns:
            Tuple of (products, scores dict)
        """
        if not self.visual_flags.enable_visual_search:
            return [], {}

        visual_products = []
        visual_scores = {}

        try:
            # Get or create visual Qdrant client
            if self._visual_qdrant_client is None:
                await self._init_visual_client()

            if self._visual_qdrant_client is None:
                logger.warning("Visual Qdrant client not available")
                if trace:
                    trace.add_navigation_decision("Visual search skipped: client unavailable")
                return [], {}

            # Get visual query embedding
            visual_embedding = await self._get_visual_embedding(query, nav_context)

            if visual_embedding is None:
                logger.warning("Could not generate visual embedding for query")
                if trace:
                    trace.add_navigation_decision("Visual search skipped: no embedding")
                return [], {}

            # Query visual collection (include vectors for MMR)
            results = await self._visual_qdrant_client.query_points(
                collection_name=self.visual_flags.visual_collection,
                query=visual_embedding,
                limit=limit,
                timeout=30,
                with_vectors=True,  # Include embeddings for MMR
            )

            # Attach embeddings to product payloads
            visual_products = []
            for hit in results.points:
                product = hit.payload.copy()
                if hit.vector is not None:
                    product['embedding'] = hit.vector
                visual_products.append(product)

            visual_scores = {
                hit.payload.get('id', hit.payload.get('_id', str(i))): hit.score
                for i, hit in enumerate(results.points)
            }

            logger.info(f"Visual search found {len(visual_products)} products")
            if trace:
                trace.add_navigation_decision(
                    f"Visual search: {len(visual_products)} products from {self.visual_flags.visual_collection}"
                )

        except Exception as e:
            logger.error(f"Visual search failed: {e}")
            if trace:
                trace.add_navigation_decision(f"Visual search error: {str(e)[:50]}")

            # Fallback behavior
            if not self.visual_flags.fallback_on_visual_error:
                raise

        return visual_products, visual_scores

    async def _init_visual_client(self):
        """Initialize visual Qdrant client lazily."""
        try:
            # Try to use the same Qdrant client with different collection
            if self.qdrant_client:
                self._visual_qdrant_client = self.qdrant_client
                logger.info(f"Using shared Qdrant client for visual collection: {self.visual_flags.visual_collection}")
            else:
                logger.warning("No Qdrant client available for visual search")
        except Exception as e:
            logger.error(f"Failed to init visual client: {e}")
            self._visual_qdrant_client = None

    async def _get_visual_embedding(
        self,
        query: str,
        nav_context: Optional[Any],
    ) -> Optional[List[float]]:
        """
        Get visual embedding for the search query.

        Strategy:
        1. If user has Pinterest/Instagram visual profile, use that as base
        2. Otherwise, use FashionSigLIP text-to-visual encoding
        3. Fallback to None if unavailable
        """
        # Try user's social visual embedding first
        if self.visual_flags.enable_social_visual and nav_context:
            try:
                if hasattr(nav_context, 'current_position'):
                    pos = nav_context.current_position
                    if hasattr(pos, 'visual_embedding') and pos.visual_embedding is not None:
                        import numpy as np
                        emb = pos.visual_embedding
                        if not np.allclose(emb, 0):
                            logger.debug("Using user's visual embedding from social profile")
                            return emb.tolist() if hasattr(emb, 'tolist') else list(emb)
            except Exception as e:
                logger.debug(f"Could not use social visual embedding: {e}")

        # Try FashionSigLIP text-to-visual encoding
        try:
            from services.ml.fashionsig_encoder import get_fashionsig_encoder
            encoder = get_fashionsig_encoder()
            if encoder.model is not None:
                embedding = await encoder.encode_text_async(query)
                logger.debug(f"Generated FashionSigLIP text embedding, dim={len(embedding)}")
                return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        except ImportError:
            logger.debug("FashionSigLIP encoder not available")
        except Exception as e:
            logger.debug(f"FashionSigLIP encoding failed: {e}")

        return None

    def _fuse_search_results(
        self,
        semantic_products: List[Dict],
        semantic_scores: Dict[str, float],
        visual_products: List[Dict],
        visual_scores: Dict[str, float],
        trace: Optional[ExplanationTrace] = None,
    ) -> List[Dict]:
        """
        Fuse semantic and visual search results using configured strategy.

        Strategies:
        - weighted_average: Combine scores with weights, return union
        - max: Take the higher score for each product
        - cascade: Visual re-ranks semantic top-N

        Returns:
            Merged and re-ranked products
        """
        strategy = self.visual_flags.fusion_strategy
        semantic_weight = self.visual_flags.semantic_weight
        visual_weight = self.visual_flags.visual_weight

        # Build product lookup
        all_products = {}
        for p in semantic_products:
            pid = p.get('id', p.get('_id', str(id(p))))
            all_products[pid] = p.copy()
            all_products[pid]['_semantic_score'] = semantic_scores.get(pid, 0)
            all_products[pid]['_visual_score'] = 0

        for p in visual_products:
            pid = p.get('id', p.get('_id', str(id(p))))
            if pid in all_products:
                all_products[pid]['_visual_score'] = visual_scores.get(pid, 0)
            else:
                all_products[pid] = p.copy()
                all_products[pid]['_semantic_score'] = 0
                all_products[pid]['_visual_score'] = visual_scores.get(pid, 0)

        # Calculate fused scores
        for pid, product in all_products.items():
            sem = product.get('_semantic_score', 0)
            vis = product.get('_visual_score', 0)

            if strategy == "weighted_average":
                # Normalize: only count weights for available scores
                if sem > 0 and vis > 0:
                    product['_fused_score'] = sem * semantic_weight + vis * visual_weight
                elif sem > 0:
                    product['_fused_score'] = sem
                else:
                    product['_fused_score'] = vis
            elif strategy == "max":
                product['_fused_score'] = max(sem, vis)
            elif strategy == "cascade":
                # Visual score boosts semantic-selected products
                product['_fused_score'] = sem + (vis * 0.2 if vis > 0 else 0)
            else:
                product['_fused_score'] = sem * semantic_weight + vis * visual_weight

        # Sort by fused score
        ranked = sorted(all_products.values(), key=lambda p: p.get('_fused_score', 0), reverse=True)

        # Log fusion stats
        semantic_only = sum(1 for p in ranked if p.get('_visual_score', 0) == 0)
        visual_only = sum(1 for p in ranked if p.get('_semantic_score', 0) == 0)
        both = len(ranked) - semantic_only - visual_only

        logger.info(f"Fusion ({strategy}): {len(ranked)} total, {both} in both, {semantic_only} semantic-only, {visual_only} visual-only")

        if trace:
            trace.add_navigation_decision(
                f"Result fusion ({strategy}): {len(ranked)} products, "
                f"weights={semantic_weight:.1f}S/{visual_weight:.1f}V"
            )

        return ranked


def create_orchestrator(
    navigation_intelligence: Optional[NavigationIntelligence] = None,
    detection_strategy: DetectionStrategy = DetectionStrategy.RULE_FIRST,
    qdrant_client: Optional[AsyncQdrantClient] = None,
    openai_client: Optional[OpenAI] = None,
    qdrant_collection: str = "fashion_products",
    visual_flags: Optional[VisualFeatureFlags] = None,
) -> ARIOrchestrator:
    """
    Factory function to create an ARIOrchestrator.

    Args:
        navigation_intelligence: V3 Navigation Intelligence for product search
        detection_strategy: Strategy for intent detection
        qdrant_client: AsyncQdrantClient for product search
        openai_client: OpenAI client for narrative generation
        qdrant_collection: Name of Qdrant collection for products
        visual_flags: Feature flags for visual/multimodal capabilities

    Returns:
        Configured ARIOrchestrator
    """
    return ARIOrchestrator(
        navigation_intelligence=navigation_intelligence,
        detection_strategy=detection_strategy,
        qdrant_client=qdrant_client,
        openai_client=openai_client,
        qdrant_collection=qdrant_collection,
        visual_flags=visual_flags,
    )
