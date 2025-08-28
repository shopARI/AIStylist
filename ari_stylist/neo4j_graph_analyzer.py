#!/usr/bin/env python3
"""
Neo4j Graph Stats Analyzer
Comprehensive analysis of product data quality and readiness
"""

import os
from neo4j import GraphDatabase
from datetime import datetime
from tabulate import tabulate
import json
from dotenv import load_dotenv

load_dotenv()

class GraphStatsAnalyzer:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            #os.getenv('NEO4J_URL', 'bolt://34.135.40.119:7687'),
            os.getenv('NEO4J_URL'),
            auth=(os.getenv('NEO4J_USERNAME'), 
                  os.getenv('NEO4J_PASSWORD'))
        )
        self.stats = {}
    
    def run_analysis(self):
        """Run comprehensive analysis"""
        print("="*80)
        print("NEO4J GRAPH COMPREHENSIVE ANALYSIS")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        with self.driver.session() as session:
            # 1. TOTAL COUNTS
            print("\n1. BASIC COUNTS")
            print("-"*50)
            
            total_products = session.run("MATCH (p:Product) RETURN count(p) as count").single()['count']
            print(f"Total Product nodes: {total_products:,}")
            
            # Label combinations
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    CASE 
                        WHEN p:FashionProduct THEN 'Product + FashionProduct'
                        ELSE 'Product only'
                    END as labels,
                    count(p) as count
                ORDER BY count DESC
            """)
            
            print("\nLabel Distribution:")
            for r in result:
                print(f"  {r['labels']}: {r['count']:,}")
            
            # 2. DATA COMPLETENESS
            print("\n2. DATA COMPLETENESS")
            print("-"*50)
            
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    count(p) as total,
                    sum(CASE WHEN p.title IS NOT NULL THEN 1 ELSE 0 END) as has_title,
                    sum(CASE WHEN p.title IS NULL THEN 1 ELSE 0 END) as missing_title,
                    sum(CASE WHEN p.description IS NOT NULL THEN 1 ELSE 0 END) as has_description,
                    sum(CASE WHEN p.description IS NULL THEN 1 ELSE 0 END) as missing_description,
                    sum(CASE WHEN p.price IS NOT NULL THEN 1 ELSE 0 END) as has_price,
                    sum(CASE WHEN p.price IS NULL THEN 1 ELSE 0 END) as missing_price,
                    sum(CASE WHEN p.title IS NOT NULL AND p.description IS NOT NULL THEN 1 ELSE 0 END) as has_both_title_desc
            """).single()
            
            data = [
                ["Has Title", f"{result['has_title']:,}", f"{result['has_title']/result['total']*100:.1f}%"],
                ["Missing Title", f"{result['missing_title']:,}", f"{result['missing_title']/result['total']*100:.1f}%"],
                ["Has Description", f"{result['has_description']:,}", f"{result['has_description']/result['total']*100:.1f}%"],
                ["Missing Description", f"{result['missing_description']:,}", f"{result['missing_description']/result['total']*100:.1f}%"],
                ["Has Price", f"{result['has_price']:,}", f"{result['has_price']/result['total']*100:.1f}%"],
                ["Missing Price", f"{result['missing_price']:,}", f"{result['missing_price']/result['total']*100:.1f}%"],
                ["Has Both Title & Desc", f"{result['has_both_title_desc']:,}", f"{result['has_both_title_desc']/result['total']*100:.1f}%"]
            ]
            
            print(tabulate(data, headers=["Field", "Count", "Percentage"], tablefmt="grid"))
            
            # 3. CLASSIFICATION STATUS
            print("\n3. FASHION CLASSIFICATION STATUS")
            print("-"*50)
            
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    CASE
                        WHEN p.is_fashion IS NULL THEN 'Not Classified'
                        WHEN p.is_fashion = true THEN 'Classified as Fashion'
                        WHEN p.is_fashion = false THEN 'Classified as Non-Fashion'
                    END as status,
                    count(p) as count,
                    avg(p.fashion_confidence) as avg_confidence
                ORDER BY count DESC
            """)
            
            classification_data = []
            for r in result:
                classification_data.append([
                    r['status'],
                    f"{r['count']:,}",
                    f"{r['avg_confidence']:.3f}" if r['avg_confidence'] else "N/A"
                ])
            
            print(tabulate(classification_data, headers=["Classification Status", "Count", "Avg Confidence"], tablefmt="grid"))
            
            # Fashion confidence distribution
            print("\nFashion Confidence Distribution (for classified items):")
            result = session.run("""
                MATCH (p:Product)
                WHERE p.fashion_confidence IS NOT NULL
                RETURN 
                    CASE
                        WHEN p.fashion_confidence >= 0.9 THEN '0.9-1.0 (Very High)'
                        WHEN p.fashion_confidence >= 0.8 THEN '0.8-0.9 (High)'
                        WHEN p.fashion_confidence >= 0.7 THEN '0.7-0.8 (Good)'
                        WHEN p.fashion_confidence >= 0.5 THEN '0.5-0.7 (Medium)'
                        ELSE '< 0.5 (Low)'
                    END as confidence_range,
                    count(p) as count
                ORDER BY confidence_range
            """)
            
            for r in result:
                print(f"  {r['confidence_range']}: {r['count']:,}")
            
            # 4. EMBEDDING READINESS
            print("\n4. EMBEDDING READINESS")
            print("-"*50)
            
            result = session.run("""
                MATCH (p:Product)
                RETURN 
                    sum(CASE WHEN p.ready_for_embedding = true THEN 1 ELSE 0 END) as ready,
                    sum(CASE WHEN p.ready_for_embedding = false THEN 1 ELSE 0 END) as not_ready,
                    sum(CASE WHEN p.ready_for_embedding IS NULL THEN 1 ELSE 0 END) as not_set,
                    sum(CASE WHEN p.embedding_id IS NOT NULL THEN 1 ELSE 0 END) as already_embedded
            """).single()
            
            embedding_data = [
                ["Ready for Embedding", f"{result['ready']:,}"],
                ["Not Ready", f"{result['not_ready']:,}"],
                ["Not Set", f"{result['not_set']:,}"],
                ["Already Embedded", f"{result['already_embedded']:,}"]
            ]
            
            print(tabulate(embedding_data, headers=["Status", "Count"], tablefmt="grid"))
            
            # 5. QUALITY ISSUES
            print("\n5. POTENTIAL QUALITY ISSUES")
            print("-"*50)
            
            # Empty or very short titles
            result = session.run("""
                MATCH (p:Product)
                WHERE p.title IS NOT NULL
                RETURN 
                    sum(CASE WHEN trim(p.title) = '' THEN 1 ELSE 0 END) as empty_title,
                    sum(CASE WHEN size(p.title) < 5 THEN 1 ELSE 0 END) as very_short_title,
                    sum(CASE WHEN size(p.title) > 200 THEN 1 ELSE 0 END) as very_long_title
            """).single()
            
            print(f"Empty titles (whitespace only): {result['empty_title']:,}")
            print(f"Very short titles (< 5 chars): {result['very_short_title']:,}")
            print(f"Very long titles (> 200 chars): {result['very_long_title']:,}")
            
            # Potential duplicates (same title)
            dup_result = session.run("""
                MATCH (p:Product)
                WHERE p.title IS NOT NULL
                WITH p.title as title, count(p) as count
                WHERE count > 1
                RETURN sum(count) as total_duplicates, count(title) as unique_titles
            """).single()
            
            if dup_result['total_duplicates']:
                print(f"\nPotential duplicates (same title): {dup_result['total_duplicates']:,} products across {dup_result['unique_titles']:,} titles")
            
            # Test products
            test_result = session.run("""
                MATCH (p:Product)
                WHERE p.title IS NOT NULL 
                  AND (toLower(p.title) CONTAINS 'test' 
                       OR toLower(p.title) CONTAINS 'sample'
                       OR toLower(p.title) CONTAINS 'demo'
                       OR p.title =~ '.*TEST.*')
                RETURN count(p) as count
            """).single()
            
            print(f"Potential test products: {test_result['count']:,}")
            
            # 6. FASHION PRODUCTS READY FOR EMBEDDING
            print("\n6. FASHION PRODUCTS ANALYSIS")
            print("-"*50)
            
            # Fashion products with good data
            result = session.run("""
                MATCH (p:Product)
                WHERE p.is_fashion = true
                RETURN 
                    count(p) as total_fashion,
                    sum(CASE WHEN p.title IS NOT NULL THEN 1 ELSE 0 END) as with_title,
                    sum(CASE WHEN p.description IS NOT NULL THEN 1 ELSE 0 END) as with_description,
                    sum(CASE WHEN p.fashion_confidence >= 0.7 THEN 1 ELSE 0 END) as high_confidence,
                    sum(CASE WHEN p.fashion_confidence >= 0.9 THEN 1 ELSE 0 END) as very_high_confidence,
                    sum(CASE WHEN p:FashionProduct THEN 1 ELSE 0 END) as has_fashion_label,
                    sum(CASE WHEN p.embedding_id IS NOT NULL THEN 1 ELSE 0 END) as already_embedded
            """).single()
            
            fashion_data = [
                ["Total Fashion Products", f"{result['total_fashion']:,}"],
                ["With Title", f"{result['with_title']:,}"],
                ["With Description", f"{result['with_description']:,}"],
                ["Confidence >= 0.7", f"{result['high_confidence']:,}"],
                ["Confidence >= 0.9", f"{result['very_high_confidence']:,}"],
                ["Has :FashionProduct Label", f"{result['has_fashion_label']:,}"],
                ["Already Embedded", f"{result['already_embedded']:,}"]
            ]
            
            print(tabulate(fashion_data, headers=["Metric", "Count"], tablefmt="grid"))
            
            # 7. RECOMMENDED EMBEDDING CANDIDATES
            print("\n7. EMBEDDING RECOMMENDATIONS")
            print("-"*50)
            
            # Option 1: High confidence fashion only
            option1 = session.run("""
                MATCH (p:Product)
                WHERE p.is_fashion = true
                  AND p.fashion_confidence >= 0.8
                  AND p.title IS NOT NULL
                  AND p.embedding_id IS NULL
                RETURN count(p) as count
            """).single()['count']
            
            # Option 2: Medium confidence fashion
            option2 = session.run("""
                MATCH (p:Product)
                WHERE p.is_fashion = true
                  AND p.fashion_confidence >= 0.7
                  AND p.title IS NOT NULL
                  AND p.embedding_id IS NULL
                RETURN count(p) as count
            """).single()['count']
            
            # Option 3: All fashion with titles
            option3 = session.run("""
                MATCH (p:Product)
                WHERE p.is_fashion = true
                  AND p.title IS NOT NULL
                  AND p.embedding_id IS NULL
                RETURN count(p) as count
            """).single()['count']
            
            # Option 4: All products with titles
            option4 = session.run("""
                MATCH (p:Product)
                WHERE p.title IS NOT NULL
                  AND p.embedding_id IS NULL
                RETURN count(p) as count
            """).single()['count']
            
            recommendations = [
                ["High Confidence Fashion (>= 0.8)", f"{option1:,}", f"${option1 * 0.000006:.2f}"],
                ["Medium Confidence Fashion (>= 0.7)", f"{option2:,}", f"${option2 * 0.000006:.2f}"],
                ["All Fashion Products", f"{option3:,}", f"${option3 * 0.000006:.2f}"],
                ["All Products", f"{option4:,}", f"${option4 * 0.000006:.2f}"]
            ]
            
            print(tabulate(recommendations, headers=["Strategy", "Products to Embed", "Est. Cost*"], tablefmt="grid"))
            print("* Estimated cost assumes ~300 tokens per product at $0.020 per 1M tokens")
            
            # 8. SAMPLE PRODUCTS
            print("\n8. SAMPLE PRODUCTS")
            print("-"*50)
            
            print("\nSample Fashion Products (high confidence):")
            samples = session.run("""
                MATCH (p:Product)
                WHERE p.is_fashion = true 
                  AND p.fashion_confidence >= 0.9
                  AND p.title IS NOT NULL
                RETURN p.id, p.title, p.fashion_confidence, p.fashion_category
                LIMIT 5
            """)
            
            for s in samples:
                print(f"  ID: {s['p.id']}")
                print(f"  Title: {s['p.title'][:80]}...")
                print(f"  Confidence: {s['p.fashion_confidence']:.3f}")
                print(f"  Category: {s['p.fashion_category'] or 'Not specified'}")
                print()
            
            print("\nSample Unclassified Products:")
            unclassified = session.run("""
                MATCH (p:Product)
                WHERE p.is_fashion IS NULL
                  AND p.title IS NOT NULL
                RETURN p.id, p.title
                LIMIT 3
            """)
            
            for u in unclassified:
                print(f"  ID: {u['p.id']}")
                print(f"  Title: {u['p.title'][:80]}...")
                print()
        
        print("="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)

if __name__ == "__main__":
    analyzer = GraphStatsAnalyzer()
    analyzer.run_analysis()