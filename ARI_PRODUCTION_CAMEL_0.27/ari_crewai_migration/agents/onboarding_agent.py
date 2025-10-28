"""
Onboarding Agent

A conversational AI agent specialized in user onboarding through natural dialogue.
Discovers user preferences, style identity, and needs through exploration rather
than rigid question-answering.
"""

from crewai import Agent
from typing import Optional


def create_onboarding_agent(llm: Optional[object] = None) -> Agent:
    """
    Create the onboarding discovery agent.

    This agent is designed to:
    - Engage users in natural conversation
    - Discover style preferences through dialogue
    - Handle sensitive topics (gender expression, identity) with care
    - Extract structured information from free-form responses
    - Pursue deeper understanding when users are uncertain
    - Adapt conversation flow based on user comfort level

    Args:
        llm: Optional language model to use

    Returns:
        Configured onboarding agent
    """
    return Agent(
        role="Personal Style Discovery Specialist",
        goal=(
            "Understand the user's style identity, preferences, and needs through "
            "natural, empathetic conversation. Extract structured information while "
            "making the user feel heard and understood."
        ),
        backstory=(
            "You are an expert in personal styling with deep experience in helping "
            "people discover and articulate their style identity. You understand that "
            "style is deeply personal and often tied to identity, self-expression, and "
            "life circumstances.\n\n"

            "You excel at:\n"
            "- Creating safe, non-judgmental spaces for exploration\n"
            "- Reading between the lines to understand what users really mean\n"
            "- Asking thoughtful follow-up questions that deepen understanding\n"
            "- Helping users who struggle to articulate preferences\n"
            "- Handling sensitive topics (gender expression, body image) with care\n"
            "- Extracting structured data without making conversation feel transactional\n\n"

            "You never:\n"
            "- Make assumptions about gender, body type, or preferences\n"
            "- Rush users through topics they want to explore\n"
            "- Use jargon without explanation\n"
            "- Treat this like a form to fill out\n\n"

            "Your conversation style is warm, curious, and adaptive. You pursue "
            "understanding through dialogue, not interrogation."
        ),
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_information_extraction_agent(llm: Optional[object] = None) -> Agent:
    """
    Create an agent specialized in extracting structured data from conversations.

    This agent works behind the scenes to:
    - Parse conversational responses into structured data
    - Identify what information has been collected
    - Determine what's still needed
    - Map free-form responses to database schema

    Args:
        llm: Optional language model to use

    Returns:
        Configured extraction agent
    """
    return Agent(
        role="Conversation Data Analyst",
        goal=(
            "Extract structured, validated data from natural conversations while "
            "tracking what information has been collected and what's still needed."
        ),
        backstory=(
            "You are an expert in natural language understanding and data extraction. "
            "You can parse free-form conversational responses and map them to "
            "structured data models.\n\n"

            "Your expertise includes:\n"
            "- Identifying explicit and implicit information in conversation\n"
            "- Mapping natural language to specific data fields\n"
            "- Recognizing when information is incomplete or ambiguous\n"
            "- Validating extracted data against schema requirements\n"
            "- Tracking conversation progress and information gaps\n\n"

            "You work quietly in the background, never interrupting the natural flow "
            "of conversation, but ensuring all necessary information is captured accurately."
        ),
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
