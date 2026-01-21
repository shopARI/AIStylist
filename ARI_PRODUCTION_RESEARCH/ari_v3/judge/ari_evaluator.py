"""
ARI V3 - Product Evaluator

Scores products on 7 dimensions for navigation-aware recommendation.
Combines with MMR selection and outlier injection for final results.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 6.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ari_v3.judge.mmr_selector import ScoredProduct, mmr_select, create_scored_products
from ari_v3.judge.outlier_injector import inject_outliers, calculate_exploration_appetite_percentage
from ari_v3.navigation.navigation_context import NavigationContext, NavigationPath
from ari_v3.interface.types import ExplanationTrace, ScoreComponent

logger = logging.getLogger(__name__)


# =============================================================================
# Scoring Weights (Section 6.3)
# =============================================================================

@dataclass
class ScoringWeights:
    """Weights for the 7(+1) dimension scoring system."""
    smoothness: float = 0.15          # Step distance score
    coherence: float = 0.10           # Trajectory alignment
    budget_fit: float = 0.15          # Price within budget
    brand_match: float = 0.10         # Brand preference alignment
    behavioral_consistency: float = 0.20  # Matches user behavior patterns
    multi_agent_confidence: float = 0.10  # Agreement between agents
    rule_compliance: float = 0.20     # Styling rule adherence

    # Visual scoring (V3.2) - when enabled, redistributes from other weights
    visual_similarity: float = 0.0    # Visual match from FashionSigLIP (default: disabled)

    def validate(self) -> bool:
        """Validate weights sum to 1.0."""
        total = (
            self.smoothness + self.coherence + self.budget_fit +
            self.brand_match + self.behavioral_consistency +
            self.multi_agent_confidence + self.rule_compliance +
            self.visual_similarity
        )
        return abs(total - 1.0) < 0.001

    @classmethod
    def with_visual(cls, visual_weight: float = 0.15) -> 'ScoringWeights':
        """
        Create weights with visual scoring enabled.

        Redistributes weight from smoothness and coherence to visual.
        """
        # Take visual weight from smoothness (0.10) and coherence (0.05)
        return cls(
            smoothness=0.10,
            coherence=0.05,
            budget_fit=0.15,
            brand_match=0.10,
            behavioral_consistency=0.20,
            multi_agent_confidence=0.10,
            rule_compliance=0.15,
            visual_similarity=visual_weight,
        )


DEFAULT_WEIGHTS = ScoringWeights()


# =============================================================================
# Score Components
# =============================================================================

@dataclass
class ProductScoreBreakdown:
    """Detailed breakdown of a product's score."""
    smoothness_score: float = 0.0
    coherence_score: float = 0.0
    budget_fit_score: float = 0.0
    brand_match_score: float = 0.0
    behavioral_consistency_score: float = 0.0
    multi_agent_confidence_score: float = 0.0
    rule_compliance_score: float = 0.0
    visual_similarity_score: float = 0.0  # V3.2: FashionSigLIP visual match

    total_score: float = 0.0
    weights_used: ScoringWeights = field(default_factory=ScoringWeights)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'smoothness': self.smoothness_score,
            'coherence': self.coherence_score,
            'budget_fit': self.budget_fit_score,
            'brand_match': self.brand_match_score,
            'behavioral_consistency': self.behavioral_consistency_score,
            'multi_agent_confidence': self.multi_agent_confidence_score,
            'rule_compliance': self.rule_compliance_score,
            'visual_similarity': self.visual_similarity_score,
            'total': self.total_score,
        }


# =============================================================================
# Main Evaluator
# =============================================================================

