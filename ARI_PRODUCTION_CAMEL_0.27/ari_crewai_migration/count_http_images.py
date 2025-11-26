#!/usr/bin/env python3
"""
Count products with HTTP URLs in images field
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path("/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27")
load_dotenv(PROJECT_ROOT / ".env")

NEO4J_URI = os.getenv("NEO4J_URL")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "productionbackup2")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

print("Checking image URL types...")

with driver.session(database=NEO4J_DATABASE) as session:
    # Count products with 'http' in images
    result = session.run("""
        MATCH (p:Product)
        WHERE p.images IS NOT NULL
        AND p.images CONTAINS 'http'
        RETURN count(p) AS count
    """)
    http_count = result.single()['count']
    print(f"Products with 'http' in images: {http_count}")

    # Count products with 'https' in images
    result = session.run("""
        MATCH (p:Product)
        WHERE p.images IS NOT NULL
        AND p.images CONTAINS 'https'
        RETURN count(p) AS count
    """)
    https_count = result.single()['count']
    print(f"Products with 'https' in images: {https_count}")

    # Get a sample of products with https URLs
    print("\nSample products with HTTPS URLs:")
    result = session.run("""
        MATCH (p:Product)
        WHERE p.images IS NOT NULL
        AND p.images CONTAINS 'https'
        RETURN p.id, p.title, p.images
        LIMIT 5
    """)
    for record in result:
        print(f"\nID: {record['p.id']}")
        print(f"Title: {record['p.title']}")
        print(f"Images: {record['p.images'][:200]}")

driver.close()
