"""
FashionSigLIP Tools for CrewAI Migration
Wraps visual embedding functionality into CrewAI-compatible tools.
"""
import os
import logging
from typing import Dict, List, Any
from crewai.tools import tool

logger = logging.getLogger("crewai.tools.fashionsig")


@tool("Generate FashionSigLIP Image Embedding")
def fashionsig_embedding_tool(image_path: str) -> List[float]:
    """
    Generate visual embedding using FashionSigLIP model.

    Args:
        image_path: Path to product image or image URL

    Returns:
        Visual embedding vector

    Example:
        embedding = fashionsig_embedding_tool("/path/to/dress.jpg")
    """
    try:
        # Import FashionSigLIP encoder from existing services
        from services.ml.fashionsig_encoder import get_fashionsig_encoder
        import asyncio

        logger.info(f"Generating FashionSigLIP embedding for {image_path}")

        # Get singleton encoder instance
        encoder = get_fashionsig_encoder()

        # Encoder's encode_image is async, so we need to run it in event loop
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in async context, but this is a sync tool, so we can't await
            # Create a new task that will run in the background
            logger.warning("Running async encoder in sync context - may block")
            embedding = loop.run_until_complete(encoder.encode_image(image_path))
        except RuntimeError:
            # No running loop, create one
            embedding = asyncio.run(encoder.encode_image(image_path))

        # Convert numpy array to list
        return embedding.tolist()

    except ImportError as e:
        logger.error(f"Failed to import FashionSigLIP encoder: {e}")
        logger.warning("FashionSigLIP integration pending")
        return []
    except Exception as e:
        logger.error(f"FashionSigLIP embedding generation failed: {e}")
        return []


@tool("Visual Similarity Search")
def visual_similarity_search_tool(
    image_path: str,
    limit: int = 10,
    filters: Dict[str, Any] = None
) -> List[Dict]:
    """
    Find visually similar products using FashionSigLIP embeddings.

    Args:
        image_path: Path to reference image
        limit: Maximum results
        filters: Optional filters

    Returns:
        List of visually similar products

    Example:
        similar = visual_similarity_search_tool(
            image_path="/path/to/reference.jpg",
            limit=5
        )
    """
    try:
        # Generate visual embedding
        embedding = fashionsig_embedding_tool(image_path)

        if not embedding:
            logger.error("Failed to generate visual embedding")
            return []

        # Search Qdrant with visual embedding
        from tools.qdrant_tools import qdrant_search_tool

        results = qdrant_search_tool(
            query_embedding=embedding,
            limit=limit,
            filters=filters,
            collection_name="fashion_visual_embeddings"
        )

        logger.info(f"Visual search returned {len(results)} similar products")
        return results

    except Exception as e:
        logger.error(f"Visual similarity search failed: {e}")
        return []


@tool("Multi-Image Visual Search")
def multi_image_search_tool(
    image_paths: List[str],
    limit: int = 10,
    filters: Dict[str, Any] = None
) -> List[Dict]:
    """
    Find products similar to multiple reference images.
    Averages embeddings for multi-image queries.

    Args:
        image_paths: List of reference image paths
        limit: Maximum results
        filters: Optional filters

    Returns:
        List of products matching multiple visual references

    Example:
        products = multi_image_search_tool(
            image_paths=["/path/img1.jpg", "/path/img2.jpg"],
            limit=5
        )
    """
    try:
        embeddings = []

        # Generate embedding for each image
        for image_path in image_paths:
            embedding = fashionsig_embedding_tool(image_path)
            if embedding:
                embeddings.append(embedding)

        if not embeddings:
            logger.error("Failed to generate any embeddings")
            return []

        # Average embeddings
        import numpy as np
        avg_embedding = np.mean(embeddings, axis=0).tolist()

        # Search with averaged embedding
        from tools.qdrant_tools import qdrant_search_tool

        results = qdrant_search_tool(
            query_embedding=avg_embedding,
            limit=limit,
            filters=filters,
            collection_name="fashion_visual_embeddings"
        )

        logger.info(f"Multi-image search returned {len(results)} products")
        return results

    except Exception as e:
        logger.error(f"Multi-image search failed: {e}")
        return []
