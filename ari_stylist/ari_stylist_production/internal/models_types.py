"""
Type Definitions for AI Fashion System
Comprehensive type definitions using TypedDict and dataclasses
"""

from typing import TypedDict, Optional, List, Dict, Any, Union, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# =============================================================================
# ENUMS
# =============================================================================

class ProductStatus(Enum):
    """Product availability status."""
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    LIMITED = "limited"
    COMING_SOON = "coming_soon"
    DISCONTINUED = "discontinued"

class UserSegment(Enum):
    """RFM user segments."""
    CHAMPIONS = "Champions"
    LOYAL_CUSTOMERS = "Loyal Customers"
    POTENTIAL_LOYALISTS = "Potential Loyalists"
    NEW_CUSTOMERS = "New Customers"
    AT_RISK = "At Risk"
    LOST = "Lost"
    OTHER = "Other"

class SearchMethod(Enum):
    """Search method used by agents."""
    GRAPH_RELATIONSHIPS = "graph_relationships"
    VECTOR_SIMILARITY = "vector_similarity"
    COLLABORATIVE_FILTERING = "collaborative_filtering"
    SEMANTIC_SEARCH = "semantic_search"
    VISUAL_SEARCH = "visual_search"
    TRENDING = "trending"
    HYBRID = "hybrid"

class BattleWinner(Enum):
    """Battle winner."""
    CYPHER = "cypher"
    VIBE = "vibe"
    DRAW = "draw"

class InteractionType(Enum):
    """User interaction types."""
    VIEWED = "viewed"
    LIKED = "liked"
    PURCHASED = "purchased"
    ADDED_TO_CART = "added_to_cart"
    REMOVED_FROM_CART = "removed_from_cart"
    REVIEWED = "reviewed"
    SHARED = "shared"

# =============================================================================
# PRODUCT TYPES
# =============================================================================

class ProductDict(TypedDict, total=False):
    """Product dictionary structure."""
    id: str
    product_id: str  # Alias for id
    title: str
    description: str
    price: float
    original_price: Optional[float]
    discount_percentage: Optional[float]
    category: str
    subcategory: Optional[str]
    brand: str
    colors: List[str]
    sizes: List[str]
    materials: List[str]
    tags: List[str]
    images: List[str]
    status: str
    in_stock: bool
    stock_quantity: Optional[int]
    rating: Optional[float]
    review_count: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]
    # Agent metadata
    agent: Optional[str]
    search_method: Optional[str]
    relevance_score: Optional[float]
    cypher_rank: Optional[int]
    vibe_rank: Optional[int]
    recommendation_reason: Optional[str]

@dataclass
class Product:
    """Product dataclass with validation."""
    id: str
    title: str
    description: str
    price: float
    category: str
    brand: str
    images: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    sizes: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    subcategory: Optional[str] = None
    status: ProductStatus = ProductStatus.IN_STOCK
    in_stock: bool = True
    stock_quantity: Optional[int] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def is_on_sale(self) -> bool:
        """Check if product is on sale."""
        return self.discount_percentage is not None and self.discount_percentage > 0
    
    def to_dict(self) -> ProductDict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price": self.price,
            "original_price": self.original_price,
            "discount_percentage": self.discount_percentage,
            "category": self.category,
            "subcategory": self.subcategory,
            "brand": self.brand,
            "colors": self.colors,
            "sizes": self.sizes,
            "materials": self.materials,
            "tags": self.tags,
            "images": self.images,
            "status": self.status.value,
            "in_stock": self.in_stock,
            "stock_quantity": self.stock_quantity,
            "rating": self.rating,
            "review_count": self.review_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# =============================================================================
# USER TYPES
# =============================================================================

class UserPreferencesDict(TypedDict, total=False):
    """User preferences dictionary."""
    favorite_categories: List[str]
    favorite_brands: List[str]
    preferred_styles: List[str]
    preferred_colors: List[str]
    preferred_sizes: List[str]
    price_range: Dict[str, float]
    excluded_categories: List[str]
    excluded_brands: List[str]

class UserContextDict(TypedDict, total=False):
    """User context dictionary."""
    user_id: str
    segment: str
    preferences: UserPreferencesDict
    history: List[Dict[str, Any]]
    recent_queries: List[str]
    session_id: Optional[str]
    location: Optional[str]

@dataclass
class UserContext:
    """User context for personalization."""
    user_id: str
    segment: UserSegment = UserSegment.OTHER
    preferences: Optional[UserPreferencesDict] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    recent_queries: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    location: Optional[str] = None
    
    def to_dict(self) -> UserContextDict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "segment": self.segment.value,
            "preferences": self.preferences,
            "history": self.history,
            "recent_queries": self.recent_queries,
            "session_id": self.session_id,
            "location": self.location
        }

# =============================================================================
# BATTLE TYPES
# =============================================================================

class BattleRequestDict(TypedDict, total=False):
    """Battle request dictionary."""
    query: str
    filters: Optional[Dict[str, Any]]
    limit: int
    user_context: Optional[UserContextDict]
    ml_intelligence: Optional[Dict[str, Any]]
    timeout: Optional[float]
    bypass_cache: bool

