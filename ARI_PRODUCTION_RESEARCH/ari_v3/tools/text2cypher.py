"""
V3 Text2Cypher - LLM-powered natural language to Cypher query conversion.

This module provides a general-purpose text-to-Cypher query generator that works
with ANY field in the Neo4j schema, not just specific hardcoded fields.

Based on neo4j_graphrag.retrievers.text2cypher pattern but adapted for V3.
"""
import os
import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Neo4j Product Schema - fetched once and cached
NEO4J_PRODUCT_SCHEMA = """
NODE: Product
PROPERTIES:
  - id: UUID (unique identifier, matches Qdrant embedding ID)
  - title: String (product name/title)
  - description: String (product description)
  - price: Float (product price in USD)
  - extracted_brand: String (brand name, e.g., "Nike", "Gucci", "Calvin Klein")
  - extracted_styles: List[String] (style tags, e.g., ["casual", "modern", "minimalist"])
  - extracted_colors: List[String] (color tags, e.g., ["black", "navy", "white"])
  - images: List[String] (image URLs)
  - visited_num: Integer (view count)

INDEXES:
  - product_fulltext: Full-text index on [title, description]
  - Unique constraint on id

SEARCH PATTERNS:
  - Brand search: WHERE toLower(p.extracted_brand) = toLower($brand)
  - Color search: WHERE ANY(c IN p.extracted_colors WHERE toLower(c) = toLower($color))
  - Style search: WHERE ANY(s IN p.extracted_styles WHERE toLower(s) CONTAINS toLower($style))
  - Price range: WHERE p.price >= $min_price AND p.price <= $max_price
  - Full-text: CALL db.index.fulltext.queryNodes('product_fulltext', $search_terms)
"""


@dataclass
class CypherQuery:
    """Represents a generated Cypher query with parameters."""
    cypher: str
    parameters: Dict[str, Any]
    reasoning: str
    search_fields: List[str]  # Which fields the query searches


