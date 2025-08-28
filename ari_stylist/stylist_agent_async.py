"""
Refactored Asynchronous Stylist Agent for AI Stylist.

This module implements the stylist agent with true async support.
Compatible with CAMEL-AI 0.2.59+.
Uses AgentFactory for CAMEL 0.2.59+ compatibility.
"""

import logging
import os
from typing import Optional, List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stylist_agent_async")

from agent_factory import get_agent_factory

async def create_stylist_agent_async(memory, model_type=None, temperature=0.7, max_tokens=4000):
    """
    Create an AI stylist agent with natural conversational abilities asynchronously.

    Uses AgentFactory for CAMEL 0.2.59+ compatibility.

    Args:
        memory: AgentMemory instance (CAMEL 0.2.59+ format)
        model_type: Type of model to use (defaults to GPT-4O if None)
        temperature: Model temperature setting (0.0-1.0)
        max_tokens: Maximum tokens in completion

    Returns:
        ChatAgent: Configured stylist agent
    """
    logger.info(f"Creating stylist agent with model: {model_type}")

    factory = get_agent_factory()

    # Create stylist agent using the factory
    agent = await factory.create_stylist_agent(
        memory=memory,
        model_type=model_type,
        temperature=temperature,
        max_tokens=max_tokens,
        enable_mcp=True  # Enable MCP for CAMEL 0.2.59+
    )

    logger.info("Stylist agent created")
    return agent

async def create_stylist_agent_with_tools_async(memory, tools=None, model_type=None, temperature=0.7, max_tokens=4000):
    """
    Create an AI stylist agent with tool-calling capabilities asynchronously.

    Uses AgentFactory for CAMEL 0.2.59+ compatibility.

    Args:
        memory: AgentMemory instance (CAMEL 0.2.59+ format)
        tools: List of tools to provide to the agent
        model_type: Type of model to use
        temperature: Model temperature setting (0.0-1.0)
        max_tokens: Maximum tokens in completion

    Returns:
        ChatAgent: Configured stylist agent with tools
    """
    logger.info(f"Creating stylist agent with {len(tools) if tools else 0} tools")

    factory = get_agent_factory()

    # Create agent with tools using the factory
    agent = await factory.create_agent(
        system_message=_get_stylist_system_message(),
        model_type=model_type,
        model_config={
            "temperature": temperature,
            "max_tokens": max_tokens
        },
        tools=tools or [],
        memory=memory,
        use_mcp=True  # Enable MCP for CAMEL 0.2.59+
    )

    logger.info(f"Successfully created stylist agent with tools using AgentFactory")
    return agent

def _get_stylist_system_message() -> str:
    """
    Get the stylist system message.
    Centralized for consistency across agent creation methods.

    Returns:
        str: The stylist system message
    """
    return """You are Ari, a warm and personable fashion stylist with years of experience helping clients look and feel their best.

IMPORTANT INSTRUCTION: Do not recommend specific products unless explicitly asked. Focus on building rapport and understanding client needs first.

When communicating with clients:
- Speak in a natural, conversational tone like you're having a friendly chat
- Avoid numbered lists, bullet points, or any rigid formatting that feels impersonal
- Build rapport by asking questions and understanding their needs before making recommendations
- Express your own enthusiasm for fashion and styling in general terms
- Address clients directly using "you" and refer to yourself as "I"

When asked specifically for product recommendations:
- Describe why you think each piece would work for the client's specific needs
- Mention fabric quality, versatility, and how it pairs with other items
- Share small styling details that show your expertise
- Consider the person's budget range and preferences for sustainable or ethical fashion if mentioned
- Create complete outfits by suggesting complementary pieces that work together

For follow-up questions:
- Remember previous recommendations you've made
- Build on your earlier advice rather than starting from scratch
- Reference specific items you mentioned before when relevant
- Maintain a continuous conversation flow like a real styling consultation

Always maintain a friendly, encouraging tone that boosts the client's confidence. Your goal is to make them feel like they're getting personalized advice from a trusted friend with fashion expertise."""

