#!/usr/bin/env python3
"""
Enhanced cleanup script that handles:
1. Hierarchical categories (with > separators)
2. Uncategorized products
3. Can run multiple times on the same database
"""

import os
import time
import gc
from neo4j import GraphDatabase
from datetime import datetime
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EnhancedFashionCleaner:
    def __init__(self, batch_size=5000, process_uncategorized=True):
        self.driver = GraphDatabase.driver(
            os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
            auth=(
                os.getenv('NEO4J_USERNAME', 'neo4j'),
                os.getenv('NEO4J_PASSWORD', 'shopari1234')
            )
        )
        
        self.batch_size = batch_size
        self.process_uncategorized = process_uncategorized
        
        # Enhanced removal patterns for hierarchical categories
        self.definitely_remove = [
            # Business & Industrial - comprehensive
            'Business & Industrial',
            'Signage',
            'Retail & Sale Signs',
            'Commercial',
            'Industrial',
            'Manufacturing',
            'Warehouse',
            
            # Home & Garden
            'Home & Garden',
            'Home Decor',
            'House Accessories',
            'DIY & Security',
            'Ironmongery',
            'Cupboard & Drawer Handles',
            'Painting & Decorating',
            'Paint & Woodcare',
            'Emulsion Paint',
            'Wall Art',
            'Artwork',
            'Furniture',
            'Rugs',
            'Carpets',
            'Curtains',
            'Bedding',
            'Kitchen',
            'Bathroom',
            'Lighting',
            'Garden',
            'Outdoor Living',
            'Patio',
            
            # Vehicles
            'Vehicles & Parts',
            'Vehicle Parts',
            'Vehicle Storage',
            'Truck Bed Storage',
            'Car Accessories',
            'Automotive',
            
            # Recreation (non-fashion)
            'Recreation',
            'Rec Room',
            'Tailgating Supplies',
            'Swimming Pool Accessories',
            
            # Electronics & Tech
            'Electronics',
            'Computers',
            'Computer Accessories',
            'Phone Accessories',
            'Cameras',
            'Audio',
            'Video',
            'Gaming',
            'Smart Home',
            
            # Definitely not fashion
            'Tools',
            'Hardware',
            'Books',
            'Media',
            'Movies',
            'Music',
            'Toys',
            'Games',
            'Pet Supplies',
            'Office Supplies',
            'Craft Supplies',
            'Party Supplies',
            'Party & Celebration',
            'Gift Giving',
            'Food',
            'Beverages',
            'Health',
            'Vitamins',
            'Supplements',
            'Medical',
            'Sports Equipment',
            'Exercise Equipment',
            'Camping Gear',
            'Fishing Gear',
            'Hunting Gear',
            
            # Jewelry
            'Jewelry',
            'Jewellery',
            'Rings',
            'Necklaces',
            'Bracelets',
            'Earrings',
            'Watches',
            'Pendants',
            'Charms',
        ]
        
        # Enhanced AI verification patterns
        self.needs_ai_verification = [
            # Original ambiguous
            'Beauty',
            'Accessories',
            'Sports',
            'Travel',
            'Vintage',
            'Designer',
            'Gifts',
            'Holiday',
            'Seasonal',
            
            # New ambiguous patterns from your data
            'Sports > Outdoors',  # Could be apparel or equipment
            'Bags',  # Could be fashion bags or storage
            'Personal Care',  # Could have fashion accessories
            'Cosmetics',  # Makeup bags, cases
            'Uniforms',  # Usually fashion
            'Official equipments > Fan zone',  # Sports jerseys?
            'Sports BH',  # Sports bras - fashion
            'beauty & skincare',  # Could have accessories
            'Swimming',  # Could be swimwear
            
            # Sports categories that might have apparel
            'Sporting Goods',
            'Athletics',
            'Exercise & Fitness',
            'Outdoor Recreation',
            'Camping & Hiking',  # Could have hiking boots/apparel
            'Soccer',
            'Football',
            
            # Ambiguous material categories
            'Fabric',
            'Textiles',
            'Leather',
            
            # Luggage (could be fashion)
            'Luggage',
            'Backpacks',
            'Suitcases',
            
            # Personal care that might be fashion
            'Skincare',
            'Haircare',
            'Makeup',
            
            # Jewelry materials (need context)
            'Gold',
            'Platinum',
            'Rose Gold',
            'Yellow Gold',
            'Silver',
            
            # Arts & Crafts (could have fashion crafting)
            'Arts & Crafts',
            'Hobbies & Creative Arts',
            'Art & Crafting Materials',
            
            # Generic sport term
            'Sport',
            'Sports',
        ]
        
        # Definitely fashion categories
        self.definitely_fashion = [
            # English
            'Clothing',
            'Apparel',
            'Fashion',
            'Shoes',
            'Footwear',
            'Handbags',
            'Purses',
            'Belts',
            'Scarves',
            'Hats',
            'Gloves',
            'Sunglasses',
            'Fashion Accessories',
            'Dresses',
            'Shirts',
            'Tops',
            'Pants',
            'Jeans',
            'Skirts',
            'Suits',
            'Outerwear',
            'Jackets',
            'Coats',
            'Sweaters',
            'Underwear',
            'Lingerie',
            'Swimwear',
            'Activewear',
            'Sportswear',
            'Boots',
            'Tees',
            'Shorts',
            'Uniforms',
            'Socks',
            'Trousers',
            'Clothes',
            
            # Multi-language fashion terms
            'Mode',  # French for Fashion
            'Pantalons',  # French for Pants
            'Pulls',  # French for Sweaters
            'BH',  # Scandinavian for Bra
            'bøjle',  # Underwire
            
            # Sports fashion
            'football boots',
            'soccer boots',
            'athletic shoes',
            'running shoes',
            'sports shoes',
            'goalkeeper gloves',
            'sports gloves',
        ]
    
    def get_initial_stats(self):
        """Get comprehensive database statistics"""
        logger.info("=== Current Database Statistics ===")
        
        with self.driver.session() as session:
            # Overall stats
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    count(p) as total,
                    sum(CASE WHEN p:MarkedForRemoval THEN 1 ELSE 0 END) as marked_removal,
                    sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as fashion,
                    sum(CASE WHEN p:NeedsAI THEN 1 ELSE 0 END) as needs_ai,
                    sum(CASE WHEN NOT p:MarkedForRemoval 
                             AND NOT p:FashionProduct 
                             AND NOT p:NeedsAI THEN 1 ELSE 0 END) as uncategorized
            """).single()
            
            logger.info(f"\nTotal products: {result['total']:,}")
            logger.info(f"❌ Marked for removal: {result['marked_removal']:,}")
            logger.info(f"✅ Fashion products: {result['fashion']:,}")
            logger.info(f"🤖 Needs AI: {result['needs_ai']:,}")
            logger.info(f"❓ Uncategorized: {result['uncategorized']:,}")
            
            # Show uncategorized categories
            if result['uncategorized'] > 0:
                logger.info("\nTop 30 Uncategorized Categories:")
                category_results = session.run("""
                    MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                    WHERE NOT p:MarkedForRemoval 
                      AND NOT p:FashionProduct 
                      AND NOT p:NeedsAI
                    RETURN c.name as category, count(p) as count
                    ORDER BY count DESC
                    LIMIT 30
                """)
                
                for record in category_results:
                    category = record['category'] or 'Unknown'
                    count = record['count']
                    
                    # Show what action will be taken
                    action = self._get_action_for_category(category)
                    logger.info(f"  {category}: {count:,} {action}")
    
    def _get_action_for_category(self, category):
        """Determine what action to take for a category"""
        if not category:
            return "❓ UNKNOWN"
            
        category_lower = category.lower()
        
        # Check removal patterns
        for pattern in self.definitely_remove:
            if pattern.lower() in category_lower:
                return "❌ WILL REMOVE"
        
        # Check fashion patterns (but exclude jewelry)
        for pattern in self.definitely_fashion:
            if pattern.lower() in category_lower:
                # Double-check it's not jewelry
                jewelry_terms = ['jewel', 'ring', 'necklace', 'bracelet', 'earring', 'watch', 'pendant']
                if any(term in category_lower for term in jewelry_terms):
                    return "❌ WILL REMOVE"
                return "✅ WILL MARK FASHION"
        
        # Check AI patterns
        for pattern in self.needs_ai_verification:
            if pattern.lower() in category_lower:
                return "🤖 WILL MARK FOR AI"
        
        return "❓ NO MATCH"
    
    def mark_products_for_removal(self, include_uncategorized=True):
        """Mark products in non-fashion categories"""
        logger.info("\n=== Marking Products for Removal ===")
        
        total_marked = 0
        
        for category_pattern in self.definitely_remove:
            with self.driver.session() as session:
                # Build query based on whether to include uncategorized
                if include_uncategorized and self.process_uncategorized:
                    # Process products that are either uncategorized OR not yet marked
                    query = """
                        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                        WHERE toLower(c.name) CONTAINS toLower($pattern)
                        AND NOT p:MarkedForRemoval
                        AND NOT p:FashionProduct
                        RETURN count(p) as total_count
                    """
                else:
                    # Original behavior - only unmarked products
                    query = """
                        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                        WHERE toLower(c.name) CONTAINS toLower($pattern)
                        AND NOT p:MarkedForRemoval
                        AND NOT p:FashionProduct
                        RETURN count(p) as total_count
                    """
                
                count_result = session.run(query, pattern=category_pattern).single()
                total_to_mark = count_result['total_count']
                
                if total_to_mark == 0:
                    continue
                    
                logger.info(f"  Processing '{category_pattern}' ({total_to_mark:,} products)...")
                
                # Process in batches
                marked_in_category = 0
                
                while marked_in_category < total_to_mark:
                    if include_uncategorized and self.process_uncategorized:
                        batch_query = """
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                            AND NOT p:MarkedForRemoval
                            AND NOT p:FashionProduct
                            WITH p, c LIMIT $batch_size
                            REMOVE p:NeedsAI
                            SET p:MarkedForRemoval
                            SET p.removal_reason = 'Category: ' + c.name
                            SET p.marked_at = datetime()
                            RETURN count(p) as count
                        """
                    else:
                        batch_query = """
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                            AND NOT p:MarkedForRemoval
                            AND NOT p:FashionProduct
                            WITH p, c LIMIT $batch_size
                            SET p:MarkedForRemoval
                            SET p.removal_reason = 'Category: ' + c.name
                            SET p.marked_at = datetime()
                            RETURN count(p) as count
                        """
                    
                    batch_result = session.run(
                        batch_query, 
                        pattern=category_pattern, 
                        batch_size=self.batch_size
                    ).single()
                    
                    batch_marked = batch_result['count']
                    marked_in_category += batch_marked
                    total_marked += batch_marked
                    
                    if batch_marked == 0:
                        break
                
                if marked_in_category > 0:
                    logger.info(f"  ✓ '{category_pattern}': {marked_in_category:,} products marked")
        
        logger.info(f"\nTotal marked for removal: {total_marked:,}")
        return total_marked
    
    def mark_fashion_products(self, include_uncategorized=True):
        """Mark obvious fashion products"""
        logger.info("\n=== Marking Fashion Products ===")
        
        gc.collect()
        total_marked = 0
        
        for category_pattern in self.definitely_fashion:
            with self.driver.session() as session:
                # Build query
                if include_uncategorized and self.process_uncategorized:
                    count_query = """
                        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                        WHERE toLower(c.name) CONTAINS toLower($pattern)
                        AND NOT p:MarkedForRemoval
                        AND NOT p:FashionProduct
                        AND NOT (toLower(c.name) CONTAINS 'equipment' OR 
                                 toLower(c.name) CONTAINS 'tools' OR
                                 toLower(c.name) CONTAINS 'accessories > home')
                        RETURN count(p) as total_count
                    """
                else:
                    count_query = """
                        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                        WHERE toLower(c.name) CONTAINS toLower($pattern)
                        AND NOT p:MarkedForRemoval
                        AND NOT p:FashionProduct
                        AND NOT (toLower(c.name) CONTAINS 'equipment' OR 
                                 toLower(c.name) CONTAINS 'tools' OR
                                 toLower(c.name) CONTAINS 'accessories > home')
                        RETURN count(p) as total_count
                    """
                
                count_result = session.run(count_query, pattern=category_pattern).single()
                total_to_mark = count_result['total_count']
                
                if total_to_mark == 0:
                    continue
                    
                logger.info(f"  Processing '{category_pattern}' ({total_to_mark:,} products)...")
                
                # Process in batches
                marked_in_category = 0
                
                while marked_in_category < total_to_mark:
                    if include_uncategorized and self.process_uncategorized:
                        batch_query = """
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                            AND NOT p:MarkedForRemoval
                            AND NOT p:FashionProduct
                            AND NOT (toLower(c.name) CONTAINS 'equipment' OR 
                                     toLower(c.name) CONTAINS 'tools' OR
                                     toLower(c.name) CONTAINS 'accessories > home')
                            WITH p, c LIMIT $batch_size
                            REMOVE p:NeedsAI
                            SET p:FashionProduct
                            SET p.classification_reason = 'Category: ' + c.name
                            SET p.classified_at = datetime()
                            RETURN count(p) as count
                        """
                    else:
                        batch_query = """
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                            AND NOT p:MarkedForRemoval
                            AND NOT p:FashionProduct
                            AND NOT (toLower(c.name) CONTAINS 'equipment' OR 
                                     toLower(c.name) CONTAINS 'tools' OR
                                     toLower(c.name) CONTAINS 'accessories > home')
                            WITH p, c LIMIT $batch_size
                            SET p:FashionProduct
                            SET p.classification_reason = 'Category: ' + c.name
                            SET p.classified_at = datetime()
                            RETURN count(p) as count
                        """
                    
                    batch_result = session.run(
                        batch_query,
                        pattern=category_pattern,
                        batch_size=self.batch_size
                    ).single()
                    
                    batch_marked = batch_result['count']
                    marked_in_category += batch_marked
                    total_marked += batch_marked
                    
                    if batch_marked == 0:
                        break
                
                if marked_in_category > 0:
                    logger.info(f"  ✓ '{category_pattern}': {marked_in_category:,} products marked as fashion")
        
        logger.info(f"\nTotal marked as fashion: {total_marked:,}")
        return total_marked
    
    def mark_needs_ai(self, include_uncategorized=True):
        """Mark products that need AI verification"""
        logger.info("\n=== Marking Products Needing AI ===")
        
        gc.collect()
        total_marked = 0
        
        for category_pattern in self.needs_ai_verification:
            with self.driver.session() as session:
                # Build query
                if include_uncategorized and self.process_uncategorized:
                    count_query = """
                        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                        WHERE toLower(c.name) CONTAINS toLower($pattern)
                        AND NOT p:MarkedForRemoval
                        AND NOT p:FashionProduct
                        AND NOT p:NeedsAI
                        RETURN count(p) as total_count
                    """
                else:
                    count_query = """
                        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                        WHERE toLower(c.name) CONTAINS toLower($pattern)
                        AND NOT p:MarkedForRemoval
                        AND NOT p:FashionProduct
                        AND NOT p:NeedsAI
                        RETURN count(p) as total_count
                    """
                
                count_result = session.run(count_query, pattern=category_pattern).single()
                total_to_mark = count_result['total_count']
                
                if total_to_mark == 0:
                    continue
                
                logger.info(f"  Processing '{category_pattern}' ({total_to_mark:,} products)...")
                
                # Process in batches
                marked_in_category = 0
                
                while marked_in_category < total_to_mark:
                    batch_result = session.run("""
                        MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                        WHERE toLower(c.name) CONTAINS toLower($pattern)
                        AND NOT p:MarkedForRemoval
                        AND NOT p:FashionProduct
                        AND NOT p:NeedsAI
                        WITH p, c LIMIT $batch_size
                        SET p:NeedsAI
                        SET p.ai_reason = 'Ambiguous category: ' + c.name
                        SET p.needs_ai_added = datetime()
                        RETURN count(p) as count
                    """, pattern=category_pattern, batch_size=self.batch_size).single()
                    
                    batch_marked = batch_result['count']
                    marked_in_category += batch_marked
                    total_marked += batch_marked
                    
                    if batch_marked == 0:
                        break
                
                if marked_in_category > 0:
                    logger.info(f"  ✓ '{category_pattern}': {marked_in_category:,} products need AI verification")
        
        logger.info(f"\nTotal needing AI: {total_marked:,}")
        return total_marked
    
    def mark_remaining_uncategorized_for_ai(self):
        """Mark any remaining uncategorized products for AI verification"""
        logger.info("\n=== Marking Remaining Uncategorized for AI ===")
        
        with self.driver.session() as session:
            # Count remaining uncategorized
            count_result = session.run("""
                MATCH (p:Product)
                WHERE NOT p:MarkedForRemoval 
                  AND NOT p:FashionProduct 
                  AND NOT p:NeedsAI
                RETURN count(p) as count
            """).single()
            
            total_remaining = count_result['count']
            
            if total_remaining == 0:
                logger.info("No remaining uncategorized products!")
                return 0
            
            logger.info(f"Found {total_remaining:,} remaining uncategorized products")
            logger.info("Marking them all for AI verification...")
            
            # Mark in batches
            marked = 0
            while marked < total_remaining:
                result = session.run("""
                    MATCH (p:Product)
                    WHERE NOT p:MarkedForRemoval 
                      AND NOT p:FashionProduct 
                      AND NOT p:NeedsAI
                    WITH p LIMIT $batch_size
                    SET p:NeedsAI
                    SET p.ai_reason = 'Uncategorized - needs AI verification'
                    SET p.needs_ai_added = datetime()
                    RETURN count(p) as count
                """, batch_size=self.batch_size).single()
                
                batch_marked = result['count']
                marked += batch_marked
                
                if batch_marked == 0:
                    break
                    
                if marked % 100000 == 0:
                    logger.info(f"  Progress: {marked:,}/{total_remaining:,}")
            
            logger.info(f"✓ Marked {marked:,} uncategorized products for AI")
            return marked
    
    def get_final_stats(self):
        """Show final statistics"""
        logger.info("\n=== Final Statistics ===")
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    count(p) as total,
                    sum(CASE WHEN p:MarkedForRemoval THEN 1 ELSE 0 END) as to_remove,
                    sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as fashion,
                    sum(CASE WHEN p:NeedsAI THEN 1 ELSE 0 END) as needs_ai,
                    sum(CASE WHEN NOT p:MarkedForRemoval AND NOT p:FashionProduct AND NOT p:NeedsAI THEN 1 ELSE 0 END) as uncategorized
            """).single()
            
            total = result['total']
            to_remove = result['to_remove']
            fashion = result['fashion']
            needs_ai = result['needs_ai']
            uncategorized = result['uncategorized']
            
            logger.info(f"Total Products: {total:,}")
            logger.info(f"❌ To Remove: {to_remove:,} ({to_remove/total*100:.1f}%)")
            logger.info(f"✅ Fashion: {fashion:,} ({fashion/total*100:.1f}%)")
            logger.info(f"🤖 Needs AI: {needs_ai:,} ({needs_ai/total*100:.1f}%)")
            logger.info(f"❓ Still Uncategorized: {uncategorized:,} ({uncategorized/total*100:.1f}%)")
            
            # Cost analysis
            logger.info(f"\n💰 Cost Analysis:")
            logger.info(f"  Products not needing AI: {to_remove + fashion:,}")
            logger.info(f"  Estimated API cost saved: ${(to_remove + fashion) * 0.000015:.2f}")
            logger.info(f"  Products needing AI classification: {needs_ai:,}")
            logger.info(f"  Estimated AI cost: ${needs_ai * 0.000015:.2f}")
    
    def delete_marked_products(self, dry_run=True, skip_confirmation=False):
        """Delete products marked for removal"""
        with self.driver.session() as session:
            count_result = session.run("""
                MATCH (p:MarkedForRemoval)
                RETURN count(p) as count
            """).single()
            
            count = count_result['count']
            
            if count == 0:
                logger.info("\n✅ No products marked for removal!")
                return
            
            if dry_run:
                logger.info(f"\n🔍 DRY RUN: Would delete {count:,} products marked for removal")
            else:
                if skip_confirmation:
                    confirm = 'DELETE'
                else:
                    confirm = input(f"\n⚠️  DELETE {count:,} products? Type 'DELETE' to confirm: ")
                    
                if confirm == 'DELETE':
                    logger.info(f"Deleting {count:,} products...")
                    
                    deleted = 0
                    batch_size = self.batch_size
                    
                    while deleted < count:
                        result = session.run("""
                            MATCH (p:MarkedForRemoval)
                            WITH p LIMIT $batch_size
                            DETACH DELETE p
                            RETURN count(p) as deleted
                        """, batch_size=batch_size).single()
                        
                        batch_deleted = result['deleted']
                        deleted += batch_deleted
                        
                        if batch_deleted == 0:
                            break
                        
                        if deleted % 50000 == 0:
                            logger.info(f"  Deleted {deleted:,}/{count:,}...")
                    
                    logger.info(f"✅ Deleted {deleted:,} non-fashion products")
                else:
                    logger.info("Deletion cancelled")
    
    def close(self):
        self.driver.close()

