import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("agents.cypher_bot")

# Direct CAMEL 0.2.7 imports
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.memories import ChatHistoryMemory
from camel.societies import RolePlaying
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType, RoleType

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
                model_platform=ModelPlatformType.DEFAULT,
                model_type=ModelType.GPT_4O,
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
            from camel.memories.context_creators import ScoreBasedContextCreator
            from camel.utils.token_counting import OpenAITokenCounter
            
            token_counter = OpenAITokenCounter(model=ModelType.GPT_4O)
            context_creator = ScoreBasedContextCreator(token_counter=token_counter, token_limit=4000)
            self.memory = ChatHistoryMemory(context_creator=context_creator, window_size=20)
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

    async def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        ml_intelligence: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for products using INTELLIGENT GRAPH REASONING and precise filters.
        NOW uses CAMEL agent intelligence before searching like VibeBot does!
        """
        
        logger.debug(f">>> {self.name}.search() START")
        logger.info(f"{self.name} searching with query='{query[:50]}...', filters={filters}")
        
        # Log conversation context usage
        if conversation_context and conversation_context.get("current_products"):
            logger.info(f"CypherBot: Using conversation context with {len(conversation_context['current_products'])} current products")
        
        try:
            # STEP 1: GET INTELLIGENT REASONING STRATEGY (like VibeBot does!)
            logger.info("CypherBot: Engaging CAMEL agent for intelligent reasoning...")
            strategy_start = datetime.now()
            strategy = await self._get_intelligent_strategy(
                query, ml_intelligence, filters, user_context
            )
            strategy_time = (datetime.now() - strategy_start).total_seconds()
            logger.info(f"Intelligent strategy determined in {strategy_time:.2f}s: {strategy[:100]}...")

            # STEP 2: EXECUTE INTELLIGENT STRATEGY
            logger.debug("Executing intelligent graph strategy...")
            exec_start = datetime.now()
            results = await self._execute_intelligent_strategy(
                strategy, query, limit, filters, ml_intelligence, user_context
            )
            exec_time = (datetime.now() - exec_start).total_seconds()
            logger.debug(f"Intelligent strategy executed in {exec_time:.2f}s, got {len(results)} results")

            # Add metadata to the results
            for idx, product in enumerate(results):
                product['agent'] = self.name
                product['search_method'] = 'intelligent_graph_search'
                product['cypher_reasoning'] = strategy[:100]  # Store reasoning used
                logger.debug(f"  Product {idx}: {product.get('title', 'NO_TITLE')[:30]}")
            
            logger.info(f"{self.name} returning {len(results)} products with intelligent reasoning")
            logger.debug(f"<<< {self.name}.search() END")
            return results

        except asyncio.TimeoutError:
            logger.error(f"!!! TIMEOUT after {self.query_timeout}s for query: {query}")
            return []
        except Exception as e:
            logger.error(f"!!! {self.name} search failed: {e}", exc_info=True)
            return []
    
    def _calculate_relevance_score(self, product_data: Dict[str, Any], query: str, position: int) -> float:
        """Calculate relevance score for CypherBot results based on text matching and position."""
        try:
            title = product_data.get('title', '').lower()
            query_lower = query.lower()
            
            # Base score starts high for graph-matched results
            score = 0.8
            
            # Boost for exact query term matches in title
            query_terms = query_lower.split()
            for term in query_terms:
                if term in title:
                    score += 0.1
            
            # Small position penalty (first results are better)
            position_penalty = position * 0.01
            score = max(0.5, score - position_penalty)  # Minimum 0.5 for validated results
            
            return min(1.0, score)  # Cap at 1.0
            
        except Exception as e:
            logger.warning(f"Score calculation error: {e}")
            return 0.75  # Default good score for graph results

    async def _generate_semantic_cypher_query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> tuple[str, Dict[str, Any]]:
        """
        Use LLM to generate semantic Cypher query from natural language.

        Example: "black shirt for wedding" -> understands formal context
        """

        # Build comprehensive prompt for LLM
        prompt = f"""You are a Neo4j Cypher query expert for a fashion e-commerce database.

USER QUERY: "{query}"

FILTERS PROVIDED: {filters if filters else 'None'}

NEO4J SCHEMA:
- Node: Product
  - Properties: id (UUID), title (string), description (string), price (float), brand (string)
  - Full-text index: product_fulltext on [title, description]

