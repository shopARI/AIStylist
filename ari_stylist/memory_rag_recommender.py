"""
Memory-Enhanced RAG Recommendation System for AI Stylist.

This module implements a recommendation system that leverages the CAMEL memory
system to enhance recommendations based on conversation history.
Compatible with CAMEL-AI 0.2.43.
"""

import logging
import json
import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import Counter

from camel.memories import LongtermAgentMemory, MemoryRecord, ScoreBasedContextCreator
from camel.embeddings import OpenAIEmbedding
from camel.storages import QdrantStorage
from camel.types import OpenAIBackendRole, EmbeddingModelType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory_rag_recommender")

class MemoryRAGRecommender:
    """
    Implements a recommendation system that leverages the CAMEL memory system
    to enhance recommendations based on conversation history.
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
        logger.info("Initializing MemoryRAGRecommender")
        self.product_kg = product_kg
        
        # Initialize memory
        if memory is not None:
            self.memory = memory
            logger.info("Using provided memory instance")
        elif memory_setup_func is not None:
            try:
                self.memory = memory_setup_func()
                logger.info("Memory initialized using setup function")
            except Exception as e:
                logger.error(f"Error initializing memory with setup function: {e}")
                self.memory = self._create_default_memory(token_limit)
        else:
            self.memory = self._create_default_memory(token_limit)
            logger.info("Created default memory instance")
    
    def _create_default_memory(self, token_limit: int) -> LongtermAgentMemory:
        """
        Create a default memory instance.
        
        Args:
            token_limit: Token limit for context window
            
        Returns:
            CAMEL memory instance
        """
        try:
            # Set up embedding model
            embedding_model = OpenAIEmbedding(
                model_type=EmbeddingModelType.TEXT_EMBEDDING_3_SMALL
            )
            
            # Create vector storage
            vector_storage = QdrantStorage(
                vector_dim=embedding_model.get_output_dim(),
                path="memory_data",
                collection_name="stylist_memory"
            )
            
            # Create context creator
            context_creator = ScoreBasedContextCreator(
                token_limit=token_limit
            )
            
            # Create memory
            memory = LongtermAgentMemory(
                context_creator=context_creator,
                vector_db_block=vector_storage
            )
            
            return memory
        except Exception as e:
            logger.error(f"Error creating default memory: {e}")
            # Return minimal memory without vector storage
            return LongtermAgentMemory(
                context_creator=ScoreBasedContextCreator(
                    token_limit=token_limit
                )
            )
    
    def add_product_interaction(
        self, 
        user_id: str, 
        product_id: str, 
        interaction_type: str
    ) -> bool:
        """
        Add a product interaction to memory.
        
        Args:
            user_id: User ID
            product_id: Product ID
            interaction_type: Type of interaction (e.g., "viewed", "liked", "purchased")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.memory:
            logger.warning("Memory not available for adding product interaction")
            return False
            
        try:
            # Get product details
            product = self.product_kg.get_product_details(product_id)
            if not product:
                logger.warning(f"Product not found: {product_id}")
                return False
                
            # Create memory record content
            content = f"User {user_id} {interaction_type} product {product.get('title')} (ID: {product_id})."
            
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
            
            # Create memory record with metadata
            record = MemoryRecord(
                message=None,  # No message required for product interaction
                content=content,
                role_at_backend=OpenAIBackendRole.SYSTEM,
                metadata={
                    "type": "product_interaction",
                    "user_id": user_id,
                    "product_id": product_id,
                    "interaction_type": interaction_type,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "product_title": product.get('title', ''),
                    "product_categories": product.get('categories', []),
                    "product_tags": product.get('tags', []),
                    "product_collections": product.get('collections', [])
                }
            )
            
            # Add to memory
            self.memory.write_records([record])
            
            logger.info(f"Added product interaction to memory: {interaction_type} {product_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding product interaction to memory: {e}")
            return False
    
    def add_user_preference(
        self, 
        user_id: str, 
        preference_type: str, 
        preference_value: Any
    ) -> bool:
        """
        Add user preference to memory.
        
        Args:
            user_id: User ID
            preference_type: Type of preference (e.g., "color", "style", "budget")
            preference_value: Value of the preference
            
        Returns:
            True if successful, False otherwise
        """
        if not self.memory:
            logger.warning("Memory not available for adding user preference")
            return False
            
        try:
            # Format preference value for display
            if isinstance(preference_value, list):
                formatted_value = ', '.join(str(v) for v in preference_value)
            else:
                formatted_value = str(preference_value)
                
            # Create memory record content
            content = f"User {user_id} preference: {preference_type} = {formatted_value}"
            
            # Create memory record with metadata
            record = MemoryRecord(
                message=None,  # No message required for user preference
                content=content,
                role_at_backend=OpenAIBackendRole.SYSTEM,
                metadata={
                    "type": "user_preference",
                    "user_id": user_id,
                    "preference_type": preference_type,
                    "preference_value": preference_value,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            )
            
            # Add to memory
            self.memory.write_records([record])
            
            logger.info(f"Added user preference to memory: {preference_type} = {formatted_value}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding user preference to memory: {e}")
            return False
    
    def get_personalized_recommendations(
        self, 
        user_id: str, 
        query: Optional[str] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get personalized recommendations based on memory.
        
        Args:
            user_id: User ID
            query: Optional search query to refine recommendations
            limit: Maximum number of recommendations
            
        Returns:
            List of recommended products
        """
        logger.info(f"Getting personalized recommendations for user {user_id}")
        
        if not self.memory:
            logger.warning("Memory not available for recommendations")
            
            # Fallback to popular products
            if hasattr(self.product_kg, 'get_popular_products'):
                return self.product_kg.get_popular_products(limit)
            else:
                return []
        
        try:
            # Create search query for memory
            search_query = f"User {user_id} preferences and product interactions."
            if query:
                search_query += f" Looking for {query}."
                
            # Retrieve relevant records from memory
            memory_context = self._get_relevant_memory_context(search_query)
            
            if not memory_context:
                logger.warning("No relevant memory context found")
                
                # Fallback to products matching the query
                if query:
                    return self._search_products_by_query(query, limit)
                
                # Fallback to popular products
                if hasattr(self.product_kg, 'get_popular_products'):
                    return self.product_kg.get_popular_products(limit)
                else:
                    return []
            
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
                    product = self.product_kg.get_product_details(product_id)
                    if product and product.get('id') not in [p.get('id') for p in recommendations]:
                        recommendations.append(product)
                        
                        # Break if we have enough recommendations
                        if len(recommendations) >= limit:
                            break
            
            # Add recommendations based on top categories, tags, and collections
            if len(recommendations) < limit:
                # Try to get products matching top preferences
                filter_products = self.product_kg.get_product_by_filter(
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
            
            # If we still need more recommendations, search by query
            if len(recommendations) < limit and query:
                query_products = self._search_products_by_query(query, limit - len(recommendations))
                
                # Add products not already in recommendations
                for product in query_products:
                    if product.get('id') not in [p.get('id') for p in recommendations]:
                        recommendations.append(product)
                        
                        # Break if we have enough recommendations
                        if len(recommendations) >= limit:
                            break
            
            # If we still need more recommendations, get popular products
            if len(recommendations) < limit and hasattr(self.product_kg, 'get_popular_products'):
                popular_products = self.product_kg.get_popular_products(limit - len(recommendations))
                
                # Add products not already in recommendations
                for product in popular_products:
                    if product.get('id') not in [p.get('id') for p in recommendations]:
                        recommendations.append(product)
                        
                        # Break if we have enough recommendations
                        if len(recommendations) >= limit:
                            break
            
            logger.info(f"Found {len(recommendations)} personalized recommendations")
            return recommendations[:limit]
            
        except Exception as e:
            logger.error(f"Error getting personalized recommendations: {e}")
            
            # Fallback to products matching the query
            if query:
                return self._search_products_by_query(query, limit)
            
            # Fallback to popular products
            if hasattr(self.product_kg, 'get_popular_products'):
                return self.product_kg.get_popular_products(limit)
            else:
                return []
    
    def _get_relevant_memory_context(self, query: str) -> List[Dict[str, Any]]:
        """
        Get relevant context from memory.
        
        Args:
            query: Search query
            
        Returns:
            List of relevant memory records
        """
        try:
            # Get context from memory using CAMEL's interface
            if hasattr(self.memory, 'get_context'):
                context, _ = self.memory.get_context(query)
                return context
                
            # Fallback to direct retrieval if get_context isn't available
            if hasattr(self.memory, 'retrieve'):
                records = self.memory.retrieve(query, k=10)
                context = []
                
                for record in records:
                    if hasattr(record, 'content'):
                        context.append({"content": record.content})
                    elif hasattr(record, 'message') and hasattr(record.message, 'content'):
                        context.append({"content": record.message.content})
                
                return context
                
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
    
    def _search_products_by_query(self, query: str, limit: int) -> List[Dict[str, Any]]:
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
                return self.product_kg.product_retriever.search_by_natural_language(query, limit)
            
            # Fallback to basic text search in Neo4j
            search_query = """
            MATCH (p:Product)
            WHERE toLower(p.title) CONTAINS toLower($query) OR toLower(p.description) CONTAINS toLower($query)
            OR (p)-[:IN_CATEGORY]->(:Category) WHERE toLower(Category.title) CONTAINS toLower($query)
            OR (p)-[:TAGGED_WITH]->(:Tag) WHERE toLower(Tag.title) CONTAINS toLower($query)
            RETURN 
                p.id as id,
                p.title as title,
                p.price as price,
                p.description as description,
                p.images as images
            LIMIT $limit
            """
            
            result = self.product_kg.query(search_query, {"query": query, "limit": limit})
            
            if not result:
                return []
                
            # Process results
            products = []
            
            for record in result:
                if 'id' in record:
                    product = self.product_kg.get_product_details(record['id'])
                    if product:
                        products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products by query: {e}")
            return []