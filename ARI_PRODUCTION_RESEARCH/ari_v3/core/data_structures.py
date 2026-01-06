"""
ARI Navigation Intelligence V3 - Core Data Structures

This module implements the data structures specified in:
- ARI_Navigation_Intelligence_PSEUDOCODE_V3.md (Section 1)
- ARI_V3_Implementation_Roadmap.md (Step 1)

Key structures:
- StyleContext: User context enum (professional, casual, evening, etc.)
- OnboardingProfile: Structured output from interpretation LLM
- NavigationParameters: Derived from onboarding, controls navigation behavior
- StyleCoordinate: Position in style space (embeddings are canonical)
- ContextualPosition: Per-context position with trajectory
- ComputedUserState: Query-time computed state with all pillars

Date: January 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


# =============================================================================
# SECTION 1.1.a: Core Enums
# =============================================================================

class StyleContext(Enum):
    """
    Users don't have ONE style - they have a style repertoire.
    Different contexts activate different style modes.
    """
    PROFESSIONAL = "professional"      # Work, meetings, interviews
    CASUAL = "casual"                  # Weekends, errands, relaxed
    EVENING = "evening"                # Date night, dinner, events
    FORMAL = "formal"                  # Weddings, galas, ceremonies
    ACTIVE = "active"                  # Gym, sports, outdoor activities
    CREATIVE = "creative"              # Artistic events, self-expression
    TRAVEL = "travel"                  # Vacation, comfort + style
    DEFAULT = "default"                # When context is unclear


class DressCode(Enum):
    """Workplace dress code categories."""
    FORMAL = "formal"
    BUSINESS_CASUAL = "business_casual"
    CASUAL = "casual"
    CREATIVE = "creative"
    VARIES = "varies"


class UrbanType(Enum):
    """Urban/suburban/rural classification."""
    URBAN = "urban"
    SUBURBAN = "suburban"
    RURAL = "rural"


class OccasionFrequency(Enum):
    """How often an occasion occurs."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    OCCASIONAL = "occasional"


class BrandFrequency(Enum):
    """How often user shops a brand."""
    ALWAYS = "always"
    OFTEN = "often"
    SOMETIMES = "sometimes"
    EXPLORING = "exploring"


class ValidationSource(Enum):
    """Who the user seeks validation from."""
    SELF = "self"
    PARTNER = "partner"
    FRIENDS = "friends"
    COLLEAGUES = "colleagues"
    STRANGERS = "strangers"
    SOCIETY = "society"


class ExplorationPreference(Enum):
    """How user prefers to explore products."""
    LONG_EXPLORE = "long_explore"       # Likes to browse many options
    QUICK_DECIDE = "quick_decide"       # Wants to decide fast
    CURATED_OPTIONS = "curated_options" # Wants few, perfect options


class BudgetFlexibility(Enum):
    """How flexible is the budget."""
    FIRM = "firm"
    GUIDELINE = "guideline"
    FLEXIBLE = "flexible"


class BudgetLevel(Enum):
    """Per-category budget level."""
    SPLURGE = "splurge"
    MODERATE = "moderate"
    BUDGET = "budget"


class Undertone(Enum):
    """Skin undertone."""
    WARM = "warm"
    COOL = "cool"
    NEUTRAL = "neutral"


class InteractionType(Enum):
    """Types of user-product interactions."""
    VIEWED = "viewed"
    LIKED = "liked"
    PURCHASED = "purchased"
    REJECTED = "rejected"
    SAVED = "saved"
    PASSED = "passed"       # V3: Saw but didn't engage
    RETURNED = "returned"   # V3: Purchased then returned


# =============================================================================
# SECTION 1.1: Onboarding Data Structures
# =============================================================================

@dataclass
class Location:
    """User's location information."""
    city: str
    region: str
    urban_suburban_rural: UrbanType
    climate: Optional[str] = None


