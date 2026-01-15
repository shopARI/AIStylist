"""
Integration tests for ARI V3 Step 8: Navigation Intelligence Orchestrator

Tests the complete integration between orchestrator and other modules.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from ari_v3.orchestrator.navigation_intelligence import (
    NavigationIntelligence,
    NavigationOrchestrator,
    SearchResult,
    create_navigation_intelligence,
    create_navigation_orchestrator,
)
from ari_v3.core.data_structures import (
    StyleContext,
    StyleCoordinate,
    RawUserData,
    ComputedUserState,
    zero_vector,
)
from ari_v3.navigation.navigation_context import (
    NavigationContext,
    NavigationPath,
)
from ari_v3.navigation.synthesis_llm import (
    SynthesisOutput,
    BudgetInterpretation,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_openai_client():
    """Create comprehensive mock OpenAI client."""
    client = MagicMock()
    # Mock embeddings
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [MagicMock(embedding=[0.1] * 1536)]
    client.embeddings.create.return_value = mock_embedding_response
    # Mock completions
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content='{"style_descriptors": ["casual", "relaxed", "comfortable"], "exemplar_search_terms": ["casual shirt", "relaxed top"], "understood_intent": "Looking for casual everyday wear", "budget_interpretation": {"min": 50, "max": 200, "reasoning": "Standard casual range"}, "formality_level": 0.3, "relevant_context": ["casual style", "comfort focus"]}'))
    ]
    client.chat.completions.create.return_value = mock_completion
    return client


@pytest.fixture
def mock_sample_products():
    """Create sample products for testing."""
    return [
        {
            "id": "prod1",
            "title": "Casual Cotton Shirt",
            "price": 79.99,
            "category": "tops",
            "embedding": [0.1] * 1536,
        },
        {
            "id": "prod2",
            "title": "Relaxed Linen Top",
            "price": 89.99,
            "category": "tops",
            "embedding": [0.2] * 1536,
        },
        {
            "id": "prod3",
            "title": "Comfortable Weekend Tee",
            "price": 49.99,
            "category": "tops",
            "embedding": [0.15] * 1536,
        },
    ]


# =============================================================================
# Integration with Pillar 1 (Personalization) Tests
# =============================================================================

class TestPillar1Integration:
    """Test integration with Pillar 1 Personalization module."""

    @pytest.mark.asyncio
    async def test_loads_user_data_from_pillar1(self, mock_openai_client):
        """Test that orchestrator loads user data via Pillar 1."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        # Mock Pillar 1 to return user data
        mock_raw_data = MagicMock()
        mock_raw_data.user_id = "test-user"
        mock_raw_data.body_type = "rectangle"
        mock_raw_data.coloring = "warm"
        mock_raw_data.onboarding_profile = None

        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=mock_raw_data)
        nav_intel.pillar1.compute_user_state = MagicMock(return_value=MagicMock(
            active_context=StyleContext.CASUAL,
            detected_contexts=[StyleContext.CASUAL],
            active_position=MagicMock(
                position=StyleCoordinate(embedding=zero_vector(1536)),
                trajectory=None,
            ),
            nav_params=MagicMock(
                exploration_appetite=0.3,
                step_size_multiplier=1.0,
            ),
            behavioral_patterns=None,
            spending_patterns=None,
        ))

        result = await nav_intel.generate_navigation_context("test-user", "casual shirt")

        nav_intel.pillar1.load_raw_user_data.assert_called_once_with("test-user")
        assert result is not None

    @pytest.mark.asyncio
    async def test_cold_start_when_no_pillar1_data(self, mock_openai_client):
        """Test cold start path when Pillar 1 returns no data."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=None)
        nav_intel.pillar1.compute_user_state = MagicMock()  # Make it a mock

        result = await nav_intel.generate_navigation_context("new-user", "casual shirt")

        assert result is not None
        assert result.query == "casual shirt"
        # Cold start should not call compute_user_state
        nav_intel.pillar1.compute_user_state.assert_not_called()


# =============================================================================
# Integration with Pillar 2 (Stylist Knowledge) Tests
# =============================================================================

class TestPillar2Integration:
    """Test integration with Pillar 2 Stylist Knowledge module."""

    @pytest.mark.asyncio
    async def test_retrieves_styling_rules(self, mock_openai_client):
        """Test that orchestrator retrieves styling rules from Pillar 2."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        # Setup mocks
        mock_raw_data = MagicMock()
        mock_raw_data.body_type = "rectangle"
        mock_raw_data.onboarding_profile = None

        mock_computed_state = MagicMock()
        mock_computed_state.active_context = StyleContext.CASUAL
        mock_computed_state.detected_contexts = [StyleContext.CASUAL]
        mock_computed_state.active_position = MagicMock(
            position=StyleCoordinate(embedding=zero_vector(1536)),
            trajectory=None,
        )
        mock_computed_state.nav_params = MagicMock(exploration_appetite=0.3, step_size_multiplier=1.0)
        mock_computed_state.behavioral_patterns = None
        mock_computed_state.spending_patterns = None

        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=mock_raw_data)
        nav_intel.pillar1.compute_user_state = MagicMock(return_value=mock_computed_state)

        # Mock Pillar 2 methods
        nav_intel.pillar2.query_styling_rules = AsyncMock(return_value=[])
        nav_intel.pillar2.get_body_type_rules = MagicMock(return_value=[])
        nav_intel.pillar2.get_occasion_rules = MagicMock(return_value=[])
        nav_intel.pillar2.retrieve_multiple_perspectives = AsyncMock(return_value=MagicMock(
            get_summary=MagicMock(return_value=""),
        ))

        result = await nav_intel.generate_navigation_context("user123", "casual shirt", "weekend")

        # Verify Pillar 2 was consulted
        nav_intel.pillar2.query_styling_rules.assert_called_once()
        assert result is not None


