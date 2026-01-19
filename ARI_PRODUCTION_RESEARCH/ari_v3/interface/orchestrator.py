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
        detection_strategy: DetectionStrategy = DetectionStrategy.LLM_FIRST,
        session_ttl: Optional[timedelta] = None,
        cache_ttl: Optional[timedelta] = None,
        qdrant_client: Optional[AsyncQdrantClient] = None,
        openai_client: Optional[OpenAI] = None,
        async_openai_client=None,
        qdrant_collection: str = "fashion_products",
        visual_flags: Optional[VisualFeatureFlags] = None,
        enable_neo4j: bool = False,
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

        # Search backend flags
        self.enable_neo4j = enable_neo4j

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

        # Get actual strategy from intent detector (it may have been passed in with different strategy)
        actual_strategy = getattr(self.intent_detector, 'strategy', detection_strategy)
        actual_strategy_value = actual_strategy.value if hasattr(actual_strategy, 'value') else str(actual_strategy)
        logger.info(
            f"ARIOrchestrator initialized with "
            f"navigation={'enabled' if navigation_intelligence else 'disabled'}, "
            f"detection_strategy={actual_strategy_value}, "
            f"neo4j={'enabled' if enable_neo4j else 'disabled'}, "
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

        # Load user context (including gender from session if available)
        user_context = self._load_user_context(user_id, user_profile, session_id)

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

            # Step 2: Check for catalog/metadata queries first
            catalog_response = await self._check_catalog_query(query, session_id)
            if catalog_response:
                catalog_response.execution_time = time.time() - start_time
                catalog_response.intent = intent
                catalog_response.session_id = session_id
                return catalog_response

            # Step 3: Route based on intent
            if intent.is_product_intent():
                response = await self._handle_product_intent(
                    session_id=session_id,
                    user_id=user_id,
                    query=query,
                    intent=intent,
                    occasion=occasion,
                    user_profile=user_profile,
                    user_context=user_context,
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
            elif intent.primary_intent == SearchIntent.PROFILE_UPDATE:
                # User is sharing style/preference info to update their profile
                response = await self._handle_profile_update_intent(
                    session_id=session_id,
                    user_id=user_id,
                    query=query,
                    intent=intent,
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
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ARIResponse:
        """Handle product search intents via Navigation Intelligence."""
        # Create explanation trace for this request
        trace = ExplanationTrace()
        trace.query_interpretation["original_query"] = query
        trace.query_interpretation["detected_intent"] = intent.primary_intent.value

        # Always expand queries using conversation history context
        # LLM judges if this is a continuation (weave in context) or new topic (keep as-is)
        conversation_history = self._get_conversation_history(session_id)
        expanded_query = await self._expand_query_with_context(query, conversation_history)
        if expanded_query != query:
            logger.info(f"Context expansion: '{query}' → '{expanded_query}'")
            trace.query_interpretation["expanded_from_conversation"] = expanded_query
            query = expanded_query

        # Check for previous context - use it for follow-up queries
        previous_context = self._last_search_context.get(session_id)
        previous_products = previous_context.get("products", []) if previous_context else []

        # For outfit_building with previous products, provide outfit advice
        if intent.primary_intent == SearchIntent.OUTFIT_BUILDING and previous_products:
            return await self._handle_outfit_building_with_context(
                session_id=session_id,
                user_id=user_id,
                query=query,
                previous_products=previous_products,
                user_context=user_context,
                trace=trace,
            )

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
                # Record navigation decisions for debug tracing
                if nav_context:
                    trace.navigation_decisions = {
                        "ran": True,
                        "has_destination": nav_context.destination is not None,
                        "synthesis_descriptors": getattr(nav_context, 'synthesis_output', {}).get('style_descriptors', []) if hasattr(nav_context, 'synthesis_output') else [],
                        "user_id": user_id,
                    }
            except Exception as nav_err:
                logger.warning(f"Navigation pipeline failed: {nav_err}, will use direct embedding")
                trace.navigation_decisions = {"ran": False, "error": str(nav_err)}

            # Step 2: Search products
            # Use Text2Cypher for queries needing Neo4j's structured data
            # (brand, specific colors, styles, price ranges with attributes)
            products = []
            used_neo4j_search = False

            # Detect if query needs Neo4j's structured fields
            # Only use Neo4j if enabled via --neo4j flag
            needs_neo4j = self.enable_neo4j and (
                params.brand_preferences or  # Brand queries need extracted_brand
                self._query_needs_structured_search(query, params)
            )

            if needs_neo4j and self.async_openai_client:
                logger.info(f"Query needs structured data, using Text2Cypher")
                try:
                    products = await self._search_neo4j_text2cypher(
                        query=query,
                        limit=50,
                    )
                    if products:
                        used_neo4j_search = True
                        logger.info(f"Using {len(products)} products from Text2Cypher search")
                except Exception as neo4j_err:
                    logger.warning(f"Text2Cypher search failed: {neo4j_err}")

            # Fall back to Qdrant semantic search if Neo4j didn't return results
            if not products and not self.qdrant_client:
                logger.warning("Qdrant client not configured, cannot search products")
            elif not products:
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

                # Fall back to semantic query expansion + embedding if navigation failed
                semantic_expansion = None
                if query_vector is None and self.async_openai_client:
                    try:
                        logger.info("Using SemanticQueryGenerator for query expansion")
                        from ari_v3.tools.semantic_query import SemanticQueryGenerator
                        from ari_v3.navigation.constants import EMBEDDING_MODEL

                        generator = SemanticQueryGenerator(async_openai_client=self.async_openai_client)
                        semantic_expansion = await generator.expand_query_async(query, user_context=user_context)

                        # Use expanded query for embedding
                        response = await self.async_openai_client.embeddings.create(
                            model=EMBEDDING_MODEL,
                            input=semantic_expansion.expanded_query,
                        )
                        query_vector = response.data[0].embedding

                        # Track expansion in trace
                        trace.query_interpretation["semantic_expansion"] = {
                            "original": query,
                            "expanded": semantic_expansion.expanded_query[:100],
                            "styles": semantic_expansion.style_terms[:5],
                            "colors": semantic_expansion.color_terms,
                            "occasion": semantic_expansion.occasion,
                        }

                        logger.info(
                            f"Semantic expansion: styles={semantic_expansion.style_terms[:3]}, "
                            f"colors={semantic_expansion.color_terms}, "
                            f"expanded='{semantic_expansion.expanded_query[:50]}...'"
                        )
                    except Exception as emb_err:
                        logger.warning(f"Semantic expansion failed: {emb_err}, trying direct embedding")

                # Final fallback to sync client if async failed
                if query_vector is None and self.openai_client:
                    try:
                        logger.info("Using direct query embedding for search (sync fallback)")
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
                        # Build Qdrant filter based on extracted parameters + semantic expansion
                        query_filter = self._build_qdrant_filter(params, semantic_expansion)

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

            # Apply brand filtering (if specific brands requested)
            # Skip if we already used Neo4j search (products are already filtered)
            if products and params.brand_preferences and not used_neo4j_search:
                original_count = len(products)
                products = self._apply_brand_filter(products, params.brand_preferences)
                filtered_count = original_count - len(products)
                logger.info(f"Brand filter: kept {len(products)}/{original_count} products matching brands: {params.brand_preferences}")

            # Deduplicate products by title (keep highest scored version)
            if products:
                original_count = len(products)
                products = self._deduplicate_products(products)
                if len(products) < original_count:
                    logger.info(f"Deduplicated: {original_count} → {len(products)} products")

            # Enrich products with Neo4j metadata (category, brand, etc.) if missing
            # Only if Neo4j is enabled via --neo4j flag
            if self.enable_neo4j and products and self.navigation and hasattr(self.navigation, 'neo4j_driver'):
                products = await self._enrich_products_from_neo4j(products)
                logger.info(f"Enriched {len(products)} products with Neo4j metadata")

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
                # Store search context for feedback refinement (handle None items safely)
                safe_selected = [p for p in (selected or []) if p is not None]
                self._last_search_context[session_id] = {
                    "query": query,
                    "params": params,
                    "products": safe_selected[:10],  # Store products with embeddings for follow-up similarity searches
                    "products_shown": [(p.get('title') or '')[:50] for p in safe_selected[:5]],
                    "brands_shown": list(set(p.get('brand') or p.get('vendor') for p in safe_selected if p.get('brand') or p.get('vendor'))),
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

    async def _enrich_products_from_neo4j(self, products: List[Any]) -> List[Any]:
        """
        Enrich products with metadata from Neo4j using UUID matching.

        If a product from Qdrant is missing category, brand, or other fields,
        we look them up in Neo4j using the shared UUID.

        Args:
            products: List of products from Qdrant

        Returns:
            Enriched products with Neo4j metadata
        """
        if not products:
            return products

        try:
            import asyncio

            # Collect UUIDs that need enrichment
            uuids_to_enrich = []
            for p in products:
                # Check if product needs enrichment (missing key fields)
                needs_enrichment = (
                    not p.get('category') or
                    not p.get('productType') or
                    not p.get('extracted_brand')
                )
                if needs_enrichment:
                    uuid = p.get('uuid') or p.get('id')
                    if uuid:
                        uuids_to_enrich.append(str(uuid))

            if not uuids_to_enrich:
                return products  # Nothing to enrich

            # Query Neo4j for metadata
            cypher = """
                UNWIND $uuids AS uuid
                MATCH (p:Product {id: uuid})
                RETURN p.id AS uuid,
                       p.productType AS productType,
                       p.extracted_brand AS brand,
                       p.category AS category,
                       p.tags AS tags
            """

            driver = self.navigation.neo4j_driver

            def run_cypher():
                with driver.session(database="neo4j") as session:
                    result = session.run(cypher, uuids=uuids_to_enrich)
                    return {r['uuid']: dict(r) for r in result}

            loop = asyncio.get_event_loop()
            neo4j_data = await loop.run_in_executor(None, run_cypher)

            # Enrich products with Neo4j data
            enriched_count = 0
            for product in products:
                uuid = str(product.get('uuid') or product.get('id') or '')
                if uuid in neo4j_data:
                    neo_data = neo4j_data[uuid]
                    # Fill in missing fields
                    if not product.get('category') and neo_data.get('category'):
                        product['category'] = neo_data['category']
                        enriched_count += 1
                    if not product.get('productType') and neo_data.get('productType'):
                        product['productType'] = neo_data['productType']
                    if not product.get('brand') and neo_data.get('brand'):
                        product['brand'] = neo_data['brand']
                    if not product.get('extracted_brand') and neo_data.get('brand'):
                        product['extracted_brand'] = neo_data['brand']

            if enriched_count > 0:
                logger.debug(f"Enriched {enriched_count} products with Neo4j category data")

            return products

        except Exception as e:
            logger.warning(f"Neo4j enrichment failed (continuing without): {e}")
            return products

    def _deduplicate_products(self, products: List[Any]) -> List[Any]:
        """
        Remove duplicate products by title, keeping the highest-scored version.

        Args:
            products: List of product dictionaries

        Returns:
            Deduplicated list of products
        """
        if not products:
            return products

        seen_titles = {}
        for product in products:
            # Get title (try multiple field names)
            title = (product.get("title") or product.get("name") or "").strip().lower()
            if not title:
                # No title, use ID as key
                title = str(product.get("id", id(product)))

            # Get score for comparison
            score = product.get("score", 0) or product.get("_total_score", 0) or 0

            # Keep the higher-scored version
            if title not in seen_titles or score > seen_titles[title][1]:
                seen_titles[title] = (product, score)

        # Return deduplicated products in original order (by score)
        deduped = [item[0] for item in seen_titles.values()]
        # Sort by score descending
        deduped.sort(key=lambda p: p.get("score", 0) or p.get("_total_score", 0) or 0, reverse=True)
        return deduped

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
                    user_context=user_context,
                )

        # No previous context or couldn't refine - handle as conversation
        return await self._handle_conversation_intent(
            session_id=session_id,
            query=query,
            intent=intent,
            user_context=user_context,
        )

    async def _handle_outfit_building_with_context(
        self,
        session_id: str,
        user_id: str,
        query: str,
        previous_products: List[Dict],
        user_context: Optional[Dict[str, Any]] = None,
        trace: Optional[ExplanationTrace] = None,
    ) -> ARIResponse:
        """
        Handle outfit building queries using previous search results as context.

        When the user says "so I put them together?" or similar follow-ups after
        seeing products, we use those products to provide outfit advice instead
        of doing a fresh search.

        Args:
            session_id: Session identifier
            user_id: User identifier
            query: User's query (e.g., "so I put them together?")
            previous_products: Products from the previous search
            user_context: User context (style preferences, etc.)
            trace: Explanation trace for debugging

        Returns:
            ARIResponse with outfit building advice
        """
        if not self.async_openai_client:
            # Fallback if no LLM available
            product_titles = [p.get('title', 'item')[:50] for p in previous_products[:5]]
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text=(
                    f"Yes! The items I showed you can work well together. "
                    f"Here's what you have: {', '.join(product_titles)}. "
                    "Would you like me to find complementary pieces?"
                ),
                products=previous_products[:5],
                suggestions=[
                    "Find matching accessories",
                    "Show me similar items",
                    "Start a new search",
                ],
            )

        try:
            # Format products for LLM context
            product_descriptions = []
            for i, p in enumerate(previous_products[:5], 1):
                title = p.get('title', 'Unknown item')
                brand = p.get('brand') or p.get('vendor') or ''
                price = p.get('price', '')
                color = p.get('color') or ''
                desc = f"{i}. {title}"
                if brand:
                    desc += f" by {brand}"
                if price:
                    desc += f" (${price})"
                if color:
                    desc += f" - {color}"
                product_descriptions.append(desc)

            products_text = "\n".join(product_descriptions)

            # Build user context string
            context_parts = []
            if user_context:
                if user_context.get('gender'):
                    context_parts.append(f"Gender: {user_context['gender']}")
                if user_context.get('style_words'):
                    context_parts.append(f"Style: {', '.join(user_context['style_words'][:3])}")
            context_str = "; ".join(context_parts) if context_parts else "No specific preferences"

            # Get the original search context for occasion info
            prev_context = self._last_search_context.get(session_id, {})
            original_query = prev_context.get('query', 'fashion items')

            prompt = f"""The user previously searched for: "{original_query}"
I showed them these products:
{products_text}

Now they asked: "{query}"

User context: {context_str}

Provide helpful outfit advice:
1. How do these items work together (or not)?
2. What specific combinations would look good?
3. What's missing to complete the outfit?

Keep response conversational and concise (2-3 sentences max).
Focus on practical styling tips, not generic fashion advice."""

            response = await self.async_openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a personal fashion stylist. Give practical, "
                            "specific outfit advice based on the items shown. "
                            "Be warm but concise."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7,
            )

            outfit_advice = response.choices[0].message.content.strip()

            if trace:
                trace.add_navigation_decision(
                    f"Outfit building with {len(previous_products)} previous products"
                )

            # Generate suggestions based on what might be missing
            suggestions = [
                "Find complementary accessories",
                "Show me shoes to match",
                "Start a new search",
            ]

            return ARIResponse(
                response_type=ResponseType.PRODUCTS,
                products=previous_products[:5],
                text=outfit_advice,
                suggestions=suggestions,
            )

        except Exception as e:
            logger.error(f"Outfit building advice failed: {e}")
            return ARIResponse(
                response_type=ResponseType.PRODUCTS,
                products=previous_products[:5],
                text=(
                    "These pieces can definitely work together! "
                    "Would you like me to find complementary items to complete the look?"
                ),
                suggestions=[
                    "Find matching accessories",
                    "Show me similar items",
                    "Start a new search",
                ],
            )

    async def _handle_profile_update_intent(
        self,
        session_id: str,
        user_id: str,
        query: str,
        intent: IntentResult,
    ) -> ARIResponse:
        """
        Handle user sharing style/preference information to update their profile.

        Uses LLM to extract style preferences from natural language,
        then updates the user's Neo4j profile.
        """
        if not self.async_openai_client:
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text="I'd love to learn more about your style! Tell me what you like.",
                suggestions=["I prefer minimalist style", "I love vintage fashion", "My vibe is streetwear"],
            )

        try:
            # Use LLM to extract style information from user message
            extraction_prompt = f"""Extract style/profile information from this user message.
User said: "{query}"

Extract any information mentioned:
- Gender (if they say "I'm a girl/woman/female" → "female", "I'm a guy/man/male" → "male", else null)
- Style adjectives (e.g., minimalist, boho, hipster, preppy, streetwear, vintage)
- Fashion cultures/aesthetics (e.g., Scandinavian, Japanese, punk, goth)
- Color preferences
- Fit preferences (e.g., oversized, fitted, loose)
- Values (e.g., sustainable, quality, affordable)
- Is this a complaint about previous results? (true if they're saying results were wrong)

Return JSON:
{{
    "gender": "female" or "male" or null,
    "is_complaint": true or false,
    "style_adjectives": ["list of style words"],
    "cultures_aesthetics": ["cultural influences"],
    "colors": ["color preferences"],
    "fits": ["fit preferences"],
    "values": ["value priorities"],
    "summary": "one sentence summary of their style"
}}"""

            response = await self.async_openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You extract style preferences from natural language. Return valid JSON only."},
                    {"role": "user", "content": extraction_prompt}
                ],
                max_tokens=300,
                temperature=0.3,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON
            import json
            try:
                # Handle markdown code blocks safely
                if "```" in result_text:
                    parts = result_text.split("```")
                    if len(parts) >= 2:
                        result_text = parts[1]
                        if result_text.startswith("json"):
                            result_text = result_text[4:]
                style_data = json.loads(result_text)
            except (json.JSONDecodeError, IndexError):
                style_data = {}

            # Extract key fields
            gender = style_data.get("gender")
            is_complaint = style_data.get("is_complaint", False)
            updated_items = []

            # Update user profile in Neo4j if we have data and Neo4j is enabled
            if self.enable_neo4j and style_data and self.navigation and hasattr(self.navigation, 'neo4j_driver'):
                user_graph = None
                try:
                    from ari_v3.services.user_graph_manager import UserGraphManager
                    user_graph = UserGraphManager()

                    # Store gender if extracted
                    if gender:
                        user_graph.update_user_profile(user_id, {"gender": gender})
                        updated_items.append(f"gender:{gender}")
                        logger.info(f"Updated gender for {user_id}: {gender}")
                        # Also store in session for immediate use
                        with self._session_lock:
                            if session_id in self._sessions:
                                self._sessions[session_id]["gender"] = gender

                    # Add style adjectives
                    adjectives = style_data.get("style_adjectives", []) + style_data.get("cultures_aesthetics", [])
                    if adjectives:
                        user_graph.add_style_adjectives(user_id, adjectives)
                        updated_items.extend(adjectives)

                    # Add fit preferences
                    fits = style_data.get("fits", [])
                    if fits:
                        user_graph.add_fit_preferences(user_id, fits)
                        updated_items.extend(fits)

                    # Add values
                    values = style_data.get("values", [])
                    if values:
                        user_graph.add_values(user_id, values)
                        updated_items.extend(values)

                    logger.info(f"Updated profile for {user_id}: {updated_items}")

                    # Invalidate user cache so fresh profile is loaded next time
                    if updated_items:
                        self.invalidate_user_cache(user_id)

                except Exception as e:
                    logger.warning(f"Failed to update Neo4j profile: {e}")
                finally:
                    if user_graph:
                        user_graph.close()
            elif style_data and not self.enable_neo4j:
                # User shared style info but Neo4j is disabled - warn about this
                logger.warning(f"Profile update detected but Neo4j is disabled. Style data not saved: {list(style_data.keys())}")

            # Build response based on what was updated
            # Check if this was a correction after seeing wrong results
            prev_context = self._last_search_context.get(session_id)
            gender_corrected = gender is not None

            if gender_corrected and (is_complaint or prev_context):
                # User corrected their gender after seeing wrong results
                response_text = (
                    "My apologies! I'll keep that in mind. "
                    "What would you like me to find?"
                )
                suggestions = [
                    "Search again for interview outfits",
                    "Show me something else",
                    "Try something different",
                ]
            elif updated_items:
                response_text = (
                    "Got it, noted! What would you like to look for today?"
                )
                suggestions = [
                    "Show me something in my style",
                    "What else should I tell you?",
                    "Find me an outfit",
                ]
            else:
                response_text = (
                    "Thanks for sharing! What can I help you find?"
                )
                suggestions = [
                    "Show me something in my style",
                    "What else should I tell you?",
                    "Find me an outfit",
                ]

            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text=response_text,
                suggestions=suggestions,
            )

        except Exception as e:
            logger.error(f"Profile update failed: {e}")
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text="I heard you! Tell me more about your style and I'll keep it in mind.",
                suggestions=["I like minimalist fashion", "My style is casual", "I prefer quality over quantity"],
            )

    async def _expand_query_with_context(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """
        Always expand queries using conversation history context.

        LLM judges whether the current query is:
        - A CONTINUATION of previous topic → weave in context
        - A NEW TOPIC → return query as-is

        Args:
            query: The current query
            conversation_history: Recent conversation messages

        Returns:
            Context-aware expanded query
        """
        # No conversation history - nothing to expand with
        if not conversation_history:
            return query

        # No LLM client - try simple heuristic
        if not self.async_openai_client:
            # Check for explicit "new topic" signals
            # Use phrase patterns to avoid false positives (e.g., "actually I love that" is continuation)
            query_lower = query.lower()
            new_topic_patterns = [
                "actually show me",      # "actually show me Nike" = new topic
                "actually i want",       # "actually I want something different"
                "instead of",            # "instead of Prada"
                "something different",   # explicit new topic
                "forget that",           # explicit reset
                "never mind",            # explicit reset
                "something else",        # explicit new topic
                "start over",            # explicit reset
                "new search",            # explicit reset
            ]
            if any(pattern in query_lower for pattern in new_topic_patterns):
                return query

            # Extract potential topics from recent conversation
            recent_text = " ".join(
                msg.get("content", "") for msg in conversation_history[-4:]
            ).lower()

            # Look for brand names mentioned - add to query if found
            common_brands = [
                "prada", "gucci", "louis vuitton", "chanel", "dior", "versace",
                "balenciaga", "fendi", "burberry", "armani", "valentino", "hermes",
                "nike", "adidas", "zara", "h&m", "uniqlo", "mango",
            ]
            for brand in common_brands:
                if brand in recent_text and brand not in query_lower:
                    return f"{query} {brand}"

            return query

        # Use LLM to judge context relevance and expand appropriately
        try:
            # Build conversation context
            conv_text = "\n".join(
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in conversation_history[-4:]
            )

            prompt = f"""User's current query: "{query}"

Recent conversation:
{conv_text}

Decide if the current query CONTINUES the previous topic or is a NEW topic.

CONTINUATION signals: query relates to brands/categories/styles discussed earlier
NEW TOPIC signals: "actually", "instead", "different", "forget that", explicitly mentions a different brand/category, or clearly unrelated

If CONTINUATION: Return an expanded query that weaves in relevant context from the conversation.
Examples:
- "blue dress" after Prada discussion → "blue Prada dress"
- "under $200" after handbag discussion → "handbags under $200"
- "show me some" after Nike discussion → "show me Nike products"

If NEW TOPIC: Return the query unchanged.

Return ONLY the final query, nothing else."""

            response = await self.async_openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You help maintain conversation continuity in a shopping assistant. "
                            "Expand queries with relevant context from conversation history, "
                            "but recognize when the user wants to start a new topic. "
                            "Return only the query, no explanation."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=60,
                temperature=0.3,
            )

            expanded = response.choices[0].message.content.strip()

            # Remove quotes if LLM wrapped it
            if expanded.startswith('"') and expanded.endswith('"'):
                expanded = expanded[1:-1]

            # Sanity check - don't return something wildly different or too long
            if expanded and len(expanded) < 150:
                return expanded

            return query

        except Exception as e:
            logger.warning(f"Query context expansion failed: {e}")
            return query

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

    async def _check_catalog_query(
        self,
        query: str,
        session_id: str,
    ) -> Optional[ARIResponse]:
        """
        Check if query is asking about catalog metadata (e.g., "what brands do you have?").

        These queries ask about the catalog itself, not for product searches:
        - "What brands do you have?"
        - "List all luxury brands"
        - "Which designers are available?"
        - "What categories do you carry?"

        Returns:
            ARIResponse if this is a catalog query, None otherwise
        """
        query_lower = query.lower()

        # Patterns that indicate catalog/metadata queries
        catalog_patterns = [
            ("brand", ["what brands", "which brands", "list brands", "show brands",
                      "brands do you have", "brands available", "brands you carry",
                      "luxury brands", "designer brands", "all your brands"]),
            ("category", ["what categories", "which categories", "list categories",
                         "categories do you have", "what do you sell", "what do you carry"]),
            ("designer", ["what designers", "which designers", "list designers",
                         "designers do you have", "designers available"]),
        ]

        catalog_type = None
        for cat_type, patterns in catalog_patterns:
            if any(p in query_lower for p in patterns):
                catalog_type = cat_type
                break

        if not catalog_type:
            return None

        logger.info(f"Detected catalog query: type={catalog_type}")

        # Handle brand catalog query
        if catalog_type in ["brand", "designer"]:
            return await self._get_brand_catalog(query, session_id)

        # Handle category catalog query
        if catalog_type == "category":
            return await self._get_category_catalog(query, session_id)

        return None

    async def _get_brand_catalog(
        self,
        query: str,
        session_id: str,
    ) -> ARIResponse:
        """
        Get list of brands from the catalog.

        Uses Neo4j to query distinct brands.
        """
        query_lower = query.lower()

        # Check if user wants luxury/premium brands specifically
        is_luxury = any(w in query_lower for w in ["luxury", "premium", "designer", "high-end", "high end"])

        try:
            from ari_v3.tools.text2cypher import Text2CypherGenerator

            # Build appropriate Cypher query
            if is_luxury:
                # Query for premium brands (those with products over a certain price threshold)
                cypher = """
                    MATCH (p:Product)
                    WHERE p.extracted_brand IS NOT NULL
                    AND p.price >= 200
                    WITH p.extracted_brand AS brand, MAX(p.price) AS max_price, COUNT(p) AS product_count
                    WHERE product_count >= 5
                    RETURN DISTINCT brand, max_price, product_count
                    ORDER BY max_price DESC
                    LIMIT 30
                """
            else:
                cypher = """
                    MATCH (p:Product)
                    WHERE p.extracted_brand IS NOT NULL
                    WITH p.extracted_brand AS brand, COUNT(p) AS product_count
                    WHERE product_count >= 10
                    RETURN DISTINCT brand, product_count
                    ORDER BY product_count DESC
                    LIMIT 50
                """

            # Execute via Neo4j directly (not through Text2Cypher)
            # Only if Neo4j is enabled
            if self.enable_neo4j and self.navigation and hasattr(self.navigation, 'neo4j_driver'):
                import asyncio

                # Use sync driver in executor to avoid blocking
                driver = self.navigation.neo4j_driver

                def run_cypher():
                    with driver.session(database="neo4j") as neo_session:
                        result = neo_session.run(cypher)
                        return [dict(r) for r in result]

                loop = asyncio.get_event_loop()
                records = await loop.run_in_executor(None, run_cypher)

                if records:
                    brands = [r['brand'] for r in records if r.get('brand')]

                    # Format response
                    if is_luxury:
                        brand_text = ", ".join(brands[:20])
                        response_text = (
                            f"Here are the luxury/premium brands in our catalog:\n\n"
                            f"**{brand_text}**\n\n"
                            f"We have {len(brands)} premium brands with products priced at $200+. "
                            f"Would you like to explore any of these brands?"
                        )
                    else:
                        brand_text = ", ".join(brands[:30])
                        response_text = (
                            f"Here are some of the top brands in our catalog:\n\n"
                            f"**{brand_text}**\n\n"
                            f"We have {len(brands)}+ brands total. "
                            f"Would you like to see products from any specific brand?"
                        )

                    return ARIResponse(
                        response_type=ResponseType.CONVERSATION,
                        text=response_text,
                        suggestions=[
                            f"Show me {brands[0]} products" if brands else "Browse by brand",
                            "Filter by price range",
                            "What categories do you have?",
                        ],
                    )

            # Fallback if Neo4j not available
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text=(
                    "I can help you explore our brands! We carry a wide range including "
                    "luxury designers like Gucci, Prada, Louis Vuitton, Versace, and many more. "
                    "What type of brand are you interested in?"
                ),
                suggestions=[
                    "Show me luxury handbags",
                    "Browse designer sunglasses",
                    "What's your price range?",
                ],
            )

        except Exception as e:
            logger.error(f"Brand catalog query failed: {e}")
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text=(
                    "I'd be happy to tell you about our brands! We carry many luxury and "
                    "designer brands. What type of products or price range are you looking for?"
                ),
                suggestions=[
                    "Show me luxury brands",
                    "What's in my budget?",
                    "Browse by category",
                ],
            )

    async def _get_category_catalog(
        self,
        query: str,
        session_id: str,
    ) -> ARIResponse:
        """Get list of product categories from the catalog."""
        try:
            if self.enable_neo4j and self.navigation and hasattr(self.navigation, 'neo4j_driver'):
                import asyncio

                cypher = """
                    MATCH (p:Product)
                    WHERE p.productType IS NOT NULL
                    WITH p.productType AS category, COUNT(p) AS product_count
                    WHERE product_count >= 50
                    RETURN DISTINCT category, product_count
                    ORDER BY product_count DESC
                    LIMIT 30
                """

                driver = self.navigation.neo4j_driver

                def run_cypher():
                    with driver.session(database="neo4j") as neo_session:
                        result = neo_session.run(cypher)
                        return [dict(r) for r in result]

                loop = asyncio.get_event_loop()
                records = await loop.run_in_executor(None, run_cypher)

                if records:
                    categories = [r['category'] for r in records if r.get('category')]
                    cat_text = ", ".join(categories[:20])

                    return ARIResponse(
                        response_type=ResponseType.CONVERSATION,
                        text=(
                            f"Here are the main categories in our catalog:\n\n"
                            f"**{cat_text}**\n\n"
                            f"We have {len(categories)}+ product categories. "
                            f"What would you like to explore?"
                        ),
                        suggestions=[
                            f"Show me {categories[0]}" if categories else "Browse products",
                            "Filter by brand",
                            "What's trending?",
                        ],
                    )

            # Fallback
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text=(
                    "We carry a wide range of categories including dresses, tops, pants, "
                    "shoes, bags, accessories, and more. What are you in the mood for?"
                ),
                suggestions=["Show me dresses", "Browse accessories", "What's new?"],
            )

        except Exception as e:
            logger.error(f"Category catalog query failed: {e}")
            return ARIResponse(
                response_type=ResponseType.CONVERSATION,
                text="We have many categories to explore! What type of item are you looking for?",
                suggestions=["Dresses", "Tops", "Accessories"],
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
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Load user context from profile, session, or cache with TTL."""
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
                    # Merge session data (e.g., gender, name) if available
                    if session_id:
                        with self._session_lock:
                            session = self._sessions.get(session_id, {})
                            if session.get("gender"):
                                context["gender"] = session["gender"]
                            if session.get("user_name"):
                                context["user_name"] = session["user_name"]
                    return context
                else:
                    # Cache expired, remove it
                    del self._user_context_cache[user_id]

            # Build context from profile
            context: Dict[str, Any] = {"user_id": user_id}

            # Check session for user info (gender, name)
            if session_id:
                with self._session_lock:
                    session = self._sessions.get(session_id, {})
                    if session.get("gender"):
                        context["gender"] = session["gender"]
                    if session.get("user_name"):
                        context["user_name"] = session["user_name"]

            # If gender not in session, try to load from Neo4j (persistent storage)
            if "gender" not in context and self.enable_neo4j:
                try:
                    from ari_v3.services.user_graph_manager import UserGraphManager
                    user_graph = UserGraphManager()
                    try:
                        profile = user_graph.get_user_profile(user_id)
                        if profile:
                            if profile.get("gender"):
                                context["gender"] = profile["gender"]
                            if profile.get("username"):
                                context["user_name"] = profile["username"]
                            if profile.get("gender_expression"):
                                context["gender_expression"] = profile["gender_expression"]
                    finally:
                        user_graph.close()
                except Exception as e:
                    logger.debug(f"Could not load user profile from Neo4j: {e}")

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

    def _build_qdrant_filter(self, params, semantic_expansion=None) -> Optional[Filter]:
        """
        Build Qdrant filter for EXPLICIT NUMERIC constraints only.

        PHILOSOPHY: ARI navigates style space through semantic understanding,
        NOT through hardcoded category/tier filters. The embedding model and
        semantic query expansion naturally navigate to the correct region.

        Only explicit numeric price constraints (e.g., "under $50", "$100-200")
        use hard filters. Everything else flows through semantic search:
        - "luxury" / "premium" → semantic query includes luxury descriptors
        - "budget" / "affordable" → semantic query includes budget-friendly terms
        - categories, styles, vibes → all handled by embedding similarity

        Args:
            params: ExtractedParameters - only price_range (explicit $) used
            semantic_expansion: Optional SemanticQuery (expanded_query used, not filters)

        Returns:
            Qdrant Filter object or None if no explicit numeric constraints
        """
        if not QDRANT_FILTER_AVAILABLE:
            logger.debug("Qdrant filter not available, skipping")
            return None

        conditions = []

        # ONLY filter by explicit numeric price range (actual dollar amounts)
        # All other attributes flow through semantic search for style space navigation
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
                logger.info(f"Price constraint (explicit $): {range_filter}")

        # All other attributes handled by semantic navigation:
        # - price_tier → expanded in semantic query ("luxury designer high-end")
        # - premium → expanded in semantic query ("premium quality upscale")
        # - categories → expanded in semantic query (navigation destination)
        # - styles/vibes → core of semantic understanding
        #
        # This aligns with ARI's philosophy: navigate style space, don't filter it

        if not conditions:
            return None

        return Filter(must=conditions)

    async def _search_neo4j_text2cypher(
        self,
        query: str,
        limit: int = 50,
        context: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search for products using LLM-powered Text2Cypher query generation.

        This is a general-purpose Neo4j search that works with ANY field:
        brand, color, price, style, material, etc. The LLM generates the
        appropriate Cypher query based on the natural language input.

        Args:
            query: Natural language query (e.g., "Gucci handbags under $500")
            limit: Maximum products to return
            context: Additional context for query generation

        Returns:
            List of product dicts with normalized fields
        """
        try:
            from ari_v3.tools.text2cypher import execute_text2cypher_query

            records, cypher_query = await execute_text2cypher_query(
                query=query,
                async_openai_client=self.async_openai_client,
                limit=limit,
                context=context,
            )

            # Normalize results to orchestrator's expected format
            products = []
            for record in records:
                # Handle both direct dict and 'p' node wrapper
                p = record.get('p', record)
                if isinstance(p, dict):
                    products.append({
                        'uuid': p.get('id') or p.get('uuid'),
                        'title': p.get('title') or p.get('name'),
                        'brand': p.get('extracted_brand') or p.get('brand'),
                        'vendor': p.get('extracted_brand') or p.get('brand'),
                        'price': p.get('price'),
                        'description': p.get('description'),
                        'styles': p.get('extracted_styles') or p.get('styles') or [],
                        'colors': p.get('extracted_colors') or p.get('colors') or [],
                        'images': p.get('images') or [],
                    })

            logger.info(
                f"Text2Cypher search returned {len(products)} products. "
                f"Fields searched: {cypher_query.search_fields}. "
                f"Reasoning: {cypher_query.reasoning[:100]}"
            )
            return products

        except Exception as e:
            logger.warning(f"Text2Cypher search failed: {e}")
            return []

    def _query_needs_structured_search(self, query: str, params) -> bool:
        """
        Detect if a query would benefit from Neo4j's structured fields.

        Returns True if the query contains patterns that need:
        - Brand filtering (extracted_brand field)
        - Specific attribute lookups (extracted_colors, extracted_styles)
        - Complex price + attribute combinations

        These are better served by Neo4j's structured data than Qdrant's
        semantic embedding search.
        """
        query_lower = query.lower()

        # Brand-related patterns (Neo4j has extracted_brand, Qdrant doesn't)
        brand_patterns = [
            "by ", "from ", "brand", " made by",
            "designer", "luxury brand", "show me all ",
        ]
        if any(p in query_lower for p in brand_patterns):
            return True

        # Specific attribute queries (Neo4j has structured fields)
        # "all black products", "products in red", etc.
        color_attribute_patterns = [
            "all ", "only ", "products in ", "items in ",
            "everything in ", "show me ", "list all ",
        ]
        color_words = ["black", "white", "red", "blue", "green", "navy", "pink", "beige"]
        for pattern in color_attribute_patterns:
            for color in color_words:
                if f"{pattern}{color}" in query_lower:
                    return True

        # Price + attribute combinations
        # "cheap Nike", "luxury Gucci", "affordable designer"
        if params.brand_preferences and (
            "cheap" in query_lower or
            "affordable" in query_lower or
            "luxury" in query_lower or
            "expensive" in query_lower or
            "under $" in query_lower or
            "over $" in query_lower
        ):
            return True

        return False

    def _apply_brand_filter(self, products: List[Dict], brand_preferences: List[str]) -> List[Dict]:
        """
        Filter products to only include those matching requested brands.

        Fallback method when Neo4j brand search is unavailable.
        Checks if brand name appears in title, vendor, or brand fields.

        Args:
            products: List of product dicts
            brand_preferences: List of brand names to filter for

        Returns:
            Filtered list containing only products from requested brands
        """
        if not brand_preferences:
            return products

        # Normalize brand names for comparison
        brands_lower = [b.lower() for b in brand_preferences]

        filtered = []
        for product in products:
            title = (product.get('title') or '').lower()
            vendor = (product.get('vendor') or '').lower()
            brand = (product.get('brand') or '').lower()

            # Check if any requested brand appears in product
            for brand_name in brands_lower:
                if brand_name in title or brand_name in vendor or brand_name in brand:
                    filtered.append(product)
                    break

        return filtered

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

    def update_session_data(self, session_id: str, data: Dict[str, Any]) -> None:
        """
        Update session with additional data (e.g., user_name, gender).

        Args:
            session_id: Session identifier
            data: Dictionary of key-value pairs to add to session
        """
        with self._session_lock:
            if session_id in self._sessions:
                self._sessions[session_id].update(data)
            else:
                # Create session if it doesn't exist (include required fields)
                self._sessions[session_id] = {
                    "created_at": datetime.now(),
                    "last_access": datetime.now(),
                    "query_count": 0,
                    **data,
                }

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
