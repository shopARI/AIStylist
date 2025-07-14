"""
Memory-Enhanced RAG Recommendation System for AI Stylist.

This module implements a recommendation system that leverages the CAMEL memory
system to enhance recommendations based on conversation history.
Compatible with CAMEL-AI 0.2.64.

FIXED: Uses MemoryManager and proper error handling.
"""

import logging
import json
import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter

# FIXED: Use centralized imports and MemoryManager
from camel_imports import (
    CAMEL_AVAILABLE,
    LongtermAgentMemory,
    MemoryRecord,
    ScoreBasedContextCreator,
    OpenAIEmbedding,
    QdrantStorage,
    EmbeddingModelType,
    OpenAIBackendRole,
    CompatibilityLayer
)

# FIXED: Import MemoryManager for proper memory handling
from memory_integration_async import MemoryManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory_rag_recommender")

class MemoryRAGRecommender:
    """
    Implements a recommendation system that leverages the CAMEL memory system
    to enhance recommendations based on conversation history.
    
    FIXED: Uses MemoryManager and proper async memory handling.
    """
    
    def __init__(
        self, 
        product_kg, 
        memory=None,
        memory_setup_func=None,
        token_limit=2048
    ):
        """
        Initialize the memory-enhanced RAG recommender.
        
        Args:
            product_kg: Neo4j product knowledge graph instance
            memory: CAMEL memory instance (optional)
            memory_setup_func: Function to set up memory (optional)
            token_limit: Token limit for context window
        """
        logger.info("Initializing MemoryRAGRecommender with CAMEL 0.2.64 compatibility")
        self.product_kg = product_kg
        self.token_limit = token_limit
        
        # Check CAMEL availability
        if not CAMEL_AVAILABLE:
            logger.warning("CAMEL-AI not fully available, using fallback implementations")
        
        # FIXED: Initialize MemoryManager
        self.memory_manager = MemoryManager(product_kg) if product_kg else None
        
        # Initialize memory
        if memory is not None:
            self.memory = memory
            logger.info("Using provided memory instance")
        elif memory_setup_func is not None:
            try:
                # Handle both sync and async memory setup functions
                if hasattr(memory_setup_func, '__call__'):
                    # Try to call the function - handle both sync and async
                    import asyncio
                    try:
                        if asyncio.iscoroutinefunction(memory_setup_func):
                            # Async function - need to await it properly
                            self.memory = None  # Will be set up later when called in async context
                            self.memory_setup_func = memory_setup_func
                            logger.info("Memory setup function is async - will initialize later")
                        else:
                            # Sync function
                            self.memory = memory_setup_func()
                            logger.info("Memory initialized using sync setup function")
                    except Exception as e:
                        logger.error(f"Error calling memory setup function: {e}")
                        self.memory = self._create_default_memory(token_limit)
                else:
                    self.memory = self._create_default_memory(token_limit)
            except Exception as e:
                logger.error(f"Error initializing memory with setup function: {e}")
                self.memory = self._create_default_memory(token_limit)
        else:
            self.memory = self._create_default_memory(token_limit)
            logger.info("Created default memory instance")
    
    def _create_default_memory(self, token_limit: int) -> Optional[LongtermAgentMemory]:
        """
        Create a default memory instance.
        
        FIXED: Uses CompatibilityLayer for memory creation.
        
        Args:
            token_limit: Token limit for context window
            
        Returns:
            CAMEL memory instance or None
        """
        if not CAMEL_AVAILABLE or not CompatibilityLayer:
            logger.warning("CAMEL components not available for memory creation")
            return None
            
        try:
            memory = CompatibilityLayer.create_memory(
                token_limit=token_limit,
                enable_vector=True
            )
            
            if memory:
                logger.info("Created default memory using CompatibilityLayer")
                return memory
            else:
                logger.warning("CompatibilityLayer returned None memory")
                return None
                
        except Exception as e:
            logger.error(f"Error creating default memory: {e}")
            return None
    
    async def _ensure_memory_initialized(self):
        """
        Ensure memory is initialized for async operations.
        
        FIXED: Handles async memory setup properly.
        """
        if self.memory is None and hasattr(self, 'memory_setup_func') and self.memory_setup_func:
            try:
                self.memory = await self.memory_setup_func()
                logger.info("Memory initialized using async setup function")
            except Exception as e:
                logger.error(f"Error initializing memory async: {e}")
                if self.memory_manager:
                    try:
                        self.memory = await self.memory_manager.create_memory(
                            token_limit=self.token_limit,
                            enable_vector_db=True
                        )
                        logger.info("Memory initialized using MemoryManager fallback")
                    except Exception as e2:
                        logger.error(f"Error creating memory with MemoryManager: {e2}")
                        self.memory = None
    
    async def add_product_interaction(
        self, 
        user_id: str, 
        product_id: str, 
        interaction_type: str
    ) -> bool:
        """
        Add a product interaction to memory.
        
        FIXED: Uses MemoryManager for proper async handling.
        
        Args:
            user_id: User ID
            product_id: Product ID
            interaction_type: Type of interaction (e.g., "viewed", "liked", "purchased")
            
        Returns:
            True if successful, False otherwise
        """
        await self._ensure_memory_initialized()
        
        if not self.memory:
            logger.warning("Memory not available for adding product interaction")
            return False
            
        try:
            # Get product details
            if hasattr(self.product_kg, 'get_product_details'):
                product = await self.product_kg.get_product_details(product_id)
            else:
                logger.warning("Product KG does not support get_product_details")
                return False
                
            if not product:
                logger.warning(f"Product not found: {product_id}")
                return False
                
            # FIXED: Use MemoryManager for adding product interactions
            if self.memory_manager:
                success = await self.memory_manager.add_product_interaction(
                    memory=self.memory,
                    product=product,
                    interaction_type=interaction_type,
                    user_id=user_id
                )
                
                if success:
                    logger.info(f"Added product interaction to memory: {interaction_type} {product_id}")
                    return True
                else:
                    logger.warning(f"Failed to add product interaction to memory")
                    return False
            else:
                # Fallback to direct memory manipulation
                return await self._add_interaction_direct(user_id, product, interaction_type)
                
        except Exception as e:
            logger.error(f"Error adding product interaction to memory: {e}")
            return False
    
    async def _add_interaction_direct(self, user_id: str, product: Dict[str, Any], interaction_type: str) -> bool:
        """
        Fallback method to add interaction directly to memory.
        
        Args:
            user_id: User ID
            product: Product dictionary
            interaction_type: Interaction type
            
        Returns:
            Success boolean
        """
        try:
            # Create memory record content
            content = f"User {user_id} {interaction_type} product {product.get('title')} (ID: {product.get('id')})."
            
            # Add product categories
            if product.get('categories'):
                categories = ', '.join(product.get('categories'))
                content += f" Categories: {categories}."
                
            # Add product tags
            if product.get('tags'):
                tags = ', '.join(product.get('tags'))
                content += f" Tags: {tags}."
                
            # Add product collections
            if product.get('collections'):
                collections = ', '.join(product.get('collections'))
                content += f" Collections: {collections}."
            
            # FIXED: Use CompatibilityLayer for memory record creation
            if CAMEL_AVAILABLE and CompatibilityLayer:
                # Create system message
                message = CompatibilityLayer.create_assistant_message(
                    content=content,
                    role_name="System"
                )
                
                if message:
                    # Create memory record
                    record = CompatibilityLayer.create_memory_record(
                        message=message,
                        role="system"
                    )
                    
                    if record:
                        # Write to memory
                        success = CompatibilityLayer.write_to_memory(self.memory, [record])
                        return success
            
            logger.warning("Could not add interaction using CompatibilityLayer")
            return False
            
        except Exception as e:
            logger.error(f"Error in direct interaction addition: {e}")
            return False
    
    async def add_user_preference(
        self, 
        user_id: str, 
        preference_type: str, 
        preference_value: Any
    ) -> bool:
        """
        Add user preference to memory.
        
        FIXED: Uses MemoryManager for proper async handling.
        
        Args:
            user_id: User ID
            preference_type: Type of preference (e.g., "color", "style", "budget")
            preference_value: Value of the preference
            
        Returns:
            True if successful, False otherwise
        """
        await self._ensure_memory_initialized()
        
        if not self.memory:
            logger.warning("Memory not available for adding user preference")
            return False
            
        try:
            # FIXED: Use MemoryManager for adding preferences
            if self.memory_manager:
                success = await self.memory_manager.add_preference(
                    memory=self.memory,
                    preference_type=preference_type,
                    preference_value=preference_value,
                    user_id=user_id
                )
                
                if success:
                    logger.info(f"Added user preference to memory: {preference_type} = {preference_value}")
                    return True
                else:
                    logger.warning(f"Failed to add user preference to memory")
                    return False
            else:
                # Fallback to direct memory manipulation
                return await self._add_preference_direct(user_id, preference_type, preference_value)
                
        except Exception as e:
            logger.error(f"Error adding user preference to memory: {e}")
            return False
    
    async def _add_preference_direct(self, user_id: str, preference_type: str, preference_value: Any) -> bool:
        """
        Fallback method to add preference directly to memory.
        
        Args:
            user_id: User ID
            preference_type: Preference type
            preference_value: Preference value
            
        Returns:
            Success boolean
        """
        try:
            # Format preference value for display
            if isinstance(preference_value, list):
                formatted_value = ', '.join(str(v) for v in preference_value)
            else:
                formatted_value = str(preference_value)
                
            # Create memory record content
            content = f"User {user_id} preference: {preference_type} = {formatted_value}"
            
            # FIXED: Use CompatibilityLayer for memory record creation
            if CAMEL_AVAILABLE and CompatibilityLayer:
                # Create system message
                message = CompatibilityLayer.create_assistant_message(
                    content=content,
                    role_name="System"
                )
                
                if message:
                    # Create memory record
                    record = CompatibilityLayer.create_memory_record(
                        message=message,
                        role="system"
                    )
                    
                    if record:
                        # Write to memory
                        success = CompatibilityLayer.write_to_memory(self.memory, [record])
                        return success
            
            logger.warning("Could not add preference using CompatibilityLayer")
            return False
            
        except Exception as e:
            logger.error(f"Error in direct preference addition: {e}")
            return False
    
    async def get_personalized_recommendations(
        self, 
        user_id: str, 
        query: Optional[str] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations based on memory.
        
        FIXED: Uses MemoryManager for proper memory context retrieval.
        
        Args:
            user_id: User ID
            query: Optional search query to refine recommendations
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting personalized recommendations for user {user_id}")
        
        await self._ensure_memory_initialized()
        
        if not self.memory:
            logger.warning("Memory not available for recommendations")
            
            # Fallback to popular products
            return await self._get_fallback_recommendations(query, limit)
        
        try:
            # Create search query for memory
            search_query = f"User {user_id} preferences and product interactions."
            if query:
                search_query += f" Looking for {query}."
                
            # FIXED: Retrieve relevant records from memory using MemoryManager
            memory_context = await self._get_relevant_memory_context(search_query)
            
            if not memory_context:
                logger.warning("No relevant memory context found")
                
                # Fallback to products matching the query
                return await self._get_fallback_recommendations(query, limit)
            
            # Extract information from memory context
            categories, tags, collections, products = self._extract_memory_information(memory_context)
            
            # Calculate frequencies
            category_freq = Counter(categories)
            tag_freq = Counter(tags)
            collection_freq = Counter(collections)
            product_freq = Counter(products)
            
            # Get top items
            top_categories = [c for c, _ in category_freq.most_common(3)]
            top_tags = [t for t, _ in tag_freq.most_common(3)]
            top_collections = [c for c, _ in collection_freq.most_common(3)]
            
            # Build recommendations based on memory insights
            recommendations = []
            
            # Add recommendations from previously interacted products
            if product_freq:
                # Get details for most interacted products
                for product_id, _ in product_freq.most_common(limit):
                    try:
                        product = await self.product_kg.get_product_details(product_id)
                        if product and product.get('id') not in [p.get('id') for p in recommendations]:
                            recommendations.append(product)
                            
                            # Break if we have enough recommendations
                            if len(recommendations) >= limit:
                                break
                    except Exception as e:
                        logger.error(f"Error getting product details for {product_id}: {e}")
            
            # Add recommendations based on top categories, tags, and collections
            if len(recommendations) < limit:
                # Try to get products matching top preferences
                try:
                    filter_products = await self.product_kg.get_product_by_filter(
                        category=top_categories[0] if top_categories else None,
                        tag=top_tags[0] if top_tags else None,
                        collection=top_collections[0] if top_collections else None,
                        limit=limit - len(recommendations)
                    )
                    
                    # Add products not already in recommendations
                    for product in filter_products:
                        if product.get('id') not in [p.get('id') for p in recommendations]:
                            recommendations.append(product)
                            
                            # Break if we have enough recommendations
                            if len(recommendations) >= limit:
                                break
                except Exception as e:
                    logger.error(f"Error getting filtered products: {e}")
            
            # If we still need more recommendations, search by query
            if len(recommendations) < limit and query:
                try:
                    query_products = await self._search_products_by_query(query, limit - len(recommendations))
                    
                    # Add products not already in recommendations
                    for product in query_products:
                        if product.get('id') not in [p.get('id') for p in recommendations]:
                            recommendations.append(product)
                            
                            # Break if we have enough recommendations
                            if len(recommendations) >= limit:
                                break
                except Exception as e:
                    logger.error(f"Error searching products by query: {e}")
            
            # If we still need more recommendations, get popular products
            if len(recommendations) < limit:
                try:
                    popular_products = await self._get_popular_products(limit - len(recommendations))
                    
                    # Add products not already in recommendations
                    for product in popular_products:
                        if product.get('id') not in [p.get('id') for p in recommendations]:
                            recommendations.append(product)
                            
                            # Break if we have enough recommendations
                            if len(recommendations) >= limit:
                                break
                except Exception as e:
                    logger.error(f"Error getting popular products: {e}")
            
            logger.info(f"Found {len(recommendations)} personalized recommendations")
            return recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            
            # Fallback to products matching the query
            return await self._get_fallback_recommendations(query, limit)
    
    async def _get_relevant_memory_context(self, query: str) -> List[Dict[str, Any]]:
        """
        Get relevant context from memory.
        
        FIXED: Uses MemoryManager for context retrieval.
        
        Args:
            query: Search query
            
        Returns:
            List of relevant memory records
        """
        try:
            if self.memory_manager and self.memory:
                # Use MemoryManager to get context
                context, _ = await self.memory_manager.get_context(self.memory, query)
                return context
            elif self.memory and CAMEL_AVAILABLE and CompatibilityLayer:
                # Use CompatibilityLayer as fallback
                context, _ = CompatibilityLayer.get_memory_context(self.memory)
                return context
            else:
                logger.warning("No method available to get memory context")
                return []
                
        except Exception as e:
            logger.error(f"Error getting memory context: {e}")
            return []
    
    def _extract_memory_information(self, memory_context: List[Dict[str, Any]]) -> Tuple[List[str], List[str], List[str], List[str]]:
        """
        Extract information from memory context.
        
        Args:
            memory_context: Memory context
            
        Returns:
            Tuple of (categories, tags, collections, products)
        """
        categories = []
        tags = []
        collections = []
        products = []
        
        for context_item in memory_context:
            content = context_item.get('content', '')
            
            # Extract product ID
            product_id_start = content.find("(ID: ")
            if product_id_start >= 0:
                product_id_end = content.find(")", product_id_start)
                if product_id_end >= 0:
                    product_id = content[product_id_start + 5:product_id_end]
                    products.append(product_id)
            
            # Extract categories
            cat_start = content.find("Categories: ")
            if cat_start >= 0:
                cat_end = content.find(".", cat_start)
                if cat_end >= 0:
                    cat_list = content[cat_start + 12:cat_end].split(', ')
                    categories.extend(cat_list)
            
            # Extract tags
            tag_start = content.find("Tags: ")
            if tag_start >= 0:
                tag_end = content.find(".", tag_start)
                if tag_end >= 0:
                    tag_list = content[tag_start + 6:tag_end].split(', ')
                    tags.extend(tag_list)
            
            # Extract collections
            col_start = content.find("Collections: ")
            if col_start >= 0:
                col_end = content.find(".", col_start)
                if col_end >= 0:
                    col_list = content[col_start + 13:col_end].split(', ')
                    collections.extend(col_list)
            
            # Extract user preferences
            pref_start = content.find("preference: ")
            if pref_start >= 0:
                pref_end = content.find(" = ", pref_start)
                if pref_end >= 0:
                    pref_type = content[pref_start + 12:pref_end]
                    
                    if pref_type.lower() == 'category':
                        value_end = content.find(".", pref_end)
                        if value_end < 0:
                            value_end = len(content)
                        value = content[pref_end + 3:value_end]
                        categories.append(value)
                    elif pref_type.lower() == 'tag':
                        value_end = content.find(".", pref_end)
                        if value_end < 0:
                            value_end = len(content)
                        value = content[pref_end + 3:value_end]
                        tags.append(value)
                    elif pref_type.lower() == 'collection':
                        value_end = content.find(".", pref_end)
                        if value_end < 0:
                            value_end = len(content)
                        value = content[pref_end + 3:value_end]
                        collections.append(value)
        
        return categories, tags, collections, products
    
    async def _search_products_by_query(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Search products by text query.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching products
        """
        try:
            # Check if product_kg has product_retriever
            if hasattr(self.product_kg, 'product_retriever') and self.product_kg.product_retriever:
                # Use vector search
                if hasattr(self.product_kg.product_retriever, 'search_by_natural_language'):
                    return await self.product_kg.product_retriever.search_by_natural_language(query, limit)
            
            # Fallback to basic filter search in product_kg
            if hasattr(self.product_kg, 'get_product_by_filter'):
                return await self.product_kg.get_product_by_filter(
                    tag=query,  # Use query as tag for basic search
                    limit=limit
                )
                
            return []
            
        except Exception as e:
            logger.error(f"Error searching products by query: {e}")
            return []
    
    async def _get_popular_products(self, limit: int) -> List[Dict[str, Any]]:
        """Get popular products as fallback"""
        try:
            if hasattr(self.product_kg, 'get_popular_products'):
                return await self.product_kg.get_popular_products(limit)
            return []
        except Exception as e:
            logger.error(f"Error getting popular products: {e}")
            return []
    
    async def _get_fallback_recommendations(self, query: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Get fallback recommendations when memory is not available"""
        try:
            # Try query-based search first
            if query:
                results = await self._search_products_by_query(query, limit)
                if results:
                    return results
            
            # Fallback to popular products
            return await self._get_popular_products(limit)
            
        except Exception as e:
            logger.error(f"Error getting fallback recommendations: {e}")
            return []
