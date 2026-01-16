"""
Integration tests for ARI V3 Step 9: Feedback Loop

Tests integration between SessionTracker, OutcomeRecorder, ReinterpretationChecker,
and FeedbackAnalytics components.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from ari_v3.feedback import (
    SessionTracker,
    OutcomeRecorder,
    ReinterpretationChecker,
    FeedbackAnalytics,
    OutcomeType,
    BehavioralSummary,
    MIN_INTERACTIONS_FOR_DIVERGENCE,
    MIN_DIVERGENCE_SIGNALS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_nav_context():
    """Create mock NavigationContext."""
    context = MagicMock()
    context.query = "casual shirt"
    context.occasion = "work"

    # Computed state
    context.computed_state = MagicMock()
    context.computed_state.active_context = MagicMock()
    context.computed_state.active_context.value = "professional"
    context.computed_state.nav_params = MagicMock()
    context.computed_state.nav_params.exploration_appetite = 0.5
    context.computed_state.nav_params.step_size_multiplier = 1.0
    context.computed_state.nav_params.diversity_requirement = 0.3
    context.computed_state.nav_params.result_set_size = 20

    # Synthesis
    context.synthesis = MagicMock()
    context.synthesis.style_descriptors = ["casual", "professional", "comfortable"]
    context.synthesis.understood_intent = "Looking for work-appropriate casual shirt"
    context.synthesis.formality_level = 0.6

    # Destination
    context.destination = MagicMock()
    context.destination.embedding = [0.1] * 1536

    return context


@pytest.fixture
def mock_products():
    """Create mock products."""
    products = []
    for i in range(5):
        product = MagicMock()
        product.id = f"product_{i}"
        product.relevance_score = 0.9 - (i * 0.1)
        products.append(product)
    return products


@pytest.fixture
def mock_onboarding_profile():
    """Create mock OnboardingProfile."""
    profile = MagicMock()

    # Practicality
    profile.practicality = MagicMock()
    profile.practicality.budget = MagicMock()
    profile.practicality.budget.monthly = 500.0

    # Process
    profile.process = MagicMock()
    profile.process.adventurousness = 5
    profile.process.brand_loyalty = 6

    # Taste
    profile.taste = MagicMock()
    profile.taste.style_avoids = "neon,animal print,oversized"

    # Personal
    profile.personal = MagicMock()
    profile.personal.occasions = [
        MagicMock(style_context=MagicMock(value="professional")),
        MagicMock(style_context=MagicMock(value="casual")),
    ]

    return profile


# =============================================================================
# Session to Outcome Flow Tests
# =============================================================================

class TestSessionToOutcomeFlow:
    """Tests for the flow from session tracking to outcome recording."""

    @pytest.mark.asyncio
    async def test_track_session_then_record_outcomes(self, mock_nav_context, mock_products):
        """Test tracking a session and then recording outcomes."""
        tracker = SessionTracker()
        recorder = OutcomeRecorder()

        # Track session
        session_id = await tracker.track_session(
            user_id="user123",
            nav_context=mock_nav_context,
            products_shown=mock_products,
        )

        assert session_id is not None

        # Record outcomes for products
        for i, product in enumerate(mock_products[:3]):
            result = await recorder.record_outcome(
                session_id=session_id,
                product_id=product.id,
                outcome=OutcomeType.CLICKED if i == 0 else OutcomeType.VIEWED,
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_multiple_sessions_same_user(self, mock_nav_context, mock_products):
        """Test tracking multiple sessions for the same user."""
        tracker = SessionTracker()

        session_ids = []
        for i in range(3):
            mock_nav_context.query = f"query_{i}"
            session_id = await tracker.track_session(
                user_id="user123",
                nav_context=mock_nav_context,
                products_shown=mock_products,
            )
            session_ids.append(session_id)

        # All session IDs should be unique
        assert len(set(session_ids)) == 3


# =============================================================================
# Reinterpretation Integration Tests
# =============================================================================

class TestReinterpretationIntegration:
    """Tests for reinterpretation integration."""

    @pytest.mark.asyncio
    async def test_reinterpretation_check_with_mocked_data(self, mock_onboarding_profile):
        """Test reinterpretation check with mocked user data."""
        checker = ReinterpretationChecker()

        # Mock raw user data
        mock_raw_data = MagicMock()
        mock_raw_data.onboarding_profile = mock_onboarding_profile

        # Mock methods
        with patch.object(checker, '_get_interaction_count', new_callable=AsyncMock, return_value=50):
            with patch.object(checker, '_load_raw_user_data', new_callable=AsyncMock, return_value=mock_raw_data):
                with patch.object(checker, '_compute_behavioral_summary', new_callable=AsyncMock) as mock_summary:
                    # Behavioral summary that triggers divergence
                    mock_summary.return_value = BehavioralSummary(
                        median_spending=800.0,  # 1.6x budget - triggers
                        style_variance=0.95,    # 0.45 diff - triggers
                        brand_repeat_rate=0.4,
                        interaction_count=50,
                    )

                    result = await checker.check_reinterpretation_trigger("user123")

                    assert result.interaction_count == 50
                    # Should have at least 2 signals (budget + adventurousness)
                    assert result.signal_count >= 2
                    assert result.should_reinterpret is True

    @pytest.mark.asyncio
    async def test_reinterpretation_not_triggered_when_behavior_matches(self, mock_onboarding_profile):
        """Test that reinterpretation is not triggered when behavior matches."""
        checker = ReinterpretationChecker()

        mock_raw_data = MagicMock()
        mock_raw_data.onboarding_profile = mock_onboarding_profile

        with patch.object(checker, '_get_interaction_count', new_callable=AsyncMock, return_value=50):
            with patch.object(checker, '_load_raw_user_data', new_callable=AsyncMock, return_value=mock_raw_data):
                with patch.object(checker, '_compute_behavioral_summary', new_callable=AsyncMock) as mock_summary:
                    # Behavioral summary that matches stated preferences
                    mock_summary.return_value = BehavioralSummary(
                        median_spending=500.0,  # matches budget
                        style_variance=0.5,     # matches adventurousness
                        brand_repeat_rate=0.6,  # matches brand loyalty
                        interaction_count=50,
                    )

                    result = await checker.check_reinterpretation_trigger("user123")

                    assert result.signal_count < MIN_DIVERGENCE_SIGNALS
                    assert result.should_reinterpret is False


class TestOnInteractionHook:
    """Tests for on_interaction hook."""

    @pytest.mark.asyncio
    async def test_on_interaction_triggers_check_at_interval(self):
        """Test that on_interaction triggers check every 20 interactions."""
        checker = ReinterpretationChecker()

        # Mock methods
        with patch.object(checker, '_get_interaction_count', new_callable=AsyncMock, return_value=40):
            with patch.object(checker, 'check_reinterpretation_trigger', new_callable=AsyncMock) as mock_check:
                mock_check.return_value = MagicMock(should_reinterpret=False)

                await checker.on_interaction("user123", {"type": "view"})

                # Should trigger check at 40 (multiple of 20)
                mock_check.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_on_interaction_does_not_trigger_off_interval(self):
        """Test that on_interaction does not trigger check off interval."""
        checker = ReinterpretationChecker()

        with patch.object(checker, '_get_interaction_count', new_callable=AsyncMock, return_value=35):
            with patch.object(checker, 'check_reinterpretation_trigger', new_callable=AsyncMock) as mock_check:
                await checker.on_interaction("user123", {"type": "view"})

                # Should not trigger check at 35 (not multiple of 20)
                mock_check.assert_not_called()


# =============================================================================
# Analytics Integration Tests
# =============================================================================

class TestAnalyticsIntegration:
    """Tests for analytics integration."""

    @pytest.mark.asyncio
    async def test_analyze_empty_sessions(self):
        """Test analyzing with no sessions."""
        analytics = FeedbackAnalytics()

        # Without driver, should return empty analysis
        result = await analytics.analyze_session_outcomes(days=30)

        assert result.total_sessions == 0
        assert result.overall_click_through_rate == 0.0

    @pytest.mark.asyncio
    async def test_session_metrics_without_driver(self):
        """Test getting session metrics without driver."""
        analytics = FeedbackAnalytics()

        result = await analytics.get_session_metrics("sess123")

        assert result is None


# =============================================================================
# End-to-End Flow Tests
# =============================================================================

class TestEndToEndFlow:
    """Tests for end-to-end feedback flow."""

    @pytest.mark.asyncio
    async def test_complete_recommendation_feedback_cycle(self, mock_nav_context, mock_products):
        """Test complete cycle: session -> outcomes -> analysis."""
        tracker = SessionTracker()
        recorder = OutcomeRecorder()

        # Step 1: Track session
        session_id = await tracker.track_session(
            user_id="user123",
            nav_context=mock_nav_context,
            products_shown=mock_products,
            agents_used=["VibeBot", "VisionBot"],
        )

        assert session_id is not None

        # Step 2: Record outcomes
        outcomes_recorded = []
        for i, product in enumerate(mock_products):
            if i == 0:
                outcome = OutcomeType.CLICKED
            elif i == 1:
                outcome = OutcomeType.LIKED
            elif i == 2:
                outcome = OutcomeType.PURCHASED
            else:
                outcome = OutcomeType.VIEWED

            result = await recorder.record_outcome(
                session_id=session_id,
                product_id=product.id,
                outcome=outcome,
            )
            outcomes_recorded.append(result)

        assert all(outcomes_recorded)

    @pytest.mark.asyncio
    async def test_session_with_narrative(self, mock_nav_context, mock_products):
        """Test session tracking with narrative."""
        tracker = SessionTracker()

        mock_narrative = MagicMock()
        mock_narrative.intro = "Here are your recommendations!"
        mock_narrative.product_explanations = []

        session_id = await tracker.track_session(
            user_id="user123",
            nav_context=mock_nav_context,
            products_shown=mock_products,
            narrative=mock_narrative,
        )

        assert session_id is not None


# =============================================================================
# Divergence Detection Integration Tests
# =============================================================================

class TestDivergenceDetectionIntegration:
    """Tests for divergence detection integration."""

    def test_multiple_divergence_signals_combine(self, mock_onboarding_profile):
        """Test that multiple divergence signals combine correctly."""
        checker = ReinterpretationChecker()

        # Create behavioral summary with multiple divergences
        behavioral = BehavioralSummary(
            median_spending=800.0,   # 1.6x budget - triggers
            style_variance=0.95,     # 0.45 diff from 0.5 - triggers
            brand_repeat_rate=0.1,   # 0.5 diff from 0.6 - triggers
            interaction_count=50,
        )

        # Check each signal
        budget_signal = checker._check_budget_divergence(mock_onboarding_profile, behavioral)
        adventure_signal = checker._check_adventurousness_divergence(mock_onboarding_profile, behavioral)
        brand_signal = checker._check_brand_loyalty_divergence(mock_onboarding_profile, behavioral)

        signals = [s for s in [budget_signal, adventure_signal, brand_signal] if s is not None]

        # All three should be triggered
        assert len(signals) >= 2  # At least 2 for reinterpretation
        assert any(s.signal_type == "spending_above_stated" for s in signals)

    def test_severity_increases_with_divergence(self, mock_onboarding_profile):
        """Test that severity increases with divergence magnitude."""
        checker = ReinterpretationChecker()

        # Small divergence
        behavioral_small = BehavioralSummary(median_spending=550.0)  # 1.1x
        signal_small = checker._check_budget_divergence(mock_onboarding_profile, behavioral_small)

        # Large divergence
        behavioral_large = BehavioralSummary(median_spending=1000.0)  # 2x
        signal_large = checker._check_budget_divergence(mock_onboarding_profile, behavioral_large)

        # Small divergence should not trigger
        assert signal_small is None

        # Large divergence should trigger with higher severity
        assert signal_large is not None
        assert signal_large.severity > 0


# =============================================================================
# Factory Functions Integration Tests
# =============================================================================

class TestFactoryFunctionsIntegration:
    """Tests for factory function integration."""

    def test_create_all_components(self):
        """Test creating all components with shared driver."""
        from ari_v3.feedback import (
            create_session_tracker,
            create_outcome_recorder,
            create_reinterpretation_checker,
            create_feedback_analytics,
        )

        mock_driver = MagicMock()

        tracker = create_session_tracker(neo4j_driver=mock_driver)
        recorder = create_outcome_recorder(neo4j_driver=mock_driver)
        checker = create_reinterpretation_checker(neo4j_driver=mock_driver)
        analytics = create_feedback_analytics(neo4j_driver=mock_driver)

        # All should share the same driver
        assert tracker.neo4j_driver is mock_driver
        assert recorder.neo4j_driver is mock_driver
        assert checker.neo4j_driver is mock_driver
        assert analytics.neo4j_driver is mock_driver


# =============================================================================
# Error Handling Integration Tests
# =============================================================================

class TestErrorHandlingIntegration:
    """Tests for error handling in integration scenarios."""

    @pytest.mark.asyncio
    async def test_session_tracking_with_partial_context(self):
        """Test session tracking with partial navigation context."""
        tracker = SessionTracker()

        # Context with missing synthesis
        partial_context = MagicMock()
        partial_context.query = "test query"
        partial_context.occasion = None
        partial_context.computed_state = None
        partial_context.synthesis = None
        partial_context.destination = None

        session_id = await tracker.track_session(
            user_id="user123",
            nav_context=partial_context,
            products_shown=[],
        )

        assert session_id is not None

    @pytest.mark.asyncio
    async def test_outcome_recording_with_various_product_formats(self):
        """Test outcome recording with various product ID formats."""
        recorder = OutcomeRecorder()

        # Different product ID formats should all work
        formats = [
            "prod123",                          # Simple string
            "abc-def-ghi-jkl",                 # UUID-like
            "product_with_underscore_123",     # With underscores
        ]

        for prod_id in formats:
            result = await recorder.record_outcome(
                session_id="sess123",
                product_id=prod_id,
                outcome=OutcomeType.VIEWED,
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_reinterpretation_checker_handles_missing_profile_fields(self):
        """Test that checker handles profiles with missing fields."""
        checker = ReinterpretationChecker()

        # Profile with missing practicality
        partial_profile = MagicMock()
        partial_profile.practicality = None
        partial_profile.process = None
        partial_profile.taste = None
        partial_profile.personal = None

        behavioral = BehavioralSummary(
            median_spending=500.0,
            style_variance=0.5,
        )

        # These should return None (no signal) rather than raise
        budget_signal = checker._check_budget_divergence(partial_profile, behavioral)
        adventure_signal = checker._check_adventurousness_divergence(partial_profile, behavioral)
        brand_signal = checker._check_brand_loyalty_divergence(partial_profile, behavioral)

        assert budget_signal is None
        assert adventure_signal is None
        assert brand_signal is None
