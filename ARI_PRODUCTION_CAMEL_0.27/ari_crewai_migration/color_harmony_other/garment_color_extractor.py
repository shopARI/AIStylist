"""
Garment Color Extraction Module

Extracts dominant colors from garment images using SAM2 for segmentation
and K-means clustering for color extraction.
"""

import cv2
import numpy as np
import torch
from PIL import Image
from typing import List, Tuple, Optional, Union
from sklearn.cluster import KMeans
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


class GarmentColorExtractor:
    """
    Extract dominant colors from garment images using SAM2 segmentation.
    """

    def __init__(self,
                 sam2_checkpoint: Optional[str] = None,
                 model_cfg: str = "sam2_hiera_s.yaml",
                 device: str = "cuda"):
        """
        Initialize color extractor with SAM2.

        Args:
            sam2_checkpoint: Path to SAM2 checkpoint. If None, uses default location.
            model_cfg: SAM2 model config name
            device: 'cuda' or 'cpu'
        """
        self.device = device

        # Set default checkpoint path if not provided
        if sam2_checkpoint is None:
            checkpoint_dir = Path(__file__).parent / "checkpoints"
            sam2_checkpoint = str(checkpoint_dir / "sam2_hiera_small.pt")

        # Build SAM2 model
        self.sam2_model = build_sam2(model_cfg, sam2_checkpoint, device=device)
        self.predictor = SAM2ImagePredictor(self.sam2_model)

    def load_image(self, image_path: str) -> np.ndarray:
        """Load image from file path."""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image from {image_path}")
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def load_image_from_url(self, url: str) -> np.ndarray:
        """Load image from URL."""
        from imread_from_url import imread_from_url
        img = imread_from_url(url)
        if img is None:
            raise ValueError(f"Could not load image from {url}")
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def segment_garment_sam2(self, image: np.ndarray) -> np.ndarray:
        """
        Segment garment using SAM2 automatic mask generation.

        Args:
            image: RGB image array

        Returns:
            Binary mask (1 = garment, 0 = background)
        """
        # Set image in predictor
        self.predictor.set_image(image)

        # Use automatic mask generation with center point prompt
        # This assumes the garment is in the center of the image
        h, w = image.shape[:2]
        center_point = np.array([[w // 2, h // 2]])
        center_label = np.array([1])  # 1 = foreground

        # Predict mask
        masks, scores, _ = self.predictor.predict(
            point_coords=center_point,
            point_labels=center_label,
            multimask_output=True
        )

        # Select mask with highest score
        best_mask_idx = np.argmax(scores)
        mask = masks[best_mask_idx].astype(np.uint8)

        return mask

    def extract_dominant_colors(
        self,
        image: np.ndarray,
        mask: Optional[np.ndarray] = None,
        n_colors: int = 3,
        min_pixels: int = 100
    ) -> List[Tuple[int, int, int]]:
        """
        Extract dominant colors using K-means clustering.

        Args:
            image: RGB image array
            mask: Optional binary mask (1 = include, 0 = exclude)
            n_colors: Number of dominant colors to extract
            min_pixels: Minimum number of pixels required

        Returns:
            List of RGB tuples representing dominant colors
        """
        # Apply mask if provided
        if mask is not None:
            pixels = image[mask == 1]
        else:
            pixels = image.reshape(-1, 3)

        # Check if we have enough pixels
        if len(pixels) < min_pixels:
            warnings.warn(f"Only {len(pixels)} pixels available for color extraction")
            return []

        # Perform K-means clustering
        kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
        kmeans.fit(pixels)

        # Get cluster centers (dominant colors)
        colors = kmeans.cluster_centers_.astype(int)

        # Sort by frequency (most common first)
        labels = kmeans.labels_
        counts = np.bincount(labels)
        sorted_indices = np.argsort(-counts)

        return [tuple(colors[i]) for i in sorted_indices]

    def process_image(
        self,
        image_source: Union[str, np.ndarray],
        n_colors: int = 3,
        is_url: bool = False
    ) -> Tuple[List[Tuple[int, int, int]], np.ndarray, np.ndarray]:
        """
        Complete pipeline: load → segment → extract colors.

        Args:
            image_source: File path, URL, or numpy array
            n_colors: Number of dominant colors to extract
            is_url: True if image_source is a URL

        Returns:
            Tuple of (dominant_colors, original_image, mask)
        """
        # Load image
        if isinstance(image_source, str):
            if is_url:
                image = self.load_image_from_url(image_source)
            else:
                image = self.load_image(image_source)
        else:
            image = image_source

        # Segment garment using SAM2
        mask = self.segment_garment_sam2(image)

        # Extract dominant colors
        dominant_colors = self.extract_dominant_colors(image, mask, n_colors)

        return dominant_colors, image, mask

    def visualize_extraction(
        self,
        image: np.ndarray,
        mask: Optional[np.ndarray],
        colors: List[Tuple[int, int, int]],
        save_path: Optional[str] = None
    ):
        """
        Visualize segmentation and extracted colors.

        Args:
            image: Original RGB image
            mask: Binary mask (or None)
            colors: List of dominant colors
            save_path: Optional path to save visualization
        """
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3 if mask is not None else 2, figsize=(15, 5))

        # Original image
        axes[0].imshow(image)
        axes[0].set_title('Original Image')
        axes[0].axis('off')

        # Masked image (if mask exists)
        if mask is not None:
            masked = image.copy()
            masked[mask == 0] = 255  # White background
            axes[1].imshow(masked)
            axes[1].set_title('SAM2 Segmented Garment')
            axes[1].axis('off')
            ax_colors = axes[2]
        else:
            ax_colors = axes[1]

        # Color swatches
        color_array = np.array(colors).reshape(1, -1, 3)
        ax_colors.imshow(color_array, aspect='auto')
        ax_colors.set_title(f'Dominant Colors (n={len(colors)})')
        ax_colors.axis('off')

        # Add color values as text
        for i, color in enumerate(colors):
            ax_colors.text(i, 0.5, f'RGB{color}',
                          ha='center', va='center',
                          fontsize=8, color='white' if sum(color) < 384 else 'black')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()

        plt.close()


# Example usage
if __name__ == "__main__":
    # Test with a sample image
    extractor = GarmentColorExtractor()

    # Example: process an image
    try:
        colors, img, mask = extractor.process_image('test_garment.jpg', n_colors=3)
        print(f"Extracted {len(colors)} dominant colors:")
        for i, color in enumerate(colors, 1):
            print(f"  Color {i}: RGB{color}")

        # Visualize
        extractor.visualize_extraction(img, mask, colors, 'color_extraction_result.png')
    except Exception as e:
        print(f"Example requires a test image: {e}")