class BattleResultDict(TypedDict):
    """Battle result dictionary."""
    products: List[ProductDict]
    winner: str
    cypher_count: int
    vibe_count: int
    final_count: int
    battle_time: float
    cache_hit: bool
    ml_enhanced: bool
    metadata: Dict[str, Any]

@dataclass
class BattleResult:
    """Battle result with metadata."""
    products: List[Product]
    winner: BattleWinner
    cypher_count: int
    vibe_count: int
    battle_time: float
    cache_hit: bool = False
    ml_enhanced: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def final_count(self) -> int:
        """Get final product count."""
        return len(self.products)
    
    def to_dict(self) -> BattleResultDict:
        """Convert to dictionary."""
        return {
            "products": [p.to_dict() for p in self.products],
            "winner": self.winner.value,
            "cypher_count": self.cypher_count,
            "vibe_count": self.vibe_count,
            "final_count": self.final_count,
            "battle_time": self.battle_time,
            "cache_hit": self.cache_hit,
            "ml_enhanced": self.ml_enhanced,
            "metadata": self.metadata
        }

# =============================================================================
# INTELLIGENCE TYPES
# =============================================================================

class IntelligencePacketDict(TypedDict):
    """Intelligence packet dictionary."""
    query: str
    timestamp: str
    intelligence: Dict[str, Any]
    routing: Dict[str, Any]
    metadata: Dict[str, Any]

class BehavioralIntelligenceDict(TypedDict, total=False):
    """Behavioral intelligence dictionary."""
    segment: str
    tier: str
    rfm_scores: Dict[str, Any]
    purchase_patterns: List[Dict[str, Any]]
    association_rules: List[Dict[str, Any]]
    behavioral_traits: List[str]
    confidence: float

class VisualIntelligenceDict(TypedDict, total=False):
    """Visual intelligence dictionary."""
    embedding_size: int
    dominant_colors: List[str]
    style_attributes: List[str]
    aesthetic_score: float
    visual_complexity: str
    embedding_model: str
    confidence: float

class SemanticIntelligenceDict(TypedDict, total=False):
    """Semantic intelligence dictionary."""
    detected_styles: List[str]
    color_preferences: List[str]
    pattern_preferences: List[str]
    occasion_context: Optional[str]
    aesthetic_keywords: List[str]
    style_confidence: Dict[str, float]

# =============================================================================
# INTERACTION TYPES
# =============================================================================

class InteractionDict(TypedDict):
    """User interaction dictionary."""
    user_id: str
    product_id: str
    interaction_type: str
    timestamp: str
    metadata: Optional[Dict[str, Any]]

@dataclass
class Interaction:
    """User interaction with product."""
    user_id: str
    product_id: str
    interaction_type: InteractionType
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> InteractionDict:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "product_id": self.product_id,
            "interaction_type": self.interaction_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

# =============================================================================
# MEMORY TYPES
# =============================================================================

class MemoryContextDict(TypedDict):
    """Memory context dictionary."""
    user_id: str
    conversation_id: str
    messages: List[Dict[str, str]]
    context_window: int
    token_count: int

class ConversationDict(TypedDict):
    """Conversation dictionary."""
    id: str
    user_id: str
    messages: List[Dict[str, str]]
    started_at: str
    updated_at: str
    metadata: Dict[str, Any]

# =============================================================================
# RESPONSE TYPES
# =============================================================================

class ResponseDict(TypedDict):
    """API response dictionary."""
    success: bool
    data: Optional[Any]
    error: Optional[str]
    metadata: Optional[Dict[str, Any]]

class HealthCheckDict(TypedDict):
    """Health check response."""
    status: Literal["healthy", "degraded", "unhealthy"]
    timestamp: str
    components: Dict[str, Dict[str, Any]]
    performance: Dict[str, Any]

# =============================================================================
# FILTER TYPES
# =============================================================================

class SearchFiltersDict(TypedDict, total=False):
    """Search filters dictionary."""
    categories: Optional[List[str]]
    brands: Optional[List[str]]
    price_min: Optional[float]
    price_max: Optional[float]
    colors: Optional[List[str]]
    sizes: Optional[List[str]]
    materials: Optional[List[str]]
    tags: Optional[List[str]]
    in_stock_only: bool
    min_rating: Optional[float]
    exclude_categories: Optional[List[str]]
    exclude_brands: Optional[List[str]]

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    'ProductStatus',
    'UserSegment',
    'SearchMethod',
    'BattleWinner',
    'InteractionType',
    
    # Product types
    'ProductDict',
    'Product',
    
    # User types
    'UserPreferencesDict',
    'UserContextDict',
    'UserContext',
    
    # Battle types
    'BattleRequestDict',
    'BattleResultDict',
    'BattleResult',
    
    # Intelligence types
    'IntelligencePacketDict',
    'BehavioralIntelligenceDict',
    'VisualIntelligenceDict',
    'SemanticIntelligenceDict',
    
    # Interaction types
    'InteractionDict',
    'Interaction',
    
    # Memory types
    'MemoryContextDict',
    'ConversationDict',
    
    # Response types
    'ResponseDict',
    'HealthCheckDict',
    
    # Filter types
    'SearchFiltersDict'
]