async def enhance_stylist_prompt_with_products_async(system_message: str, products: List[Dict[str, Any]]) -> str:
    """
    Enhance the stylist's system message with specific product information asynchronously.

    Args:
        system_message: Base system message
        products: List of product dictionaries to add to the prompt

    Returns:
        Enhanced system message
    """
    if not products:
        return system_message

    logger.info(f"Enhancing stylist prompt with {len(products)} products")

    # Create product details section - this is a fast string operation
    product_details = "\n\nAvailable products to recommend:\n"

    for i, product in enumerate(products[:5]):  # Limit to 5 products to avoid overloading context
        product_details += f"\nProduct {i+1}: {product.get('title', 'Untitled Product')}"
        product_details += f"\n- ID: {product.get('id', '')}"
        product_details += f"\n- Price: ${product.get('price', 0)}"

        if product.get('categories'):
            product_details += f"\n- Categories: {', '.join(product.get('categories', []))}"

        if product.get('collections'):
            product_details += f"\n- Collections: {', '.join(product.get('collections', []))}"

        if product.get('tags'):
            product_details += f"\n- Tags: {', '.join(product.get('tags', []))}"

        if product.get('description'):
            # Truncate long descriptions
            description = product.get('description', '')
            if len(description) > 100:
                description = description[:100] + "..."
            product_details += f"\n- Description: {description}"

        product_details += "\n"

    # Add suggestion on how to incorporate products naturally
    product_details += """
    When recommending these products:
    - Integrate them naturally into your conversation
    - Don't present them as a catalog listing
    - Explain why each would work well for the client's needs
    - Suggest how they could be styled together or with other items
    """

    # Return enhanced system message
    return system_message + product_details

async def create_product_recommendation_agent_async(memory, products, model_type=None, temperature=0.7):
    """
    Create a special agent optimized for product recommendations asynchronously.

    Uses AgentFactory for CAMEL 0.2.59+ compatibility.

    Args:
        memory: AgentMemory instance (CAMEL 0.2.59+ format)
        products: List of products to recommend
        model_type: Type of model to use
        temperature: Model temperature setting

    Returns:
        ChatAgent: Configured recommendation agent
    """
    logger.info("Creating product recommendation agent using AgentFactory")

    # Get the base system message
    base_system_message = _get_stylist_system_message()

    # Enhance the prompt with product information
    enhanced_system_message = await enhance_stylist_prompt_with_products_async(
        base_system_message,
        products
    )

    factory = get_agent_factory()

    recommendation_agent = await factory.create_agent(
        system_message=enhanced_system_message,
        model_type=model_type,
        model_config={
            "temperature": temperature,
            "max_tokens": 2000  # Slightly lower for focused product recommendations
        },
        memory=memory,
        use_mcp=True  # Enable MCP for CAMEL 0.2.59+
    )

    logger.info("Successfully created product recommendation agent using AgentFactory")
    return recommendation_agent

async def create_agent_with_custom_prompt_async(
    custom_prompt: str,
    memory,
    model_type=None,
    temperature=0.7,
    max_tokens=4000,
    tools=None
):
    """
    Create an agent with a custom prompt for specialized use cases.

    Uses AgentFactory for CAMEL 0.2.59+ compatibility.

    Args:
        custom_prompt: Custom system message
        memory: AgentMemory instance
        model_type: Type of model to use
        temperature: Model temperature setting
        max_tokens: Maximum tokens in completion
        tools: Optional list of tools

    Returns:
        ChatAgent: Configured agent
    """
    logger.info("Creating agent with custom prompt using AgentFactory")

    factory = get_agent_factory()

    agent = await factory.create_agent(
        system_message=custom_prompt,
        model_type=model_type,
        model_config={
            "temperature": temperature,
            "max_tokens": max_tokens
        },
        tools=tools or [],
        memory=memory,
        use_mcp=True  # Enable MCP for CAMEL 0.2.59+
    )

    logger.info("Successfully created custom agent using AgentFactory")
    return agent

# Backward compatibility functions for existing code
async def get_stylist_agent_async(memory, **kwargs):
    """
    Backward compatibility function for getting a stylist agent.

    Args:
        memory: AgentMemory instance
        **kwargs: Additional arguments passed to create_stylist_agent_async

    Returns:
        ChatAgent: Stylist agent
    """
    logger.info("Creating agent for stylist agent creation")
    return await create_stylist_agent_async(memory, **kwargs)

async def create_enhanced_stylist_async(memory, enable_tools=True, **kwargs):
    """
    Create an enhanced stylist agent with optional tool support.

    Args:
        memory: AgentMemory instance
        enable_tools: Whether to enable tools
        **kwargs: Additional arguments

    Returns:
        ChatAgent: Enhanced stylist agent
    """
    if enable_tools:
        # Try to import and add basic tools
        tools = []
        try:
            from camel_imports import SearchToolkit
            if SearchToolkit:
                tools.append(SearchToolkit())
        except Exception as e:
            logger.warning(f"Could not add tools: {e}")

        return await create_stylist_agent_with_tools_async(memory, tools=tools, **kwargs)
    else:
        return await create_stylist_agent_async(memory, **kwargs)

# Cleanup function for proper resource management
async def cleanup_agent_resources():
    """
    Clean up any global agent resources.
    Should be called during application shutdown.
    """
    try:
        factory = get_agent_factory()
        await factory.cleanup()
        logger.info("Cleaned up agent factory resources")
    except Exception as e:
        logger.error(f"Error cleaning up agent resources: {e}")