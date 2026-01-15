"""
ARI V3 - Step 8: Navigation Intelligence Orchestrator

This module ties together all components to provide the full navigation flow:
- Step 1: Load raw user data (Pillar 1)
- Step 2: Compute user state (Pillar 1)
- Step 3: Get behavioral patterns (Pillar 3 - placeholder)
- Step 4: Retrieve stylist knowledge (Pillar 2)
- Step 5: LLM Synthesis
- Step 6: Compute destination from exemplars
- Step 7: Calculate navigation path

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 4 and 6
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np
from openai import OpenAI

from ari_v3.core.data_structures import (
    StyleContext,
    RawUserData,
    ComputedUserState,
    StyleCoordinate,
    zero_vector,
)
from ari_v3.pillars.personalization import (
    Pillar1_Personalization,
    QueryContext,
)
from ari_v3.pillars.stylist_knowledge import (
    Pillar2_StylistKnowledge,
    StylingContext,
    MultiPerspectiveResult,
)
from ari_v3.navigation.navigation_context import (
    NavigationContext,
    NavigationPath,
    BehavioralProfile,
    DriftAnalysis,
    calculate_navigation_path,
    create_cold_start_context,
)
from ari_v3.navigation.synthesis_llm import (
    SynthesisLLM,
    SynthesisOutput,
    ThreePillarsInput,
    BudgetInterpretation,
)
from ari_v3.navigation.constants import (
    TEXT_EMBEDDING_DIM,
    VISUAL_EMBEDDING_DIM,
    FALLBACK_BUDGET_MIN,
    FALLBACK_BUDGET_MAX,
    COLD_START_FORMALITY,
    COLD_START_RESULT_SET_SIZE,
    COLD_START_DIVERSITY_REQUIREMENT,
)

if TYPE_CHECKING:
    from ari_v3.judge import ARIEvaluator, ScoredProduct
    from ari_v3.narrative import NarrativeLLM, JourneyNarrative

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result of a complete recommendation search."""
    products: List[Any]
    narrative: Optional[Any] = None
    path: Optional[NavigationPath] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NavigationIntelligence:
    """
    V3 Navigation Intelligence Core.

    Orchestrates the generation of NavigationContext by combining
    all three pillars and the synthesis LLM.
    """

    def __init__(
        self,
        neo4j_driver=None,
        qdrant_client=None,
        openai_client: Optional[OpenAI] = None,
        embedding_service=None,
    ):
        """
        Initialize the Navigation Intelligence engine.

        Args:
            neo4j_driver: Neo4j driver for user data
            qdrant_client: Qdrant client for vector search
            openai_client: OpenAI client for LLM and embeddings
            embedding_service: Service for computing embeddings
        """
        self.neo4j_driver = neo4j_driver
        self.qdrant_client = qdrant_client
        self.openai_client = openai_client or OpenAI()
        self.embedding_service = embedding_service

        # Initialize pillar modules
        self.pillar1 = Pillar1_Personalization(
            neo4j_driver=neo4j_driver,
            embedding_service=embedding_service,
        )
        self.pillar2 = Pillar2_StylistKnowledge(
            qdrant_client=qdrant_client,
            embedding_service=embedding_service,
        )
        self.synthesis_llm = SynthesisLLM(
            openai_client=self.openai_client,
        )

    async def generate_navigation_context(
        self,
        user_id: str,
        query: str,
        occasion: Optional[str] = None,
    ) -> NavigationContext:
        """
        Main entry point for generating navigation context.

        Executes the full navigation flow:
        1. Load raw user data
        2. Compute user state
        3. Get behavioral patterns
        4. Retrieve stylist knowledge
        5. LLM Synthesis
        6. Compute destination from exemplars
        7. Calculate navigation path

        Args:
            user_id: User identifier
            query: Search query
            occasion: Optional occasion context

        Returns:
            Complete NavigationContext for agent search
        """
        # Input validation
        if not user_id:
            raise ValueError("user_id cannot be empty")
        if not query:
            raise ValueError("query cannot be empty")

        # Log with truncated user_id for privacy (show first 8 chars only)
        user_id_short = user_id[:8] + "..." if len(user_id) > 8 else user_id
        logger.info(f"Generating navigation context for user {user_id_short}, query: '{query}'")

        # Step 1: Load raw user data
        raw_user_data = self.pillar1.load_raw_user_data(user_id)

        if raw_user_data is None:
            logger.info(f"No user data found for {user_id_short}, using cold start")
            return self._create_cold_start_context(query, occasion)

        # Step 2: Compute user state
        query_context = QueryContext(
            occasion=occasion,
            query_text=query,
        )
        computed_state = self.pillar1.compute_user_state(raw_user_data, query_context)

        # Step 3: Get behavioral patterns (Pillar 3)
        behavioral_profile, drift_analysis = await self._get_behavioral_patterns(
            user_id,
            computed_state,
        )

        # Step 4: Retrieve stylist knowledge (Pillar 2)
        styling_rules, body_guidance, occasion_guidance, perspectives = await self._get_stylist_knowledge(
            raw_user_data,
            computed_state,
            query,
            occasion,
        )

        # Step 5: LLM Synthesis
        pillars_input = self._build_pillars_input(
            raw_user_data,
            computed_state,
            body_guidance,
            occasion_guidance,
            perspectives,
            behavioral_profile,
            drift_analysis,
        )

        try:
            synthesis = self.synthesis_llm.synthesize_navigation(
                pillars=pillars_input,
                query=query,
                occasion=occasion,
            )
            logger.info(f"Synthesis completed: {len(synthesis.style_descriptors)} descriptors")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            logger.error(f"Synthesis LLM failed: {e}")
            # Use fallback synthesis (BudgetInterpretation already imported at top)
            synthesis = SynthesisOutput(
                style_descriptors=[query],
                exemplar_search_terms=[query],
                understood_intent=f"Looking for {query}",
                budget_interpretation=BudgetInterpretation(
                    min=FALLBACK_BUDGET_MIN,
                    max=FALLBACK_BUDGET_MAX,
                ),
                formality_level=COLD_START_FORMALITY,
                relevant_context=["fallback due to synthesis error"],
            )

        # Step 6: Compute destination from exemplars
        try:
            if self.qdrant_client:
                destination = await self.synthesis_llm.compute_destination_from_synthesis_async(
                    synthesis=synthesis,
                    qdrant_client=self.qdrant_client,
                )
            else:
                destination = self.synthesis_llm.compute_destination_from_synthesis(
                    synthesis=synthesis,
                )
            logger.info("Destination computed from exemplars")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            logger.error(f"Destination computation failed: {e}")
            # Fallback to zero vector
            destination = StyleCoordinate(
                embedding=zero_vector(TEXT_EMBEDDING_DIM),
                visual_embedding=zero_vector(VISUAL_EMBEDDING_DIM),
            )

        # Step 7: Calculate navigation path
        # Safely access position and trajectory from active_position
        if computed_state.active_position is None:
            logger.warning("No active position in computed state, using destination as current")
            current_position = destination
            trajectory = None
        else:
            current_position = computed_state.active_position.position
            trajectory = computed_state.active_position.trajectory
        nav_params = computed_state.nav_params

        path = calculate_navigation_path(
            current=current_position,
            destination=destination,
            trajectory=trajectory,
            nav_params=nav_params,
        )

        logger.info(f"Navigation context generated: destination computed from {len(synthesis.exemplar_search_terms)} exemplars")

        return NavigationContext(
            current_position=current_position,
            trajectory=trajectory,
            destination=destination,
            path=path,
            query=query,
            occasion=occasion,
            raw_user_data=raw_user_data,
            computed_state=computed_state,
            styling_rules=styling_rules,
            body_guidance=body_guidance,
            occasion_guidance=occasion_guidance,
            behavioral_profile=behavioral_profile,
            drift_analysis=drift_analysis,
            synthesis=synthesis,
            perspectives=perspectives,
        )

    def generate_navigation_context_sync(
        self,
        user_id: str,
        query: str,
        occasion: Optional[str] = None,
    ) -> NavigationContext:
        """
        Synchronous version of generate_navigation_context.

        Args:
            user_id: User identifier
            query: Search query
            occasion: Optional occasion context

        Returns:
            Complete NavigationContext for agent search
        """
        try:
            # Check if we're already in an event loop
            asyncio.get_running_loop()
            # If we get here, we're in an async context
            raise RuntimeError(
                "generate_navigation_context_sync cannot be called from within an async context. "
                "Use generate_navigation_context instead."
            )
        except RuntimeError as e:
            # RuntimeError from get_running_loop means no loop - safe to use asyncio.run
            if "no running event loop" in str(e).lower():
                return asyncio.run(self.generate_navigation_context(user_id, query, occasion))
            # Re-raise if it's our custom error about async context
            raise

    async def _get_behavioral_patterns(
        self,
        user_id: str,
        computed_state: ComputedUserState,
    ) -> tuple[Optional[BehavioralProfile], Optional[DriftAnalysis]]:
        """
        Get behavioral patterns from Pillar 3 (Activity).

        This is a placeholder for future Pillar 3 implementation.
        Currently extracts patterns from computed_state.

        Args:
            user_id: User identifier
            computed_state: Computed user state from Pillar 1

        Returns:
            Tuple of (BehavioralProfile, DriftAnalysis)
        """
        # Extract behavioral info from computed state
        behavioral_patterns = computed_state.behavioral_patterns if computed_state else None

        behavioral_profile = None
        if behavioral_patterns:
            behavioral_profile = BehavioralProfile(
                category_interests=getattr(behavioral_patterns, 'preferred_categories', []) or [],
                brand_preferences=[],
                price_sensitivity=getattr(behavioral_patterns, 'exploration_rate', 0.5),
            )

        # Drift analysis placeholder
        drift_analysis = DriftAnalysis(
            has_significant_drift=False,
            drift_direction=None,
            drift_magnitude=0.0,
            divergent_signals=[],
            recommendations=[],
        )

        return behavioral_profile, drift_analysis

    async def _get_stylist_knowledge(
        self,
        raw_user_data: RawUserData,
        computed_state: ComputedUserState,
        query: str,
        occasion: Optional[str],
    ) -> tuple[List[str], str, str, Optional[MultiPerspectiveResult]]:
        """
        Retrieve stylist knowledge from Pillar 2.

        Args:
            raw_user_data: Raw user data
            computed_state: Computed user state
            query: Search query
            occasion: Occasion context

        Returns:
            Tuple of (styling_rules, body_guidance, occasion_guidance, perspectives)
        """
        # Build styling context
        styling_context = StylingContext(
            query=query,
            body_type=raw_user_data.body_type,
            occasion=occasion,
            style_context=computed_state.active_context.value if computed_state.active_context else None,
        )

        # Get styling rules
        styling_rules_result = await self.pillar2.query_styling_rules(styling_context)
        styling_rules = [r.content for r in styling_rules_result] if styling_rules_result else []
        logger.debug(f"Retrieved {len(styling_rules)} styling rules")

        # Get body type guidance
        body_guidance = ""
        if raw_user_data.body_type:
            body_rules = self.pillar2.get_body_type_rules(
                raw_user_data.body_type,
                category=self._infer_category(query),
            )
            if body_rules:
                body_guidance = "\n".join(r.content for r in body_rules)

        # Get occasion guidance
        occasion_guidance = ""
        if occasion:
            occasion_rules = self.pillar2.get_occasion_rules(occasion)
            if occasion_rules:
                occasion_guidance = "\n".join(r.content for r in occasion_rules)

        # Get multi-perspective knowledge
        cultural_context = None
        if raw_user_data.onboarding_profile and raw_user_data.onboarding_profile.personal:
            cultural_context = raw_user_data.onboarding_profile.personal.cultural_background

        perspectives = await self.pillar2.retrieve_multiple_perspectives(
            query=query,
            topic=self._infer_category(query),
            user_cultural_context=cultural_context,
        )

        return styling_rules, body_guidance, occasion_guidance, perspectives

    def _build_pillars_input(
        self,
        raw_user_data: RawUserData,
        computed_state: ComputedUserState,
        body_guidance: str,
        occasion_guidance: str,
        perspectives: Optional[MultiPerspectiveResult],
        behavioral_profile: Optional[BehavioralProfile],
        drift_analysis: Optional[DriftAnalysis],
    ) -> ThreePillarsInput:
        """
        Build the ThreePillarsInput for the synthesis LLM.

        Args:
            raw_user_data: Raw user data
            computed_state: Computed user state
            body_guidance: Body type styling guidance
            occasion_guidance: Occasion styling guidance
            perspectives: Multi-perspective styling knowledge
            behavioral_profile: User behavioral patterns
            drift_analysis: Preference drift analysis

        Returns:
            ThreePillarsInput for synthesis
        """
        # Extract root values
        root_values = None
        if raw_user_data.onboarding_profile:
            root_values = raw_user_data.onboarding_profile.root_values

        # Get color guidance from perspectives
        color_guidance = ""
        if perspectives and hasattr(perspectives, 'get_summary'):
            summary = perspectives.get_summary("traditional")
            color_guidance = summary if summary else ""

        # Build drift analysis dict
        drift_dict = None
        if drift_analysis and drift_analysis.has_significant_drift:
            drift_dict = {
                "direction": drift_analysis.drift_direction,
                "magnitude": drift_analysis.drift_magnitude,
                "signals": drift_analysis.divergent_signals,
            }

        # Category interests from behavioral profile
        category_interests = []
        if behavioral_profile:
            category_interests = behavioral_profile.category_interests or []

        # Safely extract position and trajectory from active_position
        current_position = None
        trajectory = None
        if computed_state.active_position is not None:
            current_position = computed_state.active_position.position
            trajectory = computed_state.active_position.trajectory

        return ThreePillarsInput(
            # Pillar 1: Personalization
            body_type=raw_user_data.body_type,
            coloring=raw_user_data.coloring,
            root_values=root_values,
            current_position=current_position,
            trajectory=trajectory,
            nav_params=computed_state.nav_params,
            behavioral_patterns=computed_state.behavioral_patterns,

            # Pillar 2: Stylist Knowledge
            body_guidance=body_guidance,
            occasion_guidance=occasion_guidance,
            color_guidance=color_guidance,

            # Pillar 3: Activity
            drift_analysis=drift_dict,
            category_interests=category_interests,
            spending_patterns=computed_state.spending_patterns,
        )

    def _create_cold_start_context(
        self,
        query: str,
        occasion: Optional[str],
    ) -> NavigationContext:
        """
        Create a NavigationContext for cold start (no user data).

        Args:
            query: Search query
            occasion: Optional occasion

        Returns:
            Cold start NavigationContext
        """
        logger.info(f"Creating cold start context for query: '{query}'")
        return create_cold_start_context(
            query=query,
            occasion=occasion,
            default_budget_min=FALLBACK_BUDGET_MIN,
            default_budget_max=FALLBACK_BUDGET_MAX,
        )

    def _infer_category(self, query: str) -> Optional[str]:
        """
        Infer product category from query.

        Args:
            query: Search query

        Returns:
            Inferred category or None
        """
        query_lower = query.lower()

        categories = {
            "tops": ["shirt", "blouse", "top", "tee", "sweater", "cardigan", "hoodie"],
            "bottoms": ["pants", "jeans", "trousers", "skirt", "shorts"],
            "dresses": ["dress", "gown", "frock"],
            "outerwear": ["jacket", "coat", "blazer"],
            "shoes": ["shoes", "boots", "sneakers", "heels", "sandals", "loafers"],
            "accessories": ["bag", "purse", "watch", "jewelry", "scarf", "belt", "hat"],
        }

        for category, keywords in categories.items():
            if any(kw in query_lower for kw in keywords):
                return category

        return None