@dataclass
class Occupation:
    """User's work information."""
    title: str
    industry: str
    dress_code: DressCode
    work_style_alignment: float  # 0-1: Does work wardrobe = authentic self?


@dataclass
class Occasion:
    """A recurring occasion in user's life."""
    name: str                      # User's exact words: "park with Max"
    frequency: OccasionFrequency
    importance: float              # 0-1: How much they care
    style_context: StyleContext    # Mapped to enum


@dataclass
class ParentalStatus:
    """User's parental information."""
    has_kids: bool
    kid_ages: List[int] = field(default_factory=list)
    parenting_style_impact: Optional[str] = None


@dataclass
class PersonalNode:
    """PERSONAL NODE - Demographics and life context."""
    age: int
    life_stage: str                # "early_career", "established", "transitioning"
    location: Location
    occupation: Occupation
    occasions: List[Occasion]
    gender_identity: str           # User's own words
    ethnicity: Optional[str] = None
    cultural_background: Optional[str] = None
    relationship_status: Optional[str] = None
    parental_status: Optional[ParentalStatus] = None


@dataclass
class GenderExpression:
    """How user expresses gender through fashion."""
    spectrum_position: str         # User's description
    fluidity: float                # 0-1: How much it varies
    fit_preferences: List[str]     # "structured", "fluid", "fitted"


@dataclass
class BrandPreference:
    """A brand the user loves."""
    brand: str
    why_love_it: str               # Root value connection
    frequency: BrandFrequency


@dataclass
class OccasionStyle:
    """How user dresses for a specific occasion."""
    description: str
    consistency_with_other_contexts: float  # 0-1: Same person or code-switching?


@dataclass
class TasteNode:
    """TASTE NODE - Style preferences and aesthetics."""
    gender_expression: GenderExpression
    brand_preferences: List[BrandPreference]
    shape_preferences: List[str]   # Silhouettes they gravitate toward
    fit_preferences: List[str]     # Oversized, tailored, bodycon
    style_loves: str               # What's working now
    style_wants: str               # Direction they want to go
    style_avoids: str              # Hard boundaries
    occasion_styles: Dict[str, OccasionStyle]  # Keyed by occasion name
    style_icons: List[str] = field(default_factory=list)


@dataclass
class StyleMotivation:
    """A motivation behind style choices."""
    motivation: str                # "confidence", "self-expression", "fitting in"
    importance: float              # 0-1
    root_value: str                # Deeper "why"


@dataclass
class ValidationPreference:
    """Who user seeks validation from."""
    source: ValidationSource
    importance: float              # 0-1


@dataclass
class SocialInfluences:
    """How social factors influence style."""
    primary_sources: List[str]     # Where they get inspiration
    trend_relationship: str        # Leader, follower, ignorer
    originality_importance: float  # 0-1


@dataclass
class ProcessNode:
    """PROCESS NODE - How user approaches style decisions. Drives NavigationParameters."""
    style_motivations: List[StyleMotivation]
    creative_control: int          # 1-10: How much they want to steer vs be steered
    style_goals: str               # What success looks like
    brand_loyalty: int             # 1-10: Stick with favorites vs explore
    adventurousness: int           # 1-10: Subtle evolution vs bold moves
    validation_sources: List[ValidationPreference]
    exploration_preference: ExplorationPreference
    social_influences: SocialInfluences


@dataclass
class Budget:
    """Budget constraints."""
    monthly: float
    yearly: float
    flexibility: BudgetFlexibility
    investment_mindset: str        # How they think about price vs value


@dataclass
class CategoryBudget:
    """Per-category budget preference."""
    budget_level: BudgetLevel
    reasoning: str


@dataclass
class PracticalityNode:
    """PRACTICALITY NODE - Budget and constraints."""
    budget: Budget
    category_budgets: Dict[str, CategoryBudget]  # e.g., "shoes", "tops"


@dataclass
class Coloring:
    """User's natural coloring."""
    skin_tone: str
    undertone: Undertone
    hair_color: str
    eye_color: str
    seasonal_palette: Optional[str] = None  # "autumn", "winter", etc.


