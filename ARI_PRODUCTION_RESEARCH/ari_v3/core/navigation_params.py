"""
ARI Navigation Intelligence V3 - Navigation Parameters Derivation

This module implements the deterministic derivation of NavigationParameters
from OnboardingProfile, as specified in:
- ARI_Navigation_Intelligence_PSEUDOCODE_V3.md (Section 1.1)
- ARI_V3_Implementation_Roadmap.md (Step 1.2)

Key principle: No LLM needed - pure computation from profile data.

Formulas:
- exploration_appetite = (adventurousness/10) * 0.7 + (1 - creative_control/10) * 0.3
- step_size_multiplier = 0.5 + (adventurousness/10) * 1.0
- user_embedding_weight = 0.3 + (creative_control/10) * 0.4
- brand_affinity_weight = brand_loyalty / 10

Date: January 2026
"""

from typing import Dict

from .data_structures import (
    OnboardingProfile,
    NavigationParameters,
    DefaultBudget,
    ExplorationPreference,
    BudgetFlexibility,
    BudgetLevel,
)


def derive_navigation_parameters(profile: OnboardingProfile) -> NavigationParameters:
    """
    Deterministic derivation of navigation parameters from onboarding profile.
    No LLM needed - pure computation.

    Args:
        profile: The user's OnboardingProfile from interpretation LLM

    Returns:
        NavigationParameters controlling navigation behavior

    Raises:
        ValueError: If any input values are outside expected ranges

    Example:
        >>> profile = OnboardingProfile(...)
        >>> nav_params = derive_navigation_parameters(profile)
        >>> print(nav_params.exploration_appetite)  # 0.0 - 1.0
    """
    process = profile.process
    practicality = profile.practicality

    # =========================================================================
    # INPUT VALIDATION
    # Ensure all values are within expected ranges to prevent calculation errors
    # =========================================================================
    if not (1 <= process.adventurousness <= 10):
        raise ValueError(f"adventurousness must be 1-10, got {process.adventurousness}")
    if not (1 <= process.creative_control <= 10):
        raise ValueError(f"creative_control must be 1-10, got {process.creative_control}")
    if not (1 <= process.brand_loyalty <= 10):
        raise ValueError(f"brand_loyalty must be 1-10, got {process.brand_loyalty}")

    # =========================================================================
    # EXPLORATION APPETITE
    # High adventurousness + low creative_control = high exploration
    # =========================================================================
    adventurousness = process.adventurousness / 10.0
    creative_control = process.creative_control / 10.0

    exploration_appetite = adventurousness * 0.7 + (1 - creative_control) * 0.3
    exploration_appetite = _clamp(exploration_appetite, 0.0, 1.0)

    # =========================================================================
    # STEP SIZE MULTIPLIER
    # High adventurousness = larger steps allowed
    # Range: 0.5 (conservative) to 1.5 (bold)
    # =========================================================================
    step_size_multiplier = 0.5 + adventurousness * 1.0
    step_size_multiplier = _clamp(step_size_multiplier, 0.5, 1.5)

    # =========================================================================
    # BRAND AFFINITY WEIGHT
    # Direct mapping from brand_loyalty
    # =========================================================================
    brand_affinity_weight = process.brand_loyalty / 10.0
    brand_affinity_weight = _clamp(brand_affinity_weight, 0.0, 1.0)

    # =========================================================================
    # RESULT SET SIZE & DIVERSITY
    # Based on exploration_preference
    # =========================================================================
    result_set_size, diversity_requirement = _derive_result_config(
        process.exploration_preference
    )

    # =========================================================================
    # USER EMBEDDING WEIGHT
    # High creative_control = user history matters more
    # =========================================================================
    user_embedding_weight = 0.3 + creative_control * 0.4
    user_embedding_weight = _clamp(user_embedding_weight, 0.3, 0.7)

    # =========================================================================
    # BUDGET
    # =========================================================================
    default_budget = _derive_default_budget(practicality.budget)
    category_budget_overrides = _derive_category_overrides(
        practicality.category_budgets,
        default_budget
    )

    return NavigationParameters(
        exploration_appetite=exploration_appetite,
        step_size_multiplier=step_size_multiplier,
        brand_affinity_weight=brand_affinity_weight,
        result_set_size=result_set_size,
        diversity_requirement=diversity_requirement,
        user_embedding_weight=user_embedding_weight,
        default_budget=default_budget,
        category_budget_overrides=category_budget_overrides,
    )


