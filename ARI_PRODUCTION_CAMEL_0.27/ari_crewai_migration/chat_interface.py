"""
Interactive Chat Interface for ARI Product Search
Run this script to test product search queries interactively.

Usage:
    python chat_interface.py

Example queries:
    - "black evening dress"
    - "summer casual shoes"
    - "elegant wedding gown"
    - "denim jacket"
"""
import asyncio
import sys
from datetime import datetime

from flows.product_search_flow import create_and_run_flow
from crews.mini_crews import (
    create_graph_search_crew,
    create_vector_search_crew,
    create_visual_search_crew,
    create_judge_crew
)


def print_header():
    """Print welcome header."""
    print("\n" + "="*70)
    print("🛍️  ARI Product Search - Interactive Chat Interface")
    print("="*70)
    print("\nWelcome! I can help you search for fashion products.")
    print("\nCommands:")
    print("  - Type your search query (e.g., 'black dress')")
    print("  - 'quit' or 'exit' to exit")
    print("  - 'help' for examples")
    print("="*70 + "\n")


def print_help():
    """Print example queries."""
    print("\n📚 Example Queries:")
    print("  - 'black evening dress'")
    print("  - 'red high heel shoes'")
    print("  - 'summer casual jacket'")
    print("  - 'elegant wedding gown'")
    print("  - 'blue denim jeans'")
    print("  - 'winter wool coat'\n")


def print_results(result, query, execution_time):
    """Print search results in a readable format."""
    print(f"\n{'='*70}")
    print(f"🔍 Query: '{query}'")
    print(f"⏱️  Execution Time: {execution_time:.2f}s")
    print(f"{'='*70}")

    if not result.products:
        print("\n❌ No products found. Try a different query.\n")
        return

    print(f"\n✅ Found {len(result.products)} products:\n")

    for i, product in enumerate(result.products, 1):
        print(f"{i}. {product.title}")
        print(f"   Price: ${product.price:.2f}")
        print(f"   Category: {product.category}")
        if product.brand:
            print(f"   Brand: {product.brand}")
        if product.colors:
            colors_str = ", ".join(product.colors)
            print(f"   Colors: {colors_str}")
        if product.in_stock:
            print(f"   In Stock: Yes")
        print()

    # Print source breakdown
    print(f"📊 Source Breakdown:")
    print(f"   Graph Search: {result.graph_count} products")
    print(f"   Vector Search: {result.vector_count} products")
    print(f"   Visual Search: {result.visual_count} products")
    print(f"   Consensus: {result.consensus_count} products")

    if result.quality_controlled:
        print(f"\n✨ Quality Controlled: Yes")
        if result.average_quality_score:
            print(f"   Average Quality Score: {result.average_quality_score:.2f}/10")

    if result.reasoning:
        print(f"\n💭 Reasoning:")
        # Truncate long reasoning
        reasoning = result.reasoning[:200] + "..." if len(result.reasoning) > 200 else result.reasoning
        print(f"   {reasoning}")

    print(f"\n{'='*70}\n")


async def process_query(query: str, crews: dict):
    """Process a single search query."""
    print(f"\n🔄 Searching for '{query}'...")
    print("   (This may take 30-60 seconds...)\n")

    start_time = datetime.now()

    try:
        result = await create_and_run_flow(
            query=query,
            limit=5,  # Return top 5 products
            graph_crew=crews['graph'],
            vector_crew=crews['vector'],
            visual_crew=crews['visual'],
            judge_crew=crews['judge']
        )

        execution_time = (datetime.now() - start_time).total_seconds()
        print_results(result, query, execution_time)

    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        print(f"\n❌ Error during search (after {execution_time:.2f}s):")
        print(f"   {str(e)}\n")
        print("   Please try again or check your database connections.\n")


async def chat_loop():
    """Main chat loop."""
    print_header()

    # Initialize crews once (reuse for all queries)
    print("🔧 Initializing search crews...")
    try:
        crews = {
            'graph': create_graph_search_crew(),
            'vector': create_vector_search_crew(),
            'visual': create_visual_search_crew(),
            'judge': create_judge_crew()
        }
        print("✅ Crews initialized successfully!\n")
    except Exception as e:
        print(f"❌ Failed to initialize crews: {e}")
        print("   Please check your configuration and database connections.\n")
        return

    # Chat loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            # Handle empty input
            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Thanks for using ARI Product Search! Goodbye!\n")
                break

            if user_input.lower() == 'help':
                print_help()
                continue

            # Process search query
            await process_query(user_input, crews)

        except KeyboardInterrupt:
            print("\n\n👋 Thanks for using ARI Product Search! Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}\n")
            continue


def main():
    """Entry point."""
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
