#!/usr/bin/env python3
"""
Deep duplicate analysis: Identifies title duplicates then analyzes similarity across all fields
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from collections import defaultdict
import hashlib
from difflib import SequenceMatcher

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
    auth=(os.getenv('NEO4J_USERNAME', 'neo4j'), 
          os.getenv('NEO4J_PASSWORD', 'shopari1234'))
)


class DuplicateAnalyzer:
    def __init__(self):
        self.stats = defaultdict(int)
        
    def analyze(self):
        """Run complete duplicate analysis"""
        print("="*80)
        print("DEEP DUPLICATE ANALYSIS")
        print("Starting with title matches, then analyzing field similarities")
        print("="*80)
        
        # Step 1: Overview
        self._get_overview()
        
        # Step 2: Analyze duplicate patterns
        self._analyze_duplicate_patterns()
        
        # Step 3: Deep dive into specific examples
        self._deep_dive_examples()
        
        # Step 4: Field similarity analysis
        self._field_similarity_analysis()
        
        # Step 5: Recommendations
        self._generate_recommendations()
    
    def _get_overview(self):
        """Get basic duplicate statistics"""
        print("\n1. DUPLICATE OVERVIEW")
        print("-"*50)
        
        with driver.session() as session:
            # Basic stats
            stats = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.title IS NOT NULL
                WITH count(p) as total_products, 
                     count(DISTINCT p.title) as unique_titles
                RETURN total_products, 
                       unique_titles,
                       total_products - unique_titles as duplicate_products,
                       toFloat(total_products - unique_titles) / total_products * 100 as dup_percentage
            """).single()
            
            print(f"Total fashion products: {stats['total_products']:,}")
            print(f"Unique titles: {stats['unique_titles']:,}")
            print(f"Products with duplicate titles: {stats['duplicate_products']:,}")
            print(f"Duplication rate: {stats['dup_percentage']:.1f}%")
            
            # Distribution of duplicates
            print("\nDuplicate distribution:")
            dist = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.title IS NOT NULL
                WITH p.title as title, count(p) as count
                RETURN 
                    CASE 
                        WHEN count = 1 THEN '1 (unique)'
                        WHEN count = 2 THEN '2 (pair)'
                        WHEN count <= 5 THEN '3-5'
                        WHEN count <= 10 THEN '6-10'
                        WHEN count <= 50 THEN '11-50'
                        ELSE '50+'
                    END as range,
                    count(title) as title_count,
                    sum(count) as product_count
                ORDER BY 
                    CASE range
                        WHEN '1 (unique)' THEN 1
                        WHEN '2 (pair)' THEN 2
                        WHEN '3-5' THEN 3
                        WHEN '6-10' THEN 4
                        WHEN '11-50' THEN 5
                        ELSE 6
                    END
            """)
            
            for r in dist:
                print(f"  {r['range']:12} copies: {r['title_count']:8,} titles ({r['product_count']:,} products)")
    
    def _analyze_duplicate_patterns(self):
        """Analyze patterns in duplicates"""
        print("\n\n2. DUPLICATE PATTERNS")
        print("-"*50)
        
        with driver.session() as session:
            # Pattern 1: Same title, same brand
            print("\nPattern Analysis:")
            
            # Get sample of duplicated titles
            sample_titles = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.title IS NOT NULL
                WITH p.title as title, count(p) as count
                WHERE count >= 5 AND count <= 20
                RETURN title
                LIMIT 100
            """)
            
            patterns = {
                'identical_all': 0,
                'same_brand_diff_price': 0,
                'diff_brand_same_price': 0,
                'diff_brand_diff_price': 0,
                'has_variants': 0
            }
            
            for title_record in sample_titles:
                title = title_record['title']
                
                # Analyze this title's duplicates
                analysis = session.run("""
                    MATCH (p:Product:FashionProduct {title: $title})
                    OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                    RETURN 
                        count(DISTINCT b.name) as brand_count,
                        count(DISTINCT p.price) as price_count,
                        count(DISTINCT p.description) as desc_count,
                        count(p) as total,
                        collect(DISTINCT p.description)[0..3] as sample_descriptions
                """, title=title).single()
                
                # Categorize pattern
                if analysis['brand_count'] <= 1 and analysis['price_count'] == 1 and analysis['desc_count'] == 1:
                    patterns['identical_all'] += 1
                elif analysis['brand_count'] <= 1 and analysis['price_count'] > 1:
                    patterns['same_brand_diff_price'] += 1
                elif analysis['brand_count'] > 1 and analysis['price_count'] == 1:
                    patterns['diff_brand_same_price'] += 1
                else:
                    patterns['diff_brand_diff_price'] += 1
                
                # Check for variants
                descs = analysis['sample_descriptions'] or []
                if any(desc and any(word in desc.lower() for word in ['size', 'color', 'colour', 'xl', 'medium', 'small']) 
                       for desc in descs):
                    patterns['has_variants'] += 1
            
            print(f"\nFrom sample of 100 duplicate groups:")
            print(f"  Identical (all fields same): {patterns['identical_all']}")
            print(f"  Same brand, different prices: {patterns['same_brand_diff_price']}")
            print(f"  Different brands, same price: {patterns['diff_brand_same_price']}")
            print(f"  Different brands & prices: {patterns['diff_brand_diff_price']}")
            print(f"  Likely size/color variants: {patterns['has_variants']}")
    
    def _deep_dive_examples(self):
        """Deep dive into specific duplicate examples"""
        print("\n\n3. DEEP DIVE EXAMPLES")
        print("-"*50)
        
        with driver.session() as session:
            # Get 3 different types of duplicates
            examples = [
                ("High duplication", 50, 100),
                ("Medium duplication", 10, 20),
                ("Low duplication", 2, 5)
            ]
            
            for example_type, min_count, max_count in examples:
                print(f"\n{example_type} example:")
                print("-"*30)
                
                # Get a sample title
                sample = session.run("""
                    MATCH (p:Product:FashionProduct)
                    WHERE p.title IS NOT NULL
                    WITH p.title as title, count(p) as count
                    WHERE count >= $min AND count <= $max
                    RETURN title, count
                    ORDER BY count DESC
                    LIMIT 1
                """, min=min_count, max=max_count).single()
                
                if not sample:
                    continue
                
                title = sample['title']
                print(f"Title: {title}")
                print(f"Instances: {sample['count']}")
                
                # Get all instances
                instances = session.run("""
                    MATCH (p:Product:FashionProduct {title: $title})
                    OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                    OPTIONAL MATCH (p)-[:IN_CATEGORY]->(c:Category)
                    RETURN 
                        p.id as id,
                        p.description as description,
                        p.price as price,
                        b.name as brand,
                        c.name as category,
                        p.visited_num as visits
                    ORDER BY p.visited_num DESC NULLS LAST
                    LIMIT 5
                """, title=title)
                
                products = list(instances)
                
                # Compare first product to others
                if products:
                    base = products[0]
                    print(f"\nBase product:")
                    print(f"  Brand: {base['brand'] or 'None'}")
                    print(f"  Price: ${base['price']:.2f}" if base['price'] else "  Price: None")
                    print(f"  Category: {base['category'] or 'None'}")
                    
                    # Compare others
                    for i, p in enumerate(products[1:], 1):
                        print(f"\nVariation {i}:")
                        print(f"  Brand: {p['brand'] or 'None'} {'✓' if p['brand'] == base['brand'] else '✗'}")
                        print(f"  Price: ${p['price']:.2f} {'✓' if p['price'] == base['price'] else '✗'}" if p['price'] else "  Price: None")
                        print(f"  Category: {p['category'] or 'None'} {'✓' if p['category'] == base['category'] else '✗'}")
                        
                        # Description similarity
                        if base['description'] and p['description']:
                            similarity = SequenceMatcher(None, base['description'], p['description']).ratio()
                            print(f"  Description similarity: {similarity*100:.1f}%")
    
    def _field_similarity_analysis(self):
        """Analyze field-level similarity across duplicates"""
        print("\n\n4. FIELD SIMILARITY ANALYSIS")
        print("-"*50)
        
        with driver.session() as session:
            # Check how often each field matches in duplicates
            print("\nChecking field consistency in duplicate groups...")
            
            # Sample analysis on moderate duplicates
            field_stats = session.run("""
                MATCH (p1:Product:FashionProduct)
                WHERE p1.title IS NOT NULL
                WITH p1.title as title, count(p1) as count
                WHERE count >= 5 AND count <= 20
                WITH title
                LIMIT 50
                MATCH (p:Product:FashionProduct {title: title})
                OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                WITH title,
                     count(p) as total,
                     count(DISTINCT b.name) as unique_brands,
                     count(DISTINCT p.price) as unique_prices,
                     count(DISTINCT p.description) as unique_descriptions,
                     count(DISTINCT p.category) as unique_categories
                RETURN 
                    avg(toFloat(unique_brands) / total) as avg_brand_variation,
                    avg(toFloat(unique_prices) / total) as avg_price_variation,
                    avg(toFloat(unique_descriptions) / total) as avg_desc_variation,
                    avg(toFloat(unique_categories) / total) as avg_cat_variation
            """).single()
            
            print(f"\nAverage uniqueness ratios (lower = more similar):")
            print(f"  Brands: {field_stats['avg_brand_variation']:.2%} unique")
            print(f"  Prices: {field_stats['avg_price_variation']:.2%} unique")
            print(f"  Descriptions: {field_stats['avg_desc_variation']:.2%} unique")
            print(f"  Categories: {field_stats['avg_cat_variation']:.2%} unique")
            
            # Find true duplicates (all fields match)
            print("\n\n5. TRUE DUPLICATES (all fields match)")
            print("-"*50)
            
            true_dups = session.run("""
                MATCH (p1:Product:FashionProduct)
                WHERE p1.title IS NOT NULL 
                  AND p1.description IS NOT NULL
                  AND p1.price IS NOT NULL
                WITH p1.title as title, count(p1) as count
                WHERE count > 1
                WITH title LIMIT 100
                MATCH (p:Product:FashionProduct {title: title})
                WHERE p.description IS NOT NULL AND p.price IS NOT NULL
                OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                WITH title, 
                     p.description as desc,
                     p.price as price,
                     b.name as brand,
                     count(p) as group_size
                WHERE group_size > 1
                RETURN title, desc, price, brand, group_size
                ORDER BY group_size DESC
                LIMIT 10
            """)
            
            true_dup_count = 0
            print("\nExamples of true duplicates (same title+desc+price+brand):")
            for r in true_dups:
                true_dup_count += 1
                print(f"\n  {r['title'][:60]}...")
                print(f"    Copies: {r['group_size']}")
                print(f"    Brand: {r['brand'] or 'None'}")
                print(f"    Price: ${r['price']:.2f}")
            
            if true_dup_count == 0:
                print("  No true duplicates found in sample!")
    
    def _generate_recommendations(self):
        """Generate recommendations based on analysis"""
        print("\n\n6. RECOMMENDATIONS")
        print("="*50)
        
        print("\n📊 Based on the analysis:")
        print("\n1. DUPLICATE TYPES in your data:")
        print("   - Marketplace listings (same product, different sellers)")
        print("   - Product variants (sizes/colors with same base title)")
        print("   - Some true duplicates from data imports")
        
        print("\n2. RECOMMENDED DEDUPLICATION STRATEGY:")
        print("   🎯 Use 'smart' deduplication (one per title+brand)")
        print("   This will:")
        print("   - Keep brand diversity")
        print("   - Remove redundant listings from same brand")
        print("   - Preserve marketplace competition")
        
        print("\n3. ESTIMATED IMPACT:")
        with driver.session() as session:
            impact = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.title IS NOT NULL
                  AND p.is_fashion = true
                  AND p.ready_for_embedding = true
                  AND p.embedding_id IS NULL
                OPTIONAL MATCH (p)-[:BY_BRAND]->(b:Brand)
                WITH p.title + '||' + COALESCE(b.name, 'NO_BRAND') as unique_key,
                     count(p) as copies
                RETURN 
                    sum(copies) as total_products,
                    count(unique_key) as unique_products,
                    sum(copies - 1) as products_to_skip
            """).single()
            
            if impact['total_products']:
                savings = impact['products_to_skip'] * 0.000006
                print(f"   - Current products to embed: {impact['total_products']:,}")
                print(f"   - After deduplication: {impact['unique_products']:,}")
                print(f"   - Products saved: {impact['products_to_skip']:,}")
                print(f"   - Cost savings: ${savings:.2f}")
                print(f"   - Time savings: ~{impact['products_to_skip']/40000:.1f} hours")
        
        print("\n4. NEXT STEPS:")
        print("   1. Run: python neo4j_cleanup.py --duplicate-strategy smart --dry-run")
        print("   2. Review the output")
        print("   3. Remove --dry-run to execute")
        print("   4. Then run embeddings on deduplicated data")
        
        print("\n" + "="*50)


if __name__ == "__main__":
    analyzer = DuplicateAnalyzer()
    try:
        analyzer.analyze()
    except Exception as e:
        print(f"\nError during analysis: {e}")
        print("\nTrying simplified analysis...")
        
        # Fallback to basic stats
        with driver.session() as session:
            basic = session.run("""
                MATCH (p:Product:FashionProduct)
                WHERE p.title IS NOT NULL
                WITH p.title as title, count(p) as count
                WHERE count > 1
                RETURN 
                    count(title) as duplicate_groups,
                    sum(count) as total_duplicates,
                    avg(count) as avg_copies_per_title,
                    max(count) as max_copies
            """).single()
            
            print(f"\nBASIC STATS:")
            print(f"Duplicate groups: {basic['duplicate_groups']:,}")
            print(f"Total duplicate products: {basic['total_duplicates']:,}")
            print(f"Average copies per title: {basic['avg_copies_per_title']:.1f}")
            print(f"Maximum copies of one title: {basic['max_copies']:,}")
    
    finally:
        driver.close()