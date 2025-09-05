#!/usr/bin/env python3
"""
Cross-Database Correlation Analysis
Analyzes consistency and correlation between Neo4j and Qdrant databases

READ-ONLY: Only reads data from both databases for correlation analysis
"""

import json
import os
import hashlib
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
from collections import Counter, defaultdict
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import numpy as np

class CrossDatabaseAnalyzer:
    """Analyzes correlations between Neo4j and Qdrant databases"""
    
    def __init__(self):
        self.output_dir = f"cross_db_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Neo4j connection details
        self.neo4j_url = "bolt://0.0.0.0:17687"
        self.neo4j_user = "neo4j"
        self.neo4j_password = "6D%q@jbYmstkK2i3oW5z6B6outew9m93"
        
        # Qdrant connection details
        self.qdrant_url = "https://9ac8ffa1-c5b7-47e2-a832-3ce559f42042.us-east4-0.gcp.cloud.qdrant.io"
        self.qdrant_api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.zz1R7TKuAT4A0dX-M-oZbgX9sYT-x6bwT1EMPGKZ6Jg"
        self.collection_name = "fashion_products"
    
    def connect_databases(self) -> Tuple[Optional[GraphDatabase.driver], Optional[QdrantClient]]:
        """Connect to both Neo4j and Qdrant databases"""
        print("🔌 Connecting to databases...")
        
        # Neo4j connection
        neo4j_driver = None
        try:
            neo4j_driver = GraphDatabase.driver(
                self.neo4j_url, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            with neo4j_driver.session() as session:
                session.run("RETURN 1")
            print("✅ Connected to Neo4j")
        except Exception as e:
            print(f"❌ Neo4j connection failed: {e}")
            return None, None
        
        # Qdrant connection
        qdrant_client = None
        try:
            qdrant_client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.qdrant_api_key
            )
            collections = qdrant_client.get_collections()
            print("✅ Connected to Qdrant")
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
            return neo4j_driver, None
        
        return neo4j_driver, qdrant_client
    
    def sample_neo4j_products(self, neo4j_driver, sample_size: int = 5000) -> Dict:
        """Sample products from Neo4j for correlation analysis"""
        print(f"📊 Sampling {sample_size:,} products from Neo4j...")
        
        neo4j_data = {
            'products': [],
            'sample_size': 0,
            'total_products': 0
        }
        
        try:
            with neo4j_driver.session() as session:
                # Get total count
                total_result = session.run("MATCH (p:Product) RETURN count(p) as total")
                neo4j_data['total_products'] = total_result.single()['total']
                
                # Sample products
                sample_query = f"""
                MATCH (p:Product)
                RETURN p.id as id, p.title as title, p.description as description, 
                       p.price as price
                ORDER BY rand()
                LIMIT {sample_size}
                """
                
                result = session.run(sample_query)
                for record in result:
                    product = {
                        'id': record['id'],
                        'title': record['title'] or '',
                        'description': record['description'] or '',
                        'price': record['price'] or 0
                    }
                    neo4j_data['products'].append(product)
                
                neo4j_data['sample_size'] = len(neo4j_data['products'])
                
                print(f"✅ Sampled {neo4j_data['sample_size']:,} products from Neo4j (total: {neo4j_data['total_products']:,})")
                
        except Exception as e:
            print(f"❌ Error sampling Neo4j products: {e}")
        
        return neo4j_data
    
    def sample_qdrant_vectors(self, qdrant_client, sample_size: int = 5000) -> Dict:
        """Sample vectors from Qdrant for correlation analysis"""
        print(f"📊 Sampling {sample_size:,} vectors from Qdrant...")
        
        qdrant_data = {
            'vectors': [],
            'sample_size': 0,
            'total_vectors': 0
        }
        
        try:
            # Get total count
            count_result = qdrant_client.count(collection_name=self.collection_name)
            qdrant_data['total_vectors'] = count_result.count
            
            # Sample vectors
            scroll_result = qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=sample_size,
                with_vectors=True,
                with_payload=True
            )
            
            points = scroll_result[0]
            
            for point in points:
                if point.vector is not None:
                    vector_data = {
                        'id': str(point.id),
                        'vector': np.array(point.vector),
                        'payload': point.payload or {}
                    }
                    qdrant_data['vectors'].append(vector_data)
            
            qdrant_data['sample_size'] = len(qdrant_data['vectors'])
            
            print(f"✅ Sampled {qdrant_data['sample_size']:,} vectors from Qdrant (total: {qdrant_data['total_vectors']:,})")
            
        except Exception as e:
            print(f"❌ Error sampling Qdrant vectors: {e}")
        
        return qdrant_data
    
    def analyze_data_overlap(self, neo4j_data: Dict, qdrant_data: Dict) -> Dict:
        """Analyze data overlap between Neo4j and Qdrant"""
        print("🔍 Analyzing data overlap between databases...")
        
        # Create lookup structures
        neo4j_products = {p['id']: p for p in neo4j_data['products']}
        qdrant_vectors = {v['id']: v for v in qdrant_data['vectors']}
        
        # Find overlaps
        neo4j_ids = set(neo4j_products.keys())
        qdrant_ids = set(qdrant_vectors.keys())
        
        overlap_analysis = {
            'neo4j_sample_size': len(neo4j_ids),
            'qdrant_sample_size': len(qdrant_ids),
            'direct_id_overlap': len(neo4j_ids & qdrant_ids),
            'neo4j_only': len(neo4j_ids - qdrant_ids),
            'qdrant_only': len(qdrant_ids - neo4j_ids),
            'overlapping_products': [],
            'missing_from_qdrant': [],
            'missing_from_neo4j': []
        }
        
        # Analyze overlapping products
        overlapping_ids = neo4j_ids & qdrant_ids
        for product_id in list(overlapping_ids)[:10]:  # First 10 for analysis
            neo4j_product = neo4j_products[product_id]
            qdrant_vector = qdrant_vectors[product_id]
            
            # Compare metadata
            neo4j_title = neo4j_product.get('title', '').strip()
            qdrant_title = qdrant_vector['payload'].get('title', '').strip()
            
            title_match = neo4j_title.lower() == qdrant_title.lower() if neo4j_title and qdrant_title else False
            
            overlap_analysis['overlapping_products'].append({
                'id': product_id,
                'neo4j_title': neo4j_title[:50] + '...' if len(neo4j_title) > 50 else neo4j_title,
                'qdrant_title': qdrant_title[:50] + '...' if len(qdrant_title) > 50 else qdrant_title,
                'title_match': title_match,
                'neo4j_price': neo4j_product.get('price'),
                'qdrant_price': qdrant_vector['payload'].get('price')
            })
        
        # Sample missing products
        missing_from_qdrant = list(neo4j_ids - qdrant_ids)[:5]
        for product_id in missing_from_qdrant:
            product = neo4j_products[product_id]
            overlap_analysis['missing_from_qdrant'].append({
                'id': product_id,
                'title': product.get('title', '')[:50]
            })
        
        missing_from_neo4j = list(qdrant_ids - neo4j_ids)[:5]
        for vector_id in missing_from_neo4j:
            vector = qdrant_vectors[vector_id]
            overlap_analysis['missing_from_neo4j'].append({
                'id': vector_id,
                'title': vector['payload'].get('title', '')[:50]
            })
        
        print(f"📊 Direct ID overlap: {overlap_analysis['direct_id_overlap']:,} products")
        print(f"📊 Neo4j only: {overlap_analysis['neo4j_only']:,}")
        print(f"📊 Qdrant only: {overlap_analysis['qdrant_only']:,}")
        
        return overlap_analysis
    
    def analyze_content_similarity(self, neo4j_data: Dict, qdrant_data: Dict) -> Dict:
        """Analyze content similarity using title/description matching"""
        print("🔍 Analyzing content similarity beyond ID matching...")
        
        # Create title/description hashes for fuzzy matching
        neo4j_content = {}
        qdrant_content = {}
        
        # Process Neo4j products
        for product in neo4j_data['products']:
            title = product.get('title', '').strip().lower()
            if title:
                title_hash = hashlib.md5(title.encode()).hexdigest()
                neo4j_content[title_hash] = {
                    'id': product['id'],
                    'title': title,
                    'source': 'neo4j'
                }
        
        # Process Qdrant vectors
        for vector in qdrant_data['vectors']:
            payload = vector.get('payload', {})
            title = payload.get('title', '').strip().lower()
            if title:
                title_hash = hashlib.md5(title.encode()).hexdigest()
                qdrant_content[title_hash] = {
                    'id': vector['id'],
                    'title': title,
                    'source': 'qdrant'
                }
        
        # Find content matches
        neo4j_hashes = set(neo4j_content.keys())
        qdrant_hashes = set(qdrant_content.keys())
        
        content_matches = neo4j_hashes & qdrant_hashes
        
        similarity_analysis = {
            'neo4j_unique_titles': len(neo4j_hashes),
            'qdrant_unique_titles': len(qdrant_hashes),
            'content_matches': len(content_matches),
            'match_examples': []
        }
        
        # Sample content matches
        for title_hash in list(content_matches)[:10]:
            neo4j_item = neo4j_content[title_hash]
            qdrant_item = qdrant_content[title_hash]
            
            similarity_analysis['match_examples'].append({
                'title': neo4j_item['title'][:50] + '...' if len(neo4j_item['title']) > 50 else neo4j_item['title'],
                'neo4j_id': neo4j_item['id'],
                'qdrant_id': qdrant_item['id'],
                'id_match': neo4j_item['id'] == qdrant_item['id']
            })
        
        print(f"📊 Content matches by title: {similarity_analysis['content_matches']:,}")
        
        return similarity_analysis
    
    def analyze_vector_quality_correlation(self, neo4j_data: Dict, qdrant_data: Dict, 
                                         overlap_analysis: Dict) -> Dict:
        """Analyze if vector quality correlates with product completeness"""
        print("🔍 Analyzing vector quality correlation with product data completeness...")
        
        quality_analysis = {
            'complete_products': [],
            'incomplete_products': [],
            'vector_quality_stats': {}
        }
        
        # Get overlapping products for analysis
        neo4j_products = {p['id']: p for p in neo4j_data['products']}
        qdrant_vectors = {v['id']: v for v in qdrant_data['vectors']}
        
        overlapping_products = []
        for product_data in overlap_analysis['overlapping_products']:
            product_id = product_data['id']
            if product_id in neo4j_products and product_id in qdrant_vectors:
                neo4j_product = neo4j_products[product_id]
                qdrant_vector = qdrant_vectors[product_id]
                
                # Calculate product completeness score
                completeness = 0
                if neo4j_product.get('title', '').strip():
                    completeness += 1
                if neo4j_product.get('description', '').strip():
                    completeness += 1
                if neo4j_product.get('price', 0) > 0:
                    completeness += 1
                
                # Calculate vector quality (norm)
                vector_norm = np.linalg.norm(qdrant_vector['vector'])
                
                overlapping_products.append({
                    'id': product_id,
                    'completeness': completeness,
                    'vector_norm': vector_norm,
                    'title_length': len(neo4j_product.get('title', '')),
                    'description_length': len(neo4j_product.get('description', ''))
                })
        
        if overlapping_products:
            # Separate by completeness
            complete = [p for p in overlapping_products if p['completeness'] >= 2]
            incomplete = [p for p in overlapping_products if p['completeness'] < 2]
            
            if complete:
                complete_norms = [p['vector_norm'] for p in complete]
                quality_analysis['complete_products'] = {
                    'count': len(complete),
                    'avg_vector_norm': float(np.mean(complete_norms)),
                    'std_vector_norm': float(np.std(complete_norms))
                }
            
            if incomplete:
                incomplete_norms = [p['vector_norm'] for p in incomplete]
                quality_analysis['incomplete_products'] = {
                    'count': len(incomplete),
                    'avg_vector_norm': float(np.mean(incomplete_norms)),
                    'std_vector_norm': float(np.std(incomplete_norms))
                }
            
            # Overall statistics
            all_norms = [p['vector_norm'] for p in overlapping_products]
            all_completeness = [p['completeness'] for p in overlapping_products]
            
            quality_analysis['vector_quality_stats'] = {
                'total_analyzed': len(overlapping_products),
                'avg_completeness': float(np.mean(all_completeness)),
                'avg_vector_norm': float(np.mean(all_norms)),
                'correlation_sample_size': len(overlapping_products)
            }
        
        print(f"📊 Quality correlation analysis on {len(overlapping_products)} products")
        
        return quality_analysis
    
    def create_correlation_report(self, neo4j_data: Dict, qdrant_data: Dict, 
                                overlap_analysis: Dict, similarity_analysis: Dict, 
                                quality_analysis: Dict) -> str:
        """Generate comprehensive cross-database correlation report"""
        
        report_lines = [
            "# Cross-Database Correlation Analysis Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Executive Summary",
            f"📊 **Neo4j Products**: {neo4j_data.get('total_products', 0):,} total, {neo4j_data.get('sample_size', 0):,} analyzed",
            f"📊 **Qdrant Vectors**: {qdrant_data.get('total_vectors', 0):,} total, {qdrant_data.get('sample_size', 0):,} analyzed",
            f"📊 **Direct ID Overlap**: {overlap_analysis.get('direct_id_overlap', 0):,} products",
            f"📊 **Content Matches**: {similarity_analysis.get('content_matches', 0):,} by title similarity",
            "",
            "## Data Overlap Analysis",
            "",
            "### ID-Based Matching",
            f"- **Perfect Matches**: {overlap_analysis.get('direct_id_overlap', 0):,} products exist in both databases",
            f"- **Neo4j Only**: {overlap_analysis.get('neo4j_only', 0):,} products missing from Qdrant",
            f"- **Qdrant Only**: {overlap_analysis.get('qdrant_only', 0):,} vectors missing from Neo4j",
            "",
            f"**Overlap Rate**: {(overlap_analysis.get('direct_id_overlap', 0) / max(overlap_analysis.get('neo4j_sample_size', 1), 1)) * 100:.1f}% of Neo4j sample",
        ]
        
        # Sample overlapping products
        if overlap_analysis.get('overlapping_products'):
            report_lines.extend([
                "",
                "### Sample Overlapping Products",
            ])
            
            for i, product in enumerate(overlap_analysis['overlapping_products'][:5]):
                title_status = "✅ Match" if product['title_match'] else "❌ Different"
                report_lines.extend([
                    f"**Product {i+1}** (ID: {product['id']})",
                    f"- Neo4j: {product['neo4j_title']}",
                    f"- Qdrant: {product['qdrant_title']}",
                    f"- Title Match: {title_status}",
                    ""
                ])
        
        # Content similarity analysis
        report_lines.extend([
            "## Content Similarity Analysis",
            "",
            "### Title-Based Matching",
            f"- **Neo4j Unique Titles**: {similarity_analysis.get('neo4j_unique_titles', 0):,}",
            f"- **Qdrant Unique Titles**: {similarity_analysis.get('qdrant_unique_titles', 0):,}",
            f"- **Title Matches**: {similarity_analysis.get('content_matches', 0):,}",
        ])
        
        # Quality correlation
        if quality_analysis.get('vector_quality_stats'):
            stats = quality_analysis['vector_quality_stats']
            report_lines.extend([
                "",
                "## Vector Quality Correlation",
                f"### Analysis of {stats.get('total_analyzed', 0)} Overlapping Products",
                f"- **Average Completeness**: {stats.get('avg_completeness', 0):.1f}/3.0",
                f"- **Average Vector Norm**: {stats.get('avg_vector_norm', 0):.3f}",
            ])
            
            if quality_analysis.get('complete_products') and quality_analysis.get('incomplete_products'):
                complete = quality_analysis['complete_products']
                incomplete = quality_analysis['incomplete_products']
                
                report_lines.extend([
                    "",
                    "### Complete vs Incomplete Products",
                    f"- **Complete Products** ({complete['count']}): Avg norm = {complete['avg_vector_norm']:.3f}",
                    f"- **Incomplete Products** ({incomplete['count']}): Avg norm = {incomplete['avg_vector_norm']:.3f}",
                ])
        
        # Critical findings
        report_lines.extend([
            "",
            "## 🎯 Critical Findings",
            "",
            "### ✅ Strengths",
        ])
        
        overlap_rate = (overlap_analysis.get('direct_id_overlap', 0) / max(overlap_analysis.get('neo4j_sample_size', 1), 1)) * 100
        if overlap_rate > 80:
            report_lines.append(f"- **High Overlap**: {overlap_rate:.1f}% of products have vectors")
        
        if qdrant_data.get('total_vectors', 0) > 6000000:
            report_lines.append(f"- **Scale**: Large vector database ({qdrant_data['total_vectors']:,} vectors)")
        
        if similarity_analysis.get('content_matches', 0) > 1000:
            report_lines.append(f"- **Content Consistency**: {similarity_analysis['content_matches']:,} title matches")
        
        # Issues
        report_lines.extend([
            "",
            "### ⚠️ Issues Identified",
        ])
        
        if overlap_rate < 50:
            report_lines.append(f"- **Low Overlap**: Only {overlap_rate:.1f}% overlap between databases")
        
        missing_vectors = overlap_analysis.get('neo4j_only', 0)
        if missing_vectors > 100:
            report_lines.append(f"- **Missing Vectors**: {missing_vectors:,} Neo4j products lack vectors")
        
        orphaned_vectors = overlap_analysis.get('qdrant_only', 0)
        if orphaned_vectors > 100:
            report_lines.append(f"- **Orphaned Vectors**: {orphaned_vectors:,} Qdrant vectors lack Neo4j products")
        
        # Recommendations
        report_lines.extend([
            "",
            "## 🚀 Recommendations",
            "",
            "### Immediate Actions",
            "1. **ID Standardization**: Ensure consistent ID formats between databases",
            "2. **Data Sync Validation**: Implement checks for new products getting vectors",
            "3. **Cleanup**: Remove orphaned vectors and generate missing vectors",
            "",
            "### Phase 2 Integration Strategy",
            "1. **Validation**: Cross-check extracted attributes against vector similarity",
            "2. **Quality Assurance**: Ensure similar vectors have similar extracted attributes",
            "3. **Hybrid Search**: Combine attribute filtering with vector similarity",
            "",
            "### Long-term Maintenance",
            "1. **Monitoring**: Set up alerts for database sync issues",
            "2. **Regular Audits**: Periodic correlation analysis",
            "3. **Performance Optimization**: Index optimization based on query patterns",
            "",
            "---",
            f"**Analysis Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | **System**: Cross-Database Correlation Analyzer"
        ])
        
        return "\n".join(report_lines)