class NavigationOrchestrator:
    """
    V3 Navigation Orchestrator.

    Executes the full search pipeline including:
    - Navigation context generation
    - Agent execution (placeholder)
    - Judge evaluation
    - Narrative generation
    """

    def __init__(
        self,
        navigation_intelligence: NavigationIntelligence,
        evaluator: Optional[ARIEvaluator] = None,
        narrative_llm: Optional[NarrativeLLM] = None,
    ):
        """
        Initialize the Navigation Orchestrator.

        Args:
            navigation_intelligence: NavigationIntelligence instance
            evaluator: ARIEvaluator for product scoring
            narrative_llm: NarrativeLLM for generating narratives
        """
        self.navigation_intelligence = navigation_intelligence
        self.evaluator = evaluator
        self.narrative_llm = narrative_llm

    async def execute_search(
        self,
        user_id: str,
        query: str,
        occasion: Optional[str] = None,
        products: Optional[List[Any]] = None,
    ) -> SearchResult:
        """
        Execute the full search pipeline.

        Args:
            user_id: User identifier
            query: Search query
            occasion: Optional occasion context
            products: Optional pre-fetched products (for testing)

        Returns:
            SearchResult with products, narrative, and metadata
        """
        # Input validation (also validated in generate_navigation_context, but check here for logging)
        if not user_id:
            raise ValueError("user_id cannot be empty")
        if not query:
            raise ValueError("query cannot be empty")

        # Log with truncated user_id for privacy
        user_id_short = user_id[:8] + "..." if len(user_id) > 8 else user_id
        logger.info(f"Executing search for user {user_id_short}: '{query}'")

        # Step 1: Generate Navigation Context
        nav_context = await self.navigation_intelligence.generate_navigation_context(
            user_id=user_id,
            query=query,
            occasion=occasion,
        )

        # Step 2: Agent Execution (placeholder)
        # In full implementation, this would call VibeBot, VisionBot, etc.
        if products is None:
            products = []
            logger.warning("No products provided, using empty list")

        # Step 3: Evaluate and select products
        final_products = products
        if self.evaluator and products:
            try:
                final_products = await self._evaluate_products(products, nav_context)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                logger.error(f"Product evaluation failed: {e}, returning unfiltered products")
                final_products = products

        # Step 4: Generate Narrative
        narrative = None
        if self.narrative_llm and final_products:
            try:
                narrative = await self._generate_narrative(
                    nav_context=nav_context,
                    products=final_products,
                )
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as e:
                logger.error(f"Narrative generation failed: {e}")

        # Step 5: Create session tracking
        session_id = str(uuid.uuid4())

        # Build metadata
        metadata = self._build_metadata(nav_context)

        logger.info(f"Search complete: {len(final_products)} products, session {session_id}")

        return SearchResult(
            products=final_products,
            narrative=narrative,
            path=nav_context.path,
            session_id=session_id,
            metadata=metadata,
        )

    async def _evaluate_products(
        self,
        products: List[Any],
        nav_context: NavigationContext,
    ) -> List[Any]:
        """
        Evaluate and select products using the Judge.

        Args:
            products: Candidate products
            nav_context: Navigation context

        Returns:
            Selected products
        """
        if not self.evaluator:
            return products

        from ari_v3.judge import mmr_select, inject_outliers

        # Score products
        scored_products = self.evaluator.score_products(products, nav_context)

        if not scored_products:
            return products

        # Get result set size from nav_params
        result_size = COLD_START_RESULT_SET_SIZE
        if nav_context.computed_state and nav_context.computed_state.nav_params:
            result_size = nav_context.computed_state.nav_params.result_set_size
        # Ensure result_size is at least 1
        result_size = max(1, result_size) if result_size else COLD_START_RESULT_SET_SIZE

        # Calculate outlier percentage (default to 0.0 if None)
        outlier_pct = 0.0
        if nav_context.path and nav_context.path.outlier_percentage is not None:
            outlier_pct = nav_context.path.outlier_percentage
        main_count = int(result_size * (1 - outlier_pct))
        # Ensure at least 1 main product
        main_count = max(1, main_count)

        # MMR selection - ensure lambda_param is never None
        lambda_param = COLD_START_DIVERSITY_REQUIREMENT
        if nav_context.path and nav_context.path.diversity_requirement is not None:
            lambda_param = nav_context.path.diversity_requirement
        selected = mmr_select(
            candidates=scored_products,
            limit=main_count,
            lambda_param=lambda_param,
        )
        logger.debug(f"MMR selected {len(selected)} products (limit={main_count}, lambda={lambda_param})")

        # Outlier injection using correct signature
        if outlier_pct > 0:
            remaining = [p for p in scored_products if p not in selected]

            # Get current position embedding for distance calculation
            current_embedding = None
            if nav_context.current_position and nav_context.current_position.embedding is not None:
                current_embedding = np.array(nav_context.current_position.embedding)

            selected, injected = inject_outliers(
                selected=selected,
                remaining=remaining,
                outlier_percentage=outlier_pct,
                current_position_embedding=current_embedding,
            )
            logger.debug(f"Injected {len(injected)} outliers (percentage={outlier_pct})")

        # Extract original products from scored products
        return [sp.product for sp in selected if hasattr(sp, 'product')]

    async def _generate_narrative(
        self,
        nav_context: NavigationContext,
        products: List[Any],
    ) -> Optional[Any]:
        """
        Generate narrative for the search results.

        Args:
            nav_context: Navigation context
            products: Selected products

        Returns:
            JourneyNarrative or None
        """
        if not self.narrative_llm:
            return None

        # Get user profile
        user_profile = None
        if nav_context.raw_user_data:
            user_profile = nav_context.raw_user_data.onboarding_profile

        # Use async version for future-proofing (currently wraps sync)
        if hasattr(self.narrative_llm, 'generate_narrative_async'):
            return await self.narrative_llm.generate_narrative_async(
                nav_context=nav_context,
                products=products,
                user_profile=user_profile,
            )
        # Fallback to sync version
        return self.narrative_llm.generate_narrative(
            nav_context=nav_context,
            products=products,
            user_profile=user_profile,
        )

    def _build_metadata(self, nav_context: NavigationContext) -> Dict[str, Any]:
        """
        Build metadata dict for the search result.

        Args:
            nav_context: Navigation context

        Returns:
            Metadata dictionary
        """
        metadata: Dict[str, Any] = {
            "query": nav_context.query,
            "occasion": nav_context.occasion,
        }

        # Add synthesis info
        if nav_context.synthesis:
            metadata["style_descriptors"] = nav_context.synthesis.style_descriptors
            metadata["understood_intent"] = nav_context.synthesis.understood_intent
            metadata["formality_level"] = nav_context.synthesis.formality_level

        # Add nav params
        if nav_context.computed_state and nav_context.computed_state.nav_params:
            params = nav_context.computed_state.nav_params
            metadata["nav_params"] = {
                "exploration_appetite": params.exploration_appetite,
                "step_size_multiplier": params.step_size_multiplier,
                "brand_affinity_weight": params.brand_affinity_weight,
                "result_set_size": params.result_set_size,
                "diversity_requirement": params.diversity_requirement,
            }

        # Add context info
        if nav_context.computed_state:
            if nav_context.computed_state.active_context:
                metadata["active_context"] = nav_context.computed_state.active_context.value
            if nav_context.computed_state.detected_contexts:
                metadata["detected_contexts"] = [
                    c.value for c in nav_context.computed_state.detected_contexts
                ]

        return metadata


