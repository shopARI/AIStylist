"""
Simple test with advanced model and minimal prompts
"""

import asyncio
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from camel.v070 import (
    create_agent,
    create_user_message,
    ModelType
)

from data_extraction.extractor_base import DatabaseReader, ProductData

async def test_advanced_extraction():
    """Test with the most advanced model and minimal prompts"""
    
    # Use most advanced model
    model_type = ModelType.GPT_4O  # Most advanced available
    
    # Create very simple color extraction agent
    color_agent = create_agent(
        system_message="Extract colors from product text. Return JSON list like: [\"red\", \"blue\"]",
        model_type=model_type,
        temperature=0.1,
        max_tokens=100
    )
    
    # Create simple brand extraction agent  
    brand_agent = create_agent(
        system_message="Extract the brand name from product text. Return just the brand name or 'UNKNOWN'.",
        model_type=model_type,
        temperature=0.1,
        max_tokens=50
    )
    
    # Create simple style agent
    style_agent = create_agent(
        system_message="Classify product style. Choose from: casual, formal, athletic, trendy. Return JSON list like: [\"casual\"]",
        model_type=model_type,
        temperature=0.2,
        max_tokens=100
    )
    
    print("=== TESTING ADVANCED MODEL EXTRACTION ===\n")
    
    # Test products
    test_products = [
        ProductData("1", "Nike Air Force 1 White Sneakers", "Classic white athletic sneakers", 90.00),
        ProductData("2", "Red Flannel Shirt", "Comfortable red cotton flannel shirt", 45.00),
        ProductData("3", "Theory Black Turtleneck", "Luxury black cashmere turtleneck", 195.00)
    ]
    
    for product in test_products:
        print(f"Product: {product.title}")
        
        # Test color extraction
        try:
            color_msg = create_user_message(f"{product.title} {product.description}")
            # Use sync step method instead
            from camel.v070 import CompatibilityBridge
            async_method = CompatibilityBridge.check_async_method(color_agent)
            
            if async_method == 'step_async':
                color_response = await color_agent.step_async(color_msg)
            elif async_method == 'astep':
                color_response = await color_agent.astep(color_msg)
            else:
                color_response = color_agent.step(color_msg)
            
            if hasattr(color_response, 'content'):
                color_content = color_response.content
            else:
                color_content = str(color_response)
            
            print(f"Colors: {color_content}")
        except Exception as e:
            print(f"Color extraction failed: {e}")
        
        # Test brand extraction
        try:
            brand_msg = create_user_message(f"{product.title} {product.description}")
            async_method = CompatibilityBridge.check_async_method(brand_agent)
            
            if async_method == 'step_async':
                brand_response = await brand_agent.step_async(brand_msg)
            elif async_method == 'astep':
                brand_response = await brand_agent.astep(brand_msg)
            else:
                brand_response = brand_agent.step(brand_msg)
            
            if hasattr(brand_response, 'content'):
                brand_content = brand_response.content
            else:
                brand_content = str(brand_response)
            
            print(f"Brand: {brand_content}")
        except Exception as e:
            print(f"Brand extraction failed: {e}")
        
        # Test style extraction
        try:
            style_msg = create_user_message(f"{product.title} {product.description}")
            async_method = CompatibilityBridge.check_async_method(style_agent)
            
            if async_method == 'step_async':
                style_response = await style_agent.step_async(style_msg)
            elif async_method == 'astep':
                style_response = await style_agent.astep(style_msg)
            else:
                style_response = style_agent.step(style_msg)
            
            if hasattr(style_response, 'content'):
                style_content = style_response.content
            else:
                style_content = str(style_response)
            
            print(f"Style: {style_content}")
        except Exception as e:
            print(f"Style extraction failed: {e}")
        
        print("---\n")

if __name__ == "__main__":
    asyncio.run(test_advanced_extraction())