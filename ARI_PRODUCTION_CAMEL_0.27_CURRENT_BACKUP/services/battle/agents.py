"""
Battle Agents for Competitive Search System
CypherBot (Neo4j), VibeBot (Qdrant), and Judge Ari
Adapted for CAMEL 0.2.7
"""

import logging
import asyncio
import json 
from typing import List, Dict, Any, Optional
from datetime import datetime

# CAMEL 0.2.7 imports
from camel.agents import ChatAgent
from camel.configs import ChatGPTConfig
from camel.messages import BaseMessage
from camel.memory import LongTermMemory, ChatHistoryMemory


logger = logging.getLogger("battle_agents")


class CypherBotAgent:
    """
    Neo4j-based agent that uses graph intelligence for recommendations.
    Specializes in relationship-based searches and user behavior patterns.
    """
    
    def __init__(self, neo4j_client, model_type: str = "gpt-4o-mini"):
        """Initialize CypherBot with Neo4j connection"""
        self.neo4j_client = neo4j_client
        self.model_type = model_type
        
        # Create CAMEL 0.2.7 agent
        self.agent = ChatAgent(
            system_message=self._get_system_message(),
            model_config=ChatGPTConfig(
                model=model_type,
                temperature=0.7,
                max_tokens=1000
            ),
            function_calling_enabled=True,
            memory=LongTermMemory(
                chat_memory=ChatHistoryMemory(window_size=10)
            )
        )
        
        logger.info(f"CypherBot initialized with model: {model_type}")
    
    def _get_system_message(self) -> str:
        """Get CypherBot's personality and instructions"""
        return """You are CypherBot, a graph-intelligence specialist who excels at finding products through relationship patterns and user behavior analysis.

Your strengths:
- Understanding user purchase patterns and preferences
- Finding products through graph relationships
- Identifying trending items based on interaction patterns
- Personalizing results based on user history

When searching for products:
1. Consider the user's interaction history
2. Look for patterns in similar users' behaviors
3. Weight results by relationship strength
4. Prioritize items with strong graph connections

Your responses should be data-driven and focus on patterns you've discovered.
You compete with VibeBot (who uses vector similarity) to find the best products.
Be confident in your graph-based approach."""
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using graph intelligence
        """
        try:
            products = []
            
            # Use ML intelligence if available (especially RFM and clustering)
            if ml_intelligence and "cypher_intel" in ml_intelligence:
                intel = ml_intelligence["cypher_intel"]
                
                # Use RFM segment for personalization
                if "user_segment" in intel:
                    segment = intel["user_segment"]
                    logger.info(f"CypherBot using segment: {segment}")
                
                # Use cluster information
                if "relevant_clusters" in intel:
                    clusters = intel["relevant_clusters"]
                    logger.info(f"CypherBot targeting clusters: {clusters}")
            
            # Build Cypher query based on context
            cypher_query = self._build_cypher_query(
                query, filters, user_context, ml_intelligence
            )
            
            # Execute query
            if self.neo4j_client and hasattr(self.neo4j_client, 'query'):
                try: 
                    results = await self.neo4j_client.query(
                        cypher_query,
                        {"query": query, "limit": limit}
                    )
                except AttributeError:
                    logger.warning("Neo4j client doesn't support query method")
                    results = []
                
                # Process results
                for record in results[:limit]:
                    product = {
                        "id": record.get("product_id"),
                        "title": record.get("title", "Unknown"),
                        "price": record.get("price", 0),
                        "category": record.get("category"),
                        "score": record.get("score", 0.5),
                        "source": "cypher",
                        "graph_connections": record.get("connections", 0)
                    }
                    products.append(product)
            
            # If no Neo4j results, generate warning
            if not products:
                logger.warning(f"No products found for query: {query}")
                Products = []
            
            # Ask agent to evaluate the products
            evaluation_prompt = f"""
            I found {len(products)} products for the query: "{query}"
            These products were selected based on graph relationships and user patterns.
            Rate my selection quality (1-10) and explain why these are good matches.
            """
            
            msg = BaseMessage(role="user", content=evaluation_prompt)
            response = await self.agent.step_async(msg)
            
            logger.info(f"CypherBot found {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"CypherBot search error: {e}")
            return []
    
    def _build_cypher_query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> str:
        """Build Cypher query for Neo4j"""
        
        # Base query structure
        base_query = """
        MATCH (p:Product)
        WHERE p.title CONTAINS $query OR p.description CONTAINS $query
        """
        
        # Add filters
        if filters:
            if filters.get("category"):
                base_query += f" AND p.category = '{filters['category']}'"
            if filters.get("min_price"):
                base_query += f" AND p.price >= {filters['min_price']}"
            if filters.get("max_price"):
                base_query += f" AND p.price <= {filters['max_price']}"
        
        # Add user context
        if user_context and user_context.get("user_id"):
            base_query = """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[r:INTERACTED_WITH]->(p:Product)
            WHERE p.title CONTAINS $query OR p.description CONTAINS $query
            """
        
        base_query += """
        RETURN p.id as product_id, p.title as title, p.price as price,
               p.category as category, COUNT(r) as connections,
               CASE WHEN r IS NOT NULL THEN 0.8 ELSE 0.5 END as score
        ORDER BY score DESC, connections DESC
        LIMIT $limit
        """
        
        return base_query
    
    def _generate_mock_products(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Generate mock products for demo purposes"""
        products = []
        for i in range(min(limit, 5)):
            products.append({
                "id": f"cypher_{i}",
                "title": f"Graph-Selected {query.title()} Item {i+1}",
                "price": 50 + (i * 20),
                "category": "Fashion",
                "score": 0.9 - (i * 0.1),
                "source": "cypher",
                "graph_connections": 10 - i
            })
        return products
    
    async def test_connection(self) -> bool:
        """Test Neo4j connection"""
        try:
            if self.neo4j_client:
                result = await self.neo4j_client.query("RETURN 1 as test")
                return bool(result)
            return True  # Return True for demo mode
        except Exception as e:
            logger.error(f"CypherBot connection test failed: {e}")
            return False


