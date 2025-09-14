"""
Product models and field mapping for ARI Fashion Stylist.
Handles conversion between different product formats.
Based on product_field_mapping.py patterns.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import uuid
import json

from .types import ProductBase, ProductFull, ProductRecommendation, PriceRange, validate_price_range

logger = logging.getLogger("models.products")


# ==================== FIELD MAPPINGS ====================

# Fashion products to standard field mapping
FASHION_TO_STANDARD_FIELD_MAP = {
    "product_id": "id",
    "categories": "category",
    "product_type": "subcategory", 
    "primary_color": "colors",
    "collections": "tags",
    "fashion_confidence": "popularity_score"
}

# Reverse mapping
STANDARD_TO_FASHION_FIELD_MAP = {v: k for k, v in FASHION_TO_STANDARD_FIELD_MAP.items()}

# Required fields for valid product
REQUIRED_PRODUCT_FIELDS = ["id", "title", "price"]


def validate_product_uuid(product: Dict[str, Any]) -> bool:
    """
    Validate that product has UUID format ID.
    Essential for new 6M node graph consistency.
    """
    if not isinstance(product, dict):
        return False
    
    product_id = product.get('id')
    if not product_id:
        logger.warning("Product missing required 'id' field")
        return False
    
    try:
        uuid.UUID(str(product_id))
        return True
    except ValueError:
        logger.warning(f"Product ID is not UUID format: {product_id}")
        return False


def ensure_uuid_consistency(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter products to ensure only UUID-based IDs are returned.
    Critical for maintaining consistency with new 6M node graph.
    """
    valid_products = []
    for product in products:
        if validate_product_uuid(product):
            valid_products.append(product)
    
    if len(valid_products) < len(products):
        logger.info(f"Filtered {len(products) - len(valid_products)} products with non-UUID IDs")
    
    return valid_products

# Default values for missing fields
DEFAULT_FIELD_VALUES = {
    "description": "",
    "price": 0.0,
    "category": "General",
    "brand": "Unknown",
    "images": [],
    "colors": [],
    "sizes": [],
    "tags": [],
    "materials": [],
    "collections": [],
    "in_stock": True,
    "popularity_score": 0.0,
    "return_rate": 0.0,
    "visited_num": 0,
    "liked_num": 0,
    "purchased_num": 0
}


# ==================== PRODUCT CLASSES ====================

