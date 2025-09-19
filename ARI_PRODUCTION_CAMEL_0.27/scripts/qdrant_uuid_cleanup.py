#!/usr/bin/env python3
"""
Qdrant UUID Cleanup Script
- Remove duplicate UUIDs (keep only one copy of each)
- Remove orphaned UUIDs (not in current Neo4j)
- Remove old numeric IDs
- Keep only valid UUIDs that exist in Neo4j
"""

import os
import asyncio
from typing import Set, Dict, List, Any
from collections import defaultdict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from neo4j import GraphDatabase

class QdrantUUIDCleaner:
    def __init__(self):
        # Qdrant connection
        self.qdrant_url = os.environ.get('QDRANT_URL', 'https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io')
        self.qdrant_api_key = os.environ.get('QDRANT_API_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg')
        self.collection_name = os.environ.get('QDRANT_COLLECTION_NAME', 'fashion_products')
        
        # Neo4j connection
        self.neo4j_url = os.environ.get('NEO4J_URL', 'bolt://0.0.0.0:17687')
        self.neo4j_username = os.environ.get('NEO4J_USERNAME', 'neo4j')
        self.neo4j_password = os.environ.get('NEO4J_PASSWORD', '6D%q@jbYmstkK2i3oW5z6B6outew9m93')
        
        self.qdrant_client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
        self.neo4j_driver = None

    async def run_cleanup(self):
        print("🧹 QDRANT UUID CLEANUP")
        print("=" * 60)
        
        try:
            # 1. Connect to Neo4j
            print("🔗 Connecting to Neo4j...")
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_url,
                auth=(self.neo4j_username, self.neo4j_password)
            )
            self.neo4j_driver.verify_connectivity()
            print(" Neo4j connected")
            
            # 2. Get valid UUIDs from Neo4j
            print("\nGetting valid UUIDs from Neo4j...")
            valid_uuids = await self.get_valid_neo4j_uuids()
            print(f" Found {len(valid_uuids):,} valid UUIDs in Neo4j")
            
            # 3. Analyze Qdrant collection
            print(f"\n Analyzing Qdrant collection: {self.collection_name}...")
            await self.analyze_qdrant_collection(valid_uuids)
            
        finally:
            if self.neo4j_driver:
                self.neo4j_driver.close()
                print("🔌 Neo4j connection closed")
    
    async def get_valid_neo4j_uuids(self) -> Set[str]:
        """Get all valid product UUIDs from Neo4j"""
        with self.neo4j_driver.session() as session:
            # Query all product UUIDs - remove limit to get ALL valid UUIDs
            result = session.run("MATCH (p:Product) RETURN p.id as uuid")
            
            valid_uuids = set()
            for record in result:
                uuid = record["uuid"]
                if uuid and isinstance(uuid, str) and len(uuid) > 20 and '-' in uuid:
                    valid_uuids.add(uuid)
            
            return valid_uuids
    
    async def analyze_qdrant_collection(self, valid_uuids: Set[str]):
        """Analyze Qdrant and perform cleanup"""
        # Use count() method instead of vectors_count (which can be stale)
        try:
            count_result = self.qdrant_client.count(self.collection_name)
            total_vectors = count_result.count if hasattr(count_result, 'count') else 0
        except:
            collection_info = self.qdrant_client.get_collection(self.collection_name)  
            total_vectors = collection_info.vectors_count or 0
        
        print(f"Total vectors in Qdrant: {total_vectors:,}")
        
        if total_vectors == 0:
            print(" Collection is empty - no cleanup needed")
            return
        
        # Scan all points
        print("🔄 Scanning all vectors...")
        
        all_points = []
        next_page_offset = None
        scanned = 0
        
        while True:
            points, next_page_offset = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=next_page_offset
            )
            
            all_points.extend(points)
            scanned += len(points)
            print(f"   📄 Scanned {scanned:,}/{total_vectors:,} vectors")
            
            if next_page_offset is None or len(points) == 0:
                break
        
        print(f" Scanned {len(all_points):,} total points")
        
        # Categorize points
        await self.categorize_and_cleanup(all_points, valid_uuids)
    
    async def categorize_and_cleanup(self, all_points: List, valid_uuids: Set[str]):
        """Categorize points and perform cleanup"""
        print("\n📂 Categorizing vectors...")
        
        # Categories
        valid_points = []           # UUID exists in Neo4j
        duplicate_points = []       # Same UUID appears multiple times
        orphaned_points = []        # UUID not in Neo4j
        numeric_points = []         # Old numeric IDs
        
        # Track duplicates
        uuid_counts = defaultdict(list)
        
        for point in all_points:
            point_id = str(point.id)
            
            # Check if numeric (old format)
            if not (len(point_id) > 20 and '-' in point_id):
                numeric_points.append(point)
                continue
            
            # Check if UUID exists in Neo4j
            if point_id in valid_uuids:
                uuid_counts[point_id].append(point)
            else:
                orphaned_points.append(point)
        
        # Separate valid from duplicates
        for uuid, points_list in uuid_counts.items():
            if len(points_list) == 1:
                valid_points.extend(points_list)
            else:
                # Keep first, mark rest as duplicates
                valid_points.append(points_list[0])
                duplicate_points.extend(points_list[1:])
        
        # Report analysis
        print(f" Valid vectors (UUID in Neo4j): {len(valid_points):,}")
        print(f"🔄 Duplicate vectors (same UUID): {len(duplicate_points):,}")
        print(f"👻 Orphaned vectors (UUID not in Neo4j): {len(orphaned_points):,}")
        print(f"🔢 Numeric ID vectors (old format): {len(numeric_points):,}")
        
        # Calculate cleanup
        to_delete = duplicate_points + orphaned_points + numeric_points
        print(f"\n🗑️ Total vectors to delete: {len(to_delete):,}")
        print(f"💾 Vectors to keep: {len(valid_points):,}")
        
        if len(to_delete) == 0:
            print(" No cleanup needed - collection is already clean!")
            return
        
        # Ask for confirmation
        print(f"\nCLEANUP SUMMARY:")
        print(f"   🗑️ Delete {len(duplicate_points):,} duplicates")
        print(f"   🗑️ Delete {len(orphaned_points):,} orphaned UUIDs")  
        print(f"   🗑️ Delete {len(numeric_points):,} old numeric IDs")
        print(f"   💾 Keep {len(valid_points):,} valid UUIDs")
        
        # Auto-confirm deletion (user pre-authorized)
        print(f" Auto-confirmed: Proceeding with deletion of {len(to_delete):,} vectors")
        
        # Perform deletion
        await self.delete_vectors(to_delete)
        
        # Verify final state
        print(f"\n CLEANUP COMPLETE!")
        collection_info = self.qdrant_client.get_collection(self.collection_name)
        final_count = collection_info.vectors_count or 0
        print(f"Final vector count: {final_count:,}")
        print(f" Expected count: {len(valid_points):,}")
        
        if final_count == len(valid_points):
            print(" Perfect! Cleanup successful!")
        else:
            print("WARNING: Count mismatch - may need to wait for Qdrant to update")
    
    async def delete_vectors(self, to_delete: List):
        """Delete vectors in batches"""
        print(f"\n🗑️ Deleting {len(to_delete):,} vectors...")
        
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(to_delete), batch_size):
            batch = to_delete[i:i + batch_size]
            batch_ids = [point.id for point in batch]
            
            try:
                self.qdrant_client.delete(
                    collection_name=self.collection_name,
                    points_selector=models.PointIdsList(points=batch_ids)
                )
                deleted_count += len(batch_ids)
                print(f"   🗑️ Batch {i//batch_size + 1}: Deleted {len(batch_ids)} vectors ({deleted_count:,}/{len(to_delete):,})")
                
            except Exception as e:
                print(f"    Error deleting batch {i//batch_size + 1}: {e}")

async def main():
    cleaner = QdrantUUIDCleaner()
    await cleaner.run_cleanup()

if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    if os.path.exists('.env'):
        load_dotenv('.env')
        print("📁 Loaded .env file")
    
    asyncio.run(main())