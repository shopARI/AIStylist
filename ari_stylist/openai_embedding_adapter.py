"""
OpenAI Embedding Adapter for CAMEL-AI 0.2.43.

This module provides a compatibility layer between OpenAI APIs and CAMEL-AI's embedding system,
ensuring smooth operation with both older and newer OpenAI API versions.
"""

import os
import logging
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("openai_embedding_adapter")

# Global flag to track initialization status
initialization_result = False

# Check if OpenAI is available and configure the adapter
try:
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key)
    OPENAI_AVAILABLE = True
    logger.info("OpenAI package is available")
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not available. Install with: pip install openai")

# Apply the necessary monkey patches to ensure compatibility
def apply_openai_compatibility_patches():
    """
    Apply monkey patches to ensure compatibility with both old and new OpenAI APIs.
    
    Returns:
        bool: True if successful, False otherwise
    """
    global initialization_result

    if not OPENAI_AVAILABLE:
        logger.warning("Cannot apply OpenAI compatibility patches: OpenAI package not available")
        return False

    try:
        # Set up OpenAI API key from environment if not already set
        if not openai.api_key:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key:
                logger.info("OpenAI API key set from environment variable")
            else:
                logger.warning("No OpenAI API key found. Set OPENAI_API_KEY environment variable")
                return False

        # Check if we need to monkey patch CAMEL's embedding classes
        try:
            # Import CAMEL's embedding functionality
            from camel.embeddings import OpenAIEmbedding

            # Check which OpenAI client version is being used
            if hasattr(openai, "Embedding") and callable(getattr(openai, "Embedding", None)):
                # New API style (v1.0.0+), patch for compatibility
                _apply_new_api_patches()
            else:
                # Old API style (pre-v1.0.0), patch for compatibility
                _apply_old_api_patches()

            initialization_result = True
            logger.info("OpenAI embedding adapter initialized successfully")
            return True

        except ImportError:
            logger.warning("CAMEL embeddings not available. Compatible patch not applied")
            return False

    except Exception as e:
        logger.error(f"Error applying OpenAI compatibility patches: {e}")
        return False

def _apply_new_api_patches():
    """Apply patches for the new OpenAI API style (v1.0.0+)"""
    try:
        from camel.embeddings import OpenAIEmbedding

        # Save the original embed method
        original_embed = OpenAIEmbedding.embed

        # Define patched embed method for the new API
        def patched_embed(self, text):
            try:
                # Import the client directly for the new API style
                from openai import OpenAI
                client = OpenAI(api_key=openai.api_key)

                # If text is a list, we want to embed multiple texts
                if isinstance(text, list):
                    result = client.embeddings.create(
                        model=self.model_type.value,
                        input=text
                    )
                    # Extract embeddings from new API format
                    embeddings = [item.embedding for item in result.data]
                    return embeddings
                else:
                    # Single text input
                    result = client.embeddings.create(
                        model=self.model_type.value,
                        input=[text]
                    )
                    # Extract the embedding from new API format
                    embedding = result.data[0].embedding
                    return embedding
            except Exception as e:
                logger.error(f"Error in patched embed method: {e}")
                # Fall back to original implementation
                return original_embed(self, text)

        # Apply the patch
        OpenAIEmbedding.embed = patched_embed
        logger.info("Applied patches for new OpenAI API style (v1.0.0+)")

    except Exception as e:
        logger.error(f"Error applying patches for new OpenAI API style: {e}")

def _apply_old_api_patches():
    """Apply patches for the old OpenAI API style (pre-v1.0.0)"""
    try:
        from camel.embeddings import OpenAIEmbedding

        # For old API, we just need to ensure the API call works correctly
        # under different conditions - mainly handling errors and retries

        # Save the original embed method
        original_embed = OpenAIEmbedding.embed

        # Define patched embed method for the old API
        def patched_embed(self, text):
            try:
                return original_embed(self, text)
            except Exception as e:
                logger.error(f"Error in original embed method: {e}")

                # Try an alternative approach for the old API
                try:
                    if isinstance(text, list):
                        # Multiple texts
                        result = client.embeddings.create(model=self.model_type.value,
                        input=text)
                        embeddings = [item["embedding"] for item in result.data]
                        return embeddings
                    else:
                        # Single text
                        result = client.embeddings.create(model=self.model_type.value,
                        input=[text])
                        embedding = result.data[0].embedding
                        return embedding
                except Exception as e2:
                    logger.error(f"Error in fallback embed method: {e2}")
                    # No more fallbacks, raise the original exception
                    raise e

        # Apply the patch
        OpenAIEmbedding.embed = patched_embed
        logger.info("Applied patches for old OpenAI API style (pre-v1.0.0)")

    except Exception as e:
        logger.error(f"Error applying patches for old OpenAI API style: {e}")

# Try to apply patches during module import
initialization_result = apply_openai_compatibility_patches()
