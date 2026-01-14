"""
ARI V3 Judge Module

Provides MMR selection, outlier injection, and 7-dimension product scoring.

Components:
- mmr_selector: Maximal Marginal Relevance for diversity
- outlier_injector: Exploration product injection
- ari_evaluator: 7-dimension scoring and selection pipeline
"""

from ari_v3.judge.mmr_selector import (
    ScoredProduct,
    mmr_select,
    create_scored_products,
)

from ari_v3.judge.outlier_injector import (
    inject_outliers,
    calculate_exploration_appetite_percentage,
    OUTLIER_DISTANCE_THRESHOLD,
)

from ari_v3.judge.ari_evaluator import (
    ARIEvaluator,
    ScoringWeights,
    ProductScoreBreakdown,
    DEFAULT_WEIGHTS,
)

__all__ = [
    # MMR Selector
    'ScoredProduct',
    'mmr_select',
    'create_scored_products',
    # Outlier Injector
    'inject_outliers',
    'calculate_exploration_appetite_percentage',
    'OUTLIER_DISTANCE_THRESHOLD',
    # Evaluator
    'ARIEvaluator',
    'ScoringWeights',
    'ProductScoreBreakdown',
    'DEFAULT_WEIGHTS',
]
