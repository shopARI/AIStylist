"""
Competitive Search System for Vector Migration
Manages battles between agents and judges results
"""

import logging
import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np

logger = logging.getLogger("competitive_search_system")


class Judge:
    """
    Judge Ari - Head stylist who evaluates search results
    """
    
    def __init__(self, name: str = "Ari"):
        self.name = name
        self.judgment_history = []
        
    async def evaluate_results(
        self,
        query: str,
        cypher_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate and compare results from both agents
        
        Returns:
            Judgment with winner, scores, and explanation
        """
        # Calculate scores for each set of results
        cypher_score = await self._calculate_score(query, cypher_results, "graph", user_context)
        vector_score = await self._calculate_score(query, vector_results, "vector", user_context)
        
        # Determine winner
        if cypher_score > vector_score * 1.1:  # 10% margin for clear win
            winner = "cypher"
        elif vector_score > cypher_score * 1.1:
            winner = "vector"
        else:
            winner = "draw"
        
        # Generate explanation
        explanation = self._generate_explanation(
            query, cypher_results, vector_results,
            cypher_score, vector_score, winner, user_context
        )
        
        judgment = {
            "query": query,
            "winner": winner,
            "cypher_score": cypher_score,
            "vector_score": vector_score,
            "explanation": explanation,
            "timestamp": datetime.now().isoformat(),
            "confidence": abs(cypher_score - vector_score) / max(cypher_score, vector_score, 0.1)
        }
        
        # Store judgment
        self.judgment_history.append(judgment)
        
        return judgment
    
    async def _calculate_score(
        self,
        query: str,
        results: List[Dict[str, Any]],
        source: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate score for a set of results
        
        Scoring factors:
        - Relevance to query
        - Diversity of results
        - Price appropriateness
        - User preference alignment
        - Result quality (completeness)
        """
        if not results:
            return 0.0
        
        scores = []
        
        # 1. Relevance score (based on title/description matching)
        relevance_scores = []
        query_terms = set(query.lower().split())
        
        for product in results:
            title = product.get('title', '').lower()
            desc = product.get('description', '').lower()
            
            # Count matching terms
            title_matches = sum(1 for term in query_terms if term in title)
            desc_matches = sum(1 for term in query_terms if term in desc) * 0.5
            
            relevance = (title_matches + desc_matches) / len(query_terms) if query_terms else 0
            relevance_scores.append(min(relevance, 1.0))
        
        avg_relevance = np.mean(relevance_scores) if relevance_scores else 0
        scores.append(avg_relevance * 30)  # 30% weight
        
        # 2. Diversity score (variety in categories/prices)
        categories = set()
        prices = []
        
        for product in results:
            cats = product.get('categories', [])
            if isinstance(cats, list):
                categories.update(cats)
            
            price = product.get('price', 0)
            if price > 0:
                prices.append(price)
        
        diversity_score = min(len(categories) / 3, 1.0)  # Normalize by expecting 3+ categories
        scores.append(diversity_score * 20)  # 20% weight
        
        # 3. Price appropriateness
        if prices:
            price_cv = np.std(prices) / np.mean(prices) if np.mean(prices) > 0 else 0
            price_score = 1.0 - min(price_cv, 1.0)  # Lower CV is better
            scores.append(price_score * 15)  # 15% weight
        else:
            scores.append(0)
        
        # 4. Result completeness (having all necessary fields)
        completeness_scores = []
        required_fields = ['id', 'title', 'price', 'description']
        
        for product in results:
            complete_fields = sum(1 for field in required_fields if product.get(field))
            completeness = complete_fields / len(required_fields)
            completeness_scores.append(completeness)
        
        avg_completeness = np.mean(completeness_scores) if completeness_scores else 0
        scores.append(avg_completeness * 15)  # 15% weight
        
        # 5. Source-specific bonuses
        if source == "graph":
            # Bonus for relationship-based queries
            if any(word in query.lower() for word in ["similar", "like", "goes with", "match"]):
                scores.append(10)  # Relationship bonus
        elif source == "vector":
            # Bonus for natural language queries
            if len(query.split()) > 5:  # Complex natural language
                scores.append(10)  # NLP bonus
        
        # 6. User context alignment (if available)
        if user_context:
            context_score = self._calculate_context_alignment(results, user_context)
            scores.append(context_score * 10)  # 10% weight
        
        # Calculate final score
        total_score = sum(scores)
        return min(total_score, 100)  # Cap at 100
    
    def _calculate_context_alignment(
        self,
        results: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> float:
        """Calculate how well results align with user context"""
        alignment_scores = []
        
        # Check price range alignment
        if 'budget_range' in user_context:
            min_budget = user_context['budget_range'].get('min', 0)
            max_budget = user_context['budget_range'].get('max', float('inf'))
            
            for product in results:
                price = product.get('price', 0)
                if min_budget <= price <= max_budget:
                    alignment_scores.append(1.0)
                else:
                    alignment_scores.append(0.0)
        
        # Check category preferences
        if 'preferred_categories' in user_context:
            pref_cats = set(user_context['preferred_categories'])
            
            for product in results:
                prod_cats = set(product.get('categories', []))
                if prod_cats & pref_cats:  # Intersection
                    alignment_scores.append(1.0)
                else:
                    alignment_scores.append(0.5)
        
        return np.mean(alignment_scores) if alignment_scores else 0.5
    
    def _generate_explanation(
        self,
        query: str,
        cypher_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        cypher_score: float,
        vector_score: float,
        winner: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate natural language explanation of the judgment"""
        
        explanations = []
        
        # Opening
        explanations.append(f'After analyzing both sets of results for "{query}":')
        explanations.append("")
        
        # CypherBot analysis
        explanations.append("CypherBot (Neo4j Graph):")
        if cypher_results:
            explanations.append(f"- Found {len(cypher_results)} products using graph relationships")
            
            # Analyze strength
            if any(word in query.lower() for word in ["similar", "like", "goes with"]):
                explanations.append("- Excelled at finding products with strong relational connections")
            
            categories = set()
            for p in cypher_results:
                cats = p.get('categories', [])
                if isinstance(cats, list):
                    categories.update(cats)
            
            if categories:
                explanations.append(f"- Covered {len(categories)} different categories")
        else:
            explanations.append("- No results found")
        
        explanations.append(f"- Score: {cypher_score:.1f}/100")
        explanations.append("")
        
        # VibeBot analysis
        explanations.append("VibeBot (Vector Search):")
        if vector_results:
            explanations.append(f"- Found {len(vector_results)} products using semantic similarity")
            
            # Analyze strength
            if len(query.split()) > 5:
                explanations.append("- Demonstrated strong understanding of natural language nuances")
            
            # Check diversity
            prices = [p.get('price', 0) for p in vector_results if p.get('price', 0) > 0]
            if prices:
                explanations.append(f"- Price range: ${min(prices):.2f} - ${max(prices):.2f}")
        else:
            explanations.append("- No results found")
        
        explanations.append(f"- Score: {vector_score:.1f}/100")
        explanations.append("")
        
        # Winner explanation
        if winner == "cypher":
            explanations.append("🏆 CypherBot wins this round!")
            explanations.append("The graph-based approach provided more relevant results for this query type.")
        elif winner == "vector":
            explanations.append("🏆 VibeBot wins this round!")
            explanations.append("The vector search better understood the intent and context of the query.")
        else:
            explanations.append("🤝 It's a draw!")
            explanations.append("Both approaches provided similarly valuable results.")
        
        # Confidence
        confidence = abs(cypher_score - vector_score) / max(cypher_score, vector_score, 0.1)
        if confidence < 0.1:
            explanations.append("The results were very close, indicating both methods work well for this query.")
        elif confidence > 0.3:
            explanations.append("There was a clear winner, showing one method's superiority for this query type.")
        
        return "\n".join(explanations)


class CompetitiveSearchSystem:
    """
    Main system for managing competitive searches
    """
    
    def __init__(self, battle_agents=None):
        self.battle_agents = battle_agents
        self.judge = Judge()
        self.battle_stats = {
            "total_battles": 0,
            "cypher_wins": 0,
            "vector_wins": 0,
            "draws": 0,
            "win_by_query_type": {
                "specific_item": {"cypher": 0, "vector": 0},
                "style_search": {"cypher": 0, "vector": 0},
                "occasion_based": {"cypher": 0, "vector": 0},
                "filter_heavy": {"cypher": 0, "vector": 0},
                "natural_language": {"cypher": 0, "vector": 0}
            },
            "average_response_time": {
                "cypher": [],
                "vector": []
            },
            "user_satisfaction": {
                "cypher": [],
                "vector": []
            }
        }
        
        logger.info("CompetitiveSearchSystem initialized")
    
    async def execute_battle(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a competitive search battle
        
        Returns:
            Complete battle results with judgment
        """
        if not self.battle_agents:
            logger.error("No battle agents configured")
            return {"error": "No battle agents available"}
        
        # Start battle
        start_time = time.time()
        
        # Get results from both agents
        battle_results = await self.battle_agents.battle_search(query, filters, limit)
        
        # Extract results for judgment
        cypher_data = battle_results.get("agents", {}).get("CypherBot", {})
        vector_data = battle_results.get("agents", {}).get("VibeBot", {})
        
        cypher_results = cypher_data.get("products", [])
        vector_results = vector_data.get("products", [])
        
        # Judge the results
        judgment = await self.judge.evaluate_results(
            query, cypher_results, vector_results, user_context
        )
        
        # Update statistics
        self._update_stats(
            judgment["winner"],
            self._classify_query(query),
            cypher_data.get("response_time", 0),
            vector_data.get("response_time", 0)
        )
        
        # Compile final results
        final_results = {
            "battle_id": f"battle_{int(time.time())}_{hash(query) % 10000}",
            "query": query,
            "filters": filters,
            "execution_time": time.time() - start_time,
            "agents": {
                "cypher": {
                    "products": cypher_results,
                    "response_time": cypher_data.get("response_time", 0),
                    "score": judgment["cypher_score"]
                },
                "vector": {
                    "products": vector_results,
                    "response_time": vector_data.get("response_time", 0),
                    "score": judgment["vector_score"]
                }
            },
            "judgment": judgment,
            "stats_snapshot": self.get_current_stats()
        }
        
        return final_results
    
    def _classify_query(self, query: str) -> str:
        """Classify query type for statistics"""
        query_lower = query.lower()
        
        if len(query.split()) > 6:
            return "natural_language"
        elif any(word in query_lower for word in ["wedding", "party", "formal", "casual"]):
            return "occasion_based"
        elif "filter" in query_lower or "under $" in query_lower or "between" in query_lower:
            return "filter_heavy"
        elif any(word in query_lower for word in ["dress", "shirt", "pants", "shoes"]):
            return "specific_item"
        else:
            return "style_search"
    
    def _update_stats(
        self,
        winner: str,
        query_type: str,
        cypher_time: float,
        vector_time: float
    ):
        """Update battle statistics"""
        self.battle_stats["total_battles"] += 1
        
        if winner == "cypher":
            self.battle_stats["cypher_wins"] += 1
            self.battle_stats["win_by_query_type"][query_type]["cypher"] += 1
        elif winner == "vector":
            self.battle_stats["vector_wins"] += 1
            self.battle_stats["win_by_query_type"][query_type]["vector"] += 1
        else:
            self.battle_stats["draws"] += 1
        
        # Update response times
        self.battle_stats["average_response_time"]["cypher"].append(cypher_time)
        self.battle_stats["average_response_time"]["vector"].append(vector_time)
        
        # Keep only last 100 response times
        if len(self.battle_stats["average_response_time"]["cypher"]) > 100:
            self.battle_stats["average_response_time"]["cypher"] = \
                self.battle_stats["average_response_time"]["cypher"][-100:]
        
        if len(self.battle_stats["average_response_time"]["vector"]) > 100:
            self.battle_stats["average_response_time"]["vector"] = \
                self.battle_stats["average_response_time"]["vector"][-100:]
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current battle statistics"""
        stats = self.battle_stats.copy()
        
        # Calculate averages
        if stats["average_response_time"]["cypher"]:
            stats["avg_cypher_time"] = np.mean(stats["average_response_time"]["cypher"])
        else:
            stats["avg_cypher_time"] = 0
        
        if stats["average_response_time"]["vector"]:
            stats["avg_vector_time"] = np.mean(stats["average_response_time"]["vector"])
        else:
            stats["avg_vector_time"] = 0
        
        # Calculate win rates
        total = stats["total_battles"]
        if total > 0:
            stats["cypher_win_rate"] = (stats["cypher_wins"] / total) * 100
            stats["vector_win_rate"] = (stats["vector_wins"] / total) * 100
            stats["draw_rate"] = (stats["draws"] / total) * 100
        else:
            stats["cypher_win_rate"] = 0
            stats["vector_win_rate"] = 0
            stats["draw_rate"] = 0
        
        # Remove raw arrays from response
        stats.pop("average_response_time", None)
        stats.pop("user_satisfaction", None)
        
        return stats
    
    async def simulate_user_feedback(
        self,
        battle_id: str,
        winner_preference: str,
        satisfaction_score: float
    ):
        """
        Record user feedback on battle results
        
        Args:
            battle_id: ID of the battle
            winner_preference: Which agent's results the user preferred
            satisfaction_score: User satisfaction (0-1)
        """
        if winner_preference in ["cypher", "vector"]:
            self.battle_stats["user_satisfaction"][winner_preference].append(satisfaction_score)
            
            # Keep only last 100 feedback entries
            if len(self.battle_stats["user_satisfaction"][winner_preference]) > 100:
                self.battle_stats["user_satisfaction"][winner_preference] = \
                    self.battle_stats["user_satisfaction"][winner_preference][-100:]
        
        logger.info(f"Recorded user feedback for battle {battle_id}: {winner_preference} ({satisfaction_score:.2f})")