class ARIEvaluator:
    """
    V3 Product Evaluator.

    Scores products on 7 dimensions, applies MMR for diversity,
    and injects outliers for exploration.
    """

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
    ):
        """
        Initialize the evaluator.

        Args:
            weights: Custom scoring weights (uses defaults if not provided)
        """
        self.weights = weights or DEFAULT_WEIGHTS
        if not self.weights.validate():
            logger.warning("Scoring weights do not sum to 1.0 - using defaults")
            self.weights = DEFAULT_WEIGHTS

    def evaluate_and_select(
        self,
        products: List[Dict[str, Any]],
        nav_context: NavigationContext,
        limit: int = 10,
        agent_scores: Optional[Dict[str, Dict[str, float]]] = None,
        styling_rules: Optional[List[str]] = None,
        brand_preferences: Optional[List[str]] = None,
        trace: Optional[ExplanationTrace] = None,
    ) -> List[Dict[str, Any]]:
        """
        Evaluate products and select final recommendations.

        Full pipeline:
        1. Score each product on 7 dimensions
        2. Apply MMR selection for diversity
        3. Inject outliers for exploration
        4. Return final ranked list

        Args:
            products: List of candidate products
            nav_context: Navigation context with user state and path
            limit: Maximum products to return
            agent_scores: Optional dict of {product_id: {agent_name: score}}
            styling_rules: Optional list of styling rules to check compliance
            brand_preferences: Optional list of preferred brands
            trace: Optional ExplanationTrace to populate with score breakdowns

        Returns:
            List of products with scores, sorted by rank
        """
        if not products:
            return []

        logger.info(f"Evaluating {len(products)} products for selection")

        # Step 1: Score each product
        scored_products = self._score_products(
            products=products,
            nav_context=nav_context,
            agent_scores=agent_scores or {},
            styling_rules=styling_rules or [],
            brand_preferences=brand_preferences or [],
            trace=trace,
        )

        # Step 2: Apply MMR selection
        diversity_requirement = nav_context.path.diversity_requirement if nav_context.path else 0.5
        mmr_selected = mmr_select(
            candidates=scored_products,
            limit=limit,
            lambda_param=diversity_requirement,
        )

        # Step 3: Inject outliers
        exploration_appetite = 0.5  # Default
        if nav_context.computed_state and nav_context.computed_state.nav_params:
            exploration_appetite = nav_context.computed_state.nav_params.exploration_appetite

        outlier_percentage = calculate_exploration_appetite_percentage(exploration_appetite)

        # Get remaining products not selected by MMR
        selected_ids = {sp.product_id for sp in mmr_selected}
        remaining = [sp for sp in scored_products if sp.product_id not in selected_ids]

        # Get current position embedding for outlier calculation
        current_embedding = None
        if nav_context.current_position and nav_context.current_position.embedding is not None:
            emb = nav_context.current_position.embedding
            current_embedding = np.array(emb) if not isinstance(emb, np.ndarray) else emb

        final_products, injected_outliers = inject_outliers(
            selected=mmr_selected,
            remaining=remaining,
            outlier_percentage=outlier_percentage,
            current_position_embedding=current_embedding,
        )

        # Step 4: Convert to output format and add metadata
        result = self._prepare_output(final_products, len(products), trace)

        logger.info(
            f"Selection complete: {len(result)} products "
            f"({len(injected_outliers)} outliers injected)"
        )

        return result

    def _score_products(
        self,
        products: List[Dict[str, Any]],
        nav_context: NavigationContext,
        agent_scores: Dict[str, Dict[str, float]],
        styling_rules: List[str],
        brand_preferences: List[str],
        trace: Optional[ExplanationTrace] = None,
    ) -> List[ScoredProduct]:
        """Score all products on 7 dimensions."""
        scored = []

        for product in products:
            breakdown = self._score_single_product(
                product=product,
                nav_context=nav_context,
                agent_scores=agent_scores,
                styling_rules=styling_rules,
                brand_preferences=brand_preferences,
            )

            # Get embedding if available
            embedding = None
            if 'embedding' in product:
                emb = product['embedding']
                embedding = np.array(emb) if not isinstance(emb, np.ndarray) else emb

            # Create copy of product to avoid mutating input
            product_copy = product.copy()
            product_copy['_score_breakdown'] = breakdown.to_dict()
            product_copy['_total_score'] = breakdown.total_score

            scored.append(ScoredProduct(
                product=product_copy,
                relevance_score=breakdown.total_score,
                embedding=embedding,
            ))

            # Add to explanation trace if provided
            if trace:
                product_id = product.get('id', str(id(product)))
                product_title = product.get('title', product.get('name', 'Unknown'))

                # Convert breakdown to ScoreComponents for the trace
                components = [
                    ScoreComponent(
                        name="smoothness",
                        value=breakdown.smoothness_score * self.weights.smoothness,
                        max_possible=self.weights.smoothness,
                        factors={"step_distance": breakdown.smoothness_score},
                        explanation=self._explain_smoothness(breakdown.smoothness_score),
                    ),
                    ScoreComponent(
                        name="coherence",
                        value=breakdown.coherence_score * self.weights.coherence,
                        max_possible=self.weights.coherence,
                        factors={"trajectory_alignment": breakdown.coherence_score},
                        explanation=self._explain_coherence(breakdown.coherence_score),
                    ),
                    ScoreComponent(
                        name="budget_fit",
                        value=breakdown.budget_fit_score * self.weights.budget_fit,
                        max_possible=self.weights.budget_fit,
                        factors={"price_within_budget": breakdown.budget_fit_score},
                        explanation=self._explain_budget_fit(breakdown.budget_fit_score, product),
                    ),
                    ScoreComponent(
                        name="brand_match",
                        value=breakdown.brand_match_score * self.weights.brand_match,
                        max_possible=self.weights.brand_match,
                        factors={"brand_preference_match": breakdown.brand_match_score},
                        explanation=self._explain_brand_match(breakdown.brand_match_score, product),
                    ),
                    ScoreComponent(
                        name="behavioral_consistency",
                        value=breakdown.behavioral_consistency_score * self.weights.behavioral_consistency,
                        max_possible=self.weights.behavioral_consistency,
                        factors={"behavior_pattern_match": breakdown.behavioral_consistency_score},
                        explanation=self._explain_behavioral(breakdown.behavioral_consistency_score),
                    ),
                    ScoreComponent(
                        name="multi_agent_confidence",
                        value=breakdown.multi_agent_confidence_score * self.weights.multi_agent_confidence,
                        max_possible=self.weights.multi_agent_confidence,
                        factors={"agent_agreement": breakdown.multi_agent_confidence_score},
                        explanation=self._explain_agent_confidence(breakdown.multi_agent_confidence_score),
                    ),
                    ScoreComponent(
                        name="rule_compliance",
                        value=breakdown.rule_compliance_score * self.weights.rule_compliance,
                        max_possible=self.weights.rule_compliance,
                        factors={"styling_rules_met": breakdown.rule_compliance_score},
                        explanation=self._explain_rule_compliance(breakdown.rule_compliance_score),
                    ),
                ]

                # Add visual similarity component if enabled (V3.2)
                if self.weights.visual_similarity > 0:
                    components.append(
                        ScoreComponent(
                            name="visual_similarity",
                            value=breakdown.visual_similarity_score * self.weights.visual_similarity,
                            max_possible=self.weights.visual_similarity,
                            factors={"fashionsig_match": breakdown.visual_similarity_score},
                            explanation=self._explain_visual_similarity(breakdown.visual_similarity_score, product),
                        )
                    )

                trace.add_product_breakdown(
                    product_id=product_id,
                    product_title=product_title,
                    final_score=breakdown.total_score,
                    components=components,
                )

        return scored

    def _score_single_product(
        self,
        product: Dict[str, Any],
        nav_context: NavigationContext,
        agent_scores: Dict[str, Dict[str, float]],
        styling_rules: List[str],
        brand_preferences: List[str],
    ) -> ProductScoreBreakdown:
        """Score a single product on all 7 dimensions."""
        breakdown = ProductScoreBreakdown(weights_used=self.weights)

        # 1. Smoothness (step distance)
        breakdown.smoothness_score = self._score_smoothness(product, nav_context)

        # 2. Coherence (trajectory alignment)
        breakdown.coherence_score = self._score_coherence(product, nav_context)

        # 3. Budget fit
        breakdown.budget_fit_score = self._score_budget_fit(product, nav_context)

        # 4. Brand match - factor in brand_affinity_weight from nav_params
        brand_affinity_weight = 0.5  # Default
        if nav_context.computed_state and nav_context.computed_state.nav_params:
            brand_affinity_weight = nav_context.computed_state.nav_params.brand_affinity_weight
        breakdown.brand_match_score = self._score_brand_match(
            product, brand_preferences, brand_affinity_weight
        )

        # 5. Behavioral consistency
        breakdown.behavioral_consistency_score = self._score_behavioral_consistency(
            product, nav_context
        )

        # 6. Multi-agent confidence
        product_id = product.get('id', str(id(product)))
        breakdown.multi_agent_confidence_score = self._score_multi_agent_confidence(
            product_id, agent_scores
        )

        # 7. Rule compliance
        breakdown.rule_compliance_score = self._score_rule_compliance(product, styling_rules)

        # 8. Visual similarity (V3.2) - uses pre-computed visual score from fusion
        breakdown.visual_similarity_score = self._score_visual_similarity(product)

        # Calculate total weighted score
        breakdown.total_score = (
            breakdown.smoothness_score * self.weights.smoothness +
            breakdown.coherence_score * self.weights.coherence +
            breakdown.budget_fit_score * self.weights.budget_fit +
            breakdown.brand_match_score * self.weights.brand_match +
            breakdown.behavioral_consistency_score * self.weights.behavioral_consistency +
            breakdown.multi_agent_confidence_score * self.weights.multi_agent_confidence +
            breakdown.rule_compliance_score * self.weights.rule_compliance +
            breakdown.visual_similarity_score * self.weights.visual_similarity
        )

        return breakdown

    def _score_smoothness(
        self,
        product: Dict[str, Any],
        nav_context: NavigationContext,
    ) -> float:
        """
        Score smoothness - how well product fits within step size constraints.

        Returns:
            Score 0-1 (1 = within max step size, lower = exceeds step size)
        """
        if not nav_context.path:
            return 0.5  # Neutral if no path

        # Get product embedding
        product_emb = product.get('embedding')
        if product_emb is None:
            return 0.5

        # Get current position embedding (null check for current_position first)
        if nav_context.current_position is None:
            return 0.5
        current_emb = nav_context.current_position.embedding
        if current_emb is None:
            return 0.5

        # Calculate distance
        product_vec = np.array(product_emb) if not isinstance(product_emb, np.ndarray) else product_emb
        current_vec = np.array(current_emb) if not isinstance(current_emb, np.ndarray) else current_emb

        if product_vec.size == 0 or current_vec.size == 0:
            return 0.5

        # Handle dimension mismatch (e.g., 1536-dim semantic vs 1024-dim visual)
        if product_vec.shape != current_vec.shape:
            # Use search score as proxy when dimensions don't match
            # This allows visual products to be differentiated by their search relevance
            search_score = product.get('_visual_score', 0) or product.get('_semantic_score', 0) or product.get('_fused_score', 0)
            if search_score > 0:
                # Map search score (0-1) to smoothness range (0.3-0.8)
                return 0.3 + (search_score * 0.5)
            return 0.5  # Neutral only if no search score

        distance = self._cosine_distance(current_vec, product_vec)

        # Score based on whether distance is within max step
        max_step = nav_context.path.max_step_size
        if distance <= max_step:
            return 1.0  # Perfect score if within bounds
        else:
            # Penalty proportional to how much it exceeds
            excess = distance - max_step
            return max(0.0, 1.0 - (excess / max_step))

    def _score_coherence(
        self,
        product: Dict[str, Any],
        nav_context: NavigationContext,
    ) -> float:
        """
        Score coherence - alignment with user's trajectory.

        Returns:
            Score 0-1 (1 = perfectly aligned with trajectory)
        """
        if not nav_context.trajectory or nav_context.trajectory.direction is None:
            return 0.8  # Neutral if no trajectory

        # Get product embedding
        product_emb = product.get('embedding')
        if product_emb is None:
            return 0.5

        # Get current position (null check for current_position first)
        if nav_context.current_position is None:
            return 0.5
        current_emb = nav_context.current_position.embedding
        if current_emb is None:
            return 0.5

        # Calculate movement direction
        product_vec = np.array(product_emb) if not isinstance(product_emb, np.ndarray) else product_emb
        current_vec = np.array(current_emb) if not isinstance(current_emb, np.ndarray) else current_emb
        traj_dir = np.array(nav_context.trajectory.direction)

        if product_vec.size == 0 or current_vec.size == 0 or traj_dir.size == 0:
            return 0.5

        # Handle dimension mismatch (e.g., 1536-dim semantic vs 1024-dim visual)
        if product_vec.shape != current_vec.shape or product_vec.shape != traj_dir.shape:
            # Use search score as proxy when dimensions don't match
            search_score = product.get('_visual_score', 0) or product.get('_semantic_score', 0) or product.get('_fused_score', 0)
            if search_score > 0:
                # Map search score (0-1) to coherence range (0.5-0.9)
                # Higher search scores suggest better alignment with user intent
                return 0.5 + (search_score * 0.4)
            return 0.8  # Neutral only if no search score

        movement = product_vec - current_vec
        movement_norm = np.linalg.norm(movement)
        traj_norm = np.linalg.norm(traj_dir)

        if movement_norm == 0 or traj_norm == 0:
            return 0.8  # No movement = neutral coherence

        # Cosine similarity between movement and trajectory
        movement_normalized = movement / movement_norm
        traj_normalized = traj_dir / traj_norm

        dot_product = np.dot(movement_normalized, traj_normalized)
        # Align with pseudocode spec: trajectory_dot + 0.5, clamped to [0, 1]
        # This maps [-0.5, 0.5] to [0, 1], being stricter about divergent movements
        coherence = max(0.0, min(1.0, dot_product + 0.5))

        return float(coherence)

    def _score_budget_fit(
        self,
        product: Dict[str, Any],
        nav_context: NavigationContext,
    ) -> float:
        """
        Score budget fit - how well price matches user's budget.

        Returns:
            Score 0-1 (1 = within budget, lower = outside budget)
        """
        price = product.get('price', 0)
        if not price or price <= 0:
            return 0.5  # Unknown price = neutral

        # Get budget from synthesis
        if not nav_context.synthesis or not nav_context.synthesis.budget_interpretation:
            return 0.7  # No budget info = slight positive bias

        budget = nav_context.synthesis.budget_interpretation
        min_budget = budget.min
        max_budget = budget.max

        if min_budget <= price <= max_budget:
            return 1.0  # Perfect fit

        # Calculate how far outside budget (aligned with pseudocode spec)
        if price < min_budget:
            # Below budget is acceptable per pseudocode (0.8 score)
            return 0.8
        else:
            # Above budget - penalize based on how far over
            # Formula: max(0, 1.0 - (price - max_budget) / max_budget)
            if max_budget > 0:
                penalty = (price - max_budget) / max_budget
                return max(0.0, 1.0 - penalty)
            return 0.0

    def _score_brand_match(
        self,
        product: Dict[str, Any],
        brand_preferences: List[str],
        brand_affinity_weight: float = 0.5,
    ) -> float:
        """
        Score brand match - alignment with preferred brands.

        Uses brand_affinity_weight to determine how much brand matters:
        - High affinity (0.8-1.0): Strong preference for known brands
        - Medium affinity (0.4-0.7): Some brand preference
        - Low affinity (0.0-0.3): Brand-agnostic, neutral scores

        Args:
            product: Product to score
            brand_preferences: List of user's preferred brands
            brand_affinity_weight: User's brand loyalty (0-1 from nav_params)

        Returns:
            Score 0-1 (1 = preferred brand, 0.5 = neutral)
        """
        # Low brand affinity = brand doesn't matter much, return neutral
        if brand_affinity_weight < 0.3:
            return 0.5  # Brand-agnostic users get neutral scores

        if not brand_preferences:
            return 0.5  # No preferences = neutral

        product_brand = (product.get('brand') or '').lower()
        if not product_brand:
            return 0.5  # Unknown brand = neutral

        # Check if brand matches preferences
        for pref_brand in brand_preferences:
            pref_lower = (pref_brand or '').lower()
            if pref_lower in product_brand or product_brand in pref_lower:
                # Scale the bonus by brand affinity
                # High affinity (1.0) -> full 1.0 score
                # Medium affinity (0.5) -> 0.75 score
                return 0.5 + (0.5 * brand_affinity_weight)

        # No match - penalty scales with affinity
        # High affinity users get penalized more for non-preferred brands
        # Low affinity users barely notice
        penalty = 0.2 * brand_affinity_weight
        return max(0.3, 0.5 - penalty)

    def _score_behavioral_consistency(
        self,
        product: Dict[str, Any],
        nav_context: NavigationContext,
    ) -> float:
        """
        Score behavioral consistency - matches user's behavior patterns.

        Returns:
            Score 0-1 (1 = highly consistent with behavior)
        """
        if not nav_context.behavioral_profile:
            return 0.5  # No profile = neutral

        score = 0.5  # Base score

        # Check category interests
        category = (product.get('category') or '').lower()
        if nav_context.behavioral_profile.category_interests:
            for interest in nav_context.behavioral_profile.category_interests:
                interest_lower = (interest or '').lower()
                if interest_lower in category or category in interest_lower:
                    score += 0.3
                    break

        # Check brand preferences from behavioral profile
        brand = (product.get('brand') or '').lower()
        if nav_context.behavioral_profile.brand_preferences:
            for pref_brand in nav_context.behavioral_profile.brand_preferences:
                pref_lower = (pref_brand or '').lower()
                if pref_lower in brand:
                    score += 0.2
                    break

        return min(1.0, score)

    def _score_multi_agent_confidence(
        self,
        product_id: str,
        agent_scores: Dict[str, Dict[str, float]],
    ) -> float:
        """
        Score multi-agent confidence - agreement between recommendation agents.

        Aligned with pseudocode spec:
        - 1 agent present: 0.6
        - 2 agents present: 0.8
        - 3 agents present: 1.0
        Formula: 0.6 + (agent_count - 1) * 0.2

        Returns:
            Score 0-1 (1 = all agents agree, lower = fewer agents)
        """
        if not agent_scores or product_id not in agent_scores:
            return 0.5  # No agent scores = neutral

        product_scores = agent_scores[product_id]
        num_agents = len(product_scores)

        if num_agents == 0:
            return 0.5

        # Use pseudocode formula: 0.6 + (agent_count - 1) * 0.2
        # This gives: 1 agent = 0.6, 2 agents = 0.8, 3 agents = 1.0
        base_score = 0.6 + (num_agents - 1) * 0.2

        return min(1.0, base_score)

    def _score_rule_compliance(
        self,
        product: Dict[str, Any],
        styling_rules: List[str],
    ) -> float:
        """
        Score rule compliance - adherence to styling rules.

        Returns:
            Score 0-1 (1 = complies with all rules)
        """
        if not styling_rules:
            return 0.7  # No rules = slight positive bias

        # Simple keyword-based compliance check
        # In production, this would use more sophisticated NLP
        title = product.get('title') or ''
        description = product.get('description') or ''
        product_text = f"{title} {description}".lower()

        compliance_score = 0.5  # Base score

        for rule in styling_rules:
            if not rule:
                continue
            rule_lower = rule.lower()
            # Extract key terms from rule
            key_terms = [term for term in rule_lower.split() if len(term) > 3]

            # Check if product matches rule terms
            matches = sum(1 for term in key_terms if term in product_text)
            if key_terms and matches > 0:
                compliance_score += 0.1 * (matches / len(key_terms))

        return min(1.0, compliance_score)

    def _score_visual_similarity(
        self,
        product: Dict[str, Any],
    ) -> float:
        """
        Score visual similarity (V3.2) - uses FashionSigLIP visual match score.

        The visual score is pre-computed during search fusion and attached
        to the product as '_visual_score'. If visual search wasn't enabled,
        returns neutral score.

        Returns:
            Score 0-1 (1 = high visual similarity)
        """
        # Check for pre-computed visual score from fusion step
        visual_score = product.get('_visual_score', 0)

        if visual_score > 0:
            # Visual search was performed and this product was found
            # Normalize the score (Qdrant scores can vary)
            return min(1.0, visual_score)

        # No visual score available - return neutral
        # This happens when:
        # - Visual search wasn't enabled
        # - Product was found only by semantic search
        return 0.5

    def _cosine_distance(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate cosine distance between two vectors."""
        # Handle dimension mismatch
        if v1.shape != v2.shape:
            return 0.5  # Neutral distance for mismatched dimensions

        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 1.0

        cosine_sim = dot_product / (norm1 * norm2)
        return float(1.0 - cosine_sim)

    def _prepare_output(
        self,
        scored_products: List[ScoredProduct],
        total_candidates: int,
        trace: Optional[ExplanationTrace] = None,
    ) -> List[Dict[str, Any]]:
        """Prepare final output with metadata."""
        result = []

        for rank, sp in enumerate(scored_products, start=1):
            product = sp.product.copy()
            product['_final_rank'] = rank
            product['_relevance_score'] = sp.relevance_score
            product['_total_candidates'] = total_candidates
            result.append(product)

            # Update trace with final rank and selection reason
            if trace:
                product_id = product.get('id', str(id(product)))
                breakdown = trace.get_product_breakdown(product_id)
                if breakdown:
                    breakdown.rank = rank
                    # Determine selection reason
                    if product.get('_is_outlier'):
                        breakdown.selection_reason = "exploration_outlier"
                    elif rank <= 3:
                        breakdown.selection_reason = "top_relevance"
                    else:
                        breakdown.selection_reason = "diversity_pick"

        return result

    # =========================================================================
    # Explanation Helper Methods (for ExplanationTrace)
    # =========================================================================

    def _explain_smoothness(self, score: float) -> str:
        """Generate human explanation for smoothness score."""
        if score >= 0.9:
            return "Fits naturally within your style comfort zone"
        elif score >= 0.7:
            return "A comfortable step from your current preferences"
        elif score >= 0.5:
            return "Slightly adventurous for your typical style"
        else:
            return "A bold departure from your usual choices"

    def _explain_coherence(self, score: float) -> str:
        """Generate human explanation for coherence score."""
        if score >= 0.8:
            return "Aligns well with your style evolution direction"
        elif score >= 0.6:
            return "Compatible with your recent style trajectory"
        elif score >= 0.4:
            return "Neutral to your current style direction"
        else:
            return "Diverges from your recent style evolution"

    def _explain_budget_fit(self, score: float, product: Dict[str, Any]) -> str:
        """Generate human explanation for budget fit."""
        price = product.get('price', 0)
        if score >= 1.0:
            return f"${price:.0f} fits perfectly within your budget"
        elif score >= 0.8:
            return f"${price:.0f} is below your typical spend"
        elif score >= 0.5:
            return f"${price:.0f} is slightly above your budget"
        else:
            return f"${price:.0f} exceeds your budget range"

    def _explain_brand_match(self, score: float, product: Dict[str, Any]) -> str:
        """Generate human explanation for brand match."""
        brand = product.get('brand', 'This brand')
        if score >= 0.8:
            return f"{brand} is among your preferred brands"
        elif score >= 0.5:
            return f"{brand} is a neutral choice for you"
        else:
            return f"{brand} isn't typically in your preferences"

    def _explain_behavioral(self, score: float) -> str:
        """Generate human explanation for behavioral consistency."""
        if score >= 0.8:
            return "Matches your shopping patterns closely"
        elif score >= 0.6:
            return "Consistent with your browsing history"
        elif score >= 0.4:
            return "Different from your usual picks"
        else:
            return "Outside your typical selection patterns"

    def _explain_agent_confidence(self, score: float) -> str:
        """Generate human explanation for multi-agent confidence."""
        if score >= 0.9:
            return "Multiple recommendation systems agree on this"
        elif score >= 0.7:
            return "Good agreement across recommendations"
        elif score >= 0.5:
            return "Moderate confidence in this pick"
        else:
            return "Single perspective recommendation"

    def _explain_rule_compliance(self, score: float) -> str:
        """Generate human explanation for rule compliance."""
        if score >= 0.8:
            return "Follows your style guidelines well"
        elif score >= 0.6:
            return "Generally aligns with your preferences"
        elif score >= 0.4:
            return "Partially matches your criteria"
        else:
            return "May not fully match your stated preferences"

    def _explain_visual_similarity(self, score: float, product: Dict[str, Any]) -> str:
        """Generate human explanation for visual similarity (V3.2)."""
        # Check if this had both visual and semantic scores
        has_visual = product.get('_visual_score', 0) > 0
        has_semantic = product.get('_semantic_score', 0) > 0

        if score >= 0.8:
            if has_visual:
                return "Visually matches your aesthetic preferences very well"
            return "Strong visual alignment with your style"
        elif score >= 0.6:
            if has_visual and has_semantic:
                return "Good visual and semantic match"
            return "Visually compatible with your preferences"
        elif score >= 0.5:
            return "Neutral visual match (found by text search)"
        elif score >= 0.3:
            return "Visual style differs from your typical preferences"
        else:
            return "Visually distinct from your usual aesthetic"