@dataclass
class BodyNode:
    """BODY NODE - Physical attributes (photos stored separately)."""
    face_photo_id: Optional[str] = None
    body_photo_id: Optional[str] = None
    coloring: Optional[Coloring] = None
    body_verbal: Optional[str] = None       # Their own description
    favorite_features: List[str] = field(default_factory=list)
    # Note: insecurities NOT stored explicitly - too sensitive


@dataclass
class SocialMediaConnection:
    """A connected social media account."""
    handle: str
    connected: bool
    last_synced: Optional[datetime] = None
    boards_analyzed: List[str] = field(default_factory=list)  # Pinterest only


@dataclass
class ExternalNode:
    """EXTERNAL NODE - Social media connections."""
    instagram: Optional[SocialMediaConnection] = None
    pinterest: Optional[SocialMediaConnection] = None
    tiktok: Optional[SocialMediaConnection] = None


@dataclass
class RootValues:
    """Root values extracted across all onboarding nodes."""
    primary: str                   # The deepest "why" - what style means to them
    secondary: List[str]           # Supporting values

    # Value dimensions (0-1 scales)
    authenticity_importance: float      # Being true to self
    belonging_importance: float         # Fitting in with community
    standing_out_importance: float      # Being noticed/unique
    comfort_importance: float           # Physical and psychological comfort
    competence_importance: float        # Looking capable/professional

    value_tensions: List[str] = field(default_factory=list)  # Where values conflict


@dataclass
class OnboardingProfile:
    """
    Structured output from the Interpretation LLM (#2).
    Maps directly to the 6 onboarding nodes.

    This is the V3-aligned structure that captures:
    - Explicit preferences (what user said)
    - Implicit signals (how they said it)
    - Root values (why they care)
    """
    personal: PersonalNode
    taste: TasteNode
    process: ProcessNode
    practicality: PracticalityNode
    body: BodyNode
    external: ExternalNode
    root_values: RootValues

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    reinterpreted_at: Optional[datetime] = None
    reinterpretation_count: int = 0


# =============================================================================
# SECTION 1.2: Social Media Embeddings
# =============================================================================

@dataclass
class BoardEmbedding:
    """Embedding for a Pinterest board."""
    embedding: np.ndarray          # 1536d vector
    pin_count: int
    dominant_themes: List[str]
    # style_coordinates computed on demand via property


@dataclass
class PinterestEmbeddings:
    """Embeddings from Pinterest analysis."""
    boards: Dict[str, BoardEmbedding]
    overall_embedding: np.ndarray  # Weighted blend of boards
    last_synced: datetime


@dataclass
class InstagramEmbeddings:
    """Embeddings from Instagram analysis."""
    saved_posts_embedding: np.ndarray
    liked_posts_embedding: Optional[np.ndarray] = None
    following_style_embedding: np.ndarray = None
    overall_embedding: np.ndarray = None
    last_synced: datetime = None


@dataclass
class TikTokEmbeddings:
    """Embeddings from TikTok analysis."""
    liked_videos_embedding: np.ndarray
    saved_videos_embedding: Optional[np.ndarray] = None
    overall_embedding: np.ndarray = None
    last_synced: datetime = None


@dataclass
class SocialTasteEmbeddings:
    """
    Embeddings derived from connected social media accounts.
    Provides rich taste signals beyond explicit preferences.
    """
    pinterest: Optional[PinterestEmbeddings] = None
    instagram: Optional[InstagramEmbeddings] = None
    tiktok: Optional[TikTokEmbeddings] = None
    unified_social_embedding: Optional[np.ndarray] = None  # Combined 1536d


# =============================================================================
# SECTION 1.3: Core Navigation Structures
# =============================================================================

