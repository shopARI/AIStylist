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

        # Reconstruct category_budget_overrides as DefaultBudget objects
        raw_overrides = data.get("category_budget_overrides", {})
        category_overrides = {}
        if isinstance(raw_overrides, dict):
            for cat, budget_data in raw_overrides.items():
                if isinstance(budget_data, dict):
                    category_overrides[cat] = DefaultBudget(
                        min=budget_data.get("min", 50),
                        max=budget_data.get("max", 250),
                        flexibility=budget_data.get("flexibility", 0.4),
                    )

        return NavigationParameters(
            exploration_appetite=float(data.get("exploration_appetite", 0.5)),
            step_size_multiplier=float(data.get("step_size_multiplier", 1.0)),
            brand_affinity_weight=float(data.get("brand_affinity_weight", 0.5)),
            result_set_size=int(data.get("result_set_size", 10)),
            diversity_requirement=float(data.get("diversity_requirement", 0.5)),
            user_embedding_weight=float(data.get("user_embedding_weight", 0.5)),
            default_budget=default_budget,
            category_budget_overrides=category_overrides,
        )
    except Exception as e:
        print(f"Error deserializing NavigationParameters: {e}")
        return None


def deserialize_to_onboarding_profile(data: Dict[str, Any]) -> Optional[OnboardingProfile]:
    """
    Deserialize dict from Neo4j to OnboardingProfile.

    This reconstructs the full OnboardingProfile dataclass from stored dict.

    Args:
        data: Dict from Neo4j (serialized OnboardingProfile)

    Returns:
        OnboardingProfile dataclass or None
    """
    if not data:
        return None

    from ari_v3.core.data_structures import (
        Location, Occupation, Occasion, BrandPreference, GenderExpression,
        ValidationPreference, ValidationSource, StyleMotivation, Budget, CategoryBudget,
        Coloring, StyleContext, OccasionStyle, ExplorationPreference, SocialInfluences,
        SocialMediaConnection,
    )

    def _safe_get(d: Any, key: str, default: Any = None) -> Any:
        """Safely get from dict or return default."""
        if isinstance(d, dict):
            return d.get(key, default)
        return default

    def _parse_enum(value: Any, enum_class: type, default: Any) -> Any:
        """Parse enum from string value."""
        if value is None:
            return default
        if isinstance(value, enum_class):
            return value
        if isinstance(value, str):
            for member in enum_class:
                if member.value == value or member.name == value:
                    return member
        return default

    try:
        # Reconstruct PersonalNode
        personal_data = _safe_get(data, "personal", {}) or {}
        location_data = _safe_get(personal_data, "location", {}) or {}
        occupation_data = _safe_get(personal_data, "occupation", {}) or {}
        occasions_data = _safe_get(personal_data, "occasions", []) or []

        location = Location(
            city=_safe_get(location_data, "city", ""),
            region=_safe_get(location_data, "region", ""),
            urban_suburban_rural=_safe_get(location_data, "urban_suburban_rural", "urban"),
            climate=_safe_get(location_data, "climate", ""),
        )

        occupation = Occupation(
            title=_safe_get(occupation_data, "title", ""),
            industry=_safe_get(occupation_data, "industry", ""),
            dress_code=_safe_get(occupation_data, "dress_code", "casual"),
            work_style_alignment=float(_safe_get(occupation_data, "work_style_alignment", 0.5) or 0.5),
        )

        occasions = []
        for occ in occasions_data:
            if isinstance(occ, dict):
                occasions.append(Occasion(
                    name=_safe_get(occ, "name", ""),
                    frequency=_safe_get(occ, "frequency", ""),
                    importance=float(_safe_get(occ, "importance", 0.5) or 0.5),
                    style_context=_parse_enum(
                        _safe_get(occ, "style_context"),
                        StyleContext,
                        StyleContext.CASUAL
                    ),
                ))

        personal = PersonalNode(
            age=int(_safe_get(personal_data, "age", 30) or 30),
            life_stage=_safe_get(personal_data, "life_stage", ""),
            location=location,
            occupation=occupation,
            occasions=occasions,
            gender_identity=_safe_get(personal_data, "gender_identity", ""),
        )

        # Reconstruct TasteNode
        taste_data = _safe_get(data, "taste", {}) or {}
        brand_prefs_data = _safe_get(taste_data, "brand_preferences", []) or []
        gender_exp_data = _safe_get(taste_data, "gender_expression", {}) or {}

        brand_preferences = []
        for bp in brand_prefs_data:
            if isinstance(bp, dict):
                brand_preferences.append(BrandPreference(
                    brand=_safe_get(bp, "brand", ""),
                    why_love_it=_safe_get(bp, "why_love_it", ""),
                    frequency=_safe_get(bp, "frequency", ""),
                ))

        gender_expression = GenderExpression(
            spectrum_position=_safe_get(gender_exp_data, "spectrum_position", ""),
            fluidity=float(_safe_get(gender_exp_data, "fluidity", 0.5) or 0.5),
            fit_preferences=_safe_get(gender_exp_data, "fit_preferences", []) or [],
        )

        # Reconstruct occasion_styles
        occasion_styles_data = _safe_get(taste_data, "occasion_styles", {}) or {}
        occasion_styles = {}
        for occ_name, occ_style in occasion_styles_data.items():
            if isinstance(occ_style, dict):
                occasion_styles[occ_name] = OccasionStyle(
                    description=_safe_get(occ_style, "description", ""),
                    consistency_with_other_contexts=float(
                        _safe_get(occ_style, "consistency_with_other_contexts", 0.5) or 0.5
                    ),
                )

        taste = TasteNode(
            gender_expression=gender_expression,
            brand_preferences=brand_preferences,
            shape_preferences=_safe_get(taste_data, "shape_preferences", []) or [],
            fit_preferences=_safe_get(taste_data, "fit_preferences", []) or [],
            style_loves=_safe_get(taste_data, "style_loves", ""),
            style_wants=_safe_get(taste_data, "style_wants", ""),
            style_avoids=_safe_get(taste_data, "style_avoids", ""),
            occasion_styles=occasion_styles,
            style_icons=_safe_get(taste_data, "style_icons", []) or [],
        )

        # Reconstruct ProcessNode
        process_data = _safe_get(data, "process", {}) or {}
        validation_data = _safe_get(process_data, "validation_sources", []) or []
        motivation_data = _safe_get(process_data, "style_motivations", []) or []
        social_data = _safe_get(process_data, "social_influences", {}) or {}

        validation_sources = []
        for vs in validation_data:
            if isinstance(vs, dict):
                source_val = _safe_get(vs, "source", "self")
                source_enum = _parse_enum(source_val, ValidationSource, ValidationSource.SELF)
                validation_sources.append(ValidationPreference(
                    source=source_enum,
                    importance=float(_safe_get(vs, "importance", 0.5) or 0.5),
                ))

        style_motivations = []
        for sm in motivation_data:
            if isinstance(sm, dict):
                style_motivations.append(StyleMotivation(
                    motivation=_safe_get(sm, "motivation", ""),
                    importance=float(_safe_get(sm, "importance", 0.5) or 0.5),
                    root_value=_safe_get(sm, "root_value", ""),
                ))

        exploration_pref = _parse_enum(
            _safe_get(process_data, "exploration_preference"),
            ExplorationPreference,
            ExplorationPreference.CURATED_OPTIONS
        )

        social_influences = SocialInfluences(
            primary_sources=_safe_get(social_data, "primary_sources", []) or [],
            trend_relationship=_safe_get(social_data, "trend_relationship", "follower"),
            originality_importance=float(_safe_get(social_data, "originality_importance", 0.5) or 0.5),
        )

        process = ProcessNode(
            style_motivations=style_motivations,
            creative_control=int(_safe_get(process_data, "creative_control", 5) or 5),
            style_goals=_safe_get(process_data, "style_goals", ""),
            brand_loyalty=int(_safe_get(process_data, "brand_loyalty", 5) or 5),
            adventurousness=int(_safe_get(process_data, "adventurousness", 5) or 5),
            validation_sources=validation_sources,
            exploration_preference=exploration_pref,
            social_influences=social_influences,
        )

        # Reconstruct PracticalityNode
        practicality_data = _safe_get(data, "practicality", {}) or {}
        budget_data = _safe_get(practicality_data, "budget", {}) or {}
        category_budgets_data = _safe_get(practicality_data, "category_budgets", {}) or {}

        budget = Budget(
            monthly=int(_safe_get(budget_data, "monthly", 200) or 200),
            yearly=int(_safe_get(budget_data, "yearly", 2400) or 2400),
            flexibility=_safe_get(budget_data, "flexibility", "guideline"),
            investment_mindset=_safe_get(budget_data, "investment_mindset", "balanced"),
        )

        category_budgets = {}
        for cat, cb in category_budgets_data.items():
            if isinstance(cb, dict):
                category_budgets[cat] = CategoryBudget(
                    budget_level=_safe_get(cb, "budget_level", "moderate"),
                    reasoning=_safe_get(cb, "reasoning", ""),
                )

        practicality = PracticalityNode(
            budget=budget,
            category_budgets=category_budgets,
        )

        # Reconstruct BodyNode
        body_data = _safe_get(data, "body", {}) or {}
        coloring_data = _safe_get(body_data, "coloring", {}) or {}

        coloring = Coloring(
            skin_tone=_safe_get(coloring_data, "skin_tone", ""),
            undertone=_safe_get(coloring_data, "undertone", ""),
            hair_color=_safe_get(coloring_data, "hair_color", ""),
            eye_color=_safe_get(coloring_data, "eye_color", ""),
        )

        body = BodyNode(
            face_photo_id=_safe_get(body_data, "face_photo_id"),
            body_photo_id=_safe_get(body_data, "body_photo_id"),
            coloring=coloring,
            body_verbal=_safe_get(body_data, "body_verbal"),
            favorite_features=_safe_get(body_data, "favorite_features", []) or [],
        )

        # Reconstruct ExternalNode
        external_data = _safe_get(data, "external", {}) or {}

        def _parse_social_connection(conn_data: Any) -> Optional[SocialMediaConnection]:
            """Parse a social media connection from dict or string."""
            if conn_data is None:
                return None
            if isinstance(conn_data, dict):
                return SocialMediaConnection(
                    handle=_safe_get(conn_data, "handle", ""),
                    connected=bool(_safe_get(conn_data, "connected", False)),
                    last_synced=None,  # Don't parse datetime for simplicity
                )
            if isinstance(conn_data, str):
                return SocialMediaConnection(handle=conn_data, connected=True, last_synced=None)
            return None

        external = ExternalNode(
            instagram=_parse_social_connection(_safe_get(external_data, "instagram")),
            pinterest=_parse_social_connection(_safe_get(external_data, "pinterest")),
            tiktok=_parse_social_connection(_safe_get(external_data, "tiktok")),
        )

        # Reconstruct RootValues
        root_values_data = _safe_get(data, "root_values", {}) or {}

        root_values = RootValues(
            primary=_safe_get(root_values_data, "primary", ""),
            secondary=_safe_get(root_values_data, "secondary", []) or [],
            authenticity_importance=float(_safe_get(root_values_data, "authenticity_importance", 0.5) or 0.5),
            belonging_importance=float(_safe_get(root_values_data, "belonging_importance", 0.5) or 0.5),
            standing_out_importance=float(_safe_get(root_values_data, "standing_out_importance", 0.5) or 0.5),
            comfort_importance=float(_safe_get(root_values_data, "comfort_importance", 0.5) or 0.5),
            competence_importance=float(_safe_get(root_values_data, "competence_importance", 0.5) or 0.5),
            value_tensions=_safe_get(root_values_data, "value_tensions", []) or [],
        )

        # Parse metadata
        created_at_str = _safe_get(data, "created_at")
        if created_at_str and isinstance(created_at_str, str):
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except ValueError:
                created_at = datetime.now()
        else:
            created_at = datetime.now()

        reinterpreted_at = None
        reinterpreted_at_str = _safe_get(data, "reinterpreted_at")
        if reinterpreted_at_str and isinstance(reinterpreted_at_str, str):
            try:
                reinterpreted_at = datetime.fromisoformat(reinterpreted_at_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return OnboardingProfile(
            personal=personal,
            taste=taste,
            process=process,
            practicality=practicality,
            body=body,
            external=external,
            root_values=root_values,
            created_at=created_at,
            reinterpreted_at=reinterpreted_at,
            reinterpretation_count=int(_safe_get(data, "reinterpretation_count", 0) or 0),
        )

    except Exception as e:
        print(f"Error deserializing OnboardingProfile: {e}")
        import traceback
        traceback.print_exc()
        return None
