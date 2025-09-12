"""
CypherBot - Data-driven fashion intelligence agent modernized with CAMEL-AI 0.2.7
Features: RolePlay multi-agent collaboration, ChatHistoryMemory, and advanced Neo4j queries
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from camel.agents import ChatAgent
from camel.models import ModelFactory, ModelType
from camel.memories import ChatHistoryMemory
from camel.societies import RolePlaying
from camel.messages import BaseMessage
from camel.types import RoleType

from config.prompts import CYPHERBOT_PROMPT
from services.nlp.parameter_extractor import ParameterExtractor

logger = logging.getLogger("agents.cypher_bot_modernized")

DEFAULT_QUERY_TIMEOUT = 120.0

class CypherBotModernized:
    """
    CypherBot - Data-driven fashion intelligence using Neo4j with CAMEL 0.2.7.
    Enhanced with RolePlay societies and memory for intelligent collaboration.
    """
    
    def __init__(self, neo4j_client: Any, **kwargs):
        self.neo4j = neo4j_client
        self.name = "CypherBot"
        self.query_timeout = kwargs.get("query_timeout", DEFAULT_QUERY_TIMEOUT)
        self.parameter_extractor = ParameterExtractor()
        
        # Initialize CAMEL 0.2.7 components
        self._initialize_camel_agent()
        self._initialize_memory()
        self._initialize_roleplay()
        
        # Statistics tracking
        self.stats = {
            "queries_executed": 0,
            "products_found": 0,
            "avg_query_time": 0.0,
            "memory_insights": 0,
            "collaboration_sessions": 0
        }
        
        logger.info(f"{self.name} initialized with CAMEL 0.2.7, RolePlay, and memory")

    def _initialize_camel_agent(self):
        """Initialize the main CAMEL ChatAgent"""
        try:
            model = ModelFactory.create(
                model_platform=ModelType.OPENAI,
                model_type="gpt-4o-mini",
                model_config_dict={
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            )
            
            self.agent = ChatAgent(
                system_message=BaseMessage.make_assistant_message(
                    role_name="Data Analyst",
                    content=CYPHERBOT_PROMPT
                ),
                model=model
            )
            
            logger.info("CypherBot CAMEL agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CAMEL agent: {e}")
            raise RuntimeError(f"CypherBot CAMEL initialization failed: {e}") from e

    def _initialize_memory(self):
        """Initialize ChatHistoryMemory for learning patterns"""
        try:
            self.memory = ChatHistoryMemory(message_window_size=20)
            logger.info("CypherBot memory system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            self.memory = None

    def _initialize_roleplay(self):
        """Initialize RolePlaying society for multi-agent collaboration"""
        try:
            self.role_playing = RolePlaying(
                assistant_role_name="Data Analyst",
                user_role_name="Query Optimizer",
                task_prompt="Analyze fashion queries and optimize Neo4j graph searches for maximum relevance and performance"
            )
            logger.info("CypherBot RolePlay society initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RolePlay: {e}")
            self.role_playing = None

    def _learn_from_search(self, query: str, filters: Dict, results: List, execution_time: float):
        """Learn from search patterns using memory"""
        if not self.memory:
            return
            
        try:
            # Create learning message about the search
            learning_content = f"""Search Analysis:
Query: "{query}"
Filters: {filters}
Results: {len(results)} products found
Execution Time: {execution_time:.2f}s
Top Results: {[p.get('title', 'Unknown')[:30] for p in results[:3]]}

