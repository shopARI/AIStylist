"""
Multi-Clustering Recommendation System for AI Stylist.

This module implements a recommendation system that uses clustering
to group similar products and users for better recommendations.
Compatible with CAMEL-AI 0.2.43.
"""

import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

try:
    from sklearn.cluster import KMeans
except ImportError:
    logging.warning("scikit-learn not installed. Please install with: pip install scikit-learn")

from camel.embeddings import OpenAIEmbedding
from camel.storages import QdrantStorage
from camel.retrievers import VectorRetriever
from camel.types import EmbeddingModelType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("multi_cluster_recommender")

class MultiClusterRecommender:
    """
    Implements a recommendation system that uses clustering to group
    similar products and users for better recommendations.
    """
    
    def __init__(
        self, 
        product_kg, 
        embedding_model=None, 
        n_clusters=5,
        storage_path="product_data/cluster_embeddings"
    ):
        """
        Initialize the multi-cluster recommender.
        
        Args:
            product_kg: Neo4j product knowledge graph instance
            embedding_model: CAMEL embedding model (optional)
            n_clusters: Number of clusters to create
            storage_path: Path to store vector embeddings
        """
        logger.info("Initializing MultiClusterRecommender")
        self.product_kg = product_kg
        self.n_clusters = n_clusters
        
        # Initialize embedding model
        try:
            self.embedding_model = embedding_model or OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_3_SMALL
            )
            logger.info("Embedding model initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing embedding model: {e}")
            # Fallback to a simpler approach if embeddings aren't available
            self.embedding_model = None
            logger.warning("Using fallback without embeddings")
        
        # Initialize storage and retriever if embedding model is available
        if self.embedding_model:
            try:
                # Create vector storage with CAMEL
                self.storage = QdrantStorage(
                    vector_dim=self.embedding_model.get_output_dim(),
                    path=storage_path,
                    collection_name="fashion_clusters"
                )
                
                # Initialize retriever
                self.retriever = VectorRetriever(
                    embedding_model=self.embedding_model,
                    storage=self.storage
                )
                logger.info("Vector storage and retriever initialized")
            except Exception as e:
                logger.error(f"Error initializing vector storage: {e}")
                self.storage = None
                self.retriever = None
                logger.warning("Vector storage and retriever not available")
        else:
            self.storage = None
            self.retriever = None
        
        # Cluster models
        self.product_cluster_model = None
        self.user_cluster_model = None
        
        # Track if clustering has been done
        self.is_clustered = False
    
    def _create_product_text(self, product: Dict[str, Any]) -> str:
        """
        Create a text representation of a product for embedding.
        
        Args:
            product: Product dictionary
            
        Returns:
            Text representation
        """
        # Extract key product information
        title = product.get('title', '')
        description = product.get('description', '')
        categories = ' '.join(product.get('categories', []))
        tags = ' '.join(product.get('tags', []))
        collections = ' '.join(product.get('collections', []))
        
        # Combine into a single text
        return f"{title}. {description}. Categories: {categories}. Tags: {tags}. Collections: {collections}"
    
    def _get_product_embedding(self, product: Dict[str, Any]) -> Optional[List[float]]:
        """
        Get embedding for a product.
        
        Args:
            product: Product dictionary
            
        Returns:
            Embedding vector or None if not available
        """
        if not self.embedding_model:
            return None
            
        try:
            # Create text representation
            text = self._create_product_text(product)
            
            # Generate embedding
            embedding = self.embedding_model.embed(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating product embedding: {e}")
            return None
    
    def create_product_clusters(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create clusters of products using KMeans.
        
        Args:
            products: List of product dictionaries
            
        Returns:
            Products with cluster information added
        """
        logger.info(f"Creating product clusters with {len(products)} products")
        
        if not products:
            logger.warning("No products provided for clustering")
            return []
            
        try:
            # Generate embeddings for products
            product_embeddings = []
            valid_products = []
            
            for product in products:
                embedding = self._get_product_embedding(product)
                if embedding is not None:
                    product_embeddings.append(embedding)
                    valid_products.append(product)
            
            if not product_embeddings:
                logger.warning("No valid product embeddings generated")
                return products
                
            # Convert to numpy array
            embeddings_array = np.array(product_embeddings)
            
            # Adjust n_clusters if needed
            actual_n_clusters = min(self.n_clusters, len(valid_products))
            
            # Create clusters
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=actual_n_clusters, random_state=42)
            clusters = kmeans.fit_predict(embeddings_array)
            
            # Store the model
            self.product_cluster_model = kmeans
            
            # Update products with cluster information
            for i, product in enumerate(valid_products):
                product['cluster'] = int(clusters[i])
                
            # Store cluster embeddings for future use
            if self.storage and self.retriever:
                for i, product in enumerate(valid_products):
                    # Create document for the product
                    document_id = f"product_{product.get('id')}"
                    self.storage.add_vector(
                        id=document_id,
                        vector=product_embeddings[i],
                        payload={
                            "product_id": product.get('id'),
                            "cluster": int(clusters[i]),
                            "title": product.get('title', ''),
                            "category": product.get('categories', [])
                        }
                    )
            
            self.is_clustered = True
            logger.info(f"Successfully created {actual_n_clusters} product clusters")
            
            # Update Neo4j with cluster information
            self._update_product_clusters_in_neo4j(valid_products)
            
            return valid_products
            
        except Exception as e:
            logger.error(f"Error creating product clusters: {e}")
            return products
    
    def _update_product_clusters_in_neo4j(self, products: List[Dict[str, Any]]) -> bool:
        """
        Update cluster information in Neo4j.
        
        Args:
            products: Products with cluster information
            
        Returns:
            True if successful, False otherwise
        """
        if not self.product_kg or not hasattr(self.product_kg, 'query'):
            logger.warning("Product knowledge graph not available for updating clusters")
            return False
            
        try:
            # Update products in Neo4j
            for product in products:
                if 'id' in product and 'cluster' in product:
                    # Update the cluster property
                    query = """
                    MATCH (p:Product {id: $id})
                    SET p.cluster = $cluster
                    """
                    
                    self.product_kg.query(
                        query, 
                        {"id": product['id'], "cluster": product['cluster']}
                    )
            
            logger.info("Updated cluster information in Neo4j")
            return True
            
        except Exception as e:
            logger.error(f"Error updating cluster information in Neo4j: {e}")
            return False
    
    def get_recommendations(self, product_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get product recommendations based on clusters.
        
        Args:
            product_id: Reference product ID
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting cluster-based recommendations for product {product_id}")
        
        # Get product details
        product = self.product_kg.get_product_details(product_id)
        if not product:
            logger.warning(f"Product not found: {product_id}")
            return []
            
        # Check if product has cluster information
        if 'cluster' not in product and self.is_clustered:
            # Try to infer cluster
            embedding = self._get_product_embedding(product)
            if embedding is not None and self.product_cluster_model:
                # Predict cluster
                cluster = int(self.product_cluster_model.predict([embedding])[0])
                product['cluster'] = cluster
                
                # Update in Neo4j
                self._update_product_clusters_in_neo4j([product])
        
        # Get recommendations based on cluster
        if 'cluster' in product:
            try:
                # Query Neo4j for products in the same cluster
                query = """
                MATCH (p:Product)
                WHERE p.cluster = $cluster AND p.id <> $product_id
                RETURN 
                    p.id as id,
                    p.title as title,
                    p.price as price,
                    p.description as description,
                    p.images as images,
                    p.cluster as cluster
                ORDER BY p.visited_num DESC
                LIMIT $limit
                """
                
                result = self.product_kg.query(
                    query, 
                    {
                        "cluster": product['cluster'], 
                        "product_id": product_id, 
                        "limit": limit
                    }
                )
                
                if result:
                    # Process results into product objects
                    recommendations = []
                    for record in result:
                        # Get full product details
                        if 'id' in record:
                            product_detail = self.product_kg.get_product_details(record['id'])
                            if product_detail:
                                recommendations.append(product_detail)
                    
                    logger.info(f"Found {len(recommendations)} cluster-based recommendations")
                    return recommendations
            
            except Exception as e:
                logger.error(f"Error getting cluster-based recommendations: {e}")
        
        # Fallback to similar products if clustering is not available
        logger.info("Using fallback to similar products")
        return self.product_kg.get_similar_products(product_id, limit)
    
    def cluster_all_products(self) -> bool:
        """
        Cluster all products in the knowledge graph.
        
        Returns:
            True if successful, False otherwise
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
                p.images as images,
                p.visited_num as visited_num
            LIMIT 1000
            """
            
            result = self.product_kg.query(query)
            
            if not result:
                logger.warning("No products found in knowledge graph")
                return False
                
            # Process results into product objects
            products = []
            for record in result:
                # Get full product details
                if 'id' in record:
                    product_detail = self.product_kg.get_product_details(record['id'])
                    if product_detail:
                        products.append(product_detail)
            
            # Create clusters
            if products:
                self.create_product_clusters(products)
                return True
            else:
                logger.warning("No valid products found for clustering")
                return False
                
        except Exception as e:
            logger.error(f"Error clustering all products: {e}")
            return False