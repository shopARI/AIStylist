"""
V3 SemanticQueryGenerator - LLM-powered query expansion for Qdrant searches.

This module provides semantic query understanding and expansion for embedding-based
searches. It enhances natural language queries with:
- Style/vibe understanding ("boho chic" → adds bohemian, relaxed, earthy)
- Synonym expansion
- Occasion-appropriate suggestions
- Filter recommendations

Counterpart to Text2CypherGenerator (Neo4j) - this handles Qdrant/embedding searches.
"""
import os
import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SemanticQuery:
    """Represents an enhanced semantic query for Qdrant search."""
    original_query: str
    expanded_query: str  # Enhanced query text for embedding
    style_terms: List[str] = field(default_factory=list)  # Extracted style descriptors
    color_terms: List[str] = field(default_factory=list)  # Extracted colors
    category_terms: List[str] = field(default_factory=list)  # Product categories
    occasion: Optional[str] = None  # Detected occasion
    price_range: Optional[Tuple[float, float]] = None  # (min, max) or None
    filters: Dict[str, Any] = field(default_factory=dict)  # Qdrant filter suggestions
    reasoning: str = ""  # LLM's reasoning about the query


class SemanticQueryGenerator:
    """
    LLM-powered semantic query expansion for Qdrant embedding searches.

    Enhances natural language queries with style understanding, synonym
    expansion, and intelligent filter suggestions.
    """

    SEMANTIC_EXPANSION_PROMPT = """You are ARI, a fashion AI that navigates users through multi-dimensional style space.

## Philosophy
Fashion exists in a rich style space with dimensions like:
- **Form**: silhouette, structure, drape (A-line, bodycon, oversized, fitted)
- **Aesthetic**: minimalist, bohemian, preppy, edgy, romantic, streetwear
- **Texture**: smooth, knitted, structured, flowing, matte, shiny
- **Color**: warm/cool, neutral/vibrant, monochrome/colorful
- **Occasion**: professional, casual, formal, creative, athletic
- **Price positioning**: luxury, premium, accessible, budget-friendly

Your job is to understand where the user wants to GO in this style space and generate
a rich semantic description of that DESTINATION. This description will be embedded
and used to navigate to the right region of style space via similarity.

## User Query
"{query}"

{user_context}

## Your Task
1. **Identify the Style Space Destination**: What region of style space is the user trying to reach?
   Think about the intersection of aesthetics, occasion, formality, and vibe.

2. **Expand the Destination Description**: Generate rich descriptors that capture this region.
   Include: silhouette words, fabric feels, aesthetic terms, mood descriptors, occasion cues.

3. **Capture Price Positioning Through Language** (NOT filters):
   - "luxury" → include: designer, high-end, premium quality, refined, upscale, exclusive
   - "affordable" → include: accessible, value, everyday, practical, budget-friendly
   - Don't worry about exact price numbers - capture the VIBE of the price point

4. **Generate Navigation Query**: Create a comprehensive text that, when embedded, will
   navigate to the correct region of the 10,600-dimensional style space.

## Response Format (JSON)
{{
    "expanded_query": "Rich navigation description - 20-40 words capturing the full style destination",
    "style_terms": ["aesthetic", "descriptors", "that", "define", "this", "region"],
    "color_terms": ["colors", "implied", "or", "stated"],
    "category_terms": ["garment", "types"],
    "occasion": "primary occasion or null",
    "price_hint": "luxury|premium|mid-range|affordable|budget or null",
    "reasoning": "Explain the style space destination you're navigating to"
}}

## Examples

Query: "interview at fashion institute"
Response:
{{
    "expanded_query": "professional creative fashion industry interview sophisticated polished stylish modern artistic elevated smart casual designer aesthetic refined tailored contemporary chic fashion-forward",
    "style_terms": ["professional", "creative", "sophisticated", "polished", "artistic", "elevated", "contemporary", "fashion-forward", "refined"],
    "color_terms": ["black", "navy", "neutral", "monochrome"],
    "category_terms": ["blazer", "dress", "trousers", "blouse", "heels"],
    "occasion": "interview",
    "price_hint": "premium",
    "reasoning": "Fashion institute interview = intersection of professional and creative. Need to look polished yet fashion-aware, sophisticated but not corporate. Premium quality signals industry knowledge."
}}

Query: "cozy weekend vibes"
Response:
{{
    "expanded_query": "cozy comfortable weekend relaxed casual loungewear soft knit oversized warm layered effortless laid-back easy breathable cotton fleece",
    "style_terms": ["cozy", "comfortable", "relaxed", "casual", "oversized", "soft", "effortless", "laid-back"],
    "color_terms": ["neutral", "cream", "gray", "earth tones", "muted"],
    "category_terms": ["sweater", "joggers", "hoodie", "cardigan", "leggings"],
    "occasion": "casual",
    "price_hint": null,
    "reasoning": "Weekend cozy = comfort-focused region of style space. Soft textures, relaxed silhouettes, easy pieces for home or casual outings."
}}

Query: "luxury summer wedding guest"
Response:
{{
    "expanded_query": "luxury summer wedding guest elegant sophisticated designer high-end formal refined graceful romantic flowy chiffon silk pastel garden party upscale special occasion",
    "style_terms": ["elegant", "sophisticated", "luxury", "designer", "refined", "graceful", "romantic", "formal", "upscale"],
    "color_terms": ["pastel", "blush", "sage", "lavender", "champagne", "soft"],
    "category_terms": ["dress", "midi dress", "maxi dress", "heels", "clutch"],
    "occasion": "wedding",
    "price_hint": "luxury",
    "reasoning": "Luxury + summer wedding = high-end elegant region. Destination is sophisticated formal with seasonal lightness. Premium quality fabrics, refined silhouettes."
}}

Now analyze the user query and navigate to the right region of style space:"""

    def __init__(
        self,
        openai_client=None,
        async_openai_client=None,
        model: str = "gpt-4o-mini",
    ):
        """
        Initialize the Semantic Query Generator.

        Args:
            openai_client: Sync OpenAI client
            async_openai_client: Async OpenAI client for non-blocking calls
            model: Model to use for query expansion
        """
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
        self.model = model

    async def expand_query_async(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> SemanticQuery:
        """
        Expand a query with semantic understanding for style space navigation.

        The expanded query is a rich description of the user's DESTINATION in
        style space. This description will be embedded and used for similarity
        search to navigate to the correct region.

        Args:
            query: Natural language query
            user_context: Optional user style position/preferences for navigation

        Returns:
            SemanticQuery with expanded navigation description
        """
        if not self.async_openai_client:
            raise ValueError("Async OpenAI client not configured")

        # Build user context string for the prompt
        context_str = ""
        if user_context:
            context_parts = []
            # Gender is critical for fashion - determines which products to show
            if user_context.get("gender"):
                gender = user_context["gender"]
                gender_label = "women's" if gender == "female" else "men's" if gender == "male" else None
                if gender_label:
                    context_parts.append(f"Shopping for: {gender_label} fashion/clothing")
            if user_context.get("preferred_styles"):
                context_parts.append(f"Current style position: {user_context['preferred_styles']}")
            if user_context.get("preferred_colors"):
                context_parts.append(f"Color preferences: {user_context['preferred_colors']}")
            if user_context.get("style_trajectory"):
                context_parts.append(f"Style evolution: {user_context['style_trajectory']}")
            if user_context.get("occasion_context"):
                context_parts.append(f"Typical occasions: {user_context['occasion_context']}")
            if context_parts:
                context_str = "## User's Current Position in Style Space\n" + "\n".join(f"- {p}" for p in context_parts)

        prompt = self.SEMANTIC_EXPANSION_PROMPT.format(
            query=query,
            user_context=context_str
        )

        try:
            response = await self.async_openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fashion AI that understands style and aesthetics. Always respond with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Some creativity for style understanding
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # Build price range from hint
            price_range = self._price_hint_to_range(result.get("price_hint"))

            # Build Qdrant filters
            filters = self._build_filters(result, price_range)

            semantic_query = SemanticQuery(
                original_query=query,
                expanded_query=result.get("expanded_query", query),
                style_terms=result.get("style_terms", []),
                color_terms=result.get("color_terms", []),
                category_terms=result.get("category_terms", []),
                occasion=result.get("occasion"),
                price_range=price_range,
                filters=filters,
                reasoning=result.get("reasoning", ""),
            )

            logger.info(
                f"Semantic expansion: '{query}' -> "
                f"styles={semantic_query.style_terms[:3]}, "
                f"colors={semantic_query.color_terms}, "
                f"occasion={semantic_query.occasion}"
            )

            return semantic_query

        except Exception as e:
            logger.error(f"Semantic expansion failed: {e}")
            return self._fallback_expansion(query)

    def expand_query(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> SemanticQuery:
        """
        Expand a query with semantic understanding (sync).
        """
        if not self.openai_client:
            raise ValueError("OpenAI client not configured")

        prompt = self.SEMANTIC_EXPANSION_PROMPT.format(query=query)

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fashion AI that understands style and aesthetics. Always respond with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            price_range = self._price_hint_to_range(result.get("price_hint"))
            filters = self._build_filters(result, price_range)

            return SemanticQuery(
                original_query=query,
                expanded_query=result.get("expanded_query", query),
                style_terms=result.get("style_terms", []),
                color_terms=result.get("color_terms", []),
                category_terms=result.get("category_terms", []),
                occasion=result.get("occasion"),
                price_range=price_range,
                filters=filters,
                reasoning=result.get("reasoning", ""),
            )

        except Exception as e:
            logger.error(f"Semantic expansion failed: {e}")
            return self._fallback_expansion(query)

    def _price_hint_to_range(self, price_hint: Optional[str]) -> Optional[Tuple[float, float]]:
        """Convert price hint to numeric range."""
        if not price_hint:
            return None

        price_ranges = {
            "budget": (0, 50),
            "affordable": (0, 100),
            "mid-range": (50, 200),
            "premium": (150, 500),
            "luxury": (300, float('inf')),
        }

        return price_ranges.get(price_hint.lower())

    def _build_filters(
        self,
        result: Dict[str, Any],
        price_range: Optional[Tuple[float, float]],
    ) -> Dict[str, Any]:
        """
        Build filter dict - ONLY for explicit numeric price ranges.

        PHILOSOPHY: All style attributes (including price positioning like
        "luxury" or "budget") flow through the semantic query expansion.
        The expanded_query includes terms like "high-end designer premium"
        or "affordable everyday practical" which the embedding model uses
        to navigate to the right region of style space.

        Hard filters are ONLY used for explicit numeric constraints
        (e.g., "under $50" → price.max = 50).
        """
        # NOTE: We intentionally return empty filters here.
        # The orchestrator's _build_qdrant_filter handles explicit numeric
        # price ranges from ExtractedParameters.price_range.
        #
        # All other attributes flow through semantic navigation:
        # - "luxury" → expanded_query includes luxury descriptors
        # - "affordable" → expanded_query includes budget-friendly terms
        # - categories → expanded_query includes garment types
        #
        # This prevents 0-result queries from mismatched filter values.
        return {}

    def _fallback_expansion(self, query: str) -> SemanticQuery:
        """Generate a basic expansion without LLM."""
        # Extract obvious terms
        query_lower = query.lower()

        # Common colors
        colors = []
        color_words = ["black", "white", "red", "blue", "green", "navy", "pink",
                       "beige", "brown", "gray", "grey", "yellow", "orange", "purple"]
        for color in color_words:
            if color in query_lower:
                colors.append(color)

        # Common categories
        categories = []
        category_words = ["dress", "shirt", "pants", "jeans", "shoes", "boots",
                         "jacket", "coat", "sweater", "top", "skirt", "blazer",
                         "bag", "handbag", "sneakers", "heels"]
        for cat in category_words:
            if cat in query_lower:
                categories.append(cat)

        # Common occasions
        occasion = None
        occasion_words = {
            "wedding": "wedding", "work": "work", "office": "work",
            "date": "date night", "party": "party", "casual": "casual",
            "formal": "formal", "vacation": "vacation", "beach": "vacation",
        }
        for word, occ in occasion_words.items():
            if word in query_lower:
                occasion = occ
                break

        return SemanticQuery(
            original_query=query,
            expanded_query=query,  # No expansion in fallback
            style_terms=[],
            color_terms=colors,
            category_terms=categories,
            occasion=occasion,
            price_range=None,
            filters={},
            reasoning="Fallback expansion - basic term extraction",
        )


async def expand_and_embed(
    query: str,
    openai_client=None,
    async_openai_client=None,
    embedding_model: str = "text-embedding-3-small",
) -> Tuple[SemanticQuery, List[float]]:
    """
    Convenience function: Expand query and generate embedding.

    Args:
        query: Natural language query
        openai_client: OpenAI client
        async_openai_client: Async OpenAI client
        embedding_model: Model for embedding generation

    Returns:
        Tuple of (SemanticQuery, embedding vector)
    """
    generator = SemanticQueryGenerator(
        openai_client=openai_client,
        async_openai_client=async_openai_client,
    )

    # Expand query
    if async_openai_client:
        semantic_query = await generator.expand_query_async(query)

        # Generate embedding from expanded query
        embedding_response = await async_openai_client.embeddings.create(
            model=embedding_model,
            input=semantic_query.expanded_query,
        )
        embedding = embedding_response.data[0].embedding
    else:
        semantic_query = generator.expand_query(query)

        embedding_response = openai_client.embeddings.create(
            model=embedding_model,
            input=semantic_query.expanded_query,
        )
        embedding = embedding_response.data[0].embedding

    logger.info(f"Generated embedding for expanded query (dim={len(embedding)})")

    return semantic_query, embedding
