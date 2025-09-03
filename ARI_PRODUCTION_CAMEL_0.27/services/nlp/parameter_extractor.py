"""
Parameter Extractor for AI Stylist
Extracts structured parameters from natural language queries
Complete implementation from old system
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("parameter_extractor")


import re
import logging
from typing import Any, Dict, List, Optional

# Setup logger for this module
logger = logging.getLogger(__name__)


class ParameterExtractor:
    """Extracts structured parameters from user messages"""

    def __init__(self):
        """Initialize with fashion vocabularies and pre-compiled regex patterns"""

        # Fashion vocabularies (unchanged)
        self.occasions = ["wedding", "party", "work", "casual", "formal", "date", "dinner", "beach", "gala", "cocktail", "interview", "brunch", "vacation", "travel", "gym", "workout", "meeting", "conference", "birthday", "anniversary", "graduation", "prom", "homecoming", "festival", "concert", "clubbing", "office", "business"]
        self.colors = ["red", "blue", "green", "black", "white", "yellow", "purple", "orange", "pink", "brown", "gray", "grey", "navy", "teal", "maroon", "beige", "turquoise", "gold", "silver", "cream", "burgundy", "coral", "mint", "olive", "rust", "sage", "lavender", "peach", "emerald", "crimson", "indigo", "khaki", "tan", "ivory", "charcoal", "rose", "wine", "forest"]
        self.materials = ["cotton", "silk", "wool", "polyester", "linen", "leather", "denim", "suede", "velvet", "cashmere", "satin", "nylon", "chiffon", "lace", "tweed", "jersey", "modal", "bamboo", "rayon", "spandex", "lycra", "mesh", "sequin", "fleece", "corduroy", "canvas", "georgette", "crepe", "taffeta"]
        self.categories = ["dress", "shirt", "pants", "jeans", "skirt", "blouse", "sweater", "jacket", "coat", "suit", "blazer", "t-shirt", "hoodie", "shorts", "swimwear", "activewear", "athletic", "sportswear", "workout", "gym", "shoes", "boots", "sneakers", "accessories", "jewelry", "necklace", "bracelet", "earrings", "ring", "watch", "scarf", "hat", "gown", "outfit", "cardigan", "vest", "leggings", "jumpsuit", "romper", "tank", "camisole", "tunic", "kimono", "poncho", "trench", "parka", "bomber", "duster", "cape", "shawl"]
        self.styles = ["classic", "modern", "vintage", "boho", "minimalist", "chic", "elegant", "edgy", "preppy", "streetwear", "athleisure", "romantic", "gothic", "punk", "grunge", "retro", "glamorous", "sophisticated", "trendy", "timeless", "bold", "feminine", "masculine", "androgynous", "casual", "professional", "luxe", "indie", "hipster", "nautical", "western", "ethnic"]
        self.seasons = ["spring", "summer", "fall", "autumn", "winter"]
        self.sizes = ["xs", "s", "m", "l", "xl", "xxl", "xxxl", "petite", "plus", "tall", "regular", "0", "2", "4", "6", "8", "10", "12", "14", "16", "18", "20"]
        self.luxury_brands = ["chanel", "dior", "gucci", "prada", "versace", "balenciaga", "saint laurent", "bottega veneta", "burberry", "givenchy", "valentino", "fendi", "celine", "loewe", "hermes", "louis vuitton", "tom ford", "alexander mcqueen", "stella mccartney", "miu miu"]

        # --- FIX: Pre-compile regex patterns for performance ---
        self.size_patterns = [
            re.compile(r'size\s+(\d+)'),
            re.compile(r'size\s+(\d+\w+)'),
            re.compile(r'(\d+)\s+size'),
            re.compile(r'wear\s+a?\s+(\d+)'),
            re.compile(r'i\'m\s+a?\s+(\d+)'),
        ]
        self.price_patterns = {
            "under": re.compile(r'(?:under|less than|below|max|maximum)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
            "over": re.compile(r'(?:over|more than|above|min|minimum|at least)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
            "between": re.compile(r'(?:between|from)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s+(?:and|to|-)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
            "around": re.compile(r'(?:around|about|approximately|roughly)\s+\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
            "budget": re.compile(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s+budget', re.IGNORECASE),
            "simple": re.compile(r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)')
        }
        self.brand_patterns = [
            re.compile(r'(?:from|by|brand|designer|label)\s+([A-Z][A-Za-z\s&]+?)(?:\s|,|\.|\?|!|$)'),
            re.compile(r'([A-Z][A-Za-z\s&]+?)\s+(?:collection|brand|designer)'),
            re.compile(r'like\s+([A-Z][A-Za-z\s&]+?)(?:\s|,|\.|\?|!|$)'),
        ]
        self.time_patterns = {
            re.compile(r'\btoday\b'): "today", re.compile(r'\btonight\b'): "tonight",
            re.compile(r'\btomorrow\b'): "tomorrow", re.compile(r'\bthis week\b'): "this_week",
            re.compile(r'\bnext week\b'): "next_week", re.compile(r'\bthis weekend\b'): "this_weekend",
            re.compile(r'\bnext weekend\b'): "next_weekend", re.compile(r'\bthis month\b'): "this_month",
            re.compile(r'\bnext month\b'): "next_month", re.compile(r'\basap\b'): "asap",
            re.compile(r'\burgent\b'): "urgent", re.compile(r'\bsoon\b'): "soon",
            re.compile(r'\bimmediately\b'): "immediate"
        }
        self.specific_date_pattern = re.compile(r'(?:on|by|for)\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?)')
        self.number_pattern = re.compile(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b')
        self.date_patterns = [
            re.compile(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b'),
            re.compile(r'\b\d{1,2}-\d{1,2}-\d{2,4}\b'),
            re.compile(r'\b\d{4}-\d{1,2}-\d{1,2}\b')
        ]
        
        logger.info("ParameterExtractor initialized with comprehensive fashion vocabulary and compiled regex")

    def extract_parameters(self, message: str) -> Dict[str, Any]:
        """Extract all relevant parameters from a message"""
        # This method's logic remains the same, but it now calls the updated helpers.
        params = {"category": None, "categories": [], "occasion": None, "occasions": [], "colors": [], "materials": [], "styles": [], "season": None, "size": None, "price_range": {}, "budget": None, "brand_preferences": [], "is_luxury": False, "time_frame": None, "urgency": None, "formality_level": None, "special_requirements": [], "sustainability": False, "vegan": False, "entities": {"numbers": [], "dates": []}}
        message_lower = message.lower()
        found_categories = self._extract_items(message_lower, self.categories)
        if found_categories:
            params["categories"] = found_categories
            params["category"] = found_categories[0]
        found_occasions = self._extract_items(message_lower, self.occasions)
        if found_occasions:
            params["occasions"] = found_occasions
            params["occasion"] = found_occasions[0]
        params["colors"] = self._extract_items(message_lower, self.colors)
        params["materials"] = self._extract_items(message_lower, self.materials)
        params["styles"] = self._extract_items(message_lower, self.styles)
        found_seasons = self._extract_items(message_lower, self.seasons)
        if found_seasons:
            params["season"] = found_seasons[0]
        params["size"] = self._extract_size(message_lower)
        price_info = self._extract_price_range(message)
        if price_info:
            params["price_range"] = price_info
            if "max" in price_info:
                params["budget"] = price_info["max"]
        params["brand_preferences"] = self._extract_brand_preferences(message)
        params["is_luxury"] = self._is_luxury_request(message_lower)
        params["time_frame"] = self._extract_time_frame(message_lower)
        params["urgency"] = self._extract_urgency(message_lower)
        params["formality_level"] = self._extract_formality_level(message_lower)
        params["special_requirements"] = self._extract_special_requirements(message_lower)
        sustainability_keywords = ["sustainable", "eco-friendly", "ethical", "organic", "recycled"]
        params["sustainability"] = any(keyword in message_lower for keyword in sustainability_keywords)
        vegan_keywords = ["vegan", "cruelty-free", "no leather", "no fur", "no wool"]
        params["vegan"] = any(keyword in message_lower for keyword in vegan_keywords)
        params["entities"]["numbers"] = self._extract_numbers(message)
        params["entities"]["dates"] = self._extract_dates(message_lower)
        params = self._clean_params(params)
        logger.debug(f"Extracted parameters: {params}")
        return params

    def _extract_items(self, text: str, vocabulary: List[str]) -> List[str]:
        """Extract items from text that match vocabulary, with typo correction and plural handling"""
        found_items = []
        
        # Common typos mapping
        typo_corrections = {
            "shrt": "shirt",
            "shrts": "shirts", 
            "pnts": "pants",
            "jens": "jeans",
            "drss": "dress",
            "sheos": "shoes",
            "jackt": "jacket",
            "swetr": "sweater"
        }
        
        # ENHANCED: Plural to singular mapping for better category detection
        plural_corrections = {
            "shirts": "shirt",
            "pants": "pants",  # pants is already plural
            "jeans": "jeans",  # jeans is already plural
            "dresses": "dress",
            "tops": "top",
            "sweaters": "sweater",
            "jackets": "jacket",
            "blazers": "blazer",
            "skirts": "skirt",
            "shorts": "shorts",  # shorts is already plural
            "boots": "boots",   # boots can be plural
            "shoes": "shoes",   # shoes is already plural
            "tees": "tee",
            "tanks": "tank",
            "hoodies": "hoodie"
        }
        
        # Correct common typos first
        corrected_text = text
        for typo, correction in typo_corrections.items():
            corrected_text = re.sub(r'\b' + re.escape(typo) + r'\b', correction, corrected_text)
        
        # ENHANCED: Handle plurals by converting to singulars for better matching
        for plural, singular in plural_corrections.items():
            corrected_text = re.sub(r'\b' + re.escape(plural) + r'\b', singular, corrected_text)
        
        # ENHANCED: Handle common variations and synonyms
        variations = {
            "t-shirt": "shirt",
            "tshirt": "shirt", 
            "tee": "shirt",
            "tank top": "tank",
            "tanktop": "tank",
            "polo": "shirt",
            "button-up": "shirt",
            "button up": "shirt",
            "blouse": "blouse",  # Keep blouse separate
            "top": "top",
            "athletic wear": "activewear",
            "workout": "activewear"
        }
        
        for variation, canonical in variations.items():
            corrected_text = re.sub(r'\b' + re.escape(variation) + r'\b', canonical, corrected_text)
        
        # Extract items from corrected text
        for item in vocabulary:
            if re.search(r'\b' + re.escape(item) + r'\b', corrected_text):
                found_items.append(item)
        
        return found_items

    def _extract_size(self, text: str) -> Optional[str]:
        """Extract size information"""
        for size in self.sizes:
            if re.search(r'\b' + str(size) + r'\b', text):
                return str(size).upper() if size in ["xs", "s", "m", "l", "xl", "xxl", "xxxl"] else str(size)
        for pattern in self.size_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1)
        return None

    def _extract_price_range(self, text: str) -> Dict[str, float]:
        """Extract price range information with validation"""
        price_range = {}
        
        def validate_and_clamp(price_val: float) -> float:
            """Inner function for price sanity checks."""
            # --- FIX: Validate prices ---
            if price_val < 0 or price_val > 1000000:  # Sanity check
                logger.warning(f"Unusual price detected: ${price_val}. Clamping to a valid range.")
                return min(max(price_val, 0), 1000000)
            return price_val

        match = self.price_patterns["under"].search(text)
        if match:
            price_range["max"] = validate_and_clamp(float(match.group(1).replace(',', '')))

        match = self.price_patterns["over"].search(text)
        if match:
            price_range["min"] = validate_and_clamp(float(match.group(1).replace(',', '')))

        match = self.price_patterns["between"].search(text)
        if match:
            price_range["min"] = validate_and_clamp(float(match.group(1).replace(',', '')))
            price_range["max"] = validate_and_clamp(float(match.group(2).replace(',', '')))

        match = self.price_patterns["around"].search(text)
        if match:
            price = validate_and_clamp(float(match.group(1).replace(',', '')))
            price_range["min"] = price * 0.8
            price_range["max"] = price * 1.2
            price_range["target"] = price

        match = self.price_patterns["budget"].search(text)
        if match:
            price_range["max"] = validate_and_clamp(float(match.group(1).replace(',', '')))

        if not price_range:
            matches = self.price_patterns["simple"].findall(text)
            if matches:
                prices = [validate_and_clamp(float(m.replace(',', ''))) for m in matches]
                if len(prices) == 1:
                    price_range["target"] = prices[0]
                    price_range["min"] = prices[0] * 0.7
                    price_range["max"] = prices[0] * 1.3
                elif len(prices) == 2:
                    price_range["min"] = min(prices)
                    price_range["max"] = max(prices)
        return price_range

    def _extract_brand_preferences(self, text: str) -> List[str]:
        """Extract brand mentions"""
        brands = []
        text_lower = text.lower()
        for brand in self.luxury_brands:
            if brand in text_lower:
                proper_name = " ".join(word.capitalize() for word in brand.split())
                brands.append(proper_name)
        
        for pattern in self.brand_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                brand = match.group(1).strip()
                if len(brand) > 2 and brand.lower() not in ["the", "and", "for", "with", "new", "best"]:
                    brands.append(brand)
        
        return list(set(brands))

    def _is_luxury_request(self, text: str) -> bool:
        """Detect if this is a luxury/high-end request"""
        luxury_indicators = ["luxury", "designer", "premium", "exclusive", "haute", "couture", "high-end", "high end", "upscale", "deluxe", "prestige", "elite", "bespoke", "artisan", "sophisticated"]
        if any(indicator in text for indicator in luxury_indicators):
            return True
        if any(brand in text for brand in self.luxury_brands):
            return True
        return False

    def _extract_time_frame(self, text: str) -> Optional[str]:
        """Extract when the item is needed"""
        for pattern, time_frame in self.time_patterns.items():
            if pattern.search(text):
                return time_frame
        match = self.specific_date_pattern.search(text)
        if match:
            return f"specific_date: {match.group(1)}"
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days:
            if day in text:
                prefix = "next_" if "next" in text else "this_" if "this" in text else ""
                return f"{prefix}{day}"
        return None
    
    # All other helper methods (_extract_urgency, _extract_formality_level, etc.) remain the same,
    # except for those using regex which are now updated.

    def _extract_urgency(self, text: str) -> Optional[str]:
        """Extract urgency level"""
        if any(word in text for word in ["asap", "urgent", "immediately", "right now", "emergency"]):
            return "high"
        elif any(word in text for word in ["soon", "quickly", "fast"]):
            return "medium"
        elif any(word in text for word in ["whenever", "no rush", "take your time"]):
            return "low"
        return None

    def _extract_formality_level(self, text: str) -> Optional[str]:
        """Extract formality level"""
        formality_indicators = {"formal": ["formal", "black tie", "white tie", "gala", "elegant", "sophisticated", "dressy"], "semi_formal": ["semi-formal", "cocktail", "smart casual", "business casual"], "business": ["business", "professional", "work", "office", "corporate", "meeting"], "casual": ["casual", "relaxed", "comfortable", "everyday", "laid-back", "informal"], "very_casual": ["very casual", "loungewear", "athleisure", "sporty", "lounge", "comfy"]}
        for level, indicators in formality_indicators.items():
            if any(indicator in text for indicator in indicators):
                return level
        return None

    def _extract_special_requirements(self, text: str) -> List[str]:
        """Extract special requirements or preferences"""
        requirements = []
        weather_patterns = {"warm weather": "warm_weather", "hot weather": "warm_weather", "cold weather": "cold_weather", "winter": "cold_weather", "rain": "water_resistant", "rainy": "water_resistant", "outdoor": "outdoor_appropriate", "sun": "sun_protection"}
        for pattern, requirement in weather_patterns.items():
            if pattern in text:
                requirements.append(requirement)
        if any(word in text for word in ["comfortable", "comfy", "stretchy", "soft"]):
            requirements.append("comfortable_fit")
        if any(word in text for word in ["loose", "relaxed fit", "oversized", "baggy"]):
            requirements.append("loose_fit")
        if any(word in text for word in ["fitted", "tailored", "slim fit", "tight", "bodycon"]):
            requirements.append("fitted")
        if "maternity" in text or "pregnant" in text:
            requirements.append("maternity")
        if "nursing" in text or "breastfeeding" in text:
            requirements.append("nursing_friendly")
        if any(word in text for word in ["modest", "conservative", "covered"]):
            requirements.append("modest")
        if "machine washable" in text or "easy care" in text:
            requirements.append("easy_care")
        if "wrinkle" in text:
            requirements.append("wrinkle_resistant")
        if "travel" in text:
            requirements.append("travel_friendly")
        return list(set(requirements))

    def _extract_numbers(self, text: str) -> List[float]:
        """Extract numbers from text"""
        matches = self.number_pattern.findall(text)
        numbers = []
        for match in matches:
            try:
                numbers.append(float(match.replace(',', '')))
            except ValueError:
                pass
        return numbers

    def _extract_dates(self, text: str) -> List[str]:
        """Extract date references"""
        dates = []
        months = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
        for month in months:
            if month in text:
                dates.append(month)
        for pattern in self.date_patterns:
            matches = pattern.findall(text)
            dates.extend(matches)
        return dates

    def _clean_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Clean up empty values from parameters"""
        cleaned = {}
        for key, value in params.items():
            if not value:
                continue
            if isinstance(value, dict):
                cleaned_dict = self._clean_params(value)
                if cleaned_dict:
                    cleaned[key] = cleaned_dict
            elif isinstance(value, list) and not value:
                continue
            else:
                cleaned[key] = value
        return cleaned  

# Singleton instance
_extractor_instance = None


def get_parameter_extractor() -> ParameterExtractor:
    """Get singleton parameter extractor instance"""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ParameterExtractor()
    return _extractor_instance


# Legacy function for backward compatibility
def extract_parameters(message: str) -> Dict[str, Any]:
    """
    Legacy function for parameter extraction
    
    Args:
        message: User message
        
    Returns:
        Dictionary of extracted parameters
    """
    extractor = get_parameter_extractor()
    return extractor.extract_parameters(message)
