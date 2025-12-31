"""
Pydantic models for structured CrewAI output.
Eliminates regex parsing and enforces type safety.
"""
from .product_models import (
    Product,
    GraphSearchResult,
    VectorSearchResult,
    VisualSearchResult,
    JudgmentResult,
    ProductSearchState,
    ProductSearchResult
)

__all__ = [
    'Product',
    'GraphSearchResult',
    'VectorSearchResult',
    'VisualSearchResult',
    'JudgmentResult',
    'ProductSearchState',
    'ProductSearchResult'
]
