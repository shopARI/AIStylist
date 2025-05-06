import asyncio
from neo4j import AsyncGraphDatabase
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_category_collection_constraints")

# Neo4j connection settings
NEO4J_URI = "bolt://34.135.40.119:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "shopari1234"

async def fix_constraints():
    """Fix the Category and Collection constraint issues"""
    logger.info(f"Connecting to Neo4j at {NEO4J_URI}")
    
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    
    try:
        async with driver.session() as session:
            # Step 1: Find all indexes on Category.title and Collection.title
            logger.info("Looking for indexes on Category.title and Collection.title...")
            
            indexes_result = await session.run("SHOW INDEXES")
            
            category_index_name = None
            collection_index_name = None
            
            async for record in indexes_result:
                record_dict = dict(record)
                labels = record_dict.get('labelsOrTypes', [])
                props = record_dict.get('properties', [])
                
                # Check for Category.title index
                if labels and props and 'Category' in labels and 'title' in props:
                    category_index_name = record_dict.get('name')
                    logger.info(f"Found Category.title index: {category_index_name}")
                
                # Check for Collection.title index
                if labels and props and 'Collection' in labels and 'title' in props:
                    collection_index_name = record_dict.get('name')
                    logger.info(f"Found Collection.title index: {collection_index_name}")
            
            # Step 2: Drop the indexes if found - with retry mechanism for deadlocks
            max_retries = 3
            
            if category_index_name:
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Dropping Category.title index {category_index_name} (attempt {attempt+1}/{max_retries})...")
                        await session.run(f"DROP INDEX {category_index_name}")
                        logger.info(f"Successfully dropped index {category_index_name}")
                        break
                    except Exception as e:
                        logger.error(f"Error dropping Category.title index (attempt {attempt+1}): {e}")
                        # Wait before retry to avoid deadlocks
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 * (attempt + 1))  # Exponential backoff
            
            if collection_index_name:
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Dropping Collection.title index {collection_index_name} (attempt {attempt+1}/{max_retries})...")
                        await session.run(f"DROP INDEX {collection_index_name}")
                        logger.info(f"Successfully dropped index {collection_index_name}")
                        break
                    except Exception as e:
                        logger.error(f"Error dropping Collection.title index (attempt {attempt+1}): {e}")
                        # Wait before retry to avoid deadlocks
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 * (attempt + 1))  # Exponential backoff
            
            # Add a delay to ensure index changes are processed
            logger.info("Waiting for index changes to be processed...")
            await asyncio.sleep(3)
            
            # Step 3: Create the constraints with correct syntax
            for attempt in range(max_retries):
                try:
                    logger.info(f"Creating Category constraint (attempt {attempt+1}/{max_retries})...")
                    await session.run("CREATE CONSTRAINT category_title_unique FOR (c:Category) REQUIRE c.title IS UNIQUE")
                    logger.info("Category constraint created successfully")
                    break
                except Exception as e:
                    logger.error(f"Error creating Category constraint (attempt {attempt+1}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 * (attempt + 1))
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Creating Collection constraint (attempt {attempt+1}/{max_retries})...")
                    await session.run("CREATE CONSTRAINT collection_title_unique FOR (c:Collection) REQUIRE c.title IS UNIQUE")
                    logger.info("Collection constraint created successfully")
                    break
                except Exception as e:
                    logger.error(f"Error creating Collection constraint (attempt {attempt+1}): {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 * (attempt + 1))
            
            # Step 4: Verify the constraints were created
            constraints_result = await session.run("SHOW CONSTRAINTS")
            
            category_constraint_found = False
            collection_constraint_found = False
            
            async for record in constraints_result:
                record_dict = dict(record)
                labels = record_dict.get('labelsOrTypes', [])
                props = record_dict.get('properties', [])
                
                if labels and props and 'Category' in labels and 'title' in props:
                    category_constraint_found = True
                    logger.info(f"Verified Category constraint: {record_dict}")
                
                if labels and props and 'Collection' in labels and 'title' in props:
                    collection_constraint_found = True
                    logger.info(f"Verified Collection constraint: {record_dict}")
            
            if category_constraint_found and collection_constraint_found:
                logger.info("Fix complete: Both constraints exist with correct syntax")
            elif category_constraint_found:
                logger.warning("Fix incomplete: Only Category constraint found")
            elif collection_constraint_found:
                logger.warning("Fix incomplete: Only Collection constraint found")
            else:
                logger.warning("Fix failed: Neither constraint was found")
                
    except Exception as e:
        logger.error(f"Error fixing constraints: {e}")
    finally:
        await driver.close()

if __name__ == "__main__":
    asyncio.run(fix_constraints())
