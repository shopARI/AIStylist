#!/usr/bin/env python3
"""
Check Qdrant collections status and verify VisionBot collection
"""

import asyncio
from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()

async def check_collections():
    """Check all Qdrant collections"""

    # Connect to Qdrant
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")

    print(f"Connecting to Qdrant: {qdrant_url}")

    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
        prefer_grpc=False,
        timeout=30.0
    )

    # List all collections
    collections = client.get_collections().collections
    print(f"\n{'='*80}")
    print(f"QDRANT COLLECTIONS ({len(collections)} total)")
    print(f"{'='*80}\n")

    for collection in collections:
        print(f"Collection: {collection.name}")

        # Get detailed info
        info = client.get_collection(collection.name)
        print(f"  Points: {info.points_count:,}")
        print(f"  Status: {info.status}")

        # Check vector config
        vectors_config = info.config.params.vectors
        if hasattr(vectors_config, 'items'):
            # Named vectors
            print(f"  Vectors (named):")
            for name, config in vectors_config.items():
                print(f"    - {name}: {config.size}d, {config.distance}")
        else:
            # Single vector
            print(f"  Vector: {vectors_config.size}d, {vectors_config.distance}")

        print()

    # Check specific collection used by VisionBot
    visionbot_collection = "fashion_fashionsig_neo4j_1024d"
    print(f"\n{'='*80}")
    print(f"VISIONBOT COLLECTION CHECK: {visionbot_collection}")
    print(f"{'='*80}\n")

    collection_names = [c.name for c in collections]
    if visionbot_collection in collection_names:
        info = client.get_collection(visionbot_collection)
        print(f"✓ Collection EXISTS")
        print(f"  Points: {info.points_count:,}")
        print(f"  Status: {info.status}")

        # Get a sample point to verify structure
        scroll_result = client.scroll(
            collection_name=visionbot_collection,
            limit=1,
            with_payload=True,
            with_vectors=False
        )

        if scroll_result[0]:
            sample = scroll_result[0][0]
            print(f"\n  Sample point:")
            print(f"    ID: {sample.id}")
            print(f"    Payload keys: {list(sample.payload.keys())}")
            print(f"    Product ID: {sample.payload.get('product_id')}")
            print(f"    Name: {sample.payload.get('name', 'N/A')[:60]}...")
            print(f"    Embedding type: {sample.payload.get('embedding_type', 'N/A')}")
            print(f"    Description: {sample.payload.get('description', 'N/A')[:80]}...")
        else:
            print(f"\n  ⚠️  Collection has 0 points!")
    else:
        print(f"❌ Collection NOT FOUND")
        print(f"   Available collections: {collection_names}")

if __name__ == "__main__":
    asyncio.run(check_collections())
