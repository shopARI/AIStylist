"""
VibeBot Agent - Qdrant Aesthetic Intelligence
Clean CAMEL 0.2.70 implementation
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("agents.vibe_bot")

# Import from our new CAMEL 0.2.70 module
from lib.camel.v070 import (
    create_battle_agent,
    create_user_message,
    BaseMessage,
    CAMEL_AVAILABLE
)

# Import prompts
from config.prompts import VIBEBOT_PROMPT

class VibeBotAgent:
    """
    VibeBot - Aesthetic-driven fashion intelligence using Qdrant.
    
    Clean implementation with CAMEL 0.2.70 patterns:
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
        
        # Initialize CAMEL agent using 0.2.70 pattern
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL 0.2.70+ is required for VibeBot")
        
        try:
            self.agent = create_battle_agent(
                name=self.name,
                system_message=VIBEBOT_PROMPT
            )
            logger.info(f"{self.name} initialized with CAMEL 0.2.70")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}")
            raise RuntimeError(f"VibeBot initialization failed: {e}") from e
        
        # Track statistics
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0
        }
    
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
            # Get strategy from CAMEL agent
            logger.debug("Getting agent strategy...")
            strategy_start = datetime.now()
            strategy = await self._get_agent_strategy(
                query, ml_intelligence, filters, user_context
            )
            strategy_time = (datetime.now() - strategy_start).total_seconds()
            logger.debug(f"Strategy determined in {strategy_time:.2f}s: {strategy[:100]}...")
            
            # Execute strategy
            logger.debug("Executing strategy...")
            exec_start = datetime.now()
            results = await self._execute_strategy(
                strategy, query, limit, filters, ml_intelligence
            )
            exec_time = (datetime.now() - exec_start).total_seconds()
            logger.debug(f"Strategy executed in {exec_time:.2f}s, got {len(results)} results")
            
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
            
            # Don't pass filters - they reference non-existent fields
            results = await self.qdrant.search_by_natural_language(
                query=enhanced_query,
                limit=limit,
                filters=None  # Critical: Set to None
            )
            
            search_time = asyncio.get_event_loop().time() - search_start
            logger.debug(f"Qdrant search returned in {search_time:.2f}s with {len(results)} results")
            
            products = []
            for i, product in enumerate(results):
                if isinstance(product, dict):
                    product['vibe_reason'] = "Semantic similarity match"
                    products.append(product)
                    if i < 3:  # Log first 3
                        logger.debug(f"  Product {i}: {product.get('title', 'NO_TITLE')[:30]}")
            
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
            user_msg = create_user_message(context)
            
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
        
        # Execute based on strategy keywords
        if "semantic" in strategy_lower or "natural" in strategy_lower:
            results.extend(await self._semantic_search(enhanced_query, limit, filters))
        
        if "visual" in strategy_lower or "similar" in strategy_lower:
            results.extend(await self._visual_similarity_search(query, limit, filters, ml_intelligence))
        
        if "color" in strategy_lower:
            results.extend(await self._color_based_search(query, limit, filters, ml_intelligence))
        
        if "style" in strategy_lower or "trend" in strategy_lower:
            results.extend(await self._style_search(enhanced_query, limit, filters))
        
        # Always include some general results
        if len(results) < limit:
            general = await self._general_search(query, limit - len(results), filters)
            results.extend(general)
        
        # Deduplicate and rank
        unique_results = self._deduplicate_and_rank(results, query)
        
        # Add metadata
        for idx, product in enumerate(unique_results[:limit]):
            product['vibe_rank'] = idx + 1
            product['agent'] = self.name
            product['search_method'] = 'aesthetic_similarity'
            product['vibe_score'] = 1.0 - (idx * 0.1)
        
        return unique_results[:limit]
    
    async def _semantic_search(self, query: str, limit: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            # Enhance query with filter terms instead of using metadata filters
            enhanced_query = query
            if filters:
                if 'category' in filters:
                    enhanced_query = f"{filters['category']} {enhanced_query}"
                if 'colors' in filters:
                    enhanced_query = f"{' '.join(filters['colors'])} {enhanced_query}"
            
            # Don't pass filters - they reference non-existent fields
            results = await self.qdrant.search_by_natural_language(
                query=enhanced_query,
                limit=limit,
                filters=None  # <-- Critical: Set to None
            )
            
            products = []
            for product in results:
                if isinstance(product, dict):
                    product['vibe_reason'] = "Semantic similarity match"
                    products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
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
                    if isinstance(product, dict):
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
                # Use filter-based search for colors
                results = await self.qdrant.get_products_by_filter(
                    colors=colors[:3],
                    limit=limit
                )
                
                products = []
                for product in results:
                    if isinstance(product, dict):
                        product['vibe_reason'] = f"Color match: {', '.join(colors[:2])}"
                        products.append(product)
                
                return products
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
                filters=filters
            )
            
            products = []
            for product in results:
                if isinstance(product, dict):
                    product['vibe_reason'] = "Style and trend match"
                    products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Style search failed: {e}")
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
                filters=filters
            )
            
            products = []
            for product in results:
                if isinstance(product, dict):
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
