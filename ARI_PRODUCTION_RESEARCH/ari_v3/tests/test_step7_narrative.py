"""
Unit tests for Step 7: Narrative LLM

Tests the NarrativeLLM class and supporting dataclasses.
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
    NARRATIVE_MODEL,
    NARRATIVE_TEMPERATURE,
)
from ari_v3.navigation.navigation_context import (
    NavigationContext,
    NavigationPath,
    create_cold_start_context,
)
from ari_v3.core.data_structures import StyleCoordinate, Trajectory, zero_vector
from ari_v3.navigation.constants import TEXT_EMBEDDING_DIM, VISUAL_EMBEDDING_DIM


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_products():
    """Sample products for testing."""
    return [
        {
            "id": "prod_001",
            "title": "Classic Navy Blazer",
            "brand": "Brooks Brothers",
            "price": 299.99,
            "category": "outerwear",
            "description": "A timeless navy blazer with gold buttons, perfect for any occasion.",
        },
        {
            "id": "prod_002",
            "title": "White Oxford Shirt",
            "brand": "Ralph Lauren",
            "price": 89.50,
            "category": "tops",
            "description": "Crisp white oxford shirt with button-down collar.",
        },
        {
            "id": "prod_003",
            "title": "Slim Fit Chinos",
            "brand": "J.Crew",
            "price": 79.00,
            "category": "bottoms",
            "description": "Versatile chinos in a modern slim fit.",
            "_is_outlier": True,
        },
    ]


@pytest.fixture
def sample_nav_context():
    """Sample navigation context for testing."""
    return create_cold_start_context(
        query="professional interview outfit",
        occasion="job interview",
    )


@pytest.fixture
def sample_user_profile():
    """Sample user profile for testing."""
    return UserProfileForNarrative(
        root_value="confidence",
        primary_validation_source="colleagues",
        style_motivation="making a strong first impression",
        style_wants=["polished", "professional", "timeless"],
        style_avoids=["trendy", "casual", "loud patterns"],
        body_type="athletic",
        coloring="warm",
    )


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """OPENING: Your goal of making a confident first impression really shows in these selections. Each piece here works together to project the polished, professional image you're after.

PRODUCT: Classic Navy Blazer
WHY: This blazer is a cornerstone of professional style - it'll help you project authority while staying approachable, exactly what you need for that interview.

PRODUCT: White Oxford Shirt
WHY: A crisp white oxford is the foundation of any polished look. It's timeless and says "I pay attention to details."

PRODUCT: Slim Fit Chinos
WHY: As an exploration pick, these chinos offer a modern twist on traditional interview wear while maintaining that professional edge you want.

CLOSING: You've got this - these pieces will help you walk in feeling ready."""
    return mock_response


# =============================================================================
# ProductExplanation Tests
# =============================================================================

class TestProductExplanation:
    """Tests for ProductExplanation dataclass."""

    def test_creation(self):
        """Test basic creation."""
        pe = ProductExplanation(
            product_id="test_id",
            product_title="Test Product",
            explanation="This is why it works.",
        )
        assert pe.product_id == "test_id"
        assert pe.product_title == "Test Product"
        assert pe.explanation == "This is why it works."


# =============================================================================
# JourneyNarrative Tests
# =============================================================================