AVAILABLE SEARCH SYNTAX:
- Use: CALL db.index.fulltext.queryNodes('product_fulltext', search_string)
- Search string supports: "term1 OR term2", "term1 AND term2", "(term1 OR term2) AND term3"
- Returns: node AS p, score (relevance score)

YOUR TASK:
1. UNDERSTAND THE SEMANTIC INTENT:
   - "black shirt for wedding" = formal/elegant black dress shirt
   - "red dress for party" = stylish/trendy red party dress
   - "casual jeans" = relaxed/comfortable denim pants

2. EXPAND WITH SYNONYMS AND CONTEXT:
   - Shirt → "shirt OR blouse OR top OR dress shirt"
   - Wedding → ADD: "formal OR elegant OR sophisticated"
   - Casual → ADD: "casual OR relaxed OR comfortable"
   - Party → ADD: "party OR trendy OR stylish OR fashionable"

3. GENERATE OPTIMIZED FULLTEXT SEARCH STRING:
   - Combine base terms with context terms
   - Use AND for must-have, OR for alternatives
   - Example: "(black) AND (shirt OR blouse OR top) AND (formal OR elegant)"

4. HANDLE COLORS/ATTRIBUTES:
   - Colors should be AND conditions (black = must have black)
   - Categories can be OR (shirt OR blouse)

RESPOND WITH JSON:
{{
    "search_string": "optimized fulltext search string",
    "reasoning": "brief explanation of semantic understanding",
    "terms_added": ["list", "of", "context", "terms"]
}}

EXAMPLES:

Query: "black shirt for wedding"
Response: {{
    "search_string": "(black) AND (shirt OR blouse OR dress shirt) AND (formal OR elegant OR sophisticated)",
    "reasoning": "Wedding context requires formal attire, expanded shirt to include formal alternatives",
    "terms_added": ["formal", "elegant", "sophisticated", "dress shirt"]
}}

Query: "red dress for party"
Response: {{
    "search_string": "(red) AND (dress OR gown) AND (party OR trendy OR stylish OR fashionable)",
    "reasoning": "Party context suggests trendy/stylish dress, kept color specific",
    "terms_added": ["party", "trendy", "stylish", "fashionable", "gown"]
}}

Query: "casual jeans for weekend"
Response: {{
    "search_string": "(jeans OR denim) AND (casual OR relaxed OR comfortable)",
    "reasoning": "Weekend casual wear, added comfort-related terms",
    "terms_added": ["denim", "casual", "relaxed", "comfortable"]
}}

