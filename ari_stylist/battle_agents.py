"""
Battle Agents for Vector Migration
Implements CypherBot (Neo4j) and VibeBot (Qdrant) competing agents
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from abc import ABC, abstractmethod
import json

logger = logging.getLogger("battle_agents")


class BaseAgent(ABC):
    """Base class for battle agents"""
    
    def __init__(self, name: str, data_store=None):
        self.name = name
        self.data_store = data_store
        self.stats = {
            "queries_processed": 0,
            "total_response_time": 0.0,
            "wins": 0,
            "losses": 0,
            "draws": 0
        }
    
    @abstractmethod
    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> Tuple[List[Dict[str, Any]], float]:
        """
        Search for products based on query and filters
        
        Returns:
            Tuple of (results, response_time)
        """
        pass
    
    def update_stats(self, response_time: float, result: str = None):
        """Update agent statistics"""
        self.stats["queries_processed"] += 1
        self.stats["total_response_time"] += response_time
        
        if result == "win":
            self.stats["wins"] += 1
        elif result == "loss":
            self.stats["losses"] += 1
        elif result == "draw":
            self.stats["draws"] += 1
    
    def get_avg_response_time(self) -> float:
        """Get average response time"""
        if self.stats["queries_processed"] == 0:
            return 0.0
        return self.stats["total_response_time"] / self.stats["queries_processed"]


class CypherBot(BaseAgent):
    """
    Neo4j query specialist
    Uses graph relationships to find products
    """
    
    def __init__(self, neo4j_client):
        super().__init__("CypherBot")
        self.neo4j_client = neo4j_client
    
    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> Tuple[List[Dict[str, Any]], float]:
        """
        Search using Neo4j graph queries
        Excels at relationship-based searches
        """
        start_time = time.time()
        
        try:
            # Parse query to extract intent
            query_type = self._analyze_query_type(query)
            
            if query_type == "similar_to_liked":
                results = await self._search_similar_to_liked(query, filters, limit)
            elif query_type == "occasion_based":
                results = await self._search_by_occasion(query, filters, limit)
            elif query_type == "style_combo":
                results = await self._search_style_combinations(query, filters, limit)
            elif query_type == "user_preference":
                results = await self._search_by_user_preferences(query, filters, limit)
            else:
                # Default to standard filter search
                results = await self._standard_search(query, filters, limit)
            
            response_time = time.time() - start_time
            self.update_stats(response_time)
            
            logger.info(f"CypherBot completed search in {response_time:.2f}s, found {len(results)} products")
            return results, response_time
            
        except Exception as e:
            logger.error(f"CypherBot search error: {e}")
            response_time = time.time() - start_time
            self.update_stats(response_time)
            return [], response_time
    
    def _analyze_query_type(self, query: str) -> str:
        """Analyze query to determine search strategy"""
        query_lower = query.lower()
        
        if "similar to" in query_lower or "like the" in query_lower:
            return "similar_to_liked"
        elif any(word in query_lower for word in ["wedding", "party", "work", "casual", "formal"]):
            return "occasion_based"
        elif "goes with" in query_lower or "match with" in query_lower:
            return "style_combo"
        elif "my style" in query_lower or "for me" in query_lower:
            return "user_preference"
        else:
            return "standard"
    
    async def _search_similar_to_liked(self, query: str, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Search for products similar to previously liked items"""
        if not filters or 'user_id' not in filters:
            return await self._standard_search(query, filters, limit)
        
        user_id = filters['user_id']
        
        # Cypher query to find products similar to user's liked items
        cypher_query = """
        MATCH (u:User {id: $user_id})-[:LIKED]->(liked:Product)
        MATCH (liked)-[:IN_CATEGORY]->(c:Category)<-[:IN_CATEGORY]-(p:Product)
        WHERE p.id <> liked.id
        WITH p, COUNT(DISTINCT liked) as similarity_score
        ORDER BY similarity_score DESC, p.visited_num DESC
        LIMIT $limit
        RETURN p.id as id, p.title as title, p.price as price, 
               p.description as description, p.images as images,
               similarity_score
        """
        
        try:
            results = await self.neo4j_client.query(
                cypher_query,
                {"user_id": user_id, "limit": limit}
            )
            
            return [self._format_product(r) for r in results]
        except Exception as e:
            logger.error(f"Error in similar_to_liked search: {e}")
            return []
    
    async def _search_by_occasion(self, query: str, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Search products by occasion using graph relationships"""
        # Extract occasion from query
        occasions = ["wedding", "party", "work", "casual", "formal", "beach", "date"]
        occasion = None
        
        query_lower = query.lower()
        for occ in occasions:
            if occ in query_lower:
                occasion = occ
                break
        
        if not occasion:
            return await self._standard_search(query, filters, limit)
        
        # Cypher query for occasion-based search
        cypher_query = """
        MATCH (p:Product)-[:TAGGED_WITH]->(t:Tag)
        WHERE toLower(t.title) CONTAINS $occasion
        OPTIONAL MATCH (p)-[:IN_COLLECTION]->(col:Collection)
        WHERE toLower(col.title) CONTAINS $occasion
        WITH p, COUNT(DISTINCT t) + COUNT(DISTINCT col) as relevance_score
        WHERE relevance_score > 0
        ORDER BY relevance_score DESC, p.visited_num DESC
        LIMIT $limit
        RETURN p.id as id, p.title as title, p.price as price,
               p.description as description, p.images as images,
               relevance_score
        """
        
        try:
            results = await self.neo4j_client.query(
                cypher_query,
                {"occasion": occasion, "limit": limit}
            )
            
            return [self._format_product(r) for r in results]
        except Exception as e:
            logger.error(f"Error in occasion search: {e}")
            return []
    
    async def _search_style_combinations(self, query: str, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Search for products that go well together"""
        # This would look for products frequently bought together
        cypher_query = """
        MATCH (p1:Product)<-[:PURCHASED]-(u:User)-[:PURCHASED]->(p2:Product)
        WHERE p1.id <> p2.id
        WITH p1, p2, COUNT(DISTINCT u) as co_purchase_count
        WHERE co_purchase_count > 2
        ORDER BY co_purchase_count DESC
        LIMIT $limit
        RETURN p2.id as id, p2.title as title, p2.price as price,
               p2.description as description, p2.images as images,
               co_purchase_count
        """
        
        try:
            results = await self.neo4j_client.query(
                cypher_query,
                {"limit": limit}
            )
            
            return [self._format_product(r) for r in results]
        except Exception as e:
            logger.error(f"Error in style combination search: {e}")
            return await self._standard_search(query, filters, limit)
    
    async def _search_by_user_preferences(self, query: str, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Search based on user preferences"""
        if not filters or 'user_id' not in filters:
            return await self._standard_search(query, filters, limit)
        
        user_id = filters['user_id']
        
        # Get user preferences and search accordingly
        cypher_query = """
        MATCH (u:User {id: $user_id})-[:HAS_PREFERENCE]->(pref:UserPreference)
        MATCH (p:Product)
        WHERE (pref.type = 'category' AND EXISTS {
            MATCH (p)-[:IN_CATEGORY]->(c:Category)
            WHERE c.title = pref.value
        })
        OR (pref.type = 'brand' AND EXISTS {
            MATCH (p)-[:TAGGED_WITH]->(t:Tag)
            WHERE t.title = pref.value
        })
        WITH p, COUNT(DISTINCT pref) as preference_match_score
        ORDER BY preference_match_score DESC, p.visited_num DESC
        LIMIT $limit
        RETURN p.id as id, p.title as title, p.price as price,
               p.description as description, p.images as images,
               preference_match_score
        """
        
        try:
            results = await self.neo4j_client.query(
                cypher_query,
                {"user_id": user_id, "limit": limit}
            )
            
            return [self._format_product(r) for r in results]
        except Exception as e:
            logger.error(f"Error in user preference search: {e}")
            return await self._standard_search(query, filters, limit)
    
    async def _standard_search(self, query: str, filters: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Standard search with filters"""
        # Build WHERE clauses
        where_clauses = ["p.price > 0"]
        params = {"limit": limit}
        
        if filters:
            if 'category' in filters:
                where_clauses.append("""
                EXISTS {
                    MATCH (p)-[:IN_CATEGORY]->(c:Category)
                    WHERE toLower(c.title) CONTAINS toLower($category)
                }
                """)
                params["category"] = filters['category']
            
            if 'min_price' in filters:
                where_clauses.append("p.price >= $min_price")
                params["min_price"] = filters['min_price']
            
            if 'max_price' in filters:
                where_clauses.append("p.price <= $max_price")
                params["max_price"] = filters['max_price']
        
        cypher_query = f"""
        MATCH (p:Product)
        WHERE {' AND '.join(where_clauses)}
        RETURN p.id as id, p.title as title, p.price as price,
               p.description as description, p.images as images,
               p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        try:
            results = await self.neo4j_client.query(cypher_query, params)
            return [self._format_product(r) for r in results]
        except Exception as e:
            logger.error(f"Error in standard search: {e}")
            return []
    
    def _format_product(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Format product record"""
        return {
            "id": record.get("id", ""),
            "title": record.get("title", "Unknown Product"),
            "price": record.get("price", 0.0),
            "description": record.get("description", ""),
            "images": self._parse_images(record.get("images", "[]")),
            "score": record.get("similarity_score", 0) or 
                    record.get("relevance_score", 0) or 
                    record.get("preference_match_score", 0) or 
                    record.get("co_purchase_count", 0) or 1.0,
            "source": "graph"
        }
    
    def _parse_images(self, images_str: str) -> List[str]:
        """Parse images string"""
        try:
            if images_str and images_str.startswith('['):
                return json.loads(images_str.replace("'", '"'))
            return []
        except:
            return []


class VibeBot(BaseAgent):
    """
    Natural language search specialist
    Uses vector embeddings for semantic search
    """
    
    def __init__(self, qdrant_retriever):
        super().__init__("VibeBot")
        self.retriever = qdrant_retriever
    
    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None, limit: int = 5) -> Tuple[List[Dict[str, Any]], float]:
        """
        Search using vector similarity
        Excels at understanding natural language nuances
        """
        start_time = time.time()
        
        try:
            # Enhance query with context
            enhanced_query = self._enhance_query(query, filters)
            
            # Perform vector search
            results = await self.retriever.search_by_natural_language(
                query=enhanced_query,
                limit=limit * 2  # Get more to filter
            )
            
            # Apply post-processing filters
            if filters:
                results = self._apply_filters(results, filters)
            
            # Limit results
            results = results[:limit]
            
            response_time = time.time() - start_time
            self.update_stats(response_time)
            
            logger.info(f"VibeBot completed search in {response_time:.2f}s, found {len(results)} products")
            return results, response_time
            
        except Exception as e:
            logger.error(f"VibeBot search error: {e}")
            response_time = time.time() - start_time
            self.update_stats(response_time)
            return [], response_time
    
    def _enhance_query(self, query: str, filters: Dict[str, Any]) -> str:
        """Enhance query with additional context"""
        enhanced_parts = [query]
        
        if filters:
            if 'occasion' in filters:
                enhanced_parts.append(f"for {filters['occasion']}")
            
            if 'style' in filters:
                enhanced_parts.append(f"in {filters['style']} style")
            
            if 'colors' in filters and filters['colors']:
                colors_str = " or ".join(filters['colors'])
                enhanced_parts.append(f"preferably in {colors_str}")
            
            if 'season' in filters:
                enhanced_parts.append(f"suitable for {filters['season']}")
        
        return " ".join(enhanced_parts)
    
    def _apply_filters(self, results: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply post-search filters"""
        filtered_results = []
        
        for product in results:
            # Price filter
            if 'min_price' in filters and product.get('price', 0) < filters['min_price']:
                continue
            
            if 'max_price' in filters and product.get('price', 0) > filters['max_price']:
                continue
            
            # Category filter
            if 'category' in filters:
                categories = product.get('categories', [])
                if not any(filters['category'].lower() in cat.lower() for cat in categories):
                    continue
            
            # Add to filtered results
            filtered_results.append(product)
        
        return filtered_results


class BattleAgents:
    """
    Manager for battle agents
    """
    
    def __init__(self, neo4j_client=None, qdrant_retriever=None):
        self.cypher_bot = CypherBot(neo4j_client) if neo4j_client else None
        self.vibe_bot = VibeBot(qdrant_retriever) if qdrant_retriever else None
        self.agents = []
        
        if self.cypher_bot:
            self.agents.append(self.cypher_bot)
        if self.vibe_bot:
            self.agents.append(self.vibe_bot)
        
        logger.info(f"BattleAgents initialized with {len(self.agents)} agents")
    
    async def battle_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Execute a battle search between agents
        
        Returns:
            Battle results with products from each agent
        """
        if not self.agents:
            logger.error("No agents available for battle")
            return {
                "error": "No agents available",
                "results": {}
            }
        
        # Run searches in parallel
        tasks = []
        for agent in self.agents:
            tasks.append(agent.search(query, filters, limit))
        
        # Wait for all agents to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        battle_results = {
            "query": query,
            "filters": filters,
            "timestamp": time.time(),
            "agents": {}
        }
        
        for i, agent in enumerate(self.agents):
            if isinstance(results[i], Exception):
                logger.error(f"Agent {agent.name} failed: {results[i]}")
                battle_results["agents"][agent.name] = {
                    "products": [],
                    "response_time": 0.0,
                    "error": str(results[i])
                }
            else:
                products, response_time = results[i]
                battle_results["agents"][agent.name] = {
                    "products": products,
                    "response_time": response_time,
                    "product_count": len(products)
                }
        
        return battle_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all agents"""
        stats = {}
        
        for agent in self.agents:
            stats[agent.name] = {
                "queries_processed": agent.stats["queries_processed"],
                "avg_response_time": agent.get_avg_response_time(),
                "wins": agent.stats["wins"],
                "losses": agent.stats["losses"],
                "draws": agent.stats["draws"]
            }
        
        return stats
