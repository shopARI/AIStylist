"""
User Models

Pydantic models for user profiles, preferences, and behavioral data.
These models ensure type safety and validation throughout the system.
"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DecisionMakingStyle(str, Enum):
    """Decision making style options."""
    TELL_ME = "tell_me"
    CURATED_OPTIONS = "curated_options"
    MANY_OPTIONS = "many_options"


class ChangeReadiness(str, Enum):
    """Change readiness options."""
    REFINE = "refine"
    EVOLVE = "evolve"
    TRANSFORM = "transform"
    EXPLORE = "explore"


class WorkplaceContext(str, Enum):
    """Workplace context options."""
    FORMAL_OFFICE = "formal_office"
    BUSINESS_CASUAL = "business_casual"
    CASUAL = "casual"
    REMOTE = "remote"
    NO_WORKPLACE = "no_workplace"
    VARIES = "varies"


class ShoppingBehavior(str, Enum):
    """Shopping behavior options."""
    PLANNED_ONLINE = "planned_online"
    PLANNED_INSTORE = "planned_instore"
    IMPULSE_ONLINE = "impulse_online"
    IMPULSE_INSTORE = "impulse_instore"
    MIXED = "mixed"


class ShoppingFrequency(str, Enum):
    """Shopping frequency options."""
    SEASONAL = "seasonal"
    MONTHLY = "monthly"
    CONTINUOUS = "continuous"
    MINIMAL = "minimal"


class User(BaseModel):
    """Core user profile model."""

    # Identity
    id: str
    username: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime
    last_active: datetime
    onboarding_completed: bool = False
    onboarding_completed_at: Optional[datetime] = None

    # Demographics
    age_range: Optional[str] = None
    location: Optional[str] = None

    # Social (optional)
    instagram_handle: Optional[str] = None
    pinterest_handle: Optional[str] = None
    tiktok_handle: Optional[str] = None

    # Style Autonomy - Stated
    stated_advice_receptiveness: Optional[float] = Field(None, ge=1, le=10)
    stated_creative_control: Optional[float] = Field(None, ge=1, le=10)
    stated_risk_tolerance: Optional[float] = Field(None, ge=1, le=10)
    decision_making_style: Optional[DecisionMakingStyle] = None

    # Style Autonomy - Observed
    observed_advice_receptiveness: Optional[float] = Field(None, ge=1, le=10)
    observed_creative_control: Optional[float] = Field(None, ge=1, le=10)
    observed_risk_tolerance: Optional[float] = Field(None, ge=1, le=10)
    observation_confidence: Optional[float] = Field(None, ge=0, le=1)
    preference_drift: Optional[float] = None

    # Expression
    stated_expression_spectrum: Optional[float] = Field(None, ge=1, le=10)
    observed_expression_spectrum: Optional[float] = Field(None, ge=1, le=10)

    # Self Expression
    statement_level: Optional[float] = Field(None, ge=1, le=10)
    change_readiness: Optional[ChangeReadiness] = None
    aspiration_text: Optional[str] = None

    # Lifestyle
    workplace_context: Optional[WorkplaceContext] = None
    occasion_flexibility: Optional[float] = Field(None, ge=1, le=10)

    # Shopping
    shopping_behavior: Optional[ShoppingBehavior] = None
    brand_loyalty: Optional[float] = Field(None, ge=1, le=10)
    shopping_frequency: Optional[ShoppingFrequency] = None

    # Budget
    monthly_budget_min: Optional[int] = Field(None, ge=0)
    monthly_budget_max: Optional[int] = Field(None, ge=0)
    value_perception: Optional[float] = Field(None, ge=1, le=10)

    # Metrics
    total_searches: int = 0
    total_products_viewed: int = 0
    total_products_saved: int = 0
    total_purchases: int = 0

    # Free text fields
    confidence_areas: Optional[str] = None
    pain_points: Optional[str] = None
    inspiration_sources: Optional[str] = None
    splurge_save_preference: Optional[str] = None

    class Config:
        use_enum_values = True


class StyleAdjectiveWithPriority(BaseModel):
    """Style adjective with priority."""
    name: str
    priority: int


class OccasionWithFrequency(BaseModel):
    """Occasion with frequency."""
    name: str
    frequency: str


class ValueWithImportance(BaseModel):
    """Value priority with importance rank."""
    name: str
    importance: int


class BudgetCategory(BaseModel):
    """Budget category with price range."""
    category: str
    min_price: int = Field(ge=0)
    max_price: int = Field(ge=0)

    @field_validator('max_price')
    @classmethod
    def validate_max_greater_than_min(cls, v, info):
        """Ensure max price is greater than min price."""
        if 'min_price' in info.data and v < info.data['min_price']:
            raise ValueError('max_price must be greater than min_price')
        return v


class UserProfile(BaseModel):
    """Complete user profile with relationships."""
    user: User
    style_adjectives: List[StyleAdjectiveWithPriority] = []
    fit_preferences: List[str] = []
    life_stages: List[str] = []
    occasions: List[OccasionWithFrequency] = []
    values: List[ValueWithImportance] = []
    motivations: List[str] = []
    budgets: List[BudgetCategory] = []


class UserBehaviorSummary(BaseModel):
    """Summary of user behavioral data."""
    user_id: str
    total_views: int
    total_saves: int
    total_purchases: int
    total_searches: int
    top_categories: List[str]
    top_brands: List[str]
    average_price_point: Optional[float] = None
    last_activity: datetime


class PreferenceDriftReport(BaseModel):
    """Report on stated vs observed preference drift."""
    user_id: str
    overall_drift: float
    expression_spectrum_drift: Optional[float] = None
    risk_tolerance_drift: Optional[float] = None
    advice_receptiveness_drift: Optional[float] = None
    observation_confidence: float
    recommendation: str


class ProductRef(BaseModel):
    """Reference to a product in the product database."""
    product_id: str
    product_title: Optional[str] = None
    product_category: Optional[str] = None


class ProductInteraction(BaseModel):
    """User interaction with a product."""
    user_id: str
    product: ProductRef
    interaction_type: str  # viewed, saved, purchased
    timestamp: datetime
    metadata: Dict[str, Any] = {}
