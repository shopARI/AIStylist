#!/usr/bin/env python3
"""
Neo4j Fashion Product Cleanup and Classification Pipeline
Comprehensive solution for cleaning, classifying, deduplicating, and preparing products

Features:
- Keyword-based classification for obvious categories
- Duplicate detection with multiple strategies
- Property management for embeddings
- Deletion of non-fashion and duplicate products
- Full logging and reporting
- Resume capability for interrupted runs

# Examples 

# Dry run with aggressive deduplication
python neo4j_cleanup.py --duplicate-strategy aggressive --dry-run

# Full cleanup with duplicate deletion
python neo4j_cleanup.py --auto-delete --delete-duplicates

# Conservative approach for production
python neo4j_cleanup.py --duplicate-strategy conservative --batch-size 2000

# Skip duplicate detection
python neo4j_cleanup.py --skip-duplicates

Version: 2.0
"""

import os
import time
import gc
import json
from neo4j import GraphDatabase
from datetime import datetime
import logging
from dotenv import load_dotenv
from tqdm import tqdm
from tabulate import tabulate
from collections import defaultdict
import argparse

load_dotenv()

# Logging setup
log_dir = './cleanup_logs'
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f'cleanup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FashionProductCleanup:
    """
    Comprehensive cleanup pipeline for fashion product databases
    
    This class handles:
    1. Classification of products into fashion/non-fashion/needs-AI categories
    2. Deduplication of products based on configurable strategies
    3. Setting properties required for embedding pipelines
    4. Deletion of unwanted products
    5. Generation of detailed reports
    """
    
    def __init__(self, config=None):
        """
        Initialize the cleanup pipeline
        
        Args:
            config (dict): Configuration dictionary with options:
                - batch_size: Number of products to process per transaction
                - process_uncategorized: Whether to process products without labels
                - mark_duplicates: Whether to detect and mark duplicates
                - duplicate_strategy: 'aggressive', 'smart', or 'conservative'
                - delete_duplicates: Whether to delete duplicate products
                - auto_delete: Whether to delete non-fashion products
                - dry_run: Test mode without making changes
        """
        self.config = config or self._get_default_config()
        
        self.driver = GraphDatabase.driver(
            os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
            auth=(
                os.getenv('NEO4J_USERNAME', 'neo4j'),
                os.getenv('NEO4J_PASSWORD', 'shopari1234')
            ),
            max_connection_lifetime=3600
        )
        
        # Statistics tracking
        self.stats = defaultdict(int)
        self.start_time = None
        
        # Classification patterns
        self._init_classification_patterns()
        
        # State management for resume capability
        self.state_file = os.path.join(log_dir, 'cleanup_state.json')
        self.state = self._load_state()
    
    def _get_default_config(self):
        """Get default configuration"""
        return {
            'batch_size': 5000,
            'process_uncategorized': True,
            'mark_duplicates': True,
            'duplicate_strategy': 'smart',
            'delete_duplicates': False,
            'auto_delete': False,
            'dry_run': False,
            'update_existing': True  # Update products that already have labels
        }
    
    def _init_classification_patterns(self):
        """Initialize classification patterns for keyword-based matching"""
        
        # Definitely NOT fashion
        self.definitely_remove = [
            # Business & Industrial
            'Business & Industrial', 'Signage', 'Retail & Sale Signs', 'Commercial',
            'Industrial', 'Manufacturing', 'Warehouse', 'Business Equipment',
            
            # Home & Garden
            'Home & Garden', 'Home Decor', 'House Accessories', 'DIY & Security',
            'Ironmongery', 'Cupboard & Drawer Handles', 'Painting & Decorating',
            'Paint & Woodcare', 'Wall Art', 'Artwork', 'Furniture', 'Rugs',
            'Carpets', 'Curtains', 'Bedding', 'Kitchen', 'Bathroom', 'Lighting',
            'Garden', 'Outdoor Living', 'Patio', 'Home Improvement',
            
            # Vehicles & Parts
            'Vehicles & Parts', 'Vehicle Parts', 'Car Accessories', 'Automotive',
            'Motorcycles', 'Car Electronics', 'Car Care', 'Tires', 'Auto Parts',
            
            # Electronics & Tech
            'Electronics', 'Computers', 'Computer Accessories', 'Phone Accessories',
            'Cameras', 'Audio', 'Video', 'Gaming', 'Smart Home', 'Tablets',
            'Printers', 'Networking', 'Software', 'Tech Accessories',
            
            # Other non-fashion
            'Tools', 'Hardware', 'Books', 'Media', 'Movies', 'Music', 'Toys',
            'Games', 'Pet Supplies', 'Office Supplies', 'Craft Supplies',
            'Party Supplies', 'Food', 'Beverages', 'Health', 'Vitamins',
            'Supplements', 'Medical', 'Sports Equipment', 'Exercise Equipment',
            'Camping Gear', 'Fishing Gear', 'Hunting Gear', 'Musical Instruments',
            
            # Jewelry (per requirements)
            'Jewelry', 'Jewellery', 'Rings', 'Necklaces', 'Bracelets', 'Earrings',
            'Watches', 'Pendants', 'Charms', 'Fine Jewelry', 'Fashion Jewelry',
        ]
        
        # Needs AI verification
        self.needs_ai_verification = [
            'Beauty', 'Accessories', 'Sports', 'Travel', 'Vintage', 'Designer',
            'Gifts', 'Holiday', 'Seasonal', 'Bags', 'Personal Care', 'Cosmetics',
            'Luggage', 'Backpacks', 'Outdoor Recreation', 'Swimming',
            'Athletics', 'Sporting Goods', 'Uniforms', 'Costumes',
        ]
        
        # Definitely fashion
        self.definitely_fashion = [
            # Core clothing
            'Clothing', 'Apparel', 'Fashion', 'Clothes', 'Garments', 'Wear',
            
            # Tops
            'Shirts', 'Tops', 'Tees', 'T-shirts', 'Blouses', 'Tanks', 'Camisoles',
            'Tunics', 'Polo Shirts', 'Henley', 'Button-downs', 'Crop Tops',
            
            # Bottoms
            'Pants', 'Jeans', 'Trousers', 'Leggings', 'Shorts', 'Skirts',
            'Capris', 'Culottes', 'Joggers', 'Chinos', 'Corduroys',
            
            # Dresses & Suits
            'Dresses', 'Gowns', 'Suits', 'Blazers', 'Tuxedos', 'Jumpsuits',
            'Rompers', 'Overalls', 'Sundresses', 'Cocktail Dresses',
            
            # Outerwear
            'Outerwear', 'Jackets', 'Coats', 'Sweaters', 'Hoodies', 'Cardigans',
            'Pullovers', 'Parkas', 'Windbreakers', 'Raincoats', 'Peacoats',
            
            # Undergarments
            'Underwear', 'Lingerie', 'Bras', 'Panties', 'Boxers', 'Briefs',
            'Thermals', 'Shapewear', 'Hosiery', 'Sleepwear', 'Pajamas',
            
            # Active & Swim
            'Swimwear', 'Bikinis', 'Swimsuits', 'Trunks', 'Activewear',
            'Sportswear', 'Athletic Wear', 'Yoga Pants', 'Sports Bras',
            
            # Footwear
            'Shoes', 'Footwear', 'Boots', 'Sneakers', 'Sandals', 'Heels',
            'Loafers', 'Flats', 'Pumps', 'Athletic Shoes', 'Running Shoes',
            'Dress Shoes', 'Casual Shoes', 'Slippers', 'Espadrilles',
            
            # Fashion accessories
            'Handbags', 'Purses', 'Clutches', 'Wallets', 'Belts', 'Scarves',
            'Hats', 'Caps', 'Beanies', 'Gloves', 'Mittens', 'Sunglasses',
            'Fashion Accessories', 'Socks', 'Stockings', 'Tights', 'Ties',
        ]
    
    def _load_state(self):
        """Load previous state for resume capability"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_state(self):
        """Save current state"""
        self.state['last_updated'] = datetime.now().isoformat()
        self.state['stats'] = dict(self.stats)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def run_full_pipeline(self):
        """
        Run the complete cleanup pipeline
        
        Steps:
        1. Analyze initial state
        2. Update existing labeled products (if any)
        3. Classify products by category
        4. Handle duplicates
        5. Mark remaining uncategorized
        6. Delete unwanted products
        7. Generate final report
        """
        logger.info("="*80)
        logger.info("FASHION PRODUCT CLEANUP PIPELINE v2.0")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        self.start_time = time.time()
        
        try:
            # Step 1: Initial analysis
            self._analyze_initial_state()
            
            # Step 2: Confirm with user
            if not self._get_user_confirmation():
                logger.info("Pipeline cancelled by user")
                return
            
            # Step 3: Update existing fashion products
            if self.config['update_existing']:
                self._update_existing_fashion_products()
            
            # Step 4: Mark products by category
            self._mark_products_by_category()
            
            # Step 5: Handle duplicates
            if self.config['mark_duplicates']:
                self._handle_duplicates()
            
            # Step 6: Mark remaining uncategorized
            self._mark_remaining_uncategorized()
            
            # Step 7: Delete if configured
            if self.config['auto_delete'] and not self.config['dry_run']:
                self._delete_marked_products()
            
            # Step 8: Final report
            self._generate_final_report()
            
        except KeyboardInterrupt:
            logger.warning("\nPipeline interrupted by user")
            self._save_state()
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            self._save_state()
            raise
        finally:
            elapsed = time.time() - self.start_time
            logger.info(f"\nTotal processing time: {elapsed/60:.1f} minutes")
            self.driver.close()
    
    def _analyze_initial_state(self):
        """Analyze and report current database state"""
        logger.info("\n1. ANALYZING CURRENT STATE")
        logger.info("-"*50)
        
        with self.driver.session() as session:
            # Overall statistics
            stats = session.run("""
                MATCH (p:Product)
                RETURN 
                    count(p) as total,
                    sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as has_fashion_label,
                    sum(CASE WHEN p.is_fashion = true THEN 1 ELSE 0 END) as is_fashion_true,
                    sum(CASE WHEN p.ready_for_embedding = true THEN 1 ELSE 0 END) as ready_for_embedding,
                    sum(CASE WHEN p:MarkedForRemoval THEN 1 ELSE 0 END) as marked_removal,
                    sum(CASE WHEN p:NeedsAI THEN 1 ELSE 0 END) as needs_ai,
                    sum(CASE WHEN p.duplicate_of IS NOT NULL THEN 1 ELSE 0 END) as marked_duplicate,
                    sum(CASE WHEN p.title IS NULL THEN 1 ELSE 0 END) as missing_title
            """).single()
            
            self.stats['initial'] = dict(stats)
            
            # Display statistics
            data = [
                ["Total products", f"{stats['total']:,}"],
                ["Has :FashionProduct label", f"{stats['has_fashion_label']:,}"],
                ["Has is_fashion=true", f"{stats['is_fashion_true']:,}"],
                ["Ready for embedding", f"{stats['ready_for_embedding']:,}"],
                ["Marked for removal", f"{stats['marked_removal']:,}"],
                ["Needs AI verification", f"{stats['needs_ai']:,}"],
                ["Marked as duplicate", f"{stats['marked_duplicate']:,}"],
                ["Missing title", f"{stats['missing_title']:,}"]
            ]
            
            print("\n" + tabulate(data, headers=["Metric", "Count"], tablefmt="grid"))
            
            # Duplicate preview
            if self.config['mark_duplicates']:
                dup_stats = session.run("""
                    MATCH (p:Product)
                    WHERE p.title IS NOT NULL
                    WITH p.title as title, count(p) as count
                    WHERE count > 1
                    RETURN count(title) as duplicate_titles,
                           sum(count) as total_duplicates,
                           sum(count - 1) as redundant_products
                """).single()
                
                if dup_stats['duplicate_titles']:
                    logger.info(f"\nDuplicate preview:")
                    logger.info(f"  Titles with duplicates: {dup_stats['duplicate_titles']:,}")
                    logger.info(f"  Total duplicate products: {dup_stats['total_duplicates']:,}")
                    logger.info(f"  Could remove: {dup_stats['redundant_products']:,}")
                    logger.info(f"  Potential savings: ${dup_stats['redundant_products'] * 0.000006:.2f}")
    
    def _get_user_confirmation(self):
        """Get user confirmation to proceed"""
        logger.info("\n" + "="*50)
        logger.info("CLEANUP PLAN:")
        
        steps = []
        if self.config['update_existing']:
            steps.append("Update existing FashionProduct labels")
        steps.append("Mark non-fashion products for removal")
        steps.append("Mark fashion products and set properties")
        steps.append("Mark ambiguous products for AI verification")
        
        if self.config['mark_duplicates']:
            steps.append(f"Mark duplicates ({self.config['duplicate_strategy']} strategy)")
        
        if self.config['auto_delete']:
            steps.append("DELETE products marked for removal")
            if self.config['delete_duplicates']:
                steps.append("DELETE duplicate products")
        
        for i, step in enumerate(steps, 1):
            logger.info(f"{i}. {step}")
        
        logger.info("="*50)
        
        if self.config['dry_run']:
            logger.info("\n🔍 DRY RUN MODE - No changes will be made")
            return True
        
        response = input("\nProceed with cleanup? (yes/no): ")
        return response.lower() in ['yes', 'y']
    
    def _update_existing_fashion_products(self):
        """Update products that already have :FashionProduct label"""
        logger.info("\n2. UPDATING EXISTING FASHION PRODUCTS")
        logger.info("-"*50)
        
        total_updated = 0
        
        with self.driver.session() as session:
            # Count products needing update
            count_result = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.is_fashion IS NULL
                   OR p.ready_for_embedding IS NULL
                RETURN count(p) as count
            """).single()
            
            need_update = count_result['count']
            
            if need_update == 0:
                logger.info("No existing FashionProduct labels need updating")
                return
            
            logger.info(f"Found {need_update:,} FashionProduct nodes needing property updates")
            
            if self.config['dry_run']:
                logger.info(f"DRY RUN: Would update {need_update:,} products")
                return
            
            # Update in batches
            with tqdm(total=need_update, desc="Updating properties") as pbar:
                while total_updated < need_update:
                    result = session.run("""
                        MATCH (p:Product:FashionProduct)
                        WHERE p.is_fashion IS NULL
                           OR p.ready_for_embedding IS NULL
                        WITH p LIMIT $batch_size
                        SET p.is_fashion = true,
                            p.fashion_confidence = COALESCE(p.fashion_confidence, 0.95),
                            p.ready_for_embedding = true,
                            p.classification_source = COALESCE(p.classification_source, 'keyword_based'),
                            p.classified_at = COALESCE(p.classified_at, datetime())
                        RETURN count(p) as count
                    """, batch_size=self.config['batch_size']).single()
                    
                    batch_updated = result['count']
                    total_updated += batch_updated
                    pbar.update(batch_updated)
                    
                    if batch_updated == 0:
                        break
        
        self.stats['updated_existing'] = total_updated
        logger.info(f"✓ Updated {total_updated:,} existing FashionProduct nodes")
    
    def _mark_products_by_category(self):
        """Mark products based on category keywords"""
        logger.info("\n3. CLASSIFYING PRODUCTS BY CATEGORY")
        logger.info("-"*50)
        
        # Mark for removal
        self._mark_for_removal()
        
        # Mark as fashion
        self._mark_as_fashion()
        
        # Mark needs AI
        self._mark_needs_ai()
    
    def _mark_for_removal(self):
        """Mark non-fashion products for removal"""
        logger.info("\nMarking non-fashion products...")
        
        total_marked = 0
        
        for pattern in tqdm(self.definitely_remove, desc="Removal patterns"):
            with self.driver.session() as session:
                while True:
                    if self.config['dry_run']:
                        result = session.run("""
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                              AND NOT p:MarkedForRemoval
                              AND NOT p:FashionProduct
                            RETURN count(p) as count
                        """, pattern=pattern).single()
                        
                        total_marked += result['count']
                        break
                    else:
                        result = session.run("""
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                              AND NOT p:MarkedForRemoval
                              AND NOT p:FashionProduct
                            WITH p, c LIMIT $batch_size
                            SET p:MarkedForRemoval
                            SET p.removal_reason = 'Category: ' + c.name
                            SET p.marked_at = datetime()
                            REMOVE p:NeedsAI
                            RETURN count(p) as count
                        """, pattern=pattern, batch_size=self.config['batch_size']).single()
                        
                        if result['count'] == 0:
                            break
                        total_marked += result['count']
        
        self.stats['marked_removal'] = total_marked
        logger.info(f"✓ Marked {total_marked:,} products for removal")
    
    def _mark_as_fashion(self):
        """Mark fashion products with all necessary properties"""
        logger.info("\nMarking fashion products...")
        
        total_marked = 0
        
        for pattern in tqdm(self.definitely_fashion, desc="Fashion patterns"):
            with self.driver.session() as session:
                while True:
                    if self.config['dry_run']:
                        result = session.run("""
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                              AND NOT p:MarkedForRemoval
                              AND NOT p:FashionProduct
                            RETURN count(p) as count
                        """, pattern=pattern).single()
                        
                        total_marked += result['count']
                        break
                    else:
                        result = session.run("""
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                              AND NOT p:MarkedForRemoval
                              AND NOT p:FashionProduct
                              AND NOT (toLower(c.name) CONTAINS 'equipment' OR 
                                       toLower(c.name) CONTAINS 'supplies')
                            WITH p, c LIMIT $batch_size
                            SET p:FashionProduct
                            SET p.is_fashion = true
                            SET p.fashion_confidence = 0.95
                            SET p.ready_for_embedding = true
                            SET p.classification_source = 'keyword_based'
                            SET p.classification_reason = 'Category: ' + c.name
                            SET p.classified_at = datetime()
                            REMOVE p:NeedsAI
                            RETURN count(p) as count
                        """, pattern=pattern, batch_size=self.config['batch_size']).single()
                        
                        if result['count'] == 0:
                            break
                        total_marked += result['count']
        
        self.stats['marked_fashion'] = total_marked
        logger.info(f"✓ Marked {total_marked:,} products as fashion")
    
    def _mark_needs_ai(self):
        """Mark ambiguous products for AI verification"""
        logger.info("\nMarking ambiguous products...")
        
        total_marked = 0
        
        for pattern in tqdm(self.needs_ai_verification, desc="AI patterns"):
            with self.driver.session() as session:
                while True:
                    if self.config['dry_run']:
                        result = session.run("""
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                              AND NOT p:MarkedForRemoval
                              AND NOT p:FashionProduct
                              AND NOT p:NeedsAI
                            RETURN count(p) as count
                        """, pattern=pattern).single()
                        
                        total_marked += result['count']
                        break
                    else:
                        result = session.run("""
                            MATCH (p:Product)-[:IN_CATEGORY]->(c:Category)
                            WHERE toLower(c.name) CONTAINS toLower($pattern)
                              AND NOT p:MarkedForRemoval
                              AND NOT p:FashionProduct
                              AND NOT p:NeedsAI
                            WITH p, c LIMIT $batch_size
                            SET p:NeedsAI
                            SET p.ai_reason = 'Ambiguous category: ' + c.name
                            SET p.needs_ai_at = datetime()
                            RETURN count(p) as count
                        """, pattern=pattern, batch_size=self.config['batch_size']).single()
                        
                        if result['count'] == 0:
                            break
                        total_marked += result['count']
        
        self.stats['marked_needs_ai'] = total_marked
        logger.info(f"✓ Marked {total_marked:,} products for AI verification")
    
    def _handle_duplicates(self):
        """Handle duplicate products based on strategy"""
        logger.info("\n4. HANDLING DUPLICATES")
        logger.info("-"*50)
        
        strategy = self.config['duplicate_strategy']
        logger.info(f"Using {strategy} deduplication strategy")
        
        with self.driver.session() as session:
            # Analyze duplicates
            dup_stats = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.title IS NOT NULL
                  AND NOT p:MarkedForRemoval
                WITH p.title as title, count(p) as count
                WHERE count > 1
                RETURN sum(count) as total_duplicates,
                       count(title) as unique_titles,
                       sum(count - 1) as redundant_products
            """).single()
            
            if not dup_stats['total_duplicates']:
                logger.info("No duplicates found!")
                return
            
            logger.info(f"Found {dup_stats['total_duplicates']:,} products with duplicate titles")
            logger.info(f"Unique titles that are duplicated: {dup_stats['unique_titles']:,}")
            logger.info(f"Potential products to skip: {dup_stats['redundant_products']:,}")
            logger.info(f"Potential savings: ${dup_stats['redundant_products'] * 0.000006:.2f}")
            
            if self.config['dry_run']:
                logger.info("DRY RUN - Would mark duplicates but not making changes")
                self.stats['marked_duplicate'] = dup_stats['redundant_products']
                return
            
            # Apply deduplication strategy
            if strategy == 'aggressive':
                marked = self._deduplicate_aggressive(session)
            elif strategy == 'smart':
                marked = self._deduplicate_smart(session)
            else:  # conservative
                marked = self._deduplicate_conservative(session)
            
            self.stats['marked_duplicate'] = marked
            logger.info(f"✓ Marked {marked:,} products as duplicates")
    
    def _deduplicate_aggressive(self, session):
        """Keep only most popular product per title"""
        logger.info("Aggressive deduplication: one per title...")
        
        marked = 0
        batch_size = 1000
        
        with tqdm(desc="Processing duplicates") as pbar:
            while True:
                result = session.run("""
                    MATCH (p:Product:FashionProduct)
                    WHERE p.title IS NOT NULL
                      AND p.duplicate_of IS NULL
                      AND p.is_primary IS NULL
                      AND NOT p:MarkedForRemoval
                    WITH p.title as title, collect(p) as products
                    WHERE size(products) > 1
                    WITH title, products LIMIT $batch_size
                    UNWIND products as product
                    WITH title, product
                    ORDER BY title, product.visited_num DESC, product.id
                    WITH title, collect(product) as sorted_products
                    // First is primary, rest are duplicates
                    WITH title, sorted_products[0] as primary, sorted_products[1..] as duplicates
                    SET primary.is_primary = true
                    WITH title, primary, duplicates
                    UNWIND duplicates as dup
                    SET dup.duplicate_of = primary.id,
                        dup.ready_for_embedding = false,
                        dup.skip_embedding = true
                    RETURN count(DISTINCT title) as groups_processed,
                           count(dup) as duplicates_marked
                """, batch_size=batch_size).single()
                
                groups = result['groups_processed']
                dups = result['duplicates_marked']
                
                if groups == 0:
                    break
                
                marked += dups
                pbar.update(groups)
        
        return marked
    
    def _deduplicate_smart(self, session):
        """Keep one per title+brand combination"""
        logger.info("Smart deduplication: one per title+brand...")
        
        marked = 0
        batch_size = 1000
        
        with tqdm(desc="Processing duplicates") as pbar:
            while True:
                result = session.run("""
                    MATCH (p:Product:FashionProduct)
                    WHERE p.title IS NOT NULL
                      AND p.duplicate_of IS NULL
                      AND p.is_primary IS NULL
                      AND NOT p:MarkedForRemoval
                    OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                    WITH p.title + '||' + COALESCE(b.name, 'NO_BRAND') as group_key,
                         collect(p) as products
                    WHERE size(products) > 1
                    WITH group_key, products LIMIT $batch_size
                    UNWIND products as product
                    WITH group_key, product
                    ORDER BY group_key, product.visited_num DESC, product.id
                    WITH group_key, collect(product) as sorted_products
                    WITH group_key, sorted_products[0] as primary, sorted_products[1..] as duplicates
                    SET primary.is_primary = true
                    WITH group_key, primary, duplicates
                    UNWIND duplicates as dup
                    SET dup.duplicate_of = primary.id,
                        dup.ready_for_embedding = false,
                        dup.skip_embedding = true
                    RETURN count(DISTINCT group_key) as groups_processed,
                           count(dup) as duplicates_marked
                """, batch_size=batch_size).single()
                
                groups = result['groups_processed']
                dups = result['duplicates_marked']
                
                if groups == 0:
                    break
                
                marked += dups
                pbar.update(groups)
        
        return marked
    
    def _deduplicate_conservative(self, session):
        """Only mark exact duplicates (same title, brand, price)"""
        logger.info("Conservative deduplication: exact matches only...")
        
        marked = 0
        batch_size = 1000
        
        with tqdm(desc="Processing duplicates") as pbar:
            while True:
                result = session.run("""
                    MATCH (p:Product:FashionProduct)
                    WHERE p.title IS NOT NULL
                      AND p.price IS NOT NULL
                      AND p.duplicate_of IS NULL
                      AND p.is_primary IS NULL
                      AND NOT p:MarkedForRemoval
                    OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                    WITH p.title + '||' + COALESCE(b.name, 'NO_BRAND') + '||' + toString(p.price) as group_key,
                         collect(p) as products
                    WHERE size(products) > 1
                    WITH group_key, products LIMIT $batch_size
                    WITH group_key, products[0] as primary, products[1..] as duplicates
                    SET primary.is_primary = true
                    WITH group_key, primary, duplicates
                    UNWIND duplicates as dup
                    SET dup.duplicate_of = primary.id,
                        dup.ready_for_embedding = false,
                        dup.skip_embedding = true
                    RETURN count(DISTINCT group_key) as groups_processed,
                           count(dup) as duplicates_marked
                """, batch_size=batch_size).single()
                
                groups = result['groups_processed']
                dups = result['duplicates_marked']
                
                if groups == 0:
                    break
                
                marked += dups
                pbar.update(groups)
        
        return marked
    
    def _mark_remaining_uncategorized(self):
        """Mark any remaining uncategorized products"""
        logger.info("\n5. HANDLING REMAINING UNCATEGORIZED")
        logger.info("-"*50)
        
        with self.driver.session() as session:
            count_result = session.run("""
                MATCH (p:Product)
                WHERE NOT p:MarkedForRemoval 
                  AND NOT p:FashionProduct 
                  AND NOT p:NeedsAI
                RETURN count(p) as count
            """).single()
            
            remaining = count_result['count']
            
            if remaining == 0:
                logger.info("No uncategorized products remaining!")
                return
            
            logger.info(f"Found {remaining:,} uncategorized products")
            
            if self.config['dry_run']:
                logger.info("DRY RUN - Would mark for AI verification")
                self.stats['marked_uncategorized'] = remaining
                return
            
            # Mark them for AI
            marked = 0
            with tqdm(total=remaining, desc="Marking uncategorized") as pbar:
                while marked < remaining:
                    result = session.run("""
                        MATCH (p:Product)
                        WHERE NOT p:MarkedForRemoval 
                          AND NOT p:FashionProduct 
                          AND NOT p:NeedsAI
                        WITH p LIMIT $batch_size
                        SET p:NeedsAI
                        SET p.ai_reason = 'Uncategorized product'
                        SET p.needs_ai_at = datetime()
                        RETURN count(p) as count
                    """, batch_size=self.config['batch_size']).single()
                    
                    batch_marked = result['count']
                    marked += batch_marked
                    pbar.update(batch_marked)
                    
                    if batch_marked == 0:
                        break
            
            self.stats['marked_uncategorized'] = marked
            self.stats['marked_needs_ai'] += marked
            logger.info(f"✓ Marked {marked:,} uncategorized products for AI")
    
    def _delete_marked_products(self):
        """Delete products marked for removal and optionally duplicates"""
        logger.info("\n6. DELETING PRODUCTS")
        logger.info("-"*50)
        
        with self.driver.session() as session:
            # Count what needs deletion
            removal_count = session.run("""
                MATCH (p:MarkedForRemoval)
                RETURN count(p) as count
            """).single()['count']
            
            duplicate_count = 0
            if self.config['delete_duplicates']:
                duplicate_count = session.run("""
                    MATCH (p:Product)
                    WHERE p.duplicate_of IS NOT NULL
                    RETURN count(p) as count
                """).single()['count']
            
            total_to_delete = removal_count + duplicate_count
            
            if total_to_delete == 0:
                logger.info("No products to delete!")
                return
            
            logger.info(f"Products marked for removal: {removal_count:,}")
            if self.config['delete_duplicates']:
                logger.info(f"Duplicate products: {duplicate_count:,}")
            logger.info(f"Total to delete: {total_to_delete:,}")
            
            confirm = input(f"\n⚠️  DELETE {total_to_delete:,} products? Type 'DELETE' to confirm: ")
            
            if confirm != 'DELETE':
                logger.info("Deletion cancelled")
                return
            
            # Delete marked for removal
            if removal_count > 0:
                deleted_removal = self._delete_by_condition(
                    "MATCH (p:MarkedForRemoval)",
                    "non-fashion products"
                )
                self.stats['deleted_removal'] = deleted_removal
            
            # Delete duplicates
            if duplicate_count > 0 and self.config['delete_duplicates']:
                deleted_dups = self._delete_by_condition(
                    "MATCH (p:Product) WHERE p.duplicate_of IS NOT NULL",
                    "duplicate products"
                )
                self.stats['deleted_duplicates'] = deleted_dups
    
    def _delete_by_condition(self, match_query, description):
        """Delete products matching a condition"""
        deleted = 0
        
        with self.driver.session() as session:
            with tqdm(desc=f"Deleting {description}") as pbar:
                while True:
                    result = session.run(f"""
                        {match_query}
                        WITH p LIMIT $batch_size
                        DETACH DELETE p
                        RETURN count(p) as count
                    """, batch_size=self.config['batch_size']).single()
                    
                    batch = result['count']
                    deleted += batch
                    pbar.update(batch)
                    
                    if batch == 0:
                        break
        
        logger.info(f"✓ Deleted {deleted:,} {description}")
        return deleted
    
    def _generate_final_report(self):
        """Generate comprehensive final report"""
        logger.info("\n" + "="*80)
        logger.info("FINAL REPORT")
        logger.info("="*80)
        
        with self.driver.session() as session:
            # Get final state
            final_stats = session.run("""
                MATCH (p:Product)
                RETURN 
                    count(p) as total,
                    sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as fashion_products,
                    sum(CASE WHEN p.is_fashion = true THEN 1 ELSE 0 END) as is_fashion_true,
                    sum(CASE WHEN p.ready_for_embedding = true 
                             AND p.duplicate_of IS NULL 
                             AND p.embedding_id IS NULL THEN 1 ELSE 0 END) as ready_to_embed,
                    sum(CASE WHEN p:NeedsAI THEN 1 ELSE 0 END) as needs_ai,
                    sum(CASE WHEN p.duplicate_of IS NOT NULL THEN 1 ELSE 0 END) as marked_duplicate
            """).single()
            
            # Summary table
            summary_data = [
                ["Initial products", f"{self.stats.get('initial', {}).get('total', 0):,}"],
                ["", ""],
                ["ACTIONS TAKEN:", ""],
                ["Updated existing fashion", f"{self.stats.get('updated_existing', 0):,}"],
                ["Marked for removal", f"{self.stats.get('marked_removal', 0):,}"],
                ["Marked as fashion", f"{self.stats.get('marked_fashion', 0):,}"],
                ["Marked needs AI", f"{self.stats.get('marked_needs_ai', 0):,}"],
                ["Marked as duplicate", f"{self.stats.get('marked_duplicate', 0):,}"],
                ["Deleted non-fashion", f"{self.stats.get('deleted_removal', 0):,}"],
                ["Deleted duplicates", f"{self.stats.get('deleted_duplicates', 0):,}"],
                ["", ""],
                ["FINAL STATE:", ""],
                ["Total products", f"{final_stats['total']:,}"],
                ["Fashion products", f"{final_stats['fashion_products']:,}"],
                ["Ready for embedding", f"{final_stats['ready_to_embed']:,}"],
                ["Need AI classification", f"{final_stats['needs_ai']:,}"],
            ]
            
            print("\n" + tabulate(summary_data, headers=["Metric", "Count"], tablefmt="grid"))
            
            # Cost analysis
            embedding_cost = final_stats['ready_to_embed'] * 0.000006
            ai_cost = final_stats['needs_ai'] * 0.000015
            saved_by_dedup = self.stats.get('marked_duplicate', 0) * 0.000006
            
            logger.info(f"\n💰 COST ANALYSIS:")
            logger.info(f"  Embedding cost: ${embedding_cost:.2f} ({final_stats['ready_to_embed']:,} products)")
            logger.info(f"  AI classification cost: ${ai_cost:.2f} ({final_stats['needs_ai']:,} products)")
            logger.info(f"  Saved by deduplication: ${saved_by_dedup:.2f}")
            logger.info(f"  Total estimated cost: ${embedding_cost + ai_cost:.2f}")
            
            # Performance metrics
            elapsed = time.time() - self.start_time
            products_per_second = self.stats.get('initial', {}).get('total', 0) / elapsed
            
            logger.info(f"\n⚡ PERFORMANCE:")
            logger.info(f"  Total time: {elapsed/60:.1f} minutes")
            logger.info(f"  Processing speed: {products_per_second:.0f} products/second")
            
            # Save detailed report
            report_file = os.path.join(log_dir, f'cleanup_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            report_data = {
                'timestamp': datetime.now().isoformat(),
                'config': self.config,
                'stats': dict(self.stats),
                'final_state': dict(final_stats),
                'costs': {
                    'embedding': embedding_cost,
                    'ai_classification': ai_cost,
                    'saved_by_deduplication': saved_by_dedup,
                    'total': embedding_cost + ai_cost
                },
                'performance': {
                    'total_time_seconds': elapsed,
                    'products_per_second': products_per_second
                }
            }
            
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            logger.info(f"\n📄 Detailed report saved to: {report_file}")
            logger.info(f"📋 Log file: {log_file}")
            
            # Next steps
            logger.info(f"\n🎯 NEXT STEPS:")
            if final_stats['ready_to_embed'] > 0:
                logger.info(f"1. Run embedding pipeline for {final_stats['ready_to_embed']:,} products")
                logger.info(f"   python fashion_embeddings_pipeline.py")
            if final_stats['needs_ai'] > 0:
                logger.info(f"2. Run AI classification for {final_stats['needs_ai']:,} ambiguous products")
            logger.info(f"3. Monitor system performance and adjust as needed")


def main():
    """Main execution with command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Neo4j Fashion Product Cleanup Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run with aggressive deduplication
  python neo4j_cleanup.py --duplicate-strategy aggressive --dry-run
  
  # Full cleanup with duplicate deletion
  python neo4j_cleanup.py --auto-delete --delete-duplicates
  
  # Conservative approach
  python neo4j_cleanup.py --duplicate-strategy conservative --batch-size 2000
  
  # Skip duplicate detection entirely
  python neo4j_cleanup.py --skip-duplicates
        """
    )
    
    # Main options
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='Batch size for processing (default: 5000)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without making changes')
    
    # Classification options
    parser.add_argument('--skip-existing-update', action='store_true',
                        help='Skip updating existing FashionProduct labels')
    
    # Duplicate handling
    parser.add_argument('--skip-duplicates', action='store_true',
                        help='Skip duplicate detection entirely')
    parser.add_argument('--duplicate-strategy', 
                        choices=['aggressive', 'smart', 'conservative'],
                        default='smart',
                        help='Duplicate handling strategy (default: smart)')
    
    # Deletion options
    parser.add_argument('--auto-delete', action='store_true',
                        help='Automatically delete marked products')
    parser.add_argument('--delete-duplicates', action='store_true',
                        help='Also delete duplicate products')
    
    args = parser.parse_args()
    
    # Build configuration
    config = {
        'batch_size': args.batch_size,
        'dry_run': args.dry_run,
        'update_existing': not args.skip_existing_update,
        'mark_duplicates': not args.skip_duplicates,
        'duplicate_strategy': args.duplicate_strategy,
        'auto_delete': args.auto_delete,
        'delete_duplicates': args.delete_duplicates,
        'process_uncategorized': True
    }
    
    # Show configuration
    logger.info("Configuration:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    
    # Run pipeline
    cleaner = FashionProductCleanup(config)
    cleaner.run_full_pipeline()


if __name__ == "__main__":
    main()