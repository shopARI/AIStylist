"""
Fashion vocabulary configuration
Centralized configuration for colors, categories, and other fashion terms
"""

# Color vocabulary
COLORS = [
    "red", "blue", "green", "yellow", "black", "white", "pink", "purple",
    "orange", "brown", "gray", "grey", "navy", "beige", "gold", "silver",
    "maroon", "teal", "coral", "turquoise", "lavender", "mint", "cream",
    "khaki", "burgundy", "olive", "rose", "tan", "charcoal", "ivory"
]

# Category vocabulary
CATEGORIES = [
    "dress", "shirt", "pants", "shoes", "clothing", "outfit", "fashion", "style",
    "jacket", "coat", "blazer", "skirt", "blouse", "sweater", "jeans", "shorts",
    "boots", "sneakers", "sandals", "accessories", "bag", "purse", "scarf",
    "hat", "belt", "jewelry", "watch", "sunglasses", "swimwear", "underwear"
]

# Specific item categories for optimization
SPECIFIC_ITEMS = [
    "dress", "gown", "suit", "jacket", "coat", "shirt", "pants", "shoes",
    "blazer", "blouse", "skirt", "sweater", "cardigan", "vest", "top",
    "leggings", "shorts", "boots", "heels", "flats", "sneakers"
]

# Style preferences
STYLE_PREFERENCES = [
    "casual", "formal", "business", "elegant", "trendy", "classic", "modern",
    "vintage", "bohemian", "minimalist", "edgy", "romantic", "sporty",
    "professional", "chic", "sophisticated", "relaxed", "street", "preppy"
]

# Occasions
OCCASIONS = [
    "work", "business", "meeting", "interview", "party", "wedding", "date",
    "casual", "formal", "evening", "cocktail", "brunch", "vacation", "beach",
    "gym", "workout", "travel", "dinner", "lunch", "office", "weekend"
]

# Price range keywords
PRICE_KEYWORDS = [
    "cheap", "affordable", "budget", "expensive", "luxury", "premium",
    "discount", "sale", "under", "below", "above", "around", "maximum", "minimum"
]

# Brand keywords (extendable)
BRAND_KEYWORDS = [
    "designer", "brand", "label", "signature", "collection", "exclusive",
    "limited", "edition", "premium", "luxury", "boutique", "custom"
]