def _derive_result_config(preference: ExplorationPreference) -> tuple[int, float]:
    """
    Derive result set size and diversity requirement from exploration preference.

    Returns:
        Tuple of (result_set_size, diversity_requirement)
    """
    if preference == ExplorationPreference.LONG_EXPLORE:
        return 20, 0.7  # More results, more diverse
    elif preference == ExplorationPreference.CURATED_OPTIONS:
        return 5, 0.3   # Few results, more focused
    else:  # QUICK_DECIDE
        return 10, 0.5  # Balanced


def _derive_default_budget(budget) -> DefaultBudget:
    """
    Derive default budget range from user's stated budget.

    Assumptions:
    - Single item budget is ~10% of monthly budget
    - Max for investment piece is ~50% of monthly budget
    """
    monthly = budget.monthly

    # Flexibility factor based on budget flexibility
    flexibility_map = {
        BudgetFlexibility.FIRM: 0.2,
        BudgetFlexibility.GUIDELINE: 0.4,
        BudgetFlexibility.FLEXIBLE: 0.6,
    }
    flexibility = flexibility_map.get(budget.flexibility, 0.4)

    return DefaultBudget(
        min=monthly * 0.1,
        max=monthly * 0.5,
        flexibility=flexibility,
    )


def _derive_category_overrides(
    category_budgets: Dict,
    default_budget: DefaultBudget
) -> Dict[str, DefaultBudget]:
    """
    Derive per-category budget overrides.

    - SPLURGE: 1.5x min, 2.0x max
    - BUDGET: 0.3x min, 0.5x max
    - MODERATE: uses default
    """
    overrides = {}

    for category, pref in category_budgets.items():
        if pref.budget_level == BudgetLevel.SPLURGE:
            overrides[category] = DefaultBudget(
                min=default_budget.min * 1.5,
                max=default_budget.max * 2.0,
                flexibility=default_budget.flexibility,
            )
        elif pref.budget_level == BudgetLevel.BUDGET:
            overrides[category] = DefaultBudget(
                min=default_budget.min * 0.3,
                max=default_budget.max * 0.5,
                flexibility=default_budget.flexibility,
            )
        # MODERATE uses default - no override needed

    return overrides


