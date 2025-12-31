#!/usr/bin/env python3
"""Check available Neo4j databases and find products with images"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path("/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27")
load_dotenv(PROJECT_ROOT / ".env")

NEO4J_URI = os.getenv("NEO4J_URL")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# List all databases
print("Available databases:")
with driver.session() as session:
    result = session.run("SHOW DATABASES")
    for record in result:
        print(f"  - {record['name']} (default: {record.get('default', False)})")

print("\n" + "="*80)

# Check each database for products with images
databases = ["neo4j", "productionbackup2"]

for db_name in databases:
    print(f"\nChecking database: {db_name}")
    print("-" * 80)

    try:
        with driver.session(database=db_name) as session:
            # Count total products
            result = session.run("MATCH (p:Product) RETURN count(p) AS count")
            total = result.single()['count']
            print(f"Total products: {total:,}")

            # Count products with images field
            result = session.run("""
                MATCH (p:Product)
                WHERE p.images IS NOT NULL
                RETURN count(p) AS count
            """)
            with_images = result.single()['count']
            print(f"Products with images field: {with_images:,}")

            # Get sample
            if with_images > 0:
                result = session.run("""
                    MATCH (p:Product)
                    WHERE p.images IS NOT NULL
                    RETURN p.id, p.title, p.images
                    LIMIT 1
                """)
                record = result.single()
                if record:
                    print(f"\nSample product:")
                    print(f"  ID: {record['p.id']}")
                    print(f"  Title: {record['p.title']}")
                    print(f"  Images: {record['p.images'][:150]}")
    except Exception as e:
        print(f"Error accessing database {db_name}: {e}")

driver.close()
