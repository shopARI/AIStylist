"""
Asynchronous Neo4j Integration for AI Stylist

Provides integration with Neo4j for product retrieval and recommendations.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple, Set
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo4j_integration_async")

try:
    from neo4j import AsyncGraphDatabase
except ImportError:
    logger.warning("neo4j AsyncGraphDatabase not available. Install with: pip install neo4j>=5.0.0")
    # Use a mock version
    class AsyncGraphDatabase:
        @staticmethod
        def driver(*args, **kwargs):
            logger.error("Cannot create AsyncGraphDatabase driver. Using mock version.")
            # Create a mock driver with async methods
            class MockAsyncDriver:
                async def close(self):
                    pass
                    
                async def __aenter__(self):
                    return self
                    
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass
                    
                async def execute_query(self, query, parameters=None, **kwargs):
                    logger.warning(f"Mock driver executing query: {query}")
                    return []
                    
                def session(self, **kwargs):
                    class MockAsyncSession:
                        async def __aenter__(self):
                            return self
                            
                        async def __aexit__(self, exc_type, exc_val, exc_tb):
                            pass
                            
                        async def run(self, query, parameters=None, **kwargs):
                            logger.warning(f"Mock session running query: {query}")
                            class MockResult:
                                def __init__(self):
                                    self.records = []
                                    
                                def single(self):
                                    return None
                                    
                                def __iter__(self):
                                    return iter([])
                                    
                                async def __aiter__(self):
                                    return
                                    yield
                            return MockResult()
                    return MockAsyncSession()
            return MockAsyncDriver()

class ProductKnowledgeGraphAsync:
    """
    Provides asynchronous integration with Neo4j for product retrieval and recommendations.
    Adapted to work with the actual database schema containing Products connected
    to Collections, Categories, and Tags.
    """
    
    def __init__(self, url, username, password):
        """
        Initialize the Neo4j connection.
        
        Args:
            url: Neo4j connection URL
            username: Neo4j username
            password: Neo4j password
        """
        logger.info(f"Initializing Async Neo4j connection to {url}")
        self.url = url
        self.username = username
        self.password = password
        self.driver = None
        self.neo4j = self  # For compatibility with existing code
        
        # Connect to Neo4j
        try:
            self.driver = AsyncGraphDatabase.driver(url, auth=(username, password))
            logger.info("Successfully initialized async Neo4j driver")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            # Don't raise exception, allow initialization to continue for graceful degradation
    
    async def _verify_connection(self):
        """Verify the Neo4j connection with a simple query"""
        if not self.driver:
            raise ConnectionError("Neo4j driver not available")
            
        async with self.driver.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            if not record or record.get("test") != 1:
                raise ConnectionError("Could not verify Neo4j connection")
    
    async def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")
    
    async def query(self, query, params=None):
        """
        Execute a Cypher query against Neo4j.
        
        Args:
            query: The Cypher query to execute
            params: Query parameters
            
        Returns:
            List of records as dictionaries
        """
        if not self.driver:
            logger.error("No active Neo4j connection")
            return []
        
        try:
            async with self.driver.session() as session:
                result = await session.run(query, params or {})
                records = []
                async for record in result:
                    records.append(dict(record))
                return records
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return []
    
    async def verify_database_schema(self) -> Tuple[bool, List[str]]:
        """
        Verify that the database contains the expected schema elements.
        
        Returns:
            Tuple of (schema_valid, missing_elements)
        """
        # Required elements based on our analysis
        required_node_labels = ["Product", "Category", "Collection", "Tag"]
        required_relationship_types = ["IN_CATEGORY", "IN_COLLECTION", "TAGGED_WITH"]
        
        missing_elements = []
        
        # Check for node labels
        labels_query = "CALL db.labels()"
        labels_result = await self.query(labels_query)
        
        if labels_result:
            existing_labels = [record.get("label") for record in labels_result]
            for label in required_node_labels:
                if label not in existing_labels:
                    missing_elements.append(f"Node label: {label}")
        else:
            # If query failed, assume all labels are missing
            missing_elements.extend([f"Node label: {label}" for label in required_node_labels])
        
        # Check for relationship types
        rels_query = "CALL db.relationshipTypes()"
        rels_result = await self.query(rels_query)
        
        if rels_result:
            existing_rels = [record.get("relationshipType") for record in rels_result]
            for rel in required_relationship_types:
                if rel not in existing_rels:
                    missing_elements.append(f"Relationship type: {rel}")
        else:
            # If query failed, assume all relationships are missing
            missing_elements.extend([f"Relationship type: {rel}" for rel in required_relationship_types])
        
        # Check if Products have the expected properties
        props_query = """
        MATCH (p:Product) 
        RETURN p LIMIT 1
        """
        props_result = await self.query(props_query)
        
        required_properties = ["id", "title", "price", "images"]
        
        if props_result and len(props_result) > 0:
            product = props_result[0].get("p", {})
            for prop in required_properties:
                if prop not in product:
                    missing_elements.append(f"Product property: {prop}")
        
        schema_valid = len(missing_elements) == 0
        
        if schema_valid:
            logger.info("Database schema verification successful")
        else:
            logger.warning(f"Database schema incomplete. Missing: {missing_elements}")
        
        return schema_valid, missing_elements
    
    def _parse_images(self, images_str: str) -> List[str]:
        """
        Parse the images string into a list of URLs.
        
        Args:
            images_str: String representation of image URLs array
            
        Returns:
            List of image URLs
        """
        if not images_str:
            return []
            
        try:
            # Handle the case where images is a string representation of a JSON array
            import json
            # Clean up the string to make it valid JSON
            clean_str = images_str.replace("'", '"')
            return json.loads(clean_str)
        except Exception as e:
            logger.warning(f"Failed to parse images JSON: {e}")
            # Fall back to simple string split if JSON parsing fails
            if "[" in images_str and "]" in images_str:
                # Extract content between brackets
                content = images_str[images_str.find("[")+1:images_str.find("]")]
                # Split by comma and clean up
                return [url.strip().strip('"\'') for url in content.split(",")]
            return [images_str]  # Return as single item if all else fails
    
    async def get_product_by_filter(self, category=None, collection=None, tag=None, 
                        brand=None, min_price=None, max_price=None, material=None, limit=5):
        """
        Get products by filtering on various attributes with improved diversity.
        
        Args:
            category: Category filter (optional)
            collection: Collection filter (optional)
            tag: Tag filter (optional)
            brand: Brand filter (optional) - kept for interface compatibility
            min_price: Minimum price filter (optional)
            max_price: Maximum price filter (optional)
            material: Material filter (optional) - kept for interface compatibility
            limit: Maximum number of products to return
            
        Returns:
            List of products
        """
        logger.info(f"Retrieving products with filters: category={category}, "
                f"collection={collection}, tag={tag}, price={min_price}-{max_price}")
        
        # First, count total products to diagnose the database
        count_query = "MATCH (p:Product) RETURN count(p) as total"
        count_result = await self.query(count_query)
        product_count = count_result[0]['total'] if count_result else 0
        logger.info(f"Total products in database: {product_count}")
        
        # Use different strategies based on the type of query
        use_randomization = True  # Default to using randomization
        
        # Special handling for occasions like weddings
        is_wedding = False
        if tag:
            wedding_terms = ["wedding", "formal", "ceremony", "gala", "cocktail", "party"]
            is_wedding = any(term in tag.lower() for term in wedding_terms)
            # For specific occasions, we want more targeted results
            if is_wedding:
                use_randomization = False
        
        # Build the main query
        if use_randomization:
            # Randomized approach to get variety
            query = """
            MATCH (p:Product)
            WHERE p.price > 0 AND p.title IS NOT NULL AND p.title <> ''
            AND NOT toLower(p.title) CONTAINS 'test' AND NOT toLower(p.title) CONTAINS 'untitled'
            """
            
            # Add filters as needed
            params = {"sample_size": 2000, "limit": limit}  # Increased sample size for more variety
            
            if category:
                query += """
                WITH p
                MATCH (p)-[:IN_CATEGORY]->(c:Category)
                WHERE toLower(c.title) CONTAINS toLower($category)
                """
                params["category"] = category
                
            if collection:
                query += """
                WITH p
                MATCH (p)-[:IN_COLLECTION]->(col:Collection)
                WHERE toLower(col.title) CONTAINS toLower($collection)
                """
                params["collection"] = collection
                
            if tag:
                query += """
                WITH p
                MATCH (p)-[:TAGGED_WITH]->(t:Tag)
                """
                # Split tag into words for better matching
                tag_words = tag.lower().split()
                tag_conditions = []
                
                # Add conditions for each word in the tag
                for i, word in enumerate(tag_words):
                    if len(word) > 3:  # Only use meaningful words
                        tag_param = f"tag_word_{i}"
                        tag_conditions.append(f"toLower(t.title) CONTAINS ${tag_param}")
                        params[tag_param] = word
                
                # Add the OR condition for any matching word
                if tag_conditions:
                    query += "WHERE " + " OR ".join(tag_conditions)
            
            # Add price filters
            if min_price is not None:
                query += " WITH p WHERE p.price >= $min_price"
                params["min_price"] = float(min_price)
            
            if max_price is not None:
                query += " WITH p WHERE p.price <= $max_price"
                params["max_price"] = float(max_price)
            
            # Add randomization and limit
            query += """
            WITH p, rand() as random
            ORDER BY random
            LIMIT $sample_size
            WITH collect(p) as products
            UNWIND products as p
            RETURN 
                p.id as id,
                p.title as title,
                p.price as price,
                p.description as description,
                p.images as images,
                COALESCE(p.visited_num, 0) as visited_num,
                COALESCE(p.size, '') as size,
                COALESCE(p.color, '') as color
            LIMIT $limit
            """
            
        else:
            # Traditional targeted query for specific requirements
            # Build query parts
            query_parts = ["MATCH (p:Product)"]
            where_clauses = []
            params = {"limit": limit}
            
            # Add category filter if provided
            if category:
                query_parts.append("MATCH (p)-[:IN_CATEGORY]->(c:Category)")
                where_clauses.append("toLower(c.title) CONTAINS toLower($category)")
                params["category"] = category
            
            # Add collection filter if provided
            if collection:
                query_parts.append("MATCH (p)-[:IN_COLLECTION]->(col:Collection)")
                where_clauses.append("toLower(col.title) CONTAINS toLower($collection)")
                params["collection"] = collection
            
            # For weddings, add formal dress categories if no category specified
            if is_wedding and not category:
                query_parts.append("MATCH (p)-[:IN_CATEGORY]->(c:Category)")
                where_clauses.append("(toLower(c.title) CONTAINS 'dress' OR toLower(c.title) CONTAINS 'suit' OR toLower(c.title) CONTAINS 'formal' OR toLower(c.title) CONTAINS 'gown')")
            
            # Improved tag filter with word-based matching
            if tag:
                query_parts.append("MATCH (p)-[:TAGGED_WITH]->(t:Tag)")
                # Split tag into words for better matching
                tag_words = tag.lower().split()
                tag_conditions = []
                
                # Add conditions for each word in the tag
                for i, word in enumerate(tag_words):
                    if len(word) > 3:  # Only use meaningful words
                        tag_param = f"tag_word_{i}"
                        tag_conditions.append(f"toLower(t.title) CONTAINS ${tag_param}")
                        params[tag_param] = word
                
                # Add the OR condition for any matching word
                if tag_conditions:
                    where_clauses.append("(" + " OR ".join(tag_conditions) + ")")
            
            # Add price filters
            if min_price is not None:
                where_clauses.append("p.price >= $min_price")
                params["min_price"] = float(min_price)
            
            if max_price is not None:
                where_clauses.append("p.price <= $max_price")
                params["max_price"] = float(max_price)
            
            # Filter out low-quality items
            where_clauses.append("p.price > 0")  # Skip zero-priced items
            where_clauses.append("p.title IS NOT NULL AND p.title <> ''")  # Require title
            where_clauses.append("NOT toLower(p.title) CONTAINS 'test'")  # Skip test items
            where_clauses.append("NOT toLower(p.title) CONTAINS 'untitled'")  # Skip untitled
            
            # Add WHERE clause if needed
            if where_clauses:
                query_parts.append("WHERE " + " AND ".join(where_clauses))
            
            # Add ordering based on occasion
            if is_wedding:
                # Add to the ORDER BY clause to prioritize dresses
                query_parts.append("""
                ORDER BY 
                    CASE 
                        WHEN toLower(p.title) CONTAINS 'dress' THEN 1
                        WHEN toLower(p.title) CONTAINS 'gown' THEN 2
                        WHEN toLower(p.title) CONTAINS 'suit' THEN 3
                        ELSE 4
                    END,
                    COALESCE(p.visited_num, 0) DESC
                """)
            else:
                # Mix popularity with some randomness
                query_parts.append("ORDER BY COALESCE(p.visited_num, 0) DESC, rand()")
            
            # Complete the query
            query = "\n".join(query_parts)
            query += """
            LIMIT $limit
            """
            
            # Add return statement
            query += """
            RETURN 
                p.id as id,
                p.title as title,
                p.price as price,
                p.description as description,
                p.images as images,
                COALESCE(p.visited_num, 0) as visited_num,
                COALESCE(p.size, '') as size,
                COALESCE(p.color, '') as color
            """
        
        # Log the query for debugging
        logger.info(f"Neo4j query: {query}")
        logger.info(f"Query parameters: {params}")
        
        # Execute the query
        result = await self.query(query, params)
        
        filtered_result = []
        for record in result:
            # Only keep items with price > 0 and proper titles
            if (record.get("price", 0) > 0 and 
                record.get("title") and 
                "test" not in record.get("title", "").lower() and 
                "untitled" not in record.get("title", "").lower()):
                filtered_result.append(record)
        
        if not filtered_result:
            logger.warning(f"No products found matching filters")
            return []
        
        # Process results into product objects
        products = []
        seen_titles = set()
        product_types = set()
        
        for record in filtered_result:
            # Skip if we've seen this title already
            title = record.get("title", "").strip()
            if title in seen_titles:
                continue
                
            product_id = record.get("id", "")
            
            # Add to seen titles
            seen_titles.add(title)
            
            # Create standardized product object
            product_obj = {
                "id": product_id,
                "title": title,
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "size": record.get("size", ""),
                "color": record.get("color", ""),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
            
            # Stop if we have enough products
            if len(products) >= limit:
                break
        
        logger.info(f"Retrieved {len(products)} products matching filters")
        return products
    
    async def _get_product_categories(self, product_id):
        """
        Get categories for a specific product.
        
        Args:
            product_id: Product ID
            
        Returns:
            List of category names
        """
        if not product_id:
            return []
            
        query = """
        MATCH (p:Product {id: $product_id})-[:IN_CATEGORY]->(c:Category)
        RETURN c.title as category
        """
        
        result = await self.query(query, {"product_id": product_id})
        
        if not result:
            return []
            
        return [record.get("category") for record in result if record.get("category")]
    
    async def get_product_details(self, product_id):
        """
        Get detailed information about a specific product.
        
        Args:
            product_id: Product ID
            
        Returns:
            Dictionary with product details
        """
        logger.info(f"Getting details for product {product_id}")
        
        if not product_id:
            logger.error("No product ID provided")
            return None
            
        # Query product information
        query = """
        MATCH (p:Product {id: $product_id})
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        """
        
        result = await self.query(query, {"product_id": product_id})
        
        if not result or len(result) == 0:
            logger.warning(f"Product not found: {product_id}")
            return None
            
        product = result[0]
        
        # Get categories
        categories = await self._get_product_categories(product_id)
        
        # Get tags
        tags_query = """
        MATCH (p:Product {id: $product_id})-[:TAGGED_WITH]->(t:Tag)
        RETURN t.title as tag
        """
        
        tags_result = await self.query(tags_query, {"product_id": product_id})
        tags = [record.get("tag") for record in tags_result if record.get("tag")]
        
        # Get collections
        collections_query = """
        MATCH (p:Product {id: $product_id})-[:IN_COLLECTION]->(c:Collection)
        RETURN c.title as collection
        """
        
        collections_result = await self.query(collections_query, {"product_id": product_id})
        collections = [record.get("collection") for record in collections_result if record.get("collection")]
        
        # Create detailed product object
        product_details = {
            "id": product.get("id", ""),
            "title": product.get("title", "Untitled Product"),
            "price": product.get("price", 0.0),
            "description": product.get("description", ""),
            "images": self._parse_images(product.get("images", "[]")),
            "categories": categories,
            "tags": tags,
            "collections": collections,
            "visited_num": product.get("visited_num", 0),
            # Add feature attributes derived from tags
            "features": tags,  # Use tags as features since we don't have explicit features
            "brand": self._extract_brand_from_tags(tags)
        }
        
        # Increment the visit counter for this product
        await self._increment_product_visit(product_id)
        
        return product_details
    
    async def _increment_product_visit(self, product_id):
        """
        Increment the visit counter for a product.
        
        Args:
            product_id: Product ID
        """
        try:
            query = """
            MATCH (p:Product {id: $product_id})
            SET p.visited_num = COALESCE(p.visited_num, 0) + 1
            """
            
            await self.query(query, {"product_id": product_id})
        except Exception as e:
            logger.error(f"Failed to increment visit counter: {e}")
    
    def _extract_brand_from_tags(self, tags):
        """
        Extract a potential brand from tags.
        
        Args:
            tags: List of tags
            
        Returns:
            Potential brand name or None
        """
        if not tags:
            return None
            
        # Look for tags that might represent brands
        # This is a heuristic approach since we don't have explicit brand nodes
        potential_brands = []
        for tag in tags:
            # Simple heuristic: tags that are capitalized and not common categories
            # are likely to be brand names
            common_categories = ["women", "men", "accessories", "jewelry", "clothing", 
                               "summer", "winter", "fall", "spring", "sale"]
            
            if tag and tag[0].isupper() and tag.lower() not in common_categories:
                potential_brands.append(tag)
        
        if potential_brands:
            return potential_brands[0]  # Return the first potential brand
        
        return None
    
    async def get_similar_products(self, product_id, limit=5):
        """
        Get products similar to a given product.
        
        Args:
            product_id: Reference product ID
            limit: Maximum number of similar products to return
            
        Returns:
            List of similar products
        """
        logger.info(f"Finding products similar to {product_id}")
        
        if not product_id:
            logger.error("No product ID provided")
            return []
            
        # Get the categories and tags of the reference product
        product_details = await self.get_product_details(product_id)
        
        if not product_details:
            logger.warning(f"Reference product not found: {product_id}")
            return []
            
        categories = product_details.get("categories", [])
        tags = product_details.get("tags", [])
        
        if not categories and not tags:
            logger.warning(f"Reference product has no categories or tags")
            return []
            
        # Build a query to find products with similar categories and tags
        query_parts = ["MATCH (p:Product)"]
        where_clauses = ["p.id <> $product_id"]  # Exclude the reference product
        params = {"product_id": product_id, "limit": limit}
        
        # Add category matching if available
        if categories:
            query_parts.append("MATCH (p)-[:IN_CATEGORY]->(c:Category)")
            where_clauses.append("c.title IN $categories")
            params["categories"] = categories
        
        # Add tag matching if available
        if tags:
            query_parts.append("MATCH (p)-[:TAGGED_WITH]->(t:Tag)")
            where_clauses.append("t.title IN $tags")
            params["tags"] = tags
        
        # Add WHERE clause
        query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        # Complete the query
        query = "\n".join(query_parts)
        query += """
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num,
            COUNT(DISTINCT c) + COUNT(DISTINCT t) as similarity_score
        ORDER BY similarity_score DESC, p.visited_num DESC
        LIMIT $limit
        """
        
        # Execute the query
        result = await self.query(query, params)
        
        if not result:
            logger.warning(f"No similar products found")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0),
                "similarity_score": record.get("similarity_score", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Found {len(products)} similar products")
        return products
    
    async def get_popular_products(self, limit=5):
        """
        Get the most popular products based on visit count.
        
        Args:
            limit: Maximum number of products to return
            
        Returns:
            List of popular products
        """
        logger.info(f"Getting popular products (limit={limit})")
        
        query = """
        MATCH (p:Product)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"limit": limit})
        
        if not result:
            logger.warning("No popular products found")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} popular products")
        return products
    
    async def get_products_by_category(self, category, limit=5):
        """
        Get products in a specific category.
        
        Args:
            category: Category name
            limit: Maximum number of products to return
            
        Returns:
            List of products in the category
        """
        logger.info(f"Getting products in category: {category}")
        
        if not category:
            logger.error("No category provided")
            return []
        
        query = """
        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
        WHERE toLower(c.title) CONTAINS toLower($category)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"category": category, "limit": limit})
        
        if not result:
            logger.warning(f"No products found in category: {category}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products in category: {category}")
        return products
    
    async def get_products_by_collection(self, collection, limit=5):
        """
        Get products in a specific collection.
        
        Args:
            collection: Collection name
            limit: Maximum number of products to return
            
        Returns:
            List of products in the collection
        """
        logger.info(f"Getting products in collection: {collection}")
        
        if not collection:
            logger.error("No collection provided")
            return []
        
        query = """
        MATCH (p:Product)-[:IN_COLLECTION]->(c:Collection)
        WHERE toLower(c.title) CONTAINS toLower($collection)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"collection": collection, "limit": limit})
        
        if not result:
            logger.warning(f"No products found in collection: {collection}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products in collection: {collection}")
        return products
    
    async def get_products_by_tag(self, tag, limit=5):
        """
        Get products with a specific tag.
        
        Args:
            tag: Tag name
            limit: Maximum number of products to return
            
        Returns:
            List of products with the tag
        """
        logger.info(f"Getting products with tag: {tag}")
        
        if not tag:
            logger.error("No tag provided")
            return []
        
        query = """
        MATCH (p:Product)-[:TAGGED_WITH]->(t:Tag)
        WHERE toLower(t.title) CONTAINS toLower($tag)
        RETURN 
            p.id as id,
            p.title as title,
            p.price as price,
            p.description as description,
            p.images as images,
            p.visited_num as visited_num
        ORDER BY p.visited_num DESC
        LIMIT $limit
        """
        
        result = await self.query(query, {"tag": tag, "limit": limit})
        
        if not result:
            logger.warning(f"No products found with tag: {tag}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_id = record.get("id", "")
            
            product_obj = {
                "id": product_id,
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": await self._get_product_categories(product_id),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products with tag: {tag}")
        return products
    
    async def get_user_preferences(self, user_id):
        """
        Get user preferences. Included for interface compatibility.
        In a real system, this would retrieve user preferences from the database.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary of user preferences (placeholder)
        """
        logger.info(f"Getting preferences for user: {user_id}")
        
        # Placeholder for user preferences
        # In a real system, this would retrieve actual user data from the database
        return {
            "preferred_categories": [],
            "preferred_collections": [],
            "preferred_tags": [],
            "budget_range": None
        }