"""
ARI V3 Serialization Utilities

Convert V3 dataclasses to/from dict format for Neo4j storage.
"""

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import numpy as np

from ari_v3.core.data_structures import (
    OnboardingProfile,
    NavigationParameters,
    PersonalNode,
    TasteNode,
    ProcessNode,
    PracticalityNode,
    BodyNode,
    ExternalNode,
    RootValues,
)


def serialize_dataclass(obj: Any) -> Any:
    """
    Recursively serialize a dataclass to a JSON-serializable dict.

    Handles:
    - Nested dataclasses
    - Enums (converts to string value)
    - datetime (converts to ISO format)
    - numpy arrays (converts to list)
    - Optional fields
    """
    if obj is None:
        return None

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    if isinstance(obj, (list, tuple)):
        return [serialize_dataclass(item) for item in obj]

    if isinstance(obj, dict):
        return {k: serialize_dataclass(v) for k, v in obj.items()}

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            result[field.name] = serialize_dataclass(value)
        return result

    # Primitive types
    return obj


def serialize_onboarding_profile(profile: OnboardingProfile) -> Dict[str, Any]:
    """
    Serialize OnboardingProfile to dict for Neo4j storage.

    Args:
        profile: V3 OnboardingProfile dataclass

    Returns:
        Dict suitable for Neo4j storage
    """
    return serialize_dataclass(profile)


def serialize_navigation_params(params: NavigationParameters) -> Dict[str, Any]:
    """
    Serialize NavigationParameters to dict for Neo4j storage.

    Args:
        params: V3 NavigationParameters dataclass

    Returns:
        Dict suitable for Neo4j storage
    """
    return serialize_dataclass(params)


def deserialize_to_navigation_params(data: Dict[str, Any]) -> Optional[NavigationParameters]:
    """
    Deserialize dict from Neo4j to NavigationParameters.

    Args:
        data: Dict from Neo4j

    Returns:
        NavigationParameters dataclass or None
    """
    if not data:
        return None

    from ari_v3.core.data_structures import DefaultBudget

    try:
        default_budget = DefaultBudget(
            min=data.get("default_budget_min", 50),
            max=data.get("default_budget_max", 250),
            flexibility=data.get("default_budget_flexibility", 0.4),
        )

        return NavigationParameters(
            exploration_appetite=float(data.get("exploration_appetite", 0.5)),
            step_size_multiplier=float(data.get("step_size_multiplier", 1.0)),
            brand_affinity_weight=float(data.get("brand_affinity_weight", 0.5)),
            result_set_size=int(data.get("result_set_size", 10)),
            diversity_requirement=float(data.get("diversity_requirement", 0.5)),
            user_embedding_weight=float(data.get("user_embedding_weight", 0.5)),
            default_budget=default_budget,
            category_budget_overrides=data.get("category_budget_overrides", {}),
        )
    except Exception as e:
        print(f"Error deserializing NavigationParameters: {e}")
        return None
