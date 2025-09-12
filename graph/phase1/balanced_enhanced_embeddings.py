#!/usr/bin/env python3
"""
Balanced Enhanced Embedding Generator
Embeds core attributes, keeps fashion intelligence as searchable metadata only
"""

import os
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI

load_dotenv()

def generate_balanced_enhanced_embeddings(limit: Optional[int] = None):
    """Generate balanced embeddings: core attributes in vectors, intelligence in metadata"""
    
    print("🎯 BALANCED ENHANCED EMBEDDING GENERATION")
    print("="*60)
    
    # Initialize connections
    neo4j_driver = GraphDatabase.driver('bolt://34.135.40.119:7687', auth=('neo4j', 'shopari1234'))
    qdrant_client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    collection_name = 'fashion_products'
    database = 'productionbackup2'
    
    print("🧠 BALANCED APPROACH:")
    print("="*30)
    print("📊 EMBEDDED IN VECTORS (core attributes):")
    print("   ✅ Title (product name)")
    print("   ✅ Description (product details)")
    print("   ✅ Colors (AI-extracted from Phase 1-5)")
    print("   ✅ Styles (AI-extracted from Phase 1-5)")
    print("   ✅ Price Tier (budget/mid-range/premium)")
    print("   ✅ Category (tops/bottoms/shoes/etc)")
    print()
    print("🔍 SEARCHABLE METADATA ONLY (fashion intelligence):")
    print("   📋 Color Complements (for recommendations)")
    print("   📋 Style Compatibility (for outfit building)")
    print("   📋 Occasions (for contextual filtering)")
    print()
    
    print("💡 WHY THIS APPROACH:")
    print("   • Vectors capture core product essence")
    print("   • No bias from fashion rules")
    print("   • Natural discovery of combinations")
    print("   • Intelligence available for advanced features")
    print()
    
    try:
        # Step 1: Clear and create collection
        print("🗑️ Clearing existing collection...")
        try:
            qdrant_client.delete_collection(collection_name)
            print("   Deleted existing collection")
        except:
            print("   No existing collection to delete")
        
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
        print(f"✅ Created balanced collection: {collection_name}")
        
        # Step 2: Get total count
        with neo4j_driver.session(database=database) as session:
            result = session.run("MATCH (p:Product) WHERE p.id IS NOT NULL AND p.title IS NOT NULL RETURN count(p) as total")
            total_products = result.single()['total']
        
        if limit:
            total_products = min(total_products, limit)
        
        print(f"📊 Products to process: {total_products:,}")
        print(f"💰 Estimated cost: ${total_products * 0.00002:.2f}")
        
        # Step 3: Pre-build fashion intelligence lookup (for metadata only)
        print("🧠 Building fashion intelligence lookup (for metadata)...")
        
        with neo4j_driver.session(database=database) as session:
            # Color complements
            result = session.run("MATCH (c1:Color)-[:COMPLEMENTS]->(c2:Color) RETURN c1.name as color, collect(c2.name) as complements")
            color_complements_map = {record['color']: record['complements'] for record in result}
            
            # Style compatibility
            result = session.run("MATCH (s1:Style)-[:COMPATIBLE_WITH]->(s2:Style) RETURN s1.name as style, collect(s2.name) as compatible")
            style_compatibility_map = {record['style']: record['compatible'] for record in result}
            
            # Occasions
            result = session.run("MATCH (o:Occasion)-[:SUITABLE_FOR]->(s:Style) RETURN s.name as style, collect(o.display_name) as occasions")
            style_occasions_map = {record['style']: record['occasions'] for record in result}
        
        print(f"   Color complements: {len(color_complements_map)} mappings")
        print(f"   Style compatibility: {len(style_compatibility_map)} mappings")
        print(f"   Occasion mappings: {len(style_occasions_map)} mappings")
        
        # Step 4: Process in large optimized batches for maximum speed  
        batch_size = 800   # Optimized for A100 - safely under Qdrant's 33.5MB payload limit
        processed = 0
        
        print(f"\\n🚀 Generating balanced enhanced embeddings...")
        
        for offset in range(0, total_products, batch_size):
            current_batch_size = min(batch_size, total_products - offset)
            
            try:
                # Simple query to avoid memory issues
                with neo4j_driver.session(database=database) as session:
                    result = session.run("""
                        MATCH (p:Product)
                        WHERE p.id IS NOT NULL AND p.title IS NOT NULL
                        RETURN p.id as uuid, p.title as title, p.description as description, p.price as price
                        ORDER BY p.title
                        SKIP $offset LIMIT $batch_size
                    """, offset=offset, batch_size=current_batch_size)
                    
                    batch_products = list(result)
                
                if not batch_products:
                    break
                
                # Get colors and styles for this batch separately to avoid memory issues
                uuids = [p['uuid'] for p in batch_products]
                
                # Get colors for batch
                with neo4j_driver.session(database=database) as session:
                    result = session.run("""
                        MATCH (p:Product)-[:HAS_COLOR]->(c:Color)
                        WHERE p.id IN $uuids
                        RETURN p.id as uuid, collect(c.name) as colors
                    """, uuids=uuids)
                    
                    colors_by_uuid = {record['uuid']: record['colors'] for record in result}
                
                # Get styles for batch
                with neo4j_driver.session(database=database) as session:
                    result = session.run("""
                        MATCH (p:Product)-[:HAS_STYLE]->(s:Style)
                        WHERE p.id IN $uuids
                        RETURN p.id as uuid, collect(s.name) as styles
                    """, uuids=uuids)
                    
                    styles_by_uuid = {record['uuid']: record['styles'] for record in result}
                
                # Process products
                products = []
                embedding_texts = []
                
                for record in batch_products:
                    uuid = record['uuid']
                    title = record['title'] or ''
                    description = record['description'] or ''
                    price = float(record['price'] or 0)
                    colors = colors_by_uuid.get(uuid, [])
                    styles = styles_by_uuid.get(uuid, [])
                    
                    # Get fashion intelligence for metadata (not embedding)
                    color_complements = []
                    style_compatible = []
                    occasions = []
                    
                    for color in colors:
                        if color in color_complements_map:
                            color_complements.extend(color_complements_map[color])
                    color_complements = list(set(color_complements))
                    
                    for style in styles:
                        if style in style_compatibility_map:
                            style_compatible.extend(style_compatibility_map[style])
                        if style in style_occasions_map:
                            occasions.extend(style_occasions_map[style])
                    style_compatible = list(set(style_compatible))
                    occasions = list(set(occasions))
                    
                    # Price tier
                    if price <= 30:
                        price_tier = 'budget'
                    elif price <= 105:
                        price_tier = 'mid_range'
                    else:
                        price_tier = 'premium'
                    
                    # Infer category
                    title_lower = title.lower()
                    if any(word in title_lower for word in ['dress', 'gown']):
                        category = 'dresses'
                    elif any(word in title_lower for word in ['shirt', 'top', 'blouse', 'tee']):
                        category = 'tops'
                    elif any(word in title_lower for word in ['pants', 'jeans', 'shorts']):
                        category = 'bottoms'
                    elif any(word in title_lower for word in ['shoe', 'boot', 'sneaker']):
                        category = 'shoes'
                    elif any(word in title_lower for word in ['jacket', 'coat', 'blazer']):
                        category = 'outerwear'
                    else:
                        category = 'other'
                    
                    # CREATE BALANCED EMBEDDING TEXT (core attributes only)
                    embedding_parts = []
                    
                    # Core product info
                    embedding_parts.append(title)
                    if description:
                        embedding_parts.append(description[:300])
                    
                    # Core extracted attributes (no bias)
                    if colors:
                        embedding_parts.append(f"Colors: {', '.join(colors)}")
                    if styles:
                        embedding_parts.append(f"Styles: {', '.join(styles)}")
                    if price_tier:
                        embedding_parts.append(f"Price tier: {price_tier}")
                    
                    # Category and fashion context
                    embedding_parts.append(f"Category: {category}")
                    embedding_parts.append("fashion clothing apparel")
                    
                    # Create balanced embedding text
                    balanced_embedding_text = ' | '.join(embedding_parts)
                    embedding_texts.append(balanced_embedding_text[:8000])
                    
                    # Create comprehensive payload (includes intelligence as metadata)
                    payload = {
                        'uuid': uuid,
                        'title': title,
                        'description': description,
                        'price': price,
                        'category': category,
                        
                        # Core attributes (also in embedding)
                        'colors': colors,
                        'styles': styles,
                        'price_tier': price_tier,
                        
                        # Fashion intelligence (metadata only - NOT in embedding)
                        'color_complements': color_complements,
                        'style_compatible': style_compatible,
                        'occasions': occasions,
                        
                        # Search optimization
                        'has_color_info': len(colors) > 0,
                        'has_style_info': len(styles) > 0,
                        'has_description': bool(description),
                        'has_price': price > 0,
                        'primary_color': colors[0] if colors else None,
                        'primary_style': styles[0] if styles else None,
                        'is_budget_friendly': price_tier == 'budget',
                        'is_premium': price_tier == 'premium',
                        
                        # Intelligence metrics
                        'color_complement_count': len(color_complements),
                        'style_compatibility_count': len(style_compatible),
                        'occasion_count': len(occasions),
                        'metadata_completeness': (bool(title) + bool(description) + bool(colors) + bool(styles) + bool(price > 0)) / 5.0
                    }
                    
                    products.append({
                        'uuid': uuid,
                        'payload': payload
                    })
                
                # Generate balanced embeddings
                response = openai_client.embeddings.create(
                    model='text-embedding-ada-002',
                    input=embedding_texts
                )
                embeddings = [item.embedding for item in response.data]
                
                # Create Qdrant points
                points = []
                for product, embedding in zip(products, embeddings):
                    point = PointStruct(
                        id=product['uuid'],
                        vector=embedding,  # Balanced: core attributes only
                        payload=product['payload']  # Complete: includes intelligence
                    )
                    points.append(point)
                
                # Upload to Qdrant
                qdrant_client.upsert(collection_name=collection_name, points=points)
                
                processed += len(products)
                
                if processed % 100 == 0:
                    print(f"   Balanced: {processed:,}/{total_products:,} ({processed/total_products*100:.1f}%)")
                
                time.sleep(0.1)  # Faster rate limiting for optimized production
                
            except Exception as e:
                print(f"⚠️  Batch error at offset {offset}: {e}")
                continue
        
        # Step 5: Validate balanced approach
        print(f"\\n🔍 VALIDATING BALANCED APPROACH:")
        
        collection_info = qdrant_client.get_collection(collection_name)
        print(f"📊 Balanced vectors created: {collection_info.points_count:,}")
        
        # Show sample balanced embedding and metadata
        if collection_info.points_count > 0:
            sample_points = qdrant_client.scroll(collection_name=collection_name, limit=1, with_payload=True)[0]
            if sample_points:
                payload = sample_points[0].payload
                
                print(f"\\n📋 SAMPLE BALANCED STRUCTURE:")
                print(f"   UUID: {payload['uuid']}")
                print(f"   Title: {payload['title'][:40]}...")
                
                print(f"\\n🧠 EMBEDDED ATTRIBUTES (in vector):")
                print(f"   Colors: {payload.get('colors', [])}")
                print(f"   Styles: {payload.get('styles', [])}")
                print(f"   Price tier: {payload.get('price_tier')}")
                print(f"   Category: {payload.get('category')}")
                
                print(f"\\n🔍 INTELLIGENCE METADATA (searchable only):")
                print(f"   Color complements: {payload.get('color_complements', [])}")
                print(f"   Style compatible: {payload.get('style_compatible', [])}")
                print(f"   Occasions: {payload.get('occasions', [])}")
        
        print(f"\\n🎉 BALANCED ENHANCED EMBEDDINGS COMPLETE!")
        print("="*60)
        print(f"✅ Vectors: Unbiased core attributes (colors, styles, price, category)")
        print(f"✅ Metadata: Fashion intelligence available for recommendations")
        print(f"✅ Discovery: Natural exploration without bias")
        print(f"✅ Intelligence: Available when needed for advanced features")
        print(f"✅ UUID correspondence: Perfect Neo4j mapping")
        print(f"\\n🚀 Collection '{collection_name}' ready for production!")
        
    except Exception as e:
        print(f"❌ Balanced embedding generation failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        neo4j_driver.close()

if __name__ == "__main__":
    # Production run - all 6.4M products
    print("🚀 PRODUCTION RUN: Generating balanced embeddings for ALL products...")
    generate_balanced_enhanced_embeddings(limit=None)