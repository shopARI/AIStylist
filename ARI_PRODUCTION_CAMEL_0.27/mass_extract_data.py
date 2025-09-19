#!/usr/bin/env python3
"""
Mass Data Extraction - Add color/style/brand properties to all 6.4M products
This is the REAL Phase 1 that was never actually run
"""

import asyncio
import os
import sys
import re
import json
from dotenv import load_dotenv
from typing import List, Dict, Set
load_dotenv()

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Color extraction patterns
COLORS = {
    'black', 'white', 'red', 'blue', 'green', 'yellow', 'pink', 'purple', 
    'orange', 'brown', 'gray', 'grey', 'navy', 'beige', 'cream', 'gold', 
    'silver', 'maroon', 'olive', 'lime', 'teal', 'aqua', 'fuchsia', 'tan',
    'burgundy', 'coral', 'turquoise', 'lavender', 'indigo', 'magenta'
}

# Style extraction patterns  
STYLES = {
    'casual', 'formal', 'business', 'athletic', 'trendy', 'vintage', 
    'bohemian', 'minimalist', 'elegant', 'glamorous', 'edgy', 'preppy',
    'romantic', 'modern', 'classic', 'street', 'chic', 'sophisticated'
}

# Common brand patterns
BRAND_PATTERNS = [
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b(?=\s+(?:Women|Men|Mens|Womens|Ladies|Unisex))',
    r'\b([A-Z][A-Z\s&]+)\b(?=\s+\w)',  # All caps brands like "COACH" 
    r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s',  # Brand at start
]

def extract_colors(text: str) -> List[str]:
    """Extract colors from text."""
    text_lower = text.lower()
    found_colors = []
    
    for color in COLORS:
        if color in text_lower:
            found_colors.append(color)
    
    return list(set(found_colors))[:3]  # Max 3 colors

def extract_styles(text: str) -> List[str]:
    """Extract styles from text."""
    text_lower = text.lower()
    found_styles = []
    
    for style in STYLES:
        if style in text_lower:
            found_styles.append(style)
    
    return list(set(found_styles))[:2]  # Max 2 styles

def extract_brand(text: str) -> str:
    """Extract brand from text."""
    for pattern in BRAND_PATTERNS:
        matches = re.findall(pattern, text)
        if matches:
            brand = matches[0].strip()
            if len(brand) > 2 and len(brand) < 30:
                return brand
    
    return ""

async def mass_extract_data():
    """Extract colors, styles, brands for all products."""
    print(" MASS DATA EXTRACTION - Phase 1 (The Real One)")
    print("=" * 60)
    
    try:
        from services.user.knowledge_graph import UserKnowledgeGraphService
        
        # Initialize Neo4j connection
        neo4j_service = UserKnowledgeGraphService(
            url=os.getenv("NEO4J_URL"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD")
        )
        await neo4j_service.initialize()
        print(f" Connected to Neo4j: {os.getenv('NEO4J_DATABASE', 'default')}")
        
        # Get total count
        count_query = "MATCH (p:Product) RETURN count(p) as total"
        count_result = await neo4j_service.query(count_query)
        total_products = count_result[0]['total'] if count_result else 0
        print(f"Total products to process: {total_products:,}")
        
        # Process in batches
        batch_size = 1000
        processed = 0
        updated = 0
        batch_num = 1
        
        while processed < total_products:
            print(f"\nProcessing batch {batch_num} (products {processed + 1:,} - {min(processed + batch_size, total_products):,})")
            
            # Get batch of products
            batch_query = f"""
            MATCH (p:Product)
            WHERE p.extracted_colors IS NULL
            RETURN p.id as id, p.title as title, p.description as description
            LIMIT {batch_size}
            """
            
            batch_result = await neo4j_service.query(batch_query)
            
            if not batch_result:
                print(" No more products to process")
                break
            
            # Process each product in the batch
            batch_updates = []
            for product in batch_result:
                product_id = product['id']
                title = product.get('title', '')
                description = product.get('description', '')
                
                # Combine text
                full_text = f"{title} {description}"
                
                # Extract metadata
                colors = extract_colors(full_text)
                styles = extract_styles(full_text)
                brand = extract_brand(title)  # Focus on title for brands
                
                if colors or styles or brand:
                    batch_updates.append({
                        'id': product_id,
                        'colors': colors,
                        'styles': styles,
                        'brand': brand
                    })
            
            # Update database with batch
            if batch_updates:
                for update in batch_updates:
                    update_query = """
                    MATCH (p:Product {id: $product_id})
                    SET p.extracted_colors = $colors,
                        p.extracted_styles = $styles,
                        p.extracted_brand = $brand
                    """
                    
                    await neo4j_service.query(update_query, {
                        'product_id': update['id'],
                        'colors': update['colors'],
                        'styles': update['styles'],
                        'brand': update['brand']
                    })
                    
                    updated += 1
            
            processed += len(batch_result)
            batch_num += 1
            
            # Progress update
            if batch_num % 10 == 0:
                percentage = (processed / total_products) * 100
                print(f"Progress: {processed:,}/{total_products:,} ({percentage:.1f}%) - {updated:,} updated")
        
        print(f"\n MASS EXTRACTION COMPLETE!")
        print(f"Total processed: {processed:,}")
        print(f"Total updated: {updated:,}")
        
        # Now create relationships
        print(f"\nCreating HAS_COLOR relationships...")
        color_rel_query = """
        MATCH (p:Product), (c:Color)
        WHERE c.name IN p.extracted_colors
        MERGE (p)-[:HAS_COLOR]->(c)
        """
        await neo4j_service.query(color_rel_query)
        
        print(f"Creating HAS_STYLE relationships...")
        style_rel_query = """
        MATCH (p:Product), (s:Style)
        WHERE s.name IN p.extracted_styles
        MERGE (p)-[:HAS_STYLE]->(s)
        """
        await neo4j_service.query(style_rel_query)
        
        # Count final relationships
        final_count_query = """
        MATCH ()-[r]->()
        RETURN type(r) as relationship_type, count(r) as count
        ORDER BY count DESC
        """
        
        final_result = await neo4j_service.query(final_count_query)
        print(f"\nFINAL RELATIONSHIP COUNTS:")
        total_rels = 0
        for record in final_result:
            rel_type = record['relationship_type']
            count = record['count']
            total_rels += count
            print(f"  {rel_type}: {count:,}")
        
        print(f"  TOTAL: {total_rels:,}")
        print(f"\n Mass data extraction complete! The graph is now properly structured!")
        
    except Exception as e:
        print(f" Mass extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(mass_extract_data())