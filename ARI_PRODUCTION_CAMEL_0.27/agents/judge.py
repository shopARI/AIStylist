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
            "total_products_evaluated": 0
        }
        
        from threading import RLock
        self.stats_lock = RLock()

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
        limit: int = 5
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
            
        Returns:
            Judgment dictionary with winner, reasoning, and final products
        """
        start_time = datetime.now()

        with self.stats_lock:
            self.stats["total_judgments"] += 1
       
        logger.info(f"{self.name} evaluating: {len(cypher_results)} vs {len(vibe_results)} products")
        
        try:
            # STEP 1: CONSCIOUS RELEVANCE VALIDATION - Reject garbage results
            logger.info("🧠 Judge Ari: Applying conscious quality control...")
            
            filtered_cypher = await self._validate_relevance(cypher_results, query, "CypherBot")
            filtered_vibe = await self._validate_relevance(vibe_results, query, "VibeBot")
            
            # STEP 2: Check if we have acceptable results
            if not filtered_cypher and not filtered_vibe:
                logger.warning("⚠️  Judge Ari: ALL PRODUCTS REJECTED - No relevant results found!")
                return {
                    "winner": "rejected",
                    "reasoning": "All products were irrelevant to the query and consciously rejected",
                    "products": [],
                    "cypher_count": len(cypher_results),
                    "vibe_count": len(vibe_results),
                    "filtered_cypher_count": 0,
                    "filtered_vibe_count": 0,
                    "rejection_reason": "Quality control: No products met relevance standards",
                    "needs_agent_retry": True,
                    "judgment_confidence": 1.0  # High confidence in rejection
                }
            
            # Log quality control results
            logger.info(f"✅ Quality control results: CypherBot {len(cypher_results)}→{len(filtered_cypher)}, VibeBot {len(vibe_results)}→{len(filtered_vibe)}")
            
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
            
            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_stats(judgment, elapsed)
            
            logger.info(f"Judgment complete: {judgment['winner']} wins with {len(judgment['products'])} quality-controlled products")
            return judgment
            
        except Exception as e:
            logger.error(f"Judgment failed: {e}")
            # Return balanced selection on error
            return self._create_fallback_judgment(cypher_results, vibe_results, limit)
    
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
        
        logger.info(f"🧠 Judge Ari independent assessment: CypherBot={cypher_quality:.3f}, VibeBot={vibe_quality:.3f}")
        
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
            reasoning = f"VibeBot found higher quality products ({vibe_quality:.2f} vs {cypher_quality:.2f})"
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
            "judgment_confidence": self._calculate_confidence(winner, final_products)
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
        
        logger.info(f"🔍 Validating relevance of {len(products)} products from {agent_name} for query: '{query}'")
        
        # Build relevance validation context
        validation_context = f"""QUERY: "{query}"

PRODUCTS TO VALIDATE:
{self._format_products_for_validation(products[:10])}  

Your job: CONSCIOUSLY EVALUATE each product for relevance to the query.

CRITICAL EVALUATION CRITERIA:
- Does this product make sense for the stated occasion/need?
- Would a real fashion stylist recommend this item for this specific request?
- Is the product category appropriate? (No kids' items for adult formal wear)
- Does the style/formality level match the occasion?

EXAMPLE REJECTIONS:
- Kids' t-shirts for wedding guest attire → REJECT
- Sports jerseys for "impressing at a party" → REJECT  
- Casual sneakers for formal interviews → REJECT
- Formal gowns for casual coffee dates → REJECT

RESPOND WITH: List only the product IDs that are TRULY RELEVANT and appropriate.
If NO products are relevant, respond with: "REJECT_ALL"

Think like a conscious fashion expert who would never embarrass a client with inappropriate recommendations."""

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
            
            logger.info(f"🧠 Judge Ari relevance decision: {relevance_decision[:200]}...")
            
            # Parse the decision
            if "REJECT_ALL" in relevance_decision.upper():
                logger.warning(f"❌ Judge Ari REJECTED ALL products from {agent_name} as irrelevant")
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
                logger.info(f"⚠️  Fallback: Keeping top 3 products as LLM decision was unclear")
            
            rejected_count = len(products) - len(approved_products)
            if rejected_count > 0:
                logger.info(f"🚫 Judge Ari rejected {rejected_count} irrelevant products from {agent_name}")
            
            return approved_products
            
        except Exception as e:
            logger.error(f"Relevance validation failed for {agent_name}: {e}")
            # Conservative fallback - keep products but log the issue
            logger.warning(f"⚠️  Relevance validation error - keeping products as fallback")
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
            )
        }