class Text2CypherGenerator:
    """
    LLM-powered natural language to Cypher query generator.

    Works with ANY Neo4j product field - brand, color, price, style, etc.
    Not hardcoded for specific fields.
    """

    CYPHER_GENERATION_PROMPT = """You are a Neo4j Cypher query expert for a fashion e-commerce database.

## Neo4j Schema
{schema}

## User Query
"{query}"

## Additional Context (if any)
{context}

## Your Task
Generate a Cypher query that answers the user's natural language query.

## Rules
1. ALWAYS use parameterized queries ($variable) to prevent injection
2. Use toLower() for case-insensitive string matching
3. For brand searches, use extracted_brand field
4. For color searches, use extracted_colors array (use ANY() for array membership)
5. For style searches, use extracted_styles array
6. For text searches across title/description, use the fulltext index
7. Always include LIMIT to prevent returning too many results
8. Order by relevance (fulltext score) or price when appropriate

## Response Format
Return a JSON object with:
{{
    "cypher": "The Cypher query with $parameters",
    "parameters": {{"param_name": "value"}},
    "reasoning": "Brief explanation of query strategy",
    "search_fields": ["list", "of", "fields", "searched"]
}}

## Examples

Query: "Show me Nike shoes"
Response:
{{
    "cypher": "MATCH (p:Product) WHERE toLower(p.extracted_brand) = toLower($brand) AND (toLower(p.title) CONTAINS 'shoe' OR toLower(p.title) CONTAINS 'sneaker' OR toLower(p.title) CONTAINS 'footwear') RETURN p ORDER BY p.visited_num DESC LIMIT $limit",
    "parameters": {{"brand": "Nike", "limit": 50}},
    "reasoning": "Filtering by brand=Nike and category keywords for shoes",
    "search_fields": ["extracted_brand", "title"]
}}

Query: "Black dresses under $100"
Response:
{{
    "cypher": "MATCH (p:Product) WHERE ANY(c IN p.extracted_colors WHERE toLower(c) = 'black') AND toLower(p.title) CONTAINS 'dress' AND p.price <= $max_price RETURN p ORDER BY p.price ASC LIMIT $limit",
    "parameters": {{"max_price": 100, "limit": 50}},
    "reasoning": "Filtering by color=black, category=dress, and price cap",
    "search_fields": ["extracted_colors", "title", "price"]
}}

Query: "Luxury designer handbags"
Response:
{{
    "cypher": "MATCH (p:Product) WHERE p.price >= $min_price AND (toLower(p.title) CONTAINS 'handbag' OR toLower(p.title) CONTAINS 'purse' OR toLower(p.title) CONTAINS 'tote') RETURN p ORDER BY p.price DESC LIMIT $limit",
    "parameters": {{"min_price": 200, "limit": 50}},
    "reasoning": "Luxury implies higher price point, searching bag-related terms",
    "search_fields": ["price", "title"]
}}

Now generate for the user query above:"""

    def __init__(
        self,
        openai_client=None,
        async_openai_client=None,
        model: str = "gpt-4o-mini",
        schema: Optional[str] = None,
    ):
        """
        Initialize the Text2Cypher generator.

        Args:
            openai_client: Sync OpenAI client
            async_openai_client: Async OpenAI client for non-blocking calls
            model: Model to use for query generation
            schema: Neo4j schema string (uses default if not provided)
        """
        self.openai_client = openai_client
        self.async_openai_client = async_openai_client
        self.model = model
        self.schema = schema or NEO4J_PRODUCT_SCHEMA

    async def generate_cypher_async(
        self,
        query: str,
        context: Optional[str] = None,
        limit: int = 50,
    ) -> CypherQuery:
        """
        Generate a Cypher query from natural language (async).

        Args:
            query: Natural language query (e.g., "show me Gucci bags")
            context: Additional context (e.g., user preferences)
            limit: Default limit for results

        Returns:
            CypherQuery with the generated query, parameters, and metadata
        """
        if not self.async_openai_client:
            raise ValueError("Async OpenAI client not configured")

        prompt = self.CYPHER_GENERATION_PROMPT.format(
            schema=self.schema,
            query=query,
            context=context or "None",
        )

        try:
            response = await self.async_openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Cypher query expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,  # Low temperature for consistent queries
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # Ensure limit is in parameters
            if "limit" not in result.get("parameters", {}):
                result["parameters"]["limit"] = limit

            # Validate the generated Cypher
            cypher = result.get("cypher", "")
            if not self._validate_cypher(cypher):
                logger.warning(f"Generated Cypher failed validation, using fallback")
                return self._fallback_query(query, limit)

            logger.info(f"Generated Cypher: {cypher[:100]}...")
            logger.info(f"Search fields: {result.get('search_fields', [])}")

            return CypherQuery(
                cypher=cypher,
                parameters=result.get("parameters", {}),
                reasoning=result.get("reasoning", ""),
                search_fields=result.get("search_fields", []),
            )

        except Exception as e:
            logger.error(f"Cypher generation failed: {e}")
            return self._fallback_query(query, limit)

    def generate_cypher(
        self,
        query: str,
        context: Optional[str] = None,
        limit: int = 50,
    ) -> CypherQuery:
        """
        Generate a Cypher query from natural language (sync).
        """
        if not self.openai_client:
            raise ValueError("OpenAI client not configured")

        prompt = self.CYPHER_GENERATION_PROMPT.format(
            schema=self.schema,
            query=query,
            context=context or "None",
        )

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a Cypher query expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            if "limit" not in result.get("parameters", {}):
                result["parameters"]["limit"] = limit

            cypher = result.get("cypher", "")
            if not self._validate_cypher(cypher):
                logger.warning(f"Generated Cypher failed validation, using fallback")
                return self._fallback_query(query, limit)

            return CypherQuery(
                cypher=cypher,
                parameters=result.get("parameters", {}),
                reasoning=result.get("reasoning", ""),
                search_fields=result.get("search_fields", []),
            )

        except Exception as e:
            logger.error(f"Cypher generation failed: {e}")
            return self._fallback_query(query, limit)

    def _validate_cypher(self, cypher: str) -> bool:
        """
        Validate that generated Cypher is safe and well-formed.
        """
        if not cypher:
            return False

        cypher_upper = cypher.upper()

        # Must have MATCH and RETURN
        if "MATCH" not in cypher_upper or "RETURN" not in cypher_upper:
            return False

        # Must not have write operations
        write_ops = ["CREATE", "DELETE", "DETACH", "SET", "REMOVE", "MERGE", "DROP"]
        for op in write_ops:
            if re.search(rf'\b{op}\b', cypher_upper):
                logger.warning(f"Write operation {op} detected in generated Cypher")
                return False

        # Should have LIMIT for safety
        if "LIMIT" not in cypher_upper:
            logger.warning("Generated Cypher missing LIMIT clause")
            # Don't fail, but warn

        return True

    def _fallback_query(self, query: str, limit: int) -> CypherQuery:
        """
        Generate a safe fallback query using fulltext search.
        """
        # Extract keywords from query
        keywords = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        search_terms = " OR ".join(keywords[:5])  # Limit to 5 keywords

        return CypherQuery(
            cypher="""
                CALL db.index.fulltext.queryNodes('product_fulltext', $search_terms)
                YIELD node AS p, score
                RETURN p, score
                ORDER BY score DESC
                LIMIT $limit
            """,
            parameters={"search_terms": search_terms, "limit": limit},
            reasoning="Fallback to fulltext search due to generation error",
            search_fields=["title", "description"],
        )


async def execute_text2cypher_query(
    query: str,
    openai_client=None,
    async_openai_client=None,
    neo4j_driver=None,
    limit: int = 50,
    context: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], CypherQuery]:
    """
    Convenience function: Generate Cypher from text and execute it.

    Args:
        query: Natural language query
        openai_client: OpenAI client for LLM
        async_openai_client: Async OpenAI client
        neo4j_driver: Neo4j async driver
        limit: Result limit
        context: Additional context

    Returns:
        Tuple of (results list, CypherQuery object)
    """
    from neo4j import AsyncGraphDatabase

    # Get Neo4j connection
    if neo4j_driver is None:
        neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")

        neo4j_driver = AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )
        should_close_driver = True
    else:
        should_close_driver = False
        neo4j_database = os.getenv("NEO4J_DATABASE", "neo4j")

    try:
        # Generate Cypher
        generator = Text2CypherGenerator(
            openai_client=openai_client,
            async_openai_client=async_openai_client,
        )

        if async_openai_client:
            cypher_query = await generator.generate_cypher_async(query, context, limit)
        else:
            cypher_query = generator.generate_cypher(query, context, limit)

        # Execute query
        async with neo4j_driver.session(database=neo4j_database) as session:
            result = await session.run(cypher_query.cypher, cypher_query.parameters)
            records = []
            async for record in result:
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    if hasattr(value, '_properties'):
                        record_dict[key] = dict(value._properties)
                    else:
                        record_dict[key] = value
                records.append(record_dict)

        logger.info(f"Text2Cypher query returned {len(records)} results")
        return records, cypher_query

    finally:
        if should_close_driver:
            await neo4j_driver.close()
