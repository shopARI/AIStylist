#!/usr/bin/env python3
"""
Phase 2 Preparation: Graph Reconstruction Scripts
Generates Cypher queries to reconstruct graph from Phase 1 extraction data

READ-ONLY: No database writes, only script generation
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Set, Tuple

class Phase2Preparation:
    """Generate Phase 2 Cypher scripts from Phase 1 extraction data"""
    
    def __init__(self, extraction_dir: str):
        self.extraction_dir = extraction_dir
        self.output_dir = f"phase2_scripts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        
    def analyze_extraction_data(self) -> Dict:
        """Analyze extraction results to understand data distribution"""
        print("📊 Analyzing Phase 1 extraction data...")
        
        # Collect all unique values
        all_colors = set()
        all_brands = set()
        all_styles = set()
        product_metadata = {}
        
        # Process all batch files
        batch_files = [f for f in os.listdir(self.extraction_dir) if f.startswith('batch_') and f.endswith('.json')]
        
        for batch_file in sorted(batch_files):
            batch_path = os.path.join(self.extraction_dir, batch_file)
            with open(batch_path, 'r', encoding='utf-8') as f:
                batch_data = json.load(f)
                
            for item in batch_data:
                product_id = item['product_id']
                metadata = item['extracted_metadata']
                
                # Track unique values
                if metadata['colors']:
                    all_colors.update(metadata['colors'])
                if metadata['brands']:
                    all_brands.update(metadata['brands'])
                if metadata['styles']:
                    all_styles.update(metadata['styles'])
                
                # Store product metadata
                product_metadata[product_id] = {
                    'colors': metadata['colors'],
                    'brands': metadata['brands'],
                    'styles': metadata['styles'],
                    'confidence': item['confidence_scores']
                }
        
        analysis = {
            'total_products': len(product_metadata),
            'unique_colors': len(all_colors),
            'unique_brands': len(all_brands),
            'unique_styles': len(all_styles),
            'color_list': sorted(list(all_colors)),
            'brand_list': sorted(list(all_brands)),
            'style_list': sorted(list(all_styles))
        }
        
        print(f"✅ Analyzed {analysis['total_products']:,} products")
        print(f"📊 Found {analysis['unique_colors']} colors, {analysis['unique_brands']} brands, {analysis['unique_styles']} styles")
        
        return analysis, product_metadata
    
    def generate_node_creation_scripts(self, analysis: Dict) -> str:
        """Generate Cypher scripts to create Color, Brand, Style nodes"""
        print("🏗️ Generating node creation scripts...")
        
        cypher_lines = [
            "// Phase 2: Node Creation Scripts",
            "// Generated from Phase 1 extraction data",
            f"// Timestamp: {datetime.now().isoformat()}",
            "",
            "// ================================",
            "// CREATE COLOR NODES",
            "// ================================",
        ]
        
        # Create Color nodes
        for color in analysis['color_list']:
            cypher_lines.extend([
                f"MERGE (c:Color {{name: '{color.lower()}', display_name: '{color.title()}'}})",
                f"ON CREATE SET c.created_at = datetime(), c.extraction_source = 'phase1'",
                f"ON MATCH SET c.updated_at = datetime();",
                ""
            ])
        
        cypher_lines.extend([
            "// ================================",
            "// CREATE BRAND NODES", 
            "// ================================",
        ])
        
        # Create Brand nodes
        for brand in analysis['brand_list']:
            cypher_lines.extend([
                f"MERGE (b:Brand {{name: '{brand}', display_name: '{brand}'}})",
                f"ON CREATE SET b.created_at = datetime(), b.extraction_source = 'phase1'",
                f"ON MATCH SET b.updated_at = datetime();",
                ""
            ])
        
        cypher_lines.extend([
            "// ================================",
            "// CREATE STYLE NODES",
            "// ================================",
        ])
        
        # Create Style nodes
        for style in analysis['style_list']:
            cypher_lines.extend([
                f"MERGE (s:Style {{name: '{style.lower()}', display_name: '{style.title()}'}})",
                f"ON CREATE SET s.created_at = datetime(), s.extraction_source = 'phase1'",
                f"ON MATCH SET s.updated_at = datetime();",
                ""
            ])
        
        script_content = "\n".join(cypher_lines)
        
        # Save to file
        node_script_file = os.path.join(self.output_dir, "01_create_nodes.cypher")
        with open(node_script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"✅ Node creation script: {node_script_file}")
        return script_content
    
    def generate_relationship_scripts(self, product_metadata: Dict) -> str:
        """Generate Cypher scripts to create product relationships"""
        print("🔗 Generating relationship creation scripts...")
        
        cypher_lines = [
            "// Phase 2: Relationship Creation Scripts",
            "// Links products to Colors, Brands, Styles",
            f"// Timestamp: {datetime.now().isoformat()}",
            "",
            "// ================================",
            "// PRODUCT -> COLOR RELATIONSHIPS",
            "// ================================",
        ]
        
        # Generate color relationships
        color_count = 0
        for product_id, metadata in product_metadata.items():
            if metadata['colors']:
                for color in metadata['colors']:
                    confidence = metadata['confidence']['colors']
                    cypher_lines.extend([
                        f"MATCH (p:Product {{id: '{product_id}'}}), (c:Color {{name: '{color.lower()}'}})",
                        f"MERGE (p)-[r:HAS_COLOR]->(c)",
                        f"ON CREATE SET r.confidence = {confidence}, r.created_at = datetime(), r.extraction_source = 'phase1'",
                        f"ON MATCH SET r.updated_at = datetime();",
                        ""
                    ])
                    color_count += 1
        
        cypher_lines.extend([
            "// ================================",
            "// PRODUCT -> BRAND RELATIONSHIPS",
            "// ================================",
        ])
        
        # Generate brand relationships
        brand_count = 0
        for product_id, metadata in product_metadata.items():
            if metadata['brands']:
                for brand in metadata['brands']:
                    confidence = metadata['confidence']['brands']
                    cypher_lines.extend([
                        f"MATCH (p:Product {{id: '{product_id}'}}), (b:Brand {{name: '{brand}'}})",
                        f"MERGE (p)-[r:HAS_BRAND]->(b)",
                        f"ON CREATE SET r.confidence = {confidence}, r.created_at = datetime(), r.extraction_source = 'phase1'",
                        f"ON MATCH SET r.updated_at = datetime();",
                        ""
                    ])
                    brand_count += 1
        
        cypher_lines.extend([
            "// ================================",
            "// PRODUCT -> STYLE RELATIONSHIPS",
            "// ================================",
        ])
        
        # Generate style relationships  
        style_count = 0
        for product_id, metadata in product_metadata.items():
            if metadata['styles']:
                for style in metadata['styles']:
                    confidence = metadata['confidence']['styles']
                    cypher_lines.extend([
                        f"MATCH (p:Product {{id: '{product_id}'}}), (s:Style {{name: '{style.lower()}'}})",
                        f"MERGE (p)-[r:HAS_STYLE]->(s)",
                        f"ON CREATE SET r.confidence = {confidence}, r.created_at = datetime(), r.extraction_source = 'phase1'",
                        f"ON MATCH SET r.updated_at = datetime();",
                        ""
                    ])
                    style_count += 1
        
        script_content = "\n".join(cypher_lines)
        
        # Save to file
        rel_script_file = os.path.join(self.output_dir, "02_create_relationships.cypher")
        with open(rel_script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"✅ Relationship script: {rel_script_file}")
        print(f"📊 Will create {color_count:,} color, {brand_count:,} brand, {style_count:,} style relationships")
        return script_content
    
    def generate_indexes_and_constraints(self) -> str:
        """Generate performance optimization scripts"""
        print("⚡ Generating index and constraint scripts...")
        
        cypher_lines = [
            "// Phase 2: Database Optimization Scripts",
            "// Indexes and constraints for performance",
            f"// Timestamp: {datetime.now().isoformat()}",
            "",
            "// ================================",
            "// CONSTRAINTS",
            "// ================================",
            "",
            "// Unique constraints for node identity",
            "CREATE CONSTRAINT color_name_unique IF NOT EXISTS FOR (c:Color) REQUIRE c.name IS UNIQUE;",
            "CREATE CONSTRAINT brand_name_unique IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE;", 
            "CREATE CONSTRAINT style_name_unique IF NOT EXISTS FOR (s:Style) REQUIRE s.name IS UNIQUE;",
            "",
            "// ================================",
            "// INDEXES",
            "// ================================",
            "",
            "// Performance indexes for common queries",
            "CREATE INDEX color_display_name IF NOT EXISTS FOR (c:Color) ON (c.display_name);",
            "CREATE INDEX brand_display_name IF NOT EXISTS FOR (b:Brand) ON (b.display_name);",
            "CREATE INDEX style_display_name IF NOT EXISTS FOR (s:Style) ON (s.display_name);",
            "",
            "// Relationship confidence indexes for filtering",
            "CREATE INDEX has_color_confidence IF NOT EXISTS FOR ()-[r:HAS_COLOR]-() ON (r.confidence);",
            "CREATE INDEX has_brand_confidence IF NOT EXISTS FOR ()-[r:HAS_BRAND]-() ON (r.confidence);",
            "CREATE INDEX has_style_confidence IF NOT EXISTS FOR ()-[r:HAS_STYLE]-() ON (r.confidence);",
            "",
            "// Timestamp indexes for maintenance",
            "CREATE INDEX color_created_at IF NOT EXISTS FOR (c:Color) ON (c.created_at);",
            "CREATE INDEX brand_created_at IF NOT EXISTS FOR (b:Brand) ON (b.created_at);",
            "CREATE INDEX style_created_at IF NOT EXISTS FOR (s:Style) ON (s.created_at);",
            ""
        ]
        
        script_content = "\n".join(cypher_lines)
        
        # Save to file
        index_script_file = os.path.join(self.output_dir, "03_create_indexes.cypher")
        with open(index_script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"✅ Index script: {index_script_file}")
        return script_content
    
    def generate_validation_queries(self) -> str:
        """Generate validation queries to verify Phase 2 success"""
        print("✅ Generating validation queries...")
        
        cypher_lines = [
            "// Phase 2: Validation Queries",
            "// Verify graph reconstruction success",
            f"// Timestamp: {datetime.now().isoformat()}",
            "",
            "// ================================",
            "// NODE COUNT VALIDATION",
            "// ================================",
            "",
            "// Count all node types",
            "MATCH (c:Color) RETURN 'Colors' as type, count(c) as count;",
            "MATCH (b:Brand) RETURN 'Brands' as type, count(b) as count;", 
            "MATCH (s:Style) RETURN 'Styles' as type, count(s) as count;",
            "MATCH (p:Product) RETURN 'Products' as type, count(p) as count;",
            "",
            "// ================================",
            "// RELATIONSHIP COUNT VALIDATION",
            "// ================================",
            "",
            "// Count all relationship types",
            "MATCH ()-[r:HAS_COLOR]->() RETURN 'HAS_COLOR' as type, count(r) as count;",
            "MATCH ()-[r:HAS_BRAND]->() RETURN 'HAS_BRAND' as type, count(r) as count;",
            "MATCH ()-[r:HAS_STYLE]->() RETURN 'HAS_STYLE' as type, count(r) as count;",
            "",
            "// ================================",
            "// SAMPLE DATA VALIDATION",
            "// ================================",
            "",
            "// Show sample products with all attributes",
            "MATCH (p:Product)",
            "OPTIONAL MATCH (p)-[:HAS_COLOR]->(c:Color)",
            "OPTIONAL MATCH (p)-[:HAS_BRAND]->(b:Brand)",
            "OPTIONAL MATCH (p)-[:HAS_STYLE]->(s:Style)",
            "WITH p, collect(DISTINCT c.name) as colors, collect(DISTINCT b.name) as brands, collect(DISTINCT s.name) as styles",
            "WHERE size(colors) > 0 OR size(brands) > 0 OR size(styles) > 0",
            "RETURN p.title, colors, brands, styles",
            "LIMIT 20;",
            "",
            "// ================================",
            "// CONFIDENCE DISTRIBUTION",
            "// ================================",
            "",
            "// Check confidence score distribution",
            "MATCH ()-[r:HAS_COLOR]->() RETURN r.confidence, count(*) ORDER BY r.confidence;",
            "MATCH ()-[r:HAS_BRAND]->() RETURN r.confidence, count(*) ORDER BY r.confidence;",
            "MATCH ()-[r:HAS_STYLE]->() RETURN r.confidence, count(*) ORDER BY r.confidence;",
            ""
        ]
        
        script_content = "\n".join(cypher_lines)
        
        # Save to file  
        validation_script_file = os.path.join(self.output_dir, "04_validation_queries.cypher")
        with open(validation_script_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"✅ Validation script: {validation_script_file}")
        return script_content
    
    def generate_execution_plan(self) -> str:
        """Generate execution plan README"""
        print("📋 Generating execution plan...")
        
        plan_content = f"""# Phase 2 Execution Plan
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview
Phase 2 reconstructs the graph database using metadata extracted from Phase 1.
This creates the missing Color, Brand, and Style nodes and their relationships.

