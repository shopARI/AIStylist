import logging
from typing import Dict, List, Any, Optional, Tuple
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neo4j_integration")

class ProductKnowledgeGraph:
    """
    Provides integration with Neo4j for product retrieval and recommendations.
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
        logger.info(f"Initializing Neo4j connection to {url}")
        self.url = url
        self.username = username
        self.password = password
        self.driver = None
        self.neo4j = self  # For compatibility with existing code
        
        # Connect to Neo4j
        try:
            self.driver = GraphDatabase.driver(url, auth=(username, password))
            # Verify connection with a simple query
            self._verify_connection()
            logger.info("Successfully connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            # Don't raise exception, allow initialization to continue for graceful degradation
    
    def _verify_connection(self):
        """Verify the Neo4j connection with a simple query"""
        with self.driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            if not record or record.get("test") != 1:
                raise ConnectionError("Could not verify Neo4j connection")
    
    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def query(self, query, params=None):
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
            with self.driver.session() as session:
                result = session.run(query, params or {})
                return [dict(record) for record in result]
        except Exception as e:
            logger.error(f"Neo4j query failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return []
    
    def verify_database_schema(self) -> Tuple[bool, List[str]]:
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
        labels_result = self.query(labels_query)
        
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
        rels_result = self.query(rels_query)
        
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
        props_result = self.query(props_query)
        
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
    
    def get_product_by_filter(self, category=None, collection=None, tag=None, 
                           brand=None, min_price=None, max_price=None, material=None, limit=5):
        """
        Get products by filtering on various attributes.
        
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
        
        # Add tag filter if provided
        if tag:
            query_parts.append("MATCH (p)-[:TAGGED_WITH]->(t:Tag)")
            where_clauses.append("toLower(t.title) CONTAINS toLower($tag)")
            params["tag"] = tag
        
        # Add brand filter if provided (try to match against tags as fallback)
        if brand:
            query_parts.append("MATCH (p)-[:TAGGED_WITH]->(b:Tag)")
            where_clauses.append("toLower(b.title) CONTAINS toLower($brand)")
            params["brand"] = brand
        
        # Add price filters
        if min_price is not None:
            where_clauses.append("p.price >= $min_price")
            params["min_price"] = float(min_price)
        
        if max_price is not None:
            where_clauses.append("p.price <= $max_price")
            params["max_price"] = float(max_price)
        
        # Add WHERE clause if needed
        if where_clauses:
            query_parts.append("WHERE " + " AND ".join(where_clauses))
        
        # Complete the query with return statements
        query = "\n".join(query_parts)
        query += """
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
        
        # Execute the query
        result = self.query(query, params)
        
        if not result:
            logger.warning(f"No products found matching filters")
            return []
        
        # Process results into a standardized format
        products = []
        for record in result:
            # Create standardized product object
            product_obj = {
                "id": record.get("id", ""),
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": self._get_product_categories(record.get("id")),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products matching filters")
        return products
    
    def _get_product_categories(self, product_id):
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
        
        result = self.query(query, {"product_id": product_id})
        
        if not result:
            return []
            
        return [record.get("category") for record in result if record.get("category")]
    
    def get_product_details(self, product_id):
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
        
        result = self.query(query, {"product_id": product_id})
        
        if not result or len(result) == 0:
            logger.warning(f"Product not found: {product_id}")
            return None
            
        product = result[0]
        
        # Get categories
        categories = self._get_product_categories(product_id)
        
        # Get tags
        tags_query = """
        MATCH (p:Product {id: $product_id})-[:TAGGED_WITH]->(t:Tag)
        RETURN t.title as tag
        """
        
        tags_result = self.query(tags_query, {"product_id": product_id})
        tags = [record.get("tag") for record in tags_result if record.get("tag")]
        
        # Get collections
        collections_query = """
        MATCH (p:Product {id: $product_id})-[:IN_COLLECTION]->(c:Collection)
        RETURN c.title as collection
        """
        
        collections_result = self.query(collections_query, {"product_id": product_id})
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
        self._increment_product_visit(product_id)
        
        return product_details
    
    def _increment_product_visit(self, product_id):
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
            
            self.query(query, {"product_id": product_id})
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
    
    def get_similar_products(self, product_id, limit=5):
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
        product_details = self.get_product_details(product_id)
        
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
        result = self.query(query, params)
        
        if not result:
            logger.warning(f"No similar products found")
            return []
        
        # Process results
        products = []
        for record in result:
            product_obj = {
                "id": record.get("id", ""),
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": self._get_product_categories(record.get("id")),
                "visited_num": record.get("visited_num", 0),
                "similarity_score": record.get("similarity_score", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Found {len(products)} similar products")
        return products
    
    def get_popular_products(self, limit=5):
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
        
        result = self.query(query, {"limit": limit})
        
        if not result:
            logger.warning("No popular products found")
            return []
        
        # Process results
        products = []
        for record in result:
            product_obj = {
                "id": record.get("id", ""),
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": self._get_product_categories(record.get("id")),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} popular products")
        return products
    
    def get_products_by_category(self, category, limit=5):
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
        
        result = self.query(query, {"category": category, "limit": limit})
        
        if not result:
            logger.warning(f"No products found in category: {category}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_obj = {
                "id": record.get("id", ""),
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": self._get_product_categories(record.get("id")),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products in category: {category}")
        return products
    
    def get_products_by_collection(self, collection, limit=5):
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
        
        result = self.query(query, {"collection": collection, "limit": limit})
        
        if not result:
            logger.warning(f"No products found in collection: {collection}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_obj = {
                "id": record.get("id", ""),
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": self._get_product_categories(record.get("id")),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products in collection: {collection}")
        return products
    
    def get_products_by_tag(self, tag, limit=5):
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
        
        result = self.query(query, {"tag": tag, "limit": limit})
        
        if not result:
            logger.warning(f"No products found with tag: {tag}")
            return []
        
        # Process results
        products = []
        for record in result:
            product_obj = {
                "id": record.get("id", ""),
                "title": record.get("title", "Untitled Product"),
                "price": record.get("price", 0.0),
                "description": record.get("description", ""),
                "images": self._parse_images(record.get("images", "[]")),
                "categories": self._get_product_categories(record.get("id")),
                "visited_num": record.get("visited_num", 0)
            }
            
            products.append(product_obj)
        
        logger.info(f"Retrieved {len(products)} products with tag: {tag}")
        return products
    
    def get_user_preferences(self, user_id):
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
    
    def add_interaction_context(self, key, value):
        """
        Placeholder for adding interaction context.
        Included for compatibility with the existing code.
        
        Args:
            key: Context key
            value: Context value
        """
        logger.info(f"Adding interaction context: {key}")
        # This is a placeholder for future implementation
        pass
