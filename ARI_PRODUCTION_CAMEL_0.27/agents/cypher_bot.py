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
            logger.info("No specific filters provided, performing general search")
            # For conversational queries without specific filters, return empty results
            # This prevents "no items found" message for greetings like "how are you?"
            return []
        
        # Convert plural filter keys to singular for compatibility
        if 'occasions' in filters and filters['occasions']:
            filters['occasion'] = filters['occasions'][0] if isinstance(filters['occasions'], list) else filters['occasions']
            logger.debug(f"Converted occasions to occasion: {filters['occasion']}")
        if 'categories' in filters and filters['categories']:
            filters['category'] = filters['categories'][0] if isinstance(filters['categories'], list) else filters['categories']
            logger.debug(f"Converted categories to category: {filters['category']}")
        
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
        
        # ENHANCED: Add explicit category filtering for better precision
        # Check if we have a specific category filter
        category_filter = filters.get("category") if filters else None
        
        if len(search_terms) == 1 and len(search_terms[0]) >= 3:
            # Single term optimization with optional category filtering
            if category_filter:
                cypher_query = """
                MATCH (p:Product)
                WHERE p.id IS NOT NULL
                AND (
                    toLower(p.category) = toLower($category_filter)
                    OR toLower(p.subcategory) = toLower($category_filter) 
                    OR ANY(cat IN p.categories WHERE toLower(cat) = toLower($category_filter))
                )
                AND (
                    toLower(p.title) STARTS WITH toLower($first_term)
                    OR toLower(p.title) CONTAINS (' ' + toLower($first_term))
                    OR (toLower(p.title) CONTAINS toLower($first_term) AND size(p.title) < 100)
                )
                RETURN p
                ORDER BY 
                    CASE WHEN toLower(p.title) STARTS WITH toLower($first_term) THEN 1 ELSE 2 END,
                    CASE WHEN toLower(p.category) = toLower($category_filter) THEN 1 ELSE 2 END
                LIMIT $limit
                """
                params["first_term"] = search_terms[0]
                params["category_filter"] = category_filter
            else:
                cypher_query = """
                MATCH (p:Product)
                WHERE p.id IS NOT NULL
                AND (
                    toLower(p.title) STARTS WITH toLower($first_term)
                    OR toLower(p.title) CONTAINS (' ' + toLower($first_term))
                    OR (toLower(p.title) CONTAINS toLower($first_term) AND size(p.title) < 100)
                )
                RETURN p
                ORDER BY CASE WHEN toLower(p.title) STARTS WITH toLower($first_term) THEN 1 ELSE 2 END
                LIMIT $limit
                """
                params["first_term"] = search_terms[0]
        else:
            # Multi-term with enhanced category filtering
            if category_filter:
                cypher_query = """
                MATCH (p:Product)
                WHERE p.id IS NOT NULL
                AND (
                    toLower(p.category) = toLower($category_filter)
                    OR toLower(p.subcategory) = toLower($category_filter)
                    OR ANY(cat IN p.categories WHERE toLower(cat) = toLower($category_filter))
                )
                AND ANY(term IN $search_terms WHERE 
                    toLower(p.title) CONTAINS toLower(term)
                )
                WITH p
                WHERE ALL(term IN $search_terms WHERE 
                    toLower(p.title) CONTAINS toLower(term) OR 
                    (toLower(p.description) CONTAINS toLower(term) AND size(p.description) < 200)
                )
                RETURN p
                ORDER BY 
                    CASE WHEN toLower(p.category) = toLower($category_filter) THEN 1 ELSE 2 END,
                    size([term IN $search_terms WHERE toLower(p.title) CONTAINS toLower(term)]) DESC
                LIMIT $limit
                """
                params["category_filter"] = category_filter
            else:
                cypher_query = """
                MATCH (p:Product)
                WHERE p.id IS NOT NULL
                AND ANY(term IN $search_terms WHERE 
                    toLower(p.title) CONTAINS toLower(term)
                )
                WITH p
                WHERE ALL(term IN $search_terms WHERE 
                    toLower(p.title) CONTAINS toLower(term) OR 
                    (toLower(p.description) CONTAINS toLower(term) AND size(p.description) < 200)
                )
                RETURN p
                ORDER BY size([term IN $search_terms WHERE toLower(p.title) CONTAINS toLower(term)]) DESC
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
            filtered_count = 0
            if results:
                logger.debug(f"Processing {len(results)} Neo4j records")
                for i, record in enumerate(results):
                    # Extract the product node from the record
                    product_data = dict(record['p']) if 'p' in record else dict(record)
                    
                    # Add product directly - new graph guarantees p.id is UUID format
                    product_id = product_data.get('id')
                    if product_id:
                        # ENHANCED: Add category validation post-processing
                        if self._validate_product_category(product_data, filters):
                            products.append(product_data)
                            if len(products) <= 3:  # Log first 3 accepted products
                                logger.debug(f"  Product {len(products)}: {product_data.get('title', 'NO_TITLE')[:30]}")
                        else:
                            filtered_count += 1
                            logger.debug(f"  Filtered out: {product_data.get('title', 'NO_TITLE')[:30]} - wrong category")
                    else:
                        logger.warning("Skipping product without ID")
                        
                if filtered_count > 0:
                    logger.info(f"Category validation filtered out {filtered_count} irrelevant products")
            else:
                logger.warning("Neo4j query returned None or empty results")
            
            logger.info(f"CypherBot found {len(products)} products")
            logger.debug(f"<<< _filtered_search END")
            return products
        except Exception as e:
            logger.error(f"!!! Neo4j query failed: {e}", exc_info=True)
            return []

    def _validate_product_category(
        self,
        product: Dict[str, Any],
        filters: Optional[Dict[str, Any]]
    ) -> bool:
        """
        Validate that a product matches the requested category.
        
        Args:
            product: Product data
            filters: Search filters including category
            
        Returns:
            True if product matches category or no category filter
        """
        if not filters or 'category' not in filters:
            return True  # No category filter, accept all products
        
        requested_category = filters['category'].lower()
        
        # Check multiple product category fields
        product_categories = []
        
        # Check main category field
        if product.get('category'):
            product_categories.append(product['category'].lower())
        
        # Check subcategory field
        if product.get('subcategory'):
            product_categories.append(product['subcategory'].lower())
        
        # Check categories array
        if product.get('categories') and isinstance(product['categories'], list):
            product_categories.extend([cat.lower() for cat in product['categories'] if cat])
        
        # Check if any product category matches the requested category
        if requested_category in product_categories:
            return True
        
        # ENHANCED: Check for category relationships and synonyms
        category_mappings = {
            'shirt': ['shirt', 'blouse', 'top', 't-shirt', 'tee', 'tank', 'polo'],
            'pants': ['pants', 'jeans', 'trousers', 'chinos', 'slacks'],
            'dress': ['dress', 'gown', 'frock', 'sundress', 'maxi', 'midi'],
            'shoes': ['shoes', 'boots', 'sneakers', 'heels', 'flats', 'sandals'],
            'jacket': ['jacket', 'blazer', 'coat', 'outerwear'],
            'shorts': ['shorts', 'short', 'bermuda'],
            'top': ['top', 'shirt', 'blouse', 'tee', 'tank', 'camisole']
        }
        
        # Check if requested category has known synonyms
        if requested_category in category_mappings:
            for synonym in category_mappings[requested_category]:
                if synonym in product_categories:
                    return True
        
        # Check reverse mapping (product category has synonyms that match request)
        for category, synonyms in category_mappings.items():
            if requested_category in synonyms:
                for product_cat in product_categories:
                    if product_cat in synonyms:
                        return True
        
        # Last resort: check title for category indicators (less reliable)
        title = product.get('title', '').lower()
        title_indicators = category_mappings.get(requested_category, [requested_category])
        for indicator in title_indicators:
            if indicator in title and len(indicator) > 3:  # Avoid short matches
                return True
        
        return False

