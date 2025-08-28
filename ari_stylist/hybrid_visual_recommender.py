"""
PyTorch-based Visual Recommendation System for AI Stylist.

This module implements a recommendation system that combines content-based
and visual similarity approaches for fashion recommendations.
Compatible with CAMEL-AI 0.2.64.

Uses PyTorch instead of TensorFlow for better performance.
"""

import logging
import os
import json
import requests
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse

try:
    # PyTorch dependencies - much lighter than TensorFlow
    import torch
    import torchvision.models as models
    import torchvision.transforms as transforms
    from PIL import Image
    import numpy as np
    PYTORCH_AVAILABLE = True
    logger = logging.getLogger("hybrid_visual_recommender")
    logger.info("PyTorch available for visual similarity")
except ImportError:
    PYTORCH_AVAILABLE = False
    logger = logging.getLogger("hybrid_visual_recommender")
    logger.warning("PyTorch not installed. Visual similarity will be limited.")
    logger.info("Install with: pip install torch torchvision pillow")

# Use centralized imports with error handling
from camel_imports import (
    CAMEL_AVAILABLE,
    AutoRetriever,
    OpenAIEmbedding,
    EmbeddingModelType,
    StorageType,
    QdrantStorage
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hybrid_visual_recommender")

class HybridVisualRecommender:
    """
    Implements a hybrid recommendation system combining content-based filtering
    and visual similarity for fashion recommendations using PyTorch.
    
    Uses PyTorch instead of TensorFlow for better performance and efficiency.
    """
    
    def __init__(
        self, 
        product_kg, 
        embedding_model=None,
        model_name='resnet50',
        storage_path="product_data/visual_embeddings"
    ):
        """
        Initialize the PyTorch-based hybrid visual recommender.
        
        Args:
            product_kg: Neo4j product knowledge graph instance
            embedding_model: CAMEL embedding model (optional)
            model_name: PyTorch model to use ('resnet50', 'resnet101', 'efficientnet_b0')
            storage_path: Path to store vector embeddings
        """
        logger.info("Initializing HybridVisualRecommender with CAMEL 0.2.64 compatibility")
        self.product_kg = product_kg
        self.model_name = model_name
        
        # Check CAMEL availability
        if not CAMEL_AVAILABLE:
            logger.warning("CAMEL-AI not fully available, using fallback implementations")
        
        # Initialize embedding model with error handling
        try:
            if CAMEL_AVAILABLE and OpenAIEmbedding and EmbeddingModelType:
                self.embedding_model = embedding_model or OpenAIEmbedding(
                    model_type=EmbeddingModelType.TEXT_EMBEDDING_3_SMALL
                )
                logger.info("Text embedding model initialized successfully")
            else:
                logger.warning("CAMEL embeddings not available")
                self.embedding_model = None
        except Exception as e:
            logger.error(f"Error initializing text embedding model: {e}")
            self.embedding_model = None
            logger.warning("Text embeddings not available")
        
        # Initialize CAMEL retriever for text-based search with error handling
        try:
            if (CAMEL_AVAILABLE and AutoRetriever and StorageType and 
                self.embedding_model):
                self.auto_retriever = AutoRetriever(
                    vector_storage_local_path=storage_path,
                    storage_type=StorageType.QDRANT,
                    embedding_model=self.embedding_model
                )
                logger.info("AutoRetriever initialized successfully")
            else:
                logger.warning("CAMEL AutoRetriever not available")
                self.auto_retriever = None
        except Exception as e:
            logger.error(f"Error initializing AutoRetriever: {e}")
            self.auto_retriever = None
            logger.warning("AutoRetriever not available")
        
        # Initialize PyTorch model if available
        self.image_model = None
        self.preprocess = None
        self.device = None
        
        if PYTORCH_AVAILABLE:
            try:
                self._initialize_pytorch_model()
                logger.info(f"PyTorch model ({model_name}) initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing PyTorch model: {e}")
                self.image_model = None
                logger.warning("PyTorch model not available")
        else:
            logger.warning("PyTorch not available for visual similarity")
    
    def _initialize_pytorch_model(self):
        """Initialize the PyTorch model and preprocessing pipeline"""
        # Determine device (GPU if available, else CPU)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")
        
        # Initialize model based on specified architecture
        if self.model_name == 'resnet50':
            # ResNet50 - good balance of speed and accuracy
            self.image_model = models.resnet50(pretrained=True)
            # Remove final classification layer to get feature embeddings
            self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
            
        elif self.model_name == 'resnet101':
            # ResNet101 - higher accuracy, slower
            self.image_model = models.resnet101(pretrained=True)
            self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
            
        elif self.model_name == 'efficientnet_b0':
            # EfficientNet - best efficiency
            try:
                self.image_model = models.efficientnet_b0(pretrained=True)
                # Remove classifier to get features
                self.image_model.classifier = torch.nn.Identity()
            except AttributeError:
                # Fallback to ResNet50 if EfficientNet not available
                logger.warning("EfficientNet not available, falling back to ResNet50")
                self.image_model = models.resnet50(pretrained=True)
                self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
        else:
            # Default to ResNet50
            logger.warning(f"Unknown model {self.model_name}, using ResNet50")
            self.image_model = models.resnet50(pretrained=True)
            self.image_model = torch.nn.Sequential(*list(self.image_model.children())[:-1])
        
        # Move model to device and set to evaluation mode
        self.image_model = self.image_model.to(self.device)
        self.image_model.eval()
        
        # Define preprocessing pipeline
        self.preprocess = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],  # ImageNet means
                std=[0.229, 0.224, 0.225]    # ImageNet stds
            )
        ])
        
        logger.info(f"Initialized {self.model_name} on {self.device}")
    
    def _get_image_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate embedding for an image using PyTorch.
        
        Args:
            image_url: URL of the image
            
        Returns:
            Image embedding or None if not available
        """
        if not PYTORCH_AVAILABLE or self.image_model is None:
            logger.warning("PyTorch model not available for image embedding")
            return None
            
        try:
            # Validate URL
            parsed_url = urlparse(image_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                logger.warning(f"Invalid image URL: {image_url}")
                return None
            
            # Download image with timeout and size limits
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; AI-Stylist/1.0)'
            }
            
            response = requests.get(
                image_url, 
                headers=headers,
                timeout=10,
                stream=True
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not any(ct in content_type for ct in ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']):
                logger.warning(f"Unsupported content type: {content_type}")
                return None
            
            # Check file size (limit to 10MB)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 10 * 1024 * 1024:
                logger.warning(f"Image too large: {content_length} bytes")
                return None
            
            # Load and preprocess image
            image_data = BytesIO(response.content)
            img = Image.open(image_data).convert('RGB')
            
            # Preprocess image
            img_tensor = self.preprocess(img).unsqueeze(0).to(self.device)
            
            # Generate embedding
            with torch.no_grad():
                embedding = self.image_model(img_tensor)
                
                # Flatten the embedding
                if len(embedding.shape) > 2:
                    embedding = torch.nn.functional.adaptive_avg_pool2d(embedding, (1, 1))
                    embedding = embedding.view(embedding.size(0), -1)
                
                # Convert to list
                embedding = embedding.cpu().squeeze().tolist()
                
                # Ensure it's a list of floats
                if isinstance(embedding, float):
                    embedding = [embedding]
                
                logger.debug(f"Generated embedding of size {len(embedding)}")
                return embedding
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image from {image_url}: {e}")
            return None
        except PIL.UnidentifiedImageError as e:
            logger.error(f"Error processing image: {e}")
            return None
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
                
                # Index the document with error handling
                try:
                    if hasattr(self.auto_retriever, 'add_document'):
                        self.auto_retriever.add_document(document)
                        indexed_count += 1
                    else:
                        logger.warning("AutoRetriever does not support add_document method")
                        break
                except Exception as e:
                    logger.error(f"Error adding document to auto-retriever: {e}")
                    continue
                
                # Generate and store image embedding if available
                if self.image_model and image_url:
                    image_embedding = self._get_image_embedding(image_url)
                    if image_embedding:
                        # Store image embedding in Neo4j
                        try:
                            query = """
                            MATCH (p:Product {id: $id})
                            SET p.image_embedding = $embedding,
                                p.embedding_model = $model_name,
                                p.embedding_timestamp = $timestamp
                            """
                            
                            if hasattr(self.product_kg, 'query'):
                                result = self.product_kg.query(
                                    query, 
                                    {
                                        "id": product.get("id"), 
                                        "embedding": json.dumps(image_embedding),
                                        "model_name": self.model_name,
                                        "timestamp": str(torch.datetime.now() if hasattr(torch, 'datetime') else 'unknown')
                                    }
                                )
                        except Exception as e:
                            logger.error(f"Error storing image embedding in Neo4j: {e}")
                
            except Exception as e:
                logger.error(f"Error indexing product {product.get('id', 'unknown')}: {e}")
        
        logger.info(f"Indexed {indexed_count} products using PyTorch")
        return indexed_count
    
    def get_visual_recommendations(self, product_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recommendations based on visual similarity using PyTorch.
        
        Args:
            product_id: Reference product ID
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting PyTorch-based visual recommendations for product {product_id}")
        
        # Get product details
        try:
            if hasattr(self.product_kg, 'get_product_details'):
                product = self.product_kg.get_product(product_id)
            else:
                logger.error("Product KG does not support get_product_details")
                return []
        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            return []
            
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
                    # Generate image embedding using PyTorch
                    image_embedding = self._get_image_embedding(image_url)
                    
                    if image_embedding:
                        # Query Neo4j for products with image embeddings
                        similar_products = self._find_similar_image_products(product_id, image_embedding, limit)
                        
                        if similar_products:
                            recommendations.extend(similar_products)
                            logger.info(f"Found {len(similar_products)} visually similar products using PyTorch")
            except Exception as e:
                logger.error(f"Error getting PyTorch image-based recommendations: {e}")
        
        # If no image-based recommendations or not enough, try text-based
        if len(recommendations) < limit and self.auto_retriever:
            try:
                # Create query from product details
                title = product.get('title', '')
                categories = ', '.join(product.get('categories', []))
                tags = ', '.join(product.get('tags', []))
                
                query = f"{title} {categories} {tags}"
                
                # Search similar products with error handling
                try:
                    if hasattr(self.auto_retriever, 'search'):
                        results = self.auto_retriever.search(
                            query=query,
                            limit=limit + 1  # Add 1 to exclude the query product
                        )
                        
                        # Process results
                        for result in results:
                            if isinstance(result, dict) and 'metadata' in result:
                                result_product_id = result['metadata'].get('product_id')
                                
                                # Skip the query product
                                if result_product_id == product_id:
                                    continue
                                    
                                # Get full product details
                                try:
                                    product_detail = self.product_kg.get_product(result_product_id)
                                    if product_detail:
                                        # Check if already in recommendations
                                        if not any(r.get('id') == result_product_id for r in recommendations):
                                            recommendations.append(product_detail)
                                            
                                            # Break if we have enough recommendations
                                            if len(recommendations) >= limit:
                                                break
                                except Exception as e:
                                    logger.error(f"Error getting product details for {result_product_id}: {e}")
                    else:
                        logger.warning("AutoRetriever does not support search method")
                except Exception as e:
                    logger.error(f"Error searching with AutoRetriever: {e}")
            except Exception as e:
                logger.error(f"Error getting text-based recommendations: {e}")
        
        # If still not enough recommendations, fallback to similar products
        if len(recommendations) < limit:
            try:
                if hasattr(self.product_kg, 'get_similar_products'):
                    fallback_products = self.product_kg.get_similar_products(product_id, limit - len(recommendations))
                    
                    # Add fallback products not already in recommendations
                    for product in fallback_products:
                        if not any(r.get('id') == product.get('id') for r in recommendations):
                            recommendations.append(product)
            except Exception as e:
                logger.error(f"Error getting fallback similar products: {e}")
        
        logger.info(f"Found {len(recommendations)} total visual recommendations using PyTorch")
        return recommendations[:limit]
    
    def _find_similar_image_products(self, product_id: str, image_embedding: List[float], limit: int) -> List[Dict[str, Any]]:
        """
        Find products with similar image embeddings using PyTorch-optimized similarity.
        
        Args:
            product_id: Reference product ID to exclude
            image_embedding: Image embedding to compare with
            limit: Maximum number of products to return
            
        Returns:
            List of similar products
        """
        try:
            # Fetch products with image embeddings from Neo4j
            query = """
            MATCH (p:Product)
            WHERE p.id <> $product_id 
              AND p.image_embedding IS NOT NULL
              AND p.embedding_model = $model_name
            RETURN 
                p.id as id,
                p.image_embedding as embedding,
                p.title as title,
                p.price as price
            LIMIT 100
            """
            
            if hasattr(self.product_kg, 'query'):
                results = self.product_kg.query(query, {
                    "product_id": product_id,
                    "model_name": self.model_name
                })
            else:
                logger.error("Product KG does not support query method")
                return []
            
            if not results:
                return []
                
            # Calculate cosine similarity using PyTorch for efficiency
            similar_products = []
            
            if PYTORCH_AVAILABLE:
                # Convert query embedding to tensor
                query_tensor = torch.tensor(image_embedding, dtype=torch.float32).to(self.device)
                query_tensor = query_tensor / torch.norm(query_tensor)  # Normalize
                
                embeddings_list = []
                product_info = []
                
                for result in results:
                    if 'id' in result and 'embedding' in result:
                        try:
                            product_embedding = json.loads(result['embedding'])
                            embeddings_list.append(product_embedding)
                            product_info.append(result)
                        except (json.JSONDecodeError, TypeError):
                            continue
                
                if embeddings_list:
                    # Convert to tensor and calculate similarities in batch
                    embeddings_tensor = torch.tensor(embeddings_list, dtype=torch.float32).to(self.device)
                    embeddings_tensor = embeddings_tensor / torch.norm(embeddings_tensor, dim=1, keepdim=True)
                    
                    # Calculate cosine similarities
                    similarities = torch.mm(embeddings_tensor, query_tensor.unsqueeze(1)).squeeze()
                    
                    # Get top similar products
                    top_indices = torch.topk(similarities, min(limit, len(similarities))).indices
                    
                    for idx in top_indices:
                        idx_val = idx.item()
                        similarity_score = similarities[idx_val].item()
                        
                        similar_products.append({
                            'id': product_info[idx_val]['id'],
                            'similarity': similarity_score,
                            'title': product_info[idx_val].get('title', ''),
                            'price': product_info[idx_val].get('price', 0)
                        })
            else:
                # Fallback to numpy-based similarity if PyTorch not available
                for result in results:
                    if 'id' in result and 'embedding' in result:
                        try:
                            product_embedding = json.loads(result['embedding'])
                            similarity = self._cosine_similarity(image_embedding, product_embedding)
                            
                            similar_products.append({
                                'id': result['id'],
                                'similarity': similarity
                            })
                        except (json.JSONDecodeError, TypeError):
                            continue
                
                # Sort by similarity
                similar_products.sort(key=lambda x: x['similarity'], reverse=True)
                similar_products = similar_products[:limit]
            
            # Get full product details
            recommendations = []
            
            for item in similar_products:
                try:
                    product = self.product_kg.get_product(item['id'])
                    if product:
                        product['similarity_score'] = item['similarity']
                        recommendations.append(product)
                except Exception as e:
                    logger.error(f"Error getting product details for {item['id']}: {e}")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error finding similar image products: {e}")
            return []
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        Fallback implementation when PyTorch is not available.
        
        Args:
            a: First vector
            b: Second vector
            
        Returns:
            Cosine similarity
        """
        if not a or not b or len(a) != len(b):
            return 0.0
            
        try:
            if PYTORCH_AVAILABLE:
                # Use PyTorch for faster computation
                tensor_a = torch.tensor(a, dtype=torch.float32)
                tensor_b = torch.tensor(b, dtype=torch.float32)
                
                similarity = torch.nn.functional.cosine_similarity(
                    tensor_a.unsqueeze(0), 
                    tensor_b.unsqueeze(0)
                ).item()
                
                return similarity
            else:
                # Fallback to numpy/pure Python
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
            # Final fallback to pure Python
            dot_product = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(y * y for y in b) ** 0.5
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
                
            return dot_product / (norm_a * norm_b)
    
    def index_all_products(self) -> int:
        """
        Index all products in the knowledge graph using PyTorch.
        
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
            
            if hasattr(self.product_kg, 'query'):
                result = self.product_kg.query(query)
            else:
                logger.error("Product KG does not support query method")
                return 0
            
            if not result:
                logger.warning("No products found in knowledge graph")
                return 0
                
            # Process results into product objects
            products = []
            for record in result:
                # Get full product details
                if 'id' in record:
                    try:
                        product_detail = self.product_kg.get_product(record['id'])
                        if product_detail:
                            products.append(product_detail)
                    except Exception as e:
                        logger.error(f"Error getting product details for {record['id']}: {e}")
            
            # Index products using PyTorch
            if products:
                return self.index_product_images(products)
            else:
                logger.warning("No valid products found for indexing")
                return 0
                
        except Exception as e:
            logger.error(f"Error indexing all products: {e}")
            return 0
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current PyTorch model"""
        return {
            "backend": "pytorch",
            "model_name": self.model_name,
            "device": str(self.device) if self.device else "unknown",
            "available": PYTORCH_AVAILABLE and self.image_model is not None,
            "pytorch_version": torch.__version__ if PYTORCH_AVAILABLE else None
        }