"""
Enhanced Asynchronous Recommender Manager for AI Stylist.

This module provides a recommender manager that combines different recommendation
approaches including RFM-Apriori, neural recommendations, and knowledge graph.
Compatible with CAMEL-AI 0.2.43.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhanced_recommender_manager_async")

# Import AsyncCAMELService
from async_camel_service import AsyncCAMELService

class EnhancedRecommenderManagerAsync:
    """
    Enhanced recommender manager with multiple recommendation strategies.
    Uses AsyncCAMELService for proper asynchronous integration.
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
            product_kg: Product knowledge graph instance
            product_retriever: Product retriever instance (optional)
            memory_setup_func: Function to set up memory (optional)
            stylist_agent: Stylist agent instance (optional)
        """
        logger.info("Initializing Enhanced Recommender Manager")
        self.product_kg = product_kg
        self.product_retriever = product_retriever
        self.memory_setup_func = memory_setup_func
        self.stylist_agent = stylist_agent
        
        # Initialize CAMEL service
        self.camel_service = AsyncCAMELService()
        
        # Create recommender components
        self.recommenders = {}
        self.user_preferences = {}
        self.interactions = {}
        
        # Initialize ensemble recommender
        self.ensemble = None
        
        # Initialize recommenders
        asyncio.create_task(self._initialize_recommenders())
    
    async def _initialize_recommenders(self):
        """Initialize the different recommender components"""
        try:
            # Optional: Initialize RFM-Apriori recommender if available
            try:
                from rfm_apriori_recommender import RFMAprioriRecommender
                
                def memory_setup_wrapper():
                    """Wrapper for memory setup function to handle async/sync difference"""
                    if self.memory_setup_func:
                        return self.memory_setup_func()
                    return None
                
                rfm_recommender = RFMAprioriRecommender(
                    product_kg=self.product_kg,
                    memory_setup_func=memory_setup_wrapper
                )
                
                self.recommenders['rfm_apriori'] = rfm_recommender
                logger.info("RFM-Apriori recommender initialized")
                
                # Load transactions in background
                asyncio.create_task(self._load_transactions())
                
            except ImportError:
                logger.warning("RFM-Apriori recommender not available")
            
            # Create ensemble recommender (placeholder for now)
            self.ensemble = EnsembleRecommender(
                recommenders=self.recommenders,
                product_kg=self.product_kg,
                product_retriever=self.product_retriever,
                stylist_agent=self.stylist_agent
            )
            
            logger.info("Enhanced Recommender Manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing recommenders: {e}")
    
    async def _load_transactions(self):
        """Load transactions for RFM-Apriori recommender in background"""
        try:
            rfm_recommender = self.recommenders.get('rfm_apriori')
            if rfm_recommender:
                # Use a separate thread for this potentially intensive operation
                await asyncio.to_thread(rfm_recommender.load_transactions_from_neo4j)
                
                # Calculate RFM segments
                await asyncio.to_thread(rfm_recommender.calculate_rfm)
                
                # Find association rules
                await asyncio.to_thread(rfm_recommender.find_association_rules)
                
                logger.info("RFM-Apriori data loaded successfully")
        except Exception as e:
            logger.error(f"Error loading transactions: {e}")
    
    async def get_recommendations(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        product_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get enhanced recommendations using the ensemble approach.
        
        Args:
            user_id: Optional user ID for personalized recommendations
            session_id: Optional session ID for context-aware recommendations
            product_id: Optional product ID for similar products
            query: Optional query string for natural language search
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting recommendations for user {user_id} with query: {query}")
        
        try:
            # Use ensemble recommender as primary approach
            if self.ensemble:
                recommendations = await self.ensemble.get_recommendations(
                    user_id=user_id,
                    session_id=session_id,
                    product_id=product_id,
                    query=query,
                    limit=limit
                )
                
                if recommendations:
                    logger.info(f"Found {len(recommendations)} recommendations from ensemble")
                    return recommendations
            
            # Fallback to knowledge graph if ensemble fails
            if self.product_kg:
                if product_id:
                    # Get similar products
                    recommendations = await self.product_kg.get_similar_products(
                        product_id=product_id,
                        limit=limit
                    )
                    
                    if recommendations:
                        logger.info(f"Found {len(recommendations)} similar products")
                        return recommendations
                
                if query:
                    # Use category/tag search
                    recommendations = await self.product_kg.get_product_by_filter(
                        tag=query,
                        limit=limit
                    )
                    
                    if recommendations:
                        logger.info(f"Found {len(recommendations)} products by tag")
                        return recommendations
                
                # Fallback to popular products
                recommendations = await self.product_kg.get_popular_products(limit=limit)
                
                if recommendations:
                    logger.info(f"Found {len(recommendations)} popular products as fallback")
                    return recommendations
            
            # Last resort: empty list
            logger.warning("No recommendations found")
            return []
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {e}")
            return []
    
    def record_interaction(
        self,
        user_id: str,
        product_id: str,
        interaction_type: str = "viewed"
    ) -> bool:
        """
        Record a product interaction for recommendation improvement.
        
        Args:
            user_id: User ID
            product_id: Product ID
            interaction_type: Type of interaction (e.g., "viewed", "liked")
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not user_id or not product_id:
            return False
            
        try:
            # Store in user interactions
            if user_id not in self.interactions:
                self.interactions[user_id] = []
                
            # Add interaction with timestamp
            import datetime
            self.interactions[user_id].append({
                "product_id": product_id,
                "type": interaction_type,
                "timestamp": datetime.datetime.now()
            })
            
            # Update RFM-Apriori recommender if available
            rfm_recommender = self.recommenders.get('rfm_apriori')
            if rfm_recommender:
                rfm_recommender.add_transaction(
                    user_id=user_id,
                    product_id=product_id
                )
            
            logger.info(f"Recorded interaction for user {user_id}: {interaction_type} {product_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error recording interaction: {e}")
            return False
    
    def add_user_preference(
        self,
        user_id: str,
        preference_type: str,
        preference_value: Any
    ) -> bool:
        """
        Add a user preference for recommendation improvement.
        
        Args:
            user_id: User ID
            preference_type: Type of preference (e.g., "color", "style")
            preference_value: Value of the preference
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not user_id:
            return False
            
        try:
            # Initialize user preferences
            if user_id not in self.user_preferences:
                self.user_preferences[user_id] = {}
                
            # Update preference
            self.user_preferences[user_id][preference_type] = preference_value
            
            logger.info(f"Added preference for user {user_id}: {preference_type} = {preference_value}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding user preference: {e}")
            return False
    
    async def get_recommendations_for_product(
        self,
        product_id: str,
        user_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations based on a specific product.
        
        Args:
            product_id: Reference product ID
            user_id: Optional user ID for personalization
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting recommendations for product {product_id}")
        
        try:
            # Get the product details
            product = await self.product_kg.get_product_details(product_id)
            
            if not product:
                logger.warning(f"Product {product_id} not found")
                return []
                
            # Get personalized recommendations if user_id provided
            if user_id and 'rfm_apriori' in self.recommenders:
                # Run in separate thread to avoid blocking
                recommendations = await asyncio.to_thread(
                    self.recommenders['rfm_apriori'].get_personalized_recommendations,
                    user_id=user_id,
                    limit=limit
                )
                
                if recommendations:
                    logger.info(f"Found {len(recommendations)} personalized recommendations")
                    return recommendations
            
            # Get similar products from knowledge graph
            recommendations = await self.product_kg.get_similar_products(
                product_id=product_id,
                limit=limit
            )
            
            if recommendations:
                logger.info(f"Found {len(recommendations)} similar products")
                return recommendations
                
            # Fallback to products in same category
            category = product.get('categories', [])[0] if product.get('categories') else None
            
            if category:
                recommendations = await self.product_kg.get_products_by_category(
                    category=category,
                    limit=limit
                )
                
                if recommendations:
                    logger.info(f"Found {len(recommendations)} products in category {category}")
                    return recommendations
            
            # Fallback to popular products
            recommendations = await self.product_kg.get_popular_products(limit=limit)
            
            if recommendations:
                logger.info(f"Found {len(recommendations)} popular products as fallback")
                return recommendations
                
            return []
            
        except Exception as e:
            logger.error(f"Error getting recommendations for product: {e}")
            return []
            
    async def close(self):
        """Clean up resources"""
        for name, recommender in self.recommenders.items():
            if hasattr(recommender, 'close'):
                try:
                    await recommender.close()
                except Exception as e:
                    logger.error(f"Error closing recommender {name}: {e}")
        
        await self.camel_service.close()


class EnsembleRecommender:
    """
    Ensemble recommender that combines multiple recommendation approaches.
    Uses AsyncCAMELService for CAMEL operations.
    """
    
    def __init__(
        self,
        recommenders: Dict[str, Any],
        product_kg,
        product_retriever=None,
        stylist_agent=None
    ):
        """
        Initialize the ensemble recommender.
        
        Args:
            recommenders: Dictionary of recommender instances
            product_kg: Product knowledge graph instance
            product_retriever: Product retriever instance (optional)
            stylist_agent: Stylist agent instance (optional)
        """
        self.recommenders = recommenders
        self.product_kg = product_kg
        self.product_retriever = product_retriever
        self.stylist_agent = stylist_agent
        
        # Initialize CAMEL service
        self.camel_service = AsyncCAMELService()
        
        logger.info("Ensemble recommender initialized")
    
    async def get_recommendations(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        product_id: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations using an ensemble approach.
        
        Args:
            user_id: Optional user ID for personalized recommendations
            session_id: Optional session ID for context-aware recommendations
            product_id: Optional product ID for similar products
            query: Optional query string for natural language search
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Ensemble getting recommendations for user {user_id}")
        
        results = {}
        
        try:
            # Collect recommendations from different sources
            tasks = []
            
            # 1. If product_id provided, get similar products
            if product_id:
                tasks.append(self._get_similar_products(product_id, limit))
            
            # 2. If user_id provided, get personalized recommendations
            if user_id:
                tasks.append(self._get_personalized_recommendations(user_id, limit))
            
            # 3. If query provided, get search results
            if query:
                tasks.append(self._get_query_recommendations(query, limit))
            
            # 4. Get popular products as fallback
            tasks.append(self._get_popular_products(limit))
            
            # Run tasks concurrently
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            all_recommendations = []
            
            for result in results_list:
                if isinstance(result, Exception):
                    logger.warning(f"Error in recommendation task: {result}")
                    continue
                    
                if result and isinstance(result, list):
                    all_recommendations.extend(result)
            
            # Deduplicate results
            unique_recommendations = []
            seen_ids = set()
            
            for product in all_recommendations:
                product_id = product.get('id')
                if product_id and product_id not in seen_ids:
                    unique_recommendations.append(product)
                    seen_ids.add(product_id)
            
            # Limit results
            return unique_recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error in ensemble recommender: {e}")
            return []
    
    async def _get_similar_products(self, product_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get similar products"""
        try:
            return await self.product_kg.get_similar_products(product_id, limit)
        except Exception as e:
            logger.error(f"Error getting similar products: {e}")
            return []
    
    async def _get_personalized_recommendations(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get personalized recommendations"""
        try:
            rfm_recommender = self.recommenders.get('rfm_apriori')
            if rfm_recommender:
                # Run in separate thread to avoid blocking
                return await asyncio.to_thread(
                    rfm_recommender.get_personalized_recommendations,
                    user_id=user_id,
                    limit=limit
                )
            return []
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            return []
    
    async def _get_query_recommendations(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Get recommendations based on query"""
        try:
            if self.product_retriever:
                return await self.product_retriever.search_by_natural_language(query, limit)
            elif self.product_kg:
                return await self.product_kg.get_product_by_filter(tag=query, limit=limit)
            return []
        except Exception as e:
            logger.error(f"Error getting query recommendations: {e}")
            return []
    
    async def _get_popular_products(self, limit: int) -> List[Dict[str, Any]]:
        """Get popular products"""
        try:
            return await self.product_kg.get_popular_products(limit)
        except Exception as e:
            logger.error(f"Error getting popular products: {e}")
            return []
    
    async def get_agent_recommendations(
        self,
        query: str,
        user_id: Optional[str] = None,
        memory=None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recommendations using the stylist agent.
        
        Args:
            query: User query
            user_id: Optional user ID
            memory: Optional memory instance
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        if not self.stylist_agent:
            logger.warning("No stylist agent available for agent recommendations")
            return []
            
        try:
            # Get potential products based on query
            products = []
            
            if self.product_retriever:
                products = await self.product_retriever.search_by_natural_language(query, limit=limit*2)
            
            if not products and self.product_kg:
                # Extract potential category or tag from query
                query_terms = query.lower().split()
                categories = ["dress", "shirt", "pants", "jeans", "skirt", "shoes"]
                
                category = None
                for term in query_terms:
                    if term in categories:
                        category = term
                        break
                
                if category:
                    products = await self.product_kg.get_products_by_category(category, limit=limit*2)
                else:
                    # Try as tag
                    products = await self.product_kg.get_product_by_filter(tag=query, limit=limit*2)
            
            if not products:
                products = await self.product_kg.get_popular_products(limit=limit*2)
            
            if not products:
                logger.warning("No products found for agent recommendations")
                return []
            
            # Use the stylist agent to filter products
            # First, create a prompt with product details and user query
            prompt = f"The user is looking for products matching this query: '{query}'\n\n"
            prompt += "Here are some potential products:\n\n"
            
            for i, product in enumerate(products[:10]):  # Limit to 10 products to avoid overloading
                prompt += f"Product {i+1}: {product.get('title', 'Untitled')}\n"
                prompt += f"- ID: {product.get('id', '')}\n"
                prompt += f"- Price: ${product.get('price', 0)}\n"
                prompt += f"- Categories: {', '.join(product.get('categories', []))}\n"
                if product.get('description'):
                    # Truncate long descriptions
                    desc = product.get('description', '')
                    if len(desc) > 100:
                        desc = desc[:100] + "..."
                    prompt += f"- Description: {desc}\n"
                prompt += "\n"
            
            prompt += f"\nPlease select the top {limit} products that best match the user's query. "
            prompt += "Return your answer as a list of product IDs separated by commas, like this: PROD-1, PROD-2, PROD-3"
            
            # Process with the agent
            response = await self.camel_service.process_message(
                agent=self.stylist_agent,
                message=prompt
            )
            
            response_text = response.msg.content
            
            # Extract product IDs from response
            import re
            product_id_pattern = r'\b([A-Za-z0-9-]+)\b'
            product_ids = re.findall(product_id_pattern, response_text)
            
            # Get product details for selected IDs
            selected_products = []
            seen_ids = set()
            
            for product_id in product_ids:
                if product_id in seen_ids:
                    continue
                    
                # First check if the product is in our retrieved products
                found = False
                for product in products:
                    if product.get('id') == product_id:
                        selected_products.append(product)
                        seen_ids.add(product_id)
                        found = True
                        break
                
                # If not found, try to get from knowledge graph
                if not found:
                    product = await self.product_kg.get_product_details(product_id)
                    if product:
                        selected_products.append(product)
                        seen_ids.add(product_id)
            
            # If we didn't get enough products, add some from original results
            if len(selected_products) < limit:
                for product in products:
                    if len(selected_products) >= limit:
                        break
                        
                    product_id = product.get('id')
                    if product_id and product_id not in seen_ids:
                        selected_products.append(product)
                        seen_ids.add(product_id)
            
            logger.info(f"Agent selected {len(selected_products)} products for query: {query}")
            return selected_products[:limit]
            
        except Exception as e:
            logger.error(f"Error getting agent recommendations: {e}")
            return []
