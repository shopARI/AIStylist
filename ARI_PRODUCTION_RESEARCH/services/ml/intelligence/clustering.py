"""
Clustering Intelligence for CypherBot

Provides clustering-based intelligence using KMeans.
NEVER returns products - only cluster insights for CypherBot to use.

Based on multi_cluster_recommender.py patterns.
FIXED: Memory-safe batch processing for large datasets
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
import numpy as np

logger = logging.getLogger("intelligence.clustering")

# Try to import scikit-learn
try:
    from sklearn.cluster import KMeans, MiniBatchKMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn not installed. Clustering intelligence will be limited.")

# Memory management constants
MAX_PRODUCTS_IN_MEMORY = 5000  # Maximum products to hold in memory at once
BATCH_SIZE = 1000  # Process products in batches
MAX_FEATURES_FOR_CLUSTERING = 10000  # Maximum features for clustering


class ClusteringIntelligence:
    """
    Provides clustering-based intelligence for CypherBot.
    
    Uses KMeans to identify product clusters and patterns.
    CRITICAL: Returns cluster intelligence, NEVER products!
    FIXED: Memory-safe batch processing to handle millions of products
    """
    
    async def get_product_clusters_batch(
        self, 
        product_ids: List[str]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get clusters for multiple products in batch.
        
        Args:
            product_ids: List of product IDs
            
        Returns:
            Dict mapping product_id to cluster info
        """
        results = {}
        
        # Check cache first
        uncached_ids = []
        for pid in product_ids:
            if pid in self.cluster_labels:
                results[pid] = {
                    "cluster_id": self.cluster_labels[pid],
                    "characteristics": self.cluster_characteristics.get(
                        self.cluster_labels[pid], {}
                    ),
                    "confidence": 0.85
                }
            else:
                uncached_ids.append(pid)
        
        # Batch query for uncached products
        if uncached_ids and self.product_kg:
            query = """
            MATCH (p:Product)
            WHERE p.id IN $product_ids
            RETURN p.id as product_id, p.cluster as cluster_id, p
            """
            
            batch_results = await self.product_kg.query(
                query,
                {"product_ids": uncached_ids}
            )
            
            for record in batch_results:
                pid = record['product_id']
                cluster_id = record.get('cluster_id')
                
                if cluster_id is not None:
                    results[pid] = {
                        "cluster_id": cluster_id,
                        "characteristics": self.cluster_characteristics.get(cluster_id, {}),
                        "confidence": 0.8
                    }
                    # Cache it
                    if len(self.cluster_labels) < self.max_cached_labels:
                        self.cluster_labels[pid] = cluster_id
        
        return results


    def __init__(
        self,
        product_kg: Any,
        n_clusters: int = 8,
        min_cluster_size: int = 5,
        use_minibatch: bool = True,  # Use MiniBatchKMeans for large datasets
        batch_size: int = BATCH_SIZE
    ):
        """
        Initialize clustering intelligence system with memory management.
        
        Args:
            product_kg: Product knowledge graph
            n_clusters: Number of clusters to create (default 8 from multi_cluster_recommender.py)
            min_cluster_size: Minimum size for valid cluster
            use_minibatch: Use MiniBatchKMeans for memory efficiency
            batch_size: Batch size for processing
        """
        logger.info(f"Initializing Clustering Intelligence with {n_clusters} clusters")
        logger.info(f"Memory management: batch_size={batch_size}, use_minibatch={use_minibatch}")
        
        self.product_kg = product_kg
        self.n_clusters = n_clusters
        self.min_cluster_size = min_cluster_size
        self.use_minibatch = use_minibatch
        self.batch_size = batch_size
        
        # Cluster models and data
        self.kmeans_model = None
        self.scaler = None
        self.cluster_centers = None
        self.cluster_labels = {}  # product_id -> cluster_id (limited size)
        self.cluster_characteristics = {}  # cluster_id -> characteristics
        
        # Memory management
        self.max_cached_labels = 10000  # Maximum labels to keep in memory
        self.sample_size = MAX_FEATURES_FOR_CLUSTERING  # Sample size for large datasets
        
        # Check if sklearn is available
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available - clustering intelligence disabled")
            return
        
        # Track if clustering has been performed
        self.is_clustered = False
        
        logger.info("Clustering Intelligence initialized with memory management")
    
    async def initialize_clusters(self) -> bool:
        """
        Initialize clusters from product data with batch processing.
        
        Returns:
            Success status
        """
        if not SKLEARN_AVAILABLE:
            return False
        
        try:
            logger.info("Starting cluster initialization with batch processing...")
            
            # Process products in batches and create clusters
            success = await self._create_clusters_batch()
            
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
                # Cache if under limit
                if len(self.cluster_labels) < self.max_cached_labels:
                    self.cluster_labels[product_id] = cluster_id
                
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
    
    async def _product_batch_generator(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Generate batches of products from knowledge graph.
        Memory-efficient generator that yields batches.
        """
        if not self.product_kg:
            return
        
        offset = 0
        
        while True:
            try:
                # Use appropriate method based on what's available
                if hasattr(self.product_kg, 'query'):
                    # Query for batch using SKIP and LIMIT
                    query = """
                    MATCH (p:Product)
                    RETURN p
                    SKIP $offset
                    LIMIT $batch_size
                    """
                    
                    results = await self.product_kg.query(
                        query,
                        {"offset": offset, "batch_size": self.batch_size}
                    )
                    
                    if not results:
                        break
                    
                    # Extract products from results
                    batch = [r['p'] for r in results if 'p' in r]
                    
                    if batch:
                        yield batch
                    
                    if len(batch) < self.batch_size:
                        break
                    
                    offset += self.batch_size
                    
                    # Log progress
                    if offset % (self.batch_size * 10) == 0:
                        logger.info(f"Processed {offset} products...")
                        
                elif hasattr(self.product_kg, 'get_all_products'):
                    # Fallback to get_all_products with limit
                    products = await self.product_kg.get_all_products(
                        limit=self.batch_size,
                        offset=offset
                    )
                    
                    if not products:
                        break
                    
                    yield products
                    
                    if len(products) < self.batch_size:
                        break
                    
                    offset += self.batch_size
                else:
                    logger.warning("No method to get products from knowledge graph")
                    break
                    
            except Exception as e:
                logger.error(f"Error in batch generator: {e}")
                break
    
    async def _create_clusters_batch(self) -> bool:
        """
        Create clusters using batch processing for memory efficiency.
        Uses MiniBatchKMeans for large datasets.
        """
        if not SKLEARN_AVAILABLE:
            return False
        
        try:
            logger.info("Starting batch clustering process...")
            
            # Collect features in batches
            all_features = []
            sample_products = []  # Keep sample for analysis
            total_products = 0
            
            async for batch in self._product_batch_generator():
                batch_features = []
                
                for product in batch:
                    feature_vector = self._extract_features(product)
                    if feature_vector is not None:
                        batch_features.append(feature_vector)
                        
                        # Keep sample of products for analysis
                        if len(sample_products) < 1000:
                            sample_products.append(product)
                        
                        total_products += 1
                
                # Add batch features to collection
                if batch_features:
                    all_features.extend(batch_features)
                
                # Check memory limit
                if len(all_features) >= self.sample_size:
                    logger.info(f"Reached sample size limit ({self.sample_size}), stopping collection")
                    break
                
                # Prevent memory overload
                if len(all_features) >= MAX_FEATURES_FOR_CLUSTERING:
                    logger.warning(f"Dataset too large, using sample of {MAX_FEATURES_FOR_CLUSTERING}")
                    break
            
            logger.info(f"Collected features from {total_products} products, using {len(all_features)} for clustering")
            
            if len(all_features) < self.n_clusters:
                logger.warning(f"Not enough products ({len(all_features)}) for {self.n_clusters} clusters")
                return False
            
            # Convert to numpy array
            X = np.array(all_features)
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Choose clustering algorithm based on dataset size
            if self.use_minibatch and len(X_scaled) > 5000:
                logger.info("Using MiniBatchKMeans for memory efficiency")
                self.kmeans_model = MiniBatchKMeans(
                    n_clusters=min(self.n_clusters, len(all_features)),
                    random_state=42,
                    batch_size=min(1024, len(all_features) // 10),
                    n_init=3
                )
            else:
                logger.info("Using standard KMeans")
                self.kmeans_model = KMeans(
                    n_clusters=min(self.n_clusters, len(all_features)),
                    random_state=42,
                    n_init=10
                )
            
            # Run clustering in thread pool to avoid blocking
            labels = await asyncio.to_thread(
                self.kmeans_model.fit_predict,
                X_scaled
            )
            
            # Store limited cluster labels (only for sample)
            for i, product in enumerate(sample_products[:self.max_cached_labels]):
                product_id = product.get('id')
                if product_id and i < len(labels):
                    self.cluster_labels[product_id] = int(labels[i])
            
            # Store cluster centers
            self.cluster_centers = self.kmeans_model.cluster_centers_
            
            # Analyze cluster characteristics using sample
            await self._analyze_cluster_characteristics(sample_products[:len(labels)], labels[:len(sample_products)])
            
            # Update some products in Neo4j with cluster info (in batches)
            await self._update_clusters_in_neo4j_batch(sample_products[:100], labels[:100])
            
            logger.info(f"Clustering complete: {self.n_clusters} clusters created from {total_products} products")
            
            # Clear features to free memory
            del all_features
            del X
            del X_scaled
            
            return True
            
        except Exception as e:
            logger.error(f"Error in batch clustering: {e}")
            return False
    
    def _extract_features(self, product: Dict[str, Any]) -> Optional[np.ndarray]:
        """Extract numerical features from product."""
        try:
            features = []
            
            # Price feature
            price = product.get('price', 0)
            #features.append(float(price) if price else 0.0)
            
            # Category features (simplified - in production would use embeddings)
            categories = product.get('categories', [])
            #features.append(len(categories))
            
            features.extend([
                np.log1p(float(price)) if price else 0.0,  # Log scale for price
                len(set(categories)),  # Unique categories
                self._encode_category_embedding(categories),  # Category embeddings
            ])

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
                if i < len(labels) and labels[i] == cluster_id
            ]
            
            if not cluster_products:
                continue
            
            # Analyze cluster characteristics
            characteristics = {
                "size": len(cluster_products),
                "avg_price": np.mean([p.get('price', 0) for p in cluster_products]),
                "price_range": {
                    "min": min((p.get('price', 0) for p in cluster_products), default=0),
                    "max": max((p.get('price', 0) for p in cluster_products), default=0)
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
            if isinstance(item_list, list):
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
        """Get size of a cluster from characteristics."""
        # Use stored size from characteristics instead of counting labels
        if cluster_id in self.cluster_characteristics:
            return self.cluster_characteristics[cluster_id].get('size', 0)
        return 0
    
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
    
    async def _update_clusters_in_neo4j_batch(
        self,
        products: List[Dict[str, Any]],
        labels: np.ndarray
    ):
        """Update cluster information in Neo4j using batch operations."""
        if not self.product_kg or not hasattr(self.product_kg, 'query'):
            return
        
        try:
            # Prepare batch update data
            batch_data = []
            for i, product in enumerate(products):
                if i < len(labels):
                    product_id = product.get('id')
                    if product_id:
                        batch_data.append({
                            "product_id": product_id,
                            "cluster_id": int(labels[i])
                        })
            
            if not batch_data:
                return
            
            # Batch update query
            query = """
            UNWIND $batch AS row
            MATCH (p:Product {id: row.product_id})
            SET p.cluster = row.cluster_id
            """
            
            # Process in smaller batches to avoid overwhelming Neo4j
            for i in range(0, len(batch_data), 50):
                batch_chunk = batch_data[i:i+50]
                await self.product_kg.query(query, {"batch": batch_chunk})
                await asyncio.sleep(0.1)  # Small delay between batches
            
            logger.info(f"Updated cluster information for {len(batch_data)} products in Neo4j")
            
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
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        return {
            "cached_labels": len(self.cluster_labels),
            "max_cached_labels": self.max_cached_labels,
            "cluster_characteristics": len(self.cluster_characteristics),
            "batch_size": self.batch_size,
            "sample_size": self.sample_size,
            "use_minibatch": self.use_minibatch
        }
