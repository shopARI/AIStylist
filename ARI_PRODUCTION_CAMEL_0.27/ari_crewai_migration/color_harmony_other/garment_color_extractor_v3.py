"""
Garment Color Extraction Module - SAM3 Version

Extracts dominant colors from garment images using SAM3 for segmentation
with TEXT prompts and URL support for product images.

Major improvements over SAM2:
- Text-based prompts (use product categories directly)
- 270K+ concept coverage (vs ~5K in SAM2)
- Better segmentation accuracy
- Open-vocabulary support
"""

import cv2
import numpy as np
import torch
import requests
from PIL import Image
from io import BytesIO
from typing import List, Tuple, Optional, Union, Dict, Any
from sklearn.cluster import KMeans
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# SAM3 imports
try:
    from sam3.model_builder import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor
    SAM3_AVAILABLE = True
except ImportError:
    SAM3_AVAILABLE = False
    print("SAM3 not installed. Install with: git clone https://github.com/facebookresearch/sam3.git && cd sam3 && pip install -e .")


class GarmentColorExtractorV3:
    """
    Extract dominant colors from garment images using SAM3 segmentation.

    Features:
    - Text-based prompts (e.g., "dress", "shirt", "jeans")
    - URL support for product images
    - 270K+ concept vocabulary
    - Automatic garment segmentation
    """

    def __init__(self, device: str = "cuda"):
        """
        Initialize color extractor with SAM3.

        Args:
            device: 'cuda' or 'cpu'
        """
        if not SAM3_AVAILABLE:
            raise ImportError("SAM3 is not installed. See installation instructions above.")

        self.device = device

        # Build SAM3 image model
        print("Loading SAM3 image model...")
        self.model = build_sam3_image_model()
        self.processor = Sam3Processor(self.model)
        print("SAM3 model loaded successfully!")

    def load_image_from_url(self, url: str, timeout: int = 10) -> Image.Image:
        """
        Load image from URL (works with your product image links).

        Args:
            url: HTTP(S) URL to image
            timeout: Request timeout in seconds

        Returns:
            PIL Image object
        """
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        except requests.RequestException as e:
            raise ValueError(f"Failed to load image from {url}: {e}")

    def load_image_from_path(self, path: str) -> Image.Image:
        """Load image from local file path."""
        return Image.open(path)

    def segment_garment_sam3(
        self,
        image: Union[str, Image.Image],
        text_prompt: Optional[str] = None,
        category: Optional[str] = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Segment garment using SAM3 with text prompts.

        Args:
            image: PIL Image, URL string, or local path
            text_prompt: Text description (e.g., "red dress", "denim jeans")
            category: Product category (e.g., "dress", "shirt", "pants")
                     Used as prompt if text_prompt is None

        Returns:
            Tuple of (masks, boxes, scores)
            - masks: Binary segmentation masks [N, H, W]
            - boxes: Bounding boxes [N, 4]
            - scores: Confidence scores [N]
        """
        # Load image if string
        if isinstance(image, str):
            if image.startswith(('http://', 'https://')):
                image = self.load_image_from_url(image)
            else:
                image = self.load_image_from_path(image)

        # Set image in processor
        inference_state = self.processor.set_image(image)

        # Determine prompt
        prompt = text_prompt or category or "garment clothing"

        # Use TEXT prompt (SAM3's killer feature!)
        output = self.processor.set_text_prompt(
            state=inference_state,
            prompt=prompt
        )

        # Get results
        masks = output["masks"]
        boxes = output["boxes"]
        scores = output["scores"]

        return masks, boxes, scores

    def extract_dominant_colors(
        self,
        image: Union[str, Image.Image, np.ndarray],
        mask: Optional[np.ndarray] = None,
        n_colors: int = 5,
        text_prompt: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Tuple[Tuple[int, int, int], float]]:
        """
        Extract dominant colors from garment image.

        Args:
            image: PIL Image, URL, path, or numpy array
            mask: Pre-computed mask (optional). If None, will segment using SAM3
            n_colors: Number of dominant colors to extract
            text_prompt: Text description for segmentation
            category: Product category for segmentation

        Returns:
            List of (RGB color tuple, percentage) sorted by dominance
        """
        # Convert image to numpy array if needed
        if isinstance(image, str):
            if image.startswith(('http://', 'https://')):
                pil_img = self.load_image_from_url(image)
            else:
                pil_img = self.load_image_from_path(image)
            img_array = np.array(pil_img)
        elif isinstance(image, Image.Image):
            img_array = np.array(image)
        else:
            img_array = image

        # Ensure RGB format
        if img_array.shape[-1] == 4:  # RGBA
            img_array = img_array[..., :3]

        # Get mask if not provided
        if mask is None:
            masks, boxes, scores = self.segment_garment_sam3(
                image, text_prompt, category
            )
            # Use best mask
            best_idx = np.argmax(scores)
            mask = masks[best_idx]

        # Ensure mask is binary
        mask = (mask > 0.5).astype(np.uint8)

        # Extract pixels from masked region
        masked_pixels = img_array[mask == 1]

        if len(masked_pixels) == 0:
            # Fallback to full image if mask is empty
            masked_pixels = img_array.reshape(-1, 3)

        # K-means clustering for dominant colors
        kmeans = KMeans(n_clusters=min(n_colors, len(masked_pixels)),
                       random_state=42, n_init=10)
        kmeans.fit(masked_pixels)

        # Get colors and their frequencies
        colors = kmeans.cluster_centers_.astype(int)
        labels = kmeans.labels_

        # Calculate percentages
        unique, counts = np.unique(labels, return_counts=True)
        percentages = counts / len(labels)

        # Sort by dominance
        color_percentages = [
            (tuple(colors[i]), percentages[i])
            for i in range(len(colors))
        ]
        color_percentages.sort(key=lambda x: x[1], reverse=True)

        return color_percentages

    def process_product_url(
        self,
        product_url: str,
        category: Optional[str] = None,
        n_colors: int = 5
    ) -> Dict[str, Any]:
        """
        Complete pipeline: URL → Segment → Extract Colors

        Args:
            product_url: HTTP(S) URL to product image
            category: Product category (e.g., "dress", "shirt")
            n_colors: Number of dominant colors

        Returns:
            Dictionary with:
            - colors: List of (RGB, percentage) tuples
            - mask: Segmentation mask
            - box: Bounding box
            - score: Confidence score
        """
        # Load image
        image = self.load_image_from_url(product_url)

        # Segment garment
        masks, boxes, scores = self.segment_garment_sam3(
            image, category=category
        )

        # Use best result
        best_idx = np.argmax(scores)
        mask = masks[best_idx]
        box = boxes[best_idx]
        score = scores[best_idx]

        # Extract colors
        colors = self.extract_dominant_colors(
            image, mask=mask, n_colors=n_colors
        )

        return {
            "colors": colors,
            "mask": mask,
            "box": box,
            "score": float(score),
            "category": category,
            "url": product_url
        }


# Example usage
if __name__ == "__main__":
    # Initialize extractor
    extractor = GarmentColorExtractorV3(device="cuda")

    # Example 1: Process product from URL with category
    product_url = "https://example.com/red-dress.jpg"
    result = extractor.process_product_url(
        product_url=product_url,
        category="dress",
        n_colors=5
    )

    print(f"Segmentation score: {result['score']:.3f}")
    print(f"\nDominant colors:")
    for i, (color, percentage) in enumerate(result['colors'], 1):
        print(f"  {i}. RGB{color}: {percentage*100:.1f}%")

    # Example 2: Use with your product database
    product = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Elegant Black Evening Dress",
        "category": "dress",
        "image_url": "https://example.com/images/black-dress.jpg"
    }

    result = extractor.process_product_url(
        product_url=product["image_url"],
        category=product["category"]
    )

    # Use colors for harmony analysis
    dominant_colors = [color for color, _ in result['colors']]
    print(f"\nExtracted {len(dominant_colors)} colors for harmony analysis")
