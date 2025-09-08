#!/usr/bin/env python3
"""
Test Enhanced Embedding Creation
"""

import os
import time
from dotenv import load_dotenv
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from openai import OpenAI

load_dotenv()

def test_enhanced_embedding():
    print('🚀 Testing Enhanced Qdrant Embedding Process...')
    print('='*60)

    # Initialize connections
    neo4j_driver = GraphDatabase.driver(
        'bolt://34.135.40.119:7687',
        auth=('neo4j', 'shopari1234')
    )

    qdrant = QdrantClient(
        url=os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API_KEY'),
        timeout=30
    )

    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    collection_name = 'fashion_products_enhanced_test'
    database = 'productionbackup2'

    print(f'📊 Test collection: {collection_name}')

    try:
        # Step 1: Clear and create test collection
        print('\n🗑️ Managing test collection...')
        try:
            qdrant.delete_collection(collection_name)
            print('   Deleted existing test collection')
        except:
            print('   Test collection does not exist')

        # Create new collection
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
        print(f'✅ Created test collection: {collection_name}')

        # Step 2: Get sample enhanced products
        print('\n📊 Fetching enhanced product data...')

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
        LIMIT 5
        """

        products = []
        with neo4j_driver.session(database=database) as session:
            result = session.run(query)
            
            for record in result:
                # Create enhanced text
                title = record['title'] or ''
                description = (record['description'] or '')[:300]
                colors = record['colors'] or []
                styles = record['styles'] or []
                
                enhanced_text_parts = [title]
                if description:
                    enhanced_text_parts.append(description)
                if colors:
                    enhanced_text_parts.append(f"Colors: {', '.join(colors)}")
                if styles:
                    enhanced_text_parts.append(f"Styles: {', '.join(styles)}")
                    
                enhanced_text = ' | '.join(enhanced_text_parts)
                
                # Create enhanced payload
                payload = {
                    'uuid': record['uuid'],
                    'title': title,
                    'description': description,
                    'price': float(record['price'] or 0),
                    'colors': colors,
                    'styles': styles,
                    'has_color_info': len(colors) > 0,
                    'has_style_info': len(styles) > 0,
                    'primary_color': colors[0] if colors else None,
                    'primary_style': styles[0] if styles else None,
                }
                
                products.append({
                    'uuid': record['uuid'],
                    'enhanced_text': enhanced_text,
                    'payload': payload
                })

        print(f'   Found {len(products)} products with enhanced metadata')
        
        # Show sample enhanced text
        if products:
            print(f'   Sample enhanced text: {products[0]["enhanced_text"][:150]}...')

        # Step 3: Generate embeddings
        if products:
            print('\n🧠 Generating OpenAI embeddings...')
            texts = [p['enhanced_text'] for p in products]
            
            response = openai_client.embeddings.create(
                model='text-embedding-ada-002',
                input=texts
            )
            
            embeddings = [item.embedding for item in response.data]
            print(f'   Created {len(embeddings)} embeddings')
            
            # Step 4: Upload to Qdrant
            print('\n🚀 Uploading enhanced embeddings...')
            points = []
            for product, embedding in zip(products, embeddings):
                point = PointStruct(
                    id=product['uuid'],
                    vector=embedding,
                    payload=product['payload']
                )
                points.append(point)
            
            qdrant.upsert(collection_name=collection_name, points=points)
            print(f'   Uploaded {len(points)} enhanced embeddings')
            
            # Step 5: Validate
            print('\n✅ Validating enhanced collection...')
            collection_info = qdrant.get_collection(collection_name)
            print(f'   Total points: {collection_info.points_count}')
            
            if collection_info.points_count > 0:
                sample = qdrant.scroll(collection_name=collection_name, limit=1, with_payload=True)[0]
                if sample:
                    print(f'   Enhanced payload keys: {list(sample[0].payload.keys())}')
                    print(f'   Sample colors: {sample[0].payload.get("colors", [])}')
                    print(f'   Sample styles: {sample[0].payload.get("styles", [])}')
            
            print('\n🎉 Enhanced embedding test completed successfully!')
            return True
            
        else:
            print('❌ No products found to process')
            return False

    except Exception as e:
        print(f'❌ Test failed: {e}')
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        neo4j_driver.close()

if __name__ == "__main__":
    success = test_enhanced_embedding()
    exit(0 if success else 1)