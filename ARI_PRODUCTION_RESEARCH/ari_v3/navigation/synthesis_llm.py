"""
ARI V3 - LLM #3: Synthesis

Combines Three Pillars of knowledge to output style descriptors.
V3 Key Innovation: Outputs DESCRIPTORS, not coordinates.
Coordinates are derived via exemplar retrieval (grounding in real product space).

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 3.3
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

import numpy as np
from openai import OpenAI, AsyncOpenAI

from ari_v3.core.data_structures import (
    StyleCoordinate,
    NavigationParameters,
    BehavioralPatterns,
    SpendingPatterns,
    RootValues,
    Trajectory,
    zero_vector,
    normalize_vector,
)
from ari_v3.core.prompt_sanitizer import sanitize_user_input, wrap_user_content
from ari_v3.navigation.constants import (
    EMBEDDING_MODEL,
    TEXT_EMBEDDING_DIM,
    VISUAL_EMBEDDING_DIM,
    SYNTHESIS_MODEL,
    SYNTHESIS_LLM_TEMPERATURE,
    FALLBACK_BUDGET_MIN,
    FALLBACK_BUDGET_MAX,
    LLM_PARSE_BUDGET_MIN,
    LLM_PARSE_BUDGET_MAX,
    EXEMPLAR_SEARCH_LIMIT,
    VELOCITY_THRESHOLD_EXPLORING,
    VELOCITY_THRESHOLD_CONSISTENT,
    COLD_START_FORMALITY,
)

logger = logging.getLogger(__name__)


@dataclass
class BudgetInterpretation:
    """Interpreted budget for the current query."""
    min: float
    max: float
    reasoning: str = ""


@dataclass
class SynthesisOutput:
    """
    Output from Synthesis LLM.
    V3: Outputs descriptors, not coordinates.
    """
    style_descriptors: List[str]       # 3-5 specific style terms
    exemplar_search_terms: List[str]   # 2-3 search queries for exemplars
    understood_intent: str             # What the user is looking for
    budget_interpretation: BudgetInterpretation
    formality_level: float             # 0-1 for the occasion
    relevant_context: List[str]        # Key factors influencing interpretation

    # Optional: raw LLM response for debugging
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class ThreePillarsInput:
    """
    Input combining all three pillars for synthesis.
    """
    # Pillar 1: Personalization
    body_type: Optional[str] = None
    coloring: Optional[str] = None
    root_values: Optional[RootValues] = None
    current_position: Optional[StyleCoordinate] = None
    trajectory: Optional[Trajectory] = None
    nav_params: Optional[NavigationParameters] = None
    behavioral_patterns: Optional[BehavioralPatterns] = None

    # Pillar 2: Stylist Knowledge
    body_guidance: str = ""
    occasion_guidance: str = ""
    color_guidance: str = ""

    # Pillar 3: Activity
    drift_analysis: Optional[Dict[str, Any]] = None
    category_interests: List[str] = field(default_factory=list)
    spending_patterns: Optional[SpendingPatterns] = None


class SynthesisLLM:
    """
    V3 Synthesis LLM.

    Combines Three Pillars to output style descriptors.
    Key V3 change: No coordinate hallucination - outputs descriptors
    that are then grounded via exemplar retrieval.
    """

    def __init__(
        self,
        openai_client: Optional[OpenAI] = None,
        async_openai_client: Optional[AsyncOpenAI] = None,
        model: str = SYNTHESIS_MODEL,
        embedding_model: str = EMBEDDING_MODEL,
    ):
        """
        Initialize the Synthesis LLM.

        Args:
            openai_client: OpenAI sync client instance
            async_openai_client: OpenAI async client instance (for async methods)
            model: Model to use for synthesis
            embedding_model: Model for embeddings
        """
        self.client = openai_client or OpenAI()
        self.async_client = async_openai_client or AsyncOpenAI()
        self.model = model
        self.embedding_model = embedding_model
        # Simple cache for embeddings to reduce API calls
        self._embedding_cache: Dict[str, List[float]] = {}

    def synthesize_navigation(
        self,
        pillars: ThreePillarsInput,
        query: str,
        occasion: Optional[str] = None,
    ) -> SynthesisOutput:
        """
        Synthesize navigation from three pillars.

        V3: Outputs descriptors, not coordinates.

        Args:
            pillars: Combined input from all three pillars
            query: User's search query
            occasion: Optional occasion context

        Returns:
            SynthesisOutput with style descriptors and search terms
        """
        prompt = self._build_synthesis_prompt(pillars, query, occasion)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are ARI, a style navigator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=SYNTHESIS_LLM_TEMPERATURE,
            )

            result = json.loads(response.choices[0].message.content)

            # Validate and coerce LLM response types
            style_descriptors = self._validate_string_list(result.get("style_descriptors"), [query])
            exemplar_search_terms = self._validate_string_list(result.get("exemplar_search_terms"), [query])
            understood_intent = self._validate_string(result.get("understood_intent"), f"Looking for {query}")
            formality_level = self._validate_float(result.get("formality_level"), COLD_START_FORMALITY, 0.0, 1.0)
            relevant_context = self._validate_string_list(result.get("relevant_context"), [])

            # Parse budget interpretation
            budget_data = result.get("budget_interpretation", {})
            if not isinstance(budget_data, dict):
                budget_data = {}
            budget_min = self._validate_float(budget_data.get("min"), LLM_PARSE_BUDGET_MIN, 0.0, 100000.0)
            budget_max = self._validate_float(budget_data.get("max"), LLM_PARSE_BUDGET_MAX, 0.0, 100000.0)
            budget_reasoning = self._validate_string(budget_data.get("reasoning"), "")

            # Swap if min > max (LLM may return inverted values)
            if budget_min > budget_max:
                budget_min, budget_max = budget_max, budget_min

            return SynthesisOutput(
                style_descriptors=style_descriptors,
                exemplar_search_terms=exemplar_search_terms,
                understood_intent=understood_intent,
                budget_interpretation=BudgetInterpretation(
                    min=budget_min,
                    max=budget_max,
                    reasoning=budget_reasoning,
                ),
                formality_level=formality_level,
                relevant_context=relevant_context,
                raw_response=result,
            )

        except Exception as e:
            logger.error(f"Synthesis LLM failed: {e}")
            # Return fallback output
            return self._fallback_synthesis(query, occasion)

    async def synthesize_navigation_async(
        self,
        pillars: ThreePillarsInput,
        query: str,
        occasion: Optional[str] = None,
    ) -> SynthesisOutput:
        """
        Async version of synthesize_navigation.

        Uses AsyncOpenAI client to avoid blocking the event loop.

        Args:
            pillars: Combined input from all three pillars
            query: User's search query
            occasion: Optional occasion context

        Returns:
            SynthesisOutput with style descriptors and search terms
        """
        prompt = self._build_synthesis_prompt(pillars, query, occasion)

        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are ARI, a style navigator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=SYNTHESIS_LLM_TEMPERATURE,
            )

            result = json.loads(response.choices[0].message.content)

            # Validate and coerce LLM response types
            style_descriptors = self._validate_string_list(result.get("style_descriptors"), [query])
            exemplar_search_terms = self._validate_string_list(result.get("exemplar_search_terms"), [query])
            understood_intent = self._validate_string(result.get("understood_intent"), f"Looking for {query}")
            formality_level = self._validate_float(result.get("formality_level"), COLD_START_FORMALITY, 0.0, 1.0)
            relevant_context = self._validate_string_list(result.get("relevant_context"), [])

            # Parse budget interpretation
            budget_data = result.get("budget_interpretation", {})
            if not isinstance(budget_data, dict):
                budget_data = {}
            budget_min = self._validate_float(budget_data.get("min"), LLM_PARSE_BUDGET_MIN, 0.0, 100000.0)
            budget_max = self._validate_float(budget_data.get("max"), LLM_PARSE_BUDGET_MAX, 0.0, 100000.0)
            budget_reasoning = self._validate_string(budget_data.get("reasoning"), "")

            # Swap if min > max (LLM may return inverted values)
            if budget_min > budget_max:
                budget_min, budget_max = budget_max, budget_min

            return SynthesisOutput(
                style_descriptors=style_descriptors,
                exemplar_search_terms=exemplar_search_terms,
                understood_intent=understood_intent,
                budget_interpretation=BudgetInterpretation(
                    min=budget_min,
                    max=budget_max,
                    reasoning=budget_reasoning,
                ),
                formality_level=formality_level,
                relevant_context=relevant_context,
                raw_response=result,
            )

        except Exception as e:
            logger.error(f"Async Synthesis LLM failed: {e}")
            return self._fallback_synthesis(query, occasion)

    def _validate_string_list(self, value: Any, default: List[str]) -> List[str]:
        """Validate and coerce value to list of strings."""
        if value is None:
            return default
        if isinstance(value, str):
            return [value]  # Single string -> list
        if isinstance(value, list):
            result = [str(v) for v in value if v is not None]
            # Return default if list is empty after filtering
            return result if result else default
        return default

    def _validate_string(self, value: Any, default: str) -> str:
        """Validate and coerce value to string."""
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)

    def _validate_float(self, value: Any, default: float, min_val: float, max_val: float) -> float:
        """Validate and coerce value to float within bounds."""
        if value is None:
            return default
        try:
            result = float(value)
            return max(min_val, min(max_val, result))  # Clamp to bounds
        except (ValueError, TypeError):
            return default

    def _build_synthesis_prompt(
        self,
        pillars: ThreePillarsInput,
        query: str,
        occasion: Optional[str],
    ) -> str:
        """Build the synthesis prompt from pillars."""

        # Format position description
        position_desc = "unknown"
        if pillars.current_position:
            position_desc = "established style preferences"

        # Format trajectory description
        trajectory_desc = "stable"
        if pillars.trajectory:
            if pillars.trajectory.velocity > VELOCITY_THRESHOLD_EXPLORING:
                trajectory_desc = f"actively exploring (velocity: {pillars.trajectory.velocity:.2f})"
            elif pillars.trajectory.velocity < VELOCITY_THRESHOLD_CONSISTENT:
                trajectory_desc = "very consistent, minimal change"
            else:
                trajectory_desc = "gradual evolution"

        # Format nav params
        nav_desc = ""
        if pillars.nav_params:
            nav_desc = f"""
