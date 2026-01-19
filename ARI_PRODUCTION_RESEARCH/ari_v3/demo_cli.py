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
      python ari_v3/demo_cli.py --visual  # Enable visual search
      python ari_v3/demo_cli.py --visual --visual-scoring  # Enable visual scoring
"""

import argparse
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
from openai import OpenAI, AsyncOpenAI

# V3 Interface imports
from ari_v3.interface import (
    ARIOrchestrator,
    HybridIntentDetector,
    ConversationHandler,
    DetectionStrategy,
    ResponseType,
    SearchIntent,
)
from ari_v3.interface.types import VisualFeatureFlags

# Configure logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Suppress noisy loggers (set to ERROR to hide warnings)
for name in ["neo4j", "neo4j.notifications", "neo4j.io", "neo4j.pool",
             "httpx", "httpcore", "openai", "qdrant_client"]:
    logging.getLogger(name).setLevel(logging.ERROR)


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

    def __init__(
        self,
        visual_flags: Optional[VisualFeatureFlags] = None,
        debug_mode: bool = False,
        rule_intent: bool = False,
        enable_neo4j: bool = False,
        qdrant_only: bool = False,
    ):
        # Database connections
        self.neo4j_driver_sync = None
        self.neo4j_driver_async = None
        self.qdrant_client = None
        self.qdrant_client_async = None
        self.openai_client = None

        # Current user state
        self.current_user = None
        self.current_profile = None

        # OpenAI clients
        self.openai_client = None
        self.openai_client_async = None

        # V3 Interface components
        self.orchestrator: Optional[ARIOrchestrator] = None
        self.intent_detector: Optional[HybridIntentDetector] = None
        self.conversation_handler: Optional[ConversationHandler] = None
        self.navigation_intelligence = None
        self.user_graph_manager = None  # For recording user activity (Pillar 3)

        # Visual feature flags (V3.2)
        self.visual_flags = visual_flags or VisualFeatureFlags()

        # Debug mode (V3.2)
        self.debug_mode = debug_mode

        # Intent detection mode (V3.2) - LLM is default, rule_intent overrides
        self.use_llm_intent = not rule_intent

        # Search backend flags (V3.2)
        # If qdrant_only is set, disable neo4j and visual
        if qdrant_only:
            self.enable_neo4j = False
            self.visual_flags = VisualFeatureFlags()  # All visual off
        else:
            self.enable_neo4j = enable_neo4j
            # visual_flags already set above

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

            # Initialize UserGraphManager for activity recording (Pillar 3)
            from ari_v3.services.user_graph_manager import UserGraphManager
            self.user_graph_manager = UserGraphManager()
            print(f"  [OK] UserGraphManager initialized (activity recording)")

            # Qdrant
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            self.qdrant_client = QdrantClient(url=qdrant_url, timeout=60)
            self.qdrant_client_async = AsyncQdrantClient(url=qdrant_url, timeout=60)

            info = self.qdrant_client.get_collection("fashion_products")
            print(f"  [OK] Qdrant connected ({info.points_count:,} products)")

            # OpenAI (sync + async for performance)
            self.openai_client = OpenAI()
            self.openai_client_async = AsyncOpenAI()
            print(f"  [OK] OpenAI connected (sync + async)")

            # Initialize V3 Navigation Intelligence
            print("  Initializing Navigation Intelligence...")
            from ari_v3.orchestrator.navigation_intelligence import NavigationIntelligence
            self.navigation_intelligence = NavigationIntelligence(
                neo4j_driver=self.neo4j_driver_sync,
                qdrant_client=self.qdrant_client_async,
                openai_client=self.openai_client,
                async_openai_client=self.openai_client_async,
            )
            print(f"  [OK] Navigation Intelligence ready")

            # Initialize V3 Interface components
            print("  Initializing conversational interface...")
            intent_strategy = DetectionStrategy.LLM_FIRST if self.use_llm_intent else DetectionStrategy.RULE_FIRST
            self.intent_detector = HybridIntentDetector(
                strategy=intent_strategy,
                confidence_threshold=0.6,
            )
            if self.use_llm_intent:
                print(f"  [OK] Intent detection: LLM-based (default)")
            else:
                print(f"  [OK] Intent detection: Rule-based (--rule-intent)")
            self.conversation_handler = ConversationHandler()
            self.orchestrator = ARIOrchestrator(
                navigation_intelligence=self.navigation_intelligence,
                intent_detector=self.intent_detector,
                conversation_handler=self.conversation_handler,
                qdrant_client=self.qdrant_client_async,
                openai_client=self.openai_client,
                async_openai_client=self.openai_client_async,
                visual_flags=self.visual_flags,
                enable_neo4j=self.enable_neo4j,
            )
            print(f"  [OK] Conversational interface ready")

            # Show search backend status
            backends = ["Qdrant (semantic)"]
            if self.enable_neo4j:
                backends.append("Neo4j (Text2Cypher + enrichment)")
            if self.visual_flags.enable_visual_search:
                backends.append("Visual (FashionSigLIP)")
            print(f"  [OK] Search backends: {' + '.join(backends)}")

            if self.debug_mode:
                print(f"  [OK] Debug mode: ENABLED (pipeline tracing active)")

            return True

        except Exception as e:
            print(f"\n  [ERROR] Failed to initialize: {e}")
            import traceback
            traceback.print_exc()
            return False

    def detect_demo_user_request(self, text: str) -> Optional[Dict]:
        """
        Detect if user is requesting a demo profile from natural language.

        Examples that should match:
        - "I'm Emma" / "I am Emma" / "call me Emma"
        - "Use Emma's profile" / "load Emma"
        - "Be Marcus" / "switch to Sophia"
        """
        text_lower = text.lower()

        for key, user_data in DEMO_USERS.items():
            name_lower = user_data["name"].lower()

            # Check various patterns
            patterns = [
                f"i'm {name_lower}",
                f"i am {name_lower}",
                f"call me {name_lower}",
                f"use {name_lower}",
                f"load {name_lower}",
                f"be {name_lower}",
                f"switch to {name_lower}",
                f"as {name_lower}",
                f"{name_lower}'s profile",
                f"{name_lower} profile",
            ]

            for pattern in patterns:
                if pattern in text_lower:
                    return user_data

        return None

    def detect_onboarding_request(self, text: str) -> bool:
        """Detect if user wants to go through onboarding."""
        text_lower = text.lower()

        onboarding_phrases = [
            "set up my profile",
            "setup my profile",
            "create my profile",
            "onboarding",
            "get started",
            "learn about me",
            "know my style",
            "my preferences",
            "personalize",
            "customize",
        ]

        for phrase in onboarding_phrases:
            if phrase in text_lower:
                return True

        return False

    def detect_help_request(self, text: str) -> bool:
        """Detect if user is asking for help with the system."""
        text_lower = text.lower()

        help_phrases = [
            "what can you do",
            "how do i use",
            "how does this work",
            "help me understand",
            "what are my options",
            "who are the demo",
        ]

        for phrase in help_phrases:
            if phrase in text_lower:
                return True

        return False

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

    async def display_results(self, products: List[Dict], narrative, user_id: str = None, session_id: str = None):
        """Display recommendation results and record views for Pillar 3."""
        print("\n" + "="*60)
        print("  YOUR PERSONALIZED RECOMMENDATIONS")
        print("="*60)

        # Record product views for Pillar 3 (User Activity)
        if self.user_graph_manager and user_id and session_id:
            for product in products[:5]:  # Only record displayed products
                product_id = product.get("_id") or product.get("id") or product.get("product_id")
                if product_id:
                    try:
                        self.user_graph_manager.record_product_view(
                            user_id=user_id,
                            product_id=str(product_id),
                            session_id=session_id,
                            product_title=product.get("title", "")[:100],
                            product_category=product.get("category", ""),
                        )
                    except Exception as e:
                        pass  # Don't fail display if recording fails

        # Save products for like/save commands
        self._last_products = products[:5]

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
            # Try multiple field names for category
            # Use explicit parentheses for the conditional to avoid operator precedence issues
            tags = product.get("tags")
            tags_first = tags[0] if isinstance(tags, list) and tags else ""
            category = (
                product.get("category") or
                product.get("productType") or
                product.get("product_type") or
                product.get("type") or
                tags_first or
                ""
            )

            print(f"\n  [{i}] {title}")
            if isinstance(price, (int, float)):
                print(f"      Price: ${price:.2f} | Category: {category}")
            else:
                print(f"      Price: {price} | Category: {category}")

            # Show score as percentage with visual bar
            if score and score > 0:
                pct = int(score * 100)
                filled = int(score * 5)
                empty = 5 - filled
                bar = "[" + "*" * filled + "-" * empty + "]"
                print(f"      Match: {pct}% {bar}")

            # Show product explanation if available (handle various structures)
            if narrative:
                explanations = getattr(narrative, 'product_explanations', None) or []
                for exp in explanations:
                    exp_product_id = getattr(exp, 'product_id', None)
                    exp_title = getattr(exp, 'product_title', '')
                    exp_text = getattr(exp, 'explanation', '')

                    if exp_product_id == product.get("_id") or (exp_title and exp_title in title):
                        if exp_text:
                            # Wrap text to ~70 chars per line for readability
                            import textwrap
                            wrapped = textwrap.fill(exp_text, width=65, initial_indent='      "', subsequent_indent='       ')
                            print(f"{wrapped}\"")
                        break

        print("\n" + "-"*60)
        print("  Tip: Ask 'why this?' or 'how did you know?' to understand my reasoning")

    async def collect_feedback(self, products: List[Dict]):
        """
        Collect user feedback naturally through conversation.

        Instead of asking for numbers, we just continue the conversation.
        Users can say things like "I like the first one" or "show me more like #3"
        and the orchestrator will handle it via intent detection.
        """
        # No explicit feedback prompt - keep it conversational
        # The user can naturally say "I love that first one" or "not quite right"
        # and the conversation handler will pick it up
        pass

    async def run_simple_onboarding(self) -> Optional[str]:
        """Run a conversational onboarding flow."""
        print()

        # Name
        name = input("ARI: First off, what's your name?\nYou: ").strip() or "Friend"
        user_id = f"user_{name.lower()}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Style goal - conversational
        print(f"\nARI: Great to meet you, {name}! When you get dressed, what's")
        print("     most important to you - standing out, looking polished,")
        print("     being comfortable, or staying on trend?")
        goal_input = input("You: ").strip().lower()

        # Parse natural language response
        if any(w in goal_input for w in ["stand out", "express", "unique", "bold", "creative"]):
            root_value, style_word = "self-expression", "bold"
        elif any(w in goal_input for w in ["polish", "professional", "sharp", "clean", "refined"]):
            root_value, style_word = "competence", "polished"
        elif any(w in goal_input for w in ["comfort", "practical", "easy", "casual", "relaxed"]):
            root_value, style_word = "comfort", "practical"
        elif any(w in goal_input for w in ["trend", "fashion", "current", "modern", "fresh"]):
            root_value, style_word = "belonging", "trendy"
        else:
            root_value, style_word = "self-expression", "versatile"

        # Colors - conversational
        print(f"\nARI: Got it - {style_word} vibes. What colors do you find")
        print("     yourself reaching for most?")
        colors = input("You: ").strip() or "black, navy, white"

        # Budget - conversational
        print("\nARI: And roughly, how much do you usually spend on clothes")
        print("     in a month?")
        budget_input = input("You: ").strip().lower()

        # Parse natural language budget
        budget = 500  # default
        if any(w in budget_input for w in ["not much", "little", "under 200", "100", "150", "cheap"]):
            budget = 150
        elif any(w in budget_input for w in ["moderate", "200", "300", "400", "medium"]):
            budget = 350
        elif any(w in budget_input for w in ["500", "600", "700", "800", "decent"]):
            budget = 750
        elif any(w in budget_input for w in ["lot", "1000", "thousand", "splurge", "invest"]):
            budget = 1500

        # Create user
        import json
        profile = {
            "personal": {"root_value": root_value, "style_goal": style_word},
            "taste": {"style_words": [style_word], "color_preferences": [c.strip() for c in colors.split(",")]},
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

        self.current_profile = self._build_onboarding_profile(profile)
        return user_id

    async def interactive_session(self, user_id: str, show_welcome: bool = True):
        """Run interactive recommendation session with conversational interface."""
        self.current_user = user_id

        # Create session ID
        session_id = str(uuid.uuid4())

        # Track last displayed products for like/save commands
        self._last_products = []

        if show_welcome:
            print("\n")
            print("ARI: Hey there! I'm ARI. What brings you in today - looking for")
            print("     something specific, or just browsing for inspiration?")

        while True:
            print()
            query = input("You: ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                # Say goodbye
                print("\nARI: Goodbye! It was lovely helping you today. Come back anytime!")
                return "quit"

            if not query:
                continue

            # Check for demo user switch request
            demo_user = self.detect_demo_user_request(query)
            if demo_user:
                user_id = await self.setup_demo_user(demo_user)
                self.current_user = user_id
                desc = demo_user['description'].lower()
                print(f"\nARI: Nice to meet you, {demo_user['name']}! I see you're a")
                print(f"     {desc} - that's a great aesthetic.")
                print(f"     What are you in the mood for today?")
                continue

            # Check for onboarding request
            if self.detect_onboarding_request(query):
                print("\nARI: I'd love to get to know your style better. Let me ask")
                print("     you a few quick questions...")
                new_user_id = await self.run_simple_onboarding()
                if new_user_id:
                    user_id = new_user_id
                    self.current_user = user_id
                    print("\nARI: Great, I've got a good sense of your style now.")
                    print("     So what brings you in today?")
                continue

            # Check for help request
            if self.detect_help_request(query):
                self._show_natural_help()
                continue

            # Check for like/save command (e.g., "like 1", "save #2", "love the first one")
            like_match = self._detect_like_command(query)
            if like_match and self._last_products:
                idx = like_match - 1  # Convert to 0-indexed
                if 0 <= idx < len(self._last_products):
                    product = self._last_products[idx]
                    product_id = product.get("_id") or product.get("id") or product.get("product_id")
                    if product_id and self.user_graph_manager:
                        try:
                            self.user_graph_manager.record_product_save(
                                user_id=user_id,
                                product_id=str(product_id),
                                product_title=product.get("title", "")[:100],
                                product_category=product.get("category", ""),
                            )
                            title = product.get("title", "that item")[:40]
                            print(f"\nARI: Great choice! I've saved \"{title}\" to your likes.")
                            print("     This helps me learn your style better!")
                        except Exception as e:
                            print(f"\nARI: I love that one too! (Note: couldn't save - {e})")
                    else:
                        print(f"\nARI: I love that one too!")
                else:
                    print(f"\nARI: Hmm, I don't see item #{like_match}. Try 1-{len(self._last_products)}.")
                continue

            # Debug: Show pipeline modules BEFORE processing
            if self.debug_mode:
                self._show_debug_pre_processing(query)

            # Use the orchestrator to process input
            response = await self.orchestrator.process_input(
                session_id=session_id,
                user_id=user_id,
                query=query,
                user_profile=self.current_profile,
            )

            # Record search for Pillar 3 (User Activity)
            if self.user_graph_manager and response.response_type == ResponseType.PRODUCTS:
                try:
                    result_count = len(response.products) if response.products else 0
                    self.user_graph_manager.record_search(
                        user_id=user_id,
                        query=query[:200],  # Truncate long queries
                        category=response.intent.extracted_params.categories[0] if response.intent and response.intent.extracted_params and response.intent.extracted_params.categories else "",
                        result_count=result_count,
                    )
                except Exception as e:
                    pass  # Don't fail if recording fails

            # Debug: Show pipeline trace AFTER processing
            if self.debug_mode:
                self._show_debug_post_processing(response, session_id)

            # Handle different response types
            if response.response_type == ResponseType.PRODUCTS:
                # Product search completed by orchestrator
                if response.products:
                    # Display results from orchestrator (also records views for Pillar 3)
                    await self.display_results(response.products, response.narrative, user_id=user_id, session_id=session_id)

                    # Offer feedback collection (now just continues conversation)
                    await self.collect_feedback(response.products)
                else:
                    # No products found - natural response
                    print(f"\nARI: {response.text}")

            elif response.response_type in [ResponseType.CONVERSATION, ResponseType.GREETING, ResponseType.GOODBYE]:
                # Conversational response - no suggestions, keep it natural
                print(f"\nARI: {response.text}")

            elif response.response_type == ResponseType.ERROR:
                print(f"\nARI: {response.text}")

            else:
                print(f"\nARI: {response.text or 'How can I help you today?'}")

        return "continue"

    def _is_profile_query(self, text: str) -> bool:
        """Detect if user is asking about their profile/preferences."""
        text_lower = text.lower()
        patterns = [
            "what do you know about me",
            "what do you know",
            "my preferences",
            "my profile",
            "my style",
            "know about me",
            "remember about me",
            "extract",
            "show my",
            "tell me about me",
        ]
        return any(p in text_lower for p in patterns)

    def _detect_like_command(self, text: str) -> Optional[int]:
        """
        Detect if user wants to like/save a product.
        Returns the product number (1-indexed) or None.
        """
        import re
        text_lower = text.lower().strip()

        # Patterns: "like 1", "save #2", "love 3", "like the first", etc.
        patterns = [
            r"^(?:like|love|save|want|favorite)\s*#?(\d+)$",
            r"^(?:like|love|save|want|favorite)\s+(?:the\s+)?(?:first|1st)\s*(?:one)?$",
            r"^(?:like|love|save|want|favorite)\s+(?:the\s+)?(?:second|2nd)\s*(?:one)?$",
            r"^(?:like|love|save|want|favorite)\s+(?:the\s+)?(?:third|3rd)\s*(?:one)?$",
            r"^(?:like|love|save|want|favorite)\s+(?:the\s+)?(?:fourth|4th)\s*(?:one)?$",
            r"^(?:like|love|save|want|favorite)\s+(?:the\s+)?(?:fifth|5th)\s*(?:one)?$",
            r"^#(\d+)$",
        ]

        # Check numeric patterns
        for pattern in patterns[:2]:
            match = re.match(pattern, text_lower)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass

        # Check ordinal patterns
        ordinals = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5}
        for ordinal, num in ordinals.items():
            if ordinal in text_lower and any(word in text_lower for word in ["like", "love", "save", "want", "favorite"]):
                return num

        # Check bare number with # prefix
        match = re.match(r"^#(\d+)$", text_lower)
        if match:
            return int(match.group(1))

        return None

    def _is_score_query(self, text: str) -> bool:
        """Detect if user is asking about match scores/ratings."""
        text_lower = text.lower()
        patterns = [
            "match score", "match rating",
            "asterisk", "stars", "star rating",
            "score mean", "rating mean",
            "out of", "maximum", "max score",
            "how many stars", "what does the score",
            "scoring", "how do you score",
            "percent", "percentage",
        ]
        return any(p in text_lower for p in patterns)

    def _explain_scoring(self):
        """Explain the match scoring system."""
        print("\nARI: Great question! Here's how the Match Score works:")
        print()
        print("     The score shows how well each item matches YOUR style:")
        print()
        print("     90-100%  [*****]  Perfect match - hits all your preferences")
        print("     70-89%   [****-]  Strong match - aligns well with your style")
        print("     50-69%   [***--]  Good match - solid choice for you")
        print("     30-49%   [**---]  Moderate - might work in some contexts")
        print("     10-29%   [*----]  Light match - outside your usual style")
        print()
        print("     Factors that affect your score:")
        print("     - Style alignment (bold vs minimal, etc.)")
        print("     - Color preferences")
        print("     - Budget fit")
        print("     - Occasion appropriateness")
        print("     - Brand affinity")
        print()
        print("     Want me to explain why a specific item scored the way it did?")

    def _show_user_profile(self):
        """Display what ARI knows about the current user."""
        if not self.current_profile:
            print("\nARI: I don't have a profile loaded for you yet. You can:")
            print("     - Say 'I'm Emma' to load a demo profile")
            print("     - Say 'set up my profile' to create your own")
            print("     - Or just tell me what you're looking for!")
            return

        print("\nARI: Here's what I know about your style:")
        print()

        # Extract from profile
        if hasattr(self.current_profile, 'taste') and self.current_profile.taste:
            taste = self.current_profile.taste
            if hasattr(taste, 'style_words') and taste.style_words:
                print(f"     Style: {', '.join(taste.style_words)}")
            if hasattr(taste, 'color_preferences') and taste.color_preferences:
                print(f"     Favorite colors: {', '.join(taste.color_preferences)}")
            if hasattr(taste, 'style_avoids') and taste.style_avoids:
                print(f"     You avoid: {', '.join(taste.style_avoids)}")
            if hasattr(taste, 'adventurousness'):
                adv = taste.adventurousness
                adv_label = "very adventurous" if adv >= 7 else "moderate" if adv >= 4 else "classic"
                print(f"     Adventurousness: {adv}/10 ({adv_label})")

        if hasattr(self.current_profile, 'practicality') and self.current_profile.practicality:
            prac = self.current_profile.practicality
            if hasattr(prac, 'budget_monthly') and prac.budget_monthly:
                print(f"     Monthly budget: ${prac.budget_monthly}")

        if hasattr(self.current_profile, 'personal') and self.current_profile.personal:
            personal = self.current_profile.personal
            if hasattr(personal, 'style_goal') and personal.style_goal:
                print(f"     Style goal: {personal.style_goal}")
            if hasattr(personal, 'occasions') and personal.occasions:
                occ_names = [o.get('name', o) if isinstance(o, dict) else str(o) for o in personal.occasions[:3]]
                print(f"     Key occasions: {', '.join(occ_names)}")

        print()
        print("     Would you like to find something that matches your style?")

    def _show_natural_help(self):
        """Show help in a natural, conversational way."""
        print("\nARI: I'm here to help you find the perfect pieces! Just tell me")
        print("     what you're looking for - an occasion, a vibe, a specific item,")
        print("     whatever's on your mind. The more you share about your style")
        print("     and what you're after, the better I can help. What's the occasion?")

    def _show_debug_pre_processing(self, query: str):
        """Show debug information BEFORE processing a query."""
        print("\n" + "="*60)
        print(f"  [DEBUG] Processing: \"{query[:50]}{'...' if len(query) > 50 else ''}\"")
        print("="*60)

    def _show_debug_post_processing(self, response, session_id: str):
        """Show debug information AFTER processing a query with verification."""
        print("\n" + "-"*60)
        print("  [DEBUG] PIPELINE EXECUTION RESULTS")
        print("-"*60)

        # Track what ran
        ran_catalog = False
        ran_intent = False
        ran_params = False
        ran_profile_update = False
        ran_feedback = False
        ran_conversation = False
        ran_navigation = False
        ran_text2cypher = False
        ran_semantic = False
        ran_neo4j = False
        ran_qdrant = False
        ran_visual = False
        ran_exclusions = False
        ran_brand_filter = False
        ran_dedup = False
        ran_enrichment = False
        ran_evaluator = False
        ran_narrative = False
        ran_activity = False  # Pillar 3 activity recording

        # Check what actually ran based on response
        if response.intent:
            ran_intent = True
            intent = response.intent
            if intent.extracted_parameters:
                params = intent.extracted_parameters
                if (hasattr(params, 'categories') and params.categories) or \
                   (hasattr(params, 'colors') and params.colors) or \
                   (hasattr(params, 'exclusions') and params.exclusions):
                    ran_params = True

        # Check for catalog query
        if response.response_type.value == "conversation" and response.text:
            if "brands" in response.text.lower() or "categories" in response.text.lower():
                ran_catalog = True

        # Check for profile update
        if response.intent and response.intent.primary_intent.value == "profile_update":
            ran_profile_update = True

        # Check for feedback handler
        if response.intent and response.intent.primary_intent.value == "feedback":
            ran_feedback = True

        # Check for conversation handler (non-product intents)
        if response.intent and response.response_type.value == "conversation":
            if response.intent.primary_intent.value not in ["profile_update", "feedback"]:
                ran_conversation = True

        # Check post-processing steps (only on product searches)
        if response.response_type.value == "products" and response.products:
            # Dedup always runs on product searches
            ran_dedup = True

            # Enrichment runs if neo4j is enabled
            if self.enable_neo4j:
                ran_enrichment = True

            # Check if exclusions were applied
            if response.intent and response.intent.extracted_parameters:
                params = response.intent.extracted_parameters
                if hasattr(params, 'exclusions') and params.exclusions:
                    ran_exclusions = True
                if hasattr(params, 'brand_preferences') and params.brand_preferences:
                    ran_brand_filter = True

        # Check trace for what ran
        trace = self.orchestrator._explanation_traces.get(session_id) if hasattr(self.orchestrator, '_explanation_traces') else None
        if trace:
            if trace.navigation_decisions:
                ran_navigation = True
            if trace.query_interpretation:
                qi = trace.query_interpretation
                if qi.get("semantic_expansion"):
                    ran_semantic = True
                if qi.get("cypher_query"):
                    ran_text2cypher = True
            if trace.product_breakdowns:
                ran_evaluator = True

        # Check response for what ran
        if response.response_type.value == "products":
            ran_qdrant = True  # We always use Qdrant for product searches
            if response.products:
                ran_evaluator = True
                # Activity recording runs when products are displayed
                if self.user_graph_manager:
                    ran_activity = True
            if response.text and len(response.text) > 100:
                ran_narrative = True

        # Visual search check
        if self.visual_flags.enable_visual_search and response.response_type.value == "products":
            ran_visual = True

        # Print verification table
        def status(ran: bool) -> str:
            return "YES" if ran else " - "

        print(f"  CatalogQueryDetector     [{status(ran_catalog)}]  Brand/category metadata lookup")
        print(f"  HybridIntentDetector     [{status(ran_intent)}]  {response.intent.primary_intent.value if response.intent else 'N/A'} ({response.intent.detection_method if response.intent else 'N/A'})")
        print(f"  ParameterExtractor       [{status(ran_params)}]  Colors, brands, exclusions")
        print(f"  ProfileUpdateHandler     [{status(ran_profile_update)}]  User style → Neo4j user graph")
        print(f"  FeedbackHandler          [{status(ran_feedback)}]  Refine search from feedback")
        print(f"  ConversationHandler      [{status(ran_conversation)}]  Chat/system response")
        print(f"  NavigationIntelligence   [{status(ran_navigation)}]  User profile context")
        print(f"  Text2CypherGenerator     [{status(ran_text2cypher)}]  Structured Neo4j query")
        print(f"  SemanticQueryGenerator   [{status(ran_semantic)}]  Query expansion for embeddings")
        print(f"  Neo4j Search             [{status(ran_neo4j)}]  Graph database search")
        print(f"  Qdrant Semantic Search   [{status(ran_qdrant)}]  Embedding similarity")
        if self.visual_flags.enable_visual_search:
            print(f"  Qdrant Visual Search     [{status(ran_visual)}]  Visual similarity")
        print(f"  ExclusionFilter          [{status(ran_exclusions)}]  Remove excluded items")
        print(f"  BrandFilter              [{status(ran_brand_filter)}]  Filter by brand preference")
        print(f"  Deduplication            [{status(ran_dedup)}]  Remove duplicate products")
        if self.enable_neo4j:
            print(f"  Neo4jEnrichment          [{status(ran_enrichment)}]  Fill missing metadata")
        print(f"  ARIEvaluator             [{status(ran_evaluator)}]  Product scoring/ranking")
        print(f"  NarrativeLLM             [{status(ran_narrative)}]  Response generation")
        print(f"  ActivityRecorder         [{status(ran_activity)}]  Pillar 3: views/searches → Neo4j")

        print("-"*60)

        # Show key details
        if response.intent:
            intent = response.intent
            print(f"  Intent: {intent.primary_intent.value} (confidence: {intent.confidence:.0%})")

            # Show extracted parameters if any
            if ran_params and intent.extracted_parameters:
                params = intent.extracted_parameters
                details = []
                if hasattr(params, 'categories') and params.categories:
                    details.append(f"categories={params.categories}")
                if hasattr(params, 'colors') and params.colors:
                    details.append(f"colors={params.colors}")
                if hasattr(params, 'exclusions') and params.exclusions:
                    details.append(f"exclusions=[{len(params.exclusions)}]")
                if details:
                    print(f"  Params: {', '.join(details)}")

        # Show results
        if response.response_type.value == "products" and response.products:
            print(f"  Results: {len(response.products)} products returned")
        elif ran_catalog:
            print(f"  Results: Catalog information returned")
        else:
            print(f"  Route: {response.response_type.value.upper()}")

        print(f"  Time: {response.execution_time:.2f}s")
        print("="*60 + "\n")

    def _show_user_menu(self) -> Optional[Dict]:
        """Show menu to select a demo user or continue as guest."""
        print("\n" + "-"*60)
        print("  SELECT A USER PROFILE")
        print("-"*60)
        print()

        # List demo users
        user_list = list(DEMO_USERS.items())
        for i, (key, user_data) in enumerate(user_list, 1):
            name = user_data["name"]
            desc = user_data["description"]
            print(f"  [{i}] {name} - {desc}")

        print(f"  [{len(user_list) + 1}] New User - Create your own profile")
        print(f"  [{len(user_list) + 2}] Guest - Browse without a profile")
        print()

        choice = input("Select (1-5): ").strip()

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(user_list):
                return user_list[choice_num - 1][1]  # Return the user_data dict
            elif choice_num == len(user_list) + 1:
                return "onboarding"  # Signal to run onboarding
            else:
                return None  # Guest
        except ValueError:
            # Check if they typed a name
            for key, user_data in DEMO_USERS.items():
                if key in choice.lower() or user_data["name"].lower() in choice.lower():
                    return user_data
            return None  # Guest

    async def run(self):
        """Main run loop - fully naturalistic conversational interface."""
        if not await self.initialize():
            return

        # Show user selection menu
        selected = self._show_user_menu()

        if selected == "onboarding":
            # Run onboarding for new user
            print("\nARI: Welcome! Let's get to know your style...")
            user_id = await self.run_simple_onboarding()
            if not user_id:
                user_id = f"guest_{datetime.now().strftime('%H%M%S')}"
        elif selected:
            # Load selected demo user
            user_id = await self.setup_demo_user(selected)
            print(f"\nARI: Hey {selected['name']}! Great to see you.")
            print(f"     I remember your style - {selected['profile']['taste']['style_words'][0]},")
            print(f"     {selected['profile']['taste']['style_words'][1]}. What can I help you find today?")
        else:
            # Guest mode
            user_id = f"guest_{datetime.now().strftime('%H%M%S')}"
            print("\nARI: Hey there! I'm ARI. Since you're browsing as a guest,")
            print("     I don't have your style preferences yet. You can say")
            print("     'I'm Emma' to load a demo profile, or just tell me")
            print("     what you're looking for!")

        # Run the interactive session
        await self.interactive_session(user_id, show_welcome=False)

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

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ARI V3 Demo CLI - Fashion Recommendation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_cli.py                     # Default (Qdrant semantic only)
  python demo_cli.py --neo4j             # Qdrant + Neo4j (Text2Cypher + enrichment)
  python demo_cli.py --visual            # Qdrant + Visual search
  python demo_cli.py --neo4j --visual    # Qdrant + Neo4j + Visual (full stack)
  python demo_cli.py --qdrant-only       # Force Qdrant-only (no Neo4j, no visual)
  python demo_cli.py --debug             # Show pipeline execution trace
        """
    )

    # Debug mode
    parser.add_argument(
        "--debug", action="store_true",
        help="Show pipeline modules called during each query (useful for understanding the flow)"
    )

    # Intent detection mode
    parser.add_argument(
        "--rule-intent", action="store_true",
        help="Use regex-based intent detection instead of LLM (faster but less accurate)"
    )

    # Search backend flags
    search_group = parser.add_argument_group("Search Backends")
    search_group.add_argument(
        "--neo4j", action="store_true",
        help="Enable Neo4j features (Text2Cypher + metadata enrichment)"
    )
    search_group.add_argument(
        "--qdrant-only", action="store_true",
        help="Use only Qdrant semantic search (no Neo4j, no visual)"
    )

    # Visual feature flags
    visual_group = parser.add_argument_group("Visual Features (V3.2)")
    visual_group.add_argument(
        "--visual", action="store_true",
        help="Enable visual search (FashionSigLIP collection)"
    )
    visual_group.add_argument(
        "--visual-scoring", action="store_true",
        help="Enable visual similarity in scoring (requires --visual)"
    )
    visual_group.add_argument(
        "--visual-weight", type=float, default=0.4,
        help="Weight for visual results in fusion (default: 0.4)"
    )
    visual_group.add_argument(
        "--social-visual", action="store_true",
        help="Use Pinterest/Instagram visual embeddings if available"
    )
    visual_group.add_argument(
        "--all-visual", action="store_true",
        help="Enable all visual features"
    )
    visual_group.add_argument(
        "--fusion-strategy", choices=["weighted_average", "max", "cascade"],
        default="weighted_average",
        help="Strategy for fusing semantic and visual results (default: weighted_average)"
    )

    return parser.parse_args()


