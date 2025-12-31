"""
FashionSigLIP Embedding Encoder Service
Generates visual and text embeddings for fashion queries using FashionSigLIP model
"""

import logging
import numpy as np
import torch
from typing import Optional, Union
from PIL import Image
import requests
from io import BytesIO

logger = logging.getLogger(__name__)

# Global model instance (singleton for performance)
_fashionsig_encoder = None


class FashionSigLIPEncoder:
    """
    Encoder service for FashionSigLIP embeddings.
    Generates 768-dim text embeddings and 768-dim image embeddings.
    """

    def __init__(self):
        """Initialize FashionSigLIP model"""
        self.model = None
        self.preprocess = None
        self.tokenizer = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialize_model()

    def _initialize_model(self):
        """Load FashionSigLIP model from Hugging Face transformers (1024d)"""
        try:
            from transformers import SiglipModel, SiglipProcessor, SiglipTokenizer
            import torch

            logger.info("Loading FashionSigLIP model (google/siglip-large-patch16-384)...")

            # Load the SAME model used for product embeddings (1024d)
            model_name = "google/siglip-large-patch16-384"
            self.model = SiglipModel.from_pretrained(model_name, torch_dtype=torch.float16)
            self.processor = SiglipProcessor.from_pretrained(model_name)
            self.tokenizer = SiglipTokenizer.from_pretrained(model_name)
            self.preprocess = self.processor  # Alias for compatibility

            # Move model to device and set to eval mode
            self.model = self.model.to(self.device)
            self.model.eval()

            logger.info(f"FashionSigLIP model loaded successfully on {self.device} (1024d embeddings)")

        except ImportError:
            logger.error("transformers not installed. Run: pip install transformers")
            raise RuntimeError("FashionSigLIP encoder requires transformers package")
        except Exception as e:
            logger.error(f"Failed to load FashionSigLIP model: {e}")
            raise

    def is_available(self) -> bool:
        """Check if encoder is ready"""
        return self.model is not None

    async def encode_text(self, query: str) -> np.ndarray:
        """
        Convert text query to 1024-dim embedding using SigLIP text encoder.

        Args:
            query: Text query string

        Returns:
            1024-dim numpy array (normalized embedding)
        """
        if not self.is_available():
            raise RuntimeError("FashionSigLIP encoder not initialized")

        try:
            with torch.no_grad():
                # Tokenize text using transformers tokenizer (SigLIP max is 64 tokens)
                text_inputs = self.tokenizer([query], return_tensors="pt", padding=True, truncation=True, max_length=64)
                text_inputs = {k: v.to(self.device) for k, v in text_inputs.items()}

                # Encode to embedding using text_model
                text_outputs = self.model.text_model(**text_inputs)
                text_embedding = text_outputs.last_hidden_state.mean(dim=1)  # [1, 1024]

                # Normalize (cosine similarity)
                text_embedding = text_embedding / text_embedding.norm(dim=-1, keepdim=True)

                # Convert to numpy
                embedding = text_embedding.cpu().numpy()[0]

                logger.debug(f"Generated text embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.3f}")

                return embedding  # 1024-dim vector

        except Exception as e:
            logger.error(f"Failed to encode text: {e}")
            raise

    async def encode_image(self, image_input: Union[str, Image.Image]) -> np.ndarray:
        """
        Convert image to 1024-dim embedding using SigLIP vision encoder.

        Args:
            image_input: Image file path, URL, or PIL Image object

        Returns:
            1024-dim numpy array (normalized embedding)
        """
        if not self.is_available():
            raise RuntimeError("FashionSigLIP encoder not initialized")

        try:
            # Load image
            if isinstance(image_input, str):
                if image_input.startswith('http://') or image_input.startswith('https://'):
                    # Download from URL
                    response = requests.get(image_input, stream=True, timeout=10)
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert('RGB')
                else:
                    # Load from file
                    image = Image.open(image_input).convert('RGB')
            elif isinstance(image_input, Image.Image):
                image = image_input.convert('RGB')
            else:
                raise ValueError(f"Unsupported image input type: {type(image_input)}")

            with torch.no_grad():
                # Preprocess image using transformers processor
                image_inputs = self.processor(images=image, return_tensors="pt", padding=True)
                image_inputs = {k: v.to(self.device) for k, v in image_inputs.items()}

                # Encode to embedding using vision_model
                vision_outputs = self.model.vision_model(**image_inputs)
                image_embedding = vision_outputs.last_hidden_state.mean(dim=1)  # [1, 1024]

                # Normalize (cosine similarity)
                image_embedding = image_embedding / image_embedding.norm(dim=-1, keepdim=True)

                # Convert to numpy
                embedding = image_embedding.cpu().numpy()[0]

                logger.debug(f"Generated image embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.3f}")

                return embedding  # 1024-dim vector

        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            raise

    async def encode_multimodal(
        self,
        query: str,
        image_input: Optional[Union[str, Image.Image]] = None
    ) -> np.ndarray:
        """
        Generate combined 1536-dim embedding (768 text + 768 image).

        Args:
            query: Text query string
            image_input: Optional image (path, URL, or PIL Image)

        Returns:
            1536-dim numpy array (concatenated text + image embeddings)
        """
        text_emb = await self.encode_text(query)

        if image_input:
            image_emb = await self.encode_image(image_input)
        else:
            # No image provided, duplicate text embedding
            image_emb = text_emb

        # Concatenate for 1536-dim combined embedding
        combined = np.concatenate([text_emb, image_emb])

        logger.debug(f"Generated multimodal embedding: shape={combined.shape}")

        return combined

    def get_stats(self) -> dict:
        """Get encoder statistics"""
        return {
            "model_loaded": self.is_available(),
            "device": self.device,
            "embedding_dim_text": 768,
            "embedding_dim_image": 768,
            "embedding_dim_combined": 1536
        }


def get_fashionsig_encoder() -> FashionSigLIPEncoder:
    """
    Get global FashionSigLIP encoder instance (singleton pattern).

    Returns:
        FashionSigLIPEncoder instance
    """
    global _fashionsig_encoder

    if _fashionsig_encoder is None:
        logger.info("Initializing global FashionSigLIP encoder...")
        _fashionsig_encoder = FashionSigLIPEncoder()

    return _fashionsig_encoder


# Exports
__all__ = [
    'FashionSigLIPEncoder',
    'get_fashionsig_encoder'
]
