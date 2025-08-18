"""
Clustering Intelligence for CypherBot

Provides clustering-based intelligence using KMeans.
NEVER returns products - only cluster insights for CypherBot to use.

Based on multi_cluster_recommender.py patterns.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger("intelligence.clustering")

# Try to import scikit-learn
try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed. Clustering intelligence will be limited.")


class ClusteringIntelligence:
    """
    Provides clustering-based intelligence for CypherBot.
    
    Uses KMeans to identify product clusters and patterns.
    CRITICAL: Returns cluster intelligence, NEVER products!
    """
    
    def __init__(
        self,
        product_kg: Any,
        n_clusters: int = 8,
        min_cluster_size: int = 5
    ):
        """
        Initialize clustering intelligence system.
        
        Args:
            product_kg: Product knowledge graph
            n_clusters: Number of clusters to create (default 8 from multi_cluster_recommender.py)
            min_cluster_size: Minimum size for valid cluster
        """
        logger.info(f"Initializing Clustering Intelligence with {n_clusters} clusters")
        
        self.product_kg = product_kg
        self.n_clusters = n_clusters
        self.min_cluster_size = min_cluster_size
        
        # Cluster models and data
        self.kmeans_model = None
        self.scaler = None
        self.cluster_centers = None
        self.cluster_labels = {}  # product_id -> cluster_id
        self.cluster_characteristics = {}  # cluster_id -> characteristics
        
        # Check if sklearn is available
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available - clustering intelligence disabled")
            return
        
        # Track if clustering has been performed
        self.is_clustered = False
        
        logger.info("Clustering Intelligence initialized")
    
    async def initialize_clusters(self) -> bool:
        """
        Initialize clusters from product data.
        
        Returns:
            Success status
        """
        if not SKLEARN_AVAILABLE:
            return False
        
        try:
            # Get products from knowledge graph
            products = await self._get_all_products()
            if not products:
                logger.warning("No products available for clustering")
                return False
            
            # Extract features and create clusters
            success = await self._create_clusters(products)
            
            if success:
                logger.info(f"Successfully created {self.n_clusters} clusters")
                self.is_clustered = True
            
            return success
            
        except Exception as e:
            logger.error(f"Error initializing clusters: {e}")
            return False
    
    async def get_product_cluster(
        self,
        product_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cluster intelligence for a specific product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Cluster intelligence (NOT products!)
        """
        # Check if product has cached cluster
        if product_id in self.cluster_labels:
            cluster_id = self.cluster_labels[product_id]
            return {
                "cluster_id": cluster_id,
                "characteristics": self.cluster_characteristics.get(cluster_id, {}),
                "keywords": self._get_cluster_keywords(cluster_id),
                "cluster_size": self._get_cluster_size(cluster_id),
                "confidence": 0.85
            }
        
        # Try to get from Neo4j
        cluster_info = await self._get_cluster_from_neo4j(product_id)
        if cluster_info:
            return cluster_info
        
        # If no cluster info and model is available, predict
        if self.kmeans_model and SKLEARN_AVAILABLE:
            cluster_id = await self._predict_cluster(product_id)
            if cluster_id is not None:
                return {
                    "cluster_id": cluster_id,
                    "characteristics": self.cluster_characteristics.get(cluster_id, {}),
                    "keywords": self._get_cluster_keywords(cluster_id),
                    "confidence": 0.7  # Lower confidence for predicted
                }
        
        return None
    
    async def find_relevant_clusters(
        self,
        query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find clusters relevant to a query.
        
        Args:
            query: Search query
            
        Returns:
            Relevant cluster intelligence
        """
        if not self.is_clustered:
            return None
        
        try:
            # Extract keywords from query
            query_lower = query.lower()
            
            # Score each cluster based on keyword matches
            cluster_scores = {}
            
            for cluster_id in range(self.n_clusters):
                keywords = self._get_cluster_keywords(cluster_id)
                score = sum(1 for kw in keywords if kw in query_lower)
                if score > 0:
                    cluster_scores[cluster_id] = score
            
            if not cluster_scores:
                return None
            
            # Get top clusters
            top_clusters = sorted(
                cluster_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            return {
                "relevant_clusters": [
                    {
                        "cluster_id": cid,
                        "relevance_score": score,
                        "characteristics": self.cluster_characteristics.get(cid, {}),
                        "keywords": self._get_cluster_keywords(cid)
                    }
                    for cid, score in top_clusters
                ],
                "confidence": 0.6
            }
            
        except Exception as e:
            logger.error(f"Error finding relevant clusters: {e}")
            return None
    
    async def get_cluster_analysis(
        self,
        query: Optional[str] = None,
        product_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive cluster analysis.
        
        Args:
            query: Optional search query
            product_id: Optional product ID
            
        Returns:
            Cluster analysis intelligence
        """
        analysis = {
            "clusters": [],
            "keywords": [],
            "distribution": {},
            "coherence": 0.0,
            "confidence": 0.0
        }
        
        if not self.is_clustered:
            return analysis
        
        # Get cluster distribution
        for cluster_id in range(self.n_clusters):
            size = self._get_cluster_size(cluster_id)
            if size >= self.min_cluster_size:
                analysis["distribution"][f"cluster_{cluster_id}"] = size
        
        # Get keywords across all clusters
        all_keywords = set()
        for cluster_id in range(self.n_clusters):
            keywords = self._get_cluster_keywords(cluster_id)
            all_keywords.update(keywords)
        
        analysis["keywords"] = list(all_keywords)[:20]  # Top 20 keywords
        
        # Calculate coherence (simplified)
        if len(analysis["distribution"]) > 0:
            sizes = list(analysis["distribution"].values())
            mean_size = np.mean(sizes)
            std_size = np.std(sizes)
            # Lower std means more coherent clusters
            analysis["coherence"] = 1.0 / (1.0 + std_size / mean_size) if mean_size > 0 else 0.5
        
        # Add specific cluster if product_id provided
        if product_id:
            cluster_info = await self.get_product_cluster(product_id)
            if cluster_info:
                analysis["clusters"].append(cluster_info)
        
        # Add relevant clusters if query provided
        if query:
            relevant = await self.find_relevant_clusters(query)
            if relevant:
                analysis["clusters"].extend(relevant.get("relevant_clusters", []))
        
        # Set overall confidence
        analysis["confidence"] = 0.8 if self.is_clustered else 0.3
        
        return analysis
    
    async def _get_all_products(self) -> List[Dict[str, Any]]:
        """Get all products from knowledge graph."""
        if not self.product_kg:
            return []
        
        try:
            # Use appropriate method based on what's available
            if hasattr(self.product_kg, 'get_all_products'):
                return await self.product_kg.get_all_products(limit=1000)
            elif hasattr(self.product_kg, 'query'):
                query = """
                MATCH (p:Product)
                RETURN p
                LIMIT 1000
                """
                results = await self.product_kg.query(query)
                return [r['p'] for r in results if 'p' in r]
            else:
                logger.warning("No method to get products from knowledge graph")
                return []
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return []
    
    async def _create_clusters(self, products: List[Dict[str, Any]]) -> bool:
        """Create clusters from products."""
        if not SKLEARN_AVAILABLE:
            return False
        
        try:
            # Extract features from products
            features = []
            valid_products = []
            
            for product in products:
                feature_vector = self._extract_features(product)
                if feature_vector is not None:
                    features.append(feature_vector)
                    valid_products.append(product)
            
            if len(features) < self.n_clusters:
                logger.warning(f"Not enough products ({len(features)}) for {self.n_clusters} clusters")
                return False
            
            # Convert to numpy array
            X = np.array(features)
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Perform clustering
            self.kmeans_model = KMeans(
                n_clusters=min(self.n_clusters, len(features)),
                random_state=42,
                n_init=10
            )
            
            # Run clustering in thread pool to avoid blocking
            labels = await asyncio.to_thread(
                self.kmeans_model.fit_predict,
                X_scaled
            )
            
            # Store cluster information
            for i, product in enumerate(valid_products):
                product_id = product.get('id')
                if product_id:
                    self.cluster_labels[product_id] = int(labels[i])
            
            # Store cluster centers
            self.cluster_centers = self.kmeans_model.cluster_centers_
            
            # Analyze cluster characteristics
            await self._analyze_cluster_characteristics(valid_products, labels)
            
            # Update Neo4j with cluster information
            await self._update_clusters_in_neo4j(valid_products, labels)
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating clusters: {e}")
            return False
    
    def _extract_features(self, product: Dict[str, Any]) -> Optional[np.ndarray]:
        """Extract numerical features from product."""
        try:
            features = []
            
            # Price feature
            price = product.get('price', 0)
            features.append(float(price) if price else 0.0)
            
            # Category features (simplified - in production would use embeddings)
            categories = product.get('categories', [])
            features.append(len(categories))
            
            # Tag features
            tags = product.get('tags', [])
            features.append(len(tags))
            
            # Popularity features
            features.append(float(product.get('visited_num', 0)))
            features.append(float(product.get('liked_num', 0)))
            features.append(float(product.get('purchased_num', 0)))
            
            return np.array(features)
            
        except Exception as e:
            logger.warning(f"Error extracting features: {e}")
            return None
    
    async def _analyze_cluster_characteristics(
        self,
        products: List[Dict[str, Any]],
        labels: np.ndarray
    ):
        """Analyze characteristics of each cluster."""
        for cluster_id in range(self.n_clusters):
            cluster_products = [
                p for i, p in enumerate(products)
                if labels[i] == cluster_id
            ]
            
            if not cluster_products:
                continue
            
            # Analyze cluster characteristics
            characteristics = {
                "size": len(cluster_products),
                "avg_price": np.mean([p.get('price', 0) for p in cluster_products]),
                "price_range": {
                    "min": min(p.get('price', 0) for p in cluster_products),
                    "max": max(p.get('price', 0) for p in cluster_products)
                },
                "common_categories": self._get_common_items(
                    [p.get('categories', []) for p in cluster_products]
                ),
                "common_tags": self._get_common_items(
                    [p.get('tags', []) for p in cluster_products]
                )
            }
            
            self.cluster_characteristics[cluster_id] = characteristics
    
    def _get_common_items(self, item_lists: List[List[str]], top_n: int = 5) -> List[str]:
        """Get most common items from lists."""
        from collections import Counter
        
        all_items = []
        for item_list in item_lists:
            all_items.extend(item_list)
        
        counter = Counter(all_items)
        return [item for item, _ in counter.most_common(top_n)]
    
    def _get_cluster_keywords(self, cluster_id: int) -> List[str]:
        """Get keywords for a cluster."""
        if cluster_id not in self.cluster_characteristics:
            return []
        
        chars = self.cluster_characteristics[cluster_id]
        keywords = []
        
        # Add common categories and tags as keywords
        keywords.extend(chars.get('common_categories', []))
        keywords.extend(chars.get('common_tags', []))
        
        # Add price-based keywords
        avg_price = chars.get('avg_price', 0)
        if avg_price < 50:
            keywords.append('affordable')
        elif avg_price > 200:
            keywords.append('luxury')
        else:
            keywords.append('mid-range')
        
        return keywords
    
    def _get_cluster_size(self, cluster_id: int) -> int:
        """Get size of a cluster."""
        return sum(1 for cid in self.cluster_labels.values() if cid == cluster_id)
    
    async def _get_cluster_from_neo4j(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get cluster information from Neo4j."""
        if not self.product_kg or not hasattr(self.product_kg, 'query'):
            return None
        
        try:
            query = """
            MATCH (p:Product {id: $product_id})
            WHERE p.cluster IS NOT NULL
            RETURN p.cluster as cluster_id
            """
            
            result = await self.product_kg.query(query, {"product_id": product_id})
            
            if result and result[0].get('cluster_id') is not None:
                cluster_id = result[0]['cluster_id']
                return {
                    "cluster_id": cluster_id,
                    "characteristics": self.cluster_characteristics.get(cluster_id, {}),
                    "keywords": self._get_cluster_keywords(cluster_id),
                    "confidence": 0.8
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error getting cluster from Neo4j: {e}")
            return None
    
    async def _update_clusters_in_neo4j(
        self,
        products: List[Dict[str, Any]],
        labels: np.ndarray
    ):
        """Update cluster information in Neo4j."""
        if not self.product_kg or not hasattr(self.product_kg, 'query'):
            return
        
        try:
            for i, product in enumerate(products):
                product_id = product.get('id')
                if product_id:
                    query = """
                    MATCH (p:Product {id: $product_id})
                    SET p.cluster = $cluster_id
                    """
                    
                    await self.product_kg.query(
                        query,
                        {
                            "product_id": product_id,
                            "cluster_id": int(labels[i])
                        }
                    )
            
            logger.info("Updated cluster information in Neo4j")
            
        except Exception as e:
            logger.error(f"Error updating clusters in Neo4j: {e}")
    
    async def _predict_cluster(self, product_id: str) -> Optional[int]:
        """Predict cluster for a product."""
        if not self.kmeans_model or not SKLEARN_AVAILABLE:
            return None
        
        try:
            # Get product details
            if hasattr(self.product_kg, 'get_product'):
                product = await self.product_kg.get_product(product_id)
            else:
                return None
            
            if not product:
                return None
            
            # Extract features
            features = self._extract_features(product)
            if features is None:
                return None
            
            # Scale features
            if self.scaler:
                features_scaled = self.scaler.transform([features])
            else:
                features_scaled = [features]
            
            # Predict cluster
            cluster_id = await asyncio.to_thread(
                self.kmeans_model.predict,
                features_scaled
            )
            
            return int(cluster_id[0])
            
        except Exception as e:
            logger.error(f"Error predicting cluster: {e}")
            return None