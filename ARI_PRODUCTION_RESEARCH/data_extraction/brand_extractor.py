"""
Brand Extraction using Hybrid Approach
Phase 1: Read-only brand data extraction from product text
"""

import asyncio
import re
import json
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass

# Direct CAMEL 0.2.7 imports
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.messages import BaseMessage
from camel.types import ModelType, ModelPlatformType
try:
    import camel
    CAMEL_AVAILABLE = True
except ImportError:
    CAMEL_AVAILABLE = False

from .extractor_base import BaseExtractor, ProductData

# Known fashion brands database (expandable)
KNOWN_BRANDS = {
    # Luxury brands
    'gucci', 'prada', 'louis vuitton', 'chanel', 'versace', 'armani', 'dolce gabbana', 
    'saint laurent', 'balenciaga', 'bottega veneta', 'hermès', 'dior', 'fendi',
    
    # Premium brands  
    'ralph lauren', 'calvin klein', 'tommy hilfiger', 'hugo boss', 'lacoste',
    'polo ralph lauren', 'michael kors', 'kate spade', 'coach', 'marc jacobs',
    
    # Popular/Contemporary
    'nike', 'adidas', 'puma', 'under armour', 'reebok', 'vans', 'converse',
    'levis', "levi's", 'gap', 'banana republic', 'old navy', 'j crew', 'zara',
    'h&m', 'uniqlo', 'forever 21', 'urban outfitters', 'anthropologie',
    
    # Athletic/Outdoor
    'north face', 'patagonia', 'columbia', 'rei', 'lululemon', 'athleta',
    'champion', 'fila', 'new balance', 'asics', 'saucony',
    
    # Department store brands
    'nordstrom', 'macys', 'bloomingdales', 'saks', 'neiman marcus',
    
    # Fast fashion
    'shein', 'romwe', 'zaful', 'boohoo', 'asos', 'prettylittlething',
    
    # Specialty/Niche
    'free people', 'reformation', 'everlane', 'madewell', 'allsaints',
    'theory', 'elizabeth suzann', 'eileen fisher', 'american eagle',
    'abercrombie', 'hollister', 'express', 'ann taylor', 'loft'
}

# Brand extraction patterns
BRAND_PATTERNS = [
    # Possessive patterns: "Nike's Air Force", "Adidas' Stan Smith"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'s?\s+",
    
    # Direct brand mentions: "Nike Air Force", "Ralph Lauren Polo"  
    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+",
    
    # "by Brand" patterns: "Sneakers by Nike"
    r"\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    
    # Brand collection patterns: "Collection Women's", "Men's Nike"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Collection|Men's|Women's|Unisex)",
    
    # Parenthetical brands: "(Nike)", "(Ralph Lauren)"
    r"\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\)"
]

