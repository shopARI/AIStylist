#!/usr/bin/env python3
"""
Direct Neo4j connection - bypass Redis/full app stack.
Check actual Product node properties in production database.
"""
import asyncio
import os
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

async def check_real_schema():
    """Connect directly to Neo4j and check what actually exists"""

    neo4j_uri = os.getenv("NEO4J_URL", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    print(f"Connecting to Neo4j at {neo4j_uri}...")

    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )

    try:
        async with driver.session() as session:
            # 1. Get one sample product with ALL its properties
            print("\n" + "="*70)
            print("SAMPLE PRODUCT NODE (all properties):")
            print("="*70)

            result = await session.run('MATCH (p:Product) RETURN p LIMIT 1')
            record = await result.single()

            if record:
                product = dict(record['p'])
                for key in sorted(product.keys()):
                    value = product[key]
                    value_type = type(value).__name__

                    if isinstance(value, str):
                        sample = value[:50] + "..." if len(value) > 50 else value
                    elif isinstance(value, list):
                        sample = f"[{len(value)} items]" + (f" e.g. {value[:2]}" if value else "")
                    else:
                        sample = str(value)

                    print(f"  {key:25s} ({value_type:10s}): {sample}")

            # 2. Count node types
            print("\n" + "="*70)
            print("NODE COUNTS:")
            print("="*70)

            node_types = ['Product', 'Brand', 'Collection', 'Tag', 'Attribute', 'Color', 'Style', 'User']
            for node_type in node_types:
                result = await session.run(f'MATCH (n:{node_type}) RETURN count(n) as count')
                record = await result.single()
                count = record['count'] if record else 0
                print(f"  {node_type:15s}: {count:,}")

            # 3. Count relationship types
            print("\n" + "="*70)
            print("RELATIONSHIP COUNTS:")
            print("="*70)

            rel_query = """
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(r) as count
            ORDER BY count DESC
            """
            result = await session.run(rel_query)
            async for record in result:
                rel_type = record['rel_type']
                count = record['count']
                print(f"  {rel_type:25s}: {count:,}")

            # 4. Check property coverage on Products
            print("\n" + "="*70)
            print("PRODUCT PROPERTY COVERAGE (sample 1000):")
            print("="*70)

            # Get all possible properties from 1000 products
            result = await session.run('MATCH (p:Product) RETURN p LIMIT 1000')
            all_properties = set()
            property_counts = {}

            async for record in result:
                product = dict(record['p'])
                for key in product.keys():
                    all_properties.add(key)
                    if product[key] is not None and product[key] != '' and product[key] != []:
                        property_counts[key] = property_counts.get(key, 0) + 1

            for prop in sorted(all_properties):
                count = property_counts.get(prop, 0)
                coverage = (count / 1000) * 100
                print(f"  {prop:25s}: {count:4d}/1000 ({coverage:5.1f}% coverage)")

            # 5. Sample a product with extracted_colors to verify
            print("\n" + "="*70)
            print("SAMPLE PRODUCT WITH EXTRACTED METADATA (if any):")
            print("="*70)

            result = await session.run("""
                MATCH (p:Product)
                WHERE p.extracted_colors IS NOT NULL
                RETURN p LIMIT 1
            """)
            record = await result.single()

            if record:
                product = dict(record['p'])
                print(f"  Found product with extracted metadata:")
                print(f"  Title: {product.get('title', 'N/A')}")
                print(f"  extracted_colors: {product.get('extracted_colors', 'N/A')}")
                print(f"  extracted_brand: {product.get('extracted_brand', 'N/A')}")
                print(f"  ai_category: {product.get('ai_category', 'N/A')}")
                print(f"  formality_level: {product.get('formality_level', 'N/A')}")
                print(f"  target_demographic: {product.get('target_demographic', 'N/A')}")
            else:
                print("  No products with extracted_colors found in database")

    finally:
        await driver.close()
        print("\n" + "="*70)
        print("Connection closed")

if __name__ == "__main__":
    asyncio.run(check_real_schema())
