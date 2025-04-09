"""
CAMEL-AI OpenAI Embedding Adapter

This module creates an adapter for CAMEL-AI's OpenAIEmbedding that ensures proper
compatibility with the current OpenAI API format. It should be imported before
any other CAMEL components that use embeddings.
"""

import logging
import os
from typing import List, Dict, Any, Union, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openai_embedding_adapter")

def initialize_embedding_adapter():
    """
    Initialize the adapter for CAMEL's OpenAIEmbedding to ensure compatibility
    with the current OpenAI API. This must be called before using any CAMEL memory
    components.
    """
    try:
        # First, make sure we're using the correct OpenAI package
        import openai
        logger.info(f"Using OpenAI package version: {openai.__version__}")
        
        # Make sure the OPENAI_API_KEY is set
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY environment variable is not set")
        else:
            # Configure the OpenAI client
            openai.api_key = api_key
        
        # Now modify the CAMEL OpenAIEmbedding class to be compatible
        from camel.embeddings import OpenAIEmbedding
        
        # Store the original methods
        original_embed = OpenAIEmbedding.embed
        original_embed_list = OpenAIEmbedding.embed_list
        
        # Define new wrapper methods that ensure proper formatting
        def new_embed(self, text: str) -> List[float]:
            try:
                # Try to directly call OpenAI client with the correct format
                client = openai.OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=text,
                    encoding_format="float"
                )
                logger.info("Successfully used direct OpenAI client for embedding")
                return response.data[0].embedding
            except Exception as e1:
                logger.warning(f"Direct OpenAI client failed: {e1}, trying original method")
                try:
                    # Fall back to original method
                    return original_embed(self, text)
                except Exception as e2:
                    logger.error(f"Both embedding methods failed: {e2}")
                    # Return empty embedding as last resort
                    return [0.0] * 1536
        
        def new_embed_list(self, texts: List[str]) -> List[List[float]]:
            try:
                # Try to directly call OpenAI client with the correct format
                client = openai.OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    model="text-embedding-ada-002",
                    input=texts,
                    encoding_format="float"
                )
                logger.info("Successfully used direct OpenAI client for batch embedding")
                return [item.embedding for item in response.data]
            except Exception as e1:
                logger.warning(f"Direct OpenAI client failed for batch: {e1}, trying original method")
                try:
                    # Fall back to original method
                    return original_embed_list(self, texts)
                except Exception as e2:
                    logger.error(f"Both batch embedding methods failed: {e2}")
                    # Return empty embeddings as last resort
                    return [[0.0] * 1536 for _ in range(len(texts))]
        
        # Apply the new methods
        OpenAIEmbedding.embed = new_embed
        OpenAIEmbedding.embed_list = new_embed_list
        
        logger.info("Successfully initialized OpenAI embedding adapter")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI embedding adapter: {e}")
        return False

# Automatically initialize when imported
initialization_result = initialize_embedding_adapter()