def main():
    logger.info("Starting Enhanced Fashion Cleanup")
    logger.info("="*60)
    
    # CONFIGURATION
    batch_size = 5000
    auto_delete = True
    process_uncategorized = True  # Process products without any labels
    mark_all_uncategorized_as_ai = True  # Mark remaining uncategorized for AI
    
    cleaner = EnhancedFashionCleaner(
        batch_size=batch_size, 
        process_uncategorized=process_uncategorized
    )
    
    logger.info(f"Configuration:")
    logger.info(f"  Batch size: {batch_size:,}")
    logger.info(f"  Auto-delete: {'ENABLED' if auto_delete else 'DISABLED'}")
    logger.info(f"  Process uncategorized: {'YES' if process_uncategorized else 'NO'}")
    logger.info(f"  Mark all remaining for AI: {'YES' if mark_all_uncategorized_as_ai else 'NO'}")
    
    try:
        # Show current state
        cleaner.get_initial_stats()
        
        # Get confirmation
        if auto_delete:
            logger.info("\n⚠️  WARNING: This will DELETE products marked for removal!")
            response = input("\nType 'PROCEED' to continue: ")
            if response != 'PROCEED':
                logger.info("Cancelled by user")
                return
        
        start_time = time.time()
        
        # Process products
        removed = cleaner.mark_products_for_removal(include_uncategorized=process_uncategorized)
        fashion = cleaner.mark_fashion_products(include_uncategorized=process_uncategorized)
        needs_ai = cleaner.mark_needs_ai(include_uncategorized=process_uncategorized)
        
        # Handle remaining uncategorized
        if mark_all_uncategorized_as_ai:
            remaining = cleaner.mark_remaining_uncategorized_for_ai()
        
        elapsed = time.time() - start_time
        logger.info(f"\nProcessing completed in {elapsed/60:.1f} minutes")
        
        # Show results
        cleaner.get_final_stats()
        
        # Delete if enabled
        if auto_delete and removed > 0:
            logger.info("\n⚠️  About to DELETE marked products!")
            logger.info("You have 10 seconds to cancel...")
            
            try:
                for i in range(10, 0, -1):
                    print(f"\rDeleting in {i} seconds... ", end='', flush=True)
                    time.sleep(1)
                print("\r" + " " * 30 + "\r", end='')
                
                cleaner.delete_marked_products(dry_run=False, skip_confirmation=True)
                
            except KeyboardInterrupt:
                logger.info("\n\n❌ Deletion cancelled!")
                cleaner.delete_marked_products(dry_run=True)
        else:
            cleaner.delete_marked_products(dry_run=True)
        
        logger.info("\n✅ Cleanup complete!")
        
    finally:
        cleaner.close()

