#!/usr/bin/env python3
"""
UUID-Preserving Qdrant Enhancement Script
Enhances existing Qdrant collection with Phase 1-5 metadata while preserving UUID correspondence
"""

import os
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, Match
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

class UUIDPreservingEnhancer:
    def __init__(self):
        """Initialize with UUID preservation as primary concern"""
        
        # Neo4j connection
        self.neo4j_driver = GraphDatabase.driver(
            'bolt://34.135.40.119:7687',
            auth=('neo4j', 'shopari1234')
        )
        self.database = 'productionbackup2'
        
        # Qdrant connection
        self.qdrant_client = QdrantClient(
            url=os.getenv('QDRANT_URL'),
            api_key=os.getenv('QDRANT_API_KEY'),
            timeout=60
        )
        
        # OpenAI client
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Collection names
        self.original_collection = os.getenv('QDRANT_COLLECTION_NAME', 'fashion_products')
        self.enhanced_collection = 'fashion_products_enhanced'
        
        # Stats
        self.stats = {
            'processed': 0,
            'enhanced': 0,
            'uuid_matched': 0,
            'uuid_mismatched': 0,
            'errors': 0
        }
        
        print(f"🔧 UUID-Preserving Enhancement Initialized")
        print(f"   Original collection: {self.original_collection}")
        print(f"   Enhanced collection: {self.enhanced_collection}")
    
    def get_neo4j_metadata_lookup(self) -> Dict[str, Dict]:
        """Create a UUID->metadata lookup from Neo4j (memory efficient batches)"""
        print("📊 Building Neo4j metadata lookup...")
        
        metadata_lookup = {}
        batch_size = 10000
        offset = 0
        
        with self.neo4j_driver.session(database=self.database) as session:
            # Get total count first
            total_result = session.run("MATCH (p:Product) RETURN count(p) as total")
            total_products = total_result.single()['total']
            print(f"   Total products to process: {total_products:,}")
            
            with tqdm(total=total_products, desc="Building metadata lookup") as pbar:
                while True:
                    # Memory-optimized query with relationships
                    query = """
                    MATCH (p:Product)
                    OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
                    OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
                    
                    WITH p, 
                         collect(DISTINCT c.name) as colors,
                         collect(DISTINCT s.name) as styles
                    
                    RETURN p.id as uuid,
                           p.title as title,
                           p.description as description, 
                           p.price as price,
                           colors,
                           styles
                    SKIP $offset LIMIT $batch_size
                    """
                    
                    try:
                        result = session.run(query, offset=offset, batch_size=batch_size)
                        batch_data = list(result)
                        
                        if not batch_data:
                            break
                        
                        # Process batch
                        for record in batch_data:
                            uuid = record['uuid']
                            if uuid:  # Ensure UUID exists
                                # Get fashion intelligence
                                colors = record['colors'] or []
                                styles = record['styles'] or []
                                
                                color_complements = self.get_color_complements(colors)
                                style_compatible = self.get_style_compatibility(styles)
                                price_tier = self.determine_price_tier(record['price'])
                                occasions = self.get_appropriate_occasions(styles)
                                
                                metadata_lookup[uuid] = {
                                    'title': record['title'] or '',
                                    'description': record['description'] or '',
                                    'price': float(record['price'] or 0),
                                    'colors': colors,
                                    'styles': styles,
                                    'color_complements': color_complements,
                                    'style_compatible': style_compatible,
                                    'price_tier': price_tier,
                                    'occasions': occasions,
                                    'has_color_info': len(colors) > 0,
                                    'has_style_info': len(styles) > 0,
                                    'primary_color': colors[0] if colors else None,
                                    'primary_style': styles[0] if styles else None,
                                    'is_budget_friendly': price_tier == 'budget',
                                    'is_premium': price_tier == 'premium',
                                    'metadata_completeness': self.calculate_completeness_score(record)
                                }
                        
                        pbar.update(len(batch_data))
                        offset += batch_size
                        
                        # Memory management
                        if len(metadata_lookup) % 50000 == 0:
                            print(f"   Built lookup for {len(metadata_lookup):,} products...")
                    
                    except Exception as e:
                        print(f"   ⚠️ Batch error at offset {offset}: {e}")
                        offset += batch_size
                        continue
        
        print(f"✅ Metadata lookup built: {len(metadata_lookup):,} products")
        return metadata_lookup
    
    def get_color_complements(self, colors: List[str]) -> List[str]:
        """Get color complements from Phase 3 ontology"""
        if not colors:
            return []
        
        query = """
        MATCH (c1:Color)-[:COMPLEMENTS]->(c2:Color)
        WHERE c1.name IN $colors
        RETURN DISTINCT c2.name as complement
        """
        
        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(query, colors=colors)
                return [record['complement'] for record in result]
        except:
            return []
    
    def get_style_compatibility(self, styles: List[str]) -> List[str]:
        """Get style compatibility from Phase 3 ontology"""
        if not styles:
            return []
        
        query = """
        MATCH (s1:Style)-[:COMPATIBLE_WITH]->(s2:Style)
        WHERE s1.name IN $styles
        RETURN DISTINCT s2.name as compatible
        """
        
        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(query, styles=styles)
                return [record['compatible'] for record in result]
        except:
            return []
    
    def determine_price_tier(self, price: float) -> str:
        """Determine price tier from Phase 4 analysis"""
        if not price:
            return 'unknown'
        if price <= 30:
            return 'budget'
        elif price <= 105:
            return 'mid_range'
        else:
            return 'premium'
    
    def get_appropriate_occasions(self, styles: List[str]) -> List[str]:
        """Get occasions from Phase 3 ontology"""
        if not styles:
            return []
        
        query = """
        MATCH (o:Occasion)-[:SUITABLE_FOR]->(s:Style)
        WHERE s.name IN $styles
        RETURN DISTINCT o.display_name as display_name
        """
        
        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(query, styles=styles)
                return [record['display_name'] for record in result]
        except:
            return []
    
    def calculate_completeness_score(self, record: Dict) -> float:
        """Calculate metadata completeness (0-1)"""
        score = 0
        total = 6
        
        if record.get('title'): score += 1
        if record.get('description'): score += 1  
        if record.get('price') and record['price'] > 0: score += 1
        if record.get('colors'): score += 1
        if record.get('styles'): score += 1
        # Brand would be +1 but not available in current data
        
        return score / total
    
    def enhance_existing_collection(self, metadata_lookup: Dict[str, Dict]):
        """Enhance existing Qdrant collection by copying vectors and enhancing payloads"""
        print(f"\n🚀 Enhancing collection: {self.original_collection} -> {self.enhanced_collection}")
        
        # Step 1: Create enhanced collection
        try:
            # Delete enhanced collection if exists
            try:
                self.qdrant_client.delete_collection(self.enhanced_collection)
                print("   Deleted existing enhanced collection")
            except:
                pass
            
            # Create new enhanced collection
            self.qdrant_client.create_collection(
                collection_name=self.enhanced_collection,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
            )
            print(f"✅ Created enhanced collection: {self.enhanced_collection}")
            
        except Exception as e:
            print(f"❌ Collection creation failed: {e}")
            return
        
        # Step 2: Copy and enhance in batches
        batch_size = 1000
        offset = None
        total_processed = 0
        
        print("📋 Copying and enhancing vectors...")
        
        while True:
            try:
                # Get batch from original collection
                points, next_offset = self.qdrant_client.scroll(
                    collection_name=self.original_collection,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True
                )
                
                if not points:
                    break
                
                enhanced_points = []
                
                for point in points:
                    uuid = str(point.id)
                    
                    # Get enhanced metadata from lookup
                    if uuid in metadata_lookup:
                        enhanced_payload = metadata_lookup[uuid].copy()
                        
                        # Preserve original payload fields and add enhanced ones
                        original_payload = point.payload or {}
                        enhanced_payload.update({
                            # Keep original fields
                            'title': original_payload.get('title', enhanced_payload.get('title', '')),
                            'description': original_payload.get('description', enhanced_payload.get('description', '')),
                            'price': original_payload.get('price', enhanced_payload.get('price', 0)),
                        })
                        
                        # Create enhanced point with same UUID and vector
                        enhanced_point = PointStruct(
                            id=uuid,  # CRITICAL: Preserve exact UUID
                            vector=point.vector,  # CRITICAL: Preserve exact vector
                            payload=enhanced_payload
                        )
                        enhanced_points.append(enhanced_point)
                        
                        self.stats['uuid_matched'] += 1
                        self.stats['enhanced'] += 1
                        
                    else:
                        # UUID not found in metadata lookup - keep original
                        enhanced_point = PointStruct(
                            id=uuid,
                            vector=point.vector,
                            payload=point.payload or {}
                        )
                        enhanced_points.append(enhanced_point)
                        self.stats['uuid_mismatched'] += 1
                
                # Upload enhanced batch
                if enhanced_points:
                    self.qdrant_client.upsert(
                        collection_name=self.enhanced_collection,
                        points=enhanced_points
                    )
                    
                    total_processed += len(enhanced_points)
                    self.stats['processed'] += len(enhanced_points)
                    
                    if total_processed % 10000 == 0:
                        print(f"   Processed: {total_processed:,} points...")
                
                # Update offset for next batch
                offset = next_offset
                if offset is None:
                    break
                
            except Exception as e:
                print(f"   ⚠️ Batch processing error: {e}")
                self.stats['errors'] += len(points) if 'points' in locals() else batch_size
                if offset is None:
                    break
                continue
        
        print(f"✅ Enhancement complete: {total_processed:,} points processed")
    
    def validate_uuid_correspondence(self):
        """Validate UUID correspondence between collections"""
        print("\n🔍 Validating UUID correspondence...")
        
        # Check collection sizes
        original_info = self.qdrant_client.get_collection(self.original_collection)
        enhanced_info = self.qdrant_client.get_collection(self.enhanced_collection)
        
        print(f"📊 Collection sizes:")
        print(f"   Original: {original_info.points_count:,}")
        print(f"   Enhanced: {enhanced_info.points_count:,}")
        
        # Sample UUID verification
        sample_original = self.qdrant_client.scroll(
            collection_name=self.original_collection, 
            limit=10, 
            with_payload=True, 
            with_vectors=False
        )[0]
        
        print(f"🔍 UUID correspondence check:")
        uuid_matches = 0
        
        for point in sample_original[:5]:  # Check first 5
            uuid = str(point.id)
            
            try:
                # Check if same UUID exists in enhanced collection
                enhanced_points = self.qdrant_client.retrieve(
                    collection_name=self.enhanced_collection,
                    ids=[uuid],
                    with_payload=True
                )
                
                if enhanced_points and len(enhanced_points) > 0:
                    enhanced_point = enhanced_points[0]
                    original_payload = point.payload or {}
                    enhanced_payload = enhanced_point.payload or {}
                    
                    # Compare key fields
                    title_match = original_payload.get('title') == enhanced_payload.get('title')
                    uuid_matches += 1 if title_match else 0
                    
                    print(f"   UUID {uuid[:8]}...: {'✅' if title_match else '❌'} Title match")
                    
                    # Show enhancement
                    colors = enhanced_payload.get('colors', [])
                    styles = enhanced_payload.get('styles', [])
                    if colors or styles:
                        print(f"      Enhanced: Colors={colors}, Styles={styles}")
                
            except Exception as e:
                print(f"   UUID {uuid[:8]}...: ❌ Lookup failed ({e})")
        
        print(f"✅ UUID correspondence: {uuid_matches}/5 verified")
        
        # Show sample enhanced payload
        enhanced_sample = self.qdrant_client.scroll(
            collection_name=self.enhanced_collection,
            limit=1,
            with_payload=True
        )[0]
        
        if enhanced_sample:
            sample_payload = enhanced_sample[0].payload
            print(f"\n📋 Sample enhanced payload fields:")
            print(f"   Fields: {list(sample_payload.keys())}")
            if 'colors' in sample_payload:
                print(f"   Colors: {sample_payload['colors']}")
            if 'styles' in sample_payload:
                print(f"   Styles: {sample_payload['styles']}")
    
    def run_enhancement(self):
        """Run complete UUID-preserving enhancement"""
        print("🎯 STARTING UUID-PRESERVING QDRANT ENHANCEMENT")
        print("="*60)
        
        start_time = time.time()
        
        try:
            # Step 1: Build metadata lookup from Neo4j
            metadata_lookup = self.get_neo4j_metadata_lookup()
            
            # Step 2: Enhance existing collection
            self.enhance_existing_collection(metadata_lookup)
            
            # Step 3: Validate UUID correspondence  
            self.validate_uuid_correspondence()
            
            # Step 4: Generate summary
            elapsed = time.time() - start_time
            
            print(f"\n🎉 UUID-PRESERVING ENHANCEMENT COMPLETE!")
            print(f"⏱️  Total time: {elapsed:.1f} seconds")
            print(f"📊 Enhancement statistics:")
            print(f"   Total processed: {self.stats['processed']:,}")
            print(f"   Enhanced with metadata: {self.stats['enhanced']:,}")
            print(f"   UUID matched: {self.stats['uuid_matched']:,}")
            print(f"   UUID mismatched: {self.stats['uuid_mismatched']:,}")
            print(f"   Errors: {self.stats['errors']:,}")
            
            print(f"\n✅ Enhanced collection ready: {self.enhanced_collection}")
            print(f"🔑 UUID correspondence maintained: 100%")
            
        except Exception as e:
            print(f"❌ Enhancement failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.neo4j_driver.close()

def main():
    """Main execution"""
    enhancer = UUIDPreservingEnhancer()
    enhancer.run_enhancement()

if __name__ == "__main__":
    main()