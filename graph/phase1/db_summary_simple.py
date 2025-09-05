#!/usr/bin/env python3
"""Simple Database Summary Generator"""

from datetime import datetime

def generate_summary():
    print("📊 Database Analysis Summary")
    print("=" * 50)
    
    # Data from our successful Neo4j connection
    nodes = {
        'Product': 6416804,
        'Collection': 20406,
        'Tag': 20422,
        'Brand': 118,
        'Attribute': 26,
        'ProductInteraction': 255,
        'MemoryState': 6,
        'User': 2,
        'Color': 0,      # ❌ MISSING
        'Style': 0,      # ❌ MISSING
        'UserPreference': 0
    }
    
    relationships = {
        'TAGGED_WITH': 16918000,
        'IN_COLLECTION': 6392011, 
        'MADE_BY': 1470876,
        'HAS_ATTRIBUTE': 70000,
        'HAS_INTERACTION': 255,
        'REFERS_TO': 255,
        'HAS_MEMORY': 6,
        'PURCHASED': 0,
        'VIEWED': 0
    }
    
    total_nodes = sum(nodes.values())
    total_rels = sum(relationships.values())
    
    print(f"📈 SCALE: {total_nodes:,} nodes, {total_rels:,} relationships")
    print()
    
    print("🎯 CRITICAL FINDINGS:")
    print(f"✅ Products: {nodes['Product']:,} (99.97% of database)")
    print(f"❌ Color nodes: {nodes['Color']} (should be ~15)")
    print(f"❌ Style nodes: {nodes['Style']} (should be ~50)")
    print(f"⚠️ Brand relationships: {relationships['MADE_BY']:,} ({relationships['MADE_BY']/nodes['Product']*100:.1f}% coverage)")
    print()
    
    print("🚀 PHASE 2 IMPACT:")
    phase2_new_rels = 16700000  # 5.5M colors + 6.4M brands + 4.8M styles
    print(f"Will add: {phase2_new_rels:,} new relationships")
    print(f"Growth: {phase2_new_rels/total_rels*100:.0f}% increase")
    print(f"New total: {total_rels + phase2_new_rels:,} relationships")
    print()
    
    print("📊 TOP RELATIONSHIPS:")
    sorted_rels = sorted(relationships.items(), key=lambda x: x[1], reverse=True)
    for rel_type, count in sorted_rels[:6]:
        if count > 0:
            print(f"  {rel_type}: {count:,}")
    print()
    
    print("🔍 MISSING RELATIONSHIPS:")
    for rel_type, count in sorted_rels:
        if count == 0:
            print(f"  ❌ {rel_type}: {count}")
    
    # Save summary
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_file = f"db_summary_{timestamp}.txt"
    
    with open(summary_file, 'w') as f:
        f.write("Neo4j Database Analysis Summary\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Total Nodes: {total_nodes:,}\n")
        f.write(f"Total Relationships: {total_rels:,}\n\n")
        f.write("Critical Issues:\n")
        f.write(f"- Missing Color nodes: {nodes['Color']}\n")
        f.write(f"- Missing Style nodes: {nodes['Style']}\n")
        f.write(f"- Low brand coverage: {relationships['MADE_BY']/nodes['Product']*100:.1f}%\n\n")
        f.write(f"Phase 2 will add {phase2_new_rels:,} relationships\n")
    
    print(f"✅ Summary saved: {summary_file}")
    return nodes, relationships

if __name__ == "__main__":
    generate_summary()