- Exploration appetite: {pillars.nav_params.exploration_appetite:.2f} (0=conservative, 1=adventurous)
- Step size multiplier: {pillars.nav_params.step_size_multiplier:.2f}
- Brand affinity: {pillars.nav_params.brand_affinity_weight:.2f}"""

        # Format behavioral patterns
        # Use getattr for defensive access - BehavioralPatterns may have different field names
        behavioral_desc = ""
        if pillars.behavioral_patterns:
            consistent = getattr(pillars.behavioral_patterns, 'consistent_dimensions', None) or ["general style"]
            variable = getattr(pillars.behavioral_patterns, 'variable_dimensions', None) or []
            behavioral_desc = f"""
- Consistent on: {', '.join(consistent[:3])}
- Varies on: {', '.join(variable[:3]) if variable else 'nothing notable'}"""

        # Format root values
        root_values_desc = "self-expression through style"
        if pillars.root_values:
            root_values_desc = pillars.root_values.primary or root_values_desc

        # Format spending patterns
        spending_desc = ""
        if pillars.spending_patterns:
            spending_desc = f"""
- Typical spend: ${pillars.spending_patterns.median_spend:.0f}
- Category preferences: {', '.join(pillars.spending_patterns.category_preferences[:3]) if pillars.spending_patterns.category_preferences else 'varied'}"""

        # Infer category from query
        category = self._infer_category(query)

        # Sanitize user-provided input to prevent prompt injection
        safe_query = sanitize_user_input(query, max_length=500)
        safe_occasion = sanitize_user_input(occasion, max_length=100) if occasion else "not specified"

        prompt = f"""You are ARI, a style navigator. You help users traverse style space.

