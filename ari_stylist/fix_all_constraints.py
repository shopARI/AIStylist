import asyncio
import logging
from pathlib import Path
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_all_constraints")

async def fix_constraints_in_file():
    """Fix all constraint syntax errors in neo4j_integration_async.py"""
    # File to fix
    file_path = "neo4j_integration_async.py"
    
    logger.info(f"Fixing constraints in {file_path}")
    
    # Read the file content
    try:
        with open(file_path, 'r') as file:
            content = file.read()
            original_content = content  # Save a copy for comparison
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return
    
    # Pattern to match constraint creation statements with ASSERT
    pattern = r'CREATE CONSTRAINT IF NOT EXISTS FOR \(([a-z]):([A-Za-z]+)\) ASSERT ([a-z]\.[a-z_]+) IS UNIQUE'
    
    # Replace ASSERT with REQUIRE in constraint statements
    updated_content = re.sub(pattern, r'CREATE CONSTRAINT IF NOT EXISTS FOR (\1:\2) REQUIRE \3 IS UNIQUE', content)
    
    # Check if content was modified
    if updated_content != original_content:
        # Write the fixed content back to the file
        try:
            with open(file_path, 'w') as file:
                file.write(updated_content)
            logger.info(f"Successfully updated {file_path} with REQUIRE syntax")
            
            # Count how many replacements were made
            original_matches = len(re.findall(pattern, original_content))
            logger.info(f"Fixed {original_matches} constraint statements")
        except Exception as e:
            logger.error(f"Error writing to file: {e}")
    else:
        logger.info(f"No constraint syntax to fix in {file_path}")

if __name__ == "__main__":
    asyncio.run(fix_constraints_in_file())
