"""
ARI V3 - Step 9: Reinterpretation Trigger

Detects when user behavior diverges from stated preferences and
triggers profile re-interpretation via LLM #2.

Divergence signals (2+ required to trigger):
1. Spending above/below stated budget
2. Adventurousness mismatch
3. Buying stated avoids
4. New life contexts
5. Brand loyalty mismatch

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 8
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ari_v3.core.data_structures import OnboardingProfile, NavigationParameters, RawUserData

logger = logging.getLogger(__name__)

# Minimum interactions before checking for divergence
MIN_INTERACTIONS_FOR_DIVERGENCE = 30

# Divergence thresholds
BUDGET_HIGH_THRESHOLD = 1.5  # Spending > 1.5x stated
BUDGET_LOW_THRESHOLD = 0.3   # Spending < 0.3x stated
ADVENTUROUSNESS_THRESHOLD = 0.4  # Variance diff > 0.4
BRAND_LOYALTY_THRESHOLD = 0.4    # Repeat rate diff > 0.4
MIN_AVOID_VIOLATIONS = 3         # Purchased 3+ avoided items
MIN_NEW_CONTEXTS = 2             # 2+ new contexts not in onboarding
MIN_DIVERGENCE_SIGNALS = 2       # Signals required to trigger


@dataclass
class DivergenceSignal:
    """A detected divergence between stated and observed behavior."""
    signal_type: str
    description: str
    stated_value: Any
    observed_value: Any
    severity: float = 0.0  # 0.0 to 1.0


@dataclass
class DivergenceAnalysisResult:
    """Result of divergence analysis."""
    user_id: str
    interaction_count: int
    signals: List[DivergenceSignal] = field(default_factory=list)
    should_reinterpret: bool = False
    analysis_timestamp: datetime = field(default_factory=datetime.now)

    @property
    def signal_count(self) -> int:
        """Number of divergence signals detected."""
        return len(self.signals)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "interaction_count": self.interaction_count,
            "signals": [
                {
                    "type": s.signal_type,
                    "description": s.description,
                    "stated": s.stated_value,
                    "observed": s.observed_value,
                    "severity": s.severity,
                }
                for s in self.signals
            ],
            "should_reinterpret": self.should_reinterpret,
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
        }


@dataclass
class BehavioralSummary:
    """Summary of user's observed behavior."""
    median_spending: Optional[float] = None
    style_variance: Optional[float] = None
    brand_repeat_rate: Optional[float] = None
    purchased_styles: List[str] = field(default_factory=list)
    observed_contexts: List[str] = field(default_factory=list)
    interaction_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for LLM prompt."""
        return {
            "median_spending": self.median_spending,
            "style_variance": self.style_variance,
            "brand_repeat_rate": self.brand_repeat_rate,
            "purchased_styles": self.purchased_styles,
            "observed_contexts": self.observed_contexts,
            "interaction_count": self.interaction_count,
        }


class ReinterpretationChecker:
    """
    Checks for behavioral divergence and triggers profile re-interpretation.
    """

    def __init__(
        self,
        neo4j_driver=None,
        onboarding_service=None,
    ):
        """
        Initialize the reinterpretation checker.

        Args:
            neo4j_driver: Neo4j driver for behavior queries
            onboarding_service: OnboardingServiceV3 for re-interpretation
        """
        self.neo4j_driver = neo4j_driver
        self.onboarding_service = onboarding_service
        self._database = "users"

    async def check_reinterpretation_trigger(
        self,
        user_id: str,
        raw_user_data: Optional[RawUserData] = None,
    ) -> DivergenceAnalysisResult:
        """
        Check if user behavior diverges enough to trigger re-interpretation.

        Args:
            user_id: User identifier
            raw_user_data: Optional pre-loaded user data

        Returns:
            DivergenceAnalysisResult with signals and recommendation
        """
        if not user_id:
            raise ValueError("user_id cannot be empty")

        # Get interaction count
        interaction_count = await self._get_interaction_count(user_id)

        # Not enough data yet
        user_id_short = user_id[:8] + "..." if len(user_id) > 8 else user_id
        if interaction_count < MIN_INTERACTIONS_FOR_DIVERGENCE:
            logger.debug(
                f"User {user_id_short} has {interaction_count} interactions, "
                f"need {MIN_INTERACTIONS_FOR_DIVERGENCE} for divergence check"
            )
            return DivergenceAnalysisResult(
                user_id=user_id,
                interaction_count=interaction_count,
                should_reinterpret=False,
            )

        # Load user data if not provided
        if raw_user_data is None:
            raw_user_data = await self._load_raw_user_data(user_id)

        if raw_user_data is None or raw_user_data.onboarding_profile is None:
            logger.warning(f"No onboarding profile for user {user_id_short}")
            return DivergenceAnalysisResult(
                user_id=user_id,
                interaction_count=interaction_count,
                should_reinterpret=False,
            )

        # Compute behavioral summary
        behavioral = await self._compute_behavioral_summary(user_id)

        # Check for divergence signals
        profile = raw_user_data.onboarding_profile
        signals = []

        # 1. Budget divergence
        budget_signal = self._check_budget_divergence(profile, behavioral)
        if budget_signal:
            signals.append(budget_signal)

        # 2. Adventurousness divergence
        adventure_signal = self._check_adventurousness_divergence(profile, behavioral)
        if adventure_signal:
            signals.append(adventure_signal)

        # 3. Style avoidance violations
        avoid_signal = self._check_avoid_violations(profile, behavioral)
        if avoid_signal:
            signals.append(avoid_signal)

        # 4. New contexts
        context_signal = self._check_new_contexts(profile, behavioral)
        if context_signal:
            signals.append(context_signal)

        # 5. Brand loyalty divergence
        brand_signal = self._check_brand_loyalty_divergence(profile, behavioral)
        if brand_signal:
            signals.append(brand_signal)

        # Determine if reinterpretation needed
        should_reinterpret = len(signals) >= MIN_DIVERGENCE_SIGNALS

        user_id_short = user_id[:8] + "..." if len(user_id) > 8 else user_id
        if should_reinterpret:
            logger.info(
                f"User {user_id_short} has {len(signals)} divergence signals, "
                f"recommending re-interpretation"
            )
        else:
            logger.debug(
                f"User {user_id_short} has {len(signals)} divergence signals, "
                f"below threshold of {MIN_DIVERGENCE_SIGNALS}"
            )

        return DivergenceAnalysisResult(
            user_id=user_id,
            interaction_count=interaction_count,
            signals=signals,
            should_reinterpret=should_reinterpret,
        )

    async def run_reinterpretation(
        self,
        user_id: str,
        divergence_result: Optional[DivergenceAnalysisResult] = None,
    ) -> bool:
        """
        Run profile re-interpretation via LLM #2.

        Args:
            user_id: User identifier
            divergence_result: Optional pre-computed divergence analysis

        Returns:
            True if re-interpretation was successful
        """
        if not self.onboarding_service:
            logger.error("No onboarding service configured for re-interpretation")
            return False

        # Get behavioral summary for LLM context
        behavioral = await self._compute_behavioral_summary(user_id)

        # Get divergence notes
        divergence_notes = []
        if divergence_result:
            for signal in divergence_result.signals:
                divergence_notes.append(signal.description)

        # Build behavioral summary dict
        behavioral_summary = behavioral.to_dict()
        behavioral_summary["divergence_notes"] = divergence_notes

        # Get raw conversations (needed for re-interpretation)
        raw_conversations = await self._get_raw_conversations(user_id)

        try:
            # Call onboarding service's reinterpret_profile
            updated_profile, updated_params = await self.onboarding_service.reinterpret_profile(
                user_id=user_id,
                raw_conversations=raw_conversations,
                behavioral_summary=behavioral_summary,
            )

            user_id_short = user_id[:8] + "..." if len(user_id) > 8 else user_id
            logger.info(f"Re-interpreted profile for user {user_id_short}")
            return True

        except Exception as e:
            user_id_short = user_id[:8] + "..." if len(user_id) > 8 else user_id
            logger.error(f"Re-interpretation failed for user {user_id_short}: {e}")
            return False

    async def on_interaction(
        self,
        user_id: str,
        interaction: Dict[str, Any],
    ) -> None:
        """
        Called after each user interaction.
        Checks for re-interpretation trigger every 20 interactions.

        Args:
            user_id: User identifier
            interaction: Interaction data
        """
        # Get current interaction count
        interaction_count = await self._get_interaction_count(user_id)

        # Check every 20 interactions
        if interaction_count > 0 and interaction_count % 20 == 0:
            result = await self.check_reinterpretation_trigger(user_id)
            if result.should_reinterpret:
                await self.run_reinterpretation(user_id, result)

    def _check_budget_divergence(
        self,
        profile: OnboardingProfile,
        behavioral: BehavioralSummary,
    ) -> Optional[DivergenceSignal]:
        """Check if spending diverges from stated budget."""
        if behavioral.median_spending is None:
            return None

        stated_budget = None
        if profile.practicality and profile.practicality.budget:
            stated_budget = profile.practicality.budget.monthly

        if stated_budget is None or stated_budget <= 0:
            return None

        ratio = behavioral.median_spending / stated_budget

        if ratio > BUDGET_HIGH_THRESHOLD:
            return DivergenceSignal(
                signal_type="spending_above_stated",
                description=f"Median spending ${behavioral.median_spending:.0f} is {ratio:.1f}x stated budget ${stated_budget:.0f}",
                stated_value=stated_budget,
                observed_value=behavioral.median_spending,
                severity=min(1.0, (ratio - 1.0) / 2.0),
            )

        if ratio < BUDGET_LOW_THRESHOLD:
            return DivergenceSignal(
                signal_type="spending_below_stated",
                description=f"Median spending ${behavioral.median_spending:.0f} is only {ratio:.1%} of stated budget ${stated_budget:.0f}",
                stated_value=stated_budget,
                observed_value=behavioral.median_spending,
                severity=min(1.0, (1.0 - ratio) / 0.7),
            )

        return None

    def _check_adventurousness_divergence(
        self,
        profile: OnboardingProfile,
        behavioral: BehavioralSummary,
    ) -> Optional[DivergenceSignal]:
        """Check if style variance diverges from stated adventurousness."""
        if behavioral.style_variance is None:
            return None

        stated_adventurousness = None
        if profile.process:
            stated_adventurousness = profile.process.adventurousness
            if stated_adventurousness is not None:
                stated_adventurousness = stated_adventurousness / 10.0  # Normalize to 0-1

        if stated_adventurousness is None:
            return None

        diff = abs(behavioral.style_variance - stated_adventurousness)

        if diff > ADVENTUROUSNESS_THRESHOLD:
            direction = "more" if behavioral.style_variance > stated_adventurousness else "less"
            return DivergenceSignal(
                signal_type="adventurousness_mismatch",
                description=f"Actual style variance {behavioral.style_variance:.2f} is {direction} adventurous than stated {stated_adventurousness:.2f}",
                stated_value=stated_adventurousness,
                observed_value=behavioral.style_variance,
                severity=min(1.0, diff / 0.6),
            )

        return None

    def _check_avoid_violations(
        self,
        profile: OnboardingProfile,
        behavioral: BehavioralSummary,
    ) -> Optional[DivergenceSignal]:
        """Check if user is buying items they said they avoid."""
        if not behavioral.purchased_styles:
            return None

        stated_avoids = []
        if profile.taste and profile.taste.style_avoids:
            # Parse avoids - could be string or list
            avoids = profile.taste.style_avoids
            if isinstance(avoids, str):
                # Filter out empty strings after splitting
                stated_avoids = [a.strip().lower() for a in avoids.split(",") if a.strip()]
            elif isinstance(avoids, list):
                stated_avoids = [str(a).lower() for a in avoids if a]

        if not stated_avoids:
            return None

        # Find overlap (filter None values)
        purchased_lower = [s.lower() for s in behavioral.purchased_styles if s]
        violations = [a for a in stated_avoids if any(a in p for p in purchased_lower)]

        if len(violations) >= MIN_AVOID_VIOLATIONS:
            return DivergenceSignal(
                signal_type="buying_stated_avoids",
                description=f"Purchased {len(violations)} items from stated avoids: {', '.join(violations[:3])}",
                stated_value=stated_avoids,
                observed_value=violations,
                severity=min(1.0, len(violations) / 5.0),
            )

        return None

    def _check_new_contexts(
        self,
        profile: OnboardingProfile,
        behavioral: BehavioralSummary,
    ) -> Optional[DivergenceSignal]:
        """Check if user has new life contexts not in onboarding."""
        if not behavioral.observed_contexts:
            return None

        stated_contexts = []
        if profile.personal and profile.personal.occasions:
            for occ in profile.personal.occasions:
                if hasattr(occ, 'style_context') and occ.style_context:
                    ctx = occ.style_context
                    if hasattr(ctx, 'value'):
                        stated_contexts.append(ctx.value.lower())
                    else:
                        stated_contexts.append(str(ctx).lower())

        # Find new contexts (filter None values)
        observed_lower = [c.lower() for c in behavioral.observed_contexts if c]
        new_contexts = [c for c in observed_lower if c not in stated_contexts]

        if len(new_contexts) >= MIN_NEW_CONTEXTS:
            return DivergenceSignal(
                signal_type="new_life_contexts",
                description=f"Detected {len(new_contexts)} new contexts not in onboarding: {', '.join(new_contexts[:3])}",
                stated_value=stated_contexts,
                observed_value=new_contexts,
                severity=min(1.0, len(new_contexts) / 4.0),
            )

        return None

    def _check_brand_loyalty_divergence(
        self,
        profile: OnboardingProfile,
        behavioral: BehavioralSummary,
    ) -> Optional[DivergenceSignal]:
        """Check if brand loyalty diverges from stated preference."""
        if behavioral.brand_repeat_rate is None:
            return None

        stated_loyalty = None
        if profile.process:
            stated_loyalty = profile.process.brand_loyalty
            if stated_loyalty is not None:
                stated_loyalty = stated_loyalty / 10.0  # Normalize to 0-1

        if stated_loyalty is None:
            return None

        diff = abs(behavioral.brand_repeat_rate - stated_loyalty)

        if diff > BRAND_LOYALTY_THRESHOLD:
            direction = "higher" if behavioral.brand_repeat_rate > stated_loyalty else "lower"
            return DivergenceSignal(
                signal_type="brand_loyalty_mismatch",
                description=f"Actual brand repeat rate {behavioral.brand_repeat_rate:.2f} is {direction} than stated loyalty {stated_loyalty:.2f}",
                stated_value=stated_loyalty,
                observed_value=behavioral.brand_repeat_rate,
                severity=min(1.0, diff / 0.6),
            )

        return None

    async def _get_interaction_count(self, user_id: str) -> int:
        """Get total interaction count for user."""
        if not self.neo4j_driver:
            return 0

        query = """
            MATCH (u:User {id: $user_id})-[:HAD_SESSION]->(s)-[o:OUTCOME]->()
            RETURN count(o) as count
        """

        async with self.neo4j_driver.session(database=self._database) as session:
            result = await session.run(query, user_id=user_id)
            record = await result.single()
            return record["count"] if record else 0

    async def _load_raw_user_data(self, user_id: str) -> Optional[RawUserData]:
        """Load raw user data from Pillar 1."""
        try:
            from ari_v3.pillars.personalization import Pillar1_Personalization
            pillar1 = Pillar1_Personalization(neo4j_driver=self.neo4j_driver)
            return pillar1.load_raw_user_data(user_id)
        except Exception as e:
            logger.error(f"Failed to load raw user data: {e}")
            return None

    async def _compute_behavioral_summary(self, user_id: str) -> BehavioralSummary:
        """Compute behavioral summary from interactions."""
        if not self.neo4j_driver:
            return BehavioralSummary()

        # Query for behavioral data
        # Note: Purchase info is stored in OUTCOME relationship with type='purchased'
        query = """
            MATCH (u:User {id: $user_id})-[:HAD_SESSION]->(s)-[o:OUTCOME]->(p:ProductRef)

            // Get session contexts and interaction count
            WITH u, s, o, p,
                 CASE WHEN o.type = 'purchased' THEN p.price ELSE null END as purchase_price
            RETURN
                collect(DISTINCT purchase_price) as prices,
                collect(DISTINCT s.active_context) as contexts,
                collect(DISTINCT p.product_id) as products,
                count(o) as interaction_count
        """

        async with self.neo4j_driver.session(database=self._database) as session:
            result = await session.run(query, user_id=user_id)
            record = await result.single()

            if not record:
                return BehavioralSummary()

            prices = [p for p in record["prices"] if p is not None]
            contexts = [c for c in record["contexts"] if c is not None]

            # Calculate median spending
            median_spending = None
            if prices:
                sorted_prices = sorted(prices)
                mid = len(sorted_prices) // 2
                median_spending = sorted_prices[mid]

            # Calculate style variance (placeholder - would need embedding analysis)
            style_variance = 0.5  # Default mid-range

            # Calculate brand repeat rate (placeholder)
            brand_repeat_rate = 0.3  # Default low

            return BehavioralSummary(
                median_spending=median_spending,
                style_variance=style_variance,
                brand_repeat_rate=brand_repeat_rate,
                purchased_styles=[],  # Would need product category analysis
                observed_contexts=contexts,
                interaction_count=record["interaction_count"],
            )

    async def _get_raw_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get raw onboarding conversations for re-interpretation."""
        if not self.neo4j_driver:
            return []

        query = """
            MATCH (u:User {id: $user_id})-[:HAS_ONBOARDING]->(ob)
            RETURN ob.raw_conversations as conversations
        """

        async with self.neo4j_driver.session(database=self._database) as session:
            result = await session.run(query, user_id=user_id)
            record = await result.single()

            if record and record.get("conversations"):
                convs = record["conversations"]
                if isinstance(convs, str):
                    try:
                        return json.loads(convs)
                    except json.JSONDecodeError:
                        return []
                return convs

            return []


def create_reinterpretation_checker(
    neo4j_driver=None,
    onboarding_service=None,
) -> ReinterpretationChecker:
    """
    Factory function to create a ReinterpretationChecker.

    Args:
        neo4j_driver: Neo4j driver instance
        onboarding_service: OnboardingServiceV3 instance

    Returns:
        Configured ReinterpretationChecker
    """
    return ReinterpretationChecker(
        neo4j_driver=neo4j_driver,
        onboarding_service=onboarding_service,
    )
