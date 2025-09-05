#!/usr/bin/env python3
"""
Database Analysis Summary
Creates summary report from successful schema analysis data

READ-ONLY: Generates report from collected data
"""

import json
import os
from datetime import datetime

def create_analysis_summary():
    """Create summary from the schema analysis we collected"""
    
    print("📊 Creating Database Analysis Summary...")
    
    # Schema data we collected successfully
    node_data = {
        'User': 2,
        'MemoryState': 6,
        'UserPreference': 0,
        'ProductInteraction': 255,
        'StyleProfile': 0,
        'UserSegment': 0,
        'Product': 6416804,
        'Collection': 20406,
        'Tag': 20422,
        'Brand': 118,
        'Attribute': 26,
        'Style': 0,  # ⚠️ CRITICAL MISSING
        'Color': 0   # ⚠️ CRITICAL MISSING
    }
    
    relationship_data = {
        'IN_COLLECTION': 6392011,
        'TAGGED_WITH': 16918000,
        'HAS_MEMORY': 6,
        'HAS_INTERACTION': 255,
        'REFERS_TO': 255,
        'MADE_BY': 1470876,
        'HAS_ATTRIBUTE': 70000,
        'PURCHASED': 0,
        'VIEWED': 0
    }
    
    # Generate analysis report
    output_dir = f"database_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(output_dir, exist_ok=True)
    
    total_nodes = sum(node_data.values())
    total_relationships = sum(relationship_data.values())
    
    report_lines = [
        "# Neo4j Database Schema Analysis Summary",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 🎯 Critical Findings",
        "",
        "### ✅ Database Scale",
        f"- **Total Nodes**: {total_nodes:,}",
        f"- **Total Relationships**: {total_relationships:,}",
        f"- **Primary Dataset**: 6,416,804 products (99.97% of all nodes)",
        "",
        "### ❌ **CRITICAL MISSING COMPONENTS**",
        "- **Color nodes**: 0 (should have ~15-20)",
        "- **Style nodes**: 0 (should have ~50+)",
        "- **UserPreference nodes**: 0 (personalization missing)",
        "- **StyleProfile nodes**: 0 (user styling missing)",
        "",
        "## 📊 Node Distribution",
        "",
        "| Node Type | Count | Percentage | Status |",
        "|-----------|-------|------------|--------|",
    ]
    
    # Sort nodes by count for table
    sorted_nodes = sorted(node_data.items(), key=lambda x: x[1], reverse=True)
    for node_type, count in sorted_nodes:
        percentage = (count / total_nodes) * 100 if total_nodes > 0 else 0
        status = "❌ MISSING" if count == 0 and node_type in ['Color', 'Style', 'UserPreference'] else "✅"
        report_lines.append(f"| {node_type} | {count:,} | {percentage:.3f}% | {status}")
    
    report_lines.extend([
        "",
        "## 🔗 Relationship Distribution",
        "",
        "| Relationship Type | Count | Percentage | Status |",
        "|-------------------|-------|------------|--------|",
    ])
    
    # Sort relationships by count for table
    sorted_relationships = sorted(relationship_data.items(), key=lambda x: x[1], reverse=True)
    for rel_type, count in sorted_relationships:
        percentage = (count / total_relationships) * 100 if total_relationships > 0 else 0
        status = "❌ UNUSED" if count == 0 else "✅"
        report_lines.append(f"| {rel_type} | {count:,} | {percentage:.2f}% | {status}")
    
    report_lines.extend([
        "",
        "## 🧐 Key Insights",
        "",
        "### Product Coverage",
        f"- **Products**: {node_data['Product']:,} (massive dataset)",
        f"- **Collections**: {node_data['Collection']:,} products organized",
        f"- **Tags**: {node_data['Tag']:,} different tags available", 
        f"- **Brands**: {node_data['Brand']:,} brand entities (very low compared to {node_data['Product']:,} products)",
        "",
        "### Relationship Density",
        f"- **TAGGED_WITH**: {relationship_data['TAGGED_WITH']:,} (avg {relationship_data['TAGGED_WITH']/node_data['Product']:.1f} tags per product)",
        f"- **IN_COLLECTION**: {relationship_data['IN_COLLECTION']:,} ({relationship_data['IN_COLLECTION']/node_data['Product']*100:.1f}% products in collections)",
        f"- **MADE_BY**: {relationship_data['MADE_BY']:,} ({relationship_data['MADE_BY']/node_data['Product']*100:.1f}% products have brand relationships)",
        f"- **HAS_ATTRIBUTE**: {relationship_data['HAS_ATTRIBUTE']:,} ({relationship_data['HAS_ATTRIBUTE']/node_data['Product']*100:.1f}% products have attributes)",
        "",
        "### Missing Critical Relationships",
        "- **HAS_COLOR**: 0 relationships (should be ~5.5M based on Phase 1)",
        "- **HAS_STYLE**: 0 relationships (should be ~4.8M based on Phase 1)", 
        "- **PURCHASED/VIEWED**: 0 user interaction tracking",
        "",
        "## 🚨 **CRITICAL ISSUES IDENTIFIED**",
        "",
        "### 1. Missing Core Fashion Attributes",
        "```",
        "❌ Color nodes: 0 (Phase 1 extracted from 86% of products)",
        "❌ Style nodes: 0 (Phase 1 extracted from 75% of products)", 
        "❌ HAS_COLOR relationships: 0 (should be 5.5M)",
        "❌ HAS_STYLE relationships: 0 (should be 4.8M)",
        "```",
        "",
        "### 2. Brand Relationship Coverage Gap",
        f"- Only {relationship_data['MADE_BY']:,} products have brand relationships",
        f"- That's {relationship_data['MADE_BY']/node_data['Product']*100:.1f}% coverage",
        f"- Phase 1 found brands in 99.7% of products (6.4M)",
        f"- **Missing: ~4.9M brand relationships**",
        "",
        "### 3. Attribute System Underutilized",
        f"- Only {relationship_data['HAS_ATTRIBUTE']:,} attribute relationships",
        f"- {relationship_data['HAS_ATTRIBUTE']/node_data['Product']*100:.2f}% of products have attributes",
        f"- 26 Attribute nodes but minimal usage",
        "",
        "## 🎯 **PHASE 2 IMPACT ANALYSIS**",
        "",
        "### What Phase 2 Will Add",
        "- **New Nodes**: ~15 Colors + ~100 Brands + ~50 Styles = **~165 new nodes**",
        f"- **New Relationships**: ~16.7M new relationships (5.5M + 6.4M + 4.8M)",
        f"- **Database Growth**: +16.7M relationships ({16700000/total_relationships*100:.0f}% increase)",
        "",
        "### Performance Considerations",
        f"- Current relationship count: {total_relationships:,}",
        f"- After Phase 2: {total_relationships + 16700000:,} relationships",
        "- **Critical**: Need indexes on new relationship types",
        "- **Critical**: Consider batch processing for 16.7M relationship creation",
        "",
        "## 🔧 **IMMEDIATE RECOMMENDATIONS**",
        "",
        "### Pre-Phase 2 Optimization",
        "1. **Create indexes** on Product.id, Product.title, Product.description",
        "2. **Monitor memory** during Phase 2 relationship creation", 
        "3. **Batch processing** recommended for 16.7M new relationships",
        "",
        "### Post-Phase 2 Validation",
        "1. **Verify relationship counts** match Phase 1 extraction",
        "2. **Performance test** color/style filtering queries",
        "3. **Index optimization** based on query patterns",
        "",
        "## 🚀 **PHASE 2 READINESS ASSESSMENT**",
        "",
        "| Component | Status | Notes |",
        "|-----------|---------|-------|",
        "| Database Connection | ✅ Ready | Tested successfully |",
        f"| Product Nodes | ✅ Ready | {node_data['Product']:,} products available |",
        f"| Brand Foundation | ⚠️ Partial | Only {node_data['Brand']} brands vs ~100 expected |",
        "| Color/Style Infrastructure | ❌ Missing | Zero nodes, zero relationships |",
        "| Performance Indexes | ❓ Unknown | Need assessment of current indexes |",
        "| Memory Capacity | ❓ Unknown | 16.7M new relationships require validation |",
        "",
        "## 📈 **SUCCESS METRICS POST-PHASE 2**",
        "",
        "### Expected Final State",
        f"- **Color relationships**: {relationship_data.get('HAS_COLOR', 0)} → 5,500,000",
        f"- **Brand relationships**: {relationship_data.get('MADE_BY', 0)} → 6,400,000", 
        f"- **Style relationships**: {relationship_data.get('HAS_STYLE', 0)} → 4,800,000",
        "- **Query performance**: Color filtering <100ms",
        "- **Search accuracy**: Significant improvement in attribute-based search",
        "",
        "---",
        "",
        f"**Analysis Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "**Data Source**: Live Neo4j Production Database",
        "**Analysis Type**: Read-Only Schema Deep Dive",
        "**Next Step**: Execute Phase 2 graph reconstruction when SWEs clone database"
    ]
    
    # Save the report
    report_content = "\n".join(report_lines)
    report_file = os.path.join(output_dir, "DATABASE_ANALYSIS_SUMMARY.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    # Save raw data
    raw_data = {
        'analysis_timestamp': datetime.now().isoformat(),
        'node_counts': node_data,
        'relationship_counts': relationship_data,
        'totals': {
            'nodes': total_nodes,
            'relationships': total_relationships
        },
        'critical_findings': {
            'missing_color_nodes': node_data['Color'] == 0,
            'missing_style_nodes': node_data['Style'] == 0,
            'low_brand_coverage': relationship_data['MADE_BY'] / node_data['Product'] < 0.5,
            'missing_user_preferences': node_data['UserPreference'] == 0
        }
    }
    
    data_file = os.path.join(output_dir, "database_analysis_data.json")
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, indent=2, ensure_ascii=False)
    
    print("✅ Database analysis summary complete!")
    print(f"📁 Report: {report_file}")
    print(f"📊 Data: {data_file}")
    
    # Print key findings
    print("\n🎯 KEY FINDINGS:")
    print(f"✅ Database Scale: {total_nodes:,} nodes, {total_relationships:,} relationships")
    print(f"❌ Missing Critical: Color nodes ({node_data['Color']}), Style nodes ({node_data['Style']})")  
    print(f"⚠️ Low Brand Coverage: {relationship_data['MADE_BY']:,} relationships ({relationship_data['MADE_BY']/node_data['Product']*100:.1f}%)")
    print(f"🚀 Phase 2 Impact: +16.7M relationships ({16700000/total_relationships*100:.0f}% database growth)")
    
    return output_dir

if __name__ == "__main__":
    create_analysis_summary()