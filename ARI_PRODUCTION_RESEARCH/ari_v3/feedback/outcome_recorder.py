"""
ARI V3 - Step 9: Outcome Recorder

Records user interactions with recommended products.
Tracks outcomes: viewed, clicked, liked, purchased, rejected.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 8
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OutcomeType(Enum):
    """Types of user interactions with products."""
    VIEWED = "viewed"
    CLICKED = "clicked"
    LIKED = "liked"
    PURCHASED = "purchased"
    REJECTED = "rejected"


@dataclass
class SessionOutcome:
    """
    Record of a user's interaction with a product from a session.
    """
    session_id: str
    product_id: str
    outcome_type: OutcomeType
    timestamp: datetime
    time_spent_seconds: Optional[int] = None
    explicit_feedback: Optional[int] = None  # 1-5 rating
    feedback_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "session_id": self.session_id,
            "product_id": self.product_id,
            "outcome_type": self.outcome_type.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "time_spent_seconds": self.time_spent_seconds,
            "explicit_feedback": self.explicit_feedback,
            "feedback_text": self.feedback_text,
        }


class OutcomeRecorder:
    """
    Records user interaction outcomes with recommended products.

    Creates [:OUTCOME] relationships between sessions and products,
    and updates user-product [:INTERACTED_WITH] relationships.
    """

    def __init__(self, neo4j_driver=None):
        """
        Initialize the outcome recorder.

        Args:
            neo4j_driver: Neo4j driver instance
        """
        self.neo4j_driver = neo4j_driver
        self._database = "users"

    async def record_outcome(
        self,
        session_id: str,
        product_id: str,
        outcome: OutcomeType,
        time_spent_seconds: Optional[int] = None,
        explicit_feedback: Optional[int] = None,
        feedback_text: Optional[str] = None,
    ) -> bool:
        """
        Record a user interaction outcome.

        Args:
            session_id: Session UUID
            product_id: Product identifier
            outcome: Type of interaction (viewed, clicked, liked, purchased, rejected)
            time_spent_seconds: Time user spent viewing product
            explicit_feedback: User's rating (1-5)
            feedback_text: Optional text feedback

        Returns:
            True if recorded successfully
        """
        if not session_id:
            raise ValueError("session_id cannot be empty")
        if not product_id:
            raise ValueError("product_id cannot be empty")

        # Validate explicit_feedback range
        if explicit_feedback is not None:
            if not 1 <= explicit_feedback <= 5:
                raise ValueError("explicit_feedback must be between 1 and 5")

        timestamp = datetime.now()

        outcome_record = SessionOutcome(
            session_id=session_id,
            product_id=product_id,
            outcome_type=outcome,
            timestamp=timestamp,
            time_spent_seconds=time_spent_seconds,
            explicit_feedback=explicit_feedback,
            feedback_text=feedback_text,
        )

        stored = True  # Default to True when no driver (in-memory only)
        if self.neo4j_driver:
            stored = await self._store_outcome_neo4j(outcome_record)
            if not stored:
                session_id_short = session_id[:8] + "..." if len(session_id) > 8 else session_id
                logger.warning(f"Session {session_id_short} not found, outcome not persisted")
        else:
            logger.warning("No Neo4j driver configured, outcome not persisted")

        product_id_short = product_id[:8] + "..." if len(product_id) > 8 else product_id
        session_id_short = session_id[:8] + "..." if len(session_id) > 8 else session_id
        logger.debug(
            f"Recorded {outcome.value} outcome for product {product_id_short} "
            f"in session {session_id_short}"
        )

        return stored

    async def _store_outcome_neo4j(self, outcome: SessionOutcome) -> bool:
        """
        Store outcome in Neo4j.

        Creates [:OUTCOME] relationship and updates user-product interaction.

        Returns:
            True if outcome was stored, False if session not found
        """
        if not self.neo4j_driver:
            return False

        query = """
            // Find session and product
            MATCH (s:RecommendationSession {id: $session_id})
            MERGE (p:ProductRef {product_id: $product_id})

            // Create outcome relationship
            CREATE (s)-[r:OUTCOME {
                type: $outcome_type,
                timestamp: datetime($timestamp),
                time_spent_seconds: $time_spent,
                explicit_feedback: $feedback,
                feedback_text: $feedback_text
            }]->(p)

            // Update user-product interaction
            WITH s, p
            MATCH (u:User)-[:HAD_SESSION]->(s)
            MERGE (u)-[i:INTERACTED_WITH]->(p)
            ON CREATE SET
                i.first_interaction = datetime(),
                i.interaction_count = 0
            SET
                i.last_interaction = datetime(),
                i.interaction_count = i.interaction_count + 1,
                i.last_outcome_type = $outcome_type

            RETURN s.id as session_id
        """

        async with self.neo4j_driver.session(database=self._database) as neo_session:
            result = await neo_session.run(
                query,
                session_id=outcome.session_id,
                product_id=outcome.product_id,
                outcome_type=outcome.outcome_type.value,
                timestamp=outcome.timestamp.isoformat() if outcome.timestamp else None,
                time_spent=outcome.time_spent_seconds,
                feedback=outcome.explicit_feedback,
                feedback_text=outcome.feedback_text,
            )
            record = await result.single()
            return record is not None

    async def record_view(
        self,
        session_id: str,
        product_id: str,
        time_spent_seconds: Optional[int] = None,
    ) -> bool:
        """Record a product view."""
        return await self.record_outcome(
            session_id=session_id,
            product_id=product_id,
            outcome=OutcomeType.VIEWED,
            time_spent_seconds=time_spent_seconds,
        )

    async def record_click(
        self,
        session_id: str,
        product_id: str,
    ) -> bool:
        """Record a product click."""
        return await self.record_outcome(
            session_id=session_id,
            product_id=product_id,
            outcome=OutcomeType.CLICKED,
        )

    async def record_like(
        self,
        session_id: str,
        product_id: str,
    ) -> bool:
        """Record a product like/save."""
        return await self.record_outcome(
            session_id=session_id,
            product_id=product_id,
            outcome=OutcomeType.LIKED,
        )

    async def record_purchase(
        self,
        session_id: str,
        product_id: str,
    ) -> bool:
        """Record a product purchase."""
        return await self.record_outcome(
            session_id=session_id,
            product_id=product_id,
            outcome=OutcomeType.PURCHASED,
        )

    async def record_rejection(
        self,
        session_id: str,
        product_id: str,
        feedback_text: Optional[str] = None,
    ) -> bool:
        """Record a product rejection."""
        return await self.record_outcome(
            session_id=session_id,
            product_id=product_id,
            outcome=OutcomeType.REJECTED,
            feedback_text=feedback_text,
        )

    async def record_rating(
        self,
        session_id: str,
        product_id: str,
        rating: int,
        feedback_text: Optional[str] = None,
    ) -> bool:
        """
        Record a user's rating of a product.

        Args:
            session_id: Session UUID
            product_id: Product identifier
            rating: User's rating (1-5)
            feedback_text: Optional text feedback

        Returns:
            True if recorded successfully
        """
        # Determine outcome type based on rating
        if rating >= 4:
            outcome = OutcomeType.LIKED
        elif rating <= 2:
            outcome = OutcomeType.REJECTED
        else:
            outcome = OutcomeType.VIEWED

        return await self.record_outcome(
            session_id=session_id,
            product_id=product_id,
            outcome=outcome,
            explicit_feedback=rating,
            feedback_text=feedback_text,
        )

    async def get_session_outcomes(
        self,
        session_id: str,
    ) -> List[SessionOutcome]:
        """
        Get all outcomes for a session.

        Args:
            session_id: Session UUID

        Returns:
            List of SessionOutcome objects
        """
        if not self.neo4j_driver:
            logger.warning("No Neo4j driver configured")
            return []

        query = """
            MATCH (s:RecommendationSession {id: $session_id})-[o:OUTCOME]->(p:ProductRef)
            RETURN
                p.product_id as product_id,
                o.type as outcome_type,
                o.timestamp as timestamp,
                o.time_spent_seconds as time_spent,
                o.explicit_feedback as feedback,
                o.feedback_text as feedback_text
            ORDER BY o.timestamp
        """

        async with self.neo4j_driver.session(database=self._database) as neo_session:
            result = await neo_session.run(query, session_id=session_id)
            records = await result.data()

            outcomes = []
            for record in records:
                timestamp = record["timestamp"]
                if timestamp and hasattr(timestamp, "to_native"):
                    timestamp = timestamp.to_native()
                elif timestamp is None:
                    timestamp = datetime.now()

                # Parse outcome type safely
                try:
                    outcome_type = OutcomeType(record["outcome_type"])
                except (ValueError, KeyError):
                    logger.warning(f"Unknown outcome type: {record.get('outcome_type')}, defaulting to VIEWED")
                    outcome_type = OutcomeType.VIEWED

                product_id = record.get("product_id")
                if not product_id:
                    logger.warning(f"Skipping outcome with null product_id in session {session_id}")
                    continue

                outcomes.append(SessionOutcome(
                    session_id=session_id,
                    product_id=product_id,
                    outcome_type=outcome_type,
                    timestamp=timestamp,
                    time_spent_seconds=record.get("time_spent"),
                    explicit_feedback=record.get("feedback"),
                    feedback_text=record.get("feedback_text"),
                ))

            return outcomes

    async def get_user_interaction_count(self, user_id: str) -> int:
        """
        Get total interaction count for a user.

        Args:
            user_id: User identifier

        Returns:
            Total number of interactions
        """
        if not self.neo4j_driver:
            return 0

        query = """
            MATCH (u:User {id: $user_id})-[:HAD_SESSION]->(s)-[o:OUTCOME]->()
            RETURN count(o) as count
        """

        async with self.neo4j_driver.session(database=self._database) as neo_session:
            result = await neo_session.run(query, user_id=user_id)
            record = await result.single()
            return record["count"] if record else 0


def create_outcome_recorder(neo4j_driver=None) -> OutcomeRecorder:
    """
    Factory function to create an OutcomeRecorder.

    Args:
        neo4j_driver: Neo4j driver instance

    Returns:
        Configured OutcomeRecorder
    """
    return OutcomeRecorder(neo4j_driver=neo4j_driver)