class Product:
    """
    Main product class with validation and conversion methods.
    """
    
    def __init__(self, data: Dict[str, Any]):
        """
        Initialize product from dictionary.
        
        Args:
            data: Product data dictionary
        """
        self._data = self._normalize_product_data(data)
        self._validate()
    
    def _normalize_product_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize product data to standard format.
        
        Args:
            data: Raw product data
            
        Returns:
            Normalized product data
        """
        normalized = {}
        
        # Map fashion fields to standard fields
        for fashion_field, standard_field in FASHION_TO_STANDARD_FIELD_MAP.items():
            if fashion_field in data:
                normalized[standard_field] = data[fashion_field]
        
        # Copy all other fields
        for key, value in data.items():
            if key not in FASHION_TO_STANDARD_FIELD_MAP:
                normalized[key] = value
        
        # Ensure ID exists and is UUID format (critical for Neo4j consistency)
        if "id" not in normalized and "product_id" not in normalized:
            # Instead of generating random UUID, reject product to maintain consistency
            raise ValueError("Product missing UUID - cannot maintain Neo4j consistency")
        
        # Apply defaults for missing fields
        for field, default_value in DEFAULT_FIELD_VALUES.items():
            if field not in normalized:
                normalized[field] = default_value
        
        # Special field processing
        normalized = self._process_special_fields(normalized)
        
        return normalized
    
    def _process_special_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process special fields that need conversion.
        
        Args:
            data: Product data
            
        Returns:
            Processed data
        """
        # Ensure lists are lists
        list_fields = ["images", "colors", "sizes", "tags", "materials", "collections", "categories"]
        for field in list_fields:
            if field in data:
                data[field] = self._ensure_list(data[field])
        
        # Handle category extraction from categories list
        if "categories" in data and isinstance(data["categories"], list) and data["categories"]:
            if "category" not in data or not data["category"]:
                data["category"] = data["categories"][0]
        
        # Handle colors extraction
        if "primary_color" in data and "colors" not in data:
            data["colors"] = [data["primary_color"]]
        elif "colors" in data and data["colors"] and "primary_color" not in data:
            data["primary_color"] = data["colors"][0]
        
        # Ensure numeric fields are numeric
        numeric_fields = ["price", "popularity_score", "return_rate", "visited_num", "liked_num", "purchased_num"]
        for field in numeric_fields:
            if field in data:
                try:
                    data[field] = float(data[field])
                except (ValueError, TypeError):
                    data[field] = DEFAULT_FIELD_VALUES.get(field, 0.0)
        
        # Ensure integer fields
        int_fields = ["visited_num", "liked_num", "purchased_num"]
        for field in int_fields:
            if field in data:
                data[field] = int(data[field])
        
        # Add timestamps if missing
        if "created_at" not in data:
            data["created_at"] = datetime.now().isoformat()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now().isoformat()
        
        # Calculate price range
        if "price" in data:
            data["price_range"] = validate_price_range(data["price"]).value
        
        return data
    
    def _ensure_list(self, value: Any) -> List[Any]:
        """
        Ensure value is a list.
        
        Args:
            value: Value to convert
            
        Returns:
            List value
        """
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            # Check if it's a JSON string
            if value.startswith('['):
                try:
                    return json.loads(value)
                except:
                    return [value]
            else:
                return [value] if value else []
        elif value:
            return [value]
        return []
    
    def _validate(self):
        """
        Validate product has required fields.
        
        Raises:
            ValueError: If required fields are missing
        """
        missing_fields = []
        for field in REQUIRED_PRODUCT_FIELDS:
            if field not in self._data or self._data[field] is None:
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Product missing required fields: {missing_fields}")
        
        # Validate price is positive
        if self._data.get("price", 0) < 0:
            raise ValueError(f"Product price cannot be negative: {self._data['price']}")
    
    @property
    def id(self) -> str:
        """Get product ID."""
        return self._data["id"]
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get product data dictionary."""
        return self._data.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Product dictionary
        """
        return self.data
    
    def to_base(self) -> ProductBase:
        """
        Convert to base product type.
        
        Returns:
            ProductBase dictionary
        """
        return {
            "id": self._data["id"],
            "title": self._data.get("title", ""),
            "description": self._data.get("description", ""),
            "price": self._data.get("price", 0.0),
            "category": self._data.get("category", ""),
            "brand": self._data.get("brand", ""),
            "images": self._data.get("images", [])
        }
    
    def to_full(self) -> ProductFull:
        """
        Convert to full product type.
        
        Returns:
            ProductFull dictionary
        """
        return {
            "id": self._data["id"],
            "title": self._data.get("title", ""),
            "description": self._data.get("description", ""),
            "price": self._data.get("price", 0.0),
            "category": self._data.get("category", ""),
            "brand": self._data.get("brand", ""),
            "images": self._data.get("images", []),
            "subcategory": self._data.get("subcategory"),
            "colors": self._data.get("colors", []),
            "sizes": self._data.get("sizes", []),
            "tags": self._data.get("tags", []),
            "materials": self._data.get("materials", []),
            "collections": self._data.get("collections", []),
            "created_at": self._data.get("created_at", ""),
            "updated_at": self._data.get("updated_at", ""),
            "popularity_score": self._data.get("popularity_score", 0.0),
            "return_rate": self._data.get("return_rate", 0.0),
            "in_stock": self._data.get("in_stock", True),
            "visited_num": self._data.get("visited_num", 0),
            "liked_num": self._data.get("liked_num", 0),
            "purchased_num": self._data.get("purchased_num", 0)
        }
    
    def to_recommendation(
        self,
        score: float = 0.0,
        reason: str = "",
        agent: str = "",
        rank: int = 0,
        confidence: float = 0.0
    ) -> ProductRecommendation:
        """
        Convert to recommendation type.
        
        Args:
            score: Recommendation score
            reason: Recommendation reason
            agent: Recommending agent
            rank: Product rank
            confidence: Confidence score
            
        Returns:
            ProductRecommendation dictionary
        """
        base = self.to_base()
        return {
            **base,
            "score": score,
            "reason": reason,
            "agent": agent,
            "rank": rank,
            "confidence": confidence
        }
    
    def to_fashion_format(self) -> Dict[str, Any]:
        """
        Convert to fashion product format.
        
        Returns:
            Fashion format dictionary
        """
        fashion = {}
        
        # Map standard fields to fashion fields
        for standard_field, fashion_field in STANDARD_TO_FASHION_FIELD_MAP.items():
            if standard_field in self._data:
                fashion[fashion_field] = self._data[standard_field]
        
        # Copy non-mapped fields
        for key, value in self._data.items():
            if key not in STANDARD_TO_FASHION_FIELD_MAP and key not in fashion:
                fashion[key] = value
        
        return fashion
    
    def calculate_popularity_score(self) -> float:
        """
        Calculate popularity score from interactions.
        
        Returns:
            Popularity score (0-1)
        """
        visited = self._data.get("visited_num", 0)
        liked = self._data.get("liked_num", 0)
        purchased = self._data.get("purchased_num", 0)
        
        # Weighted score
        score = (visited * 0.1 + liked * 0.3 + purchased * 0.6) / 100
        
        # Normalize to 0-1
        return min(1.0, score)
    
    def update_interaction_count(
        self,
        interaction_type: str,
        increment: int = 1
    ):
        """
        Update interaction count.
        
        Args:
            interaction_type: Type of interaction
            increment: Amount to increment
        """
        if interaction_type == "viewed":
            self._data["visited_num"] = self._data.get("visited_num", 0) + increment
        elif interaction_type == "liked":
            self._data["liked_num"] = self._data.get("liked_num", 0) + increment
        elif interaction_type == "purchased":
            self._data["purchased_num"] = self._data.get("purchased_num", 0) + increment
        
        # Update popularity score
        self._data["popularity_score"] = self.calculate_popularity_score()
        
        # Update timestamp
        self._data["updated_at"] = datetime.now().isoformat()
    
    def matches_filters(self, filters: Dict[str, Any]) -> bool:
        """
        Check if product matches filters.
        
        Args:
            filters: Filter dictionary
            
        Returns:
            True if matches all filters
        """
        for key, value in filters.items():
            if key == "min_price" and self._data.get("price", 0) < value:
                return False
            elif key == "max_price" and self._data.get("price", 0) > value:
                return False
            elif key == "category" and self._data.get("category") != value:
                return False
            elif key == "brand" and self._data.get("brand") != value:
                return False
            elif key == "colors" and isinstance(value, list):
                product_colors = self._data.get("colors", [])
                if not any(color in product_colors for color in value):
                    return False
            elif key == "in_stock" and self._data.get("in_stock") != value:
                return False
        
        return True
    
    def __str__(self) -> str:
        """String representation."""
        return f"Product({self.id}: {self._data.get('title', 'Untitled')})"
    
    def __repr__(self) -> str:
        """Developer representation."""
        return f"Product(id={self.id}, title={self._data.get('title')}, price={self._data.get('price')})"


