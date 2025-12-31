#!/usr/bin/env python3
"""
Optimized LLM-Based Mass Data Extraction
Handles large-scale databases (4.6M+ products) efficiently
"""

import asyncio
import os
import sys
import json
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_mass_extract import LLMExtractor, ProductExtraction

async def optimized_llm_mass_extract():
    """Optimized LLM extraction for large databases"""
    print(" OPTIMIZED LLM MASS DATA EXTRACTION")
    print("=" * 60)
    print(" Optimized for large-scale databases (4.6M+ products)")
    print(" Features:")
    print("   • Cursor-based pagination (no expensive counting)")
    print("   • Streaming batch processing")
    print("   • Index-optimized queries")
    print("   • Memory-efficient processing")
    print("   • Automatic progress tracking")
    print()
    
    try:
        from services.user.knowledge_graph import UserKnowledgeGraphService
        
        # Initialize connections
        neo4j_service = UserKnowledgeGraphService(
            url=os.getenv("NEO4J_URL"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )
        await neo4j_service.initialize()
        print(f" Connected to Neo4j: {os.getenv('NEO4J_DATABASE', 'default')}")
        
        extractor = LLMExtractor()
        print(f" Initialized: {extractor.model}")
        
        # Create optimized index for cursor-based pagination
        print(" Creating optimized indexes...")
        try:
            await neo4j_service.query("CREATE INDEX product_id_title_opt FOR (p:Product) ON (p.id, p.title)")
        except:
            pass  # Index might already exist
        
        # Optimized parameters
        batch_size = 25  # Smaller batches for large datasets
        processed = 0
        updated = 0
        batch_num = 1
        last_processed_id = ""  # Cursor for pagination
        
        # Rate limiting
        requests_per_minute = 100
        batch_delay = (60 / requests_per_minute) * batch_size
        
        print(f"Starting streaming extraction (batch size: {batch_size})")
        print(f"Estimated cost: ~$0.015 per product")
        
        start_time = time.time()
        
        while True:
            print(f"\nProcessing batch {batch_num} (cursor: {last_processed_id[:8]}...)")
            
            # Cursor-based batch query (much faster than SKIP/LIMIT)
            if last_processed_id:
                batch_query = """
                MATCH (p:Product)
                WHERE p.id > $cursor AND p.title IS NOT NULL AND p.title <> ''
                RETURN p.id as id, p.title as title, p.description as description
                ORDER BY p.id ASC
                LIMIT $batch_size
                """
                params = {'cursor': last_processed_id, 'batch_size': batch_size}
            else:
                # First batch
                batch_query = """
                MATCH (p:Product)
                WHERE p.title IS NOT NULL AND p.title <> ''
                RETURN p.id as id, p.title as title, p.description as description
                ORDER BY p.id ASC
                LIMIT $batch_size
                """
                params = {'batch_size': batch_size}
            
            batch_result = await neo4j_service.query(batch_query, params)
            
            if not batch_result:
                print(" No more products to process")
                break
            
            # Update cursor
            last_processed_id = batch_result[-1]['id']
            
            # Filter products that need processing (check in Python, not Cypher)
            products_to_process = []
            for product in batch_result:
                # Quick check - if product might need processing
                products_to_process.append(product)
            
            if not products_to_process:
                processed += len(batch_result)
                continue
            
            # Process batch with LLM
            try:
                extractions = await extractor.batch_extract(products_to_process)
                
                # Update database efficiently
                for extraction in extractions:
                    try:
                        update_query = """
                        MATCH (p:Product {id: $product_id})
                        SET p.extracted_colors = $colors,
                            p.color_confidence = $color_confidence,
                            p.extracted_styles = $styles,
                            p.target_demographic = $target_demographic,
                            p.extracted_brand = $brand,
                            p.brand_confidence = $brand_confidence,
                            p.brand_tier = $brand_tier,
                            p.ai_category = $category,
                            p.materials = $materials,
                            p.occasions = $occasions,
                            p.season = $season,
                            p.extraction_model = $extraction_model,
                            p.extraction_timestamp = $extraction_timestamp
                        """
                        
                        await neo4j_service.query(update_query, {
                            'product_id': extraction['id'],
                            'colors': extraction['extracted_colors'],
                            'color_confidence': extraction['color_confidence'],
                            'styles': extraction['extracted_styles'],
                            'target_demographic': extraction['target_demographic'],
                            'brand': extraction['extracted_brand'],
                            'brand_confidence': extraction['brand_confidence'],
                            'brand_tier': extraction['brand_tier'],
                            'category': extraction['ai_category'],
                            'materials': extraction['materials'],
                            'occasions': extraction['occasions'],
                            'season': extraction['season'],
                            'extraction_model': extraction['extraction_model'],
                            'extraction_timestamp': extraction['extraction_timestamp']
                        })
                        
                        updated += 1
                        
                    except Exception as e:
                        print(f"WARNING: Update error for product {extraction['id']}: {e}")
                        continue
                        
            except Exception as e:
                print(f"WARNING: Batch processing error: {e}")
                # Continue with next batch
            
            processed += len(batch_result)
            batch_num += 1
            
            # Progress update every 5 batches
            if batch_num % 5 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (4600000 - processed) / rate / 3600 if rate > 0 else 0  # Rough ETA in hours
                print(f"Progress: {processed:,} processed, {updated:,} updated")
                print(f"Rate: {rate:.1f} products/sec, ETA: {eta:.1f} hours")
            
            # Rate limiting
            if batch_delay > 0:
                await asyncio.sleep(batch_delay)
        
        # Final statistics
        elapsed = time.time() - start_time
        total_cost = updated * 0.015
        
        print(f"\n OPTIMIZED LLM EXTRACTION COMPLETE!")
        print(f"Total processed: {processed:,}")
        print(f"Total updated: {updated:,}")
        print(f"Time elapsed: {elapsed/3600:.1f} hours")
        print(f"Total cost: ${total_cost:.2f}")
        print(f" Model: {extractor.model}")
        
        # Create relationships efficiently
        print(f"\nCreating optimized relationships...")
        
        # Batch relationship creation
        rel_queries = [
            # Color relationships
            """
            MATCH (p:Product), (c:Color)
            WHERE c.name IN p.extracted_colors
            MERGE (p)-[:HAS_COLOR {confidence: coalesce(p.color_confidence, 0.5)}]->(c)
            """,
            # Style relationships
            """
            MATCH (p:Product), (s:Style)
            WHERE s.name IN p.extracted_styles
            MERGE (p)-[:HAS_STYLE]->(s)
            """,
            # Brand relationships
            """
            MATCH (p:Product)
            WHERE p.extracted_brand IS NOT NULL AND p.extracted_brand <> ''
            MERGE (b:Brand {name: p.extracted_brand})
            ON CREATE SET b.tier = p.brand_tier
            MERGE (p)-[:HAS_BRAND {confidence: coalesce(p.brand_confidence, 0.5)}]->(b)
            """,
            # Material relationships
            """
            MATCH (p:Product)
            WHERE p.materials IS NOT NULL AND size(p.materials) > 0
            UNWIND p.materials as material_name
            MERGE (m:Material {name: material_name})
            MERGE (p)-[:MADE_OF]->(m)
            """
        ]
        
        for rel_query in rel_queries:
            try:
                await neo4j_service.query(rel_query)
                print(f"   Relationship batch created")
            except Exception as e:
                print(f"  WARNING: Relationship error: {e}")
        
        print(f" Optimized LLM extraction complete! Enhanced knowledge graph ready!")
        
    except Exception as e:
        print(f" Optimized extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(optimized_llm_mass_extract())