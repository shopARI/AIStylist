"""
Base classes for data extraction pipeline
Phase 1: Read-only data extraction and analysis
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import time

from neo4j import GraphDatabase
import requests

logger = logging.getLogger("data_extraction")

@dataclass
class ProductData:
    """Structured product data"""
    id: str
    title: str
    description: str
    price: float
    images: Optional[List[str]] = None
    visited_num: int = 0

@dataclass
class ExtractedData:
    """Extracted metadata from product"""
    product_id: str
    colors: List[str]
    brands: List[str]
    styles: List[str]
    categories: List[str]
    materials: List[str]
    sizes: List[str]
    seasons: List[str]
    occasions: List[str]
    confidence_scores: Dict[str, float]

class DatabaseReader:
    """Read-only database access for extraction pipeline"""
    
    def __init__(self, neo4j_url: str, neo4j_user: str, neo4j_password: str):
        self.neo4j_driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
        self.logger = logging.getLogger("data_extraction.reader")
        
    def get_product_sample(self, limit: int = 1000, offset: int = 0) -> List[ProductData]:
        """Get sample products for testing extraction"""
        with self.neo4j_driver.session() as session:
            result = session.run(f"""
            MATCH (p:Product)
            RETURN p.id, p.title, p.description, p.price, p.images, p.visited_num
            SKIP {offset}
            LIMIT {limit}
            """)
            
            products = []
            for record in result:
                try:
                    # Parse images if they exist
                    images = None
                    if record['p.images']:
                        images = json.loads(record['p.images'])
                    
                    product = ProductData(
                        id=record['p.id'],
                        title=record['p.title'] or '',
                        description=record['p.description'] or '',
                        price=record['p.price'] or 0.0,
                        images=images,
                        visited_num=record['p.visited_num'] or 0
                    )
                    products.append(product)
                except Exception as e:
                    self.logger.warning(f"Error parsing product {record.get('p.id', 'unknown')}: {e}")
                    continue
                    
            return products
    
    def get_existing_brands(self) -> List[str]:
        """Get list of existing brand names"""
        with self.neo4j_driver.session() as session:
            result = session.run("MATCH (b:Brand) RETURN b.name as name")
            return [record['name'] for record in result if record['name']]
    
    def get_product_count(self) -> int:
        """Get total product count"""
        with self.neo4j_driver.session() as session:
            result = session.run("MATCH (p:Product) RETURN count(p) as count")
            return result.single()['count']
    
    def close(self):
        """Close database connections"""
        self.neo4j_driver.close()

class BaseExtractor(ABC):
    """Base class for data extractors"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"data_extraction.{name}")
        self.stats = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'total_time': 0.0
        }
    
    @abstractmethod
    async def extract(self, product: ProductData) -> Dict[str, Any]:
        """Extract data from product. Returns dict with extracted fields"""
        pass
    
    def update_stats(self, success: bool, processing_time: float):
        """Update extraction statistics"""
        self.stats['processed'] += 1
        self.stats['total_time'] += processing_time
        if success:
            self.stats['successful'] += 1
        else:
            self.stats['failed'] += 1
    
    def get_accuracy(self) -> float:
        """Get extraction accuracy rate"""
        if self.stats['processed'] == 0:
            return 0.0
        return self.stats['successful'] / self.stats['processed']
    
    def get_avg_time(self) -> float:
        """Get average processing time per product"""
        if self.stats['processed'] == 0:
            return 0.0
        return self.stats['total_time'] / self.stats['processed']

class ExtractionPipeline:
    """Main extraction pipeline coordinator"""
    
    def __init__(self, db_reader: DatabaseReader):
        self.db_reader = db_reader
        self.extractors: List[BaseExtractor] = []
        self.logger = logging.getLogger("data_extraction.pipeline")
        
    def add_extractor(self, extractor: BaseExtractor):
        """Add an extractor to the pipeline"""
        self.extractors.append(extractor)
        self.logger.info(f"Added extractor: {extractor.name}")
    
    async def process_batch(self, products: List[ProductData]) -> List[ExtractedData]:
        """Process a batch of products through all extractors"""
        results = []
        
        for product in products:
            start_time = time.time()
            
            try:
                # Initialize extraction result
                extracted = ExtractedData(
                    product_id=product.id,
                    colors=[],
                    brands=[],
                    styles=[],
                    categories=[],
                    materials=[],
                    sizes=[],
                    seasons=[],
                    occasions=[],
                    confidence_scores={}
                )
                
                # Run all extractors on this product
                for extractor in self.extractors:
                    try:
                        extractor_start = time.time()
                        extractor_result = await extractor.extract(product)
                        extractor_time = time.time() - extractor_start
                        
                        # Merge results into extracted data
                        self._merge_extraction_results(extracted, extractor_result)
                        
                        extractor.update_stats(True, extractor_time)
                        
                    except Exception as e:
                        self.logger.error(f"Extractor {extractor.name} failed for product {product.id}: {e}")
                        extractor.update_stats(False, time.time() - extractor_start)
                        continue
                
                results.append(extracted)
                
            except Exception as e:
                self.logger.error(f"Failed to process product {product.id}: {e}")
                continue
        
        processing_time = time.time() - start_time
        self.logger.info(f"Processed {len(products)} products in {processing_time:.2f}s")
        
        return results
    
    def _merge_extraction_results(self, extracted: ExtractedData, extractor_result: Dict[str, Any]):
        """Merge results from an extractor into the main extracted data"""
        
        # Merge lists (avoiding duplicates)
        for field in ['colors', 'brands', 'styles', 'categories', 'materials', 'sizes', 'seasons', 'occasions']:
            if field in extractor_result:
                current_list = getattr(extracted, field)
                new_items = extractor_result[field] if isinstance(extractor_result[field], list) else [extractor_result[field]]
                
                for item in new_items:
                    if item and item not in current_list:
                        current_list.append(item)
        
        # Merge confidence scores
        if 'confidence_scores' in extractor_result:
            extracted.confidence_scores.update(extractor_result['confidence_scores'])
    
    async def run_sample_extraction(self, sample_size: int = 100) -> List[ExtractedData]:
        """Run extraction on a sample for testing"""
        self.logger.info(f"Starting sample extraction on {sample_size} products")
        
        # Get sample products
        products = self.db_reader.get_product_sample(limit=sample_size)
        self.logger.info(f"Retrieved {len(products)} products for processing")
        
        # Process through pipeline
        results = await self.process_batch(products)
        
        # Log statistics
        self.print_pipeline_stats()
        
        return results
    
    def print_pipeline_stats(self):
        """Print statistics for all extractors"""
        self.logger.info("=== EXTRACTION PIPELINE STATS ===")
        
        for extractor in self.extractors:
            stats = extractor.stats
            accuracy = extractor.get_accuracy()
            avg_time = extractor.get_avg_time()
            
            self.logger.info(f"{extractor.name}:")
            self.logger.info(f"  Processed: {stats['processed']}")
            self.logger.info(f"  Success rate: {accuracy:.1%}")
            self.logger.info(f"  Avg time: {avg_time:.3f}s")
    
    def save_results(self, results: List[ExtractedData], filepath: str):
        """Save extraction results to JSON file"""
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
        
        self.logger.info(f"Saved {len(results)} extraction results to {filepath}")

# Global configuration
EXTRACTION_CONFIG = {
    'batch_size': 100,
    'max_concurrent': 5,
    'timeout_seconds': 30,
    'retry_attempts': 2
}