# ==================== HELPER FUNCTIONS ====================

def map_fashion_product(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map fashion product fields to standard fields.
    Legacy function for compatibility.
    
    Args:
        product: Fashion format product
        
    Returns:
        Standard format product, or None if invalid UUID
    """
    if not product:
        return product
    
    try:
        p = Product(product)
        return p.to_dict()
    except ValueError as e:
        if "missing UUID" in str(e):
            logger.warning(f"Skipping product without UUID to maintain Neo4j consistency: {product.get('title', 'Unknown')}")
            return None  # Return None for invalid products
        else:
            logger.error(f"Error mapping product: {e}")
            return product
    except Exception as e:
        logger.error(f"Error mapping product: {e}")
        return product


def create_product_from_dict(data: Dict[str, Any]) -> Optional[Product]:
    """
    Create Product instance from dictionary.
    
    Args:
        data: Product data
        
    Returns:
        Product instance or None if invalid
    """
    try:
        return Product(data)
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return None


def validate_product_data(data: Dict[str, Any]) -> bool:
    """
    Validate product data.
    
    Args:
        data: Product data
        
    Returns:
        True if valid
    """
    try:
        Product(data)
        return True
    except:
        return False


def merge_product_data(
    base: Dict[str, Any],
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge product data with updates.
    
    Args:
        base: Base product data
        updates: Updates to apply
        
    Returns:
        Merged product data
    """
    merged = base.copy()
    
    for key, value in updates.items():
        if value is not None:
            merged[key] = value
    
    # Update timestamp
    merged["updated_at"] = datetime.now().isoformat()
    
    return merged


def create_search_text(product: Dict[str, Any]) -> str:
    """
    Create searchable text from product data.
    
    Args:
        product: Product data
        
    Returns:
        Searchable text string
    """
    parts = []
    
    # Add text fields
    for field in ['title', 'description']:
        if product.get(field):
            parts.append(product[field])
    
    # Add categorical fields
    for field, label in [('category', 'Category'), ('brand', 'Brand')]:
        if product.get(field):
            parts.append(f"{label}: {product[field]}")
    
    # Add list fields
    for field, label in [('colors', 'Colors'), ('tags', 'Tags'), ('materials', 'Materials')]:
        if product.get(field):
            values = product[field] if isinstance(product[field], list) else [product[field]]
            if values:
                parts.append(f"{label}: {', '.join(str(v) for v in values)}")
    
    return " ".join(parts)


def prepare_qdrant_payload(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare product payload for Qdrant storage.
    
    Args:
        product: Product data
        
    Returns:
        Qdrant-ready payload
    """
    try:
        # Create Product instance to normalize data
        p = Product(product)
        data = p.to_dict()
        
        # Ensure all required Qdrant fields with proper types
        payload = {
            "id": data.get("id", str(uuid.uuid4())),
            "title": str(data.get("title", "")),
            "description": str(data.get("description", "")),
            "price": float(data.get("price", 0)),
            "category": str(data.get("category", "")),
            "subcategory": str(data.get("subcategory", "")),
            "brand": str(data.get("brand", "")),
            "colors": list(data.get("colors", [])),
            "sizes": list(data.get("sizes", [])),
            "tags": list(data.get("tags", [])),
            "materials": list(data.get("materials", [])),
            "collections": list(data.get("collections", [])),
            "images": list(data.get("images", [])),
            "created_at": str(data.get("created_at", datetime.now().isoformat())),
            "updated_at": datetime.now().isoformat(),
            "popularity_score": float(data.get("popularity_score", 0)),
            "return_rate": float(data.get("return_rate", 0)),
            "in_stock": bool(data.get("in_stock", True)),
            "visited_num": int(data.get("visited_num", 0)),
            "fashion_confidence": float(data.get("fashion_confidence", data.get("popularity_score", 0))),
            "product_type": str(data.get("subcategory", data.get("category", ""))),
            "primary_color": str(data.get("colors", [""])[0] if data.get("colors") else ""),
            "categories": list(data.get("categories", [data.get("category", "")]))
        }
        
        return payload
        
    except Exception as e:
        logger.error(f"Error preparing Qdrant payload: {e}")
        # Return minimal valid payload
        return {
            "id": product.get("id", str(uuid.uuid4())),
            "title": str(product.get("title", "")),
            "price": float(product.get("price", 0))
        }


def extract_product_features(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract features for ML processing.
    
    Args:
        product: Product data
        
    Returns:
        Feature dictionary
    """
    features = {
        "price": float(product.get("price", 0)),
        "category_count": len(product.get("categories", [])),
        "tag_count": len(product.get("tags", [])),
        "color_count": len(product.get("colors", [])),
        "has_images": len(product.get("images", [])) > 0,
        "popularity_score": float(product.get("popularity_score", 0)),
        "return_rate": float(product.get("return_rate", 0)),
        "visited_num": int(product.get("visited_num", 0)),
        "liked_num": int(product.get("liked_num", 0)),
        "purchased_num": int(product.get("purchased_num", 0)),
        "in_stock": product.get("in_stock", True),
        "description_length": len(product.get("description", ""))
    }
    
    return features
