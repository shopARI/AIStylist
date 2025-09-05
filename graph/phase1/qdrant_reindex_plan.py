#!/usr/bin/env python3
"""
Qdrant Re-indexing Plan with Proper Product ID Correlation
Complete strategy to fix the missing product_id issue
"""

import json
import os
from datetime import datetime
from typing import Dict, List

def create_qdrant_reindex_plan():
    """Create comprehensive plan to fix Qdrant product_id correlation"""
    
    print("🚀 QDRANT RE-INDEXING PLAN")
    print("="*50)
    print()
    
    # Current state analysis
    current_state = {
        'neo4j_products': 6416804,
        'qdrant_vectors': 6182557,
        'missing_products': 6416804 - 6182557,  # ~234K products missing vectors
        'qdrant_payload_fields': ['title', 'description', 'price'],
        'missing_field': 'product_id'
    }
    
    print("📊 CURRENT STATE:")
    print(f"- Neo4j Products: {current_state['neo4j_products']:,}")
    print(f"- Qdrant Vectors: {current_state['qdrant_vectors']:,}")
    print(f"- Missing Vectors: {current_state['missing_products']:,}")
    print(f"- Current Payload: {current_state['qdrant_payload_fields']}")
    print(f"- Missing Critical Field: {current_state['missing_field']}")
    print()
    
    # Strategy options
    strategies = {
        'option_1': {
            'name': 'Update Existing Vectors (Recommended)',
            'approach': 'Add product_id to existing vectors using title/description matching',
            'pros': ['Preserves existing vectors', 'No re-embedding needed', 'Faster execution'],
            'cons': ['Matching may be imperfect', 'Some vectors may remain unmatched'],
            'time_estimate': '2-4 hours',
            'complexity': 'Medium'
        },
        'option_2': {
            'name': 'Complete Re-indexing',
            'approach': 'Delete all vectors and recreate with proper product_id',
            'pros': ['Perfect correlation', 'Clean slate', 'All products included'],
            'cons': ['Requires re-embedding all 6.4M products', 'Very time consuming', 'Expensive API calls'],
            'time_estimate': '2-3 days',
            'complexity': 'High'
        },
        'option_3': {
            'name': 'Hybrid Approach',
            'approach': 'Update existing + add missing vectors',
            'pros': ['Best of both worlds', 'Handles missing 234K products', 'Reasonable time'],
            'cons': ['More complex logic', 'Some API costs'],
            'time_estimate': '4-8 hours',
            'complexity': 'Medium-High'
        }
    }
    
    print("🎯 STRATEGY OPTIONS:")
    for key, strategy in strategies.items():
        print(f"\n**{strategy['name']}** ({strategy['complexity']} complexity)")
        print(f"Approach: {strategy['approach']}")
        print(f"Time: {strategy['time_estimate']}")
        print("Pros:", ', '.join(strategy['pros']))
        print("Cons:", ', '.join(strategy['cons']))
    
    print(f"\n✅ **RECOMMENDED: Option 1 - Update Existing Vectors**")
    print()
    
    # Implementation plan for Option 1
    implementation_steps = [
        {
            'step': 1,
            'title': 'Backup Current Qdrant Collection',
            'description': 'Create snapshot of current vectors before modifications',
            'commands': [
                'Create collection backup/snapshot',
                'Export sample of current vectors for validation'
            ],
            'time': '30 minutes'
        },
        {
            'step': 2,
            'title': 'Build Title-to-ProductID Mapping',
            'description': 'Create lookup table from Neo4j products',
            'commands': [
                'Query all Neo4j products: SELECT id, title, description',
                'Create title hash -> product_id mapping',
                'Handle duplicate titles with disambiguation'
            ],
            'time': '1 hour'
        },
        {
            'step': 3,
            'title': 'Match Existing Qdrant Vectors',
            'description': 'Correlate existing vectors with Neo4j products',
            'commands': [
                'Scroll through all Qdrant vectors',
                'Match title/description to Neo4j products',
                'Track match confidence and duplicates'
            ],
            'time': '2 hours'
        },
        {
            'step': 4,
            'title': 'Update Qdrant Payloads',
            'description': 'Add product_id field to matched vectors',
            'commands': [
                'Batch update Qdrant payloads with product_id',
                'Handle unmatched vectors (flag for manual review)',
                'Validate updated payload structure'
            ],
            'time': '1 hour'
        },
        {
            'step': 5,
            'title': 'Validation and Testing',
            'description': 'Verify correlation works correctly',
            'commands': [
                'Sample Neo4j product -> Qdrant vector lookup',
                'Test vector search -> product retrieval',
                'Compare before/after correlation rates'
            ],
            'time': '30 minutes'
        }
    ]
    
    print("🛠️ IMPLEMENTATION PLAN (Option 1):")
    total_time = 0
    for step in implementation_steps:
        print(f"\n**Step {step['step']}: {step['title']}** ({step['time']})")
        print(f"Goal: {step['description']}")
        for cmd in step['commands']:
            print(f"  - {cmd}")
        
        # Extract time estimate
        if 'hour' in step['time']:
            hours = float(step['time'].split()[0]) if step['time'].split()[0].replace('.', '').isdigit() else 0.5
            total_time += hours
        elif 'minute' in step['time']:
            minutes = float(step['time'].split()[0])
            total_time += minutes / 60
    
    print(f"\n⏱️ **TOTAL ESTIMATED TIME: {total_time:.1f} hours**")
    print()
    
    # Technical requirements
    print("🔧 TECHNICAL REQUIREMENTS:")
    requirements = [
        'Qdrant client with write permissions',
        'Neo4j read access for product data',
        'Python environment with qdrant-client, neo4j libraries',
        'Sufficient memory for mapping tables (~50MB)',
        'Network bandwidth for Qdrant API calls'
    ]
    for req in requirements:
        print(f"  ✅ {req}")
    print()
    
    # Risk mitigation
    print("⚠️ RISK MITIGATION:")
    risks = [
        'Backup collection before any changes',
        'Process in small batches (1000 vectors at a time)',
        'Track all operations in logs for rollback',
        'Validate matching accuracy before mass updates',
        'Keep original vectors until validation complete'
    ]
    for risk in risks:
        print(f"  🛡️ {risk}")
    print()
    
    # Success criteria
    print("🎯 SUCCESS CRITERIA:")
    success_metrics = [
        '>95% of Qdrant vectors have valid product_id',
        'Neo4j product -> Qdrant vector lookup success rate >90%',
        'Vector search results properly link to product pages',
        'No degradation in search performance',
        'All Phase 2 extracted attributes correlate with vectors'
    ]
    for metric in success_metrics:
        print(f"  📈 {metric}")
    
    return {
        'recommended_strategy': 'option_1',
        'total_time_hours': total_time,
        'implementation_steps': implementation_steps,
        'current_state': current_state
    }

