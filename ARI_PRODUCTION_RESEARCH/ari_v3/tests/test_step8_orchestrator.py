"""
Unit tests for ARI V3 Step 8: Navigation Intelligence Orchestrator

Tests for NavigationIntelligence and NavigationOrchestrator classes.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ari_v3.orchestrator.navigation_intelligence import (
    NavigationIntelligence,
    NavigationOrchestrator,
    SearchResult,
    create_navigation_intelligence,
)
from datetime import datetime
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
    BehavioralProfile,
    DriftAnalysis,
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
    """Create mock OpenAI client."""
    client = MagicMock()
    # Mock embeddings
    mock_embedding_response = MagicMock()
    mock_embedding_response.data = [MagicMock(embedding=[0.1] * 1536)]
    client.embeddings.create.return_value = mock_embedding_response
    # Mock completions
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content='{"style_descriptors": ["casual"], "exemplar_search_terms": ["casual shirt"], "understood_intent": "Looking for casual wear", "budget_interpretation": {"min": 50, "max": 200}, "formality_level": 0.3, "relevant_context": ["casual style"]}'))
    ]
    client.chat.completions.create.return_value = mock_completion
    return client


@pytest.fixture
def sample_raw_user_data():
    """Create sample raw user data."""
    return RawUserData(
        user_id="test-user-123",
        body_type="rectangle",
        coloring="warm",
        onboarding_profile=None,
        raw_onboarding_conversations=[],
        navigation_parameters=None,
        body_photo_url=None,
        face_photo_url=None,
        social_embeddings=None,
        interactions=[],
        conversation_history=[],
        created_at=datetime.now(),
        last_active=datetime.now(),
        onboarding_completed=True,
    )


@pytest.fixture
def sample_computed_state():
    """Create sample computed user state using mocks for complex nested objects."""
    # Use MagicMock to simplify complex nested dataclasses
    position = StyleCoordinate(
        embedding=zero_vector(1536),
        visual_embedding=zero_vector(512),
    )

    # Mock active position
    active_position = MagicMock()
    active_position.position = position
    active_position.trajectory = MagicMock()
    active_position.trajectory.direction = [0.1] * 1536
    active_position.trajectory.velocity = 0.05

    # Mock nav params
    nav_params = MagicMock()
    nav_params.exploration_appetite = 0.3
    nav_params.step_size_multiplier = 1.0
    nav_params.brand_affinity_weight = 0.5
    nav_params.result_set_size = 20
    nav_params.diversity_requirement = 0.4

    # Mock computed state
    computed_state = MagicMock(spec=ComputedUserState)
    computed_state.active_context = StyleContext.CASUAL
    computed_state.detected_contexts = [StyleContext.CASUAL]
    computed_state.active_position = active_position
    computed_state.nav_params = nav_params
    computed_state.behavioral_patterns = None
    computed_state.spending_patterns = None

    return computed_state


@pytest.fixture
def sample_synthesis():
    """Create sample synthesis output."""
    return SynthesisOutput(
        style_descriptors=["casual", "comfortable", "relaxed"],
        exemplar_search_terms=["casual shirt", "relaxed fit"],
        understood_intent="Looking for casual everyday wear",
        budget_interpretation=BudgetInterpretation(min=50, max=200),
        formality_level=0.3,
        relevant_context=["casual style", "comfort-focused"],
    )


@pytest.fixture
def sample_nav_context(sample_computed_state, sample_synthesis, sample_raw_user_data):
    """Create sample navigation context."""
    position = StyleCoordinate(
        embedding=zero_vector(1536),
        visual_embedding=zero_vector(512),
    )
    # Use MagicMock for NavigationPath due to complex fields
    path = MagicMock(spec=NavigationPath)
    path.current_position = position
    path.destination = position
    path.max_step_size = 0.2
    path.outlier_percentage = 0.1
    path.diversity_requirement = 0.4
    path.smoothness_score = 0.8
    path.coherence_score = 0.8

    return NavigationContext(
        current_position=position,
        trajectory=None,
        destination=position,
        path=path,
        query="casual shirt",
        occasion="weekend",
        computed_state=sample_computed_state,
        synthesis=sample_synthesis,
        raw_user_data=sample_raw_user_data,
    )


# =============================================================================
# NavigationIntelligence Tests
# =============================================================================

class TestNavigationIntelligenceInit:
    """Test NavigationIntelligence initialization."""

    def test_init_with_defaults(self):
        """Test init with default values."""
        with patch('ari_v3.orchestrator.navigation_intelligence.OpenAI') as mock_openai:
            nav_intel = NavigationIntelligence()
            assert nav_intel.pillar1 is not None
            assert nav_intel.pillar2 is not None
            assert nav_intel.synthesis_llm is not None

    def test_init_with_custom_client(self, mock_openai_client):
        """Test init with custom OpenAI client."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel.openai_client == mock_openai_client

    def test_init_with_neo4j_driver(self, mock_openai_client):
        """Test init with Neo4j driver."""
        mock_driver = MagicMock()
        nav_intel = NavigationIntelligence(
            neo4j_driver=mock_driver,
            openai_client=mock_openai_client,
        )
        assert nav_intel.neo4j_driver == mock_driver


