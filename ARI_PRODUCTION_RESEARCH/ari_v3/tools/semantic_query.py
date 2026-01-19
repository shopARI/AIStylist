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

    SEMANTIC_EXPANSION_PROMPT = """You are a fashion AI assistant that understands style, aesthetics, and shopping intent.

## User Query
"{query}"

## Your Task
Analyze this fashion query and enhance it for semantic search. You need to:

1. **Understand the Vibe/Aesthetic**: What style, mood, or aesthetic is the user looking for?
   - Minimalist, bohemian, preppy, streetwear, elegant, casual, edgy, romantic, etc.

2. **Expand with Related Terms**: Add synonyms and related fashion terms that would help find similar items.
   - "boho" → bohemian, free-spirited, relaxed, earthy, flowy, natural
   - "chic" → stylish, sophisticated, elegant, polished, refined
   - "casual" → relaxed, comfortable, everyday, laid-back, effortless

3. **Extract Specific Attributes**:
   - Colors mentioned or implied
   - Product categories (dress, shirt, pants, shoes, etc.)
   - Occasions (wedding, work, date night, casual, formal)
   - Price expectations (luxury, affordable, budget, etc.)

4. **Generate an Expanded Query**: Create an enhanced query string that captures the full intent.

## Response Format (JSON)
{{
    "expanded_query": "Enhanced query text that captures the full semantic intent",
    "style_terms": ["list", "of", "style", "descriptors"],
    "color_terms": ["colors", "if", "mentioned"],
    "category_terms": ["product", "categories"],
    "occasion": "occasion if detected or null",
    "price_hint": "luxury|premium|mid-range|affordable|budget or null",
    "reasoning": "Brief explanation of your understanding"
}}

## Examples

Query: "something cute for a beach vacation"
Response:
{{
    "expanded_query": "cute beach vacation outfit resort wear summer tropical relaxed flowy lightweight breathable casual comfortable",
    "style_terms": ["cute", "vacation", "resort", "summer", "tropical", "relaxed", "flowy", "lightweight"],
    "color_terms": ["bright", "pastel", "white", "coral"],
    "category_terms": ["dress", "swimwear", "coverup", "sandals", "shorts", "top"],
    "occasion": "vacation",
    "price_hint": null,
    "reasoning": "Beach vacation suggests resort wear - lightweight, flowy pieces in summer colors"
}}

Query: "edgy black outfit for concert"
Response:
{{
    "expanded_query": "edgy black concert outfit rock alternative streetwear bold statement leather studs dark urban cool",
    "style_terms": ["edgy", "rock", "alternative", "streetwear", "bold", "statement", "urban", "cool", "dark"],
    "color_terms": ["black", "dark"],
    "category_terms": ["jacket", "jeans", "boots", "top", "leather"],
    "occasion": "concert",
    "price_hint": null,
    "reasoning": "Concert + edgy + black suggests rock/alternative aesthetic with statement pieces"
}}

Query: "affordable work blazer"
Response:
{{
    "expanded_query": "affordable work blazer professional office business formal structured tailored polished classic",
    "style_terms": ["professional", "office", "business", "formal", "structured", "tailored", "polished", "classic"],
    "color_terms": ["navy", "black", "gray", "neutral"],
    "category_terms": ["blazer", "jacket"],
    "occasion": "work",
    "price_hint": "affordable",
    "reasoning": "Work blazer with budget constraint - classic professional pieces in neutral colors"
}}

Now analyze the user query above:"""

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
        Expand a query with semantic understanding (async).

        Args:
            query: Natural language query
            user_context: Optional user preferences/history

        Returns:
            SemanticQuery with expanded terms and filter suggestions
        """
        if not self.async_openai_client:
            raise ValueError("Async OpenAI client not configured")

        prompt = self.SEMANTIC_EXPANSION_PROMPT.format(query=query)

        # Add user context if available
        if user_context:
            context_str = f"\n\nUser Context:\n"
            if user_context.get("preferred_styles"):
                context_str += f"- Preferred styles: {user_context['preferred_styles']}\n"
            if user_context.get("preferred_colors"):
                context_str += f"- Preferred colors: {user_context['preferred_colors']}\n"
            if user_context.get("budget_range"):
                context_str += f"- Budget: ${user_context['budget_range'].get('min', 0)}-${user_context['budget_range'].get('max', 'unlimited')}\n"
            prompt += context_str

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
        """Build Qdrant filter suggestions from expansion result."""
        filters = {}

        # Price filter
        if price_range:
            filters["price"] = {
                "min": price_range[0],
                "max": price_range[1] if price_range[1] != float('inf') else None,
            }

        # NOTE: Category filter intentionally NOT included here.
        # Extracted categories are abstract terms that don't match DB values.
        # Semantic search handles category matching through embeddings.

        # Price tier based on hint
        price_hint = result.get("price_hint")
        if price_hint:
            tier_mapping = {
                "budget": "budget",
                "affordable": "budget",
                "mid-range": "mid_range",
                "premium": "premium",
                "luxury": "premium",
            }
            if price_hint.lower() in tier_mapping:
                filters["price_tier"] = tier_mapping[price_hint.lower()]

        return filters

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
