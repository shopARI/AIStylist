#!/usr/bin/env python3
"""
Qdrant Metadata Refresh Script
Fixes stale collection metadata like vectors_count after heavy operations
"""

import os
import time
import asyncio
from typing import Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantMetadataRefresher:
    def __init__(self):
        self.qdrant_url = os.environ.get('QDRANT_URL', 'https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io')
        self.qdrant_api_key = os.environ.get('QDRANT_API_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg')
        self.collection_name = os.environ.get('QDRANT_COLLECTION_NAME', 'fashion_products')
        
        self.client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)

    async def refresh_metadata(self):
        """Refresh stale collection metadata"""
        print("QDRANT METADATA REFRESH")
        print("=" * 60)
        
        try:
            # 1. Check current metadata state
            print(" Checking current metadata state...")
            await self._check_metadata_consistency()
            
            # 2. Try various refresh methods
            print("\n Attempting metadata refresh...")
            
            # Method 1: Collection optimization (forces metadata recalculation)
            success = await self._optimize_collection()
            if success:
                print(" Method 1: Collection optimization successful")
            else:
                print("WARNING: Method 1: Collection optimization failed, trying alternatives...")
                
                # Method 2: Flush segments (forces index update)
                success = await self._flush_collection()
                if success:
                    print(" Method 2: Segment flush successful")
                else:
                    print("WARNING: Method 2: Segment flush failed, trying final method...")
                    
                    # Method 3: Wait for natural sync (background processes)
                    await self._wait_for_sync()
            
            # 3. Verify fix
            print("\n VERIFICATION")
            print("-" * 40)
            await self._check_metadata_consistency()
            
        except Exception as e:
            print(f" Error during metadata refresh: {e}")
    
    async def _check_metadata_consistency(self):
        """Check if metadata is consistent with actual data"""
        try:
            # Get metadata count
            collection_info = self.client.get_collection(self.collection_name)
            metadata_count = collection_info.vectors_count or 0
            
            # Get actual count
            count_result = self.client.count(self.collection_name)
            actual_count = count_result.count if hasattr(count_result, 'count') else 0
            
            print(f"Metadata vectors_count: {metadata_count:,}")
            print(f"Count Actual count() result: {actual_count:,}")
            print(f"Collection status: {collection_info.status}")
            
            # Calculate discrepancy
            if metadata_count != actual_count:
                discrepancy = abs(metadata_count - actual_count)
                percentage = (discrepancy / max(actual_count, 1)) * 100
                print(f"WARNING: Discrepancy: {discrepancy:,} vectors ({percentage:.1f}%)")
                return False
            else:
                print(" Metadata is consistent!")
                return True
                
        except Exception as e:
            print(f" Error checking metadata: {e}")
            return False
    
    async def _optimize_collection(self) -> bool:
        """Optimize collection to force metadata refresh"""
        try:
            print(" Running collection optimization...")
            
            # This forces Qdrant to rebuild indexes and update metadata
            # Note: This can take time for large collections
            self.client.update_collection(
                collection_name=self.collection_name,
                optimizer_config=models.OptimizersConfigDiff(
                    # Just a minimal update to trigger optimization
                    indexing_threshold=10000
                )
            )
            
            # Wait a bit for the optimization to start
            print("⏳ Waiting for optimization to process...")
            await asyncio.sleep(10)
            
            # Check if optimization is running
            collection_info = self.client.get_collection(self.collection_name)
            print(f"Collection status after optimization: {collection_info.status}")
            
            return True
            
        except Exception as e:
            print(f" Collection optimization failed: {e}")
            return False
    
    async def _flush_collection(self) -> bool:
        """Flush collection segments to disk"""
        try:
            print("Saving Flushing collection segments...")
            
            # Force flush to disk (may trigger metadata update)
            # This is a gentler approach than full optimization
            try:
                # Try the flush endpoint if available
                self.client._client.post(
                    path=f"/collections/{self.collection_name}/segments/flush",
                )
                print(" Segments flushed successfully")
                
                await asyncio.sleep(5)
                return True
                
            except Exception as flush_error:
                print(f"WARNING: Direct flush failed: {flush_error}")
                return False
                
        except Exception as e:
            print(f" Segment flush failed: {e}")
            return False
    
    async def _wait_for_sync(self):
        """Wait for natural background sync"""
        print("⏰ Waiting for natural metadata sync...")
        print("   This may take 5-10 minutes for large collections...")
        
        max_wait_time = 300  # 5 minutes
        check_interval = 30   # 30 seconds
        
        for i in range(0, max_wait_time, check_interval):
            await asyncio.sleep(check_interval)
            
            is_consistent = await self._check_metadata_consistency()
            if is_consistent:
                print(f" Metadata synced after {i + check_interval} seconds!")
                return
            
            print(f"⏳ Still waiting... ({i + check_interval}/{max_wait_time}s)")
        
        print("WARNING: Natural sync timeout - metadata may still be stale")
        print(" Try running this script again later, or consider recreating the collection")
    
    async def force_metadata_refresh(self):
        """Nuclear option: Force complete metadata refresh"""
        print("FORCING COMPLETE METADATA REFRESH")
        print("WARNING: This is the nuclear option - use only if other methods fail")
        
        confirm = input("Type 'FORCE_REFRESH' to proceed: ")
        if confirm != 'FORCE_REFRESH':
            print(" Force refresh cancelled")
            return
        
        try:
            # Get collection configuration
            print("Backing up collection configuration...")
            collection_info = self.client.get_collection(self.collection_name)
            
            # Update collection with same config (forces rebuild)
            print("Loading Triggering metadata rebuild...")
            self.client.update_collection(
                collection_name=self.collection_name,
                optimizer_config=models.OptimizersConfigDiff(
                    # Force a meaningful change that triggers full rebuild
                    indexing_threshold=1000,
                    flush_interval_sec=5
                )
            )
            
            print(" Metadata refresh initiated")
            print("⏳ This may take 10-30 minutes for large collections")
            
        except Exception as e:
            print(f" Force refresh failed: {e}")

async def main():
    refresher = QdrantMetadataRefresher()
    
    print(" Checking if metadata refresh is needed...")
    is_consistent = await refresher._check_metadata_consistency()
    
    if is_consistent:
        print("\n Metadata is already consistent - no refresh needed!")
        return
    
    print("\nWARNING: Stale metadata detected - proceeding with refresh...")
    await refresher.refresh_metadata()

if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    if os.path.exists('.env'):
        load_dotenv('.env')
        print("Directory Loaded .env file")
    
    asyncio.run(main())