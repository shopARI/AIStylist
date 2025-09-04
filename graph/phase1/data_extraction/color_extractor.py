"""
Color Extraction using LLM
Phase 1: Read-only color data extraction from product text
"""

import asyncio
import re
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from camel.v070 import (
    create_agent,
    create_user_message,
    BaseMessage,
    ModelType,
    CAMEL_AVAILABLE
)

from .extractor_base import BaseExtractor, ProductData

# Comprehensive color mapping
COLOR_PATTERNS = {
    # Basic colors
    'red': ['red', 'crimson', 'burgundy', 'maroon', 'cherry', 'ruby', 'scarlet', 'wine', 'brick'],
    'blue': ['blue', 'navy', 'azure', 'cobalt', 'royal', 'midnight', 'cerulean', 'sapphire', 'denim'],
    'green': ['green', 'emerald', 'olive', 'lime', 'forest', 'mint', 'sage', 'jade', 'kelly'],
    'yellow': ['yellow', 'gold', 'amber', 'lemon', 'mustard', 'canary', 'butter', 'cream'],
    'orange': ['orange', 'coral', 'peach', 'tangerine', 'rust', 'copper', 'apricot', 'burnt'],
    'purple': ['purple', 'violet', 'lavender', 'plum', 'magenta', 'amethyst', 'lilac', 'mauve'],
    'pink': ['pink', 'rose', 'blush', 'fuchsia', 'salmon', 'hot pink', 'dusty rose', 'ballet'],
    'brown': ['brown', 'tan', 'beige', 'camel', 'chocolate', 'coffee', 'mocha', 'cognac', 'khaki'],
    'black': ['black', 'charcoal', 'ebony', 'jet', 'onyx', 'coal', 'midnight', 'raven'],
    'white': ['white', 'ivory', 'cream', 'pearl', 'snow', 'alabaster', 'off-white', 'bone'],
    'gray': ['gray', 'grey', 'silver', 'platinum', 'ash', 'slate', 'pewter', 'graphite', 'stone'],
    'gold': ['gold', 'golden', 'metallic gold', 'brass', 'bronze', 'champagne'],
    'silver': ['silver', 'metallic', 'chrome', 'steel', 'platinum', 'pewter']
}

