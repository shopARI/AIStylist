from config import get_database_config, get_ai_config, get_system_config
"""
Test the complete data extraction pipeline
Phase 1: Read-only testing of all extractors on real database sample
"""

import asyncio
import logging
import sys
import os
from typing import List, Dict, Any
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from data_extraction.extractor_base import DatabaseReader, ExtractionPipeline, ProductData
from data_extraction.color_extractor import ColorExtractor
from data_extraction.brand_extractor import BrandExtractor  
from data_extraction.style_extractor import StyleExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("extraction_test")

async def test_extraction_pipeline():
    """Test the complete extraction pipeline on real data"""
    
    logger.info("=== STARTING EXTRACTION PIPELINE TEST ===")
    
    # Database connection from environment
    neo4j_url = "bolt://0.0.0.0:17687"
    neo4j_user = "neo4j" 
    neo4j_password = self.db_config.neo4j_password
    
    # Initialize database reader
    db_reader = None
    try:
        db_reader = DatabaseReader(neo4j_url, neo4j_user, neo4j_password)
        
        # Get database statistics
        total_products = db_reader.get_product_count()
        existing_brands = db_reader.get_existing_brands()
        
        logger.info(f"Database contains {total_products:,} total products")
        logger.info(f"Found {len(existing_brands)} existing brand nodes")
        
        # Initialize extraction pipeline
        pipeline = ExtractionPipeline(db_reader)
        
        # Add extractors to pipeline
        color_extractor = ColorExtractor(use_llm=True)
        brand_extractor = BrandExtractor(known_brands=set(existing_brands), use_llm=True)
        style_extractor = StyleExtractor(use_llm=True)
        
        pipeline.add_extractor(color_extractor)
        pipeline.add_extractor(brand_extractor)
        pipeline.add_extractor(style_extractor)
        
        # Test on sample data
        logger.info("Testing extractors on sample data...")
        
        sample_sizes = [10, 50, 100]  # Progressive testing
        
        for sample_size in sample_sizes:
            logger.info(f"\n--- Testing with {sample_size} products ---")
            
            # Run extraction on sample
            results = await pipeline.run_sample_extraction(sample_size)
            
            # Analyze results
            analysis = analyze_extraction_results(results)
            print_analysis(analysis, sample_size)
            
            # Save results for manual inspection
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = f"extraction_results_{sample_size}_{timestamp}.json"
            pipeline.save_results(results, results_file)
            logger.info(f"Saved {len(results)} results to {results_file}")
            
            # Break if accuracy is too low
            if analysis['overall_success_rate'] < 0.5:
                logger.warning("Low success rate detected, investigating...")
                break
        
        # Print final pipeline statistics
        print("\n" + "="*60)
        print("FINAL PIPELINE STATISTICS")
        print("="*60)
        pipeline.print_pipeline_stats()
        
    except Exception as e:
        logger.error(f"Pipeline test failed: {e}", exc_info=True)
        return False
    
    finally:
        if db_reader:
            db_reader.close()
    
    return True

def analyze_extraction_results(results: List) -> Dict[str, Any]:
    """Analyze extraction results for quality metrics"""
    
    total_products = len(results)
    if total_products == 0:
        return {'overall_success_rate': 0.0}
    
    # Count successful extractions by type
    colors_found = sum(1 for r in results if r.colors)
    brands_found = sum(1 for r in results if r.brands) 
    styles_found = sum(1 for r in results if r.styles)
    
    # Count confidence scores
    high_confidence_color = sum(1 for r in results if r.confidence_scores.get('color_extraction', 0) > 0.8)
    high_confidence_brand = sum(1 for r in results if r.confidence_scores.get('brand_extraction', 0) > 0.8)
    high_confidence_style = sum(1 for r in results if r.confidence_scores.get('style_classification', 0) > 0.8)
    
    # Average confidence scores
    avg_color_confidence = sum(r.confidence_scores.get('color_extraction', 0) for r in results) / total_products
    avg_brand_confidence = sum(r.confidence_scores.get('brand_extraction', 0) for r in results) / total_products
    avg_style_confidence = sum(r.confidence_scores.get('style_classification', 0) for r in results) / total_products
    
    # Overall success rate (at least one extraction successful)
    successful_products = sum(1 for r in results if (r.colors or r.brands or r.styles))
    overall_success_rate = successful_products / total_products
    
    # Detailed statistics
    color_stats = collect_extraction_stats([r.colors for r in results])
    brand_stats = collect_extraction_stats([r.brands for r in results])
    style_stats = collect_extraction_stats([r.styles for r in results])
    
    return {
        'total_products': total_products,
        'overall_success_rate': overall_success_rate,
        
        # Success rates by type
        'colors_found_rate': colors_found / total_products,
        'brands_found_rate': brands_found / total_products,
        'styles_found_rate': styles_found / total_products,
        
        # High confidence rates
        'high_confidence_color_rate': high_confidence_color / total_products,
        'high_confidence_brand_rate': high_confidence_brand / total_products,
        'high_confidence_style_rate': high_confidence_style / total_products,
        
        # Average confidence
        'avg_color_confidence': avg_color_confidence,
        'avg_brand_confidence': avg_brand_confidence,
        'avg_style_confidence': avg_style_confidence,
        
        # Detailed stats
        'color_stats': color_stats,
        'brand_stats': brand_stats,
        'style_stats': style_stats
    }