if __name__ == "__main__":
    main()



    
# #!/usr/bin/env python3
# """
# Aggressive cleanup of obvious non-fashion products
# Only keeps ambiguous categories like Beauty for AI classification
# """

# import os
# import time
# import gc
# from neo4j import GraphDatabase
# from datetime import datetime
# import logging
# from dotenv import load_dotenv

# load_dotenv()

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# class AggressiveFashionCleaner:
#     def __init__(self, batch_size=10000):
#         self.driver = GraphDatabase.driver(
#             os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
#             auth=(
#                 os.getenv('NEO4J_USERNAME', 'neo4j'),
#                 os.getenv('NEO4J_PASSWORD', 'shopari1234')
#             )
#         )
        
#         self.batch_size = batch_size  # Configurable batch size
        
#         # Categories that DEFINITELY need to go
#         self.definitely_remove = [
#             # Home & Garden
#             'Home & Garden',
#             'Home Decor', 
#             'Wall Art',
#             'Artwork',
#             'Furniture',
#             'Rugs',
#             'Carpets',
#             'Curtains',
#             'Bedding',
#             'Kitchen',
#             'Bathroom',
#             'Lighting',
#             'Garden',
#             'Outdoor Living',
#             'Patio',
            
#             # Electronics & Tech
#             'Electronics',
#             'Computers',
#             'Computer Accessories',
#             'Phone Accessories',
#             'Cameras',
#             'Audio',
#             'Video',
#             'Gaming',
#             'Smart Home',
            