class VibeBotAgent:
    """
    Qdrant-based agent that uses vector similarity for recommendations.
    Specializes in semantic search and visual similarity.
    """
    
    def __init__(self, qdrant_client, model_type: str = "gpt-4o-mini"):
        """Initialize VibeBot with Qdrant connection"""
        self.qdrant_client = qdrant_client
        self.model_type = model_type
        
        # Create CAMEL 0.2.7 agent
        self.agent = ChatAgent(
            system_message=self._get_system_message(),
            model_config=ChatGPTConfig(
                model=model_type,
                temperature=0.8,  # Slightly more creative
                max_tokens=1000
            ),
            function_calling_enabled=True,
            memory=LongTermMemory(
                chat_memory=ChatHistoryMemory(window_size=10)
            )
        )
        
        logger.info(f"VibeBot initialized with model: {model_type}")
    
    def _get_system_message(self) -> str:
        """Get VibeBot's personality and instructions"""
        return """You are VibeBot, a style and aesthetic specialist who excels at finding products through semantic understanding and visual similarity.

Your strengths:
- Understanding style nuances and aesthetic preferences
- Finding products through semantic similarity
- Identifying items with similar visual characteristics
- Capturing the "vibe" or feeling of what users want

When searching for products:
1. Focus on understanding the essence of what the user wants
2. Look for semantic and stylistic matches
3. Consider visual similarity and aesthetic coherence
4. Trust your understanding of fashion trends and styles

Your responses should be creative and focus on the aesthetic appeal.
You compete with CypherBot (who uses graph patterns) to find the best products.
Be confident in your semantic and style-based approach."""
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using vector similarity
        """
        try:
            products = []
            
            # Use ML intelligence if available (especially visual features)
            if ml_intelligence and "vibe_intel" in ml_intelligence:
                intel = ml_intelligence["vibe_intel"]
                
                # Use visual features
                if "visual_features" in intel:
                    features = intel["visual_features"]
                    logger.info(f"VibeBot using visual features: {features.get('dominant_colors')}")
                
                # Use style attributes
                if "style_attributes" in intel:
                    styles = intel["style_attributes"]
                    logger.info(f"VibeBot targeting styles: {styles}")
            
            # Search using Qdrant
            if self.qdrant_client:
                results = await self.qdrant_client.search_by_natural_language(
                    query=query,
                    limit=limit,
                    filters=filters
                )
                
                # Process results
                for idx, result in enumerate(results):
                    product = {
                        "id": result.get("id"),
                        "title": result.get("title", "Unknown"),
                        "price": result.get("price", 0),
                        "category": result.get("category"),
                        "score": 0.95 - (idx * 0.05),  # Score based on ranking
                        "source": "vector",
                        "similarity_score": result.get("score", 0.5)
                    }
                    products.append(product)
            
            if not products:
                logger.warning(f"No products found for query: {query}")
                products = []
            
            # Ask agent to evaluate the products
            evaluation_prompt = f"""
            I found {len(products)} products for the query: "{query}"
            These products were selected based on semantic similarity and style matching.
            Rate my selection quality (1-10) and explain why these capture the right vibe.
            """
            
            msg = BaseMessage(role="user", content=evaluation_prompt)
            response = await self.agent.step_async(msg)
            
            logger.info(f"VibeBot found {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"VibeBot search error: {e}")
            return []
    
    def _generate_mock_products(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Generate mock products for demo purposes"""
        products = []
        for i in range(min(limit, 5)):
            products.append({
                "id": f"vibe_{i}",
                "title": f"Style-Matched {query.title()} Piece {i+1}",
                "price": 60 + (i * 25),
                "category": "Fashion",
                "score": 0.95 - (i * 0.08),
                "source": "vector",
                "similarity_score": 0.9 - (i * 0.1)
            })
        return products
    
    async def test_connection(self) -> bool:
        """Test Qdrant connection"""
        try:
            if self.qdrant_client:
                stats = await self.qdrant_client.get_collection_stats()
                return bool(stats)
            return True  # Return True for demo mode
        except Exception as e:
            logger.error(f"VibeBot connection test failed: {e}")
            return False




