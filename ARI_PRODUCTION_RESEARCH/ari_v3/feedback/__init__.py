"""
ARI V3 Feedback Module

Provides the feedback loop for learning from user outcomes:
- SessionTracker: Track recommendation sessions
- OutcomeRecorder: Record user interactions (viewed, clicked, liked, purchased, rejected)
- ReinterpretationChecker: Detect behavioral drift and trigger re-interpretation
- FeedbackAnalytics: Analyze session outcomes

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 8
"""

from ari_v3.feedback.session_tracker import (
    SessionTracker,
    SessionProduct,
    RecommendationSession,
    create_session_tracker,
)
from ari_v3.feedback.outcome_recorder import (
    OutcomeRecorder,
    OutcomeType,
    SessionOutcome,
    create_outcome_recorder,
)
from ari_v3.feedback.reinterpretation import (
    ReinterpretationChecker,
    DivergenceSignal,
    DivergenceAnalysisResult,
    BehavioralSummary,
    create_reinterpretation_checker,
    MIN_INTERACTIONS_FOR_DIVERGENCE,
    MIN_DIVERGENCE_SIGNALS,
)
from ari_v3.feedback.analytics import (
    FeedbackAnalytics,
    FeedbackAnalysis,
    SessionMetrics,
    DescriptorEffectiveness,
    create_feedback_analytics,
)

__all__ = [
    # Session tracking
    "SessionTracker",
    "SessionProduct",
    "RecommendationSession",
    "create_session_tracker",
    # Outcome recording
    "OutcomeRecorder",
    "OutcomeType",
    "SessionOutcome",
    "create_outcome_recorder",
    # Reinterpretation
    "ReinterpretationChecker",
    "DivergenceSignal",
    "DivergenceAnalysisResult",
    "BehavioralSummary",
    "create_reinterpretation_checker",
    "MIN_INTERACTIONS_FOR_DIVERGENCE",
    "MIN_DIVERGENCE_SIGNALS",
    # Analytics
    "FeedbackAnalytics",
    "FeedbackAnalysis",
    "SessionMetrics",
    "DescriptorEffectiveness",
    "create_feedback_analytics",
]