class BrandExtractor(BaseExtractor):
    """Extract brand information using hybrid approach: known brands + LLM + patterns"""
    
    def __init__(self, known_brands: Optional[Set[str]] = None, use_llm: bool = True, model_type: ModelType = ModelType.GPT_4O_MINI):
        super().__init__("brand_extractor")
        
        # Initialize known brands (from database + predefined)
        self.known_brands = set()
        if known_brands:
            self.known_brands.update(brand.lower() for brand in known_brands)
        self.known_brands.update(KNOWN_BRANDS)
        
        self.use_llm = use_llm and CAMEL_AVAILABLE
        self.model_type = model_type
        
        if self.use_llm:
            self.llm_agent = self._create_brand_agent()
            self.logger.info(f"Initialized Brand Extractor with {len(self.known_brands)} known brands + LLM")
        else:
            self.logger.info(f"Initialized Brand Extractor with {len(self.known_brands)} known brands only")
    
    def _create_brand_agent(self):
        """Create CAMEL agent specialized for brand extraction"""
        
        system_message = """You are a fashion brand identification specialist. Your job is to identify brand names from product titles and descriptions.

INSTRUCTIONS:
1. Extract the PRIMARY brand name only (not sub-brands or collections)
2. Return the official brand name with proper capitalization
3. Focus on fashion, clothing, shoe, and accessory brands
4. If multiple brands mentioned, prioritize the manufacturer/main brand
5. Return ONLY the brand name, nothing else
6. If no clear brand found, return "UNKNOWN"

EXAMPLES:

Input: "Nike Air Force 1 Low White Sneakers"
Output: Nike

Input: "Ralph Lauren Polo Classic Fit Shirt" 
Output: Ralph Lauren

Input: "Adidas Originals Stan Smith Shoes"
Output: Adidas

Input: "Coach Parker Leather Handbag"
Output: Coach

Input: "Women's Cotton T-Shirt"
Output: UNKNOWN

Input: "Levi's 501 Original Fit Jeans"
Output: Levi's

Input: "Theory Cashmere Turtleneck Sweater"
Output: Theory

IMPORTANT:
- Only return the brand name, no extra text
- Use proper brand capitalization (Nike, not NIKE)
- Don't include product types (shoes, shirt, etc.)
- Don't include collections or sub-lines
- If unsure, return "UNKNOWN"
"""
        
        return create_agent(
            system_message=system_message,
            model_type=self.model_type,
            temperature=0.1,
            max_tokens=200    # Sufficient for brand name responses
        )
    
    async def extract(self, product: ProductData) -> Dict[str, Any]:
        """Extract brand from product data using hybrid approach"""
        
        text_content = f"{product.title} {product.description}".strip()
        
        if not text_content:
            return {
                'brands': [],
                'confidence_scores': {'brand_extraction': 0.0}
            }
        
        extracted_brands = []
        confidence = 0.0
        
        # Method 1: Known brand matching (highest confidence)
        known_brand = self._extract_known_brand(text_content)
        if known_brand:
            extracted_brands.append(known_brand)
            confidence = 0.95
        
        # Method 2: LLM extraction (medium confidence)
        if self.use_llm and not extracted_brands:
            llm_brand, llm_confidence = await self._extract_brand_llm(text_content)
            if llm_brand and llm_brand != "UNKNOWN":
                extracted_brands.append(llm_brand)
                confidence = llm_confidence
        
        # Method 3: Pattern matching (lower confidence)
        if not extracted_brands:
            pattern_brands = self._extract_brand_patterns(text_content)
            if pattern_brands:
                extracted_brands.extend(pattern_brands)
                confidence = 0.6
        
        # Clean and normalize results
        final_brands = self._normalize_brands(extracted_brands)
        
        return {
            'brands': final_brands,
            'confidence_scores': {'brand_extraction': confidence}
        }
    
    def _extract_known_brand(self, text: str) -> Optional[str]:
        """Extract brand using known brand database"""
        
        text_lower = text.lower()
        
        # Direct matching - prioritize longer brand names first
        sorted_brands = sorted(self.known_brands, key=len, reverse=True)
        
        for brand in sorted_brands:
            # Word boundary matching to avoid partial matches
            pattern = r'\b' + re.escape(brand) + r'\b'
            if re.search(pattern, text_lower):
                return self._format_brand_name(brand)
        
        return None
    
    def _format_brand_name(self, brand: str) -> str:
        """Format brand name with proper capitalization"""
        
        # Special cases for known brand formatting
        brand_formatting = {
            "levi's": "Levi's",
            "h&m": "H&M",
            "j crew": "J.Crew",
            "old navy": "Old Navy",
            "banana republic": "Banana Republic",
            "ralph lauren": "Ralph Lauren",
            "polo ralph lauren": "Polo Ralph Lauren",
            "calvin klein": "Calvin Klein",
            "tommy hilfiger": "Tommy Hilfiger",
            "hugo boss": "Hugo Boss",
            "michael kors": "Michael Kors",
            "kate spade": "Kate Spade",
            "marc jacobs": "Marc Jacobs",
            "louis vuitton": "Louis Vuitton",
            "dolce gabbana": "Dolce & Gabbana",
            "saint laurent": "Saint Laurent",
            "bottega veneta": "Bottega Veneta",
            "under armour": "Under Armour",
            "new balance": "New Balance",
            "north face": "The North Face",
            "forever 21": "Forever 21",
            "urban outfitters": "Urban Outfitters",
            "american eagle": "American Eagle",
            "ann taylor": "Ann Taylor",
            "free people": "Free People",
            "eileen fisher": "Eileen Fisher"
        }
        
        if brand.lower() in brand_formatting:
            return brand_formatting[brand.lower()]
        
        # Default title case formatting
        return ' '.join(word.capitalize() for word in brand.split())
    
    async def _extract_brand_llm(self, text: str) -> tuple[Optional[str], float]:
        """Extract brand using LLM"""
        
        try:
            user_message = create_user_message(f"Identify brand from: {text}")
            
            # Use compatibility bridge for async method
            from lib.camel.v070 import CompatibilityBridge
            async_method = CompatibilityBridge.check_async_method(self.llm_agent)
            
            if async_method == 'step_async':
                response = await self.llm_agent.step_async(user_message)
            elif async_method == 'astep':
                response = await self.llm_agent.astep(user_message)
            else:
                response = self.llm_agent.step(user_message)
            
            # Parse response content
            if hasattr(response, 'content'):
                response_content = response.content
            elif hasattr(response, 'msg'):
                response_content = response.msg.content if hasattr(response.msg, 'content') else str(response.msg)
            elif hasattr(response, 'message'):
                response_content = response.message.content if hasattr(response.message, 'content') else str(response.message)
            else:
                response_content = str(response)
            
            # Clean and validate response
            brand = response_content.strip()
            
            # Remove common LLM response artifacts
            brand = brand.replace("Brand:", "").replace("Output:", "").strip()
            
            if brand and brand != "UNKNOWN" and len(brand) < 50:  # Reasonable brand name length
                confidence = 0.8
                return brand, confidence
            else:
                return None, 0.0
                
        except Exception as e:
            self.logger.error(f"LLM brand extraction failed: {e}")
            return None, 0.0
    
    def _extract_brand_patterns(self, text: str) -> List[str]:
        """Extract brands using regex patterns"""
        
        found_brands = []
        
        for pattern in BRAND_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]  # Take first group
                
                # Validate potential brand name
                if self._is_likely_brand(match):
                    formatted_brand = self._format_brand_name(match)
                    if formatted_brand not in found_brands:
                        found_brands.append(formatted_brand)
        
        return found_brands
    
    def _is_likely_brand(self, candidate: str) -> bool:
        """Check if candidate string is likely a brand name"""
        
        candidate = candidate.strip()
        
        # Basic validation rules
        if len(candidate) < 2 or len(candidate) > 30:
            return False
        
        # Must start with capital letter
        if not candidate[0].isupper():
            return False
        
        # Exclude common non-brand words
        exclude_words = {
            'Collection', 'Women', 'Men', 'Womens', 'Mens', 'Unisex', 'Kids',
            'Brand', 'New', 'Vintage', 'Classic', 'Premium', 'Original',
            'Official', 'Authentic', 'Genuine', 'Real', 'True', 'Pure',
            'Cotton', 'Leather', 'Silk', 'Wool', 'Polyester', 'Denim'
        }
        
        if candidate in exclude_words:
            return False
        
        # Prefer shorter, more brand-like names
        word_count = len(candidate.split())
        if word_count > 3:  # Most brands are 1-3 words
            return False
        
        return True
    
    def _normalize_brands(self, brands: List[str]) -> List[str]:
        """Normalize and deduplicate brand names"""
        
        if not brands:
            return []
        
        normalized = []
        seen = set()
        
        for brand in brands:
            brand = brand.strip()
            
            # Skip if already seen (case insensitive)
            if brand.lower() in seen:
                continue
            
            # Validate brand name
            if self._is_likely_brand(brand):
                normalized.append(brand)
                seen.add(brand.lower())
        
        return normalized[:3]  # Limit to top 3 brands per product