#             # Definitely not fashion
#             'Tools',
#             'Hardware', 
#             'Automotive',
#             'Car Accessories',
#             'Books',
#             'Media',
#             'Movies',
#             'Music',
#             'Toys',
#             'Games',
#             'Pet Supplies',
#             'Office Supplies',
#             'Craft Supplies',
#             'Party Supplies',
#             'Food',
#             'Beverages',
#             'Health',
#             'Vitamins',
#             'Supplements',
#             'Medical',
#             'Sports Equipment',  # Not apparel
#             'Exercise Equipment',
#             'Camping Gear',  # Not clothing
#             'Fishing Gear',
#             'Hunting Gear',
            
#             # Jewelry (per your request)
#             'Jewelry',
#             'Jewellery',  # British spelling
#             'Rings',
#             'Necklaces',
#             'Bracelets',
#             'Earrings',
#             'Watches',
#             'Pendants',
#             'Charms',
#         ]
        
#         # Categories that need AI verification
#         self.needs_ai_verification = [
#             'Beauty',  # Could have fashion accessories
#             'Accessories',  # Too vague
#             'Sports',  # Could be apparel or equipment
#             'Travel',  # Could be luggage (fashion) or accessories
#             'Vintage',  # Could be fashion or collectibles  
#             'Designer',  # Could be fashion or home goods
#             'Gifts',  # Could be anything
#             'Holiday',  # Could contain fashion items
#             'Seasonal',  # Could contain fashion items
#         ]
        
