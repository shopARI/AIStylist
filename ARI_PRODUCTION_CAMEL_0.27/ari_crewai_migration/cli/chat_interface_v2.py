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
import warnings
from datetime import datetime
from typing import Optional, Dict, Any

# Suppress deprecation warnings for cleaner output
warnings.filterwarnings("ignore", category=DeprecationWarning)

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
from memory.mem0_memory_provider import create_mem0_memory_provider


class EnhancedChatInterface:
    """Enhanced chat interface with user awareness."""

    def __init__(self):
        """Initialize chat interface."""
        self.user_service = UserService()
        self.onboarding_service = OnboardingService()

        self.orchestrator = None
        self.current_user: Optional[User] = None
        self.session_id = f"session_{uuid.uuid4().hex[:8]}"
        self.mem0 = None  # Initialized after user authentication

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

        # Initialize Mem0 for this user
        mem0 = create_mem0_memory_provider(user_id, f"onboarding_{self.session_id}")

        # Track onboarding start
        try:
            await mem0.add_episodic(
                f"Started onboarding for user {username}",
                metadata={"event": "onboarding_start", "email": email}
            )
        except Exception as mem_error:
            print(f"[DEBUG] Warning: Memory storage failed: {mem_error}")

        # Create onboarding crew with GPT-5
        from crewai.llm import LLM
        llm = LLM(
            model="gpt-5",
            temperature=1  # GPT-5 only supports temperature=1
        )
        crew = create_onboarding_crew(llm=llm)

        # Run through all onboarding steps
        all_steps = get_all_step_ids()

        for step_id in all_steps:
            print(f"\n{'=' * 70}")
            print(f" Topic {all_steps.index(step_id) + 1}/{len(all_steps)}")
            print(f"{'=' * 70}\n")

            # Start step
            opening_message = crew.start_step(step_id)
            print(f"ARI: {opening_message}\n")

            # Track opening message
            try:
                await mem0.add_episodic(
                    f"ARI: {opening_message}",
                    metadata={"step": step_id, "turn_type": "opening"}
                )
            except Exception as mem_error:
                print(f"[DEBUG] Warning: Memory storage failed: {mem_error}")

            step_complete = False

            while not step_complete:
                # Get user input
                user_input = input("You: ").strip()

                if not user_input:
                    print("(Please share your thoughts, or type 'skip' to move on)\n")
                    continue

                # Track user input
                try:
                    await mem0.add_episodic(
                        f"User: {user_input}",
                        metadata={"step": step_id, "turn_type": "user_input"}
                    )
                except Exception as mem_error:
                    print(f"[DEBUG] Warning: Memory storage failed: {mem_error}")

                #  Handle skip
                if user_input.lower() in ['skip', 'next']:
                    crew.complete_step()
                    try:
                        await mem0.add_episodic(
                            f"User skipped step: {step_id}",
                            metadata={"step": step_id, "action": "skip"}
                        )
                    except Exception as mem_error:
                        print(f"[DEBUG] Warning: Memory storage failed: {mem_error}")
                    break

                # Process response
                try:
                    result = crew.process_user_response(user_input)
                    agent_response = result.get('agent_response', '')
                    completeness = result.get('completeness', 0.0)

                    print(f"\nARI: {agent_response}\n")

                    # Track agent response (non-blocking)
                    try:
                        await mem0.add_episodic(
                            f"ARI: {agent_response}",
                            metadata={"step": step_id, "turn_type": "agent_response", "completeness": completeness}
                        )
                    except Exception as mem_error:
                        print(f"[DEBUG] Warning: Memory storage failed: {mem_error}")

                    # Auto-complete if agent suggests moving on
                    if completeness >= 0.8 or 'move on' in agent_response.lower():
                        crew.complete_step()
                        step_complete = True

                except Exception as e:
                    print(f"\n(Could you rephrase that?)\n")
                    print(f"[DEBUG] Error processing response: {e}")
                    import traceback
                    print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")

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

        # Store onboarding data in Mem0 (non-blocking)
        try:
            await self._store_onboarding_in_mem0(mem0, all_data)
        except Exception as mem_error:
            print(f"[DEBUG] Warning: Memory storage failed: {mem_error}")

        # Mark complete
        self.user_service.update_user_profile(user_id, {
            'onboarding_completed': True,
            'onboarding_completed_at': datetime.now()
        })

        # Track onboarding completion (non-blocking)
        try:
            await mem0.add_episodic(
                f"Completed onboarding successfully",
                metadata={"event": "onboarding_complete", "steps_completed": len(all_data)}
            )
        except Exception as mem_error:
            print(f"[DEBUG] Warning: Memory storage failed: {mem_error}")

        print("Your style profile has been saved!\n")

        # Return updated user
        return self.user_service.get_user_by_username(username)

    async def _store_onboarding_in_mem0(self, mem0, all_data: Dict[str, Any]):
        """
        Store onboarding data in Mem0 factual and semantic memories.

        Args:
            mem0: Mem0 provider instance
            all_data: Extracted onboarding data
        """
        # Style autonomy data
        if 'style_autonomy' in all_data:
            data = all_data['style_autonomy']

            if 'decision_making_style' in data:
                await mem0.add_factual(
                    f"Decision-making style: {data['decision_making_style']}",
                    category="preferences"
                )

            if 'risk_tolerance' in data:
                await mem0.add_factual(
                    f"Style risk tolerance: {data['risk_tolerance']}/10",
                    category="preferences"
                )

            if 'advice_receptiveness' in data:
                await mem0.add_semantic(
                    f"User prefers {'guided recommendations' if data['advice_receptiveness'] < 5 else 'independent exploration'} when shopping"
                )

        # Gender expression data
        if 'gender_expression' in all_data:
            data = all_data['gender_expression']

            if 'expression_spectrum' in data:
                await mem0.add_factual(
                    f"Gender expression spectrum: {data['expression_spectrum']}/10",
                    category="identity"
                )

        # Self-expression data
        if 'self_expression' in all_data:
            data = all_data['self_expression']

            if 'aspiration' in data:
                await mem0.add_factual(
                    f"Style aspiration: {data['aspiration']}",
                    category="goals"
                )

            if 'style_adjectives' in data and data['style_adjectives']:
                adjectives = ', '.join(data['style_adjectives'])
                await mem0.add_factual(
                    f"Preferred style adjectives: {adjectives}",
                    category="style_preference"
                )

                # Semantic relationships for each adjective
                for adj in data['style_adjectives']:
                    await mem0.add_semantic(
                        f"User identifies with {adj} aesthetic",
                        metadata={"entity_type": "style", "entity_value": adj}
                    )

        # Lifestyle context data
        if 'lifestyle_context' in all_data:
            data = all_data['lifestyle_context']

            if 'occasions' in data and data['occasions']:
                occasions = ', '.join(data['occasions'])
                await mem0.add_factual(
                    f"Typical occasions: {occasions}",
                    category="lifestyle"
                )

        # Values and shopping data
        if 'values_shopping' in all_data:
            data = all_data['values_shopping']

            if 'shopping_behavior' in data:
                await mem0.add_factual(
                    f"Shopping behavior: {data['shopping_behavior']}",
                    category="behavior"
                )

            if 'values' in data and data['values']:
                values = ', '.join(data['values'])
                await mem0.add_factual(
                    f"Shopping values: {values}",
                    category="values"
                )

                # Semantic relationships for values
                for value in data['values']:
                    await mem0.add_semantic(
                        f"User prioritizes {value} when shopping",
                        metadata={"entity_type": "value", "entity_value": value}
                    )

        # Budget data
        if 'budget' in all_data:
            data = all_data['budget']

            if 'budget_min' in data and 'budget_max' in data:
                await mem0.add_factual(
                    f"Monthly budget: ${data['budget_min']}-${data['budget_max']}",
                    category="budget"
                )

        # Demographics data
        if 'demographics_contact' in all_data:
            data = all_data['demographics_contact']

            if 'age_range' in data:
                await mem0.add_factual(
                    f"Age range: {data['age_range']}",
                    category="demographics"
                )

            if 'location' in data:
                await mem0.add_factual(
                    f"Location: {data['location']}",
                    category="demographics"
                )

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

            # BYPASS: user0 skips onboarding for testing
            if username.lower() == "user0":
                print("\nTest mode: Bypassing onboarding, going straight to recommendations...\n")

                # Check if user0 already exists
                user = self.user_service.get_user_by_username(username)

                if user is None:
                    # Create minimal test user
                    try:
                        user = self.user_service.create_user(
                            username=username,
                            email="user0@test.com"
                        )

                        # Update profile with test defaults
                        profile_data = {
                            'onboarding_completed': True,
                            'decision_making_style': 'curated_options',
                            'monthly_budget_max': 500,
                            'monthly_budget_min': 0
                        }

                        user = self.user_service.update_user_profile(user.id, profile_data)

                        if user:
                            print(f"✓ Test user '{username}' created and ready!")
                        else:
                            print(f"✗ Failed to configure test user")
                            continue

                    except Exception as e:
                        print(f"Error creating test user: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                else:
                    # Existing user0 - ensure onboarding is marked complete
                    if not user.onboarding_completed:
                        self.user_service.mark_onboarding_complete(user.id)
                        user = self.user_service.get_user_by_id(user.id)

                    print(f"✓ Welcome back, test user '{username}'!")

                self.current_user = user

                # Initialize Mem0 for test user
                self.mem0 = create_mem0_memory_provider(user.id, self.session_id)

                break

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

            # Initialize Mem0 for authenticated user
            self.mem0 = create_mem0_memory_provider(user.id, self.session_id)

            # Track login
            await self.mem0.add_episodic(
                f"User {username} logged in",
                metadata={"event": "login", "session_id": self.session_id}
            )

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

        context = {
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

        # Add recent conversation context from Mem0
        if self.mem0:
            recent_searches = await self.mem0.get_episodic(limit=5)
            if recent_searches:
                context["recent_activity"] = [
                    mem["content"] for mem in recent_searches
                ]

        return context

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

                # Track user query in Mem0
                await self.mem0.add_episodic(
                    f"User searched: {query}",
                    metadata={"interaction_type": "search", "query": query}
                )

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

                # Track interaction in Neo4j
                await self.track_search(query, result)

                # Track search results in Mem0
                products = result.get("products", [])
                if products:
                    product_summary = f"Showed {len(products)} products: " + ", ".join(
                        [p.get('title', '')[:30] for p in products[:3]]
                    )
                    await self.mem0.add_episodic(
                        product_summary,
                        metadata={
                            "interaction_type": "search_results",
                            "product_count": len(products),
                            "query": query
                        }
                    )

                    # Track semantic relationships with products
                    for product in products[:3]:  # Top 3 products
                        if 'brand' in product and product['brand']:
                            await self.mem0.add_semantic(
                                f"User saw {product['brand']} {product.get('category', 'product')} when searching for {query}",
                                metadata={
                                    "brand": product['brand'],
                                    "category": product.get('category', ''),
                                    "product_id": product.get('id', '')
                                }
                            )

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
        """Display search results or conversation response."""
        products = result.get("products", [])

        # Check if this is a conversation response (not a product search)
        if "response" in result and result.get("metadata", {}).get("is_conversation", False):
            print("\n" + "="*70)
            print("ARI")
            print("="*70)
            print(f"\n{result['response']}\n")
            print("="*70)
            print()
            return

        # Get bot contribution stats and timing from metadata
        metadata = result.get("metadata", {})
        graph_count = metadata.get("graph_count", 0)
        vector_count = metadata.get("vector_count", 0)
        visual_count = metadata.get("visual_count", 0)

        # Get execution times
        graph_time = metadata.get("graph_execution_time", 0)
        vector_time = metadata.get("vector_execution_time", 0)
        visual_time = metadata.get("visual_execution_time", 0)
        judge_time = metadata.get("judge_execution_time", 0)
        total_time = result.get("execution_time", 0)

        # Get intent detection time if available
        intent_info = result.get("intent", {})
        intent_time = intent_info.get("detection_time", 0)

        print("\n" + "="*70)
        print(f"RESULTS ({len(products)} products)")

        # Show bot contributions with timing
        bot_summary = []
        if graph_count > 0:
            bot_summary.append(f"CypherBot: {graph_count} ({graph_time:.2f}s)")
        else:
            bot_summary.append(f"CypherBot: 0 ({graph_time:.2f}s)")

        if vector_count > 0:
            bot_summary.append(f"VibeBot: {vector_count} ({vector_time:.2f}s)")
        else:
            bot_summary.append(f"VibeBot: 0 ({vector_time:.2f}s)")

        if visual_count > 0:
            bot_summary.append(f"VisionBot: {visual_count} ({visual_time:.2f}s)")
        else:
            bot_summary.append(f"VisionBot: 0 ({visual_time:.2f}s)")

        print(f"Bot Contributions: {' | '.join(bot_summary)}")

        # Show timing breakdown
        if judge_time > 0:
            print(f"Judge: {judge_time:.2f}s | Intent: {intent_time:.2f}s | Total: {total_time:.2f}s")
        else:
            print(f"Intent: {intent_time:.2f}s | Total: {total_time:.2f}s")

        print("="*70)

        if not products:
            print("\nNo products found. Try a different query.")
            print()
            return

        for i, product in enumerate(products, 1):
            print(f"\n{i}. {product.get('title', 'Unknown Product')}")

            # Handle price display with None check
            price = product.get('price', 0)
            if price is not None:
                print(f"   Price: ${price:.2f}")
            else:
                print(f"   Price: N/A")

            if 'category' in product and product['category']:
                print(f"   Category: {product['category']}")

            if 'brand' in product and product['brand']:
                print(f"   Brand: {product['brand']}")

            # Show which bot(s) found this product and their scores
            cypher_score = product.get('cypher_score')
            vibe_score = product.get('vibe_score')
            visual_score = product.get('visual_score')

            # Determine source bots
            source_bots = []
            if cypher_score is not None:
                source_bots.append("CypherBot")
            if vibe_score is not None:
                source_bots.append("VibeBot")
            if visual_score is not None:
                source_bots.append("VisionBot")

            if source_bots:
                print(f"   Found by: {', '.join(source_bots)}")

            # Show scores
            if cypher_score is not None or vibe_score is not None or visual_score is not None:
                scores = []
                if cypher_score is not None:
                    scores.append(f"Graph={cypher_score:.2f}")
                if vibe_score is not None:
                    scores.append(f"Vector={vibe_score:.2f}")
                if visual_score is not None:
                    scores.append(f"Visual={visual_score:.2f}")
                if scores:
                    print(f"   Scores: {' '.join(scores)}")

        # Show reasoning
        if 'reasoning' in result and result['reasoning']:
            reasoning = result['reasoning']
            # Show full reasoning, but format nicely for long text
            if len(reasoning) > 500:
                # For very long reasoning, wrap text nicely
                import textwrap
                wrapped = textwrap.fill(reasoning, width=68, initial_indent='  ', subsequent_indent='  ')
                print(f"\n{wrapped}")
            else:
                print(f"\n  {reasoning}")

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
