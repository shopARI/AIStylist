#!/usr/bin/env python3
from config import get_database_config, get_ai_config, get_system_config
"""
Production Run Script for Phase 1 Data Extraction
Processes ALL 6.4M products safely (read-only)
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime
from typing import Dict, Any, List

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from data_extraction import (
    DatabaseReader, ExtractionPipeline, 
    ColorExtractor, BrandExtractor, StyleExtractor
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('phase1_production.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("phase1_production")

class ProductionExtractor:
    """Production-scale extraction with batch processing and progress tracking"""
    
    def __init__(self, batch_size: int = 1000, max_products: int = None):
        self.batch_size = batch_size
        self.max_products = max_products
        self.total_processed = 0
        self.total_successful = 0
        self.start_time = None
        
        # Database connection
        self.db_config = get_database_config()
        self.neo4j_url = self.db_config.neo4j_url
        self.neo4j_user = self.db_config.neo4j_user 
        self.neo4j_password = self.db_config.neo4j_password
        
        self.db_reader = None
        self.pipeline = None
    
    async def initialize(self):
        """Initialize database connection and pipeline"""
        logger.info("=== PHASE 1 PRODUCTION EXTRACTION STARTING ===")
        
        # Connect to database
        self.db_reader = DatabaseReader(self.neo4j_url, self.neo4j_user, self.neo4j_password)
        
        # Get total count
        total_products = self.db_reader.get_product_count()
        logger.info(f"Total products in database: {total_products:,}")
        
        if self.max_products:
            logger.info(f"Limited run: processing {self.max_products:,} products")
        
        # Get existing brands for brand extractor
        existing_brands = self.db_reader.get_existing_brands()
        logger.info(f"Found {len(existing_brands)} existing brand nodes")
        
        # Initialize pipeline
        self.pipeline = ExtractionPipeline(self.db_reader)
        
        # Add extractors
        color_extractor = ColorExtractor(use_llm=True)
        brand_extractor = BrandExtractor(known_brands=set(existing_brands), use_llm=True)
        style_extractor = StyleExtractor(use_llm=True)
        
        self.pipeline.add_extractor(color_extractor)
        self.pipeline.add_extractor(brand_extractor)
        self.pipeline.add_extractor(style_extractor)
        
        logger.info("Pipeline initialized with all extractors")
    
    async def run_production_extraction(self):
        """Run extraction on all products in batches"""
        
        await self.initialize()
        self.start_time = datetime.now()
        
        # Create output directory
        output_dir = f"extraction_results_{self.start_time.strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(output_dir, exist_ok=True)
        
        batch_num = 0
        offset = 0
        all_results = []
        
        try:
            while True:
                # Check if we've reached the limit
                if self.max_products and offset >= self.max_products:
                    logger.info(f"Reached maximum products limit: {self.max_products:,}")
                    break
                
                # Adjust batch size for final batch
                current_batch_size = self.batch_size
                if self.max_products:
                    remaining = self.max_products - offset
                    current_batch_size = min(self.batch_size, remaining)
                
                logger.info(f"Processing batch {batch_num + 1}: products {offset:,} to {offset + current_batch_size:,}")
                
                # Get batch of products
                products = self.db_reader.get_product_sample(current_batch_size, offset)
                
                if not products:
                    logger.info("No more products to process")
                    break
                
                # Process batch
                batch_results = await self.pipeline.process_batch(products)
                
                # Update counters
                self.total_processed += len(products)
                self.total_successful += len(batch_results)
                
                # Save batch results
                batch_file = os.path.join(output_dir, f"batch_{batch_num:04d}.json")
                self.save_batch_results(batch_results, batch_file)
                
                # Add to master results
                all_results.extend(batch_results)
                
                # Progress report
                self.print_progress_report(batch_num + 1)
                
                batch_num += 1
                offset += current_batch_size
                
                # Memory management - save and clear every 10 batches
                if batch_num % 10 == 0:
                    logger.info(f"Memory checkpoint: saving {len(all_results)} results")
                    checkpoint_file = os.path.join(output_dir, f"checkpoint_{batch_num}.json")
                    self.save_batch_results(all_results, checkpoint_file)
                    all_results = []  # Clear memory
        
        except Exception as e:
            logger.error(f"Production extraction failed: {e}", exc_info=True)
            return False
        
        finally:
            # Save final results and statistics
            await self.finalize_results(output_dir, all_results)
        
        return True
    
    def save_batch_results(self, results: List, filepath: str):
        """Save batch results to JSON file"""
        
        output_data = []
        for result in results:
            output_data.append({
                'product_id': result.product_id,
                'colors': result.colors,
                'brands': result.brands,
                'styles': result.styles,
                'categories': result.categories,
                'materials': result.materials,
                'sizes': result.sizes,
                'seasons': result.seasons,
                'occasions': result.occasions,
                'confidence_scores': result.confidence_scores
            })
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved {len(results)} results to {filepath}")
    
    def print_progress_report(self, batch_num: int):
        """Print progress statistics"""
        
        elapsed = datetime.now() - self.start_time
        rate = self.total_processed / elapsed.total_seconds() if elapsed.total_seconds() > 0 else 0
        success_rate = (self.total_successful / self.total_processed * 100) if self.total_processed > 0 else 0
        
        logger.info(f"=== PROGRESS REPORT ===")
        logger.info(f"Batches completed: {batch_num}")
        logger.info(f"Products processed: {self.total_processed:,}")
        logger.info(f"Successful extractions: {self.total_successful:,} ({success_rate:.1f}%)")
        logger.info(f"Processing rate: {rate:.1f} products/second")
        logger.info(f"Elapsed time: {elapsed}")
        
        if self.max_products:
            progress = (self.total_processed / self.max_products * 100)
            logger.info(f"Progress: {progress:.1f}%")
    
    async def finalize_results(self, output_dir: str, remaining_results: List):
        """Save final results and generate summary statistics"""
        
        # Save any remaining results
        if remaining_results:
            final_file = os.path.join(output_dir, "final_batch.json")
            self.save_batch_results(remaining_results, final_file)
        
        # Generate pipeline statistics
        self.pipeline.print_pipeline_stats()
        
        # Create summary report
        summary = {
            'extraction_run': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'total_processed': self.total_processed,
                'total_successful': self.total_successful,
                'success_rate': (self.total_successful / self.total_processed * 100) if self.total_processed > 0 else 0,
                'batch_size': self.batch_size,
                'max_products': self.max_products
            },
            'extractor_stats': {
                extractor.name: {
                    'processed': extractor.stats['processed'],
                    'successful': extractor.stats['successful'], 
                    'accuracy': extractor.get_accuracy(),
                    'avg_time': extractor.get_avg_time()
                }
                for extractor in self.pipeline.extractors
            }
        }
        
        summary_file = os.path.join(output_dir, "extraction_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"=== EXTRACTION COMPLETE ===")
        logger.info(f"Results saved to: {output_dir}/")
        logger.info(f"Summary: {summary_file}")
        
        # Cleanup
        if self.db_reader:
            self.db_reader.close()

# Production run configurations
PRODUCTION_CONFIGS = {
    'test': {'max_products': 100, 'batch_size': 50},
    'sample': {'max_products': 10000, 'batch_size': 500},
    'full': {'max_products': None, 'batch_size': 1000}
}

async def main():
    """Main production run"""
    
    import argparse
    parser = argparse.ArgumentParser(description='Phase 1 Production Data Extraction')
    parser.add_argument('--config', choices=['test', 'sample', 'full'], default='test',
                       help='Extraction configuration (test=100, sample=10K, full=6.4M)')
    
    args = parser.parse_args()
    config = PRODUCTION_CONFIGS[args.config]
    
    logger.info(f"Starting production extraction with config: {args.config}")
    logger.info(f"Max products: {config['max_products'] or '6.4M'}")
    logger.info(f"Batch size: {config['batch_size']}")
    
    extractor = ProductionExtractor(
        batch_size=config['batch_size'],
        max_products=config['max_products']
    )
    
    success = await extractor.run_production_extraction()
    
    if success:
        logger.info("✅ Production extraction completed successfully!")
    else:
        logger.error("❌ Production extraction failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())