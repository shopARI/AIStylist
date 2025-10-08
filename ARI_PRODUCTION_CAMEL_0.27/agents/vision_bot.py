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

# Import FashionSigLIP encoder
from services.ml.fashionsig_encoder import get_fashionsig_encoder

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

        # Initialize FashionSigLIP encoder for query embeddings
        try:
            logger.info(f"{self.name}: Loading FashionSigLIP encoder (may take 10-30 seconds)...")
            self.encoder = get_fashionsig_encoder()
            logger.info(f"{self.name}: FashionSigLIP encoder loaded successfully (1024d)")

            # Warm up the encoder with a test query to avoid first-query timeout
            try:
                import asyncio
                logger.info(f"{self.name}: Warming up encoder with test query...")
                test_embedding = asyncio.run(self.encoder.encode_text("test query"))
                logger.info(f"{self.name}: Encoder warmed up successfully (embedding shape: {test_embedding.shape})")
            except Exception as warmup_error:
                logger.warning(f"{self.name}: Encoder warmup failed (will work on first real query): {warmup_error}")

        except Exception as e:
            logger.warning(f"{self.name}: FashionSigLIP encoder failed to load: {e}")
            logger.warning(f"{self.name}: Will fall back to text-only search")
            self.encoder = None

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
        conversation_context: Optional[Dict[str, Any]] = None,
        image_path: Optional[str] = None
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
            image_path: Optional path/URL to image for visual search

        Returns:
            List of visually similar products
        """
        start_time = datetime.now()
        self.stats["total_searches"] += 1

        logger.debug(f">>> {self.name}.search() START")
        logger.info(f"{self.name} searching: query='{query[:50]}...', filters={filters}")

        try:
            # Get visual strategy from CAMEL agent
            strategy_start = datetime.now()
            strategy = await self._get_visual_strategy(
                query, ml_intelligence, filters, user_context
            )
            strategy_time = (datetime.now() - strategy_start).total_seconds()
            logger.info(f"Visual strategy determined in {strategy_time:.2f}s")

            # Execute visual strategy
            logger.debug("Executing visual strategy...")
            exec_start = datetime.now()
            results = await self._execute_visual_strategy(
                strategy, query, limit, filters, ml_intelligence, image_path
            )
            exec_time = (datetime.now() - exec_start).total_seconds()
            logger.debug(f"Visual strategy executed in {exec_time:.2f}s, got {len(results)} results")

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

    async def _visual_similarity_search(self, query: str, limit: int, filters: Optional[Dict[str, Any]], image_path: Optional[str] = None) -> List[Dict[str, Any]]:
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
            if hasattr(self.visual_qdrant, 'visual_similarity_search') and self.encoder:
                # Use FashionSigLIP visual similarity search with query embeddings
                logger.debug("Using FashionSigLIP visual similarity search with query embeddings")

                try:
                    # Determine search type based on input
                    if image_path:
                        # Image-based search
                        logger.debug(f"Generating image embedding from: '{image_path}'")
                        image_embedding = await self.encoder.encode_image(image_path)
                        logger.debug(f"Image embedding generated: shape={image_embedding.shape}, norm={np.linalg.norm(image_embedding):.3f}")

                        # Convert filters to product_filters
                        product_filters = {}
                        if filters:
                            if 'category' in filters:
                                pass

                        # Search using image embedding
                        results = await self.visual_qdrant.visual_similarity_search(
                            image_embedding=image_embedding,
                            search_type="image",  # Using image embeddings
                            limit=limit,
                            score_threshold=0.01,  # Very low threshold for vision-only collection
                            product_filters=product_filters
                        )

                        logger.debug(f"Image-based visual search returned {len(results)} results")

                    else:
                        # Text-based search
                        logger.debug(f"Generating text embedding for: '{visual_enhanced_query[:50]}...'")
                        text_embedding = await self.encoder.encode_text(visual_enhanced_query)
                        logger.debug(f"Text embedding generated: shape={text_embedding.shape}, norm={np.linalg.norm(text_embedding):.3f}")

                        # Convert filters to product_filters
                        product_filters = {}
                        if filters:
                            if 'category' in filters:
                                # Note: This would need category field in Qdrant payloads
                                pass

                        # Search using text embedding
                        results = await self.visual_qdrant.visual_similarity_search(
                            text_embedding=text_embedding,
                            search_type="text",  # Using text embeddings
                            limit=limit,
                            score_threshold=0.01,  # Very low threshold for text vs vision embeddings
                            product_filters=product_filters
                        )

                        # FALLBACK: If no results with threshold, try without threshold
                        if not results:
                            logger.warning(f"VisionBot: No results with threshold 0.01, trying without threshold")
                            results = await self.visual_qdrant.visual_similarity_search(
                                text_embedding=text_embedding,
                                search_type="text",
                                limit=limit,
                                score_threshold=0.0,  # No threshold - return top matches
                                product_filters=product_filters
                            )
                            logger.info(f"VisionBot: Fallback search returned {len(results)} results")

                        logger.debug(f"Text-based visual search returned {len(results)} results")

                    logger.debug(f"Visual similarity search with embeddings returned {len(results)} results")

                except Exception as e:
                    logger.error(f"FashionSigLIP embedding search failed: {e}")
                    logger.warning("Falling back to text search")
                    # Fallback to text search
                    results = await self.visual_qdrant.search_by_natural_language(
                        query=visual_enhanced_query,
                        limit=limit,
                        filters=None,
                        score_threshold=0.01  # Very low threshold for better recall
                    )

            elif hasattr(self.visual_qdrant, 'visual_similarity_search'):
                # Encoder not available, use text search without embeddings
                logger.debug("FashionSigLIP encoder not available, using text search")

                product_filters = {}
                if filters:
                    if 'category' in filters:
                        pass

                results = await self.visual_qdrant.visual_similarity_search(
                    search_type="combined",
                    limit=limit,
                    score_threshold=0.05,  # Lower threshold for vision-only collection
                    product_filters=product_filters
                )

            else:
                # Fallback to legacy text search
                logger.debug("Falling back to legacy text search")
                results = await self.visual_qdrant.search_by_natural_language(
                    query=visual_enhanced_query,
                    limit=limit,
                    filters=None,
                    score_threshold=0.05  # Lower threshold for better recall
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
            response = self.agent.step(context)
            strategy_text = response.msg.content if hasattr(response.msg, 'content') else str(response)
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
        ml_intelligence: Optional[Dict[str, Any]],
        image_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute the chosen visual search strategy.

        Args:
            strategy: Visual strategy from CAMEL agent
            query: Search query
            limit: Result limit
            filters: Search filters
            ml_intelligence: ML intelligence data
            image_path: Optional image for visual search

        Returns:
            Search results
        """
        # Enhance query based on visual strategy
        enhanced_query = self._enhance_visual_query(query, strategy, ml_intelligence)

        # Use visual similarity search for all strategies
        results = await self._visual_similarity_search(enhanced_query, limit, filters, image_path)

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