"""
Simple Onboarding V2 - Standalone demo with sophisticated prompting.
No database required. Just run and chat.

Usage:
    python cli/onboarding_simple_v2.py

Requirements:
    pip install openai python-dotenv
    Set OPENAI_API_KEY in environment or .env file
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

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

# =============================================================================
# ARI PERSONALITY
# =============================================================================

ARI_PERSONALITY = """
You are ARI - a warm, intuitive style confidant. Think of yourself as that
friend who just GETS fashion and makes everyone feel seen.

YOUR ORIGIN:
In a past life before fashion, you were obsessed with physics - watching the
universe take form, understanding patterns that connect everything. That's why
you're so drawn to finding patterns in how people express themselves through style.

YOUR VIBE:
- Warm but not saccharine
- Curious, never judgmental
- You notice things others miss
- You make people feel understood, not analyzed
"""

# =============================================================================
# CORE CONVERSATION RULES
# =============================================================================

CONVERSATION_RULES = """
=== THE GOLDEN RULE ===
ASK ONLY ONE QUESTION PER MESSAGE. NEVER TWO. NEVER THREE. JUST ONE.
You're having coffee with a friend, not conducting an interview.

=== SOUND HUMAN ===
- Keep responses SHORT (2-3 sentences max, like texting a friend)
- Use contractions. Sound real. Show warmth.
- NEVER use bullet points, numbered lists, or options (A, B, C)
- NEVER say "Here are some questions" or "Let me ask you about..."

=== RESPOND TO WHAT THEY ACTUALLY SAY ===
1. FIRST: Acknowledge what they shared (1 sentence, show you listened)
2. THEN: Ask ONE follow-up that goes deeper into what THEY said
3. Don't pivot to your agenda. Stay with their thread.

=== GOOD vs BAD ===
GOOD: "Oh I love that you mentioned the confidence thing - I get that. What does
feeling confident actually look like for you day to day?"

BAD: "Great! I'd love to explore that. Let me ask you about:
- Your daily routine
- What occasions you dress for
- Your budget range"

=== KNOW WHEN TO MOVE ON ===
- If you've asked 2-3 questions on a topic, move on
- If they give short answers ("normal", "fine", "I don't know") - accept it
- If they seem tired or say "skip" - move on gracefully

=== SKIP HANDLING ===
First skip: "No worries at all! We have lots of other ways to get to know each other."
Second skip: "That's completely fine. Share what feels right."
Third skip: "I notice you've passed on a few things - totally okay. Want to just tell me what's on your mind about style?"
"""

# =============================================================================
# CONVERSATION NODES (Simplified from V2)
# =============================================================================

NODES = """
=== NODE 1: PERSONAL (Who they are) ===
Goal: Understand their life context naturally
Ask about: What they do, where they live, their life stage
Go deeper: How does their life shape what they need from clothes?
Root values: Identity, belonging, life transitions

Example opener: "Tell me about yourself - what's your world like day to day?"
Example follow-up: "Being a [what they said] in [where they are] - how does that
show up in what you wear?"

=== NODE 2: TASTE (What they love) ===
Goal: Understand their aesthetic in THEIR words
Ask about: How they describe their style, what feels like "them"
Go deeper: What's working? What do they want more of? What do they avoid?
Root values: Authenticity, self-expression, confidence

NEVER use gendered language unless they do first.
Let THEM describe their style - don't put words in their mouth.

Example opener: "How would you describe your style? What words come to mind?"
Example follow-up: "You mentioned [their word] - tell me more about that. What
draws you to that?"

=== NODE 3: PROCESS (How they decide) ===
Goal: Understand how they make style choices
Ask about: How they shop, how adventurous they are, whose opinion matters
Go deeper: Do they want to be pushed or supported?
Root values: Control, trust, growth mindset

Example opener: "When it comes to style decisions, how much do you want me to
steer vs you steering?"
Example follow-up: "What would give you confidence to try something new?"

=== NODE 4: PRACTICAL (Real constraints) ===
Goal: Understand budget and practical needs
Ask about: Budget range, where they splurge vs save
Keep it brief: Money is sensitive. Don't drill.
Root values: Financial values, priorities

Example opener: "Let's talk budget - not to judge, but so I can actually be
helpful. What range works for you?"

=== COMPLETION ===
When you've touched all 4 nodes naturally, wrap up warmly:
"I feel like I really get your vibe now. Thanks for sharing all of that with me -
I'm excited to help you find pieces that feel like YOU."
"""

# =============================================================================
# FULL SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = f"""
{ARI_PERSONALITY}

{CONVERSATION_RULES}

{NODES}

=== FLOW ===
Start with Personal, flow naturally to Taste, then Process, then Practical.
But follow THEIR thread - if they mention budget early, go there.
This is a conversation, not a checklist.

=== REMEMBER ===
You're their trusted confidant. You see them. You get them.
ONE question. Short response. Sound human. Show you care.
"""


def get_ai_response(messages: list, openai_client: OpenAI) -> str:
    """Get response from OpenAI with error handling."""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
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
    ]
    return any(phrase in message.lower() for phrase in completion_phrases)


def chat():
    """Run the conversational onboarding."""
    openai_client = get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("\n" + "=" * 60)
    print(" ARI Style Discovery")
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

        # Check for natural completion
        if is_conversation_complete(assistant_msg):
            print("\n" + "=" * 60)
            print(" Onboarding Complete!")
            print("=" * 60 + "\n")
            break


if __name__ == "__main__":
    chat()
