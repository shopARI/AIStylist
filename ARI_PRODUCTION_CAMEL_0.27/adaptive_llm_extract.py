#!/usr/bin/env python3
"""
Adaptive LLM-Based Mass Data Extraction
Handles token limits with dynamic batch size adjustment
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

async def adaptive_llm_mass_extract():
    """Adaptive LLM extraction with dynamic batch sizing"""
    print(" ADAPTIVE LLM MASS DATA EXTRACTION")
    print("=" * 60)
    print(" Features:")
    print("   • Adaptive batch sizing for token limits")
    print("   • Cursor-based pagination")
    print("   • Automatic error recovery")
    print("   • Progress continuation")
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
        
        # Create optimized index (ignore errors)
        try:
            await neo4j_service.query("CREATE INDEX product_id_title_opt FOR (p:Product) ON (p.id, p.title)")
        except:
            pass
        
        # Adaptive parameters
        initial_batch_size = 20  # Start smaller to avoid token limits
        min_batch_size = 5       # Minimum batch size
        max_batch_size = 25      # Maximum batch size
        current_batch_size = initial_batch_size
        
        processed = 0
        updated = 0
        batch_num = 1
        token_limit_errors = 0
        successful_batches = 0
        
        # Find where we left off
        print(" Finding continuation point...")
        try:
            progress_query = """
            MATCH (p:Product)
            WHERE p.extracted_colors IS NOT NULL
            RETURN p.id as id
            ORDER BY p.id DESC
            LIMIT 1
            """
            progress_result = await neo4j_service.query(progress_query)
            last_processed_id = progress_result[0]['id'] if progress_result else ""
            
            if last_processed_id:
                count_query = """
                MATCH (p:Product)
                WHERE p.extracted_colors IS NOT NULL
                RETURN count(p) as processed_count
                """
                count_result = await neo4j_service.query(count_query)
                processed = count_result[0]['processed_count'] if count_result else 0
                updated = processed
                print(f"Resuming from: {last_processed_id[:8]}... ({processed:,} already processed)")
            else:
                print("Starting fresh extraction")
        except:
            last_processed_id = ""
            print("Starting fresh extraction (continuation check failed)")
        
        start_time = time.time()
        
        while True:
            print(f"\nBatch {batch_num} (size: {current_batch_size}, cursor: {last_processed_id[:8]}...)")
            
            # Cursor-based batch query
            if last_processed_id:
                batch_query = """
                MATCH (p:Product)
                WHERE p.id > $cursor AND p.title IS NOT NULL AND p.title <> ''
                AND p.extracted_colors IS NULL
                RETURN p.id as id, p.title as title, p.description as description
                ORDER BY p.id ASC
                LIMIT $batch_size
                """
                params = {'cursor': last_processed_id, 'batch_size': current_batch_size}
            else:
                batch_query = """
                MATCH (p:Product)
                WHERE p.title IS NOT NULL AND p.title <> ''
                AND p.extracted_colors IS NULL
                RETURN p.id as id, p.title as title, p.description as description
                ORDER BY p.id ASC
                LIMIT $batch_size
                """
                params = {'batch_size': current_batch_size}
            
            batch_result = await neo4j_service.query(batch_query, params)
            
            if not batch_result:
                print(" No more products to process")
                break
            
            # Update cursor for next batch
            last_processed_id = batch_result[-1]['id']
            
            # Process batch with LLM
            try:
                extractions = await extractor.batch_extract(batch_result)
                
                # Update database
                batch_updated = 0
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
                        
                        batch_updated += 1
                        
                    except Exception as e:
                        print(f"WARNING: Update error for product {extraction['id']}: {e}")
                        continue
                
                # Success - increase batch size gradually
                successful_batches += 1
                updated += batch_updated
                
                if successful_batches >= 3 and current_batch_size < max_batch_size:
                    current_batch_size = min(current_batch_size + 2, max_batch_size)
                    successful_batches = 0
                    print(f"Increased batch size to {current_batch_size}")
                        
            except Exception as e:
                error_msg = str(e).lower()
                if "length limit was reached" in error_msg or "token" in error_msg:
                    # Token limit hit - reduce batch size
                    token_limit_errors += 1
                    if current_batch_size > min_batch_size:
                        current_batch_size = max(current_batch_size - 3, min_batch_size)
                        print(f"Token limit hit - reduced batch size to {current_batch_size}")
                        successful_batches = 0
                        continue  # Retry with smaller batch
                    else:
                        print(f"WARNING: Token limit at minimum batch size: {e}")
                        # Skip this batch and continue
                else:
                    print(f"WARNING: Batch processing error: {e}")
            
            processed += len(batch_result)
            batch_num += 1
            
            # Progress update every 5 batches
            if batch_num % 5 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = max(0, 4600000 - processed)
                eta = remaining / rate / 3600 if rate > 0 else 0
                
                print(f"Progress: {processed:,} processed, {updated:,} updated")
                print(f"Timer Rate: {rate:.1f} products/sec, ETA: {eta:.1f} hours")
                print(f" Batch size: {current_batch_size}, Token errors: {token_limit_errors}")
            
            # Rate limiting
            await asyncio.sleep(0.5)  # Reduced delay for better throughput
        
        # Final statistics
        elapsed = time.time() - start_time
        total_cost = updated * 0.015
        
        print(f"\n ADAPTIVE LLM EXTRACTION COMPLETE!")
        print(f"Total processed: {processed:,}")
        print(f"Total updated: {updated:,}")
        print(f"Timer Time elapsed: {elapsed/3600:.1f} hours")
        print(f"Total cost: ${total_cost:.2f}")
        print(f" Final batch size: {current_batch_size}")
        print(f"WARNING: Token limit errors: {token_limit_errors}")
        
        # Create relationships efficiently
        print(f"\nCreating optimized relationships...")
        
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
        
        for i, rel_query in enumerate(rel_queries):
            try:
                print(f"   Creating relationship batch {i+1}/4...")
                await neo4j_service.query(rel_query)
                print(f"    Relationship batch {i+1} created")
            except Exception as e:
                print(f"   WARNING: Relationship batch {i+1} error: {e}")
        
        await neo4j_service.close()
        print(f" Adaptive LLM extraction complete! Enhanced knowledge graph ready!")
        
    except Exception as e:
        print(f" Adaptive extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(adaptive_llm_mass_extract())