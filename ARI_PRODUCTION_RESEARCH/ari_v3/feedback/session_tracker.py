"""
ARI V3 - Step 9: Session Tracker

Tracks recommendation sessions in Neo4j for feedback loop analysis.
Creates RecommendationSession nodes with links to users and products.

Based on: ARI_Navigation_Intelligence_PSEUDOCODE_V3.md Section 8
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ari_v3.navigation.navigation_context import NavigationContext
    from ari_v3.narrative import JourneyNarrative

logger = logging.getLogger(__name__)


@dataclass
class SessionProduct:
    """Product shown in a recommendation session."""
    product_id: str
    relevance_score: float = 0.0
    position: int = 0  # Position in result list (1-indexed)


@dataclass
class RecommendationSession:
    """
    Complete recommendation session record.

    Stores all context needed for feedback analysis.
    """
    session_id: str
    user_id: str
    timestamp: datetime

    # Query context
    query: str
    occasion: Optional[str] = None
    active_context: Optional[str] = None

    # Synthesis output
    style_descriptors: List[str] = field(default_factory=list)
    destination_embedding: Optional[List[float]] = None
    understood_intent: Optional[str] = None
    formality_level: Optional[float] = None

    # Navigation parameters snapshot
    exploration_appetite: Optional[float] = None
    step_size_multiplier: Optional[float] = None
    diversity_requirement: Optional[float] = None
    result_set_size: Optional[int] = None

    # Results
    products_shown: List[SessionProduct] = field(default_factory=list)
    agents_used: List[str] = field(default_factory=list)
    narrative_generated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Neo4j storage."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "query": self.query,
            "occasion": self.occasion,
            "active_context": self.active_context,
            "style_descriptors": self.style_descriptors,
            "destination_embedding": self.destination_embedding,
            "understood_intent": self.understood_intent,
            "formality_level": self.formality_level,
            "exploration_appetite": self.exploration_appetite,
            "step_size_multiplier": self.step_size_multiplier,
            "diversity_requirement": self.diversity_requirement,
            "result_set_size": self.result_set_size,
            "product_ids": [p.product_id for p in self.products_shown],
            "product_scores": [p.relevance_score for p in self.products_shown],
            "agents_used": self.agents_used,
            "narrative_generated": self.narrative_generated,
        }


class SessionTracker:
    """
    Tracks recommendation sessions in Neo4j.

    Creates RecommendationSession nodes with relationships to:
    - User (via [:HAD_SESSION])
    - Products shown (via [:SHOWED])
    """

    def __init__(self, neo4j_driver=None):
        """
        Initialize the session tracker.

        Args:
            neo4j_driver: Neo4j driver instance (optional, can use env vars)
        """
        self.neo4j_driver = neo4j_driver
        self._database = "users"  # User graph database

    async def track_session(
        self,
        user_id: str,
        nav_context: NavigationContext,
        products_shown: List[Any],
        agents_used: Optional[List[str]] = None,
        narrative: Optional[JourneyNarrative] = None,
    ) -> str:
        """
        Create a tracking record for a recommendation session.

        Args:
            user_id: User identifier
            nav_context: Navigation context from the search
            products_shown: List of products shown to user
            agents_used: List of agent names used (VibeBot, VisionBot, etc.)
            narrative: Generated journey narrative (if any)

        Returns:
            session_id: UUID of the created session
        """
        if not user_id:
            raise ValueError("user_id cannot be empty")

        session_id = str(uuid.uuid4())
        timestamp = datetime.now()

        # Extract navigation context data safely
        query = nav_context.query if nav_context else ""
        occasion = nav_context.occasion if nav_context else None

        # Extract active context
        active_context = None
        if nav_context and nav_context.computed_state:
            if nav_context.computed_state.active_context:
                ctx = nav_context.computed_state.active_context
                # Handle both Enum and string values
                active_context = ctx.value if hasattr(ctx, 'value') else str(ctx)

        # Extract synthesis data
        style_descriptors = []
        understood_intent = None
        formality_level = None
        if nav_context and nav_context.synthesis:
            style_descriptors = nav_context.synthesis.style_descriptors or []
            understood_intent = nav_context.synthesis.understood_intent
            formality_level = nav_context.synthesis.formality_level

        # Extract destination embedding
        destination_embedding = None
        if nav_context and nav_context.destination:
            if nav_context.destination.embedding is not None:
                emb = nav_context.destination.embedding
                # Convert to list if numpy array
                destination_embedding = emb.tolist() if hasattr(emb, 'tolist') else list(emb)

        # Extract nav params
        exploration_appetite = None
        step_size_multiplier = None
        diversity_requirement = None
        result_set_size = None
        if nav_context and nav_context.computed_state and nav_context.computed_state.nav_params:
            params = nav_context.computed_state.nav_params
            exploration_appetite = params.exploration_appetite
            step_size_multiplier = params.step_size_multiplier
            diversity_requirement = params.diversity_requirement
            result_set_size = params.result_set_size

        # Build product list
        session_products = []
        for idx, product in enumerate(products_shown or []):
            product_id = self._extract_product_id(product)
            if product_id:
                score = self._extract_product_score(product)
                session_products.append(SessionProduct(
                    product_id=product_id,
                    relevance_score=score,
                    position=idx + 1,
                ))

        # Create session record
        session = RecommendationSession(
            session_id=session_id,
            user_id=user_id,
            timestamp=timestamp,
            query=query,
            occasion=occasion,
            active_context=active_context,
            style_descriptors=style_descriptors,
            destination_embedding=destination_embedding,
            understood_intent=understood_intent,
            formality_level=formality_level,
            exploration_appetite=exploration_appetite,
            step_size_multiplier=step_size_multiplier,
            diversity_requirement=diversity_requirement,
            result_set_size=result_set_size,
            products_shown=session_products,
            agents_used=agents_used or [],
            narrative_generated=narrative is not None,
        )

        # Store in Neo4j if driver available
        if self.neo4j_driver:
            await self._store_session_neo4j(session)
        else:
            logger.warning("No Neo4j driver configured, session not persisted")

        # Log with truncated user_id for privacy
        user_id_short = user_id[:8] + "..." if len(user_id) > 8 else user_id
        query_short = query[:30] + "..." if len(query) > 30 else query
        logger.info(
            f"Tracked session {session_id[:8]}... for user {user_id_short}: "
            f"{len(session_products)} products, query='{query_short}'"
        )

        return session_id

    async def _store_session_neo4j(self, session: RecommendationSession) -> None:
        """
        Store session in Neo4j.

        Creates RecommendationSession node and relationships.
        """
        if not self.neo4j_driver:
            return

        # Prepare data for Neo4j
        session_data = session.to_dict()
        product_ids = session_data.pop("product_ids", [])
        product_scores = session_data.pop("product_scores", [])

        # Create session node and link to user
        cypher = """
            // Create session node
            CREATE (s:RecommendationSession {
                id: $session_id,
                user_id: $user_id,
                timestamp: datetime($timestamp),
                query: $search_query,
                occasion: $occasion,
                active_context: $active_context,
                style_descriptors: $style_descriptors,
                understood_intent: $understood_intent,
                formality_level: $formality_level,
                exploration_appetite: $exploration_appetite,
                step_size_multiplier: $step_size_multiplier,
                diversity_requirement: $diversity_requirement,
                result_set_size: $result_set_size,
                agents_used: $agents_used,
                narrative_generated: $narrative_generated
            })

            // Link to user (MERGE ensures user exists)
            WITH s
            MERGE (u:User {id: $user_id})
            CREATE (u)-[:HAD_SESSION]->(s)

            RETURN s.id as session_id
        """

        async with self.neo4j_driver.session(database=self._database) as neo_session:
            await neo_session.run(
                cypher,
                session_id=session.session_id,
                user_id=session.user_id,
                timestamp=session.timestamp.isoformat() if session.timestamp else None,
                search_query=session.query,
                occasion=session.occasion,
                active_context=session.active_context,
                style_descriptors=session.style_descriptors,
                understood_intent=session.understood_intent,
                formality_level=session.formality_level,
                exploration_appetite=session.exploration_appetite,
                step_size_multiplier=session.step_size_multiplier,
                diversity_requirement=session.diversity_requirement,
                result_set_size=session.result_set_size,
                agents_used=session.agents_used,
                narrative_generated=session.narrative_generated,
            )

            # Link to products shown
            if product_ids:
                product_query = """
                    MATCH (s:RecommendationSession {id: $session_id})
                    UNWIND range(0, size($product_ids) - 1) as idx
                    WITH s, $product_ids[idx] as pid, $product_scores[idx] as score, idx + 1 as position
                    MERGE (p:ProductRef {product_id: pid})
                    CREATE (s)-[:SHOWED {
                        position: position,
                        relevance_score: score
                    }]->(p)
                """
                await neo_session.run(
                    product_query,
                    session_id=session.session_id,
                    product_ids=product_ids,
                    product_scores=product_scores,
                )

    async def get_session(self, session_id: str) -> Optional[RecommendationSession]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session UUID

        Returns:
            RecommendationSession or None if not found
        """
        if not self.neo4j_driver:
            logger.warning("No Neo4j driver configured")
            return None

        query = """
            MATCH (s:RecommendationSession {id: $session_id})
            OPTIONAL MATCH (s)-[showed:SHOWED]->(p:ProductRef)
            RETURN s, collect({
                product_id: p.product_id,
                relevance_score: showed.relevance_score,
                position: showed.position
            }) as products
        """

        async with self.neo4j_driver.session(database=self._database) as neo_session:
            result = await neo_session.run(query, session_id=session_id)
            record = await result.single()

            if not record:
                return None

            session_node = record["s"]
            products_data = record["products"]

            # Build session products
            session_products = []
            for p in products_data:
                if p.get("product_id"):
                    session_products.append(SessionProduct(
                        product_id=p["product_id"],
                        relevance_score=p.get("relevance_score") or 0.0,
                        position=p.get("position") or 0,
                    ))

            # Sort by position
            session_products.sort(key=lambda x: x.position)

            return RecommendationSession(
                session_id=session_node["id"],
                user_id=session_node["user_id"],
                timestamp=session_node["timestamp"].to_native() if session_node.get("timestamp") else datetime.now(),
                query=session_node.get("query") or "",
                occasion=session_node.get("occasion"),
                active_context=session_node.get("active_context"),
                style_descriptors=session_node.get("style_descriptors") or [],
                understood_intent=session_node.get("understood_intent"),
                formality_level=session_node.get("formality_level"),
                exploration_appetite=session_node.get("exploration_appetite"),
                step_size_multiplier=session_node.get("step_size_multiplier"),
                diversity_requirement=session_node.get("diversity_requirement"),
                result_set_size=session_node.get("result_set_size"),
                products_shown=session_products,
                agents_used=session_node.get("agents_used") or [],
                narrative_generated=session_node.get("narrative_generated") or False,
            )

    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RecommendationSession]:
        """
        Get all sessions for a user.

        Args:
            user_id: User identifier
            limit: Maximum sessions to return
            offset: Number of sessions to skip

        Returns:
            List of RecommendationSession objects
        """
        if not self.neo4j_driver:
            logger.warning("No Neo4j driver configured")
            return []

        query = """
            MATCH (u:User {id: $user_id})-[:HAD_SESSION]->(s:RecommendationSession)
            RETURN s
            ORDER BY s.timestamp DESC
            SKIP $offset
            LIMIT $limit
        """

        async with self.neo4j_driver.session(database=self._database) as neo_session:
            result = await neo_session.run(
                query,
                user_id=user_id,
                limit=limit,
                offset=offset,
            )
            records = await result.data()

            sessions = []
            for record in records:
                session_node = record["s"]
                sessions.append(RecommendationSession(
                    session_id=session_node["id"],
                    user_id=session_node["user_id"],
                    timestamp=session_node["timestamp"].to_native() if session_node.get("timestamp") else datetime.now(),
                    query=session_node.get("query") or "",
                    occasion=session_node.get("occasion"),
                    active_context=session_node.get("active_context"),
                    style_descriptors=session_node.get("style_descriptors") or [],
                    agents_used=session_node.get("agents_used") or [],
                    narrative_generated=session_node.get("narrative_generated") or False,
                ))

            return sessions

    def _extract_product_id(self, product: Any) -> Optional[str]:
        """Extract product ID from various product formats."""
        if product is None:
            return None
        if isinstance(product, str):
            return product
        if isinstance(product, dict):
            return product.get("id") or product.get("product_id")
        if hasattr(product, "id"):
            return product.id
        if hasattr(product, "product_id"):
            return product.product_id
        return None

    def _extract_product_score(self, product: Any) -> float:
        """Extract relevance score from product."""
        if product is None:
            return 0.0
        if isinstance(product, dict):
            score = product.get("relevance_score")
            return float(score) if score is not None else 0.0
        if hasattr(product, "relevance_score") and product.relevance_score is not None:
            return float(product.relevance_score)
        if hasattr(product, "score") and product.score is not None:
            return float(product.score)
        return 0.0


def create_session_tracker(neo4j_driver=None) -> SessionTracker:
    """
    Factory function to create a SessionTracker.

    Args:
        neo4j_driver: Neo4j driver instance

    Returns:
        Configured SessionTracker
    """
    return SessionTracker(neo4j_driver=neo4j_driver)
