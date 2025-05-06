"""
Refactored Asynchronous Stylist Agent for AI Stylist.

This module implements the stylist agent with true async support.
Compatible with CAMEL-AI 0.2.43.
"""

import logging
import os
from typing import Optional, List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stylist_agent_async")

# Import AsyncCAMELService
from async_camel_service import AsyncCAMELService

# Global service instance
_service = None

def get_service(max_workers=10):
    """Get or create the global service instance"""
    global _service
    if _service is None:
        _service = AsyncCAMELService(max_workers=max_workers)
    return _service

async def create_stylist_agent_async(memory, model_type=None, temperature=0.7, max_tokens=4000):
    """
    Create an AI stylist agent with natural conversational abilities asynchronously.
    
    Args:
        memory: LongtermAgentMemory instance 
        model_type: Type of model to use (defaults to GPT-4O if None)
        temperature: Model temperature setting (0.0-1.0)
        max_tokens: Maximum tokens in completion
        
    Returns:
        ChatAgent: Configured stylist agent
    """
    logger.info(f"Creating stylist agent with model: {model_type}")
    
    # Define the stylist system message with emphasis on natural conversation
    stylist_system_message = """You are Ari, a warm and personable fashion stylist with years of experience helping clients look and feel their best. 

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

Always maintain a friendly, encouraging tone that boosts the client's confidence. Your goal is to make them feel like they're getting personalized advice from a trusted friend with fashion expertise.
"""
    
    # Use the AsyncCAMELService to create the agent
    service = get_service()
    
    # Create a session ID for this agent
    session_id = f"stylist_{os.urandom(4).hex()}"
    
    agent = await service.get_or_create_agent(
        session_id=session_id,
        system_message=stylist_system_message,
        model_type=model_type,
        memory=memory
    )
    
    return agent

async def create_stylist_agent_with_tools_async(memory, tools=None, model_type=None, temperature=0.7, max_tokens=4000):
    """
    Create an AI stylist agent with tool-calling capabilities asynchronously.
    
    Args:
        memory: LongtermAgentMemory instance
        tools: List of tools to provide to the agent
        model_type: Type of model to use
        temperature: Model temperature setting (0.0-1.0)
        max_tokens: Maximum tokens in completion
        
    Returns:
        ChatAgent: Configured stylist agent with tools
    """
    # Create the base agent
    stylist_agent = await create_stylist_agent_async(
        memory=memory,
        model_type=model_type,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    # Add tools if provided - this operation is quick and can be done directly
    if tools and len(tools) > 0:
        try:
            stylist_agent.tools = tools
            logger.info(f"Added {len(tools)} tools to stylist agent")
        except Exception as e:
            logger.error(f"Error adding tools to stylist agent: {e}")
    
    return stylist_agent

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
    
    # Create product details section - this is a fast string operation that can run directly
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
    
    Args:
        memory: LongtermAgentMemory instance
        products: List of products to recommend
        model_type: Type of model to use
        temperature: Model temperature setting
        
    Returns:
        ChatAgent: Configured recommendation agent
    """
    logger.info("Creating product recommendation agent")
    
    # Start with the base stylist agent with lower max tokens
    base_agent = await create_stylist_agent_async(
        memory=memory,
        model_type=model_type,
        temperature=temperature,
        max_tokens=2000
    )
    
    # Enhance the prompt with product information
    enhanced_system_message = await enhance_stylist_prompt_with_products_async(
        base_agent.system_message,
        products
    )
    
    # Use the enhanced prompt to create a new agent
    service = get_service()
    session_id = f"product_rec_{os.urandom(4).hex()}"
    
    recommendation_agent = await service.get_or_create_agent(
        session_id=session_id,
        system_message=enhanced_system_message,
        model_type=model_type,
        memory=memory
    )
    
    return recommendation_agent
