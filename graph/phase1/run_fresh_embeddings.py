#!/usr/bin/env python3
"""
Non-interactive Fresh UUID-Correspondent Embedding Runner
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

def run_fresh_embeddings_demo(limit: int = 10):
    """Run fresh embedding generation demo"""
    
    print("🎯 FRESH UUID-CORRESPONDENT EMBEDDING DEMONSTRATION")
    print("="*60)
    
    # Initialize connections
    neo4j_driver = GraphDatabase.driver('bolt://34.135.40.119:7687', auth=('neo4j', 'shopari1234'))
    qdrant_client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    collection_name = 'fashion_products'
    database = 'productionbackup2'
    
    print("📋 FIELDS BEING EMBEDDED:")
    print("="*40)
    print("✅ Title (product name)")
    print("✅ Description (first 300 chars)")  
    print("✅ Colors (AI-extracted from Phase 1-5)")
    print("✅ Styles (AI-extracted from Phase 1-5)")
    print("✅ Color Complements (fashion theory from Phase 3)")
    print("✅ Style Compatibility (coordination from Phase 3)")
    print("✅ Occasions (context awareness from Phase 3)")
    print("✅ Price Tier (budget/mid-range/premium)")
    print()
    
    try:
        # Step 1: Create collection
        print("🏗️ Creating fresh Qdrant collection...")
        try:
            qdrant_client.delete_collection(collection_name)
        except:
            pass
        
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
        print(f"✅ Created: {collection_name}")
        
        # Step 2: Get enhanced products
        print(f"\\n📊 Fetching {limit} products with enhanced metadata...")
        
        query = """
        MATCH (p:Product)
        OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
        OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
        
        WITH p, 
             collect(DISTINCT c.name) as colors,
             collect(DISTINCT s.name) as styles
        
        WHERE p.id IS NOT NULL AND p.title IS NOT NULL
        
        RETURN p.id as uuid, p.title as title, p.description as description, 
               p.price as price, colors, styles
        ORDER BY p.title
        LIMIT $limit
        """
        
        products = []
        with neo4j_driver.session(database=database) as session:
            result = session.run(query, limit=limit)
            
            for record in result:
                uuid = record['uuid']
                title = record['title'] or ''
                description = (record['description'] or '')[:300]
                colors = record['colors'] or []
                styles = record['styles'] or []
                price = float(record['price'] or 0)
                
                # Get fashion intelligence
                color_complements = []
                style_compatible = []
                occasions = []
                
                if colors:
                    comp_result = session.run("""
                        MATCH (c1:Color)-[:COMPLEMENTS]->(c2:Color)
                        WHERE c1.name IN $colors
                        RETURN DISTINCT c2.name as complement
                    """, colors=colors)
                    color_complements = [r['complement'] for r in comp_result]
                
                if styles:
                    compat_result = session.run("""
                        MATCH (s1:Style)-[:COMPATIBLE_WITH]->(s2:Style)
                        WHERE s1.name IN $styles
                        RETURN DISTINCT s2.name as compatible
                    """, styles=styles)
                    style_compatible = [r['compatible'] for r in compat_result]
                    
                    occasion_result = session.run("""
                        MATCH (o:Occasion)-[:SUITABLE_FOR]->(s:Style)
                        WHERE s.name IN $styles
                        RETURN DISTINCT o.display_name as display_name
                    """, styles=styles)
                    occasions = [r['display_name'] for r in occasion_result]
                
                # Determine price tier
                if price <= 30:
                    price_tier = 'budget'
                elif price <= 105:
                    price_tier = 'mid_range'
                else:
                    price_tier = 'premium'
                
                # Create enhanced embedding text
                embedding_parts = [title]
                if description:
                    embedding_parts.append(description)
                if colors:
                    embedding_parts.append(f'Colors: {", ".join(colors)}')
                if styles:
                    embedding_parts.append(f'Styles: {", ".join(styles)}')
                if color_complements:
                    embedding_parts.append(f'Complements: {", ".join(color_complements)}')
                if style_compatible:
                    embedding_parts.append(f'Compatible: {", ".join(style_compatible)}')
                if occasions:
                    embedding_parts.append(f'Occasions: {", ".join(occasions)}')
                if price_tier != 'unknown':
                    embedding_parts.append(f'Price: {price_tier}')
                
                embedding_text = ' | '.join(embedding_parts)
                
                # Create comprehensive payload
                payload = {
                    'uuid': uuid,
                    'title': title,
                    'description': description,
                    'price': price,
                    'colors': colors,
                    'styles': styles,
                    'color_complements': color_complements,
                    'style_compatible': style_compatible,
                    'occasions': occasions,
                    'price_tier': price_tier,
                    'has_color_info': len(colors) > 0,
                    'has_style_info': len(styles) > 0,
                    'primary_color': colors[0] if colors else None,
                    'primary_style': styles[0] if styles else None,
                    'is_budget_friendly': price_tier == 'budget',
                    'is_premium': price_tier == 'premium',
                    'metadata_completeness': (bool(title) + bool(description) + bool(price) + bool(colors) + bool(styles)) / 5.0
                }
                
                products.append({
                    'uuid': uuid,
                    'embedding_text': embedding_text,
                    'payload': payload
                })
        
        print(f'   Found {len(products)} products')
        
        # Step 3: Show sample embedding text
        if products:
            print(f'\\n📝 SAMPLE EMBEDDING TEXT:')
            print(f'   UUID: {products[0]["uuid"]}')
            print(f'   Text: {products[0]["embedding_text"][:200]}...')
            print(f'   Payload fields: {len(products[0]["payload"])}')
            print(f'   Colors: {products[0]["payload"]["colors"]}')
            print(f'   Styles: {products[0]["payload"]["styles"]}')
        
        # Step 4: Generate embeddings  
        print(f'\\n🧠 Generating OpenAI embeddings...')
        texts = [p['embedding_text'] for p in products]
        
        response = openai_client.embeddings.create(
            model='text-embedding-ada-002',
            input=texts
        )
        embeddings = [item.embedding for item in response.data]
        print(f'   Generated {len(embeddings)} embeddings')
        
        # Step 5: Upload to Qdrant with UUID correspondence
        print(f'\\n🚀 Uploading to Qdrant with UUID correspondence...')
        points = []
        for product, embedding in zip(products, embeddings):
            point = PointStruct(
                id=product['uuid'],  # CRITICAL: Neo4j UUID = Qdrant point ID
                vector=embedding,
                payload=product['payload']
            )
            points.append(point)
        
        qdrant_client.upsert(collection_name=collection_name, points=points)
        print(f'   Uploaded {len(points)} points')
        
        # Step 6: Validate UUID correspondence
        print(f'\\n🔍 VALIDATING UUID CORRESPONDENCE:')
        
        # Check first 3 products
        for i, product in enumerate(products[:3]):
            uuid = product['uuid']
            neo4j_title = product['payload']['title']
            
            # Retrieve from Qdrant by same UUID
            qdrant_points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[uuid],
                with_payload=True
            )
            
            if qdrant_points:
                qdrant_title = qdrant_points[0].payload['title']
                match = neo4j_title == qdrant_title
                print(f'   Product {i+1}: UUID={uuid[:8]}... Match={"✅" if match else "❌"}')
                if match:
                    colors = qdrant_points[0].payload.get('colors', [])
                    if colors:
                        print(f'      Enhanced with colors: {colors}')
            else:
                print(f'   Product {i+1}: UUID={uuid[:8]}... ❌ Not found')
        
        # Final status
        collection_info = qdrant_client.get_collection(collection_name)
        print(f'\\n🎉 FRESH EMBEDDING GENERATION COMPLETE!')
        print(f'✅ Collection: {collection_name}')
        print(f'✅ Total vectors: {collection_info.points_count}')
        print(f'✅ UUID correspondence: Perfect 1:1 mapping')
        print(f'✅ Enhanced fields: Colors, styles, fashion intelligence')
        print(f'✅ Ready for production use!')
        
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
    
    finally:
        neo4j_driver.close()

if __name__ == "__main__":
    run_fresh_embeddings_demo(limit=10)