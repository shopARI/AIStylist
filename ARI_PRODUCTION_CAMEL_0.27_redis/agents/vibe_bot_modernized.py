"""
VibeBot - Aesthetic-driven fashion intelligence agent modernized with CAMEL-AI 0.2.7
Features: RolePlay multi-agent collaboration, ChatHistoryMemory, and advanced Qdrant aesthetic intelligence
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from camel.agents import ChatAgent
from camel.models import ModelFactory, ModelType
from camel.memories import ChatHistoryMemory
from camel.societies import RolePlaying
from camel.messages import BaseMessage
from camel.types import RoleType

from config.prompts import VIBEBOT_PROMPT

logger = logging.getLogger("agents.vibe_bot_modernized")

class VibeBotModernized:
    """
    VibeBot - Aesthetic-driven fashion intelligence using Qdrant with CAMEL 0.2.7.
    Enhanced with RolePlay societies, memory, and advanced aesthetic reasoning.
    """
    
    def __init__(self, qdrant_client, **kwargs):
        """
        Initialize VibeBot with Qdrant connection and CAMEL 0.2.7 features.
        
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
        
        # Aesthetic intelligence features
        self.aesthetic_patterns = {}
        self.style_learning_cache = {}
        self.color_preferences = {}
        
        # Statistics tracking
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0,
            "aesthetic_insights": 0,
            "style_collaborations": 0,
            "memory_enhanced_searches": 0
        }
        
        logger.info(f"{self.name} initialized with CAMEL 0.2.7, RolePlay, and aesthetic intelligence")

    def _initialize_camel_agent(self):
        """Initialize the main CAMEL ChatAgent for aesthetic intelligence"""
        try:
            model = ModelFactory.create(
                model_platform=ModelType.OPENAI,
                model_type="gpt-4o-mini",
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
            self.memory = ChatHistoryMemory(message_window_size=25)  # Larger window for style patterns
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

    def _learn_aesthetic_patterns(self, query: str, results: List, strategy: str, execution_time: float):
        """Learn aesthetic patterns and style preferences using memory"""
        if not self.memory:
            return
            
        try:
            # Analyze aesthetic patterns in results
            color_analysis = self._analyze_color_patterns(results)
            style_analysis = self._analyze_style_patterns(results)
            
            # Create aesthetic learning message
            aesthetic_insights = f"""Aesthetic Analysis:
Query: "{query}"
Strategy: {strategy}
Results: {len(results)} products found
Execution Time: {execution_time:.2f}s

Color Patterns: {color_analysis}
Style Patterns: {style_analysis}
Visual Harmony Score: {self._calculate_visual_harmony_score(results)}

Top Aesthetic Matches:
{self._get_top_aesthetic_descriptions(results[:3])}

Learning Insights:
- Query aesthetic interpretation: {self._interpret_aesthetic_query(query)}
- Strategy effectiveness: {self._assess_strategy_effectiveness(strategy, results)}
- Style coherence: {self._assess_style_coherence(results)}
"""
            
            message = BaseMessage.make_user_message(
                role_name="Aesthetic Analyzer", 
                content=aesthetic_insights
            )
            self.memory.write(message)
            self.stats["aesthetic_insights"] += 1
            
            # Update aesthetic learning cache
            self._update_aesthetic_cache(query, results, strategy)
            
            logger.debug(f"Stored aesthetic learning: {len(results)} results, strategy: {strategy}")
            
        except Exception as e:
            logger.error(f"Failed to store aesthetic learning: {e}")

    def _analyze_color_patterns(self, results: List) -> Dict[str, Any]:
        """Analyze color patterns in search results"""
        color_counts = {}
        color_combinations = []
        
        for product in results[:10]:  # Analyze top 10
            title = product.get('title', '').lower()
            description = product.get('description', '').lower()
            text = f"{title} {description}"
            
            # Extract color keywords
            color_keywords = ['red', 'blue', 'green', 'black', 'white', 'pink', 
                             'purple', 'yellow', 'orange', 'brown', 'gray', 'navy',
                             'beige', 'cream', 'gold', 'silver', 'maroon', 'teal']
            
            found_colors = [color for color in color_keywords if color in text]
            
            for color in found_colors:
                color_counts[color] = color_counts.get(color, 0) + 1
            
            if len(found_colors) > 1:
                color_combinations.append(found_colors[:2])
        
        return {
            "dominant_colors": sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "color_combinations": color_combinations[:3],
            "color_diversity": len(color_counts)
        }

    def _analyze_style_patterns(self, results: List) -> Dict[str, Any]:
        """Analyze style patterns in search results"""
        style_keywords = {
            'casual': ['casual', 'relaxed', 'comfortable', 'everyday'],
            'formal': ['formal', 'elegant', 'sophisticated', 'professional'],
            'trendy': ['trendy', 'fashionable', 'modern', 'contemporary'],
            'classic': ['classic', 'timeless', 'traditional', 'vintage'],
            'bohemian': ['bohemian', 'boho', 'free-spirited', 'artistic'],
            'minimalist': ['minimalist', 'simple', 'clean', 'understated']
        }
        
        style_scores = {}
        
        for product in results[:10]:
            title = product.get('title', '').lower()
            description = product.get('description', '').lower()
            text = f"{title} {description}"
            
            for style, keywords in style_keywords.items():
                score = sum(1 for keyword in keywords if keyword in text)
                style_scores[style] = style_scores.get(style, 0) + score
        
        return {
            "dominant_styles": sorted(style_scores.items(), key=lambda x: x[1], reverse=True)[:3],
            "style_coherence": max(style_scores.values()) / sum(style_scores.values()) if style_scores else 0
        }

    def _calculate_visual_harmony_score(self, results: List) -> float:
        """Calculate visual harmony score based on product consistency"""
        if len(results) < 2:
            return 1.0
        
        # Simple harmony calculation based on title similarity and style consistency
        titles = [product.get('title', '') for product in results[:5]]
        
        # Check for common words (style indicators)
        all_words = []
        for title in titles:
            all_words.extend(title.lower().split())
        
        word_counts = {}
        for word in all_words:
            if len(word) > 3:  # Skip short words
                word_counts[word] = word_counts.get(word, 0) + 1
        
        # Harmony is higher when products share style-related words
        common_words = {w: c for w, c in word_counts.items() if c > 1}
        harmony_score = min(len(common_words) / 10, 1.0)  # Normalize to 0-1
        
        return harmony_score

    def _get_top_aesthetic_descriptions(self, products: List) -> str:
        """Get aesthetic descriptions of top products"""
        descriptions = []
        for i, product in enumerate(products[:3]):
            title = product.get('title', 'Unknown product')[:50]
            price = product.get('price', 'N/A')
            descriptions.append(f"{i+1}. {title} (${price})")
        
        return '\n'.join(descriptions) if descriptions else "No products to describe"

    def _interpret_aesthetic_query(self, query: str) -> str:
        """Interpret the aesthetic intention behind a query"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['elegant', 'sophisticated', 'classy']):
            return "Seeking refined, upscale aesthetic"
        elif any(word in query_lower for word in ['casual', 'comfortable', 'relaxed']):
            return "Seeking comfortable, everyday aesthetic"
        elif any(word in query_lower for word in ['trendy', 'fashionable', 'modern']):
            return "Seeking contemporary, fashion-forward aesthetic"
        elif any(word in query_lower for word in ['unique', 'artistic', 'creative']):
            return "Seeking distinctive, expressive aesthetic"
        else:
            return "General aesthetic preference"

    def _assess_strategy_effectiveness(self, strategy: str, results: List) -> str:
        """Assess how effective the chosen strategy was"""
        result_count = len(results)
        
        if result_count == 0:
            return "Strategy failed - no results found"
        elif result_count < 5:
            return "Strategy too specific - limited results"
        elif result_count > 20:
            return "Strategy too broad - many results"
        else:
            return "Strategy well-balanced - good result range"

    def _assess_style_coherence(self, results: List) -> str:
        """Assess the style coherence of results"""
        if len(results) < 3:
            return "Insufficient results for coherence analysis"
        
        # Simple coherence check based on price range consistency
        prices = []
        for product in results[:5]:
            try:
                price_str = str(product.get('price', '0')).replace('$', '').replace(',', '')
                price = float(price_str)
                prices.append(price)
            except (ValueError, TypeError):
                continue
        
        if len(prices) >= 3:
            price_range = max(prices) - min(prices)
            avg_price = sum(prices) / len(prices)
            
            if price_range / avg_price < 0.5:
                return "High coherence - consistent price range"
            elif price_range / avg_price < 1.0:
                return "Medium coherence - moderate price variation"
            else:
                return "Low coherence - wide price variation"
        
        return "Unable to assess coherence"

    def _update_aesthetic_cache(self, query: str, results: List, strategy: str):
        """Update aesthetic learning cache"""
        query_key = query.lower()[:50]  # Use first 50 chars as key
        
        self.aesthetic_patterns[query_key] = {
            'strategy': strategy,
            'result_count': len(results),
            'timestamp': datetime.now().isoformat(),
            'effectiveness': self._assess_strategy_effectiveness(strategy, results)
        }
        
        # Keep only recent 100 patterns
        if len(self.aesthetic_patterns) > 100:
            oldest_key = min(self.aesthetic_patterns.keys(), 
                           key=lambda k: self.aesthetic_patterns[k]['timestamp'])
            del self.aesthetic_patterns[oldest_key]

    async def collaborate_on_aesthetic_strategy(self, query: str, ml_intelligence: Optional[Dict]) -> Dict[str, Any]:
        """Use RolePlay to collaborate on aesthetic strategy"""
        if not self.role_playing:
            return {"strategy": "GENERAL", "method": "direct"}
        
        try:
            self.stats["style_collaborations"] += 1
            
            # Create aesthetic collaboration task
            aesthetic_context = f"""Analyze this aesthetic fashion query: '{query}'
            
Available intelligence: {json.dumps(ml_intelligence, indent=2) if ml_intelligence else 'None'}

Determine the best aesthetic search strategy:
1. VISUAL_SIMILARITY - Based on visual features and appearance
2. COLOR_HARMONY - Based on color coordination and palette
3. STYLE_COHERENCE - Based on consistent style attributes
4. TREND_ANALYSIS - Based on current fashion trends
5. MOOD_AESTHETIC - Based on emotional/aesthetic mood
6. HYBRID_AESTHETIC - Combination approach

Consider visual harmony, color theory, and style coherence."""
            
            # Run collaborative aesthetic analysis
            assistant_msg, user_msg = self.role_playing.init_chat()
            
            # Aesthetic Stylist analyzes the query
            stylist_response = self.role_playing.step(
                assistant_msg, 
                BaseMessage.make_user_message("Style Analyst", aesthetic_context)
            )
            
            # Extract aesthetic strategy
            collaboration_result = {
                "original_query": query,
                "aesthetic_analysis": stylist_response.content if stylist_response else "No analysis available",
                "strategy": self._extract_strategy_from_collaboration(stylist_response),
                "method": "collaborative_aesthetic_roleplay",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Aesthetic collaboration completed: {collaboration_result['strategy']}")
            return collaboration_result
            
        except Exception as e:
            logger.error(f"Aesthetic collaboration failed: {e}")
            return {"strategy": "GENERAL", "method": "fallback", "error": str(e)}

    def _extract_strategy_from_collaboration(self, response) -> str:
        """Extract strategy from collaborative response"""
        if not response or not hasattr(response, 'content'):
            return "GENERAL"
        
        content = response.content.upper()
        strategies = ["VISUAL_SIMILARITY", "COLOR_HARMONY", "STYLE_COHERENCE", 
                     "TREND_ANALYSIS", "MOOD_AESTHETIC", "HYBRID_AESTHETIC"]
        
        for strategy in strategies:
            if strategy.replace('_', ' ') in content or strategy in content:
                return strategy
        
        return "GENERAL"

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Enhanced aesthetic search with CAMEL 0.2.7 features: memory, RolePlay, and aesthetic intelligence.
        """
        
        start_time = datetime.now()
        self.stats["total_searches"] += 1
        
        logger.debug(f">>> {self.name}.search() START with CAMEL 0.2.7")
        logger.info(f"{self.name} aesthetic search: query='{query[:50]}...', filters={filters}")
        
        try:
            # Collaborative aesthetic strategy determination
            collaboration = await self.collaborate_on_aesthetic_strategy(query, ml_intelligence)
            strategy = collaboration.get("strategy", "GENERAL")
            logger.debug(f"Aesthetic collaboration result: {strategy}")
            
            # Memory-enhanced strategy refinement
            memory_context = self._get_memory_aesthetic_context() if self.memory else {}
            if memory_context and self.memory:
                self.stats["memory_enhanced_searches"] += 1
                logger.debug(f"Memory enhancement: {len(memory_context)} aesthetic insights")
            
            # Get enhanced strategy from CAMEL agent
            agent_strategy = await self._get_memory_enhanced_agent_strategy(
                query, ml_intelligence, filters, user_context, memory_context
            )
            
            # Execute aesthetic strategy
            logger.debug(f"Executing aesthetic strategy: {strategy}")
            exec_start = datetime.now()
            results = await self._execute_aesthetic_strategy(
                agent_strategy, query, limit, filters, ml_intelligence, collaboration
            )
            exec_time = (datetime.now() - exec_start).total_seconds()
            
            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_stats(len(results), elapsed, success=True)
            
            # Learn from aesthetic search
            self._learn_aesthetic_patterns(query, results, strategy, exec_time)
            
            # Add CAMEL 0.2.7 metadata
            for idx, product in enumerate(results):
                product['agent'] = self.name
                product['search_method'] = 'camel_aesthetic_intelligence'
                product['camel_version'] = '0.2.7'
                product['aesthetic_strategy'] = strategy
                product['memory_enhanced'] = bool(self.memory)
                product['collaborative'] = bool(self.role_playing)
                product['aesthetic_score'] = self._calculate_aesthetic_score(product, query)
                
                if idx < 3:
                    logger.debug(f"  Aesthetic Product {idx}: {product.get('title', 'NO_TITLE')[:30]}")
            
            logger.info(f"{self.name} found {len(results)} aesthetic matches in {elapsed:.2f}s (CAMEL 0.2.7)")
            logger.debug(f"<<< {self.name}.search() END")
            return results
            
        except Exception as e:
            logger.error(f"!!! {self.name} aesthetic search failed: {e}", exc_info=True)
            self.stats["failed_searches"] += 1
            return []

    def _get_memory_aesthetic_context(self) -> Dict[str, Any]:
        """Extract aesthetic insights from memory"""
        if not self.memory:
            return {}
        
        try:
            messages = self.memory.retrieve()
            
            # Analyze aesthetic patterns from memory
            aesthetic_patterns = []
            color_preferences = {}
            style_preferences = {}
            
            for message in messages[-10:]:  # Last 10 messages
                content = message.content if hasattr(message, 'content') else str(message)
                
                # Extract aesthetic insights
                if "Color Patterns:" in content:
                    # Parse color information
                    pass
                if "Style Patterns:" in content:
                    # Parse style information  
                    pass
            
            context = {
                "recent_aesthetic_analyses": len(messages),
                "aesthetic_learning_cache": len(self.aesthetic_patterns),
                "memory_insights": "aesthetic patterns identified"
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get memory aesthetic context: {e}")
            return {}

    async def _get_memory_enhanced_agent_strategy(
        self,
        query: str,
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]],
        memory_context: Dict[str, Any]
    ) -> str:
        """Get enhanced strategy from CAMEL agent using memory insights"""
        
        # Build comprehensive context
        context = f"""Determine the optimal aesthetic search strategy for:
Query: "{query}"
Has filters: {bool(filters)}
Memory insights: {len(memory_context)} previous aesthetic analyses
"""
        
        # Add ML intelligence
        if ml_intelligence and 'vibe_intel' in ml_intelligence:
            intel = ml_intelligence['vibe_intel']
            context += f"\nML Intelligence available: {list(intel.keys())}"
            
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
                        context += f"\nStyle analysis: {json.dumps(style)[:100]}"
        
        # Add user preferences
        if user_context:
            context += f"\nUser context: {json.dumps(user_context, indent=2)[:200]}"
        
        # Add memory insights
        if memory_context:
            context += f"\nMemory context: {json.dumps(memory_context)[:200]}"
        
        # Add aesthetic strategy options
        context += """

Available aesthetic strategies:
1. VISUAL_SIMILARITY - Find products with similar visual appearance and styling
2. COLOR_HARMONY - Focus on color coordination and palette matching
3. STYLE_COHERENCE - Maintain consistent style attributes and themes
4. TREND_ANALYSIS - Incorporate current fashion trends and popular styles
5. MOOD_AESTHETIC - Match the emotional and aesthetic mood of the query
6. HYBRID_AESTHETIC - Combine multiple aesthetic approaches

Respond with the strategy name and detailed aesthetic reasoning."""
        
        try:
            user_msg = BaseMessage.make_user_message("Strategy Analyzer", content=context)
            response = self.agent.step(user_msg)
            
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                strategy = response.msg.content
            else:
                strategy = str(response)
            
            logger.debug(f"Memory-enhanced agent strategy: {strategy[:100]}...")
            return strategy
            
        except Exception as e:
            logger.error(f"Memory-enhanced agent strategy error: {e}")
            return "GENERAL aesthetic search"

    async def _execute_aesthetic_strategy(
        self,
        strategy: str,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]],
        collaboration: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Execute the chosen aesthetic strategy with CAMEL 0.2.7 enhancements"""
        
        strategy_lower = strategy.lower()
        results = []
        
        # Enhanced query based on strategy and collaboration
        enhanced_query = self._enhance_aesthetic_query(query, strategy, ml_intelligence, collaboration)
        
        # Execute based on aesthetic strategy
        if "visual" in strategy_lower or "similarity" in strategy_lower:
            results.extend(await self._visual_similarity_search(enhanced_query, limit, filters, ml_intelligence))
        
        if "color" in strategy_lower or "harmony" in strategy_lower:
            results.extend(await self._color_harmony_search(query, limit, filters, ml_intelligence))
        
        if "style" in strategy_lower or "coherence" in strategy_lower:
            results.extend(await self._style_coherence_search(enhanced_query, limit, filters))
        
        if "trend" in strategy_lower or "analysis" in strategy_lower:
            results.extend(await self._trend_analysis_search(enhanced_query, limit, filters))
        
        if "mood" in strategy_lower or "aesthetic" in strategy_lower:
            results.extend(await self._mood_aesthetic_search(query, limit, filters, ml_intelligence))
        
        if "hybrid" in strategy_lower:
            # Combine multiple approaches
            hybrid_results = await self._hybrid_aesthetic_search(query, limit, filters, ml_intelligence)
            results.extend(hybrid_results)
        
        # Always include some general results for diversity
        if len(results) < limit:
            general = await self._general_aesthetic_search(query, limit - len(results), filters)
            results.extend(general)
        
        # Aesthetic-aware deduplication and ranking
        unique_results = self._aesthetic_deduplicate_and_rank(results, query, collaboration)
        
        # Add aesthetic metadata
        for idx, product in enumerate(unique_results[:limit]):
            product['aesthetic_rank'] = idx + 1
            product['aesthetic_strategy'] = collaboration.get('strategy', 'UNKNOWN')
            product['visual_harmony_score'] = self._calculate_product_harmony_score(product)
        
        return unique_results[:limit]

    def _enhance_aesthetic_query(self, query: str, strategy: str, ml_intelligence: Optional[Dict], collaboration: Dict) -> str:
        """Enhance query with aesthetic intelligence"""
        enhanced = query
        
        # Add aesthetic descriptors based on strategy
        strategy_lower = strategy.lower()
        
        if "visual" in strategy_lower:
            enhanced += " aesthetic appearance visual style look"
        if "color" in strategy_lower:
            enhanced += " color coordination palette harmony"
        if "style" in strategy_lower:
            enhanced += " style coherent fashionable design"
        if "trend" in strategy_lower:
            enhanced += " trending popular current fashion"
        if "mood" in strategy_lower:
            enhanced += " mood aesthetic vibe feeling"
        
        # Add collaboration insights
        if collaboration and 'aesthetic_analysis' in collaboration:
            analysis = collaboration['aesthetic_analysis'].lower()
            if 'elegant' in analysis:
                enhanced += " elegant sophisticated refined"
            if 'casual' in analysis:
                enhanced += " casual comfortable relaxed"
            if 'modern' in analysis:
                enhanced += " modern contemporary current"
        
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

    async def _visual_similarity_search(self, query: str, limit: int, filters: Optional[Dict], ml_intelligence: Optional[Dict]) -> List[Dict]:
        """Enhanced visual similarity search"""
        try:
            # If we have a reference product from ML intelligence, use it
            reference_product_id = None
            if ml_intelligence and 'vibe_intel' in ml_intelligence:
                for source, data in ml_intelligence['vibe_intel'].items():
                    if isinstance(data, dict) and 'reference_product' in data:
                        reference_product_id = data['reference_product']
                        break
            
            if reference_product_id:
                results = await self.qdrant.get_similar_products(
                    product_id=reference_product_id,
                    limit=limit
                )
                
                for product in results:
                    product['vibe_reason'] = "Visual similarity to reference (CAMEL enhanced)"
                    product['aesthetic_method'] = "visual_similarity"
                
                return results
            else:
                # Enhanced semantic search with visual keywords
                visual_query = f"{query} visual style aesthetic appearance look design"
                return await self._semantic_search(visual_query, limit, filters)
                
        except Exception as e:
            logger.error(f"Visual similarity search failed: {e}")
            return []

    async def _color_harmony_search(self, query: str, limit: int, filters: Optional[Dict], ml_intelligence: Optional[Dict]) -> List[Dict]:
        """Enhanced color harmony search"""
        try:
            # Extract colors from various sources
            colors = []
            
            # From ML intelligence
            if ml_intelligence and 'vibe_intel' in ml_intelligence:
                for source, data in ml_intelligence['vibe_intel'].items():
                    if isinstance(data, dict) and 'visual_features' in data:
                        detected_colors = data['visual_features'].get('colors', [])
                        colors.extend(detected_colors[:3])
                        break
            
            # From query text
            if not colors:
                color_keywords = ['red', 'blue', 'green', 'black', 'white', 'pink', 
                                'purple', 'yellow', 'orange', 'brown', 'gray', 'navy',
                                'beige', 'cream', 'gold', 'silver', 'maroon', 'teal']
                query_lower = query.lower()
                colors = [c for c in color_keywords if c in query_lower]
            
            if colors:
                # Enhanced color search with harmony considerations
                color_query = f"{query} {' '.join(colors[:3])} color harmony coordination"
                results = await self.qdrant.search_by_natural_language(
                    query=color_query,
                    limit=limit,
                    filters=None
                )
                
                for product in results:
                    product['vibe_reason'] = f"Color harmony match: {', '.join(colors[:2])} (CAMEL enhanced)"
                    product['aesthetic_method'] = "color_harmony"
                
                return results
            else:
                return await self._general_aesthetic_search(query, limit, filters)
                
        except Exception as e:
            logger.error(f"Color harmony search failed: {e}")
            return []

    async def _style_coherence_search(self, query: str, limit: int, filters: Optional[Dict]) -> List[Dict]:
        """Enhanced style coherence search"""
        try:
            style_keywords = {
                'elegant': ['sophisticated', 'refined', 'classy', 'graceful'],
                'casual': ['relaxed', 'comfortable', 'informal', 'everyday'],
                'modern': ['contemporary', 'current', 'trendy', 'updated'],
                'classic': ['timeless', 'traditional', 'vintage', 'enduring'],
                'bohemian': ['boho', 'artistic', 'free-spirited', 'eclectic'],
                'minimalist': ['simple', 'clean', 'understated', 'streamlined']
            }
            
            # Identify dominant style from query
            query_lower = query.lower()
            dominant_style = None
            for style, keywords in style_keywords.items():
                if style in query_lower or any(kw in query_lower for kw in keywords):
                    dominant_style = style
                    break
            
            if dominant_style:
                # Enhance query with style coherence terms
                style_terms = style_keywords[dominant_style]
                enhanced_query = f"{query} {dominant_style} {' '.join(style_terms[:2])} coherent style"
            else:
                enhanced_query = f"{query} coherent style consistent design"
            
            results = await self.qdrant.search_by_natural_language(
                query=enhanced_query,
                limit=limit,
                filters=filters
            )
            
            for product in results:
                product['vibe_reason'] = f"Style coherence match: {dominant_style or 'general'} (CAMEL enhanced)"
                product['aesthetic_method'] = "style_coherence"
            
            return results
            
        except Exception as e:
            logger.error(f"Style coherence search failed: {e}")
            return []

    async def _trend_analysis_search(self, query: str, limit: int, filters: Optional[Dict]) -> List[Dict]:
        """Enhanced trend analysis search"""
        try:
            # Current trend keywords (would be updated regularly in production)
            trend_keywords = ['trending', 'popular', 'fashionable', 'current', 'hot', 'latest', 'new', 'modern']
            
            # Enhance query with trend analysis
            trend_query = f"{query} {' '.join(trend_keywords[:3])} fashion trend"
            
            results = await self.qdrant.search_by_natural_language(
                query=trend_query,
                limit=limit,
                filters=filters
            )
            
            for product in results:
                product['vibe_reason'] = "Trend analysis match (CAMEL enhanced)"
                product['aesthetic_method'] = "trend_analysis"
            
            return results
            
        except Exception as e:
            logger.error(f"Trend analysis search failed: {e}")
            return []

    async def _mood_aesthetic_search(self, query: str, limit: int, filters: Optional[Dict], ml_intelligence: Optional[Dict]) -> List[Dict]:
        """Enhanced mood aesthetic search"""
        try:
            # Mood mapping
            mood_keywords = {
                'romantic': ['romantic', 'dreamy', 'feminine', 'soft', 'delicate'],
                'edgy': ['edgy', 'bold', 'dramatic', 'striking', 'powerful'],
                'playful': ['playful', 'fun', 'quirky', 'colorful', 'whimsical'],
                'sophisticated': ['sophisticated', 'mature', 'professional', 'polished'],
                'relaxed': ['relaxed', 'comfortable', 'easy', 'laid-back', 'casual']
            }
            
            # Detect mood from query
            query_lower = query.lower()
            detected_moods = []
            for mood, keywords in mood_keywords.items():
                if mood in query_lower or any(kw in query_lower for kw in keywords):
                    detected_moods.append(mood)
            
            if detected_moods:
                mood = detected_moods[0]
                mood_terms = mood_keywords[mood]
                enhanced_query = f"{query} {mood} {' '.join(mood_terms[:2])} aesthetic mood"
            else:
                enhanced_query = f"{query} aesthetic mood vibe feeling"
            
            results = await self.qdrant.search_by_natural_language(
                query=enhanced_query,
                limit=limit,
                filters=filters
            )
            
            for product in results:
                product['vibe_reason'] = f"Mood aesthetic match: {detected_moods[0] if detected_moods else 'general'} (CAMEL enhanced)"
                product['aesthetic_method'] = "mood_aesthetic"
            
            return results
            
        except Exception as e:
            logger.error(f"Mood aesthetic search failed: {e}")
            return []

    async def _hybrid_aesthetic_search(self, query: str, limit: int, filters: Optional[Dict], ml_intelligence: Optional[Dict]) -> List[Dict]:
        """Hybrid aesthetic search combining multiple approaches"""
        try:
            # Get smaller batches from different approaches
            batch_size = max(limit // 3, 3)
            
            # Visual + Color + Style combination
            visual_results = await self._visual_similarity_search(query, batch_size, filters, ml_intelligence)
            color_results = await self._color_harmony_search(query, batch_size, filters, ml_intelligence)
            style_results = await self._style_coherence_search(query, batch_size, filters)
            
            # Combine and mark as hybrid
            all_results = visual_results + color_results + style_results
            
            for product in all_results:
                current_reason = product.get('vibe_reason', '')
                product['vibe_reason'] = f"Hybrid aesthetic: {current_reason}"
                product['aesthetic_method'] = "hybrid_aesthetic"
            
            return all_results
            
        except Exception as e:
            logger.error(f"Hybrid aesthetic search failed: {e}")
            return []

    async def _general_aesthetic_search(self, query: str, limit: int, filters: Optional[Dict]) -> List[Dict]:
        """General aesthetic search with CAMEL enhancements"""
        try:
            # Enhanced general query
            general_query = f"{query} aesthetic style fashion"
            
            results = await self.qdrant.search_by_natural_language(
                query=general_query,
                limit=limit,
                filters=filters
            )
            
            for product in results:
                product['vibe_reason'] = "General aesthetic match (CAMEL enhanced)"
                product['aesthetic_method'] = "general_aesthetic"
            
            return results
            
        except Exception as e:
            logger.error(f"General aesthetic search failed: {e}")
            return []

    async def _semantic_search(self, query: str, limit: int, filters: Optional[Dict]) -> List[Dict]:
        """Enhanced semantic search"""
        try:
            results = await self.qdrant.search_by_natural_language(
                query=query,
                limit=limit,
                filters=None  # Don't use metadata filters
            )
            
            products = []
            for i, product in enumerate(results):
                if isinstance(product, dict):
                    product_id = product.get('id')
                    if product_id:
                        product['vibe_reason'] = "Semantic similarity match (CAMEL enhanced)"
                        product['aesthetic_method'] = "semantic"
                        products.append(product)
                        
                        if i < 3:
                            logger.debug(f"  Semantic Product {i}: {product.get('title', 'NO_TITLE')[:30]}")
            
            return products
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def _aesthetic_deduplicate_and_rank(self, results: List[Dict], query: str, collaboration: Dict) -> List[Dict]:
        """Enhanced deduplication and ranking with aesthetic intelligence"""
        seen = set()
        unique = []
        
        for product in results:
            product_id = product.get('id')
            if product_id and product_id not in seen:
                seen.add(product_id)
                
                # Calculate enhanced aesthetic relevance score
                score = self._calculate_aesthetic_score(product, query)
                
                # Boost based on aesthetic method
                method = product.get('aesthetic_method', '')
                if method == 'visual_similarity':
                    score += 0.2
                elif method == 'color_harmony':
                    score += 0.15
                elif method == 'style_coherence':
                    score += 0.15
                elif method == 'hybrid_aesthetic':
                    score += 0.1
                
                # Boost for CAMEL enhancements
                if 'CAMEL enhanced' in product.get('vibe_reason', ''):
                    score += 0.1
                
                product['aesthetic_relevance_score'] = min(score, 1.0)
                unique.append(product)
        
        # Sort by aesthetic relevance score
        unique.sort(key=lambda x: x.get('aesthetic_relevance_score', 0), reverse=True)
        
        return unique

    def _calculate_aesthetic_score(self, product: Dict, query: str) -> float:
        """Calculate aesthetic relevance score"""
        try:
            score = 0.5  # Base score
            
            # Title quality and relevance
            title = product.get('title', '').lower()
            query_lower = query.lower()
            
            # Exact query word matches
            query_words = query_lower.split()
            title_words = title.split()
            
            matches = sum(1 for word in query_words if len(word) > 2 and word in title)
            if query_words:
                match_ratio = matches / len(query_words)
                score += match_ratio * 0.3
            
            # Description quality
            description = product.get('description', '')
            if len(description) > 100:
                score += 0.1
            
            # Visual elements (images)
            images = product.get('images', [])
            if images and len(images) > 0:
                score += 0.1
            if len(images) > 3:
                score += 0.05
            
            # Price reasonableness (not too extreme)
            try:
                price_str = str(product.get('price', '0')).replace('$', '').replace(',', '')
                price = float(price_str)
                if 20 <= price <= 500:  # Reasonable fashion item price range
                    score += 0.1
            except (ValueError, TypeError):
                pass
            
            # Popularity indicator
            visited = product.get('visited_num', 0)
            if visited > 10:
                score += 0.05
            if visited > 100:
                score += 0.05
            
            return min(score, 1.0)
            
        except Exception:
            return 0.5

    def _calculate_product_harmony_score(self, product: Dict) -> float:
        """Calculate visual harmony score for a product"""
        try:
            score = 0.5
            
            title = product.get('title', '').lower()
            description = product.get('description', '').lower()
            text = f"{title} {description}"
            
            # Color consistency check
            color_keywords = ['red', 'blue', 'green', 'black', 'white', 'pink', 
                             'purple', 'yellow', 'orange', 'brown', 'gray', 'navy']
            found_colors = [color for color in color_keywords if color in text]
            
            if len(found_colors) == 1:
                score += 0.2  # Single color = harmony
            elif len(found_colors) == 2:
                score += 0.1  # Two colors can be harmonious
            elif len(found_colors) > 3:
                score -= 0.1  # Too many colors may lack harmony
            
            # Style consistency
            style_keywords = ['elegant', 'casual', 'formal', 'trendy', 'classic', 'modern']
            found_styles = [style for style in style_keywords if style in text]
            
            if len(found_styles) == 1:
                score += 0.15  # Consistent style
            elif len(found_styles) > 2:
                score -= 0.1  # Conflicting styles
            
            # Quality indicators
            quality_words = ['premium', 'quality', 'designer', 'luxury', 'crafted']
            if any(word in text for word in quality_words):
                score += 0.1
            
            return min(score, 1.0)
            
        except Exception:
            return 0.5

    def _update_stats(self, products_found: int, search_time: float, success: bool):
        """Update agent statistics"""
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
        """Get enhanced agent statistics"""
        return {
            **self.stats,
            "agent": self.name,
            "style": self.style,
            "camel_version": "0.2.7",
            "features": ["RolePlay", "ChatHistoryMemory", "Aesthetic Intelligence", "Color Harmony", "Style Coherence"],
            "memory_enabled": bool(self.memory),
            "roleplay_enabled": bool(self.role_playing),
            "aesthetic_patterns_learned": len(self.aesthetic_patterns),
            "success_rate": (
                self.stats["successful_searches"] / self.stats["total_searches"] * 100
                if self.stats["total_searches"] > 0 else 0
            )
        }

    def reset_stats(self):
        """Reset performance statistics"""
        self.stats = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "total_products_found": 0,
            "avg_search_time": 0.0,
            "aesthetic_insights": 0,
            "style_collaborations": 0,
            "memory_enhanced_searches": 0
        }
        logger.info("VibeBot aesthetic statistics reset")

    async def cleanup(self):
        """Clean up resources"""
        logger.info(f"Cleaning up {self.name} (CAMEL 0.2.7)")
        
        # Clear aesthetic caches
        self.aesthetic_patterns.clear()
        self.style_learning_cache.clear()
        self.color_preferences.clear()
        
        # Reset statistics
        self.reset_stats()
        
        logger.info(f"{self.name} CAMEL 0.2.7 cleanup complete")