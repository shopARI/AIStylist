"""
ARI V3 - Outlier Injector

Injects exploration products (outliers) into recommendation results.
Enables serendipitous discovery and style space exploration.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 6.2
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ari_v3.judge.mmr_selector import ScoredProduct

logger = logging.getLogger(__name__)

# Outlier qualification threshold (cosine distance from current position)
OUTLIER_DISTANCE_THRESHOLD = 0.4


def inject_outliers(
    selected: List[ScoredProduct],
    remaining: List[ScoredProduct],
    outlier_percentage: float,
    current_position_embedding: Optional[np.ndarray] = None,
    distance_threshold: float = OUTLIER_DISTANCE_THRESHOLD,
    seed: Optional[int] = None,
) -> Tuple[List[ScoredProduct], List[ScoredProduct]]:
    """
    Inject outlier products for exploration.

    Outliers are products with distance > threshold from current position.
    They introduce exploration and serendipity into recommendations.

    Args:
        selected: Already selected products (from MMR)
        remaining: Products not yet selected
        outlier_percentage: Percentage of final results to be outliers (0.0-0.2)
        current_position_embedding: User's current style position embedding
        distance_threshold: Minimum distance to qualify as outlier (default 0.4)
        seed: Optional random seed for deterministic outlier selection (for testing)

    Returns:
        Tuple of (final_products, injected_outliers)
        - final_products: Selected products with outliers injected
        - injected_outliers: List of products that were injected as outliers

    Algorithm:
        1. Calculate distance from current position for each remaining product
        2. Products with distance > threshold qualify as outliers
        3. Randomly sample from qualified outliers
        4. Replace lowest-scoring selected products with outliers
    """
    if not selected:
        return [], []

    if outlier_percentage <= 0:
        logger.debug("Outlier injection disabled (percentage=0)")
        return selected, []

    # Cap outlier percentage at 20%
    outlier_percentage = min(outlier_percentage, 0.2)

    # Calculate number of outliers to inject
    num_outliers = max(1, int(len(selected) * outlier_percentage))

    logger.debug(f"Outlier injection: {outlier_percentage:.1%} = {num_outliers} outliers for {len(selected)} products")

    # Find qualified outliers from remaining products
    qualified_outliers = _find_qualified_outliers(
        remaining=remaining,
        current_position=current_position_embedding,
        distance_threshold=distance_threshold,
    )

    if not qualified_outliers:
        logger.info("No qualified outliers found - skipping injection")
        return selected, []

    # Sample outliers (with optional seed for reproducibility)
    num_to_sample = min(num_outliers, len(qualified_outliers))
    if seed is not None:
        rng = random.Random(seed)
        sampled_outliers = rng.sample(qualified_outliers, num_to_sample)
    else:
        sampled_outliers = random.sample(qualified_outliers, num_to_sample)

    logger.info(f"Injecting {len(sampled_outliers)} outliers from {len(qualified_outliers)} qualified candidates")

    # Create final list by replacing lowest-scoring products
    final_products = _inject_into_selected(selected, sampled_outliers)

    return final_products, sampled_outliers


def _find_qualified_outliers(
    remaining: List[ScoredProduct],
    current_position: Optional[np.ndarray],
    distance_threshold: float,
) -> List[ScoredProduct]:
    """Find products that qualify as outliers based on distance from current position."""
    qualified = []

    for product in remaining:
        # Calculate distance from current position
        distance = _calculate_distance_from_current(product, current_position)

        if distance > distance_threshold:
            qualified.append(product)
            logger.debug(
                f"Qualified outlier: {product.product_id} "
                f"(distance={distance:.3f} > {distance_threshold})"
            )

    return qualified


def _calculate_distance_from_current(
    product: ScoredProduct,
    current_position: Optional[np.ndarray],
) -> float:
    """
    Calculate cosine distance from current position.

    Returns:
        Cosine distance (0-2 range, 0=identical, 2=opposite)
        Returns 1.0 (neutral) if no embeddings available
    """
    if current_position is None:
        # No current position - use relevance score as proxy
        # Lower relevance = more "outlier-like"
        return 1.0 - product.relevance_score

    if product.embedding is None:
        return 0.5  # Neutral distance if no embedding

    if current_position.size == 0 or product.embedding.size == 0:
        return 0.5

    # Handle dimension mismatch (e.g., 1536-dim semantic vs 1024-dim visual)
    if current_position.shape != product.embedding.shape:
        return 0.5  # Neutral distance for mismatched dimensions

    # Cosine distance = 1 - cosine similarity
    dot_product = np.dot(current_position, product.embedding)
    norm_current = np.linalg.norm(current_position)
    norm_product = np.linalg.norm(product.embedding)

    if norm_current == 0 or norm_product == 0:
        return 1.0

    cosine_sim = dot_product / (norm_current * norm_product)
    return float(1.0 - cosine_sim)


def _inject_into_selected(
    selected: List[ScoredProduct],
    outliers: List[ScoredProduct],
) -> List[ScoredProduct]:
    """
    Inject outliers into selected products by interspersing them at strategic positions.

    Outliers are marked with '_is_outlier' flag in product dict.
    Instead of sorting by relevance (which pushes outliers to the end),
    we place outliers at specific positions (e.g., positions 3, 7, etc.)
    to ensure they're actually visible to users.
    """
    if not outliers:
        return selected

    # Sort selected by relevance (ascending) to find replaceable items
    sorted_selected = sorted(selected, key=lambda x: x.relevance_score)

    # Replace lowest-scoring items with outliers
    num_to_replace = len(outliers)
    main_items = sorted_selected[num_to_replace:]  # Keep higher-scoring items

    # Sort main items by relevance (descending)
    main_items.sort(key=lambda x: x.relevance_score, reverse=True)

    # Prepare outliers with markers (copy product dict to avoid mutating input)
    marked_outliers = []
    for outlier in outliers:
        outlier_copy = ScoredProduct(
            product=outlier.product.copy(),
            relevance_score=outlier.relevance_score,
            embedding=outlier.embedding,
        )
        outlier_copy.product['_is_outlier'] = True
        outlier_copy.product['_outlier_reason'] = 'exploration_injection'
        marked_outliers.append(outlier_copy)

    # Intersperse outliers at strategic positions instead of just appending
    # Place first outlier at position 3 (0-indexed: 2), then every 4 positions
    final = []
    outlier_positions = [2 + i * 4 for i in range(len(marked_outliers))]
    outlier_idx = 0
    main_idx = 0

    for pos in range(len(main_items) + len(marked_outliers)):
        if outlier_idx < len(marked_outliers) and pos in outlier_positions:
            final.append(marked_outliers[outlier_idx])
            outlier_idx += 1
        elif main_idx < len(main_items):
            final.append(main_items[main_idx])
            main_idx += 1

    # Add any remaining items
    while main_idx < len(main_items):
        final.append(main_items[main_idx])
        main_idx += 1
    while outlier_idx < len(marked_outliers):
        final.append(marked_outliers[outlier_idx])
        outlier_idx += 1

    return final


def calculate_exploration_appetite_percentage(
    exploration_appetite: float,
    max_outlier_factor: float = 0.20,
) -> float:
    """
    Convert exploration_appetite to outlier_percentage.

    Args:
        exploration_appetite: User's exploration appetite (0-1)
        max_outlier_factor: Maximum outlier percentage (default 0.20 = 20%)

    Returns:
        Outlier percentage (0.0 to max_outlier_factor)

    Formula from pseudocode:
        outlier_percentage = exploration_appetite * MAX_OUTLIER_FACTOR
    """
    return exploration_appetite * max_outlier_factor
