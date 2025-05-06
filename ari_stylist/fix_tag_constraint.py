import asyncio
from neo4j import AsyncGraphDatabase
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_tag_constraint")

# Neo4j connection settings
NEO4J_URI = "bolt://34.135.40.119:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "shopari1234"

async def fix_tag_constraint():
    """Fix the Tag constraint syntax error"""
    logger.info(f"Connecting to Neo4j at {NEO4J_URI}")
    
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    
    try:
        async with driver.session() as session:
            # Step 1: Look for the specific index on Tag.title
            logger.info("Looking for index on Tag.title...")
            
            # Get all indexes first
            indexes_result = await session.run("SHOW INDEXES")
            tag_title_index_name = None
            
            async for record in indexes_result:
                record_dict = dict(record)
                labels = record_dict.get('labelsOrTypes', [])
                props = record_dict.get('properties', [])
                
                # Check if this is the Tag.title index
                if labels and props and 'Tag' in labels and 'title' in props:
                    tag_title_index_name = record_dict.get('name')
                    logger.info(f"Found Tag.title index: {tag_title_index_name}")
                    break
            
            # Step 2: Drop the index if found
            if tag_title_index_name:
                logger.info(f"Dropping index {tag_title_index_name}...")
                try:
                    await session.run(f"DROP INDEX {tag_title_index_name}")
                    logger.info(f"Successfully dropped index {tag_title_index_name}")
                except Exception as e:
                    logger.error(f"Error dropping index: {e}")
            
            # Step 3: Create the constraint with correct syntax
            logger.info("Creating Tag constraint with correct syntax")
            try:
                # Use the proper syntax based on Neo4j version
                await session.run("CREATE CONSTRAINT tag_title_unique FOR (t:Tag) REQUIRE t.title IS UNIQUE")
                logger.info("Tag constraint created successfully")
            except Exception as e:
                logger.error(f"Error creating constraint: {e}")
            
            # Step 4: Verify the constraint was created
            constraints_result = await session.run("SHOW CONSTRAINTS")
            
            constraint_found = False
            async for record in constraints_result:
                record_dict = dict(record)
                labels = record_dict.get('labelsOrTypes', [])
                props = record_dict.get('properties', [])
                
                if labels and props and 'Tag' in labels and 'title' in props:
                    constraint_found = True
                    logger.info(f"Verified Tag constraint: {record_dict}")
                    break
            
            if constraint_found:
                logger.info("Fix complete: Tag constraint exists with correct syntax")
            else:
                logger.warning("Fix incomplete: Tag constraint still not found")
                
    except Exception as e:
        logger.error(f"Error fixing Tag constraint: {e}")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(fix_tag_constraint())