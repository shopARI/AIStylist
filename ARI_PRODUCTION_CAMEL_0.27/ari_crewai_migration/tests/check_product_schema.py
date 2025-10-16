"""
Quick script to check Neo4j product schema
"""
from neo4j import GraphDatabase
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL'),
    auth=(os.getenv('NEO4J_USERNAME'), os.getenv('NEO4J_PASSWORD'))
)

print("Checking Neo4j product schema...\n")

# Check what properties a product has
with driver.session() as session:
    result = session.run('MATCH (p:Product) RETURN p LIMIT 1')
    record = result.single()
    if record:
        product = record['p']
        print('Sample product properties:')
        for key in sorted(product.keys()):
            value = product[key]
            if isinstance(value, str) and len(value) > 100:
                print(f'  {key}: {value[:100]}...')
            else:
                print(f'  {key}: {value}')

# Check distinct categories
print("\nChecking distinct categories (sample):")
with driver.session() as session:
    result = session.run('MATCH (p:Product) RETURN DISTINCT p.category as cat LIMIT 10')
    for record in result:
        print(f'  - {record["cat"]}')

# Check if there's a different category field
print("\nChecking for 'dress' in various fields:")
with driver.session() as session:
    # Try product_type
    result = session.run("MATCH (p:Product) WHERE toLower(p.product_type) CONTAINS 'dress' RETURN count(p) as count")
    count = result.single()['count']
    print(f'  product_type contains "dress": {count:,}')

    # Try title
    result = session.run("MATCH (p:Product) WHERE toLower(p.title) CONTAINS 'dress' RETURN count(p) as count")
    count = result.single()['count']
    print(f'  title contains "dress": {count:,}')

driver.close()
