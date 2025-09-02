#!/usr/bin/env python3
"""
UUID Consistency Verification Script
Verifies that both Neo4j and Qdrant are using UUID format for product IDs
Run this after migrating to the new 6M node graph with UUIDs
"""

import asyncio
import logging
import uuid
import sys
import os
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.user.knowledge_graph import UserKnowledgeGraphService
from services.product.retriever import ProductRetrieverService
from config.settings import Settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_neo4j_uuids(neo4j: UserKnowledgeGraphService, sample_size: int = 100) -> tuple[int, int]:
    """
    Verify Neo4j product IDs are UUIDs.
    Returns: (valid_uuid_count, total_count)
    """
    logger.info(f"Checking {sample_size} Neo4j products for UUID format...")
    
    query = """
    MATCH (p:Product) 
    WHERE p.id IS NOT NULL
    RETURN p.id as id, p.title as title
    LIMIT $limit
    """
    
    try:
        results = await neo4j.query(query, {"limit": sample_size}, timeout=30.0)
        valid_uuids = 0
        total_count = len(results)
        
        for record in results:
            product_id = record.get("id")
            if product_id:
                try:
                    uuid.UUID(str(product_id))
                    valid_uuids += 1
                except ValueError:
                    logger.warning(f"Non-UUID ID found in Neo4j: {product_id}")
        
        logger.info(f"Neo4j: {valid_uuids}/{total_count} products have valid UUID IDs")
        return valid_uuids, total_count
        
    except Exception as e:
        logger.error(f"Error checking Neo4j UUIDs: {e}")
        return 0, 0

async def verify_qdrant_uuids(qdrant: ProductRetrieverService, sample_size: int = 100) -> tuple[int, int]:
    """
    Verify Qdrant product IDs are UUIDs.
    Returns: (valid_uuid_count, total_count)
    """
    logger.info(f"Checking {sample_size} Qdrant products for UUID format...")
    
    try:
        # Get sample products from Qdrant
        results = await qdrant.search_by_natural_language(
            query="fashion product",
            limit=sample_size,
            filters=None
        )
        
        valid_uuids = 0
        total_count = len(results)
        
        for product in results:
            if isinstance(product, dict):
                product_id = product.get("id")
                if product_id:
                    try:
                        uuid.UUID(str(product_id))
                        valid_uuids += 1
                    except ValueError:
                        logger.warning(f"Non-UUID ID found in Qdrant: {product_id}")
        
        logger.info(f"Qdrant: {valid_uuids}/{total_count} products have valid UUID IDs")
        return valid_uuids, total_count
        
    except Exception as e:
        logger.error(f"Error checking Qdrant UUIDs: {e}")
        return 0, 0

async def main():
    """Main verification function."""
    logger.info("🔍 Starting UUID consistency verification...")
    
    # Load settings
    settings = Settings()
    
    # Initialize services
    logger.info("Initializing services...")
    neo4j = UserKnowledgeGraphService(
        url=settings.neo4j.url,
        username=settings.neo4j.username,
        password=settings.neo4j.password
    )
    await neo4j.initialize()
    
    qdrant = ProductRetrieverService(
        collection_name=settings.qdrant.collection_name
    )
    await qdrant.initialize()
    
    try:
        # Verify both systems
        neo4j_valid, neo4j_total = await verify_neo4j_uuids(neo4j)
        qdrant_valid, qdrant_total = await verify_qdrant_uuids(qdrant)
        
        # Summary
        logger.info("=" * 60)
        logger.info("UUID CONSISTENCY VERIFICATION RESULTS:")
        logger.info("=" * 60)
        logger.info(f"Neo4j:  {neo4j_valid}/{neo4j_total} products with valid UUIDs ({neo4j_valid/neo4j_total*100 if neo4j_total > 0 else 0:.1f}%)")
        logger.info(f"Qdrant: {qdrant_valid}/{qdrant_total} products with valid UUIDs ({qdrant_valid/qdrant_total*100 if qdrant_total > 0 else 0:.1f}%)")
        
        if neo4j_valid == neo4j_total and qdrant_valid == qdrant_total:
            logger.info("✅ SUCCESS: All sampled products have UUID format IDs!")
        else:
            logger.warning("⚠️  WARNING: Some products have non-UUID IDs - migration may be incomplete")
            
        if neo4j_total == 0 or qdrant_total == 0:
            logger.error("❌ ERROR: No products found in one or both systems")
            
    finally:
        # Cleanup
        await neo4j.close()
        await qdrant.close()
        
    logger.info("Verification complete.")

if __name__ == "__main__":
    asyncio.run(main())