"""
Qdrant Tools for CrewAI Migration
Wraps Qdrant vector search functionality into CrewAI-compatible tools.
"""
import os
import logging
from typing import Dict, List, Any, Optional
from crewai import tool
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

logger = logging.getLogger("crewai.tools.qdrant")


@tool("Search Qdrant Vector Database")
def qdrant_search_tool(
    query_embedding: List[float],
    limit: int = 10,
    filters: Dict[str, Any] = None,
    collection_name: str = None
) -> List[Dict]:
    """
    Search Qdrant for similar products using vector embeddings.

    Args:
        query_embedding: Vector embedding for similarity search
        limit: Maximum results to return
        filters: Optional filters for category, price, etc.
        collection_name: Qdrant collection name (defaults to env var)

    Returns:
        List of similar products with scores

    Example:
        products = qdrant_search_tool(
            query_embedding=[0.1, 0.2, ...],
            limit=5,
            filters={"category": "dress"}
        )
    """
    try:
        # Get Qdrant connection from environment
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection = collection_name or os.getenv("QDRANT_COLLECTION_NAME", "fashion_products")

        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key if qdrant_api_key else None,
            timeout=90  # Increased timeout for cloud Qdrant instances
        )

        # Build Qdrant filters
        qdrant_filter = None
        if filters:
            conditions = []

            if "category" in filters:
                conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=filters["category"])
                    )
                )

            if "min_price" in filters or "max_price" in filters:
                price_range = Range(
                    gte=filters.get("min_price"),
                    lte=filters.get("max_price")
                )
                conditions.append(
                    FieldCondition(key="price", range=price_range)
                )

            if conditions:
                qdrant_filter = Filter(must=conditions)

        # Execute search
        results = client.search(
            collection_name=collection,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=limit,
            with_payload=True
        )

        # Format results
        products = []
        for hit in results:
            product = {
                "id": hit.id,
                "score": hit.score,
                **hit.payload
            }
            products.append(product)

        logger.info(f"Qdrant search returned {len(products)} products")
        return products

    except Exception as e:
        logger.error(f"Qdrant search failed: {e}")
        return []


@tool("Generate Text Embedding")
def embedding_generation_tool(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Generate embedding vector for text query using OpenAI.

    Args:
        text: Text to embed
        model: OpenAI embedding model name

    Returns:
        Embedding vector as list of floats

    Example:
        embedding = embedding_generation_tool("black dress for wedding")
    """
    try:
        import openai

        openai.api_key = os.getenv("OPENAI_API_KEY")

        response = openai.embeddings.create(
            input=text,
            model=model
        )

        embedding = response.data[0].embedding
        logger.info(f"Generated embedding of dimension {len(embedding)}")
        return embedding

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return []


@tool("Hybrid Search Qdrant")
def qdrant_hybrid_search_tool(
    query_text: str,
    limit: int = 10,
    filters: Dict[str, Any] = None
) -> List[Dict]:
    """
    Perform hybrid search combining text embedding and filtering.
    Generates embedding and searches in one step.

    Args:
        query_text: Natural language search query
        limit: Maximum results to return
        filters: Optional filters

    Returns:
        List of similar products

    Example:
        products = qdrant_hybrid_search_tool(
            query_text="elegant black dress",
            limit=5,
            filters={"category": "dress"}
        )
    """
    try:
        # Generate embedding
        embedding = embedding_generation_tool(query_text)

        if not embedding:
            logger.error("Failed to generate embedding")
            return []

        # Search with embedding
        return qdrant_search_tool(embedding, limit, filters)

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return []
