"""
Data Extraction Pipeline Package
Phase 1: Read-only AI-powered metadata extraction from products
"""

from .extractor_base import (
    DatabaseReader,
    BaseExtractor, 
    ExtractionPipeline,
    ProductData,
    ExtractedData,
    EXTRACTION_CONFIG
)

from .color_extractor import ColorExtractor
from .brand_extractor import BrandExtractor  
from .style_extractor import StyleExtractor

__version__ = "1.0.0"
__all__ = [
    # Base classes
    'DatabaseReader',
    'BaseExtractor',
    'ExtractionPipeline', 
    'ProductData',
    'ExtractedData',
    'EXTRACTION_CONFIG',
    
    # Extractors
    'ColorExtractor',
    'BrandExtractor',
    'StyleExtractor'
]