# Test function
def test_brand_extraction():
    """Test brand extraction on sample data"""
    
    test_products = [
        ProductData("1", "Nike Air Force 1 Low White Sneakers", "Classic Nike sneakers in white leather", 90.00),
        ProductData("2", "Ralph Lauren Polo Classic Fit Shirt", "Premium cotton polo shirt by Ralph Lauren", 85.00),
        ProductData("3", "Levi's 501 Original Fit Jeans", "Authentic Levi's denim jeans in classic fit", 79.99),
        ProductData("4", "Coach Parker Leather Handbag", "Luxury leather handbag from Coach collection", 295.00),
        ProductData("5", "Women's Cotton T-Shirt", "Basic cotton t-shirt for everyday wear", 19.99),
        ProductData("6", "Adidas Originals Stan Smith Tennis Shoes", "Iconic Adidas tennis shoes in white and green", 75.00)
    ]
    
    return test_products

if __name__ == "__main__":
    # Test the brand extractor
    async def test():
        # Simulate known brands from database
        db_brands = ['Theory', 'Journee Collection', 'Urban Classics', 'Franco Sarto']
        
        extractor = BrandExtractor(known_brands=set(db_brands))
        test_data = test_brand_extraction()
        
        for product in test_data:
            result = await extractor.extract(product)
            print(f"Product: {product.title}")
            print(f"Brands: {result['brands']}")
            print(f"Confidence: {result['confidence_scores']['brand_extraction']:.2f}")
            print("---")
    
    asyncio.run(test())