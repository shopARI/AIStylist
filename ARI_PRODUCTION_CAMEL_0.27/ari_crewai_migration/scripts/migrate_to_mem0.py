"""
Migration Script: Neo4j User Data → Mem0 Memory
Populates Mem0 factual and semantic memories from existing Neo4j user graph.
"""
import asyncio
import sys
import os

sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration')
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

from services.user_service import UserService
from memory.mem0_memory_provider import create_mem0_memory_provider
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_user_to_mem0(user_id: str, user_service: UserService):
    """
    Migrate single user's data from Neo4j to Mem0.

    Args:
        user_id: User ID
        user_service: UserService instance
    """
    logger.info(f"Migrating user {user_id} to Mem0...")

    # Create Mem0 provider for this user
    session_id = f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    mem0 = create_mem0_memory_provider(user_id, session_id)

    # Get user profile
    profile = user_service.get_user_profile(user_id)
    if not profile:
        logger.warning(f"No profile found for user {user_id}")
        return

    user = profile.user

    # ======================
    # FACTUAL MEMORIES (Stable User Data)
    # ======================

    factual_count = 0

    # Basic info
    if user.email:
        await mem0.add_factual(f"User email: {user.email}", category="account")
        factual_count += 1

    if user.username:
        await mem0.add_factual(f"Username: {user.username}", category="account")
        factual_count += 1

    if user.age_range:
        await mem0.add_factual(f"Age range: {user.age_range}", category="demographics")
        factual_count += 1

    if user.location:
        await mem0.add_factual(f"Location: {user.location}", category="demographics")
        factual_count += 1

    # Style preferences
    if profile.style_adjectives:
        adjectives = ", ".join([adj.name for adj in profile.style_adjectives])
        await mem0.add_factual(f"Preferred style adjectives: {adjectives}", category="style_preference")
        factual_count += 1

    if profile.fit_preferences:
        fits = ", ".join(profile.fit_preferences)
        await mem0.add_factual(f"Preferred fits: {fits}", category="style_preference")
        factual_count += 1

    if profile.occasions:
        occasions = ", ".join([occ.name for occ in profile.occasions])
        await mem0.add_factual(f"Typical occasions: {occasions}", category="lifestyle")
        factual_count += 1

    if profile.values:
        values = ", ".join([val.name for val in profile.values])
        await mem0.add_factual(f"Shopping values: {values}", category="values")
        factual_count += 1

    # Budget
    if user.monthly_budget_min and user.monthly_budget_max:
        await mem0.add_factual(
            f"Monthly budget range: ${user.monthly_budget_min}-${user.monthly_budget_max}",
            category="budget"
        )
        factual_count += 1

    # Decision-making style
    if user.decision_making_style:
        await mem0.add_factual(
            f"Decision-making style: {user.decision_making_style}",
            category="preferences"
        )
        factual_count += 1

    if user.stated_risk_tolerance:
        await mem0.add_factual(
            f"Risk tolerance: {user.stated_risk_tolerance}/10",
            category="preferences"
        )
        factual_count += 1

    if user.stated_expression_spectrum:
        await mem0.add_factual(
            f"Style expression spectrum: {user.stated_expression_spectrum}/10",
            category="preferences"
        )
        factual_count += 1

    # Shopping behavior
    if user.shopping_behavior:
        await mem0.add_factual(
            f"Shopping behavior: {user.shopping_behavior}",
            category="behavior"
        )
        factual_count += 1

    # Aspiration
    if user.aspiration_text:
        await mem0.add_factual(
            f"Style aspiration: {user.aspiration_text}",
            category="goals"
        )
        factual_count += 1

    # ======================
    # SEMANTIC MEMORIES (Relationships)
    # ======================

    semantic_count = 0

    # Style adjective relationships
    for adj in profile.style_adjectives:
        await mem0.add_semantic(
            f"User identifies with {adj.name} aesthetic",
            metadata={"entity_type": "style", "entity_value": adj.name}
        )
        semantic_count += 1

    # Occasion-style relationships
    for occasion in profile.occasions:
        if profile.style_adjectives:
            primary_style = profile.style_adjectives[0].name
            await mem0.add_semantic(
                f"User wears {primary_style} style for {occasion.name} occasions",
                metadata={"entity_type": "occasion", "entity_value": occasion.name}
            )
            semantic_count += 1

    # Value-preference relationships
    for value in profile.values:
        await mem0.add_semantic(
            f"User prioritizes {value.name} when shopping",
            metadata={"entity_type": "value", "entity_value": value.name}
        )
        semantic_count += 1

    # Budget-category relationships (inferred)
    if user.monthly_budget_max:
        if user.monthly_budget_max < 200:
            await mem0.add_semantic("User shops in budget-friendly categories")
        elif user.monthly_budget_max > 1000:
            await mem0.add_semantic("User comfortable with premium and luxury items")
        semantic_count += 1

    logger.info(f"  Migrated {factual_count} factual memories")
    logger.info(f"  Migrated {semantic_count} semantic memories")

    # ======================
    # EPISODIC MEMORIES (Past Interactions)
    # ======================

    # Get user stats for episodic context
    stats = user_service.get_user_stats(user_id)

    episodic_count = 0

    if stats.get('total_searches', 0) > 0:
        await mem0.add_episodic(
            f"User has performed {stats['total_searches']} searches",
            metadata={"interaction_type": "search", "count": stats['total_searches']}
        )
        episodic_count += 1

    if stats.get('total_products_viewed', 0) > 0:
        await mem0.add_episodic(
            f"User has viewed {stats['total_products_viewed']} products",
            metadata={"interaction_type": "view", "count": stats['total_products_viewed']}
        )
        episodic_count += 1

    if stats.get('total_purchases', 0) > 0:
        await mem0.add_episodic(
            f"User has made {stats['total_purchases']} purchases",
            metadata={"interaction_type": "purchase", "count": stats['total_purchases']}
        )
        episodic_count += 1

    # Onboarding completion
    if user.onboarding_completed and user.onboarding_completed_at:
        await mem0.add_episodic(
            f"Completed onboarding on {user.onboarding_completed_at.strftime('%Y-%m-%d')}",
            metadata={"milestone": "onboarding"}
        )
        episodic_count += 1

    logger.info(f"  Migrated {episodic_count} episodic memories")
    logger.info(f"  Total: {factual_count + semantic_count + episodic_count} memories")


