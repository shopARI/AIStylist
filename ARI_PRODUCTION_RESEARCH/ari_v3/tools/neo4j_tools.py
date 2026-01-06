"""
Async Neo4j Tools for CrewAI - Non-blocking graph database operations.
Phase 2: True async tools that don't block the event loop.
"""
import os
import logging
from typing import Dict, List, Any, Optional
from crewai.tools import tool
from neo4j import AsyncGraphDatabase

logger = logging.getLogger("crewai.tools.async_neo4j")


# ============================================================================
# CORE IMPLEMENTATION FUNCTIONS (no @tool decorator)
# These can be called internally by other functions
# ============================================================================

async def _execute_neo4j_query(cypher: str, parameters: Dict[str, Any] = None) -> List[Dict]:
    """
    Core implementation: Execute Cypher query against Neo4j (internal use).
    """
    driver = None
    try:
        # Get Neo4j connection from environment (support both naming conventions)
        neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        neo4j_database = os.getenv("NEO4J_DATABASE", "productionbackup2")

        driver = AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )

        async with driver.session(database=neo4j_database) as session:
            result = await session.run(cypher, parameters or {})
            records = []
            async for record in result:
                # Convert record to dict
                record_dict = {}
                for key in record.keys():
                    value = record[key]
                    # Handle Neo4j node objects
                    if hasattr(value, '_properties'):
                        record_dict[key] = dict(value._properties)
                    else:
                        record_dict[key] = value
                records.append(record_dict)

            logger.info(f"Neo4j async query returned {len(records)} records")
            return records

    except Exception as e:
        logger.error(f"Neo4j async query failed: {e}")
        return []
    finally:
        if driver:
            await driver.close()


# ============================================================================
# TOOL WRAPPERS (with @tool decorator)
# These are exposed to CrewAI agents
# ============================================================================

@tool("Execute Neo4j Cypher Query (Async)")
async def async_neo4j_query_tool(cypher: str, parameters: Dict[str, Any] = None) -> List[Dict]:
    """
    Execute Cypher query against fashion product graph database (async, non-blocking).

    Args:
        cypher: Cypher query string with semantic expansion
        parameters: Optional query parameters for safe binding

    Returns:
        List of product records from graph database

    Example:
        results = await async_neo4j_query_tool(
            cypher="MATCH (p:Product) WHERE p.category = $category RETURN p LIMIT 10",
            parameters={"category": "dress"}
        )
    """
    return await _execute_neo4j_query(cypher, parameters)


