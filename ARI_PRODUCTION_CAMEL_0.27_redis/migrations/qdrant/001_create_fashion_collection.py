"""
Qdrant Migration: Create Fashion Products Collection
Sets up vector collection with proper configuration for fashion product embeddings
"""

from qdrant_client.models import Distance, VectorParams, CollectionInfo

async def up(qdrant_client):
    """Apply migration - create fashion products collection."""
    
    collection_name = qdrant_client.collection_name
    
    try:
        # Check if collection already exists
        collections = await qdrant_client.client.get_collections()
        existing_collections = [col.name for col in collections.collections]
        
        if collection_name in existing_collections:
            print(f"✅ Collection '{collection_name}' already exists, skipping creation")
            return
        
        # Create collection with optimal settings for fashion embeddings
        await qdrant_client.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=1536,  # OpenAI text-embedding-3-small dimension
                distance=Distance.COSINE,  # Cosine similarity for text embeddings
                on_disk=True  # Store vectors on disk for large datasets (20-30M products)
            ),
            optimizers_config={
                "default_segment_number": 16,  # Optimize for large dataset
                "max_segment_size": 200000,    # 200k points per segment
                "memmap_threshold": 50000,     # Use memory mapping for large segments
                "indexing_threshold": 10000,   # Start indexing after 10k points
                "flush_interval_sec": 30,      # Flush every 30 seconds
                "max_optimization_threads": 4  # Parallel optimization
            },
            hnsw_config={
                "m": 32,           # Higher connectivity for better recall
                "ef_construct": 256, # Higher for better index quality
                "full_scan_threshold": 10000,  # Use full scan for small datasets
                "max_indexing_threads": 4,     # Parallel indexing
                "on_disk": True    # Store index on disk
            },
            shard_number=2,  # Use 2 shards for better performance
            replication_factor=1  # Single replica for now
        )
        
        print(f"✅ Created Qdrant collection '{collection_name}' with optimized settings")
        
    except Exception as e:
        print(f"❌ Failed to create collection: {e}")
        raise

async def down(qdrant_client):
    """Rollback migration - delete collection."""
    
    collection_name = qdrant_client.collection_name
    
    try:
        # Check if collection exists before deleting
        collections = await qdrant_client.client.get_collections()
        existing_collections = [col.name for col in collections.collections]
        
        if collection_name not in existing_collections:
            print(f"✅ Collection '{collection_name}' does not exist, skipping deletion")
            return
        
        # WARNING: This will delete all data in the collection
        await qdrant_client.client.delete_collection(collection_name)
        print(f"✅ Deleted Qdrant collection '{collection_name}'")
        
    except Exception as e:
        print(f"❌ Failed to delete collection: {e}")
        raise