"""
Enhanced Chat Interface V2

User-aware chat interface with onboarding and personalization.
Integrates with user graph for personalized fashion recommendations.

Usage:
    python cli/chat_interface_v2.py
"""

import asyncio
import sys
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

# Add parent directory to path - ensure it's at the front to avoid conflicts
import os
_current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ari_crewai_migration
_parent_dir = os.path.dirname(_current_dir)  # ARI_PRODUCTION_CAMEL_0.27

# Remove both from path if present
while _current_dir in sys.path:
    sys.path.remove(_current_dir)
while _parent_dir in sys.path:
    sys.path.remove(_parent_dir)

# Add current directory first (for our modules like agents, crews)
# Then parent directory (for shared models.types, etc.)
sys.path.insert(0, _parent_dir)
sys.path.insert(0, _current_dir)

from services.user_service import UserService
from services.onboarding_service import OnboardingService
from crews.onboarding_crew import create_onboarding_crew
from crews.crewai_orchestrator import create_crewai_orchestrator
from models.user_models import User
from prompts.onboarding_prompts import get_all_step_ids


class EnhancedChatInterface:
    """Enhanced chat interface with user awareness."""

    def __init__(self):
        """Initialize chat interface."""
        self.user_service = UserService()
        self.onboarding_service = OnboardingService()

        self.orchestrator = None
        self.current_user: Optional[User] = None
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"

    def close(self):
        """Close services."""
        self.user_service.close()
        self.onboarding_service.close()

    # ======================
    # ONBOARDING FLOW
    # ======================

    async def run_conversational_onboarding(self, username: str, email: str = None) -> Optional[User]:
        """
        Run conversational onboarding flow using AI agents.

        Args:
            username: Username
            email: Optional email (will be collected if not provided)

        Returns:
            User object if successful, None otherwise
        """
        print("\n" + "=" * 70)
        print(" Welcome to ARI - Your Personal Style Discovery Experience")
        print("=" * 70)
        print("\nI'm here to help you discover and articulate your style identity.")
        print("This isn't a form or quiz - it's a conversation.")
        print("\nTake your time. There are no wrong answers.")
        print("=" * 70 + "\n")

        # Collect email if not provided
        if not email:
            while True:
                email = input("What's your email address? ").strip()
                if email and '@' in email:
                    break
                print("Please enter a valid email address.\n")

        # Create user
        try:
            user = self.user_service.create_user(username, email)
            user_id = user.id
        except Exception as e:
            print(f"\nError creating user: {e}")
            return None

        # Create onboarding crew
        crew = create_onboarding_crew()

        # Run through all onboarding steps
        all_steps = get_all_step_ids()

        for step_id in all_steps:
            print(f"\n{'=' * 70}")
            print(f" Topic {all_steps.index(step_id) + 1}/{len(all_steps)}")
            print(f"{'=' * 70}\n")

            # Start step
            opening_message = crew.start_step(step_id)
            print(f"ARI: {opening_message}\n")

            step_complete = False

            while not step_complete:
                # Get user input
                user_input = input("You: ").strip()

                if not user_input:
                    print("(Please share your thoughts, or type 'skip' to move on)\n")
                    continue

                #  Handle skip
                if user_input.lower() in ['skip', 'next']:
                    crew.complete_step()
                    break

                # Process response
                try:
                    result = crew.process_user_response(user_input)
                    agent_response = result.get('agent_response', '')
                    completeness = result.get('completeness', 0.0)

                    print(f"\nARI: {agent_response}\n")

                    # Auto-complete if agent suggests moving on
                    if completeness >= 0.8 or 'move on' in agent_response.lower():
                        crew.complete_step()
                        step_complete = True

                except Exception as e:
                    print(f"\n(Could you rephrase that?)\n")

        # Save data to Neo4j
        print("\n" + "=" * 70)
        print(" Saving Your Style Profile...")
        print("=" * 70 + "\n")

        all_data = crew.get_all_extracted_data()

        for step_id, step_data in all_data.items():
            try:
                await self.onboarding_service.store_step_responses(
                    user_id=user_id,
                    step_id=step_id,
                    responses=step_data
                )
            except Exception as e:
                print(f"Warning: Error saving {step_id}: {e}")

        # Mark complete
        self.user_service.update_user_profile(user_id, {
            'onboarding_completed': True,
            'onboarding_completed_at': datetime.now()
        })

        print("Your style profile has been saved!\n")

        # Return updated user
        return self.user_service.get_user_by_username(username)

    # ======================
    # USER AUTHENTICATION
    # ======================

    async def authenticate(self):
        """Authenticate user or run onboarding for new users."""
        print("\n" + "="*70)
        print("ARI FASHION RECOMMENDATION SYSTEM")
        print("="*70)
        print()

        while True:
            username = input("Username: ").strip()

            if not username:
                print("  Username cannot be empty")
                continue

            # Check if user exists
            user = self.user_service.get_user_by_username(username)

            if user is None:
                # New user - run conversational onboarding
                print(f"\nWelcome, {username}! You're new here.")

                try:
                    user = await self.run_conversational_onboarding(username)

                    if user and user.onboarding_completed:
                        print(f"\nProfile complete! Welcome to ARI, {username}!")
                    else:
                        print("\nOnboarding incomplete. Please complete it to continue.")
                        continue

                except Exception as e:
                    print(f"\nError during onboarding: {e}")
                    print("Please try again.")
                    import traceback
                    traceback.print_exc()
                    continue

            else:
                # Existing user
                if not user.onboarding_completed:
                    print(f"\nWelcome back, {username}!")
                    print("Let's finish your profile setup...")

                    try:
                        user = await self.run_conversational_onboarding(username, user.email)

                        if not user or not user.onboarding_completed:
                            print("\nOnboarding incomplete. Please complete it to continue.")
                            continue

                    except Exception as e:
                        print(f"\nError during onboarding: {e}")
                        print("Please try again.")
                        import traceback
                        traceback.print_exc()
                        continue

                else:
                    print(f"\nWelcome back, {username}!")

            self.current_user = user
            break

    # ======================
    # PERSONALIZATION
    # ======================

    def get_personalized_limit(self) -> int:
        """Get personalized result limit based on decision-making style."""
        if not self.current_user:
            return 5

        style = self.current_user.decision_making_style

        if style == "tell_me":
            return 2
        elif style == "curated_options":
            return 5
        else:  # many_options
            return 8

    async def get_user_style_context(self) -> Dict[str, Any]:
        """Get user style context for personalized search."""
        if not self.current_user:
            return {}

        # Get full profile
        profile = self.user_service.get_user_profile(self.current_user.id)

        if not profile:
            return {}

        return {
            "user_id": self.current_user.id,
            "username": self.current_user.username,
            "style_adjectives": [adj.name for adj in profile.style_adjectives],
            "fit_preferences": profile.fit_preferences,
            "occasions": [occ.name for occ in profile.occasions],
            "values": [val.name for val in profile.values],
            "budget_range": {
                "min": self.current_user.monthly_budget_min or 0,
                "max": self.current_user.monthly_budget_max or 1000
            },
            "risk_tolerance": self.current_user.stated_risk_tolerance or 5.0,
            "expression_spectrum": self.current_user.stated_expression_spectrum or 5.0,
            "aspiration": self.current_user.aspiration_text or "",
            "change_readiness": self.current_user.change_readiness or "evolve"
        }

    def apply_user_filters(self) -> Dict[str, Any]:
        """Apply user-specific filters."""
        if not self.current_user:
            return {}

        filters = {}

        # Budget constraints
        if self.current_user.monthly_budget_max:
            # Rough per-item budget (monthly budget / 4)
            filters['max_price'] = self.current_user.monthly_budget_max // 4

        return filters

    # ======================
    # INTERACTION TRACKING
    # ======================

    async def track_search(self, query: str, result: Dict[str, Any]):
        """Track search interaction."""
        if not self.current_user:
            return

        products = result.get("products", [])

        # Track search
        self.user_service.track_search(
            user_id=self.current_user.id,
            query=query,
            category=result.get("metadata", {}).get("primary_category", ""),
            result_count=len(products)
        )

        # Track product views
        for product in products:
            self.user_service.track_product_view(
                user_id=self.current_user.id,
                product_id=product.get("id", ""),
                session_id=self.session_id,
                product_title=product.get("title", ""),
                product_category=product.get("category", "")
            )

    # ======================
    # CHAT LOOP
    # ======================

    async def start_chat(self):
        """Start the chat loop."""
        # Initialize orchestrator
        print("\nInitializing ARI recommendation system...")

        try:
            from nlp.hybrid_intent_detector import DetectionStrategy

            self.orchestrator = create_crewai_orchestrator(
                process_type="sequential",
                intent_strategy=DetectionStrategy.LLM_FIRST
            )

            print("System ready!")

        except Exception as e:
            print(f"Error initializing system: {e}")
            return

        # Show user info
        print("\n" + "="*70)
        print("YOUR PROFILE")
        print("="*70)
        print(f"Username: {self.current_user.username}")

        if self.current_user.stated_expression_spectrum:
            print(f"Style Expression: {self.current_user.stated_expression_spectrum:.1f}/10")

        if self.current_user.decision_making_style:
            print(f"Decision Style: {self.current_user.decision_making_style}")

        if self.current_user.monthly_budget_max:
            print(f"Monthly Budget: ${self.current_user.monthly_budget_min}-${self.current_user.monthly_budget_max}")

        print("="*70)
        print()
        print("Commands:")
        print("  'profile' - View your complete profile")
        print("  'stats' - View your usage statistics")
        print("  'quit' or 'exit' - Exit")
        print()
        print("="*70)
        print()

        # Chat loop
        while True:
            try:
                query = input("You: ").strip()

                if not query:
                    continue

                # Handle commands
                if query.lower() in ['quit', 'exit', 'q']:
                    print("\nThanks for using ARI! Goodbye!")
                    break

                if query.lower() == 'profile':
                    await self.show_profile()
                    continue

                if query.lower() == 'stats':
                    await self.show_stats()
                    continue

                # Execute search
                print(f"\n  Searching...")

                result = await self.orchestrator.execute_search(
                    query=query,
                    limit=self.get_personalized_limit(),
                    user_context=await self.get_user_style_context(),
                    filters=self.apply_user_filters(),
                    conversation_context={
                        "session_id": self.session_id,
                        "user_id": self.current_user.id
                    }
                )

                # Track interaction
                await self.track_search(query, result)

                # Display results
                self.display_results(result)

                # Update observed preferences periodically
                if self.current_user.total_searches % 5 == 0:
                    self.user_service.update_observed_preferences(self.current_user.id)

            except KeyboardInterrupt:
                print("\n\nThanks for using ARI! Goodbye!")
                break

            except Exception as e:
                print(f"\nError: {e}")
                continue

    # ======================
    # DISPLAY METHODS
    # ======================

    def display_results(self, result: Dict[str, Any]):
        """Display search results."""
        products = result.get("products", [])

        print("\n" + "="*70)
        print(f"RESULTS ({len(products)} products)")
        print("="*70)

        if not products:
            print("\nNo products found. Try a different query.")
            print()
            return

        for i, product in enumerate(products, 1):
            print(f"\n{i}. {product.get('title', 'Unknown Product')}")
            print(f"   Price: ${product.get('price', 0):.2f}")

            if 'category' in product:
                print(f"   Category: {product['category']}")

            if 'brand' in product and product['brand']:
                print(f"   Brand: {product['brand']}")

            # Show agent scores if available
            if 'cypher_score' in product:
                print(f"   Scores: Graph={product.get('cypher_score', 0):.2f} "
                      f"Vector={product.get('vibe_score', 0):.2f} "
                      f"Visual={product.get('visual_score', 0):.2f}")

        # Show reasoning
        if 'reasoning' in result:
            print(f"\n  {result['reasoning'][:200]}")

        print("\n" + "="*70)
        print()

    async def show_profile(self):
        """Display user profile."""
        profile = self.user_service.get_user_profile(self.current_user.id)

        if not profile:
            print("\nProfile not found.")
            return

        print("\n" + "="*70)
        print("YOUR COMPLETE PROFILE")
        print("="*70)

        user = profile.user

        print(f"\nUsername: {user.username}")
        print(f"Email: {user.email}")
        print(f"Member since: {user.created_at.strftime('%Y-%m-%d')}")

        if user.age_range:
            print(f"Age Range: {user.age_range}")

        if user.location:
            print(f"Location: {user.location}")

        print("\n--- STYLE PREFERENCES ---")

        if profile.style_adjectives:
            print("Style: " + ", ".join([adj.name for adj in profile.style_adjectives[:3]]))

        if profile.fit_preferences:
            print("Fit: " + ", ".join(profile.fit_preferences))

        if profile.occasions:
            print("Occasions: " + ", ".join([occ.name for occ in profile.occasions[:3]]))

        print("\n--- SHOPPING ---")

        if user.shopping_behavior:
            print(f"Shopping Style: {user.shopping_behavior}")

        if user.monthly_budget_min and user.monthly_budget_max:
            print(f"Monthly Budget: ${user.monthly_budget_min}-${user.monthly_budget_max}")

        if user.aspiration_text:
            print(f"\nYour Goal: \"{user.aspiration_text}\"")

        print("\n" + "="*70)
        print()

    async def show_stats(self):
        """Display user statistics."""
        stats = self.user_service.get_user_stats(self.current_user.id)

        print("\n" + "="*70)
        print("YOUR STATISTICS")
        print("="*70)

        print(f"\nTotal Searches: {stats.get('total_searches', 0)}")
        print(f"Products Viewed: {stats.get('total_products_viewed', 0)}")
        print(f"Products Saved: {stats.get('total_products_saved', 0)}")
        print(f"Purchases: {stats.get('total_purchases', 0)}")

        drift = stats.get('preference_drift', 0)
        confidence = stats.get('observation_confidence', 0)

        if confidence > 0.3:
            print(f"\nPreference Learning: {confidence*100:.0f}% confidence")

            if drift < 1.0:
                print("  Your choices match your stated preferences well!")
            elif drift < 2.0:
                print("  Minor differences between stated and observed preferences.")
            else:
                print("  Your style may be evolving! Consider updating your profile.")

        print("\n" + "="*70)
        print()

    # ======================
    # MAIN ENTRY POINT
    # ======================

    async def run(self):
        """Main entry point."""
        try:
            # Authenticate
            await self.authenticate()

            # Start chat
            await self.start_chat()

        finally:
            self.close()


async def main():
    """Main function."""
    interface = EnhancedChatInterface()
    await interface.run()


if __name__ == "__main__":
    asyncio.run(main())
