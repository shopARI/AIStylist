"""
CrewAI Orchestrator
Replaces BattleOrchestrator with CrewAI-based implementation.
Maintains API compatibility with existing ApplicationService.

Now includes intent detection and routing to appropriate crews.
Supports both V1 (agent-based) and V2 (pure flow) implementations.
"""
import logging
import time
import hashlib
import json
import sys
import os
from typing import Dict, List, Any, Optional, Union

# Add parent directory to path for imports
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration')

from crews.product_search_crew import ProductSearchCrew, load_and_create_crew
from crews.mini_crews import (
    create_graph_search_crew,
    create_vector_search_crew,
    create_visual_search_crew,
    create_judge_crew
)
from flows import create_and_run_flow
from flows.product_search_flow_v2 import create_and_run_flow_v2
from memory.mem0_memory_provider import create_mem0_memory_provider
from nlp.hybrid_intent_detector import get_hybrid_intent_detector, DetectionStrategy
from models.types import SearchIntent

# Create logger first
logger = logging.getLogger("crewai.orchestrator")

# Import ML Intelligence Coordinator
try:
    sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')
    from services.ml.intelligence.coordinator import IntelligenceCoordinator
    ML_INTELLIGENCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ML Intelligence Coordinator not available: {e}")
    ML_INTELLIGENCE_AVAILABLE = False

# Import ConversationHandler for natural language responses
try:
    from services.conversation_handler import ConversationHandler
    CONVERSATION_HANDLER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ConversationHandler not available: {e}")
    CONVERSATION_HANDLER_AVAILABLE = False


