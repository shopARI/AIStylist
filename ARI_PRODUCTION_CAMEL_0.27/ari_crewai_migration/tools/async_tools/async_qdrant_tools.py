"""
Async Qdrant Tools for CrewAI - Non-blocking vector search operations.
Phase 2: True async tools using AsyncQdrantClient.
"""
import os
import logging
from typing import Dict, List, Any, Optional
from crewai.tools import tool
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

logger = logging.getLogger("crewai.tools.async_qdrant")


# ============================================================================
# CORE IMPLEMENTATION FUNCTIONS (no @tool decorator)
# These can be called internally by other functions
# ============================================================================

async def _search_qdrant(
    query_embedding: List[float],
    limit: int = 10,
    filters: Dict[str, Any] = None,
    collection_name: str = None
) -> List[Dict]:
    """
    Core implementation: Search Qdrant vector database (internal use).
    """
    client = None
    try:
        # Get Qdrant connection from environment
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection = collection_name or os.getenv("QDRANT_COLLECTION_NAME", "fashion_products")

        client = AsyncQdrantClient(
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

        # Execute async search
        results = await client.search(
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

        logger.info(f"Async Qdrant search returned {len(products)} products")
        return products

    except Exception as e:
        logger.error(f"Async Qdrant search failed: {e}")
        return []
    finally:
        if client:
            await client.close()


async def _generate_embedding(text: str, model: str = "text-embedding-ada-002") -> List[float]:
    """
    Core implementation: Generate text embedding using OpenAI (internal use).
    ✅ Using text-embedding-ada-002 to match Qdrant collection embeddings.
    """
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = await client.embeddings.create(
            input=text,
            model=model
        )

        embedding = response.data[0].embedding
        logger.info(f"Generated async embedding of dimension {len(embedding)}")
        return embedding

    except Exception as e:
        logger.error(f"Async embedding generation failed: {e}")
        return []


# ============================================================================
# TOOL WRAPPERS (with @tool decorator)
# These are exposed to CrewAI agents
# ============================================================================

@tool("Search Qdrant Vector Database (Async)")
async def async_qdrant_search_tool(
    query_embedding: List[float],
    limit: int = 10,
    filters: Dict[str, Any] = None,
    collection_name: str = None
) -> List[Dict]:
    """
    Search Qdrant for similar products using vector embeddings (async, non-blocking).

    Args:
        query_embedding: Vector embedding for similarity search
        limit: Maximum results to return
        filters: Optional filters for category, price, etc.
        collection_name: Qdrant collection name (defaults to env var)

    Returns:
        List of similar products with scores

    Example:
        products = await async_qdrant_search_tool(
            query_embedding=[0.1, 0.2, ...],
            limit=5,
            filters={"category": "dress"}
        )
    """
    return await _search_qdrant(query_embedding, limit, filters, collection_name)


@tool("Generate Text Embedding (Async)")
async def async_embedding_generation_tool(text: str, model: str = "text-embedding-ada-002") -> List[float]:
    """
    Generate embedding vector for text query using OpenAI (async, non-blocking).
    ✅ Using text-embedding-ada-002 to match Qdrant collection embeddings.

    Args:
        text: Text to embed
        model: OpenAI embedding model name

    Returns:
        Embedding vector as list of floats

    Example:
        embedding = await async_embedding_generation_tool("black dress for wedding")
    """
    return await _generate_embedding(text, model)


@tool("Hybrid Search Qdrant (Async)")
async def async_qdrant_hybrid_search_tool(
    query_text: str,
    limit: int = 10,
    filters: Dict[str, Any] = None,
    collection_name: str = None
) -> List[Dict]:
    """
    Perform hybrid search combining text embedding and filtering (async, non-blocking).
    Generates embedding and searches in one step.

    Args:
        query_text: Natural language search query
        limit: Maximum results to return
        filters: Optional filters
        collection_name: Qdrant collection name (defaults to env var)

    Returns:
        List of similar products

    Example:
        products = await async_qdrant_hybrid_search_tool(
            query_text="elegant black dress",
            limit=5,
            filters={"category": "dress"}
        )
    """
    try:
        # Generate embedding asynchronously (use internal function)
        embedding = await _generate_embedding(query_text)

        if not embedding:
            logger.error("Failed to generate async embedding")
            return []

        # Search with embedding asynchronously (use internal function)
        return await _search_qdrant(embedding, limit, filters, collection_name)

    except Exception as e:
        logger.error(f"Async hybrid search failed: {e}")
        return []


@tool("Qdrant Filter Search (Async)")
async def async_qdrant_filter_search_tool(
    filters: Dict[str, Any],
    limit: int = 10,
    collection_name: str = None
) -> List[Dict]:
    """
    Search Qdrant using only filters (no vector similarity) - async, non-blocking.
    Useful for category browsing, price range queries, etc.

    Args:
        filters: Required filters (category, price, brand, etc.)
        limit: Maximum results to return
        collection_name: Qdrant collection name (defaults to env var)

    Returns:
        List of filtered products

    Example:
        products = await async_qdrant_filter_search_tool(
            filters={"category": "dress", "min_price": 50, "max_price": 200},
            limit=10
        )
    """
    client = None
    try:
        # Get Qdrant connection from environment
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection = collection_name or os.getenv("QDRANT_COLLECTION_NAME", "fashion_products")

        client = AsyncQdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key if qdrant_api_key else None,
            timeout=90
        )

        # Build Qdrant filters
        conditions = []

        if "category" in filters:
            conditions.append(
                FieldCondition(
                    key="category",
                    match=MatchValue(value=filters["category"])
                )
            )

        if "brand" in filters:
            conditions.append(
                FieldCondition(
                    key="brand",
                    match=MatchValue(value=filters["brand"])
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

        if not conditions:
            logger.warning("No filters provided for filter-only search")
            return []

        qdrant_filter = Filter(must=conditions)

        # Scroll through filtered results (no vector search)
        results = await client.scroll(
            collection_name=collection,
            scroll_filter=qdrant_filter,
            limit=limit,
            with_payload=True
        )

        # Format results (scroll returns tuple: (points, next_page_offset))
        points, _ = results
        products = []
        for point in points:
            product = {
                "id": point.id,
                **point.payload
            }
            products.append(product)

        logger.info(f"Async Qdrant filter search returned {len(products)} products")
        return products

    except Exception as e:
        logger.error(f"Async Qdrant filter search failed: {e}")
        return []
    finally:
        if client:
            await client.close()