def main():
    """Run cross-database correlation analysis"""
    print("🔍 Cross-Database Correlation Analysis Starting...")
    
    analyzer = CrossDatabaseAnalyzer()
    
    # Connect to both databases
    neo4j_driver, qdrant_client = analyzer.connect_databases()
    if not neo4j_driver or not qdrant_client:
        print("❌ Cannot proceed without both database connections")
        return
    
    try:
        # Sample data from both databases
        neo4j_data = analyzer.sample_neo4j_products(neo4j_driver, sample_size=3000)
        qdrant_data = analyzer.sample_qdrant_vectors(qdrant_client, sample_size=3000)
        
        # Run correlation analyses
        overlap_analysis = analyzer.analyze_data_overlap(neo4j_data, qdrant_data)
        similarity_analysis = analyzer.analyze_content_similarity(neo4j_data, qdrant_data)
        quality_analysis = analyzer.analyze_vector_quality_correlation(
            neo4j_data, qdrant_data, overlap_analysis
        )
        
        # Generate comprehensive report
        report_content = analyzer.create_correlation_report(
            neo4j_data, qdrant_data, overlap_analysis, similarity_analysis, quality_analysis
        )
        
        # Save report
        report_file = os.path.join(analyzer.output_dir, "CROSS_DATABASE_CORRELATION_ANALYSIS.md")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        # Save raw data
        raw_data = {
            'analysis_timestamp': datetime.now().isoformat(),
            'neo4j_data': {
                'sample_size': neo4j_data['sample_size'],
                'total_products': neo4j_data['total_products']
            },
            'qdrant_data': {
                'sample_size': qdrant_data['sample_size'],
                'total_vectors': qdrant_data['total_vectors']
            },
            'overlap_analysis': overlap_analysis,
            'similarity_analysis': similarity_analysis,
            'quality_analysis': quality_analysis
        }
        
        data_file = os.path.join(analyzer.output_dir, "correlation_analysis_data.json")
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        
        print("🎉 Cross-database correlation analysis complete!")
        print(f"📁 Report: {report_file}")
        print(f"📊 Data: {data_file}")
        
        # Quick summary
        overlap_count = overlap_analysis.get('direct_id_overlap', 0)
        neo4j_sample = neo4j_data.get('sample_size', 1)
        overlap_rate = (overlap_count / neo4j_sample) * 100 if neo4j_sample > 0 else 0
        
        print(f"\n📊 SUMMARY:")
        print(f"✅ Neo4j-Qdrant overlap: {overlap_count:,}/{neo4j_sample:,} ({overlap_rate:.1f}%)")
        print(f"✅ Content matches: {similarity_analysis.get('content_matches', 0):,}")
        print(f"✅ Quality correlation analyzed: {quality_analysis.get('vector_quality_stats', {}).get('total_analyzed', 0)} products")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if neo4j_driver:
            neo4j_driver.close()

if __name__ == "__main__":
    main()