You have THREE PILLARS of knowledge:

PILLAR 1 - PERSONALIZATION (who they are):
- Body type: {pillars.body_type or 'not specified'}
- Coloring: {pillars.coloring or 'not specified'}
- Root values: {root_values_desc}
- Current position: {position_desc}
- Trajectory: {trajectory_desc}
{nav_desc}
{behavioral_desc}

PILLAR 2 - STYLIST KNOWLEDGE (fashion expertise):
- Body guidance: {pillars.body_guidance or 'general fashion guidance applies'}
- Occasion guidance: {pillars.occasion_guidance or 'versatile styling'}
- Color guidance: {pillars.color_guidance or 'personal color preferences'}

PILLAR 3 - ACTIVITY (what they've done):
- Recent drift: {json.dumps(pillars.drift_analysis) if pillars.drift_analysis else 'stable preferences'}
- Category interests: {', '.join(pillars.category_interests[:5]) if pillars.category_interests else 'broad interests'}
{spending_desc}

<USER_QUERY>
{safe_query}
</USER_QUERY>
OCCASION: {safe_occasion}
CATEGORY DETECTED: {category}

YOUR TASK:
Based on all this, determine WHERE they want to go stylistically.

DO NOT output coordinates. Instead, describe the destination in words that can be used to search for exemplar products.

Output a JSON object with:
1. "style_descriptors": List of 3-5 specific style terms (e.g., "minimalist structured blazer", "warm earth tones", "relaxed tailored fit")
2. "exemplar_search_terms": 2-3 search queries to find products that represent the destination
3. "understood_intent": What you understand they're looking for (1-2 sentences)
4. "budget_interpretation": {{"min": number, "max": number, "reasoning": "brief explanation"}}
5. "formality_level": number 0-1 for THIS occasion
6. "relevant_context": List of key factors influencing your interpretation
"""
        return prompt

    def _infer_category(self, query: str) -> str:
        """Infer product category from query."""
        query_lower = query.lower()

        categories = {
            "tops": ["shirt", "blouse", "top", "tee", "sweater", "cardigan", "hoodie"],
            "bottoms": ["pants", "jeans", "trousers", "skirt", "shorts"],
            "dresses": ["dress", "gown", "frock"],
            "outerwear": ["jacket", "coat", "blazer", "outerwear"],
            "shoes": ["shoes", "boots", "sneakers", "heels", "sandals", "loafers"],
            "accessories": ["bag", "purse", "watch", "jewelry", "scarf", "belt", "hat"],
            "suits": ["suit", "formal wear", "tuxedo"],
            "activewear": ["athletic", "workout", "gym", "yoga", "running"],
        }

        for category, keywords in categories.items():
            if any(kw in query_lower for kw in keywords):
                return category

        return "general"

    def _fallback_synthesis(
        self,
        query: str,
        occasion: Optional[str],
    ) -> SynthesisOutput:
        """Generate fallback synthesis when LLM fails."""
        return SynthesisOutput(
            style_descriptors=[query, "versatile", "classic"],
            exemplar_search_terms=[query, f"{query} classic style"],
            understood_intent=f"Looking for {query}",
            budget_interpretation=BudgetInterpretation(min=FALLBACK_BUDGET_MIN, max=FALLBACK_BUDGET_MAX),
            formality_level=COLD_START_FORMALITY,
            relevant_context=["fallback due to synthesis error"],
        )

    def compute_destination_from_synthesis(
        self,
        synthesis: SynthesisOutput,
        qdrant_client: Optional[Any] = None,
        collection_name: str = "fashion_products",
    ) -> StyleCoordinate:
        """
        Convert LLM descriptors to coordinates via exemplar retrieval.

        V3: Grounds the destination in actual product space.

        Args:
            synthesis: Output from synthesize_navigation
            qdrant_client: Qdrant client for vector search (sync client)
            collection_name: Name of the product collection

        Returns:
            StyleCoordinate representing the destination
        """
        exemplar_embeddings = []

        # Search for exemplars using each search term
        for search_term in synthesis.exemplar_search_terms:
            try:
                # Get embedding for search term
                query_embedding = self.get_embedding_sync(search_term)

                if qdrant_client:
                    # Search for products matching the descriptor
                    # Use query_points with with_vectors=True to get embeddings back
                    try:
                        results = qdrant_client.query_points(
                            collection_name=collection_name,
                            query=query_embedding,
                            limit=EXEMPLAR_SEARCH_LIMIT,
                            with_vectors=True,
                        )
                        # Collect embeddings of top results
                        for point in results.points:
                            if point.vector is not None:
                                exemplar_embeddings.append(np.array(point.vector))
                    except Exception as search_err:
                        logger.warning(f"Qdrant search failed: {search_err}, using query embedding directly")
                        exemplar_embeddings.append(np.array(query_embedding))
                else:
                    # No Qdrant client - use search term embedding directly
                    exemplar_embeddings.append(np.array(query_embedding))

            except Exception as e:
                logger.warning(f"Exemplar search failed for '{search_term}': {e}")
                continue

        return self._compute_destination_from_embeddings(exemplar_embeddings, synthesis)

    async def compute_destination_from_synthesis_async(
        self,
        synthesis: SynthesisOutput,
        qdrant_client: Optional[Any] = None,
        collection_name: str = "fashion_products",
    ) -> StyleCoordinate:
        """
        Async version: Convert LLM descriptors to coordinates via exemplar retrieval.

        V3: Grounds the destination in actual product space.
        Uses async embedding and parallel Qdrant searches for performance.

        Args:
            synthesis: Output from synthesize_navigation
            qdrant_client: Qdrant async client for vector search
            collection_name: Name of the product collection

        Returns:
            StyleCoordinate representing the destination
        """
        # Get embeddings for all search terms in parallel
        async def get_embedding_safe(term: str) -> Optional[List[float]]:
            try:
                return await self.get_embedding_async(term)
            except Exception as e:
                logger.warning(f"Failed to get embedding for '{term}': {e}")
                return None

        embedding_tasks = [get_embedding_safe(term) for term in synthesis.exemplar_search_terms]
        query_embeddings = await asyncio.gather(*embedding_tasks)

        # Filter out failed embeddings and pair with terms
        valid_pairs = [
            (term, emb) for term, emb in zip(synthesis.exemplar_search_terms, query_embeddings)
            if emb is not None
        ]

        if not valid_pairs:
            logger.warning("No valid embeddings obtained, using fallback")
            return self._compute_destination_from_embeddings([], synthesis)

        exemplar_embeddings = []

        if qdrant_client:
            # Search Qdrant in parallel for all search terms
            async def search_qdrant(query_embedding: List[float]) -> List[np.ndarray]:
                try:
                    results = await qdrant_client.query_points(
                        collection_name=collection_name,
                        query=query_embedding,
                        limit=EXEMPLAR_SEARCH_LIMIT,
                        with_vectors=True,
                    )
                    return [np.array(point.vector) for point in results.points if point.vector is not None]
                except Exception as e:
                    logger.warning(f"Qdrant search failed: {e}")
                    return [np.array(query_embedding)]

            search_tasks = [search_qdrant(emb) for _, emb in valid_pairs]
            search_results = await asyncio.gather(*search_tasks)

            for result_list in search_results:
                exemplar_embeddings.extend(result_list)
        else:
            # No Qdrant client - use search term embeddings directly
            for _, emb in valid_pairs:
                exemplar_embeddings.append(np.array(emb))

        return self._compute_destination_from_embeddings(exemplar_embeddings, synthesis)

    def _compute_destination_from_embeddings(
        self,
        exemplar_embeddings: List[np.ndarray],
        synthesis: SynthesisOutput,
    ) -> StyleCoordinate:
        """Compute destination coordinate from collected exemplar embeddings.

        Args:
            exemplar_embeddings: List of embeddings from exemplar products
            synthesis: Synthesis output for fallback descriptor text

        Returns:
            StyleCoordinate representing the destination

        Raises:
            Exception: If both exemplar and fallback embedding fail
        """
        if not exemplar_embeddings:
            # Fallback: embed the descriptors directly
            descriptor_text = " ".join(synthesis.style_descriptors)
            # This will raise if embedding fails - let orchestrator handle fallback
            destination_embedding = self.get_embedding_sync(descriptor_text)
            logger.info("Using fallback descriptor embedding for destination")
        else:
            # Destination = centroid of exemplars (normalized mean)
            stacked = np.stack(exemplar_embeddings)
            mean_embedding = np.mean(stacked, axis=0)
            destination_embedding = normalize_vector(mean_embedding).tolist()
            logger.info(f"Computed destination from {len(exemplar_embeddings)} exemplars")

        return StyleCoordinate(
            embedding=destination_embedding,
            visual_embedding=zero_vector(VISUAL_EMBEDDING_DIM),
        )

    def get_embedding_sync(self, text: str) -> List[float]:
        """Get embedding for text (synchronous).

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding.

        Raises:
            Exception: Re-raises if embedding API call fails
        """
        # Check cache first
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
            embedding = response.data[0].embedding
            # Cache the result (limit cache size to prevent memory issues)
            if len(self._embedding_cache) < 1000:
                self._embedding_cache[text] = embedding
            return embedding
        except Exception as e:
            logger.error(f"Embedding API call failed for text '{text[:50]}...': {e}")
            # Re-raise so orchestrator can use fallback
            raise

    async def get_embedding_async(self, text: str) -> List[float]:
        """Get embedding for text (asynchronous).

        Uses AsyncOpenAI client to avoid blocking the event loop.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding.

        Raises:
            Exception: Re-raises if embedding API call fails
        """
        # Check cache first
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        try:
            response = await self.async_client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
            embedding = response.data[0].embedding
            # Cache the result (limit cache size to prevent memory issues)
            if len(self._embedding_cache) < 1000:
                self._embedding_cache[text] = embedding
            return embedding
        except Exception as e:
            logger.error(f"Async embedding API call failed for text '{text[:50]}...': {e}")
            raise
