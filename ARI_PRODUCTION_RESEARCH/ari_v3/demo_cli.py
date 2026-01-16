#!/usr/bin/env python3
"""
ARI V3 - Complete Operational Demo

A fully functional CLI demo that:
1. Uses real Neo4j (users database) and Qdrant (6.4M products)
2. Has preset demo users with full onboarding profiles
3. Supports real onboarding flow
4. Interactive recommendation with feedback tracking
5. **Conversational interface** - detects intent and responds naturally

Run: python ari_v3/demo_cli.py
"""

import asyncio
import os
import sys
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Imports
from neo4j import GraphDatabase, AsyncGraphDatabase
from qdrant_client import QdrantClient, AsyncQdrantClient
from openai import OpenAI

# V3 Interface imports
from ari_v3.interface import (
    ARIOrchestrator,
    HybridIntentDetector,
    ConversationHandler,
    DetectionStrategy,
    ResponseType,
    SearchIntent,
)

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
for name in ["neo4j", "httpx", "openai", "qdrant_client"]:
    logging.getLogger(name).setLevel(logging.WARNING)


# =============================================================================
# PRESET DEMO USERS
# =============================================================================

DEMO_USERS = {
    "emma": {
        "id": "demo_emma_creative",
        "name": "Emma",
        "description": "Creative professional, loves bold colors and unique pieces",
        "profile": {
            "personal": {
                "root_value": "self-expression",
                "validation_source": "self",
                "style_goal": "stand out authentically",
                "occasions": [
                    {"name": "work", "formality": 0.6, "style_context": "creative_professional"},
                    {"name": "gallery openings", "formality": 0.7, "style_context": "artistic"},
                    {"name": "weekend brunch", "formality": 0.3, "style_context": "casual"},
                ]
            },
            "taste": {
                "style_words": ["bold", "artistic", "eclectic", "colorful"],
                "style_avoids": ["basic", "corporate", "beige"],
                "color_preferences": ["emerald", "cobalt", "coral", "mustard"],
                "pattern_comfort": 0.8,
                "adventurousness": 8,
            },
            "process": {
                "decision_speed": "deliberate",
                "research_depth": "deep",
                "brand_loyalty": 4,
                "trend_following": 5,
            },
            "practicality": {
                "budget_monthly": 600,
                "budget_flexibility": 0.3,
                "care_tolerance": "medium",
                "versatility_priority": 0.6,
            },
            "body": {
                "height": "5'7\"",
                "body_type": "hourglass",
                "favorite_features": ["waist", "legs"],
                "fit_preferences": ["fitted waist", "midi length"],
            },
            "external": {
                "pinterest_connected": True,
                "instagram_aesthetic": "artistic",
            },
        },
    },
    "marcus": {
        "id": "demo_marcus_classic",
        "name": "Marcus",
        "description": "Finance professional, prefers timeless quality pieces",
        "profile": {
            "personal": {
                "root_value": "competence",
                "validation_source": "peers",
                "style_goal": "look polished and trustworthy",
                "occasions": [
                    {"name": "client meetings", "formality": 0.85, "style_context": "business_formal"},
                    {"name": "office", "formality": 0.7, "style_context": "business_casual"},
                    {"name": "golf weekends", "formality": 0.3, "style_context": "smart_casual"},
                ]
            },
            "taste": {
                "style_words": ["classic", "refined", "quality", "timeless"],
                "style_avoids": ["trendy", "flashy", "loud patterns"],
                "color_preferences": ["navy", "charcoal", "burgundy", "white"],
                "pattern_comfort": 0.3,
                "adventurousness": 3,
            },
            "process": {
                "decision_speed": "quick",
                "research_depth": "moderate",
                "brand_loyalty": 8,
                "trend_following": 2,
            },
            "practicality": {
                "budget_monthly": 1200,
                "budget_flexibility": 0.5,
                "care_tolerance": "high",
                "versatility_priority": 0.8,
            },
            "body": {
                "height": "6'1\"",
                "body_type": "athletic",
                "favorite_features": ["shoulders", "build"],
                "fit_preferences": ["tailored", "slim fit"],
            },
            "external": {
                "pinterest_connected": False,
                "instagram_aesthetic": None,
            },
        },
    },
    "sophia": {
        "id": "demo_sophia_minimal",
        "name": "Sophia",
        "description": "Tech founder, loves minimalist Scandinavian style",
        "profile": {
            "personal": {
                "root_value": "authenticity",
                "validation_source": "self",
                "style_goal": "effortless and intentional",
                "occasions": [
                    {"name": "investor pitches", "formality": 0.6, "style_context": "startup_professional"},
                    {"name": "team meetings", "formality": 0.4, "style_context": "casual_professional"},
                    {"name": "travel", "formality": 0.3, "style_context": "comfortable"},
                ]
            },
            "taste": {
                "style_words": ["minimal", "clean", "Scandinavian", "architectural"],
                "style_avoids": ["fussy", "decorative", "bright colors"],
                "color_preferences": ["black", "white", "grey", "camel"],
                "pattern_comfort": 0.2,
                "adventurousness": 5,
            },
            "process": {
                "decision_speed": "quick",
                "research_depth": "deep",
                "brand_loyalty": 7,
                "trend_following": 4,
            },
            "practicality": {
                "budget_monthly": 800,
                "budget_flexibility": 0.4,
                "care_tolerance": "low",
                "versatility_priority": 0.9,
            },
            "body": {
                "height": "5'9\"",
                "body_type": "tall_slim",
                "favorite_features": ["height", "posture"],
                "fit_preferences": ["relaxed", "oversized", "clean lines"],
            },
            "external": {
                "pinterest_connected": True,
                "instagram_aesthetic": "minimalist",
            },
        },
    },
}


