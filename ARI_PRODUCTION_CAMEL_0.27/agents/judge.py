"""
Judge Ari Agent - Battle Evaluator
Clean CAMEL 0.2.70 implementation
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter
from threading import RLock 
logger = logging.getLogger("agents.judge")

# Import from our new CAMEL 0.2.70 module
from lib.camel.v070 import (
    create_battle_agent,
    create_user_message,
    BaseMessage,
    CAMEL_AVAILABLE
)

# Import prompts
from config.prompts import JUDGE_ARI_PROMPT

class JudgeAriAgent:
    """
    Judge Ari - The ultimate fashion arbiter.
    Evaluates battle results from CypherBot and VibeBot.
    
    Clean implementation with CAMEL 0.2.70 patterns:
    - Uses ModelFactory to create models
    - Passes model objects to ChatAgent
    - Direct string system messages
    - No hidden fallbacks
    """
    
    def __init__(self):
        """Initialize Judge Ari."""
        self.name = "Judge Ari"
        self.role = "Battle Evaluator"
        
        # Initialize CAMEL agent using 0.2.70 pattern
        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL 0.2.70+ is required for Judge Ari")
        
        try:
            self.agent = create_battle_agent(
                name=self.name,
                system_message=JUDGE_ARI_PROMPT
            )
            logger.info(f"{self.name} initialized with CAMEL 0.2.70")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}")
            raise RuntimeError(f"Judge Ari initialization failed: {e}") from e
        
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
        Evaluate battle results and select winners.
        
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
            # Get judgment strategy from CAMEL agent
            strategy = await self._get_judgment_strategy(
                cypher_results, vibe_results, query, ml_context, user_context
            )
            
            # Execute judgment
            judgment = await self._execute_judgment(
                strategy, cypher_results, vibe_results, query, limit
            )
            
            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_stats(judgment, elapsed)
            
            logger.info(f"Judgment complete: {judgment['winner']} wins")
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
            user_msg = create_user_message(context)
            
            # Get response from CAMEL agent
            response = self.agent.step(user_msg)
            
            # Extract strategy
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                strategy = response.msg.content
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
        strategy_lower = strategy.lower()
        
        # Determine winner based on strategy
        if "cypher" in strategy_lower or "data" in strategy_lower:
            winner = "cypher"
            reasoning = "Data-driven approach is most suitable for this query"
        elif "vibe" in strategy_lower or "aesthetic" in strategy_lower:
            winner = "vibe"
            reasoning = "Aesthetic approach is most suitable for this query"
        elif "consensus" in strategy_lower:
            winner = "consensus"
            reasoning = "Both agents agree on the best products"
        elif "quality" in strategy_lower:
            winner = "quality"
            reasoning = "Selecting highest quality products from both agents"
        else:
            winner = "balanced"
            reasoning = "Balanced selection from both agents"
        
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
    
    # def _count_consensus(
    #     self,
    #     cypher_results: List[Dict[str, Any]],
    #     vibe_results: List[Dict[str, Any]]
    # ) -> int:
    #     """Count products both agents found."""
    #     cypher_ids = {p.get('id') for p in cypher_results if p.get('id')}
    #     vibe_ids = {p.get('id') for p in vibe_results if p.get('id')}
    #     return len(cypher_ids & vibe_ids)
    
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