## Execution Order

### Step 1: Database Preparation
```bash
# Backup current database (CRITICAL!)
neo4j-admin dump --database=neo4j --to=backup_before_phase2.dump

# Verify backup
ls -la backup_before_phase2.dump
```

### Step 2: Index and Constraint Creation
```cypher
# Execute: 03_create_indexes.cypher
# Creates constraints and performance indexes
# Runtime: ~5 minutes
```

### Step 3: Node Creation
```cypher
# Execute: 01_create_nodes.cypher  
# Creates Color, Brand, Style nodes
# Runtime: ~10 minutes
```

### Step 4: Relationship Creation
```cypher
# Execute: 02_create_relationships.cypher
# Links products to attributes
# Runtime: ~2-3 hours (large dataset)
```

### Step 5: Validation
```cypher
# Execute: 04_validation_queries.cypher
# Verify reconstruction success
# Runtime: ~5 minutes
```

## Safety Features
- All operations use MERGE (safe for re-execution)
- Timestamps track creation/updates
- Confidence scores preserved
- Source tracking (extraction_source = 'phase1')

## Rollback Plan
If issues occur:
```bash
# Stop Neo4j
neo4j stop

# Restore backup
neo4j-admin load --database=neo4j --from=backup_before_phase2.dump --force

# Start Neo4j
neo4j start
```

