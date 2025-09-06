#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Phase 2 Completion Validation Script
Validates that Phase 2 graph reconstruction completed successfully

IMMEDIATE POST-PHASE 2 EXECUTION
Run this script immediately after Phase 2 completes to validate results
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Tuple
from neo4j import GraphDatabase
from collections import Counter

class Phase2CompletionValidator:
    """Validates Phase 2 graph reconstruction completion"""
    
    def __init__(self):
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user
        self.neo4j_password = self.db_config.neo4j_password
        
        # Expected results from Phase 1 extraction
        self.expected_results = {
            'total_products': 6416804,
            'expected_colors': {'red', 'blue', 'black', 'white', 'green', 'brown', 'gray', 'pink', 'yellow', 'orange', 'purple', 'beige', 'gold'},
            'min_color_relationships': 5500000,  # 86% of 6.4M
            'min_brand_relationships': 6000000,  # 99.7% of 6.4M (conservative)
            'min_style_relationships': 4500000,  # 75% of 6.4M (conservative)
            'min_brand_nodes': 50,  # Conservative estimate
            'min_style_nodes': 30,  # Conservative estimate
            'expected_relationship_types': {'HAS_COLOR', 'HAS_BRAND', 'HAS_STYLE'}
        }
        
        self.validation_results = {
            'timestamp': datetime.now().isoformat(),
            'overall_success': False,
            'node_validation': {},
            'relationship_validation': {},
            'sample_validation': {},
            'performance_metrics': {},
            'errors': []
        }
    
    def connect_to_database(self):
        """Connect to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_url,
                auth=(self.neo4j_user, self.neo4j_password)
            )
            
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            
            print("✅ Connected to Neo4j database")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            self.validation_results['errors'].append(f"Connection failed: {e}")
            return False
    
    def validate_new_nodes(self) -> bool:
        """Validate that new Color, Brand, Style nodes were created"""
        print("🔍 Validating new node creation...")
        
        try:
            with self.driver.session() as session:
                # Count all node types
                node_counts = {}
                
                for node_type in ['Color', 'Brand', 'Style', 'Product']:
                    result = session.run(f"MATCH (n:`{node_type}`) RETURN count(n) as count")
                    count = result.single()['count']
                    node_counts[node_type] = count
                    print(f"  📊 {node_type} nodes: {count:,}")
                
                # Validate Color nodes
                color_count = node_counts.get('Color', 0)
                color_success = color_count >= len(self.expected_results['expected_colors'])
                
                if color_success:
                    print(f"  ✅ Color nodes: {color_count} (expected >= {len(self.expected_results['expected_colors'])})")
                else:
                    print(f"  ❌ Color nodes: {color_count} (expected >= {len(self.expected_results['expected_colors'])})")
                    self.validation_results['errors'].append(f"Insufficient Color nodes: {color_count}")
                
                # Validate Brand nodes
                brand_count = node_counts.get('Brand', 0)
                brand_success = brand_count >= self.expected_results['min_brand_nodes']
                
                if brand_success:
                    print(f"  ✅ Brand nodes: {brand_count} (expected >= {self.expected_results['min_brand_nodes']})")
                else:
                    print(f"  ❌ Brand nodes: {brand_count} (expected >= {self.expected_results['min_brand_nodes']})")
                    self.validation_results['errors'].append(f"Insufficient Brand nodes: {brand_count}")
                
                # Validate Style nodes
                style_count = node_counts.get('Style', 0)
                style_success = style_count >= self.expected_results['min_style_nodes']
                
                if style_success:
                    print(f"  ✅ Style nodes: {style_count} (expected >= {self.expected_results['min_style_nodes']})")
                else:
                    print(f"  ❌ Style nodes: {style_count} (expected >= {self.expected_results['min_style_nodes']})")
                    self.validation_results['errors'].append(f"Insufficient Style nodes: {style_count}")
                
                # Check for expected colors
                if color_count > 0:
                    color_result = session.run("MATCH (c:Color) RETURN c.name as name LIMIT 20")
                    found_colors = {record['name'] for record in color_result}
                    missing_colors = self.expected_results['expected_colors'] - found_colors
                    
                    if missing_colors:
                        print(f"  ⚠️ Missing expected colors: {missing_colors}")
                        self.validation_results['errors'].append(f"Missing colors: {missing_colors}")
                    else:
                        print(f"  ✅ All expected colors found")
                
                self.validation_results['node_validation'] = {
                    'color_nodes': color_count,
                    'brand_nodes': brand_count,
                    'style_nodes': style_count,
                    'product_nodes': node_counts.get('Product', 0),
                    'color_success': color_success,
                    'brand_success': brand_success,
                    'style_success': style_success
                }
                
                return color_success and brand_success and style_success
                
        except Exception as e:
            print(f"❌ Error validating nodes: {e}")
            self.validation_results['errors'].append(f"Node validation error: {e}")
            return False
    
    def validate_new_relationships(self) -> bool:
        """Validate that new relationships were created correctly"""
        print("🔗 Validating new relationship creation...")
        
        try:
            with self.driver.session() as session:
                relationship_counts = {}
                
                # Count each relationship type
                for rel_type in self.expected_results['expected_relationship_types']:
                    result = session.run(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) as count")
                    count = result.single()['count']
                    relationship_counts[rel_type] = count
                    print(f"  🔗 {rel_type}: {count:,}")
                
                # Validate HAS_COLOR relationships
                color_rels = relationship_counts.get('HAS_COLOR', 0)
                color_rel_success = color_rels >= self.expected_results['min_color_relationships']
                
                if color_rel_success:
                    print(f"  ✅ HAS_COLOR relationships: {color_rels:,} (expected >= {self.expected_results['min_color_relationships']:,})")
                else:
                    print(f"  ❌ HAS_COLOR relationships: {color_rels:,} (expected >= {self.expected_results['min_color_relationships']:,})")
                    self.validation_results['errors'].append(f"Insufficient HAS_COLOR relationships: {color_rels:,}")
                
                # Validate HAS_BRAND relationships
                brand_rels = relationship_counts.get('HAS_BRAND', 0)
                brand_rel_success = brand_rels >= self.expected_results['min_brand_relationships']
                
                if brand_rel_success:
                    print(f"  ✅ HAS_BRAND relationships: {brand_rels:,} (expected >= {self.expected_results['min_brand_relationships']:,})")
                else:
                    print(f"  ❌ HAS_BRAND relationships: {brand_rels:,} (expected >= {self.expected_results['min_brand_relationships']:,})")
                    self.validation_results['errors'].append(f"Insufficient HAS_BRAND relationships: {brand_rels:,}")
                
                # Validate HAS_STYLE relationships
                style_rels = relationship_counts.get('HAS_STYLE', 0)
                style_rel_success = style_rels >= self.expected_results['min_style_relationships']
                
                if style_rel_success:
                    print(f"  ✅ HAS_STYLE relationships: {style_rels:,} (expected >= {self.expected_results['min_style_relationships']:,})")
                else:
                    print(f"  ❌ HAS_STYLE relationships: {style_rels:,} (expected >= {self.expected_results['min_style_relationships']:,})")
                    self.validation_results['errors'].append(f"Insufficient HAS_STYLE relationships: {style_rels:,}")
                
                # Check relationship properties (confidence, timestamps, etc.)
                print("  🔍 Validating relationship properties...")
                
                for rel_type in self.expected_results['expected_relationship_types']:
                    if relationship_counts.get(rel_type, 0) > 0:
                        prop_result = session.run(f"""
                        MATCH ()-[r:`{rel_type}`]->()
                        WITH r LIMIT 100
                        RETURN 
                            count(r) as total,
                            count(r.confidence) as has_confidence,
                            count(r.created_at) as has_created_at,
                            count(r.extraction_source) as has_source
                        """)
                        
                        prop_data = prop_result.single()
                        if prop_data:
                            confidence_coverage = (prop_data['has_confidence'] / prop_data['total']) * 100
                            timestamp_coverage = (prop_data['has_created_at'] / prop_data['total']) * 100
                            
                            print(f"    {rel_type} properties: {confidence_coverage:.1f}% confidence, {timestamp_coverage:.1f}% timestamps")
                            
                            if confidence_coverage < 90:
                                self.validation_results['errors'].append(f"{rel_type} missing confidence scores")
                
                self.validation_results['relationship_validation'] = {
                    'has_color_count': color_rels,
                    'has_brand_count': brand_rels,
                    'has_style_count': style_rels,
                    'color_success': color_rel_success,
                    'brand_success': brand_rel_success,
                    'style_success': style_rel_success,
                    'total_new_relationships': sum(relationship_counts.values())
                }
                
                return color_rel_success and brand_rel_success and style_rel_success
                
        except Exception as e:
            print(f"❌ Error validating relationships: {e}")
            self.validation_results['errors'].append(f"Relationship validation error: {e}")
            return False
    
    def validate_sample_products(self, sample_size: int = 100) -> bool:
        """Validate that sample products have expected attributes"""
        print(f"🎯 Validating sample products ({sample_size} random products)...")
        
        try:
            with self.driver.session() as session:
                # Get random sample of products with their new relationships
                result = session.run(f"""
                MATCH (p:Product)
                WITH p
                ORDER BY rand()
                LIMIT {sample_size}
                OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)
                OPTIONAL MATCH (p)-[:HAS_BRAND]->(b:Brand)
                OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)
                RETURN 
                    p.id as product_id,
                    p.title as title,
                    collect(DISTINCT c.name) as colors,
                    collect(DISTINCT b.name) as brands,
                    collect(DISTINCT s.name) as styles
                """)
                
                products_with_colors = 0
                products_with_brands = 0
                products_with_styles = 0
                products_with_all_attributes = 0
                sample_products = []
                
                for record in result:
                    product = {
                        'id': record['product_id'],
                        'title': record['title'],
                        'colors': [c for c in record['colors'] if c],
                        'brands': [b for b in record['brands'] if b],
                        'styles': [s for s in record['styles'] if s]
                    }
                    
                    sample_products.append(product)
                    
                    if product['colors']:
                        products_with_colors += 1
                    if product['brands']:
                        products_with_brands += 1
                    if product['styles']:
                        products_with_styles += 1
                    if product['colors'] and product['brands'] and product['styles']:
                        products_with_all_attributes += 1
                
                # Calculate success rates
                color_rate = (products_with_colors / sample_size) * 100
                brand_rate = (products_with_brands / sample_size) * 100
                style_rate = (products_with_styles / sample_size) * 100
                all_attributes_rate = (products_with_all_attributes / sample_size) * 100
                
                print(f"  📊 Products with colors: {products_with_colors}/{sample_size} ({color_rate:.1f}%)")
                print(f"  📊 Products with brands: {products_with_brands}/{sample_size} ({brand_rate:.1f}%)")
                print(f"  📊 Products with styles: {products_with_styles}/{sample_size} ({style_rate:.1f}%)")
                print(f"  📊 Products with all attributes: {products_with_all_attributes}/{sample_size} ({all_attributes_rate:.1f}%)")
                
                # Show sample products
                print("  📋 Sample products with attributes:")
                for product in sample_products[:5]:
                    title_short = product['title'][:50] + '...' if len(product['title']) > 50 else product['title']
                    colors_str = ', '.join(product['colors'][:3]) if product['colors'] else 'None'
                    brands_str = ', '.join(product['brands'][:2]) if product['brands'] else 'None'
                    styles_str = ', '.join(product['styles'][:2]) if product['styles'] else 'None'
                    
                    print(f"    • {title_short}")
                    print(f"      Colors: {colors_str} | Brands: {brands_str} | Styles: {styles_str}")
                
                # Validation success criteria
                color_success = color_rate >= 80  # Expected 86% from Phase 1
                brand_success = brand_rate >= 95  # Expected 99.7% from Phase 1
                style_success = style_rate >= 70  # Expected 75% from Phase 1
                
                validation_success = color_success and brand_success and style_success
                
                if not validation_success:
                    if not color_success:
                        self.validation_results['errors'].append(f"Low color coverage: {color_rate:.1f}%")
                    if not brand_success:
                        self.validation_results['errors'].append(f"Low brand coverage: {brand_rate:.1f}%")
                    if not style_success:
                        self.validation_results['errors'].append(f"Low style coverage: {style_rate:.1f}%")
                
                self.validation_results['sample_validation'] = {
                    'sample_size': sample_size,
                    'color_coverage': color_rate,
                    'brand_coverage': brand_rate,
                    'style_coverage': style_rate,
                    'all_attributes_coverage': all_attributes_rate,
                    'success': validation_success
                }
                
                return validation_success
                
        except Exception as e:
            print(f"❌ Error validating sample products: {e}")
            self.validation_results['errors'].append(f"Sample validation error: {e}")
            return False
    
    def test_query_performance(self) -> bool:
        """Test query performance with new graph structure"""
        print("⚡ Testing query performance...")
        
        try:
            with self.driver.session() as session:
                performance_tests = [
                    {
                        'name': 'Color filter query',
                        'query': 'MATCH (p:Product)-[:HAS_COLOR]->(c:Color {name: "red"}) RETURN count(p) as count'
                    },
                    {
                        'name': 'Brand filter query',
                        'query': 'MATCH (p:Product)-[:HAS_BRAND]->(b:Brand) WHERE b.name CONTAINS "Nike" RETURN count(p) as count'
                    },
                    {
                        'name': 'Style filter query',
                        'query': 'MATCH (p:Product)-[:HAS_STYLE]->(s:Style {name: "casual"}) RETURN count(p) as count'
                    },
                    {
                        'name': 'Multi-attribute query',
                        'query': '''MATCH (p:Product)-[:HAS_COLOR]->(c:Color {name: "blue"})
                                   MATCH (p)-[:HAS_STYLE]->(s:Style {name: "casual"})
                                   RETURN count(p) as count'''
                    }
                ]
                
                performance_results = {}
                
                for test in performance_tests:
                    start_time = time.time()
                    
                    try:
                        result = session.run(test['query'])
                        count = result.single()['count']
                        
                        end_time = time.time()
                        execution_time = (end_time - start_time) * 1000  # Convert to ms
                        
                        performance_results[test['name']] = {
                            'execution_time_ms': execution_time,
                            'result_count': count,
                            'success': True
                        }
                        
                        print(f"  ✅ {test['name']}: {execution_time:.1f}ms ({count:,} results)")
                        
                        if execution_time > 5000:  # > 5 seconds is concerning
                            self.validation_results['errors'].append(f"Slow query: {test['name']} took {execution_time:.1f}ms")
                        
                    except Exception as e:
                        performance_results[test['name']] = {
                            'execution_time_ms': 0,
                            'result_count': 0,
                            'success': False,
                            'error': str(e)
                        }
                        print(f"  ❌ {test['name']}: Failed - {e}")
                        self.validation_results['errors'].append(f"Query failed: {test['name']} - {e}")
                
                self.validation_results['performance_metrics'] = performance_results
                
                # Check if all queries succeeded
                all_success = all(result['success'] for result in performance_results.values())
                return all_success
                
        except Exception as e:
            print(f"❌ Error testing query performance: {e}")
            self.validation_results['errors'].append(f"Performance testing error: {e}")
            return False
    
    def generate_validation_report(self) -> str:
        """Generate comprehensive validation report"""
        print("📋 Generating validation report...")
        
        # Determine overall success
        overall_success = (
            self.validation_results.get('node_validation', {}).get('color_success', False) and
            self.validation_results.get('node_validation', {}).get('brand_success', False) and
            self.validation_results.get('node_validation', {}).get('style_success', False) and
            self.validation_results.get('relationship_validation', {}).get('color_success', False) and
            self.validation_results.get('relationship_validation', {}).get('brand_success', False) and
            self.validation_results.get('relationship_validation', {}).get('style_success', False) and
            self.validation_results.get('sample_validation', {}).get('success', False) and
            len(self.validation_results.get('errors', [])) == 0
        )
        
        self.validation_results['overall_success'] = overall_success
        
        # Generate report
        report_lines = [
            "# Phase 2 Completion Validation Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## 🎯 Overall Result: {'✅ SUCCESS' if overall_success else '❌ ISSUES FOUND'}",
            "",
            "## Node Creation Validation"
        ]
        
        node_val = self.validation_results.get('node_validation', {})
        if node_val:
            report_lines.extend([
                f"- **Color Nodes**: {node_val.get('color_nodes', 0):,} {'✅' if node_val.get('color_success') else '❌'}",
                f"- **Brand Nodes**: {node_val.get('brand_nodes', 0):,} {'✅' if node_val.get('brand_success') else '❌'}",
                f"- **Style Nodes**: {node_val.get('style_nodes', 0):,} {'✅' if node_val.get('style_success') else '❌'}",
                f"- **Product Nodes**: {node_val.get('product_nodes', 0):,} (unchanged)"
            ])
        
        report_lines.append("\n## Relationship Creation Validation")
        
        rel_val = self.validation_results.get('relationship_validation', {})
        if rel_val:
            report_lines.extend([
                f"- **HAS_COLOR**: {rel_val.get('has_color_count', 0):,} {'✅' if rel_val.get('color_success') else '❌'}",
                f"- **HAS_BRAND**: {rel_val.get('has_brand_count', 0):,} {'✅' if rel_val.get('brand_success') else '❌'}",
                f"- **HAS_STYLE**: {rel_val.get('has_style_count', 0):,} {'✅' if rel_val.get('style_success') else '❌'}",
                f"- **Total New Relationships**: {rel_val.get('total_new_relationships', 0):,}"
            ])
        
        report_lines.append("\n## Sample Product Validation")
        
        sample_val = self.validation_results.get('sample_validation', {})
        if sample_val:
            report_lines.extend([
                f"- **Sample Size**: {sample_val.get('sample_size', 0)} products",
                f"- **Color Coverage**: {sample_val.get('color_coverage', 0):.1f}%",
                f"- **Brand Coverage**: {sample_val.get('brand_coverage', 0):.1f}%",
                f"- **Style Coverage**: {sample_val.get('style_coverage', 0):.1f}%",
                f"- **All Attributes**: {sample_val.get('all_attributes_coverage', 0):.1f}%"
            ])
        
        report_lines.append("\n## Performance Validation")
        
        perf_metrics = self.validation_results.get('performance_metrics', {})
        if perf_metrics:
            for test_name, metrics in perf_metrics.items():
                status = '✅' if metrics.get('success') else '❌'
                exec_time = metrics.get('execution_time_ms', 0)
                count = metrics.get('result_count', 0)
                report_lines.append(f"- **{test_name}**: {exec_time:.1f}ms ({count:,} results) {status}")
        
        # Errors section
        errors = self.validation_results.get('errors', [])
        if errors:
            report_lines.extend([
                "\n## ❌ Issues Found",
                ""
            ])
            for error in errors:
                report_lines.append(f"- {error}")
        else:
            report_lines.append("\n## ✅ No Issues Found")
        
        # Next steps
        if overall_success:
            report_lines.extend([
                "\n## 🚀 Next Steps",
                "1. ✅ Phase 2 validation complete - proceed with confidence",
                "2. 🔄 Ready for Qdrant re-embedding with perfect UUID sync",
                "3. 📊 Monitor production performance after deployment",
                "4. 🧪 Run user acceptance testing"
            ])
        else:
            report_lines.extend([
                "\n## ⚠️ Required Actions",
                "1. ❌ Review and fix issues listed above",
                "2. 🔄 Re-run Phase 2 validation after fixes",
                "3. ⏸️ Do NOT proceed to embedding until validation passes"
            ])
        
        report_lines.extend([
            "",
            "---",
            f"**Validation completed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Validator**: Phase 2 Completion Validation System"
        ])
        
        return "\n".join(report_lines)
    
    def run_complete_validation(self) -> bool:
        """Run complete Phase 2 validation"""
        print("🚀 PHASE 2 COMPLETION VALIDATION")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        try:
            # Connect to database
            if not self.connect_to_database():
                return False
            
            # Run all validation steps
            step_results = [
                self.validate_new_nodes(),
                self.validate_new_relationships(),
                self.validate_sample_products(),
                self.test_query_performance()
            ]
            
            # Generate report
            report = self.generate_validation_report()
            
            # Save report
            report_file = f"phase2_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # Save raw results
            results_file = f"phase2_validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(self.validation_results, f, indent=2)
            
            overall_success = self.validation_results['overall_success']
            
            print()
            print("=" * 60)
            if overall_success:
                print("🎉 PHASE 2 VALIDATION: ✅ SUCCESS")
                print("🚀 Ready to proceed with Qdrant re-embedding!")
            else:
                print("⚠️ PHASE 2 VALIDATION: ❌ ISSUES FOUND")
                print("🔧 Review issues and fix before proceeding!")
            
            print(f"📋 Report saved: {report_file}")
            print(f"📊 Raw data: {results_file}")
            print("=" * 60)
            
            return overall_success
            
        except Exception as e:
            print(f"❌ Validation failed with error: {e}")
            self.validation_results['errors'].append(f"Critical validation error: {e}")
            return False
        
        finally:
            if hasattr(self, 'driver'):
                self.driver.close()

if __name__ == "__main__":
    validator = Phase2CompletionValidator()
    success = validator.run_complete_validation()
    
    if success:
        print("✅ Validation completed successfully - Phase 2 is ready!")
        exit(0)
    else:
        print("❌ Validation found issues - fix before proceeding!")
        exit(1)