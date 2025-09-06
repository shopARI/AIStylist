#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Qdrant Product ID Correlation Fix
Updates existing Qdrant vectors with proper product_id fields
"""

import json
import hashlib
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http import models

class QdrantProductIdFixer:
    """Fixes missing product_id correlation in Qdrant vectors"""
    
    def __init__(self):
        # Connection details
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        self.qdrant_url = self.db_config.qdrant_url
        self.qdrant_api_key = self.db_config.qdrant_api_key
        self.collection_name = self.db_config.collection_name
        
        # Statistics
        self.stats = {
            'neo4j_products_loaded': 0,
            'qdrant_vectors_processed': 0,
            'successful_matches': 0,
            'failed_matches': 0,
            'duplicate_titles': 0,
            'updates_applied': 0
        }
        
    def connect_databases(self):
        """Connect to both databases"""
        print("🔌 Connecting to databases...")
        
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_url, 
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        self.qdrant_client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key
        )
        
        print("✅ Connected to both databases")
    
    def build_product_mapping(self) -> Dict:
        """Build title -> product_id mapping from Neo4j"""
        print("🗺️ Building product mapping from Neo4j...")
        
        title_to_product = {}
        duplicate_titles = defaultdict(list)
        
        with self.neo4j_driver.session() as session:
            # Query all products
            result = session.run("""
                MATCH (p:Product)
                RETURN p.id as id, p.title as title, p.description as description
            """)
            
            for record in result:
                product_id = record['id']
                title = (record['title'] or '').strip().lower()
                description = (record['description'] or '').strip().lower()
                
                if title:
                    # Create title hash for exact matching
                    title_hash = hashlib.md5(title.encode()).hexdigest()
                    
                    if title_hash in title_to_product:
                        # Duplicate title - store both
                        existing_id = title_to_product[title_hash]
                        duplicate_titles[title_hash].extend([existing_id, product_id])
                    else:
                        title_to_product[title_hash] = product_id
                
                self.stats['neo4j_products_loaded'] += 1
                
                if self.stats['neo4j_products_loaded'] % 100000 == 0:
                    print(f"  Loaded {self.stats['neo4j_products_loaded']:,} products...")
        
        self.stats['duplicate_titles'] = len(duplicate_titles)
        
        print(f"✅ Built mapping for {len(title_to_product):,} unique titles")
        print(f"⚠️ Found {len(duplicate_titles):,} duplicate titles")
        
        return title_to_product, duplicate_titles
    
    def match_and_update_vectors(self, title_mapping: Dict, batch_size: int = 1000):
        """Match existing Qdrant vectors and update with product_id"""
        print("🔄 Matching and updating Qdrant vectors...")
        
        # Process vectors in batches
        offset = None
        batch_count = 0
        
        while True:
            # Scroll through vectors
            scroll_result = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            
            points, next_offset = scroll_result
            
            if not points:
                break
            
            # Process this batch
            updates = []
            
            for point in points:
                self.stats['qdrant_vectors_processed'] += 1
                
                payload = point.payload or {}
                title = payload.get('title', '').strip().lower()
                
                if title:
                    title_hash = hashlib.md5(title.encode()).hexdigest()
                    
                    if title_hash in title_mapping:
                        # Found match!
                        product_id = title_mapping[title_hash]
                        
                        # Prepare update
                        updated_payload = payload.copy()
                        updated_payload['product_id'] = product_id
                        
                        updates.append({
                            'id': point.id,
                            'payload': updated_payload
                        })
                        
                        self.stats['successful_matches'] += 1
                    else:
                        self.stats['failed_matches'] += 1
                else:
                    self.stats['failed_matches'] += 1
            
            # Apply batch updates
            if updates:
                self.apply_batch_updates(updates)
                self.stats['updates_applied'] += len(updates)
            
            batch_count += 1
            
            print(f"  Processed batch {batch_count}: {len(points)} vectors, {len(updates)} updates")
            
            # Check if we have more data
            offset = next_offset
            if offset is None:
                break
        
        print(f"✅ Matching complete: {self.stats['successful_matches']:,} matches found")
    
    def apply_batch_updates(self, updates: List[Dict]):
        """Apply batch updates to Qdrant"""
        try:
            # Prepare update points
            update_points = []
            for update in updates:
                update_points.append(
                    models.PointStruct(
                        id=update['id'],
                        payload=update['payload'],
                        vector=None  # Don't update vectors
                    )
                )
            
            # Update payload only
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=update_points
            )
            
        except Exception as e:
            print(f"❌ Error updating batch: {e}")
    
    def validate_updates(self, sample_size: int = 100):
        """Validate that updates worked correctly"""
        print("🔍 Validating updates...")
        
        # Sample some vectors and check for product_id
        scroll_result = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            limit=sample_size,
            with_payload=True
        )
        
        points = scroll_result[0]
        has_product_id = 0
        
        for point in points:
            if point.payload and 'product_id' in point.payload:
                has_product_id += 1
        
        success_rate = (has_product_id / len(points)) * 100
        print(f"✅ Validation: {has_product_id}/{len(points)} vectors have product_id ({success_rate:.1f}%)")
        
        return success_rate
    
    def print_final_stats(self):
        """Print final statistics"""
        print("\n📊 FINAL STATISTICS:")
        print("="*40)
        for key, value in self.stats.items():
            print(f"{key.replace('_', ' ').title()}: {value:,}")
        
        match_rate = (self.stats['successful_matches'] / 
                     max(self.stats['qdrant_vectors_processed'], 1)) * 100
        print(f"\nMatch Rate: {match_rate:.1f}%")
    
    def run_fix(self):
        """Run the complete fixing process"""
        start_time = datetime.now()
        
        print("🚀 Starting Qdrant Product ID Correlation Fix...")
        print(f"Started at: {start_time}")
        print()
        
        try:
            # Step 1: Connect
            self.connect_databases()
            
            # Step 2: Build mapping
            title_mapping, duplicates = self.build_product_mapping()
            
            # Step 3: Match and update
            self.match_and_update_vectors(title_mapping)
            
            # Step 4: Validate
            success_rate = self.validate_updates()
            
            # Step 5: Report
            self.print_final_stats()
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() / 3600
            
            print(f"\n🎉 Fix completed in {duration:.1f} hours")
            print(f"✅ Success rate: {success_rate:.1f}%")
            
            if success_rate > 90:
                print("🚀 CORRELATION FIX SUCCESSFUL!")
            else:
                print("⚠️ Low success rate - may need manual review")
        
        except Exception as e:
            print(f"❌ Error during fix: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            if hasattr(self, 'neo4j_driver'):
                self.neo4j_driver.close()

if __name__ == "__main__":
    fixer = QdrantProductIdFixer()
    fixer.run_fix()
