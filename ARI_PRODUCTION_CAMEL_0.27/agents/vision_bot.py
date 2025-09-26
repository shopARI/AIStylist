"""
VisionBot Agent - Qdrant Visual Intelligence
Clean CAMEL 0.2.7 implementation for visual similarity search
"""

import logging
import json
import asyncio
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("agents.vision_bot")

# Direct CAMEL 0.2.7 imports
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.memories import ChatHistoryMemory
from camel.societies import RolePlaying
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType, RoleType

# Import prompts
from config.prompts import VISIONBOT_PROMPT

class VisionBotAgent:
    """
    VisionBot - Visual similarity-driven fashion intelligence using Qdrant visual embeddings.

    Clean implementation with CAMEL 0.2.7 patterns:
    - Uses ModelFactory to create models
    - Passes model objects to ChatAgent
    - Direct string system messages
    - Queries fashion_multimodal_embeddings collection for visual similarity
    """

    def __init__(self, visual_qdrant_client):
        """
        Initialize VisionBot with visual Qdrant connection.

        Args:
            visual_qdrant_client: ProductRetrieverAsync instance configured for visual embeddings
        """
        self.visual_qdrant = visual_qdrant_client
        self.name = "VisionBot"
        self.style = "visual-similarity"

        # Initialize CAMEL 0.2.7 components
        self._initialize_camel_agent()
        self._initialize_memory()
        self._initialize_roleplay()

        logger.info(f"{self.name} initialized with CAMEL 0.2.7, RolePlay, and visual intelligence")

        # Track statistics
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0
        }

    def _initialize_camel_agent(self):
        """Initialize the main CAMEL ChatAgent for visual intelligence"""
        try:
            model = ModelFactory.create(
                model_platform=ModelPlatformType.DEFAULT,
                model_type=ModelType.GPT_4O,
                model_config_dict={
                    "temperature": 0.8,  # Higher creativity for visual decisions
                    "max_tokens": 2000
                }
            )

            # Use dedicated VisionBot prompt

            self.agent = ChatAgent(
                system_message=BaseMessage.make_assistant_message(
                    role_name="Visual Stylist",
                    content=VISIONBOT_PROMPT
                ),
                model=model
            )

            logger.info("VisionBot CAMEL agent initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize CAMEL agent: {e}")
            raise RuntimeError(f"VisionBot CAMEL initialization failed: {e}") from e

    def _initialize_memory(self):
        """Initialize ChatHistoryMemory for visual pattern learning"""
        try:
            from camel.memories.context_creators import ScoreBasedContextCreator
            from camel.utils.token_counting import OpenAITokenCounter

            token_counter = OpenAITokenCounter(model=ModelType.GPT_4O)
            context_creator = ScoreBasedContextCreator(token_counter=token_counter, token_limit=4000)
            self.memory = ChatHistoryMemory(context_creator=context_creator, window_size=25)
            logger.info("VisionBot visual memory system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory = None

    def _initialize_roleplay(self):
        """Initialize RolePlaying society for visual collaboration"""
        try:
            self.role_playing = RolePlaying(
                assistant_role_name="Visual Stylist",
                user_role_name="Style Analyst",
                task_prompt="Analyze visual style queries and provide image-based fashion recommendations using visual similarity"
            )
            logger.info("VisionBot RolePlay society initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RolePlay: {e}")
            self.role_playing = None

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using VISUAL SIMILARITY intelligence.

        Args:
            query: Search query (will be interpreted visually)
            limit: Number of products to return
            filters: Search filters
            ml_intelligence: ML intelligence data
            user_context: User context
            conversation_context: Current conversation context

        Returns:
            List of visually similar products
        """
        start_time = datetime.now()
        self.stats["total_searches"] += 1

        logger.debug(f">>> {self.name}.search() START")
        logger.info(f"{self.name} searching: query='{query[:50]}...', filters={filters}")

        try:
            print(f"   VisionBot: Called with query='{query[:30]}...', filters={filters is not None}")

            # Get visual strategy from CAMEL agent
            strategy_start = datetime.now()
            strategy = await self._get_visual_strategy(
                query, ml_intelligence, filters, user_context
            )
            strategy_time = (datetime.now() - strategy_start).total_seconds()
            logger.info(f"Visual strategy determined in {strategy_time:.2f}s")
            print(f"   VisionBot: Strategy: {strategy[:50]}...")

            # Execute visual strategy
            logger.debug("Executing visual strategy...")
            exec_start = datetime.now()
            results = await self._execute_visual_strategy(
                strategy, query, limit, filters, ml_intelligence
            )
            exec_time = (datetime.now() - exec_start).total_seconds()
            logger.debug(f"Visual strategy executed in {exec_time:.2f}s, got {len(results)} results")
            print(f"   VisionBot: Strategy returned {len(results)} results in {exec_time:.2f}s")

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

    async def _visual_similarity_search(self, query: str, limit: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Visual similarity search using multimodal embeddings"""
        logger.debug(f">>> _visual_similarity_search: query='{query[:50]}...', limit={limit}")
        try:
            # Convert plural filter keys to singular for compatibility
            if filters:
                if 'categories' in filters and filters['categories']:
                    filters['category'] = filters['categories'][0] if isinstance(filters['categories'], list) else filters['categories']
                    logger.debug(f"Converted categories to category: {filters['category']}")
                if 'occasions' in filters and filters['occasions']:
                    filters['occasion'] = filters['occasions'][0] if isinstance(filters['occasions'], list) else filters['occasions']
                    logger.debug(f"Converted occasions to occasion: {filters['occasion']}")

            # Enhance query with visual terms
            visual_enhanced_query = f"visual style {query} appearance look"
            if filters:
                if 'category' in filters:
                    visual_enhanced_query = f"{filters['category']} {visual_enhanced_query}"
                    logger.debug(f"Added category to visual query: {filters['category']}")
                if 'colors' in filters:
                    visual_enhanced_query = f"{' '.join(filters['colors'])} {visual_enhanced_query}"
                    logger.debug(f"Added colors to visual query: {filters['colors']}")

            logger.debug(f"Calling Visual Qdrant with enhanced_query: '{visual_enhanced_query[:50]}...'")
            search_start = asyncio.get_event_loop().time()

            # Check if this is a new Visual Qdrant Client for FashionSigLIP embeddings
            if hasattr(self.visual_qdrant, 'visual_similarity_search'):
                # Use new FashionSigLIP visual similarity search
                logger.debug("Using FashionSigLIP visual similarity search")

                # For now, use combined embedding search with text query
                # TODO: Add image upload and processing for true visual search

                # Convert text query to search parameters
                product_filters = {}
                if filters:
                    if 'category' in filters:
                        # Note: This would need category field in Qdrant payloads
                        pass

                # Use text-based similarity search for now
                # In future: process uploaded images to get image_embedding
                results = await self.visual_qdrant.visual_similarity_search(
                    search_type="combined",  # Could be "image", "text", or "combined"
                    limit=limit,
                    score_threshold=0.3,
                    product_filters=product_filters
                )

            else:
                # Fallback to legacy text search
                logger.debug("Falling back to legacy text search")
                results = await self.visual_qdrant.search_by_natural_language(
                    query=visual_enhanced_query,
                    limit=limit,
                    filters=None,
                    score_threshold=0.3
                )

            search_time = asyncio.get_event_loop().time() - search_start
            logger.debug(f"Visual Qdrant search returned in {search_time:.2f}s with {len(results)} results")

            products = []
            filtered_count = 0
            for i, product in enumerate(results):
                if isinstance(product, dict):
                    product_id = product.get('id')
                    if product_id:
                        if self._validate_product_category(product, filters):
                            product['vision_reason'] = "Visual similarity match"
                            product['search_method'] = 'visual_similarity'
                            products.append(product)
                            if len(products) <= 3:
                                logger.debug(f"  Product {len(products)}: {product.get('title', 'NO_TITLE')[:30]}")
                        else:
                            filtered_count += 1
                            logger.debug(f"  Filtered out: {product.get('title', 'NO_TITLE')[:30]} - wrong category")
                    else:
                        logger.warning("Skipping product without ID from Visual Qdrant")

            if filtered_count > 0:
                logger.info(f"Category validation filtered out {filtered_count} irrelevant products")

            logger.debug(f"<<< _visual_similarity_search returning {len(products)} products")
            return products

        except Exception as e:
            logger.error(f"!!! Visual similarity search failed: {e}", exc_info=True)
            return []

    async def _get_visual_strategy(
        self,
        query: str,
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Use CAMEL agent to determine visual search strategy.

        Args:
            query: Search query
            ml_intelligence: ML intelligence data
            filters: Search filters
            user_context: User context

        Returns:
            Visual search strategy
        """
        context = f"""Determine the best visual search strategy for:
Query: "{query}"
Filters: {filters}
ML Intelligence: {ml_intelligence}
User Context: {user_context}

Available visual search strategies:
1. VISUAL_SIMILARITY - Direct visual similarity search using image embeddings
2. COLOR_BASED_VISUAL - Visual search focused on color matching
3. STYLE_VISUAL - Visual search focused on style patterns
4. TEXTURE_VISUAL - Visual search focused on texture and materials
5. GENERAL_VISUAL - General visual similarity search

Choose the best strategy and explain your reasoning in one sentence.
Return format: STRATEGY: reasoning"""

        try:
            response = await self.agent.arun(context)
            strategy_text = response.msg if hasattr(response, 'msg') else str(response)
            logger.debug(f"VisionBot strategy response: {strategy_text[:100]}...")
            return strategy_text
        except Exception as e:
            logger.error(f"Error getting visual strategy: {e}")
            return "GENERAL_VISUAL: Using general visual similarity search as fallback"

    async def _execute_visual_strategy(
        self,
        strategy: str,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute the chosen visual search strategy.

        Args:
            strategy: Visual strategy from CAMEL agent
            query: Search query
            limit: Result limit
            filters: Search filters
            ml_intelligence: ML intelligence data

        Returns:
            Search results
        """
        # Enhance query based on visual strategy
        enhanced_query = self._enhance_visual_query(query, strategy, ml_intelligence)

        # Use visual similarity search for all strategies
        print(f"   VisionBot: Using visual similarity search with query: '{enhanced_query}'")
        results = await self._visual_similarity_search(enhanced_query, limit, filters)
        print(f"   VisionBot: Visual search returned {len(results)} results")

        # Deduplicate and rank results
        unique_results = self._deduplicate_and_rank(results, query)

        # Add metadata to results
        for idx, product in enumerate(unique_results[:limit]):
            product['agent'] = self.name
            product['search_method'] = 'visual_similarity'
            product['rank'] = idx + 1

        return unique_results[:limit]

    def _enhance_visual_query(
        self,
        query: str,
        strategy: str,
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> str:
        """
        Enhance query based on visual strategy and ML intelligence.
        """
        enhanced = query

        # Add visual enhancement terms based on strategy
        if "COLOR" in strategy.upper():
            enhanced += " color palette visual harmony"
        elif "STYLE" in strategy.upper():
            enhanced += " style aesthetic design pattern"
        elif "TEXTURE" in strategy.upper():
            enhanced += " texture material fabric visual"
        else:
            enhanced += " visual style appearance look"

        # Add ML intelligence enhancements
        if ml_intelligence:
            for source, data in ml_intelligence.items():
                if "visual" in source.lower():
                    if isinstance(data, dict):
                        # Add visual ML insights
                        if 'query_visual_analysis' in data:
                            visual_data = data['query_visual_analysis']

                            # Add color information
                            visual_cues = visual_data.get('visual_cues', {})
                            colors = visual_cues.get('colors', [])
                            if colors:
                                enhanced += f" {' '.join(colors[:3])}"

                            # Add style information
                            styles = visual_cues.get('styles', [])
                            if styles:
                                enhanced += f" {' '.join(styles[:2])}"

                        print(f"   VisionBot: Enhanced query with Visual Intelligence: '{enhanced}'")
                        logger.info(f"VisionBot enhanced query with visual intelligence: '{enhanced}'")

        return enhanced

    def _validate_product_category(self, product: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
        """Validate product matches category filters"""
        if not filters or 'category' not in filters:
            return True

        required_category = filters['category'].lower()
        product_categories = product.get('categories', [])

        if isinstance(product_categories, str):
            product_categories = [product_categories]

        product_categories_lower = [cat.lower() for cat in product_categories]

        return any(required_category in cat or cat in required_category
                  for cat in product_categories_lower)

    def _deduplicate_and_rank(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Remove duplicates and rank results by visual relevance"""
        seen_ids = set()
        unique_results = []

        for product in results:
            product_id = product.get('id')
            if product_id and product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_results.append(product)

        # Sort by visual relevance (can be enhanced with visual scoring)
        unique_results.sort(key=lambda x: x.get('score', 0), reverse=True)

        return unique_results

    def get_stats(self) -> Dict[str, Any]:
        """Get VisionBot statistics"""
        stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0
        }
        stats.update(self.stats)

        # Calculate success rate
        if stats["total_searches"] > 0:
            stats["success_rate"] = (
                stats["successful_searches"] / stats["total_searches"] * 100
                if stats["total_searches"] > 0 else 0
            )
        else:
            stats["success_rate"] = 0

        return stats

    def _update_stats(
        self,
        products_found: int,
        search_time: float,
        success: bool = True
    ):
        """Update VisionBot statistics"""
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