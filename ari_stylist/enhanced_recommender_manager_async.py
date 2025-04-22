"""
Enhanced Recommender Manager for AI Stylist.

This module provides a manager for creating and integrating all the enhanced
recommendation systems into the AI Stylist application.
Compatible with CAMEL-AI 0.2.43.
"""

import logging
import os
from typing import Dict, List, Any, Optional, Tuple

# Import the recommender systems
from multi_cluster_recommender import MultiClusterRecommender
from hybrid_visual_recommender import HybridVisualRecommender
from rfm_apriori_recommender import RFMAprioriRecommender
from memory_rag_recommender import MemoryRAGRecommender
from ensemble_recommender import EnsembleRecommender

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhanced_recommender_manager")

class EnhancedRecommenderManagerAsync:
    """
    Manages the creation, configuration, and integration of enhanced
    recommendation systems for the AI Stylist application.
    """
    
    def __init__(
        self, 
        product_kg, 
        product_retriever=None, 
        memory_setup_func=None, 
        stylist_agent=None
    ):
        """
        Initialize the enhanced recommender manager.
        
        Args:
            product_kg: Neo4j product knowledge graph instance
            product_retriever: Product retriever (optional)
            memory_setup_func: Function to set up memory (optional)
            stylist_agent: CAMEL stylist agent (optional)
        """
        logger.info("Initializing EnhancedRecommenderManager")
        self.product_kg = product_kg
        self.product_retriever = product_retriever
        self.memory_setup_func = memory_setup_func
        self.stylist_agent = stylist_agent
        
        # Dictionary to store recommender instances
        self.recommenders = {}
        
        # Ensemble recommender
        self.ensemble = None
    
    def create_all_recommenders(self, initialize_data=False) -> Dict[str, Any]:
        """
        Create all recommender systems.
        
        Args:
            initialize_data: Whether to initialize data for recommenders
            
        Returns:
            Dictionary of created recommenders
        """
        logger.info("Creating all recommenders")
        
        try:
            # Create MultiClusterRecommender
            multi_cluster = self.create_multi_cluster_recommender()
            if multi_cluster:
                self.recommenders['multi_cluster'] = multi_cluster
                
            # Create HybridVisualRecommender
            hybrid_visual = self.create_hybrid_visual_recommender()
            if hybrid_visual:
                self.recommenders['hybrid_visual'] = hybrid_visual
                
            # Create RFMAprioriRecommender
            rfm_apriori = self.create_rfm_apriori_recommender()
            if rfm_apriori:
                self.recommenders['rfm_apriori'] = rfm_apriori
                
            # Create MemoryRAGRecommender
            memory_rag = self.create_memory_rag_recommender()
            if memory_rag:
                self.recommenders['memory_rag'] = memory_rag
                
            # Create EnsembleRecommender
            self.ensemble = self.create_ensemble_recommender()
            
            # Initialize data if needed
            if initialize_data:
                self.initialize_recommender_data()
                
            logger.info(f"Created {len(self.recommenders)} recommenders")
            return self.recommenders
            
        except Exception as e:
            logger.error(f"Error creating recommenders: {e}")
            return {}
    
    def create_multi_cluster_recommender(self) -> Optional[MultiClusterRecommender]:
        """
        Create a MultiClusterRecommender.
        
        Returns:
            MultiClusterRecommender instance or None
        """
        try:
            recommender = MultiClusterRecommender(
                product_kg=self.product_kg,
                n_clusters=8
            )
            
            logger.info("Created MultiClusterRecommender")
            return recommender
            
        except Exception as e:
            logger.error(f"Error creating MultiClusterRecommender: {e}")
            return None
    
    def create_hybrid_visual_recommender(self) -> Optional[HybridVisualRecommender]:
        """
        Create a HybridVisualRecommender.
        
        Returns:
            HybridVisualRecommender instance or None
        """
        try:
            recommender = HybridVisualRecommender(
                product_kg=self.product_kg,
                storage_path="product_data/visual_embeddings"
            )
            
            logger.info("Created HybridVisualRecommender")
            return recommender
            
        except Exception as e:
            logger.error(f"Error creating HybridVisualRecommender: {e}")
            return None
    
    def create_rfm_apriori_recommender(self) -> Optional[RFMAprioriRecommender]:
        """
        Create a RFMAprioriRecommender.
        
        Returns:
            RFMAprioriRecommender instance or None
        """
        try:
            recommender = RFMAprioriRecommender(
                product_kg=self.product_kg,
                memory_setup_func=self.memory_setup_func
            )
            
            logger.info("Created RFMAprioriRecommender")
            return recommender
            
        except Exception as e:
            logger.error(f"Error creating RFMAprioriRecommender: {e}")
            return None
    
    def create_memory_rag_recommender(self) -> Optional[MemoryRAGRecommender]:
        """
        Create a MemoryRAGRecommender.
        
        Returns:
            MemoryRAGRecommender instance or None
        """
        try:
            recommender = MemoryRAGRecommender(
                product_kg=self.product_kg,
                memory_setup_func=self.memory_setup_func
            )
            
            logger.info("Created MemoryRAGRecommender")
            return recommender
            
        except Exception as e:
            logger.error(f"Error creating MemoryRAGRecommender: {e}")
            return None
    
    def create_ensemble_recommender(self) -> Optional[EnsembleRecommender]:
        """
        Create an EnsembleRecommender.
        
        Returns:
            EnsembleRecommender instance or None
        """
        try:
            # Create ensemble
            ensemble = EnsembleRecommender(
                product_kg=self.product_kg,
                product_retriever=self.product_retriever,
                stylist_agent=self.stylist_agent
            )
            
            # Add individual recommenders
            for name, recommender in self.recommenders.items():
                if name == 'multi_cluster':
                    ensemble.add_recommender(recommender, weight=1.0, name=name)
                elif name == 'hybrid_visual':
                    ensemble.add_recommender(recommender, weight=1.0, name=name)
                elif name == 'rfm_apriori':
                    ensemble.add_recommender(recommender, weight=1.2, name=name)
                elif name == 'memory_rag':
                    ensemble.add_recommender(recommender, weight=1.3, name=name)
                else:
                    ensemble.add_recommender(recommender, name=name)
            
            logger.info("Created EnsembleRecommender")
            return ensemble
            
        except Exception as e:
            logger.error(f"Error creating EnsembleRecommender: {e}")
            return None
    
    def initialize_recommender_data(self) -> bool:
        """
        Initialize data for all recommenders.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Initializing recommender data")
        success = True
        
        try:
            # Initialize MultiClusterRecommender
            if 'multi_cluster' in self.recommenders:
                try:
                    logger.info("Clustering all products")
                    self.recommenders['multi_cluster'].cluster_all_products()
                except Exception as e:
                    logger.error(f"Error clustering products: {e}")
                    success = False
            
            # Initialize HybridVisualRecommender
            if 'hybrid_visual' in self.recommenders:
                try:
                    logger.info("Indexing all products for visual search")
                    self.recommenders['hybrid_visual'].index_all_products()
                except Exception as e:
                    logger.error(f"Error indexing products for visual search: {e}")
                    success = False
            
            # Initialize RFMAprioriRecommender
            if 'rfm_apriori' in self.recommenders:
                try:
                    logger.info("Loading transactions and generating association rules")
                    self.recommenders['rfm_apriori'].load_transactions_from_neo4j()
                    self.recommenders['rfm_apriori'].calculate_rfm()
                    self.recommenders['rfm_apriori'].find_association_rules()
                except Exception as e:
                    logger.error(f"Error initializing RFMAprioriRecommender: {e}")
                    success = False
            
            logger.info("Recommender data initialization complete")
            return success
            
        except Exception as e:
            logger.error(f"Error initializing recommender data: {e}")
            return False
    
    def get_recommendations(
        self, 
        user_id: Optional[str] = None, 
        session_id: Optional[str] = None, 
        product_id: Optional[str] = None, 
        query: Optional[str] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations using the ensemble recommender.
        
        Args:
            user_id: Optional user ID for personalization
            session_id: Optional session ID for context
            product_id: Optional product ID for similar products
            query: Optional search query to refine recommendations
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        # Use ensemble if available
        if self.ensemble:
            return self.ensemble.get_recommendations(
                user_id=user_id,
                session_id=session_id,
                product_id=product_id,
                query=query,
                limit=limit
            )
        
        # Fallback to individual recommenders if ensemble not available
        if product_id:
            # Try memory RAG first
            if 'memory_rag' in self.recommenders and user_id:
                try:
                    return self.recommenders['memory_rag'].get_personalized_recommendations(
                        user_id=user_id,
                        query=f"Products similar to {product_id}",
                        limit=limit
                    )
                except Exception:
                    pass
            
            # Try hybrid visual
            if 'hybrid_visual' in self.recommenders:
                try:
                    return self.recommenders['hybrid_visual'].get_visual_recommendations(
                        product_id=product_id,
                        limit=limit
                    )
                except Exception:
                    pass
            
            # Try multi cluster
            if 'multi_cluster' in self.recommenders:
                try:
                    return self.recommenders['multi_cluster'].get_recommendations(
                        product_id=product_id,
                        limit=limit
                    )
                except Exception:
                    pass
            
            # Fallback to product_kg
            return self.product_kg.get_similar_products(product_id, limit)
        
        # For user-based recommendations
        if user_id:
            # Try memory RAG first
            if 'memory_rag' in self.recommenders:
                try:
                    return self.recommenders['memory_rag'].get_personalized_recommendations(
                        user_id=user_id,
                        query=query,
                        limit=limit
                    )
                except Exception:
                    pass
            
            # Try RFM Apriori
            if 'rfm_apriori' in self.recommenders:
                try:
                    return self.recommenders['rfm_apriori'].get_personalized_recommendations(
                        user_id=user_id,
                        limit=limit
                    )
                except Exception:
                    pass
        
        # For query-based recommendations
        if query and self.product_retriever:
            try:
                return self.product_retriever.search_by_natural_language(query, limit)
            except Exception:
                pass
        
        # Fallback to popular products
        if hasattr(self.product_kg, 'get_popular_products'):
            return self.product_kg.get_popular_products(limit)
        else:
            return []
    
    def record_interaction(
        self, 
        user_id: str, 
        product_id: str, 
        interaction_type: str
    ) -> bool:
        """
        Record a user interaction with a product.
        
        Args:
            user_id: User ID
            product_id: Product ID
            interaction_type: Type of interaction (e.g., "viewed", "liked", "purchased")
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        
        # Record in memory RAG
        if 'memory_rag' in self.recommenders:
            try:
                success = success and self.recommenders['memory_rag'].add_product_interaction(
                    user_id=user_id,
                    product_id=product_id,
                    interaction_type=interaction_type
                )
            except Exception as e:
                logger.error(f"Error recording interaction in memory RAG: {e}")
                success = False
        
        # Record in RFM Apriori
        if 'rfm_apriori' in self.recommenders and interaction_type == 'purchased':
            try:
                success = success and self.recommenders['rfm_apriori'].add_transaction(
                    user_id=user_id,
                    product_id=product_id
                )
            except Exception as e:
                logger.error(f"Error recording interaction in RFM Apriori: {e}")
                success = False
        
        return success
    
    def add_user_preference(
        self, 
        user_id: str, 
        preference_type: str, 
        preference_value: Any
    ) -> bool:
        """
        Add a user preference.
        
        Args:
            user_id: User ID
            preference_type: Type of preference (e.g., "color", "style", "budget")
            preference_value: Value of the preference
            
        Returns:
            True if successful, False otherwise
        """
        success = True
        
        # Add to memory RAG
        if 'memory_rag' in self.recommenders:
            try:
                success = success and self.recommenders['memory_rag'].add_user_preference(
                    user_id=user_id,
                    preference_type=preference_type,
                    preference_value=preference_value
                )
            except Exception as e:
                logger.error(f"Error adding user preference to memory RAG: {e}")
                success = False
        
        return success