## Expected Results
- ~{analysis.get('unique_colors', 'XX')} Color nodes
- ~{analysis.get('unique_brands', 'XX')} Brand nodes  
- ~{analysis.get('unique_styles', 'XX')} Style nodes
- ~{analysis.get('total_products', 'XX')} products with new relationships

## Performance Notes
- Execute during low-traffic periods
- Monitor memory usage during relationship creation
- Consider batching if memory issues occur

Ready for execution once SWEs clone the graph database!
"""
        
        plan_file = os.path.join(self.output_dir, "EXECUTION_PLAN.md")
        with open(plan_file, 'w', encoding='utf-8') as f:
            f.write(plan_content)
        
        print(f"✅ Execution plan: {plan_file}")
        return plan_content

def main():
    """Run Phase 2 preparation"""
    print("🚀 Phase 2 Preparation Starting...")
    
    # Find the most recent extraction directory
    extraction_dirs = [d for d in os.listdir('.') if d.startswith('full_extraction_')]
    if not extraction_dirs:
        print("❌ No extraction directories found. Run Phase 1 first.")
        return
    
    latest_dir = sorted(extraction_dirs)[-1]
    print(f"📁 Using extraction data: {latest_dir}")
    
    # Initialize preparation
    prep = Phase2Preparation(latest_dir)
    
    try:
        # Analyze extraction data
        analysis, product_metadata = prep.analyze_extraction_data()
        
        # Generate all scripts
        prep.generate_indexes_and_constraints()
        prep.generate_node_creation_scripts(analysis)
        prep.generate_relationship_scripts(product_metadata)
        prep.generate_validation_queries()
        prep.generate_execution_plan()
        
        print("🎉 Phase 2 preparation complete!")
        print(f"📁 Scripts generated in: {prep.output_dir}/")
        print("✅ Ready for execution once graph is cloned!")
        
    except Exception as e:
        print(f"❌ Error during preparation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()