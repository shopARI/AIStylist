"""
Inspect Neo4j Product Graph Schema
This script connects to Neo4j and reports:
1. What properties exist on Product nodes
2. What indexes are available
3. Sample Product data
NOT used in runtime - used for seeing what's actually in the neo4j for migrations, sanity checks etc
"""
import os
import asyncio
from dotenv import load_dotenv
from neo4j import AsyncGraphDatabase

load_dotenv()

async def inspect_neo4j_schema():
    """Inspect Neo4j Product Graph schema"""
    # Get Neo4j connection details from environment
    neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "")

    print("="*70)
    print("NEO4J PRODUCT GRAPH SCHEMA INSPECTION")
    print("="*70)
    print(f"\nConnecting to: {neo4j_uri}")
    print(f"User: {neo4j_user}")

    driver = AsyncGraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_user, neo4j_password)
    )

    try:
        async with driver.session() as session:
            # 1. Get all node labels
            print("\n" + "="*70)
            print("1. NODE LABELS IN DATABASE")
            print("="*70)
            result = await session.run("CALL db.labels()")
            labels = []
            async for record in result:
                label = record[0]
                labels.append(label)
                print(f"  - {label}")

            # 2. Get Product node count
            print("\n" + "="*70)
            print("2. PRODUCT NODE COUNT")
            print("="*70)
            result = await session.run("MATCH (p:Product) RETURN count(p) as count")
            async for record in result:
                print(f"  Total Products: {record['count']:,}")

            # 3. Get sample Product properties
            print("\n" + "="*70)
            print("3. SAMPLE PRODUCT PROPERTIES (first 3 products)")
            print("="*70)
            result = await session.run("MATCH (p:Product) RETURN p LIMIT 3")
            sample_count = 0
            all_properties = set()
            async for record in result:
                sample_count += 1
                product = dict(record['p'])
                print(f"\nProduct #{sample_count}:")
                for key, value in product.items():
                    all_properties.add(key)
                    # Truncate long values
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    elif isinstance(value, list) and len(value) > 3:
                        value = value[:3] + ["..."]
                    print(f"  {key}: {value}")

            # 4. List all unique properties on Product nodes
            print("\n" + "="*70)
            print("4. ALL PRODUCT NODE PROPERTIES")
            print("="*70)
            print("Properties found across all sampled products:")
            for prop in sorted(all_properties):
                print(f"  - {prop}")

            # 5. Get property schema from one product
            print("\n" + "="*70)
            print("5. PROPERTY TYPES (from schema)")
            print("="*70)
            result = await session.run("""
                MATCH (p:Product)
                WITH p LIMIT 1
                RETURN keys(p) as properties
            """)
            async for record in result:
                props = record['properties']
                print(f"  Total property keys on Product: {len(props)}")
                print(f"  Properties: {', '.join(sorted(props))}")

            # 6. Get all indexes
            print("\n" + "="*70)
            print("6. DATABASE INDEXES")
            print("="*70)
            result = await session.run("SHOW INDEXES")
            indexes = []
            async for record in result:
                index_info = dict(record)
                indexes.append(index_info)
                print(f"\nIndex: {index_info.get('name', 'N/A')}")
                print(f"  Type: {index_info.get('type', 'N/A')}")
                print(f"  Entity Type: {index_info.get('entityType', 'N/A')}")
                print(f"  Labels/Types: {index_info.get('labelsOrTypes', 'N/A')}")
                print(f"  Properties: {index_info.get('properties', 'N/A')}")
                print(f"  State: {index_info.get('state', 'N/A')}")

            if not indexes:
                print("  No indexes found!")

            # 7. Check for fulltext indexes specifically
            print("\n" + "="*70)
            print("7. FULLTEXT INDEXES (if any)")
            print("="*70)
            try:
                result = await session.run("CALL db.indexes() YIELD name, type, labelsOrTypes, properties WHERE type = 'FULLTEXT' RETURN name, labelsOrTypes, properties")
                fulltext_count = 0
                async for record in result:
                    fulltext_count += 1
                    print(f"\nFulltext Index: {record['name']}")
                    print(f"  Labels: {record['labelsOrTypes']}")
                    print(f"  Properties: {record['properties']}")

                if fulltext_count == 0:
                    print("  No fulltext indexes found!")
            except Exception as e:
                print(f"  Error checking fulltext indexes: {e}")

            # 8. Sample queries that should work
            print("\n" + "="*70)
            print("8. TEST QUERIES")
            print("="*70)

            # Test: Find products with 'black' in title
            print("\nTest 1: Products with 'black' in title (CONTAINS)")
            result = await session.run("""
                MATCH (p:Product)
                WHERE toLower(p.title) CONTAINS 'black'
                RETURN p
                LIMIT 5
            """)
            count = 0
            async for record in result:
                count += 1
                product = dict(record['p'])
                print(f"  {count}. {product.get('title', 'N/A')}")
                print(f"     ID: {product.get('id', 'N/A')}")
                print(f"     Category: {product.get('category', 'N/A')}")
                print(f"     Price: ${product.get('price', 'N/A')}")
            print(f"  Found: {count} products")

            # Test: Find products with 'shirt' in title or category
            print("\nTest 2: Products with 'shirt' in title or category")
            result = await session.run("""
                MATCH (p:Product)
                WHERE toLower(p.title) CONTAINS 'shirt' OR toLower(p.category) CONTAINS 'shirt'
                RETURN p
                LIMIT 5
            """)
            count = 0
            async for record in result:
                count += 1
                product = dict(record['p'])
                print(f"  {count}. {product.get('title', 'N/A')}")
                print(f"     ID: {product.get('id', 'N/A')}")
                print(f"     Category: {product.get('category', 'N/A')}")
            print(f"  Found: {count} products")

            # 9. Check what categories exist
            print("\n" + "="*70)
            print("9. UNIQUE CATEGORIES (first 30)")
            print("="*70)
            result = await session.run("""
                MATCH (p:Product)
                WITH p.category as category, count(*) as count
                RETURN category, count
                ORDER BY count DESC
                LIMIT 30
            """)
            async for record in result:
                cat = record['category']
                if cat and len(cat) > 80:
                    cat = cat[:80] + "..."
                print(f"  {cat}: {record['count']:,} products")

            # 10. Check fashion_category values
            print("\n" + "="*70)
            print("10. UNIQUE FASHION_CATEGORIES (first 20)")
            print("="*70)
            result = await session.run("""
                MATCH (p:Product)
                WHERE p.fashion_category IS NOT NULL
                WITH p.fashion_category as fashion_category, count(*) as count
                RETURN fashion_category, count
                ORDER BY count DESC
                LIMIT 20
            """)
            async for record in result:
                print(f"  {record['fashion_category']}: {record['count']:,} products")

    finally:
        await driver.close()

    print("\n" + "="*70)
    print("SCHEMA INSPECTION COMPLETE")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(inspect_neo4j_schema())
