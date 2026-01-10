"""
ARI V3 Pillar 2: Stylist Knowledge

RAG-based retrieval over fashion literature and styling rules.
Provides multi-perspective fashion guidance for the Synthesis LLM.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 2.2
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ari_v3.nlp.fashion_knowledge_v3 import (
    FASHION_KNOWLEDGE_V3,
    CURATION_PRINCIPLES,
    COLOR_THEORY,
    get_knowledge_by_perspective,
    get_knowledge_for_body_type,
    get_knowledge_for_occasion,
)


# Collection name for fashion knowledge in Qdrant
KNOWLEDGE_COLLECTION = "ari_v3_fashion_knowledge"

# Embedding dimension (OpenAI text-embedding-3-small)
EMBEDDING_DIM = 1536


@dataclass
class RetrievedKnowledge:
    """A piece of retrieved fashion knowledge with relevance score."""

    id: str
    content: str
    knowledge_type: str
    perspective: Optional[str]
    relevance_score: float
    metadata: Dict[str, Any]


@dataclass
class StylingContext:
    """Context for retrieving styling rules."""

    query: str
    body_type: Optional[str] = None
    occasion: Optional[str] = None
    style_context: Optional[str] = None
    cultural_background: Optional[str] = None


@dataclass
class MultiPerspectiveResult:
    """Results organized by perspective."""

    traditional: List[RetrievedKnowledge]
    body_neutral: List[RetrievedKnowledge]
    cultural: List[RetrievedKnowledge]
    practical: List[RetrievedKnowledge]

    def get_summary(self, perspective: str) -> str:
        """Get concatenated content for a perspective."""
        results = getattr(self, perspective, [])
        if not results:
            return ""
        return "\n\n".join(r.content for r in results)


class Pillar2_StylistKnowledge:
    """
    V3 Stylist Knowledge Engine.

    Provides RAG retrieval over fashion knowledge with:
    - Multi-perspective content (traditional, body-neutral, cultural, practical)
    - Hybrid search (semantic + keyword + metadata filtering)
    - Body type, occasion, and color guidance
    - The 6 curation principles
    """

    def __init__(
        self,
        qdrant_client=None,
        embedding_service=None,
        collection_name: str = KNOWLEDGE_COLLECTION,
    ):
        """
        Initialize the stylist knowledge engine.

        Args:
            qdrant_client: Qdrant client instance
            embedding_service: Service for computing embeddings
            collection_name: Name of the Qdrant collection
        """
        self.qdrant_client = qdrant_client
        self.embedding_service = embedding_service
        self.collection_name = collection_name

    def _generate_id(self, entry: Dict[str, Any]) -> str:
        """Generate a stable ID for a knowledge entry."""
        content = entry.get("content", "")
        return hashlib.md5(content.encode()).hexdigest()[:16]

    # =========================================================================
    # Ingestion Methods
    # =========================================================================

    async def ingest_knowledge(self, recreate: bool = False) -> int:
        """
        Ingest all fashion knowledge into Qdrant.

        Args:
            recreate: If True, delete and recreate the collection

        Returns:
            Number of entries ingested
        """
        if not self.qdrant_client or not self.embedding_service:
            raise ValueError("Qdrant client and embedding service required for ingestion")

        from qdrant_client.models import Distance, VectorParams, PointStruct

        # Create collection if needed
        if recreate:
            try:
                self.qdrant_client.delete_collection(self.collection_name)
            except Exception:
                pass

        collections = self.qdrant_client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

        # Prepare points
        points = []
        for i, entry in enumerate(FASHION_KNOWLEDGE_V3):
            entry_id = entry.get("id", self._generate_id(entry))
            content = entry.get("content", "")

            if not content:
                continue

            # Generate embedding
            embedding = await self.embedding_service.embed_async(content)

            # Build metadata payload
            payload = {
                "id": entry_id,
                "content": content,
                "type": entry.get("type", ""),
                "perspective": entry.get("perspective", ""),
                "keywords": entry.get("keywords", []),
                "body_type": entry.get("body_type", ""),
                "occasion": entry.get("occasion", ""),
                "category": entry.get("category", ""),
                "style": entry.get("style", ""),
                "silhouette": entry.get("silhouette", ""),
            }

            points.append(
                PointStruct(
                    id=i,
                    vector=embedding.tolist() if hasattr(embedding, "tolist") else embedding,
                    payload=payload,
                )
            )

        # Upsert in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        return len(points)

    # =========================================================================
    # Core Retrieval Methods
    # =========================================================================

    async def query_styling_rules(
        self,
        context: StylingContext,
        limit: int = 5,
    ) -> List[RetrievedKnowledge]:
        """
        Retrieve styling rules relevant to the given context.

        Uses hybrid search: semantic similarity + metadata filtering.

        Args:
            context: Styling context with query and filters
            limit: Maximum results to return

        Returns:
            List of relevant knowledge entries
        """
        results: List[RetrievedKnowledge] = []

        # Try vector search if Qdrant available
        if self.qdrant_client and self.embedding_service:
            results = await self._vector_search(context.query, limit, context)
        else:
            # Fallback to keyword-based retrieval
            results = self._keyword_search(context, limit)

        return results

    async def retrieve_multiple_perspectives(
        self,
        query: str,
        topic: Optional[str] = None,
        user_cultural_context: Optional[str] = None,
        limit_per_perspective: int = 2,
    ) -> MultiPerspectiveResult:
        """
        Retrieve knowledge from all four perspectives.

        Args:
            query: Search query
            topic: Topic to filter by (body_type, color, occasion, silhouette)
            user_cultural_context: User's cultural background for relevance
            limit_per_perspective: Max results per perspective

        Returns:
            MultiPerspectiveResult with organized knowledge
        """
        perspectives = self.get_perspectives()
        result = MultiPerspectiveResult(
            traditional=[],
            body_neutral=[],
            cultural=[],
            practical=[],
        )

        for perspective in perspectives:
            if self.qdrant_client and self.embedding_service:
                # Vector search with perspective filter
                knowledge = await self._vector_search_with_perspective(
                    query=query,
                    perspective=perspective,
                    limit=limit_per_perspective,
                )
            else:
                # Keyword fallback with perspective filter
                knowledge = self._keyword_search_perspective(
                    query=query,
                    perspective=perspective,
                    limit=limit_per_perspective,
                )

            setattr(result, perspective, knowledge)

        return result

    def get_body_type_rules(
        self,
        body_type: str,
        category: Optional[str] = None,
    ) -> List[RetrievedKnowledge]:
        """
        Get styling rules for a specific body type.

        Args:
            body_type: Body type (hourglass, rectangle, pear, apple)
            category: Optional category filter (tops, bottoms, etc.)

        Returns:
            List of relevant body type guidance
        """
        entries = get_knowledge_for_body_type(body_type)

        results = []
        for entry in entries:
            results.append(
                RetrievedKnowledge(
                    id=entry.get("id", ""),
                    content=entry.get("content", ""),
                    knowledge_type=entry.get("type", ""),
                    perspective=entry.get("perspective"),
                    relevance_score=1.0,
                    metadata={
                        "body_type": entry.get("body_type"),
                        "keywords": entry.get("keywords", []),
                    },
                )
            )

        return results

    def get_occasion_rules(self, occasion: str) -> List[RetrievedKnowledge]:
        """
        Get styling rules for a specific occasion.

        Args:
            occasion: Occasion type (professional, wedding, casual, date)

        Returns:
            List of relevant occasion guidance
        """
        entries = get_knowledge_for_occasion(occasion)

        results = []
        for entry in entries:
            results.append(
                RetrievedKnowledge(
                    id=entry.get("id", ""),
                    content=entry.get("content", ""),
                    knowledge_type=entry.get("type", ""),
                    perspective=entry.get("perspective"),
                    relevance_score=1.0,
                    metadata={
                        "occasion": entry.get("occasion"),
                        "keywords": entry.get("keywords", []),
                    },
                )
            )

        return results

    def get_curation_principles(self) -> List[RetrievedKnowledge]:
        """
        Get the 6 curation principles.

        Returns:
            List of curation principle entries
        """
        results = []
        for entry in CURATION_PRINCIPLES:
            results.append(
                RetrievedKnowledge(
                    id=entry.get("id", ""),
                    content=entry.get("content", ""),
                    knowledge_type="curation_principle",
                    perspective=None,
                    relevance_score=1.0,
                    metadata={
                        "name": entry.get("name"),
                        "keywords": entry.get("keywords", []),
                    },
                )
            )
        return results

    def get_color_guidance(
        self,
        undertone: Optional[str] = None,
    ) -> List[RetrievedKnowledge]:
        """
        Get color theory guidance.

        Args:
            undertone: Optional filter by undertone (warm, cool, neutral)

        Returns:
            List of color theory entries
        """
        results = []
        for entry in COLOR_THEORY:
            if undertone:
                category = entry.get("category", "")
                if undertone.lower() not in category.lower() and category != "all":
                    continue

            results.append(
                RetrievedKnowledge(
                    id=entry.get("id", ""),
                    content=entry.get("content", ""),
                    knowledge_type="color_theory",
                    perspective=entry.get("perspective"),
                    relevance_score=1.0,
                    metadata={
                        "category": entry.get("category"),
                        "keywords": entry.get("keywords", []),
                    },
                )
            )

        return results

    # =========================================================================
    # Search Implementations
    # =========================================================================

    async def _vector_search(
        self,
        query: str,
        limit: int,
        context: Optional[StylingContext] = None,
    ) -> List[RetrievedKnowledge]:
        """Perform vector similarity search with optional filters."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Generate query embedding
        query_embedding = await self.embedding_service.embed_async(query)
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        # Build filters
        filter_conditions = []

        if context:
            if context.body_type:
                filter_conditions.append(
                    FieldCondition(
                        key="body_type",
                        match=MatchValue(value=context.body_type),
                    )
                )
            if context.occasion:
                filter_conditions.append(
                    FieldCondition(
                        key="occasion",
                        match=MatchValue(value=context.occasion),
                    )
                )

        query_filter = None
        if filter_conditions:
            # Use 'should' (OR logic) to broaden search - most entries have only
            # body_type OR occasion, not both. This ensures we get relevant results
            # from both body-type-specific and occasion-specific knowledge.
            query_filter = Filter(should=filter_conditions)

        # Search
        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=limit,
        )

        # Convert to RetrievedKnowledge
        results = []
        for hit in search_results:
            payload = hit.payload
            results.append(
                RetrievedKnowledge(
                    id=payload.get("id", ""),
                    content=payload.get("content", ""),
                    knowledge_type=payload.get("type", ""),
                    perspective=payload.get("perspective"),
                    relevance_score=hit.score,
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ["id", "content", "type", "perspective"]
                    },
                )
            )

        return results

    async def _vector_search_with_perspective(
        self,
        query: str,
        perspective: str,
        limit: int,
    ) -> List[RetrievedKnowledge]:
        """Vector search filtered by perspective."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_embedding = await self.embedding_service.embed_async(query)
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        query_filter = Filter(
            must=[
                FieldCondition(
                    key="perspective",
                    match=MatchValue(value=perspective),
                )
            ]
        )

        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=limit,
        )

        results = []
        for hit in search_results:
            payload = hit.payload
            results.append(
                RetrievedKnowledge(
                    id=payload.get("id", ""),
                    content=payload.get("content", ""),
                    knowledge_type=payload.get("type", ""),
                    perspective=payload.get("perspective"),
                    relevance_score=hit.score,
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ["id", "content", "type", "perspective"]
                    },
                )
            )

        return results

    def _keyword_search(
        self,
        context: StylingContext,
        limit: int,
    ) -> List[RetrievedKnowledge]:
        """Fallback keyword-based search when Qdrant unavailable."""
        # Extract keywords from query
        query_words = context.query.lower().split()

        # Score each entry
        scored_entries = []
        for entry in FASHION_KNOWLEDGE_V3:
            score = 0.0

            # Keyword matching
            entry_keywords = [k.lower() for k in entry.get("keywords", [])]
            content_lower = entry.get("content", "").lower()

            for word in query_words:
                if word in entry_keywords:
                    score += 2.0
                elif word in content_lower:
                    score += 1.0

            # Metadata matching
            if context.body_type and entry.get("body_type") == context.body_type:
                score += 3.0
            if context.occasion and entry.get("occasion") == context.occasion:
                score += 3.0

            if score > 0:
                scored_entries.append((entry, score))

        # Sort by score and limit
        scored_entries.sort(key=lambda x: x[1], reverse=True)
        top_entries = scored_entries[:limit]

        # Convert to RetrievedKnowledge
        results = []
        for entry, score in top_entries:
            results.append(
                RetrievedKnowledge(
                    id=entry.get("id", ""),
                    content=entry.get("content", ""),
                    knowledge_type=entry.get("type", ""),
                    perspective=entry.get("perspective"),
                    relevance_score=score / 10.0,  # Normalize
                    metadata={
                        k: v
                        for k, v in entry.items()
                        if k not in ["id", "content", "type", "perspective"]
                    },
                )
            )

        return results

    def _keyword_search_perspective(
        self,
        query: str,
        perspective: str,
        limit: int,
    ) -> List[RetrievedKnowledge]:
        """Keyword search filtered by perspective."""
        query_words = query.lower().split()

        # Filter by perspective first
        perspective_entries = get_knowledge_by_perspective(perspective)

        scored_entries = []
        for entry in perspective_entries:
            score = 0.0

            entry_keywords = [k.lower() for k in entry.get("keywords", [])]
            content_lower = entry.get("content", "").lower()

            for word in query_words:
                if word in entry_keywords:
                    score += 2.0
                elif word in content_lower:
                    score += 1.0

            if score > 0:
                scored_entries.append((entry, score))

        scored_entries.sort(key=lambda x: x[1], reverse=True)
        top_entries = scored_entries[:limit]

        results = []
        for entry, score in top_entries:
            results.append(
                RetrievedKnowledge(
                    id=entry.get("id", ""),
                    content=entry.get("content", ""),
                    knowledge_type=entry.get("type", ""),
                    perspective=entry.get("perspective"),
                    relevance_score=score / 10.0,
                    metadata={
                        k: v
                        for k, v in entry.items()
                        if k not in ["id", "content", "type", "perspective"]
                    },
                )
            )

        return results

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def get_knowledge_count(self) -> int:
        """Get total number of knowledge entries."""
        return len(FASHION_KNOWLEDGE_V3)

    def get_knowledge_types(self) -> List[str]:
        """Get list of all knowledge types."""
        types = set()
        for entry in FASHION_KNOWLEDGE_V3:
            if entry.get("type"):
                types.add(entry["type"])
        return list(types)

    def get_perspectives(self) -> List[str]:
        """Get list of all perspectives."""
        return ["traditional", "body_neutral", "cultural", "practical"]
