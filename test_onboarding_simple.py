"""Simple onboarding test - just the conversation, no database."""

import os
from openai import OpenAI

client = OpenAI()

SYSTEM_PROMPT = """You are ARI, a warm style confidant.

RULES:
- Ask ONE question at a time
- Keep responses to 2-3 sentences
- Sound human, like texting a friend
- No bullet points or lists

TOPICS TO COVER (in order):
1. What they do for work/lifestyle
2. Style they're drawn to
3. How adventurous they are with fashion
4. Budget comfort level

When done with all topics, say "That's all I need! Thanks for sharing."
"""

def chat():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # First message
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages + [{"role": "user", "content": "Hi, I'm ready to start"}]
    )
    assistant_msg = response.choices[0].message.content
    messages.append({"role": "user", "content": "Hi, I'm ready to start"})
    messages.append({"role": "assistant", "content": assistant_msg})
    print(f"\nARI: {assistant_msg}\n")

    # Conversation loop
    while True:
        user_input = input("You: ").strip()
        if not user_input or user_input.lower() in ["quit", "exit", "q"]:
            break

        messages.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        assistant_msg = response.choices[0].message.content
        messages.append({"role": "assistant", "content": assistant_msg})
        print(f"\nARI: {assistant_msg}\n")

        if "That's all I need" in assistant_msg:
            break

if __name__ == "__main__":
    print("\n=== Simple Onboarding Test ===")
    print("Type 'quit' to exit\n")
    chat()
