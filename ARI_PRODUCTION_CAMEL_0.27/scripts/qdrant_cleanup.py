#!/usr/bin/env python3
"""
Qdrant Cleanup Script
Cleans up old embeddings and ensures consistency with new UUID-based Neo4j graph
"""

import asyncio
import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models

async def main():
    print("QDRANT CLEANUP SCRIPT")
    print("=" * 60)
    
    # Load environment variables
    qdrant_url = os.environ.get('QDRANT_URL', 'https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io')
    qdrant_api_key = os.environ.get('QDRANT_API_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg')
    collection_name = os.environ.get('QDRANT_COLLECTION_NAME', 'fashion_products')
    
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    try:
        # 1. Analyze current collection
        print(f" ANALYZING COLLECTION: {collection_name}")
        print("-" * 40)
        
        collection_info = client.get_collection(collection_name)
        vectors_count = collection_info.vectors_count or 0
        print(f"Total vectors: {vectors_count:,}")
        print(f"Collection status: {collection_info.status}")
        
        if vectors_count == 0:
            print(" Collection is already empty - no cleanup needed")
            return
        
        # 2. Sample analysis
        print(f"\nSAMPLING VECTORS")
        print("-" * 40)
        
        points, _ = client.scroll(collection_name, limit=10)
        if not points:
            print("WARNING: No points found despite non-zero count")
            return
            
        # Analyze ID formats
        uuid_count = 0
        numeric_count = 0
        id_samples = []
        
        for point in points:
            point_id = str(point.id)
            id_samples.append(point_id)
            
            if len(point_id) > 20 and '-' in point_id:
                uuid_count += 1
            else:
                numeric_count += 1
        
        print(f"🆔 UUID format IDs: {uuid_count}")
        print(f"🔢 Numeric format IDs: {numeric_count}")
        print(f"Sample IDs: {id_samples[:3]}")
        
        # 3. Check payload structure
        sample_payload = points[0].payload
        print(f"🏷️ Sample payload keys: {list(sample_payload.keys())}")
        
        # 4. Decision logic
        print(f"\n🤔 CLEANUP ANALYSIS")
        print("-" * 40)
        
        needs_cleanup = False
        cleanup_reason = []
        
        if numeric_count > 0:
            needs_cleanup = True
            cleanup_reason.append(f"{numeric_count} old numeric IDs found")
            
        # Check if we have mixed formats
        if uuid_count > 0 and numeric_count > 0:
            cleanup_reason.append("Mixed ID formats detected")
            
        # Check payload structure for old vs new fields
        expected_fields = ['title', 'category', 'price', 'brand', 'description']
        missing_fields = [f for f in expected_fields if f not in sample_payload]
        if missing_fields:
            cleanup_reason.append(f"Missing expected fields: {missing_fields}")
        
        if not needs_cleanup:
            print(" Collection appears to be up-to-date with new UUID format")
            return
            
        print(f"WARNING: Cleanup needed:")
        for reason in cleanup_reason:
            print(f"   - {reason}")
        
        # 5. Ask for confirmation
        print(f"\n CLEANUP OPTIONS")
        print("-" * 40)
        print("1. [SAFE] Delete only numeric ID vectors (preserve UUID vectors)")
        print("2. [COMPLETE] Delete entire collection and recreate")
        print("3. [CANCEL] Exit without changes")
        
        choice = input("\nEnter choice (1/2/3): ").strip()
        
        if choice == "1":
            await safe_cleanup(client, collection_name, points)
        elif choice == "2":
            await complete_cleanup(client, collection_name)
        else:
            print(" Cleanup cancelled")
            
    except Exception as e:
        print(f" Error during cleanup: {e}")

async def safe_cleanup(client: QdrantClient, collection_name: str, points: List):
    """Delete only vectors with numeric IDs (old format)"""
    print(f"\n🛡️ SAFE CLEANUP: Removing only numeric ID vectors")
    print("-" * 50)
    
    numeric_ids = []
    for point in points:
        point_id = str(point.id)
        if not (len(point_id) > 20 and '-' in point_id):
            numeric_ids.append(point.id)
    
    if not numeric_ids:
        print(" No numeric IDs found to clean up")
        return
    
    print(f"🗑️ Found {len(numeric_ids)} numeric ID vectors to delete")
    print(f"Sample numeric IDs: {numeric_ids[:5]}")
    
    confirm = input(f"Confirm deletion of {len(numeric_ids)} old vectors? (yes/no): ")
    if confirm.lower() != 'yes':
        print(" Deletion cancelled")
        return
    
    try:
        # Delete in batches
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(numeric_ids), batch_size):
            batch = numeric_ids[i:i + batch_size]
            client.delete(
                collection_name=collection_name,
                points_selector=models.PointIdsList(points=batch)
            )
            deleted_count += len(batch)
            print(f"🗑️ Deleted batch {i//batch_size + 1}: {len(batch)} vectors ({deleted_count}/{len(numeric_ids)})")
        
        print(f" Safe cleanup completed! Deleted {deleted_count} old numeric ID vectors")
        
        # Verify
        collection_info = client.get_collection(collection_name)
        vectors_count = collection_info.vectors_count or 0
        print(f"Remaining vectors: {vectors_count:,}")
        
    except Exception as e:
        print(f" Error during safe cleanup: {e}")

async def complete_cleanup(client: QdrantClient, collection_name: str):
    """Delete entire collection and recreate"""
    print(f"\nCOMPLETE CLEANUP: Recreating entire collection")
    print("-" * 50)
    
    print("WARNING: This will DELETE ALL vectors in the collection!")
    confirm = input("Type 'DELETE_ALL' to confirm complete cleanup: ")
    if confirm != 'DELETE_ALL':
        print(" Complete cleanup cancelled")
        return
    
    try:
        # Delete collection
        print("🗑️ Deleting collection...")
        client.delete_collection(collection_name)
        
        # Recreate collection
        print("🔄 Recreating collection...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=1536,  # OpenAI embedding dimension
                distance=models.Distance.COSINE
            )
        )
        
        print(" Complete cleanup successful!")
        print("ℹ️ Collection is now empty and ready for new embeddings")
        
        # Verify
        collection_info = client.get_collection(collection_name)
        vectors_count = collection_info.vectors_count or 0
        print(f"Vector count: {vectors_count}")
        
    except Exception as e:
        print(f" Error during complete cleanup: {e}")

def verify_neo4j_consistency():
    """Check if Neo4j graph has UUID-based product IDs"""
    print(f"\n🔗 NEO4J CONSISTENCY CHECK")
    print("-" * 40)
    
    try:
        # This would require Neo4j connection
        print("ℹ️ Run this separately to verify Neo4j has UUID product IDs:")
        print("   MATCH (p:Product) RETURN p.id LIMIT 5")
        print("   Expected: UUID format like '123e4567-e89b-12d3-a456-426614174000'")
        
    except Exception as e:
        print(f"WARNING: Neo4j check not implemented: {e}")

if __name__ == "__main__":
    print(" Starting Qdrant cleanup...")
    
    # Load environment
    from dotenv import load_dotenv
    if os.path.exists('.env'):
        load_dotenv('.env')
        print("📁 Loaded .env file")
    
    asyncio.run(main())