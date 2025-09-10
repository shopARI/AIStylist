"""
Judge Ari Agent - Battle Evaluator
Modernized CAMEL 0.2.7 implementation with RolePlay and Memory
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import Counter
from threading import RLock

logger = logging.getLogger("agents.judge")

# CAMEL 0.2.7 imports - correct patterns
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.messages import BaseMessage
from camel.types import ModelType, RoleType
from camel.memories import ChatHistoryMemory
from camel.societies import RolePlaying

# Import prompts
from config.prompts import JUDGE_ARI_PROMPT

class JudgeAriAgent:
    """
    Judge Ari - The ultimate fashion arbiter.
    Evaluates battle results from CypherBot and VibeBot.
    
    Modern CAMEL 0.2.7 implementation with:
    - RolePlay society for multi-agent collaboration
    - ChatHistoryMemory for learning from judgments
    - ModelFactory for proper model initialization
    - Thread-safe statistics tracking
    """
    
    def __init__(self):
        """Initialize Judge Ari with CAMEL 0.2.7 RolePlay and Memory."""
        self.name = "Judge Ari"
        self.role = "Battle Evaluator"
        
        try:
            # Create model using CAMEL 0.2.7 ModelFactory
            self.model = ModelFactory.create(
                model_platform=ModelType.OPENAI,
                model_type="gpt-4o-mini",
                model_config_dict={
                    "temperature": 0.7, 
                    "max_tokens": 2000,
                    "top_p": 0.9
                }
            )
            
            # Initialize memory for learning from judgments
            self.memory = ChatHistoryMemory(
                message_window_size=20,  # Remember last 20 interactions
            )
            
            # Create CAMEL ChatAgent with memory and advanced features
            self.agent = ChatAgent(
                system_message=JUDGE_ARI_PROMPT,
                model=self.model,
                memory=self.memory,
                message_window_size=20,
                token_limit=4000,
                output_language="English"
            )
            
            # Setup RolePlay society for multi-agent collaboration
            self.role_playing = RolePlaying(
                assistant_role_name="Fashion Judge",
                user_role_name="Battle Evaluator",
                assistant_agent=self.agent,
                user_agent=self.agent,  # Self-evaluation capability
                task_prompt="Evaluate fashion agent battle results fairly and comprehensively, learning from past decisions"
            )
            
            logger.info(f"{self.name} initialized with CAMEL 0.2.7, memory, and RolePlay")
            
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
            "total_products_evaluated": 0,
            "learning_interactions": 0
        }
        
        self.stats_lock = RLock()
        
        # Judgment history for learning
        self.judgment_history = []

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
        Evaluate battle results and select winners using CAMEL RolePlay.
        
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
            # Get judgment strategy using RolePlay
            strategy = await self._get_roleplay_strategy(
                cypher_results, vibe_results, query, ml_context, user_context
            )
            
            # Execute judgment with memory-enhanced decision making
            judgment = await self._execute_memory_enhanced_judgment(
                strategy, cypher_results, vibe_results, query, limit
            )
            
            # Store judgment for learning
            self._store_judgment_for_learning(judgment, query, strategy)
            
            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds()
            self._update_stats(judgment, elapsed)
            
            logger.info(f"Judgment complete: {judgment['winner']} wins")
            return judgment
            
        except Exception as e:
            logger.error(f"Judgment failed: {e}")
            # Return balanced selection on error
            return self._create_fallback_judgment(cypher_results, vibe_results, limit)
    
    async def _get_roleplay_strategy(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        ml_context: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Use CAMEL RolePlay to determine judgment strategy with memory context.
        
        Returns:
            Strategy description from RolePlay agent
        """
        # Build comprehensive context with memory insights
        context = f"""FASHION BATTLE EVALUATION for query: "{query}"

CYPHERBOT (Data-driven approach):
- Found {len(cypher_results)} products
- Top products: {self._summarize_products(cypher_results[:3])}
- Strengths: Graph relationships, purchase patterns, user behavior

VIBEBOT (Aesthetic approach):
- Found {len(vibe_results)} products  
- Top products: {self._summarize_products(vibe_results[:3])}
- Strengths: Visual similarity, style matching, trending aesthetics

HISTORICAL CONTEXT:
- Previous judgments: {len(self.judgment_history)}
- Recent patterns: {self._get_recent_patterns()}
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

JUDGMENT STRATEGIES:
1. CYPHER_DOMINANT - Data and relationships are most important
2. VIBE_DOMINANT - Aesthetics and style are most important  
3. BALANCED - Equal weight to both approaches
4. CONSENSUS - Prioritize products both agents agree on
5. QUALITY - Focus on highest quality regardless of source
6. LEARNING - Apply insights from previous successful judgments

Determine the best strategy based on query type, agent performance, and historical success patterns."""
        
        try:
            # Use RolePlay for strategic decision making
            user_msg = BaseMessage(
                role_name="Battle Evaluator",
                role_type=RoleType.USER,
                content=context
            )
            
            # Get response from CAMEL agent with RolePlay
            assistant_msg, user_msg = self.role_playing.step(user_msg)
            
            # Extract strategy from assistant response
            if hasattr(assistant_msg, 'content'):
                strategy = assistant_msg.content
            else:
                strategy = str(assistant_msg)
            
            with self.stats_lock:
                self.stats["learning_interactions"] += 1
            
            logger.debug(f"RolePlay strategy: {strategy[:100]}...")
            return strategy
            
        except Exception as e:
            logger.error(f"RolePlay strategy determination error: {e}")
            return "BALANCED"  # Fallback strategy
    
    async def _execute_memory_enhanced_judgment(
        self,
        strategy: str,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        limit: int
    ) -> Dict[str, Any]:
        """
        Execute judgment enhanced by memory and learning from past decisions.
        
        Returns:
            Judgment dictionary with winner and final products
        """
        strategy_lower = strategy.lower()
        
        # Apply learning from memory if available
        memory_insights = self._get_memory_insights(query, strategy)
        
        # Determine winner based on strategy + memory
        if "cypher" in strategy_lower or "data" in strategy_lower:
            winner = "cypher"
            reasoning = f"Data-driven approach selected {memory_insights}"
        elif "vibe" in strategy_lower or "aesthetic" in strategy_lower:
            winner = "vibe"
            reasoning = f"Aesthetic approach selected {memory_insights}"
        elif "consensus" in strategy_lower:
            winner = "consensus"
            reasoning = f"Both agents consensus {memory_insights}"
        elif "quality" in strategy_lower:
            winner = "quality"
            reasoning = f"Highest quality selection {memory_insights}"
        elif "learning" in strategy_lower:
            winner = self._apply_learning_strategy(cypher_results, vibe_results)
            reasoning = f"Learning-based selection using historical patterns"
        else:
            winner = "balanced"
            reasoning = f"Balanced selection {memory_insights}"
        
        # Select products based on enhanced winner logic
        final_products = self._select_products_enhanced(
            winner, cypher_results, vibe_results, limit, memory_insights
        )
        
        # Create judgment result with memory context
        judgment = {
            "winner": winner,
            "reasoning": reasoning,
            "products": final_products,
            "cypher_count": len(cypher_results),
            "vibe_count": len(vibe_results),
            "consensus_count": self._count_consensus(cypher_results, vibe_results),
            "judgment_confidence": self._calculate_confidence(winner, final_products),
            "memory_enhanced": True,
            "learning_insights": memory_insights
        }
        
        return judgment
    
    def _get_memory_insights(self, query: str, strategy: str) -> str:
        """Extract insights from memory for enhanced judgment."""
        if len(self.judgment_history) == 0:
            return "(first judgment - no history available)"
        
        # Analyze recent successful patterns
        recent = self.judgment_history[-5:]  # Last 5 judgments
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
            return "balanced"  # Default for first judgment
        
        # Analyze success patterns
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
            'successful': judgment['judgment_confidence'] > 0.7  # Consider high confidence as successful
        }
        
        self.judgment_history.append(judgment_record)
        
        # Keep only last 50 judgments to prevent memory bloat
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
    
    def _select_products_enhanced(
        self,
        winner: str,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int,
        memory_insights: str
    ) -> List[Dict[str, Any]]:
        """
        Enhanced product selection with memory context.
        """
        if winner == "cypher":
            products = cypher_results[:limit]
            for p in products:
                p['winning_agent'] = 'CypherBot'
                p['selection_reason'] = f'Data-driven selection {memory_insights}'
                
        elif winner == "vibe":
            products = vibe_results[:limit]
            for p in products:
                p['winning_agent'] = 'VibeBot'
                p['selection_reason'] = f'Aesthetic selection {memory_insights}'
                
        elif winner == "consensus":
            products = self._get_consensus_products(cypher_results, vibe_results, limit)
            
        elif winner == "quality":
            products = self._select_by_quality(cypher_results, vibe_results, limit)
            
        else:  # balanced
            products = self._interleave_products(cypher_results, vibe_results, limit)
        
        # Add final ranking with memory context
        for idx, product in enumerate(products):
            product['final_rank'] = idx + 1
            product['judge_score'] = 1.0 - (idx * 0.1)
            product['memory_enhanced'] = True
        
        return products
    
    # [Previous helper methods remain the same - _get_consensus_products, _select_by_quality, etc.]
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
        """Count products both agents found using ID matching."""
        cypher_ids = {p.get('id') for p in cypher_results if p.get('id')}
        vibe_ids = {p.get('id') for p in vibe_results if p.get('id')}
        return len(cypher_ids & vibe_ids)

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
        
        # Memory enhancement bonus
        if len(self.judgment_history) > 5:
            confidence += 0.05
        
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
            "judgment_confidence": 0.5,
            "memory_enhanced": False
        }
    
    def _update_stats(self, judgment: Dict[str, Any], elapsed_time: float):
        """Update judge statistics."""
        winner = judgment.get('winner', 'unknown')
        
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
    
    async def cleanup(self):
        """Clean up resources and save learning data."""
        logger.info(f"Cleaning up {self.name}")
        
        # Save judgment history for persistence
        if self.judgment_history:
            logger.info(f"Saving {len(self.judgment_history)} judgment records")
        
        # Clear memory
        if hasattr(self, 'memory'):
            self.memory.clear()
        
        logger.info(f"{self.name} cleanup complete")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get enhanced judge statistics with learning metrics."""
        total = self.stats['total_judgments']
        
        return {
            "judge": self.name,
            "role": self.role,
            "camel_version": "0.2.7",
            "features": ["RolePlay", "Memory", "Learning"],
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
            "learning_rate": (
                self.stats['learning_interactions'] / total
                if total > 0 else 0
            ),
            "judgment_history_size": len(self.judgment_history)
        }