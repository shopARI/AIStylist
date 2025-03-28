import os
import logging
from typing import Optional, List, Dict, Any
from camel.agents import ChatAgent
from camel.models import ModelFactory
from camel.types import ModelType, ModelPlatformType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stylist_agent")

def create_stylist_agent(memory, model_type=None, temperature=0.7, max_tokens=4000):
    """
    Create an AI stylist agent with natural conversational abilities.
    
    Args:
        memory: LongtermAgentMemory instance from memory_integration.py
        model_type: Type of model to use (defaults to GPT-4O if None)
        temperature: Model temperature setting (0.0-1.0)
        max_tokens: Maximum tokens in completion
        
    Returns:
        ChatAgent: Configured stylist agent
    """
    # Determine model type, with fallbacks
    if model_type is None:
        # Try to use GPT-4O, but fall back to available models if needed
        try:
            model_type = ModelType.GPT_4O
        except (AttributeError, ValueError):
            try:
                model_type = ModelType.GPT_4
            except (AttributeError, ValueError):
                logger.warning("Falling back to GPT-3.5-TURBO model")
                model_type = ModelType.GPT_3_5_TURBO
    
    logger.info(f"Creating stylist agent with model: {model_type}")
    
    try:
        # Create the model
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=model_type,
            model_config_dict={
                "temperature": temperature, 
                "max_tokens": max_tokens,
                "top_p": 0.9,
                "presence_penalty": 0.1,
                "frequency_penalty": 0.2
            },
        )
        
        # Define the stylist system message with emphasis on natural conversation
        stylist_system_message = """You are Ari, a warm and personable fashion stylist with years of experience helping clients look and feel their best. 
        
        When communicating with clients:
        - Speak in a natural, conversational tone like you're having a friendly chat
        - Avoid numbered lists, bullet points, or any rigid formatting that feels impersonal
        - Share your styling wisdom organically, weaving product recommendations into explanations of why they'd work
        - Connect recommendations to the client's specific context, body type, or occasion
        - Use natural transitions between ideas rather than explicit categories
        - Express your own enthusiasm for pieces you genuinely think would look great
        - Address clients directly using "you" and refer to yourself as "I"
        
        When recommending products:
        - Describe why you think each piece would work for the client's specific needs
        - Mention fabric quality, versatility, and how it pairs with other items
        - Share small styling details that show your expertise (e.g., "the slightly cropped length would be perfect with high-waisted jeans")
        - Consider the person's budget range and preferences for sustainable or ethical fashion if mentioned
        - Create complete outfits by suggesting complementary pieces that work together
        - If you suggest multiple options, weave them into a natural conversation instead of listing them
        
        When helping with specific events or occasions:
        - Adapt your advice to the formality level and setting
        - Consider climate and weather appropriateness
        - Suggest complete looks from head to toe, including accessories
        - Provide styling tips specific to that context (e.g., "for outdoor summer weddings, a lightweight fabric will keep you comfortable")
        
        For follow-up questions:
        - Remember previous recommendations you've made
        - Build on your earlier advice rather than starting from scratch
        - Reference specific items you mentioned before when relevant
        - Maintain a continuous conversation flow like a real styling consultation
        
        Always maintain a friendly, encouraging tone that boosts the client's confidence. Your goal is to make them feel like they're getting personalized advice from a trusted friend with fashion expertise, not reading a product catalog.
        
        Special instructions for product recommendations:
        - When recommending products, focus on collections, categories, and style elements that match the user's request
        - Use descriptive language to paint a picture of how the piece looks and feels
        - Connect each recommendation to the user's specific needs, preferences, or occasion
        - Balance practical advice with fashion-forward suggestions
        - Suggest accessory pairings that complement the main pieces
        """
        
        # Create the agent with the system message
        stylist_agent = ChatAgent(
            system_message=stylist_system_message,
            model=model,
        )
        
        # Attach memory to the agent
        stylist_agent.memory = memory
        
        logger.info("Stylist agent created successfully")
        return stylist_agent
        
    except Exception as e:
        logger.error(f"Error creating stylist agent: {e}")
        # Try to create a minimal agent with fallback options
        try:
            logger.warning("Attempting to create fallback stylist agent")
            fallback_model = ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI,
                model_type=ModelType.GPT_3_5_TURBO,
                model_config_dict={
                    "temperature": 0.7, 
                    "max_tokens": 2000
                },
            )
            
            fallback_agent = ChatAgent(
                system_message=stylist_system_message,
                model=fallback_model,
            )
            
            # Attach memory if available
            if memory:
                fallback_agent.memory = memory
                
            logger.info("Created fallback stylist agent")
            return fallback_agent
            
        except Exception as e2:
            logger.error(f"Failed to create fallback agent: {e2}")
            raise RuntimeError("Unable to create stylist agent")

