#!/usr/bin/env python3
"""
Check Product node schema in Neo4j to find image property names
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from pathlib import Path

# Load environment
PROJECT_ROOT = Path("/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27")
load_dotenv(PROJECT_ROOT / ".env")

# Neo4j configuration
NEO4J_URI = os.getenv("NEO4J_URL", "neo4j://34.135.40.119:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "productionbackup2")

print("Connecting to Neo4j...")
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# Query 1: Get all property keys on Product nodes
print("\n1. Checking all property keys on Product nodes:")
with driver.session(database=NEO4J_DATABASE) as session:
    result = session.run("""
        MATCH (p:Product)
        WITH p LIMIT 1
        RETURN keys(p) AS property_keys
    """)
    for record in result:
        print(f"Property keys: {record['property_keys']}")

# Query 2: Get a sample Product with all properties
print("\n2. Sample Product node with all properties:")
with driver.session(database=NEO4J_DATABASE) as session:
    result = session.run("""
        MATCH (p:Product)
        RETURN p
        LIMIT 1
    """)
    for record in result:
        product = record['p']
        print(f"Product ID: {product.get('id', 'N/A')}")
        print(f"All properties: {dict(product)}")

# Query 3: Look for image-related properties
print("\n3. Looking for image-related properties:")
with driver.session(database=NEO4J_DATABASE) as session:
    result = session.run("""
        MATCH (p:Product)
        WHERE any(key in keys(p) WHERE toLower(key) CONTAINS 'image')
        RETURN p
        LIMIT 1
    """)
    count = 0
    for record in result:
        count += 1
        product = record['p']
        print(f"Found product with image property: {dict(product)}")
    if count == 0:
        print("No products found with 'image' in property name")

# Query 4: Count products with various potential image properties
print("\n4. Checking potential image property names:")
potential_props = ['image_url', 'imageUrl', 'image', 'images', 'img_url', 'picture', 'photo', 'url']
with driver.session(database=NEO4J_DATABASE) as session:
    for prop in potential_props:
        result = session.run(f"""
            MATCH (p:Product)
            WHERE p.`{prop}` IS NOT NULL
            RETURN count(p) AS count
        """)
        record = result.single()
        if record and record['count'] > 0:
            print(f"  ✓ {prop}: {record['count']} products")

# Query 5: Check total Product count
print("\n5. Total Product count:")
with driver.session(database=NEO4J_DATABASE) as session:
    result = session.run("MATCH (p:Product) RETURN count(p) AS count")
    record = result.single()
    print(f"Total products: {record['count']}")

driver.close()
print("\n✓ Schema check complete")
