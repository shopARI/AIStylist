"""
Type definitions for ARI Fashion Stylist System.
TypedDicts, Enums, and data models for type safety.
"""

from typing import TypedDict, Dict, List, Any, Optional, Union, Literal
from enum import Enum
from datetime import datetime


# ==================== ENUMS ====================

class InteractionType(str, Enum):
    """Types of user-product interactions."""
    VIEWED = "viewed"
    LIKED = "liked"
    PURCHASED = "purchased"
    DISLIKED = "disliked"
    ADDED_TO_CART = "added_to_cart"
    REMOVED_FROM_CART = "removed_from_cart"
    WISHLISTED = "wishlisted"


class UserSegment(str, Enum):
    """User segmentation categories."""
    CHAMPIONS = "Champions"
    LOYAL_CUSTOMERS = "Loyal Customers"
    POTENTIAL_LOYALISTS = "Potential Loyalists"
    NEW_CUSTOMERS = "New Customers"
    AT_RISK = "At Risk Customers"
    CANT_LOSE = "Can't Lose Them"
    HIBERNATING = "Hibernating"
    LOST = "Lost"
    OTHERS = "Others"


class PriceRange(str, Enum):
    """Price range categories."""
    BUDGET = "budget"  # < $50
    AFFORDABLE = "affordable"  # $50-$100
    MID_RANGE = "mid_range"  # $100-$200
    PREMIUM = "premium"  # $200-$500
    LUXURY = "luxury"  # > $500


class StyleProfile(str, Enum):
    """User style profiles."""
    CLASSIC = "classic"
    TRENDY = "trendy"
    CASUAL = "casual"
    FORMAL = "formal"
    SPORTY = "sporty"
    BOHEMIAN = "bohemian"
    MINIMALIST = "minimalist"
    VINTAGE = "vintage"
    EDGY = "edgy"
    ROMANTIC = "romantic"


class SearchIntent(str, Enum):
    """User search intent types."""
    BROWSE = "browse"
    SPECIFIC_ITEM = "specific_item"
    INSPIRATION = "inspiration"
    COMPARISON = "comparison"
    GIFT = "gift"
    OUTFIT = "outfit"
    BRAND = "brand"
    SALE = "sale"


class BattleWinner(str, Enum):
    """Battle winner options."""
    CYPHER = "cypher"
    VIBE = "vibe"
    TIE = "tie"
    CONSENSUS = "consensus"


# ==================== PRODUCT TYPES ====================

class ProductBase(TypedDict):
    """Base product structure."""
    id: str
    title: str
    description: str
    price: float
    category: str
    brand: str
    images: List[str]


class ProductFull(ProductBase):
    """Full product with all fields."""
    subcategory: Optional[str]
    colors: List[str]
    sizes: List[str]
    tags: List[str]
    materials: List[str]
    collections: List[str]
    created_at: str
    updated_at: str
    popularity_score: float
    return_rate: float
    in_stock: bool
    visited_num: int
    liked_num: int
    purchased_num: int


class ProductVector(TypedDict):
    """Product with vector embedding."""
    id: str
    embedding: List[float]
    metadata: Dict[str, Any]


class ProductRecommendation(ProductBase):
    """Product recommendation with scores."""
    score: float
    reason: str
    agent: str
    rank: int
    confidence: float


# ==================== USER TYPES ====================

class UserPreferences(TypedDict):
    """User preference structure."""
    preferred_categories: List[str]
    preferred_brands: List[str]
    preferred_colors: List[str]
    preferred_tags: List[str]
    budget_range: Dict[str, float]
    size_preferences: Dict[str, str]
    style_attributes: List[str]
    excluded_items: List[str]


class UserProfile(TypedDict):
    """User profile structure."""
    id: str
    created_at: str
    last_active: str
    email: Optional[str]
    name: Optional[str]
    location: Optional[str]
    age_group: Optional[str]
    gender: Optional[str]
    preferences: UserPreferences
    segments: List[str]
    style_profile: Optional[str]
    total_interactions: int
    total_purchases: int
    lifetime_value: float


class UserInteraction(TypedDict):
    """User interaction record."""
    user_id: str
    product_id: str
    interaction_type: str
    timestamp: str
    metadata: Optional[Dict[str, Any]]


class UserMemory(TypedDict):
    """User memory state."""
    user_id: str
    conversation_history: List[Dict[str, Any]]
    product_context: List[str]
    current_intent: Optional[str]
    session_preferences: Dict[str, Any]
    last_updated: str


# ==================== ML INTELLIGENCE TYPES ====================

class ClusterInfo(TypedDict):
    """Cluster information."""
    cluster_id: int
    characteristics: Dict[str, Any]
    keywords: List[str]
    cluster_size: int
    confidence: float


class VisualFeatures(TypedDict):
    """Visual feature information."""
    embedding_size: int
    dominant_colors: List[str]
    style_attributes: List[str]
    aesthetic_score: float
    visual_complexity: str
    embedding_model: str
    device_used: str
    processing_time: float
    metadata: Dict[str, Any]
    confidence: float