# Setup logger for this module
logger = logging.getLogger(__name__)


class JudgeAriAgent:
    """
    Judge Ari evaluates results from both agents and selects the best products.
    Uses the same warm, personable fashion stylist personality.
    """

    def __init__(self, model_type: str = "gpt-4o-mini"):
        """Initialize Judge Ari"""
        self.model_type = model_type

        # Create CAMEL 0.2.7 agent with Ari's personality
        self.agent = ChatAgent(
            system_message=self._get_system_message(),
            model_config=ChatGPTConfig(
                model=model_type,
                temperature=0.6,  # Balanced for fair judgment
                max_tokens=1500
            ),
            function_calling_enabled=True,
            memory=LongTermMemory(
                chat_memory=ChatHistoryMemory(window_size=20)
            )
        )

        logger.info(f"Judge Ari initialized with model: {model_type}")

    def _get_system_message(self) -> str:
        """Get Judge Ari's personality and instructions"""
        return """You are Ari, a warm and personable fashion stylist with years of experience. You're now acting as a judge to evaluate product recommendations from two different search approaches.

Your role as Judge:
1. Evaluate products from CypherBot (graph-based) and VibeBot (vector-based)
2. Select the best products that truly match what the client needs
3. Consider both data-driven insights AND aesthetic appeal
4. Combine the strengths of both approaches

When evaluating:
- CypherBot excels at: user patterns, trending items, personalized history
- VibeBot excels at: style matching, aesthetic coherence, semantic understanding
- Look for products that satisfy BOTH criteria when possible

Your judgment should be fair but decisive. Select products that you would genuinely recommend to a client as their trusted stylist.

Important: Return your evaluation as a structured JSON object. For example:
{
    "winner": "cypher",
    "reason": "CypherBot's results were more aligned with the user's past purchase history, while VibeBot offered great aesthetic alternatives. I've selected a mix that balances both.",
    "selected_products": [
        {"id": "prod_123", "title": "Classic Blue Denim Jacket", "score": 0.9},
        {"id": "prod_456", "title": "Vintage Style T-Shirt", "score": 0.85}
    ],
    "cypher_score": 0.7,
    "vibe_score": 0.3
}"""

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
        Evaluate results from both agents and select the best products
        """
        try:
            # Prepare evaluation prompt
            evaluation_prompt = self._create_evaluation_prompt(
                cypher_results, vibe_results, query, ml_context, user_context
            )

            # Get judgment from Ari
            msg = BaseMessage(role="user", content=evaluation_prompt)
            response = await self.agent.step_async(msg)

            # Parse response
            response_content = response.content if hasattr(response, 'content') else str(response)
            judgment = self._parse_judgment(
                response_content,
                cypher_results,
                vibe_results,
                limit
            )

            logger.info(f"Judge Ari selected {len(judgment['selected_products'])} products")
            logger.info(f"Winner: {judgment['winner']}")

            return judgment

        except Exception as e:
            logger.error(f"Judge evaluation error: {e}")

            # Fallback: combine both results
            all_products = cypher_results[:limit//2] + vibe_results[:limit//2]
            return {
                "winner": "tie",
                "reason": "Error in evaluation, using balanced selection",
                "selected_products": all_products[:limit],
                "cypher_score": 0.5,
                "vibe_score": 0.5
            }

    def _create_evaluation_prompt(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        ml_context: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """Create evaluation prompt for Judge Ari"""

        prompt = f"""As Judge Ari, evaluate these product recommendations for the query: "{query}"