def generate_implementation_script():
    """Generate the actual implementation script template"""
    
    script_content = '''#!/usr/bin/env python3
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
        self.neo4j_url = "bolt://0.0.0.0:17687"
        self.neo4j_user = "neo4j"
        self.neo4j_password = "6D%q@jbYmstkK2i3oW5z6B6outew9m93"
        
        self.qdrant_url = "https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io"
        self.qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg"
        self.collection_name = "fashion_products"
        
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
        print("\\n📊 FINAL STATISTICS:")
        print("="*40)
        for key, value in self.stats.items():
            print(f"{key.replace('_', ' ').title()}: {value:,}")
        
        match_rate = (self.stats['successful_matches'] / 
                     max(self.stats['qdrant_vectors_processed'], 1)) * 100
        print(f"\\nMatch Rate: {match_rate:.1f}%")
    
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
            
            print(f"\\n🎉 Fix completed in {duration:.1f} hours")
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
'''
    
    script_file = "fix_qdrant_product_ids.py"
    with open(script_file, 'w') as f:
        f.write(script_content)
    
    print(f"📝 Implementation script generated: {script_file}")
    return script_file

def main():
    """Generate complete Qdrant re-indexing plan"""
    
    plan = create_qdrant_reindex_plan()
    script_file = generate_implementation_script()
    
    print()
    print("📋 NEXT STEPS:")
    print("1. Review the implementation plan above")
    print(f"2. Execute the script: python {script_file}")
    print("3. Monitor progress and validate results")
    print("4. Test Neo4j -> Qdrant correlation")
    print("5. Proceed with Phase 2 once correlation is fixed")
    print()
    print("🎯 After this fix, you'll have proper Neo4j <-> Qdrant correlation!")

if __name__ == "__main__":
    main()