"""
ARI V3 - LLM #4: Narrative

Generates personalized journey narratives using root values and validation sources.
Creates warm, human explanations for why each product fits the user.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 3.4
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import OpenAI, AsyncOpenAI

from ari_v3.navigation.navigation_context import NavigationContext
from ari_v3.navigation.constants import SYNTHESIS_MODEL
from ari_v3.core.prompt_sanitizer import sanitize_user_input, sanitize_list

logger = logging.getLogger(__name__)

# Default model for narrative generation
NARRATIVE_MODEL = SYNTHESIS_MODEL  # gpt-4o
NARRATIVE_TEMPERATURE = 0.8  # Slightly higher for more natural language

# Limits
MAX_TOKENS = 1500  # Maximum response tokens for cost control
MAX_PRODUCTS_IN_PROMPT = 10  # Maximum products to include in prompt
MAX_DESCRIPTION_LENGTH = 100  # Truncate product descriptions
MAX_STYLE_PREFERENCES = 3  # Max wants/avoids to show
API_TIMEOUT = 30  # Seconds to wait for API response

# Validation source framings (from pseudocode Section 3.4)
VALIDATION_FRAMINGS = {
    "self": "how these pieces express who you are",
    "partner": "pieces your partner would love seeing you in",
    "colleagues": "how you'll be perceived professionally",
    "strangers": "the impression you'll make",
    "friends": "what your friends would say about your style",
    "family": "pieces that feel authentically you",
}


@dataclass
class ProductExplanation:
    """Explanation for why a specific product fits the user."""
    product_id: str
    product_title: str
    explanation: str


@dataclass
class JourneyNarrative:
    """
    Complete narrative for a recommendation session.

    Includes opening context, per-product explanations, and optional closing.
    """
    opening: str
    product_explanations: List[ProductExplanation] = field(default_factory=list)
    closing: str = ""

    # Metadata
    validation_framing: str = ""  # The framing used based on validation source
    root_value_referenced: str = ""  # The root value that was referenced

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "opening": self.opening,
            "product_explanations": [
                {
                    "product_id": pe.product_id,
                    "product_title": pe.product_title,
                    "explanation": pe.explanation,
                }
                for pe in self.product_explanations
            ],
            "closing": self.closing,
            "validation_framing": self.validation_framing,
            "root_value_referenced": self.root_value_referenced,
        }

    def format_for_display(self) -> str:
        """Format narrative for user-facing display."""
        parts = [self.opening, ""]

        for pe in self.product_explanations:
            parts.append(f"**{pe.product_title}**: {pe.explanation}")

        if self.closing:
            parts.append("")
            parts.append(self.closing)

        return "\n".join(parts)


@dataclass
class UserProfileForNarrative:
    """
    Simplified user profile for narrative generation.

    Extracts just the fields needed for personalized narratives.
    """
    root_value: str = "self-expression"
    primary_validation_source: str = "self"
    style_motivation: str = "looking good"
    style_wants: List[str] = field(default_factory=list)
    style_avoids: List[str] = field(default_factory=list)
    body_type: Optional[str] = None
    coloring: Optional[str] = None


class NarrativeLLM:
    """
    V3 Narrative LLM.

    Generates personalized journey narratives that:
    1. Connect to user's root values
    2. Frame recommendations based on validation sources
    3. Explain WHY each piece works for them specifically
    """

    def __init__(
        self,
        openai_client: Optional[OpenAI] = None,
        async_openai_client: Optional[AsyncOpenAI] = None,
        model: str = NARRATIVE_MODEL,
    ):
        """
        Initialize the Narrative LLM.

        Args:
            openai_client: OpenAI sync client instance
            async_openai_client: OpenAI async client instance (for async methods)
            model: Model to use for narrative generation
        """
        self.client = openai_client or OpenAI()
        self.async_client = async_openai_client or AsyncOpenAI()
        self.model = model

    def generate_narrative(
        self,
        nav_context: NavigationContext,
        products: List[Dict[str, Any]],
        user_profile: Optional[UserProfileForNarrative] = None,
    ) -> JourneyNarrative:
        """
        Generate personalized journey narrative.

        Args:
            nav_context: Navigation context with query, occasion, synthesis
            products: List of selected products with metadata
            user_profile: User profile for personalization

        Returns:
            JourneyNarrative with opening, product explanations, and closing
        """
        # Use default profile if not provided
        if user_profile is None:
            user_profile = UserProfileForNarrative()

        # Determine framing based on validation source
        framing = self._get_validation_framing(user_profile.primary_validation_source)

        # Build prompt
        prompt = self._build_narrative_prompt(
            nav_context=nav_context,
            products=products,
            user_profile=user_profile,
            framing=framing,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=NARRATIVE_TEMPERATURE,
                max_tokens=MAX_TOKENS,
                timeout=API_TIMEOUT,
            )

            # Validate response
            if not response.choices or not response.choices[0].message.content:
                logger.warning("Empty response from Narrative LLM")
                return self._fallback_narrative(products, framing, user_profile.root_value)

            raw_response = response.choices[0].message.content

            # Parse the response into structured narrative
            narrative = self._parse_narrative_response(
                response=raw_response,
                products=products,
                framing=framing,
                root_value=user_profile.root_value,
            )

            logger.debug(f"Narrative generated successfully with {len(narrative.product_explanations)} product explanations")
            return narrative

        except (KeyboardInterrupt, SystemExit):
            raise  # Don't catch system-level interrupts
        except Exception as e:
            logger.error(f"Narrative LLM failed: {e}")
            return self._fallback_narrative(products, framing, user_profile.root_value)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for narrative generation."""
        return """You are ARI, a style navigator with a warm, wise personality.

Your role is to create personalized narratives that help people understand WHY certain pieces work for them. You're not just listing features - you're connecting style choices to who they are and what they value.

Guidelines:
- Be warm but concise
- Sound human, not robotic
- Reference the user's actual preferences when relevant
- Focus on the "why" not just the "what"
- Each product explanation should be 1-2 sentences max
- The opening should be 2-4 sentences that set context"""

    def _get_validation_framing(self, validation_source: str) -> str:
        """
        Get framing based on validation source.

        From pseudocode Section 3.4:
        - self: "how these pieces express who you are"
        - partner: "pieces your partner would love seeing you in"
        - colleagues: "how you'll be perceived professionally"
        - strangers: "the impression you'll make"
        """
        return VALIDATION_FRAMINGS.get(validation_source.lower(), "your style journey")

    def _build_narrative_prompt(
        self,
        nav_context: NavigationContext,
        products: List[Dict[str, Any]],
        user_profile: UserProfileForNarrative,
        framing: str,
    ) -> str:
        """Build the narrative generation prompt."""

        # Sanitize user-provided values to prevent prompt injection
        safe_wants = sanitize_list(user_profile.style_wants[:MAX_STYLE_PREFERENCES]) if user_profile.style_wants else []
        safe_avoids = sanitize_list(user_profile.style_avoids[:MAX_STYLE_PREFERENCES]) if user_profile.style_avoids else []

        wants_text = ", ".join(safe_wants) if safe_wants else "versatile, quality pieces"
        avoids_text = ", ".join(safe_avoids) if safe_avoids else "nothing specific"

        # Sanitize other user-controlled fields
        safe_root_value = sanitize_user_input(user_profile.root_value, max_length=200)
        safe_style_motivation = sanitize_user_input(user_profile.style_motivation, max_length=300)

        # Format navigation description
        # understood_intent is what user is looking for (their goal)
        # style_descriptors describe the destination style
        intent_desc = "exploring new style directions"
        destination_desc = "their ideal style"

        if nav_context.synthesis:
            if nav_context.synthesis.understood_intent:
                intent_desc = sanitize_user_input(nav_context.synthesis.understood_intent, max_length=300)
            if nav_context.synthesis.style_descriptors:
                safe_descriptors = sanitize_list(nav_context.synthesis.style_descriptors[:MAX_STYLE_PREFERENCES])
                destination_desc = ", ".join(safe_descriptors)

        # Safely get query (could be None) and sanitize
        query_text = sanitize_user_input(nav_context.query, max_length=500) if nav_context.query else "general style request"
        safe_occasion = sanitize_user_input(nav_context.occasion, max_length=100) if nav_context.occasion else "general"

        # Format products
        products_text = self._format_products_for_prompt(products)

        prompt = f"""You've just helped someone find products. Now create a brief narrative that:
1. Connects to their ROOT VALUE: "{safe_root_value}"
2. Frames recommendations around: {framing}
3. Explains WHY each piece works for them specifically

USER CONTEXT:
- Style motivation: {safe_style_motivation}
- They want MORE: {wants_text}
- They AVOID: {avoids_text}
<USER_QUERY>
{query_text}
</USER_QUERY>
- Occasion: {safe_occasion}

NAVIGATION:
- What they're looking for: {intent_desc}
- Target style: {destination_desc}

PRODUCTS SELECTED:
{products_text}

Write a brief (2-4 sentence) opening narrative that connects to their root value, then write 1-2 sentences per product explaining why it's right for THEM specifically.

Format your response as:
OPENING: [your opening narrative]

PRODUCT: [product title]
WHY: [explanation]

PRODUCT: [product title]
WHY: [explanation]

[continue for each product]

CLOSING: [optional 1 sentence closing - can be empty]"""

        return prompt

    def _format_products_for_prompt(self, products: List[Dict[str, Any]]) -> str:
        """Format products for the narrative prompt."""
        lines = []

        for i, product in enumerate(products[:MAX_PRODUCTS_IN_PROMPT], 1):
            title = product.get("title", f"Product {i}")
            price = product.get("price", "")
            category = product.get("category", "")
            brand = product.get("brand", "")
            description_raw = product.get("description", "")
            description = str(description_raw)[:MAX_DESCRIPTION_LENGTH] if description_raw else ""

            # Check if it's an outlier
            is_outlier = product.get("_is_outlier", False)
            outlier_tag = " [EXPLORATION PICK]" if is_outlier else ""

            line = f"{i}. {title}{outlier_tag}"
            if brand:
                line += f" by {brand}"
            if price:
                # Handle both numeric and string prices
                try:
                    line += f" - ${float(price):.2f}"
                except (ValueError, TypeError):
                    line += f" - {price}"
            if category:
                line += f" ({category})"
            if description:
                line += f"\n   {description}"

            lines.append(line)

        return "\n".join(lines)

    def _parse_narrative_response(
        self,
        response: str,
        products: List[Dict[str, Any]],
        framing: str,
        root_value: str,
    ) -> JourneyNarrative:
        """Parse the LLM response into structured narrative."""

        # Extract opening
        opening = ""
        opening_match = re.search(r"OPENING:\s*(.+?)(?=PRODUCT:|$)", response, re.DOTALL | re.IGNORECASE)
        if opening_match:
            opening = opening_match.group(1).strip()
        else:
            # Try to get first paragraph as opening
            paragraphs = response.split("\n\n")
            if paragraphs:
                opening = paragraphs[0].strip()

        # Extract product explanations
        # Pattern allows flexible whitespace between PRODUCT and WHY
        product_explanations = []
        product_pattern = r"PRODUCT:\s*(.+?)\s*\n\s*WHY:\s*(.+?)(?=PRODUCT:|CLOSING:|$)"
        matches = re.findall(product_pattern, response, re.DOTALL | re.IGNORECASE)

        for product_title, explanation in matches:
            # Try to match with actual product
            product_title = product_title.strip()
            explanation = explanation.strip()

            # Find matching product - try exact match first, then partial
            product_id = ""
            matched_title = product_title
            best_match = None
            best_match_score = 0

            for product in products:
                actual_title = product.get("title", "")
                actual_lower = actual_title.lower()
                search_lower = product_title.lower()

                # Exact match (highest priority)
                if actual_lower == search_lower:
                    best_match = product
                    break

                # Check if search term is contained in actual title
                if search_lower in actual_lower:
                    score = len(search_lower) / len(actual_lower) if actual_lower else 0
                    if score > best_match_score:
                        best_match_score = score
                        best_match = product

            if best_match:
                # Use product id, or generate deterministic fallback from title
                fallback_id = f"product_{abs(hash(best_match.get('title', ''))) % 100000}"
                product_id = best_match.get("id", fallback_id)
                matched_title = best_match.get("title", product_title)

            product_explanations.append(ProductExplanation(
                product_id=product_id,
                product_title=matched_title,
                explanation=explanation,
            ))

        # If no structured explanations found, try to create from products
        if not product_explanations and products:
            product_explanations = self._create_fallback_explanations(products)

        # Extract closing
        closing = ""
        closing_match = re.search(r"CLOSING:\s*(.+?)$", response, re.DOTALL | re.IGNORECASE)
        if closing_match:
            closing = closing_match.group(1).strip()

        return JourneyNarrative(
            opening=opening,
            product_explanations=product_explanations,
            closing=closing,
            validation_framing=framing,
            root_value_referenced=root_value,
        )

    def _create_fallback_explanations(
        self,
        products: List[Dict[str, Any]],
    ) -> List[ProductExplanation]:
        """Create fallback explanations when parsing fails."""
        explanations = []

        for i, product in enumerate(products[:MAX_PRODUCTS_IN_PROMPT]):
            title = product.get("title", f"Product {i+1}")
            # Use product id, or generate deterministic fallback
            fallback_id = f"product_{abs(hash(title)) % 100000}"
            product_id = product.get("id", fallback_id)

            # Generate generic but relevant explanation
            is_outlier = product.get("_is_outlier", False)
            if is_outlier:
                explanation = "An exploration pick to expand your style horizons."
            else:
                category = product.get("category", "piece")
                explanation = f"A {category} that aligns with your current style direction."

            explanations.append(ProductExplanation(
                product_id=product_id,
                product_title=title,
                explanation=explanation,
            ))

        return explanations

    def _fallback_narrative(
        self,
        products: List[Dict[str, Any]],
        framing: str,
        root_value: str,
    ) -> JourneyNarrative:
        """Generate fallback narrative when LLM fails."""

        opening = f"I've selected some pieces that connect to what matters to you - {root_value}. Here's why each one works:"

        product_explanations = self._create_fallback_explanations(products)

        return JourneyNarrative(
            opening=opening,
            product_explanations=product_explanations,
            closing="",
            validation_framing=framing,
            root_value_referenced=root_value,
        )

    async def generate_narrative_async(
        self,
        nav_context: NavigationContext,
        products: List[Dict[str, Any]],
        user_profile: Optional[UserProfileForNarrative] = None,
    ) -> JourneyNarrative:
        """
        Async version of narrative generation.

        Uses AsyncOpenAI client to avoid blocking the event loop.

        Args:
            nav_context: Navigation context with query, occasion, synthesis
            products: List of selected products with metadata
            user_profile: User profile for personalization

        Returns:
            JourneyNarrative with opening, product explanations, and closing
        """
        # Use default profile if not provided
        if user_profile is None:
            user_profile = UserProfileForNarrative()

        # Determine framing based on validation source
        framing = self._get_validation_framing(user_profile.primary_validation_source)

        # Build prompt
        prompt = self._build_narrative_prompt(
            nav_context=nav_context,
            products=products,
            user_profile=user_profile,
            framing=framing,
        )

        try:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=NARRATIVE_TEMPERATURE,
                max_tokens=MAX_TOKENS,
                timeout=API_TIMEOUT,
            )

            # Validate response
            if not response.choices or not response.choices[0].message.content:
                logger.warning("Empty response from async Narrative LLM")
                return self._fallback_narrative(products, framing, user_profile.root_value)

            raw_response = response.choices[0].message.content

            # Parse the response into structured narrative
            narrative = self._parse_narrative_response(
                response=raw_response,
                products=products,
                framing=framing,
                root_value=user_profile.root_value,
            )

            logger.debug(f"Async narrative generated successfully with {len(narrative.product_explanations)} product explanations")
            return narrative

        except (KeyboardInterrupt, SystemExit):
            raise  # Don't catch system-level interrupts
        except Exception as e:
            logger.error(f"Async Narrative LLM failed: {e}")
            return self._fallback_narrative(products, framing, user_profile.root_value)


