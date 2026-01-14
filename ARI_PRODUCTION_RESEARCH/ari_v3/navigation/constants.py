"""
ARI V3 Navigation Constants

All values are derived from ARI_Navigation_Intelligence_PSEUDOCODE_V3.md.
This module centralizes navigation algorithm constants for maintainability.

DO NOT modify these values without updating the pseudocode specification.

Reference: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 4
"""

# =============================================================================
# Step Size Configuration (Section 4, lines 2064-2071)
# =============================================================================

# Base step size in embedding space (cosine distance units)
# This is the default maximum distance to travel in one navigation step
BASE_STEP_SIZE = 0.3

# Velocity thresholds for movement speed classification
SLOW_MOVER_VELOCITY_THRESHOLD = 0.03   # Below this = conservative navigation
FAST_MOVER_VELOCITY_THRESHOLD = 0.06   # Above this = aggressive navigation

# Step size multipliers based on user velocity
SLOW_MOVER_STEP_MULTIPLIER = 0.7       # Conservative: smaller steps
FAST_MOVER_STEP_MULTIPLIER = 1.2       # Aggressive: larger steps


# =============================================================================
# Outlier and Diversity (Section 4, line 2074)
# =============================================================================

# Maximum outlier percentage factor
# outlier_percentage = exploration_appetite * MAX_OUTLIER_FACTOR
MAX_OUTLIER_FACTOR = 0.20


# =============================================================================
# Quality Scores (Section 4, line 2082)
# =============================================================================

# Smoothness score when step is within bounds
SMOOTHNESS_SCORE_VALID = 1.0

# Smoothness score when step exceeds max (but still attempted)
SMOOTHNESS_SCORE_EXCEEDED = 0.7

# Default coherence when trajectory is missing or invalid
DEFAULT_COHERENCE_NO_TRAJECTORY = 0.8

# Coherence when embeddings are missing
DEFAULT_COHERENCE_NO_EMBEDDINGS = 0.5


# =============================================================================
# Embedding Dimensions
# =============================================================================

# OpenAI text-embedding-3-small dimension
TEXT_EMBEDDING_DIM = 1536

# SigLIP visual embedding dimension
VISUAL_EMBEDDING_DIM = 1024


# =============================================================================
# LLM Configuration
# =============================================================================

# Default LLM temperature for synthesis
SYNTHESIS_LLM_TEMPERATURE = 0.7

# Default model for synthesis LLM
SYNTHESIS_MODEL = "gpt-4o"

# Default model for embeddings
EMBEDDING_MODEL = "text-embedding-3-small"


# =============================================================================
# Fallback Budget Defaults
# =============================================================================

# Default budget when LLM fails to provide one
FALLBACK_BUDGET_MIN = 50
FALLBACK_BUDGET_MAX = 300

# Default budget when parsing LLM response fails
LLM_PARSE_BUDGET_MIN = 0
LLM_PARSE_BUDGET_MAX = 500


# =============================================================================
# Cold Start Defaults (for users with no history)
# =============================================================================

COLD_START_EXPLORATION_APPETITE = 0.5
COLD_START_STEP_SIZE_MULTIPLIER = 1.0
COLD_START_BRAND_AFFINITY_WEIGHT = 0.3
COLD_START_RESULT_SET_SIZE = 12
COLD_START_DIVERSITY_REQUIREMENT = 0.5
COLD_START_USER_EMBEDDING_WEIGHT = 0.5
COLD_START_MAX_STEP_SIZE = 0.3
COLD_START_OUTLIER_PERCENTAGE = 0.1
COLD_START_COHERENCE = 0.8
COLD_START_FORMALITY = 0.5


# =============================================================================
# Exemplar Retrieval
# =============================================================================

# Number of exemplars to retrieve per search term
EXEMPLAR_SEARCH_LIMIT = 5


# =============================================================================
# Trajectory Velocity Thresholds for Prompt Description
# =============================================================================

# Thresholds for describing trajectory in synthesis prompt
VELOCITY_THRESHOLD_EXPLORING = 0.05    # Above = "actively exploring"
VELOCITY_THRESHOLD_CONSISTENT = 0.02   # Below = "very consistent, minimal change"
