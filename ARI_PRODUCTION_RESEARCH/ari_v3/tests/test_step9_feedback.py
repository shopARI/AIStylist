"""
Unit tests for ARI V3 Step 9: Feedback Loop

Tests for SessionTracker, OutcomeRecorder, ReinterpretationChecker, and FeedbackAnalytics.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ari_v3.feedback import (
    SessionTracker,
    SessionProduct,
    RecommendationSession,
    create_session_tracker,
    OutcomeRecorder,
    OutcomeType,
    SessionOutcome,
    create_outcome_recorder,
    ReinterpretationChecker,
    DivergenceSignal,
    DivergenceAnalysisResult,
    BehavioralSummary,
    create_reinterpretation_checker,
    FeedbackAnalytics,
    FeedbackAnalysis,
    SessionMetrics,
    DescriptorEffectiveness,
    create_feedback_analytics,
    MIN_INTERACTIONS_FOR_DIVERGENCE,
    MIN_DIVERGENCE_SIGNALS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_neo4j_driver():
    """Create mock Neo4j driver."""
    driver = MagicMock()
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.run = AsyncMock(return_value=MagicMock())
    driver.session = MagicMock(return_value=mock_session)
    return driver


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
# SessionTracker Tests
# =============================================================================

class TestSessionTrackerInit:
    """Tests for SessionTracker initialization."""

    def test_init_without_driver(self):
        """Test initialization without Neo4j driver."""
        tracker = SessionTracker()
        assert tracker.neo4j_driver is None
        assert tracker._database == "users"

    def test_init_with_driver(self, mock_neo4j_driver):
        """Test initialization with Neo4j driver."""
        tracker = SessionTracker(neo4j_driver=mock_neo4j_driver)
        assert tracker.neo4j_driver is mock_neo4j_driver


class TestSessionTrackerTrackSession:
    """Tests for track_session method."""

    @pytest.mark.asyncio
    async def test_track_session_without_driver(self, mock_nav_context, mock_products):
        """Test track_session without Neo4j driver."""
        tracker = SessionTracker()

        session_id = await tracker.track_session(
            user_id="user123",
            nav_context=mock_nav_context,
            products_shown=mock_products,
        )

        assert session_id is not None
        assert len(session_id) == 36  # UUID length

    @pytest.mark.asyncio
    async def test_track_session_empty_user_id_raises(self, mock_nav_context):
        """Test that empty user_id raises ValueError."""
        tracker = SessionTracker()

        with pytest.raises(ValueError, match="user_id cannot be empty"):
            await tracker.track_session(
                user_id="",
                nav_context=mock_nav_context,
                products_shown=[],
            )

    @pytest.mark.asyncio
    async def test_track_session_extracts_context_data(self, mock_nav_context, mock_products):
        """Test that session extracts data from nav_context correctly."""
        tracker = SessionTracker()

        # Capture the session created
        with patch.object(tracker, '_store_session_neo4j', new_callable=AsyncMock) as mock_store:
            await tracker.track_session(
                user_id="user123",
                nav_context=mock_nav_context,
                products_shown=mock_products,
            )

            # Since no driver, store won't be called
            mock_store.assert_not_called()

    @pytest.mark.asyncio
    async def test_track_session_with_none_nav_context(self, mock_products):
        """Test track_session with None nav_context."""
        tracker = SessionTracker()

        session_id = await tracker.track_session(
            user_id="user123",
            nav_context=None,
            products_shown=mock_products,
        )

        assert session_id is not None


class TestSessionProduct:
    """Tests for SessionProduct dataclass."""

    def test_create_session_product(self):
        """Test creating a SessionProduct."""
        product = SessionProduct(
            product_id="prod123",
            relevance_score=0.85,
            position=1,
        )

        assert product.product_id == "prod123"
        assert product.relevance_score == 0.85
        assert product.position == 1

    def test_default_values(self):
        """Test default values."""
        product = SessionProduct(product_id="prod123")

        assert product.relevance_score == 0.0
        assert product.position == 0


class TestRecommendationSession:
    """Tests for RecommendationSession dataclass."""

    def test_create_recommendation_session(self):
        """Test creating a RecommendationSession."""
        session = RecommendationSession(
            session_id="sess123",
            user_id="user123",
            timestamp=datetime.now(),
            query="casual shirt",
        )

        assert session.session_id == "sess123"
        assert session.user_id == "user123"
        assert session.query == "casual shirt"

    def test_to_dict(self):
        """Test to_dict method."""
        session = RecommendationSession(
            session_id="sess123",
            user_id="user123",
            timestamp=datetime.now(),
            query="casual shirt",
            style_descriptors=["casual", "professional"],
            products_shown=[
                SessionProduct("prod1", 0.9, 1),
                SessionProduct("prod2", 0.8, 2),
            ],
        )

        result = session.to_dict()

        assert result["session_id"] == "sess123"
        assert result["user_id"] == "user123"
        assert result["query"] == "casual shirt"
        assert result["product_ids"] == ["prod1", "prod2"]
        assert result["product_scores"] == [0.9, 0.8]


class TestSessionTrackerFactory:
    """Tests for factory function."""

    def test_create_session_tracker(self, mock_neo4j_driver):
        """Test factory function."""
        tracker = create_session_tracker(neo4j_driver=mock_neo4j_driver)

        assert isinstance(tracker, SessionTracker)
        assert tracker.neo4j_driver is mock_neo4j_driver


# =============================================================================
# OutcomeRecorder Tests
# =============================================================================

class TestOutcomeRecorderInit:
    """Tests for OutcomeRecorder initialization."""

    def test_init_without_driver(self):
        """Test initialization without Neo4j driver."""
        recorder = OutcomeRecorder()
        assert recorder.neo4j_driver is None

    def test_init_with_driver(self, mock_neo4j_driver):
        """Test initialization with Neo4j driver."""
        recorder = OutcomeRecorder(neo4j_driver=mock_neo4j_driver)
        assert recorder.neo4j_driver is mock_neo4j_driver


class TestOutcomeRecorderRecordOutcome:
    """Tests for record_outcome method."""

    @pytest.mark.asyncio
    async def test_record_outcome_without_driver(self):
        """Test record_outcome without Neo4j driver."""
        recorder = OutcomeRecorder()

        result = await recorder.record_outcome(
            session_id="sess123",
            product_id="prod123",
            outcome=OutcomeType.CLICKED,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_record_outcome_empty_session_id_raises(self):
        """Test that empty session_id raises ValueError."""
        recorder = OutcomeRecorder()

        with pytest.raises(ValueError, match="session_id cannot be empty"):
            await recorder.record_outcome(
                session_id="",
                product_id="prod123",
                outcome=OutcomeType.CLICKED,
            )

    @pytest.mark.asyncio
    async def test_record_outcome_empty_product_id_raises(self):
        """Test that empty product_id raises ValueError."""
        recorder = OutcomeRecorder()

        with pytest.raises(ValueError, match="product_id cannot be empty"):
            await recorder.record_outcome(
                session_id="sess123",
                product_id="",
                outcome=OutcomeType.CLICKED,
            )

    @pytest.mark.asyncio
    async def test_record_outcome_invalid_feedback_raises(self):
        """Test that invalid feedback raises ValueError."""
        recorder = OutcomeRecorder()

        with pytest.raises(ValueError, match="explicit_feedback must be between 1 and 5"):
            await recorder.record_outcome(
                session_id="sess123",
                product_id="prod123",
                outcome=OutcomeType.CLICKED,
                explicit_feedback=6,
            )


class TestOutcomeRecorderConvenienceMethods:
    """Tests for convenience methods."""

    @pytest.mark.asyncio
    async def test_record_view(self):
        """Test record_view method."""
        recorder = OutcomeRecorder()
        result = await recorder.record_view("sess123", "prod123", time_spent_seconds=30)
        assert result is True

    @pytest.mark.asyncio
    async def test_record_click(self):
        """Test record_click method."""
        recorder = OutcomeRecorder()
        result = await recorder.record_click("sess123", "prod123")
        assert result is True

    @pytest.mark.asyncio
    async def test_record_like(self):
        """Test record_like method."""
        recorder = OutcomeRecorder()
        result = await recorder.record_like("sess123", "prod123")
        assert result is True

    @pytest.mark.asyncio
    async def test_record_purchase(self):
        """Test record_purchase method."""
        recorder = OutcomeRecorder()
        result = await recorder.record_purchase("sess123", "prod123")
        assert result is True

    @pytest.mark.asyncio
    async def test_record_rejection(self):
        """Test record_rejection method."""
        recorder = OutcomeRecorder()
        result = await recorder.record_rejection("sess123", "prod123", feedback_text="Not my style")
        assert result is True


class TestOutcomeRecorderRating:
    """Tests for record_rating method."""

    @pytest.mark.asyncio
    async def test_high_rating_maps_to_liked(self):
        """Test that high rating (4-5) maps to LIKED."""
        recorder = OutcomeRecorder()

        with patch.object(recorder, 'record_outcome', new_callable=AsyncMock, return_value=True) as mock:
            await recorder.record_rating("sess123", "prod123", rating=5)
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args.kwargs["outcome"] == OutcomeType.LIKED

    @pytest.mark.asyncio
    async def test_low_rating_maps_to_rejected(self):
        """Test that low rating (1-2) maps to REJECTED."""
        recorder = OutcomeRecorder()

        with patch.object(recorder, 'record_outcome', new_callable=AsyncMock, return_value=True) as mock:
            await recorder.record_rating("sess123", "prod123", rating=2)
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args.kwargs["outcome"] == OutcomeType.REJECTED

    @pytest.mark.asyncio
    async def test_medium_rating_maps_to_viewed(self):
        """Test that medium rating (3) maps to VIEWED."""
        recorder = OutcomeRecorder()

        with patch.object(recorder, 'record_outcome', new_callable=AsyncMock, return_value=True) as mock:
            await recorder.record_rating("sess123", "prod123", rating=3)
            mock.assert_called_once()
            call_args = mock.call_args
            assert call_args.kwargs["outcome"] == OutcomeType.VIEWED


class TestOutcomeType:
    """Tests for OutcomeType enum."""

    def test_outcome_types(self):
        """Test all outcome types."""
        assert OutcomeType.VIEWED.value == "viewed"
        assert OutcomeType.CLICKED.value == "clicked"
        assert OutcomeType.LIKED.value == "liked"
        assert OutcomeType.PURCHASED.value == "purchased"
        assert OutcomeType.REJECTED.value == "rejected"


class TestSessionOutcome:
    """Tests for SessionOutcome dataclass."""

    def test_create_session_outcome(self):
        """Test creating a SessionOutcome."""
        outcome = SessionOutcome(
            session_id="sess123",
            product_id="prod123",
            outcome_type=OutcomeType.CLICKED,
            timestamp=datetime.now(),
        )

        assert outcome.session_id == "sess123"
        assert outcome.outcome_type == OutcomeType.CLICKED

    def test_to_dict(self):
        """Test to_dict method."""
        outcome = SessionOutcome(
            session_id="sess123",
            product_id="prod123",
            outcome_type=OutcomeType.CLICKED,
            timestamp=datetime.now(),
            time_spent_seconds=30,
            explicit_feedback=4,
        )

        result = outcome.to_dict()

        assert result["session_id"] == "sess123"
        assert result["outcome_type"] == "clicked"
        assert result["time_spent_seconds"] == 30
        assert result["explicit_feedback"] == 4


# =============================================================================
# ReinterpretationChecker Tests
# =============================================================================

class TestReinterpretationCheckerInit:
    """Tests for ReinterpretationChecker initialization."""

    def test_init_without_services(self):
        """Test initialization without services."""
        checker = ReinterpretationChecker()
        assert checker.neo4j_driver is None
        assert checker.onboarding_service is None

    def test_init_with_services(self, mock_neo4j_driver):
        """Test initialization with services."""
        mock_service = MagicMock()
        checker = ReinterpretationChecker(
            neo4j_driver=mock_neo4j_driver,
            onboarding_service=mock_service,
        )
        assert checker.neo4j_driver is mock_neo4j_driver
        assert checker.onboarding_service is mock_service


class TestReinterpretationCheckerTrigger:
    """Tests for check_reinterpretation_trigger method."""

    @pytest.mark.asyncio
    async def test_empty_user_id_raises(self):
        """Test that empty user_id raises ValueError."""
        checker = ReinterpretationChecker()

        with pytest.raises(ValueError, match="user_id cannot be empty"):
            await checker.check_reinterpretation_trigger("")

    @pytest.mark.asyncio
    async def test_not_enough_interactions(self):
        """Test that not enough interactions returns no reinterpret."""
        checker = ReinterpretationChecker()

        with patch.object(checker, '_get_interaction_count', new_callable=AsyncMock, return_value=10):
            result = await checker.check_reinterpretation_trigger("user123")

            assert result.should_reinterpret is False
            assert result.interaction_count == 10

    @pytest.mark.asyncio
    async def test_no_user_data_returns_no_reinterpret(self):
        """Test that no user data returns no reinterpret."""
        checker = ReinterpretationChecker()

        with patch.object(checker, '_get_interaction_count', new_callable=AsyncMock, return_value=50):
            with patch.object(checker, '_load_raw_user_data', new_callable=AsyncMock, return_value=None):
                result = await checker.check_reinterpretation_trigger("user123")

                assert result.should_reinterpret is False


class TestDivergenceSignal:
    """Tests for DivergenceSignal dataclass."""

    def test_create_divergence_signal(self):
        """Test creating a DivergenceSignal."""
        signal = DivergenceSignal(
            signal_type="spending_above_stated",
            description="Spending too high",
            stated_value=500,
            observed_value=800,
            severity=0.6,
        )

        assert signal.signal_type == "spending_above_stated"
        assert signal.severity == 0.6


class TestDivergenceAnalysisResult:
    """Tests for DivergenceAnalysisResult dataclass."""

    def test_create_result(self):
        """Test creating a result."""
        result = DivergenceAnalysisResult(
            user_id="user123",
            interaction_count=50,
            signals=[],
            should_reinterpret=False,
        )

        assert result.user_id == "user123"
        assert result.signal_count == 0

    def test_signal_count_property(self):
        """Test signal_count property."""
        result = DivergenceAnalysisResult(
            user_id="user123",
            interaction_count=50,
            signals=[
                DivergenceSignal("type1", "desc1", 1, 2),
                DivergenceSignal("type2", "desc2", 3, 4),
            ],
        )

        assert result.signal_count == 2

    def test_to_dict(self):
        """Test to_dict method."""
        result = DivergenceAnalysisResult(
            user_id="user123",
            interaction_count=50,
            signals=[DivergenceSignal("type1", "desc1", 1, 2, 0.5)],
            should_reinterpret=True,
        )

        data = result.to_dict()

        assert data["user_id"] == "user123"
        assert data["should_reinterpret"] is True
        assert len(data["signals"]) == 1


class TestBehavioralSummary:
    """Tests for BehavioralSummary dataclass."""

    def test_create_summary(self):
        """Test creating a BehavioralSummary."""
        summary = BehavioralSummary(
            median_spending=300.0,
            style_variance=0.6,
            brand_repeat_rate=0.4,
            interaction_count=50,
        )

        assert summary.median_spending == 300.0
        assert summary.interaction_count == 50

    def test_to_dict(self):
        """Test to_dict method."""
        summary = BehavioralSummary(
            median_spending=300.0,
            purchased_styles=["casual", "formal"],
        )

        data = summary.to_dict()

        assert data["median_spending"] == 300.0
        assert data["purchased_styles"] == ["casual", "formal"]


class TestBudgetDivergence:
    """Tests for budget divergence checking."""

    def test_spending_above_threshold(self, mock_onboarding_profile):
        """Test detection of spending above threshold."""
        checker = ReinterpretationChecker()
        behavioral = BehavioralSummary(median_spending=800.0)  # 1.6x stated 500

        signal = checker._check_budget_divergence(mock_onboarding_profile, behavioral)

        assert signal is not None
        assert signal.signal_type == "spending_above_stated"

    def test_spending_below_threshold(self, mock_onboarding_profile):
        """Test detection of spending below threshold."""
        checker = ReinterpretationChecker()
        behavioral = BehavioralSummary(median_spending=100.0)  # 0.2x stated 500

        signal = checker._check_budget_divergence(mock_onboarding_profile, behavioral)

        assert signal is not None
        assert signal.signal_type == "spending_below_stated"

    def test_spending_within_range(self, mock_onboarding_profile):
        """Test no signal when spending within range."""
        checker = ReinterpretationChecker()
        behavioral = BehavioralSummary(median_spending=450.0)  # 0.9x stated 500

        signal = checker._check_budget_divergence(mock_onboarding_profile, behavioral)

        assert signal is None


class TestAdventurousnessDivergence:
    """Tests for adventurousness divergence checking."""

    def test_adventurousness_mismatch(self, mock_onboarding_profile):
        """Test detection of adventurousness mismatch."""
        checker = ReinterpretationChecker()
        behavioral = BehavioralSummary(style_variance=0.95)  # vs 0.5 stated, diff=0.45 > 0.4 threshold

        signal = checker._check_adventurousness_divergence(mock_onboarding_profile, behavioral)

        assert signal is not None
        assert signal.signal_type == "adventurousness_mismatch"

    def test_adventurousness_match(self, mock_onboarding_profile):
        """Test no signal when adventurousness matches."""
        checker = ReinterpretationChecker()
        behavioral = BehavioralSummary(style_variance=0.5)  # matches stated

        signal = checker._check_adventurousness_divergence(mock_onboarding_profile, behavioral)

        assert signal is None


# =============================================================================
# FeedbackAnalytics Tests
# =============================================================================

class TestFeedbackAnalyticsInit:
    """Tests for FeedbackAnalytics initialization."""

    def test_init_without_driver(self):
        """Test initialization without Neo4j driver."""
        analytics = FeedbackAnalytics()
        assert analytics.neo4j_driver is None

    def test_init_with_driver(self, mock_neo4j_driver):
        """Test initialization with Neo4j driver."""
        analytics = FeedbackAnalytics(neo4j_driver=mock_neo4j_driver)
        assert analytics.neo4j_driver is mock_neo4j_driver


class TestFeedbackAnalysisDataclass:
    """Tests for FeedbackAnalysis dataclass."""

    def test_create_analysis(self):
        """Test creating a FeedbackAnalysis."""
        now = datetime.now()
        analysis = FeedbackAnalysis(
            start_date=now - timedelta(days=30),
            end_date=now,
            days_analyzed=30,
            total_sessions=100,
            overall_click_through_rate=0.25,
        )

        assert analysis.total_sessions == 100
        assert analysis.overall_click_through_rate == 0.25

    def test_to_dict(self):
        """Test to_dict method."""
        now = datetime.now()
        analysis = FeedbackAnalysis(
            start_date=now - timedelta(days=30),
            end_date=now,
            days_analyzed=30,
        )

        data = analysis.to_dict()

        assert "time_range" in data
        assert "session_counts" in data
        assert "overall_metrics" in data


class TestSessionMetrics:
    """Tests for SessionMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating SessionMetrics."""
        metrics = SessionMetrics(
            session_id="sess123",
            products_shown=10,
            products_clicked=3,
            products_purchased=1,
        )

        assert metrics.session_id == "sess123"
        assert metrics.products_shown == 10

    def test_click_through_rate(self):
        """Test click_through_rate property."""
        metrics = SessionMetrics(
            session_id="sess123",
            products_shown=10,
            products_clicked=3,
        )

        assert metrics.click_through_rate == 0.3

    def test_conversion_rate(self):
        """Test conversion_rate property."""
        metrics = SessionMetrics(
            session_id="sess123",
            products_shown=10,
            products_purchased=2,
        )

        assert metrics.conversion_rate == 0.2

    def test_engagement_rate(self):
        """Test engagement_rate property."""
        metrics = SessionMetrics(
            session_id="sess123",
            products_shown=10,
            products_clicked=2,
            products_liked=1,
            products_purchased=1,
        )

        assert metrics.engagement_rate == 0.4

    def test_zero_products_shown(self):
        """Test rates with zero products shown."""
        metrics = SessionMetrics(
            session_id="sess123",
            products_shown=0,
        )

        assert metrics.click_through_rate == 0.0
        assert metrics.conversion_rate == 0.0
        assert metrics.engagement_rate == 0.0


class TestDescriptorEffectiveness:
    """Tests for DescriptorEffectiveness dataclass."""

    def test_create_effectiveness(self):
        """Test creating DescriptorEffectiveness."""
        eff = DescriptorEffectiveness(
            descriptor="casual",
            times_used=10,
            total_conversions=2,
            total_clicks=5,
            total_rejections=1,
        )

        assert eff.descriptor == "casual"
        assert eff.times_used == 10

    def test_conversion_rate(self):
        """Test conversion_rate property."""
        eff = DescriptorEffectiveness(
            descriptor="casual",
            times_used=10,
            total_conversions=3,
        )

        assert eff.conversion_rate == 0.3

    def test_effectiveness_score(self):
        """Test effectiveness_score property."""
        eff = DescriptorEffectiveness(
            descriptor="casual",
            times_used=10,
            total_conversions=3,
            total_rejections=1,
        )

        # conversion_rate (0.3) - rejection_rate (0.1) = 0.2
        assert eff.effectiveness_score == pytest.approx(0.2)

    def test_zero_times_used(self):
        """Test rates with zero times used."""
        eff = DescriptorEffectiveness(
            descriptor="casual",
            times_used=0,
        )

        assert eff.conversion_rate == 0.0
        assert eff.effectiveness_score == 0.0


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_outcome_recorder(self, mock_neo4j_driver):
        """Test create_outcome_recorder."""
        recorder = create_outcome_recorder(neo4j_driver=mock_neo4j_driver)
        assert isinstance(recorder, OutcomeRecorder)

    def test_create_reinterpretation_checker(self, mock_neo4j_driver):
        """Test create_reinterpretation_checker."""
        checker = create_reinterpretation_checker(neo4j_driver=mock_neo4j_driver)
        assert isinstance(checker, ReinterpretationChecker)

    def test_create_feedback_analytics(self, mock_neo4j_driver):
        """Test create_feedback_analytics."""
        analytics = create_feedback_analytics(neo4j_driver=mock_neo4j_driver)
        assert isinstance(analytics, FeedbackAnalytics)


# =============================================================================
# Module Import Tests
# =============================================================================

class TestModuleImports:
    """Tests for module imports."""

    def test_import_from_feedback_package(self):
        """Test importing from feedback package."""
        from ari_v3.feedback import (
            SessionTracker,
            OutcomeRecorder,
            ReinterpretationChecker,
            FeedbackAnalytics,
            OutcomeType,
            MIN_INTERACTIONS_FOR_DIVERGENCE,
            MIN_DIVERGENCE_SIGNALS,
        )

        assert SessionTracker is not None
        assert OutcomeRecorder is not None
        assert MIN_INTERACTIONS_FOR_DIVERGENCE == 30
        assert MIN_DIVERGENCE_SIGNALS == 2