def main():
    """Entry point."""
    args = parse_args()

    # Validate mutually exclusive flags
    if args.neo4j and args.qdrant_only:
        print("Error: --neo4j and --qdrant-only are mutually exclusive.")
        print("  --neo4j enables Neo4j features (Text2Cypher + metadata)")
        print("  --qdrant-only forces semantic-only mode (no Neo4j, no visual)")
        sys.exit(1)

    # Build visual feature flags from CLI args
    visual_flags = VisualFeatureFlags(
        enable_visual_search=args.visual or args.all_visual,
        enable_visual_scoring=args.visual_scoring or args.all_visual,
        enable_social_visual=args.social_visual or args.all_visual,
        visual_weight=args.visual_weight,
        semantic_weight=1.0 - args.visual_weight,
        fusion_strategy=args.fusion_strategy,
    )

    # If visual scoring enabled, set a default weight
    if visual_flags.enable_visual_scoring:
        visual_flags.visual_score_weight = 0.15

    # Enable debug mode logging
    if args.debug:
        # Set ARI-related loggers to DEBUG level
        for name in ["ari_v3.interface.orchestrator", "ari_v3.tools.text2cypher",
                     "ari_v3.tools.semantic_query", "ari_v3.orchestrator.navigation_intelligence"]:
            logging.getLogger(name).setLevel(logging.DEBUG)
        print("[DEBUG MODE] Pipeline tracing enabled")

    if args.rule_intent:
        print("[RULE INTENT] Using regex-based intent detection (faster but less accurate)")

    demo = ARIDemoCLI(
        visual_flags=visual_flags,
        debug_mode=args.debug,
        rule_intent=args.rule_intent,
        enable_neo4j=args.neo4j,
        qdrant_only=args.qdrant_only,
    )
    asyncio.run(demo.run())


if __name__ == "__main__":
    main()
