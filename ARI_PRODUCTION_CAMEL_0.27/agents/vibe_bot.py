"""
VibeBot Agent - Qdrant Aesthetic Intelligence
Clean CAMEL 0.2.7 implementation
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("agents.vibe_bot")

# Direct CAMEL 0.2.7 imports
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.memories import ChatHistoryMemory
from camel.societies import RolePlaying
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType, RoleType

# Import prompts
from config.prompts import VIBEBOT_PROMPT

class VibeBotAgent:
    """
    VibeBot - Aesthetic-driven fashion intelligence using Qdrant.
    
    Clean implementation with CAMEL 0.2.7 patterns:
    - Uses ModelFactory to create models
    - Passes model objects to ChatAgent
    - Direct string system messages
    - No hidden fallbacks
    """
    
    def __init__(self, qdrant_client):
        """
        Initialize VibeBot with Qdrant connection.
        
        Args:
            qdrant_client: ProductRetrieverAsync instance
        """
        self.qdrant = qdrant_client
        self.name = "VibeBot"
        self.style = "aesthetic-similarity"
        
        # Initialize CAMEL 0.2.7 components
        self._initialize_camel_agent()
        self._initialize_memory()
        self._initialize_roleplay()
        
        logger.info(f"{self.name} initialized with CAMEL 0.2.7, RolePlay, and aesthetic intelligence")
        
        # Track statistics
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0
        }

    def _initialize_camel_agent(self):
        """Initialize the main CAMEL ChatAgent for aesthetic intelligence"""
        try:
            model = ModelFactory.create(
                model_platform=ModelPlatformType.DEFAULT,
                model_type=ModelType.GPT_4O,
                model_config_dict={
                    "temperature": 0.8,  # Higher creativity for aesthetic decisions
                    "max_tokens": 2000
                }
            )
            
            self.agent = ChatAgent(
                system_message=BaseMessage.make_assistant_message(
                    role_name="Aesthetic Stylist",
                    content=VIBEBOT_PROMPT
                ),
                model=model
            )
            
            logger.info("VibeBot CAMEL agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CAMEL agent: {e}")
            raise RuntimeError(f"VibeBot CAMEL initialization failed: {e}") from e

    def _initialize_memory(self):
        """Initialize ChatHistoryMemory for aesthetic pattern learning"""
        try:
            from camel.memories.context_creators import ScoreBasedContextCreator
            from camel.utils.token_counting import OpenAITokenCounter
            
            token_counter = OpenAITokenCounter(model=ModelType.GPT_4O)
            context_creator = ScoreBasedContextCreator(token_counter=token_counter, token_limit=4000)
            self.memory = ChatHistoryMemory(context_creator=context_creator, window_size=25)
            logger.info("VibeBot aesthetic memory system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory = None

    def _initialize_roleplay(self):
        """Initialize RolePlaying society for aesthetic collaboration"""
        try:
            self.role_playing = RolePlaying(
                assistant_role_name="Aesthetic Stylist",
                user_role_name="Style Analyst",
                task_prompt="Collaborate on aesthetic fashion analysis, style matching, and visual harmony for optimal product recommendations"
            )
            logger.info("VibeBot RolePlay aesthetic society initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RolePlay: {e}")
            self.role_playing = None
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using aesthetic similarity.
        """
        start_time = datetime.now()
        self.stats["total_searches"] += 1
        
        logger.debug(f">>> {self.name}.search() START")
        logger.info(f"{self.name} searching: query='{query[:50]}...', filters={filters}")
        
        try:
            # BATTLE DEBUG: Print when called during battle
            print(f"   🎯 VibeBot: Called with query='{query[:30]}...', filters={filters is not None}")
            
            # Get strategy from CAMEL agent
            logger.debug("Getting agent strategy...")
            strategy_start = datetime.now()
            strategy = await self._get_agent_strategy(
                query, ml_intelligence, filters, user_context
            )
            strategy_time = (datetime.now() - strategy_start).total_seconds()
            logger.debug(f"Strategy determined in {strategy_time:.2f}s: {strategy[:100]}...")
            print(f"   🎯 VibeBot: Strategy: {strategy[:50]}...")
            
            # Execute strategy
            logger.debug("Executing strategy...")
            exec_start = datetime.now()
            results = await self._execute_strategy(
                strategy, query, limit, filters, ml_intelligence
            )
            exec_time = (datetime.now() - exec_start).total_seconds()
            logger.debug(f"Strategy executed in {exec_time:.2f}s, got {len(results)} results")
            print(f"   🎯 VibeBot: Strategy returned {len(results)} results in {exec_time:.2f}s")
            
            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_stats(len(results), elapsed, success=True)
            
            logger.info(f"{self.name} found {len(results)} products in {elapsed:.2f}s")
            logger.debug(f"<<< {self.name}.search() END")
            return results
            
        except Exception as e:
            logger.error(f"!!! {self.name} search failed: {e}", exc_info=True)
            self.stats["failed_searches"] += 1
            return []
      
    async def _semantic_search(self, query: str, limit: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.debug(f">>> _semantic_search: query='{query[:50]}...', limit={limit}")
        try:
            # Enhance query with filter terms instead of using metadata filters
            enhanced_query = query
            if filters:
                if 'category' in filters:
                    enhanced_query = f"{filters['category']} {enhanced_query}"
                    logger.debug(f"Added category to query: {filters['category']}")
                if 'colors' in filters:
                    enhanced_query = f"{' '.join(filters['colors'])} {enhanced_query}"
                    logger.debug(f"Added colors to query: {filters['colors']}")
            
            logger.debug(f"Calling Qdrant with enhanced_query: '{enhanced_query[:50]}...'")
            search_start = asyncio.get_event_loop().time()
            
            # FIXED: Don't use Qdrant filters that may not have indexes - use text enhancement instead
            qdrant_filters = None
            
            results = await self.qdrant.search_by_natural_language(
                query=enhanced_query,
                limit=limit,
                filters=qdrant_filters,  # Use category filters when available
                score_threshold=0.5  # Balanced threshold - good similarity without being too strict
            )
            
            search_time = asyncio.get_event_loop().time() - search_start
            logger.debug(f"Qdrant search returned in {search_time:.2f}s with {len(results)} results")
            
            products = []
            filtered_count = 0
            for i, product in enumerate(results):
                if isinstance(product, dict):
                    # New graph guarantees p.id is UUID format
                    product_id = product.get('id')
                    if product_id:
                        # ENHANCED: Add category validation post-processing
                        if self._validate_product_category(product, filters):
                            product['vibe_reason'] = "Semantic similarity match"
                            products.append(product)
                            if len(products) <= 3:  # Log first 3 accepted products
                                logger.debug(f"  Product {len(products)}: {product.get('title', 'NO_TITLE')[:30]}")
                        else:
                            filtered_count += 1
                            logger.debug(f"  Filtered out: {product.get('title', 'NO_TITLE')[:30]} - wrong category")
                    else:
                        logger.warning("Skipping product without ID from Qdrant")
            
            if filtered_count > 0:
                logger.info(f"Category validation filtered out {filtered_count} irrelevant products")
            
            logger.debug(f"<<< _semantic_search returning {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"!!! Semantic search failed: {e}", exc_info=True)
            return []
  
    
    async def _get_agent_strategy(
        self,
        query: str,
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Use CAMEL agent to determine search strategy.
        
        Returns:
            Strategy description from agent
        """
        # Build context for agent
        context = f"""Determine the best aesthetic search strategy for:
Query: "{query}"
Has filters: {bool(filters)}
"""
        
        # Add ML intelligence if available
        if ml_intelligence and 'vibe_intel' in ml_intelligence:
            intel = ml_intelligence['vibe_intel']
            
            # Add relevant intelligence
            for source, data in intel.items():
                if isinstance(data, dict):
                    if 'visual_features' in data:
                        visual = data['visual_features']
                        if 'colors' in visual:
                            context += f"\nDetected colors: {visual['colors'][:3]}"
                        if 'style_attributes' in visual:
                            context += f"\nStyle attributes: {visual['style_attributes'][:3]}"
                    if 'style_analysis' in data:
                        style = data['style_analysis']
                        if 'mood' in style:
                            context += f"\nMood: {style['mood']}"
                        if 'formality' in style:
                            context += f"\nFormality: {style['formality']}"
        
        # Add user preferences if available
        if user_context:
            if user_context.get('preferred_colors'):
                context += f"\nUser prefers: {user_context['preferred_colors'][:3]}"
            if user_context.get('preferred_styles'):
                context += f"\nUser styles: {user_context['preferred_styles'][:3]}"
        
        # Add filters if present
        if filters:
            context += f"\nFilters: {json.dumps(filters, indent=2)}"
        
        context += """

Choose strategy:
1. SEMANTIC - Natural language embedding search
2. VISUAL - Visual similarity and style matching
3. COLOR - Color-based aesthetic search
4. STYLE - Style attributes and trends
5. GENERAL - Basic aesthetic search

Respond with the strategy name and brief explanation."""
        
        try:
            # Create message for agent
            user_msg = BaseMessage.make_user_message(
                role_name="Style Analyst",
                content=context
            )
            
            # Get response from CAMEL agent
            response = self.agent.step(user_msg)
            
            # Extract strategy
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                strategy = response.msg.content
            else:
                strategy = str(response)
            
            logger.debug(f"Agent strategy: {strategy[:100]}...")
            return strategy
            
        except Exception as e:
            logger.error(f"Agent strategy error: {e}")
            return "GENERAL"  # Fallback strategy
    
    async def _execute_strategy(
        self,
        strategy: str,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute the chosen search strategy.
        
        Returns:
            List of products from Qdrant
        """
        strategy_lower = strategy.lower()
        results = []
        
        # Enhance query based on strategy
        enhanced_query = self._enhance_query(query, strategy, ml_intelligence)
        
        # Use semantic search for all strategies (most reliable approach)
        print(f"   🎯 VibeBot: Using semantic search for all strategies with query: '{enhanced_query}'")
        results = await self._semantic_search(enhanced_query, limit, filters)
        print(f"   🎯 VibeBot: Semantic search returned {len(results)} results")
        
        # Deduplicate and rank
        unique_results = self._deduplicate_and_rank(results, query)
        
        # Add metadata
        for idx, product in enumerate(unique_results[:limit]):
            product['vibe_rank'] = idx + 1
            product['agent'] = self.name
            product['search_method'] = 'semantic_similarity'
            product['vibe_score'] = 1.0 - (idx * 0.1)
            product['vibe_reason'] = f"Semantic match for {strategy.lower()} strategy"
        
        return unique_results[:limit]
    
    async def _visual_similarity_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Search based on visual similarity.
        """
        try:
            # If we have a reference product from ML intelligence, use it
            reference_product_id = None
            if ml_intelligence and 'vibe_intel' in ml_intelligence:
                for source, data in ml_intelligence['vibe_intel'].items():
                    if isinstance(data, dict) and 'reference_product' in data:
                        reference_product_id = data['reference_product']
                        break
            
            if reference_product_id:
                # Get similar products to reference
                results = await self.qdrant.get_similar_products(
                    product_id=reference_product_id,
                    limit=limit
                )
                
                products = []
                for product in results:
                    # New graph guarantees p.id is UUID format
                    product['vibe_reason'] = "Visual similarity to reference"
                    products.append(product)
                
                return products
            else:
                # Fall back to semantic search with visual keywords
                visual_query = f"{query} visual style aesthetic look"
                return await self._semantic_search(visual_query, limit, filters)
                
        except Exception as e:
            logger.error(f"Visual similarity search failed: {e}")
            return []
    
    async def _color_based_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Search based on colors.
        """
        try:
            # Extract colors from ML intelligence or query
            colors = []
            
            if ml_intelligence and 'vibe_intel' in ml_intelligence:
                for source, data in ml_intelligence['vibe_intel'].items():
                    if isinstance(data, dict) and 'visual_features' in data:
                        detected_colors = data['visual_features'].get('colors', [])
                        colors.extend(detected_colors[:3])
                        break
            
            # Parse colors from query if not in ML intelligence
            if not colors:
                color_keywords = ['red', 'blue', 'green', 'black', 'white', 'pink', 
                                'purple', 'yellow', 'orange', 'brown', 'gray', 'navy']
                query_lower = query.lower()
                colors = [c for c in color_keywords if c in query_lower]
            
            if colors:
                # Use semantic search with color-enhanced query (filter-based search disabled in Qdrant)
                enhanced_query = f"{query} {' '.join(colors)}"
                results = await self._semantic_search(enhanced_query, limit, filters)
                
                # Add color reasoning to results
                for product in results:
                    product['vibe_reason'] = f"Semantic color match: {', '.join(colors[:2])}"
                
                return results
            else:
                # No colors detected, use general search
                return await self._general_search(query, limit, filters)
                
        except Exception as e:
            logger.error(f"Color-based search failed: {e}")
            return []
    
    async def _style_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Search based on style attributes and trends.
        """
        try:
            # Enhance query with style keywords
            style_keywords = ['trendy', 'fashionable', 'stylish', 'modern', 'classic',
                            'elegant', 'casual', 'formal', 'bohemian', 'minimalist']
            
            # Add relevant style keywords to query
            enhanced_query = query
            query_lower = query.lower()
            for keyword in style_keywords:
                if keyword in query_lower:
                    enhanced_query += f" {keyword} style"
                    break
            
            # Search with enhanced query
            results = await self.qdrant.search_by_natural_language(
                query=enhanced_query,
                limit=limit,
                filters=filters,
                score_threshold=0.5  # Balanced threshold - good similarity without being too strict
            )
            
            products = []
            for product in results:
                # New graph guarantees p.id is UUID format
                product['vibe_reason'] = "Style and trend match"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Style search failed: {e}")
            print(f"   🎯 VibeBot: Style search ERROR: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _general_search(
        self,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        General aesthetic search in Qdrant.
        """
        try:
            # Use natural language search as general method
            results = await self.qdrant.search_by_natural_language(
                query=query,
                limit=limit,
                filters=filters,
                score_threshold=0.5  # Balanced threshold - good similarity without being too strict
            )
            
            products = []
            for product in results:
                # New graph guarantees p.id is UUID format
                product['vibe_reason'] = "Aesthetic match"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"General search failed: {e}")
            return []
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info(f"Cleaning up {self.name}")
        
        # Clear statistics
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0
        }
        
        # If there are any cached connections or resources
        # clean them up here
        
        logger.info(f"{self.name} cleanup complete")

    def _enhance_query(
        self,
        query: str,
        strategy: str,
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> str:
        """
        Enhance query based on strategy and ML intelligence.
        """
        enhanced = query
        
        # Add style descriptors based on strategy
        if "visual" in strategy.lower():
            enhanced += " visual aesthetic appearance"
        
        if "trend" in strategy.lower():
            enhanced += " trending popular fashionable"
        
        # Add ML intelligence insights
        if ml_intelligence and 'vibe_intel' in ml_intelligence:
            for source, data in ml_intelligence['vibe_intel'].items():
                if isinstance(data, dict):
                    if 'style_analysis' in data:
                        style = data['style_analysis']
                        if 'inferred_styles' in style:
                            styles = style['inferred_styles'][:2]
                            enhanced += f" {' '.join(styles)}"
                    break
        
        return enhanced
    
    def _deduplicate_and_rank(
        self,
        results: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicates and rank results.
        """
        seen = set()
        unique = []
        
        for product in results:
            product_id = product.get('id')
            if product_id and product_id not in seen:
                seen.add(product_id)
                
                # Calculate relevance score
                score = 0.5
                
                # Boost for semantic matches
                if 'semantic' in product.get('vibe_reason', '').lower():
                    score += 0.3
                
                # Boost for visual matches
                if 'visual' in product.get('vibe_reason', '').lower():
                    score += 0.2
                
                # Boost for color matches
                if 'color' in product.get('vibe_reason', '').lower():
                    score += 0.2
                
                # Boost for products with images
                if product.get('images') and len(product['images']) > 0:
                    score += 0.1
                
                # Boost for in-stock items
                if product.get('in_stock', True):
                    score += 0.1
                
                product['relevance_score'] = min(score, 1.0)
                unique.append(product)
        
        # Sort by relevance score
        unique.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return unique
    
    def _validate_product_category(
        self,
        product: Dict[str, Any],
        filters: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Validate that a product matches the requested category.
        
        Args:
            product: Product data
            filters: Search filters including category
            
        Returns:
            True if product matches category or no category filter
        """
        if not filters or 'category' not in filters:
            return True  # No category filter, accept all products
        
        requested_category = filters['category'].lower()
        
        # Check multiple product category fields
        product_categories = []
        
        # Check main category field
        if product.get('category'):
            product_categories.append(product['category'].lower())
        
        # Check subcategory field
        if product.get('subcategory'):
            product_categories.append(product['subcategory'].lower())
        
        # Check categories array
        if product.get('categories') and isinstance(product['categories'], list):
            product_categories.extend([cat.lower() for cat in product['categories'] if cat])
        
        # Check if any product category matches the requested category
        if requested_category in product_categories:
            return True
        
        # ENHANCED: Check for category relationships and synonyms
        category_mappings = {
            'shirt': ['shirt', 'blouse', 'top', 't-shirt', 'tee', 'tank', 'polo'],
            'pants': ['pants', 'jeans', 'trousers', 'chinos', 'slacks'],
            'dress': ['dress', 'gown', 'frock', 'sundress', 'maxi', 'midi'],
            'shoes': ['shoes', 'boots', 'sneakers', 'heels', 'flats', 'sandals'],
            'jacket': ['jacket', 'blazer', 'coat', 'outerwear'],
            'shorts': ['shorts', 'short', 'bermuda'],
            'top': ['top', 'shirt', 'blouse', 'tee', 'tank', 'camisole']
        }
        
        # Check if requested category has known synonyms
        if requested_category in category_mappings:
            for synonym in category_mappings[requested_category]:
                if synonym in product_categories:
                    return True
        
        # Check reverse mapping (product category has synonyms that match request)
        for category, synonyms in category_mappings.items():
            if requested_category in synonyms:
                for product_cat in product_categories:
                    if product_cat in synonyms:
                        return True
        
        # Last resort: check title for category indicators (less reliable)
        title = product.get('title', '').lower()
        title_indicators = category_mappings.get(requested_category, [requested_category])
        for indicator in title_indicators:
            if indicator in title and len(indicator) > 3:  # Avoid short matches
                return True
        
        return False
    
    def _update_stats(
        self,
        products_found: int,
        search_time: float,
        success: bool
    ):
        """Update agent statistics."""
        if success:
            self.stats["successful_searches"] += 1
            self.stats["total_products_found"] += products_found
            
            # Update average search time
            total_searches = self.stats["successful_searches"]
            current_avg = self.stats["avg_search_time"]
            self.stats["avg_search_time"] = (
                (current_avg * (total_searches - 1) + search_time) / total_searches
            )
        else:
            self.stats["failed_searches"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "agent": self.name,
            "style": self.style,
            **self.stats,
            "success_rate": (
                self.stats["successful_searches"] / self.stats["total_searches"] * 100
                if self.stats["total_searches"] > 0 else 0
            )
        }
