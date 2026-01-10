"""
ARI V3 NLP - Fashion Knowledge for RAG
"""

from .fashion_knowledge_v3 import (
    FASHION_KNOWLEDGE_V3,
    CURATION_PRINCIPLES,
    BODY_TYPE_GUIDANCE,
    COLOR_THEORY,
    OCCASION_GUIDANCE,
    SILHOUETTE_GUIDANCE,
    get_knowledge_by_type,
    get_knowledge_by_perspective,
    get_all_knowledge_texts,
    get_knowledge_for_body_type,
    get_knowledge_for_occasion,
    search_knowledge_by_keywords,
)

__all__ = [
    "FASHION_KNOWLEDGE_V3",
    "CURATION_PRINCIPLES",
    "BODY_TYPE_GUIDANCE",
    "COLOR_THEORY",
    "OCCASION_GUIDANCE",
    "SILHOUETTE_GUIDANCE",
    "get_knowledge_by_type",
    "get_knowledge_by_perspective",
    "get_all_knowledge_texts",
    "get_knowledge_for_body_type",
    "get_knowledge_for_occasion",
    "search_knowledge_by_keywords",
]