class TestJourneyNarrative:
    """Tests for JourneyNarrative dataclass."""

    def test_creation_minimal(self):
        """Test minimal creation with just opening."""
        narrative = JourneyNarrative(opening="Welcome to your style journey.")
        assert narrative.opening == "Welcome to your style journey."
        assert narrative.product_explanations == []
        assert narrative.closing == ""

    def test_creation_full(self):
        """Test full creation with all fields."""
        explanations = [
            ProductExplanation("p1", "Product 1", "Great fit"),
            ProductExplanation("p2", "Product 2", "Perfect color"),
        ]
        narrative = JourneyNarrative(
            opening="Here are your picks.",
            product_explanations=explanations,
            closing="Enjoy your new style!",
            validation_framing="how these pieces express who you are",
            root_value_referenced="authenticity",
        )
        assert len(narrative.product_explanations) == 2
        assert narrative.closing == "Enjoy your new style!"
        assert narrative.validation_framing == "how these pieces express who you are"

    def test_to_dict(self):
        """Test serialization to dictionary."""
        narrative = JourneyNarrative(
            opening="Opening text",
            product_explanations=[
                ProductExplanation("id1", "Title 1", "Explanation 1"),
            ],
            closing="Closing text",
            validation_framing="framing",
            root_value_referenced="value",
        )
        result = narrative.to_dict()

        assert result["opening"] == "Opening text"
        assert result["closing"] == "Closing text"
        assert len(result["product_explanations"]) == 1
        assert result["product_explanations"][0]["product_id"] == "id1"
        assert result["validation_framing"] == "framing"

    def test_format_for_display(self):
        """Test display formatting."""
        narrative = JourneyNarrative(
            opening="Here's what I found for you.",
            product_explanations=[
                ProductExplanation("p1", "Navy Blazer", "Perfect for interviews."),
                ProductExplanation("p2", "White Shirt", "A timeless classic."),
            ],
            closing="You're going to look great!",
        )
        display = narrative.format_for_display()

        assert "Here's what I found for you." in display
        assert "**Navy Blazer**: Perfect for interviews." in display
        assert "**White Shirt**: A timeless classic." in display
        assert "You're going to look great!" in display

    def test_format_for_display_no_closing(self):
        """Test display formatting without closing."""
        narrative = JourneyNarrative(
            opening="Opening",
            product_explanations=[
                ProductExplanation("p1", "Product", "Why"),
            ],
        )
        display = narrative.format_for_display()
        # Should not have extra newlines at end from empty closing
        assert display.endswith("**Product**: Why")


# =============================================================================
# UserProfileForNarrative Tests
# =============================================================================

class TestUserProfileForNarrative:
    """Tests for UserProfileForNarrative dataclass."""

    def test_defaults(self):
        """Test default values."""
        profile = UserProfileForNarrative()
        assert profile.root_value == "self-expression"
        assert profile.primary_validation_source == "self"
        assert profile.style_motivation == "looking good"
        assert profile.style_wants == []
        assert profile.style_avoids == []

    def test_custom_values(self):
        """Test custom values."""
        profile = UserProfileForNarrative(
            root_value="authenticity",
            primary_validation_source="partner",
            style_wants=["elegant", "classic"],
        )
        assert profile.root_value == "authenticity"
        assert profile.primary_validation_source == "partner"
        assert profile.style_wants == ["elegant", "classic"]


# =============================================================================
# NarrativeLLM Tests
# =============================================================================

class TestNarrativeLLM:
    """Tests for NarrativeLLM class."""

    def test_init_default(self):
        """Test initialization with defaults."""
        with patch('ari_v3.narrative.narrative_llm.OpenAI'):
            llm = NarrativeLLM()
            assert llm.model == NARRATIVE_MODEL

    def test_init_custom_model(self):
        """Test initialization with custom model."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client, model="gpt-3.5-turbo")
        assert llm.model == "gpt-3.5-turbo"
        assert llm.client == mock_client

    def test_get_validation_framing_self(self):
        """Test validation framing for self."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)
        framing = llm._get_validation_framing("self")
        assert framing == "how these pieces express who you are"

    def test_get_validation_framing_partner(self):
        """Test validation framing for partner."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)
        framing = llm._get_validation_framing("partner")
        assert framing == "pieces your partner would love seeing you in"

    def test_get_validation_framing_colleagues(self):
        """Test validation framing for colleagues."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)
        framing = llm._get_validation_framing("colleagues")
        assert framing == "how you'll be perceived professionally"

    def test_get_validation_framing_strangers(self):
        """Test validation framing for strangers."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)
        framing = llm._get_validation_framing("strangers")
        assert framing == "the impression you'll make"

    def test_get_validation_framing_unknown(self):
        """Test validation framing for unknown source."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)
        framing = llm._get_validation_framing("unknown_source")
        assert framing == "your style journey"

    def test_get_validation_framing_case_insensitive(self):
        """Test validation framing is case insensitive."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)
        assert llm._get_validation_framing("SELF") == "how these pieces express who you are"
        assert llm._get_validation_framing("Partner") == "pieces your partner would love seeing you in"

    def test_format_products_for_prompt(self, sample_products):
        """Test product formatting for prompt."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)
        formatted = llm._format_products_for_prompt(sample_products)

        assert "Classic Navy Blazer" in formatted
        assert "Brooks Brothers" in formatted
        assert "$299.99" in formatted
        assert "(outerwear)" in formatted
        assert "[EXPLORATION PICK]" in formatted  # For outlier product

    def test_format_products_limits_to_10(self, sample_products):
        """Test that product formatting limits to 10 products."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        # Create 15 products
        many_products = sample_products * 5
        formatted = llm._format_products_for_prompt(many_products)

        # Should only have 10 numbered items
        assert "10." in formatted
        assert "11." not in formatted

    def test_format_products_handles_missing_fields(self):
        """Test product formatting with missing fields."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        products = [{"id": "minimal"}]
        formatted = llm._format_products_for_prompt(products)
        assert "Product 1" in formatted  # Default title

    def test_parse_narrative_response(self, sample_products):
        """Test parsing LLM response."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        response = """OPENING: Here are your picks.

PRODUCT: Classic Navy Blazer
WHY: Perfect for interviews.

PRODUCT: White Oxford Shirt
WHY: A timeless foundation.

CLOSING: You'll look great!"""

        narrative = llm._parse_narrative_response(
            response=response,
            products=sample_products,
            framing="test framing",
            root_value="confidence",
        )

        assert "Here are your picks." in narrative.opening
        assert len(narrative.product_explanations) == 2
        assert narrative.closing == "You'll look great!"
        assert narrative.validation_framing == "test framing"
        assert narrative.root_value_referenced == "confidence"

    def test_parse_narrative_response_no_structured_format(self, sample_products):
        """Test parsing when LLM doesn't follow format."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        # Unstructured response
        response = "I think these products would work well for you. The blazer is great!"

        narrative = llm._parse_narrative_response(
            response=response,
            products=sample_products,
            framing="test",
            root_value="test",
        )

        # Should use fallback explanations
        assert len(narrative.product_explanations) == 3
        assert narrative.opening == "I think these products would work well for you. The blazer is great!"

    def test_create_fallback_explanations(self, sample_products):
        """Test fallback explanation creation."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        explanations = llm._create_fallback_explanations(sample_products)

        assert len(explanations) == 3
        assert explanations[0].product_title == "Classic Navy Blazer"
        assert "outerwear" in explanations[0].explanation

        # Check outlier handling
        assert "exploration" in explanations[2].explanation.lower()

    def test_fallback_narrative(self, sample_products):
        """Test fallback narrative generation."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        narrative = llm._fallback_narrative(
            products=sample_products,
            framing="professional",
            root_value="confidence",
        )

        assert "confidence" in narrative.opening
        assert len(narrative.product_explanations) == 3
        assert narrative.root_value_referenced == "confidence"

    def test_generate_narrative_success(
        self, sample_nav_context, sample_products, sample_user_profile, mock_openai_response
    ):
        """Test successful narrative generation."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=sample_nav_context,
            products=sample_products,
            user_profile=sample_user_profile,
        )

        assert narrative.opening != ""
        assert len(narrative.product_explanations) >= 1
        mock_client.chat.completions.create.assert_called_once()

    def test_generate_narrative_empty_response(
        self, sample_nav_context, sample_products, sample_user_profile
    ):
        """Test narrative generation with empty response."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = []  # Empty choices
        mock_client.chat.completions.create.return_value = mock_response

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=sample_nav_context,
            products=sample_products,
            user_profile=sample_user_profile,
        )

        # Should return fallback
        assert "confidence" in narrative.opening
        assert len(narrative.product_explanations) == 3

    def test_generate_narrative_api_error(
        self, sample_nav_context, sample_products, sample_user_profile
    ):
        """Test narrative generation handles API errors."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=sample_nav_context,
            products=sample_products,
            user_profile=sample_user_profile,
        )

        # Should return fallback without raising
        assert narrative.opening != ""
        assert len(narrative.product_explanations) == 3

    def test_generate_narrative_default_profile(
        self, sample_nav_context, sample_products, mock_openai_response
    ):
        """Test narrative generation with default profile."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_openai_response

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=sample_nav_context,
            products=sample_products,
            user_profile=None,  # Should use default
        )

        assert narrative is not None

    def test_generate_narrative_empty_products(self, sample_nav_context, sample_user_profile):
        """Test narrative generation with no products."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OPENING: No products to show.\n\nCLOSING: Come back soon!"
        mock_client.chat.completions.create.return_value = mock_response

        llm = NarrativeLLM(openai_client=mock_client)
        narrative = llm.generate_narrative(
            nav_context=sample_nav_context,
            products=[],
            user_profile=sample_user_profile,
        )

        assert narrative.product_explanations == []


# =============================================================================
# create_user_profile_for_narrative Tests
# =============================================================================

class TestCreateUserProfileForNarrative:
    """Tests for create_user_profile_for_narrative function."""

    def test_none_inputs(self):
        """Test with None inputs returns defaults."""
        profile = create_user_profile_for_narrative(None, None)
        assert profile.root_value == "self-expression"
        assert profile.primary_validation_source == "self"

    def test_with_raw_user_data(self):
        """Test extraction from raw user data."""
        # Create mock raw user data
        mock_data = MagicMock()
        mock_data.onboarding_profile = MagicMock()
        mock_data.onboarding_profile.root_values = MagicMock()
        mock_data.onboarding_profile.root_values.primary = "authenticity"

        mock_data.onboarding_profile.process = MagicMock()
        mock_data.onboarding_profile.process.validation_sources = [MagicMock()]
        mock_data.onboarding_profile.process.validation_sources[0].source = "partner"

        mock_data.onboarding_profile.process.style_motivations = [MagicMock()]
        mock_data.onboarding_profile.process.style_motivations[0].motivation = "feeling confident"

        mock_data.onboarding_profile.taste = MagicMock()
        mock_data.onboarding_profile.taste.style_wants = ["elegant", "classic"]
        mock_data.onboarding_profile.taste.style_avoids = ["flashy"]

        mock_data.physical_attributes = MagicMock()
        mock_data.physical_attributes.body_type = "hourglass"
        mock_data.physical_attributes.coloring = "cool"

        profile = create_user_profile_for_narrative(mock_data)

        assert profile.root_value == "authenticity"
        assert profile.primary_validation_source == "partner"
        assert profile.style_motivation == "feeling confident"
        assert profile.style_wants == ["elegant", "classic"]
        assert profile.style_avoids == ["flashy"]
        assert profile.body_type == "hourglass"
        assert profile.coloring == "cool"

    def test_partial_data(self):
        """Test with partial data - missing fields should use defaults."""
        mock_data = MagicMock()
        mock_data.onboarding_profile = MagicMock()
        mock_data.onboarding_profile.root_values = None  # Missing
        mock_data.onboarding_profile.process = None  # Missing
        mock_data.onboarding_profile.taste = None  # Missing
        mock_data.physical_attributes = None  # Missing

        profile = create_user_profile_for_narrative(mock_data)

        assert profile.root_value == "self-expression"  # Default
        assert profile.primary_validation_source == "self"  # Default

    def test_empty_validation_sources(self):
        """Test with empty validation sources list."""
        mock_data = MagicMock()
        mock_data.onboarding_profile = MagicMock()
        mock_data.onboarding_profile.root_values = None
        mock_data.onboarding_profile.process = MagicMock()
        mock_data.onboarding_profile.process.validation_sources = []  # Empty list
        mock_data.onboarding_profile.process.style_motivations = []  # Empty list
        mock_data.onboarding_profile.taste = None
        mock_data.physical_attributes = None

        profile = create_user_profile_for_narrative(mock_data)

        # Should use defaults for missing/empty data
        assert profile.primary_validation_source == "self"
        assert profile.style_motivation == "looking good"


# =============================================================================
# Product Matching Tests
# =============================================================================

class TestProductMatching:
    """Tests for product title matching in parse_narrative_response."""

    def test_exact_match(self):
        """Test exact title matching."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        products = [
            {"id": "1", "title": "Navy Blazer"},
            {"id": "2", "title": "White Shirt"},
        ]

        response = """OPENING: Test

PRODUCT: Navy Blazer
WHY: Perfect.

CLOSING:"""

        narrative = llm._parse_narrative_response(response, products, "", "")
        assert narrative.product_explanations[0].product_id == "1"
        assert narrative.product_explanations[0].product_title == "Navy Blazer"

    def test_partial_match_prefers_better_coverage(self):
        """Test that partial matching prefers better coverage."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        products = [
            {"id": "1", "title": "Classic Navy Blazer with Gold Buttons"},
            {"id": "2", "title": "Navy Blazer"},  # Better match for "Navy Blazer"
        ]

        response = """OPENING: Test

PRODUCT: Navy Blazer
WHY: Great.

CLOSING:"""

        narrative = llm._parse_narrative_response(response, products, "", "")
        # Should match the shorter, more exact title
        assert narrative.product_explanations[0].product_id == "2"

    def test_case_insensitive_matching(self):
        """Test case insensitive matching."""
        mock_client = MagicMock()
        llm = NarrativeLLM(openai_client=mock_client)

        products = [{"id": "1", "title": "NAVY BLAZER"}]

        response = """OPENING: Test

PRODUCT: navy blazer
WHY: Great.

CLOSING:"""

        narrative = llm._parse_narrative_response(response, products, "", "")
        assert narrative.product_explanations[0].product_id == "1"