class TestNavigationIntelligenceInputValidation:
    """Test input validation."""

    @pytest.mark.asyncio
    async def test_empty_user_id_raises(self, mock_openai_client):
        """Test that empty user_id raises ValueError."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            await nav_intel.generate_navigation_context("", "query")

    @pytest.mark.asyncio
    async def test_empty_query_raises(self, mock_openai_client):
        """Test that empty query raises ValueError."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        with pytest.raises(ValueError, match="query cannot be empty"):
            await nav_intel.generate_navigation_context("user123", "")

    @pytest.mark.asyncio
    async def test_none_user_id_raises(self, mock_openai_client):
        """Test that None user_id raises ValueError."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            await nav_intel.generate_navigation_context(None, "query")


class TestNavigationIntelligenceColdStart:
    """Test cold start functionality."""

    @pytest.mark.asyncio
    async def test_cold_start_when_no_user_data(self, mock_openai_client):
        """Test cold start context is returned when no user data."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=None)

        result = await nav_intel.generate_navigation_context("new-user", "casual shirt")

        assert result is not None
        assert result.query == "casual shirt"
        # Cold start should have default navigation parameters
        nav_intel.pillar1.load_raw_user_data.assert_called_once_with("new-user")


class TestNavigationIntelligenceInferCategory:
    """Test category inference."""

    def test_infer_tops_category(self, mock_openai_client):
        """Test inference of tops category."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel._infer_category("casual shirt") == "tops"
        assert nav_intel._infer_category("blue blouse") == "tops"
        assert nav_intel._infer_category("cozy sweater") == "tops"

    def test_infer_bottoms_category(self, mock_openai_client):
        """Test inference of bottoms category."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel._infer_category("blue jeans") == "bottoms"
        assert nav_intel._infer_category("tailored pants") == "bottoms"

    def test_infer_dresses_category(self, mock_openai_client):
        """Test inference of dresses category."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel._infer_category("summer dress") == "dresses"
        assert nav_intel._infer_category("evening gown") == "dresses"

    def test_infer_outerwear_category(self, mock_openai_client):
        """Test inference of outerwear category."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel._infer_category("leather jacket") == "outerwear"
        assert nav_intel._infer_category("winter coat") == "outerwear"

    def test_infer_shoes_category(self, mock_openai_client):
        """Test inference of shoes category."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel._infer_category("running shoes") == "shoes"
        assert nav_intel._infer_category("ankle boots") == "shoes"

    def test_infer_accessories_category(self, mock_openai_client):
        """Test inference of accessories category."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel._infer_category("leather bag") == "accessories"
        assert nav_intel._infer_category("gold watch") == "accessories"

    def test_infer_no_category(self, mock_openai_client):
        """Test no category inference for generic query."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        assert nav_intel._infer_category("something stylish") is None
        assert nav_intel._infer_category("fashion items") is None


class TestNavigationIntelligenceSyncWrapper:
    """Test synchronous wrapper."""

    def test_sync_wrapper_not_in_event_loop(self, mock_openai_client):
        """Test sync wrapper works outside event loop."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=None)

        # Should work outside event loop
        result = nav_intel.generate_navigation_context_sync("user123", "casual shirt")
        assert result is not None


# =============================================================================
# SearchResult Tests
# =============================================================================

