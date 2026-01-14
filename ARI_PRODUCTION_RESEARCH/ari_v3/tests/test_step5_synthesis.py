"""
Tests for ARI V3 Step 5 - LLM #3 Synthesis

Tests cover:
- SynthesisLLM prompt building
- ThreePillarsInput construction
- SynthesisOutput parsing
- Path calculation (deterministic)
- NavigationContext creation
- Cold start context generation
"""

import pytest
import sys
import os

sys.path.insert(0, '/home/ubuntu/AIStylist/ARI_PRODUCTION_RESEARCH')

from dotenv import load_dotenv
load_dotenv()

import numpy as np
from unittest.mock import Mock, patch, MagicMock

from ari_v3.navigation import (
    SynthesisLLM,
    SynthesisOutput,
    ThreePillarsInput,
    BudgetInterpretation,
    NavigationContext,
    NavigationPath,
    calculate_navigation_path,
    create_cold_start_context,
)
from datetime import datetime

from ari_v3.core.data_structures import (
    StyleContext,
    StyleCoordinate,
    NavigationParameters,
    Trajectory,
    RootValues,
    BehavioralPatterns,
    SpendingPatterns,
    DefaultBudget,
    zero_vector,
)


# =============================================================================
# Test ThreePillarsInput Construction
# =============================================================================

class TestThreePillarsInput:
    """Tests for ThreePillarsInput dataclass."""

    def test_minimal_pillars_input(self):
        """Test creating minimal pillars input."""
        pillars = ThreePillarsInput()
        assert pillars.body_type is None
        assert pillars.coloring is None
        assert pillars.body_guidance == ""
        assert pillars.category_interests == []

    def test_full_pillars_input(self):
        """Test creating full pillars input."""
        nav_params = NavigationParameters(
            exploration_appetite=0.6,
            step_size_multiplier=1.2,
            brand_affinity_weight=0.4,
            result_set_size=12,
            diversity_requirement=0.5,
            user_embedding_weight=0.5,
            default_budget=DefaultBudget(min=100, max=500, flexibility=0.2),
            category_budget_overrides={},
        )

        root_values = RootValues(
            primary="authenticity",
            secondary=["creativity", "quality"],
            authenticity_importance=0.9,
            belonging_importance=0.3,
            standing_out_importance=0.6,
            comfort_importance=0.7,
            competence_importance=0.5,
        )

        pillars = ThreePillarsInput(
            body_type="hourglass",
            coloring="warm autumn",
            root_values=root_values,
            nav_params=nav_params,
            body_guidance="Structured silhouettes work well",
            occasion_guidance="Professional with personal flair",
            color_guidance="Earth tones complement your coloring",
            category_interests=["blazers", "dresses", "accessories"],
        )

        assert pillars.body_type == "hourglass"
        assert pillars.nav_params.exploration_appetite == 0.6
        assert len(pillars.category_interests) == 3


# =============================================================================
# Test SynthesisOutput
# =============================================================================

class TestSynthesisOutput:
    """Tests for SynthesisOutput dataclass."""

    def test_synthesis_output_creation(self):
        """Test creating SynthesisOutput."""
        output = SynthesisOutput(
            style_descriptors=["minimalist", "structured", "neutral tones"],
            exemplar_search_terms=["minimalist blazer", "structured wool coat"],
            understood_intent="Looking for professional outerwear with clean lines",
            budget_interpretation=BudgetInterpretation(min=200, max=600),
            formality_level=0.7,
            relevant_context=["professional context", "prefers quality"],
        )

        assert len(output.style_descriptors) == 3
        assert output.formality_level == 0.7
        assert output.budget_interpretation.min == 200


# =============================================================================
# Test SynthesisLLM
# =============================================================================