@dataclass
class InterpretableDimensions:
    """
    Human-readable style dimensions.
    Derived from embeddings via learned projections.
    Used for explanations and UI, NOT for retrieval.
    """
    form: float           # structured <-> fluid (0-1)
    color_warmth: float   # cool <-> warm (0-1)
    color_saturation: float  # muted <-> vibrant (0-1)
    formality: float      # casual <-> formal (0-1)
    proportion: float     # fitted <-> oversized (0-1)
    minimalism: float     # minimal <-> maximalist (0-1)
    edge: float           # classic <-> edgy (0-1)


@dataclass
class StyleCoordinate:
    """
    Position in style space.
    Embeddings are canonical. Explicit dimensions are DERIVED for interpretability.
    """
    embedding: np.ndarray          # Primary representation (OpenAI 1536d)
    visual_embedding: Optional[np.ndarray] = None  # SigLIP 1024d

    def interpretable_dimensions(self) -> InterpretableDimensions:
        """
        Project embedding onto interpretable axes.
        Used for explanations and UI, NOT for retrieval.

        Note: This requires trained projection vectors.
        Returns placeholder values until projections are trained.
        """
        # TODO: Implement with trained projection vectors
        # These projections are learned from labeled product data
        return InterpretableDimensions(
            form=0.5,
            color_warmth=0.5,
            color_saturation=0.5,
            formality=0.5,
            proportion=0.5,
            minimalism=0.5,
            edge=0.5
        )


@dataclass
class Trajectory:
    """Style evolution direction and velocity."""
    direction: np.ndarray          # Normalized direction vector in embedding space
    velocity: float                # Rate of change (0-1)
    consistency: float             # Stability of this direction (0-1)
    last_computed: datetime


@dataclass
class UserEmbeddings:
    """User's computed embeddings."""
    liked_embedding: np.ndarray           # From liked products
    purchased_embedding: np.ndarray       # From purchases (stronger signal)
    unified_embedding: np.ndarray         # Weighted combination
    confidence: float                     # Based on data quality


@dataclass
class ContextualPosition:
    """
    V3: Full per-context state including trajectory.
    Users have different positions in different contexts.
    """
    context: StyleContext
    position: StyleCoordinate
    trajectory: Trajectory
    embeddings: UserEmbeddings

    # Data quality metrics
    interaction_count: int
    confidence: float              # 0-1, based on data volume
    last_interaction: datetime


@dataclass
class SpendingPatterns:
    """Analyzed spending behavior."""
    median_spend: float
    stated_budget: float
    spending_ratio: float          # actual / stated
    category_spend: Dict[str, float]
    investment_categories: List[str]  # Where they splurge
    budget_categories: List[str]      # Where they save


@dataclass
class BehavioralPatterns:
    """Detected behavioral patterns from interactions."""
    exploration_rate: float        # How much they explore vs stick to known
    return_rate: float             # How often they return items
    decision_speed: float          # How quickly they make decisions
    time_of_day_preference: str    # When they shop
    seasonal_preference: Dict[str, float]  # Season -> preference weight


@dataclass
class UniversalPreferences:
    """Cross-context stable preferences."""
    always_preferred: List[str]    # e.g., ["natural fabrics", "earth tones"]
    always_avoided: List[str]      # e.g., ["synthetic", "neon colors"]
    stable_dimensions: List[str]   # Interpretable dimensions that don't vary


@dataclass
class ComputedUserState:
    """
    V3: Computed at query time with per-context trajectories.
    This is the complete user state used for navigation.
    """
    # Context-aware positions (one per detected context)
    detected_contexts: List[StyleContext]
    positions_by_context: Dict[StyleContext, ContextualPosition]

    # Active context for current query
    active_context: StyleContext
    active_position: ContextualPosition

    # Cross-context patterns
    universal_preferences: UniversalPreferences

    # Unified embeddings (blends across contexts + social)
    embeddings: UserEmbeddings

    # Social taste signal
    social_embeddings: Optional[SocialTasteEmbeddings]

    # Patterns
    spending_patterns: SpendingPatterns
    behavioral_patterns: BehavioralPatterns

    # Navigation parameters (from onboarding)
    nav_params: 'NavigationParameters'


