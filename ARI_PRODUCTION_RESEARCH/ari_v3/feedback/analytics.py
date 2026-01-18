"""
ARI V3 - Step 9: Feedback Analytics

Analyzes session outcomes to understand what's working and what's not.
Provides metrics for:
- Click-through rates and conversion rates
- Successful vs failed destinations
- Effective style descriptors
- Exploration vs conversion tradeoffs

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 8
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ari_v3.feedback.outcome_recorder import OutcomeType

logger = logging.getLogger(__name__)


@dataclass
class SessionMetrics:
    """Metrics for a single session."""
    session_id: str
    products_shown: int = 0
    products_viewed: int = 0
    products_clicked: int = 0
    products_liked: int = 0
    products_purchased: int = 0
    products_rejected: int = 0
    avg_time_spent: Optional[float] = None
    avg_rating: Optional[float] = None

    @property
    def view_rate(self) -> float:
        """Percentage of shown products that were viewed."""
        if self.products_shown == 0:
            return 0.0
        return self.products_viewed / self.products_shown

    @property
    def click_through_rate(self) -> float:
        """Percentage of shown products that were clicked."""
        if self.products_shown == 0:
            return 0.0
        return self.products_clicked / self.products_shown

    @property
    def conversion_rate(self) -> float:
        """Percentage of shown products that were purchased."""
        if self.products_shown == 0:
            return 0.0
        return self.products_purchased / self.products_shown

    @property
    def engagement_rate(self) -> float:
        """
        Percentage of shown products with any positive engagement.

        Note: We use max() to avoid double-counting products that were
        clicked, liked, AND purchased. A product can only be engaged once,
        regardless of how many engagement types it received.
        """
        if self.products_shown == 0:
            return 0.0
        # Use the highest engagement count as a proxy for unique engaged products
        # This prevents inflating the rate by counting same product multiple times
        max_engaged = max(self.products_clicked, self.products_liked, self.products_purchased)
        return min(1.0, max_engaged / self.products_shown)


@dataclass
class DescriptorEffectiveness:
    """Effectiveness metrics for a style descriptor."""
    descriptor: str
    times_used: int = 0
    total_conversions: int = 0
    total_clicks: int = 0
    total_rejections: int = 0

    @property
    def conversion_rate(self) -> float:
        """Conversion rate when this descriptor was used."""
        if self.times_used == 0:
            return 0.0
        return self.total_conversions / self.times_used

    @property
    def click_rate(self) -> float:
        """Click rate when this descriptor was used."""
        if self.times_used == 0:
            return 0.0
        return self.total_clicks / self.times_used

    @property
    def rejection_rate(self) -> float:
        """Rejection rate when this descriptor was used."""
        if self.times_used == 0:
            return 0.0
        return self.total_rejections / self.times_used

    @property
    def effectiveness_score(self) -> float:
        """Overall effectiveness score (conversion - rejection)."""
        return self.conversion_rate - self.rejection_rate


@dataclass
class FeedbackAnalysis:
    """
    Complete feedback analysis report.
    """
    # Time range
    start_date: datetime
    end_date: datetime
    days_analyzed: int

    # Session counts
    total_sessions: int = 0
    sessions_with_outcomes: int = 0

    # Overall metrics
    overall_click_through_rate: float = 0.0
    overall_conversion_rate: float = 0.0
    overall_engagement_rate: float = 0.0
    avg_products_per_session: float = 0.0

    # Destination analysis
    successful_destinations: List[Dict[str, Any]] = field(default_factory=list)
    failed_destinations: List[Dict[str, Any]] = field(default_factory=list)

    # Descriptor effectiveness
    effective_descriptors: List[DescriptorEffectiveness] = field(default_factory=list)
    ineffective_descriptors: List[DescriptorEffectiveness] = field(default_factory=list)

    # Navigation parameter analysis
    exploration_vs_conversion: Dict[str, Any] = field(default_factory=dict)
    diversity_vs_satisfaction: Dict[str, Any] = field(default_factory=dict)

    # Context analysis
    context_performance: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "time_range": {
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat(),
                "days": self.days_analyzed,
            },
            "session_counts": {
                "total": self.total_sessions,
                "with_outcomes": self.sessions_with_outcomes,
            },
            "overall_metrics": {
                "click_through_rate": self.overall_click_through_rate,
                "conversion_rate": self.overall_conversion_rate,
                "engagement_rate": self.overall_engagement_rate,
                "avg_products_per_session": self.avg_products_per_session,
            },
            "destinations": {
                "successful": self.successful_destinations[:10],
                "failed": self.failed_destinations[:10],
            },
            "descriptors": {
                "effective": [
                    {"descriptor": d.descriptor, "score": d.effectiveness_score}
                    for d in self.effective_descriptors[:10]
                ],
                "ineffective": [
                    {"descriptor": d.descriptor, "score": d.effectiveness_score}
                    for d in self.ineffective_descriptors[:10]
                ],
            },
            "navigation_analysis": {
                "exploration_vs_conversion": self.exploration_vs_conversion,
                "diversity_vs_satisfaction": self.diversity_vs_satisfaction,
            },
            "context_performance": self.context_performance,
        }


class FeedbackAnalytics:
    """
    Analyzes feedback data to understand recommendation effectiveness.
    """

    def __init__(self, neo4j_driver=None):
        """
        Initialize the feedback analytics.

        Args:
            neo4j_driver: Neo4j driver instance
        """
        self.neo4j_driver = neo4j_driver
        self._database = "users"

    async def analyze_session_outcomes(
        self,
        days: int = 30,
        user_id: Optional[str] = None,
    ) -> FeedbackAnalysis:
        """
        Analyze session outcomes over a time period.

        Args:
            days: Number of days to analyze
            user_id: Optional user to filter by

        Returns:
            FeedbackAnalysis with comprehensive metrics
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        if not self.neo4j_driver:
            logger.warning("No Neo4j driver configured")
            return FeedbackAnalysis(
                start_date=start_date,
                end_date=end_date,
                days_analyzed=days,
            )

        # Get session data with outcomes
        sessions_data = await self._get_sessions_with_outcomes(
            start_date=start_date,
            user_id=user_id,
        )

        if not sessions_data:
            return FeedbackAnalysis(
                start_date=start_date,
                end_date=end_date,
                days_analyzed=days,
            )

        # Calculate metrics
        total_sessions = len(sessions_data)
        sessions_with_outcomes = sum(1 for s in sessions_data if s.get("outcomes"))

        # Overall rates
        total_shown = sum(s.get("products_shown", 0) for s in sessions_data)
        total_clicked = sum(s.get("clicked", 0) for s in sessions_data)
        total_purchased = sum(s.get("purchased", 0) for s in sessions_data)
        total_engaged = sum(
            s.get("clicked", 0) + s.get("liked", 0) + s.get("purchased", 0)
            for s in sessions_data
        )

        ctr = total_clicked / total_shown if total_shown > 0 else 0.0
        cvr = total_purchased / total_shown if total_shown > 0 else 0.0
        engagement = total_engaged / total_shown if total_shown > 0 else 0.0
        avg_products = total_shown / total_sessions if total_sessions > 0 else 0.0

        # Analyze destinations
        successful_dests, failed_dests = await self._analyze_destinations(sessions_data)

        # Analyze descriptors
        effective_desc, ineffective_desc = await self._analyze_descriptors(sessions_data)

        # Analyze nav params vs outcomes
        exploration_analysis = await self._analyze_exploration_vs_conversion(sessions_data)
        diversity_analysis = await self._analyze_diversity_vs_satisfaction(sessions_data)

        # Analyze by context
        context_perf = await self._analyze_by_context(sessions_data)

        return FeedbackAnalysis(
            start_date=start_date,
            end_date=end_date,
            days_analyzed=days,
            total_sessions=total_sessions,
            sessions_with_outcomes=sessions_with_outcomes,
            overall_click_through_rate=ctr,
            overall_conversion_rate=cvr,
            overall_engagement_rate=engagement,
            avg_products_per_session=avg_products,
            successful_destinations=successful_dests,
            failed_destinations=failed_dests,
            effective_descriptors=effective_desc,
            ineffective_descriptors=ineffective_desc,
            exploration_vs_conversion=exploration_analysis,
            diversity_vs_satisfaction=diversity_analysis,
            context_performance=context_perf,
        )

    async def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        """
        Get metrics for a specific session.

        Args:
            session_id: Session UUID

        Returns:
            SessionMetrics or None
        """
        if not self.neo4j_driver:
            return None

        query = """
            MATCH (s:RecommendationSession {id: $session_id})
            OPTIONAL MATCH (s)-[:SHOWED]->(shown:ProductRef)
            OPTIONAL MATCH (s)-[o:OUTCOME]->(p:ProductRef)
            WITH s,
                count(DISTINCT shown) as products_shown,
                collect({type: o.type, time: o.time_spent_seconds, rating: o.explicit_feedback}) as outcomes
            RETURN
                s.id as session_id,
                products_shown,
                outcomes
        """

        async with self.neo4j_driver.session(database=self._database) as session:
            result = await session.run(query, session_id=session_id)
            record = await result.single()

            if not record:
                return None

            outcomes = record["outcomes"]

            # Count by type
            viewed = sum(1 for o in outcomes if o.get("type") == OutcomeType.VIEWED.value)
            clicked = sum(1 for o in outcomes if o.get("type") == OutcomeType.CLICKED.value)
            liked = sum(1 for o in outcomes if o.get("type") == OutcomeType.LIKED.value)
            purchased = sum(1 for o in outcomes if o.get("type") == OutcomeType.PURCHASED.value)
            rejected = sum(1 for o in outcomes if o.get("type") == OutcomeType.REJECTED.value)

            # Average time spent
            times = [o.get("time") for o in outcomes if o.get("time") is not None]
            avg_time = sum(times) / len(times) if times else None

            # Average rating
            ratings = [o.get("rating") for o in outcomes if o.get("rating") is not None]
            avg_rating = sum(ratings) / len(ratings) if ratings else None

            return SessionMetrics(
                session_id=session_id,
                products_shown=record["products_shown"],
                products_viewed=viewed,
                products_clicked=clicked,
                products_liked=liked,
                products_purchased=purchased,
                products_rejected=rejected,
                avg_time_spent=avg_time,
                avg_rating=avg_rating,
            )

    async def _get_sessions_with_outcomes(
        self,
        start_date: datetime,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get session data with outcomes from Neo4j."""
        if not self.neo4j_driver:
            return []

        user_filter = "AND u.id = $user_id" if user_id else ""

        query = f"""
            MATCH (u:User)-[:HAD_SESSION]->(s:RecommendationSession)
            WHERE s.timestamp >= datetime($start_date) {user_filter}

            OPTIONAL MATCH (s)-[:SHOWED]->(shown:ProductRef)
            OPTIONAL MATCH (s)-[o:OUTCOME]->(p:ProductRef)

            WITH s, u,
                count(DISTINCT shown) as products_shown,
                collect({{type: o.type, product: p.product_id}}) as outcomes

            RETURN
                s.id as session_id,
                s.style_descriptors as descriptors,
                s.active_context as context,
                s.exploration_appetite as exploration,
                s.diversity_requirement as diversity,
                products_shown,
                outcomes
        """

        params = {"start_date": start_date.isoformat()}
        if user_id:
            params["user_id"] = user_id

        async with self.neo4j_driver.session(database=self._database) as session:
            result = await session.run(query, **params)
            records = await result.data()

            sessions = []
            for record in records:
                outcomes = record.get("outcomes", [])
                clicked = sum(1 for o in outcomes if o.get("type") == OutcomeType.CLICKED.value)
                liked = sum(1 for o in outcomes if o.get("type") == OutcomeType.LIKED.value)
                purchased = sum(1 for o in outcomes if o.get("type") == OutcomeType.PURCHASED.value)
                rejected = sum(1 for o in outcomes if o.get("type") == OutcomeType.REJECTED.value)

                sessions.append({
                    "session_id": record["session_id"],
                    "descriptors": record.get("descriptors") or [],
                    "context": record.get("context"),
                    "exploration": record.get("exploration"),
                    "diversity": record.get("diversity"),
                    "products_shown": record.get("products_shown") or 0,
                    "outcomes": outcomes,
                    "clicked": clicked,
                    "liked": liked,
                    "purchased": purchased,
                    "rejected": rejected,
                })

            return sessions

    async def _analyze_destinations(
        self,
        sessions_data: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Analyze which destinations led to conversions."""
        # Group by descriptor combination
        descriptor_outcomes: Dict[str, Dict[str, int]] = {}

        for session in sessions_data:
            descriptors = session.get("descriptors") or []
            # Filter out None/empty values
            descriptors = [d for d in descriptors if d]
            if not descriptors:
                continue

            key = "|".join(sorted(descriptors[:3]))  # Use top 3 descriptors
            if key not in descriptor_outcomes:
                descriptor_outcomes[key] = {
                    "sessions": 0,
                    "conversions": 0,
                    "clicks": 0,
                    "rejections": 0,
                }

            descriptor_outcomes[key]["sessions"] += 1
            descriptor_outcomes[key]["conversions"] += session.get("purchased", 0)
            descriptor_outcomes[key]["clicks"] += session.get("clicked", 0)
            descriptor_outcomes[key]["rejections"] += session.get("rejected", 0)

        # Calculate rates and sort
        results = []
        for key, data in descriptor_outcomes.items():
            if data["sessions"] >= 3:  # Minimum threshold
                cvr = data["conversions"] / data["sessions"]
                results.append({
                    "descriptors": key.split("|"),
                    "sessions": data["sessions"],
                    "conversion_rate": cvr,
                    "click_rate": data["clicks"] / data["sessions"],
                })

        # Sort by conversion rate
        results.sort(key=lambda x: x["conversion_rate"], reverse=True)

        # Split into successful (top half) and failed (bottom half)
        mid = len(results) // 2
        return results[:mid], results[mid:]

    async def _analyze_descriptors(
        self,
        sessions_data: List[Dict[str, Any]],
    ) -> tuple[List[DescriptorEffectiveness], List[DescriptorEffectiveness]]:
        """Analyze effectiveness of individual descriptors."""
        descriptor_stats: Dict[str, DescriptorEffectiveness] = {}

        for session in sessions_data:
            descriptors = session.get("descriptors") or []
            for desc in descriptors:
                # Skip None or empty descriptors
                if not desc:
                    continue

                if desc not in descriptor_stats:
                    descriptor_stats[desc] = DescriptorEffectiveness(descriptor=desc)

                descriptor_stats[desc].times_used += 1
                descriptor_stats[desc].total_conversions += session.get("purchased", 0)
                descriptor_stats[desc].total_clicks += session.get("clicked", 0)
                descriptor_stats[desc].total_rejections += session.get("rejected", 0)

        # Filter to descriptors with enough data
        valid_descriptors = [
            d for d in descriptor_stats.values()
            if d.times_used >= 5
        ]

        # Sort by effectiveness score
        valid_descriptors.sort(key=lambda x: x.effectiveness_score, reverse=True)

        # Split into effective and ineffective
        mid = len(valid_descriptors) // 2
        return valid_descriptors[:mid], valid_descriptors[mid:]

    async def _analyze_exploration_vs_conversion(
        self,
        sessions_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze relationship between exploration appetite and conversions."""
        # Bucket by exploration level
        buckets = {
            "low": {"sessions": 0, "conversions": 0, "exploration": []},      # 0-0.33
            "medium": {"sessions": 0, "conversions": 0, "exploration": []},   # 0.33-0.66
            "high": {"sessions": 0, "conversions": 0, "exploration": []},     # 0.66-1.0
        }

        for session in sessions_data:
            exploration = session.get("exploration")
            if exploration is None:
                continue

            if exploration < 0.33:
                bucket = "low"
            elif exploration < 0.66:
                bucket = "medium"
            else:
                bucket = "high"

            buckets[bucket]["sessions"] += 1
            buckets[bucket]["conversions"] += session.get("purchased", 0)
            buckets[bucket]["exploration"].append(exploration)

        # Calculate rates
        result = {}
        for level, data in buckets.items():
            if data["sessions"] > 0:
                result[level] = {
                    "sessions": data["sessions"],
                    "conversion_rate": data["conversions"] / data["sessions"],
                    "avg_exploration": sum(data["exploration"]) / len(data["exploration"]) if data["exploration"] else 0,
                }

        return result

    async def _analyze_diversity_vs_satisfaction(
        self,
        sessions_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze relationship between diversity requirement and satisfaction."""
        # Bucket by diversity level
        buckets = {
            "low": {"sessions": 0, "liked": 0, "rejected": 0},      # 0-0.33
            "medium": {"sessions": 0, "liked": 0, "rejected": 0},   # 0.33-0.66
            "high": {"sessions": 0, "liked": 0, "rejected": 0},     # 0.66-1.0
        }

        for session in sessions_data:
            diversity = session.get("diversity")
            if diversity is None:
                continue

            if diversity < 0.33:
                bucket = "low"
            elif diversity < 0.66:
                bucket = "medium"
            else:
                bucket = "high"

            buckets[bucket]["sessions"] += 1
            buckets[bucket]["liked"] += session.get("liked", 0)
            buckets[bucket]["rejected"] += session.get("rejected", 0)

        # Calculate satisfaction (liked - rejected rate)
        result = {}
        for level, data in buckets.items():
            if data["sessions"] > 0:
                total_feedback = data["liked"] + data["rejected"]
                satisfaction = 0.5  # Neutral default
                if total_feedback > 0:
                    satisfaction = data["liked"] / total_feedback

                result[level] = {
                    "sessions": data["sessions"],
                    "satisfaction_rate": satisfaction,
                    "like_rate": data["liked"] / data["sessions"],
                    "rejection_rate": data["rejected"] / data["sessions"],
                }

        return result

    async def _analyze_by_context(
        self,
        sessions_data: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, float]]:
        """Analyze performance by style context."""
        context_stats: Dict[str, Dict[str, int]] = {}

        for session in sessions_data:
            context = session.get("context") or "unknown"

            if context not in context_stats:
                context_stats[context] = {
                    "sessions": 0,
                    "products_shown": 0,
                    "clicked": 0,
                    "purchased": 0,
                }

            context_stats[context]["sessions"] += 1
            context_stats[context]["products_shown"] += session.get("products_shown", 0)
            context_stats[context]["clicked"] += session.get("clicked", 0)
            context_stats[context]["purchased"] += session.get("purchased", 0)

        # Calculate rates
        result = {}
        for context, data in context_stats.items():
            if data["sessions"] >= 3:  # Minimum threshold
                shown = data["products_shown"]
                result[context] = {
                    "sessions": data["sessions"],
                    "click_rate": data["clicked"] / shown if shown > 0 else 0,
                    "conversion_rate": data["purchased"] / shown if shown > 0 else 0,
                }

        return result


def create_feedback_analytics(neo4j_driver=None) -> FeedbackAnalytics:
    """
    Factory function to create FeedbackAnalytics.

    Args:
        neo4j_driver: Neo4j driver instance

    Returns:
        Configured FeedbackAnalytics
    """
    return FeedbackAnalytics(neo4j_driver=neo4j_driver)