@tool("Semantic Query Expansion (Async)")
async def async_semantic_expansion_tool(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Generate semantic expansions and synonyms for search query (async).
    Uses fashion domain knowledge to expand queries intelligently.

    Args:
        query: Natural language search query
        context: Optional context (occasion, formality, etc.)

    Returns:
        Dictionary with expanded terms, synonyms, and related concepts

    Example:
        expansion = await async_semantic_expansion_tool(
            query="black shirt for wedding",
            context={"occasion": "wedding", "formality": "formal"}
        )
    """
    try:
        query_lower = query.lower()

        # Fashion-specific synonym mappings
        category_synonyms = {
            "shirt": ["blouse", "top", "dress shirt", "tee"],
            "pants": ["trousers", "jeans", "slacks", "chinos"],
            "dress": ["gown", "frock", "maxi", "midi"],
            "shoes": ["footwear", "boots", "heels", "flats"],
            "jacket": ["blazer", "coat", "outerwear"]
        }

        # Occasion-based expansions
        occasion_terms = {
            "wedding": ["formal", "elegant", "sophisticated", "refined"],
            "interview": ["professional", "business", "polished", "structured"],
            "party": ["stylish", "trendy", "fashionable", "chic"],
            "casual": ["relaxed", "comfortable", "everyday", "laid-back"]
        }

        # Extract base terms
        synonyms = []
        related_terms = []
        category_hints = []

        # Find category synonyms
        for category, syns in category_synonyms.items():
            if category in query_lower:
                synonyms.extend(syns)
                category_hints.append(category)

        # Add occasion context
        if context and "occasion" in context:
            occasion = context["occasion"].lower()
            if occasion in occasion_terms:
                related_terms.extend(occasion_terms[occasion])
        else:
            # Detect occasion from query
            for occasion, terms in occasion_terms.items():
                if occasion in query_lower:
                    related_terms.extend(terms)

        result = {
            "original": query,
            "synonyms": list(set(synonyms)),
            "related_terms": list(set(related_terms)),
            "category_hints": list(set(category_hints)),
            "expanded_query": " OR ".join(set(synonyms + [query]))
        }

        logger.info(f"Semantic expansion: {len(synonyms)} synonyms, {len(related_terms)} related terms")
        return result

    except Exception as e:
        logger.error(f"Semantic expansion failed: {e}")
        return {
            "original": query,
            "synonyms": [],
            "related_terms": [],
            "category_hints": [],
            "expanded_query": query
        }


@tool("Neo4j Fulltext Search (Async)")
async def async_neo4j_fulltext_search_tool(
    search_string: str,
    limit: int = 10,
    filters: Dict[str, Any] = None
) -> List[Dict]:
    """
    Execute fulltext search against Neo4j product index (async, non-blocking).
    Searches both title and description fields.
    Falls back to CONTAINS search if fulltext index doesn't exist.

    Args:
        search_string: Fulltext search string (supports OR, AND operators)
        limit: Maximum number of results to return
        filters: Optional filters (category, price range, etc.)

    Returns:
        List of products matching search criteria with relevance scores
    """
    try:
        # Try fulltext index first
        cypher = """
        CALL db.index.fulltext.queryNodes('product_fulltext', $search_string)
        YIELD node AS p, score
        WHERE 1=1
        """

        parameters = {
            "search_string": search_string,
            "limit": limit
        }

        # Add filter conditions
        if filters:
            if "category" in filters:
                cypher += " AND (toLower(p.category) CONTAINS toLower($category))"
                parameters["category"] = filters["category"]

            if "min_price" in filters:
                cypher += " AND p.price >= $min_price"
                parameters["min_price"] = filters["min_price"]

            if "max_price" in filters:
                cypher += " AND p.price <= $max_price"
                parameters["max_price"] = filters["max_price"]

        cypher += """
        RETURN p, score
        ORDER BY score DESC, p.price ASC
        LIMIT $limit
        """

        # Execute query using internal function (not the decorated tool)
        results = await _execute_neo4j_query(cypher, parameters)

        # Format results
        products = []
        for record in results:
            product_data = record.get('p', {})
            product_data['neo4j_score'] = record.get('score', 0.0)
            products.append(product_data)

        if products:
            logger.info(f"Async fulltext search returned {len(products)} products")
            return products

    except Exception as fulltext_error:
        logger.warning(f"Fulltext index not available, using CONTAINS fallback: {fulltext_error}")

    # Fallback to CONTAINS search
    try:
        cypher_fallback = """
        MATCH (p:Product)
        WHERE toLower(p.title) CONTAINS toLower($search_string)
           OR toLower(p.description) CONTAINS toLower($search_string)
        """

        parameters = {
            "search_string": search_string,
            "limit": limit
        }

        # Add filter conditions for fallback
        if filters:
            if "category" in filters:
                cypher_fallback += " AND toLower(p.category) CONTAINS toLower($category)"
                parameters["category"] = filters["category"]

            if "min_price" in filters:
                cypher_fallback += " AND p.price >= $min_price"
                parameters["min_price"] = filters["min_price"]

            if "max_price" in filters:
                cypher_fallback += " AND p.price <= $max_price"
                parameters["max_price"] = filters["max_price"]

        cypher_fallback += """
        RETURN p
        ORDER BY p.price ASC
        LIMIT $limit
        """

        results = await _execute_neo4j_query(cypher_fallback, parameters)

        # Format results
        products = []
        for record in results:
            product_data = record.get('p', {})
            product_data['neo4j_score'] = 0.5  # Default score for CONTAINS matches
            products.append(product_data)

        logger.info(f"Async CONTAINS search returned {len(products)} products")
        return products

    except Exception as e:
        logger.error(f"Both async fulltext and CONTAINS search failed: {e}")
        return []
