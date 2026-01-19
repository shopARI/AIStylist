"""
Async Neo4j Tools for CrewAI - Non-blocking graph database operations.
Phase 2: True async tools that don't block the event loop.
"""
import os
import logging
import re
from typing import Dict, List, Any, Optional, Set

# CrewAI is optional - only needed for agent tool wrappers
try:
    from crewai.tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    # Create a no-op decorator when crewai is not installed
    def tool(name: str):
        def decorator(func):
            return func
        return decorator

from neo4j import AsyncGraphDatabase

logger = logging.getLogger("crewai.tools.async_neo4j")


# =============================================================================
# CYPHER QUERY VALIDATION (Security)
# =============================================================================

# Whitelisted Cypher operations for read-only queries
ALLOWED_CYPHER_OPERATIONS = frozenset({
    "MATCH", "WHERE", "RETURN", "LIMIT", "ORDER", "BY", "ASC", "DESC",
    "WITH", "OPTIONAL", "UNWIND", "CALL", "YIELD", "AND", "OR", "NOT",
    "IN", "AS", "IS", "NULL", "TRUE", "FALSE", "CONTAINS", "STARTS",
    "ENDS", "COUNT", "SUM", "AVG", "MIN", "MAX", "COLLECT", "DISTINCT",
    "SKIP", "toLower", "toUpper", "toString", "toInteger", "toFloat",
})

# Disallowed operations that could modify data
DISALLOWED_CYPHER_OPERATIONS = frozenset({
    "CREATE", "DELETE", "DETACH", "SET", "REMOVE", "MERGE", "DROP",
    "LOAD", "CSV", "FOREACH", "PERIODIC", "COMMIT", "USING",
})

# Whitelisted fields for property access to prevent injection
ALLOWED_PROPERTY_FIELDS = frozenset({
    "id", "_id", "title", "name", "description", "price", "category",
    "brand", "vendor", "color", "size", "material", "tags", "productType",
    "imageUrl", "url", "sku", "embedding", "score", "created_at", "updated_at",
    "extracted_brand", "extracted_styles", "extracted_colors",  # Neo4j extracted fields
})


def validate_cypher_query(cypher: str) -> tuple[bool, str]:
    """
    Validate a Cypher query for security.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not cypher or not isinstance(cypher, str):
        return False, "Query must be a non-empty string"

    cypher_upper = cypher.upper()

    # Check for disallowed operations (write/modify operations)
    for op in DISALLOWED_CYPHER_OPERATIONS:
        # Match as whole word to avoid false positives
        if re.search(rf'\b{op}\b', cypher_upper):
            return False, f"Disallowed operation: {op}"

    # Check for suspicious patterns
    suspicious_patterns = [
        r'//.*',           # Comments (could hide malicious code)
        r'/\*.*\*/',       # Block comments
        r'CALL\s+dbms\.',  # Admin procedures
        r'CALL\s+db\.(?!index)',  # Most db.* procedures (except fulltext index)
        r'\$\{',           # Template injection
        r'apoc\.',         # APOC procedures (unless explicitly allowed)
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, cypher, re.IGNORECASE):
            return False, f"Suspicious pattern detected"

    return True, ""


def validate_property_access(cypher: str) -> tuple[bool, str]:
    """
    Validate that only whitelisted property fields are accessed.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Extract property accesses like p.field or node.field
    property_pattern = r'[a-zA-Z_][a-zA-Z0-9_]*\.([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(property_pattern, cypher)

    for field in matches:
        if field.lower() not in {f.lower() for f in ALLOWED_PROPERTY_FIELDS}:
            # Allow common Neo4j methods/functions
            if field not in {'keys', 'labels', 'type', 'id', 'properties'}:
                logger.warning(f"Unwhitelisted property field accessed: {field}")
                # We warn but don't block - new fields may be legitimate

    return True, ""


# ============================================================================
# CORE IMPLEMENTATION FUNCTIONS (no @tool decorator)
# These can be called internally by other functions
# ============================================================================

# Default database name (use environment variable for production)
DEFAULT_NEO4J_DATABASE = "neo4j"