def _clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value to a range.

    Handles NaN and Inf values safely by returning the midpoint of the range.
    """
    import math
    if not math.isfinite(value):
        # Return midpoint for invalid values
        return (min_val + max_val) / 2.0
    return max(min_val, min(max_val, value))


# =============================================================================
# Velocity and Step Size Calculations (used by navigation engine)
# =============================================================================

def calculate_max_step_size(nav_params: NavigationParameters) -> float:
    """
    Calculate maximum step size for navigation.

    From V3 spec:
    - Base max step = 0.3 (in normalized embedding space)
    - Scaled by step_size_multiplier

    Returns:
        Maximum step size in embedding space (0.15 - 0.45 typical range)
    """
    BASE_MAX_STEP = 0.3
    return BASE_MAX_STEP * nav_params.step_size_multiplier


def calculate_velocity_adjustment(
    user_velocity: float,
    nav_params: NavigationParameters
) -> float:
    """
    Adjust step size based on user's style evolution velocity.

    From V3 spec:
    - Slow movers (velocity < 0.3): 0.7x multiplier
    - Normal movers (0.3 - 0.7): 1.0x multiplier
    - Fast movers (velocity > 0.7): 1.2x multiplier

    Args:
        user_velocity: Current velocity from trajectory (0-1)
        nav_params: User's navigation parameters

    Returns:
        Velocity adjustment factor
    """
    if user_velocity < 0.3:
        return 0.7
    elif user_velocity > 0.7:
        return 1.2
    else:
        return 1.0


def calculate_outlier_percentage(nav_params: NavigationParameters) -> float:
    """
    Calculate what percentage of results should be outliers (exploration items).

    From V3 spec:
    - outlier_percentage = exploration_appetite * 0.20
    - This means max 20% outliers for most adventurous users

    Returns:
        Percentage of results to fill with outliers (0.0 - 0.2)
    """
    return nav_params.exploration_appetite * 0.20


def get_budget_for_category(
    category: str,
    nav_params: NavigationParameters
) -> DefaultBudget:
    """
    Get the budget range for a specific category.

    Args:
        category: Product category (e.g., "shoes", "tops")
        nav_params: User's navigation parameters

    Returns:
        Budget range for the category (override if exists, else default)
    """
    return nav_params.category_budget_overrides.get(
        category,
        nav_params.default_budget
    )


def calculate_budget_range(
    budget: DefaultBudget,
    allow_flexibility: bool = True
) -> tuple[float, float]:
    """
    Calculate actual min/max budget range, optionally applying flexibility.

    Args:
        budget: Budget specification
        allow_flexibility: Whether to apply flexibility buffer

    Returns:
        Tuple of (min_price, max_price)
    """
    min_price = budget.min
    max_price = budget.max

    if allow_flexibility:
        # Apply flexibility as buffer (e.g., 0.4 flexibility = 40% buffer)
        buffer = max_price * budget.flexibility
        min_price = max(0, min_price - buffer * 0.5)
        max_price = max_price + buffer

    return min_price, max_price


# =============================================================================
# Navigation Parameters Summary (for debugging/logging)
# =============================================================================

def summarize_navigation_parameters(nav_params: NavigationParameters) -> dict:
    """
    Create a human-readable summary of navigation parameters.

    Useful for debugging and logging.
    """
    return {
        "exploration_appetite": f"{nav_params.exploration_appetite:.2f}",
        "exploration_style": _describe_exploration(nav_params.exploration_appetite),
        "step_size_multiplier": f"{nav_params.step_size_multiplier:.2f}",
        "max_step_size": f"{calculate_max_step_size(nav_params):.3f}",
        "brand_affinity": f"{nav_params.brand_affinity_weight:.2f}",
        "brand_style": _describe_brand_affinity(nav_params.brand_affinity_weight),
        "result_set_size": nav_params.result_set_size,
        "diversity_requirement": f"{nav_params.diversity_requirement:.2f}",
        "user_embedding_weight": f"{nav_params.user_embedding_weight:.2f}",
        "outlier_percentage": f"{calculate_outlier_percentage(nav_params):.1%}",
        "budget_range": f"${nav_params.default_budget.min:.0f} - ${nav_params.default_budget.max:.0f}",
        "budget_flexibility": f"{nav_params.default_budget.flexibility:.0%}",
    }


def _describe_exploration(appetite: float) -> str:
    """Human-readable exploration style description."""
    if appetite < 0.3:
        return "Conservative (sticks close to known styles)"
    elif appetite < 0.6:
        return "Balanced (open to gentle exploration)"
    else:
        return "Adventurous (loves discovering new styles)"


def _describe_brand_affinity(weight: float) -> str:
    """Human-readable brand affinity description."""
    if weight < 0.3:
        return "Brand-agnostic (open to any brand)"
    elif weight < 0.6:
        return "Moderate loyalty (has favorites but explores)"
    else:
        return "Brand-loyal (strongly prefers known brands)"
