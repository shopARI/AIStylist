"""
Visual Embeddings Qdrant Client Service
Handles FashionSigLIP visual similarity search using Qdrant vector database
"""

import os
import logging
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid
import hashlib

# Qdrant client
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)

class VisualQdrantClient:
    """Qdrant client for visual similarity search using FashionSigLIP embeddings"""

    def __init__(self):
        self.client = None
        self.collection_name = "fashion_fashionsig_768d"  # FashionSigLIP collection
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Qdrant client"""
        try:
            self.client = QdrantClient(
                url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                api_key=os.getenv("QDRANT_API_KEY"),
                prefer_grpc=False  # Use HTTP to avoid gRPC issues
            )

            # Test connection
            collections = self.client.get_collections().collections
            logger.info(f"Success Visual Qdrant client connected ({len(collections)} collections)")

            # Check if our collection exists
            collection_exists = any(c.name == self.collection_name for c in collections)
            if collection_exists:
                logger.info(f"Success FashionSigLIP collection '{self.collection_name}' found")
            else:
                logger.warning(f"Warning  FashionSigLIP collection '{self.collection_name}' not found")

        except Exception as e:
            logger.error(f"Error Visual Qdrant client initialization failed: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if the visual Qdrant client is available"""
        return self.client is not None

    async def visual_similarity_search(
        self,
        image_embedding: np.ndarray = None,
        text_embedding: np.ndarray = None,
        combined_embedding: np.ndarray = None,
        search_type: str = "combined",  # "image", "text", "combined"
        limit: int = 10,
        score_threshold: float = 0.7,
        product_filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform visual similarity search using FashionSigLIP embeddings

        Args:
            image_embedding: Image embedding vector (768-dim)
            text_embedding: Text embedding vector (768-dim)
            combined_embedding: Combined embedding vector (1536-dim)
            search_type: Type of search ("image", "text", "combined")
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            product_filters: Additional filters to apply

        Returns:
            List of similar products with scores and metadata
        """
        if not self.is_available():
            logger.error("Error Visual Qdrant client not available")
            return []

        try:
            # Determine query vector based on search type
            if search_type == "combined" and combined_embedding is not None:
                query_vector = combined_embedding.flatten().tolist()
                vector_name = "combined"
            elif search_type == "image" and image_embedding is not None:
                query_vector = image_embedding.flatten().tolist()
                vector_name = "image"
            elif search_type == "text" and text_embedding is not None:
                query_vector = text_embedding.flatten().tolist()
                vector_name = "text"
            else:
                # If no embeddings provided, return a sample of all products
                logger.warning(f"Warning  No embeddings provided for {search_type} search, returning sample products")
                try:
                    # Get a scroll of sample products instead
                    scroll_result = self.client.scroll(
                        collection_name=self.collection_name,
                        limit=limit,
                        with_payload=True,
                        with_vectors=False
                    )

                    results = []
                    for point in scroll_result[0]:  # scroll returns (points, next_page_offset)
                        product_data = {
                            "product_id": point.payload.get("product_id"),
                            "title": point.payload.get("title", "Unknown Product"),
                            "text_content": point.payload.get("text_content", ""),
                            "image_url": point.payload.get("image_url"),
                            "image_size": point.payload.get("image_size"),
                            "similarity_score": 1.0,  # No similarity computed
                            "point_id": str(point.id),
                            "model_used": point.payload.get("model_used", "unknown"),
                            "embedding_dims": point.payload.get("embedding_dims"),
                            "timestamp": point.payload.get("timestamp"),
                            "search_type": "sample"
                        }
                        results.append(product_data)

                    logger.info(f"Success Retrieved {len(results)} sample products")
                    return results
                except Exception as scroll_error:
                    logger.error(f"Error Failed to get sample products: {scroll_error}")
                    return []

            # Build filters
            query_filter = None
            if product_filters:
                conditions = []
                for field, value in product_filters.items():
                    conditions.append(FieldCondition(key=field, match=MatchValue(value=value)))
                if conditions:
                    query_filter = Filter(must=conditions)

            logger.info(f"Search Performing {search_type} similarity search (limit={limit}, threshold={score_threshold})")

            # Execute search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=query_filter,
                with_payload=True,
                with_vectors=False  # Don't return vectors to save bandwidth
            )

            # Format results
            results = []
            for result in search_results:
                product_data = {
                    "product_id": result.payload.get("product_id"),
                    "title": result.payload.get("title", "Unknown Product"),
                    "text_content": result.payload.get("text_content", ""),
                    "image_url": result.payload.get("image_url"),
                    "image_size": result.payload.get("image_size"),
                    "similarity_score": float(result.score),
                    "point_id": str(result.id),
                    "model_used": result.payload.get("model_used", "unknown"),
                    "embedding_dims": result.payload.get("embedding_dims"),
                    "timestamp": result.payload.get("timestamp"),
                    "search_type": search_type
                }
                results.append(product_data)

            logger.info(f"Success Visual search found {len(results)} similar products")
            return results

        except Exception as e:
            logger.error(f"Error Visual similarity search failed: {e}")
            return []

    async def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the visual embeddings collection"""
        if not self.is_available():
            return {"error": "Client not available"}

        try:
            collection_info = self.client.get_collection(self.collection_name)

            return {
                "collection_name": self.collection_name,
                "points_count": collection_info.points_count,
                "vectors_config": collection_info.config.params.vectors,
                "status": collection_info.status,
                "optimizer_status": collection_info.optimizer_status
            }

        except Exception as e:
            logger.error(f"Error Failed to get collection info: {e}")
            return {"error": str(e)}

    async def add_visual_embedding(
        self,
        product_id: str,
        image_embedding: np.ndarray,
        text_embedding: np.ndarray,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add a visual embedding to the collection

        Args:
            product_id: Unique product identifier
            image_embedding: Image embedding vector (768-dim)
            text_embedding: Text embedding vector (768-dim)
            metadata: Additional product metadata

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            logger.error("Error Visual Qdrant client not available")
            return False

        try:
            # Create combined embedding
            combined_embedding = np.concatenate([
                image_embedding.flatten(),
                text_embedding.flatten()
            ])

            # Generate unique point ID
            unique_string = f"{product_id}_img_{metadata.get('image_index', 0)}"
            hash_object = hashlib.md5(unique_string.encode())
            point_id = str(uuid.UUID(hash_object.hexdigest()))

            # Create point
            point = PointStruct(
                id=point_id,
                vector={
                    "image": image_embedding.flatten().tolist(),
                    "text": text_embedding.flatten().tolist(),
                    "combined": combined_embedding.tolist()
                },
                payload={
                    "product_id": product_id,
                    "title": metadata.get("title", ""),
                    "text_content": metadata.get("text_content", ""),
                    "image_url": metadata.get("image_url", ""),
                    "image_size": metadata.get("image_size", ""),
                    "model_used": "marqo_fashionsig",
                    "embedding_dims": len(image_embedding.flatten()),
                    "timestamp": datetime.now().isoformat(),
                    **metadata  # Include any additional metadata
                }
            )

            # Upload to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            logger.info(f"Success Added visual embedding for product {product_id}")
            return True

        except Exception as e:
            logger.error(f"Error Failed to add visual embedding: {e}")
            return False

# Global instance
visual_qdrant_client = VisualQdrantClient()