**CypherBot Results (Graph Intelligence):**
"""
        cypher_text = "\n".join([
            f"- ID: {p['id']}, Title: {p.get('title')}, Score: {p.get('score', 0):.2f}"
            for p in cypher_results[:5]
        ])
        prompt += cypher_text if cypher_results else "No results found."

        prompt += f"\n\n**VibeBot Results (Style Matching):**\n"
        vibe_text = "\n".join([
            f"- ID: {p['id']}, Title: {p.get('title')}, Score: {p.get('score', 0):.2f}"
            for p in vibe_results[:5]
        ])
        prompt += vibe_text if vibe_results else "No results found."

        if user_context or ml_context:
            prompt += "\n\n**Additional Context:**"
            if user_context and user_context.get("user_id"):
                prompt += f"\n- User: Registered user with ID {user_context['user_id']}"
            if ml_context:
                if "cypher_intel" in ml_context:
                    prompt += f"\n- Graph Insights: {list(ml_context['cypher_intel'].keys())}"
                if "vibe_intel" in ml_context:
                    prompt += f"\n- Style Insights: {list(ml_context['vibe_intel'].keys())}"

        prompt += """

**Your Task:**
Based on all the information, please provide your final judgment. Your response MUST be a single JSON object. Do not include any text before or after the JSON block.

Format your response as a JSON object with the following keys: "winner", "reason", "selected_products", "cypher_score", "vibe_score".
- The "winner" should be "cypher", "vibe", or "tie".
- The "selected_products" should be a list of product objects, containing at least the "id", "title", and your final "score". Select up to 5 products.
"""
        return prompt

    def _parse_judgment(
        self,
        response: str,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> Dict[str, Any]:
        """Parse Judge Ari's response."""

        # First, attempt to parse the response as a structured JSON object.
        try:
            if "{" in response and "}" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
                return json.loads(json_str)
        except Exception:
            # If JSON parsing fails, fall back to the text parsing method below.
            logger.warning("Could not parse judgment as JSON, falling back to text parsing.")
            pass

        # Fallback logic for parsing plain text responses.
        judgment = {
            "winner": "tie",
            "reason": "",
            "selected_products": [],
            "cypher_score": 0.5,
            "vibe_score": 0.5
        }

        try:
            # Parse the winner from a "WINNER:" line.
            if "WINNER:" in response:
                winner_line = response.split("WINNER:")[1].split("\n")[0].strip().lower()
                if "cypher" in winner_line:
                    judgment["winner"] = "cypher"
                    judgment["cypher_score"] = 0.7
                    judgment["vibe_score"] = 0.3
                elif "vibe" in winner_line:
                    judgment["winner"] = "vibe"
                    judgment["cypher_score"] = 0.3
                    judgment["vibe_score"] = 0.7

            # Parse the reason from a "REASON:" line.
            if "REASON:" in response:
                judgment["reason"] = response.split("REASON:")[1].strip()

            # Parse selected product IDs from a "SELECTED:" line.
            if "SELECTED:" in response:
                selected_line = response.split("SELECTED:")[1].split("\n")[0].strip()
                selected_ids = [pid.strip() for pid in selected_line.split(",")]

                # Match IDs to the actual product data.
                all_products = {p["id"]: p for p in cypher_results + vibe_results}
                for product_id in selected_ids:
                    if product_id in all_products:
                        judgment["selected_products"].append(all_products[product_id])

            # If parsing failed to find any selected products, create a fallback list.
            if not judgment["selected_products"]:
                if judgment["winner"] == "cypher":
                    judgment["selected_products"] = cypher_results[:limit]
                elif judgment["winner"] == "vibe":
                    judgment["selected_products"] = vibe_results[:limit]
                else:
                    # In case of a tie, mix products from both agents.
                    judgment["selected_products"] = []
                    for i in range(limit):
                        if i < len(cypher_results) and i % 2 == 0:
                            judgment["selected_products"].append(cypher_results[i])
                        elif i < len(vibe_results):
                            judgment["selected_products"].append(vibe_results[i])
                        if len(judgment["selected_products"]) >= limit:
                            break

        except Exception as e:
            logger.error(f"Error during text parsing of judgment: {e}")
            # As a final resort, create a balanced selection of products.
            judgment["selected_products"] = (cypher_results[:limit//2] +
                                            vibe_results[:limit//2])[:limit]

        return judgment