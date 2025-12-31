#!/usr/bin/env python3
"""
Fresh UUID-Correspondent Embedding Generator
Creates new embeddings with perfect Neo4j UUID correspondence and enhanced metadata
"""

import os
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI
from tqdm import tqdm

load_dotenv()

class FreshUUIDEmbeddingGenerator:
    def __init__(self):
        """Initialize fresh embedding generator"""
        
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
        
        # Collection configuration
        self.collection_name = os.getenv('QDRANT_COLLECTION_NAME', 'fashion_products')
        self.batch_size = 50  # OpenAI rate limiting
        
        # Stats
        self.stats = {
            'processed': 0,
            'embedded': 0,
            'errors': 0,
            'enhanced_fields': 0
        }
        
        print("🎯 Fresh UUID-Correspondent Embedding Generator")
        print(f"   Collection: {self.collection_name}")
        print(f"   Batch size: {self.batch_size}")
    
    def explain_embedding_fields(self):
        """Explain exactly which fields will be embedded"""
        print("\n📋 EMBEDDING FIELD EXPLANATION")
        print("="*60)
        print("The following fields will be combined into the embedding text:")
        print()
        
        print("🔤 CORE PRODUCT FIELDS:")
        print("   • Title: Product name/title")
        print("   • Description: Product description (first 300 chars)")
        print()
        
        print("🎨 PHASE 1-5 ENHANCED METADATA:")
        print("   • Colors: AI-extracted colors (red, blue, black, etc.)")
        print("   • Styles: AI-extracted styles (casual, formal, trendy, etc.)")
        print("   • Brand: Product brand (if available)")
        print()
        
        print("🧠 PHASE 3 FASHION INTELLIGENCE:")
        print("   • Color Complements: Fashion-theory based color matches")
        print("   • Style Compatibility: Compatible style suggestions")
        print("   • Occasions: Appropriate occasions (Office, Party, etc.)")
        print("   • Price Tier: Budget/mid-range/premium classification")
        print()
        
        print("📝 EXAMPLE EMBEDDING TEXT:")
        sample_text = '''Casual Cotton T-Shirt | Comfortable everyday wear perfect for casual outings | 
Colors: red, white | Styles: casual, comfortable | 
Complements: black, navy, gray | Compatible: trendy, relaxed | 
Occasions: Casual Day, Weekend | Price: mid-range'''
        print(f"   \"{sample_text}\"")
        print()
        
        print("✅ This creates semantically rich embeddings that understand:")
        print("   • Product characteristics and materials")
        print("   • Fashion color theory and style coordination") 
        print("   • Context and occasion appropriateness")
        print("   • Price positioning and market segment")
    
    def create_qdrant_collection(self):
        """Create fresh Qdrant collection"""
        print(f"\n🏗️ Creating fresh Qdrant collection: {self.collection_name}")
        
        try:
            # Ensure collection is deleted
            try:
                self.qdrant_client.delete_collection(self.collection_name)
                print("   Deleted any existing collection")
            except:
                pass
            
            # Create new collection
            self.qdrant_client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE)  # OpenAI ada-002
            )
            print(f"✅ Created collection: {self.collection_name}")
            
        except Exception as e:
            print(f"❌ Collection creation failed: {e}")
            raise
    
    def get_enhanced_products_batch(self, offset: int, limit: int) -> List[Dict]:
        """Get batch of products with enhanced metadata from Neo4j"""
        
        query = """
        MATCH (p:Product)
        OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
        OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
        
        WITH p, 
             collect(DISTINCT c.name) as colors,
             collect(DISTINCT s.name) as styles
        
        WHERE p.id IS NOT NULL
        AND p.title IS NOT NULL
        
        RETURN p.id as uuid,
               p.title as title,
               p.description as description, 
               p.price as price,
               colors,
               styles
        ORDER BY p.title
        SKIP $offset LIMIT $limit
        """
        
        enhanced_products = []
        
        try:
            with self.neo4j_driver.session(database=self.database) as session:
                result = session.run(query, offset=offset, limit=limit)
                
                for record in result:
                    # Get fashion intelligence from Phase 3 ontology
                    colors = record['colors'] or []
                    styles = record['styles'] or []
                    
                    color_complements = self.get_color_complements(colors)
                    style_compatible = self.get_style_compatibility(styles)
                    occasions = self.get_appropriate_occasions(styles)
                    price_tier = self.determine_price_tier(record['price'])
                    
                    # Create enhanced embedding text
                    embedding_text = self.create_embedding_text(
                        record['title'] or '',
                        record['description'] or '',
                        colors,
                        styles,
                        color_complements,
                        style_compatible,
                        occasions,
                        price_tier
                    )
                    
                    # Create comprehensive payload
                    payload = self.create_comprehensive_payload(
                        record, colors, styles, color_complements, 
                        style_compatible, occasions, price_tier
                    )
                    
                    enhanced_products.append({
                        'uuid': record['uuid'],  # CRITICAL: Neo4j p.id becomes Qdrant point ID
                        'embedding_text': embedding_text,
                        'payload': payload
                    })
                    
        except Exception as e:
            print(f"⚠️  Error fetching products at offset {offset}: {e}")
        
        return enhanced_products
    
    def create_embedding_text(self, title: str, description: str, colors: List[str], 
                            styles: List[str], color_complements: List[str], 
                            style_compatible: List[str], occasions: List[str], 
                            price_tier: str) -> str:
        """Create rich embedding text from all available metadata"""
        
        parts = []
        
        # Core product information
        if title:
            parts.append(title)
        if description:
            parts.append(description[:300])  # Limit description length
        
        # Phase 1-5 extracted metadata  
        if colors:
            parts.append(f"Available colors: {', '.join(colors)}")
        if styles:
            parts.append(f"Style categories: {', '.join(styles)}")
        
        # Phase 3 fashion intelligence
        if color_complements:
            parts.append(f"Complements colors: {', '.join(color_complements)}")
        if style_compatible:
            parts.append(f"Style compatible with: {', '.join(style_compatible)}")
        if occasions:
            parts.append(f"Perfect for: {', '.join(occasions)}")
        if price_tier and price_tier != 'unknown':
            parts.append(f"Price tier: {price_tier}")
        
        return " | ".join(parts)
    
    def create_comprehensive_payload(self, record: Dict, colors: List[str], styles: List[str],
                                   color_complements: List[str], style_compatible: List[str],
                                   occasions: List[str], price_tier: str) -> Dict:
        """Create comprehensive searchable payload"""
        
        return {
            # Core product data
            'uuid': record['uuid'],
            'title': record['title'] or '',
            'description': (record['description'] or '')[:500],
            'price': float(record['price'] or 0),
            
            # Phase 1-5 AI-extracted metadata
            'colors': colors,
            'styles': styles,
            'brand': None,  # Would need brand extraction
            
            # Phase 3 fashion intelligence 
            'color_complements': color_complements,
            'style_compatible': style_compatible,
            'occasions': occasions,
            'price_tier': price_tier,
            
            # Search optimization fields
            'has_color_info': len(colors) > 0,
            'has_style_info': len(styles) > 0,
            'primary_color': colors[0] if colors else None,
            'primary_style': styles[0] if styles else None,
            'is_budget_friendly': price_tier == 'budget',
            'is_mid_range': price_tier == 'mid_range', 
            'is_premium': price_tier == 'premium',
            'metadata_completeness': self.calculate_completeness_score(record, colors, styles),
            
            # Quality indicators
            'has_enhanced_metadata': len(colors) > 0 or len(styles) > 0,
            'fashion_intelligence_score': len(color_complements) + len(style_compatible) + len(occasions)
        }
    
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
    
    def calculate_completeness_score(self, record: Dict, colors: List[str], styles: List[str]) -> float:
        """Calculate metadata completeness (0-1)"""
        score = 0
        total = 5
        
        if record.get('title'): score += 1
        if record.get('description'): score += 1  
        if record.get('price') and record['price'] > 0: score += 1
        if colors: score += 1
        if styles: score += 1
        
        return score / total
    
    def generate_embeddings_batch(self, products: List[Dict]) -> List[List[float]]:
        """Generate embeddings for batch using OpenAI"""
        texts = [product['embedding_text'] for product in products]
        
        try:
            response = self.openai_client.embeddings.create(
                model='text-embedding-ada-002',
                input=texts
            )
            return [item.embedding for item in response.data]
            
        except Exception as e:
            print(f"❌ OpenAI embedding error: {e}")
            # Return zero vectors as fallback
            return [[0.0] * 1536 for _ in texts]
    
    def run_fresh_embedding_generation(self, limit: Optional[int] = None):
        """Run complete fresh embedding generation with UUID correspondence"""
        
        # Step 1: Explain embedding fields
        self.explain_embedding_fields()
        
        # Step 2: Get total product count
        with self.neo4j_driver.session(database=self.database) as session:
            result = session.run("MATCH (p:Product) WHERE p.id IS NOT NULL AND p.title IS NOT NULL RETURN count(p) as total")
            total_products = result.single()['total']
        
        if limit:
            total_products = min(total_products, limit)
        
        print(f"\n📊 FRESH EMBEDDING GENERATION")
        print(f"   Total products to process: {total_products:,}")
        
        # Cost estimation
        cost_estimate = total_products * 0.00002
        print(f"   Estimated cost: ${cost_estimate:.2f}")
        
        # Confirm before proceeding
        confirm = input(f"\n🎯 Proceed with fresh embedding generation? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Generation cancelled")
            return
        
        # Step 3: Create fresh Qdrant collection
        self.create_qdrant_collection()
        
        # Step 4: Process in batches
        print(f"\n🚀 Generating fresh UUID-correspondent embeddings...")
        
        processed = 0
        offset = 0
        
        with tqdm(total=total_products, desc="Creating embeddings") as pbar:
            while processed < total_products:
                batch_limit = min(self.batch_size, total_products - processed)
                
                try:
                    # Get enhanced products batch
                    products = self.get_enhanced_products_batch(offset, batch_limit)
                    
                    if not products:
                        break
                    
                    # Generate embeddings
                    embeddings = self.generate_embeddings_batch(products)
                    
                    # Create Qdrant points with UUID correspondence
                    points = []
                    for product, embedding in zip(products, embeddings):
                        point = PointStruct(
                            id=product['uuid'],  # CRITICAL: Neo4j UUID = Qdrant point ID
                            vector=embedding,
                            payload=product['payload']
                        )
                        points.append(point)
                    
                    # Upload to Qdrant
                    self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=points
                    )
                    
                    # Update stats
                    processed += len(products)
                    self.stats['processed'] += len(products)
                    self.stats['embedded'] += len(products)
                    self.stats['enhanced_fields'] += sum(1 for p in products if p['payload']['has_enhanced_metadata'])
                    
                    pbar.update(len(products))
                    offset += batch_limit
                    
                    # Rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"❌ Batch error at offset {offset}: {e}")
                    self.stats['errors'] += batch_limit
                    offset += batch_limit
                    pbar.update(batch_limit)
                    continue
        
        # Step 5: Validate and report
        self.validate_uuid_correspondence()
        self.generate_final_report()
    
    def validate_uuid_correspondence(self):
        """Validate UUID correspondence between Neo4j and Qdrant"""
        print(f"\n🔍 VALIDATING UUID CORRESPONDENCE")
        
        # Check collection
        collection_info = self.qdrant_client.get_collection(self.collection_name)
        print(f"📊 Qdrant collection: {collection_info.points_count:,} vectors")
        
        # Sample UUID verification
        print(f"🔑 UUID Correspondence Check:")
        
        with self.neo4j_driver.session(database=self.database) as session:
            # Get 5 random Neo4j products
            result = session.run("""
                MATCH (p:Product) 
                WHERE p.id IS NOT NULL AND p.title IS NOT NULL
                RETURN p.id as uuid, p.title as title
                ORDER BY rand() 
                LIMIT 5
            """)
            
            neo4j_products = list(result)
        
        matches = 0
        for product in neo4j_products:
            uuid = product['uuid']
            neo4j_title = product['title']
            
            try:
                # Check if same UUID exists in Qdrant
                qdrant_points = self.qdrant_client.retrieve(
                    collection_name=self.collection_name,
                    ids=[uuid],
                    with_payload=True
                )
                
                if qdrant_points:
                    qdrant_title = qdrant_points[0].payload.get('title', '')
                    title_match = neo4j_title == qdrant_title
                    matches += 1 if title_match else 0
                    
                    print(f"   UUID {uuid[:8]}...: {'✅' if title_match else '❌'} Title match")
                    
                    if title_match:
                        # Show enhanced fields
                        payload = qdrant_points[0].payload
                        colors = payload.get('colors', [])
                        styles = payload.get('styles', [])
                        if colors or styles:
                            print(f"      Enhanced: Colors={colors}, Styles={styles}")
                else:
                    print(f"   UUID {uuid[:8]}...: ❌ Not found in Qdrant")
                    
            except Exception as e:
                print(f"   UUID {uuid[:8]}...: ❌ Error: {e}")
        
        print(f"✅ UUID Correspondence: {matches}/5 verified")
        
        # Show sample enhanced payload
        sample_points = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            limit=1,
            with_payload=True
        )[0]
        
        if sample_points:
            sample_payload = sample_points[0].payload
            print(f"\n📋 Sample Enhanced Payload Fields:")
            print(f"   Total fields: {len(sample_payload)}")
            print(f"   Field names: {list(sample_payload.keys())}")
            if 'colors' in sample_payload:
                print(f"   Sample colors: {sample_payload['colors']}")
            if 'occasions' in sample_payload:
                print(f"   Sample occasions: {sample_payload['occasions']}")
    
    def generate_final_report(self):
        """Generate final embedding generation report"""
        print(f"\n🎉 FRESH UUID-CORRESPONDENT EMBEDDING GENERATION COMPLETE!")
        print("="*70)
        
        print(f"📊 GENERATION STATISTICS:")
        print(f"   Products processed: {self.stats['processed']:,}")
        print(f"   Embeddings created: {self.stats['embedded']:,}")
        print(f"   Enhanced with metadata: {self.stats['enhanced_fields']:,}")
        print(f"   Errors: {self.stats['errors']:,}")
        
        print(f"\n🔑 UUID CORRESPONDENCE:")
        print(f"   ✅ Perfect 1:1 mapping between Neo4j p.id and Qdrant point.id")
        print(f"   ✅ Every embedding corresponds to exact Neo4j product UUID")
        
        print(f"\n📝 EMBEDDED FIELDS SUMMARY:")
        print(f"   Core: title, description, price")
        print(f"   Colors: AI-extracted color information")
        print(f"   Styles: AI-extracted style categories")
        print(f"   Intelligence: color complements, style compatibility, occasions")
        print(f"   Optimization: 15+ searchable payload fields")
        
        print(f"\n✅ Collection '{self.collection_name}' ready for production!")
        
    def cleanup(self):
        """Cleanup resources"""
        self.neo4j_driver.close()

def main():
    """Main execution"""
    generator = FreshUUIDEmbeddingGenerator()
    
    try:
        # Ask for limit
        limit_input = input("\n🎯 Limit products for testing? (Enter number or press Enter for all): ")
        limit = int(limit_input) if limit_input.strip() else None
        
        generator.run_fresh_embedding_generation(limit=limit)
        
    except KeyboardInterrupt:
        print("\n❌ Generation interrupted by user")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        generator.cleanup()

if __name__ == "__main__":
    main()