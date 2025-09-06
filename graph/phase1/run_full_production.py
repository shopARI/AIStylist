#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Full Production Batched Extraction - 6.4M Products
Uses the reliable simple extractor in batches
"""

import json
import time
import os
from datetime import datetime
from neo4j import GraphDatabase

def connect_to_database():
    """Connect to production Neo4j database"""
    neo4j_url = "bolt://0.0.0.0:17687"
    neo4j_user = "neo4j"
    neo4j_password = self.db_config.neo4j_password
    return GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))

def extract_metadata_batch(products):
    """Extract metadata from a batch of products"""
    from run_phase1 import extract_colors_simple, extract_brands_simple, extract_styles_simple
    
    results = []
    for product in products:
        product_id = product.get('id', 'unknown')
        title = product.get('title', '')
        description = product.get('description', '')
        price = product.get('price', 0)
        
        # Combine text for analysis
        full_text = f"{title} {description}"
        
        # Extract metadata
        colors = extract_colors_simple(full_text)
        brands = extract_brands_simple(full_text)
        styles = extract_styles_simple(full_text)
        
        result = {
            'product_id': product_id,
            'title': title,
            'price': price,
            'extracted_metadata': {
                'colors': colors,
                'brands': brands,
                'styles': styles
            },
            'confidence_scores': {
                'colors': 0.8 if colors else 0.0,
                'brands': 0.9 if brands else 0.0,
                'styles': 0.7 if styles else 0.0
            }
        }
        results.append(result)
    
    return results

def run_full_extraction():
    """Run full production extraction with batching"""
    
    print("="*80)
    print("🚀 PHASE 1: FULL PRODUCTION EXTRACTION")
    print("="*80)
    print("📊 Target: 6,416,804 products")
    print("📦 Batch size: 5,000 products")
    print("🔒 Read-only mode - NO database changes")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()
    
    # Setup
    batch_size = 5000
    start_time = time.time()
    
    # Create output directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = f"full_extraction_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Statistics tracking
    total_processed = 0
    total_with_colors = 0
    total_with_brands = 0  
    total_with_styles = 0
    batch_count = 0
    
    driver = None
    try:
        # Connect to database
        print("🔌 Connecting to production database...")
        driver = connect_to_database()
        
        with driver.session() as session:
            # Get total count
            total_result = session.run("MATCH (p:Product) RETURN count(p) as total")
            total_count = total_result.single()['total']
            print(f"✅ Connected! Total products: {total_count:,}")
            
            # Process in batches
            offset = 0
            while offset < total_count:
                batch_start_time = time.time()
                
                # Fetch batch
                print(f"📦 Batch {batch_count + 1}: Fetching products {offset:,} to {offset + batch_size:,}")
                
                result = session.run(f"""
                MATCH (p:Product)
                RETURN p.id as id, p.title as title, p.description as description, p.price as price
                SKIP {offset}
                LIMIT {batch_size}
                """)
                
                products = []
                for record in result:
                    products.append({
                        'id': record['id'],
                        'title': record['title'] or '',
                        'description': record['description'] or '',
                        'price': record['price'] or 0
                    })
                
                if not products:
                    print("✅ No more products to process")
                    break
                
                # Process batch
                print(f"🧠 Processing {len(products):,} products...")
                batch_results = extract_metadata_batch(products)
                
                # Update statistics
                batch_colors = sum(1 for r in batch_results if r['extracted_metadata']['colors'])
                batch_brands = sum(1 for r in batch_results if r['extracted_metadata']['brands'])
                batch_styles = sum(1 for r in batch_results if r['extracted_metadata']['styles'])
                
                total_processed += len(products)
                total_with_colors += batch_colors
                total_with_brands += batch_brands
                total_with_styles += batch_styles
                
                # Save batch
                batch_file = os.path.join(output_dir, f"batch_{batch_count:04d}.json")
                with open(batch_file, 'w', encoding='utf-8') as f:
                    json.dump(batch_results, f, indent=2, ensure_ascii=False)
                
                # Progress report
                batch_time = time.time() - batch_start_time
                total_time = time.time() - start_time
                progress = (offset + len(products)) / total_count * 100
                rate = total_processed / total_time if total_time > 0 else 0
                eta_seconds = (total_count - total_processed) / rate if rate > 0 else 0
                eta_hours = eta_seconds / 3600
                
                print(f"✅ Batch {batch_count + 1} completed in {batch_time:.1f}s")
                print(f"📊 Progress: {progress:.1f}% ({total_processed:,}/{total_count:,})")
                print(f"⚡ Rate: {rate:.0f} products/second")
                print(f"🕐 ETA: {eta_hours:.1f} hours")
                print(f"📈 Colors: {total_with_colors:,} ({total_with_colors/total_processed*100:.1f}%)")
                print(f"📈 Brands: {total_with_brands:,} ({total_with_brands/total_processed*100:.1f}%)")
                print(f"📈 Styles: {total_with_styles:,} ({total_with_styles/total_processed*100:.1f}%)")
                print("-" * 60)
                
                batch_count += 1
                offset += batch_size
                
                # Memory checkpoint every 20 batches (100K products)
                if batch_count % 20 == 0:
                    checkpoint = {
                        'timestamp': datetime.now().isoformat(),
                        'batch_count': batch_count,
                        'total_processed': total_processed,
                        'progress_percent': progress,
                        'statistics': {
                            'colors_found': total_with_colors,
                            'brands_found': total_with_brands,
                            'styles_found': total_with_styles
                        }
                    }
                    
                    checkpoint_file = os.path.join(output_dir, f"checkpoint_{batch_count}.json")
                    with open(checkpoint_file, 'w') as f:
                        json.dump(checkpoint, f, indent=2)
                    
                    print(f"💾 Checkpoint saved: {checkpoint_file}")
                    print()
        
        # Final summary
        total_time = time.time() - start_time
        
        final_summary = {
            'extraction_info': {
                'start_time': datetime.fromtimestamp(start_time).isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_time_seconds': total_time,
                'total_time_hours': total_time / 3600,
                'total_database_products': total_count,
                'processed_products': total_processed,
                'batches_completed': batch_count,
                'batch_size': batch_size
            },
            'final_statistics': {
                'colors_found': total_with_colors,
                'brands_found': total_with_brands,
                'styles_found': total_with_styles,
                'success_rates': {
                    'colors': f"{total_with_colors/total_processed*100:.1f}%",
                    'brands': f"{total_with_brands/total_processed*100:.1f}%", 
                    'styles': f"{total_with_styles/total_processed*100:.1f}%"
                },
                'processing_rate': f"{total_processed/total_time:.0f} products/second"
            }
        }
        
        summary_file = os.path.join(output_dir, "FINAL_SUMMARY.json")
        with open(summary_file, 'w') as f:
            json.dump(final_summary, f, indent=2)
        
        print("="*80)
        print("🎉 FULL EXTRACTION COMPLETE!")
        print("="*80)
        print(f"✅ Processed: {total_processed:,} products")
        print(f"✅ Time taken: {total_time/3600:.1f} hours")
        print(f"✅ Average rate: {total_processed/total_time:.0f} products/second")
        print(f"✅ Colors extracted: {total_with_colors:,} ({total_with_colors/total_processed*100:.1f}%)")
        print(f"✅ Brands extracted: {total_with_brands:,} ({total_with_brands/total_processed*100:.1f}%)")
        print(f"✅ Styles extracted: {total_with_styles:,} ({total_with_styles/total_processed*100:.1f}%)")
        print(f"✅ Results saved to: {output_dir}/")
        print(f"✅ Summary: {summary_file}")
        print("✅ Ready for Phase 2 (graph reconstruction)")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    success = run_full_extraction()
    if not success:
        exit(1)