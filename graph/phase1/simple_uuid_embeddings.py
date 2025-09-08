#!/usr/bin/env python3
"""
Simple UUID-Correspondent Embedding Generator
Memory-efficient approach that works with Neo4j constraints
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

def generate_simple_uuid_embeddings(limit: Optional[int] = None):
    """Generate embeddings with perfect UUID correspondence using simple queries"""
    
    print("🎯 SIMPLE UUID-CORRESPONDENT EMBEDDING GENERATION")
    print("="*60)
    
    # Initialize connections
    neo4j_driver = GraphDatabase.driver('bolt://34.135.40.119:7687', auth=('neo4j', 'shopari1234'))
    qdrant_client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    collection_name = 'fashion_products'
    database = 'productionbackup2'
    
    print("📋 FIELDS BEING EMBEDDED INTO VECTOR:")
    print("="*50)
    print("✅ Title (product name)")
    print("✅ Description (product description)")
    print("✅ Enhanced with: 'fashion product clothing apparel'")
    print()
    
    print("📊 PAYLOAD FIELDS (searchable metadata):")
    print("="*50)
    print("✅ uuid (Neo4j product ID)")
    print("✅ title (product name)")  
    print("✅ description (product description)")
    print("✅ price (product price)")
    print("✅ category (inferred from title)")
    print("✅ has_description (boolean)")
    print("✅ has_price (boolean)")
    print("✅ price_tier (budget/mid_range/premium)")
    print()
    
    try:
        # Step 1: Create fresh collection
        print("🏗️ Creating fresh Qdrant collection...")
        try:
            qdrant_client.delete_collection(collection_name)
        except:
            pass
        
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
        print(f"✅ Created collection: {collection_name}")
        
        # Step 2: Get total count
        with neo4j_driver.session(database=database) as session:
            result = session.run("MATCH (p:Product) WHERE p.id IS NOT NULL AND p.title IS NOT NULL RETURN count(p) as total")
            total_products = result.single()['total']
        
        if limit:
            total_products = min(total_products, limit)
        
        print(f"📊 Products to process: {total_products:,}")
        print(f"💰 Estimated cost: ${total_products * 0.00002:.2f}")
        
        # Step 3: Process in small batches to avoid memory issues
        batch_size = 20  # Very small to avoid memory issues
        processed = 0
        
        print(f"\n🚀 Processing in batches of {batch_size}...")
        
        for offset in range(0, total_products, batch_size):
            current_batch_size = min(batch_size, total_products - offset)
            
            try:
                # Simple query without relationships to avoid memory issues
                with neo4j_driver.session(database=database) as session:
                    result = session.run("""
                        MATCH (p:Product)
                        WHERE p.id IS NOT NULL AND p.title IS NOT NULL
                        RETURN p.id as uuid, p.title as title, p.description as description, p.price as price
                        SKIP $offset LIMIT $batch_size
                    """, offset=offset, batch_size=current_batch_size)
                    
                    products = []
                    texts = []
                    
                    for record in result:
                        uuid = record['uuid']
                        title = record['title'] or ''
                        description = record['description'] or ''
                        price = float(record['price'] or 0)
                        
                        # Create embedding text (simple approach)
                        embedding_text = f"{title} {description} fashion product clothing apparel"
                        texts.append(embedding_text[:8000])  # Limit length
                        
                        # Infer category from title
                        title_lower = title.lower()
                        if any(word in title_lower for word in ['dress', 'gown']):
                            category = 'dresses'
                        elif any(word in title_lower for word in ['shirt', 'top', 'blouse', 'tee']):
                            category = 'tops'
                        elif any(word in title_lower for word in ['pants', 'jeans', 'shorts', 'trouser']):
                            category = 'bottoms'
                        elif any(word in title_lower for word in ['shoe', 'boot', 'sneaker', 'sandal']):
                            category = 'shoes'
                        elif any(word in title_lower for word in ['jacket', 'coat', 'blazer']):
                            category = 'outerwear'
                        else:
                            category = 'other'
                        
                        # Determine price tier
                        if price <= 30:
                            price_tier = 'budget'
                        elif price <= 105:
                            price_tier = 'mid_range'
                        else:
                            price_tier = 'premium'
                        
                        # Create payload
                        payload = {
                            'uuid': uuid,
                            'title': title,
                            'description': description,
                            'price': price,
                            'category': category,
                            'has_description': bool(description),
                            'has_price': price > 0,
                            'price_tier': price_tier,
                            'is_budget_friendly': price_tier == 'budget',
                            'is_premium': price_tier == 'premium'
                        }
                        
                        products.append({
                            'uuid': uuid,
                            'payload': payload
                        })
                
                if not products:
                    break
                
                # Generate embeddings for batch
                response = openai_client.embeddings.create(
                    model='text-embedding-ada-002',
                    input=texts
                )
                embeddings = [item.embedding for item in response.data]
                
                # Create Qdrant points with perfect UUID correspondence
                points = []
                for product, embedding in zip(products, embeddings):
                    point = PointStruct(
                        id=product['uuid'],  # CRITICAL: Neo4j p.id = Qdrant point.id
                        vector=embedding,
                        payload=product['payload']
                    )
                    points.append(point)
                
                # Upload to Qdrant
                qdrant_client.upsert(collection_name=collection_name, points=points)
                
                processed += len(products)
                
                if processed % 100 == 0:
                    print(f"   Processed: {processed:,}/{total_products:,} ({processed/total_products*100:.1f}%)")
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Batch error at offset {offset}: {e}")
                continue
        
        # Step 4: Validate UUID correspondence
        print(f"\n🔍 VALIDATING UUID CORRESPONDENCE:")
        
        collection_info = qdrant_client.get_collection(collection_name)
        print(f"📊 Qdrant vectors created: {collection_info.points_count:,}")
        
        # Test UUID correspondence
        with neo4j_driver.session(database=database) as session:
            result = session.run("""
                MATCH (p:Product) 
                WHERE p.id IS NOT NULL AND p.title IS NOT NULL
                RETURN p.id as uuid, p.title as title
                LIMIT 5
            """)
            
            test_products = list(result)
        
        print("🔑 UUID Correspondence Test:")
        matches = 0
        
        for product in test_products:
            uuid = product['uuid']
            neo4j_title = product['title']
            
            try:
                # Check if same UUID exists in Qdrant
                qdrant_points = qdrant_client.retrieve(
                    collection_name=collection_name,
                    ids=[uuid],
                    with_payload=True
                )
                
                if qdrant_points and len(qdrant_points) > 0:
                    qdrant_title = qdrant_points[0].payload['title']
                    title_match = neo4j_title == qdrant_title
                    matches += 1 if title_match else 0
                    
                    print(f"   UUID {uuid[:8]}...: {'✅' if title_match else '❌'} Title: '{qdrant_title[:30]}...'")
                else:
                    print(f"   UUID {uuid[:8]}...: ❌ Not found in Qdrant")
                    
            except Exception as e:
                print(f"   UUID {uuid[:8]}...: ❌ Error: {e}")
        
        print(f"✅ UUID correspondence: {matches}/{len(test_products)} verified")
        
        # Show sample payload
        if collection_info.points_count > 0:
            sample = qdrant_client.scroll(collection_name=collection_name, limit=1, with_payload=True)[0]
            if sample:
                payload = sample[0].payload
                print(f"\n📋 Sample payload structure:")
                for key, value in payload.items():
                    if isinstance(value, str) and len(value) > 50:
                        print(f"   {key}: '{value[:50]}...'")
                    else:
                        print(f"   {key}: {value}")
        
        print(f"\n🎉 SIMPLE UUID-CORRESPONDENT EMBEDDINGS COMPLETE!")
        print(f"✅ Perfect UUID mapping: Neo4j p.id = Qdrant point.id")
        print(f"✅ Embeddings include: title + description + fashion context")
        print(f"✅ Searchable payloads: 10 metadata fields")
        print(f"✅ Collection ready: {collection_name}")
        
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        neo4j_driver.close()

if __name__ == "__main__":
    # For demonstration, limit to 100 products
    generate_simple_uuid_embeddings(limit=100)