async def migrate_all_users():
    """Migrate all users from Neo4j to Mem0."""
    logger.info("Starting Neo4j → Mem0 migration...")

    user_service = UserService()

    try:
        # Get all users from Neo4j
        # Note: UserService doesn't have get_all_users, so we'll need to add that
        # For now, migrate specific users

        # Example: Migrate user by username
        test_user = user_service.get_user_by_username("zozo")

        if test_user:
            await migrate_user_to_mem0(test_user.id, user_service)
        else:
            logger.warning("No test user found")

        logger.info("Migration complete!")

    finally:
        user_service.close()


async def test_mem0_retrieval(user_id: str):
    """
    Test retrieving memories from Mem0.

    Args:
        user_id: User ID to test
    """
    logger.info(f"\nTesting Mem0 retrieval for user {user_id}...")

    mem0 = create_mem0_memory_provider(user_id, "test_session")

    # Test factual memory
    logger.info("\nFactual Memories (Preferences):")
    factual = await mem0.get_factual(category="style_preference")
    for mem in factual[:3]:
        logger.info(f"  - {mem['content']}")

    # Test semantic search
    logger.info("\nSemantic Memories (style-related):")
    semantic = await mem0.get_semantic(query="style aesthetic", limit=3)
    for mem in semantic:
        logger.info(f"  - {mem['content']} (score: {mem['score']:.2f})")

    # Test episodic
    logger.info("\nEpisodic Memories (recent activity):")
    episodic = await mem0.get_episodic(limit=3)
    for mem in episodic:
        logger.info(f"  - {mem['content']}")

    # Test unified search
    logger.info("\nUnified Search (query: 'budget shopping'):")
    results = await mem0.search_all(query="budget shopping", limit=2)
    for mem_type, memories in results.items():
        if memories:
            logger.info(f"  {mem_type.upper()}:")
            for mem in memories:
                logger.info(f"    - {mem['content']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Neo4j user data to Mem0")
    parser.add_argument("--test-only", action="store_true", help="Only test retrieval, don't migrate")
    parser.add_argument("--user-id", help="Specific user ID to test")

    args = parser.parse_args()

    if args.test_only and args.user_id:
        asyncio.run(test_mem0_retrieval(args.user_id))
    else:
        asyncio.run(migrate_all_users())