#         # Definitely fashion categories
#         self.definitely_fashion = [
#             'Clothing',
#             'Apparel',
#             'Fashion',
#             'Shoes',
#             'Footwear',
#             'Handbags',
#             'Purses',
#             'Belts',
#             'Scarves',
#             'Hats',
#             'Gloves',
#             'Sunglasses',
#             'Fashion Accessories',
#             'Dresses',
#             'Shirts',
#             'Tops',
#             'Pants',
#             'Jeans',
#             'Skirts',
#             'Suits',
#             'Outerwear',
#             'Jackets',
#             'Coats',
#             'Sweaters',
#             'Underwear',
#             'Lingerie',
#             'Swimwear',
#             'Activewear',
#             'Sportswear',
#         ]
    
#     def get_initial_stats(self):
#         """Get current database statistics"""
#         logger.info("=== Initial Statistics ===")
        
#         with self.driver.session() as session:
#             result = session.run("""
#                 MATCH (p:Product)
#                 RETURN count(p) as total_products
#             """).single()
            
#             total = result['total_products']
#             logger.info(f"Total products: {total:,}")
            
#             # Show top categories
#             logger.info("\nTop 30 Categories:")
#             category_results = session.run("""
#                 MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
#                 RETURN c.name as category, count(p) as count
#                 ORDER BY count DESC
#                 LIMIT 30
#             """)
            
