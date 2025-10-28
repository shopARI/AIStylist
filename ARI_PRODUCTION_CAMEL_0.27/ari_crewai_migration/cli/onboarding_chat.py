"""
Conversational Onboarding Interface

A natural dialogue-based onboarding experience using AI agents.
"""

import asyncio
import sys
import os
from typing import Optional, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from crews.onboarding_crew import create_onboarding_crew
from services.user_service import UserService
from services.onboarding_service import OnboardingService
from models.user_models import User
from prompts.onboarding_prompts import get_step_prompt, get_all_step_ids


class ConversationalOnboarding:
    """
    Manages conversational onboarding flow.

    Uses AI agents to:
    - Engage users in natural dialogue
    - Extract structured information
    - Store data in Neo4j
    """

    def __init__(self):
        """Initialize conversational onboarding."""
        self.crew = create_onboarding_crew()
        self.user_service = UserService()
        self.onboarding_service = OnboardingService()

        self.username: Optional[str] = None
        self.email: Optional[str] = None
        self.user_id: Optional[str] = None

    def print_welcome(self):
        """Print welcome message."""
        print("\n" + "=" * 70)
        print(" Welcome to ARI - Your Personal Style Discovery Experience")
        print("=" * 70)
        print()
        print("I'm here to help you discover and articulate your style identity.")
        print("This isn't a form or quiz - it's a conversation.")
        print()
        print("We'll explore topics like:")
        print("  - How you like to make style decisions")
        print("  - What makes you feel confident and authentic")
        print("  - Your lifestyle and practical needs")
        print("  - What matters to you beyond just aesthetics")
        print()
        print("Take your time. There are no wrong answers.")
        print("You can explore topics deeply or move quickly - it's up to you.")
        print()
        print("=" * 70 + "\n")

    def print_step_intro(self, step_id: str):
        """Print introduction for a new step."""
        prompt = get_step_prompt(step_id)
        print(f"\n{'=' * 70}")
        print(f" {prompt.get('title', 'Next Topic')}")
        print(f"{'=' * 70}\n")

    def print_progress(self):
        """Print progress indicator."""
        percentage = self.crew.get_completion_percentage()
        completed_steps = sum(1 for step in get_all_step_ids()
                            if self.crew.step_completion.get(step, False))
        total_steps = len(get_all_step_ids())

        print(f"\n[Progress: {completed_steps}/{total_steps} topics complete - {percentage*100:.0f}%]\n")

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
        Run the conversational onboarding flow.
        """
        # Start with first step
        current_step = self.crew.get_next_step()

        while current_step:
            self.print_step_intro(current_step)
            self.print_progress()

            # Start the conversation for this step
            opening_message = self.crew.start_step(current_step)
            print(f"ARI: {opening_message}\n")

            step_complete = False

            while not step_complete:
                # Get user input
                user_input = input("You: ").strip()

                if not user_input:
                    print("(Please share your thoughts, or type 'skip' if you'd prefer to move on)\n")
                    continue

                # Handle special commands
                if user_input.lower() in ['skip', 'next', 'move on']:
                    response = input("\nReady to move to the next topic? (yes/no): ").strip().lower()
                    if response == 'yes':
                        self.crew.complete_step()
                        break
                    else:
                        print("\nNo problem, let's continue.\n")
                        continue

                if user_input.lower() in ['quit', 'exit']:
                    print("\nYour progress has been saved. You can continue anytime!")
                    return False

                # Process response
                try:
                    result = self.crew.process_user_response(user_input)

                    agent_response = result.get('agent_response', '')
                    completeness = result.get('completeness', 0.0)

                    print(f"\nARI: {agent_response}\n")

                    # Check if agent suggests moving on
                    if any(phrase in agent_response.lower() for phrase in
                           ['ready to move', 'shall we move', 'move on to', 'next topic']):
                        response = input("\n(Type 'yes' to continue to next topic, or keep chatting): ").strip().lower()
                        if response == 'yes':
                            self.crew.complete_step()
                            step_complete = True

                    # Auto-complete if highly complete and no questions pending
                    elif completeness >= 0.9 and '?' not in agent_response[-50:]:
                        self.crew.complete_step()
                        step_complete = True

                except Exception as e:
                    print(f"\n(Oops, I had trouble processing that. Could you rephrase?)")
                    print(f"Error: {e}\n")

            # Move to next step
            current_step = self.crew.get_next_step()

        return True

    async def save_onboarding_data(self):
        """
        Save extracted data to Neo4j.
        """
        print("\n" + "=" * 70)
        print(" Saving Your Style Profile...")
        print("=" * 70 + "\n")

        all_data = self.crew.get_all_extracted_data()

        try:
            # Process each step's data
            for step_id, step_data in all_data.items():
                # The onboarding service knows how to store each step
                await self.onboarding_service.store_step_responses(
                    user_id=self.user_id,
                    step_id=step_id,
                    responses=step_data
                )

            # Mark onboarding as complete
            self.user_service.update_user_profile(self.user_id, {
                'onboarding_completed': True,
                'onboarding_completed_at': datetime.now()
            })

            print("Your style profile has been saved!")
            print("\nYou're all set! Let's find you some amazing pieces.\n")

        except Exception as e:
            print(f"\nError saving profile: {e}")
            print("Your responses were collected but there was an error saving.")
            print("Please contact support.\n")

    async def run(self):
        """
        Run the complete conversational onboarding experience.
        """
        self.print_welcome()

        # Collect basic info
        if not await self.collect_basic_info():
            return

        input("\nPress Enter when you're ready to begin...\n")

        # Run conversation
        completed = await self.run_conversation()

        if completed:
            # Save to database
            await self.save_onboarding_data()

            print("=" * 70)
            print(" Thank You!")
            print("=" * 70)
            print("\nI really enjoyed getting to know you and your style.")
            print("You can update your preferences anytime, and I'll keep learning")
            print("what works for you as we go.\n")

        else:
            print("\nNo problem! Your progress is saved.")
            print("Just run this again when you're ready to continue.\n")


async def main():
    """Entry point for conversational onboarding."""
    onboarding = ConversationalOnboarding()
    try:
        await onboarding.run()
    except KeyboardInterrupt:
        print("\n\nProgress saved. See you soon!\n")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        print("Your progress has been saved. Please try again later.\n")


if __name__ == "__main__":
    asyncio.run(main())
