#!/usr/bin/env python3
"""
Investigate ID Mismatch Between Neo4j and Qdrant
Deep dive into the ID format and matching issues
"""

import json
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

def investigate_id_formats():
    print("🔍 Investigating ID format mismatch between Neo4j and Qdrant...")
    
    # Neo4j connection
    neo4j_url = "bolt://0.0.0.0:17687"
    neo4j_user = "neo4j"
    neo4j_password = "6D%q@jbYmstkK2i3oW5z6B6outew9m93"
    
    # Qdrant connection
    qdrant_url = "https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io"
    qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg"
    collection_name = "fashion_products"
    
    # Connect to Neo4j
    neo4j_driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
    
    # Connect to Qdrant
    qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    print("\n📊 SAMPLING IDs FROM BOTH DATABASES:")
    
    # Sample Neo4j IDs
    print("\n🔍 Neo4j Sample IDs:")
    with neo4j_driver.session() as session:
        result = session.run("MATCH (p:Product) RETURN p.id as id LIMIT 10")
        neo4j_sample_ids = []
        for i, record in enumerate(result):
            product_id = record['id']
            neo4j_sample_ids.append(product_id)
            print(f"  {i+1}. {product_id} (type: {type(product_id)}, length: {len(str(product_id))})")
    
    # Sample Qdrant IDs  
    print("\n🔍 Qdrant Sample IDs:")
    scroll_result = qdrant_client.scroll(
        collection_name=collection_name,
        limit=10,
        with_vectors=False,
        with_payload=True
    )
    
    qdrant_sample_ids = []
    for i, point in enumerate(scroll_result[0]):
        point_id = point.id
        qdrant_sample_ids.append(str(point_id))
        print(f"  {i+1}. {point_id} (type: {type(point_id)}, length: {len(str(point_id))})")
        
        # Also show payload structure
        if i == 0:
            print(f"     Payload keys: {list(point.payload.keys()) if point.payload else 'No payload'}")
            if point.payload and 'product_id' in point.payload:
                print(f"     Payload product_id: {point.payload['product_id']}")
    
    print("\n🔍 CHECKING FOR MATCHES:")
    
    # Check if any Neo4j IDs match Qdrant IDs directly
    neo4j_set = set(str(id) for id in neo4j_sample_ids)
    qdrant_set = set(str(id) for id in qdrant_sample_ids)
    direct_matches = neo4j_set & qdrant_set
    
    print(f"Direct ID matches: {len(direct_matches)}")
    if direct_matches:
        print(f"Matching IDs: {direct_matches}")
    
    # Check if Qdrant payload contains Neo4j IDs
    print("\n🔍 CHECKING QDRANT PAYLOAD FOR NEO4J IDs:")
    payload_matches = 0
    
    for neo4j_id in neo4j_sample_ids[:5]:  # Check first 5
        # Search for this ID in Qdrant payload
        try:
            search_result = qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter={"must": [{"key": "product_id", "match": {"value": str(neo4j_id)}}]},
                limit=1,
                with_payload=True
            )
            
            if search_result[0]:
                payload_matches += 1
                point = search_result[0][0]
                print(f"  ✅ Neo4j ID {neo4j_id} found in Qdrant as point {point.id}")
                print(f"     Payload: {point.payload}")
            else:
                print(f"  ❌ Neo4j ID {neo4j_id} NOT found in Qdrant payload")
                
        except Exception as e:
            print(f"  ⚠️ Error searching for {neo4j_id}: {e}")
    
    print(f"\nPayload matches found: {payload_matches}/5")
    
    # Check Qdrant collection info
    print("\n📊 QDRANT COLLECTION DETAILS:")
    collection_info = qdrant_client.get_collection(collection_name)
    print(f"Total points: {collection_info.points_count}")
    print(f"Vectors count: {collection_info.vectors_count}")
    
    # Sample a few more Qdrant points to understand ID format
    print("\n🔍 ANALYZING QDRANT ID PATTERNS:")
    scroll_result = qdrant_client.scroll(
        collection_name=collection_name,
        limit=20,
        with_payload=True
    )
    
    id_types = {}
    payload_product_ids = []
    
    for point in scroll_result[0]:
        point_id = str(point.id)
        id_type = "uuid" if "-" in point_id and len(point_id) > 30 else "other"
        id_types[id_type] = id_types.get(id_type, 0) + 1
        
        if point.payload and 'product_id' in point.payload:
            payload_product_ids.append(point.payload['product_id'])
    
    print(f"Qdrant ID types: {id_types}")
    print(f"Sample payload product_ids: {payload_product_ids[:5]}")
    
    # Final analysis
    print("\n🎯 ANALYSIS:")
    if payload_matches > 0:
        print("✅ Neo4j IDs ARE found in Qdrant payloads")
        print("❗ The issue is that Qdrant point IDs ≠ Neo4j product IDs")
        print("✅ Correct matching should use payload.product_id field")
    else:
        print("❌ No matches found - investigating further...")
    
    # Clean up connections
    neo4j_driver.close()

if __name__ == "__main__":
    investigate_id_formats()