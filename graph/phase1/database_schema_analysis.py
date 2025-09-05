#!/usr/bin/env python3
"""
Database Schema Deep Dive Analysis
Analyzes Neo4j production database schema for optimization opportunities

READ-ONLY: Only reads database structure, no writes
"""

import json
import os
from datetime import datetime
from typing import Dict, List
from neo4j import GraphDatabase
from collections import defaultdict, Counter

class DatabaseSchemaAnalyzer:
    """Analyzes Neo4j database schema and structure"""
    
    def __init__(self):
        self.output_dir = f"schema_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Connection details (read-only)
        self.neo4j_url = "bolt://0.0.0.0:17687"
        self.neo4j_user = "neo4j"
        self.neo4j_password = "6D%q@jbYmstkK2i3oW5z6B6outew9m93"
    
    def connect_to_database(self):
        """Connect to production Neo4j database (read-only)"""
        try:
            driver = GraphDatabase.driver(
                self.neo4j_url, 
                auth=(self.neo4j_user, self.neo4j_password)
            )
            # Test connection
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                result.single()
            print("✅ Connected to Neo4j production database")
            return driver
        except Exception as e:
            print(f"❌ Failed to connect to Neo4j: {e}")
            return None
    
    def analyze_node_structure(self, session) -> Dict:
        """Analyze all node types and their properties"""
        print("🔍 Analyzing node structure...")
        
        # Get all node labels
        labels_result = session.run("CALL db.labels()")
        all_labels = [record["label"] for record in labels_result]
        
        node_analysis = {
            'total_labels': len(all_labels),
            'labels': all_labels,
            'node_counts': {},
            'property_analysis': {}
        }
        
        # Count nodes for each label
        for label in all_labels:
            try:
                count_result = session.run(f"MATCH (n:`{label}`) RETURN count(n) as count")
                count = count_result.single()['count']
                node_analysis['node_counts'][label] = count
                print(f"  📊 {label}: {count:,} nodes")
            except Exception as e:
                print(f"  ❌ Error counting {label}: {e}")
                node_analysis['node_counts'][label] = 0
        
        # Analyze properties for major node types
        major_labels = [label for label, count in node_analysis['node_counts'].items() if count > 0]
        
        for label in major_labels[:5]:  # Analyze top 5 node types
            try:
                # Sample properties from first 1000 nodes
                prop_result = session.run(f"""
                MATCH (n:`{label}`)
                WITH n LIMIT 1000
                UNWIND keys(n) as key
                RETURN key, count(*) as frequency, 
                       collect(DISTINCT type(n[key]))[0..5] as sample_types
                ORDER BY frequency DESC
                LIMIT 20
                """)
                
                properties = {}
                for record in prop_result:
                    properties[record['key']] = {
                        'frequency': record['frequency'],
                        'types': record['sample_types']
                    }
                
                node_analysis['property_analysis'][label] = properties
                
            except Exception as e:
                print(f"  ⚠️ Could not analyze properties for {label}: {e}")
        
        return node_analysis
    
    def analyze_relationship_structure(self, session) -> Dict:
        """Analyze all relationship types and patterns"""
        print("🔗 Analyzing relationship structure...")
        
        # Get all relationship types
        rel_types_result = session.run("CALL db.relationshipTypes()")
        all_rel_types = [record["relationshipType"] for record in rel_types_result]
        
        rel_analysis = {
            'total_relationship_types': len(all_rel_types),
            'relationship_types': all_rel_types,
            'relationship_counts': {},
            'relationship_patterns': {}
        }
        
        # Count relationships for each type
        for rel_type in all_rel_types:
            try:
                count_result = session.run(f"MATCH ()-[r:`{rel_type}`]->() RETURN count(r) as count")
                count = count_result.single()['count']
                rel_analysis['relationship_counts'][rel_type] = count
                print(f"  🔗 {rel_type}: {count:,} relationships")
            except Exception as e:
                print(f"  ❌ Error counting {rel_type}: {e}")
                rel_analysis['relationship_counts'][rel_type] = 0
        
        # Analyze relationship patterns for major types
        major_rel_types = [rel_type for rel_type, count in rel_analysis['relationship_counts'].items() 
                          if count > 0][:5]
        
        for rel_type in major_rel_types:
            try:
                # Get relationship patterns (source -> target label combinations)
                pattern_result = session.run(f"""
                MATCH (a)-[r:`{rel_type}`]->(b)
                WITH labels(a)[0] as source_label, labels(b)[0] as target_label, count(*) as count
                WHERE count > 10
                RETURN source_label, target_label, count
                ORDER BY count DESC
                LIMIT 10
                """)
                
                patterns = []
                for record in pattern_result:
                    patterns.append({
                        'source': record['source_label'] or 'UNLABELED',
                        'target': record['target_label'] or 'UNLABELED', 
                        'count': record['count']
                    })
                
                rel_analysis['relationship_patterns'][rel_type] = patterns
                
            except Exception as e:
                print(f"  ⚠️ Could not analyze patterns for {rel_type}: {e}")
        
        return rel_analysis
    
    def analyze_data_quality(self, session) -> Dict:
        """Analyze data quality issues"""
        print("🔬 Analyzing data quality...")
        
        quality_analysis = {
            'orphaned_nodes': {},
            'missing_properties': {},
            'null_properties': {},
            'duplicate_detection': {}
        }
        
        # Check for orphaned nodes (no relationships)
        try:
            orphan_result = session.run("""
            MATCH (n)
            WHERE NOT (n)--()
            WITH labels(n)[0] as label, count(*) as count
            WHERE count > 0
            RETURN label, count
            ORDER BY count DESC
            LIMIT 10
            """)
            
            for record in orphan_result:
                quality_analysis['orphaned_nodes'][record['label'] or 'UNLABELED'] = record['count']
                
        except Exception as e:
            print(f"  ⚠️ Could not check orphaned nodes: {e}")
        
        # Check Product node quality specifically
        try:
            product_quality = session.run("""
            MATCH (p:Product)
            WITH p
            LIMIT 10000
            RETURN 
                count(*) as sample_size,
                count(p.title) as has_title,
                count(p.description) as has_description,
                count(p.price) as has_price,
                count(p.id) as has_id
            """)
            
            result = product_quality.single()
            if result:
                sample_size = result['sample_size']
                quality_analysis['missing_properties']['Product'] = {
                    'sample_size': sample_size,
                    'missing_title': sample_size - result['has_title'],
                    'missing_description': sample_size - result['has_description'],
                    'missing_price': sample_size - result['has_price'],
                    'missing_id': sample_size - result['has_id']
                }
                
        except Exception as e:
            print(f"  ⚠️ Could not check Product quality: {e}")
        
        return quality_analysis
    
    def analyze_indexes_constraints(self, session) -> Dict:
        """Analyze existing indexes and constraints"""
        print("⚡ Analyzing indexes and constraints...")
        
        index_analysis = {
            'indexes': [],
            'constraints': [],
            'recommendations': []
        }
        
        # Get indexes
        try:
            index_result = session.run("SHOW INDEXES")
            for record in index_result:
                index_info = {
                    'name': record.get('name', 'unknown'),
                    'type': record.get('type', 'unknown'),
                    'entity_type': record.get('entityType', 'unknown'),
                    'labels': record.get('labelsOrTypes', []),
                    'properties': record.get('properties', []),
                    'state': record.get('state', 'unknown')
                }
                index_analysis['indexes'].append(index_info)
                
        except Exception as e:
            print(f"  ⚠️ Could not retrieve indexes: {e}")
        
        # Get constraints
        try:
            constraint_result = session.run("SHOW CONSTRAINTS")
            for record in constraint_result:
                constraint_info = {
                    'name': record.get('name', 'unknown'),
                    'type': record.get('type', 'unknown'),
                    'entity_type': record.get('entityType', 'unknown'),
                    'labels': record.get('labelsOrTypes', []),
                    'properties': record.get('properties', [])
                }
                index_analysis['constraints'].append(constraint_info)
                
        except Exception as e:
            print(f"  ⚠️ Could not retrieve constraints: {e}")
        
        return index_analysis
    
    def generate_optimization_recommendations(self, node_analysis: Dict, rel_analysis: Dict, 
                                           quality_analysis: Dict, index_analysis: Dict) -> List[str]:
        """Generate optimization recommendations based on analysis"""
        recommendations = []
        
        # Node-based recommendations
        product_count = node_analysis['node_counts'].get('Product', 0)
        if product_count > 1000000:  # > 1M products
            recommendations.append(f"🚀 PERFORMANCE: Consider partitioning Product nodes ({product_count:,} nodes)")
        
        # Check for missing core node types
        missing_nodes = []
        expected_nodes = ['Color', 'Brand', 'Style', 'Category', 'Tag']
        for node_type in expected_nodes:
            if node_analysis['node_counts'].get(node_type, 0) == 0:
                missing_nodes.append(node_type)
        
        if missing_nodes:
            recommendations.append(f"📊 STRUCTURE: Missing core node types: {', '.join(missing_nodes)}")
        
        # Relationship-based recommendations
        total_relationships = sum(rel_analysis['relationship_counts'].values())
        if total_relationships < product_count * 2:  # Less than 2 relationships per product
            recommendations.append("🔗 RELATIONSHIPS: Low relationship density - products may be under-connected")
        
        # Quality-based recommendations
        orphaned_count = sum(quality_analysis['orphaned_nodes'].values())
        if orphaned_count > 0:
            recommendations.append(f"🔍 QUALITY: {orphaned_count:,} orphaned nodes found")
        
        # Index recommendations
        product_indexes = [idx for idx in index_analysis.get('indexes', []) 
                         if 'Product' in (idx.get('labels') or [])]
        if len(product_indexes) < 3:
            recommendations.append("⚡ PERFORMANCE: Consider more indexes on Product properties")
        
        return recommendations
    
    def create_schema_report(self, node_analysis: Dict, rel_analysis: Dict, 
                           quality_analysis: Dict, index_analysis: Dict) -> str:
        """Generate comprehensive schema analysis report"""
        
        recommendations = self.generate_optimization_recommendations(
            node_analysis, rel_analysis, quality_analysis, index_analysis
        )
        
        report_lines = [
            "# Neo4j Database Schema Deep Dive Analysis",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Executive Summary",
            f"📊 **Node Types**: {node_analysis['total_labels']} different labels",
            f"🔗 **Relationship Types**: {rel_analysis['total_relationship_types']} different types",
            f"📈 **Total Nodes**: {sum(node_analysis['node_counts'].values()):,}",
            f"📈 **Total Relationships**: {sum(rel_analysis['relationship_counts'].values()):,}",
            "",
            "## Node Analysis",
            "### Node Counts by Label",
        ]
        
        # Sort nodes by count
        sorted_nodes = sorted(node_analysis['node_counts'].items(), key=lambda x: x[1], reverse=True)
        for label, count in sorted_nodes:
            percentage = (count / sum(node_analysis['node_counts'].values())) * 100 if sum(node_analysis['node_counts'].values()) > 0 else 0
            report_lines.append(f"- **{label}**: {count:,} nodes ({percentage:.1f}%)")
        
        report_lines.extend([
            "",
            "## Relationship Analysis", 
            "### Relationship Counts by Type",
        ])
        
        # Sort relationships by count
        sorted_rels = sorted(rel_analysis['relationship_counts'].items(), key=lambda x: x[1], reverse=True)
        for rel_type, count in sorted_rels:
            percentage = (count / sum(rel_analysis['relationship_counts'].values())) * 100 if sum(rel_analysis['relationship_counts'].values()) > 0 else 0
            report_lines.append(f"- **{rel_type}**: {count:,} relationships ({percentage:.1f}%)")
        
        # Relationship patterns
        report_lines.extend([
            "",
            "### Relationship Patterns",
        ])
        
        for rel_type, patterns in rel_analysis['relationship_patterns'].items():
            if patterns:
                report_lines.append(f"\n**{rel_type}:**")
                for pattern in patterns[:5]:  # Top 5 patterns
                    report_lines.append(f"- {pattern['source']} → {pattern['target']}: {pattern['count']:,}")
        
        # Data quality section
        report_lines.extend([
            "",
            "## Data Quality Analysis",
        ])
        
        if quality_analysis['orphaned_nodes']:
            report_lines.append("\n### Orphaned Nodes (No Relationships)")
            for label, count in quality_analysis['orphaned_nodes'].items():
                report_lines.append(f"- **{label}**: {count:,} orphaned nodes")
        
        if quality_analysis['missing_properties'].get('Product'):
            prod_qual = quality_analysis['missing_properties']['Product']
            report_lines.extend([
                "\n### Product Data Quality",
                f"- **Sample Size**: {prod_qual['sample_size']:,} products",
                f"- **Missing Title**: {prod_qual['missing_title']:,}",
                f"- **Missing Description**: {prod_qual['missing_description']:,}",
                f"- **Missing Price**: {prod_qual['missing_price']:,}",
                f"- **Missing ID**: {prod_qual['missing_id']:,}",
            ])
        
        # Index analysis
        report_lines.extend([
            "",
            "## Performance Analysis",
            f"### Current Indexes ({len(index_analysis['indexes'])})",
        ])
        
        for idx in index_analysis['indexes'][:10]:  # Top 10 indexes
            labels = ', '.join(idx.get('labels', ['unknown']))
            properties = ', '.join(idx.get('properties', ['unknown']))
            report_lines.append(f"- **{idx['name']}**: {labels}.{properties} ({idx['type']})")
        
        report_lines.extend([
            f"\n### Current Constraints ({len(index_analysis['constraints'])})",
        ])
        
        for constraint in index_analysis['constraints'][:10]:  # Top 10 constraints
            labels = ', '.join(constraint.get('labels', ['unknown']))
            properties = ', '.join(constraint.get('properties', ['unknown']))
            report_lines.append(f"- **{constraint['name']}**: {labels}.{properties} ({constraint['type']})")
        
        # Recommendations section
        if recommendations:
            report_lines.extend([
                "",
                "## 🚀 Optimization Recommendations",
            ])
            
            for rec in recommendations:
                report_lines.append(f"- {rec}")
        
        report_lines.extend([
            "",
            "## Phase 2 Impact Assessment",
            "### New Nodes to be Created",
            "- Color nodes (~15-20 based on extraction)",
            "- Brand nodes (~100+ based on extraction)", 
            "- Style nodes (~50+ based on extraction)",
            "",
            "### New Relationships to be Created",
            "- Product → Color relationships (~5.5M)",
            "- Product → Brand relationships (~6.4M)",
            "- Product → Style relationships (~4.8M)",
            "",
            "**Total Impact**: +16.7M new relationships, significant performance considerations",
            "",
            "---",
            f"**Analysis Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | **Analyzer**: Schema Deep Dive System"
        ])
        
        return "\n".join(report_lines)