class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating SearchResult."""
        result = SearchResult(
            products=[{"id": 1}, {"id": 2}],
            session_id="test-session",
        )
        assert len(result.products) == 2
        assert result.session_id == "test-session"
        assert result.narrative is None
        assert result.metadata == {}

    def test_search_result_with_all_fields(self, sample_nav_context):
        """Test SearchResult with all fields."""
        result = SearchResult(
            products=[{"id": 1}],
            narrative={"intro": "Great picks!"},
            path=sample_nav_context.path,
            session_id="full-session",
            metadata={"key": "value"},
        )
        assert result.narrative is not None
        assert result.path is not None
        assert result.metadata["key"] == "value"


# =============================================================================
# NavigationOrchestrator Tests
# =============================================================================

class TestNavigationOrchestratorInit:
    """Test NavigationOrchestrator initialization."""

    def test_init_with_nav_intelligence(self, mock_openai_client):
        """Test init with NavigationIntelligence."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)
        assert orchestrator.navigation_intelligence == nav_intel
        assert orchestrator.evaluator is None
        assert orchestrator.narrative_llm is None

    def test_init_with_all_dependencies(self, mock_openai_client):
        """Test init with all dependencies."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        mock_evaluator = MagicMock()
        mock_narrative = MagicMock()

        orchestrator = NavigationOrchestrator(
            navigation_intelligence=nav_intel,
            evaluator=mock_evaluator,
            narrative_llm=mock_narrative,
        )
        assert orchestrator.evaluator == mock_evaluator
        assert orchestrator.narrative_llm == mock_narrative


class TestNavigationOrchestratorExecuteSearch:
    """Test execute_search method."""

    @pytest.mark.asyncio
    async def test_execute_search_returns_search_result(self, mock_openai_client, sample_nav_context):
        """Test execute_search returns SearchResult."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.generate_navigation_context = AsyncMock(return_value=sample_nav_context)

        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)
        result = await orchestrator.execute_search(
            user_id="user123",
            query="casual shirt",
            products=[{"id": 1, "title": "Shirt"}],
        )

        assert isinstance(result, SearchResult)
        assert len(result.products) == 1
        assert result.session_id is not None

    @pytest.mark.asyncio
    async def test_execute_search_with_no_products(self, mock_openai_client, sample_nav_context):
        """Test execute_search with no products returns empty list."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.generate_navigation_context = AsyncMock(return_value=sample_nav_context)

        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)
        result = await orchestrator.execute_search(
            user_id="user123",
            query="casual shirt",
        )

        assert result.products == []

    @pytest.mark.asyncio
    async def test_execute_search_with_occasion(self, mock_openai_client, sample_nav_context):
        """Test execute_search with occasion parameter."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.generate_navigation_context = AsyncMock(return_value=sample_nav_context)

        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)
        result = await orchestrator.execute_search(
            user_id="user123",
            query="dress",
            occasion="wedding",
        )

        nav_intel.generate_navigation_context.assert_called_with(
            user_id="user123",
            query="dress",
            occasion="wedding",
        )


class TestNavigationOrchestratorBuildMetadata:
    """Test _build_metadata method."""

    def test_build_metadata_basic(self, mock_openai_client, sample_nav_context):
        """Test building basic metadata."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)

        metadata = orchestrator._build_metadata(sample_nav_context)

        assert metadata["query"] == "casual shirt"
        assert metadata["occasion"] == "weekend"

    def test_build_metadata_with_synthesis(self, mock_openai_client, sample_nav_context):
        """Test metadata includes synthesis info."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)

        metadata = orchestrator._build_metadata(sample_nav_context)

        assert "style_descriptors" in metadata
        assert metadata["understood_intent"] == "Looking for casual everyday wear"
        assert metadata["formality_level"] == 0.3

    def test_build_metadata_with_nav_params(self, mock_openai_client, sample_nav_context):
        """Test metadata includes nav params."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        orchestrator = NavigationOrchestrator(navigation_intelligence=nav_intel)

        metadata = orchestrator._build_metadata(sample_nav_context)

        assert "nav_params" in metadata
        assert metadata["nav_params"]["exploration_appetite"] == 0.3
        assert metadata["nav_params"]["result_set_size"] == 20


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_navigation_intelligence_with_api_key(self):
        """Test creating NavigationIntelligence with API key."""
        with patch('ari_v3.orchestrator.navigation_intelligence.OpenAI') as mock_openai:
            nav_intel = create_navigation_intelligence(openai_api_key="test-key")
            mock_openai.assert_called_with(api_key="test-key")
            assert nav_intel is not None

    def test_create_navigation_intelligence_with_env_var(self):
        """Test creating NavigationIntelligence with env var."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'env-key'}):
            with patch('ari_v3.orchestrator.navigation_intelligence.OpenAI') as mock_openai:
                nav_intel = create_navigation_intelligence()
                assert nav_intel is not None

    def test_create_navigation_intelligence_with_drivers(self):
        """Test creating NavigationIntelligence with database drivers."""
        mock_neo4j = MagicMock()
        mock_qdrant = MagicMock()

        with patch('ari_v3.orchestrator.navigation_intelligence.OpenAI'):
            nav_intel = create_navigation_intelligence(
                neo4j_driver=mock_neo4j,
                qdrant_client=mock_qdrant,
            )
            assert nav_intel.neo4j_driver == mock_neo4j
            assert nav_intel.qdrant_client == mock_qdrant