# =============================================================================
# SECTION 1.3b: Navigation Parameters (moved from separate file for clarity)
# =============================================================================

@dataclass
class DefaultBudget:
    """Default budget range for product search."""
    min: float
    max: float
    flexibility: float  # How much to allow over/under (0-1)


@dataclass
class NavigationParameters:
    """
    Deterministically derived from OnboardingProfile.
    These control the navigation algorithm behavior.

    Derivation formulas (from V3 spec):
    - exploration_appetite = (adventurousness/10) * 0.7 + (1 - creative_control/10) * 0.3
    - step_size_multiplier = 0.5 + (adventurousness/10) * 1.0
    - user_embedding_weight = 0.3 + (creative_control/10) * 0.4
    - brand_affinity_weight = brand_loyalty / 10
    """

    # From process.adventurousness + process.creative_control
    exploration_appetite: float        # 0-1, controls outlier %
    step_size_multiplier: float        # 0.5-1.5, scales default step size

    # From process.brand_loyalty
    brand_affinity_weight: float       # 0-1, how much to favor known brands

    # From process.exploration_preference
    result_set_size: int               # How many results to return
    diversity_requirement: float       # 0-1, MMR lambda parameter

    # From process.creative_control
    user_embedding_weight: float       # Base weight for user vs query

    # From practicality.budget
    default_budget: DefaultBudget
    category_budget_overrides: Dict[str, DefaultBudget]


# =============================================================================
# SECTION 1.4: Interaction and Feedback Structures
# =============================================================================

@dataclass
class InteractionContext:
    """Context in which an interaction occurred."""
    occasion: Optional[str]
    query: Optional[str]
    session_id: str
    style_context: StyleContext


@dataclass
class InteractionFeedback:
    """Feedback signals from an interaction."""
    explicit_rating: Optional[int] = None  # 1-5 if provided
    time_spent_seconds: int = 0
    returned_to_view: bool = False


@dataclass
class Interaction:
    """A user-product interaction."""
    product_id: str
    type: InteractionType
    timestamp: datetime
    context: InteractionContext
    feedback: InteractionFeedback


@dataclass
class RawOnboardingConversation:
    """Raw conversation from onboarding (for re-interpretation)."""
    node: str                      # "personal", "taste", etc.
    messages: List[Dict[str, str]]  # [{role: str, content: str}]
    timestamp: datetime


@dataclass
class ConversationHistory:
    """A past conversation session."""
    timestamp: datetime
    messages: List[Dict[str, str]]
    session_context: Dict[str, Any]
    products_discussed: List[str]


@dataclass
class RawUserData:
    """
    V3: Complete user data loaded from Neo4j.
    Extended to include all onboarding data.
    """
    user_id: str

    # Onboarding data
    onboarding_profile: Optional[OnboardingProfile]
    raw_onboarding_conversations: List[RawOnboardingConversation]
    navigation_parameters: Optional[NavigationParameters]

    # Body data
    body_type: Optional[str]
    coloring: Optional[str]
    body_photo_url: Optional[str]
    face_photo_url: Optional[str]

    # Social media
    social_embeddings: Optional[SocialTasteEmbeddings]

    # Interaction history
    interactions: List[Interaction]

    # Conversation history
    conversation_history: List[ConversationHistory]

    # Metadata
    created_at: datetime
    last_active: datetime
    onboarding_completed: bool
    calibration_completed: bool = False  # TBD: Post-onboarding calibration


# =============================================================================
# Helper functions for numpy array handling
# =============================================================================

def zero_vector(dim: int = 1536) -> np.ndarray:
    """Create a zero vector of specified dimension."""
    return np.zeros(dim, dtype=np.float32)


def normalize_vector(v: np.ndarray) -> np.ndarray:
    """Normalize a vector to unit length."""
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm
