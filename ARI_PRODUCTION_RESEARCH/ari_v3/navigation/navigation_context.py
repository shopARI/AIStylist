"""
ARI V3 - Navigation Context

Contains NavigationPath and NavigationContext structures
that combine all pillar outputs for query-time navigation.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np

from ari_v3.core.data_structures import (
    StyleCoordinate,
    NavigationParameters,
    ComputedUserState,
    RawUserData,
    Trajectory,
    zero_vector,
)

# Avoid circular imports - these are only needed for type hints
if TYPE_CHECKING:
    from ari_v3.navigation.synthesis_llm import SynthesisOutput
    from ari_v3.pillars.stylist_knowledge import MultiPerspectiveResult
from ari_v3.navigation.constants import (
    BASE_STEP_SIZE,
    SLOW_MOVER_VELOCITY_THRESHOLD,
    FAST_MOVER_VELOCITY_THRESHOLD,
    SLOW_MOVER_STEP_MULTIPLIER,
    FAST_MOVER_STEP_MULTIPLIER,
    MAX_OUTLIER_FACTOR,
    SMOOTHNESS_SCORE_VALID,
    SMOOTHNESS_SCORE_EXCEEDED,
    DEFAULT_COHERENCE_NO_TRAJECTORY,
    DEFAULT_COHERENCE_NO_EMBEDDINGS,
    TEXT_EMBEDDING_DIM,
    VISUAL_EMBEDDING_DIM,
    COLD_START_EXPLORATION_APPETITE,
    COLD_START_STEP_SIZE_MULTIPLIER,
    COLD_START_BRAND_AFFINITY_WEIGHT,
    COLD_START_RESULT_SET_SIZE,
    COLD_START_DIVERSITY_REQUIREMENT,
    COLD_START_USER_EMBEDDING_WEIGHT,
    COLD_START_MAX_STEP_SIZE,
    COLD_START_OUTLIER_PERCENTAGE,
    COLD_START_COHERENCE,
    COLD_START_FORMALITY,
    FALLBACK_BUDGET_MIN,
    FALLBACK_BUDGET_MAX,
)


@dataclass
class NavigationPath:
    """
    The calculated path from current position to destination.
    All calculations are deterministic based on nav_params.
    """
    current_position: StyleCoordinate
    destination: StyleCoordinate

    # Step constraints (from nav_params)
    max_step_size: float              # Maximum distance to travel
    outlier_percentage: float         # Percentage of outliers to inject (0-0.2)
    diversity_requirement: float      # MMR lambda parameter (0-1)

    # Path quality scores
    smoothness_score: float           # 0-1, how smooth is the step
    coherence_score: float            # 0-1, alignment with trajectory

    # Computed distance (None means not yet computed)
    total_distance: Optional[float] = None

    def __post_init__(self):
        """Compute total distance after initialization if not provided."""
        if self.total_distance is None:
            self.total_distance = self._compute_distance()

    def _compute_distance(self) -> float:
        """Compute cosine distance between current and destination.

        Uses the module-level _cosine_distance function for consistency.
        Returns 1.0 (maximum distance) for None/empty embeddings.
        """
        return _cosine_distance(
            self.current_position.embedding,
            self.destination.embedding
        )

    def is_step_valid(self) -> bool:
        """Check if the step is within allowed bounds."""
        if self.total_distance is None:
            return True  # Unknown distance treated as valid
        return self.total_distance <= self.max_step_size


@dataclass
class BehavioralProfile:
    """Behavioral patterns from Pillar 3."""
    category_interests: List[str] = field(default_factory=list)
    brand_preferences: List[str] = field(default_factory=list)
    price_sensitivity: float = 0.5      # 0=price insensitive, 1=very sensitive
    engagement_patterns: Dict[str, float] = field(default_factory=dict)


@dataclass
class DriftAnalysis:
    """Analysis of preference drift over time."""
    has_significant_drift: bool = False
    drift_direction: Optional[str] = None     # e.g., "more_casual", "higher_budget"
    drift_magnitude: float = 0.0
    divergent_signals: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class NavigationContext:
    """
    Complete context for navigation-aware product search.
    Combines outputs from all three pillars + synthesis.
    """
    # Core navigation
    current_position: StyleCoordinate
    trajectory: Trajectory
    destination: StyleCoordinate
    path: NavigationPath

    # Query context
    query: str
    occasion: Optional[str]

    # User data
    raw_user_data: Optional[RawUserData]
    computed_state: Optional[ComputedUserState]

    # Pillar 2: Styling rules
    styling_rules: List[str] = field(default_factory=list)
    body_guidance: str = ""
    occasion_guidance: str = ""

    # Pillar 3: Behavioral
    behavioral_profile: Optional[BehavioralProfile] = None
    drift_analysis: Optional[DriftAnalysis] = None

    # Synthesis output
    synthesis: Optional[SynthesisOutput] = None

    # Multi-perspective knowledge
    perspectives: Optional[MultiPerspectiveResult] = None

    def to_agent_context(self) -> Dict[str, Any]:
        """
        Format NavigationContext for agent input.
        Adapts V3 context to existing agent interface.
        """
        context = {
            "query": self.query,
            "occasion": self.occasion,
            "max_step_size": self.path.max_step_size if self.path else COLD_START_MAX_STEP_SIZE,
            "outlier_percentage": self.path.outlier_percentage if self.path else COLD_START_OUTLIER_PERCENTAGE,
            "diversity_requirement": self.path.diversity_requirement if self.path else COLD_START_DIVERSITY_REQUIREMENT,
        }

        # Add destination embedding
        if self.destination is not None:
            emb = self.destination.embedding
            if emb is not None and (not isinstance(emb, np.ndarray) or emb.size > 0):
                context["destination_embedding"] = emb.tolist() if isinstance(emb, np.ndarray) else emb

        # Add styling rules
        if self.styling_rules:
            context["styling_rules"] = self.styling_rules

        # Add body guidance
        if self.body_guidance:
            context["body_guidance"] = self.body_guidance

        # Add synthesis descriptors
        if self.synthesis:
            context["style_descriptors"] = self.synthesis.style_descriptors
            context["understood_intent"] = self.synthesis.understood_intent
            context["formality_level"] = self.synthesis.formality_level

        # Add budget interpretation
        if self.synthesis and self.synthesis.budget_interpretation:
            context["budget_min"] = self.synthesis.budget_interpretation.min
            context["budget_max"] = self.synthesis.budget_interpretation.max

        # Add user state summary
        if self.computed_state:
            user_context: Dict[str, Any] = {}

            # Safely get active_context
            if self.computed_state.active_context is not None:
                user_context["active_context"] = self.computed_state.active_context.value
            else:
                user_context["active_context"] = "default"

            # Safely get detected_contexts
            if self.computed_state.detected_contexts:
                user_context["detected_contexts"] = [c.value for c in self.computed_state.detected_contexts]
            else:
                user_context["detected_contexts"] = []

            context["user_context"] = user_context

            if self.computed_state.nav_params:
                context["nav_params"] = {
                    "exploration_appetite": self.computed_state.nav_params.exploration_appetite,
                    "step_size_multiplier": self.computed_state.nav_params.step_size_multiplier,
                    "brand_affinity_weight": self.computed_state.nav_params.brand_affinity_weight,
                }

        return context


def calculate_navigation_path(
    current: StyleCoordinate,
    destination: StyleCoordinate,
    trajectory: Trajectory,
    nav_params: NavigationParameters,
) -> NavigationPath:
    """
    Calculate navigation path (deterministic).

    V3: Uses navigation parameters from onboarding.

    Args:
        current: Current style position
        destination: Target style position
        trajectory: User's movement trajectory
        nav_params: Navigation parameters from onboarding

    Returns:
        NavigationPath with step constraints and quality scores
    """
    # Calculate total distance
    total_distance = _cosine_distance(current.embedding, destination.embedding)

    # V3: Step size from nav_params (see constants.py for values from pseudocode)
    max_step = BASE_STEP_SIZE * nav_params.step_size_multiplier

    # Velocity adjustment based on user movement patterns
    if trajectory and trajectory.velocity is not None:
        if trajectory.velocity < SLOW_MOVER_VELOCITY_THRESHOLD:
            max_step *= SLOW_MOVER_STEP_MULTIPLIER  # Conservative for slow movers
        elif trajectory.velocity > FAST_MOVER_VELOCITY_THRESHOLD:
            max_step *= FAST_MOVER_STEP_MULTIPLIER  # Aggressive for fast movers

    # Outlier percentage from nav_params
    outlier_percentage = nav_params.exploration_appetite * MAX_OUTLIER_FACTOR

    # Compute smoothness score
    smoothness_score = SMOOTHNESS_SCORE_VALID if total_distance <= max_step else SMOOTHNESS_SCORE_EXCEEDED

    # Compute coherence score
    coherence_score = _compute_coherence(current, destination, trajectory)

    return NavigationPath(
        current_position=current,
        destination=destination,
        max_step_size=max_step,
        outlier_percentage=outlier_percentage,
        diversity_requirement=nav_params.diversity_requirement,
        smoothness_score=smoothness_score,
        coherence_score=coherence_score,
        total_distance=total_distance,
    )


def _cosine_distance(embedding1, embedding2) -> float:
    """Compute cosine distance between two embeddings."""
    # Handle None
    if embedding1 is None or embedding2 is None:
        return 1.0

    # Handle empty arrays
    if isinstance(embedding1, np.ndarray) and embedding1.size == 0:
        return 1.0
    if isinstance(embedding2, np.ndarray) and embedding2.size == 0:
        return 1.0

    v1 = np.array(embedding1)
    v2 = np.array(embedding2)

    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 1.0

    cosine_sim = dot_product / (norm1 * norm2)
    return float(1.0 - cosine_sim)


def _compute_coherence(
    current: StyleCoordinate,
    destination: StyleCoordinate,
    trajectory: Optional[Trajectory],
) -> float:
    """
    Compute coherence score - how well destination aligns with trajectory.

    Returns:
        Coherence score 0-1 (1 = perfectly aligned with trajectory)
    """
    # Check trajectory
    if trajectory is None:
        return DEFAULT_COHERENCE_NO_TRAJECTORY  # No trajectory = neutral coherence

    traj_dir = trajectory.direction
    if traj_dir is None:
        return DEFAULT_COHERENCE_NO_TRAJECTORY
    if isinstance(traj_dir, np.ndarray) and traj_dir.size == 0:
        return DEFAULT_COHERENCE_NO_TRAJECTORY

    # Check embeddings
    current_emb = current.embedding
    dest_emb = destination.embedding
    if current_emb is None or dest_emb is None:
        return DEFAULT_COHERENCE_NO_EMBEDDINGS
    if isinstance(current_emb, np.ndarray) and current_emb.size == 0:
        return DEFAULT_COHERENCE_NO_EMBEDDINGS
    if isinstance(dest_emb, np.ndarray) and dest_emb.size == 0:
        return DEFAULT_COHERENCE_NO_EMBEDDINGS

    # Compute movement direction
    current_vec = np.array(current.embedding)
    dest_vec = np.array(destination.embedding)
    movement = dest_vec - current_vec

    # Normalize movement
    movement_norm = np.linalg.norm(movement)
    if movement_norm == 0:
        return 1.0  # No movement = coherent

    movement_normalized = movement / movement_norm

    # Compare with trajectory direction
    trajectory_dir = np.array(trajectory.direction)
    trajectory_norm = np.linalg.norm(trajectory_dir)

    if trajectory_norm == 0:
        return DEFAULT_COHERENCE_NO_TRAJECTORY  # No trajectory direction = neutral

    trajectory_normalized = trajectory_dir / trajectory_norm

    # Coherence = cosine similarity (0 to 1 range, shifted from -1 to 1)
    dot_product = np.dot(movement_normalized, trajectory_normalized)
    coherence = (dot_product + 1.0) / 2.0  # Map from [-1, 1] to [0, 1]

    return float(coherence)


def create_cold_start_context(
    query: str,
    occasion: Optional[str] = None,
    default_budget_min: float = FALLBACK_BUDGET_MIN,
    default_budget_max: float = FALLBACK_BUDGET_MAX,
) -> NavigationContext:
    """
    Create a minimal NavigationContext for cold start (no user data).

    Args:
        query: Search query
        occasion: Optional occasion
        default_budget_min: Default minimum budget
        default_budget_max: Default maximum budget

    Returns:
        NavigationContext with default values
    """
    from ari_v3.navigation.synthesis_llm import BudgetInterpretation, SynthesisOutput

    # Create default coordinates
    default_embedding = zero_vector(TEXT_EMBEDDING_DIM)
    current = StyleCoordinate(embedding=default_embedding, visual_embedding=zero_vector(VISUAL_EMBEDDING_DIM))
    destination = StyleCoordinate(embedding=default_embedding, visual_embedding=zero_vector(VISUAL_EMBEDDING_DIM))

    # Create default trajectory
    from datetime import datetime
    trajectory = Trajectory(
        direction=zero_vector(TEXT_EMBEDDING_DIM),
        velocity=0.0,
        consistency=COLD_START_DIVERSITY_REQUIREMENT,
        last_computed=datetime.now(),
    )

    # Create default path (cold start defaults from constants)
    path = NavigationPath(
        current_position=current,
        destination=destination,
        max_step_size=COLD_START_MAX_STEP_SIZE,
        outlier_percentage=COLD_START_OUTLIER_PERCENTAGE,
        diversity_requirement=COLD_START_DIVERSITY_REQUIREMENT,
        smoothness_score=SMOOTHNESS_SCORE_VALID,
        coherence_score=COLD_START_COHERENCE,
    )

    # Create minimal synthesis
    synthesis = SynthesisOutput(
        style_descriptors=[query],
        exemplar_search_terms=[query],
        understood_intent=f"Looking for {query}",
        budget_interpretation=BudgetInterpretation(
            min=default_budget_min,
            max=default_budget_max,
        ),
        formality_level=COLD_START_FORMALITY,
        relevant_context=["cold start - no user history"],
    )

    return NavigationContext(
        current_position=current,
        trajectory=trajectory,
        destination=destination,
        path=path,
        query=query,
        occasion=occasion,
        raw_user_data=None,
        computed_state=None,
        synthesis=synthesis,
    )
