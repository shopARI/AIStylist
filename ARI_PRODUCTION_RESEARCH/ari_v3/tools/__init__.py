"""
ARI V3 Tools - Database and Vector Operations

Async tools for Neo4j, Qdrant, and FashionSigLIP operations.
These are reused from V2 (ari_crewai_migration) with updated imports.

Note: These are CrewAI @tool decorated functions for agent use.
For direct use, import the internal _functions.
"""

# Neo4j tools
from ari_v3.tools.neo4j_tools import (
    async_neo4j_query_tool,
    async_semantic_expansion_tool,
    async_neo4j_fulltext_search_tool,
)

# Qdrant tools
from ari_v3.tools.qdrant_tools import (
    async_qdrant_search_tool,
    async_embedding_generation_tool,
    async_qdrant_hybrid_search_tool,
    async_qdrant_filter_search_tool,
    # Internal functions for other tools
    _search_qdrant,
    _generate_embedding,
)

# FashionSigLIP tools
from ari_v3.tools.fashionsig_tools import (
    async_fashionsig_embedding_tool,
    async_visual_similarity_search_tool,
    async_multi_image_search_tool,
    async_fashionsig_multimodal_search_tool,
)

__all__ = [
    # Neo4j
    "async_neo4j_query_tool",
    "async_semantic_expansion_tool",
    "async_neo4j_fulltext_search_tool",
    # Qdrant
    "async_qdrant_search_tool",
    "async_embedding_generation_tool",
    "async_qdrant_hybrid_search_tool",
    "async_qdrant_filter_search_tool",
    "_search_qdrant",
    "_generate_embedding",
    # FashionSigLIP
    "async_fashionsig_embedding_tool",
    "async_visual_similarity_search_tool",
    "async_multi_image_search_tool",
    "async_fashionsig_multimodal_search_tool",
]
