"""
Ensemble Recommendation System for AI Stylist.

This module implements an ensemble recommendation system that combines
multiple recommenders for more robust and accurate recommendations.
Compatible with CAMEL-AI 0.2.64.

FIXED: Uses centralized imports and proper error handling.
"""

import logging
import json
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter

# FIXED: Use centralized imports with proper error handling
from camel_imports import (
    CAMEL_AVAILABLE,
    ChatAgent,
    BaseMessage,
    CompatibilityLayer
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ensemble_recommender")

class EnsembleRecommender:
    """
    Implements an ensemble recommendation system that combines multiple
    recommenders for more robust and accurate recommendations.
    
    FIXED: Uses proper error handling for all CAMEL operations.
    """
    
    def __init__(
        self, 
        product_kg, 
        product_retriever=None, 
        stylist_agent=None
    ):
        """
        Initialize the ensemble recommender.
        
        Args:
            product_kg: Neo4j product knowledge graph instance
            product_retriever: Product retriever (optional)
            stylist_agent: CAMEL stylist agent (optional)
        """
        logger.info("Initializing EnsembleRecommender with CAMEL 0.2.64 compatibility")
        self.product_kg = product_kg
        self.product_retriever = product_retriever
        self.stylist_agent = stylist_agent
        self.recommenders = []
        self.weights = {}
        
        # Check CAMEL availability
        if not CAMEL_AVAILABLE:
            logger.warning("CAMEL-AI not fully available, using fallback implementations")
        
        # Default weights for different recommendation types
        self.default_weights = {
            "multi_cluster": 1.0,
            "hybrid_visual": 1.0,
            "rfm_apriori": 1.2,  # Higher weight for personalized recommendations
            "memory_rag": 1.3,    # Higher weight for memory-based recommendations
            "similar": 0.8,       # Lower weight for basic similarity
            "popular": 0.6        # Lower weight for popular products
        }
    
    def add_recommender(self, recommender, weight=1.0, name=None):
        """
        Add a recommender to the ensemble.
        
        Args:
            recommender: Recommender instance
            weight: Weight for this recommender (higher = more important)
            name: Name of the recommender (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if recommender is None:
            logger.warning("Cannot add None as a recommender")
            return False
            
        # Generate name if not provided
        if name is None:
            name = recommender.__class__.__name__
            
        # Add to recommenders list
        self.recommenders.append(recommender)
        
        # Set weight
        self.weights[name] = weight
        
        logger.info(f"Added recommender: {name} with weight {weight}")
        return True
    
    def get_recommendations(
        self, 
        user_id: Optional[str] = None, 
        session_id: Optional[str] = None, 
        product_id: Optional[str] = None, 
        query: Optional[str] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get ensemble recommendations using weighted voting.
        
        Args:
            user_id: Optional user ID for personalization
            session_id: Optional session ID for context
            product_id: Optional product ID for similar products
            query: Optional search query to refine recommendations
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info("Getting ensemble recommendations")
        
        if not self.recommenders:
            logger.warning("No recommenders available")
            
            # Fallback to basic product retrieval
            if product_id:
                return self._get_fallback_similar_products(product_id, limit)
            elif query and self.product_retriever:
                return self._get_fallback_query_products(query, limit)
            elif hasattr(self.product_kg, 'get_popular_products'):
                return self._get_fallback_popular_products(limit)
            else:
                return []
        
        # Collect recommendations from all recommenders
        all_recommendations = []
        
        for recommender in self.recommenders:
            recommendations = []
            recommender_name = recommender.__class__.__name__
            recommender_weight = self.weights.get(recommender_name, 1.0)
            
            try:
                recommendations = self._get_recommendations_from_recommender(
                    recommender, user_id, session_id, product_id, query, limit
                )
                
                # Add recommendations with weight
                if recommendations:
                    logger.info(f"Got {len(recommendations)} recommendations from {recommender_name}")
                    
                    all_recommendations.append({
                        'recommender': recommender_name,
                        'weight': recommender_weight,
                        'recommendations': recommendations
                    })
            except Exception as e:
                logger.error(f"Error getting recommendations from {recommender_name}: {e}")
        
        # Add basic product retrieval if needed
        if product_id and (not all_recommendations or len(all_recommendations) < 2):
            try:
                similar_products = self._get_fallback_similar_products(product_id, limit)
                
                if similar_products:
                    logger.info(f"Got {len(similar_products)} similar products")
                    
                    all_recommendations.append({
                        'recommender': 'similar',
                        'weight': self.default_weights.get('similar', 0.8),
                        'recommendations': similar_products
                    })
            except Exception as e:
                logger.error(f"Error getting similar products: {e}")
        
        # Add popular products if needed
        if not all_recommendations or len(all_recommendations) < 2:
            try:
                popular_products = self._get_fallback_popular_products(limit)
                
                if popular_products:
                    logger.info(f"Got {len(popular_products)} popular products")
                    
                    all_recommendations.append({
                        'recommender': 'popular',
                        'weight': self.default_weights.get('popular', 0.6),
                        'recommendations': popular_products
                    })
            except Exception as e:
                logger.error(f"Error getting popular products: {e}")
        
        # If still no recommendations, return empty list
        if not all_recommendations:
            logger.warning("No recommendations available")
            return []
        
        # Calculate weighted votes
        product_votes = {}
        
        for recommender_data in all_recommendations:
            weight = recommender_data['weight']
            
            for i, product in enumerate(recommender_data['recommendations']):
                # Get product ID
                product_id = product.get('id')
                if not product_id:
                    continue
                    
                # Position-based weight (earlier = better)
                position_weight = 1.0 - (i / (limit * 2))
                
                # Initialize if not exists
                if product_id not in product_votes:
                    product_votes[product_id] = {
                        'product': product,
                        'score': 0.0,
                        'sources': []
                    }
                
                # Add weighted vote
                vote_weight = weight * position_weight
                product_votes[product_id]['score'] += vote_weight
                product_votes[product_id]['sources'].append(recommender_data['recommender'])
        
        # Sort by score
        sorted_products = sorted(
            product_votes.values(), 
            key=lambda x: x['score'], 
            reverse=True
        )
        
        # Get top recommendations
        top_recommendations = []
        
        for item in sorted_products[:limit]:
            product = item['product']
            
            # Add recommendation sources and score
            product['recommendation_score'] = item['score']
            product['recommendation_sources'] = item['sources']
            
            top_recommendations.append(product)
        
        # If we have a stylist agent, let it filter and explain the recommendations
        if self.stylist_agent and top_recommendations and CAMEL_AVAILABLE:
            try:
                # Add explanations to the recommendations
                self._add_stylist_explanations(top_recommendations, user_id, query, product_id)
            except Exception as e:
                logger.error(f"Error adding stylist explanations: {e}")
        
        logger.info(f"Found {len(top_recommendations)} ensemble recommendations")
        return top_recommendations
    
    def _get_recommendations_from_recommender(
        self, 
        recommender, 
        user_id, 
        session_id, 
        product_id, 
        query, 
        limit
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations from a specific recommender with error handling.
        
        Args:
            recommender: Recommender instance
            user_id: User ID
            session_id: Session ID
            product_id: Product ID
            query: Query string
            limit: Limit
            
        Returns:
            List of recommendations
        """
        try:
            # Call appropriate method based on parameters
            if product_id is not None and hasattr(recommender, 'get_similar_products'):
                return recommender.get_similar_products(product_id, limit)
                
            elif product_id is not None and hasattr(recommender, 'get_visual_recommendations'):
                return recommender.get_visual_recommendations(product_id, limit)
                
            elif product_id is not None and hasattr(recommender, 'get_recommendations'):
                # Check if method accepts product_id parameter
                import inspect
                sig = inspect.signature(recommender.get_recommendations)
                if 'product_id' in sig.parameters:
                    return recommender.get_recommendations(product_id=product_id, limit=limit)
                
            elif user_id is not None and hasattr(recommender, 'get_personalized_recommendations'):
                return recommender.get_personalized_recommendations(user_id, query=query, limit=limit)
                
            elif user_id is not None and hasattr(recommender, 'get_recommendations'):
                # Check if method accepts user_id parameter
                import inspect
                sig = inspect.signature(recommender.get_recommendations)
                if 'user_id' in sig.parameters:
                    return recommender.get_recommendations(user_id=user_id, limit=limit)
                
            elif query is not None and hasattr(recommender, 'search_by_natural_language'):
                return recommender.search_by_natural_language(query, limit)
                
            elif query is not None and hasattr(recommender, 'search_products'):
                return recommender.search_products(query, limit)
                
            elif hasattr(recommender, 'get_recommendations'):
                # Generic recommendation method
                return recommender.get_recommendations(limit=limit)
                
            return []
            
        except Exception as e:
            logger.error(f"Error calling recommender method: {e}")
            return []
    
    def _get_fallback_similar_products(self, product_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get similar products as fallback"""
        try:
            if hasattr(self.product_kg, 'get_similar_products'):
                return self.product_kg.get_similar_products(product_id, limit)
        except Exception as e:
            logger.error(f"Error getting fallback similar products: {e}")
        return []
    
    def _get_fallback_query_products(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Get query-based products as fallback"""
        try:
            if self.product_retriever and hasattr(self.product_retriever, 'search_by_natural_language'):
                return self.product_retriever.search_by_natural_language(query, limit)
        except Exception as e:
            logger.error(f"Error getting fallback query products: {e}")
        return []
    
    def _get_fallback_popular_products(self, limit: int) -> List[Dict[str, Any]]:
        """Get popular products as fallback"""
        try:
            if hasattr(self.product_kg, 'get_popular_products'):
                return self.product_kg.get_popular_products(limit)
        except Exception as e:
            logger.error(f"Error getting fallback popular products: {e}")
        return []
    
    def _add_stylist_explanations(
        self, 
        recommendations: List[Dict[str, Any]], 
        user_id: Optional[str] = None, 
        query: Optional[str] = None, 
        reference_product_id: Optional[str] = None
    ):
        """
        Add stylist explanations to recommendations.
        
        FIXED: Uses CompatibilityLayer for message creation.
        
        Args:
            recommendations: List of recommendations to explain
            user_id: Optional user ID for personalization
            query: Optional search query that led to these recommendations
            reference_product_id: Optional reference product ID
        """
        if not self.stylist_agent or not recommendations or not CAMEL_AVAILABLE:
            return
            
        try:
            # Create a prompt for the stylist agent
            prompt = "As a fashion stylist, explain why these products would be perfect recommendations"
            
            if user_id:
                prompt += f" for user {user_id}"
                
            if query:
                prompt += f" who is looking for {query}"
                
            if reference_product_id:
                try:
                    reference_product = self.product_kg.get_product_details(reference_product_id)
                    if reference_product:
                        prompt += f" based on their interest in {reference_product.get('title')}"
                except Exception as e:
                    logger.warning(f"Could not get reference product details: {e}")
            
            prompt += ":\n\n"
            
            # Add products to the prompt
            for i, product in enumerate(recommendations):
                prompt += f"{i+1}. {product.get('title')} - ${product.get('price', 0)}"
                
                if product.get('categories'):
                    prompt += f" - Categories: {', '.join(product.get('categories'))}"
                    
                prompt += f"\n{product.get('description', '')}\n\n"
            
            prompt += "For each recommendation, explain:\n"
            prompt += "1. Why it's a good recommendation based on the context\n"
            prompt += "2. How it complements other recommendations\n"
            prompt += "3. Specific styling tips for wearing or using this item\n\n"
            prompt += "Keep your explanations conversational, personable, and focused on the stylistic aspects."
            
            # Get stylist response using CompatibilityLayer
            try:
                if CompatibilityLayer:
                    user_message = CompatibilityLayer.create_user_message(
                        content=prompt,
                        role_name="User"
                    )
                    
                    if user_message and hasattr(self.stylist_agent, 'step'):
                        response = self.stylist_agent.step(user_message)
                        explanations = response.msg.content if hasattr(response, 'msg') else str(response)
                        
                        # Process explanations
                        self._process_explanations(recommendations, explanations)
                    else:
                        logger.warning("Could not create user message or stylist agent step failed")
                else:
                    logger.warning("CompatibilityLayer not available for stylist explanations")
                    
            except Exception as e:
                logger.error(f"Error getting stylist explanations: {e}")
                
        except Exception as e:
            logger.error(f"Error adding stylist explanations: {e}")
    
    def _process_explanations(self, recommendations: List[Dict[str, Any]], explanations: str):
        """
        Process and add stylist explanations to recommendations.
        
        Args:
            recommendations: List of recommendations to add explanations to
            explanations: Stylist explanations text
        """
        if not explanations or not recommendations:
            return
            
        try:
            # Split explanations by recommendation number
            lines = explanations.split('\n')
            current_rec_index = -1
            current_explanation = []
            
            for line in lines:
                # Check if line starts with a number followed by period or bracket
                if line.strip() and (
                    line.strip()[0].isdigit() and 
                    len(line.strip()) > 1 and 
                    (line.strip()[1] == '.' or line.strip()[1] == ')')
                ):
                    # Save previous explanation if any
                    if current_rec_index >= 0 and current_rec_index < len(recommendations) and current_explanation:
                        explanation_text = '\n'.join(current_explanation).strip()
                        if explanation_text:
                            recommendations[current_rec_index]['stylist_explanation'] = explanation_text
                    
                    # Start new explanation
                    try:
                        # Extract recommendation number
                        num_str = line.strip()[0]
                        current_rec_index = int(num_str) - 1
                        current_explanation = [line.strip()]
                    except (ValueError, IndexError):
                        # Not a valid recommendation number
                        current_explanation.append(line)
                else:
                    # Continue current explanation
                    current_explanation.append(line)
            
            # Save last explanation
            if current_rec_index >= 0 and current_rec_index < len(recommendations) and current_explanation:
                explanation_text = '\n'.join(current_explanation).strip()
                if explanation_text:
                    recommendations[current_rec_index]['stylist_explanation'] = explanation_text
            
            # If we couldn't parse individual explanations, add the whole text to all recommendations
            if not any('stylist_explanation' in rec for rec in recommendations):
                for recommendation in recommendations:
                    recommendation['stylist_explanation'] = explanations
                    
        except Exception as e:
            logger.error(f"Error processing stylist explanations: {e}")
            # Add raw explanations to all recommendations
            for recommendation in recommendations:
                recommendation['stylist_explanation'] = explanations
