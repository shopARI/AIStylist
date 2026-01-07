"""
ARI Navigation Intelligence V3 - Core Module

This module provides the foundational data structures for the V3 navigation system.

Key exports:
- Enums: StyleContext, InteractionType, ExplorationPreference, etc.
- Structures: OnboardingProfile, NavigationParameters, ComputedUserState, etc.
- Functions: derive_navigation_parameters, calculate_max_step_size, etc.

Usage:
    from ari_v3.core import StyleContext, NavigationParameters, derive_navigation_parameters
    from ari_v3.core.data_structures import OnboardingProfile, ComputedUserState
"""

# Enums
from .data_structures import (
    StyleContext,
    DressCode,
    UrbanType,
    OccasionFrequency,
    BrandFrequency,
    ValidationSource,
    ExplorationPreference,
    BudgetFlexibility,
    BudgetLevel,
    Undertone,
    InteractionType,
)

# Onboarding structures
from .data_structures import (
    Location,
    Occupation,
    Occasion,
    ParentalStatus,
    PersonalNode,
    GenderExpression,
    BrandPreference,
    OccasionStyle,
    TasteNode,
    StyleMotivation,
    ValidationPreference,
    SocialInfluences,
    ProcessNode,
    Budget,
    CategoryBudget,
    PracticalityNode,
    Coloring,
    BodyNode,
    SocialMediaConnection,
    ExternalNode,
    RootValues,
    OnboardingProfile,
)

# Social media embeddings
from .data_structures import (
    BoardEmbedding,
    PinterestEmbeddings,
    InstagramEmbeddings,
    TikTokEmbeddings,
    SocialTasteEmbeddings,
)

# Navigation structures
from .data_structures import (
    InterpretableDimensions,
    StyleCoordinate,
    Trajectory,
    UserEmbeddings,
    ContextualPosition,
    SpendingPatterns,
    BehavioralPatterns,
    UniversalPreferences,
    ComputedUserState,
    DefaultBudget,
    NavigationParameters,
)

# Interaction structures
from .data_structures import (
    InteractionContext,
    InteractionFeedback,
    Interaction,
    RawOnboardingConversation,
    ConversationHistory,
    RawUserData,
)

# Helper functions
from .data_structures import (
    zero_vector,
    normalize_vector,
)

# Navigation parameter functions
from .navigation_params import (
    derive_navigation_parameters,
    calculate_max_step_size,
    calculate_velocity_adjustment,
    calculate_outlier_percentage,
    get_budget_for_category,
    calculate_budget_range,
    summarize_navigation_parameters,
)

# Serialization utilities
from .serialization import (
    serialize_dataclass,
    serialize_onboarding_profile,
    serialize_navigation_params,
    deserialize_to_navigation_params,
    deserialize_to_onboarding_profile,
)

__all__ = [
    # Enums
    "StyleContext",
    "DressCode",
    "UrbanType",
    "OccasionFrequency",
    "BrandFrequency",
    "ValidationSource",
    "ExplorationPreference",
    "BudgetFlexibility",
    "BudgetLevel",
    "Undertone",
    "InteractionType",
    # Onboarding structures
    "Location",
    "Occupation",
    "Occasion",
    "ParentalStatus",
    "PersonalNode",
    "GenderExpression",
    "BrandPreference",
    "OccasionStyle",
    "TasteNode",
    "StyleMotivation",
    "ValidationPreference",
    "SocialInfluences",
    "ProcessNode",
    "Budget",
    "CategoryBudget",
    "PracticalityNode",
    "Coloring",
    "BodyNode",
    "SocialMediaConnection",
    "ExternalNode",
    "RootValues",
    "OnboardingProfile",
    # Social media embeddings
    "BoardEmbedding",
    "PinterestEmbeddings",
    "InstagramEmbeddings",
    "TikTokEmbeddings",
    "SocialTasteEmbeddings",
    # Navigation structures
    "InterpretableDimensions",
    "StyleCoordinate",
    "Trajectory",
    "UserEmbeddings",
    "ContextualPosition",
    "SpendingPatterns",
    "BehavioralPatterns",
    "UniversalPreferences",
    "ComputedUserState",
    "DefaultBudget",
    "NavigationParameters",
    # Interaction structures
    "InteractionContext",
    "InteractionFeedback",
    "Interaction",
    "RawOnboardingConversation",
    "ConversationHistory",
    "RawUserData",
    # Helper functions
    "zero_vector",
    "normalize_vector",
    # Navigation parameter functions
    "derive_navigation_parameters",
    "calculate_max_step_size",
    "calculate_velocity_adjustment",
    "calculate_outlier_percentage",
    "get_budget_for_category",
    "calculate_budget_range",
    "summarize_navigation_parameters",
    # Serialization utilities
    "serialize_dataclass",
    "serialize_onboarding_profile",
    "serialize_navigation_params",
    "deserialize_to_navigation_params",
    "deserialize_to_onboarding_profile",
]