class TestSynthesisLLM:
    """Tests for SynthesisLLM class."""

    def test_category_inference(self):
        """Test category inference from query."""
        synthesis = SynthesisLLM(openai_client=Mock())

        assert synthesis._infer_category("black leather jacket") == "outerwear"
        assert synthesis._infer_category("summer dress") == "dresses"
        assert synthesis._infer_category("running shoes") == "shoes"
        assert synthesis._infer_category("casual jeans") == "bottoms"
        assert synthesis._infer_category("white shirt") == "tops"
        assert synthesis._infer_category("something nice") == "general"

    def test_fallback_synthesis(self):
        """Test fallback synthesis when LLM fails."""
        synthesis = SynthesisLLM(openai_client=Mock())

        result = synthesis._fallback_synthesis("winter coat", "work")

        assert "winter coat" in result.style_descriptors
        assert result.understood_intent == "Looking for winter coat"
        assert result.formality_level == 0.5

    @patch('ari_v3.navigation.synthesis_llm.OpenAI')
    def test_synthesize_navigation_mock(self, mock_openai_class):
        """Test synthesize_navigation with mocked OpenAI."""
        # Setup mock response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''{
            "style_descriptors": ["minimalist", "structured"],
            "exemplar_search_terms": ["minimalist blazer"],
            "understood_intent": "Professional outerwear",
            "budget_interpretation": {"min": 200, "max": 500},
            "formality_level": 0.7,
            "relevant_context": ["work context"]
        }'''
        mock_client.chat.completions.create.return_value = mock_response

        synthesis = SynthesisLLM(openai_client=mock_client)
        pillars = ThreePillarsInput(body_type="athletic")

        result = synthesis.synthesize_navigation(pillars, "blazer", "work")

        assert "minimalist" in result.style_descriptors
        assert result.formality_level == 0.7


# =============================================================================
# Test NavigationPath
# =============================================================================

class TestNavigationPath:
    """Tests for NavigationPath calculation."""

    def test_navigation_path_creation(self):
        """Test creating NavigationPath."""
        # Use non-parallel vectors so cosine distance is > 0
        current_emb = np.array([0.1] * 768 + [0.0] * 768)  # Different direction
        dest_emb = np.array([0.0] * 768 + [0.2] * 768)
        current = StyleCoordinate(
            embedding=current_emb,
            visual_embedding=np.array([0.1] * 1024),
        )
        destination = StyleCoordinate(
            embedding=dest_emb,
            visual_embedding=np.array([0.2] * 1024),
        )

        path = NavigationPath(
            current_position=current,
            destination=destination,
            max_step_size=0.3,
            outlier_percentage=0.1,
            diversity_requirement=0.5,
            smoothness_score=1.0,
            coherence_score=0.8,
        )

        assert path.max_step_size == 0.3
        assert path.total_distance > 0  # Should be computed automatically (non-parallel vectors)

    def test_is_step_valid(self):
        """Test step validity check."""
        current = StyleCoordinate(
            embedding=np.array([0.1] * 1536),
            visual_embedding=np.array([0.1] * 1024),
        )
        destination = StyleCoordinate(
            embedding=np.array([0.15] * 1536),  # Close to current
            visual_embedding=np.array([0.15] * 1024),
        )

        path = NavigationPath(
            current_position=current,
            destination=destination,
            max_step_size=0.5,  # Large step allowed
            outlier_percentage=0.1,
            diversity_requirement=0.5,
            smoothness_score=1.0,
            coherence_score=0.8,
        )

        assert path.is_step_valid()  # Small distance, large allowed step


# =============================================================================
# Test calculate_navigation_path
# =============================================================================

class TestCalculateNavigationPath:
    """Tests for path calculation function."""

    def test_calculate_path_basic(self):
        """Test basic path calculation."""
        current = StyleCoordinate(
            embedding=np.array([0.1] * 1536),
            visual_embedding=np.array([0.1] * 1024),
        )
        destination = StyleCoordinate(
            embedding=np.array([0.2] * 1536),
            visual_embedding=np.array([0.2] * 1024),
        )
        trajectory = Trajectory(
            direction=np.array([0.1] * 1536),
            velocity=0.04,
            consistency=0.7,
            last_computed=datetime.now(),
        )
        nav_params = NavigationParameters(
            exploration_appetite=0.5,
            step_size_multiplier=1.0,
            brand_affinity_weight=0.3,
            result_set_size=12,
            diversity_requirement=0.5,
            user_embedding_weight=0.5,
            default_budget=None,
            category_budget_overrides={},
        )

        path = calculate_navigation_path(current, destination, trajectory, nav_params)

        assert path.max_step_size == 0.3  # base_step * multiplier
        assert path.outlier_percentage == 0.1  # 0.5 * 0.20

    def test_slow_mover_adjustment(self):
        """Test that slow movers get conservative step size."""
        current = StyleCoordinate(embedding=np.array([0.1] * 1536), visual_embedding=None)
        destination = StyleCoordinate(embedding=np.array([0.2] * 1536), visual_embedding=None)
        trajectory = Trajectory(direction=np.array([]), velocity=0.01, consistency=0.9, last_computed=datetime.now())  # Slow mover
        nav_params = NavigationParameters(
            exploration_appetite=0.5,
            step_size_multiplier=1.0,
            brand_affinity_weight=0.3,
            result_set_size=12,
            diversity_requirement=0.5,
            user_embedding_weight=0.5,
            default_budget=None,
            category_budget_overrides={},
        )

        path = calculate_navigation_path(current, destination, trajectory, nav_params)

        assert path.max_step_size == 0.21  # 0.3 * 0.7 for slow mover

    def test_fast_mover_adjustment(self):
        """Test that fast movers get aggressive step size."""
        current = StyleCoordinate(embedding=np.array([0.1] * 1536), visual_embedding=None)
        destination = StyleCoordinate(embedding=np.array([0.2] * 1536), visual_embedding=None)
        trajectory = Trajectory(direction=np.array([]), velocity=0.08, consistency=0.5, last_computed=datetime.now())  # Fast mover
        nav_params = NavigationParameters(
            exploration_appetite=0.5,
            step_size_multiplier=1.0,
            brand_affinity_weight=0.3,
            result_set_size=12,
            diversity_requirement=0.5,
            user_embedding_weight=0.5,
            default_budget=None,
            category_budget_overrides={},
        )

        path = calculate_navigation_path(current, destination, trajectory, nav_params)

        assert path.max_step_size == 0.36  # 0.3 * 1.2 for fast mover


# =============================================================================
# Test NavigationContext
# =============================================================================

class TestNavigationContext:
    """Tests for NavigationContext."""

    def test_to_agent_context(self):
        """Test conversion to agent context dict."""
        current = StyleCoordinate(embedding=np.array([0.1] * 1536), visual_embedding=None)
        destination = StyleCoordinate(embedding=np.array([0.2] * 1536), visual_embedding=None)
        trajectory = Trajectory(direction=np.array([]), velocity=0.04, consistency=0.7, last_computed=datetime.now())

        path = NavigationPath(
            current_position=current,
            destination=destination,
            max_step_size=0.3,
            outlier_percentage=0.1,
            diversity_requirement=0.5,
            smoothness_score=1.0,
            coherence_score=0.8,
        )

        synthesis = SynthesisOutput(
            style_descriptors=["minimalist", "structured"],
            exemplar_search_terms=["minimalist blazer"],
            understood_intent="Professional outerwear",
            budget_interpretation=BudgetInterpretation(min=200, max=500),
            formality_level=0.7,
            relevant_context=["work context"],
        )

        context = NavigationContext(
            current_position=current,
            trajectory=trajectory,
            destination=destination,
            path=path,
            query="blazer",
            occasion="work",
            raw_user_data=None,
            computed_state=None,
            synthesis=synthesis,
        )

        agent_ctx = context.to_agent_context()

        assert agent_ctx["query"] == "blazer"
        assert agent_ctx["occasion"] == "work"
        assert agent_ctx["max_step_size"] == 0.3
        assert agent_ctx["style_descriptors"] == ["minimalist", "structured"]
        assert agent_ctx["budget_min"] == 200


# =============================================================================
# Test Cold Start Context
# =============================================================================

class TestColdStartContext:
    """Tests for cold start context creation."""

    def test_create_cold_start_context(self):
        """Test creating cold start context."""
        context = create_cold_start_context(
            query="summer dress",
            occasion="vacation",
            default_budget_min=100,
            default_budget_max=400,
        )

        assert context.query == "summer dress"
        assert context.occasion == "vacation"
        assert context.synthesis.budget_interpretation.min == 100
        assert "cold start" in context.synthesis.relevant_context[0]
        assert context.path.max_step_size == 0.3

    def test_cold_start_agent_context(self):
        """Test cold start context converts to agent context."""
        context = create_cold_start_context("shoes")
        agent_ctx = context.to_agent_context()

        assert agent_ctx["query"] == "shoes"
        assert "destination_embedding" in agent_ctx


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
