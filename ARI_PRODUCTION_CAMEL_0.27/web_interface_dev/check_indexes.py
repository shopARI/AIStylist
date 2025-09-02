#!/usr/bin/env python3
import asyncio
from services.user.knowledge_graph import UserKnowledgeGraphService
import os

async def check_indexes():
    neo4j = UserKnowledgeGraphService(
        url=os.getenv('NEO4J_URL'),
        username=os.getenv('NEO4J_USERNAME'), 
        password=os.getenv('NEO4J_PASSWORD')
    )
    await neo4j.initialize()
    
    print('📊 CHECKING NEO4J INDEXES:')
    # Try newer syntax first, fallback to older
    try:
        indexes_query = 'CALL db.indexes() YIELD name, labelsOrTypes, properties, type, state'
        indexes = await neo4j.query(indexes_query, timeout=10.0)
        for record in indexes:
            print(f'  {record["name"]}: {record["labelsOrTypes"]} - {record["properties"]} ({record["type"]}) - {record["state"]}')
    except Exception as e:
        print(f'Newer syntax failed: {e}')
        try:
            # Older Neo4j syntax
            indexes_query = 'CALL db.indexes'
            indexes = await neo4j.query(indexes_query, timeout=10.0)
            for record in indexes:
                print(f'  Index: {record}')
        except Exception as e2:
            print(f'Older syntax also failed: {e2}')
            # Fallback: check if specific indexes exist by trying to use them
            print('Trying to detect indexes by testing queries...')
            
    # Check Product properties that could benefit from indexes
    print('\n📊 PRODUCT PROPERTY ANALYSIS:')
    try:
        # First get any product to see what properties exist
        sample_query = """
        MATCH (p:Product) 
        RETURN p
        LIMIT 3
        """
        samples = await neo4j.query(sample_query, timeout=10.0)
        for i, record in enumerate(samples):
            product = dict(record['p'])
            print(f"  Sample {i+1} properties: {list(product.keys())}")
            # Show a few key properties
            for key in ['id', 'title', 'product_type', 'is_fashion', 'description']:
                if key in product:
                    value = str(product[key])[:50] + '...' if len(str(product[key])) > 50 else product[key]
                    print(f"    {key}: {value}")
    except Exception as e:
        print(f'Error getting product samples: {e}')
    
    # Test query performance
    print('\n⏱️ QUERY PERFORMANCE TEST:')
    try:
        import time
        start = time.time()
        count_query = "MATCH (p:Product) RETURN count(p) as count"
        result = await neo4j.query(count_query, timeout=20.0)
        end = time.time()
        count = result[0]['count'] if result else 0
        print(f"  Product count query: {count:,} products in {end-start:.2f}s")
    except Exception as e:
        print(f'Error getting product count: {e}')
    
    await neo4j.close()

if __name__ == "__main__":
    asyncio.run(check_indexes())