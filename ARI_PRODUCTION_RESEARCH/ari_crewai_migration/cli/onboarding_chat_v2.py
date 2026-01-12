"""
Conversational Onboarding CLI V2
Based on Miro Flow - October 2025

Standalone script for running the new onboarding flow with:
- Node-based structure (Personal, Taste, Process, Practicality, Body, External)
- Two-tier progression
- Skip/pass handling
- ARI personality responses
- Photo and social media placeholders

Usage:
    python cli/onboarding_chat_v2.py
"""

import sys
import os
import asyncio
from datetime import datetime
from typing import Optional

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crews.onboarding_crew_v2 import create_onboarding_crew_v2
from prompts.onboarding_prompts_v2 import get_all_nodes, get_node_by_id
from services.user_service import UserService
from services.onboarding_service import OnboardingService


class ConversationalOnboardingV2:
    """
    Conversational onboarding interface V2.

    Features:
    - Engage users in natural dialogue
    - Extract structured information with V2 node structure
    - Handle skip/pass gracefully
    - Support photo and social media integration
    - Store data in Neo4j
    """

    def __init__(self):
        """Initialize conversational onboarding V2."""
        # Create GPT-5 LLM for onboarding agents
        from crewai.llm import LLM
        llm = LLM(
            model="gpt-5",
            temperature=1  # GPT-5 only supports temperature=1
        )

        self.crew = create_onboarding_crew_v2(llm=llm)
        self.user_service = UserService()
        self.onboarding_service = OnboardingService()

        self.username: Optional[str] = None
        self.email: Optional[str] = None
        self.user_id: Optional[str] = None

    def print_welcome(self):
        """Print welcome message."""
        print("\n" + "=" * 70)
        print(" Welcome to ARI V2 - Your Personal Style Discovery Experience")
        print("=" * 70)
        print()
        print("I'm here to help you discover and articulate your style identity.")
        print("This is a conversation, not a form - let's explore who you are.")
        print()
        print("We'll talk about:")
        print("  • WHO you are (your identity and experiences)")
        print("  • WHAT you love aesthetically (your taste)")
        print("  • HOW you make decisions (your process)")
        print("  • WHAT'S practical for you (your constraints)")
        print()
        print("Take your time. Share what feels right. You can skip anything that doesn't.")
        print()
        print("=" * 70 + "\n")

    def print_node_intro(self, node_id: str):
        """Print introduction for a new node."""
        node = get_node_by_id(node_id)
        print(f"\n{'=' * 70}")
        print(f" {node.get('title', 'Next Topic')}")
        print(f"{'=' * 70}\n")

    def print_progress(self):
        """Print progress indicator."""
        percentage = self.crew.get_completion_percentage()
        all_nodes = get_all_nodes()
        completed_count = sum(1 for node_id in all_nodes
                            if node_id in self.crew.node_completion
                            and self.crew.node_completion[node_id].get("need_to_ask", False))

        print(f"\n[Progress: {completed_count}/{len(all_nodes)} nodes complete - {percentage*100:.0f}%]\n")

    async def collect_basic_info(self) -> bool:
        """
        Collect username and email.

        Returns:
            Success boolean
        """
        print("First, let's get you set up.\n")

        while True:
            username = input("What would you like me to call you? ").strip()
            if username:
                self.username = username
                break
            print("Please enter a name.\n")

        # Check if user exists
        existing_user = self.user_service.get_user_by_username(username)

        if existing_user:
            print(f"\nWelcome back, {username}!")
            if existing_user.onboarding_completed:
                response = input("\nYou've already completed onboarding. Start fresh? (yes/no): ").strip().lower()
                if response != 'yes':
                    return False

            self.user_id = existing_user.id
            self.email = existing_user.email
            return True

        # New user - collect email
        while True:
            email = input("\nWhat's your email address? ").strip()
            if email and '@' in email:
                self.email = email
                break
            print("Please enter a valid email address.\n")

        # Create user
        try:
            user = self.user_service.create_user(username, email)
            self.user_id = user.id
            print(f"\nGreat! Welcome to ARI, {username}.\n")
            return True
        except Exception as e:
            print(f"\nError creating user: {e}")
            return False

    async def run_conversation(self):
        """
        Run the conversational onboarding flow with V2 structure.
        """
        # Start with first node
        all_nodes = get_all_nodes()
        node_index = 0

        while node_index < len(all_nodes):
            current_node = all_nodes[node_index]

            self.print_node_intro(current_node)
            self.print_progress()

            # Start need_to_ask tier
            opening_message = self.crew.start_node(current_node, tier="need_to_ask")
            print(f"ARI: {opening_message}\n")

            tier_complete = False
            offering_nice_to_know = False

            while not tier_complete:
                # Get user input
                user_input = input("You: ").strip()

                if not user_input:
                    print("(Please share your thoughts, or type 'skip' if you'd prefer to move on)\n")
                    continue

                # Handle quit
                if user_input.lower() in ['quit', 'exit']:
                    print("\nYour progress has been saved. You can continue anytime!")
                    return False

                # Process response
                try:
                    result = self.crew.process_user_response(user_input)

                    agent_response = result.get('agent_response', '')
                    tier_complete = result.get('tier_complete', False)
                    offering_progression = result.get('offering_progression', False)

                    print(f"\nARI: {agent_response}\n")

                    # Check if skip handled or raincheck offered
                    if result.get('offer_raincheck', False):
                        raincheck_response = input("\nWhat would you like to do? ").strip().lower()
                        if 'break' in raincheck_response or 'another time' in raincheck_response:
                            print("\nNo problem! Your progress is saved. See you soon!")
                            return False

                    # If offering progression to nice_to_know or next node
                    if tier_complete and offering_progression:
                        # Check if we should offer nice_to_know
                        if self.crew.should_offer_nice_to_know(current_node):
                            proceed = input("\nWould you like to explore this area more deeply? (yes/no): ").strip().lower()
                            if proceed == 'yes':
                                # Move to nice_to_know tier
                                self.crew.complete_tier(current_node, "need_to_ask")
                                self.crew.current_tier = "nice_to_know"
                                print(f"\nARI: Great! Let's go deeper...\n")
                                tier_complete = False  # Continue with nice_to_know
                            else:
                                # Move to next node
                                self.crew.complete_tier(current_node, "need_to_ask")
                                self.crew.complete_tier(current_node, "nice_to_know")  # Mark as skipped
                                break
                        else:
                            # No nice_to_know, just complete and move on
                            self.crew.complete_tier(current_node, "need_to_ask")
                            break

                    # Auto-complete if agent determines it's done
                    elif tier_complete:
                        current_tier = self.crew.current_tier
                        self.crew.complete_tier(current_node, current_tier)

                        if current_tier == "need_to_ask":
                            # Check for nice_to_know
                            if self.crew.should_offer_nice_to_know(current_node):
                                offering_nice_to_know = True
                            else:
                                break
                        else:
                            # Completed nice_to_know, move on
                            break

                except Exception as e:
                    print(f"\n(Oops, I had trouble processing that. Could you rephrase?)")
                    print(f"[DEBUG] Error: {e}")
                    import traceback
                    print(f"[DEBUG] Traceback:\n{traceback.format_exc()}\n")

            # If offering nice_to_know after need_to_ask complete
            if offering_nice_to_know:
                proceed = input("\nWould you like to go deeper into this area? (yes/no): ").strip().lower()
                if proceed == 'yes':
                    self.crew.current_tier = "nice_to_know"
                    nice_opening = f"Let's explore {get_node_by_id(current_node).get('title', 'this')} more deeply..."
                    print(f"\nARI: {nice_opening}\n")

                    # Continue with nice_to_know tier
                    tier_complete = False
                    while not tier_complete:
                        user_input = input("You: ").strip()
                        if not user_input:
                            continue

                        try:
                            result = self.crew.process_user_response(user_input)
                            agent_response = result.get('agent_response', '')
                            tier_complete = result.get('tier_complete', False)

                            print(f"\nARI: {agent_response}\n")

                            if tier_complete:
                                self.crew.complete_tier(current_node, "nice_to_know")
                                break

                        except Exception as e:
                            print(f"\n(Oops, error: {e})\n")
                else:
                    # Skip nice_to_know
                    self.crew.complete_tier(current_node, "nice_to_know")

            # Move to next node
            node_index += 1

        return True

    async def save_onboarding_data(self):
        """
        Save extracted data to Neo4j.
        """
        print("\n" + "=" * 70)
        print(" Saving Your Style Profile...")
        print("=" * 70 + "\n")

        all_data = self.crew.get_all_extracted_data()

        # Save each node's data
        for node_id, node_data in all_data["nodes"].items():
            try:
                await self.onboarding_service.store_step_responses(
                    user_id=self.user_id,
                    step_id=node_id,  # Using node_id as step_id for now
                    responses=node_data
                )
                print(f"Saved {node_id} data")
            except Exception as e:
                print(f"[ERROR] Error saving {node_id}: {e}")

        # Save root values
        if all_data["root_values"]:
            try:
                # Store root values as a special section
                await self.onboarding_service.store_step_responses(
                    user_id=self.user_id,
                    step_id="root_values",
                    responses={"values": all_data["root_values"]}
                )
                print(f"Saved root values")
            except Exception as e:
                print(f"[ERROR] Error saving root values: {e}")

        # Save metadata
        try:
            await self.onboarding_service.store_step_responses(
                user_id=self.user_id,
                step_id="onboarding_metadata",
                responses=all_data["metadata"]
            )
            print(f"Saved metadata")
        except Exception as e:
            print(f"[ERROR] Error saving metadata: {e}")

        # Mark onboarding complete
        self.user_service.update_user_profile(self.user_id, {
            'onboarding_completed': True,
            'onboarding_completed_at': datetime.now()
        })

        print("\nYour style profile has been saved!\n")

    async def run(self):
        """Run the full onboarding experience."""
        try:
            self.print_welcome()

            # Collect basic info
            if not await self.collect_basic_info():
                print("\nExiting...")
                return

            # Run conversational flow
            completed = await self.run_conversation()

            if completed:
                # Save data
                await self.save_onboarding_data()

                print("=" * 70)
                print(" Onboarding Complete!")
                print("=" * 70)
                print()
                print(f"Welcome to ARI, {self.username}!")
                print("Your style profile is ready. Let's find your perfect pieces.")
                print()

        except KeyboardInterrupt:
            print("\n\nInterrupted. Your progress has been saved.")
        except Exception as e:
            print(f"\n\nUnexpected error: {e}")
            print("Your progress has been saved. Please try again later.")
            import traceback
            traceback.print_exc()


async def main():
    """Main entry point."""
    onboarding = ConversationalOnboardingV2()
    await onboarding.run()


if __name__ == "__main__":
    asyncio.run(main())