# Pattern-based color detection
COLOR_REGEX_PATTERNS = [
    r'\b(' + '|'.join([color for colors in COLOR_PATTERNS.values() for color in colors]) + r')\b',
    r'\b\w*(' + '|'.join(['red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'brown', 'black', 'white', 'gray', 'grey']) + r')\w*\b'
]

class ColorExtractor(BaseExtractor):
    """Extract color information from product text using hybrid LLM + pattern matching"""
    
    def __init__(self, use_llm: bool = True, model_type: ModelType = ModelType.GPT_4O_MINI):
        super().__init__("color_extractor")
        self.use_llm = use_llm and CAMEL_AVAILABLE
        self.model_type = model_type
        
        if self.use_llm:
            self.llm_agent = self._create_color_agent()
            self.logger.info("Initialized Color Extractor with LLM support")
        else:
            self.logger.info("Initialized Color Extractor with pattern matching only")
    
    def _create_color_agent(self):
        """Create CAMEL agent specialized for color extraction"""
        
        system_message = f"""You are a color extraction specialist for fashion products. Your job is to identify ALL colors mentioned in product titles and descriptions.

INSTRUCTIONS:
1. Extract ALL colors mentioned, not just dominant ones
2. Normalize color names to basic color families: {list(COLOR_PATTERNS.keys())}
3. Include metallic colors (gold, silver, bronze)
4. Ignore patterns/textures (stripes, dots, etc.) unless they specify colors
5. Return ONLY the color names as a JSON list

EXAMPLES:

Input: "Red flannel shirt with blue buttons"
Output: ["red", "blue"]

Input: "Navy blue dress with silver zipper"  
Output: ["blue", "silver"]

Input: "Emerald green silk blouse"
Output: ["green"]

Input: "Black leather jacket with gold hardware"
Output: ["black", "gold"]

Input: "Striped cotton shirt"
Output: []

Input: "Floral print dress with pink roses on white background"
Output: ["pink", "white"]

IMPORTANT:
- Only return valid JSON list format: ["color1", "color2"]
- Use lowercase color names only
- If no colors found, return empty list: []
- Map color variations to base colors (burgundy → red, navy → blue, etc.)
"""
        
        return create_agent(
            system_message=system_message,
            model_type=self.model_type,
            temperature=0.1,  # Low temperature for consistent extraction
            max_tokens=500    # Sufficient tokens for JSON responses
        )
    
    async def extract(self, product: ProductData) -> Dict[str, Any]:
        """Extract colors from product data"""
        
        # Combine title and description for analysis
        text_content = f"{product.title} {product.description}".strip()
        
        if not text_content:
            return {
                'colors': [],
                'confidence_scores': {'color_extraction': 0.0}
            }
        
        extracted_colors = []
        confidence = 0.0
        
        if self.use_llm:
            # Primary: LLM extraction
            llm_colors, llm_confidence = await self._extract_colors_llm(text_content)
            extracted_colors.extend(llm_colors)
            confidence = max(confidence, llm_confidence)
        
        # Fallback: Pattern matching
        pattern_colors = self._extract_colors_patterns(text_content)
        
        # Merge results (LLM takes precedence)
        if not extracted_colors:
            extracted_colors = pattern_colors
            confidence = 0.6 if pattern_colors else 0.0
        else:
            # Add any pattern colors not found by LLM
            for color in pattern_colors:
                if color not in extracted_colors:
                    extracted_colors.append(color)
        
        # Remove duplicates and normalize
        extracted_colors = self._normalize_colors(list(set(extracted_colors)))
        
        return {
            'colors': extracted_colors,
            'confidence_scores': {'color_extraction': confidence}
        }
    
    async def _extract_colors_llm(self, text: str) -> tuple[List[str], float]:
        """Extract colors using LLM"""
        
        try:
            user_message = create_user_message(f"Extract colors from: {text}")
            
            # Use compatibility bridge for async method
            from camel.v070 import CompatibilityBridge
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
            
            # Parse JSON response
            colors = self._parse_llm_color_response(response_content)
            confidence = 0.9 if colors else 0.1
            
            return colors, confidence
            
        except Exception as e:
            self.logger.error(f"LLM color extraction failed: {e}")
            return [], 0.0
    
    def _parse_llm_color_response(self, response_content: str) -> List[str]:
        """Parse LLM JSON response to extract colors"""
        
        try:
            # Clean response content
            response_content = response_content.strip()
            
            # Handle potential markdown code blocks
            if "```json" in response_content:
                start = response_content.find("```json") + 7
                end = response_content.find("```", start)
                json_str = response_content[start:end].strip()
            elif "```" in response_content:
                start = response_content.find("```") + 3
                end = response_content.rfind("```")
                json_str = response_content[start:end].strip()
            else:
                json_str = response_content
            
            # Find JSON array in response
            if '[' in json_str and ']' in json_str:
                start = json_str.find('[')
                end = json_str.rfind(']') + 1
                json_str = json_str[start:end]
            
            # Parse JSON
            colors = json.loads(json_str)
            
            # Validate and clean
            if isinstance(colors, list):
                return [str(color).lower().strip() for color in colors if color]
            else:
                return []
                
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            self.logger.warning(f"Failed to parse LLM color response: {e}")
            self.logger.debug(f"Raw response: {response_content}")
            return []
    
    def _extract_colors_patterns(self, text: str) -> List[str]:
        """Extract colors using regex patterns"""
        
        text_lower = text.lower()
        found_colors = []
        
        # Use compiled regex patterns
        for pattern in COLOR_REGEX_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle group matches
                    for submatch in match:
                        if submatch:
                            found_colors.append(submatch)
                else:
                    found_colors.append(match)
        
        # Map variations to base colors
        normalized_colors = []
        for color in found_colors:
            base_color = self._map_to_base_color(color)
            if base_color and base_color not in normalized_colors:
                normalized_colors.append(base_color)
        
        return normalized_colors
    
    def _map_to_base_color(self, color_mention: str) -> Optional[str]:
        """Map color variation to base color"""
        
        color_mention = color_mention.lower().strip()
        
        # Direct mapping
        for base_color, variations in COLOR_PATTERNS.items():
            if color_mention in variations:
                return base_color
        
        # Partial matching for compound colors
        for base_color, variations in COLOR_PATTERNS.items():
            for variation in variations:
                if variation in color_mention or color_mention in variation:
                    return base_color
        
        return None
    
    def _normalize_colors(self, colors: List[str]) -> List[str]:
        """Normalize and validate extracted colors"""
        
        normalized = []
        valid_colors = set(COLOR_PATTERNS.keys())
        
        for color in colors:
            color = color.lower().strip()
            
            # Only keep valid base colors
            if color in valid_colors:
                normalized.append(color)
            else:
                # Try to map to base color
                base_color = self._map_to_base_color(color)
                if base_color and base_color not in normalized:
                    normalized.append(base_color)
        
        return normalized

# Utility functions for testing
def test_color_extraction():
    """Test color extraction on sample data"""
    
    test_products = [
        ProductData("1", "Red flannel shirt", "Comfortable red cotton flannel with blue buttons", 29.99),
        ProductData("2", "Navy dress", "Elegant navy blue dress with silver zipper", 89.99),
        ProductData("3", "Black leather jacket", "Premium black leather with gold hardware", 199.99),
        ProductData("4", "Floral print blouse", "Beautiful floral print with pink roses on white background", 45.99),
        ProductData("5", "Striped shirt", "Classic striped pattern cotton shirt", 35.99)
    ]
    
    return test_products

if __name__ == "__main__":
    # Test the color extractor
    async def test():
        extractor = ColorExtractor()
        test_data = test_color_extraction()
        
        for product in test_data:
            result = await extractor.extract(product)
            print(f"Product: {product.title}")
            print(f"Colors: {result['colors']}")
            print(f"Confidence: {result['confidence_scores']['color_extraction']:.2f}")
            print("---")
    
    asyncio.run(test())