async def _execute_neo4j_query(
    cypher: str,
    parameters: Dict[str, Any] = None,
    validate: bool = True,
) -> List[Dict]:
    """
    Core implementation: Execute Cypher query against Neo4j (internal use).

    Args:
        cypher: The Cypher query to execute
        parameters: Query parameters for safe binding
        validate: Whether to validate the query for security (default: True)

    Returns:
        List of records as dictionaries, or empty list on error
    """
    # Validate query for security (prevents Cypher injection)
    if validate:
        is_valid, error_msg = validate_cypher_query(cypher)
        if not is_valid:
            logger.error(f"Cypher query validation failed: {error_msg}")
            return []

        # Also validate property access (warning only)
        validate_property_access(cypher)

    driver = None
    try:
        # Get Neo4j connection from environment (support both naming conventions)
        neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        neo4j_database = os.getenv("NEO4J_DATABASE", DEFAULT_NEO4J_DATABASE)

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
# BRAND LOOKUP FUNCTIONS
# Used by orchestrator for brand-specific product queries
# ============================================================================

async def get_products_by_brand(
    brand_name: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Lookup products by brand name from Neo4j.

    Neo4j has proper extracted_brand field while Qdrant fashion_products does not.
    Used for brand-specific queries like "show me Gucci products".

    Prioritizes exact brand matches, then partial brand matches, then title matches.

    Args:
        brand_name: Brand name to search for (case-insensitive)
        limit: Maximum number of products to return

    Returns:
        List of product dicts with id, title, brand, price, description, category
    """
    # Prioritize exact brand matches first, then partial matches
    # Exclude title-only matches to avoid false positives like "Gucci Mane" t-shirts
    cypher = """
        MATCH (p:Product)
        WHERE p.extracted_brand IS NOT NULL
          AND (
            toLower(p.extracted_brand) = toLower($brand_name)
            OR toLower(p.extracted_brand) STARTS WITH toLower($brand_name)
            OR toLower(p.extracted_brand) ENDS WITH toLower($brand_name)
          )
        RETURN
            p.id as uuid,
            p.title as title,
            p.extracted_brand as brand,
            p.price as price,
            p.description as description,
            p.extracted_styles as styles,
            p.extracted_colors as colors
        ORDER BY
            CASE
                WHEN toLower(p.extracted_brand) = toLower($brand_name) THEN 0
                WHEN toLower(p.extracted_brand) STARTS WITH toLower($brand_name) THEN 1
                ELSE 2
            END
        LIMIT $limit
    """

    # Use internal function with validation disabled (parameterized query is safe)
    records = await _execute_neo4j_query(
        cypher,
        parameters={"brand_name": brand_name, "limit": limit},
        validate=True  # Still validate for other security checks
    )

    logger.info(f"Brand lookup for '{brand_name}' returned {len(records)} products")
    return records


async def list_available_brands(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get list of available brands with product counts.

    Args:
        limit: Maximum number of brands to return

    Returns:
        List of dicts with brand name and count, sorted by count descending
    """
    cypher = """
        MATCH (p:Product)
        WHERE p.extracted_brand IS NOT NULL AND p.extracted_brand <> ''
        RETURN p.extracted_brand as brand, count(*) as product_count
        ORDER BY product_count DESC
        LIMIT $limit
    """

    records = await _execute_neo4j_query(
        cypher,
        parameters={"limit": limit},
        validate=True
    )

    return records


async def search_brands(query: str, limit: int = 20) -> List[str]:
    """
    Search for brands matching a query string.

    Args:
        query: Search string (partial match)
        limit: Maximum number of brands to return

    Returns:
        List of matching brand names
    """
    cypher = """
        MATCH (p:Product)
        WHERE p.extracted_brand IS NOT NULL
          AND toLower(p.extracted_brand) CONTAINS toLower($query)
        RETURN DISTINCT p.extracted_brand as brand
        LIMIT $limit
    """

    records = await _execute_neo4j_query(
        cypher,
        parameters={"query": query, "limit": limit},
        validate=True
    )

    return [r["brand"] for r in records if r.get("brand")]


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