# =============================================================================
# Behavioral Pattern Tests
# =============================================================================

class TestBehavioralPatterns:
    """Test behavioral pattern extraction."""

    @pytest.mark.asyncio
    async def test_get_behavioral_patterns_with_state(self, mock_openai_client, sample_computed_state):
        """Test extracting behavioral patterns from computed state."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        profile, drift = await nav_intel._get_behavioral_patterns("user123", sample_computed_state)

        assert drift is not None
        assert drift.has_significant_drift is False
        assert drift.drift_magnitude == 0.0

    @pytest.mark.asyncio
    async def test_get_behavioral_patterns_with_none_state(self, mock_openai_client):
        """Test behavioral patterns with None state."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)

        profile, drift = await nav_intel._get_behavioral_patterns("user123", None)

        assert profile is None
        assert drift is not None


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_synthesis_failure_uses_fallback(self, mock_openai_client, sample_raw_user_data, sample_computed_state):
        """Test that synthesis failure uses fallback."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=sample_raw_user_data)
        nav_intel.pillar1.compute_user_state = MagicMock(return_value=sample_computed_state)
        nav_intel.synthesis_llm.synthesize_navigation = MagicMock(side_effect=Exception("LLM Error"))

        # Should not raise, should use fallback
        result = await nav_intel.generate_navigation_context("user123", "casual shirt")

        assert result is not None
        assert "fallback" in result.synthesis.relevant_context[0]

    @pytest.mark.asyncio
    async def test_destination_computation_failure_uses_fallback(self, mock_openai_client, sample_raw_user_data, sample_computed_state, sample_synthesis):
        """Test that destination computation failure uses fallback."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=sample_raw_user_data)
        nav_intel.pillar1.compute_user_state = MagicMock(return_value=sample_computed_state)
        nav_intel.synthesis_llm.synthesize_navigation = MagicMock(return_value=sample_synthesis)
        nav_intel.synthesis_llm.compute_destination_from_synthesis = MagicMock(side_effect=Exception("Qdrant Error"))

        result = await nav_intel.generate_navigation_context("user123", "casual shirt")

        assert result is not None
        # Destination should be zero vector fallback
        assert result.destination is not None

    @pytest.mark.asyncio
    async def test_no_active_position_uses_destination(self, mock_openai_client, sample_raw_user_data, sample_synthesis):
        """Test that missing active_position uses destination as current."""
        nav_intel = NavigationIntelligence(openai_client=mock_openai_client)
        nav_intel.pillar1.load_raw_user_data = MagicMock(return_value=sample_raw_user_data)

        # Create computed state without active_position using mocks
        mock_nav_params = MagicMock()
        mock_nav_params.exploration_appetite = 0.3
        mock_nav_params.step_size_multiplier = 1.0

        computed_state = MagicMock(spec=ComputedUserState)
        computed_state.active_context = StyleContext.CASUAL
        computed_state.detected_contexts = []
        computed_state.active_position = None
        computed_state.nav_params = mock_nav_params
        computed_state.behavioral_patterns = None
        computed_state.spending_patterns = None

        nav_intel.pillar1.compute_user_state = MagicMock(return_value=computed_state)
        nav_intel.synthesis_llm.synthesize_navigation = MagicMock(return_value=sample_synthesis)

        result = await nav_intel.generate_navigation_context("user123", "shirt")

        assert result is not None
        # Current position should equal destination when active_position is None
        assert result.current_position == result.destination


# =============================================================================
# Module Import Tests
# =============================================================================

class TestModuleImports:
    """Test module imports and exports."""

    def test_import_from_orchestrator_package(self):
        """Test imports from orchestrator package."""
        from ari_v3.orchestrator import (
            NavigationIntelligence,
            NavigationOrchestrator,
            SearchResult,
            create_navigation_intelligence,
            create_navigation_orchestrator,
        )
        assert NavigationIntelligence is not None
        assert NavigationOrchestrator is not None
        assert SearchResult is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
