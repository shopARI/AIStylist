import json
import os
from neo4j import GraphDatabase
import logging
from typing import List, Dict, Any, Set

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("schema_migration")

class ProductSchemaImporter:
    """
    Creates a simplified Neo4j schema for the AI Stylist from JSON product data.
    Aligns with the expected schema in the codebase:
    - Products connected to Category nodes via IN_CATEGORY relationships
    - Products connected to Collection nodes via IN_COLLECTION relationships
    - Products connected to Tag nodes via TAGGED_WITH relationships
    """
    
    def __init__(self, uri, username, password):
        """Initialize with Neo4j connection details"""
        logger.info(f"Connecting to Neo4j at {uri}")
        self.uri = uri
        self.username = username
        self.password = password
        
        try:
            self.driver = GraphDatabase.driver(uri, auth=(username, password))
            # Verify connection
            self._verify_connection()
            logger.info("Successfully connected to Neo4j database")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise ConnectionError(f"Could not connect to Neo4j: {e}")
    
    def _verify_connection(self):
        """Verify the Neo4j connection with a simple query"""
        with self.driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            if not record or record.get("test") != 1:
                raise ConnectionError("Could not verify Neo4j connection")
    
    def close(self):
        """Close the Neo4j connection"""
        if hasattr(self, 'driver') and self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def clear_database(self):
        """Clear all nodes and relationships from the database"""
        logger.info("Clearing all database data...")
        
        with self.driver.session() as session:
            try:
                # Delete all relationships and nodes
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("Database cleared successfully")
            except Exception as e:
                logger.error(f"Error clearing database: {e}")
                raise
    
    def create_constraints(self):
        """Create database constraints for performance and data integrity"""
        with self.driver.session() as session:
            try:
                # Create constraints for unique identifiers based on schema
                constraints = [
                    # Product constraints
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product) ASSERT p.id IS UNIQUE",
                    
                    # Category constraints
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) ASSERT c.title IS UNIQUE",
                    
                    # Collection constraints
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (col:Collection) ASSERT col.title IS UNIQUE",
                    
                    # Tag constraints
                    "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Tag) ASSERT t.title IS UNIQUE"
                ]
                
                for constraint in constraints:
                    try:
                        session.run(constraint)
                        logger.info(f"Created constraint: {constraint}")
                    except Exception as e:
                        logger.error(f"Failed to create constraint: {constraint} - Error: {e}")
                
                logger.info("Database constraints created successfully")
                
                # Create indexes for faster lookups
                indexes = [
                    "CREATE INDEX IF NOT EXISTS FOR (p:Product) ON (p.price)",
                    "CREATE INDEX IF NOT EXISTS FOR (p:Product) ON (p.visited_num)",
                    "CREATE INDEX IF NOT EXISTS FOR (c:Category) ON (c.title)",
                    "CREATE INDEX IF NOT EXISTS FOR (col:Collection) ON (col.title)",
                    "CREATE INDEX IF NOT EXISTS FOR (t:Tag) ON (t.title)"
                ]
                
                for index in indexes:
                    try:
                        session.run(index)
                        logger.info(f"Created index: {index}")
                    except Exception as e:
                        logger.error(f"Failed to create index: {index} - Error: {e}")
                
                logger.info("Database indexes created successfully")
                
            except Exception as e:
                logger.error(f"Error creating database schema: {e}")
                raise
    
    def process_json_data(self, json_file_path):
        """
        Process JSON product data and create nodes and relationships
        
        Args:
            json_file_path: Path to the JSON file with product data
        """
        logger.info(f"Processing JSON data from {json_file_path}")
        
        try:
            # Load JSON data
            with open(json_file_path, 'r', encoding='utf-8') as file:
                # Check if the file contains a JSON array or a series of JSON objects
                content = file.read()
                if content.strip().startswith('['):
                    # File contains a JSON array
                    products = json.loads(content)
                else:
                    # File contains one JSON object per line
                    products = []
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('//') and not line == '{' and not line == '}':
                            # Clean the line from trailing commas
                            if line.endswith(','):
                                line = line[:-1]
                            # Add braces if needed
                            if not line.startswith('{'):
                                line = '{' + line
                            if not line.endswith('}'):
                                line = line + '}'
                            try:
                                product = json.loads(line)
                                products.append(product)
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse line: {line}")
            
            logger.info(f"Loaded {len(products)} products from JSON")
            
            # Process each product
            for index, product in enumerate(products):
                if index % 100 == 0:
                    logger.info(f"Processing product {index+1} of {len(products)}")
                
                self._create_product_with_relationships(product)
            
            logger.info("All products processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing JSON data: {e}")
            raise
    
    def _create_product_with_relationships(self, product):
        """
        Create a product node with its relationships to categories, collections, and tags
        
        Args:
            product: Dictionary with product data
        """
        product_id = str(product.get('id', ''))
        if not product_id:
            logger.warning("Skipping product with no ID")
            return
        
        with self.driver.session() as session:
            # Create Product node
            product_props = {
                'id': product_id,
                'title': product.get('title', 'Untitled Product'),
                'price': float(product.get('price', 0)),
                'description': product.get('description', ''),
                'visited_num': int(product.get('visited_num', 0))
            }
            
            # Handle images (could be string or list)
            images = product.get('images', [])
            if isinstance(images, str):
                # If images is a string, try to convert to list
                if images.strip():
                    try:
                        images = json.loads(images.replace("'", "\""))
                    except json.JSONDecodeError:
                        images = [images]
            
            # Ensure images is a list
            if not isinstance(images, list):
                images = []
            
            # Convert images to string representation
            product_props['images'] = json.dumps(images)
            
            # Create product node
            try:
                session.run(
                    """
                    MERGE (p:Product {id: $id})
                    SET p.title = $title,
                        p.price = $price,
                        p.description = $description,
                        p.images = $images,
                        p.visited_num = $visited_num
                    """,
                    **product_props
                )
                
                # Process Categories
                categories = []
                category_string = product.get('category', '')
                if category_string:
                    # Split categories by comma
                    categories = [cat.strip() for cat in category_string.split(',') if cat.strip()]
                
                # Create Category nodes and relationships
                for category in categories:
                    session.run(
                        """
                        MERGE (c:Category {title: $category})
                        WITH c
                        MATCH (p:Product {id: $product_id})
                        MERGE (p)-[:IN_CATEGORY]->(c)
                        """,
                        category=category,
                        product_id=product_id
                    )
                
                # Process Collection (from brand)
                brand = product.get('brand', '')
                if brand:
                    session.run(
                        """
                        MERGE (col:Collection {title: $brand})
                        WITH col
                        MATCH (p:Product {id: $product_id})
                        MERGE (p)-[:IN_COLLECTION]->(col)
                        """,
                        brand=brand,
                        product_id=product_id
                    )
                
                # Process Tags
                # Create tags from:
                # 1. Categories (for cross-referencing)
                # 2. Keywords extracted from description
                # 3. Any additional attributes

                # Start with categories as tags
                tags = set(categories)
                
                # Add brand as a tag
                if brand:
                    tags.add(brand)
                    
                # Process description for keywords (simple extraction)
                description = product.get('description', '').lower()
                # Add explicit material tags if found in description
                materials = ['cotton', 'silk', 'wool', 'polyester', 'linen', 'leather', 
                           'denim', 'suede', 'velvet', 'cashmere', 'satin', 'nylon']
                for material in materials:
                    if material in description.lower():
                        tags.add(material)
                
                # Add colors if found in description
                colors = ['red', 'blue', 'green', 'black', 'white', 'yellow', 'purple', 
                        'orange', 'pink', 'brown', 'gray', 'grey', 'gold', 'silver']
                for color in colors:
                    if color in description.lower():
                        tags.add(color)
                
                # Create Tag nodes and relationships
                for tag in tags:
                    if tag:  # Ensure tag is not empty
                        session.run(
                            """
                            MERGE (t:Tag {title: $tag})
                            WITH t
                            MATCH (p:Product {id: $product_id})
                            MERGE (p)-[:TAGGED_WITH]->(t)
                            """,
                            tag=tag,
                            product_id=product_id
                        )
                
            except Exception as e:
                logger.error(f"Error creating product {product_id}: {e}")
    
    def run_import(self, json_file_path, clear_existing=True):
        """
        Run the complete import process
        
        Args:
            json_file_path: Path to the JSON file with product data
            clear_existing: Whether to clear existing data (default: True)
        """
        try:
            if clear_existing:
                self.clear_database()
            
            self.create_constraints()
            self.process_json_data(json_file_path)
            
            logger.info("Import completed successfully")
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            raise
        finally:
            self.close()


def run_migration(neo4j_uri, neo4j_username, neo4j_password, json_file_path):
    """
    Run the schema migration with the provided parameters
    
    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_username: Neo4j username
        neo4j_password: Neo4j password
        json_file_path: Path to the JSON file with product data
    """
    importer = ProductSchemaImporter(neo4j_uri, neo4j_username, neo4j_password)
    importer.run_import(json_file_path)
    logger.info("Schema migration completed")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Neo4j Schema Migration for AI Stylist')
    parser.add_argument('--uri', default=os.environ.get("NEO4J_URL", "bolt://localhost:7687"),
                        help='Neo4j connection URI')
    parser.add_argument('--username', default=os.environ.get("NEO4J_USERNAME", "neo4j"),
                        help='Neo4j username')
    parser.add_argument('--password', default=os.environ.get("NEO4J_PASSWORD", "password"),
                        help='Neo4j password')
    parser.add_argument('--json', required=True,
                        help='Path to the JSON file with product data')
    
    args = parser.parse_args()
    
    run_migration(args.uri, args.username, args.password, args.json)