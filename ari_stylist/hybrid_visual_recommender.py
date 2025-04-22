"""
Hybrid Visual Recommendation System for AI Stylist.

This module implements a recommendation system that combines content-based
and visual similarity approaches for fashion recommendations.
Compatible with CAMEL-AI 0.2.43.
"""

import logging
import os
import tempfile
import json
from typing import List, Dict, Any, Optional, Tuple
from urllib.request import urlretrieve

try:
    # Optional deep learning dependencies
    import numpy as np
    import tensorflow as tf
    from tensorflow.keras.applications.resnet50 import ResNet50, preprocess_input
    from tensorflow.keras.preprocessing import image
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logging.warning("TensorFlow not installed. Visual similarity will be limited.")

from camel.retrievers import AutoRetriever
from camel.types import StorageType
from camel.embeddings import OpenAIEmbedding
from camel.types import EmbeddingModelType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hybrid_visual_recommender")

class HybridVisualRecommender:
    """
    Implements a hybrid recommendation system combining content-based filtering
    and visual similarity for fashion recommendations.
    """
    
    def __init__(
        self, 
        product_kg, 
        embedding_model=None,
        image_model_path=None,
        storage_path="product_data/visual_embeddings"
    ):
        """
        Initialize the hybrid visual recommender.
        
        Args:
            product_kg: Neo4j product knowledge graph instance
            embedding_model: CAMEL embedding model (optional)
            image_model_path: Path to saved image model (optional)
            storage_path: Path to store vector embeddings
        """
        logger.info("Initializing HybridVisualRecommender")
        self.product_kg = product_kg
        
        # Initialize embedding model
        try:
            self.embedding_model = embedding_model or OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_3_SMALL
            )
            logger.info("Text embedding model initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing text embedding model: {e}")
            self.embedding_model = None
            logger.warning("Text embeddings not available")
        
        # Initialize CAMEL retriever for text-based search
        try:
            self.auto_retriever = AutoRetriever(
                vector_storage_local_path=storage_path,
                storage_type=StorageType.QDRANT,
                embedding_model=self.embedding_model
            )
            logger.info("AutoRetriever initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing AutoRetriever: {e}")
            self.auto_retriever = None
            logger.warning("AutoRetriever not available")
        
        # Initialize image model if TensorFlow is available
        self.image_model = None
        if TENSORFLOW_AVAILABLE:
            try:
                if image_model_path and os.path.exists(image_model_path):
                    # Load saved model
                    self.image_model = tf.keras.models.load_model(image_model_path)
                else:
                    # Initialize ResNet50 model
                    base_model = ResNet50(weights='imagenet', include_top=False, pooling='avg')
                    self.image_model = tf.keras.Model(inputs=base_model.input, outputs=base_model.output)
                
                logger.info("Image model initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing image model: {e}")
                self.image_model = None
                logger.warning("Image model not available")
    
    def _get_image_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate embedding for an image.
        
        Args:
            image_url: URL of the image
            
        Returns:
            Image embedding or None if not available
        """
        if not TENSORFLOW_AVAILABLE or self.image_model is None:
            return None
            
        try:
            # Download image to temporary file
            temp_file, _ = urlretrieve(image_url)
            
            # Load and preprocess image
            img = image.load_img(temp_file, target_size=(224, 224))
            img_array = image.img_to_array(img)
            img_array = np.expand_dims(img_array, axis=0)
            img_array = preprocess_input(img_array)
            
            # Generate embedding
            embedding = self.image_model.predict(img_array)[0].tolist()
            
            # Clean up temporary file
            os.unlink(temp_file)
            
            return embedding
        except Exception as e:
            logger.error(f"Error generating image embedding: {e}")
            return None
    
    def _get_text_embedding(self, product: Dict[str, Any]) -> Optional[List[float]]:
        """
        Generate text embedding for a product.
        
        Args:
            product: Product dictionary
            
        Returns:
            Text embedding or None if not available
        """
        if self.embedding_model is None:
            return None
            
        try:
            # Create text representation
            title = product.get('title', '')
            description = product.get('description', '')
            categories = ' '.join(product.get('categories', []))
            tags = ' '.join(product.get('tags', []))
            
            text = f"{title}. {description}. Categories: {categories}. Tags: {tags}."
            
            # Generate embedding
            embedding = self.embedding_model.embed(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating text embedding: {e}")
            return None
    
    def index_product_images(self, products: List[Dict[str, Any]]) -> int:
        """
        Index product images and text for retrieval.
        
        Args:
            products: List of product dictionaries
            
        Returns:
            Number of products indexed
        """
        if self.auto_retriever is None:
            logger.warning("AutoRetriever not available for indexing")
            return 0
            
        indexed_count = 0
        
        for product in products:
            try:
                # Get image URLs
                image_urls = product.get('images', [])
                if not image_urls:
                    continue
                    
                # Use the first image for indexing
                image_url = image_urls[0] if isinstance(image_urls, list) else image_urls
                
                # Skip if image URL is not valid
                if not image_url or not isinstance(image_url, str):
                    continue
                
                # Create document content
                title = product.get('title', '')
                description = product.get('description', '')
                categories = ', '.join(product.get('categories', []))
                tags = ', '.join(product.get('tags', []))
                
                content = f"Product: {title}. Description: {description}. Categories: {categories}. Tags: {tags}."
                
                # Create document for the auto-retriever
                document = {
                    "id": product.get("id"),
                    "content": content,
                    "metadata": {
                        "image_url": image_url,
                        "product_id": product.get("id"),
                        "categories": product.get("categories", []),
                        "tags": product.get("tags", []),
                        "price": product.get("price", 0)
                    }
                }
                
                # Index the document
                self.auto_retriever.add_document(document)
                indexed_count += 1
                
                # Generate and store image embedding if available
                if self.image_model and image_url:
                    image_embedding = self._get_image_embedding(image_url)
                    if image_embedding:
                        # Store image embedding in Neo4j
                        query = """
                        MATCH (p:Product {id: $id})
                        SET p.image_embedding = $embedding
                        """
                        
                        self.product_kg.query(
                            query, 
                            {
                                "id": product.get("id"), 
                                "embedding": json.dumps(image_embedding)
                            }
                        )
                
            except Exception as e:
                logger.error(f"Error indexing product {product.get('id', 'unknown')}: {e}")
        
        logger.info(f"Indexed {indexed_count} products")
        return indexed_count
    
    def get_visual_recommendations(self, product_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recommendations based on visual similarity.
        
        Args:
            product_id: Reference product ID
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting visual recommendations for product {product_id}")
        
        # Get product details
        product = self.product_kg.get_product_details(product_id)
        if not product:
            logger.warning(f"Product not found: {product_id}")
            return []
        
        recommendations = []
        
        # Attempt image-based recommendations if available
        if self.image_model and product.get('images'):
            try:
                # Get the first image URL
                image_urls = product.get('images', [])
                image_url = image_urls[0] if isinstance(image_urls, list) and image_urls else None
                
                if image_url and isinstance(image_url, str):
                    # Generate image embedding
                    image_embedding = self._get_image_embedding(image_url)
                    
                    if image_embedding:
                        # Query Neo4j for products with image embeddings
                        # This is a simplified approach - in a real system you would
                        # need a vector similarity search in Neo4j or a separate vector DB
                        similar_products = self._find_similar_image_products(product_id, image_embedding, limit)
                        
                        if similar_products:
                            recommendations.extend(similar_products)
            except Exception as e:
                logger.error(f"Error getting image-based recommendations: {e}")
        
        # If no image-based recommendations or not enough, try text-based
        if len(recommendations) < limit and self.auto_retriever:
            try:
                # Create query from product details
                title = product.get('title', '')
                categories = ', '.join(product.get('categories', []))
                tags = ', '.join(product.get('tags', []))
                
                query = f"{title} {categories} {tags}"
                
                # Search similar products
                results = self.auto_retriever.search(
                    query=query,
                    limit=limit + 1  # Add 1 to exclude the query product
                )
                
                # Process results
                for result in results:
                    if isinstance(result, dict) and 'metadata' in result:
                        product_id = result['metadata'].get('product_id')
                        
                        # Skip the query product
                        if product_id == product_id:
                            continue
                            
                        # Get full product details
                        product_detail = self.product_kg.get_product_details(product_id)
                        if product_detail:
                            # Check if already in recommendations
                            if not any(r.get('id') == product_id for r in recommendations):
                                recommendations.append(product_detail)
                                
                                # Break if we have enough recommendations
                                if len(recommendations) >= limit:
                                    break
            except Exception as e:
                logger.error(f"Error getting text-based recommendations: {e}")
        
        # If still not enough recommendations, fallback to similar products
        if len(recommendations) < limit:
            fallback_products = self.product_kg.get_similar_products(product_id, limit - len(recommendations))
            
            # Add fallback products not already in recommendations
            for product in fallback_products:
                if not any(r.get('id') == product.get('id') for r in recommendations):
                    recommendations.append(product)
        
        logger.info(f"Found {len(recommendations)} visual recommendations")
        return recommendations[:limit]
    
    def _find_similar_image_products(self, product_id: str, image_embedding: List[float], limit: int) -> List[Dict[str, Any]]:
        """
        Find products with similar image embeddings.
        
        Args:
            product_id: Reference product ID to exclude
            image_embedding: Image embedding to compare with
            limit: Maximum number of products to return
            
        Returns:
            List of similar products
        """
        # This is a simplified approach - ideally you would use a vector DB
        # like Qdrant, Pinecone, or Weaviate for efficient similarity search
        try:
            # Fetch products with image embeddings from Neo4j
            query = """
            MATCH (p:Product)
            WHERE p.id <> $product_id AND p.image_embedding IS NOT NULL
            RETURN 
                p.id as id,
                p.image_embedding as embedding
            LIMIT 100
            """
            
            results = self.product_kg.query(query, {"product_id": product_id})
            
            if not results:
                return []
                
            # Calculate cosine similarity
            similar_products = []
            
            for result in results:
                if 'id' in result and 'embedding' in result:
                    try:
                        product_embedding = json.loads(result['embedding'])
                        
                        # Calculate similarity
                        similarity = self._cosine_similarity(image_embedding, product_embedding)
                        
                        similar_products.append({
                            'id': result['id'],
                            'similarity': similarity
                        })
                    except (json.JSONDecodeError, TypeError) as e:
                        continue
            
            # Sort by similarity
            similar_products.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Get full product details
            recommendations = []
            
            for item in similar_products[:limit]:
                product = self.product_kg.get_product_details(item['id'])
                if product:
                    recommendations.append(product)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error finding similar image products: {e}")
            return []
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity
        """
        if not a or not b or len(a) != len(b):
            return 0.0
            
        try:
            import numpy as np
            a_array = np.array(a)
            b_array = np.array(b)
            
            dot_product = np.dot(a_array, b_array)
            norm_a = np.linalg.norm(a_array)
            norm_b = np.linalg.norm(b_array)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
                
            return dot_product / (norm_a * norm_b)
        except Exception:
            # Fallback to pure Python implementation
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(y * y for y in b) ** 0.5
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
                
            return dot_product / (norm_a * norm_b)
    
    def index_all_products(self) -> int:
        """
        Index all products in the knowledge graph.
        
        Returns:
            Number of products indexed
        """
        try:
            # Get all products from Neo4j
            query = """
            MATCH (p:Product)
            RETURN 
                p.id as id,
                p.title as title,
                p.price as price,
                p.description as description,
                p.images as images
            LIMIT 1000
            """
            
            result = self.product_kg.query(query)
            
            if not result:
                logger.warning("No products found in knowledge graph")
                return 0
                
            # Process results into product objects
            products = []
            for record in result:
                # Get full product details
                if 'id' in record:
                    product_detail = self.product_kg.get_product_details(record['id'])
                    if product_detail:
                        products.append(product_detail)
            
            # Index products
            if products:
                return self.index_product_images(products)
            else:
                logger.warning("No valid products found for indexing")
                return 0
                
        except Exception as e:
            logger.error(f"Error indexing all products: {e}")
            return 0