# =============================================================================
# Integration with Synthesis LLM Tests
# =============================================================================

class TestSynthesisLLMIntegration:
    """Test integration with Synthesis LLM."""

    @pytest.mark.asyncio
    async def test_synthesis_produces_descriptors(self, mock_openai_client):
        """Test that synthesis LLM produces style descriptors."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        # Setup mocks
        mock_raw_data = MagicMock()
        mock_raw_data.body_type = "rectangle"
        mock_raw_data.coloring = "warm"
        mock_raw_data.onboarding_profile = None

        mock_computed_state = MagicMock()
        mock_computed_state.active_context = StyleContext.CASUAL
        mock_computed_state.detected_contexts = [StyleContext.CASUAL]
        mock_computed_state.active_position = MagicMock(
            position=StyleCoordinate(embedding=zero_vector(1536)),
            trajectory=None,
        )
        mock_computed_state.nav_params = MagicMock(exploration_appetite=0.3, step_size_multiplier=1.0)
        mock_computed_state.behavioral_patterns = None
        mock_computed_state.spending_patterns = None

        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=mock_raw_data)
        nav_intel.pillar1.compute_user_state = MagicMock(return_value=mock_computed_state)
        nav_intel.pillar2.query_styling_rules = AsyncMock(return_value=[])
        nav_intel.pillar2.get_body_type_rules = MagicMock(return_value=[])
        nav_intel.pillar2.get_occasion_rules = MagicMock(return_value=[])
        nav_intel.pillar2.retrieve_multiple_perspectives = AsyncMock(return_value=MagicMock(
            get_summary=MagicMock(return_value=""),
        ))

        result = await nav_intel.generate_navigation_context("user123", "casual shirt")

        assert result.synthesis is not None
        assert len(result.synthesis.style_descriptors) > 0

    @pytest.mark.asyncio
    async def test_synthesis_fallback_on_error(self, mock_openai_client):
        """Test that synthesis uses fallback on LLM error."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        # Setup mocks
        mock_raw_data = MagicMock()
        mock_raw_data.body_type = None
        mock_raw_data.onboarding_profile = None

        mock_computed_state = MagicMock()
        mock_computed_state.active_context = StyleContext.CASUAL
        mock_computed_state.detected_contexts = [StyleContext.CASUAL]
        mock_computed_state.active_position = MagicMock(
            position=StyleCoordinate(embedding=zero_vector(1536)),
            trajectory=None,
        )
        mock_computed_state.nav_params = MagicMock(exploration_appetite=0.3, step_size_multiplier=1.0)
        mock_computed_state.behavioral_patterns = None
        mock_computed_state.spending_patterns = None

        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=mock_raw_data)
        nav_intel.pillar1.compute_user_state = MagicMock(return_value=mock_computed_state)
        nav_intel.pillar2.query_styling_rules = AsyncMock(return_value=[])
        nav_intel.pillar2.get_body_type_rules = MagicMock(return_value=[])
        nav_intel.pillar2.get_occasion_rules = MagicMock(return_value=[])
        nav_intel.pillar2.retrieve_multiple_perspectives = AsyncMock(return_value=None)

        # Force synthesis to fail
        nav_intel.synthesis_llm.synthesize_navigation = MagicMock(side_effect=Exception("LLM Error"))

        result = await nav_intel.generate_navigation_context("user123", "casual shirt")

        assert result.synthesis is not None
        assert "fallback" in result.synthesis.relevant_context[0]


# =============================================================================
# Integration with Judge Tests
# =============================================================================

