"""
Quality Assessment and Judgment Tools for CrewAI Migration
Implements quality scoring, consensus detection, and learning analysis.
"""
import logging
from typing import Dict, List, Any
from crewai.tools import tool

logger = logging.getLogger("crewai.tools.quality")


@tool("Score Product Quality")
def quality_scoring_tool(product: Dict[str, Any], query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Assess product quality independently of agent scores.
    Evaluates completeness, relevance, and commercial viability.

    Args:
        product: Product data dictionary
        query: Original search query
        context: Optional context (user preferences, occasion, etc.)

    Returns:
        Quality assessment with score and factors

    Example:
        assessment = quality_scoring_tool(
            product={"title": "Black Dress", "price": 89.99, ...},
            query="black dress for wedding",
            context={"occasion": "wedding"}
        )
    """
    try:
        score = 0.0
        factors = {}

        # Completeness check (40% of score)
        completeness = 0.0
        if product.get('title'):
            completeness += 0.25
        if product.get('price') and product['price'] > 0:
            completeness += 0.25
        if product.get('images') and len(product['images']) > 0:
            completeness += 0.25
        if product.get('description'):
            completeness += 0.25

        factors['completeness'] = completeness
        score += completeness * 0.4

        # Relevance check (40% of score)
        relevance = 0.0
        query_lower = query.lower()
        title_lower = product.get('title', '').lower()

        # Check query terms in title
        query_terms = query_lower.split()
        matching_terms = sum(1 for term in query_terms if term in title_lower)
        relevance = matching_terms / len(query_terms) if query_terms else 0

        factors['relevance'] = relevance
        score += relevance * 0.4

        # Commercial viability (20% of score)
        viability = 0.0

        # Check if in stock
        if product.get('in_stock', True):
            viability += 0.5

        # Check reasonable price range
        price = product.get('price', 0)
        if 10 <= price <= 1000:  # Reasonable fashion price range
            viability += 0.5

        factors['viability'] = viability
        score += viability * 0.2

        # Final quality score
        factors['overall_score'] = score

        result = {
            "quality_score": score,
            "completeness": completeness,
            "relevance": relevance,
            "viability": viability,
            "factors": factors,
            "pass_threshold": score >= 0.5  # 50% threshold for acceptance
        }

        logger.info(f"Quality assessment: {score:.2f} (completeness={completeness:.2f}, relevance={relevance:.2f})")
        return result

    except Exception as e:
        logger.error(f"Quality scoring failed: {e}")
        return {
            "quality_score": 0.0,
            "completeness": 0.0,
            "relevance": 0.0,
            "viability": 0.0,
            "pass_threshold": False
        }


@tool("Detect Consensus Products")
def consensus_detection_tool(
    cypher_results: List[Dict],
    vibe_results: List[Dict],
    vision_results: List[Dict] = None
) -> List[Dict]:
    """
    Identify products found by multiple agents (consensus).
    Products with consensus are higher confidence recommendations.

    Args:
        cypher_results: Products from graph search
        vibe_results: Products from vector search
        vision_results: Optional products from visual search

    Returns:
        Products with consensus count and sources

    Example:
        consensus = consensus_detection_tool(
            cypher_results=[{...}],
            vibe_results=[{...}],
            vision_results=[{...}]
        )
    """
    try:
        # Track products by ID
        product_map = {}

        # Process CypherBot results
        for product in cypher_results:
            prod_id = product.get('id')
            if prod_id:
                if prod_id not in product_map:
                    product_map[prod_id] = {
                        'product': product,
                        'sources': [],
                        'scores': {}
                    }
                product_map[prod_id]['sources'].append('CypherBot')
                product_map[prod_id]['scores']['cypher'] = product.get('score', 0.0)

        # Process VibeBot results
        for product in vibe_results:
            prod_id = product.get('id')
            if prod_id:
                if prod_id not in product_map:
                    product_map[prod_id] = {
                        'product': product,
                        'sources': [],
                        'scores': {}
                    }
                product_map[prod_id]['sources'].append('VibeBot')
                product_map[prod_id]['scores']['vibe'] = product.get('score', 0.0)

        # Process VisionBot results if provided
        if vision_results:
            for product in vision_results:
                prod_id = product.get('id')
                if prod_id:
                    if prod_id not in product_map:
                        product_map[prod_id] = {
                            'product': product,
                            'sources': [],
                            'scores': {}
                        }
                    product_map[prod_id]['sources'].append('VisionBot')
                    product_map[prod_id]['scores']['vision'] = product.get('score', 0.0)

        # Build consensus list
        consensus_products = []
        for prod_id, data in product_map.items():
            consensus_count = len(data['sources'])

            # Only include products with consensus (found by 2+ agents)
            if consensus_count >= 2:
                product = data['product'].copy()
                product['consensus_count'] = consensus_count
                product['consensus_sources'] = data['sources']
                product['agent_scores'] = data['scores']

                # Calculate average score across agents
                avg_score = sum(data['scores'].values()) / len(data['scores'])
                product['consensus_score'] = avg_score

                consensus_products.append(product)

        # Sort by consensus count, then by score
        consensus_products.sort(
            key=lambda x: (x['consensus_count'], x['consensus_score']),
            reverse=True
        )

        logger.info(f"Found {len(consensus_products)} products with consensus")
        return consensus_products

    except Exception as e:
        logger.error(f"Consensus detection failed: {e}")
        return []


@tool("Analyze Judgment History")
def learning_analysis_tool(judgment_history: List[Dict], query_context: Dict = None) -> Dict[str, Any]:
    """
    Analyze judgment history to identify patterns and optimize strategy.
    Learns from past decisions to improve future recommendations.

    Args:
        judgment_history: List of past judgment decisions
        query_context: Optional context about current query

    Returns:
        Analysis of patterns and optimization suggestions

    Example:
        analysis = learning_analysis_tool(
            judgment_history=[{...}],
            query_context={"occasion": "wedding"}
        )
    """
    try:
        if not judgment_history:
            return {
                "patterns_found": 0,
                "insights": [],
                "optimization_suggestions": []
            }

        insights = []
        patterns = {}

        # Analyze acceptance vs rejection rates
        total = len(judgment_history)
        accepted = sum(1 for j in judgment_history if j.get('accepted', False))
        rejected = total - accepted

        acceptance_rate = accepted / total if total > 0 else 0
        patterns['acceptance_rate'] = acceptance_rate

        # Analyze rejection reasons
        rejection_reasons = {}
        for judgment in judgment_history:
            if not judgment.get('accepted', False):
                reason = judgment.get('rejection_reason', 'unknown')
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

        patterns['rejection_reasons'] = rejection_reasons

        # Generate insights
        if acceptance_rate < 0.3:
            insights.append("Low acceptance rate - quality standards may be too strict")
        elif acceptance_rate > 0.8:
            insights.append("High acceptance rate - consider tightening quality criteria")

        # Most common rejection reason
        if rejection_reasons:
            most_common_rejection = max(rejection_reasons.items(), key=lambda x: x[1])
            insights.append(f"Most common rejection: {most_common_rejection[0]} ({most_common_rejection[1]} times)")

        # Optimization suggestions
        suggestions = []
        if 'incomplete_data' in rejection_reasons and rejection_reasons['incomplete_data'] > 5:
            suggestions.append("Improve data completeness filtering at source")

        if 'low_relevance' in rejection_reasons and rejection_reasons['low_relevance'] > 5:
            suggestions.append("Enhance semantic query expansion for better relevance")

        result = {
            "patterns_found": len(patterns),
            "acceptance_rate": acceptance_rate,
            "total_judgments": total,
            "accepted": accepted,
            "rejected": rejected,
            "rejection_breakdown": rejection_reasons,
            "insights": insights,
            "optimization_suggestions": suggestions,
            "patterns": patterns
        }

        logger.info(f"Analyzed {total} judgments: {acceptance_rate:.1%} acceptance rate")
        return result

    except Exception as e:
        logger.error(f"Learning analysis failed: {e}")
        return {
            "patterns_found": 0,
            "insights": [],
            "optimization_suggestions": []
        }
