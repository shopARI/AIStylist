import os
import logging
import sys
from typing import Tuple, List
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("production_schema_init")

# Neo4j connection settings
NEO4J_URI = os.environ.get("NEO4J_URL", "bolt://34.135.40.119:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "shopari1234")

class ProductSchemaInitializer:
    """
    Initializes the Neo4j schema for production use based on the actual database structure.
    Sets up constraints and indexes for Products, Categories, Collections, and Tags.
    Does NOT create sample data or users.
    """
    
    def __init__(self, uri, username, password):
        """
        Initialize with Neo4j connection details
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
        """
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
    
    def create_constraints(self):
        """Create database constraints for performance and data integrity"""
        with self.driver.session() as session:
            try:
                # Create constraints for unique identifiers based on actual schema
                constraints = [
                    # Product constraints
                    "CREATE CONSTRAINT IF NOT EXISTS ON (p:Product) ASSERT p.id IS UNIQUE",
                    
                    # Category constraints
                    "CREATE CONSTRAINT IF NOT EXISTS ON (c:Category) ASSERT c.title IS UNIQUE",
                    
                    # Collection constraints
                    "CREATE CONSTRAINT IF NOT EXISTS ON (c:Collection) ASSERT c.title IS UNIQUE",
                    
                    # Tag constraints
                    "CREATE CONSTRAINT IF NOT EXISTS ON (t:Tag) ASSERT t.title IS UNIQUE"
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
                    "CREATE INDEX IF NOT EXISTS FOR (c:Collection) ON (c.title)",
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
    
    def verify_schema(self) -> Tuple[bool, List[str]]:
        """
        Verify the database schema structure without modifying data
        
        Returns:
            Tuple of (schema_valid, missing_elements)
        """
        # Required schema elements based on actual database
        required_node_labels = ["Product", "Category", "Collection", "Tag"]
        required_relationship_types = ["IN_CATEGORY", "IN_COLLECTION", "TAGGED_WITH"]
        
        missing_elements = []
        
        with self.driver.session() as session:
            # Check for node labels
            for label in required_node_labels:
                try:
                    result = session.run(
                        f"MATCH (n:{label}) RETURN count(n) as count LIMIT 1"
                    )
                    record = result.single()
                    if not record:
                        missing_elements.append(f"Node label: {label}")
                except Exception as e:
                    logger.error(f"Error checking node label {label}: {e}")
                    missing_elements.append(f"Node label: {label} (error: {e})")
            
            # Check for relationship types
            for rel_type in required_relationship_types:
                try:
                    result = session.run(
                        f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count LIMIT 1"
                    )
                    record = result.single()
                    if not record:
                        missing_elements.append(f"Relationship type: {rel_type}")
                except Exception as e:
                    logger.error(f"Error checking relationship type {rel_type}: {e}")
                    missing_elements.append(f"Relationship type: {rel_type} (error: {e})")
            
            # Check if Products have the expected properties
            required_properties = ["id", "title", "price", "images"]
            try:
                result = session.run("MATCH (p:Product) RETURN p LIMIT 1")
                record = result.single()
                
                if record:
                    product = record.get("p")
                    for prop in required_properties:
                        if prop not in product:
                            missing_elements.append(f"Product property: {prop}")
                else:
                    logger.warning("No Product nodes found in database")
            except Exception as e:
                logger.error(f"Error checking product properties: {e}")
                missing_elements.append("Product properties (error)")
        
        schema_valid = len(missing_elements) == 0
        
        if schema_valid:
            logger.info("Database schema verification successful")
        else:
            logger.warning(f"Database schema incomplete. Missing: {missing_elements}")
        
        return schema_valid, missing_elements
    
    def get_database_statistics(self):
        """
        Get basic statistics about the database to understand its state
        
        Returns:
            Dictionary with database statistics
        """
        stats = {}
        
        with self.driver.session() as session:
            try:
                # Count nodes by label
                for label in ["Product", "Category", "Collection", "Tag"]:
                    result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                    record = result.single()
                    if record:
                        stats[f"{label.lower()}_count"] = record["count"]
                
                # Count relationships
                for rel_type in ["IN_CATEGORY", "IN_COLLECTION", "TAGGED_WITH"]:
                    result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
                    record = result.single()
                    if record:
                        stats[f"{rel_type.lower()}_count"] = record["count"]
                
                # Get price range
                result = session.run(
                    "MATCH (p:Product) WHERE p.price IS NOT NULL "
                    "RETURN min(p.price) as min_price, max(p.price) as max_price, "
                    "avg(p.price) as avg_price"
                )
                record = result.single()
                if record:
                    stats["price_stats"] = {
                        "min": record["min_price"],
                        "max": record["max_price"],
                        "avg": record["avg_price"]
                    }
                
                # Get most common categories
                result = session.run(
                    "MATCH (p:Product)-[:IN_CATEGORY]->(c:Category) "
                    "RETURN c.title as category, count(p) as count "
                    "ORDER BY count DESC LIMIT 5"
                )
                top_categories = {}
                for record in result:
                    top_categories[record["category"]] = record["count"]
                stats["top_categories"] = top_categories
                
                logger.info(f"Database statistics: {stats}")
                return stats
                
            except Exception as e:
                logger.error(f"Error getting database statistics: {e}")
                return {"error": str(e)}


def initialize_production_schema():
    """
    Initialize ONLY the schema for a production database.
    This does NOT create or modify any product or user data.
    """
    logger.info("Starting production schema initialization...")
    
    initializer = None
    try:
        # Connect to Neo4j
        initializer = ProductSchemaInitializer(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
        
        # Create constraints and indexes
        initializer.create_constraints()
        
        # Verify schema
        schema_valid, missing_elements = initializer.verify_schema()
        
        # Get database statistics
        stats = initializer.get_database_statistics()
        
        if schema_valid:
            logger.info("Production schema initialization complete and verified!")
            
            # Print database statistics
            if stats and "product_count" in stats:
                logger.info(f"Database contains {stats['product_count']} products")
                logger.info(f"Top categories: {stats.get('top_categories', {})}")
            
            return True
        else:
            logger.warning("Production schema initialized but verification failed.")
            logger.warning(f"Missing elements: {missing_elements}")
            return False
        
    except Exception as e:
        logger.error(f"Error during production schema initialization: {e}")
        return False
    finally:
        # Close connection
        if initializer:
            initializer.close()


if __name__ == "__main__":
    success = initialize_production_schema()
    sys.exit(0 if success else 1)