class TestJudgeIntegration:
    """Test integration with Judge (ARIEvaluator, MMR, Outlier Injector)."""

    @pytest.mark.asyncio
    async def test_orchestrator_uses_evaluator(self, mock_openai_client, mock_sample_products):
        """Test that orchestrator uses ARIEvaluator when provided."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.generate_navigation_context = AsyncMock(return_value=MagicMock(
            current_position=StyleCoordinate(embedding=zero_vector(1536)),
            path=MagicMock(
                outlier_percentage=0.1,
                diversity_requirement=0.4,
            ),
            computed_state=MagicMock(
                nav_params=MagicMock(result_set_size=20),
            ),
            synthesis=MagicMock(style_descriptors=["casual"]),
            raw_user_data=None,
        ))

        # Mock evaluator
        mock_evaluator = MagicMock()
        mock_scored_products = [
            MagicMock(product=p, relevance_score=0.8, embedding=[0.1]*1536)
            for p in mock_sample_products
        ]
        mock_evaluator.score_products.return_value = mock_scored_products

        orchestrator = NavigationOrchestrator(
            navigation_intelligence=nav_intel,
            evaluator=mock_evaluator,
        )

        # Patch mmr_select where it's imported in the method
        with patch('ari_v3.judge.mmr_select', return_value=mock_scored_products[:2]):
            with patch('ari_v3.judge.inject_outliers', return_value=(mock_scored_products[:2], [])):
                result = await orchestrator.execute_search(
                    user_id="user123",
                    query="casual shirt",
                    products=mock_sample_products,
                )

        mock_evaluator.score_products.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_without_evaluator(self, mock_openai_client, mock_sample_products):
        """Test that orchestrator works without evaluator (returns raw products)."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.generate_navigation_context = AsyncMock(return_value=MagicMock(
            path=MagicMock(outlier_percentage=0.0),
            computed_state=None,
            synthesis=MagicMock(style_descriptors=["casual"]),
            raw_user_data=None,
        ))

        orchestrator = NavigationOrchestrator(
            navigation_intelligence=nav_intel,
            evaluator=None,  # No evaluator
        )

        result = await orchestrator.execute_search(
            user_id="user123",
            query="casual shirt",
            products=mock_sample_products,
        )

        # Should return raw products when no evaluator
        assert len(result.products) == len(mock_sample_products)


# =============================================================================
# Integration with Narrative LLM Tests
# =============================================================================

class TestNarrativeIntegration:
    """Test integration with Narrative LLM."""

    @pytest.mark.asyncio
    async def test_orchestrator_generates_narrative(self, mock_openai_client, mock_sample_products):
        """Test that orchestrator generates narrative when NarrativeLLM provided."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.generate_navigation_context = AsyncMock(return_value=MagicMock(
            path=MagicMock(outlier_percentage=0.0),
            computed_state=None,
            synthesis=MagicMock(style_descriptors=["casual"]),
            raw_user_data=MagicMock(onboarding_profile=None),
        ))

        # Mock narrative LLM with async version
        mock_narrative_llm = MagicMock()
        mock_narrative_response = MagicMock(
            intro="Here are your picks!",
            product_explanations=[],
        )
        mock_narrative_llm.generate_narrative_async = AsyncMock(return_value=mock_narrative_response)
        mock_narrative_llm.generate_narrative = MagicMock(return_value=mock_narrative_response)

        orchestrator = NavigationOrchestrator(
            navigation_intelligence=nav_intel,
            narrative_llm=mock_narrative_llm,
        )

        result = await orchestrator.execute_search(
            user_id="user123",
            query="casual shirt",
            products=mock_sample_products,
        )

        # Should use async version when available
        mock_narrative_llm.generate_narrative_async.assert_called_once()
        assert result.narrative is not None

    @pytest.mark.asyncio
    async def test_orchestrator_handles_narrative_failure(self, mock_openai_client, mock_sample_products):
        """Test that orchestrator handles narrative generation failure gracefully."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.generate_navigation_context = AsyncMock(return_value=MagicMock(
            path=MagicMock(outlier_percentage=0.0),
            computed_state=None,
            synthesis=MagicMock(style_descriptors=["casual"]),
            raw_user_data=MagicMock(onboarding_profile=None),
        ))

        # Mock narrative LLM to raise error (async version since that's preferred)
        mock_narrative_llm = MagicMock()
        mock_narrative_llm.generate_narrative_async = AsyncMock(side_effect=Exception("Narrative Error"))
        mock_narrative_llm.generate_narrative = MagicMock(side_effect=Exception("Narrative Error"))

        orchestrator = NavigationOrchestrator(
            navigation_intelligence=nav_intel,
            narrative_llm=mock_narrative_llm,
        )

        result = await orchestrator.execute_search(
            user_id="user123",
            query="casual shirt",
            products=mock_sample_products,
        )

        # Should complete without narrative
        assert result.narrative is None
        assert len(result.products) == len(mock_sample_products)