#             for record in category_results:
#                 category = record['category'] or 'Unknown'
#                 count = record['count']
                
#                 # Mark which action will be taken
#                 if any(remove_term.lower() in category.lower() for remove_term in self.definitely_remove):
#                     action = "❌ REMOVE"
#                 elif any(fashion_term.lower() in category.lower() for fashion_term in self.definitely_fashion):
#                     # Double-check it's not jewelry
#                     if any(jewelry_term in category.lower() for jewelry_term in ['jewel', 'ring', 'necklace', 'bracelet', 'earring', 'watch']):
#                         action = "❌ REMOVE"
#                     else:
#                         action = "✅ FASHION"
#                 elif any(ai_term.lower() in category.lower() for ai_term in self.needs_ai_verification):
#                     action = "🤖 NEEDS AI"
#                 else:
#                     action = "❓ CHECK"
                
#                 logger.info(f"  {category}: {count:,} {action}")
    
#     def mark_products_for_removal(self):
#         """Mark products in non-fashion categories"""
#         logger.info("\n=== Marking Products for Removal ===")
        
#         total_marked = 0
        
#         for category_pattern in self.definitely_remove:
#             with self.driver.session() as session:
#                 # First, count how many products match
#                 count_result = session.run("""
#                     MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
#                     WHERE toLower(c.name) CONTAINS toLower($pattern)
#                     AND NOT p:MarkedForRemoval
#                     AND NOT p:FashionProduct
#                     RETURN count(p) as total_count
#                 """, pattern=category_pattern).single()
                
#                 total_to_mark = count_result['total_count']
                
#                 if total_to_mark == 0:
#                     continue
                    
#                 logger.info(f"  Processing '{category_pattern}' ({total_to_mark:,} products)...")
                
#                 # Process in batches to avoid memory issues
#                 batch_size = self.batch_size
#                 marked_in_category = 0
                
#                 while marked_in_category < total_to_mark:
#                     batch_result = session.run("""
#                         MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
#                         WHERE toLower(c.name) CONTAINS toLower($pattern)
#                         AND NOT p:MarkedForRemoval
#                         AND NOT p:FashionProduct
#                         WITH p, c LIMIT $batch_size
#                         SET p:MarkedForRemoval
#                         SET p.removal_reason = 'Category: ' + c.name
#                         SET p.marked_at = datetime()
#                         RETURN count(p) as count
#                     """, pattern=category_pattern, batch_size=batch_size).single()
                    
#                     batch_marked = batch_result['count']
#                     marked_in_category += batch_marked
#                     total_marked += batch_marked
                    
#                     # Show progress for large categories
#                     if total_to_mark > 100000 and marked_in_category % 50000 == 0:
#                         logger.info(f"    Progress: {marked_in_category:,}/{total_to_mark:,} marked")
                    
#                     if batch_marked == 0:
#                         break
                
#                 if marked_in_category > 0:
#                     logger.info(f"  ✓ '{category_pattern}': {marked_in_category:,} products marked")
        
#         logger.info(f"\nTotal marked for removal: {total_marked:,}")
#         return total_marked
    
#     def mark_fashion_products(self):
#         """Mark obvious fashion products"""
#         logger.info("\n=== Marking Fashion Products ===")
        
#         # Force garbage collection to free memory
#         gc.collect()
        
#         total_marked = 0
        
#         for category_pattern in self.definitely_fashion:
#             with self.driver.session() as session:
#                 # First, count how many products match
#                 count_result = session.run("""
#                     MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
#                     WHERE toLower(c.name) CONTAINS toLower($pattern)
#                     AND NOT p:MarkedForRemoval
#                     AND NOT p:FashionProduct
#                     AND NOT (toLower(c.name) CONTAINS 'equipment' OR 
#                              toLower(c.name) CONTAINS 'tools' OR
#                              toLower(c.name) CONTAINS 'accessories > home')
#                     RETURN count(p) as total_count
#                 """, pattern=category_pattern).single()
                
#                 total_to_mark = count_result['total_count']
                
#                 if total_to_mark == 0:
#                     continue
                    
#                 logger.info(f"  Processing '{category_pattern}' ({total_to_mark:,} products)...")
                
#                 # Process in batches
#                 batch_size = self.batch_size
#                 marked_in_category = 0
                
