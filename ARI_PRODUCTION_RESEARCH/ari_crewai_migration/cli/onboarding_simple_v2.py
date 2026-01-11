"""
Simple Onboarding V2 - Standalone demo using production V2 prompts.
No database required. Just run and chat.

This script uses the REAL onboarding_prompts_v2.py - the same sophisticated
prompts used in production, not a simplified version.

Usage:
    python cli/onboarding_simple_v2.py

Requirements:
    pip install openai python-dotenv
    Set OPENAI_API_KEY in environment or .env file
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.onboarding_prompts_v2 import (
    ARI_PERSONALITY,
    GLOBAL_DIALOGUE_RULES,
    get_node_by_id,
)

# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Configuration
DEFAULT_MODEL = "gpt-4o"
MAX_CONVERSATION_TURNS = 30

# Initialize OpenAI client
client = None


def get_client() -> OpenAI:
    """Get or create OpenAI client with error handling."""
    global client
    if client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not found in environment or .env file")
            sys.exit(1)
        client = OpenAI(api_key=api_key)
    return client


def build_system_prompt(current_node_id: str = "personal") -> str:
    """
    Build system prompt using actual V2 prompts.

    Args:
        current_node_id: The current conversation node

    Returns:
        Full system prompt with V2 content
    """
    node = get_node_by_id(current_node_id)

    # Build ARI personality section
    personality_section = f"""
=== WHO YOU ARE ===
{ARI_PERSONALITY.get('origin_story', '')}

When asked irrelevant questions:
{ARI_PERSONALITY.get('irrelevant_fallback', '')}
"""

    # Build current node context
    node_context = f"""
=== CURRENT TOPIC: {node.get('title', 'Getting to Know You')} ===
{node.get('description', '')}

OPENING APPROACH:
{node.get('opening_message', '')}

CONVERSATION GUIDE:
{node.get('conversation_guide', '')}

TRANSITION WHEN COMPLETE:
{node.get('transition_to_next', '')}
"""

    # Combine into full prompt
    system_prompt = f"""
You are ARI - a warm, intuitive style confidant.

{personality_section}

{GLOBAL_DIALOGUE_RULES}

{node_context}

=== FLOW ===
You are currently exploring: {node.get('title', 'Personal')}

The full conversation flow is:
1. Personal (who they are)
2. Taste (what they love)
3. Process (how they decide)
4. Practicality (budget/constraints)

Follow THEIR thread naturally. When you've gathered enough on this topic,
transition smoothly to the next.

=== REMEMBER ===
You're their trusted confidant. You see them. You get them.
ONE question per message. Short responses. Sound human. Show you care.
"""
    return system_prompt


def get_ai_response(
    messages: List[Dict[str, str]],
    openai_client: OpenAI,
    model: str = DEFAULT_MODEL
) -> Optional[str]:
    """Get response from OpenAI with error handling."""
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.9
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"\nError communicating with OpenAI: {e}")
        return None


def is_conversation_complete(message: str) -> bool:
    """Check if the conversation has reached natural completion."""
    completion_phrases = [
        "i really get your vibe",
        "excited to help you find",
        "thanks for sharing all of that",
        "i've got a great sense",
        "got a good picture of your style",
        "ready to find you some",
        "i feel like i know you",
        "let's find you some amazing",
    ]
    return any(phrase in message.lower() for phrase in completion_phrases)


def detect_node_transition(message: str, current_node: str) -> Optional[str]:
    """Detect if the AI is transitioning to a new node."""
    node_order = ["personal", "taste", "process", "practicality"]
    current_index = node_order.index(current_node) if current_node in node_order else 0

    # Check for transition phrases
    transition_phrases = {
        "taste": ["style", "aesthetic", "what you're drawn to", "taste"],
        "process": ["how you decide", "how you shop", "decisions", "adventurous"],
        "practicality": ["budget", "practical", "constraints", "realistic"],
    }

    msg_lower = message.lower()

    # Check if transitioning to next node
    if current_index < len(node_order) - 1:
        next_node = node_order[current_index + 1]
        if any(phrase in msg_lower for phrase in transition_phrases.get(next_node, [])):
            # Only transition if it sounds like a topic change
            if any(word in msg_lower for word in ["now", "let's", "moving", "next", "talk about"]):
                return next_node

    return None


def chat():
    """Run the conversational onboarding using V2 prompts."""
    openai_client = get_client()
    current_node = "personal"
    turn_count = 0

    # Build initial system prompt
    system_prompt = build_system_prompt(current_node)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    print("\n" + "=" * 60)
    print(" ARI Style Discovery (V2 Prompts)")
    print("=" * 60)
    print("\nThis is a conversation, not a form. Share what feels right.")
    print("Type 'quit' to exit anytime.\n")
    print("=" * 60 + "\n")

    # Get first message from ARI
    initial_messages = messages + [
        {"role": "user", "content": "Hi, I'm ready to discover my style"}
    ]
    assistant_msg = get_ai_response(initial_messages, openai_client)

    if not assistant_msg:
        print("Failed to start conversation. Please check your API key.")
        return

    messages.append({"role": "user", "content": "Hi, I'm ready to discover my style"})
    messages.append({"role": "assistant", "content": assistant_msg})
    print(f"ARI: {assistant_msg}\n")

    # Conversation loop
    while True:
        turn_count += 1

        # Check max turns
        if turn_count >= MAX_CONVERSATION_TURNS:
            print("\nARI: We've covered a lot of ground! I have a great sense of your style now.\n")
            print("=" * 60)
            print(" Onboarding Complete!")
            print("=" * 60 + "\n")
            break

        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nARI: No worries, catch you later!\n")
            break

        if not user_input:
            print("(Share what's on your mind, or type 'skip' to move on)\n")
            continue

        if user_input.lower() in ["quit", "exit", "q"]:
            print("\nARI: Thanks for chatting! Come back anytime.\n")
            break

        messages.append({"role": "user", "content": user_input})

        assistant_msg = get_ai_response(messages, openai_client)

        if not assistant_msg:
            messages.pop()  # Remove failed user message
            print("(Oops, had trouble there. Try again?)\n")
            continue

        messages.append({"role": "assistant", "content": assistant_msg})
        print(f"\nARI: {assistant_msg}\n")

        # Check for node transition
        new_node = detect_node_transition(assistant_msg, current_node)
        if new_node:
            current_node = new_node
            # Update system prompt with new node context
            new_system_prompt = build_system_prompt(current_node)
            messages[0] = {"role": "system", "content": new_system_prompt}

        # Check for natural completion
        if is_conversation_complete(assistant_msg):
            print("\n" + "=" * 60)
            print(" Onboarding Complete!")
            print("=" * 60 + "\n")
            break


if __name__ == "__main__":
    chat()
