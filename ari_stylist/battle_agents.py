"""
Battle Agents
CypherBot and VibeBot are CAMEL agents that query their respective databases
Judge Ari is a CAMEL agent that evaluates the battle
"""

import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import time

# Import CAMEL-AI components
from camel_imports import (
    CAMEL_AVAILABLE,
    ChatAgent,
    BaseMessage,
    ModelType,
    SystemMessage
)

logger = logging.getLogger("battle_agents")


class CypherBotAgent:
    """
    CAMEL-AI agent that queries Neo4j using natural language to CYPHER.
    Clean, direct implementation.
    """
    
    def __init__(self, neo4j_client, model_type=None):
        """Initialize CypherBot as a CAMEL agent."""
        self.neo4j = neo4j_client
        self.name = "CypherBot"
        self.style = "graph-relationships"
        
        # Initialize CAMEL agent if available
        self.agent = None
        if CAMEL_AVAILABLE:
            try:
                system_message = """You are CypherBot, a data-driven fashion intelligence agent.
                Your specialty is finding products through Neo4j graph relationships.
                
                You excel at:
                1. Understanding user purchase patterns and relationships
                2. Finding products through collaborative filtering (users who bought X also bought Y)
                3. Traversing category and brand relationships
                4. Identifying trending items based on interaction patterns
                
                Focus on RELATIONSHIP-BASED recommendations using graph data."""
                
                model = model_type or ModelType.GPT_4
                self.agent = ChatAgent(
                    system_message=SystemMessage(content=system_message),
                    model=model,
                    message_window_size=10
                )
                
                logger.info("CypherBot CAMEL agent initialized")
                
            except Exception as e:
                logger.error(f"Failed to initialize CAMEL agent: {e}")
                self.agent = None
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using CAMEL agent to generate and execute Neo4j queries.
        Direct implementation, no wrappers.
        """
        logger.info(f"CypherBot searching for: '{query[:50]}...'")
        
        user_id = user_context.get('user_id') if user_context else None
        
        # Get strategy from CAMEL agent if available
        strategy = "fallback"
        if self.agent and CAMEL_AVAILABLE:
            try:
                context = self._build_agent_context(query, user_id, ml_intelligence, filters)
                user_msg = BaseMessage.make_user_message(role_name="User", content=context)
                response = self.agent.step(user_msg)
                strategy = response.msg.content if hasattr(response, 'msg') else str(response)
                logger.debug(f"CypherBot strategy determined")
            except Exception as e:
                logger.error(f"CAMEL agent error: {e}")
        
        # Execute strategy
        return await self._execute_strategy(strategy, query, user_id, limit, ml_intelligence)
    
    def _build_agent_context(
        self,
        query: str,
        user_id: Optional[str],
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """Build context for CAMEL agent."""
        context = f"""Find fashion products for: "{query}"
        User: {user_id or 'anonymous'}
        Filters: {json.dumps(filters) if filters else 'none'}
        """
        
        # Add ML intelligence if available
        if ml_intelligence and 'cypher_intel' in ml_intelligence:
            for source, data in ml_intelligence['cypher_intel'].items():
                if isinstance(data, dict):
                    # Add relevant intelligence
                    if 'user_segment' in data:
                        context += f"\nUser segment: {data['user_segment']}"
                    if 'clusters' in data:
                        context += f"\nRelevant clusters: {data.get('clusters', [])[:3]}"
        
        context += "\n\nDetermine the best graph-based search strategy."
        return context
    
    async def _execute_strategy(
        self,
        strategy: str,
        query: str,
        user_id: Optional[str],
        limit: int,
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute the search strategy."""
        results = []
        strategy_lower = strategy.lower()
        
        # Execute queries based on strategy
        try:
            # Collaborative filtering for users with history
            if user_id and ("collaborative" in strategy_lower or "similar" in strategy_lower):
                collab_results = await self._collaborative_filtering(user_id, query, limit)
                results.extend(collab_results)
            
            # Purchase patterns
            if user_id and "purchase" in strategy_lower:
                pattern_results = await self._purchase_patterns(user_id, query, limit)
                results.extend(pattern_results)
            
            # Category/brand search
            if "category" in strategy_lower or "brand" in strategy_lower:
                cat_results = await self._category_brand_search(query, limit, user_id)
                results.extend(cat_results)
            
            # Trending products
            if "trending" in strategy_lower or "popular" in strategy_lower:
                trend_results = await self._trending_products(query, limit)
                results.extend(trend_results)
            
            # General search as fallback or addition
            if len(results) < limit:
                general_results = await self._general_search(query, limit - len(results))
                results.extend(general_results)
                
        except Exception as e:
            logger.error(f"Strategy execution error: {e}")
            # Fallback to general search
            results = await self._general_search(query, limit)
        
        # Deduplicate and add metadata
        unique_results = self._deduplicate(results)
        
        for idx, product in enumerate(unique_results[:limit]):
            product['cypher_rank'] = idx + 1
            product['agent'] = 'CypherBot'
            product['search_method'] = 'graph_relationships'
            product['cypher_score'] = 1.0 - (idx * 0.1)
        
        return unique_results[:limit]
    
    async def _collaborative_filtering(self, user_id: str, query: str, limit: int) -> List[Dict[str, Any]]:
        """Collaborative filtering - users who bought X also bought Y."""
        try:
            cypher_query = """
            MATCH (u:User {id: $user_id})-[:PURCHASED]->(p:Product)
            WITH p
            MATCH (other:User)-[:PURCHASED]->(p)
            WHERE other.id <> $user_id
            MATCH (other)-[:PURCHASED]->(rec:Product)
            WHERE NOT (u)-[:PURCHASED]->(rec)
            AND (rec.description CONTAINS $query OR rec.title CONTAINS $query 
                 OR rec.category CONTAINS $query)
            WITH rec, COUNT(DISTINCT other) as score
            RETURN rec.id as id, rec.title as title, rec.description as description,
                   rec.price as price, rec.category as category, rec.brand as brand,
                   score
            ORDER BY score DESC
            LIMIT $limit
            """
            
            # Try different method names
            if hasattr(self.neo4j, 'query'):
                results = await self.neo4j.query(cypher_query, {"user_id": user_id, "query": query, "limit": limit})
            elif hasattr(self.neo4j, 'execute_query'):
                results = await self.neo4j.execute_query(cypher_query, {"user_id": user_id, "query": query, "limit": limit})
            elif hasattr(self.neo4j, 'run'):
                results = await self.neo4j.run(cypher_query, {"user_id": user_id, "query": query, "limit": limit})
            else:
                logger.warning("No suitable Neo4j query method found")
                return []
            
            # Normalize results
            products = []
            for r in results if results else []:
                product = dict(r) if not isinstance(r, dict) else r
                product['cypher_reason'] = f"Collaborative filtering (score: {product.get('score', 0)})"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Collaborative filtering failed: {e}")
            return []
    
    async def _purchase_patterns(self, user_id: str, query: str, limit: int) -> List[Dict[str, Any]]:
        """Find products based on purchase patterns."""
        try:
            cypher_query = """
            MATCH (u:User {id: $user_id})-[:PURCHASED]->(p:Product)
            WITH p, u
            MATCH (p)<-[:PURCHASED]-(other:User)-[:PURCHASED]->(rec:Product)
            WHERE NOT (u)-[:PURCHASED]->(rec)
            AND (rec.description CONTAINS $query OR rec.title CONTAINS $query)
            WITH rec, COUNT(*) as co_purchase_count
            RETURN rec.id as id, rec.title as title, rec.description as description,
                   rec.price as price, rec.category as category, rec.brand as brand,
                   co_purchase_count
            ORDER BY co_purchase_count DESC
            LIMIT $limit
            """
            
            # Execute with available method
            if hasattr(self.neo4j, 'query'):
                results = await self.neo4j.query(cypher_query, {"user_id": user_id, "query": query, "limit": limit})
            elif hasattr(self.neo4j, 'execute_query'):
                results = await self.neo4j.execute_query(cypher_query, {"user_id": user_id, "query": query, "limit": limit})
            else:
                return []
            
            products = []
            for r in results if results else []:
                product = dict(r) if not isinstance(r, dict) else r
                product['cypher_reason'] = "Frequently bought together"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Purchase pattern query failed: {e}")
            return []
    
    async def _category_brand_search(self, query: str, limit: int, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search by category and brand."""
        try:
            if user_id:
                cypher_query = """
                MATCH (u:User {id: $user_id})-[:PURCHASED|LIKED|VIEWED]->(p:Product)
                WITH DISTINCT p.category as category, p.brand as brand
                MATCH (rec:Product)
                WHERE (rec.category IN [category] OR rec.brand IN [brand])
                AND (rec.description CONTAINS $query OR rec.title CONTAINS $query)
                RETURN DISTINCT rec.id as id, rec.title as title, rec.description as description,
                       rec.price as price, rec.category as category, rec.brand as brand
                LIMIT $limit
                """
                params = {"user_id": user_id, "query": query, "limit": limit}
            else:
                cypher_query = """
                MATCH (p:Product)
                WHERE p.description CONTAINS $query OR p.title CONTAINS $query
                   OR p.category CONTAINS $query OR p.brand CONTAINS $query
                RETURN p.id as id, p.title as title, p.description as description,
                       p.price as price, p.category as category, p.brand as brand
                LIMIT $limit
                """
                params = {"query": query, "limit": limit}
            
            # Execute with available method
            if hasattr(self.neo4j, 'query'):
                results = await self.neo4j.query(cypher_query, params)
            elif hasattr(self.neo4j, 'execute_query'):
                results = await self.neo4j.execute_query(cypher_query, params)
            else:
                return []
            
            products = []
            for r in results if results else []:
                product = dict(r) if not isinstance(r, dict) else r
                product['cypher_reason'] = "Category/brand match"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Category/brand search failed: {e}")
            return []
    
    async def _trending_products(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Find trending products."""
        try:
            cypher_query = """
            MATCH (p:Product)<-[r:PURCHASED|LIKED|VIEWED]-(u:User)
            WHERE r.timestamp > datetime() - duration('P7D')
            AND (p.description CONTAINS $query OR p.title CONTAINS $query)
            WITH p, COUNT(DISTINCT u) as trending_score
            RETURN p.id as id, p.title as title, p.description as description,
                   p.price as price, p.category as category, p.brand as brand,
                   trending_score
            ORDER BY trending_score DESC
            LIMIT $limit
            """
            
            # Execute with available method
            if hasattr(self.neo4j, 'query'):
                results = await self.neo4j.query(cypher_query, {"query": query, "limit": limit})
            elif hasattr(self.neo4j, 'execute_query'):
                results = await self.neo4j.execute_query(cypher_query, {"query": query, "limit": limit})
            else:
                return []
            
            products = []
            for r in results if results else []:
                product = dict(r) if not isinstance(r, dict) else r
                product['cypher_reason'] = f"Trending (score: {product.get('trending_score', 0)})"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Trending query failed: {e}")
            return []
    
    async def _general_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """General product search."""
        try:
            # First try CYPHER query
            cypher_query = """
            MATCH (p:Product)
            WHERE p.description CONTAINS $query 
               OR p.title CONTAINS $query
               OR p.category CONTAINS $query
               OR p.brand CONTAINS $query
            RETURN p.id as id, p.title as title, p.description as description,
                   p.price as price, p.category as category, p.brand as brand
            LIMIT $limit
            """
            
            if hasattr(self.neo4j, 'query'):
                results = await self.neo4j.query(cypher_query, {"query": query, "limit": limit})
            elif hasattr(self.neo4j, 'execute_query'):
                results = await self.neo4j.execute_query(cypher_query, {"query": query, "limit": limit})
            elif hasattr(self.neo4j, 'search_products'):
                # Fallback to direct search method
                results = await self.neo4j.search_products(query, limit=limit)
            else:
                return []
            
            products = []
            for r in results if results else []:
                product = dict(r) if not isinstance(r, dict) else r
                product['cypher_reason'] = "Graph search match"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"General search failed: {e}")
            return []
    
    def _deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate products."""
        seen = set()
        unique = []
        for product in results:
            if product.get('id') and product['id'] not in seen:
                seen.add(product['id'])
                unique.append(product)
        return unique


class VibeBotAgent:
    """
    CAMEL-AI agent that queries Qdrant using embeddings.
    Clean, direct implementation.
    """
    
    def __init__(self, qdrant_client, model_type=None):
        """Initialize VibeBot as a CAMEL agent."""
        self.qdrant = qdrant_client
        self.name = "VibeBot"
        self.style = "aesthetic-similarity"
        
        # Initialize CAMEL agent if available
        self.agent = None
        if CAMEL_AVAILABLE:
            try:
                system_message = """You are VibeBot, an aesthetic-driven fashion intelligence agent.
                Your specialty is finding products through visual and semantic similarity.
                
                You excel at:
                1. Understanding style, aesthetics, and visual harmony
                2. Finding products with similar "vibes" using embeddings
                3. Matching colors, patterns, and design elements
                4. Identifying trending aesthetics and styles
                
                Focus on AESTHETIC and STYLE-BASED recommendations."""
                
                model = model_type or ModelType.GPT_4
                self.agent = ChatAgent(
                    system_message=SystemMessage(content=system_message),
                    model=model,
                    message_window_size=10
                )
                
                logger.info("VibeBot CAMEL agent initialized")
                
            except Exception as e:
                logger.error(f"Failed to initialize CAMEL agent: {e}")
                self.agent = None
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using CAMEL agent to guide Qdrant embedding search.
        Direct implementation, no wrappers.
        """
        logger.info(f"VibeBot searching for: '{query[:50]}...'")
        
        # Get strategy from CAMEL agent if available
        strategy = "fallback"
        if self.agent and CAMEL_AVAILABLE:
            try:
                context = self._build_agent_context(query, ml_intelligence, filters, user_context)
                user_msg = BaseMessage.make_user_message(role_name="User", content=context)
                response = self.agent.step(user_msg)
                strategy = response.msg.content if hasattr(response, 'msg') else str(response)
                logger.debug(f"VibeBot strategy determined")
            except Exception as e:
                logger.error(f"CAMEL agent error: {e}")
        
        # Execute strategy
        return await self._execute_strategy(strategy, query, limit, filters, ml_intelligence)
    
    def _build_agent_context(
        self,
        query: str,
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """Build context for CAMEL agent."""
        context = f"""Find fashion products for: "{query}"
        Filters: {json.dumps(filters) if filters else 'none'}
        """
        
        # Add ML intelligence if available
        if ml_intelligence and 'vibe_intel' in ml_intelligence:
            for source, data in ml_intelligence['vibe_intel'].items():
                if isinstance(data, dict):
                    if 'visual_features' in data:
                        visual = data['visual_features']
                        if 'colors' in visual:
                            context += f"\nColors: {visual['colors'][:3]}"
                        if 'style_attributes' in visual:
                            context += f"\nStyles: {visual['style_attributes'][:3]}"
        
        context += "\n\nDetermine the best aesthetic-based search strategy."
        return context
    
    async def _execute_strategy(
        self,
        strategy: str,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute the search strategy."""
        results = []
        
        # Enhance query based on strategy
        enhanced_query = self._enhance_query(query, strategy)
        
        try:
            # Primary semantic search
            semantic_results = await self._semantic_search(enhanced_query, limit * 2, filters)
            results.extend(semantic_results)
            
            # Color-based search if ML intelligence suggests it
            if ml_intelligence and 'vibe_intel' in ml_intelligence:
                for source, data in ml_intelligence['vibe_intel'].items():
                    if isinstance(data, dict) and 'visual_features' in data:
                        colors = data['visual_features'].get('colors', [])
                        if colors:
                            color_results = await self._color_search(colors[:3], limit // 2, filters)
                            results.extend(color_results)
                            break
            
            # Style-based search if strategy mentions styles
            style_keywords = self._extract_styles(strategy)
            if style_keywords:
                style_query = f"{query} {' '.join(style_keywords)}"
                style_results = await self._semantic_search(style_query, limit // 2, filters)
                results.extend(style_results)
                
        except Exception as e:
            logger.error(f"Strategy execution error: {e}")
            # Fallback to basic search
            results = await self._semantic_search(query, limit, filters)
        
        # Deduplicate and score
        unique_results = self._deduplicate_and_score(results, query, strategy)
        
        # Add metadata
        for idx, product in enumerate(unique_results[:limit]):
            product['vibe_rank'] = idx + 1
            product['agent'] = 'VibeBot'
            product['search_method'] = 'embedding_similarity'
            product['vibe_score'] = 1.0 - (idx * 0.1)
        
        return unique_results[:limit]
    
    async def _semantic_search(self, query: str, limit: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Perform semantic embedding search."""
        try:
            # Try different method names
            if hasattr(self.qdrant, 'search_by_natural_language'):
                results = await self.qdrant.search_by_natural_language(query=query, limit=limit, filters=filters)
            elif hasattr(self.qdrant, 'search'):
                results = await self.qdrant.search(query=query, limit=limit, filters=filters)
            elif hasattr(self.qdrant, 'search_products'):
                results = await self.qdrant.search_products(query, limit=limit)
            else:
                logger.warning("No suitable Qdrant search method found")
                return []
            
            # Normalize results
            products = []
            for r in results if results else []:
                product = dict(r) if not isinstance(r, dict) else r
                product['vibe_reason'] = "Semantic similarity"
                products.append(product)
            
            return products
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    async def _color_search(self, colors: List[str], limit: int, filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Search by color."""
        try:
            all_results = []
            
            if hasattr(self.qdrant, 'get_products_by_filter'):
                for color in colors:
                    try:
                        results = await self.qdrant.get_products_by_filter(colors=[color], limit=limit // len(colors))
                        for r in results:
                            product = dict(r) if not isinstance(r, dict) else r
                            product['vibe_reason'] = f"Color match ({color})"
                            all_results.append(product)
                    except:
                        pass
            
            return all_results
            
        except Exception as e:
            logger.error(f"Color search failed: {e}")
            return []
    
    def _enhance_query(self, query: str, strategy: str) -> str:
        """Enhance query based on strategy."""
        enhanced = query
        
        style_words = ['minimalist', 'bohemian', 'elegant', 'casual', 'formal', 
                      'vintage', 'modern', 'classic', 'edgy', 'romantic']
        
        strategy_lower = strategy.lower()
        for style in style_words:
            if style in strategy_lower:
                enhanced += f" {style}"
        
        return enhanced
    
    def _extract_styles(self, strategy: str) -> List[str]:
        """Extract style keywords from strategy."""
        keywords = []
        style_indicators = ['aesthetic', 'vibe', 'style', 'look', 'feel',
                          'color', 'texture', 'pattern', 'design']
        
        strategy_lower = strategy.lower()
        for indicator in style_indicators:
            if indicator in strategy_lower:
                keywords.append(indicator)
        
        return keywords[:3]
    
    def _deduplicate_and_score(self, results: List[Dict[str, Any]], query: str, strategy: str) -> List[Dict[str, Any]]:
        """Deduplicate and score results."""
        seen = set()
        unique = []
        
        for product in results:
            if product.get('id') and product['id'] not in seen:
                seen.add(product['id'])
                
                # Simple scoring
                score = 0.5
                
                if 'semantic' in product.get('vibe_reason', '').lower():
                    score += 0.3
                
                if 'color' in product.get('vibe_reason', '').lower():
                    score += 0.2
                
                if product.get('images') and len(product['images']) > 2:
                    score += 0.1
                
                product['vibe_score'] = min(score, 1.0)
                unique.append(product)
        
        # Sort by score
        unique.sort(key=lambda x: x.get('vibe_score', 0), reverse=True)
        
        return unique


class JudgeAriAgent:
    """
    CAMEL-AI powered Judge that evaluates battle results.
    Clean, direct implementation.
    """
    
    def __init__(self, model_type=None):
        """Initialize Judge Ari as a CAMEL agent."""
        self.name = "Judge Ari"
        self.agent = None
        
        if CAMEL_AVAILABLE:
            try:
                system_message = """You are Judge Ari, the ultimate fashion arbiter.
                You evaluate recommendations from CypherBot (data-driven) and VibeBot (aesthetic-driven).
                
                Your role:
                1. Evaluate products from both agents fairly
                2. Balance data/relationships with aesthetics/style
                3. Consider practical and creative factors
                4. Select the best overall recommendations
                
                Focus on creating a balanced, high-quality selection."""
                
                model = model_type or ModelType.GPT_4
                self.agent = ChatAgent(
                    system_message=SystemMessage(content=system_message),
                    model=model,
                    message_window_size=10
                )
                
                logger.info("Judge Ari CAMEL agent initialized")
                
            except Exception as e:
                logger.error(f"Failed to initialize Judge Ari: {e}")
                self.agent = None
    
    async def evaluate(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        ml_context: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Evaluate battle results and select winners."""
        logger.info(f"Judge Ari evaluating: {len(cypher_results)} vs {len(vibe_results)} results")
        
        # Get judgment from CAMEL agent if available
        judgment = None
        if self.agent and CAMEL_AVAILABLE:
            try:
                context = self._build_context(cypher_results, vibe_results, query, limit)
                user_msg = BaseMessage.make_user_message(role_name="User", content=context)
                response = self.agent.step(user_msg)
                judgment = response.msg.content if hasattr(response, 'msg') else str(response)
                logger.debug("Judge Ari judgment received")
            except Exception as e:
                logger.error(f"Judge CAMEL error: {e}")
        
        # Execute judgment
        return self._execute_judgment(judgment, cypher_results, vibe_results, limit)
    
    def _build_context(
        self,
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        query: str,
        limit: int
    ) -> str:
        """Build context for Judge evaluation."""
        context = f"""Evaluate battle results for: "{query}"
        
        CYPHERBOT (Data-driven): {len(cypher_results)} results
        Top products: {[p.get('title', 'Unknown')[:30] for p in cypher_results[:5]]}
        
        VIBEBOT (Aesthetic): {len(vibe_results)} results  
        Top products: {[p.get('title', 'Unknown')[:30] for p in vibe_results[:5]]}
        
        Select the TOP {limit} products considering balance and quality."""
        
        return context
    
    def _execute_judgment(
        self,
        judgment: Optional[str],
        cypher_results: List[Dict[str, Any]],
        vibe_results: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute the judgment and select winners."""
        # Combine all products
        all_products = {}
        
        # Add CypherBot results
        for product in cypher_results:
            if product.get('id'):
                all_products[product['id']] = product
                product['agents'] = ['CypherBot']
        
        # Add VibeBot results
        for product in vibe_results:
            if product.get('id'):
                if product['id'] in all_products:
                    # Both agents found it - consensus bonus
                    all_products[product['id']]['agents'].append('VibeBot')
                    all_products[product['id']]['combined_score'] = (
                        all_products[product['id']].get('cypher_score', 0.5) +
                        product.get('vibe_score', 0.5)
                    ) / 2 * 1.2  # 20% bonus for consensus
                else:
                    product['agents'] = ['VibeBot']
                    all_products[product['id']] = product
        
        # Calculate judge scores
        for product_id, product in all_products.items():
            base_score = 0.5
            
            # Consensus bonus
            if len(product.get('agents', [])) == 2:
                base_score += 0.2
            
            # Agent scores
            if 'CypherBot' in product.get('agents', []):
                base_score += product.get('cypher_score', 0.5) * 0.3
            if 'VibeBot' in product.get('agents', []):
                base_score += product.get('vibe_score', 0.5) * 0.3
            
            # Check if mentioned in judgment
            if judgment and product.get('title', '').lower() in judgment.lower():
                base_score += 0.3
            
            product['judge_score'] = min(base_score, 1.0)
        
        # Sort by judge score
        sorted_products = sorted(
            all_products.values(),
            key=lambda x: x.get('judge_score', 0),
            reverse=True
        )
        
        # Select winners
        winners = sorted_products[:limit]
        
        # Add final metadata
        for idx, product in enumerate(winners):
            product['final_rank'] = idx + 1
            product['winning_agents'] = product.get('agents', [])
            
            # Add reasoning
            if len(product.get('agents', [])) == 2:
                product['judge_reasoning'] = "Strong consensus between both agents"
            elif 'CypherBot' in product.get('agents', []):
                product['judge_reasoning'] = "Strong data and relationship match"
            elif 'VibeBot' in product.get('agents', []):
                product['judge_reasoning'] = "Excellent aesthetic and style match"
            else:
                product['judge_reasoning'] = "Selected for overall relevance"
        
        return winners
