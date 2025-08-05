#!/usr/bin/env python3
"""
Batch update 7.1M products to mark them as fashion
Processes in small batches to avoid memory errors
"""

import os
import time
from neo4j import GraphDatabase
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
    auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), 
          os.getenv('NEO4J_PASSWORD', 'shopari1234'))
)

def batch_mark_fashion_products(batch_size=5000):
    """Mark products as fashion in batches"""
    
    print(f"\n✅ Marking products as fashion in batches of {batch_size:,}...")
    
    with driver.session() as session:
        # First, get total count
        count_result = session.run("""
            MATCH (p:Product:FashionProduct)
            WHERE p.is_fashion IS NULL
              AND p.title IS NOT NULL
            RETURN count(p) as total
        """).single()
        
        total_count = count_result['total']
        print(f"Total products to update: {total_count:,}")
        
        # Process in batches with progress bar
        updated_total = 0
        
        with tqdm(total=total_count, desc="Updating products") as pbar:
            while updated_total < total_count:
                # Update batch
                result = session.run("""
                    MATCH (p:Product:FashionProduct)
                    WHERE p.is_fashion IS NULL
                      AND p.title IS NOT NULL
                    WITH p LIMIT $batch_size
                    SET p.is_fashion = true,
                        p.fashion_confidence = 0.95,
                        p.ready_for_embedding = true,
                        p.classification_source = 'keyword_based',
                        p.classified_at = datetime()
                    RETURN count(p) as updated
                """, batch_size=batch_size)
                
                batch_updated = result.single()['updated']
                updated_total += batch_updated
                pbar.update(batch_updated)
                
                # If no more updates, we're done
                if batch_updated == 0:
                    break
                
                # Small delay to not overwhelm the database
                if updated_total % 100000 == 0:
                    time.sleep(0.5)
        
        print(f"\n✅ Successfully marked {updated_total:,} products as fashion!")
        
        # Verify the update
        print("\nVerifying update...")
        verify_result = session.run("""
            MATCH (p:Product:FashionProduct)
            WHERE p.is_fashion = true
              AND p.classification_source = 'keyword_based'
            RETURN count(p) as count
        """).single()
        
        print(f"Products marked as fashion (keyword-based): {verify_result['count']:,}")
        
        # Check embeddings readiness
        ready_result = session.run("""
            MATCH (p:Product)
            WHERE p.is_fashion = true
              AND p.ready_for_embedding = true
              AND p.embedding_id IS NULL
            RETURN count(p) as count
        """).single()
        
        print(f"\nTotal products ready for embedding: {ready_result['count']:,}")
        print(f"Estimated embedding cost: ${ready_result['count'] * 0.000006:.2f}")

if __name__ == "__main__":
    print("BATCH UPDATE: Marking 7.1M products as fashion")
    print("="*60)
    
    # Confirm the brands look good
    print("\nYou saw these top brands:")
    print("- Hot Topic (711K products)")
    print("- BoxLunch (426K products)")  
    print("- Gildan (185K products)")
    print("- Puma, Adidas, Under Armour...")
    print("\nThese are definitely fashion brands! ✅")
    
    confirm = input("\nProceed with batch update? (y/n): ")
    if confirm.lower() == 'y':
        start_time = time.time()
        
        # You can adjust batch size if needed
        # Smaller = safer but slower, Larger = faster but uses more memory
        batch_mark_fashion_products(batch_size=5000)
        
        elapsed = time.time() - start_time
        print(f"\nCompleted in {elapsed/60:.1f} minutes")
        
        print("\n🎯 Next Steps:")
        print("1. Run: python fashion_embeddings_pipeline.py")
        print("   This will embed the remaining 251K classified products")
        print("2. Run it again to embed the 7.1M newly marked products")
    else:
        print("Update cancelled")