#!/usr/bin/env python3
"""
Simple Phase 1 Runner - Read-Only Database Extraction
No dependencies issues, just works!
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
import json
from datetime import datetime
from neo4j import GraphDatabase

def connect_to_database():
    """Connect to production Neo4j database"""
    neo4j_url = "bolt://0.0.0.0:17687"
    neo4j_user = "neo4j"
    neo4j_password = "6D%q@jbYmstkK2i3oW5z6B6outew9m93"
    
    return GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))

def extract_colors_simple(text):
    """Simple color extraction using keyword matching"""
    colors = []
    color_map = {
        'red': ['red', 'crimson', 'burgundy', 'maroon', 'cherry', 'wine'],
        'blue': ['blue', 'navy', 'azure', 'cobalt', 'royal', 'denim'],
        'green': ['green', 'emerald', 'olive', 'lime', 'forest', 'mint'],
        'yellow': ['yellow', 'gold', 'amber', 'lemon', 'mustard'],
        'orange': ['orange', 'coral', 'peach', 'tangerine', 'rust'],
        'purple': ['purple', 'violet', 'lavender', 'plum', 'magenta'],
        'pink': ['pink', 'rose', 'blush', 'fuchsia', 'salmon'],
        'brown': ['brown', 'tan', 'beige', 'camel', 'chocolate'],
        'black': ['black', 'charcoal', 'ebony', 'jet', 'onyx'],
        'white': ['white', 'ivory', 'cream', 'pearl', 'snow'],
        'gray': ['gray', 'grey', 'silver', 'platinum', 'ash'],
        'gold': ['gold', 'golden', 'brass', 'bronze'],
        'silver': ['silver', 'metallic', 'chrome', 'steel']
    }
    
    text_lower = text.lower()
    for base_color, variations in color_map.items():
        if any(var in text_lower for var in variations):
            if base_color not in colors:
                colors.append(base_color)
    
    return colors

def extract_brands_simple(text):
    """Simple brand extraction"""
    brands = []
    known_brands = [
        'nike', 'adidas', 'puma', 'gucci', 'prada', 'theory', 'ralph lauren',
        'calvin klein', 'tommy hilfiger', 'hugo boss', 'lacoste', 'levis',
        'gap', 'zara', 'h&m', 'uniqlo', 'north face', 'patagonia', 'columbia',
        'lululemon', 'champion', 'fila', 'new balance', 'asics', 'vans', 'converse'
    ]
    
    text_lower = text.lower()
    for brand in known_brands:
        if brand in text_lower:
            brands.append(brand.title())
    
    # Also try to extract capitalized words that might be brands
    words = text.split()
    for word in words[:5]:  # Check first 5 words only
        if word[0].isupper() and len(word) > 2 and word not in ['The', 'Collection', 'Women', 'Men', 'Size']:
            if word.lower() not in [b.lower() for b in brands]:
                brands.append(word)
    
    return brands[:2]  # Limit to 2 brands

def extract_styles_simple(text):
    """Simple style extraction"""
    styles = []
    style_keywords = {
        'casual': ['casual', 'everyday', 'relaxed', 'comfortable', 't-shirt', 'jeans'],
        'formal': ['formal', 'dress', 'elegant', 'sophisticated', 'suit', 'blazer'],
        'athletic': ['athletic', 'sport', 'gym', 'workout', 'running', 'sneaker'],
        'business': ['business', 'professional', 'office', 'work'],
        'trendy': ['trendy', 'fashion', 'modern', 'contemporary', 'stylish'],
        'vintage': ['vintage', 'retro', 'classic', 'timeless', 'traditional'],
        'bohemian': ['bohemian', 'boho', 'flowy', 'artistic', 'free'],
        'minimalist': ['minimalist', 'simple', 'clean', 'basic', 'sleek']
    }
    
    text_lower = text.lower()
    for style, keywords in style_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            if style not in styles:
                styles.append(style)
    
    return styles[:3]  # Limit to 3 styles

def process_products(products):
    """Process products and extract metadata"""
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

def run_extraction(sample_size=1000):
    """Run the complete extraction process"""
    
    print("=" * 60)
    print("🚀 PHASE 1: PRODUCTION DATA EXTRACTION")
    print("=" * 60)
    print(f"📊 Processing {sample_size:,} products")
    print(f"🔒 Read-only mode - NO database changes")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    driver = None
    try:
        # Connect to database
        print("🔌 Connecting to production database...")
        driver = connect_to_database()
        
        with driver.session() as session:
            # Get total count
            total_result = session.run("MATCH (p:Product) RETURN count(p) as total")
            total_count = total_result.single()['total']
            print(f"✅ Connected! Total products in database: {total_count:,}")
            
            # Get sample products
            print(f"📦 Fetching {sample_size:,} sample products...")
            result = session.run(f"""
            MATCH (p:Product)
            RETURN p.id as id, p.title as title, p.description as description, p.price as price
            LIMIT {sample_size}
            """)
            
            products = []
            for record in result:
                products.append({
                    'id': record['id'],
                    'title': record['title'] or '',
                    'description': record['description'] or '',
                    'price': record['price'] or 0
                })
            
            print(f"✅ Retrieved {len(products):,} products")
            
            # Process products
            print("🧠 Extracting metadata (colors, brands, styles)...")
            results = process_products(products)
            
            # Calculate statistics
            total_with_colors = sum(1 for r in results if r['extracted_metadata']['colors'])
            total_with_brands = sum(1 for r in results if r['extracted_metadata']['brands'])
            total_with_styles = sum(1 for r in results if r['extracted_metadata']['styles'])
            
            print()
            print("=" * 60)
            print("📊 EXTRACTION RESULTS")
            print("=" * 60)
            print(f"Products processed: {len(results):,}")
            print(f"Colors extracted: {total_with_colors:,} ({total_with_colors/len(results)*100:.1f}%)")
            print(f"Brands extracted: {total_with_brands:,} ({total_with_brands/len(results)*100:.1f}%)")
            print(f"Styles extracted: {total_with_styles:,} ({total_with_styles/len(results)*100:.1f}%)")
            
            # Show sample results
            print()
            print("🔍 SAMPLE RESULTS:")
            print("-" * 40)
            for i, result in enumerate(results[:5]):
                meta = result['extracted_metadata']
                print(f"{i+1}. {result['title'][:50]}...")
                print(f"   Colors: {meta['colors']}")
                print(f"   Brands: {meta['brands']}")
                print(f"   Styles: {meta['styles']}")
                print()
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"phase1_extraction_results_{timestamp}.json"
            
            print(f"💾 Saving results to {output_file}...")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'extraction_info': {
                        'timestamp': timestamp,
                        'sample_size': sample_size,
                        'total_database_products': total_count,
                        'processed_products': len(results)
                    },
                    'statistics': {
                        'colors_found': total_with_colors,
                        'brands_found': total_with_brands,
                        'styles_found': total_with_styles,
                        'success_rates': {
                            'colors': f"{total_with_colors/len(results)*100:.1f}%",
                            'brands': f"{total_with_brands/len(results)*100:.1f}%", 
                            'styles': f"{total_with_styles/len(results)*100:.1f}%"
                        }
                    },
                    'results': results
                }, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Results saved!")
            print()
            print("=" * 60)
            print("🎉 PHASE 1 EXTRACTION COMPLETE!")
            print("=" * 60)
            print("✅ All data extracted successfully")
            print("✅ No database modifications made")
            print("✅ Ready for Phase 2 (graph reconstruction)")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
        
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Phase 1 Data Extraction')
    parser.add_argument('--size', type=int, default=1000, help='Number of products to process')
    
    args = parser.parse_args()
    
    success = run_extraction(args.size)
    
    if not success:
        sys.exit(1)