NOW GENERATE FOR THE USER QUERY ABOVE:"""

        try:
            # Call CAMEL agent for semantic understanding
            user_msg = BaseMessage.make_user_message(
                role_name="Query Optimizer",
                content=prompt
            )

            response = self.agent.step(user_msg)

            # Extract response
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                response_text = response.msg.content
            elif hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)

            logger.info(f"LLM response: {response_text[:200]}...")

            # Parse JSON response
            import json
            import re

            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                query_data = json.loads(json_str)

                search_string = query_data.get('search_string', '')
                reasoning = query_data.get('reasoning', '')
                terms_added = query_data.get('terms_added', [])

                logger.info(f"LLM SEMANTIC UNDERSTANDING:")
                logger.info(f"  Search string: {search_string}")
                logger.info(f"  Reasoning: {reasoning}")
                logger.info(f"  Context terms added: {terms_added}")

                # Build Cypher query with LLM-generated search string
                params = {"limit": limit, "search_string": search_string}

                cypher_query = f"""
                CALL db.index.fulltext.queryNodes('product_fulltext', $search_string)
                YIELD node AS p, score
                RETURN p, score
                ORDER BY score DESC, p.price ASC
                LIMIT $limit
                """

                return cypher_query, params
            else:
                raise ValueError("Could not parse JSON from LLM response")

        except Exception as e:
            logger.error(f"LLM query generation failed: {e}")
            logger.info("Falling back to basic keyword search")

            # Fallback: basic keyword search
            search_terms = []
            if filters:
                if 'category' in filters:
                    search_terms.append(filters['category'])
                if 'colors' in filters:
                    search_terms.extend(filters['colors'])

            if not search_terms:
                search_terms = query.lower().split()[:3]  # First 3 words

            search_string = " OR ".join(search_terms)
            params = {"limit": limit, "search_string": search_string}

            cypher_query = f"""
            CALL db.index.fulltext.queryNodes('product_fulltext', $search_string)
            YIELD node AS p, score
            RETURN p, score
            ORDER BY score DESC, p.price ASC
            LIMIT $limit
            """

            return cypher_query, params

    async def _filtered_search(self, filters: Optional[Dict[str, Any]], limit: int, query: str = "") -> List[Dict[str, Any]]:
        logger.debug(f">>> _filtered_search START: filters={filters}, limit={limit}")
        logger.info(f"[DEBUG _filtered_search] Received filters: {filters}")
        logger.info(f"[DEBUG _filtered_search] Filter keys: {list(filters.keys()) if filters else 'None'}")
        
        if not filters:
            logger.info("No specific filters provided, checking if query has searchable terms")
            # For conversational queries without specific filters, return empty results
            # This prevents "no items found" message for greetings like "how are you?"
            # But allow basic searches for product terms even without explicit filters
            query_lower = query.lower()
            has_product_terms = any(term in query_lower for term in [
                'shirt', 'dress', 'pants', 'shoes', 'jacket', 'coat', 'top', 'blouse', 
                'skirt', 'jeans', 'sweater', 'hoodie', 'blazer', 'suit', 'hat', 'bag'
            ])
            
            if not has_product_terms:
                logger.info("No product terms found in query, returning empty results")
                return []
            else:
                logger.info(f"Found product terms in query '{query}', performing basic search")
                # Create basic filters from query
                filters = {}
                # Extract basic category from query
                for term in ['shirt', 'dress', 'pants', 'shoes', 'jacket', 'coat', 'top', 'blouse', 
                           'skirt', 'jeans', 'sweater', 'hoodie', 'blazer', 'suit', 'hat', 'bag']:
                    if term in query_lower:
                        filters['category'] = term
                        break
        
        # Convert plural filter keys to singular for compatibility
        if 'occasions' in filters and filters['occasions']:
            filters['occasion'] = filters['occasions'][0] if isinstance(filters['occasions'], list) else filters['occasions']
            logger.debug(f"Converted occasions to occasion: {filters['occasion']}")
        if 'categories' in filters and filters['categories']:
            filters['category'] = filters['categories'][0] if isinstance(filters['categories'], list) else filters['categories']
            logger.debug(f"Converted categories to category: {filters['category']}")

        # CRITICAL FIX: Handle when category itself is a list (bad application filters)
        if 'category' in filters and isinstance(filters['category'], list) and filters['category']:
            filters['category'] = filters['category'][0]
            logger.info(f"[FIX] Converted category list to string: {filters['category']}")
        
        # Collect all search terms
        search_terms = []
        
        if "category" in filters:
            search_terms.append(filters["category"])
            logger.debug(f"Added category term: {filters['category']}")
        
        if "colors" in filters:
            search_terms.extend(filters["colors"])
            logger.debug(f"Added color terms: {filters['colors']}")
        
        # FALLBACK: If no search terms but we have occasion, use occasion-specific terms
        if not search_terms and "occasion" in filters:
            occasion = filters["occasion"].lower()
            if "wedding" in occasion or "formal" in occasion:
                search_terms = ["dress", "formal", "elegant", "gown"]
                logger.info(f"Using wedding fallback terms for {occasion}: {search_terms}")
            elif "interview" in occasion or "work" in occasion or "business" in occasion or "professional" in occasion:
                search_terms = ["suit", "shirt", "blazer", "dress", "professional"]
                logger.info(f"Using professional fallback terms for {occasion}: {search_terms}")
        
        if not search_terms:
            logger.warning(f"[DEBUG] No search terms extracted from filters: {filters}")
            logger.warning(f"[DEBUG] Filter had category: {filters.get('category')}, colors: {filters.get('colors')}, occasion: {filters.get('occasion')}")
            return []
        
        # Initialize params first
        params = {
            "limit": limit
        }
        
        # ENHANCED: Add explicit category filtering for better precision
        # Check if we have a specific category filter
        category_filter = filters.get("category") if filters else None
        
        # LLM-POWERED SEMANTIC SEARCH
        # Use GPT-4o to understand context and generate optimized Cypher queries
        # Example: "black shirt for wedding" -> LLM adds "formal", "elegant", "dress shirt"

        logger.info(f"Using LLM to generate SEMANTIC Cypher query for: '{query}'")

        # Generate semantic query using LLM
        cypher_query, params = await self._generate_semantic_cypher_query(
            query=query,
            filters=filters,
            limit=limit
        )

        logger.info(f"LLM generated query with search string: {params.get('search_string', 'N/A')[:100]}")

        try:
            logger.debug("Calling neo4j.query() for FULLTEXT search (title + description)...")
            query_start = asyncio.get_event_loop().time()
            results = await self.neo4j.query(cypher_query, params)
            query_time = asyncio.get_event_loop().time() - query_start
            logger.debug(f"FULLTEXT search returned in {query_time:.2f}s with {len(results) if results else 0} results")
            
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
                            # Add CypherBot relevance score based on position and query match
                            query_match_score = self._calculate_relevance_score(product_data, query, len(products))
                            product_data['cypher_score'] = query_match_score
                            product_data['score'] = query_match_score  # Map to standard score field
                            product_data['agent'] = 'CypherBot'
                            products.append(product_data)
                            if len(products) <= 3:  # Log first 3 accepted products
                                logger.debug(f"  Product {len(products)}: {product_data.get('title', 'NO_TITLE')[:30]} (score: {query_match_score:.2f})")
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
        title = product.get('title', '').lower()

        # CRITICAL FIX: Exclude beauty/cosmetics products when searching for clothing
        beauty_keywords = ['lipstick', 'lip color', 'nail polish', 'hairdressing', 'hair gel',
                          'makeup', 'cosmetic', 'mascara', 'eyeshadow', 'foundation', 'concealer',
                          'perfume', 'fragrance', 'lotion', 'cream', 'serum', 'shampoo', 'conditioner']
        clothing_categories = ['dress', 'shirt', 'pants', 'jacket', 'shoes', 'top', 'blazer',
                              'coat', 'jeans', 'skirt', 'shorts']

        if requested_category in clothing_categories:
            for beauty_keyword in beauty_keywords:
                if beauty_keyword in title:
                    logger.debug(f"Filtered out beauty product: {title[:50]}")
                    return False

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

        # Last resort: check title for category indicators with word boundaries
        import re
        title_indicators = category_mappings.get(requested_category, [requested_category])
        for indicator in title_indicators:
            if len(indicator) > 3:
                # Use word boundary matching to avoid "dress" matching "undressed"
                pattern = r'\b' + re.escape(indicator) + r'\b'
                if re.search(pattern, title):
                    return True

        return False

    async def _get_intelligent_strategy(
        self,
        query: str,
        ml_intelligence: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        INTELLIGENT REASONING: Use CAMEL agent to determine search strategy.
        This is what was missing - CypherBot now thinks before searching!
        
        Returns:
            Strategy description from CAMEL agent with fashion intelligence
        """
        # Build intelligent context for CAMEL agent
        context = f"""FASHION QUERY ANALYSIS: "{query}"

Your job: Use your data-driven fashion intelligence to determine the BEST graph search strategy.

AVAILABLE DATA (6.4M products in Neo4j):
- Product relationships (users who bought X also bought Y)
- Category hierarchies and brand connections  
- Purchase patterns and collaborative filtering
- Graph-based recommendation networks

QUERY CONTEXT:
- Has structured filters: {bool(filters)}
- Filters provided: {filters if filters else 'None'}
"""

        # Add ML intelligence context
        if ml_intelligence and 'cypher_intel' in ml_intelligence:
            intel = ml_intelligence['cypher_intel']
            context += f"\nML INTELLIGENCE AVAILABLE: {len(intel)} intelligence packets"
            
            # Add relevant intelligence insights
            for source, data in intel.items():
                if isinstance(data, dict):
                    if 'user_patterns' in data:
                        patterns = data['user_patterns']
                        if 'popular_categories' in patterns:
                            context += f"\nPopular categories for this pattern: {patterns['popular_categories'][:3]}"
                        if 'common_purchases' in patterns:
                            context += f"\nCommon purchase patterns: {patterns['common_purchases'][:3]}"

        # Add user context
        if user_context:
            context += f"\nUSER CONTEXT:"
            if user_context.get('purchase_history'):
                context += f"\n- Has purchase history: {len(user_context['purchase_history'])} items"
            if user_context.get('preferred_brands'):
                context += f"\n- Prefers brands: {user_context['preferred_brands'][:3]}"
            if user_context.get('budget_range'):
                context += f"\n- Budget range: ${user_context['budget_range'].get('min', 0)}-${user_context['budget_range'].get('max', 'unlimited')}"

        context += """

INTELLIGENT REASONING TASK:
Analyze this query using your fashion knowledge:

1. OCCASION ANALYSIS - What is this person preparing for?
   - Wedding guest? → Need elegant, sophisticated, formal items
   - Job interview? → Need professional, polished, conservative items  
   - Casual outing? → Need comfortable, relaxed, versatile items
   - Party/date? → Need stylish, confidence-building, trendy items
   - Work/business? → Need structured, authoritative, credible items

2. CATEGORY REASONING - What product types are ACTUALLY needed?
   - Think like a fashion expert: Does this make sense?
   - REJECT inappropriate items (no kids' clothes for adult formal events!)
   - Consider complete outfits: tops, bottoms, shoes, accessories

3. GRAPH SEARCH STRATEGY - How should we query the 6.4M product graph?
   Choose the BEST approach:
   - COLLABORATIVE: "Users who bought similar items also bought..."
   - CATEGORY_FOCUSED: Search specific categories with graph relationships
   - BRAND_RELATIONSHIPS: Leverage brand affinity networks
   - OCCASION_PATTERNS: Find items commonly purchased for this occasion
   - GENERAL: Broad keyword search across the graph

RESPOND WITH: 
Strategy name and intelligent reasoning for why this approach will find the MOST APPROPRIATE products for this specific fashion need."""

        try:
            # Create message for CAMEL agent
            user_msg = BaseMessage.make_user_message(
                role_name="Query Optimizer",
                content=context
            )
            
            # Get intelligent response from CAMEL agent
            response = self.agent.step(user_msg)
            
            # Extract strategy
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                strategy = response.msg.content
            elif hasattr(response, 'content'):
                strategy = response.content
            else:
                strategy = str(response)
            
            logger.info(f"CypherBot intelligent strategy: {strategy[:200]}...")
            return strategy
            
        except Exception as e:
            logger.error(f"Intelligent strategy determination failed: {e}")
            return "GENERAL"  # Fallback strategy

    async def _execute_intelligent_strategy(
        self,
        strategy: str,
        query: str,
        limit: int,
        filters: Optional[Dict[str, Any]],
        ml_intelligence: Optional[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute the intelligent strategy determined by CAMEL agent.
        Now CypherBot thinks about what makes sense before searching!
        
        Returns:
            List of intelligently selected products
        """
        strategy_lower = strategy.lower()
        results = []
        
        logger.info(f"Executing intelligent strategy: {strategy_lower[:50]}...")
        
        # Extract intelligent filter guidance from strategy
        intelligent_filters = self._extract_intelligent_filters(strategy, query, filters)
        logger.info(f"[DEBUG] Strategy: {strategy[:100]}...")
        logger.info(f"[DEBUG] Intelligent filters after extraction: {intelligent_filters}")
        
        # Execute based on intelligent strategy keywords
        logger.info(f"[DEBUG] Strategy lower: {strategy_lower[:100]}...")
        if "collaborative" in strategy_lower or "users who bought" in strategy_lower:
            # Use collaborative filtering via graph relationships
            logger.info(f"[DEBUG] Calling _collaborative_graph_search with filters: {intelligent_filters}")
            results.extend(await self._collaborative_graph_search(query, limit, intelligent_filters))
            
        elif "category_focused" in strategy_lower or "specific categories" in strategy_lower:
            # Focus on specific categories with graph enhancements
            results.extend(await self._category_focused_search(query, limit, intelligent_filters))
            
        elif "brand_relationships" in strategy_lower or "brand affinity" in strategy_lower:
            # Leverage brand relationship networks
            results.extend(await self._brand_relationship_search(query, limit, intelligent_filters, user_context))
            
        elif "occasion_patterns" in strategy_lower or "occasion" in strategy_lower:
            # Find items for specific occasions using graph patterns
            results.extend(await self._occasion_pattern_search(query, limit, intelligent_filters))
            
        else:
            # GENERAL strategy or unrecognized strategy - use standard filtered search
            logger.info(f"Using GENERAL strategy for: {strategy_lower[:50]}...")
            results.extend(await self._intelligent_general_search(query, limit, intelligent_filters))
        
        # Always include some general results if not enough found
        if len(results) < limit:
            general = await self._intelligent_general_search(query, limit - len(results), intelligent_filters)
            results.extend(general)
        
        # Deduplicate and rank by graph intelligence
        unique_results = self._deduplicate_and_rank_graph_results(results, query, strategy)
        
        # Add intelligent metadata with proper scoring
        for idx, product in enumerate(unique_results[:limit]):
            product['cypher_rank'] = idx + 1
            # Calculate proper graph score based on position and intelligence
            graph_score = 1.0 - (idx * 0.05)  # Smaller penalty for better scores
            product['graph_score'] = graph_score
            product['score'] = graph_score  # Map to standard score field for battle display
            product['intelligence_applied'] = True
        
        logger.info(f"Intelligent strategy returned {len(unique_results[:limit])} products")
        return unique_results[:limit]

    def _extract_intelligent_filters(
        self,
        strategy: str,
        query: str,
        original_filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract intelligent filters based on CAMEL agent strategy reasoning.
        """
        # Start with original filters
        intelligent_filters = original_filters.copy() if original_filters else {}
        
        # Extract intelligent category suggestions from strategy
        strategy_lower = strategy.lower()
        
        # Wedding occasion intelligence
        if "wedding" in strategy_lower or "formal" in strategy_lower or "elegant" in strategy_lower:
            # Enhance but don't override explicit user category choices
            if not intelligent_filters.get('categories') and not intelligent_filters.get('category'):
                intelligent_filters['category'] = 'dress'  # Default to dresses for formal events
            intelligent_filters['occasion'] = 'wedding'
            intelligent_filters['formality'] = 'formal'
        
        # Interview/professional intelligence  
        elif "interview" in strategy_lower or "professional" in strategy_lower or "business" in strategy_lower:
            # Enhance but don't override explicit user category choices  
            if not intelligent_filters.get('categories') and not intelligent_filters.get('category'):
                intelligent_filters['category'] = 'blazer'  # Default to professional pieces
            intelligent_filters['occasion'] = 'professional'
            intelligent_filters['formality'] = 'business'
        
        # Party/casual intelligence
        elif "party" in strategy_lower or "casual" in strategy_lower or "trendy" in strategy_lower:
            intelligent_filters['occasion'] = 'party'
            intelligent_filters['formality'] = 'casual'
        
        # Add fallback parameter extraction if no intelligent filters found
        if not intelligent_filters and query:
            extracted_params = self.parameter_extractor.extract_parameters(query)
            
            if extracted_params.get('categories'):
                intelligent_filters['category'] = extracted_params['categories'][0]
            if extracted_params.get('colors'):
                intelligent_filters['colors'] = extracted_params['colors']
            if extracted_params.get('occasions'):
                intelligent_filters['occasion'] = extracted_params['occasions'][0]
        
        logger.info(f"Intelligent filters extracted: {intelligent_filters}")
        return intelligent_filters

    async def _collaborative_graph_search(
        self,
        query: str,
        limit: int,
        intelligent_filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Collaborative filtering using graph relationships.
        """
        try:
            # For now, fall back to existing filtered search but with collaborative intent
            # In future, this could use actual graph traversal for "users who bought X also bought Y"
            return await self._filtered_search(intelligent_filters, limit, query)
        except Exception as e:
            logger.error(f"Collaborative graph search failed: {e}")
            return []

    async def _category_focused_search(
        self,
        query: str,
        limit: int,
        intelligent_filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Category-focused search with graph relationships.
        """
        try:
            # Use existing filtered search with enhanced category focus
            return await self._filtered_search(intelligent_filters, limit, query)
        except Exception as e:
            logger.error(f"Category-focused search failed: {e}")
            return []

    async def _brand_relationship_search(
        self,
        query: str,
        limit: int,
        intelligent_filters: Dict[str, Any],
        user_context: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Brand relationship search using graph networks.
        """
        try:
            # Add brand preferences from user context if available
            if user_context and user_context.get('preferred_brands'):
                intelligent_filters = intelligent_filters.copy()
                intelligent_filters['brand'] = user_context['preferred_brands'][0]

            return await self._filtered_search(intelligent_filters, limit, query)
        except Exception as e:
            logger.error(f"Brand relationship search failed: {e}")
            return []

    async def _occasion_pattern_search(
        self,
        query: str,
        limit: int,
        intelligent_filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Occasion-based search using purchase pattern intelligence.
        """
        try:
            # Use occasion-specific search terms with existing infrastructure
            return await self._filtered_search(intelligent_filters, limit, query)
        except Exception as e:
            logger.error(f"Occasion pattern search failed: {e}")
            return []

    async def _intelligent_general_search(
        self,
        query: str,
        limit: int,
        intelligent_filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Intelligent general search as fallback.
        """
        try:
            return await self._filtered_search(intelligent_filters, limit, query)
        except Exception as e:
            logger.error(f"Intelligent general search failed: {e}")
            return []

    def _deduplicate_and_rank_graph_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        strategy: str
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate and rank results based on graph intelligence.
        """
        seen = set()
        unique = []
        
        for product in results:
            product_id = product.get('id')
            if product_id and product_id not in seen:
                seen.add(product_id)
                
                # Calculate intelligent score
                score = 0.5
                
                # Boost for products matching intelligent strategy (check title AND description)
                title_lower = product.get('title', '').lower()
                desc_lower = product.get('description', '').lower()

                if "formal" in strategy.lower() or "wedding" in strategy.lower():
                    # Boost formal/elegant items (check both title and description)
                    formal_keywords = ['dress', 'formal', 'elegant', 'gown', 'sophisticated', 'refined', 'chic', 'luxurious']
                    title_matches = sum(1 for word in formal_keywords if word in title_lower)
                    desc_matches = sum(1 for word in formal_keywords if word in desc_lower)
                    score += min((title_matches * 0.1) + (desc_matches * 0.05), 0.4)

                elif "professional" in strategy.lower() or "interview" in strategy.lower():
                    # Boost professional items (check both title and description)
                    professional_keywords = ['blazer', 'shirt', 'suit', 'professional', 'business',
                                            'polished', 'tailored', 'structured', 'sophisticated', 'formal', 'sleek']
                    title_matches = sum(1 for word in professional_keywords if word in title_lower)
                    desc_matches = sum(1 for word in professional_keywords if word in desc_lower)
                    score += min((title_matches * 0.1) + (desc_matches * 0.05), 0.4)
                
                # Boost for products with good data
                if product.get('in_stock', True):
                    score += 0.1
                if product.get('images') and len(product['images']) > 0:
                    score += 0.1
                
                product['intelligence_score'] = min(score, 1.0)
                unique.append(product)
        
        # Sort by intelligence score
        unique.sort(key=lambda x: x.get('intelligence_score', 0), reverse=True)
        
        return unique
    
    def _should_exclude_sports_items(self, query: str, filters: Dict[str, Any]) -> bool:
        """
        Determine if we should exclude sports/athletic items for general fashion queries.
        """
        query_lower = query.lower()
        
        # Don't exclude sports if explicitly requesting sports items
        sports_keywords = ['sport', 'athletic', 'training', 'team', 'jersey', 'workout', 'gym', 'football', 'basketball', 'soccer']
        if any(keyword in query_lower for keyword in sports_keywords):
            return False
        
        # Exclude sports for general clothing queries
        general_clothing_queries = ['shirt', 'dress', 'pants', 'top', 'blouse', 'casual', 'formal', 'work', 'office']
        if any(keyword in query_lower for keyword in general_clothing_queries):
            return True
            
        return False
    
    def _get_sports_exclusion_clause(self) -> str:
        """
        Get Neo4j WHERE clause to exclude sports/athletic items.
        """
        return """NOT (
            p.title CONTAINS 'training' OR 
            p.title CONTAINS 'team' OR 
            p.title CONTAINS 'jersey' OR 
            p.title CONTAINS 'sport' OR
            p.title CONTAINS 'athletic' OR
            p.title CONTAINS 'football' OR
            p.title CONTAINS 'soccer' OR
            p.title CONTAINS 'basketball' OR
            p.title CONTAINS 'adidas' OR
            p.title CONTAINS 'nike' OR
            p.title CONTAINS 'manchester united' OR
            p.title CONTAINS 'playershirt'
        )"""

