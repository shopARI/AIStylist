"""
Example: Using Mem0 Memory Provider in ARI
Demonstrates how to use episodic, semantic, and factual memory
in fashion recommendation conversations.
"""
import asyncio
import sys
import os

sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/ari_crewai_migration')

from memory.mem0_memory_provider import create_mem0_memory_provider


async def example_conversation_flow():
    """
    Example: Tracking a conversation with Mem0.
    Shows how episodic memory captures conversation turns.
    """
    print("\n=== EXAMPLE 1: Conversation Flow ===\n")

    user_id = "example_user_123"
    session_id = "session_2025_001"

    # Create memory provider
    mem0 = create_mem0_memory_provider(user_id, session_id)

    # Turn 1: User asks for casual outfits
    await mem0.add_episodic(
        "User asked: 'Show me casual outfits for everyday wear'",
        metadata={"turn": 1, "intent": "browse"}
    )

    # Turn 2: System shows products
    await mem0.add_episodic(
        "System showed 5 casual t-shirts and jeans combinations",
        metadata={"turn": 2, "products_shown": 5}
    )

    # Turn 3: User expresses interest
    await mem0.add_episodic(
        "User liked the minimalist white t-shirt from Brand X",
        metadata={"turn": 3, "product_id": "prod_123", "reaction": "liked"}
    )

    # Turn 4: User asks about price
    await mem0.add_episodic(
        "User asked: 'Do you have similar items under $30?'",
        metadata={"turn": 4, "intent": "budget_filter"}
    )

    # Retrieve recent conversation
    print("Recent conversation history:")
    history = await mem0.get_episodic(limit=4)
    for i, mem in enumerate(history, 1):
        print(f"  {i}. {mem['content']}")

    print("\n Episodic memory captures conversation flow")


async def example_user_preferences():
    """
    Example: Storing user preferences with Mem0.
    Shows how factual memory captures stable user data.
    """
    print("\n=== EXAMPLE 2: User Preferences ===\n")

    user_id = "example_user_123"
    session_id = "session_2025_001"

    mem0 = create_mem0_memory_provider(user_id, session_id)

    # Store factual preferences from onboarding
    await mem0.add_factual(
        "User prefers minimalist and casual style",
        category="style_preference"
    )

    await mem0.add_factual(
        "User's monthly budget: $200-$500",
        category="budget"
    )

    await mem0.add_factual(
        "User shops for work, casual, and weekend occasions",
        category="lifestyle"
    )

    await mem0.add_factual(
        "User values sustainability and quality over trends",
        category="values"
    )

    await mem0.add_factual(
        "User prefers fitted and tailored fits",
        category="fit_preference"
    )

    # Retrieve all preferences
    print("User's style preferences:")
    prefs = await mem0.get_factual(category="style_preference")
    for pref in prefs:
        print(f"  - {pref['content']}")

    print("\nUser's budget:")
    budget = await mem0.get_factual(category="budget")
    for b in budget:
        print(f"  - {b['content']}")

    print("\n Factual memory stores stable user preferences")


async def example_style_relationships():
    """
    Example: Building semantic relationships with Mem0.
    Shows how semantic memory captures concept relationships.
    """
    print("\n=== EXAMPLE 3: Style Relationships (Graph Memory) ===\n")

    user_id = "example_user_123"
    session_id = "session_2025_001"

    mem0 = create_mem0_memory_provider(user_id, session_id)

    # Add semantic relationships (Mem0 extracts entities and creates graph)
    await mem0.add_semantic(
        "User loves Brand X for their minimalist aesthetic",
        metadata={"entity_type": "brand", "entity_value": "Brand X"}
    )

    await mem0.add_semantic(
        "User associates white t-shirts with versatile everyday style",
        metadata={"entity_type": "product_category", "entity_value": "t-shirts"}
    )

    await mem0.add_semantic(
        "User prefers cotton and linen materials for comfort",
        metadata={"entity_type": "material", "entity_value": "cotton"}
    )

    await mem0.add_semantic(
        "User avoids fast fashion brands due to sustainability values",
        metadata={"entity_type": "value", "entity_value": "sustainability"}
    )

    # Search semantic relationships
    print("Style-related relationships:")
    results = await mem0.get_semantic(query="minimalist style brands", limit=3)
    for res in results:
        print(f"  - {res['content']} (relevance: {res['score']:.2f})")

    print("\nMaterial preferences:")
    results = await mem0.get_semantic(query="material comfort", limit=2)
    for res in results:
        print(f"  - {res['content']} (relevance: {res['score']:.2f})")

    print("\n Semantic memory captures relationships between concepts")
    print("  (Neo4j graph stores: User → likes → Brand X → has → minimalist aesthetic)")