def collect_extraction_stats(extractions: List[List[str]]) -> Dict[str, Any]:
    """Collect detailed statistics for a specific extraction type"""
    
    # Flatten and count occurrences
    all_items = []
    for extraction in extractions:
        all_items.extend(extraction)
    
    # Count frequencies
    from collections import Counter
    item_counts = Counter(all_items)
    
    return {
        'total_extractions': len(all_items),
        'unique_items': len(item_counts),
        'top_10_items': item_counts.most_common(10),
        'avg_items_per_product': len(all_items) / len(extractions) if extractions else 0,
        'products_with_multiple_items': sum(1 for ext in extractions if len(ext) > 1)
    }

def print_analysis(analysis: Dict[str, Any], sample_size: int):
    """Print formatted analysis results"""
    
    print(f"\n📊 EXTRACTION ANALYSIS (Sample: {sample_size} products)")
    print("-" * 50)
    
    # Overall metrics
    print(f"Overall Success Rate: {analysis['overall_success_rate']:.1%}")
    print()
    
    # Success rates by type
    print("Success Rates by Type:")
    print(f"  Colors Found:  {analysis['colors_found_rate']:.1%}")
    print(f"  Brands Found:  {analysis['brands_found_rate']:.1%}")  
    print(f"  Styles Found:  {analysis['styles_found_rate']:.1%}")
    print()
    
    # High confidence rates
    print("High Confidence Rates (>80%):")
    print(f"  Colors:  {analysis['high_confidence_color_rate']:.1%}")
    print(f"  Brands:  {analysis['high_confidence_brand_rate']:.1%}")
    print(f"  Styles:  {analysis['high_confidence_style_rate']:.1%}")
    print()
    
    # Average confidence
    print("Average Confidence Scores:")
    print(f"  Colors:  {analysis['avg_color_confidence']:.2f}")
    print(f"  Brands:  {analysis['avg_brand_confidence']:.2f}")
    print(f"  Styles:  {analysis['avg_style_confidence']:.2f}")
    print()
    
    # Top extracted items
    print("Top Extracted Colors:")
    for item, count in analysis['color_stats']['top_10_items'][:5]:
        print(f"  {item}: {count}")
    
    print("\nTop Extracted Brands:")
    for item, count in analysis['brand_stats']['top_10_items'][:5]:
        print(f"  {item}: {count}")
    
    print("\nTop Extracted Styles:")
    for item, count in analysis['style_stats']['top_10_items'][:5]:
        print(f"  {item}: {count}")

async def test_individual_extractors():
    """Test individual extractors on sample data"""
    
    logger.info("\n=== TESTING INDIVIDUAL EXTRACTORS ===")
    
    # Sample products from our database analysis
    test_products = [
        ProductData(
            "1", 
            "Journee Collection Women's Tru Comfort Foam Kinsley Sneaker",
            "Liven up your everyday routine with the Kinsley by Journee Collection. This classic sneaker is rendered with corduroy uppers and satin laces for a fresh look.",
            49.99
        ),
        ProductData(
            "2",
            "Button Up Cardigan", 
            "This cardigan will be a sweater-rotation favorite. Designed for both warmth and style. Long-sleeve cardigan boasts premium materials with V-neck and hammered silver buttons.",
            36.00
        ),
        ProductData(
            "3",
            "Theory Turtleneck Sweater",
            "The Theory Turtleneck Sweater in ivory cashmere is the epitome of luxury and comfort. Ultra-soft cashmere in neutral ivory hue.",
            205.00
        )
    ]
    
    # Test each extractor
    extractors = [
        ColorExtractor(use_llm=True),
        BrandExtractor(use_llm=True), 
        StyleExtractor(use_llm=True)
    ]
    
    for product in test_products:
        print(f"\n--- Testing Product: {product.title} ---")
        
        for extractor in extractors:
            try:
                result = await extractor.extract(product)
                extractor_type = extractor.name.replace('_extractor', '').title()
                
                if extractor.name == 'color_extractor':
                    items = result.get('colors', [])
                elif extractor.name == 'brand_extractor':
                    items = result.get('brands', [])
                else:  # style_extractor
                    items = result.get('styles', [])
                
                confidence = result.get('confidence_scores', {}).get(list(result['confidence_scores'].keys())[0], 0.0)
                
                print(f"{extractor_type}: {items} (confidence: {confidence:.2f})")
                
            except Exception as e:
                logger.error(f"Extractor {extractor.name} failed: {e}")

if __name__ == "__main__":
    # Run tests
    async def main():
        # Test individual extractors first
        await test_individual_extractors()
        
        # Then test full pipeline
        success = await test_extraction_pipeline()
        
        if success:
            print("\n✅ Extraction pipeline test completed successfully!")
        else:
            print("\n❌ Extraction pipeline test failed!")
            sys.exit(1)
    
    asyncio.run(main())