#!/usr/bin/env python3
"""
Diagnose why all bots return 0 results
"""

import asyncio
import sys
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

from dotenv import load_dotenv
load_dotenv()

async def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE BOT DIAGNOSIS")
    print("="*80)
    
    query = "professional blazer for interview"
    
    # Test 1: Neo4j Direct
    print("\n1. Testing Neo4j Direct Connection")
    print("-"*80)
    from neo4j import AsyncGraphDatabase
    driver = AsyncGraphDatabase.driver(
        "neo4j://34.135.40.119:7687",
        auth=("neo4j", "shopari1234")
    )
    
    async with driver.session(database="productionbackup2") as session:
        result = await session.run("""
            MATCH (p:Product)
            WHERE toLower(p.title) CONTAINS 'blazer' 
               OR toLower(p.description) CONTAINS 'blazer'
            RETURN p.id, p.title, p.price
            LIMIT 5
        """)
        
        count = 0
        async for record in result:
            count += 1
            print(f"  ✓ {record['p.title'][:50]}")
        
        print(f"\n  Result: Found {count} products")
        if count == 0:
            print("  ❌ ERROR: Neo4j has no blazers!")
        else:
            print("  ✅ Neo4j working correctly")
    
    await driver.close()
    
    # Test 2: Qdrant Collections
    print("\n2. Testing Qdrant Collections")
    print("-"*80)
    from qdrant_client import QdrantClient
    import os
    
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
        prefer_grpc=False
    )
    
    collections = client.get_collections().collections
    print(f"  Found {len(collections)} collections:")
    for col in collections:
        info = client.get_collection(col.name)
        print(f"    - {col.name}: {info.points_count:,} points")
    
    # Test 3: VibeBot Collection
    print("\n3. Testing VibeBot Collection (fashion_products)")
    print("-"*80)
    
    try:
        from services.ml.fashionsig_encoder import get_fashionsig_encoder
        
        # Generate embedding
        encoder = get_fashionsig_encoder()
        embedding = await encoder.encode_text(query)
        
        # Search Qdrant
        results = client.search(
            collection_name="fashion_products",
            query_vector=embedding.tolist(),
            limit=5,
            score_threshold=0.0  # No threshold
        )
        
        print(f"  Results with threshold=0.0: {len(results)}")
        if len(results) > 0:
            for i, r in enumerate(results[:3]):
                print(f"    {i+1}. Score={r.score:.3f} | {r.payload.get('title', 'N/A')[:50]}")
            print("  ✅ VibeBot collection working")
        else:
            print("  ❌ ERROR: No results even with threshold=0!")
            
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    # Test 4: VisionBot Collection  
    print("\n4. Testing VisionBot Collection (fashion_fashionsig_neo4j_1024d)")
    print("-"*80)
    
    try:
        results = client.search(
            collection_name="fashion_fashionsig_neo4j_1024d",
            query_vector=embedding.tolist(),
            limit=5,
            score_threshold=0.0
        )
        
        print(f"  Results with threshold=0.0: {len(results)}")
        if len(results) > 0:
            for i, r in enumerate(results[:3]):
                print(f"    {i+1}. Score={r.score:.3f}")
            print("  ⚠️  Vision collection has results but scores are low (text/vision mismatch)")
        else:
            print("  ❌ ERROR: No results even with threshold=0!")
            
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
    
    print("\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
