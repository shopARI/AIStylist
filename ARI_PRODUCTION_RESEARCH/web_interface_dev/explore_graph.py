#!/usr/bin/env python3
"""
Neo4j Graph Explorer
Connect to the new 6M node graph and analyze structure
"""

import asyncio
import logging
import os
import json
from services.user.knowledge_graph import UserKnowledgeGraphService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def explore_neo4j_schema():
    """Explore the Neo4j graph schema and sample data."""
    
    # Get credentials from .env - now pointing to new 6M UUID-based graph  
    neo4j_url = os.getenv("NEO4J_URL", "bolt://0.0.0.0:17687")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j") 
    neo4j_password = os.getenv("NEO4J_PASSWORD", "6D%q@jbYmstkK2i3oW5z6B6outew9m93")
    
    logger.info(f"Connecting to Neo4j at {neo4j_url}")
    
    # Initialize connection
    neo4j = UserKnowledgeGraphService(
        url=neo4j_url,
        username=neo4j_username,
        password=neo4j_password
    )
    
    await neo4j.initialize()
    
    try:
        print("="*80)
        print(" NEO4J GRAPH SCHEMA ANALYSIS")
        print("="*80)
        
        # 1. Get all node labels
        print("\n📋 NODE LABELS:")
        labels_query = "CALL db.labels() YIELD label RETURN label ORDER BY label"
        labels = await neo4j.query(labels_query, timeout=10.0)
        for record in labels:
            print(f"  - {record['label']}")
        
        # 2. Get all relationship types
        print("\n🔗 RELATIONSHIP TYPES:")
        rels_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType"
        rels = await neo4j.query(rels_query, timeout=10.0)
        for record in rels:
            print(f"  - {record['relationshipType']}")
            
        # 3. Get node counts
        print("\nNODE COUNTS:")
        for record in labels:
            label = record['label']
            count_query = f"MATCH (n:{label}) RETURN count(n) as count"
            try:
                result = await neo4j.query(count_query, timeout=15.0)
                count = result[0]['count'] if result else 0
                print(f"  {label}: {count:,} nodes")
            except Exception as e:
                print(f"  {label}: Error getting count - {e}")
        
        # 4. Sample Product nodes (most important)
        print("\n👕 SAMPLE PRODUCT NODES:")
        product_sample_query = """
        MATCH (p:Product) 
        RETURN p
        LIMIT 3
        """
        products = await neo4j.query(product_sample_query, timeout=10.0)
        for i, record in enumerate(products):
            print(f"\n  Product {i+1}:")
            product = dict(record['p'])
            for key, value in product.items():
                if isinstance(value, str) and len(str(value)) > 100:
                    print(f"    {key}: {str(value)[:100]}...")
                else:
                    print(f"    {key}: {value}")
        
        # 5. Sample other node types
        for record in labels[:5]:  # Just first 5 labels
            label = record['label']
            if label != 'Product':  # Already did products
                print(f"\n📦 SAMPLE {label.upper()} NODE:")
                sample_query = f"MATCH (n:{label}) RETURN n LIMIT 1"
                try:
                    result = await neo4j.query(sample_query, timeout=10.0)
                    if result:
                        node = dict(result[0]['n'])
                        for key, value in list(node.items())[:5]:  # First 5 properties
                            print(f"    {key}: {value}")
                except Exception as e:
                    print(f"    Error: {e}")
        
        # 6. Sample relationships
        print("\n🔗 SAMPLE RELATIONSHIPS:")
        rel_query = """
        MATCH (a)-[r]->(b)
        RETURN type(r) as rel_type, labels(a)[0] as from_label, labels(b)[0] as to_label, count(*) as count
        ORDER BY count DESC
        LIMIT 5
        """
        relationships = await neo4j.query(rel_query, timeout=20.0)
        for record in relationships:
            print(f"  {record['from_label']} -[:{record['rel_type']}]-> {record['to_label']} ({record['count']:,} relationships)")
        
        # 7. Product schema details (simplified without typename function)
        print("\n🏷️  PRODUCT SCHEMA DETAILS:")
        product_props_query = """
        MATCH (p:Product)
        WITH p
        LIMIT 100
        UNWIND keys(p) as key
        RETURN key, count(*) as frequency
        ORDER BY frequency DESC
        """
        props = await neo4j.query(product_props_query, timeout=15.0)
        print("  Property frequencies in first 100 products:")
        for record in props:
            print(f"    {record['key']}: {record['frequency']}/100")
        
        # 8. UUID validation check
        print("\n🔑 UUID VALIDATION CHECK:")
        uuid_check_query = """
        MATCH (p:Product)
        WHERE p.id IS NOT NULL
        WITH p.id as id
        LIMIT 10
        RETURN id
        """
        uuid_samples = await neo4j.query(uuid_check_query, timeout=10.0)
        print("  Sample Product IDs:")
        for record in uuid_samples:
            product_id = record['id']
            # Check if it looks like UUID
            import uuid
            try:
                uuid.UUID(str(product_id))
                print(f"     {product_id} (Valid UUID)")
            except ValueError:
                print(f"     {product_id} (Not UUID format)")
        
        print("\n" + "="*80)
        print(" Schema analysis complete!")
        print("="*80)
        
    except Exception as e:
        print(f" Error during exploration: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await neo4j.close()

if __name__ == "__main__":
    asyncio.run(explore_neo4j_schema())