class CrewAIOrchestrator:
    """
    Orchestrator for CrewAI-based search with intent detection.
    Routes queries to appropriate crews based on detected intent.
    Drop-in replacement for BattleOrchestrator with same API.
    """

    def __init__(
        self,
        crew: Optional[ProductSearchCrew] = None,
        cache_service=None,
        metrics_service=None,
        redis_client=None,
        process_type: str = "sequential",  # Changed from hierarchical to fix infinite loop
        intent_strategy: DetectionStrategy = DetectionStrategy.LLM_FIRST,
        intelligence_coordinator: Optional[Any] = None,
        enable_ml_intelligence: bool = True,
        use_flow_v2: bool = None  # None = check env var, True/False = explicit override
    ):
        """
        Initialize CrewAI orchestrator with intent detection and ML intelligence.

        Args:
            crew: Optional pre-configured ProductSearchCrew
            cache_service: Cache service for result caching
            metrics_service: Metrics service for monitoring
            redis_client: Redis client for state management
            process_type: "hierarchical" or "sequential"
            intent_strategy: Intent detection strategy (LLM_FIRST recommended)
            intelligence_coordinator: Optional ML Intelligence Coordinator
            enable_ml_intelligence: Enable ML intelligence generation (default: True)
            use_flow_v2: Use V2 pure flow (no agent overhead). None = check USE_FLOW_V2 env var
        """
        self.cache = cache_service
        self.metrics = metrics_service
        self.redis = redis_client
        self.process_type = process_type

        # Determine flow version (V1 agent-based or V2 pure flow)
        if use_flow_v2 is None:
            self.use_flow_v2 = os.getenv("USE_FLOW_V2", "false").lower() in ("true", "1", "yes")
        else:
            self.use_flow_v2 = use_flow_v2

        logger.info(f"Flow version: {'V2 (pure flow - no agent overhead)' if self.use_flow_v2 else 'V1 (agent-based)'}")

        # Initialize intent detector
        logger.info(f"Initializing intent detector with strategy: {intent_strategy.value}")
        self.intent_detector = get_hybrid_intent_detector(strategy=intent_strategy)

        # Initialize ML Intelligence Coordinator
        self.intelligence_coordinator = intelligence_coordinator
        self.enable_ml_intelligence = enable_ml_intelligence and ML_INTELLIGENCE_AVAILABLE

        if self.enable_ml_intelligence:
            if self.intelligence_coordinator:
                logger.info("ML Intelligence Coordinator provided - will generate ML context")
            else:
                logger.info("ML Intelligence enabled but no coordinator provided - will create if needed")
        else:
            logger.info("ML Intelligence disabled or unavailable")

        # Initialize ConversationHandler for natural language responses
        self.conversation_handler = None
        if CONVERSATION_HANDLER_AVAILABLE:
            try:
                self.conversation_handler = ConversationHandler(
                    redis_client=redis_client,
                    enable_persistence=False,  # Disable for now
                    enable_optimization=True
                )
                logger.info("ConversationHandler initialized - natural language responses enabled")
            except Exception as e:
                logger.error(f"Failed to initialize ConversationHandler: {e}")
        else:
            logger.warning("ConversationHandler unavailable - will use fallback responses")

        # Initialize mini-crews for Flow-based execution (only needed for V1)
        if not self.use_flow_v2:
            logger.info("Initializing mini-crews for ProductSearchFlow V1 (agent-based)...")
            self.graph_crew = create_graph_search_crew()
            self.vector_crew = create_vector_search_crew()
            self.visual_crew = create_visual_search_crew()
            self.judge_crew = create_judge_crew()

            # Keep old crew for backward compatibility (deprecated)
            if crew:
                self.product_crew = crew
            else:
                logger.info(f"Loading legacy {process_type} product search crew (deprecated)")
                base_crew = load_and_create_crew(process_type=process_type)
                self.product_crew = ProductSearchCrew(base_crew)
        else:
            logger.info("Using ProductSearchFlow V2 (pure flow) - no agent/crew initialization needed")
            self.graph_crew = None
            self.vector_crew = None
            self.visual_crew = None
            self.judge_crew = None
            self.product_crew = None

        # Conversation crew will be created when needed (lazy loading)
        self._conversation_crew = None

        # Track intent routing and ML intelligence stats
        self.routing_stats = {
            "total_queries": 0,
            "product_intents": 0,
            "conversation_intents": 0,
            "intent_detection_time": [],
            "ml_intelligence_generated": 0,
            "ml_intelligence_time": []
        }

        logger.info("CrewAI Orchestrator initialized with intent detection and ML intelligence support")

    async def execute_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        bypass_cache: bool = False
    ) -> Dict[str, Any]:
        """
        Execute search with intent detection and routing.
        Detects intent, then routes to appropriate crew (product or conversation).
        Maintains BattleOrchestrator API compatibility.

        Args:
            query: User search query
            filters: Search filters (category, price, etc.)
            limit: Maximum products to return
            user_context: User preferences and history
            ml_intelligence: ML-generated context
            conversation_context: Conversation state
            bypass_cache: Skip cache lookup

        Returns:
            Dictionary with products/response and metadata
        """
        search_start = time.time()
        self.routing_stats["total_queries"] += 1

        try:
            # Step 1: Detect intent (with conversation context for continuity)
            logger.info(f"Detecting intent for query: '{query[:50]}...'")
            intent_start = time.time()

            # Get conversation history for context-aware intent detection
            conversation_hist = []
            if self.conversation_handler and conversation_context:
                session_id = conversation_context.get('session_id', 'default')
                # Get last few messages from conversation handler
                session_messages = self.conversation_handler.conversations.get(session_id, [])
                if session_messages:
                    # Convert Message objects to dicts for intent detector
                    conversation_hist = [
                        {"role": msg.role.value, "content": msg.content}
                        for msg in session_messages[-5:]  # Last 5 messages
                    ]

            # Suppress EventBus errors from CrewAI's internal task tracking
            import sys
            import io
            import contextlib

            # Create a context manager that suppresses both stdout and stderr
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                intent_result = await self.intent_detector.detect_intent_and_extract(
                    query,
                    conversation_history=conversation_hist
                )

            intent_time = time.time() - intent_start
            self.routing_stats["intent_detection_time"].append(intent_time)

            logger.info(
                f"Intent detected: {intent_result.primary_intent.name} "
                f"(confidence: {intent_result.confidence:.2f}, "
                f"method: {intent_result.detection_method}, "
                f"time: {intent_time*1000:.0f}ms)"
            )

            # Step 2: Check cache (intent-aware)
            if self.cache and not bypass_cache:
                cache_key = self._make_cache_key(
                    query,
                    filters or {},
                    limit,
                    intent_result.primary_intent.name
                )
                cached = await self.cache.get(cache_key)

                if cached:
                    logger.info(f"Cache hit for query: '{query[:30]}...'")
                    if self.metrics:
                        self.metrics.record_cache_hit(query, cached)
                    return cached

            # Step 3: Generate ML Intelligence (if enabled and product intent)
            is_conversation = self._is_conversation_intent(intent_result.primary_intent)
            generated_intelligence = ml_intelligence or {}

            if not is_conversation and self.enable_ml_intelligence and self.intelligence_coordinator:
                try:
                    logger.info("Generating ML intelligence for product search...")
                    ml_start = time.time()

                    generated_intelligence = await self.intelligence_coordinator.gather_intelligence(
                        query=query,
                        user_id=user_context.get('user_id') if user_context else None,
                        session_id=conversation_context.get('session_id') if conversation_context else None,
                        context={
                            'intent': intent_result.primary_intent.name,
                            'parameters': intent_result.extracted_parameters,
                            'filters': filters
                        }
                    )

                    ml_time = time.time() - ml_start
                    self.routing_stats["ml_intelligence_generated"] += 1
                    self.routing_stats["ml_intelligence_time"].append(ml_time)

                    logger.info(
                        f"ML Intelligence generated in {ml_time:.2f}s - "
                        f"Sources: {len(generated_intelligence.get('metadata', {}).get('sources', []))}"
                    )

                except Exception as e:
                    logger.error(f"ML Intelligence generation failed: {e}")
                    # Continue without ML intelligence

            # Step 4: Route to appropriate crew based on intent
            if is_conversation:
                self.routing_stats["conversation_intents"] += 1
                logger.info(f"Routing to CONVERSATION crew for: {intent_result.primary_intent.name}")
                result = await self._handle_conversation(
                    query=query,
                    intent_result=intent_result,
                    user_context=user_context,
                    conversation_context=conversation_context
                )
            else:
                self.routing_stats["product_intents"] += 1
                flow_version = "V2 (pure flow)" if self.use_flow_v2 else "V1 (agent-based)"
                logger.info(f"Routing to PRODUCT SEARCH FLOW {flow_version} for: {intent_result.primary_intent.name}")

                # Merge detected parameters with provided filters
                merged_filters = self._merge_filters(filters, intent_result.extracted_parameters)

                # Choose flow implementation based on configuration
                if self.use_flow_v2:
                    # V2: Pure flow (no agent overhead)
                    logger.info("Executing V2 pure flow...")
                    flow_result = await create_and_run_flow_v2(
                        query=query,
                        filters=merged_filters,
                        limit=limit,
                        user_context=user_context,
                        ml_intelligence=generated_intelligence,
                        conversation_context=conversation_context
                    )
                else:
                    # V1: Agent-based flow with mini-crews
                    logger.info("Executing V1 agent-based flow...")
                    flow_result = await create_and_run_flow(
                        query=query,
                        filters=merged_filters,
                        limit=limit,
                        user_context=user_context,
                        ml_intelligence=generated_intelligence,
                        conversation_context=conversation_context,
                        graph_crew=self.graph_crew,
                        vector_crew=self.vector_crew,
                        visual_crew=self.visual_crew,
                        judge_crew=self.judge_crew
                    )

                # Convert Pydantic result to dict for compatibility
                result = {
                    "products": [p.dict() for p in flow_result.products],
                    "reasoning": flow_result.reasoning,
                    "metadata": flow_result.metadata
                }
                result["metadata"]["graph_count"] = flow_result.graph_count
                result["metadata"]["vector_count"] = flow_result.vector_count
                result["metadata"]["visual_count"] = flow_result.visual_count
                result["metadata"]["consensus_count"] = flow_result.consensus_count
                result["metadata"]["quality_controlled"] = flow_result.quality_controlled
                result["metadata"]["flow_version"] = "v2" if self.use_flow_v2 else "v1"

                # Track product search in conversation history (for memory continuity)
                if self.conversation_handler and conversation_context:
                    from services.conversation_handler import Message, MessageRole
                    from datetime import datetime

                    session_id = conversation_context.get('session_id', 'default')

                    # Add user search query
                    user_message = Message(
                        role=MessageRole.USER,
                        content=query,
                        timestamp=datetime.now(),
                        metadata={"intent": intent_result.primary_intent.name, "type": "product_search"}
                    )
                    await self.conversation_handler._add_message(session_id, user_message)

                    # Add system response summarizing results
                    product_count = len(result["products"])
                    if product_count > 0:
                        top_products = [p.get('title', 'Unknown') for p in result["products"][:3]]
                        summary = f"Found {product_count} products: {', '.join(top_products[:2])}" + (f", and {product_count-2} more" if product_count > 2 else "")
                    else:
                        summary = "No products found for that search."

                    assistant_message = Message(
                        role=MessageRole.ASSISTANT,
                        content=summary,
                        timestamp=datetime.now(),
                        metadata={"intent": intent_result.primary_intent.name, "type": "product_search_result", "count": product_count}
                    )
                    await self.conversation_handler._add_message(session_id, assistant_message)

            # Add execution time and intent metadata
            execution_time = time.time() - search_start
            result['execution_time'] = execution_time
            result['orchestration_method'] = 'crewai_' + self.process_type
            result['intent'] = {
                'primary_intent': intent_result.primary_intent.name,
                'confidence': intent_result.confidence,
                'detection_method': intent_result.detection_method,
                'detection_time': intent_time,
                'parameters': intent_result.extracted_parameters
            }

            # Cache result
            if self.cache and result.get("products"):
                cache_data = {
                    "products": result["products"],
                    "reasoning": result.get("reasoning", ""),
                    "metadata": result.get("metadata", {}),
                    "execution_time": execution_time,
                    "cached_at": time.time()
                }

                await self.cache.set(cache_key, cache_data, ttl=180)
                logger.info(f"Cached CrewAI result: {len(result['products'])} products")

            # Record metrics
            if self.metrics:
                self.metrics.record_search(
                    query=query,
                    result_count=len(result.get("products", [])),
                    execution_time=execution_time,
                    orchestration_method='crewai_' + self.process_type
                )

            logger.info(f"CrewAI search complete in {execution_time:.2f}s: {len(result.get('products', []))} products")
            return result

        except Exception as e:
            logger.error(f"CrewAI search failed: {e}", exc_info=True)

            if self.metrics:
                self.metrics.record_error(query, str(e))

            return {
                "products": [],
                "reasoning": f"Search failed: {str(e)}",
                "metadata": {
                    "error": str(e),
                    "execution_time": time.time() - search_start
                }
            }

    def _is_conversation_intent(self, intent: SearchIntent) -> bool:
        """
        Determine if intent should route to conversation crew.

        Args:
            intent: Detected SearchIntent

        Returns:
            True if conversation intent, False if product intent
        """
        conversation_intents = {
            SearchIntent.CONVERSATION_HISTORY,
            SearchIntent.MEMORY_QUERY,
            SearchIntent.CLARIFICATION,
            SearchIntent.SYSTEM_STATUS,
            SearchIntent.GENERAL_CONVERSATION
        }
        return intent in conversation_intents

    async def _handle_conversation(
        self,
        query: str,
        intent_result,
        user_context: Optional[Dict[str, Any]],
        conversation_context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Handle conversation intents using ConversationHandler.
        Returns conversational response instead of products.

        Args:
            query: User query
            intent_result: Intent detection result
            user_context: User preferences and history
            conversation_context: Conversation state

        Returns:
            Dictionary with response and metadata
        """
        intent_name = intent_result.primary_intent.name

        # Use ConversationHandler for natural GPT-like responses
        # FAIL FAST: No fallbacks - if ConversationHandler fails, raise exception
        if not self.conversation_handler:
            raise RuntimeError("ConversationHandler not initialized - cannot handle conversation intent")

        # Get session ID from conversation context
        session_id = conversation_context.get('session_id', 'default') if conversation_context else 'default'
        user_id = user_context.get('user_id') if user_context else None

        # Add user message to conversation history (for memory continuity)
        from services.conversation_handler import Message, MessageRole
        from datetime import datetime

        user_message = Message(
            role=MessageRole.USER,
            content=query,
            timestamp=datetime.now(),
            metadata={"intent": intent_name, "confidence": intent_result.confidence}
        )
        await self.conversation_handler._add_message(session_id, user_message)

        # Generate natural conversational response using GPT
        # Let exceptions propagate - fail fast instead of silent fallback
        response_text = await self.conversation_handler.generate_conversational_response(
            session_id=session_id,
            message=query,
            user_id=user_id
        )

        # Add assistant response to conversation history
        assistant_message = Message(
            role=MessageRole.ASSISTANT,
            content=response_text,
            timestamp=datetime.now(),
            metadata={"intent": intent_name}
        )
        await self.conversation_handler._add_message(session_id, assistant_message)

        logger.info(f"ConversationHandler generated response for: '{query[:50]}...'")

        return {
            "products": [],
            "response": response_text,
            "reasoning": f"Conversation intent ({intent_name}) detected - ConversationHandler generated GPT response",
            "metadata": {
                "intent": intent_name,
                "confidence": intent_result.confidence,
                "is_conversation": True,
                "conversation_context": conversation_context,
                "handler": "ConversationHandler_GPT"
            }
        }

    def _merge_filters(
        self,
        provided_filters: Optional[Dict[str, Any]],
        extracted_parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge provided filters with intent-extracted parameters.
        Provided filters take precedence.

        Args:
            provided_filters: Filters from API call
            extracted_parameters: Parameters from intent detection

        Returns:
            Merged filter dictionary
        """
        merged = {}

        # Start with extracted parameters
        if extracted_parameters:
            # Map intent parameters to filter format
            if 'categories' in extracted_parameters and extracted_parameters['categories']:
                merged['category'] = extracted_parameters['categories'][0]
            if 'colors' in extracted_parameters and extracted_parameters['colors']:
                merged['colors'] = extracted_parameters['colors']
            if 'occasions' in extracted_parameters and extracted_parameters['occasions']:
                merged['occasion'] = extracted_parameters['occasions'][0]
            if 'price_range' in extracted_parameters:
                merged['price_range'] = extracted_parameters['price_range']
            if 'brand_preferences' in extracted_parameters and extracted_parameters['brand_preferences']:
                merged['brand'] = extracted_parameters['brand_preferences'][0]

        # Override with provided filters
        if provided_filters:
            merged.update(provided_filters)

        return merged

    def _make_cache_key(
        self,
        query: str,
        filters: Dict,
        limit: int,
        intent: Optional[str] = None
    ) -> str:
        """
        Create deterministic cache key with intent awareness.

        Args:
            query: Search query
            filters: Search filters
            limit: Result limit
            intent: Detected intent (optional)

        Returns:
            Cache key string
        """
        key_data = {
            "query": query.lower().strip(),
            "filters": sorted(filters.items()) if filters else [],
            "limit": limit,
            "intent": intent or "unknown"
        }

        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get orchestrator statistics including intent routing and ML intelligence.

        Returns:
            Dictionary with statistics
        """
        stats = {
            "orchestrator_type": "crewai_with_intent_and_ml",
            "process_type": self.process_type,
            "crew_agents": len(self.product_crew.crew.agents) if hasattr(self.product_crew.crew, 'agents') else 0,
            "crew_tasks": len(self.product_crew.crew.tasks) if hasattr(self.product_crew.crew, 'tasks') else 0,
            "routing": self.routing_stats.copy(),
            "ml_intelligence_enabled": self.enable_ml_intelligence
        }

        # Add intent detector stats
        try:
            stats["intent_detection"] = self.intent_detector.get_stats()
        except Exception as e:
            logger.warning(f"Failed to get intent detector stats: {e}")

        # Calculate average intent detection time
        if self.routing_stats["intent_detection_time"]:
            avg_time = sum(self.routing_stats["intent_detection_time"]) / len(self.routing_stats["intent_detection_time"])
            stats["routing"]["avg_intent_detection_time"] = f"{avg_time*1000:.0f}ms"

        # Calculate average ML intelligence time
        if self.routing_stats["ml_intelligence_time"]:
            avg_ml_time = sum(self.routing_stats["ml_intelligence_time"]) / len(self.routing_stats["ml_intelligence_time"])
            stats["routing"]["avg_ml_intelligence_time"] = f"{avg_ml_time*1000:.0f}ms"

        # Add ML Intelligence Coordinator stats
        if self.intelligence_coordinator:
            try:
                stats["ml_intelligence"] = self.intelligence_coordinator.get_stats()
            except Exception as e:
                logger.warning(f"Failed to get ML intelligence stats: {e}")

        if self.cache:
            try:
                stats["cache"] = await self.cache.get_stats()
            except Exception as e:
                logger.warning(f"Failed to get cache stats: {e}")

        if self.metrics:
            try:
                stats["metrics"] = self.metrics.get_summary()
            except Exception as e:
                logger.warning(f"Failed to get metrics: {e}")

        return stats


def create_crewai_orchestrator(
    cache_service=None,
    metrics_service=None,
    redis_client=None,
    process_type: str = "sequential",  # Changed from hierarchical to fix infinite loop
    intent_strategy: DetectionStrategy = DetectionStrategy.LLM_FIRST,
    intelligence_coordinator=None,
    enable_ml_intelligence: bool = True
) -> CrewAIOrchestrator:
    """
    Factory function to create CrewAI orchestrator with intent detection and ML intelligence.

    Args:
        cache_service: Optional cache service
        metrics_service: Optional metrics service
        redis_client: Optional Redis client
        process_type: "hierarchical" or "sequential"
        intent_strategy: Intent detection strategy (LLM_FIRST recommended)
        intelligence_coordinator: Optional ML Intelligence Coordinator
        enable_ml_intelligence: Enable ML intelligence generation (default: True)

    Returns:
        CrewAIOrchestrator instance with intent detection and ML intelligence
    """
    return CrewAIOrchestrator(
        cache_service=cache_service,
        metrics_service=metrics_service,
        redis_client=redis_client,
        process_type=process_type,
        intent_strategy=intent_strategy,
        intelligence_coordinator=intelligence_coordinator,
        enable_ml_intelligence=enable_ml_intelligence
    )
