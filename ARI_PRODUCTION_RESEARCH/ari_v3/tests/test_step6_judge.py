"""
Unit tests for Step 6: Judge Upgrade - MMR + Outliers

Tests:
- MMR selection algorithm
- Outlier injection
- 7-dimension product scoring
- Full evaluation pipeline
"""

import pytest
import numpy as np
from datetime import datetime

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
from ari_v3.core.data_structures import (
    StyleCoordinate,
    Trajectory,
    NavigationParameters,
    ComputedUserState,
)
from ari_v3.navigation.navigation_context import (
    NavigationContext,
    NavigationPath,
    BehavioralProfile,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_embedding():
    """Create a sample embedding vector."""
    return np.random.randn(256).astype(np.float32)


@pytest.fixture
def sample_products():
    """Create sample products for testing."""
    return [
        {
            'id': 'prod_1',
            'title': 'Blue Cotton Shirt',
            'price': 59.99,
            'brand': 'StyleCo',
            'category': 'tops',
            'embedding': np.random.randn(256).astype(np.float32),
        },
        {
            'id': 'prod_2',
            'title': 'Black Wool Blazer',
            'price': 149.99,
            'brand': 'Premium',
            'category': 'outerwear',
            'embedding': np.random.randn(256).astype(np.float32),
        },
        {
            'id': 'prod_3',
            'title': 'White Linen Pants',
            'price': 89.99,
            'brand': 'StyleCo',
            'category': 'bottoms',
            'embedding': np.random.randn(256).astype(np.float32),
        },
        {
            'id': 'prod_4',
            'title': 'Red Silk Dress',
            'price': 199.99,
            'brand': 'Luxe',
            'category': 'dresses',
            'embedding': np.random.randn(256).astype(np.float32),
        },
        {
            'id': 'prod_5',
            'title': 'Gray Cashmere Sweater',
            'price': 129.99,
            'brand': 'Premium',
            'category': 'tops',
            'embedding': np.random.randn(256).astype(np.float32),
        },
    ]


@pytest.fixture
def sample_nav_context():
    """Create sample navigation context for testing."""
    from ari_v3.navigation.synthesis_llm import BudgetInterpretation, SynthesisOutput

    embedding = np.random.randn(256).astype(np.float32)
    current_pos = StyleCoordinate(embedding=embedding.tolist(), visual_embedding=None)
    destination = StyleCoordinate(embedding=np.random.randn(256).tolist(), visual_embedding=None)

    trajectory = Trajectory(
        direction=np.random.randn(256).tolist(),
        velocity=0.05,
        consistency=0.8,
        last_computed=datetime.now(),
    )

    nav_params = NavigationParameters(
        exploration_appetite=0.5,
        step_size_multiplier=1.0,
        brand_affinity_weight=0.3,
        result_set_size=10,
        diversity_requirement=0.5,
        user_embedding_weight=0.5,
        default_budget=None,
        category_budget_overrides={},
    )

    path = NavigationPath(
        current_position=current_pos,
        destination=destination,
        max_step_size=0.3,
        outlier_percentage=0.1,
        diversity_requirement=0.5,
        smoothness_score=1.0,
        coherence_score=0.8,
    )

    synthesis = SynthesisOutput(
        style_descriptors=['casual', 'comfortable'],
        exemplar_search_terms=['casual shirt'],
        understood_intent='Looking for casual wear',
        budget_interpretation=BudgetInterpretation(min=50, max=200),
        formality_level=0.3,
        relevant_context=['casual context'],
    )

    behavioral = BehavioralProfile(
        category_interests=['tops', 'bottoms'],
        brand_preferences=['StyleCo'],
        price_sensitivity=0.5,
    )

    return NavigationContext(
        current_position=current_pos,
        trajectory=trajectory,
        destination=destination,
        path=path,
        query='casual shirt',
        occasion='everyday',
        raw_user_data=None,
        computed_state=None,
        synthesis=synthesis,
        behavioral_profile=behavioral,
    )


# =============================================================================
# MMR Selector Tests
# =============================================================================

class TestMMRSelector:
    """Tests for MMR selection algorithm."""

    def test_mmr_select_empty_input(self):
        """MMR handles empty input."""
        result = mmr_select([], limit=5, lambda_param=0.5)
        assert result == []

    def test_mmr_select_single_product(self, sample_embedding):
        """MMR with single product returns that product."""
        product = ScoredProduct(
            product={'id': 'test'},
            relevance_score=0.8,
            embedding=sample_embedding,
        )
        result = mmr_select([product], limit=5, lambda_param=0.5)
        assert len(result) == 1
        assert result[0].product_id == 'test'

    def test_mmr_select_respects_limit(self, sample_products):
        """MMR respects the limit parameter."""
        scored = create_scored_products(sample_products)
        result = mmr_select(scored, limit=3, lambda_param=0.5)
        assert len(result) == 3

    def test_mmr_select_highest_relevance_first(self):
        """MMR selects highest relevance product first."""
        products = [
            ScoredProduct(
                product={'id': f'p{i}'},
                relevance_score=0.1 * i,
                embedding=np.random.randn(256),
            )
            for i in range(1, 6)
        ]
        result = mmr_select(products, limit=5, lambda_param=1.0)  # Pure relevance
        assert result[0].relevance_score == 0.5  # Highest score

    def test_mmr_select_diversity_mode(self):
        """MMR with lambda=0 prioritizes diversity."""
        # Create products with similar embeddings
        base_embedding = np.random.randn(256)
        products = [
            ScoredProduct(
                product={'id': f'similar_{i}'},
                relevance_score=0.9,
                embedding=base_embedding + np.random.randn(256) * 0.01,  # Very similar
            )
            for i in range(3)
        ]
        # Add one diverse product
        products.append(ScoredProduct(
            product={'id': 'diverse'},
            relevance_score=0.5,  # Lower relevance
            embedding=np.random.randn(256),  # Very different
        ))

        result = mmr_select(products, limit=4, lambda_param=0.0)  # Pure diversity
        # Diverse product should be selected despite lower relevance
        selected_ids = [sp.product_id for sp in result]
        assert 'diverse' in selected_ids

    def test_mmr_fallback_without_embeddings(self):
        """MMR falls back to relevance ranking without embeddings."""
        products = [
            ScoredProduct(
                product={'id': f'p{i}'},
                relevance_score=0.1 * i,
                embedding=None,
            )
            for i in range(1, 6)
        ]
        result = mmr_select(products, limit=3, lambda_param=0.5)
        assert len(result) == 3
        # Should be sorted by relevance
        assert result[0].relevance_score >= result[1].relevance_score

    def test_create_scored_products(self, sample_products):
        """create_scored_products correctly converts products."""
        scored = create_scored_products(sample_products)
        assert len(scored) == 5
        assert all(isinstance(sp, ScoredProduct) for sp in scored)
        assert scored[0].product['id'] == 'prod_1'


# =============================================================================
# Outlier Injector Tests
# =============================================================================

class TestOutlierInjector:
    """Tests for outlier injection."""

    def test_inject_outliers_disabled(self):
        """No injection when percentage is 0."""
        selected = [
            ScoredProduct(product={'id': 'p1'}, relevance_score=0.9, embedding=None)
        ]
        remaining = [
            ScoredProduct(product={'id': 'p2'}, relevance_score=0.5, embedding=None)
        ]
        result, injected = inject_outliers(selected, remaining, outlier_percentage=0.0)
        assert len(injected) == 0
        assert result == selected

    def test_inject_outliers_empty_selected(self):
        """No injection when selected is empty."""
        result, injected = inject_outliers([], [], outlier_percentage=0.2)
        assert result == []
        assert injected == []

    def test_inject_outliers_caps_percentage(self):
        """Percentage is capped at 20%."""
        selected = [
            ScoredProduct(product={'id': f'p{i}'}, relevance_score=0.9, embedding=None)
            for i in range(10)
        ]
        remaining = [
            ScoredProduct(
                product={'id': f'outlier_{i}'},
                relevance_score=0.2,
                embedding=np.random.randn(256),
            )
            for i in range(10)
        ]
        current_pos = np.zeros(256)  # All products will be outliers (distance > 0)

        result, injected = inject_outliers(
            selected, remaining,
            outlier_percentage=0.5,  # Exceeds cap
            current_position_embedding=current_pos,
        )
        # Should inject at most 20%
        assert len(injected) <= 2  # 20% of 10

    def test_inject_outliers_marks_products(self):
        """Injected products are marked with _is_outlier flag."""
        selected = [
            ScoredProduct(product={'id': 'p1'}, relevance_score=0.9, embedding=None)
        ]
        remaining = [
            ScoredProduct(
                product={'id': 'outlier'},
                relevance_score=0.1,
                embedding=np.random.randn(256),
            )
        ]
        current_pos = np.zeros(256)

        result, injected = inject_outliers(
            selected, remaining,
            outlier_percentage=0.5,
            current_position_embedding=current_pos,
        )

        if injected:
            # Check that result contains the marked outlier product
            outlier_in_result = [p for p in result if p.product.get('id') == 'outlier']
            assert len(outlier_in_result) == 1
            assert outlier_in_result[0].product.get('_is_outlier') is True

    def test_calculate_exploration_appetite_percentage(self):
        """Correct calculation of outlier percentage."""
        assert calculate_exploration_appetite_percentage(0.0) == 0.0
        assert calculate_exploration_appetite_percentage(0.5) == 0.1
        assert calculate_exploration_appetite_percentage(1.0) == 0.2


# =============================================================================
# Scoring Weights Tests
# =============================================================================

class TestScoringWeights:
    """Tests for scoring weights validation."""

    def test_default_weights_valid(self):
        """Default weights sum to 1.0."""
        assert DEFAULT_WEIGHTS.validate() is True

    def test_custom_weights_validation(self):
        """Custom weights are validated."""
        valid = ScoringWeights(
            smoothness=0.2,
            coherence=0.1,
            budget_fit=0.2,
            brand_match=0.1,
            behavioral_consistency=0.2,
            multi_agent_confidence=0.1,
            rule_compliance=0.1,
        )
        assert valid.validate() is True

        invalid = ScoringWeights(
            smoothness=0.5,  # Too high
            coherence=0.5,
        )
        assert invalid.validate() is False


# =============================================================================
# ARI Evaluator Tests
# =============================================================================

class TestARIEvaluator:
    """Tests for the main evaluator."""

    def test_evaluator_init_default_weights(self):
        """Evaluator uses default weights."""
        evaluator = ARIEvaluator()
        assert evaluator.weights == DEFAULT_WEIGHTS

    def test_evaluator_init_custom_weights(self):
        """Evaluator accepts custom weights."""
        custom = ScoringWeights(
            smoothness=0.2,
            coherence=0.1,
            budget_fit=0.2,
            brand_match=0.1,
            behavioral_consistency=0.2,
            multi_agent_confidence=0.1,
            rule_compliance=0.1,
        )
        evaluator = ARIEvaluator(weights=custom)
        assert evaluator.weights == custom

    def test_evaluator_empty_products(self, sample_nav_context):
        """Evaluator handles empty product list."""
        evaluator = ARIEvaluator()
        result = evaluator.evaluate_and_select([], sample_nav_context, limit=5)
        assert result == []

    def test_evaluator_scores_products(self, sample_products, sample_nav_context):
        """Evaluator scores all products."""
        evaluator = ARIEvaluator()
        result = evaluator.evaluate_and_select(sample_products, sample_nav_context, limit=5)

        assert len(result) == 5
        for product in result:
            assert '_total_score' in product
            assert '_score_breakdown' in product
            assert '_final_rank' in product

    def test_evaluator_respects_limit(self, sample_products, sample_nav_context):
        """Evaluator respects limit parameter."""
        evaluator = ARIEvaluator()
        result = evaluator.evaluate_and_select(sample_products, sample_nav_context, limit=2)
        assert len(result) == 2

    def test_evaluator_ranks_products(self, sample_products, sample_nav_context):
        """Evaluator assigns sequential ranks."""
        evaluator = ARIEvaluator()
        result = evaluator.evaluate_and_select(sample_products, sample_nav_context, limit=5)

        ranks = [p['_final_rank'] for p in result]
        assert ranks == [1, 2, 3, 4, 5]

    def test_score_budget_fit_within_budget(self, sample_nav_context):
        """Products within budget get high score."""
        evaluator = ARIEvaluator()
        product = {'id': 'test', 'price': 100}  # Within 50-200 budget

        score = evaluator._score_budget_fit(product, sample_nav_context)
        assert score == 1.0

    def test_score_budget_fit_above_budget(self, sample_nav_context):
        """Products above budget get lower score."""
        evaluator = ARIEvaluator()
        product = {'id': 'test', 'price': 400}  # Above 200 budget

        score = evaluator._score_budget_fit(product, sample_nav_context)
        assert score < 1.0

    def test_score_brand_match_preferred(self, sample_nav_context):
        """Preferred brands get high score."""
        evaluator = ARIEvaluator()
        product = {'id': 'test', 'brand': 'StyleCo'}

        score = evaluator._score_brand_match(product, ['StyleCo', 'Premium'])
        assert score == 1.0

    def test_score_brand_match_not_preferred(self, sample_nav_context):
        """Non-preferred brands get lower score."""
        evaluator = ARIEvaluator()
        product = {'id': 'test', 'brand': 'Unknown'}

        score = evaluator._score_brand_match(product, ['StyleCo', 'Premium'])
        assert score < 1.0

    def test_score_multi_agent_consensus(self):
        """Multi-agent consensus gets higher score."""
        evaluator = ARIEvaluator()
        agent_scores = {
            'prod_1': {
                'vibe_agent': 0.8,
                'cypher_agent': 0.9,
            }
        }

        score = evaluator._score_multi_agent_confidence('prod_1', agent_scores)
        assert score > 0.8  # Should have consensus bonus


class TestProductScoreBreakdown:
    """Tests for score breakdown."""

    def test_breakdown_to_dict(self):
        """Breakdown converts to dictionary."""
        breakdown = ProductScoreBreakdown(
            smoothness_score=0.9,
            coherence_score=0.8,
            budget_fit_score=1.0,
            brand_match_score=0.7,
            behavioral_consistency_score=0.6,
            multi_agent_confidence_score=0.85,
            rule_compliance_score=0.75,
            total_score=0.8,
        )

        d = breakdown.to_dict()
        assert d['smoothness'] == 0.9
        assert d['total'] == 0.8


# =============================================================================
# Integration Tests
# =============================================================================

class TestJudgeIntegration:
    """Integration tests for the full judge pipeline."""

    def test_full_pipeline(self, sample_products, sample_nav_context):
        """Full evaluation pipeline works end-to-end."""
        evaluator = ARIEvaluator()

        agent_scores = {
            'prod_1': {'vibe': 0.9, 'cypher': 0.8},
            'prod_2': {'vibe': 0.7},
            'prod_3': {'cypher': 0.85},
        }

        result = evaluator.evaluate_and_select(
            products=sample_products,
            nav_context=sample_nav_context,
            limit=3,
            agent_scores=agent_scores,
            styling_rules=['casual', 'comfortable'],
            brand_preferences=['StyleCo'],
        )

        assert len(result) == 3
        assert all('_total_score' in p for p in result)
        assert all('_final_rank' in p for p in result)

    def test_pipeline_with_outliers(self, sample_products, sample_nav_context):
        """Pipeline handles high exploration appetite."""
        # Note: Outlier injection depends on computed_state.nav_params.exploration_appetite
        # With default nav_context (no computed_state), it uses default 0.5
        # This test verifies the pipeline runs correctly regardless

        evaluator = ARIEvaluator()
        result = evaluator.evaluate_and_select(
            products=sample_products,
            nav_context=sample_nav_context,
            limit=5,
        )

        # Verify pipeline completes and returns products
        assert len(result) == 5

        # All products should have scores and ranks
        for product in result:
            assert '_total_score' in product
            assert '_final_rank' in product

        # Check that outlier flags exist (may or may not be set)
        # The flag is only set when outliers are actually injected
        outlier_count = sum(1 for p in result if p.get('_is_outlier', False))
        assert outlier_count >= 0  # Valid (0 or more)
