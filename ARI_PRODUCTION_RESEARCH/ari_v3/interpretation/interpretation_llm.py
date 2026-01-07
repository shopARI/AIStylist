"""
ARI V3 Interpretation LLM (LLM #2)

Converts raw onboarding data to V3 OnboardingProfile structure.
This is "LLM #2" from the V3 specification.

Key responsibilities:
- Convert extracted JSON to V3 OnboardingProfile dataclass
- Extract root values from conversations (deeper psychological inference)
- Support re-interpretation when behavior diverges from stated preferences

Date: January 2026
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ari_v3.core import (
    # Enums
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
    # Structures
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
    # Navigation
    NavigationParameters,
    derive_navigation_parameters,
)

logger = logging.getLogger("ari_v3.interpretation")


# =============================================================================
# CONVERSION FUNCTIONS - JSON to V3 Dataclasses
# =============================================================================

def convert_extracted_to_v3_profile(
    extracted_data: Dict[str, Any],
    root_values_data: Optional[Dict[str, List[str]]] = None
) -> OnboardingProfile:
    """
    Convert extracted JSON data from OnboardingCrewV2 to V3 OnboardingProfile.

    This is the primary conversion function that maps the existing extraction
    format to the V3 dataclass structure.

    Args:
        extracted_data: Output from OnboardingCrewV2.get_all_extracted_data()
            Format: {
                "nodes": {node_id: {field: value}},
                "root_values": {node_id: [values]},
                "photos": {"face": url, "body": url},
                "social_media": {"instagram": handle, ...},
                "metadata": {...}
            }
        root_values_data: Optional override for root values

    Returns:
        V3 OnboardingProfile dataclass
    """
    nodes = extracted_data.get("nodes", {})
    root_values_by_node = root_values_data or extracted_data.get("root_values", {})
    photos = extracted_data.get("photos", {})
    social_media = extracted_data.get("social_media", {})

    # Build each node
    personal = _build_personal_node(nodes.get("personal", {}))
    taste = _build_taste_node(nodes.get("taste", {}))
    process = _build_process_node(nodes.get("process", {}))
    practicality = _build_practicality_node(nodes.get("practicality", {}))
    body = _build_body_node(nodes.get("body", {}), photos)
    external = _build_external_node(nodes.get("external", {}), social_media)
    root_values = _build_root_values(root_values_by_node, nodes)

    return OnboardingProfile(
        personal=personal,
        taste=taste,
        process=process,
        practicality=practicality,
        body=body,
        external=external,
        root_values=root_values,
        created_at=datetime.now(),
    )


def _safe_int(value: Any, default: int, min_val: int = None, max_val: int = None) -> int:
    """Safely convert value to int with optional bounds."""
    try:
        result = int(value) if value is not None else default
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)
        return result
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float, min_val: float = None, max_val: float = None) -> float:
    """Safely convert value to float with optional bounds."""
    try:
        result = float(value) if value is not None else default
        if min_val is not None:
            result = max(min_val, result)
        if max_val is not None:
            result = min(max_val, result)
        return result
    except (ValueError, TypeError):
        return default


def _build_personal_node(data: Dict[str, Any]) -> PersonalNode:
    """Build PersonalNode from extracted personal data."""
    # Location
    location_data = data.get("location") or {}
    if isinstance(location_data, str):
        location_data = {"city": location_data, "region": "", "urban_suburban_rural": "urban"}
    elif not isinstance(location_data, dict):
        location_data = {}

    location = Location(
        city=location_data.get("city", "Unknown"),
        region=location_data.get("region", ""),
        urban_suburban_rural=_parse_enum(
            location_data.get("urban_suburban_rural", "urban"),
            UrbanType,
            UrbanType.URBAN
        ),
        climate=location_data.get("climate"),
    )

    # Occupation
    occupation_data = data.get("occupation", {})
    if isinstance(occupation_data, str):
        occupation_data = {"title": occupation_data, "industry": "", "dress_code": "casual"}

    occupation = Occupation(
        title=occupation_data.get("title", ""),
        industry=occupation_data.get("industry", ""),
        dress_code=_parse_enum(
            occupation_data.get("dress_code", "casual"),
            DressCode,
            DressCode.CASUAL
        ),
        work_style_alignment=_safe_float(occupation_data.get("work_style_alignment"), 0.5, 0.0, 1.0),
    )

    # Occasions
    occasions_data = data.get("occasions", [])
    occasions = []
    for occ in occasions_data:
        if isinstance(occ, str):
            occ = {"name": occ, "frequency": "weekly", "importance": 0.5}
        occasions.append(Occasion(
            name=occ.get("name", ""),
            frequency=_parse_enum(
                occ.get("frequency", "weekly"),
                OccasionFrequency,
                OccasionFrequency.WEEKLY
            ),
            importance=_safe_float(occ.get("importance"), 0.5, 0.0, 1.0),
            style_context=_map_occasion_to_context(occ.get("name", "")),
        ))

    # Parental status
    parental_data = data.get("parental_status", {})
    parental_status = None
    if parental_data:
        parental_status = ParentalStatus(
            has_kids=parental_data.get("has_kids", False),
            kid_ages=parental_data.get("kid_ages", []),
            parenting_style_impact=parental_data.get("parenting_style_impact"),
        )

    return PersonalNode(
        age=_safe_int(data.get("age"), 30, 13, 120),
        life_stage=data.get("life_stage", "established"),
        location=location,
        occupation=occupation,
        occasions=occasions,
        gender_identity=data.get("gender_identity", ""),
        ethnicity=data.get("ethnicity"),
        cultural_background=data.get("cultural_background"),
        relationship_status=data.get("relationship_status"),
        parental_status=parental_status,
    )


def _build_taste_node(data: Dict[str, Any]) -> TasteNode:
    """Build TasteNode from extracted taste data."""
    # Gender expression
    gender_expr_data = data.get("gender_expression", {})
    if isinstance(gender_expr_data, (int, float)):
        # Handle spectrum value
        gender_expr_data = {
            "spectrum_position": f"spectrum_{gender_expr_data}",
            "fluidity": 0.3,
            "fit_preferences": []
        }

    gender_expression = GenderExpression(
        spectrum_position=str(gender_expr_data.get("spectrum_position", "balanced")),
        fluidity=_safe_float(gender_expr_data.get("fluidity"), 0.3, 0.0, 1.0),
        fit_preferences=gender_expr_data.get("fit_preferences", []),
    )

    # Brand preferences
    brand_prefs_data = data.get("brand_preferences", [])
    brand_preferences = []
    for bp in brand_prefs_data:
        if isinstance(bp, str):
            bp = {"brand": bp, "why_love_it": "", "frequency": "sometimes"}
        brand_preferences.append(BrandPreference(
            brand=bp.get("brand", ""),
            why_love_it=bp.get("why_love_it", ""),
            frequency=_parse_enum(
                bp.get("frequency", "sometimes"),
                BrandFrequency,
                BrandFrequency.SOMETIMES
            ),
        ))

    # Occasion styles
    occasion_styles_data = data.get("occasion_styles", {})
    occasion_styles = {}
    for occ_name, style_data in occasion_styles_data.items():
        if isinstance(style_data, str):
            style_data = {"description": style_data, "consistency_with_other_contexts": 0.7}
        occasion_styles[occ_name] = OccasionStyle(
            description=style_data.get("description", ""),
            consistency_with_other_contexts=_safe_float(style_data.get("consistency_with_other_contexts"), 0.7, 0.0, 1.0),
        )

    return TasteNode(
        gender_expression=gender_expression,
        brand_preferences=brand_preferences,
        shape_preferences=data.get("shape_preferences", []),
        fit_preferences=data.get("fit_preferences", []),
        style_loves=data.get("style_loves", ""),
        style_wants=data.get("style_wants", ""),
        style_avoids=data.get("style_avoids", ""),
        occasion_styles=occasion_styles,
        style_icons=data.get("style_icons", []),
    )


def _build_process_node(data: Dict[str, Any]) -> ProcessNode:
    """Build ProcessNode from extracted process data."""
    # Style motivations
    motivations_data = data.get("style_motivations", [])
    style_motivations = []
    for mot in motivations_data:
        if isinstance(mot, str):
            mot = {"motivation": mot, "importance": 0.5, "root_value": ""}
        style_motivations.append(StyleMotivation(
            motivation=mot.get("motivation", ""),
            importance=_safe_float(mot.get("importance"), 0.5, 0.0, 1.0),
            root_value=mot.get("root_value", ""),
        ))

    # Validation sources
    validation_data = data.get("validation_sources", [])
    validation_sources = []
    for vs in validation_data:
        if isinstance(vs, str):
            vs = {"source": vs, "importance": 0.5}
        validation_sources.append(ValidationPreference(
            source=_parse_enum(
                vs.get("source", "self"),
                ValidationSource,
                ValidationSource.SELF
            ),
            importance=_safe_float(vs.get("importance"), 0.5, 0.0, 1.0),
        ))

    # Default validation source if none provided
    if not validation_sources:
        validation_sources = [ValidationPreference(source=ValidationSource.SELF, importance=0.8)]

    # Social influences
    social_data = data.get("social_influences", {})
    social_influences = SocialInfluences(
        primary_sources=social_data.get("primary_sources", []),
        trend_relationship=social_data.get("trend_relationship", "follower"),
        originality_importance=_safe_float(social_data.get("originality_importance"), 0.5, 0.0, 1.0),
    )

    # Exploration preference
    exploration_pref = data.get("exploration_preference", "curated_options")
    if isinstance(exploration_pref, str):
        exploration_pref = _parse_enum(
            exploration_pref,
            ExplorationPreference,
            ExplorationPreference.CURATED_OPTIONS
        )

    return ProcessNode(
        style_motivations=style_motivations,
        creative_control=_safe_int(data.get("creative_control"), 5, 1, 10),
        style_goals=data.get("style_goals", ""),
        brand_loyalty=_safe_int(data.get("brand_loyalty"), 5, 1, 10),
        adventurousness=_safe_int(data.get("adventurousness"), 5, 1, 10),
        validation_sources=validation_sources,
        exploration_preference=exploration_pref,
        social_influences=social_influences,
    )


def _build_practicality_node(data: Dict[str, Any]) -> PracticalityNode:
    """Build PracticalityNode from extracted practicality data."""
    # Budget
    budget_data = data.get("budget", {})
    if isinstance(budget_data, (int, float)):
        monthly_val = float(budget_data)
        budget_data = {"monthly": monthly_val, "yearly": monthly_val * 12}
    elif not isinstance(budget_data, dict):
        budget_data = {}

    monthly = _safe_float(budget_data.get("monthly"), 500, 0)
    budget = Budget(
        monthly=monthly,
        yearly=_safe_float(budget_data.get("yearly"), monthly * 12, 0),
        flexibility=_parse_enum(
            budget_data.get("flexibility", "guideline"),
            BudgetFlexibility,
            BudgetFlexibility.GUIDELINE
        ),
        investment_mindset=budget_data.get("investment_mindset", "balanced"),
    )

    # Category budgets
    category_budgets_data = data.get("category_budgets", {})
    category_budgets = {}
    for cat, cb_data in category_budgets_data.items():
        if isinstance(cb_data, str):
            cb_data = {"budget_level": cb_data, "reasoning": ""}
        category_budgets[cat] = CategoryBudget(
            budget_level=_parse_enum(
                cb_data.get("budget_level", "moderate"),
                BudgetLevel,
                BudgetLevel.MODERATE
            ),
            reasoning=cb_data.get("reasoning", ""),
        )

    return PracticalityNode(
        budget=budget,
        category_budgets=category_budgets,
    )


def _build_body_node(data: Dict[str, Any], photos: Dict[str, Any]) -> BodyNode:
    """Build BodyNode from extracted body data and photos."""
    # Coloring
    coloring_data = data.get("coloring", {})
    coloring = None
    if coloring_data:
        coloring = Coloring(
            skin_tone=coloring_data.get("skin_tone", ""),
            undertone=_parse_enum(
                coloring_data.get("undertone", "neutral"),
                Undertone,
                Undertone.NEUTRAL
            ),
            hair_color=coloring_data.get("hair_color", ""),
            eye_color=coloring_data.get("eye_color", ""),
            seasonal_palette=coloring_data.get("seasonal_palette"),
        )

    return BodyNode(
        face_photo_id=photos.get("face"),
        body_photo_id=photos.get("body"),
        coloring=coloring,
        body_verbal=data.get("body_verbal"),
        favorite_features=data.get("favorite_features", []),
    )


def _build_external_node(data: Dict[str, Any], social_media: Dict[str, Any]) -> ExternalNode:
    """Build ExternalNode from extracted external data and social media."""
    def build_connection(handle: Optional[str]) -> Optional[SocialMediaConnection]:
        if not handle:
            return None
        return SocialMediaConnection(
            handle=handle,
            connected=True,
            last_synced=None,
            boards_analyzed=[],
        )

    return ExternalNode(
        instagram=build_connection(social_media.get("instagram")),
        pinterest=build_connection(social_media.get("pinterest")),
        tiktok=build_connection(social_media.get("tiktok")),
    )


def _build_root_values(
    root_values_by_node: Dict[str, List[str]],
    nodes: Dict[str, Any]
) -> RootValues:
    """Build RootValues from extracted root values across nodes."""
    # Collect all root values
    all_values = []
    for node_id, values in root_values_by_node.items():
        all_values.extend(values)

    # Remove duplicates while preserving order
    seen = set()
    unique_values = []
    for v in all_values:
        if v.lower() not in seen:
            seen.add(v.lower())
            unique_values.append(v)

    # Primary is first (most mentioned), secondary is rest
    primary = unique_values[0] if unique_values else "authenticity"
    secondary = unique_values[1:5] if len(unique_values) > 1 else []

    # Infer value dimensions from extracted data
    process_data = nodes.get("process", {})

    # Authenticity: high creative_control suggests authenticity importance
    creative_control = _safe_int(process_data.get("creative_control"), 5, 1, 10)
    authenticity = creative_control / 10.0

    # Belonging vs standing out
    adventurousness = _safe_int(process_data.get("adventurousness"), 5, 1, 10)
    standing_out = adventurousness / 10.0
    belonging = 1.0 - standing_out

    # Comfort
    comfort = 0.5  # Default, would need more data

    # Competence
    competence = 0.5  # Default, would need more data

    return RootValues(
        primary=primary,
        secondary=secondary,
        authenticity_importance=authenticity,
        belonging_importance=belonging,
        standing_out_importance=standing_out,
        comfort_importance=comfort,
        competence_importance=competence,
        value_tensions=[],
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_enum(value: Any, enum_class, default):
    """Safely parse a string value to an enum."""
    if isinstance(value, enum_class):
        return value
    if isinstance(value, str):
        try:
            return enum_class(value.lower().replace(" ", "_"))
        except ValueError:
            # Try matching by name
            for member in enum_class:
                if member.name.lower() == value.lower().replace(" ", "_"):
                    return member
    return default


def _map_occasion_to_context(occasion_name: str) -> StyleContext:
    """Map occasion name to StyleContext enum."""
    occasion_lower = occasion_name.lower()

    if any(word in occasion_lower for word in ["work", "office", "meeting", "interview", "professional"]):
        return StyleContext.PROFESSIONAL
    elif any(word in occasion_lower for word in ["party", "date", "dinner", "night out", "evening"]):
        return StyleContext.EVENING
    elif any(word in occasion_lower for word in ["wedding", "gala", "formal", "ceremony"]):
        return StyleContext.FORMAL
    elif any(word in occasion_lower for word in ["gym", "workout", "sport", "active", "hiking"]):
        return StyleContext.ACTIVE
    elif any(word in occasion_lower for word in ["art", "creative", "gallery", "concert"]):
        return StyleContext.CREATIVE
    elif any(word in occasion_lower for word in ["travel", "vacation", "trip"]):
        return StyleContext.TRAVEL
    elif any(word in occasion_lower for word in ["casual", "weekend", "everyday", "relaxed"]):
        return StyleContext.CASUAL
    else:
        return StyleContext.DEFAULT


# =============================================================================
# ROOT VALUE EXTRACTION (LLM-based)
# =============================================================================

async def extract_root_values(
    conversations: List[Dict[str, Any]],
    existing_values: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Use LLM to extract deeper root values from onboarding conversations.

    This goes beyond surface-level preferences to understand:
    - Why they care about certain styles
    - What fashion means to them emotionally
    - Core values driving their choices

    Args:
        conversations: List of conversation histories from each node
        existing_values: Already detected values to build upon

    Returns:
        Dict with extracted root values and confidence scores
    """
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Format conversations for analysis
        conversation_text = ""
        for conv in conversations:
            node = conv.get("node", "unknown")
            messages = conv.get("messages", [])
            conversation_text += f"\n--- {node.upper()} ---\n"
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                conversation_text += f"{role}: {content}\n"

        prompt = f"""Analyze this onboarding conversation and extract the user's deep root values.

Look beyond surface preferences to understand:
1. What does fashion/style mean to them emotionally?
2. What core human needs are they trying to fulfill through their style choices?
3. What tensions exist between different values?

Common root values in fashion:
- Authenticity (being true to self)
- Belonging (fitting in with community)
- Standing out (being noticed/unique)
- Comfort (physical and psychological)
- Competence (looking capable/professional)
- Self-expression (showing identity)
- Control (mastery over appearance)
- Connection (relating to others)

CONVERSATION:
{conversation_text}

ALREADY DETECTED VALUES: {existing_values or []}

Return JSON:
{{
    "primary_value": "the single most important value",
    "secondary_values": ["list", "of", "supporting", "values"],
    "value_tensions": ["where values conflict, e.g., 'wants to stand out but fears judgment'"],
    "evidence": {{
        "primary_value": "quote or observation supporting this",
        "secondary_values": ["evidence for each"]
    }},
    "confidence": 0.0-1.0
}}
"""

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a fashion psychologist analyzing user motivations. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"Extracted root values: {result.get('primary_value')}")
        return result

    except Exception as e:
        logger.error(f"Root value extraction failed: {e}")
        return {
            "primary_value": "authenticity",
            "secondary_values": [],
            "value_tensions": [],
            "evidence": {},
            "confidence": 0.3
        }


