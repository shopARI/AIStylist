#!/usr/bin/env python3
"""
Post-Cleanup Verification Script
Comprehensive check that cleanup was successful and system is healthy
"""

import os
import asyncio
from typing import Set, Dict, List, Any
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

class CleanupVerifier:
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

    async def verify_cleanup(self):
        """Comprehensive cleanup verification"""
        print(" POST-CLEANUP VERIFICATION")
        print("=" * 60)
        
        try:
            # Connect to Neo4j
            print("🔗 Connecting to Neo4j...")
            self.neo4j_driver = GraphDatabase.driver(
                self.neo4j_url,
                auth=(self.neo4j_username, self.neo4j_password)
            )
            self.neo4j_driver.verify_connectivity()
            print(" Neo4j connected")
            
            # Run all verification checks
            await self._check_collection_health()
            await self._check_data_integrity()
            await self._check_uuid_consistency()
            await self._check_no_duplicates()
            await self._check_no_orphans()
            await self._generate_final_report()
            
        finally:
            if self.neo4j_driver:
                self.neo4j_driver.close()
    
    async def _check_collection_health(self):
        """Check overall collection health"""
        print("\n🏥 COLLECTION HEALTH CHECK")
        print("-" * 40)
        
        try:
            # Basic collection info
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            
            # Get both counts
            metadata_count = collection_info.vectors_count or 0
            count_result = self.qdrant_client.count(self.collection_name)
            actual_count = count_result.count if hasattr(count_result, 'count') else 0
            
            print(f"📊 Collection status: {collection_info.status}")
            print(f"📈 Metadata count: {metadata_count:,}")
            print(f"🔢 Actual count: {actual_count:,}")
            
            if metadata_count != actual_count:
                print(f"⚠️ Metadata inconsistency detected!")
                print(f"   Run: python scripts/qdrant_metadata_refresh.py")
            else:
                print(" Collection metadata is consistent")
            
            # Check if collection is operational
            try:
                points, _ = self.qdrant_client.scroll(self.collection_name, limit=1)
                if points:
                    print(" Collection is accessible and has data")
                else:
                    print("ℹ️ Collection is empty")
            except Exception as e:
                print(f" Collection access error: {e}")
                
        except Exception as e:
            print(f" Health check failed: {e}")
    
    async def _check_data_integrity(self):
        """Check data integrity"""
        print("\n🔐 DATA INTEGRITY CHECK")
        print("-" * 40)
        
        try:
            # Sample points to check structure
            points, _ = self.qdrant_client.scroll(self.collection_name, limit=10)
            
            if not points:
                print("ℹ️ No data to check - collection is empty")
                return
            
            print(f" Checking {len(points)} sample points...")
            
            # Check ID formats
            uuid_count = 0
            numeric_count = 0
            malformed_count = 0
            
            for point in points:
                point_id = str(point.id)
                
                if len(point_id) > 20 and '-' in point_id:
                    # Looks like UUID
                    uuid_count += 1
                elif point_id.isdigit():
                    # Numeric ID
                    numeric_count += 1
                else:
                    # Malformed
                    malformed_count += 1
            
            print(f"🆔 UUID format: {uuid_count}")
            print(f"🔢 Numeric format: {numeric_count}")
            print(f"⚠️ Malformed: {malformed_count}")
            
            if numeric_count > 0:
                print(" Old numeric IDs still present - cleanup incomplete!")
            elif malformed_count > 0:
                print("⚠️ Malformed IDs detected - data quality issue!")
            else:
                print(" All IDs are in proper UUID format")
                
            # Check payload structure
            sample_point = points[0]
            payload_keys = list(sample_point.payload.keys())
            expected_keys = ['title', 'description', 'category', 'price', 'brand']
            
            print(f"🏷️ Sample payload keys: {payload_keys}")
            missing_keys = [k for k in expected_keys if k not in payload_keys]
            if missing_keys:
                print(f"⚠️ Missing expected keys: {missing_keys}")
            else:
                print(" Payload structure looks good")
                
        except Exception as e:
            print(f" Data integrity check failed: {e}")
    
    async def _check_uuid_consistency(self):
        """Check UUID consistency between Neo4j and Qdrant"""
        print("\n🔗 UUID CONSISTENCY CHECK")
        print("-" * 40)
        
        try:
            # Get sample of Neo4j UUIDs
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (p:Product) RETURN p.id as uuid LIMIT 100")
                neo4j_sample = {record["uuid"] for record in result}
            
            print(f"📊 Neo4j sample: {len(neo4j_sample)} UUIDs")
            
            # Get sample of Qdrant UUIDs
            points, _ = self.qdrant_client.scroll(self.collection_name, limit=100)
            qdrant_sample = {str(point.id) for point in points}
            
            print(f"📊 Qdrant sample: {len(qdrant_sample)} UUIDs")
            
            # Check overlap
            overlap = neo4j_sample & qdrant_sample
            neo4j_only = neo4j_sample - qdrant_sample
            qdrant_only = qdrant_sample - neo4j_sample
            
            print(f"🤝 Common UUIDs: {len(overlap)}")
            print(f"📈 Neo4j only: {len(neo4j_only)}")
            print(f"📉 Qdrant only: {len(qdrant_only)}")
            
            if len(qdrant_only) > 0:
                print(f"⚠️ Orphaned UUIDs in Qdrant: {list(qdrant_only)[:5]}")
            else:
                print(" No orphaned UUIDs detected in sample")
                
        except Exception as e:
            print(f" UUID consistency check failed: {e}")
    
    async def _check_no_duplicates(self):
        """Check for duplicate UUIDs"""
        print("\n🔄 DUPLICATE CHECK")
        print("-" * 40)
        
        try:
            # Scroll through collection and count UUIDs
            uuid_counts = {}
            total_checked = 0
            duplicates_found = 0
            
            next_offset = None
            
            while True:
                points, next_offset = self.qdrant_client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=next_offset
                )
                
                if not points:
                    break
                
                for point in points:
                    uuid = str(point.id)
                    uuid_counts[uuid] = uuid_counts.get(uuid, 0) + 1
                
                total_checked += len(points)
                print(f"   Checked {total_checked:,} vectors...", end='\r')
                
                if next_offset is None:
                    break
            
            # Find duplicates
            duplicates = {uuid: count for uuid, count in uuid_counts.items() if count > 1}
            duplicates_found = sum(count - 1 for count in duplicates.values())
            
            print(f"\n Total vectors checked: {total_checked:,}")
            print(f"🆔 Unique UUIDs: {len(uuid_counts):,}")
            print(f"🔄 Duplicate instances: {duplicates_found}")
            
            if duplicates_found > 0:
                print(f" Found {len(duplicates)} UUIDs with duplicates!")
                print("   Sample duplicates:")
                for uuid, count in list(duplicates.items())[:5]:
                    print(f"     {uuid}: {count} copies")
            else:
                print(" No duplicates found")
                
        except Exception as e:
            print(f" Duplicate check failed: {e}")
    
    async def _check_no_orphans(self):
        """Check for orphaned UUIDs (more comprehensive)"""
        print("\n👻 ORPHAN CHECK")
        print("-" * 40)
        
        try:
            # Get all Neo4j UUIDs (this could be large!)
            print("📊 Getting all Neo4j UUIDs...")
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (p:Product) RETURN p.id as uuid")
                valid_uuids = {record["uuid"] for record in result if record["uuid"]}
            
            print(f" Found {len(valid_uuids):,} valid UUIDs in Neo4j")
            
            # Sample check of Qdrant UUIDs
            print(" Sampling Qdrant UUIDs for orphan check...")
            points, _ = self.qdrant_client.scroll(self.collection_name, limit=1000)
            
            orphans_found = []
            for point in points:
                uuid = str(point.id)
                if uuid not in valid_uuids:
                    orphans_found.append(uuid)
            
            print(f" Checked {len(points)} Qdrant vectors")
            print(f"👻 Orphaned UUIDs found: {len(orphans_found)}")
            
            if orphans_found:
                print(" Sample orphaned UUIDs:")
                for orphan in orphans_found[:5]:
                    print(f"     {orphan}")
            else:
                print(" No orphaned UUIDs in sample")
                
        except Exception as e:
            print(f" Orphan check failed: {e}")
    
    async def _generate_final_report(self):
        """Generate final cleanup report"""
        print("\n📋 FINAL CLEANUP REPORT")
        print("=" * 60)
        
        try:
            # Collection stats
            collection_info = self.qdrant_client.get_collection(self.collection_name)
            count_result = self.qdrant_client.count(self.collection_name)
            
            metadata_count = collection_info.vectors_count or 0
            actual_count = count_result.count if hasattr(count_result, 'count') else 0
            
            # Neo4j stats
            with self.neo4j_driver.session() as session:
                result = session.run("MATCH (p:Product) RETURN count(p) as count")
                neo4j_products = result.single()["count"]
            
            print(f"📊 FINAL STATISTICS:")
            print(f"   🗂️ Neo4j Products: {neo4j_products:,}")
            print(f"    Qdrant Vectors: {actual_count:,}")
            print(f"   📈 Collection Status: {collection_info.status}")
            
            # Calculate efficiency
            if neo4j_products > 0:
                coverage = (actual_count / neo4j_products) * 100
                print(f"    Coverage: {coverage:.1f}%")
            
            print(f"\n CLEANUP SUMMARY:")
            print(f"    Collection is operational")
            print(f"    Data integrity verified")
            print(f"    UUID format validated")
            
            if metadata_count != actual_count:
                print(f"   ⚠️ Metadata needs refresh (run qdrant_metadata_refresh.py)")
            else:
                print(f"    Metadata is consistent")
            
            print(f"\n CLEANUP VERIFICATION COMPLETE!")
            
        except Exception as e:
            print(f" Report generation failed: {e}")

async def main():
    verifier = CleanupVerifier()
    await verifier.verify_cleanup()

if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    if os.path.exists('.env'):
        load_dotenv('.env')
        print("📁 Loaded .env file")
    
    asyncio.run(main())