class BehavioralInsight(TypedDict):
    """Behavioral insight."""
    segment: str
    tier: str
    recency_score: int
    frequency_score: int
    monetary_score: int
    rfm_score: str
    lifetime_value: float
    last_purchase_days: int
    total_purchases: int
    confidence: float


class MLIntelligence(TypedDict):
    """Combined ML intelligence."""
    cypher_intel: Optional[Dict[str, Any]]
    vibe_intel: Optional[Dict[str, Any]]
    clustering: Optional[ClusterInfo]
    visual: Optional[VisualFeatures]
    behavioral: Optional[BehavioralInsight]
    memory_context: Optional[Dict[str, Any]]


# ==================== BATTLE TYPES ====================

class BattleRequest(TypedDict):
    """Battle request structure."""
    query: str
    filters: Optional[Dict[str, Any]]
    limit: int
    user_context: Optional[UserProfile]
    ml_intelligence: Optional[MLIntelligence]
    timeout: Optional[float]
    bypass_cache: bool


class BattleResult(TypedDict):
    """Battle result structure."""
    products: List[ProductRecommendation]
    winner: str
    cypher_count: int
    vibe_count: int
    final_count: int
    battle_time: float
    timestamp: str
    ml_enhanced: bool
    cache_hit: bool


class BattleMetrics(TypedDict):
    """Battle metrics."""
    total_battles: int
    cypher_wins: int
    vibe_wins: int
    ties: int
    consensus_wins: int
    avg_battle_time: float
    cache_hit_rate: float
    error_rate: float
    timeout_rate: float


# ==================== CACHE TYPES ====================

class CacheEntry(TypedDict):
    """Cache entry structure."""
    data: Any
    timestamp: float
    hits: int
    last_accessed: float
    ttl: int


class CacheStats(TypedDict):
    """Cache statistics."""
    size: int
    max_size: int
    ttl: int
    strategy: str
    hits: int
    misses: int
    evictions: int
    expirations: int
    hit_rate: str
    avg_entry_age: str
    memory_estimate: str


# ==================== DATABASE TYPES ====================

class Neo4jStats(TypedDict):
    """Neo4j statistics."""
    user_count: int
    interaction_count: int
    preference_count: int
    segment_count: int
    active_users_30d: int
    relationship_count: int


class QdrantStats(TypedDict):
    """Qdrant statistics."""
    vectors_count: int
    indexed_vectors_count: int
    points_count: int
    segments_count: int
    status: str
    collection_name: str


class DatabaseHealth(TypedDict):
    """Database health status."""
    neo4j: Dict[str, Any]
    qdrant: Dict[str, Any]
    cache: Dict[str, Any]
    timestamp: str


# ==================== RESPONSE TYPES ====================

class APIResponse(TypedDict):
    """Standard API response."""
    success: bool
    data: Optional[Any]
    error: Optional[str]
    timestamp: str
    request_id: str


class SearchResponse(TypedDict):
    """Search response structure."""
    products: List[ProductRecommendation]
    total_found: int
    search_time: float
    filters_applied: Dict[str, Any]
    ml_intelligence_used: bool
    personalized: bool


class ChatResponse(TypedDict):
    """Chat response structure."""
    message: str
    products: Optional[List[ProductRecommendation]]
    intent: Optional[str]
    confidence: float
    session_id: str
    timestamp: str


# ==================== CONFIGURATION TYPES ====================

class BattleConfig(TypedDict):
    """Battle configuration."""
    enable_cache: bool
    enable_optimization: bool
    enable_metrics: bool
    cache_ttl: int
    cache_max_size: int
    cache_strategy: str
    connection_pool_size: int
    max_concurrent_battles: int
    enable_auto_recovery: bool
    recovery_attempts: int
    default_limit: int
    default_timeout: float
    default_prefetch_multiplier: int


class DatabaseConfig(TypedDict):
    """Database configuration."""
    neo4j_url: str
    neo4j_username: str
    neo4j_password: str
    qdrant_url: str
    qdrant_api_key: Optional[str]
    qdrant_collection: str
    embedding_model: str


class MLConfig(TypedDict):
    """ML configuration."""
    clustering_enabled: bool
    n_clusters: int
    visual_enabled: bool
    visual_model: str
    behavioral_enabled: bool
    min_support: float
    min_confidence: float
    memory_enabled: bool
    memory_ttl: int


# ==================== HELPER FUNCTIONS ====================

def validate_interaction_type(interaction: str) -> bool:
    """Validate interaction type."""
    return interaction in [i.value for i in InteractionType]


def validate_price_range(price: float) -> PriceRange:
    """Get price range for a price."""
    if price < 50:
        return PriceRange.BUDGET
    elif price < 100:
        return PriceRange.AFFORDABLE
    elif price < 200:
        return PriceRange.MID_RANGE
    elif price < 500:
        return PriceRange.PREMIUM
    else:
        return PriceRange.LUXURY


def validate_user_segment(segment: str) -> bool:
    """Validate user segment."""
    return segment in [s.value for s in UserSegment]


def get_timestamp() -> str:
    """Get current ISO timestamp."""
    return datetime.now().isoformat()


# ==================== TYPE ALIASES ====================

ProductID = str
UserID = str
SessionID = str
QueryVector = List[float]
Embedding = List[float]
Score = float
Confidence = float
Timestamp = str