def create_user_profile_for_narrative(
    raw_user_data: Optional[Any] = None,
    computed_state: Optional[Any] = None,  # Reserved for future use (nav_params extraction)
) -> UserProfileForNarrative:
    """
    Create UserProfileForNarrative from raw user data.

    Helper function to extract narrative-relevant fields from
    the full user profile.

    Args:
        raw_user_data: RawUserData from personalization pillar
        computed_state: ComputedUserState from personalization pillar (reserved for future)

    Returns:
        UserProfileForNarrative with relevant fields populated
    """
    # Note: computed_state reserved for future extraction of nav_params
    _ = computed_state  # Silence unused parameter warning

    profile = UserProfileForNarrative()

    if raw_user_data:
        # Extract from onboarding profile
        onboarding = getattr(raw_user_data, 'onboarding_profile', None)
        if onboarding:
            # Root values
            root_values = getattr(onboarding, 'root_values', None)
            if root_values:
                profile.root_value = getattr(root_values, 'primary', None) or profile.root_value

            # Validation sources
            process = getattr(onboarding, 'process', None)
            if process:
                validation_sources = getattr(process, 'validation_sources', None)
                if validation_sources and len(validation_sources) > 0:
                    profile.primary_validation_source = getattr(
                        validation_sources[0], 'source', 'self'
                    )

                style_motivations = getattr(process, 'style_motivations', None)
                if style_motivations and len(style_motivations) > 0:
                    profile.style_motivation = getattr(
                        style_motivations[0], 'motivation', profile.style_motivation
                    )

            # Taste preferences
            taste = getattr(onboarding, 'taste', None)
            if taste:
                profile.style_wants = getattr(taste, 'style_wants', []) or []
                profile.style_avoids = getattr(taste, 'style_avoids', []) or []

        # Physical attributes
        physical = getattr(raw_user_data, 'physical_attributes', None)
        if physical:
            profile.body_type = getattr(physical, 'body_type', None)
            profile.coloring = getattr(physical, 'coloring', None)

    return profile