def main():
    """Run database schema analysis"""
    print("🔍 Database Schema Deep Dive Analysis Starting...")
    
    analyzer = DatabaseSchemaAnalyzer()
    
    # Connect to database
    driver = analyzer.connect_to_database()
    if not driver:
        print("❌ Cannot proceed without database connection")
        return
    
    try:
        with driver.session() as session:
            # Run all analyses
            node_analysis = analyzer.analyze_node_structure(session)
            rel_analysis = analyzer.analyze_relationship_structure(session)
            quality_analysis = analyzer.analyze_data_quality(session)
            index_analysis = analyzer.analyze_indexes_constraints(session)
            
            # Generate comprehensive report
            report_content = analyzer.create_schema_report(
                node_analysis, rel_analysis, quality_analysis, index_analysis
            )
            
            # Save report
            report_file = os.path.join(analyzer.output_dir, "DATABASE_SCHEMA_ANALYSIS.md")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            # Save raw data
            raw_data = {
                'node_analysis': node_analysis,
                'relationship_analysis': rel_analysis,
                'quality_analysis': quality_analysis,
                'index_analysis': index_analysis,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            data_file = os.path.join(analyzer.output_dir, "schema_analysis_data.json")
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(raw_data, f, indent=2, ensure_ascii=False)
            
            print("🎉 Database schema analysis complete!")
            print(f"📁 Report saved: {report_file}")
            print(f"📊 Raw data: {data_file}")
            
            # Quick summary
            total_nodes = sum(node_analysis['node_counts'].values())
            total_rels = sum(rel_analysis['relationship_counts'].values())
            print(f"\n📊 SUMMARY: {total_nodes:,} nodes, {total_rels:,} relationships, {node_analysis['total_labels']} node types")
            
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        driver.close()

if __name__ == "__main__":
    main()