# =============================================================================
# End-to-End Flow Tests
# =============================================================================

class TestEndToEndFlow:
    """Test end-to-end orchestration flow."""

    @pytest.mark.asyncio
    async def test_complete_search_flow(self, mock_openai_client, mock_sample_products):
        """Test complete search flow from query to results."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        # Setup complete mock chain
        mock_raw_data = MagicMock()
        mock_raw_data.body_type = "rectangle"
        mock_raw_data.onboarding_profile = MagicMock(root_values=MagicMock(primary="self-expression"))

        mock_position = StyleCoordinate(embedding=zero_vector(1536))

        mock_computed_state = MagicMock()
        mock_computed_state.active_context = StyleContext.CASUAL
        mock_computed_state.detected_contexts = [StyleContext.CASUAL]
        mock_computed_state.active_position = MagicMock(
            position=mock_position,
            trajectory=None,
        )
        mock_computed_state.nav_params = MagicMock(
            exploration_appetite=0.3,
            step_size_multiplier=1.0,
            result_set_size=20,
        )
        mock_computed_state.behavioral_patterns = None
        mock_computed_state.spending_patterns = None

        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=mock_raw_data)
        nav_intel.pillar1.compute_user_state = MagicMock(return_value=mock_computed_state)
        nav_intel.pillar2.query_styling_rules = AsyncMock(return_value=[])
        nav_intel.pillar2.get_body_type_rules = MagicMock(return_value=[])
        nav_intel.pillar2.get_occasion_rules = MagicMock(return_value=[])
        nav_intel.pillar2.retrieve_multiple_perspectives = AsyncMock(return_value=None)

        # Create orchestrator without evaluator for simpler test
        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)

        result = await orchestrator.execute_search(
            user_id="user123",
            query="casual shirt",
            occasion="weekend",
            products=mock_sample_products,
        )

        assert isinstance(result, SearchResult)
        assert result.session_id is not None
        assert "query" in result.metadata
        assert result.metadata["query"] == "casual shirt"

    @pytest.mark.asyncio
    async def test_cold_start_search_flow(self, mock_openai_client, mock_sample_products):
        """Test search flow for cold start user."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=None)

        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)

        result = await orchestrator.execute_search(
            user_id="new-user",
            query="formal suit",
            products=mock_sample_products,
        )

        assert isinstance(result, SearchResult)
        assert result.session_id is not None


# =============================================================================
# Factory Function Integration Tests
# =============================================================================

class TestFactoryFunctions:
    """Test factory function integration."""

    def test_create_orchestrator_with_all_dependencies(self):
        """Test creating orchestrator with all dependencies."""
        with patch('ari_v3.orchestrator.navigation_intelligence.OpenAI'):
            with patch('ari_v3.judge.ARIEvaluator'):
                with patch('ari_v3.narrative.NarrativeLLM'):
                    orchestrator = create_navigation_orchestrator(openai_api_key="test-key")

                    assert orchestrator is not None
                    assert orchestrator.navigation_intelligence is not None
                    assert orchestrator.evaluator is not None
                    assert orchestrator.narrative_llm is not None


# =============================================================================
# Metadata Generation Tests
# =============================================================================

class TestMetadataGeneration:
    """Test metadata generation in search results."""

    @pytest.mark.asyncio
    async def test_metadata_includes_synthesis_info(self, mock_openai_client, mock_sample_products):
        """Test that metadata includes synthesis information."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        mock_synthesis = SynthesisOutput(
            style_descriptors=["casual", "relaxed"],
            exemplar_search_terms=["casual shirt"],
            understood_intent="Looking for casual wear",
            budget_interpretation=BudgetInterpretation(min=50, max=200),
            formality_level=0.3,
            relevant_context=["casual"],
        )

        nav_intel.generate_navigation_context = AsyncMock(return_value=MagicMock(
            query="casual shirt",
            occasion="weekend",
            path=MagicMock(outlier_percentage=0.0),
            computed_state=MagicMock(
                active_context=StyleContext.CASUAL,
                detected_contexts=[StyleContext.CASUAL],
                nav_params=MagicMock(
                    exploration_appetite=0.3,
                    step_size_multiplier=1.0,
                    brand_affinity_weight=0.5,
                    result_set_size=20,
                    diversity_requirement=0.4,
                ),
            ),
            synthesis=mock_synthesis,
            raw_user_data=None,
        ))

        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)

        result = await orchestrator.execute_search(
            user_id="user123",
            query="casual shirt",
            products=mock_sample_products,
        )

        assert "style_descriptors" in result.metadata
        assert "understood_intent" in result.metadata
        assert "formality_level" in result.metadata
        assert result.metadata["understood_intent"] == "Looking for casual wear"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