async def example_contextual_search():
    """
    Example: Searching across all memory types.
    Shows how to find relevant context for personalization.
    """
    print("\n=== EXAMPLE 4: Contextual Search ===\n")

    user_id = "example_user_123"
    session_id = "session_2025_001"

    mem0 = create_mem0_memory_provider(user_id, session_id)

    # New user query: "Show me sustainable brands"
    query = "sustainable brands"

    print(f"User query: '{query}'")
    print("\nSearching all memories for context...\n")

    results = await mem0.search_all(query=query, limit=3)

    print("FACTUAL memories (stable preferences):")
    for mem in results["factual"]:
        print(f"  - {mem['content']} (score: {mem['score']:.2f})")

    print("\nEPISODIC memories (past interactions):")
    for mem in results["episodic"]:
        print(f"  - {mem['content']} (score: {mem['score']:.2f})")

    print("\nSEMANTIC memories (concept relationships):")
    for mem in results["semantic"]:
        print(f"  - {mem['content']} (score: {mem['score']:.2f})")

    print("\n Unified search finds relevant context across all memory types")
    print("  → Agent can now recommend sustainable brands aligned with user values")


async def example_integration_with_product_search():
    """
    Example: Using Mem0 in product recommendation flow.
    Shows how memories enhance personalization.
    """
    print("\n=== EXAMPLE 5: Integration with Product Search ===\n")

    user_id = "example_user_123"
    session_id = "session_2025_001"

    mem0 = create_mem0_memory_provider(user_id, session_id)

    # Simulated product search flow
    user_query = "casual white t-shirt"

    print(f"User query: '{user_query}'")
    print("\nStep 1: Retrieve user context from Mem0...")

    # Get budget constraints
    budget_facts = await mem0.get_factual(category="budget")
    if budget_facts:
        print(f"  Budget: {budget_facts[0]['content']}")

    # Get style preferences
    style_facts = await mem0.get_factual(category="style_preference")
    if style_facts:
        print(f"  Style: {style_facts[0]['content']}")

    # Get relevant past interactions
    past_interactions = await mem0.get_episodic(query="white t-shirt", limit=2)
    if past_interactions:
        print(f"  Past: {past_interactions[0]['content']}")

    # Get semantic relationships
    brand_preferences = await mem0.get_semantic(query="brand preferences", limit=2)
    if brand_preferences:
        print(f"  Brands: {brand_preferences[0]['content']}")

    print("\nStep 2: Use context for personalized search...")
    print("  → Filter: Price $200-$500 (from factual memory)")
    print("  → Prioritize: Minimalist brands (from semantic memory)")
    print("  → Consider: User liked similar item before (from episodic memory)")

    print("\nStep 3: After showing results, update memories...")

    # Track this interaction
    await mem0.add_episodic(
        "User searched for casual white t-shirts",
        metadata={"query": user_query, "timestamp": "2025-01-15T10:30:00"}
    )

    # If user interacts with specific brand
    await mem0.add_semantic(
        "User showed interest in Brand Y's sustainable t-shirts",
        metadata={"brand": "Brand Y", "category": "t-shirts"}
    )

    print("\n Mem0 provides context for personalization and learns from interactions")


async def run_all_examples():
    """Run all examples."""
    await example_conversation_flow()
    await example_user_preferences()
    await example_style_relationships()
    await example_contextual_search()
    await example_integration_with_product_search()

    print("\n" + "=" * 60)
    print("SUMMARY: Mem0 Memory Types in ARI")
    print("=" * 60)
    print("\n1. EPISODIC Memory:")
    print("   - Conversation turns and interactions")
    print("   - Search history and product views")
    print("   - Purchase events and feedback")
    print("   → Use for: Recent context, conversation continuity")

    print("\n2. FACTUAL Memory:")
    print("   - Style preferences and adjectives")
    print("   - Budget and size preferences")
    print("   - Values and shopping behavior")
    print("   → Use for: Filtering and personalization constraints")

    print("\n3. SEMANTIC Memory (Graph):")
    print("   - User ↔ Brand relationships")
    print("   - Style ↔ Occasion associations")
    print("   - Value ↔ Shopping behavior links")
    print("   → Use for: Deep understanding and reasoning")

    print("\n" + "=" * 60)
    print("\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Mem0 Memory Provider - Usage Examples")
    print("=" * 60)

    asyncio.run(run_all_examples())
