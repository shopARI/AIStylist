"""
Integration tests for Step 7: Narrative LLM

Tests the NarrativeLLM integration with other ARI V3 components.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from ari_v3.narrative.narrative_llm import (
    NarrativeLLM,
    JourneyNarrative,
    ProductExplanation,
    UserProfileForNarrative,
    create_user_profile_for_narrative,
)
from ari_v3.navigation.navigation_context import (
    NavigationContext,
    NavigationPath,
    create_cold_start_context,
    BehavioralProfile,
)
from ari_v3.navigation.synthesis_llm import SynthesisOutput, BudgetInterpretation
from ari_v3.judge.ari_evaluator import ARIEvaluator
from ari_v3.judge.mmr_selector import ScoredProduct, mmr_select, create_scored_products
from ari_v3.core.data_structures import (
    StyleCoordinate,
    Trajectory,
    NavigationParameters,
    ComputedUserState,
    StyleContext,
    DefaultBudget,
    zero_vector,
)
from ari_v3.navigation.constants import TEXT_EMBEDDING_DIM, VISUAL_EMBEDDING_DIM

import numpy as np


# =============================================================================
# Integration Test Fixtures
# =============================================================================

@pytest.fixture
def full_nav_context():
    """Create a full navigation context with synthesis output."""
    # Create coordinates
    current = StyleCoordinate(
        embedding=zero_vector(TEXT_EMBEDDING_DIM),
        visual_embedding=zero_vector(VISUAL_EMBEDDING_DIM),
    )
    destination = StyleCoordinate(
        embedding=zero_vector(TEXT_EMBEDDING_DIM),
        visual_embedding=zero_vector(VISUAL_EMBEDDING_DIM),
    )

    # Create trajectory
    trajectory = Trajectory(
        direction=zero_vector(TEXT_EMBEDDING_DIM),
        velocity=0.05,
        consistency=0.8,
        last_computed=datetime.now(),
    )

    # Create nav params
    nav_params = NavigationParameters(
        exploration_appetite=0.3,
        step_size_multiplier=1.0,
        brand_affinity_weight=0.4,
        result_set_size=10,
        diversity_requirement=0.5,
        user_embedding_weight=0.6,
        default_budget=DefaultBudget(min=100, max=500, flexibility=0.2),
        category_budget_overrides={},
    )

    # Create path
    path = NavigationPath(
        current_position=current,
        destination=destination,
        max_step_size=0.3,
        outlier_percentage=0.1,
        diversity_requirement=0.5,
        smoothness_score=1.0,
        coherence_score=0.8,
    )

    # Create synthesis output
    synthesis = SynthesisOutput(
        style_descriptors=["professional", "polished", "confident"],
        exemplar_search_terms=["navy blazer interview", "professional outfit"],
        understood_intent="Looking for professional interview attire",
        budget_interpretation=BudgetInterpretation(min=100, max=500),
        formality_level=0.8,
        relevant_context=["job interview", "first impression"],
    )

    # Create computed state (using mock to avoid complex initialization)
    computed_state = MagicMock(spec=ComputedUserState)
    computed_state.nav_params = nav_params
    computed_state.active_context = StyleContext.PROFESSIONAL
    computed_state.detected_contexts = [StyleContext.PROFESSIONAL]

    return NavigationContext(
        current_position=current,
        trajectory=trajectory,
        destination=destination,
        path=path,
        query="professional interview outfit",
        occasion="job interview",
        raw_user_data=None,
        computed_state=computed_state,
        synthesis=synthesis,
        styling_rules=["Avoid overly casual items", "Stick to neutral colors"],
        body_guidance="Structured pieces work well",
        behavioral_profile=BehavioralProfile(
            category_interests=["blazers", "dress shirts"],
            brand_preferences=["Brooks Brothers", "Ralph Lauren"],
        ),
    )


@pytest.fixture
def evaluated_products():
    """Products that have been through the Judge (Step 6)."""
    return [
        {
            "id": "eval_001",
            "title": "Classic Navy Blazer",
            "brand": "Brooks Brothers",
            "price": 299.99,
            "category": "outerwear",
            "description": "A timeless navy blazer with gold buttons.",
            "_final_rank": 1,
            "_relevance_score": 0.92,
            "_score_breakdown": {
                "smoothness": 0.95,
                "coherence": 0.88,
                "budget_fit": 0.90,
                "brand_match": 1.0,
                "behavioral_consistency": 0.85,
                "multi_agent_confidence": 0.80,
                "rule_compliance": 0.95,
            },
        },
        {
            "id": "eval_002",
            "title": "White Oxford Dress Shirt",
            "brand": "Ralph Lauren",
            "price": 89.50,
            "category": "tops",
            "description": "Crisp white oxford with button-down collar.",
            "_final_rank": 2,
            "_relevance_score": 0.88,
            "_score_breakdown": {
                "smoothness": 0.90,
                "coherence": 0.85,
                "budget_fit": 1.0,
                "brand_match": 1.0,
                "behavioral_consistency": 0.82,
                "multi_agent_confidence": 0.75,
                "rule_compliance": 0.90,
            },
        },
        {
            "id": "eval_003",
            "title": "Modern Slim Chinos",
            "brand": "J.Crew",
            "price": 79.00,
            "category": "bottoms",
            "description": "Versatile chinos in a modern slim fit.",
            "_final_rank": 3,
            "_relevance_score": 0.75,
            "_is_outlier": True,
            "_outlier_reason": "exploration_injection",
            "_score_breakdown": {
                "smoothness": 0.70,
                "coherence": 0.65,
                "budget_fit": 1.0,
                "brand_match": 0.5,
                "behavioral_consistency": 0.70,
                "multi_agent_confidence": 0.60,
                "rule_compliance": 0.80,
            },
        },
    ]


@pytest.fixture
def mock_llm_response_professional():
    """Mock LLM response for professional context."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """OPENING: Your search for professional interview attire shows you understand that first impressions matter. These pieces are selected to help you project confidence and competence from the moment you walk in.

