"""
ARI V3 - Parameter Extractor

Extracts structured parameters from natural language queries.
Adapted from V2's parameter_extractor.py with improvements.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List, Optional, Pattern

from .types import ExtractedParameters

logger = logging.getLogger(__name__)

# Thread lock for singleton
_extractor_lock = threading.Lock()


class ParameterExtractor:
    """
    Extracts structured parameters from user messages.

    Uses fashion vocabulary and regex patterns to identify:
    - Categories (dress, shirt, pants, etc.)
    - Colors (red, blue, black, etc.)
    - Occasions (wedding, work, casual, etc.)
    - Price ranges
    - Brands
    - Sizes
    - Materials
    - Style modifiers
    """

    def __init__(self):
        """Initialize with fashion vocabularies and pre-compiled regex patterns."""

        # Fashion vocabularies
        self.occasions = [
            "wedding", "party", "work", "casual", "formal", "date", "dinner",
            "beach", "gala", "cocktail", "interview", "brunch", "vacation",
            "travel", "gym", "workout", "meeting", "conference", "birthday",
            "anniversary", "graduation", "prom", "homecoming", "festival",
            "concert", "clubbing", "office", "business"
        ]

        self.colors = [
            "red", "blue", "green", "black", "white", "yellow", "purple",
            "orange", "pink", "brown", "gray", "grey", "navy", "teal",
            "maroon", "beige", "turquoise", "gold", "silver", "cream",
            "burgundy", "coral", "mint", "olive", "rust", "sage", "lavender",
            "peach", "emerald", "crimson", "indigo", "khaki", "tan", "ivory",
            "charcoal", "rose", "wine", "forest", "cobalt", "mustard"
        ]

        self.materials = [
            "cotton", "silk", "wool", "polyester", "linen", "leather", "denim",
            "suede", "velvet", "cashmere", "satin", "nylon", "chiffon", "lace",
            "tweed", "jersey", "modal", "bamboo", "rayon", "spandex", "lycra",
            "mesh", "sequin", "fleece", "corduroy", "canvas", "georgette",
            "crepe", "taffeta"
        ]

        self.categories = [
            "dress", "shirt", "pants", "jeans", "skirt", "blouse", "sweater",
            "jacket", "coat", "suit", "blazer", "t-shirt", "hoodie", "shorts",
            "swimwear", "activewear", "athletic", "sportswear", "workout", "gym",
            "shoes", "boots", "sneakers", "accessories", "jewelry", "necklace",
            "bracelet", "earrings", "ring", "watch", "scarf", "hat", "gown",
            "outfit", "cardigan", "vest", "leggings", "jumpsuit", "romper",
            "tank", "camisole", "tunic", "kimono", "poncho", "trench", "parka",
            "bomber", "duster", "cape", "shawl", "top", "tee"  # Removed duplicate "blouse"
        ]

        self.styles = [
            "classic", "modern", "vintage", "boho", "minimalist", "chic",
            "elegant", "edgy", "preppy", "streetwear", "athleisure", "romantic",
            "gothic", "punk", "grunge", "retro", "glamorous", "sophisticated",
            "trendy", "timeless", "bold", "feminine", "masculine", "androgynous",
            "casual", "professional", "luxe", "indie", "hipster", "nautical",
            "western", "ethnic", "artistic", "eclectic", "colorful", "refined",
            "architectural", "scandinavian"
        ]

        self.seasons = ["spring", "summer", "fall", "autumn", "winter"]

        self.sizes = [
            "xs", "s", "m", "l", "xl", "xxl", "xxxl", "petite", "plus", "tall",
            "regular", "0", "2", "4", "6", "8", "10", "12", "14", "16", "18", "20"
        ]

        self.luxury_brands = [
            "chanel", "dior", "gucci", "prada", "versace", "balenciaga",
            "saint laurent", "bottega veneta", "burberry", "givenchy",
            "valentino", "fendi", "celine", "loewe", "hermes", "louis vuitton",
            "tom ford", "alexander mcqueen", "stella mccartney", "miu miu"
        ]

        self.common_brands = [
            "nike", "adidas", "puma", "zara", "h&m", "uniqlo", "gap", "levi's",
            "calvin klein", "tommy hilfiger", "ralph lauren", "coach",
            "michael kors", "kate spade", "tory burch"
        ]

        # Pre-compiled regex patterns
        self._compile_patterns()

        # Pre-compile vocabulary patterns for performance
        self._compile_vocabulary_patterns()

        logger.info("ParameterExtractor initialized with fashion vocabulary")

    def _compile_vocabulary_patterns(self):
        """Pre-compile vocabulary word boundary patterns for performance."""
        self._vocab_patterns: Dict[str, Dict[str, Pattern]] = {}

        vocabularies = {
            "categories": self.categories,
            "colors": self.colors,
            "occasions": self.occasions,
            "styles": self.styles,
            "materials": self.materials,
        }

        for vocab_name, vocab_list in vocabularies.items():
            self._vocab_patterns[vocab_name] = {
                item: re.compile(r'\b' + re.escape(item) + r'\b', re.IGNORECASE)
                for item in vocab_list
            }

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self.size_patterns = [
            re.compile(r'size\s+(\d+)', re.IGNORECASE),
            re.compile(r'size\s+(\d+\w+)', re.IGNORECASE),
            re.compile(r'(\d+)\s+size', re.IGNORECASE),
            re.compile(r'wear\s+a?\s+(\d+)', re.IGNORECASE),
            re.compile(r"i'm\s+a?\s+(\d+)", re.IGNORECASE),
        ]

        self.price_patterns = {
            "under": re.compile(
                r'(?:under|less than|below|max|maximum)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
                re.IGNORECASE
            ),
            "over": re.compile(
                r'(?:over|more than|above|min|minimum|at least)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
                re.IGNORECASE
            ),
            "between": re.compile(
                r'(?:between|from)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s+(?:and|to|-)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
                re.IGNORECASE
            ),
            "around": re.compile(
                r'(?:around|about|approximately|roughly)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
                re.IGNORECASE
            ),
            "budget": re.compile(
                r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s+budget',
                re.IGNORECASE
            ),
            "simple": re.compile(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)')
        }

        self.brand_patterns = [
            re.compile(
                r'(?:from|by|brand|designer|label)\s+([A-Z][A-Za-z\s&]+?)(?:\s|,|\.|\?|!|$)'
            ),
            re.compile(r'([A-Z][A-Za-z\s&]+?)\s+(?:collection|brand|designer)'),
        ]

        # Time reference patterns
        self.time_patterns = {
            "yesterday": re.compile(r'\byesterday\b', re.IGNORECASE),
            "last_week": re.compile(r'\blast\s+week\b', re.IGNORECASE),
            "last_time": re.compile(r'\blast\s+time\b', re.IGNORECASE),
            "earlier": re.compile(r'\bearlier\b', re.IGNORECASE),
            "before": re.compile(r'\bbefore\b', re.IGNORECASE),
        }

    def extract(self, message: str) -> ExtractedParameters:
        """
        Extract all relevant parameters from a message.

        Args:
            message: User message

        Returns:
            ExtractedParameters object
        """
        message_lower = message.lower()

        params = ExtractedParameters(
            categories=self._extract_vocab_items(message_lower, "categories"),
            colors=self._extract_vocab_items(message_lower, "colors"),
            occasions=self._extract_vocab_items(message_lower, "occasions"),
            price_range=self._extract_price_range(message),
            brand_preferences=self._extract_brands(message),
            style_modifiers=self._extract_vocab_items(message_lower, "styles"),
            sizes=self._extract_sizes(message_lower),
            materials=self._extract_vocab_items(message_lower, "materials"),
            time_reference=self._extract_time_reference(message_lower),
            entity_reference=self._extract_entity_reference(message_lower),
        )

        logger.debug(f"Extracted parameters: {params.to_dict()}")
        return params

    def extract_parameters(self, message: str) -> Dict[str, Any]:
        """
        Extract parameters and return as dictionary.

        Compatibility method for existing code.

        Args:
            message: User message

        Returns:
            Dictionary of extracted parameters
        """
        return self.extract(message).to_dict()

    def _apply_text_corrections(self, text: str) -> str:
        """Apply typo and plural corrections to text."""
        # Common typo corrections
        typo_corrections = {
            "shrt": "shirt", "shrts": "shirts", "pnts": "pants",
            "jens": "jeans", "drss": "dress", "sheos": "shoes",
            "jackt": "jacket", "swetr": "sweater"
        }

        # Plural to singular mapping
        plural_corrections = {
            "shirts": "shirt", "dresses": "dress", "tops": "top",
            "sweaters": "sweater", "jackets": "jacket", "blazers": "blazer",
            "skirts": "skirt", "boots": "boots", "shoes": "shoes",
            "tees": "tee", "tanks": "tank", "hoodies": "hoodie"
        }

        corrected_text = text
        for typo, correction in typo_corrections.items():
            corrected_text = re.sub(
                r'\b' + re.escape(typo) + r'\b', correction, corrected_text
            )
        for plural, singular in plural_corrections.items():
            corrected_text = re.sub(
                r'\b' + re.escape(plural) + r'\b', singular, corrected_text
            )

        return corrected_text

    def _extract_vocab_items(self, text: str, vocab_name: str) -> List[str]:
        """Extract items using pre-compiled vocabulary patterns (fast)."""
        corrected_text = self._apply_text_corrections(text)
        found_items: List[str] = []

        patterns = self._vocab_patterns.get(vocab_name, {})
        for item, pattern in patterns.items():
            if pattern.search(corrected_text):
                found_items.append(item)

        return found_items

    def _extract_items(self, text: str, vocabulary: List[str]) -> List[str]:
        """Extract items from text that match vocabulary (fallback method)."""
        corrected_text = self._apply_text_corrections(text)
        found_items: List[str] = []

        # Extract items using dynamic regex (slower, use _extract_vocab_items when possible)
        for item in vocabulary:
            if re.search(r'\b' + re.escape(item) + r'\b', corrected_text, re.IGNORECASE):
                found_items.append(item)

        return found_items

    def _extract_sizes(self, text: str) -> List[str]:
        """Extract size information."""
        sizes = []

        # Check vocabulary sizes
        for size in self.sizes:
            if re.search(r'\b' + re.escape(str(size)) + r'\b', text, re.IGNORECASE):
                size_str = str(size).upper() if size in ["xs", "s", "m", "l", "xl", "xxl", "xxxl"] else str(size)
                sizes.append(size_str)

        # Check patterns
        for pattern in self.size_patterns:
            match = pattern.search(text)
            if match:
                sizes.append(match.group(1))

        return list(set(sizes))

    def _extract_price_range(self, text: str) -> Optional[Dict[str, float]]:
        """Extract price range information."""
        price_range = {}

        def validate_price(price_val: float) -> float:
            """Validate and clamp price to reasonable range."""
            if price_val < 0 or price_val > 1000000:
                logger.warning(f"Unusual price detected: ${price_val}. Clamping.")
                return min(max(price_val, 0), 1000000)
            return price_val

        # Check each pattern
        match = self.price_patterns["under"].search(text)
        if match:
            price_range["max"] = validate_price(
                float(match.group(1).replace(',', ''))
            )

        match = self.price_patterns["over"].search(text)
        if match:
            price_range["min"] = validate_price(
                float(match.group(1).replace(',', ''))
            )

        match = self.price_patterns["between"].search(text)
        if match:
            price_range["min"] = validate_price(
                float(match.group(1).replace(',', ''))
            )
            price_range["max"] = validate_price(
                float(match.group(2).replace(',', ''))
            )

        match = self.price_patterns["around"].search(text)
        if match:
            price = validate_price(float(match.group(1).replace(',', '')))
            price_range["min"] = price * 0.8
            price_range["max"] = price * 1.2
            price_range["target"] = price

        match = self.price_patterns["budget"].search(text)
        if match:
            price_range["max"] = validate_price(
                float(match.group(1).replace(',', ''))
            )

        # Simple dollar amount
        if not price_range:
            matches = self.price_patterns["simple"].findall(text)
            if matches:
                prices = [validate_price(float(m.replace(',', ''))) for m in matches]
                if len(prices) == 1:
                    price_range["target"] = prices[0]
                    price_range["min"] = prices[0] * 0.7
                    price_range["max"] = prices[0] * 1.3
                elif len(prices) >= 2:
                    price_range["min"] = min(prices)
                    price_range["max"] = max(prices)

        return price_range if price_range else None

    def _extract_brands(self, text: str) -> List[str]:
        """Extract brand mentions."""
        brands = []
        text_lower = text.lower()

        # Check known brands
        for brand in self.luxury_brands + self.common_brands:
            if brand in text_lower:
                proper_name = " ".join(word.capitalize() for word in brand.split())
                brands.append(proper_name)

        # Check patterns for other brands
        for pattern in self.brand_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                brand = match.group(1).strip()
                excluded = [
                    "the", "and", "for", "with", "new", "best",
                    "fashion", "style", "something"
                ]
                if len(brand) > 2 and brand.lower() not in excluded:
                    brands.append(brand)

        return list(set(brands))

    def _extract_time_reference(self, text: str) -> Optional[str]:
        """Extract time reference for memory queries."""
        for time_ref, pattern in self.time_patterns.items():
            if pattern.search(text):
                return time_ref
        return None

    def _extract_entity_reference(self, text: str) -> Optional[str]:
        """Extract entity reference for clarification queries."""
        # Check for "that" or "this" + noun patterns
        patterns = [
            r'that\s+(\w+)',
            r'this\s+(\w+)',
            r'the\s+(\w+)\s+you\s+(?:showed|recommended)',
            r'item\s*#?\s*(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


# Singleton instance
_extractor_instance: Optional[ParameterExtractor] = None


def get_parameter_extractor() -> ParameterExtractor:
    """Get thread-safe singleton parameter extractor instance."""
    global _extractor_instance
    if _extractor_instance is None:
        with _extractor_lock:
            # Double-check after acquiring lock
            if _extractor_instance is None:
                _extractor_instance = ParameterExtractor()
    return _extractor_instance