#                 while marked_in_category < total_to_mark:
#                     batch_result = session.run("""
#                         MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
#                         WHERE toLower(c.name) CONTAINS toLower($pattern)
#                         AND NOT p:MarkedForRemoval
#                         AND NOT p:FashionProduct
#                         AND NOT (toLower(c.name) CONTAINS 'equipment' OR 
#                                  toLower(c.name) CONTAINS 'tools' OR
#                                  toLower(c.name) CONTAINS 'accessories > home')
#                         WITH p, c LIMIT $batch_size
#                         SET p:FashionProduct
#                         SET p.classification_reason = 'Category: ' + c.name
#                         SET p.classified_at = datetime()
#                         RETURN count(p) as count
#                     """, pattern=category_pattern, batch_size=batch_size).single()
                    
#                     batch_marked = batch_result['count']
#                     marked_in_category += batch_marked
#                     total_marked += batch_marked
                    
#                     # Show progress for large categories
#                     if total_to_mark > 100000 and marked_in_category % 50000 == 0:
#                         logger.info(f"    Progress: {marked_in_category:,}/{total_to_mark:,} marked")
                    
#                     if batch_marked == 0:
#                         break
                
#                 if marked_in_category > 0:
#                     logger.info(f"  ✓ '{category_pattern}': {marked_in_category:,} products marked as fashion")
        
#         logger.info(f"\nTotal marked as fashion: {total_marked:,}")
#         return total_marked
    
#     def mark_needs_ai(self):
#         """Mark products that need AI verification"""
#         logger.info("\n=== Marking Products Needing AI ===")
        
#         # Force garbage collection to free memory
#         gc.collect()
        
#         total_marked = 0
        
#         for category_pattern in self.needs_ai_verification:
#             with self.driver.session() as session:
#                 # First, count how many products match
#                 count_result = session.run("""
#                     MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
#                     WHERE toLower(c.name) CONTAINS toLower($pattern)
#                     AND NOT p:MarkedForRemoval
#                     AND NOT p:FashionProduct
#                     AND NOT p:NeedsAI
#                     RETURN count(p) as total_count
#                 """, pattern=category_pattern).single()
                
#                 total_to_mark = count_result['total_count']
                
#                 if total_to_mark == 0:
#                     continue
                
#                 # Process in batches
#                 batch_size = 10000
#                 marked_in_category = 0
                
#                 while marked_in_category < total_to_mark:
#                     batch_result = session.run("""
#                         MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
#                         WHERE toLower(c.name) CONTAINS toLower($pattern)
#                         AND NOT p:MarkedForRemoval
#                         AND NOT p:FashionProduct
#                         AND NOT p:NeedsAI
#                         WITH p, c LIMIT $batch_size
#                         SET p:NeedsAI
#                         SET p.ai_reason = 'Ambiguous category: ' + c.name
#                         RETURN count(p) as count
#                     """, pattern=category_pattern, batch_size=batch_size).single()
                    
#                     batch_marked = batch_result['count']
#                     marked_in_category += batch_marked
#                     total_marked += batch_marked
                    
#                     if batch_marked == 0:
#                         break
                
#                 if marked_in_category > 0:
#                     logger.info(f"  ✓ '{category_pattern}': {marked_in_category:,} products need AI verification")
        
#         logger.info(f"\nTotal needing AI: {total_marked:,}")
#         return total_marked
    
#     def get_final_stats(self):
#         """Show final statistics"""
#         logger.info("\n=== Final Statistics ===")
        
#         with self.driver.session() as session:
#             result = session.run("""
#                 MATCH (p:Product)
#                 RETURN 
#                     count(p) as total,
#                     sum(CASE WHEN p:MarkedForRemoval THEN 1 ELSE 0 END) as to_remove,
#                     sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as fashion,
#                     sum(CASE WHEN p:NeedsAI THEN 1 ELSE 0 END) as needs_ai,
#                     sum(CASE WHEN NOT p:MarkedForRemoval AND NOT p:FashionProduct AND NOT p:NeedsAI THEN 1 ELSE 0 END) as uncategorized
#             """).single()
            
#             total = result['total']
#             to_remove = result['to_remove']
#             fashion = result['fashion']
#             needs_ai = result['needs_ai']
#             uncategorized = result['uncategorized']
            
#             logger.info(f"Total Products: {total:,}")
#             logger.info(f"❌ To Remove: {to_remove:,} ({to_remove/total*100:.1f}%)")
#             logger.info(f"✅ Fashion: {fashion:,} ({fashion/total*100:.1f}%)")
#             logger.info(f"🤖 Needs AI: {needs_ai:,} ({needs_ai/total*100:.1f}%)")
#             logger.info(f"❓ Uncategorized: {uncategorized:,} ({uncategorized/total*100:.1f}%)")
            
#             # Cost savings
#             logger.info(f"\n💰 Cost Savings:")
#             logger.info(f"  Products not needing AI: {to_remove + fashion:,}")
#             logger.info(f"  Estimated API cost saved: ${(to_remove + fashion) * 0.000015:.2f}")
#             logger.info(f"  Processing time saved: ~{(to_remove + fashion) / 1000:.0f} hours")
            
#             # Memory usage tip
#             if uncategorized > 100000:
#                 logger.info(f"\n💡 Tip: You still have {uncategorized:,} uncategorized products.")
#                 logger.info("   Consider running the script again with additional patterns.")
    
#     def delete_marked_products(self, dry_run=True, skip_confirmation=False):
#         """Delete products marked for removal"""
#         with self.driver.session() as session:
#             count_result = session.run("""
#                 MATCH (p:MarkedForRemoval)
#                 RETURN count(p) as count
#             """).single()
            
#             count = count_result['count']
            