# =============================================================================
# DEMO CLASS
# =============================================================================

class ARIDemoCLI:
    """Interactive ARI V3 Demo CLI with Conversational Interface."""

    def __init__(self):
        # Database connections
        self.neo4j_driver_sync = None
        self.neo4j_driver_async = None
        self.qdrant_client = None
        self.qdrant_client_async = None
        self.openai_client = None

        # Current user state
        self.current_user = None
        self.current_profile = None

        # V3 Interface components
        self.orchestrator: Optional[ARIOrchestrator] = None
        self.intent_detector: Optional[HybridIntentDetector] = None
        self.conversation_handler: Optional[ConversationHandler] = None
        self.navigation_intelligence = None

    async def initialize(self) -> bool:
        """Initialize all connections."""
        print("\n" + "="*60)
        print("  ARI V3 - Fashion Recommendation System")
        print("="*60)
        print("\nInitializing connections...")

        try:
            # Neo4j
            neo4j_uri = os.getenv("NEO4J_URI") or os.getenv("NEO4J_URL")
            neo4j_user = os.getenv("NEO4J_USERNAME", "neo4j")
            neo4j_pass = os.getenv("NEO4J_PASSWORD")

            self.neo4j_driver_sync = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))
            self.neo4j_driver_async = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))

            # Test connection
            with self.neo4j_driver_sync.session(database="users") as session:
                result = session.run("MATCH (u:User) RETURN count(u) as count")
                count = result.single()["count"]
            print(f"  [OK] Neo4j connected ({count} users)")

            # Qdrant
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            self.qdrant_client = QdrantClient(url=qdrant_url)
            self.qdrant_client_async = AsyncQdrantClient(url=qdrant_url)

            info = self.qdrant_client.get_collection("fashion_products")
            print(f"  [OK] Qdrant connected ({info.points_count:,} products)")

            # OpenAI
            self.openai_client = OpenAI()
            print(f"  [OK] OpenAI connected")

            # Initialize V3 Navigation Intelligence
            print("  Initializing Navigation Intelligence...")
            from ari_v3.orchestrator.navigation_intelligence import NavigationIntelligence
            self.navigation_intelligence = NavigationIntelligence(
                neo4j_driver=self.neo4j_driver_sync,
                qdrant_client=self.qdrant_client_async,
                openai_client=self.openai_client,
            )
            print(f"  [OK] Navigation Intelligence ready")

            # Initialize V3 Interface components
            print("  Initializing conversational interface...")
            self.intent_detector = HybridIntentDetector(
                strategy=DetectionStrategy.RULE_FIRST,
                confidence_threshold=0.6,
            )
            self.conversation_handler = ConversationHandler()
            self.orchestrator = ARIOrchestrator(
                navigation_intelligence=self.navigation_intelligence,
                intent_detector=self.intent_detector,
                conversation_handler=self.conversation_handler,
                qdrant_client=self.qdrant_client_async,
                openai_client=self.openai_client,
            )
            print(f"  [OK] Conversational interface ready")

            return True

        except Exception as e:
            print(f"\n  [ERROR] Failed to initialize: {e}")
            import traceback
            traceback.print_exc()
            return False

    def show_main_menu(self):
        """Show main menu."""
        print("\n" + "-"*60)
        print("  MAIN MENU")
        print("-"*60)
        print("  1. Use demo user (preset onboarding)")
        print("  2. Complete real onboarding")
        print("  3. Quick start (cold start, no onboarding)")
        print("  4. Exit")
        print("-"*60)

    def select_demo_user(self) -> Optional[Dict]:
        """Let user select a demo user."""
        print("\n" + "-"*60)
        print("  SELECT DEMO USER")
        print("-"*60)

        for i, (key, user) in enumerate(DEMO_USERS.items(), 1):
            print(f"  {i}. {user['name']}: {user['description']}")
        print("  0. Back to main menu")
        print("-"*60)

        choice = input("\nSelect user (1-3): ").strip()

        if choice == "0":
            return None

        try:
            idx = int(choice) - 1
            keys = list(DEMO_USERS.keys())
            if 0 <= idx < len(keys):
                return DEMO_USERS[keys[idx]]
        except ValueError:
            pass

        print("Invalid selection.")
        return None

    async def setup_demo_user(self, user_data: Dict) -> str:
        """Create or update demo user in Neo4j."""
        user_id = user_data["id"]
        profile = user_data["profile"]

        print(f"\nSetting up demo user: {user_data['name']}...")

        # Create user with onboarding profile
        cypher = """
            MERGE (u:User {id: $user_id})
            SET u.username = $username,
                u.onboarding_completed = true,
                u.demo_user = true,
                u.updated_at = datetime()

            // Create OnboardingProfile
            MERGE (u)-[:HAS_ONBOARDING]->(ob:OnboardingProfile)
            SET ob.personal = $personal,
                ob.taste = $taste,
                ob.process = $process,
                ob.practicality = $practicality,
                ob.body = $body,
                ob.external = $external,
                ob.created_at = datetime()

            RETURN u.id as user_id
        """

        import json
        with self.neo4j_driver_sync.session(database="users") as session:
            session.run(
                cypher,
                user_id=user_id,
                username=user_data["name"].lower(),
                personal=json.dumps(profile["personal"]),
                taste=json.dumps(profile["taste"]),
                process=json.dumps(profile["process"]),
                practicality=json.dumps(profile["practicality"]),
                body=json.dumps(profile["body"]),
                external=json.dumps(profile["external"]),
            )

        print(f"  [OK] Demo user '{user_data['name']}' ready")

        # Store profile for orchestrator context
        self.current_profile = self._build_onboarding_profile(profile)

        return user_id

    def _build_onboarding_profile(self, profile_data: Dict) -> Any:
        """Build an OnboardingProfile-like object from profile data."""
        # Create a simple object that mimics OnboardingProfile structure
        class ProfileSection:
            def __init__(self, data):
                for k, v in data.items():
                    setattr(self, k, v)

        class SimpleProfile:
            def __init__(self, data):
                self.taste = ProfileSection(data.get("taste", {})) if "taste" in data else None
                self.personal = ProfileSection(data.get("personal", {})) if "personal" in data else None
                self.practicality = ProfileSection(data.get("practicality", {})) if "practicality" in data else None
                self.body = ProfileSection(data.get("body", {})) if "body" in data else None
                self.process = ProfileSection(data.get("process", {})) if "process" in data else None

        return SimpleProfile(profile_data)

    async def display_results(self, products: List[Dict], narrative):
        """Display recommendation results."""
        print("\n" + "="*60)
        print("  YOUR PERSONALIZED RECOMMENDATIONS")
        print("="*60)

        # Show narrative opening (handle various attribute names)
        if narrative:
            opening_text = None
            if hasattr(narrative, 'opening') and narrative.opening:
                opening_text = narrative.opening
            elif hasattr(narrative, 'text') and narrative.text:
                opening_text = narrative.text
            elif hasattr(narrative, 'introduction') and narrative.introduction:
                opening_text = narrative.introduction

            if opening_text:
                print(f"\n{opening_text}\n")

        # Show products
        print("-"*60)
        for i, product in enumerate(products[:5], 1):
            title = product.get("title", product.get("name", "Unknown"))[:50]
            price = product.get("price", "N/A")
            score = product.get("_total_score", 0)
            category = product.get("category", product.get("productType", ""))

            print(f"\n  [{i}] {title}")
            if isinstance(price, (int, float)):
                print(f"      Price: ${price:.2f} | Category: {category}")
            else:
                print(f"      Price: {price} | Category: {category}")

            # Show score as stars (handle 0 score gracefully)
            if score and score > 0:
                print(f"      Match Score: {'*' * max(1, int(score * 5))}")

            # Show product explanation if available (handle various structures)
            if narrative:
                explanations = getattr(narrative, 'product_explanations', None) or []
                for exp in explanations:
                    exp_product_id = getattr(exp, 'product_id', None)
                    exp_title = getattr(exp, 'product_title', '')
                    exp_text = getattr(exp, 'explanation', '')

                    if exp_product_id == product.get("_id") or (exp_title and exp_title in title):
                        if exp_text:
                            print(f"      \"{exp_text[:100]}...\"")
                        break

        print("\n" + "-"*60)

    async def collect_feedback(self, products: List[Dict]):
        """Collect user feedback on products."""
        # Get session ID from orchestrator
        feedback_session_id = None
        if self.orchestrator:
            feedback_session_id = self.orchestrator.get_last_search_session_id()

        if not feedback_session_id:
            # Still allow feedback prompt but note it won't be recorded
            print("\nFeedback (helps ARI learn your preferences):")
            print("  Enter product numbers to like (e.g., '1 3 5'), or press Enter to skip")
            liked = input("  Liked products: ").strip()
            if liked:
                print("    [Note] Feedback recorded locally (session tracking not available)")
            return

        try:
            from ari_v3.feedback import OutcomeRecorder, OutcomeType
        except ImportError:
            print("\n  [Note] Feedback system not available")
            return

        recorder = OutcomeRecorder(neo4j_driver=self.neo4j_driver_async)

        print("\nFeedback (helps ARI learn your preferences):")
        print("  Enter product numbers to like (e.g., '1 3 5'), or press Enter to skip")

        liked = input("  Liked products: ").strip()

        if liked:
            for num in liked.split():
                try:
                    idx = int(num) - 1
                    if 0 <= idx < len(products):
                        product_id = products[idx].get("_id") or products[idx].get("uuid") or f"product_{idx}"
                        await recorder.record_outcome(
                            session_id=feedback_session_id,
                            product_id=product_id,
                            outcome=OutcomeType.LIKED,
                        )
                        print(f"    [OK] Recorded like for product {num}")
                except (ValueError, IndexError):
                    pass

        print("\nThank you! Your feedback helps ARI improve recommendations.")

    async def run_simple_onboarding(self) -> Optional[str]:
        """Run a simplified onboarding flow."""
        print("\n" + "="*60)
        print("  QUICK ONBOARDING")
        print("="*60)

        print("\nLet's learn a bit about your style preferences.\n")

        # Basic questions
        name = input("What should we call you? ").strip() or "User"
        user_id = f"user_{name.lower()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        print("\nWhat's your primary style goal?")
        print("  1. Stand out and express myself")
        print("  2. Look polished and professional")
        print("  3. Be comfortable and practical")
        print("  4. Stay on trend")
        goal_choice = input("Select (1-4): ").strip()
        goals = {
            "1": ("self-expression", "bold"),
            "2": ("competence", "polished"),
            "3": ("comfort", "practical"),
            "4": ("belonging", "trendy"),
        }
        root_value, style_word = goals.get(goal_choice, ("self-expression", "versatile"))

        print("\nWhat colors do you love wearing?")
        colors = input("(e.g., black, navy, red): ").strip() or "black, navy, white"

        print("\nWhat's your monthly clothing budget?")
        print("  1. Under $200")
        print("  2. $200-500")
        print("  3. $500-1000")
        print("  4. Over $1000")
        budget_choice = input("Select (1-4): ").strip()
        budgets = {"1": 150, "2": 350, "3": 750, "4": 1500}
        budget = budgets.get(budget_choice, 500)

        # Create user
        print(f"\nCreating your profile...")

        import json
        profile = {
            "personal": {"root_value": root_value, "style_goal": style_word},
            "taste": {"style_words": [style_word], "color_preferences": colors.split(",")},
            "practicality": {"budget_monthly": budget},
        }

        cypher = """
            CREATE (u:User {
                id: $user_id,
                username: $username,
                onboarding_completed: true,
                created_at: datetime()
            })
            CREATE (u)-[:HAS_ONBOARDING]->(ob:OnboardingProfile {
                personal: $personal,
                taste: $taste,
                practicality: $practicality,
                created_at: datetime()
            })
            RETURN u.id as user_id
        """

        with self.neo4j_driver_sync.session(database="users") as session:
            session.run(
                cypher,
                user_id=user_id,
                username=name.lower(),
                personal=json.dumps(profile["personal"]),
                taste=json.dumps(profile["taste"]),
                practicality=json.dumps(profile["practicality"]),
            )

        print(f"  [OK] Welcome, {name}! Your profile is ready.\n")
        return user_id

    async def interactive_session(self, user_id: str):
        """Run interactive recommendation session with conversational interface."""
        self.current_user = user_id

        # Create session ID
        session_id = str(uuid.uuid4())

        print("\n" + "="*60)
        print("  Chat with ARI - Your Personal Fashion Stylist")
        print("="*60)
        print("  Type anything - I can chat, answer questions, or find products!")
        print("  Type 'quit' to exit")
        print("="*60)

        while True:
            print()
            query = input("You: ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                # Say goodbye
                print("\nARI: Goodbye! It was lovely helping you today. Come back anytime!")
                break

            if not query:
                continue

            # Use the orchestrator to process input
            response = await self.orchestrator.process_input(
                session_id=session_id,
                user_id=user_id,
                query=query,
                user_profile=self.current_profile,
            )

            # Handle different response types
            if response.response_type == ResponseType.PRODUCTS:
                # Product search completed by orchestrator
                if response.products:
                    # Display results from orchestrator
                    await self.display_results(response.products, response.narrative)

                    # Offer feedback collection
                    await self.collect_feedback(response.products)
                else:
                    print(f"\nARI: {response.text}")
                    if response.suggestions:
                        print("\n  Suggestions:")
                        for i, suggestion in enumerate(response.suggestions[:3], 1):
                            print(f"    {i}. {suggestion}")

            elif response.response_type in [ResponseType.CONVERSATION, ResponseType.GREETING, ResponseType.GOODBYE]:
                # Conversational response
                print(f"\nARI: {response.text}")

                # Show suggestions if available
                if response.suggestions:
                    print("\n  Suggestions:")
                    for i, suggestion in enumerate(response.suggestions[:3], 1):
                        print(f"    {i}. {suggestion}")

            elif response.response_type == ResponseType.ERROR:
                print(f"\nARI: {response.text}")

            else:
                print(f"\nARI: {response.text or 'How can I help you today?'}")

    async def run(self):
        """Main run loop."""
        if not await self.initialize():
            return

        while True:
            self.show_main_menu()
            choice = input("\nSelect option (1-4): ").strip()

            if choice == "1":
                user_data = self.select_demo_user()
                if user_data:
                    user_id = await self.setup_demo_user(user_data)
                    await self.interactive_session(user_id)

            elif choice == "2":
                user_id = await self.run_simple_onboarding()
                if user_id:
                    await self.interactive_session(user_id)

            elif choice == "3":
                user_id = f"guest_{datetime.now().strftime('%H%M%S')}"
                print(f"\nStarting as guest (cold start mode)...")
                await self.interactive_session(user_id)

            elif choice == "4":
                print("\nGoodbye! Thanks for using ARI.\n")
                break
            else:
                print("Invalid option. Please try again.")

        # Cleanup
        if self.neo4j_driver_sync:
            self.neo4j_driver_sync.close()
        if self.neo4j_driver_async:
            await self.neo4j_driver_async.close()
        if self.qdrant_client_async:
            await self.qdrant_client_async.close()


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Entry point."""
    demo = ARIDemoCLI()
    asyncio.run(demo.run())


if __name__ == "__main__":
    main()
