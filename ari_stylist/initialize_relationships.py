"""
Neo4j Relationship Type Initializer

This script creates missing relationship types in the Neo4j database
that are required by the AI Stylist application.
"""

import asyncio
from neo4j import AsyncGraphDatabase
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("relationship_initializer")

# Neo4j connection settings
NEO4J_URI = "bolt://34.135.40.119:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "shopari1234"

async def initialize_relationship_types():
    """Initialize missing relationship types in Neo4j"""
    logger.info(f"Connecting to Neo4j at {NEO4J_URI}")
    
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI, 
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    
    try:
        # Check which relationship types already exist
        async with driver.session() as session:
            result = await session.run("CALL db.relationshipTypes()")
            existing_types = []
            async for record in result:
                existing_types.append(record["relationshipType"])
            
            logger.info(f"Existing relationship types: {existing_types}")
            
            # Define required relationship types
            required_types = ["HAS_PREFERENCE", "HAS_INTERACTION", "REFERS_TO"]
            missing_types = [t for t in required_types if t not in existing_types]
            
            if not missing_types:
                logger.info("All required relationship types already exist")
                return
                
            logger.info(f"Missing relationship types: {missing_types}")
            
            # Create test user
            await session.run("""
            MERGE (u:User {id: 'system_test_user'})
            ON CREATE SET u.name = 'System Test User',
                         u.created_at = datetime()
            """)
            
            # Create test UserPreference if needed
            if "HAS_PREFERENCE" in missing_types:
                logger.info("Creating HAS_PREFERENCE relationship type")
                await session.run("""
                MATCH (u:User {id: 'system_test_user'})
                MERGE (p:UserPreference {id: 'system_test_pref'})
                ON CREATE SET p.type = 'category',
                             p.value = 'system_test',
                             p.created_at = datetime()
                MERGE (u)-[:HAS_PREFERENCE]->(p)
                """)
            
            # Find a product to use for interaction
            product_result = await session.run("MATCH (p:Product) RETURN p.id as id LIMIT 1")
            product_record = await product_result.single()
            
            if not product_record:
                logger.error("No products found in database")
                return
                
            product_id = product_record["id"]
            
            # Create ProductInteraction with relationships if needed
            if "HAS_INTERACTION" in missing_types or "REFERS_TO" in missing_types:
                logger.info("Creating HAS_INTERACTION and REFERS_TO relationship types")
                await session.run(f"""
                MATCH (u:User {{id: 'system_test_user'}}), (p:Product {{id: '{product_id}'}})
                MERGE (i:ProductInteraction {{id: 'system_test_interaction'}})
                ON CREATE SET i.type = 'viewed',
                             i.timestamp = datetime()
                MERGE (u)-[:HAS_INTERACTION]->(i)
                MERGE (i)-[:REFERS_TO]->(p)
                """)
            
            # Verify that all relationship types now exist
            result = await session.run("CALL db.relationshipTypes()")
            updated_types = []
            async for record in result:
                updated_types.append(record["relationshipType"])
                
            logger.info(f"Updated relationship types: {updated_types}")
            
            # Check if all required types exist now
            remaining_missing = [t for t in required_types if t not in updated_types]
            if remaining_missing:
                logger.error(f"Failed to create some relationship types: {remaining_missing}")
            else:
                logger.info("All required relationship types successfully created")
        
    except Exception as e:
        logger.error(f"Error initializing relationship types: {e}")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(initialize_relationship_types())