#             if dry_run:
#                 logger.info(f"\n🔍 DRY RUN: Would delete {count:,} products marked for removal")
#                 logger.info("To actually delete, run: delete_marked_products(dry_run=False)")
#             else:
#                 if skip_confirmation:
#                     confirm = 'DELETE'
#                 else:
#                     confirm = input(f"\n⚠️  DELETE {count:,} products? Type 'DELETE' to confirm: ")
                    
#                 if confirm == 'DELETE':
#                     logger.info(f"Deleting {count:,} products...")
                    
#                     deleted = 0
#                     batch_size = self.batch_size
                    
#                     while deleted < count:
#                         result = session.run("""
#                             MATCH (p:MarkedForRemoval)
#                             WITH p LIMIT $batch_size
#                             DETACH DELETE p
#                             RETURN count(p) as deleted
#                         """, batch_size=batch_size).single()
                        
#                         batch_deleted = result['deleted']
#                         deleted += batch_deleted
                        
#                         if batch_deleted == 0:
#                             break
                        
#                         if deleted % 50000 == 0:
#                             logger.info(f"  Deleted {deleted:,}/{count:,}...")
                    
#                     logger.info(f"✅ Deleted {deleted:,} non-fashion products")
                    
#                     # Show what remains
#                     remaining_result = session.run("""
#                         MATCH (p:Product)
#                         RETURN count(p) as total
#                     """).single()
                    
#                     logger.info(f"\n📊 Final Database State:")
#                     logger.info(f"  Remaining products: {remaining_result['total']:,}")
#                     logger.info(f"  Deleted products: {deleted:,}")
#                     logger.info(f"  Reduction: {deleted/(deleted + remaining_result['total'])*100:.1f}%")
#                 else:
#                     logger.info("Deletion cancelled")
    
#     def close(self):
#         self.driver.close()

# def main():
#     logger.info("Starting Aggressive Fashion Cleanup")
#     logger.info("="*60)
    
#     # CONFIGURATION
#     batch_size = 5000  # Reduced from 10000 to avoid memory errors
#     auto_delete = True  # Set to False if you only want to mark, not delete
    
#     cleaner = AggressiveFashionCleaner(batch_size=batch_size)
#     logger.info(f"Using batch size: {batch_size:,} products per transaction")
#     logger.info(f"Auto-delete mode: {'ENABLED' if auto_delete else 'DISABLED'}")
#     logger.info("Tip: If you get memory errors, reduce batch_size to 2000 or 1000")
    
#     try:
#         # Show what will happen
#         logger.info("\n📋 CLEANUP PLAN:")
#         logger.info("1. Mark non-fashion products (Home, Electronics, Jewelry, etc.)")
#         logger.info("2. Mark fashion products (Clothing, Shoes, Bags, etc.)")
#         logger.info("3. Mark ambiguous products for AI verification")
#         if auto_delete:
#             logger.info("4. DELETE all products marked for removal ⚠️")
#         else:
#             logger.info("4. Report only (no deletion)")
        
#         # Step 1: Show initial stats
#         cleaner.get_initial_stats()
        
#         # Step 2: Mark products
#         if auto_delete:
#             logger.info("\n⚠️  WARNING: This script is set to AUTO-DELETE products!")
#             logger.info("Products marked for removal WILL BE PERMANENTLY DELETED!")
#             response = input("\nType 'PROCEED' to continue (or press Ctrl+C to cancel): ")
#             if response != 'PROCEED':
#                 logger.info("Cancelled by user")
#                 return
#         else:
#             input("\nPress Enter to start marking products...")
        
#         logger.info("\nThis will process in batches to avoid memory errors.")
#         logger.info("Processing ~20M products may take 10-30 minutes...")
        
#         start_time = time.time()
        
#         removed = cleaner.mark_products_for_removal()
#         fashion = cleaner.mark_fashion_products()
#         needs_ai = cleaner.mark_needs_ai()
        
#         elapsed = time.time() - start_time
#         logger.info(f"\nMarking completed in {elapsed/60:.1f} minutes")
        
#         # Step 3: Show final stats
#         cleaner.get_final_stats()
        
#         # Step 4: Delete marked products
#         if auto_delete:
#             logger.info("\n⚠️  WARNING: About to DELETE products marked for removal!")
#             logger.info("You have 10 seconds to press Ctrl+C to cancel...")
            
#             try:
#                 for i in range(10, 0, -1):
#                     print(f"\rDeleting in {i} seconds... ", end='', flush=True)
#                     time.sleep(1)
#                 print("\r" + " " * 30 + "\r", end='')  # Clear the countdown
                
#                 # Proceed with deletion
#                 cleaner.delete_marked_products(dry_run=False, skip_confirmation=True)
                
#             except KeyboardInterrupt:
#                 logger.info("\n\n❌ Deletion cancelled by user!")
#                 logger.info("Products remain marked but not deleted.")
#                 cleaner.delete_marked_products(dry_run=True)
#         else:
#             logger.info("\nAuto-delete is DISABLED. Products are marked but not deleted.")
#             cleaner.delete_marked_products(dry_run=True)
        
#         logger.info("\n✅ Cleanup complete!")
        
#         if auto_delete:
#             logger.info("\n🎯 Next Steps:")
#             logger.info("1. Run AI classification on products with :NeedsAI label")
#             logger.info("2. Products with :FashionProduct label are ready for use")
#             logger.info("3. Consider running embedding generation on fashion products")
        
#     finally:
#         cleaner.close()

# if __name__ == "__main__":
#     main()