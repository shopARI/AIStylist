import logging
import asyncio
from typing import Dict, List, Any, Optional

logger = logging.getLogger("agents.cypher_bot")

from lib.camel.v070 import create_battle_agent, CAMEL_AVAILABLE
from config.prompts import CYPHERBOT_PROMPT
from services.nlp.parameter_extractor import ParameterExtractor

DEFAULT_QUERY_TIMEOUT = 120.0  # Extended for 20-30M node graph traversals

class CypherBotAgent:
    """
    CypherBot - Data-driven fashion intelligence using Neo4j.
    This version is corrected to use structured filters for precise queries.
    """
    
    def __init__(self, neo4j_client: Any, **kwargs):
        self.neo4j = neo4j_client
        self.name = "CypherBot"
        self.query_timeout = kwargs.get("query_timeout", DEFAULT_QUERY_TIMEOUT)
        self.parameter_extractor = ParameterExtractor()

        if not CAMEL_AVAILABLE:
            raise RuntimeError("CAMEL 0.2.70+ is required for CypherBot")
        
        try:
            self.agent = create_battle_agent(name=self.name, system_message=CYPHERBOT_PROMPT)
            logger.info(f"{self.name} initialized with parameter extraction")
        except Exception as e:
            logger.error(f"Failed to initialize {self.name}: {e}")
            raise RuntimeError(f"CypherBot initialization failed: {e}") from e

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using graph relationships and precise filters.
        """
        
        logger.debug(f">>> {self.name}.search() START")
        logger.info(f"{self.name} searching with query='{query[:50]}...', filters={filters}")
        
        # Extract parameters from natural language query if no filters provided
        if not filters and query:
            logger.debug(f"No filters provided, extracting from query: '{query}'")
            extracted_params = self.parameter_extractor.extract_parameters(query)
            
            # Convert extracted parameters to filter format
            filters = {}
            if extracted_params.get('categories'):
                filters['category'] = extracted_params['categories'][0]  # Use first category
            if extracted_params.get('colors'):
                filters['colors'] = extracted_params['colors']
            if extracted_params.get('brands'):  # Check if brands exist
                filters['brand'] = extracted_params['brands'][0]
            if extracted_params.get('occasions'):
                filters['occasion'] = extracted_params['occasions'][0]  # Pass occasion for fallback
                
            logger.info(f"Extracted filters from query: {filters}")
        
        try:
            logger.debug(f"Starting filtered_search with timeout={self.query_timeout}s")
            results = await asyncio.wait_for(
                self._filtered_search(filters, limit),
                timeout=self.query_timeout
            )
            logger.debug(f"filtered_search completed, got {len(results)} results")
            
            # Add metadata to the results
            for idx, product in enumerate(results):
                product['agent'] = self.name
                product['search_method'] = 'graph_filtered_search'
                logger.debug(f"  Product {idx}: {product.get('title', 'NO_TITLE')[:30]}")
            
            logger.info(f"{self.name} returning {len(results)} products")
            logger.debug(f"<<< {self.name}.search() END")
            return results

        except asyncio.TimeoutError:
            logger.error(f"!!! TIMEOUT after {self.query_timeout}s for query: {query}")
            return []
        except Exception as e:
            logger.error(f"!!! {self.name} search failed: {e}", exc_info=True)
            return []

    async def _filtered_search(self, filters: Optional[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        logger.debug(f">>> _filtered_search START: filters={filters}, limit={limit}")
        
        if not filters:
            logger.warning("No filters provided, returning empty list")
            return []
        
        # Collect all search terms
        search_terms = []
        
        if "category" in filters:
            search_terms.append(filters["category"])
            logger.debug(f"Added category term: {filters['category']}")
        
        if "colors" in filters:
            search_terms.extend(filters["colors"])
            logger.debug(f"Added color terms: {filters['colors']}")
        
        # FALLBACK: If no search terms but we have occasion, use professional terms
        if not search_terms and "occasion" in filters:
            occasion = filters["occasion"].lower()
            if "interview" in occasion or "work" in occasion or "business" in occasion:
                search_terms = ["suit", "shirt", "blazer", "dress", "professional"]
                logger.info(f"Using professional fallback terms for {occasion}: {search_terms}")
            elif "wedding" in occasion:
                search_terms = ["dress", "formal", "elegant", "gown"]
                logger.info(f"Using wedding fallback terms: {search_terms}")
        
        if not search_terms:
            logger.warning("No search terms extracted from filters")
            return []
        
        # Initialize params first
        params = {
            "search_terms": search_terms,
            "limit": limit
        }
        
        # PERFORMANCE OPTIMIZED: Skip quality filters for now since properties don't exist
        # Use STARTS WITH for single terms when possible to improve performance  
        if len(search_terms) == 1 and len(search_terms[0]) >= 3:
            # Single term optimization: use STARTS WITH on title for better performance
            cypher_query = """
            MATCH (p:Product)
            WHERE p.id IS NOT NULL
            AND (
                toLower(p.title) STARTS WITH toLower($first_term)
                OR toLower(p.title) CONTAINS (' ' + toLower($first_term))
                OR toLower(p.description) CONTAINS toLower($first_term)
            )
            RETURN p
            LIMIT $limit
            """
            params["first_term"] = search_terms[0]
        else:
            # Multi-term: limit search scope first, then filter
            cypher_query = """
            MATCH (p:Product)
            WHERE p.id IS NOT NULL
            AND ANY(term IN $search_terms WHERE 
                toLower(p.title) CONTAINS toLower(term)
            )
            WITH p
            WHERE ALL(term IN $search_terms WHERE 
                toLower(p.title) CONTAINS toLower(term) OR 
                toLower(p.description) CONTAINS toLower(term)
            )
            RETURN p
            LIMIT $limit
            """
        
        logger.info(f"Executing Cypher query with terms: {search_terms}")
        logger.debug(f"Query params: {params}")
        
        try:
            logger.debug("Calling neo4j.query()...")
            query_start = asyncio.get_event_loop().time()
            results = await self.neo4j.query(cypher_query, params)
            query_time = asyncio.get_event_loop().time() - query_start
            logger.debug(f"neo4j.query() returned in {query_time:.2f}s")
            
            products = []
            if results:
                logger.debug(f"Processing {len(results)} Neo4j records")
                for i, record in enumerate(results):
                    # Extract the product node from the record
                    product_data = dict(record['p']) if 'p' in record else dict(record)
                    
                    # Add product directly - new graph guarantees p.id is UUID format
                    product_id = product_data.get('id')
                    if product_id:
                        products.append(product_data)
                        if i < 3:  # Log first 3 products
                            logger.debug(f"  Product {i}: {product_data.get('title', 'NO_TITLE')[:30]}")
                    else:
                        logger.warning("Skipping product without ID")
            else:
                logger.warning("Neo4j query returned None or empty results")
            
            logger.info(f"CypherBot found {len(products)} products")
            logger.debug(f"<<< _filtered_search END")
            return products
        except Exception as e:
            logger.error(f"!!! Neo4j query failed: {e}", exc_info=True)
            return []