# Convenience factory function
def create_navigation_intelligence(
    neo4j_driver=None,
    qdrant_client=None,
    openai_api_key: Optional[str] = None,
) -> NavigationIntelligence:
    """
    Factory function to create NavigationIntelligence.

    Args:
        neo4j_driver: Neo4j driver instance
        qdrant_client: Qdrant client instance
        openai_api_key: OpenAI API key (uses env var if not provided)

    Returns:
        Configured NavigationIntelligence instance
    """
    openai_client = None
    if openai_api_key:
        openai_client = OpenAI(api_key=openai_api_key)
    elif os.environ.get("OPENAI_API_KEY"):
        openai_client = OpenAI()

    return NavigationIntelligence(
        neo4j_driver=neo4j_driver,
        qdrant_client=qdrant_client,
        openai_client=openai_client,
    )


def create_navigation_orchestrator(
    neo4j_driver=None,
    qdrant_client=None,
    openai_api_key: Optional[str] = None,
) -> NavigationOrchestrator:
    """
    Factory function to create NavigationOrchestrator with all dependencies.

    Args:
        neo4j_driver: Neo4j driver instance
        qdrant_client: Qdrant client instance
        openai_api_key: OpenAI API key

    Returns:
        Configured NavigationOrchestrator instance
    """
    from ari_v3.judge import ARIEvaluator
    from ari_v3.narrative import NarrativeLLM

    nav_intel = create_navigation_intelligence(
        neo4j_driver=neo4j_driver,
        qdrant_client=qdrant_client,
        openai_api_key=openai_api_key,
    )

    evaluator = ARIEvaluator()
    narrative_llm = NarrativeLLM()

    return NavigationOrchestrator(
        navigation_intelligence=nav_intel,
        evaluator=evaluator,
        narrative_llm=narrative_llm,
    )
