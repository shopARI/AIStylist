"""
ARI V3 Pillars - Knowledge Sources

The three pillars provide the knowledge for navigation:
1. Pillar 1: Personalization - Raw user data from Neo4j User Graph
2. Pillar 2: Stylist Knowledge - RAG over fashion literature
3. Pillar 3: User Activity - Behavioral patterns from interaction history
"""

from .personalization import (
    Pillar1_Personalization,
    QueryContext,
    MIN_INTERACTIONS_FOR_POSITION,
    MIN_INTERACTIONS_FOR_TRAJECTORY,
    RECENT_DAYS,
    CONFIDENCE_SCALE,
)

from .stylist_knowledge import (
    Pillar2_StylistKnowledge,
    RetrievedKnowledge,
    StylingContext,
    MultiPerspectiveResult,
    KNOWLEDGE_COLLECTION,
)

__all__ = [
    # Pillar 1
    "Pillar1_Personalization",
    "QueryContext",
    "MIN_INTERACTIONS_FOR_POSITION",
    "MIN_INTERACTIONS_FOR_TRAJECTORY",
    "RECENT_DAYS",
    "CONFIDENCE_SCALE",
    # Pillar 2
    "Pillar2_StylistKnowledge",
    "RetrievedKnowledge",
    "StylingContext",
    "MultiPerspectiveResult",
    "KNOWLEDGE_COLLECTION",
]
