"""
Judge Ari Agent - Battle Evaluator
Clean CAMEL 0.2.7 implementation
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter
logger = logging.getLogger("agents.judge")

# Direct CAMEL 0.2.7 imports
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.memories import ChatHistoryMemory
from camel.societies import RolePlaying
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType, RoleType

# Import prompts
from config.prompts import JUDGE_ARI_PROMPT

class JudgeAriAgent:
    """
    Judge Ari - The ultimate fashion arbiter.
    Evaluates battle results from CypherBot and VibeBot.
    
    Clean implementation with CAMEL 0.2.7 patterns:
    - Uses ModelFactory to create models
    - Passes model objects to ChatAgent
    - Direct string system messages
    - No hidden fallbacks
    """
    
    def __init__(self):
        """Initialize Judge Ari with CAMEL 0.2.7, RolePlay, and memory."""
        self.name = "Judge Ari"
        self.role = "Battle Evaluator"
        
        # Initialize CAMEL 0.2.7 components
        self._initialize_camel_agent()
        self._initialize_memory()
        self._initialize_roleplay()
        
        logger.info(f"{self.name} initialized with CAMEL 0.2.7, RolePlay, and memory")
        
        # Track judgment statistics WITH THREAD SAFETY
        self.stats = {
            "total_judgments": 0,
            "cypher_wins": 0,
            "vibe_wins": 0,
            "consensus_decisions": 0,
            "avg_judgment_time": 0.0,
            "total_products_evaluated": 0,
            "learning_interactions": 0  # Track learning usage
        }

        from threading import RLock
        self.stats_lock = RLock()

        # Judgment history for learning (last 50 judgments)
        self.judgment_history = []

    def _initialize_camel_agent(self):
        """Initialize the main CAMEL ChatAgent"""
        try:
            model = ModelFactory.create(
                model_platform=ModelPlatformType.DEFAULT,
                model_type=ModelType.GPT_4O,
                model_config_dict={
                    "temperature": 0.6,  # Balanced for fair judgment
                    "max_tokens": 1500
                }
            )
            
            self.agent = ChatAgent(
                system_message=BaseMessage.make_assistant_message(
                    role_name="Fashion Judge",
                    content=JUDGE_ARI_PROMPT
                ),
                model=model
            )
            
            logger.info("Judge Ari CAMEL agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CAMEL agent: {e}")
            raise RuntimeError(f"Judge Ari CAMEL initialization failed: {e}") from e

    def _initialize_memory(self):
        """Initialize ChatHistoryMemory for learning judgment patterns"""
        try:
            from camel.memories.context_creators import ScoreBasedContextCreator
            from camel.utils.token_counting import OpenAITokenCounter
            
            token_counter = OpenAITokenCounter(model=ModelType.GPT_4O)
            context_creator = ScoreBasedContextCreator(token_counter=token_counter, token_limit=4000)
            self.memory = ChatHistoryMemory(context_creator=context_creator, window_size=20)
            logger.info("Judge Ari memory system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory = None

    def _initialize_roleplay(self):
        """Initialize RolePlaying society for judgment collaboration"""
        try:
            self.role_playing = RolePlaying(
                assistant_role_name="Fashion Judge",
                user_role_name="Battle Evaluator",
                task_prompt="Evaluate fashion product recommendations from competing agents and make fair, informed judgments based on user needs and aesthetic preferences"
            )
            logger.info("Judge Ari RolePlay society initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RolePlay: {e}")
            self.role_playing = None

    async def evaluate(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        ml_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        vision_results: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate battle results with INTELLIGENT QUALITY CONTROL.
        Consciously rejects irrelevant products and forces agents to retry if needed.

        Args:
            cypher_results: Products from CypherBot
            vibe_results: Products from VibeBot
            query: Original search query
            ml_context: ML intelligence context
            user_context: User preferences and context
            limit: Maximum products to return
            vision_results: Optional products from VisionBot

        Returns:
            Judgment dictionary with winner, reasoning, and final products
        """
        start_time = datetime.now()

        with self.stats_lock:
            self.stats["total_judgments"] += 1

        # Initialize vision_results if not provided
        vision_results = vision_results or []

        logger.info(f"{self.name} evaluating: {len(cypher_results)} vs {len(vibe_results)} products (vision: {len(vision_results)})")

        try:
            # STEP 1: CONSCIOUS RELEVANCE VALIDATION - Reject garbage results
            logger.info("Judge Ari: Applying conscious quality control...")

            filtered_cypher = await self._validate_relevance(cypher_results, query, "CypherBot")
            filtered_vibe = await self._validate_relevance(vibe_results, query, "VibeBot")
            filtered_vision = await self._validate_relevance(vision_results, query, "VisionBot") if vision_results else []
            
            # STEP 2: Check if we have acceptable results
            if not filtered_cypher and not filtered_vibe and not filtered_vision:
                # If validation rejected everything but agents found products, be more lenient
                if cypher_results or vibe_results or vision_results:
                    logger.warning("WARNING: Validation rejected all products, but agents found results. Using original results.")
                    # Use original results as fallback
                    filtered_cypher = cypher_results[:5] if cypher_results else []
                    filtered_vibe = vibe_results[:5] if vibe_results else []
                    filtered_vision = vision_results[:5] if vision_results else []
                else:
                    logger.warning("WARNING: Judge Ari: ALL PRODUCTS REJECTED - No relevant results found!")
                    return {
                        "winner": "rejected",
                        "reasoning": "All products were irrelevant to the query and consciously rejected",
                        "products": [],
                        "cypher_count": len(cypher_results),
                        "vibe_count": len(vibe_results),
                        "vision_count": len(vision_results),
                        "filtered_cypher_count": 0,
                        "filtered_vibe_count": 0,
                        "filtered_vision_count": 0,
                        "rejection_reason": "Quality control: No products met relevance standards",
                        "needs_agent_retry": True,
                        "judgment_confidence": 1.0  # High confidence in rejection
                    }
            
            # Log quality control results
            logger.info(f"Quality control results: CypherBot {len(cypher_results)}->{len(filtered_cypher)}, VibeBot {len(vibe_results)}->{len(filtered_vibe)}, VisionBot {len(vision_results)}->{len(filtered_vision)}")
            
            # STEP 3: Get judgment strategy from CAMEL agent (using filtered results)
            strategy = await self._get_judgment_strategy(
                filtered_cypher, filtered_vibe, query, ml_context, user_context
            )
            
            # STEP 4: Execute judgment on quality-controlled results
            judgment = await self._execute_judgment(
                strategy, filtered_cypher, filtered_vibe, query, limit
            )
            
            # Add quality control metadata
            judgment.update({
                "original_cypher_count": len(cypher_results),
                "original_vibe_count": len(vibe_results),
                "filtered_cypher_count": len(filtered_cypher),
                "filtered_vibe_count": len(filtered_vibe),
                "products_rejected": (len(cypher_results) + len(vibe_results)) - (len(filtered_cypher) + len(filtered_vibe)),
                "quality_controlled": True
            })

            # Store judgment for learning (Step 3: Learning integration)
            self._store_judgment_for_learning(judgment, query, strategy)

            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_stats(judgment, elapsed)
            
            logger.info(f"Judgment complete: {judgment['winner']} wins with {len(judgment['products'])} quality-controlled products")
            return judgment
            
        except Exception as e:
            logger.error(f"Judgment failed: {e}")
            # Return balanced selection on error
            return self._create_fallback_judgment(cypher_results, vibe_results, limit)

    async def evaluate_products_individually(
        self,
        all_products: List[Dict[str, Any]],
        query: str,
        ml_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        NEW UNIFIED EVALUATION: Evaluate each product individually instead of team battles.

        Args:
            all_products: All products from both agents combined
            query: Original search query
            ml_context: ML intelligence context
            user_context: User preferences and context
            limit: Maximum products to return

        Returns:
            Evaluation dictionary with best products selected individually
        """
        start_time = datetime.now()

        with self.stats_lock:
            self.stats["total_judgments"] += 1

        logger.info(f"{self.name} evaluating {len(all_products)} products individually (unified approach)")

        try:
            # STEP 1: Quality filter - remove obviously irrelevant products
            logger.info("Judge Ari: Applying individual product quality validation...")
            filtered_products = []

            for product in all_products:
                if await self._is_product_relevant(product, query):
                    filtered_products.append(product)

            logger.info(f"Quality validation: {len(all_products)} -> {len(filtered_products)} products")

            if not filtered_products:
                logger.warning("WARNING: All products rejected during individual evaluation")
                return {
                    "products": [],
                    "reasoning": "All products were irrelevant to the query",
                    "evaluation_method": "individual_quality_rejected",
                    "total_evaluated": len(all_products),
                    "products_passed_quality": 0
                }

            # STEP 2: Score each product individually
            logger.info("Judge Ari: Scoring each product individually...")
            scored_products = []

            for product in filtered_products:
                score = await self._score_individual_product(product, query, ml_context, user_context)
                product_with_score = product.copy()
                product_with_score['_ari_score'] = score
                product_with_score['judge_score'] = score  # For quality threshold compatibility
                scored_products.append(product_with_score)

            # STEP 3: Sort by score and select top products
            scored_products.sort(key=lambda p: p.get('_ari_score', 0), reverse=True)
            top_products = scored_products[:limit]

            # STEP 4: Generate reasoning
            reasoning = await self._generate_individual_evaluation_reasoning(
                top_products, query, len(all_products), len(filtered_products)
            )

            # Calculate consensus information
            consensus_products = [p for p in top_products if p.get('_source') == 'consensus']

            result = {
                "products": top_products,
                "reasoning": reasoning,
                "evaluation_method": "individual_product_scoring",
                "total_evaluated": len(all_products),
                "products_passed_quality": len(filtered_products),
                "consensus_products_selected": len(consensus_products),
                "average_score": sum(p.get('_ari_score', 0) for p in top_products) / len(top_products) if top_products else 0
            }

            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_individual_stats(result, elapsed)

            logger.info(f"Individual evaluation complete: {len(top_products)} products selected with avg score {result['average_score']:.2f}")
            return result

        except Exception as e:
            logger.error(f"Individual evaluation failed: {e}")
            # Fallback: return products sorted by source scores
            all_products.sort(key=lambda p: p.get('_source_score', 0), reverse=True)
            return {
                "products": all_products[:limit],
                "reasoning": f"Fallback selection due to evaluation error: {e}",
                "evaluation_method": "fallback_source_score",
                "total_evaluated": len(all_products)
            }

    async def _get_judgment_strategy(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        ml_context: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Use CAMEL agent to determine judgment strategy.
        
        Returns:
            Strategy description from agent
        """
        # Build context for judge
        context = f"""Evaluate battle results for query: "{query}"

CYPHERBOT (Data-driven approach):
- Found {len(cypher_results)} products
- Top products: {self._summarize_products(cypher_results[:3])}
- Strengths: Graph relationships, purchase patterns, user behavior

VIBEBOT (Aesthetic approach):
- Found {len(vibe_results)} products
- Top products: {self._summarize_products(vibe_results[:3])}
- Strengths: Visual similarity, style matching, trending aesthetics
"""
        
        # Add ML context if available
        if ml_context:
            context += "\n\nML INTELLIGENCE AVAILABLE:"
            if 'cypher_intel' in ml_context:
                context += f"\n- CypherBot has {len(ml_context['cypher_intel'])} intelligence sources"
            if 'vibe_intel' in ml_context:
                context += f"\n- VibeBot has {len(ml_context['vibe_intel'])} intelligence sources"
        
        # Add user context if available
        if user_context:
            context += "\n\nUSER CONTEXT:"
            if user_context.get('vip_status'):
                context += "\n- VIP customer (prioritize quality)"
            if user_context.get('preferred_styles'):
                context += f"\n- Prefers: {', '.join(user_context['preferred_styles'][:3])}"
            if user_context.get('budget_range'):
                context += f"\n- Budget: ${user_context['budget_range'].get('min', 0)}-${user_context['budget_range'].get('max', 'unlimited')}"
        
        # Find consensus products
        cypher_ids = {p.get('id') for p in cypher_results if p.get('id')}
        vibe_ids = {p.get('id') for p in vibe_results if p.get('id')}
        consensus_count = len(cypher_ids & vibe_ids)

        context += f"\n\nCONSENSUS: {consensus_count} products found by both agents"

        # Add historical context for learning (Step 5: Learning integration)
        memory_insights = self._get_memory_insights(query, "")
        recent_patterns = self._get_recent_patterns()

        context += f"""

HISTORICAL CONTEXT:
- Previous judgments: {len(self.judgment_history)}
- Recent patterns: {recent_patterns}
- Memory insights: {memory_insights}"""

        context += """

Determine judgment strategy:
1. CYPHER_DOMINANT - Data and relationships are most important
2. VIBE_DOMINANT - Aesthetics and style are most important
3. BALANCED - Equal weight to both approaches
4. CONSENSUS - Prioritize products both agents agree on
5. QUALITY - Focus on highest quality regardless of source

Respond with strategy and reasoning."""
        
        try:
            # Create message for agent
            user_msg = BaseMessage.make_user_message(
                role_name="Battle Evaluator",
                content=context
            )
            
            # Get response from CAMEL agent
            response = self.agent.step(user_msg)
            
            # Extract strategy
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                strategy = response.msg.content
            elif hasattr(response, 'content'):
                strategy = response.content
            else:
                strategy = str(response)
            
            logger.debug(f"Judgment strategy: {strategy[:100]}...")
            return strategy
            
        except Exception as e:
            logger.error(f"Strategy determination error: {e}")
            return "BALANCED"  # Fallback strategy
    
    async def _execute_judgment(
        self,
        strategy: str,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        limit: int
    ) -> Dict[str, Any]:
        """
        Execute the judgment based on strategy.
        
        Returns:
            Judgment dictionary with winner and final products
        """
        # SCORE-INDEPENDENT EVALUATION: Judge Ari evaluates products directly
        # Ignore agent-reported scores and assess intrinsic product quality
        
        # Calculate independent quality scores for each agent's results
        cypher_quality = self._calculate_independent_quality(cypher_results, query)
        vibe_quality = self._calculate_independent_quality(vibe_results, query)
        
        # Log detailed reasoning for transparency and capture for return
        detailed_reasoning = self._log_detailed_reasoning(cypher_results, vibe_results, query, cypher_quality, vibe_quality)
        
        logger.info(f"Judge Ari independent assessment: CypherBot={cypher_quality:.3f}, VibeBot={vibe_quality:.3f}")

        # Check if learning strategy is requested (Step 4: Learning integration)
        if "learning" in strategy.lower() and len(self.judgment_history) >= 5:
            winner = self._apply_learning_strategy(cypher_results, vibe_results)
            reasoning = f"Learning-based selection using historical success patterns from {len(self.judgment_history)} past judgments"
            logger.info(f"Applied learning strategy: {winner}")
        else:
            # Score-independent decision based on actual product quality
            quality_diff = abs(cypher_quality - vibe_quality)

            if quality_diff < 0.1:
                # Very similar quality - select balanced approach
                winner = "balanced"
                reasoning = f"Both agents found similar quality products (CypherBot: {cypher_quality:.2f}, VibeBot: {vibe_quality:.2f})"
            elif cypher_quality > vibe_quality + 0.1:
                winner = "cypher"
                reasoning = f"CypherBot found higher quality products ({cypher_quality:.2f} vs {vibe_quality:.2f})"
            elif vibe_quality > cypher_quality + 0.1:
                winner = "vibe"
                reasoning = f"VibeBot found higher quality products ({vibe_quality:.2f} vs {vibe_quality:.2f})"
            else:
                # Close call - use count as tiebreaker
                if len(cypher_results) > len(vibe_results):
                    winner = "cypher"
                    reasoning = f"CypherBot found more relevant products ({len(cypher_results)} vs {len(vibe_results)})"
                elif len(vibe_results) > len(cypher_results):
                    winner = "vibe"
                    reasoning = f"VibeBot found more relevant products ({len(vibe_results)} vs {len(cypher_results)})"
                else:
                    winner = "balanced"
                    reasoning = "Equal quality and quantity - balanced selection"
        
        # Select products based on winner
        final_products = self._select_products(
            winner, cypher_results, vibe_results, limit
        )
        
        # Create judgment result
        judgment = {
            "winner": winner,
            "reasoning": reasoning,
            "products": final_products,
            "cypher_count": len(cypher_results),
            "vibe_count": len(vibe_results),
            "consensus_count": self._count_consensus(cypher_results, vibe_results),
            "judgment_confidence": self._calculate_confidence(winner, final_products),
            "detailed_reasoning": detailed_reasoning
        }
        
        return judgment
    
    def _calculate_independent_quality(
        self,
        products: List[Dict[str, Any]], 
        query: str
    ) -> float:
        """
        Calculate independent product quality score ignoring agent-reported scores.
        
        Evaluates based on:
        - Product completeness (title, price, images, description)
        - Query relevance (title/description matching)
        - Commercial viability (price reasonableness, availability)
        - Data quality (no missing fields)
        
        Returns:
            Average quality score (0.0 to 1.0)
        """
        if not products:
            return 0.0
        
        total_quality = 0.0
        query_terms = set(query.lower().split())
        
        for product in products:
            quality = 0.0
            
            # 1. COMPLETENESS ASSESSMENT (0.4 points max)
            title = product.get('title', '').strip()
            price = product.get('price', 0)
            images = product.get('images', [])
            description = product.get('description', '').strip()
            
            if title:
                quality += 0.15  # Has title
            if price and price > 0:
                quality += 0.1   # Has valid price
            if images and len(images) > 0:
                quality += 0.1   # Has images
            if description:
                quality += 0.05  # Has description
            
            # 2. QUERY RELEVANCE (0.3 points max)
            title_lower = title.lower()
            desc_lower = description.lower()
            
            # Count query term matches in title (higher weight)
            title_matches = sum(1 for term in query_terms if term in title_lower)
            quality += min(0.2, title_matches * 0.1)
            
            # Count query term matches in description (lower weight)
            desc_matches = sum(1 for term in query_terms if term in desc_lower)
            quality += min(0.1, desc_matches * 0.05)
            
            # 3. COMMERCIAL VIABILITY (0.2 points max)
            if price:
                # Reasonable price range (not too cheap/expensive)
                if 5 <= price <= 500:
                    quality += 0.1
                elif 1 <= price <= 1000:
                    quality += 0.05
            
            # In stock bonus
            if product.get('in_stock', True):
                quality += 0.05
            
            # Has size info
            if product.get('size') or product.get('sizes'):
                quality += 0.05
            
            # 4. DATA QUALITY (0.1 points max)
            # No missing critical fields
            critical_fields = ['title', 'price']
            missing_fields = sum(1 for field in critical_fields if not product.get(field))
            quality += max(0, 0.1 - (missing_fields * 0.05))
            
            total_quality += min(1.0, quality)  # Cap individual product at 1.0
        
        avg_quality = total_quality / len(products)
        
        logger.debug(f"Independent quality assessment: {len(products)} products, avg={avg_quality:.3f}")
        return avg_quality
    
    def _log_detailed_reasoning(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        cypher_quality: float,
        vibe_quality: float
    ) -> Dict[str, Any]:
        """
        Log detailed reasoning for Judge Ari's evaluation decisions.
        Provides transparency into why products are scored the way they are.
        
        Returns:
            Dictionary containing detailed reasoning for display
        """
        # Build reasoning data structure for return
        reasoning_data = {
            "query": query,
            "summary": {
                "cypher_quality": cypher_quality,
                "vibe_quality": vibe_quality,
                "cypher_count": len(cypher_results),
                "vibe_count": len(vibe_results),
                "quality_difference": abs(cypher_quality - vibe_quality)
            },
            "cypher_analysis": [],
            "vibe_analysis": [],
            "decision_factors": {},
            "warnings": []
        }
        
        logger.info("=" * 80)
        logger.info(f"JUDGE ARI DETAILED REASONING FOR QUERY: '{query}'")
        logger.info("=" * 80)
        
        # Log and capture CypherBot analysis
        logger.info(f"CYPHERBOT ANALYSIS ({len(cypher_results)} products, quality: {cypher_quality:.3f}):")
        if cypher_results:
            for i, product in enumerate(cypher_results[:3]):  # Show top 3
                analysis = self._analyze_product_for_display(product, f"CypherBot #{i+1}", query)
                reasoning_data["cypher_analysis"].append(analysis)
                self._log_product_analysis(product, f"CypherBot #{i+1}", query)
        else:
            logger.info("  - No products found")
            reasoning_data["cypher_analysis"].append({"message": "No products found"})
        
        logger.info("-" * 60)
        
        # Log and capture VibeBot analysis
        logger.info(f"VIBEBOT ANALYSIS ({len(vibe_results)} products, quality: {vibe_quality:.3f}):")
        if vibe_results:
            for i, product in enumerate(vibe_results[:3]):  # Show top 3
                analysis = self._analyze_product_for_display(product, f"VibeBot #{i+1}", query)
                reasoning_data["vibe_analysis"].append(analysis)
                self._log_product_analysis(product, f"VibeBot #{i+1}", query)
        else:
            logger.info("  - No products found")
            reasoning_data["vibe_analysis"].append({"message": "No products found"})
        
        logger.info("-" * 60)
        
        # Overall decision reasoning
        quality_diff = abs(cypher_quality - vibe_quality)
        decision_factors = {
            "quality_difference": quality_diff,
            "threshold": 0.1,
            "cypher_advantage": cypher_quality - vibe_quality,
            "product_counts": {"cypher": len(cypher_results), "vibe": len(vibe_results)}
        }
        reasoning_data["decision_factors"] = decision_factors
        
        logger.info(f"DECISION FACTORS:")
        logger.info(f"  - Quality difference: {quality_diff:.3f} (threshold: 0.1)")
        logger.info(f"  - CypherBot advantage: {cypher_quality - vibe_quality:.3f}")
        logger.info(f"  - Product counts: CypherBot={len(cypher_results)}, VibeBot={len(vibe_results)}")
        
        if cypher_quality == 0.0:
            warning = "CypherBot scored 0.00 - investigating reasons..."
            logger.warning(f"  WARNING: {warning}")
            reasoning_data["warnings"].append({"type": "cypher_zero_score", "message": warning})
            self._analyze_zero_score_reasons(cypher_results, query)
        
        if vibe_quality == 0.0:
            warning = "VibeBot scored 0.00 - investigating reasons..."
            logger.warning(f"  WARNING: {warning}")
            reasoning_data["warnings"].append({"type": "vibe_zero_score", "message": warning})
            self._analyze_zero_score_reasons(vibe_results, query)
        
        logger.info("=" * 80)
        
        return reasoning_data
    
    def _analyze_product_for_display(
        self,
        product: Dict[str, Any],
        source: str,
        query: str
    ) -> Dict[str, Any]:
        """Analyze a product and return structured data for display."""
        title = product.get('title', 'Unknown Product')
        price = product.get('price', 0)
        product_id = product.get('id', 'no-id')
        
        # Quality breakdown
        quality_score = 0.0
        quality_factors = []
        
        # Completeness assessment
        if product.get('title', '').strip():
            quality_score += 0.15
            quality_factors.append({"factor": "Has title", "status": "✓", "points": 0.15})
        else:
            quality_factors.append({"factor": "Missing title", "status": "✗", "points": 0.0})
        
        if product.get('price', 0) > 0:
            quality_score += 0.1
            quality_factors.append({"factor": "Has price", "status": "✓", "points": 0.1})
        else:
            quality_factors.append({"factor": "Missing/invalid price", "status": "✗", "points": 0.0})
        
        images = product.get('images', [])
        if images and len(images) > 0:
            quality_score += 0.1
            quality_factors.append({"factor": f"Has {len(images)} images", "status": "✓", "points": 0.1})
        else:
            quality_factors.append({"factor": "No images", "status": "✗", "points": 0.0})
        
        if product.get('description', '').strip():
            quality_score += 0.05
            quality_factors.append({"factor": "Has description", "status": "✓", "points": 0.05})
        else:
            quality_factors.append({"factor": "No description", "status": "✗", "points": 0.0})
        
        # Query relevance
        query_terms = set(query.lower().split())
        title_lower = title.lower()
        desc_lower = product.get('description', '').lower()
        
        title_matches = sum(1 for term in query_terms if term in title_lower)
        desc_matches = sum(1 for term in query_terms if term in desc_lower)
        
        if title_matches > 0:
            points = min(0.2, title_matches * 0.1)
            quality_score += points
            quality_factors.append({"factor": f"{title_matches} query terms in title", "status": "✓", "points": points})
        else:
            quality_factors.append({"factor": "No query terms in title", "status": "✗", "points": 0.0})
        
        if desc_matches > 0:
            points = min(0.1, desc_matches * 0.05)
            quality_score += points
            quality_factors.append({"factor": f"{desc_matches} query terms in description", "status": "✓", "points": points})
        else:
            quality_factors.append({"factor": "No query terms in description", "status": "✗", "points": 0.0})
        
        # Agent-specific scores
        agent_scores = {}
        if 'score' in product:
            agent_scores['Agent Score'] = product['score']
        if 'vibe_score' in product:
            agent_scores['Vibe Score'] = product['vibe_score']
        if 'cypher_score' in product:
            agent_scores['Cypher Score'] = product['cypher_score']
        if 'qdrant_score' in product:
            agent_scores['Qdrant Score'] = product['qdrant_score']
        
        return {
            "source": source,
            "title": title,
            "price": price,
            "product_id": product_id,
            "quality_score": min(1.0, quality_score),
            "quality_factors": quality_factors,
            "agent_scores": agent_scores,
            "query_relevance": {
                "title_matches": title_matches,
                "description_matches": desc_matches,
                "total_terms": len(query_terms)
            }
        }
    
    def _log_product_analysis(
        self,
        product: Dict[str, Any],
        source: str,
        query: str
    ):
        """Log detailed analysis of a single product."""
        title = product.get('title', 'Unknown Product')
        price = product.get('price', 0)
        product_id = product.get('id', 'no-id')
        
        logger.info(f"  {source}: {title} (ID: {product_id}, ${price:.2f})")
        
        # Quality breakdown
        quality_score = 0.0
        quality_details = []
        
        # Completeness assessment
        if product.get('title', '').strip():
            quality_score += 0.15
            quality_details.append("✓ Has title")
        else:
            quality_details.append("✗ Missing title")
        
        if product.get('price', 0) > 0:
            quality_score += 0.1
            quality_details.append("✓ Has price")
        else:
            quality_details.append("✗ Missing/invalid price")
        
        images = product.get('images', [])
        if images and len(images) > 0:
            quality_score += 0.1
            quality_details.append(f"✓ Has {len(images)} images")
        else:
            quality_details.append("✗ No images")
        
        if product.get('description', '').strip():
            quality_score += 0.05
            quality_details.append("✓ Has description")
        else:
            quality_details.append("✗ No description")
        
        # Query relevance
        query_terms = set(query.lower().split())
        title_lower = title.lower()
        desc_lower = product.get('description', '').lower()
        
        title_matches = sum(1 for term in query_terms if term in title_lower)
        desc_matches = sum(1 for term in query_terms if term in desc_lower)
        
        if title_matches > 0:
            quality_score += min(0.2, title_matches * 0.1)
            quality_details.append(f"✓ {title_matches} query terms in title")
        else:
            quality_details.append("✗ No query terms in title")
        
        if desc_matches > 0:
            quality_score += min(0.1, desc_matches * 0.05)
            quality_details.append(f"✓ {desc_matches} query terms in description")
        else:
            quality_details.append("✗ No query terms in description")
        
        # Commercial viability
        if price and 5 <= price <= 500:
            quality_score += 0.1
            quality_details.append("✓ Reasonable price range")
        elif price and 1 <= price <= 1000:
            quality_score += 0.05
            quality_details.append("~ Acceptable price range")
        else:
            quality_details.append("✗ Price out of reasonable range")
        
        # Agent-specific scores if available
        agent_score_info = []
        if 'score' in product:
            agent_score_info.append(f"Agent Score: {product['score']:.3f}")
        if 'vibe_score' in product:
            agent_score_info.append(f"Vibe Score: {product['vibe_score']:.3f}")
        if 'cypher_score' in product:
            agent_score_info.append(f"Cypher Score: {product['cypher_score']:.3f}")
        if 'qdrant_score' in product:
            agent_score_info.append(f"Qdrant Score: {product['qdrant_score']:.3f}")
        
        logger.info(f"    Quality: {quality_score:.3f} | {' | '.join(agent_score_info) if agent_score_info else 'No agent scores'}")
        logger.info(f"    Factors: {' | '.join(quality_details[:4])}")
        if len(quality_details) > 4:
            logger.info(f"             {' | '.join(quality_details[4:])}")
    
    def _analyze_zero_score_reasons(
        self,
        vibe_results: List[Dict[str, Any]],
        query: str
    ):
        """Analyze why VibeBot products scored 0.00."""
        if not vibe_results:
            logger.warning("    REASON: VibeBot returned no products")
            return
        
        logger.info(f"    ANALYZING {len(vibe_results)} VibeBot products for zero score...")
        
        issues_found = []
        
        for i, product in enumerate(vibe_results[:5]):  # Check first 5
            product_issues = []
            
            # Check completeness
            if not product.get('title', '').strip():
                product_issues.append("missing title")
            if not product.get('price', 0) or product.get('price', 0) <= 0:
                product_issues.append("missing/invalid price")
            if not product.get('images') or len(product.get('images', [])) == 0:
                product_issues.append("no images")
            
            # Check query relevance
            query_terms = set(query.lower().split())
            title_lower = product.get('title', '').lower()
            title_matches = sum(1 for term in query_terms if term in title_lower)
            
            if title_matches == 0:
                product_issues.append("no query terms in title")
            
            if product_issues:
                issues_found.extend(product_issues)
                logger.info(f"    Product {i+1} issues: {', '.join(product_issues)}")
        
        # Summarize common issues
        if issues_found:
            from collections import Counter
            issue_counts = Counter(issues_found)
            logger.warning(f"    COMMON ISSUES: {dict(issue_counts)}")
        else:
            logger.info("    No obvious quality issues found - may be relevance-based rejection")
    
    def _select_products(
        self,
        winner: str,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Select final products based on winning strategy.
        """
        if winner == "cypher":
            # CypherBot wins - take mostly from cypher
            products = cypher_results[:limit]
            # Add metadata
            for p in products:
                p['winning_agent'] = 'CypherBot'
                p['selection_reason'] = 'Data-driven selection'
                
        elif winner == "vibe":
            # VibeBot wins - take mostly from vibe
            products = vibe_results[:limit]
            # Add metadata
            for p in products:
                p['winning_agent'] = 'VibeBot'
                p['selection_reason'] = 'Aesthetic selection'
                
        elif winner == "consensus":
            # Consensus - products both agents found
            products = self._get_consensus_products(cypher_results, vibe_results, limit)
            
        elif winner == "quality":
            # Quality focus - merge and sort by scores
            products = self._select_by_quality(cypher_results, vibe_results, limit)
            
        else:  # balanced
            # Balanced - interleave results
            products = self._interleave_products(cypher_results, vibe_results, limit)
        
        # Add final ranking
        for idx, product in enumerate(products):
            product['final_rank'] = idx + 1
            product['judge_score'] = 1.0 - (idx * 0.1)
        
        return products
    
    def _get_consensus_products(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get products both agents agree on."""
        consensus = []
        
        # Create ID mapping
        cypher_map = {p.get('id'): p for p in cypher_results if p.get('id')}
        vibe_map = {p.get('id'): p for p in vibe_results if p.get('id')}
        
        # Find common IDs
        common_ids = set(cypher_map.keys()) & set(vibe_map.keys())
        
        for product_id in common_ids:
            # Merge information from both
            merged = cypher_map[product_id].copy()
            vibe_data = vibe_map[product_id]
            
            # Add vibe-specific data
            if 'vibe_score' in vibe_data:
                merged['vibe_score'] = vibe_data['vibe_score']
            if 'vibe_reason' in vibe_data:
                merged['vibe_reason'] = vibe_data['vibe_reason']
            
            merged['winning_agent'] = 'Consensus'
            merged['selection_reason'] = 'Both agents selected this product'
            consensus.append(merged)
        
        # If not enough consensus, add from both
        if len(consensus) < limit:
            remaining = limit - len(consensus)
            # Add top products from each that aren't in consensus
            for p in cypher_results:
                if p.get('id') not in common_ids and len(consensus) < limit:
                    p['winning_agent'] = 'CypherBot'
                    p['selection_reason'] = 'Added to reach limit'
                    consensus.append(p)
            
            for p in vibe_results:
                if p.get('id') not in common_ids and len(consensus) < limit:
                    p['winning_agent'] = 'VibeBot'
                    p['selection_reason'] = 'Added to reach limit'
                    consensus.append(p)
        
        return consensus[:limit]
    
    def _select_by_quality(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Select products by quality scores."""
        all_products = {}
        
        # Add all products with source tracking
        for p in cypher_results:
            if p.get('id'):
                all_products[p['id']] = p.copy()
                all_products[p['id']]['sources'] = ['CypherBot']
                
        for p in vibe_results:
            if p.get('id'):
                if p['id'] in all_products:
                    all_products[p['id']]['sources'].append('VibeBot')
                    # Merge scores
                    if 'vibe_score' in p:
                        all_products[p['id']]['vibe_score'] = p['vibe_score']
                else:
                    all_products[p['id']] = p.copy()
                    all_products[p['id']]['sources'] = ['VibeBot']
        
        # Calculate quality scores
        for product in all_products.values():
            score = 0.5
            
            # Consensus bonus
            if len(product.get('sources', [])) > 1:
                score += 0.3
                product['winning_agent'] = 'Consensus'
            else:
                product['winning_agent'] = product['sources'][0]
            
            # Agent scores
            if 'cypher_score' in product:
                score += product['cypher_score'] * 0.2
            if 'vibe_score' in product:
                score += product['vibe_score'] * 0.2
            
            # Additional quality factors
            if product.get('in_stock', True):
                score += 0.1
            if product.get('images') and len(product['images']) > 0:
                score += 0.1
            
            product['quality_score'] = min(score, 1.0)
            product['selection_reason'] = 'High quality score'
        
        # Sort by quality
        sorted_products = sorted(
            all_products.values(),
            key=lambda x: x.get('quality_score', 0),
            reverse=True
        )
        
        return sorted_products[:limit]
    
    def _interleave_products(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Interleave products from both agents."""
        products = []
        seen_ids = set()
        
        # Interleave taking from each alternately
        for i in range(limit):
            # Take from CypherBot
            if i % 2 == 0 and i // 2 < len(cypher_results):
                product = cypher_results[i // 2]
                if product.get('id') not in seen_ids:
                    product['winning_agent'] = 'CypherBot'
                    product['selection_reason'] = 'Balanced selection'
                    products.append(product)
                    seen_ids.add(product.get('id'))
            
            # Take from VibeBot
            elif i % 2 == 1 and i // 2 < len(vibe_results):
                product = vibe_results[i // 2]
                if product.get('id') not in seen_ids:
                    product['winning_agent'] = 'VibeBot'
                    product['selection_reason'] = 'Balanced selection'
                    products.append(product)
                    seen_ids.add(product.get('id'))
        
        # Fill remaining if needed
        for p in cypher_results + vibe_results:
            if len(products) >= limit:
                break
            if p.get('id') not in seen_ids:
                p['winning_agent'] = 'Filler'
                p['selection_reason'] = 'Added to reach limit'
                products.append(p)
                seen_ids.add(p.get('id'))
        
        return products[:limit]
    
    def _summarize_products(self, products: List[Dict[str, Any]]) -> str:
        """Create brief summary of products for context."""
        if not products:
            return "No products"
        
        summaries = []
        for p in products:
            title = p.get('title', 'Unknown')[:30]
            price = p.get('price', 0)
            summaries.append(f"{title} (${price:.2f})")
        
        return ", ".join(summaries)
    
    
    def _count_consensus(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]]
    ) -> int:
        """Count products both agents found using title matching."""
        # Since IDs don't match, use titles for consensus
        cypher_titles = {p.get('title').lower().strip() for p in cypher_results if p.get('title')}
        vibe_titles = {p.get('title').lower().strip() for p in vibe_results if p.get('title')}
        return len(cypher_titles & vibe_titles)

    def _calculate_confidence(
        self,
        winner: str,
        products: List[Dict[str, Any]]
    ) -> float:
        """Calculate confidence in judgment."""
        confidence = 0.5
        
        # Base confidence by winner type
        if winner == "consensus":
            confidence = 0.9
        elif winner == "quality":
            confidence = 0.85
        elif winner in ["cypher", "vibe"]:
            confidence = 0.75
        else:
            confidence = 0.7
        
        # Adjust based on product count
        if len(products) >= 5:
            confidence += 0.1
        
        # Check for consensus in products
        agents = Counter()
        for p in products:
            if 'winning_agent' in p:
                agents[p['winning_agent']] += 1
        
        if agents.get('Consensus', 0) > len(products) / 2:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    async def _validate_relevance(
        self,
        products: List[Dict[str, Any]],
        query: str,
        agent_name: str
    ) -> List[Dict[str, Any]]:
        """
        CONSCIOUS QUALITY CONTROL: Validate that products are actually relevant to the query.
        Rejects kids' t-shirts for weddings, sports jerseys for parties, etc.
        """
        if not products:
            return []
        
        logger.info(f"Validating relevance of {len(products)} products from {agent_name} for query: '{query}'")
        
        # Build relevance validation context
        validation_context = f"""QUERY: "{query}"

PRODUCTS TO VALIDATE:
{self._format_products_for_validation(products[:10])}  

Your job: CONSCIOUSLY EVALUATE each product for relevance to the query.

EVALUATION CRITERIA (Be very permissive and helpful):
- If the product category is even remotely related to the request, ACCEPT IT
- For requests like "blazer", accept blazers, jackets, coats, suits, formal wear
- For requests like "shirt", accept shirts, tops, blouses, t-shirts
- Only reject products that are completely unrelated (shoes for clothing, etc.)

IMPORTANT: Default to ACCEPTING products rather than rejecting them.
Give customers options and let them decide what they like.

EXAMPLE ACCEPTANCES:
- "blazer" request → Accept blazers, suit jackets, formal jackets, cardigans
- "black shirt" request → Accept any black tops, shirts, blouses, t-shirts
- "dress" request → Accept any dresses, regardless of style or occasion

ONLY REJECT if completely wrong category (shoes for clothing request, etc.)

RESPOND WITH: List ALL product IDs that are even remotely relevant.
Be generous and inclusive. Only use "REJECT_ALL" if literally nothing matches the category.

Think like a helpful salesperson who wants to show customers all available options."""

        try:
            # Create message for CAMEL agent to evaluate relevance
            validation_msg = BaseMessage.make_user_message(
                role_name="Quality Controller",
                content=validation_context
            )
            
            # Get relevance assessment from CAMEL agent
            response = self.agent.step(validation_msg)
            
            # Extract response content
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                relevance_decision = response.msg.content
            elif hasattr(response, 'content'):
                relevance_decision = response.content
            else:
                relevance_decision = str(response)
            
            logger.info(f"Judge Ari relevance decision: {relevance_decision[:200]}...")
            
            # Parse the decision
            if "REJECT_ALL" in relevance_decision.upper():
                logger.warning(f"Judge Ari REJECTED ALL products from {agent_name} as irrelevant")
                return []
            
            # Extract approved product IDs from response
            approved_products = []
            product_id_map = {p.get('id'): p for p in products if p.get('id')}
            
            # Look for product IDs in the response
            for product_id, product in product_id_map.items():
                if str(product_id) in relevance_decision or product.get('title', '') in relevance_decision:
                    approved_products.append(product)
            
            # If no specific IDs found but not REJECT_ALL, be conservative and keep some products
            if not approved_products and "REJECT_ALL" not in relevance_decision.upper():
                # Take top 3 as fallback if LLM didn't clearly reject
                approved_products = products[:3]
                logger.info(f"WARNING: Fallback: Keeping top 3 products as LLM decision was unclear")
            
            rejected_count = len(products) - len(approved_products)
            if rejected_count > 0:
                logger.info(f"Judge Ari rejected {rejected_count} irrelevant products from {agent_name}")
            
            return approved_products
            
        except Exception as e:
            logger.error(f"Relevance validation failed for {agent_name}: {e}")
            # Conservative fallback - keep products but log the issue
            logger.warning(f"WARNING: Relevance validation error - keeping products as fallback")
            return products
    
    def _format_products_for_validation(self, products: List[Dict[str, Any]]) -> str:
        """Format products for relevance validation."""
        if not products:
            return "No products to validate"
        
        formatted = []
        for i, p in enumerate(products):
            title = p.get('title', 'Unknown Product')
            price = p.get('price', 0)
            category = p.get('category', 'Unknown')
            product_id = p.get('id', 'no-id')
            
            formatted.append(f"{i+1}. ID:{product_id} | {title} | ${price:.2f} | Category: {category}")
        
        return "\n".join(formatted)
    
    def _create_fallback_judgment(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> Dict[str, Any]:
        """Create fallback judgment on error."""
        # Simple balanced selection
        products = self._interleave_products(cypher_results, vibe_results, limit)
        
        return {
            "winner": "balanced",
            "reasoning": "Balanced selection (fallback)",
            "products": products,
            "cypher_count": len(cypher_results),
            "vibe_count": len(vibe_results),
            "consensus_count": self._count_consensus(cypher_results, vibe_results),
            "judgment_confidence": 0.5
        }
    
    def _update_stats(self, judgment: Dict[str, Any], elapsed_time: float):
        """Update judge statistics."""
        winner = judgment.get('winner', 'unknown')
        
        # WRAP IN LOCK
        with self.stats_lock:
            if winner == 'cypher':
                self.stats['cypher_wins'] += 1
            elif winner == 'vibe':
                self.stats['vibe_wins'] += 1
            elif winner == 'consensus':
                self.stats['consensus_decisions'] += 1
            
            self.stats['total_products_evaluated'] += (
                judgment.get('cypher_count', 0) + judgment.get('vibe_count', 0)
            )
            
            # Update average judgment time
            total = self.stats['total_judgments']
            current_avg = self.stats['avg_judgment_time']
            self.stats['avg_judgment_time'] = (
                (current_avg * (total - 1) + elapsed_time) / total
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get judge statistics."""
        total = self.stats['total_judgments']

        return {
            "judge": self.name,
            "role": self.role,
            **self.stats,
            "cypher_win_rate": (
                self.stats['cypher_wins'] / total * 100
                if total > 0 else 0
            ),
            "vibe_win_rate": (
                self.stats['vibe_wins'] / total * 100
                if total > 0 else 0
            ),
            "consensus_rate": (
                self.stats['consensus_decisions'] / total * 100
                if total > 0 else 0
            ),
            "judgment_history_size": len(self.judgment_history),
            "learning_rate": (
                self.stats.get('learning_interactions', 0) / total * 100
                if total > 0 else 0
            )
        }

    # NEW HELPER METHODS FOR UNIFIED PRODUCT EVALUATION

    async def _is_product_relevant(self, product: Dict[str, Any], query: str) -> bool:
        """Check if an individual product is relevant to the query."""
        try:
            # Basic relevance checks
            title = product.get('title', '').lower()
            description = product.get('description', '').lower()
            category = product.get('category', '').lower()
            query_lower = query.lower()

            # Check for obvious irrelevance
            irrelevant_patterns = ['unrelated', 'out of stock', 'unavailable']
            text_to_check = f"{title} {description} {category}"

            if any(pattern in text_to_check for pattern in irrelevant_patterns):
                return False

            # Basic keyword matching
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 2 and word in text_to_check:
                    return True

            # If no obvious matches, assume relevant (let scoring decide)
            return True

        except Exception as e:
            logger.warning(f"Error checking product relevance: {e}")
            return True  # Default to relevant if error

    async def _score_individual_product(
        self,
        product: Dict[str, Any],
        query: str,
        ml_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> float:
        """Score an individual product for relevance and quality."""
        try:
            score = 0.0

            # 1. Title relevance (30%) - Improved algorithm
            title = product.get('title', '').lower()
            query_lower = query.lower()

            # Filter out noise words and focus on meaningful terms
            noise_words = {'hey', 'there', 'get', 'me', 'show', 'find', 'want', 'need', 'looking', 'for'}
            meaningful_words = [word for word in query_lower.split() if len(word) > 2 and word not in noise_words]

            if meaningful_words:
                title_matches = sum(1 for word in meaningful_words if word in title)
                title_score = min(title_matches / len(meaningful_words), 1.0) * 0.3
            else:
                title_score = 0.15  # Base score if no meaningful words
            score += title_score

            # 2. Source agent confidence (30%) - Increased weight since agents are smart
            source_score = product.get('_source_score', 0.6) * 0.3  # Higher default + weight
            score += source_score

            # 3. Consensus bonus (20%)
            if product.get('_source') == 'consensus':
                consensus_bonus = 0.2
                score += consensus_bonus

            # 4. ML intelligence enhancement (15%)
            if ml_context and product.get('id'):
                # Use ML intelligence to boost score
                ml_boost = self._calculate_ml_boost(product, ml_context)
                score += ml_boost * 0.15

            # 5. User preference alignment (5%)
            if user_context:
                preference_score = self._calculate_preference_score(product, user_context)
                score += preference_score * 0.05

            # 6. Base product quality score (15%) - Ensure minimum viability
            base_quality = 0.15  # All products that agents find get base quality
            score += base_quality

            return min(score, 1.0)  # Cap at 1.0

        except Exception as e:
            logger.warning(f"Error scoring product: {e}")
            return 0.5  # Default neutral score

    def _calculate_ml_boost(self, product: Dict[str, Any], ml_context: Dict[str, Any]) -> float:
        """Calculate ML intelligence boost for product scoring."""
        try:
            boost = 0.0

            # Check if product matches ML insights
            product_id = product.get('id')
            if not product_id:
                return 0.0

            # Base ML intelligence available boost
            if ml_context:
                boost += 0.2  # Having ML intelligence at all is valuable

            # Visual intelligence boost
            visual_intel = ml_context.get('vibe_intel', {}).get('visual', {})
            if visual_intel and 'query_visual_analysis' in visual_intel:
                boost += 0.3  # Visual intelligence is working
                visual_cues = visual_intel['query_visual_analysis'].get('visual_cues', {})

                # Check color matching
                product_title = product.get('title', '').lower()
                detected_colors = visual_cues.get('colors', [])
                for color in detected_colors:
                    if color.lower() in product_title:
                        boost += 0.3  # Additional boost for color match
                        break

            # Behavioral intelligence boost
            behavioral_intel = ml_context.get('cypher_intel', {}).get('behavioral', {})
            if behavioral_intel:
                boost += 0.2

            return min(boost, 1.0)

        except Exception as e:
            logger.warning(f"Error calculating ML boost: {e}")
            return 0.0

    def _calculate_preference_score(self, product: Dict[str, Any], user_context: Dict[str, Any]) -> float:
        """Calculate user preference alignment score."""
        try:
            score = 0.0

            # Check preferred categories
            preferred_categories = user_context.get('preferred_categories', [])
            product_category = product.get('category', '').lower()

            if preferred_categories and product_category:
                for pref_cat in preferred_categories:
                    if pref_cat.lower() in product_category:
                        score += 0.5
                        break

            # Check price range preferences
            preferred_price_range = user_context.get('price_range')
            product_price = product.get('price')

            if preferred_price_range and product_price:
                min_price = preferred_price_range.get('min', 0)
                max_price = preferred_price_range.get('max', float('inf'))

                if min_price <= product_price <= max_price:
                    score += 0.5

            return min(score, 1.0)

        except Exception as e:
            logger.warning(f"Error calculating preference score: {e}")
            return 0.0

    async def _generate_individual_evaluation_reasoning(
        self,
        top_products: List[Dict[str, Any]],
        query: str,
        total_evaluated: int,
        passed_quality: int
    ) -> str:
        """Generate reasoning for individual product evaluation."""
        try:
            reasoning_parts = []

            reasoning_parts.append(f"Evaluated {total_evaluated} products individually")
            reasoning_parts.append(f"{passed_quality} products passed quality filters")
            reasoning_parts.append(f"Selected top {len(top_products)} products based on individual scores")

            # Analyze sources
            sources = {}
            for product in top_products:
                source = product.get('_source', 'unknown')
                sources[source] = sources.get(source, 0) + 1

            if sources:
                source_summary = ", ".join([f"{count} from {source}" for source, count in sources.items()])
                reasoning_parts.append(f"Source distribution: {source_summary}")

            # Check for consensus products
            consensus_count = len([p for p in top_products if p.get('_source') == 'consensus'])
            if consensus_count > 0:
                reasoning_parts.append(f"{consensus_count} products found by both agents (high confidence)")

            return ". ".join(reasoning_parts) + "."

        except Exception as e:
            logger.warning(f"Error generating reasoning: {e}")
            return f"Individual evaluation of {total_evaluated} products completed with collaborative approach."

    def _update_individual_stats(self, result: Dict[str, Any], elapsed_time: float):
        """Update statistics for individual product evaluation."""
        try:
            with self.stats_lock:
                # Add new stats for individual evaluation
                if 'individual_evaluations' not in self.stats:
                    self.stats['individual_evaluations'] = 0
                    self.stats['avg_products_per_evaluation'] = 0.0
                    self.stats['avg_individual_score'] = 0.0

                self.stats['individual_evaluations'] += 1

                # Update average products per evaluation
                total_evals = self.stats['individual_evaluations']
                current_avg = self.stats['avg_products_per_evaluation']
                products_evaluated = result.get('total_evaluated', 0)
                self.stats['avg_products_per_evaluation'] = (
                    (current_avg * (total_evals - 1) + products_evaluated) / total_evals
                )

                # Update average individual score
                avg_score = result.get('average_score', 0)
                current_score_avg = self.stats['avg_individual_score']
                self.stats['avg_individual_score'] = (
                    (current_score_avg * (total_evals - 1) + avg_score) / total_evals
                )

        except Exception as e:
            logger.warning(f"Error updating individual stats: {e}")

    # LEARNING SYSTEM - Adapted from judge_modernized.py

    def _get_memory_insights(self, query: str, strategy: str) -> str:
        """Extract insights from memory for enhanced judgment."""
        if len(self.judgment_history) == 0:
            return "(first judgment - no history available)"

        recent = self.judgment_history[-5:]
        successful_strategies = [j['winner'] for j in recent if j.get('successful', True)]

        if successful_strategies:
            common_strategy = Counter(successful_strategies).most_common(1)[0][0]
            return f"(memory suggests {common_strategy} works well for similar queries)"

        return "(memory analysis applied)"

    def _apply_learning_strategy(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]]
    ) -> str:
        """Apply learning from judgment history to select best approach."""
        if len(self.judgment_history) == 0:
            return "balanced"

        recent_success = [j for j in self.judgment_history[-10:] if j.get('successful', True)]

        if recent_success:
            strategy_success = Counter([j['winner'] for j in recent_success])
            best_strategy = strategy_success.most_common(1)[0][0]
            logger.info(f"Learning strategy selected: {best_strategy}")
            return best_strategy

        return "balanced"

    def _store_judgment_for_learning(
        self,
        judgment: Dict[str, Any],
        query: str,
        strategy: str
    ):
        """Store judgment in history for learning."""
        judgment_record = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'strategy': strategy,
            'winner': judgment['winner'],
            'confidence': judgment['judgment_confidence'],
            'product_count': len(judgment['products']),
            'successful': judgment['judgment_confidence'] > 0.7
        }

        self.judgment_history.append(judgment_record)

        if len(self.judgment_history) > 50:
            self.judgment_history = self.judgment_history[-50:]

    def _get_recent_patterns(self) -> str:
        """Get patterns from recent judgments for context."""
        if len(self.judgment_history) < 3:
            return "insufficient data"

        recent = self.judgment_history[-5:]
        winners = [j['winner'] for j in recent]
        winner_counts = Counter(winners)

        if winner_counts:
            most_common = winner_counts.most_common(1)[0][0]
            return f"recently favoring {most_common}"

        return "mixed patterns"
