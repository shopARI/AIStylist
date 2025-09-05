#!/usr/bin/env python3
"""
Fashion Ontology Discovery System - Fixed Version
Analyzes extraction data to build color compatibility matrices and style relationships
"""

import json
import os
import numpy as np
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple
from datetime import datetime

def main():
    """Run fashion ontology discovery"""
    print("🧠 Fashion Ontology Discovery Starting...")
    
    # Find the most recent extraction directory
    extraction_dirs = [d for d in os.listdir('.') if d.startswith('full_extraction_')]
    if not extraction_dirs:
        print("❌ No extraction directories found. Run Phase 1 first.")
        return
    
    latest_dir = sorted(extraction_dirs)[-1]
    print(f"📁 Using extraction data: {latest_dir}")
    
    # Simple analysis for now
    print("📊 Loading sample extraction data...")
    
    # Get first few batch files for analysis
    batch_files = [f for f in os.listdir(latest_dir) if f.startswith('batch_') and f.endswith('.json')]
    sample_batches = sorted(batch_files)[:10]  # First 10 batches
    
    color_combos = []
    style_combos = []
    brand_styles = defaultdict(Counter)
    
    total_products = 0
    
    for batch_file in sample_batches:
        batch_path = os.path.join(latest_dir, batch_file)
        with open(batch_path, 'r', encoding='utf-8') as f:
            batch_data = json.load(f)
        
        for item in batch_data:
            total_products += 1
            metadata = item['extracted_metadata']
            
            # Track color combinations
            colors = metadata.get('colors', [])
            if len(colors) > 1:
                for i in range(len(colors)):
                    for j in range(i+1, len(colors)):
                        combo = tuple(sorted([colors[i], colors[j]]))
                        color_combos.append(combo)
            
            # Track style combinations
            styles = metadata.get('styles', [])
            if len(styles) > 1:
                for i in range(len(styles)):
                    for j in range(i+1, len(styles)):
                        combo = tuple(sorted([styles[i], styles[j]]))
                        style_combos.append(combo)
            
            # Track brand-style associations
            brands = metadata.get('brands', [])
            for brand in brands:
                for style in styles:
                    brand_styles[brand][style] += 1
    
    print(f"✅ Analyzed {total_products:,} products from {len(sample_batches)} batches")
    
    # Color compatibility analysis
    color_freq = Counter(color_combos)
    print("\n🎨 TOP COLOR COMBINATIONS:")
    for combo, count in color_freq.most_common(10):
        print(f"  {combo[0].title()} + {combo[1].title()}: {count} products")
    
    # Style compatibility analysis  
    style_freq = Counter(style_combos)
    print("\n👔 TOP STYLE COMBINATIONS:")
    for combo, count in style_freq.most_common(10):
        print(f"  {combo[0].title()} + {combo[1].title()}: {count} products")
    
    # Brand style analysis
    print("\n🏷️ TOP BRAND-STYLE ASSOCIATIONS:")
    for brand, style_counts in list(brand_styles.items())[:5]:
        if sum(style_counts.values()) >= 5:
            print(f"  {brand}:")
            for style, count in style_counts.most_common(3):
                print(f"    - {style.title()}: {count} products")
    
    # Create output directory and save results
    output_dir = f"fashion_ontology_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save analysis results
    results = {
        'analysis_info': {
            'timestamp': datetime.now().isoformat(),
            'products_analyzed': total_products,
            'batches_processed': len(sample_batches)
        },
        'color_combinations': [{'colors': list(combo), 'frequency': count} 
                              for combo, count in color_freq.most_common(20)],
        'style_combinations': [{'styles': list(combo), 'frequency': count}
                              for combo, count in style_freq.most_common(20)],
        'brand_style_associations': {brand: dict(styles.most_common(5))
                                   for brand, styles in brand_styles.items()
                                   if sum(styles.values()) >= 3}
    }
    
    results_file = os.path.join(output_dir, "fashion_ontology_analysis.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Fashion ontology analysis complete!")
    print(f"📁 Results saved to: {results_file}")
    print("🎉 Ready to enhance recommendation algorithms!")

if __name__ == "__main__":
    main()