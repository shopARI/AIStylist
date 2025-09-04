#!/usr/bin/env python3
"""
Fashion Ontology Discovery System
Analyzes extraction data to build color compatibility matrices and style relationships

READ-ONLY: No database writes, only ontology analysis and discovery
"""

import json
import os
import numpy as np
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple
from datetime import datetime

class FashionOntologyBuilder:
    """Builds fashion knowledge graphs from extraction data"""
    
    def __init__(self, extraction_dir: str):
        self.extraction_dir = extraction_dir
        self.output_dir = f"fashion_ontology_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Fashion knowledge base
        self.color_families = {
            'warm': ['red', 'orange', 'yellow', 'pink'],
            'cool': ['blue', 'green', 'purple'],
            'neutral': ['black', 'white', 'gray', 'brown', 'beige']
        }
        
        self.style_categories = {
            'formal': ['formal', 'business', 'professional', 'elegant', 'sophisticated'],
            'casual': ['casual', 'relaxed', 'comfortable', 'everyday'],
            'sporty': ['athletic', 'sport', 'active', 'performance', 'gym'],
            'trendy': ['trendy', 'fashionable', 'stylish', 'modern', 'contemporary'],
            'vintage': ['vintage', 'retro', 'classic', 'timeless'],
            'bohemian': ['boho', 'bohemian', 'free-spirit', 'artistic']
        }
    
    def load_extraction_data(self) -> Dict:
        """Load and aggregate all extraction data"""
        print("📊 Loading extraction data for ontology analysis...")
        
        products_data = []
        color_combinations = []
        style_combinations = []
        brand_style_pairs = []
        
        # Process all batch files
        batch_files = [f for f in os.listdir(self.extraction_dir) if f.startswith('batch_') and f.endswith('.json')]
        
        for batch_file in sorted(batch_files)[:20]:  # Limit for analysis speed
            batch_path = os.path.join(self.extraction_dir, batch_file)
            with open(batch_path, 'r', encoding='utf-8') as f:
                batch_data = json.load(f)
            
            for item in batch_data:
                metadata = item['extracted_metadata']
                confidence = item['confidence_scores']
                
                # Skip low-confidence extractions
                if confidence.get('colors', 0) < 0.5 and confidence.get('styles', 0) < 0.5:
                    continue
                
                colors = metadata.get('colors', [])
                styles = metadata.get('styles', [])
                brands = metadata.get('brands', [])
                
                if colors or styles or brands:
                    products_data.append({
                        'id': item['product_id'],
                        'title': item['title'],
                        'colors': colors,
                        'styles': styles,
                        'brands': brands,
                        'confidence': confidence
                    })
                
                # Track combinations within products
                if len(colors) > 1:
                    color_combinations.extend([tuple(sorted(colors))])
                if len(styles) > 1:
                    style_combinations.extend([tuple(sorted(styles))])
                if brands and styles:
                    for brand in brands:
                        for style in styles:
                            brand_style_pairs.append((brand, style))
        
        print(f"✅ Loaded {len(products_data):,} products for ontology analysis")
        
        return {
            'products': products_data,
            'color_combinations': color_combinations,
            'style_combinations': style_combinations,
            'brand_style_pairs': brand_style_pairs
        }
    
    def analyze_color_compatibility(self, data: Dict) -> Dict:
        """Build color compatibility matrix"""
        print("🎨 Analyzing color compatibility patterns...")
        
        # Count color co-occurrences
        color_cooccurrence = defaultdict(int)
        single_colors = Counter()
        
        for product in data['products']:
            colors = product['colors']
            if not colors:
                continue
                
            # Single color frequency
            for color in colors:
                single_colors[color] += 1
            
            # Color pairs within same product
            if len(colors) > 1:
                for i, color1 in enumerate(colors):
                    for color2 in colors[i+1:]:
                        pair = tuple(sorted([color1, color2]))
                        color_cooccurrence[pair] += 1
        
        # Calculate compatibility scores
        compatibility_matrix = {}
        for (color1, color2), cooccur_count in color_cooccurrence.items():
            # PMI-based compatibility score
            total_products = len(data['products'])
            color1_freq = single_colors[color1]
            color2_freq = single_colors[color2] 
            
            expected = (color1_freq * color2_freq) / total_products
            compatibility_score = cooccur_count / expected if expected > 0 else 0
            
            compatibility_matrix[(color1, color2)] = {
                'cooccurrence': cooccur_count,
                'compatibility_score': compatibility_score,
                'color1_freq': color1_freq,
                'color2_freq': color2_freq
            }
        
        # Group by compatibility levels
        highly_compatible = [(pair, score) for pair, score in compatibility_matrix.items() 
                           if score['compatibility_score'] > 2.0 and score['cooccurrence'] >= 10]
        moderately_compatible = [(pair, score) for pair, score in compatibility_matrix.items() 
                               if 1.0 < score['compatibility_score'] <= 2.0 and score['cooccurrence'] >= 5]
        
        # Color family analysis
        family_compatibility = defaultdict(list)
        for (color1, color2), score in compatibility_matrix.items():
            family1 = self.get_color_family(color1)
            family2 = self.get_color_family(color2)
            
            if family1 and family2:
                family_key = tuple(sorted([family1, family2]))
                family_compatibility[family_key].append(score['compatibility_score'])
        
        family_avg_compatibility = {}
        for family_pair, scores in family_compatibility.items():
            family_avg_compatibility[family_pair] = {
                'avg_compatibility': np.mean(scores),
                'sample_count': len(scores),
                'std_dev': np.std(scores)
            }
        
        analysis = {
            'total_color_pairs': len(compatibility_matrix),
            'highly_compatible': sorted(highly_compatible, key=lambda x: x[1]['compatibility_score'], reverse=True)[:20],
            'moderately_compatible': sorted(moderately_compatible, key=lambda x: x[1]['compatibility_score'], reverse=True)[:20],
            'family_compatibility': dict(family_avg_compatibility),
            'single_color_frequency': dict(single_colors.most_common(20))
        }
        
        # Save analysis
        color_analysis_file = os.path.join(self.output_dir, "color_compatibility_analysis.json")
        with open(color_analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Color compatibility analysis saved: {color_analysis_file}")
        return analysis
    
    def analyze_style_relationships(self, data: Dict) -> Dict:
        """Analyze style combination patterns"""
        print("👔 Analyzing style relationship patterns...")
        
        # Count style co-occurrences
        style_cooccurrence = defaultdict(int)
        single_styles = Counter()
        style_categories_found = defaultdict(list)
        
        for product in data['products']:
            styles = product['styles']
            if not styles:
                continue
            
            # Single style frequency
            for style in styles:
                single_styles[style] += 1
                # Categorize style
                category = self.get_style_category(style)
                if category:
                    style_categories_found[category].append(style)
            
            # Style pairs within same product
            if len(styles) > 1:
                for i, style1 in enumerate(styles):
                    for style2 in styles[i+1:]:
                        pair = tuple(sorted([style1, style2]))
                        style_cooccurrence[pair] += 1
        
        # Analyze category mixing
        category_mixing = defaultdict(int)
        for product in data['products']:
            styles = product['styles']
            if len(styles) > 1:
                categories = [self.get_style_category(s) for s in styles]
                categories = [c for c in categories if c]  # Remove None
                if len(set(categories)) > 1:  # Mixed categories
                    category_pair = tuple(sorted(set(categories)))
                    category_mixing[category_pair] += 1
        
        # Calculate style compatibility
        style_compatibility = {}
        for (style1, style2), cooccur_count in style_cooccurrence.items():
            if cooccur_count >= 3:  # Minimum threshold
                total_products = len(data['products'])
                style1_freq = single_styles[style1]
                style2_freq = single_styles[style2]
                
                expected = (style1_freq * style2_freq) / total_products
                compatibility_score = cooccur_count / expected if expected > 0 else 0
                
                style_compatibility[(style1, style2)] = {
                    'cooccurrence': cooccur_count,
                    'compatibility_score': compatibility_score
                }
        
        analysis = {
            'total_style_pairs': len(style_compatibility),
            'most_compatible_styles': sorted(
                [(pair, score) for pair, score in style_compatibility.items()],
                key=lambda x: x[1]['compatibility_score'], 
                reverse=True
            )[:15],
            'category_mixing_frequency': dict(category_mixing),
            'single_style_frequency': dict(single_styles.most_common(20)),
            'styles_by_category': {k: list(set(v)) for k, v in style_categories_found.items()}
        }
        
        # Save analysis
        style_analysis_file = os.path.join(self.output_dir, "style_relationship_analysis.json")
        with open(style_analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Style relationship analysis saved: {style_analysis_file}")
        return analysis
    
    def analyze_brand_intelligence(self, data: Dict) -> Dict:
        """Analyze brand positioning and style associations"""
        print("🏷️ Analyzing brand intelligence patterns...")
        
        brand_styles = defaultdict(Counter)
        brand_colors = defaultdict(Counter)
        brand_price_ranges = defaultdict(list)
        
        for product in data['products']:
            brands = product['brands']
            styles = product['styles']
            colors = product['colors']
            
            for brand in brands:
                # Brand-style associations
                for style in styles:
                    brand_styles[brand][style] += 1
                
                # Brand-color associations  
                for color in colors:
                    brand_colors[brand][color] += 1
        
        # Identify brand archetypes
        brand_archetypes = {}
        for brand, style_counts in brand_styles.items():
            if sum(style_counts.values()) >= 5:  # Minimum data threshold
                top_styles = style_counts.most_common(3)
                dominant_categories = [self.get_style_category(style) for style, _ in top_styles]
                dominant_categories = [c for c in dominant_categories if c]
                
                if dominant_categories:
                    archetype = Counter(dominant_categories).most_common(1)[0][0]
                    brand_archetypes[brand] = {
                        'archetype': archetype,
                        'top_styles': top_styles,
                        'style_diversity': len(style_counts),
                        'total_products': sum(style_counts.values())
                    }
        
        analysis = {
            'brand_style_associations': {brand: dict(styles.most_common(5)) 
                                       for brand, styles in brand_styles.items() 
                                       if sum(styles.values()) >= 3},
            'brand_color_preferences': {brand: dict(colors.most_common(5))
                                      for brand, colors in brand_colors.items() 
                                      if sum(colors.values()) >= 3},
            'brand_archetypes': brand_archetypes,
            'total_brands_analyzed': len(brand_styles)
        }
        
        # Save analysis
        brand_analysis_file = os.path.join(self.output_dir, "brand_intelligence_analysis.json")
        with open(brand_analysis_file, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Brand intelligence analysis saved: {brand_analysis_file}")
        return analysis
    
    def get_color_family(self, color: str) -> str:
        """Classify color into warm/cool/neutral family"""
        color_lower = color.lower()
        for family, colors in self.color_families.items():
            if color_lower in colors:
                return family
        return 'other'
    
    def get_style_category(self, style: str) -> str:
        """Classify style into category"""
        style_lower = style.lower()
        for category, styles in self.style_categories.items():
            if any(s in style_lower for s in styles):
                return category
        return None
    
    def generate_ontology_rules(self, color_analysis: Dict, style_analysis: Dict, brand_analysis: Dict) -> str:
        """Generate fashion ontology rules for recommendation engine"""
        print("🧠 Generating fashion ontology rules...")
        
        rules = [
            "# Fashion Ontology Rules",
            f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "# For use in recommendation and styling algorithms",
            "",
            "## COLOR COMPATIBILITY RULES",
            "",
            "### Highly Compatible Color Pairs",
        ]
        
        # Color compatibility rules
        for (color1, color2), score_data in color_analysis['highly_compatible'][:10]:
            compatibility = score_data['compatibility_score']
            cooccur = score_data['cooccurrence']
            rules.append(f"- {color1.title()} + {color2.title()}: compatibility={compatibility:.2f}, evidence={cooccur} products")
        
        rules.extend([
            "",
            "### Color Family Guidelines",
        ])
        
        for family_pair, stats in color_analysis['family_compatibility'].items():
            if stats['sample_count'] >= 10:
                avg_compat = stats['avg_compatibility']
                count = stats['sample_count']
                rules.append(f"- {' + '.join(family_pair)} family mixing: avg_compatibility={avg_compat:.2f}, samples={count}")
        
        rules.extend([
            "",
            "## STYLE COMBINATION RULES", 
            "",
            "### Compatible Style Pairs",
        ])
        
        # Style compatibility rules
        for (style1, style2), score_data in style_analysis['most_compatible_styles'][:10]:
            compatibility = score_data['compatibility_score']
            cooccur = score_data['cooccurrence']
            rules.append(f"- {style1.title()} + {style2.title()}: compatibility={compatibility:.2f}, evidence={cooccur} products")
        
        rules.extend([
            "",
            "### Category Mixing Patterns",
        ])
        
        for category_pair, frequency in sorted(style_analysis['category_mixing_frequency'].items(), 
                                             key=lambda x: x[1], reverse=True)[:8]:
            rules.append(f"- {' + '.join(category_pair)} categories: {frequency} mixed products")
        
        rules.extend([
            "",
            "## BRAND INTELLIGENCE RULES",
            "",
            "### Brand Archetypes",
        ])
        
        # Brand archetype rules
        archetype_brands = defaultdict(list)
        for brand, data in brand_analysis['brand_archetypes'].items():
            archetype = data['archetype']
            product_count = data['total_products']
            if product_count >= 10:
                archetype_brands[archetype].append((brand, product_count))
        
        for archetype, brand_list in archetype_brands.items():
            rules.append(f"- {archetype.title()} brands:")
            for brand, count in sorted(brand_list, key=lambda x: x[1], reverse=True)[:5]:
                rules.append(f"  - {brand}: {count} products")
        
        rules.extend([
            "",
            "## RECOMMENDATION ALGORITHMS",
            "",
            "### Color Recommendation Logic",
            "```python",
            "def recommend_compatible_colors(base_color):",
            "    # Use compatibility matrix above",
            "    compatible = get_highly_compatible_colors(base_color)",
            "    return compatible[:3]  # Top 3 suggestions",
            "```",
            "",
            "### Style Mixing Guidelines", 
            "```python",
            "def validate_style_combination(styles):",
            "    # Check if style categories can mix",
            "    categories = [get_style_category(s) for s in styles]",
            "    return is_valid_category_mix(categories)",
            "```",
            "",
            "### Brand-Aware Styling",
            "```python", 
            "def brand_style_suggestions(brand):",
            "    archetype = get_brand_archetype(brand)",
            "    return get_archetype_compatible_styles(archetype)",
            "```"
        ]
        
        rules_content = "\n".join(rules)
        
        # Save rules
        rules_file = os.path.join(self.output_dir, "FASHION_ONTOLOGY_RULES.md")
        with open(rules_file, 'w', encoding='utf-8') as f:
            f.write(rules_content)
        
        print(f"✅ Fashion ontology rules generated: {rules_file}")
        return rules_content

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
    
    # Initialize ontology builder
    ontology = FashionOntologyBuilder(latest_dir)
    
    try:
        # Load data
        data = ontology.load_extraction_data()
        
        # Run all analyses
        color_analysis = ontology.analyze_color_compatibility(data)
        style_analysis = ontology.analyze_style_relationships(data)
        brand_analysis = ontology.analyze_brand_intelligence(data)
        
        # Generate ontology rules
        ontology.generate_ontology_rules(color_analysis, style_analysis, brand_analysis)
        
        print("🎉 Fashion ontology discovery complete!")
        print(f"📁 Results saved in: {ontology.output_dir}/")
        print("✅ Ready to enhance recommendation algorithms!")
        
    except Exception as e:
        print(f"❌ Error during ontology discovery: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()