# Field mapping for fashion_products collection
FASHION_TO_STANDARD_FIELD_MAP = {
    "product_id": "id",
    "categories": "category",
    "product_type": "subcategory", 
    "primary_color": "colors",
    "collections": "tags",
    "fashion_confidence": "popularity_score"
}

def map_fashion_product(product):
    """Map fashion_products fields to standard fields"""
    if not product:
        return product
    
    mapped = product.copy()
    
    # Map ID
    if "product_id" in mapped and "id" not in mapped:
        mapped["id"] = mapped["product_id"]
    
    # Map category (take first from categories list)
    if "categories" in mapped and isinstance(mapped["categories"], list) and mapped["categories"]:
        mapped["category"] = mapped["categories"][0]
    
    # Map colors (convert single color to list)
    if "primary_color" in mapped:
        mapped["colors"] = [mapped["primary_color"]]
    
    # Ensure required fields exist
    mapped.setdefault("description", "")
    mapped.setdefault("sizes", [])
    mapped.setdefault("materials", [])
    mapped.setdefault("images", [])
    mapped.setdefault("in_stock", True)
    
    return mapped