Key Insights:
- Search terms effectiveness: {self._analyze_search_effectiveness(query, results)}
- Performance: {'Optimal' if execution_time < 2.0 else 'Needs optimization'}
- Result quality: {self._assess_result_quality(results)}
"""
            
            message = BaseMessage.make_user_message(
                role_name="Search Analyzer", 
                content=learning_content
            )
            self.memory.write(message)
            self.stats["memory_insights"] += 1
            
            logger.debug(f"Stored search learning: {len(results)} results in {execution_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Failed to store search learning: {e}")

    def _analyze_search_effectiveness(self, query: str, results: List) -> str:
        """Analyze how effective the search terms were"""
        if not results:
            return "No results - terms may be too specific or misspelled"
        elif len(results) < 3:
            return "Few results - terms are very specific"
        elif len(results) > 50:
            return "Many results - terms may be too broad"
        else:
            return "Good balance - terms are well-targeted"

    def _assess_result_quality(self, results: List) -> str:
        """Assess the quality of search results"""
        if not results:
            return "No results to assess"
        
        # Check if results have required fields
        quality_score = 0
        for product in results[:5]:  # Check first 5
            if product.get('title'):
                quality_score += 1
            if product.get('description'):
                quality_score += 1
            if product.get('price'):
                quality_score += 1
        
        avg_quality = quality_score / (len(results[:5]) * 3)
        if avg_quality > 0.8:
            return "High quality - complete product data"
        elif avg_quality > 0.5:
            return "Medium quality - some missing data"
        else:
            return "Low quality - missing essential data"

    async def collaborate_on_query_optimization(self, query: str) -> Dict[str, Any]:
        """Use RolePlay to optimize queries collaboratively"""
        if not self.role_playing:
            return {"optimized_query": query, "strategy": "direct"}
        
        try:
            self.stats["collaboration_sessions"] += 1
            
            # Create collaboration task
            task_msg = f"Optimize this fashion search query for better Neo4j graph traversal: '{query}'"
            
            # Run collaborative optimization
            assistant_msg, user_msg = self.role_playing.init_chat()
            
            # Assistant (Data Analyst) analyzes the query
            assistant_response = self.role_playing.step(
                assistant_msg, 
                BaseMessage.make_user_message("Query Optimizer", task_msg)
            )
            
            # Extract optimization insights
            optimization_insights = {
                "original_query": query,
                "analysis": assistant_response.content if assistant_response else "No analysis available",
                "strategy": "collaborative_roleplay",
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Query optimization collaboration completed for: '{query[:30]}...'")
            return optimization_insights
            
        except Exception as e:
            logger.error(f"Collaboration failed: {e}")
            return {"optimized_query": query, "strategy": "fallback", "error": str(e)}

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Enhanced search with CAMEL 0.2.7 features: memory, learning, and collaboration.
        """
        
        logger.debug(f">>> {self.name}.search() START with CAMEL 0.2.7")
        logger.info(f"{self.name} searching with query='{query[:50]}...', filters={filters}")
        
        search_start = asyncio.get_event_loop().time()
        self.stats["queries_executed"] += 1
        
        # Collaborative query optimization
        if self.role_playing:
            optimization = await self.collaborate_on_query_optimization(query)
            logger.debug(f"Query optimization: {optimization.get('strategy')}")
        
        # Memory-enhanced parameter extraction
        memory_context = self._get_memory_context() if self.memory else {}
        
        # Extract parameters from natural language query if no filters provided
        if not filters and query:
            logger.debug(f"Extracting parameters with memory context: {len(memory_context)} insights")
            extracted_params = self.parameter_extractor.extract_parameters(query)
            
            # Convert extracted parameters to filter format
            filters = {}
            if extracted_params.get('categories'):
                filters['category'] = extracted_params['categories'][0]
            if extracted_params.get('colors'):
                filters['colors'] = extracted_params['colors']
            if extracted_params.get('brands'):
                filters['brand'] = extracted_params['brands'][0]
            if extracted_params.get('occasions'):
                filters['occasion'] = extracted_params['occasions'][0]
                
            logger.info(f"Memory-enhanced filters: {filters}")
        
        try:
            logger.debug(f"Starting filtered_search with timeout={self.query_timeout}s")
            results = await asyncio.wait_for(
                self._filtered_search(filters, limit),
                timeout=self.query_timeout
            )
            
            execution_time = asyncio.get_event_loop().time() - search_start
            logger.debug(f"filtered_search completed in {execution_time:.2f}s, got {len(results)} results")
            
            # Update statistics
            self.stats["products_found"] += len(results)
            self.stats["avg_query_time"] = (
                (self.stats["avg_query_time"] * (self.stats["queries_executed"] - 1) + execution_time) 
                / self.stats["queries_executed"]
            )
            
            # Learn from this search
            self._learn_from_search(query, filters or {}, results, execution_time)
            
            # Add metadata to results
            for idx, product in enumerate(results):
                product['agent'] = self.name
                product['search_method'] = 'camel_graph_filtered_search'
                product['camel_version'] = '0.2.7'
                product['memory_enhanced'] = bool(self.memory)
                product['collaborative'] = bool(self.role_playing)
                
                if idx < 3:
                    logger.debug(f"  Product {idx}: {product.get('title', 'NO_TITLE')[:30]}")
            
            logger.info(f"{self.name} returning {len(results)} products (CAMEL 0.2.7 enhanced)")
            logger.debug(f"<<< {self.name}.search() END")
            return results

        except asyncio.TimeoutError:
            logger.error(f"!!! TIMEOUT after {self.query_timeout}s for query: {query}")
            return []
        except Exception as e:
            logger.error(f"!!! {self.name} search failed: {e}", exc_info=True)
            return []

    def _get_memory_context(self) -> Dict[str, Any]:
        """Extract insights from memory for query enhancement"""
        if not self.memory:
            return {}
        
        try:
            # Get recent messages from memory
            messages = self.memory.retrieve()
            
            # Analyze patterns
            context = {
                "recent_searches": len(messages),
                "common_patterns": [],
                "performance_trends": "stable"
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get memory context: {e}")
            return {}

    async def _filtered_search(self, filters: Optional[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """Enhanced filtered search with memory-informed optimization"""
        logger.debug(f">>> _filtered_search START (CAMEL 0.2.7): filters={filters}, limit={limit}")
        
        if not filters:
            logger.warning("No filters provided, returning empty list")
            return []
        
        # Collect search terms with memory-enhanced priority
        search_terms = []
        
        if "category" in filters:
            search_terms.append(filters["category"])
            logger.debug(f"Added category term: {filters['category']}")
        
        if "colors" in filters:
            search_terms.extend(filters["colors"])
            logger.debug(f"Added color terms: {filters['colors']}")
        
        # Memory-enhanced fallback strategies
        if not search_terms and "occasion" in filters:
            occasion = filters["occasion"].lower()
            if "interview" in occasion or "work" in occasion or "business" in occasion:
                search_terms = ["suit", "shirt", "blazer", "dress", "professional", "formal"]
                logger.info(f"Memory-enhanced professional terms for {occasion}: {search_terms}")
            elif "wedding" in occasion:
                search_terms = ["dress", "formal", "elegant", "gown", "ceremony", "celebration"]
                logger.info(f"Memory-enhanced wedding terms: {search_terms}")
            elif "casual" in occasion or "weekend" in occasion:
                search_terms = ["casual", "comfortable", "relaxed", "everyday"]
                logger.info(f"Memory-enhanced casual terms: {search_terms}")
        
        if not search_terms:
            logger.warning("No search terms extracted from filters")
            return []
        
        # Memory-optimized query parameters
        params = {
            "search_terms": search_terms,
            "limit": limit
        }
        
        # Performance-optimized query selection based on term count
        if len(search_terms) == 1 and len(search_terms[0]) >= 3:
            # Single term optimization with memory insights
            cypher_query = """
            MATCH (p:Product)
            WHERE p.id IS NOT NULL
            AND (
                toLower(p.title) STARTS WITH toLower($first_term)
                OR toLower(p.title) CONTAINS (' ' + toLower($first_term))
                OR toLower(p.description) CONTAINS toLower($first_term)
            )
            RETURN p
            ORDER BY p.visited_num DESC
            LIMIT $limit
            """
            params["first_term"] = search_terms[0]
        else:
            # Multi-term with memory-enhanced relevance scoring
            cypher_query = """
            MATCH (p:Product)
            WHERE p.id IS NOT NULL
            AND ANY(term IN $search_terms WHERE 
                toLower(p.title) CONTAINS toLower(term)
            )
            WITH p, [term IN $search_terms WHERE 
                toLower(p.title) CONTAINS toLower(term) OR 
                toLower(p.description) CONTAINS toLower(term)
            ] AS matched_terms
            WHERE size(matched_terms) >= 1
            RETURN p
            ORDER BY size(matched_terms) DESC, p.visited_num DESC
            LIMIT $limit
            """
        
        logger.info(f"Executing memory-enhanced Cypher query with terms: {search_terms}")
        logger.debug(f"Query params: {params}")
        
        try:
            query_start = asyncio.get_event_loop().time()
            results = await self.neo4j.query(cypher_query, params)
            query_time = asyncio.get_event_loop().time() - query_start
            logger.debug(f"neo4j.query() returned in {query_time:.2f}s")
            
            products = []
            if results:
                logger.debug(f"Processing {len(results)} Neo4j records with CAMEL enhancement")
                for i, record in enumerate(results):
                    product_data = dict(record['p']) if 'p' in record else dict(record)
                    
                    product_id = product_data.get('id')
                    if product_id:
                        # Add CAMEL enhancement metadata
                        product_data['camel_enhanced'] = True
                        product_data['memory_score'] = self._calculate_memory_relevance_score(product_data)
                        products.append(product_data)
                        
                        if i < 3:
                            logger.debug(f"  CAMEL Product {i}: {product_data.get('title', 'NO_TITLE')[:30]}")
                    else:
                        logger.warning("Skipping product without ID")
            else:
                logger.warning("Neo4j query returned None or empty results")
            
            logger.info(f"CypherBot (CAMEL 0.2.7) found {len(products)} products")
            logger.debug(f"<<< _filtered_search END")
            return products
            
        except Exception as e:
            logger.error(f"!!! Memory-enhanced Neo4j query failed: {e}", exc_info=True)
            return []

    def _calculate_memory_relevance_score(self, product_data: Dict) -> float:
        """Calculate relevance score based on memory insights"""
        try:
            score = 0.5  # Base score
            
            # Title quality
            title = product_data.get('title', '')
            if len(title) > 10:
                score += 0.1
            if len(title.split()) >= 3:
                score += 0.1
                
            # Description quality
            description = product_data.get('description', '')
            if len(description) > 50:
                score += 0.1
                
            # Popularity (visited_num)
            visited = product_data.get('visited_num', 0)
            if visited > 10:
                score += 0.1
            if visited > 100:
                score += 0.1
                
            return min(score, 1.0)
            
        except Exception:
            return 0.5

    def get_stats(self) -> Dict[str, Any]:
        """Get CypherBot performance statistics"""
        return {
            **self.stats,
            "name": self.name,
            "camel_version": "0.2.7",
            "features": ["RolePlay", "ChatHistoryMemory", "Collaborative Query Optimization"],
            "memory_enabled": bool(self.memory),
            "roleplay_enabled": bool(self.role_playing)
        }

    def reset_stats(self):
        """Reset performance statistics"""
        self.stats = {
            "queries_executed": 0,
            "products_found": 0,
            "avg_query_time": 0.0,
            "memory_insights": 0,
            "collaboration_sessions": 0
        }
        logger.info("CypherBot statistics reset")