#!/usr/bin/env python3
"""
Scripts to handle your embedding strategy
"""

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
    auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), 
          os.getenv('NEO4J_PASSWORD', 'shopari1234'))
)

def option_1_embed_remaining_classified():
    """
    OPTION 1: Embed the remaining 251K classified fashion products
    Cost: ~$1.51
    """
    print("OPTION 1: Embedding remaining 251K classified fashion products")
    print("This will complete embeddings for all properly classified products")
    print("Estimated cost: $1.51")
    
    # Just run your existing pipeline - it should pick up the 251K products
    print("\nRun: python fashion_embeddings_pipeline.py")
    

def option_2_prepare_unclassified_for_embedding():
    """
    OPTION 2: Prepare the 7.1M unclassified products with :FashionProduct label
    This assumes they're mostly fashion (since someone labeled them)
    Cost: ~$42 for embeddings
    """
    print("OPTION 2: Preparing 7.1M products with :FashionProduct label")
    
    with driver.session() as session:
        # First, let's sample what these products look like
        print("\nSampling unclassified :FashionProduct items...")
        
        result = session.run("""
            MATCH (p:Product:FashionProduct)
            WHERE p.is_fashion IS NULL
            RETURN p.title, p.price
            LIMIT 10
        """)
        
        print("\nSample products:")
        for r in result:
            print(f"  - {r['p.title'][:80]}... (${r['p.price']:.2f})")
        
        # Count by brand to understand better
        brand_result = session.run("""
            MATCH (p:Product:FashionProduct)-[:BY_BRAND]->(b:Brand)
            WHERE p.is_fashion IS NULL
            RETURN b.name as brand, count(p) as count
            ORDER BY count DESC
            LIMIT 20
        """)
        
        print("\nTop brands in unclassified products:")
        for r in brand_result:
            print(f"  {r['brand']}: {r['count']:,} products")
        
        # If you want to proceed, mark them as fashion
        proceed = input("\nMark these as fashion products? (y/n): ")
        if proceed.lower() == 'y':
            print("\nMarking products as fashion...")
            
            result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.is_fashion IS NULL
                  AND p.title IS NOT NULL
                SET p.is_fashion = true,
                    p.fashion_confidence = 0.95,  // High confidence since they have label
                    p.ready_for_embedding = true,
                    p.classification_source = 'bulk_label_based'
                RETURN count(p) as updated
            """)
            
            count = result.single()['updated']
            print(f"✅ Marked {count:,} products as fashion and ready for embedding")
            print(f"Estimated embedding cost: ${count * 0.000006:.2f}")


def option_3_remove_fashion_label_from_unclassified():
    """
    OPTION 3: Remove :FashionProduct label from unclassified products
    This cleans up the mislabeling
    """
    print("OPTION 3: Removing :FashionProduct label from unclassified products")
    
    with driver.session() as session:
        # First count
        count_result = session.run("""
            MATCH (p:Product:FashionProduct)
            WHERE p.is_fashion IS NULL
            RETURN count(p) as count
        """).single()
        
        print(f"Found {count_result['count']:,} products with label but no classification")
        
        proceed = input("\nRemove :FashionProduct label from these? (y/n): ")
        if proceed.lower() == 'y':
            print("\nRemoving labels...")
            
            # Remove in batches
            batch_size = 10000
            total_removed = 0
            
            while True:
                result = session.run("""
                    MATCH (p:Product:FashionProduct)
                    WHERE p.is_fashion IS NULL
                    WITH p LIMIT $batch_size
                    REMOVE p:FashionProduct
                    RETURN count(p) as removed
                """, batch_size=batch_size)
                
                removed = result.single()['removed']
                total_removed += removed
                
                if removed == 0:
                    break
                    
                print(f"  Removed label from {total_removed:,} products...")
            
            print(f"✅ Cleaned up {total_removed:,} products")


def analyze_duplicates():
    """
    Analyze the duplicate title situation
    """
    print("ANALYZING DUPLICATE TITLES")
    print("-" * 50)
    
    with driver.session() as session:
        # Find most duplicated titles
        result = session.run("""
            MATCH (p:Product)
            WHERE p.title IS NOT NULL
            WITH p.title as title, count(p) as count, collect(p.id)[..5] as sample_ids
            WHERE count > 10
            RETURN title, count, sample_ids
            ORDER BY count DESC
            LIMIT 10
        """)
        
        print("\nMost duplicated titles:")
        for r in result:
            print(f"\n'{r['title'][:60]}...'")
            print(f"  Appears {r['count']:,} times")
            print(f"  Sample IDs: {', '.join(r['sample_ids'][:3])}")
        
        # Check if duplicates are from same brand
        brand_result = session.run("""
            MATCH (p:Product)-[:BY_BRAND]->(b:Brand)
            WHERE p.title IS NOT NULL
            WITH p.title as title, count(DISTINCT b.name) as brand_count, count(p) as product_count
            WHERE product_count > 10
            RETURN avg(brand_count) as avg_brands_per_title
        """).single()
        
        print(f"\nAverage brands per duplicated title: {brand_result['avg_brands_per_title']:.1f}")
        

def get_recommendation():
    """
    Print clear recommendations
    """
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    print("\n1️⃣  IMMEDIATE ACTION (Today):")
    print("   Complete embeddings for 251K classified products")
    print("   → Run your existing pipeline")
    print("   → Cost: $1.51")
    print("   → Time: ~2-3 hours")
    
    print("\n2️⃣  NEXT STEP (This week):")
    print("   Decide what to do with 7.1M products with :FashionProduct label")
    print("   Option A: Trust the label and mark as fashion (run option_2)")
    print("   Option B: Remove the label and classify properly (run option_3)")
    print("   Option C: Sample and manually review before deciding")
    
    print("\n3️⃣  HANDLE DUPLICATES (Later):")
    print("   4.5M products share titles (mostly variants)")
    print("   Consider: Embed only one per title group")
    print("   Or: Create variant-aware embeddings")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python embedding_strategy.py [option]")
        print("\nOptions:")
        print("  1 - Embed remaining 251K classified products")
        print("  2 - Prepare 7.1M unclassified with :FashionProduct label")
        print("  3 - Remove :FashionProduct label from unclassified")
        print("  duplicates - Analyze duplicate titles")
        print("  recommend - Get recommendations")
        sys.exit(1)
    
    option = sys.argv[1]
    
    if option == "1":
        option_1_embed_remaining_classified()
    elif option == "2":
        option_2_prepare_unclassified_for_embedding()
    elif option == "3":
        option_3_remove_fashion_label_from_unclassified()
    elif option == "duplicates":
        analyze_duplicates()
    elif option == "recommend":
        get_recommendation()
    else:
        print(f"Unknown option: {option}")