PRODUCT: Classic Navy Blazer
WHY: This Brooks Brothers blazer is the cornerstone of professional presence - it signals that you take the opportunity seriously while the classic cut ensures you look polished, not overdone.

PRODUCT: White Oxford Dress Shirt
WHY: A crisp white oxford is the foundation every professional wardrobe needs. It's versatile enough for any interview setting and shows attention to detail.

PRODUCT: Modern Slim Chinos
WHY: As an exploration pick, these chinos offer a contemporary take on interview-appropriate bottoms - a subtle way to show you're current without being trendy.

CLOSING: Walk in confident - you've got this."""
    return mock_response


# =============================================================================
# Integration Tests
# =============================================================================

class TestNarrativeWithNavigationContext:
    """Test Narrative LLM with full navigation context."""

    def test_narrative_uses_synthesis_descriptors(
        self, full_nav_context, evaluated_products, mock_llm_response_professional
    ):
        """Test that narrative prompt includes synthesis descriptors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=full_nav_context,
            products=evaluated_products,
        )

        # Check that the prompt was built correctly
        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][1]["content"]

        # Synthesis descriptors should be in the prompt
        assert "professional" in prompt.lower()
        assert "polished" in prompt.lower()

    def test_narrative_uses_occasion(
        self, full_nav_context, evaluated_products, mock_llm_response_professional
    ):
        """Test that narrative prompt includes occasion."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        llm.generate_narrative(
            nav_context=full_nav_context,
            products=evaluated_products,
        )

        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][1]["content"]

        assert "job interview" in prompt.lower()

    def test_narrative_handles_outlier_products(
        self, full_nav_context, evaluated_products, mock_llm_response_professional
    ):
        """Test that narrative correctly identifies outlier products."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        llm.generate_narrative(
            nav_context=full_nav_context,
            products=evaluated_products,
        )

        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][1]["content"]

        # Outlier should be tagged
        assert "[EXPLORATION PICK]" in prompt


class TestNarrativeWithEvaluatedProducts:
    """Test Narrative LLM with products from ARIEvaluator."""

    def test_narrative_preserves_score_metadata(
        self, full_nav_context, evaluated_products, mock_llm_response_professional
    ):
        """Test that product score metadata is accessible."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=full_nav_context,
            products=evaluated_products,
        )

        # Products should still have their score metadata
        assert evaluated_products[0]["_final_rank"] == 1
        assert evaluated_products[0]["_relevance_score"] == 0.92

    def test_narrative_with_brand_preferences(
        self, full_nav_context, evaluated_products, mock_llm_response_professional
    ):
        """Test narrative generation respects brand preferences from behavioral profile."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        # User profile with brand preferences
        user_profile = UserProfileForNarrative(
            root_value="professionalism",
            primary_validation_source="colleagues",
            style_wants=["classic", "timeless"],
        )

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=full_nav_context,
            products=evaluated_products,
            user_profile=user_profile,
        )

        assert narrative.validation_framing == "how you'll be perceived professionally"


class TestNarrativeWithColdStart:
    """Test Narrative LLM with cold start context."""

    def test_cold_start_narrative(self, mock_llm_response_professional):
        """Test narrative generation for cold start users."""
        cold_start_context = create_cold_start_context(
            query="casual summer outfit",
            occasion="weekend brunch",
        )

        products = [
            {"id": "p1", "title": "Linen Shirt", "price": 59.99, "category": "tops"},
            {"id": "p2", "title": "Chino Shorts", "price": 49.99, "category": "bottoms"},
        ]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=cold_start_context,
            products=products,
        )

        # Should still generate a narrative
        assert narrative.opening != ""

    def test_cold_start_uses_default_profile(self, mock_llm_response_professional):
        """Test that cold start uses default user profile."""
        cold_start_context = create_cold_start_context(query="test")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        llm.generate_narrative(
            nav_context=cold_start_context,
            products=[{"id": "1", "title": "Test Product"}],
            user_profile=None,  # Should use default
        )

        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][1]["content"]

        # Default root value should be used
        assert "self-expression" in prompt


class TestEndToEndNarrativePipeline:
    """End-to-end tests for the full narrative pipeline."""

    def test_full_pipeline_mmr_to_narrative(self, mock_llm_response_professional):
        """Test narrative generation after MMR selection."""
        # Step 1: Create scored products
        products = [
            {"id": f"p{i}", "title": f"Product {i}", "price": 50 + i * 10}
            for i in range(10)
        ]
        embeddings = [np.random.rand(TEXT_EMBEDDING_DIM) for _ in range(10)]
        scores = [0.9 - i * 0.05 for i in range(10)]

        scored_products = create_scored_products(
            products=products,
            relevance_scores=scores,
            embeddings=embeddings,
        )

        # Step 2: Apply MMR selection
        selected = mmr_select(
            candidates=scored_products,
            limit=5,
            lambda_param=0.5,
        )

        # Step 3: Convert back to product dicts
        selected_products = [sp.product for sp in selected]

        # Step 4: Generate narrative
        nav_context = create_cold_start_context(query="test query")

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=nav_context,
            products=selected_products,
        )

        # Verify narrative was generated
        assert narrative is not None
        assert narrative.opening != ""

    def test_narrative_serialization_roundtrip(self, mock_llm_response_professional):
        """Test that narrative can be serialized and contains expected fields."""
        nav_context = create_cold_start_context(query="professional attire")

        products = [
            {"id": "1", "title": "Navy Blazer", "price": 200, "category": "outerwear"},
            {"id": "2", "title": "White Shirt", "price": 80, "category": "tops"},
        ]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=nav_context,
            products=products,
        )

        # Serialize to dict
        narrative_dict = narrative.to_dict()

        # Verify structure
        assert "opening" in narrative_dict
        assert "product_explanations" in narrative_dict
        assert "closing" in narrative_dict
        assert "validation_framing" in narrative_dict
        assert "root_value_referenced" in narrative_dict

        # Verify it can be used for display
        display_text = narrative.format_for_display()
        assert isinstance(display_text, str)
        assert len(display_text) > 0


class TestValidationFramingIntegration:
    """Test validation framing with different user contexts."""

    @pytest.mark.parametrize("validation_source,expected_phrase", [
        ("self", "express who you are"),
        ("partner", "partner would love"),
        ("colleagues", "perceived professionally"),
        ("strangers", "impression you'll make"),
    ])
    def test_validation_framing_variations(
        self, validation_source, expected_phrase, mock_llm_response_professional
    ):
        """Test different validation source framings."""
        nav_context = create_cold_start_context(query="test")

        user_profile = UserProfileForNarrative(
            root_value="confidence",
            primary_validation_source=validation_source,
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_llm_response_professional

        llm = NarrativeLLM(openai_client=mock_client)
        llm.generate_narrative(
            nav_context=nav_context,
            products=[{"id": "1", "title": "Test"}],
            user_profile=user_profile,
        )

        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args.kwargs["messages"][1]["content"]

        assert expected_phrase in prompt.lower()


class TestNarrativeErrorHandling:
    """Test error handling in narrative generation."""

    def test_graceful_degradation_on_api_timeout(self):
        """Test graceful degradation when API times out."""
        nav_context = create_cold_start_context(query="test")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError("API timeout")

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=nav_context,
            products=[{"id": "1", "title": "Test Product", "category": "test"}],
        )

        # Should return fallback narrative without raising
        assert narrative.opening != ""
        assert "self-expression" in narrative.opening  # Default root value

    def test_handles_malformed_llm_response(self):
        """Test handling of malformed LLM response."""
        nav_context = create_cold_start_context(query="test")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not in the expected format at all."
        mock_client.chat.completions.create.return_value = mock_response

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=nav_context,
            products=[{"id": "1", "title": "Test Product"}],
        )

        # Should still produce a narrative
        assert narrative is not None
        # Opening should be the raw response since no OPENING: tag
        assert "not in the expected format" in narrative.opening
