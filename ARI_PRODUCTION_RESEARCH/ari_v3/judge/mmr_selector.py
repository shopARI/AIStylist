"""
ARI V3 - MMR (Maximal Marginal Relevance) Selector

Balances relevance with diversity in product selection.
Prevents clustering of similar items in results.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 6.1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ScoredProduct:
    """Product with relevance score and embedding."""
    product: Dict[str, Any]
    relevance_score: float
    embedding: Optional[np.ndarray] = None

    @property
    def product_id(self) -> str:
        return self.product.get('id', str(id(self.product)))


def mmr_select(
    candidates: List[ScoredProduct],
    limit: int,
    lambda_param: float = 0.5,
) -> List[ScoredProduct]:
    """
    Select products using Maximal Marginal Relevance (MMR).

    MMR balances relevance with diversity:
    MMR = lambda * relevance - (1 - lambda) * max_similarity_to_selected

    Args:
        candidates: List of ScoredProduct with relevance scores and embeddings
        limit: Maximum number of products to select
        lambda_param: Balance between relevance and diversity
                     0 = pure diversity, 1 = pure relevance
                     Default 0.5 = balanced

    Returns:
        List of selected ScoredProduct in order of selection

    Algorithm:
        1. Deduplicate by product ID (keep highest relevance)
        2. Start with highest relevance product
        3. Iteratively add product with best MMR score
        4. MMR = lambda * relevance - (1 - lambda) * max_similarity_to_selected
    """
    if not candidates:
        return []

    if limit <= 0:
        return []

    # Deduplicate by product ID, keeping highest relevance score
    seen_ids: Dict[str, ScoredProduct] = {}
    for c in candidates:
        pid = c.product_id
        # Also check by title as fallback (some products may not have id)
        title = c.product.get('title', c.product.get('name', ''))
        key = pid if pid and pid != str(id(c.product)) else title

        if key not in seen_ids or c.relevance_score > seen_ids[key].relevance_score:
            seen_ids[key] = c

    deduped_candidates = list(seen_ids.values())
    if len(deduped_candidates) < len(candidates):
        logger.info(f"MMR: Deduplicated {len(candidates)} -> {len(deduped_candidates)} unique products")

    # Filter candidates with valid embeddings for MMR
    candidates_with_embeddings = [c for c in deduped_candidates if c.embedding is not None]
    candidates_without_embeddings = [c for c in deduped_candidates if c.embedding is None]

    # If no embeddings, fall back to pure relevance ranking
    if not candidates_with_embeddings:
        logger.warning("No embeddings available for MMR - falling back to relevance ranking")
        sorted_candidates = sorted(candidates, key=lambda x: x.relevance_score, reverse=True)
        return sorted_candidates[:limit]

    selected: List[ScoredProduct] = []
    remaining = candidates_with_embeddings.copy()

    # Step 1: Select highest relevance product first
    remaining.sort(key=lambda x: x.relevance_score, reverse=True)
    selected.append(remaining.pop(0))

    logger.debug(f"MMR: Selected first product with relevance {selected[0].relevance_score:.3f}")

    # Step 2: Iteratively select products with best MMR score
    while len(selected) < limit and remaining:
        best_mmr = float('-inf')
        best_idx = 0

        for idx, candidate in enumerate(remaining):
            # Calculate MMR score
            mmr_score = _calculate_mmr(
                candidate=candidate,
                selected=selected,
                lambda_param=lambda_param,
            )

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = idx

        # Select the best MMR candidate
        best_candidate = remaining.pop(best_idx)
        selected.append(best_candidate)

        logger.debug(
            f"MMR: Selected product {len(selected)} with "
            f"relevance={best_candidate.relevance_score:.3f}, mmr={best_mmr:.3f}"
        )

    # Add candidates without embeddings at the end if needed
    if len(selected) < limit and candidates_without_embeddings:
        candidates_without_embeddings.sort(key=lambda x: x.relevance_score, reverse=True)
        for candidate in candidates_without_embeddings:
            if len(selected) >= limit:
                break
            selected.append(candidate)

    logger.info(f"MMR selection complete: {len(selected)} products selected from {len(candidates)}")
    return selected


def _calculate_mmr(
    candidate: ScoredProduct,
    selected: List[ScoredProduct],
    lambda_param: float,
) -> float:
    """
    Calculate MMR score for a candidate.

    MMR = lambda * relevance - (1 - lambda) * max_similarity_to_selected
    """
    relevance = candidate.relevance_score

    # Calculate max similarity to already selected products
    max_similarity = 0.0

    for selected_product in selected:
        if selected_product.embedding is not None and candidate.embedding is not None:
            similarity = _cosine_similarity(candidate.embedding, selected_product.embedding)
            max_similarity = max(max_similarity, similarity)

    # MMR formula
    mmr = lambda_param * relevance - (1 - lambda_param) * max_similarity

    return mmr


def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    if v1 is None or v2 is None:
        return 0.0

    if v1.size == 0 or v2.size == 0:
        return 0.0

    # Handle dimension mismatch (e.g., 1536-dim semantic vs 1024-dim visual)
    if v1.shape != v2.shape:
        return 0.0

    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


def create_scored_products(
    products: List[Dict[str, Any]],
    relevance_scores: Optional[List[float]] = None,
    embeddings: Optional[List[np.ndarray]] = None,
    score_key: str = 'relevance_score',
    embedding_key: str = 'embedding',
) -> List[ScoredProduct]:
    """
    Create ScoredProduct list from raw product dictionaries.

    Args:
        products: List of product dictionaries
        relevance_scores: Optional list of relevance scores (same order as products)
        embeddings: Optional list of embeddings (same order as products)
        score_key: Key to extract relevance score from product dict if not provided
        embedding_key: Key to extract embedding from product dict if not provided

    Returns:
        List of ScoredProduct objects
    """
    scored_products = []

    for i, product in enumerate(products):
        # Get relevance score
        if relevance_scores and i < len(relevance_scores):
            score = relevance_scores[i]
        else:
            score = product.get(score_key, 0.5)

        # Get embedding
        if embeddings and i < len(embeddings):
            embedding = embeddings[i]
        else:
            embedding_data = product.get(embedding_key)
            if embedding_data is not None:
                embedding = np.array(embedding_data) if not isinstance(embedding_data, np.ndarray) else embedding_data
            else:
                embedding = None

        scored_products.append(ScoredProduct(
            product=product,
            relevance_score=float(score),
            embedding=embedding,
        ))

    return scored_products