# =============================================================================
# MAIN INTERPRETATION FUNCTION
# =============================================================================

def interpret_onboarding(extracted_data: Dict[str, Any]) -> tuple[OnboardingProfile, NavigationParameters]:
    """
    Main interpretation function - converts extracted data to V3 structures.

    This is the primary entry point for Step 2 integration.

    Args:
        extracted_data: Output from OnboardingCrewV2.get_all_extracted_data()

    Returns:
        Tuple of (OnboardingProfile, NavigationParameters)
    """
    # Convert to V3 profile
    profile = convert_extracted_to_v3_profile(extracted_data)

    # Derive navigation parameters deterministically
    nav_params = derive_navigation_parameters(profile)

    logger.info(f"Interpreted onboarding: exploration_appetite={nav_params.exploration_appetite:.2f}")

    return profile, nav_params


# =============================================================================
# INTERPRETER CLASS (for advanced usage)
# =============================================================================

class OnboardingInterpreter:
    """
    Advanced interpreter with re-interpretation support.

    Use this class when you need:
    - Re-interpretation based on behavioral drift
    - Incremental updates to profile
    - Access to interpretation history
    """

    def __init__(self):
        """Initialize interpreter."""
        self.interpretation_history: List[Dict[str, Any]] = []

    def interpret(
        self,
        extracted_data: Dict[str, Any],
        behavioral_summary: Optional[Dict[str, Any]] = None
    ) -> tuple[OnboardingProfile, NavigationParameters]:
        """
        Interpret onboarding data, optionally incorporating behavioral summary.

        Args:
            extracted_data: From OnboardingCrewV2
            behavioral_summary: Optional observed behavior data for re-interpretation

        Returns:
            Tuple of (OnboardingProfile, NavigationParameters)
        """
        profile, nav_params = interpret_onboarding(extracted_data)

        # Record interpretation
        self.interpretation_history.append({
            "timestamp": datetime.now().isoformat(),
            "profile_created_at": profile.created_at.isoformat(),
            "nav_params_summary": {
                "exploration_appetite": nav_params.exploration_appetite,
                "step_size_multiplier": nav_params.step_size_multiplier,
                "brand_affinity_weight": nav_params.brand_affinity_weight,
            },
            "had_behavioral_summary": behavioral_summary is not None,
        })

        return profile, nav_params

    async def reinterpret(
        self,
        original_profile: OnboardingProfile,
        raw_conversations: List[Dict[str, Any]],
        behavioral_summary: Dict[str, Any]
    ) -> tuple[OnboardingProfile, NavigationParameters]:
        """
        Re-interpret profile based on behavioral drift.

        Called when user behavior significantly diverges from stated preferences.

        Args:
            original_profile: The original OnboardingProfile
            raw_conversations: Original conversation histories
            behavioral_summary: Observed behavior data

        Returns:
            Updated (OnboardingProfile, NavigationParameters)
        """
        # Extract deeper root values with behavioral context
        root_values_result = await extract_root_values(
            raw_conversations,
            existing_values=[original_profile.root_values.primary] + original_profile.root_values.secondary
        )

        # For now, return original with updated reinterpretation metadata
        # Full re-interpretation would modify process node values based on behavior
        updated_profile = OnboardingProfile(
            personal=original_profile.personal,
            taste=original_profile.taste,
            process=original_profile.process,
            practicality=original_profile.practicality,
            body=original_profile.body,
            external=original_profile.external,
            root_values=RootValues(
                primary=root_values_result.get("primary_value", original_profile.root_values.primary),
                secondary=root_values_result.get("secondary_values", original_profile.root_values.secondary),
                authenticity_importance=original_profile.root_values.authenticity_importance,
                belonging_importance=original_profile.root_values.belonging_importance,
                standing_out_importance=original_profile.root_values.standing_out_importance,
                comfort_importance=original_profile.root_values.comfort_importance,
                competence_importance=original_profile.root_values.competence_importance,
                value_tensions=root_values_result.get("value_tensions", []),
            ),
            created_at=original_profile.created_at,
            reinterpreted_at=datetime.now(),
            reinterpretation_count=original_profile.reinterpretation_count + 1,
        )

        nav_params = derive_navigation_parameters(updated_profile)

        logger.info(f"Re-interpreted profile (count: {updated_profile.reinterpretation_count})")

        return updated_profile, nav_params
