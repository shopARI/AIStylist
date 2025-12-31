#!/usr/bin/env python3
"""
CrewAI Agent Chat Interface
Interactive chat to test the complete CrewAI migration system:
- Intent Detection (CrewAI agents + pattern fallback)
- ML Intelligence Integration
- 4 Agents (CypherBot, VibeBot, VisionBot, Judge ARI)
- Orchestrator Routing
- Conversation Handling
"""

import asyncio
import os
import sys
import time
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from pathlib import Path

# Add paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')

# Load environment variables FIRST
load_dotenv('/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)

# Suppress noisy logs
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('crewai').setLevel(logging.WARNING)


class CrewAIAgentChat:
    """Interactive chat interface for testing CrewAI migration system."""

    def __init__(self):
        self.session_id = f"crewai_chat_{int(time.time())}"
        self.user_id = "test_user"
        self.conversation_count = 0

        # System components
        self.orchestrator = None
        self.system_ready = False

    async def initialize_system(self):
        """Initialize the CrewAI orchestrator with all components."""
        print("="*80)
        print("INITIALIZING CREWAI MIGRATION SYSTEM")
        print("="*80)
        print()

        try:
            from crews.crewai_orchestrator import create_crewai_orchestrator
            from nlp.hybrid_intent_detector import DetectionStrategy

            # Try to import ML Intelligence (may not be available)
            try:
                sys.path.insert(0, '/home/leo/AIStylist/ARI_PRODUCTION_CAMEL_0.27')
                from services.ml.intelligence.coordinator import IntelligenceCoordinator
                intelligence_coordinator = IntelligenceCoordinator()
                print("ML Intelligence Coordinator: LOADED")
            except Exception as e:
                intelligence_coordinator = None
                print(f"ML Intelligence Coordinator: UNAVAILABLE ({e})")

            print()
            print("Creating CrewAI Orchestrator...")
            print("   Strategy: LLM_FIRST (CrewAI agents with pattern fallback)")
            print("   Process Type: Sequential (fixed infinite loop)")
            print("   ML Intelligence: ENABLED" if intelligence_coordinator else "   ML Intelligence: DISABLED")
            print()

            # Create orchestrator with LLM_FIRST strategy and sequential mode
            self.orchestrator = create_crewai_orchestrator(
                process_type="sequential",  # Changed from hierarchical to fix infinite loop
                intent_strategy=DetectionStrategy.LLM_FIRST,
                intelligence_coordinator=intelligence_coordinator,
                enable_ml_intelligence=True
            )

            print("SYSTEM COMPONENTS READY:")
            print("   Intent Detection: CrewAI Agent (Fashion Intent Analyst)")
            print("   Fallback: Pattern-based detection (confidence < 0.7)")
            print("   4 Agents:")
            print("      - CypherBot: Neo4j graph specialist")
            print("      - VibeBot: Qdrant vector search expert")
            print("      - VisionBot: FashionSigLIP visual similarity")
            print("      - Judge ARI: Quality evaluator & curator")
            print("   Orchestrator: Hierarchical CrewAI process")
            print("   Conversation Handling: 5 intent types")
            print()

            self.system_ready = True
            return True

        except Exception as e:
            print(f"CRITICAL FAILURE: Could not initialize CrewAI system")
            print(f"   Error: {e}")
            print()
            print("   Please check:")
            print("   - OpenAI API key is configured")
            print("   - CrewAI is installed (crewai>=0.203.1)")
            print("   - Neo4j database is accessible")
            print("   - Qdrant database is accessible")
            print()
            import traceback
            traceback.print_exc()
            self.system_ready = False
            return False

    async def process_message(self, message: str) -> tuple[str, Dict[str, Any]]:
        """Process message through CrewAI orchestrator."""
        if not self.orchestrator:
            return "System not initialized", {}

        try:
            print()
            print("="*80)
            print(f"PROCESSING QUERY: '{message}'")
            print("="*80)

            # Execute search through orchestrator
            start_time = time.time()
            result = await self.orchestrator.execute_search(
                query=message,
                limit=5,
                user_context={
                    "user_id": self.user_id,
                    "session_id": self.session_id
                },
                conversation_context={
                    "session_id": self.session_id,
                    "turn": self.conversation_count + 1
                }
            )
            processing_time = time.time() - start_time

            print()
            print(f"Processing completed in {processing_time:.2f}s")
            print("="*80)

            # Extract response
            if result.get("metadata", {}).get("is_conversation"):
                # Conversation response
                response_text = result.get("response", "No response")
                products = []
            else:
                # Product search response
                products = result.get("products", [])
                response_text = result.get("reasoning", "Found products")

                if products:
                    response_text += f"\n\nFound {len(products)} products:"
                    for i, product in enumerate(products[:3], 1):
                        name = product.get("name", "Unknown")
                        price = product.get("price", "N/A")
                        response_text += f"\n{i}. {name} - ${price}"

                    if len(products) > 3:
                        response_text += f"\n... and {len(products) - 3} more"

            # Build metadata
            metadata = {
                "processing_time": processing_time,
                "products_found": len(products),
                "intent": result.get("intent", {}),
                "is_conversation": result.get("metadata", {}).get("is_conversation", False),
                "orchestration_method": result.get("orchestration_method", "unknown"),
                "execution_time": result.get("execution_time", 0)
            }

            return response_text, metadata

        except Exception as e:
            print(f"Error processing message: {e}")
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}", {}

    def display_response(self, user_message: str, ari_response: str, metadata: Dict[str, Any]):
        """Display the response with detailed metadata."""
        print()
        print("="*80)
        print(f"YOU: {user_message}")
        print("="*80)
        print(f"ARI: {ari_response}")
        print("="*80)

        # Show detailed metadata
        if metadata:
            print()
            print("SYSTEM DETAILS:")

            # Intent information
            if "intent" in metadata and metadata["intent"]:
                intent_data = metadata["intent"]
                print(f"   Intent Detection:")
                print(f"      Type: {intent_data.get('primary_intent', 'unknown')}")
                print(f"      Confidence: {intent_data.get('confidence', 0):.2f}")
                print(f"      Method: {intent_data.get('detection_method', 'unknown')}")
                print(f"      Detection Time: {intent_data.get('detection_time', 0)*1000:.0f}ms")

                # Extracted parameters
                params = intent_data.get('parameters', {})
                if params:
                    print(f"      Extracted Parameters:")
                    for key, value in params.items():
                        if value:
                            print(f"         {key}: {value}")

            # Processing metrics
            print(f"   Performance:")
            print(f"      Total Time: {metadata.get('processing_time', 0):.2f}s")
            print(f"      Execution Time: {metadata.get('execution_time', 0):.2f}s")

            # Results
            if metadata.get("is_conversation"):
                print(f"   Response Type: CONVERSATION")
            else:
                print(f"   Response Type: PRODUCT SEARCH")
                print(f"   Products Found: {metadata.get('products_found', 0)}")

            print(f"   Orchestration: {metadata.get('orchestration_method', 'unknown')}")

        print("="*80)
        print()

    async def show_system_status(self):
        """Show detailed system status."""
        print()
        print("="*80)
        print("CREWAI SYSTEM STATUS")
        print("="*80)
        print()
        print(f"System Ready: {'YES' if self.system_ready else 'NO'}")
        print(f"Session ID: {self.session_id}")
        print(f"Messages Processed: {self.conversation_count}")
        print()

        if self.orchestrator:
            try:
                stats = await self.orchestrator.get_stats()

                print("ORCHESTRATOR STATS:")
                print(f"   Type: {stats.get('orchestrator_type', 'unknown')}")
                print(f"   Process: {stats.get('process_type', 'unknown')}")
                print()

                # Routing stats
                if "routing" in stats:
                    routing = stats["routing"]
                    print("ROUTING STATS:")
                    print(f"   Total Queries: {routing.get('total_queries', 0)}")
                    print(f"   Product Intents: {routing.get('product_intents', 0)}")
                    print(f"   Conversation Intents: {routing.get('conversation_intents', 0)}")
                    if routing.get('avg_intent_detection_time'):
                        print(f"   Avg Intent Detection: {routing['avg_intent_detection_time']}")
                    if routing.get('ml_intelligence_generated'):
                        print(f"   ML Intelligence Generated: {routing['ml_intelligence_generated']}")
                    print()

                # Intent detection stats
                if "intent_detection" in stats:
                    intent_stats = stats["intent_detection"]
                    print("INTENT DETECTION STATS:")
                    print(f"   Total Queries: {intent_stats.get('total_queries', 0)}")
                    print(f"   CrewAI Used: {intent_stats.get('crewai_used', 0)}")
                    print(f"   Pattern Used: {intent_stats.get('hardcoded_used', 0)}")
                    print(f"   Fallbacks: {intent_stats.get('fallbacks', 0)}")
                    print(f"   Strategy: {intent_stats.get('strategy', 'unknown')}")
                    print(f"   CrewAI Available: {intent_stats.get('crewai_available', False)}")
                    print()

                # Agent info
                if stats.get('crew_agents'):
                    print(f"CREW AGENTS: {stats['crew_agents']} agents")
                if stats.get('crew_tasks'):
                    print(f"CREW TASKS: {stats['crew_tasks']} tasks")

            except Exception as e:
                print(f"Error getting stats: {e}")

        print("="*80)
        print()

    async def run_chat(self):
        """Run the interactive chat interface."""
        print("="*80)
        print("CREWAI AGENT CHAT - INTERACTIVE TEST INTERFACE")
        print("="*80)
        print()

        # Initialize system
        if not await self.initialize_system():
            print("Failed to initialize system. Exiting...")
            return

        print("="*80)
        print("READY! Test the complete CrewAI migration system.")
        print("="*80)
        print()
        print("Try these queries:")
        print("   PRODUCT QUERIES:")
        print("   - 'black shirt for interview'")
        print("   - 'red dress for wedding'")
        print("   - 'gift for my mom'")
        print("   - 'what's on sale'")
        print()
        print("   CONVERSATION QUERIES:")
        print("   - 'what did I ask earlier'")
        print("   - 'do you remember my size'")
        print("   - 'how do you work'")
        print("   - 'what day is it'")
        print()
        print("COMMANDS:")
        print("   'status' - Show system status and statistics")
        print("   'test' - Run quick test queries")
        print("   'quit' - Exit the chat")
        print()
        print("="*80)
        print()

        # Chat loop
        while True:
            try:
                # Get user input
                message = input("You: ").strip()

                if not message:
                    continue

                # Handle commands
                if message.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                    print()
                    print("Thanks for testing the CrewAI system! Goodbye!")
                    print()
                    break

                if message.lower() == 'status':
                    await self.show_system_status()
                    continue

                if message.lower() == 'test':
                    print()
                    print("Running quick test queries...")
                    test_queries = [
                        "black shirt for interview",
                        "gift for mom",
                        "what did I ask earlier",
                    ]
                    for test_query in test_queries:
                        print()
                        print(f"Testing: '{test_query}'")
                        response, metadata = await self.process_message(test_query)
                        self.conversation_count += 1
                        self.display_response(test_query, response, metadata)
                        await asyncio.sleep(1)
                    continue

                # Process message through CrewAI orchestrator
                response, metadata = await self.process_message(message)

                # Increment conversation count
                self.conversation_count += 1

                # Display response
                self.display_response(message, response, metadata)

            except KeyboardInterrupt:
                print()
                print()
                print("Chat interrupted. Goodbye!")
                print()
                break
            except EOFError:
                print()
                print()
                print("Input stream ended. Goodbye!")
                print()
                break
            except Exception as e:
                print()
                print(f"Unexpected error: {e}")
                print("Continuing...")
                print()
                import traceback
                traceback.print_exc()
                continue


async def main():
    """Main entry point."""
    try:
        chat = CrewAIAgentChat()
        await chat.run_chat()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print()
    print("Starting CrewAI Agent Chat Interface...")
    print()
    asyncio.run(main())