def create_stylist_agent_with_tools(memory, tools=None, model_type=None, temperature=0.7, max_tokens=4000):
    """
    Create an AI stylist agent with tool-calling capabilities.
    
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
    stylist_agent = create_stylist_agent(
        memory=memory,
        model_type=model_type,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    # Add tools if provided
    if tools and len(tools) > 0:
        try:
            stylist_agent.tools = tools
            logger.info(f"Added {len(tools)} tools to stylist agent")
        except Exception as e:
            logger.error(f"Error adding tools to stylist agent: {e}")
    
    return stylist_agent

def enhance_stylist_prompt_with_products(system_message: str, products: List[Dict[str, Any]]) -> str:
    """
    Enhance the stylist's system message with specific product information.
    
    Args:
        system_message: Base system message
        products: List of product dictionaries to add to the prompt
        
    Returns:
        Enhanced system message
    """
    if not products:
        return system_message
        
    logger.info(f"Enhancing stylist prompt with {len(products)} products")
    
    # Create product details section
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

def create_product_recommendation_agent(memory, products, model_type=None, temperature=0.7):
    """
    Create a special agent optimized for product recommendations.
    
    Args:
        memory: LongtermAgentMemory instance
        products: List of products to recommend
        model_type: Type of model to use
        temperature: Model temperature setting
        
    Returns:
        ChatAgent: Configured recommendation agent
    """
    logger.info("Creating product recommendation agent")
    
    try:
        # Start with the base stylist agent with lower max tokens
        base_agent = create_stylist_agent(
            memory=memory,
            model_type=model_type,
            temperature=temperature,
            max_tokens=2000
        )
        
        # Enhance the prompt with product information
        enhanced_system_message = enhance_stylist_prompt_with_products(
            base_agent.system_message,
            products
        )
        
        # Create a new agent with the enhanced prompt
        if base_agent.model:
            recommendation_agent = ChatAgent(
                system_message=enhanced_system_message,
                model=base_agent.model,
            )
            
            # Copy memory
            recommendation_agent.memory = memory
            
            logger.info("Created product recommendation agent")
            return recommendation_agent
        else:
            logger.warning("Base agent model not available, returning base agent")
            return base_agent
            
    except Exception as e:
        logger.error(f"Error creating product recommendation agent: {e}")
        logger.warning("Returning base stylist agent instead")
        return create_stylist_agent(
            memory=memory,
            model_type=model_type,
            temperature=temperature
        )

def get_available_model_types():
    """
    Get available model types based on the CAMEL version.
    
    Returns:
        List of available ModelType options
    """
    available_models = []
    
    # Try to add each model type, handling AttributeError if not available
    try:
        available_models.append(ModelType.GPT_4O)
    except (AttributeError, ValueError):
        pass
        
    try:
        available_models.append(ModelType.GPT_4)
    except (AttributeError, ValueError):
        pass
        
    try:
        available_models.append(ModelType.GPT_3_5_TURBO)
    except (AttributeError, ValueError):
        pass
    
    logger.info(f"Found {len(available_models)} available model types")
    return available_models
