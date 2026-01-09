"""
ARI V3 Pillar 1: Personalization Engine

Provides user state computation from Neo4j data.
This module loads raw user data and computes the query-time user state
including per-context positions, trajectories, and unified embeddings.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 2.1
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np

from ari_v3.core.data_structures import (
    StyleContext,
    OnboardingProfile,
    NavigationParameters,
    RawUserData,
    RawOnboardingConversation,
    ComputedUserState,
    ContextualPosition,
    StyleCoordinate,
    Trajectory,
    UserEmbeddings,
    UniversalPreferences,
    SpendingPatterns,
    BehavioralPatterns,
    Interaction,
    InteractionType,
    SocialTasteEmbeddings,
    ConversationHistory,
    zero_vector,
    normalize_vector,
)
from ari_v3.core.serialization import (
    deserialize_to_onboarding_profile,
    deserialize_to_navigation_params,
)


# Minimum interactions needed per context before computing position
MIN_INTERACTIONS_FOR_POSITION = 5

# Minimum interactions needed before computing trajectory
MIN_INTERACTIONS_FOR_TRAJECTORY = 10

# Days to consider as "recent" for trajectory computation
RECENT_DAYS = 30

# Confidence scaling factor (interactions / this = confidence, capped at 1.0)
CONFIDENCE_SCALE = 30


@dataclass
class QueryContext:
    """Context for the current query/request."""
    occasion: Optional[str] = None
    explicit_context: Optional[StyleContext] = None
    query_text: Optional[str] = None
    session_id: Optional[str] = None


class Pillar1_Personalization:
    """
    V3 Personalization Engine.

    Loads raw user data from Neo4j and computes query-time user state
    including per-context positions, trajectories, and unified embeddings.
    """

    def __init__(self, neo4j_driver=None, embedding_service=None):
        """
        Initialize the personalization engine.

        Args:
            neo4j_driver: Neo4j driver instance (optional, for testing)
            embedding_service: Service for computing embeddings (optional)
        """
        self.neo4j_driver = neo4j_driver
        self.embedding_service = embedding_service

    def load_raw_user_data(self, user_id: str) -> Optional[RawUserData]:
        """
        Load complete user data from Neo4j.

        Args:
            user_id: The user's unique identifier

        Returns:
            RawUserData containing all user information, or None if not found
        """
        if not self.neo4j_driver:
            return None

        query = """
            MATCH (u:User {id: $user_id})

            // Get onboarding data
            OPTIONAL MATCH (u)-[:HAS_ONBOARDING]->(ob:OnboardingProfile)

            // Get body data
            OPTIONAL MATCH (u)-[:HAS_BODY_DATA]->(bd:BodyData)

            // Get social embeddings
            OPTIONAL MATCH (u)-[:HAS_SOCIAL_TASTE]->(st:SocialTasteEmbeddings)

            // Get navigation parameters
            OPTIONAL MATCH (u)-[:HAS_NAV_PARAMS]->(np:NavigationParameters)

            // Get interactions (products connected to user)
            OPTIONAL MATCH (u)-[r:INTERACTED_WITH]->(p:Product)

            // Get conversations
            OPTIONAL MATCH (u)-[:HAD_CONVERSATION]->(c:Conversation)

            RETURN u, ob, bd, st, np,
                   collect(DISTINCT {
                       product_id: p.id,
                       type: r.type,
                       timestamp: r.timestamp,
                       context: r.context,
                       feedback: r.feedback
                   }) as interactions,
                   collect(DISTINCT c) as conversations
        """

        with self.neo4j_driver.session() as session:
            result = session.run(query, user_id=user_id)
            record = result.single()

            if not record or not record["u"]:
                return None

            user_node = record["u"]
            ob_node = record["ob"]
            bd_node = record["bd"]
            st_node = record["st"]
            np_node = record["np"]
            interactions_data = record["interactions"]
            conversations_data = record["conversations"]

            # Parse onboarding profile
            onboarding_profile = None
            raw_conversations = []
            if ob_node:
                ob_dict = dict(ob_node)
                onboarding_profile = deserialize_to_onboarding_profile(ob_dict)
                raw_convs = ob_dict.get("raw_conversations", [])
                for conv in raw_convs:
                    if isinstance(conv, dict):
                        raw_conversations.append(RawOnboardingConversation(
                            node=conv.get("node", ""),
                            messages=conv.get("messages", []),
                            timestamp=self._parse_datetime(conv.get("timestamp"))
                        ))

            # Parse navigation parameters
            nav_params = None
            if np_node:
                nav_params = deserialize_to_navigation_params(dict(np_node))

            # Parse body data
            body_type = None
            coloring = None
            body_photo_url = None
            face_photo_url = None
            if bd_node:
                bd_dict = dict(bd_node)
                body_type = bd_dict.get("body_verbal")
                coloring = bd_dict.get("coloring_verbal")
                body_photo_url = bd_dict.get("body_photo_url")
                face_photo_url = bd_dict.get("face_photo_url")

            # Parse social embeddings
            social_embeddings = self._parse_social_embeddings(st_node)

            # Parse interactions
            interactions = self._parse_interactions(interactions_data)

            # Parse conversation history
            conversation_history = self._parse_conversations(conversations_data)

            # Parse timestamps safely
            created_at = self._parse_datetime(user_node.get("created_at"))
            last_active = self._parse_datetime(user_node.get("last_active"))

            return RawUserData(
                user_id=user_id,
                onboarding_profile=onboarding_profile,
                raw_onboarding_conversations=raw_conversations,
                navigation_parameters=nav_params,
                body_type=body_type,
                coloring=coloring,
                body_photo_url=body_photo_url,
                face_photo_url=face_photo_url,
                social_embeddings=social_embeddings,
                interactions=interactions,
                conversation_history=conversation_history,
                created_at=created_at,
                last_active=last_active,
                onboarding_completed=onboarding_profile is not None,
                calibration_completed=bool(user_node.get("calibration_completed", False))
            )

    def compute_user_state(
        self,
        raw_data: RawUserData,
        query_context: QueryContext
    ) -> ComputedUserState:
        """
        Compute user state with per-context trajectories and social signals.

        This is the main computation that produces the full user state
        used for navigation.

        Args:
            raw_data: Complete user data from Neo4j
            query_context: Context for the current query

        Returns:
            ComputedUserState with all computed values
        """
        # Step 1: Detect style contexts from interactions
        detected_contexts = self._detect_user_contexts(raw_data.interactions)

        # Step 2: Compute position + trajectory for EACH context
        positions_by_context: Dict[StyleContext, ContextualPosition] = {}

        for context in detected_contexts:
            context_interactions = self._filter_interactions_by_context(
                raw_data.interactions,
                context
            )

            if len(context_interactions) >= MIN_INTERACTIONS_FOR_POSITION:
                position = self._compute_position_from_interactions(context_interactions)
                trajectory = self._compute_context_trajectory(context_interactions, context)
                embeddings = self._compute_user_embeddings(
                    raw_data,
                    context_interactions
                )

                last_interaction_time = max(
                    (i.timestamp for i in context_interactions),
                    default=datetime.now()
                )

                positions_by_context[context] = ContextualPosition(
                    context=context,
                    position=position,
                    trajectory=trajectory,
                    embeddings=embeddings,
                    interaction_count=len(context_interactions),
                    confidence=min(1.0, len(context_interactions) / CONFIDENCE_SCALE),
                    last_interaction=last_interaction_time
                )

        # Step 3: Select active context
        active_context = self._select_active_context(
            query_context,
            detected_contexts,
            raw_data.onboarding_profile
        )

        if active_context in positions_by_context:
            active_position = positions_by_context[active_context]
        else:
            # Cold start for this context - use onboarding + social
            active_position = self._compute_cold_start_position(raw_data, active_context)
            positions_by_context[active_context] = active_position

        # Step 4: Detect universal preferences
        universal_preferences = self._detect_universal_preferences(
            positions_by_context,
            raw_data.onboarding_profile
        )

        # Step 5: Compute unified embeddings (interactions + social)
        user_weight = 0.5
        if raw_data.navigation_parameters:
            user_weight = raw_data.navigation_parameters.user_embedding_weight

        unified_embeddings = self._compute_unified_embeddings(
            active_position.embeddings,
            raw_data.social_embeddings,
            user_weight
        )

        # Step 6: Compute patterns
        spending_patterns = self._analyze_spending_patterns(
            raw_data.interactions,
            raw_data.onboarding_profile
        )
        behavioral_patterns = self._detect_behavioral_patterns(raw_data.interactions)

        # Build default nav params if not present
        nav_params = raw_data.navigation_parameters
        if not nav_params:
            from ari_v3.core.data_structures import DefaultBudget
            nav_params = NavigationParameters(
                exploration_appetite=0.5,
                step_size_multiplier=1.0,
                brand_affinity_weight=0.5,
                result_set_size=10,
                diversity_requirement=0.5,
                user_embedding_weight=0.5,
                default_budget=DefaultBudget(min=50, max=250, flexibility=0.4),
                category_budget_overrides={}
            )

        return ComputedUserState(
            detected_contexts=detected_contexts,
            positions_by_context=positions_by_context,
            active_context=active_context,
            active_position=active_position,
            universal_preferences=universal_preferences,
            embeddings=unified_embeddings,
            social_embeddings=raw_data.social_embeddings,
            spending_patterns=spending_patterns,
            behavioral_patterns=behavioral_patterns,
            nav_params=nav_params
        )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_social_embeddings(self, st_node) -> Optional[SocialTasteEmbeddings]:
        """Parse social embeddings from Neo4j node."""
        if not st_node:
            return None

        try:
            st_dict = dict(st_node)

            unified_embedding = None
            if "unified_social_embedding" in st_dict and st_dict["unified_social_embedding"] is not None:
                unified_embedding = np.array(st_dict["unified_social_embedding"], dtype=np.float32)

            return SocialTasteEmbeddings(
                unified_social_embedding=unified_embedding
            )
        except (TypeError, ValueError):
            # Malformed data - return None
            return None

    def _parse_interactions(self, interactions_data: List[Dict]) -> List[Interaction]:
        """Parse interaction records from Neo4j."""
        from ari_v3.core.data_structures import InteractionContext, InteractionFeedback

        interactions = []
        for i_data in interactions_data:
            if not i_data.get("product_id"):
                continue

            # Parse interaction type
            i_type_raw = i_data.get("type", "viewed")
            i_type_str = str(i_type_raw).lower() if i_type_raw else "viewed"
            try:
                i_type = InteractionType(i_type_str)
            except ValueError:
                i_type = InteractionType.VIEWED

            # Parse timestamp
            timestamp = self._parse_datetime(i_data.get("timestamp"))

            # Parse context
            ctx_data = i_data.get("context", {}) or {}
            style_ctx_str = ctx_data.get("style_context") or "default"
            try:
                style_ctx = StyleContext(style_ctx_str)
            except (ValueError, TypeError):
                style_ctx = StyleContext.DEFAULT

            context = InteractionContext(
                occasion=ctx_data.get("occasion"),
                query=ctx_data.get("query"),
                session_id=ctx_data.get("session_id", ""),
                style_context=style_ctx
            )

            # Parse feedback
            fb_data = i_data.get("feedback", {}) or {}
            feedback = InteractionFeedback(
                explicit_rating=fb_data.get("explicit_rating"),
                time_spent_seconds=fb_data.get("time_spent_seconds", 0),
                returned_to_view=fb_data.get("returned_to_view", False)
            )

            interactions.append(Interaction(
                product_id=i_data["product_id"],
                type=i_type,
                timestamp=timestamp,
                context=context,
                feedback=feedback
            ))

        return interactions

    def _parse_conversations(self, conversations_data: List) -> List[ConversationHistory]:
        """Parse conversation records from Neo4j."""
        conversations = []
        for c_data in conversations_data:
            if not c_data:
                continue
            # Check for dict-like object (has items method) rather than just iterable
            c_dict = dict(c_data) if hasattr(c_data, 'items') or hasattr(c_data, 'keys') else {}

            timestamp = self._parse_datetime(c_dict.get("timestamp"))

            conversations.append(ConversationHistory(
                timestamp=timestamp,
                messages=c_dict.get("messages", []),
                session_context=c_dict.get("session_context", {}),
                products_discussed=c_dict.get("products_discussed", [])
            ))

        return conversations

    def _parse_datetime(self, value: Any) -> datetime:
        """
        Safely parse a datetime from various formats.

        Args:
            value: datetime, string, or None

        Returns:
            Parsed datetime or current time as fallback
        """
        if value is None:
            return datetime.now()
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                return datetime.now()
        return datetime.now()

    def _detect_user_contexts(self, interactions: List[Interaction]) -> List[StyleContext]:
        """
        Detect which style contexts the user has interactions in.

        Returns contexts sorted by interaction count (most active first).
        """
        context_counts: Dict[StyleContext, int] = {}

        for interaction in interactions:
            ctx = interaction.context.style_context
            context_counts[ctx] = context_counts.get(ctx, 0) + 1

        # Always include DEFAULT if no contexts detected
        if not context_counts:
            return [StyleContext.DEFAULT]

        # Sort by count descending
        sorted_contexts = sorted(
            context_counts.keys(),
            key=lambda c: context_counts[c],
            reverse=True
        )

        return sorted_contexts

    def _filter_interactions_by_context(
        self,
        interactions: List[Interaction],
        context: StyleContext
    ) -> List[Interaction]:
        """Filter interactions to those in a specific context."""
        return [i for i in interactions if i.context.style_context == context]

    def _compute_position_from_interactions(
        self,
        interactions: List[Interaction]
    ) -> StyleCoordinate:
        """
        Compute style position from a set of interactions.

        Weights positive interactions (liked, purchased) more than negative.
        """
        if not interactions:
            return StyleCoordinate(
                embedding=zero_vector(1536),
                visual_embedding=zero_vector(1024)
            )

        # For now, return a placeholder - actual implementation requires
        # loading product embeddings and computing weighted average
        # TODO: Integrate with product embedding lookup
        return StyleCoordinate(
            embedding=zero_vector(1536),
            visual_embedding=zero_vector(1024)
        )

    def _compute_context_trajectory(
        self,
        interactions: List[Interaction],
        context: StyleContext
    ) -> Trajectory:
        """
        Compute per-context trajectory showing style evolution.

        A user might evolve differently in different contexts.
        """
        now = datetime.now()

        if len(interactions) < MIN_INTERACTIONS_FOR_TRAJECTORY:
            return Trajectory(
                direction=zero_vector(1536),
                velocity=0.05,
                consistency=0.5,
                last_computed=now
            )

        # Split by time
        cutoff = now - timedelta(days=RECENT_DAYS)
        recent = [i for i in interactions if i.timestamp > cutoff]
        historical = [i for i in interactions if i.timestamp <= cutoff]

        if len(recent) < 5 or len(historical) < 5:
            return Trajectory(
                direction=zero_vector(1536),
                velocity=0.05,
                consistency=0.5,
                last_computed=now
            )

        # Compute embeddings for each period
        recent_embedding = self._compute_embedding_from_interactions(recent)
        historical_embedding = self._compute_embedding_from_interactions(historical)

        # Direction in embedding space
        direction = recent_embedding - historical_embedding
        magnitude = np.linalg.norm(direction)

        if magnitude > 0:
            direction = direction / magnitude

        # Velocity: rate of change per week
        velocity = min(1.0, magnitude / 4.0)

        # Consistency: how stable is the evolution direction
        consistency = self._compute_trajectory_consistency(interactions, direction)

        return Trajectory(
            direction=direction,
            velocity=velocity,
            consistency=consistency,
            last_computed=now
        )

    def _compute_embedding_from_interactions(
        self,
        interactions: List[Interaction]
    ) -> np.ndarray:
        """
        Compute embedding from a set of interactions.

        TODO: Integrate with product embedding service.
        """
        # Placeholder - actual implementation loads product embeddings
        return zero_vector(1536)

    def _compute_trajectory_consistency(
        self,
        interactions: List[Interaction],
        direction: np.ndarray
    ) -> float:
        """
        Compute how consistent the trajectory direction is over time.

        High consistency = stable evolution direction.
        Low consistency = erratic changes.
        """
        # Placeholder - compute variance of direction over time windows
        return 0.5

    def _compute_user_embeddings(
        self,
        raw_data: RawUserData,
        context_interactions: List[Interaction]
    ) -> UserEmbeddings:
        """
        Compute user embeddings from interactions.

        Note: Social signal blending is done separately in _compute_unified_embeddings
        which is called later in the compute_user_state flow.
        """
        # Separate by interaction type
        liked = [i for i in context_interactions if i.type == InteractionType.LIKED]
        purchased = [i for i in context_interactions if i.type == InteractionType.PURCHASED]

        liked_embedding = self._compute_embedding_from_interactions(liked)
        purchased_embedding = self._compute_embedding_from_interactions(purchased)

        # Unified: purchases weighted higher (always normalize for consistency)
        if len(purchased) > 0 and len(liked) > 0:
            unified = normalize_vector(0.7 * purchased_embedding + 0.3 * liked_embedding)
        elif len(purchased) > 0:
            unified = normalize_vector(purchased_embedding)
        elif len(liked) > 0:
            unified = normalize_vector(liked_embedding)
        else:
            unified = zero_vector(1536)

        # Confidence based on data volume
        total = len(context_interactions)
        confidence = min(1.0, total / CONFIDENCE_SCALE)

        return UserEmbeddings(
            liked_embedding=liked_embedding,
            purchased_embedding=purchased_embedding,
            unified_embedding=unified,
            confidence=confidence
        )

    def _select_active_context(
        self,
        query_context: QueryContext,
        detected_contexts: List[StyleContext],
        onboarding_profile: Optional[OnboardingProfile]
    ) -> StyleContext:
        """
        Select the active context for the current query.

        Priority:
        1. Explicit context in query
        2. Occasion mapping from query
        3. Occasion mapping from onboarding
        4. Most frequent context
        5. DEFAULT
        """
        # Explicit context always wins
        if query_context.explicit_context:
            return query_context.explicit_context

        # Try to map occasion to context
        if query_context.occasion:
            mapped = self._map_occasion_to_context(query_context.occasion)
            if mapped:
                return mapped

        # Check onboarding occasions - pick most important one that has interaction history
        if onboarding_profile and onboarding_profile.personal.occasions:
            sorted_occasions = sorted(
                onboarding_profile.personal.occasions,
                key=lambda o: o.importance,
                reverse=True
            )
            for occasion in sorted_occasions:
                if occasion.style_context in detected_contexts:
                    return occasion.style_context

        # Most frequent context
        if detected_contexts:
            return detected_contexts[0]

        return StyleContext.DEFAULT

    def _map_occasion_to_context(self, occasion: str) -> Optional[StyleContext]:
        """Map an occasion string to a StyleContext."""
        occasion_lower = occasion.lower()

        # Keywords mapped to contexts, ordered by specificity (more specific first)
        # Order matters: check more specific keywords before general ones
        mappings = [
            # Active - check before travel/work
            ("gym", StyleContext.ACTIVE),
            ("workout", StyleContext.ACTIVE),
            ("hiking", StyleContext.ACTIVE),
            ("hike", StyleContext.ACTIVE),
            ("sport", StyleContext.ACTIVE),
            ("fitness", StyleContext.ACTIVE),
            ("exercise", StyleContext.ACTIVE),
            # Professional
            ("work", StyleContext.PROFESSIONAL),
            ("office", StyleContext.PROFESSIONAL),
            ("meeting", StyleContext.PROFESSIONAL),
            ("interview", StyleContext.PROFESSIONAL),
            # Casual
            ("weekend", StyleContext.CASUAL),
            ("brunch", StyleContext.CASUAL),
            ("errand", StyleContext.CASUAL),
            # Evening
            ("date", StyleContext.EVENING),
            ("dinner", StyleContext.EVENING),
            ("party", StyleContext.EVENING),
            # Formal
            ("wedding", StyleContext.FORMAL),
            ("gala", StyleContext.FORMAL),
            ("ceremony", StyleContext.FORMAL),
            # Creative
            ("art", StyleContext.CREATIVE),
            ("gallery", StyleContext.CREATIVE),
            ("concert", StyleContext.CREATIVE),
            # Travel - check last since "trip" is generic
            ("travel", StyleContext.TRAVEL),
            ("vacation", StyleContext.TRAVEL),
            ("trip", StyleContext.TRAVEL),
        ]

        for keyword, context in mappings:
            if keyword in occasion_lower:
                return context

        return None

    def _compute_cold_start_position(
        self,
        raw_data: RawUserData,
        context: StyleContext
    ) -> ContextualPosition:
        """
        Compute position for a context with no/few interactions.
        Uses onboarding data and social signals.
        """
        now = datetime.now()

        # Check if onboarding has occasion-specific style info
        occasion_style = None
        if raw_data.onboarding_profile:
            taste = raw_data.onboarding_profile.taste
            if taste.occasion_styles:
                for occ_name, occ_style in taste.occasion_styles.items():
                    if self._map_occasion_to_context(occ_name) == context:
                        occasion_style = occ_style
                        break

        # Generate initial embedding from available signals
        signals: List[np.ndarray] = []
        weights: List[float] = []

        # 1. Onboarding style description
        if occasion_style:
            style_text = occasion_style.description
            if self.embedding_service:
                embedding = self.embedding_service.embed(style_text)
                signals.append(embedding)
                weights.append(0.4)
        elif raw_data.onboarding_profile:
            taste = raw_data.onboarding_profile.taste
            brands = [b.brand for b in taste.brand_preferences] if taste.brand_preferences else []
            style_text = f"Loves: {taste.style_loves}. Wants: {taste.style_wants}. Brands: {brands}."
            if self.embedding_service:
                embedding = self.embedding_service.embed(style_text)
                signals.append(embedding)
                weights.append(0.3)

        # 2. Social taste embedding
        if raw_data.social_embeddings and raw_data.social_embeddings.unified_social_embedding is not None:
            signals.append(raw_data.social_embeddings.unified_social_embedding)
            weights.append(0.5)

        # 3. Population prior (placeholder - would load from precomputed centroids)
        population_centroid = self._get_population_centroid(context)
        signals.append(population_centroid)
        weights.append(0.2)

        # Normalize weights and blend
        if signals:
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]

            blended = sum(s * w for s, w in zip(signals, weights))
            embedding = normalize_vector(blended)
        else:
            embedding = zero_vector(1536)

        # Visual embedding from social if available
        visual_embedding = zero_vector(1024)
        if raw_data.social_embeddings and raw_data.social_embeddings.pinterest:
            if raw_data.social_embeddings.pinterest.overall_embedding is not None:
                visual_embedding = raw_data.social_embeddings.pinterest.overall_embedding

        position = StyleCoordinate(
            embedding=embedding,
            visual_embedding=visual_embedding
        )

        return ContextualPosition(
            context=context,
            position=position,
            trajectory=Trajectory(
                direction=zero_vector(1536),
                velocity=0.05,
                consistency=0.5,
                last_computed=now
            ),
            embeddings=UserEmbeddings(
                liked_embedding=embedding,
                purchased_embedding=embedding,
                unified_embedding=embedding,
                confidence=0.3  # Low confidence for cold start
            ),
            interaction_count=0,
            confidence=0.3,
            last_interaction=now
        )

    def _get_population_centroid(self, context: StyleContext) -> np.ndarray:
        """
        Get the population centroid for a context.

        TODO: Load from precomputed centroids file.
        """
        return zero_vector(1536)

    def _detect_universal_preferences(
        self,
        positions_by_context: Dict[StyleContext, ContextualPosition],
        onboarding_profile: Optional[OnboardingProfile]
    ) -> UniversalPreferences:
        """
        Detect preferences that are stable across all contexts.
        """
        always_preferred: List[str] = []
        always_avoided: List[str] = []
        stable_dimensions: List[str] = []

        # Use onboarding avoids as baseline
        if onboarding_profile and onboarding_profile.taste.style_avoids:
            # Parse avoids string into list
            avoids = onboarding_profile.taste.style_avoids
            if avoids:
                always_avoided.extend([a.strip() for a in avoids.split(",") if a.strip()])

        # TODO: Analyze positions to find stable dimensions
        # This requires comparing embeddings across contexts

        return UniversalPreferences(
            always_preferred=always_preferred,
            always_avoided=always_avoided,
            stable_dimensions=stable_dimensions
        )

    def _compute_unified_embeddings(
        self,
        interaction_embeddings: UserEmbeddings,
        social_embeddings: Optional[SocialTasteEmbeddings],
        user_weight: float
    ) -> UserEmbeddings:
        """
        Blend interaction history with social media signals.
        """
        # Weight social signals based on data richness
        social_weight = 0.0
        if social_embeddings and social_embeddings.unified_social_embedding is not None:
            # Social matters more when interaction history is thin
            interaction_confidence = interaction_embeddings.confidence
            social_weight = (1 - interaction_confidence) * 0.5  # Up to 50%

        interaction_weight = 1.0 - social_weight

        # Blend semantic embeddings
        if social_embeddings and social_embeddings.unified_social_embedding is not None:
            unified = normalize_vector(
                interaction_embeddings.unified_embedding * interaction_weight +
                social_embeddings.unified_social_embedding * social_weight
            )
        else:
            unified = interaction_embeddings.unified_embedding

        # Blend liked and purchased similarly
        if social_embeddings and social_embeddings.unified_social_embedding is not None:
            liked = normalize_vector(
                interaction_embeddings.liked_embedding * interaction_weight +
                social_embeddings.unified_social_embedding * social_weight
            )
            purchased = normalize_vector(
                interaction_embeddings.purchased_embedding * interaction_weight +
                social_embeddings.unified_social_embedding * social_weight
            )
        else:
            liked = interaction_embeddings.liked_embedding
            purchased = interaction_embeddings.purchased_embedding

        # Confidence is max of interaction and social
        confidence = max(
            interaction_embeddings.confidence,
            0.3 if social_embeddings and social_embeddings.unified_social_embedding is not None else 0.0
        )

        return UserEmbeddings(
            liked_embedding=liked,
            purchased_embedding=purchased,
            unified_embedding=unified,
            confidence=confidence
        )

    def _analyze_spending_patterns(
        self,
        interactions: List[Interaction],
        onboarding_profile: Optional[OnboardingProfile]
    ) -> SpendingPatterns:
        """
        Analyze user's spending behavior from interactions.
        """
        # Get stated budget from onboarding
        stated_budget = 200.0
        if onboarding_profile:
            stated_budget = float(onboarding_profile.practicality.budget.monthly)

        # TODO: Load actual purchase prices from product data
        # For now, return placeholder based on onboarding

        return SpendingPatterns(
            median_spend=stated_budget * 0.8,  # Placeholder
            stated_budget=stated_budget,
            spending_ratio=0.8,  # Placeholder
            category_spend={},
            investment_categories=[],
            budget_categories=[]
        )

    def _detect_behavioral_patterns(
        self,
        interactions: List[Interaction]
    ) -> BehavioralPatterns:
        """
        Detect behavioral patterns from interaction history.
        """
        # Calculate exploration rate
        unique_products = len(set(i.product_id for i in interactions))
        total_interactions = len(interactions)
        exploration_rate = unique_products / total_interactions if total_interactions > 0 else 0.5

        # Calculate return rate
        returned = sum(1 for i in interactions if i.type == InteractionType.RETURNED)
        purchased = sum(1 for i in interactions if i.type == InteractionType.PURCHASED)
        return_rate = returned / purchased if purchased > 0 else 0.0

        # Placeholder values for other patterns
        return BehavioralPatterns(
            exploration_rate=exploration_rate,
            return_rate=return_rate,
            decision_speed=0.5,  # TODO: Compute from time between view and purchase
            time_of_day_preference="afternoon",  # TODO: Compute from timestamps
            seasonal_preference={}
        )
